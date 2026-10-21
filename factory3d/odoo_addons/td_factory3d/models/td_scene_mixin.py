import json
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

F3D_KIND_SELECTION = [
    ("location", "Місце зберігання"),
    ("workcenter", "Робочий центр"),
    ("equipment", "Обладнання"),
    ("employee", "Працівник"),
    ("dock", "Ворота"),
    ("zone", "Зона"),
    ("vehicle", "Транспорт"),
    ("other", "Інше"),
]


class F3dSceneMixin(models.AbstractModel):
    _name = "td.scene.mixin"
    _description = "Код сцени 3D"

    _td_kind = "other"
    _td_resolve_order = [
        "td.zone",
        "stock.location",
        "mrp.workcenter",
        "maintenance.equipment",
        "hr.employee",
        "stock.picking.batch",
    ]
    F3D_CODE_RE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")

    td_code = fields.Char(
        string="Код сцени",
        index=True,
        copy=False,
        help="Код об'єкта в 3D-моделі (glTF extras code), напр. SAW-1, FG-R1-B01-L1, DOCK-W1",
    )
    td_alias = fields.Char(
        string="Другий код сцени",
        index=True,
        copy=False,
        help="Ще один код того самого запису в 3D, якщо модель малює його двома об'єктами "
        "(ворота DOCK-W1 і майданчик UNLOAD-1)",
    )
    td_kind = fields.Selection(
        F3D_KIND_SELECTION, string="Вид у сцені", required=True, index=True, default=lambda self: self._td_kind
    )
    td_viewer_available = fields.Boolean(compute="_compute_f3d_viewer_available")
    td_is_manager = fields.Boolean(compute="_compute_is_f3d_manager")

    _f3d_code_uniq = models.Constraint("UNIQUE(td_code)", "Код сцени має бути унікальним у межах моделі.")
    _f3d_alias_uniq = models.Constraint("UNIQUE(td_alias)", "Другий код сцени має бути унікальним у межах моделі.")

    # --- compute ---
    def _compute_f3d_viewer_available(self):
        available = self._td_viewer_installed()
        for rec in self:
            rec.td_viewer_available = available

    def _compute_is_f3d_manager(self):
        is_manager = self.env.user.has_group("td_factory3d.group_td_manager")
        for rec in self:
            rec.td_is_manager = is_manager

    # --- constraints ---
    @api.constrains("td_code", "td_alias")
    def _check_f3d_codes(self):
        Model = self.with_context(active_test=False)
        for rec in self:
            code, alias = rec.td_code, rec.td_alias
            if code and (len(code) > 32 or not self.F3D_CODE_RE.match(code)):
                raise ValidationError(
                    "Код сцени %s: лише великі латинські літери, цифри й дефіси між групами "
                    "(напр. FG-R1-B01-L1)." % code
                )
            if alias and (len(alias) > 32 or not self.F3D_CODE_RE.match(alias)):
                raise ValidationError(
                    "Код сцени %s: лише великі латинські літери, цифри й дефіси між групами "
                    "(напр. FG-R1-B01-L1)." % alias
                )
            if alias and not code:
                raise ValidationError("Другий код сцени можна задати лише разом з основним.")
            if alias and alias == code:
                raise ValidationError("Другий код сцени збігається з основним.")
            for value, own in ((alias, "td_alias"), (code, "td_code")):
                if not value:
                    continue
                other = "td_code" if own == "td_alias" else "td_alias"
                clash = Model.search([(other, "=", value), ("id", "!=", rec.id)], limit=1)
                if clash:
                    raise ValidationError("Код %s уже використаний записом %s." % (value, clash.display_name))

    # --- R-04 ---
    @api.model
    def _td_check_code_rights(self, vals):
        if (
            not self.env.su
            and {"td_code", "td_alias", "td_kind"} & set(vals)
            and not self.env.user.has_group("td_factory3d.group_td_manager")
        ):
            raise AccessError("Змінювати код сцени може лише менеджер «3D Завод».")

    def write(self, vals):
        self._td_check_code_rights(vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._td_check_code_rights(vals)
        return super().create(vals_list)

    # --- API ---
    @api.model
    def search_f3d(self, code):
        if not code:
            return self.browse()
        return self.with_context(active_test=False).search(
            ["|", ("td_code", "=", code), ("td_alias", "=", code)], limit=1
        )

    @api.model
    def f3d_resolve(self, code):
        for model in self._td_resolve_order:
            # носій може ще не мати домішки (модулі збираються поетапно) — пропускаємо
            if model in self.env and hasattr(self.env[model], "search_f3d"):
                found = self.env[model].search_f3d(code)
                if found:
                    return found
        return None

    @api.model
    def f3d_resolve_all(self, code):
        result = {}
        for cls in self.env.registry.descendants(["td.scene.mixin"], "_inherit"):
            model = self.env.registry[cls] if isinstance(cls, str) else cls
            name = model._name
            if name not in self.env or self.env[name]._abstract:
                continue
            found = self.env[name].search_f3d(code)
            if found:
                result[name] = found
        return result

    def f3d_codes(self):
        self.ensure_one()
        return [c for c in (self.td_code, self.td_alias) if c]

    @api.model
    def _td_viewer_installed(self):
        return (
            self.env["ir.module.module"]
            .sudo()
            .search_count([("name", "=", "td_viewer3d"), ("state", "=", "installed")])
            > 0
        )

    def action_f3d_show(self):
        self.ensure_one()
        if not self.td_code:
            raise UserError("Запис не має коду сцени. Заповніть «Код сцени» на вкладці «3D Завод».")
        if self._td_viewer_installed():
            return {
                "type": "ir.actions.client",
                "tag": "f3d_viewer.action",
                "name": "3D Завод",
                "target": "current",
                "params": {
                    "code": self.td_code,
                    "alias": self.td_alias or False,
                    "model": self._name,
                    "res_id": self.id,
                    "kind": self.td_kind,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Модуль 3D-переглядача не встановлено",
                "message": "Установіть td_viewer3d, щоб показати %s у 3D." % self.td_code,
                "type": "warning",
                "sticky": False,
            },
        }

    @api.model
    def f3d_run_migration(self):
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError("Запускати міграцію може лише адміністратор «3D Завод».")
        from .. import hooks

        report = hooks.run_all(self.sudo().env)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "3D Завод",
                "message": "Міграцію виконано: %s" % json.dumps(report, ensure_ascii=False),
                "type": "success",
                "sticky": True,
            },
        }
