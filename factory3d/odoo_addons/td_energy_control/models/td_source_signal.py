"""M-38: тип джерела `energy_ctl`, модуль `energy_control`, заборона керування системами безпеки (R-60).

Валідатори типу джерела реєструються ПІД ЧАС ІМПОРТУ модуля (A-40, Q-30; рішення менеджера): td_telemetry не змінюється.
Вид події `control` для `td.energy.event` додається тут же.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.td_telemetry.tools import address as address_tools

FORBIDDEN_PREFIXES = (
    "fire/", "evacuation/", "sprinklers/", "smoke/", "lightning/", "access/", "workcenters/", "security/", "yard/",
)  # fmt: skip
FORBIDDEN_SOURCE_MODULES = ("fire_safety", "access", "machine_connect")


def _params_energy_ctl(params):
    """Параметри `energy_ctl`: `engine` {tick_s 1…10, config_poll_s 5…60}, `doc`; секрети — загальна перевірка."""
    errors = []
    for key in params:
        if key not in ("engine", "doc"):
            errors.append("%s: невідомий ключ" % key)
    engine = params.get("engine")
    if engine is not None:
        if not isinstance(engine, dict):
            return errors + ["engine: має бути об'єкт"]
        for key, (lo, hi) in (("tick_s", (1, 10)), ("config_poll_s", (5, 60))):
            val = engine.get(key)
            if val is None:
                continue
            if isinstance(val, bool) or not isinstance(val, int) or not lo <= val <= hi:
                errors.append("engine.%s: ціле %d…%d" % (key, lo, hi))
        for key in engine:
            if key not in ("tick_s", "config_poll_s"):
                errors.append("engine.%s: невідомий ключ" % key)
    return errors


address_tools.PARAMS_VALIDATORS["energy_ctl"] = _params_energy_ctl
address_tools.ADDRESS_VALIDATORS["energy_ctl"] = lambda address: []


class TdSource(models.Model):
    _inherit = "td.source"

    type = fields.Selection(
        selection_add=[("energy_ctl", "Керування енергетикою (збирач)")], ondelete={"energy_ctl": "cascade"}
    )
    module = fields.Selection(
        selection_add=[("energy_control", "Керування енергетикою")], ondelete={"energy_control": "set default"}
    )


class TdSignal(models.Model):
    _inherit = "td.signal"

    module = fields.Selection(
        selection_add=[("energy_control", "Керування енергетикою")], ondelete={"energy_control": "set default"}
    )

    @api.constrains("code", "module", "source_id")
    def _check_td_energy_control_forbidden(self):
        """R-60 п.2 (а): сигнал `energy_control` не може керувати системами безпеки."""
        for rec in self:
            if rec.module != "energy_control":
                continue
            code = rec.code or ""
            if code.startswith(FORBIDDEN_PREFIXES) or (rec.source_id.module in FORBIDDEN_SOURCE_MODULES):
                raise ValidationError(_("Сигнал %s: керування цією системою заборонене.", code))


class TdEnergyEvent(models.Model):
    _inherit = "td.energy.event"

    kind = fields.Selection(selection_add=[("control", "Керування")], ondelete={"control": "cascade"})
