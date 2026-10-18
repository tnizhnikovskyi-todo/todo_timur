"""M-32 `td.energy.interlock` — реєстр блокувань: налаштування іменованих перевірок (`tools/interlocks.CHECKS`)."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .. import tools
from ..tools import interlocks

GUARDED = {"params", "hard", "fail_closed", "active", "where"}


class TdEnergyInterlock(models.Model):
    _name = "td.energy.interlock"
    _description = "Енергетика: блокування"
    _order = "sequence, id"

    _td_interlock_code_uniq = models.Constraint("UNIQUE(code)", "Код блокування має бути унікальним.")

    code = fields.Char(string="Код", size=32, required=True, index=True)
    name = fields.Char(string="Шаблон рядка діалогу", size=128, required=True)
    hard = fields.Boolean(string="Жорстка")
    fail_closed = fields.Boolean(string="Немає даних = небезпечно", default=True)
    where = fields.Selection(
        [("both", "Odoo і збирач"), ("odoo", "Лише Odoo"), ("collector", "Лише збирач")],
        string="Де виконується",
        default="both",
        required=True,
    )
    inputs = fields.Json(string="Входи", default=list)
    params = fields.Json(string="Пороги", default=dict)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if rec.code not in interlocks.CHECKS:
                raise ValidationError(_("Невідома перевірка %s.", rec.code))

    def _td_dict(self):
        self.ensure_one()
        return {
            "name": self.name,
            "hard": self.hard,
            "fail_closed": self.fail_closed,
            "where": self.where,
            "params": self.params or {},
            "active": self.active,
        }

    def write(self, vals):
        """R-41 п.7: пороги змінює лише адміністратор; зміна — запис журналу `interlock_param` і `bump()`."""
        if tools.is_internal(self.env) or not (GUARDED & set(vals)):
            return super().write(vals)
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Пороги блокувань змінює лише адміністратор."))
        res = super().write(vals)
        self.env["td.energy.action"]._td_log_config(
            "interlock_param", "Блокування: змінено %s" % ", ".join(self.mapped("code"))
        )
        return res
