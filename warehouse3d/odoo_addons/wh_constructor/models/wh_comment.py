from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .wh_project import iso

GROUP_DESIGN = "wh_constructor.group_wh_design"
MAX_TEXT = 2000


class WhComment(models.Model):
    """Комментарий на объекте проекта (D-19, I3, W-18): заметка или задача «перевірити на місці» на узле склада или объекте здания.
    Читает и пишет группа «перегляд», решает (и удаляет чужие) — «проєктування». Права проверяются в методах api_*; запись идёт с правами сервера."""
    _name = "wh.comment"
    _description = "Коментар на об'єкті конструктора складу"
    _order = "id desc"

    project_id = fields.Many2one("wh.project", required=True, ondelete="cascade", index=True)
    warehouse_key = fields.Char(string="Склад у застосунку", required=True, help="Поле id складу в проєкті v2.")
    node = fields.Char(string="Об'єкт", required=True, help="Id вузла дерева складу або «b:<id>» для об'єкта будівлі.")
    label = fields.Char(string="Підпис об'єкта")
    kind = fields.Selection([("note", "Нотатка"), ("task", "Задача: перевірити на місці")], required=True, default="note")
    text = fields.Text(string="Текст", required=True)
    state = fields.Selection([("open", "Відкрита"), ("done", "Вирішена")], required=True, default="open", index=True)
    user_id = fields.Many2one("res.users", string="Автор", required=True, default=lambda self: self.env.user, ondelete="restrict")
    date = fields.Datetime(string="Дата", required=True, default=fields.Datetime.now)
    done_user_id = fields.Many2one("res.users", string="Вирішив(ла)", ondelete="set null")
    done_date = fields.Datetime(string="Коли вирішено")

    @api.constrains("text")
    def _check_text(self):
        for c in self:
            if not (c.text or "").strip() or len(c.text) > MAX_TEXT:
                raise ValidationError(_("Текст коментаря — від 1 до %s символів.", MAX_TEXT))

    def _dict(self):
        self.ensure_one()
        return {"id": str(self.id), "wh": self.warehouse_key, "node": self.node, "label": self.label or "", "kind": self.kind, "text": self.text,
                "by": self.user_id.name, "at": iso(self.date), "state": self.state,
                "doneBy": self.done_user_id.name or "", "doneAt": iso(self.done_date) or ""}

    @api.model
    def _design(self):
        return self.env.user.has_group(GROUP_DESIGN)

    def _mine(self, project_key, comment_id):
        """Комментарий проекта по id (чужого проекта или несуществующий — None)."""
        project = self.env["wh.project"]._find(project_key)
        c = self.sudo().browse(int(comment_id or 0)).exists()
        return c if (project and c and c.project_id == project) else self.browse()

    # ------------------------------------------------------------ API для контроллеров
    @api.model
    def api_list(self, key):
        project = self.env["wh.project"]._find(key)  # правило записей компании — на самом проекте
        if not project:
            return []
        return [c._dict() for c in self.sudo().search([("project_id", "=", project.id)], order="id")]

    @api.model
    def api_add(self, key, warehouse_key, node, text, kind="note", label=None):
        """Добавить комментарий (право «перегляд»: он входит в «проєктування» и «застосування»)."""
        if not self.env.user.has_group("wh_constructor.group_wh_view"):
            raise AccessError(_("Коментувати можуть користувачі з правом «Конструктор: перегляд»."))
        project = self.env["wh.project"]._find(key)
        if not project:
            raise ValidationError(_("Проєкт не знайдено."))
        if not warehouse_key or not node:
            raise ValidationError(_("Потрібні склад і об'єкт."))
        c = self.sudo().create({
            "project_id": project.id, "warehouse_key": str(warehouse_key)[:80], "node": str(node)[:600], "label": (label or "")[:200],
            "kind": kind if kind in ("note", "task") else "note", "text": (text or "").strip(), "user_id": self.env.user.id})
        return c._dict()

    @api.model
    def api_resolve(self, key, comment_id, state="done"):
        """Решить комментарий или открыть заново: только «проєктування»."""
        if not self._design():
            raise AccessError(_("Вирішувати коментарі можуть користувачі з правом «Конструктор: проєктування»."))
        c = self._mine(key, comment_id)
        if not c:
            raise ValidationError(_("Коментар не знайдено."))
        if state == "done":
            c.write({"state": "done", "done_user_id": self.env.user.id, "done_date": fields.Datetime.now()})
        else:
            c.write({"state": "open", "done_user_id": False, "done_date": False})
        return c._dict()

    @api.model
    def api_remove(self, key, comment_id):
        """Удалить: «проєктування» — любой, остальные — только свой."""
        c = self._mine(key, comment_id)
        if not c:
            raise ValidationError(_("Коментар не знайдено."))
        if not self._design() and c.user_id != self.env.user:
            raise AccessError(_("Чужі коментарі видаляють користувачі з правом «Конструктор: проєктування»."))
        c.unlink()
        return {"removed": True}
