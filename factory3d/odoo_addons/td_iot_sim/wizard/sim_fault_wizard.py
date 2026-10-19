from odoo import fields, models
from odoo.exceptions import ValidationError


class F3dSimFaultWizard(models.TransientModel):
    _name = "td.sim.fault.wizard"
    _description = "Поставити збій пристрою"

    device_id = fields.Many2one("td.sim.device", string="Пристрій", required=True)
    reason = fields.Selection(
        [
            ("generic", "Загальний збій"),
            ("spindle", "Шпиндель/привід"),
            ("emergency", "Аварійна кнопка"),
            ("power", "Втрата живлення"),
            ("comm", "Втрата зв'язку"),
            ("sensor", "Датчик"),
            ("loop", "Лінія (шлейф) пожежної сигналізації"),
        ],
        string="Причина",
        default="generic",
        required=True,
    )
    note = fields.Char(string="Примітка")

    def action_confirm(self):
        self.ensure_one()
        if self.reason == "loop" and not (self.device_id.params or {}).get("lsz"):
            raise ValidationError("Причина «Лінія» — лише для зон пожежної сигналізації")
        self.device_id._set_fault(self.reason, self.note)
        return {"type": "ir.actions.act_window_close"}
