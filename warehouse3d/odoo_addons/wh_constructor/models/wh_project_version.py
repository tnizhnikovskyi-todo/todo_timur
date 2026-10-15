from odoo import fields, models

from .wh_project import iso


class WhProjectVersion(models.Model):
    _name = "wh.project.version"
    _description = "Версія проєкту конструктора складу"
    _order = "rev desc, id desc"

    project_id = fields.Many2one("wh.project", required=True, ondelete="cascade", index=True)
    rev = fields.Integer(string="Ревізія проєкту", required=True)
    data = fields.Json(string="Проєкт (JSON v2)")
    comment = fields.Char(string="Коментар")
    user_id = fields.Many2one("res.users", string="Автор", default=lambda self: self.env.user, required=True)
    date = fields.Datetime(string="Дата", default=fields.Datetime.now, required=True)

    def _summary(self):
        self.ensure_one()
        return {"id": self.id, "rev": self.rev, "comment": self.comment or "", "by": self.user_id.name, "at": iso(self.date)}

    def _prune(self, project):
        """Оставить последние N версий проекта (N — wh_constructor.max_versions, по умолчанию 50)."""
        keep = self.env["wh.project"]._max_versions()
        old = self.sudo().search([("project_id", "=", project.id)], order="rev desc, id desc", offset=keep)
        old.unlink()
