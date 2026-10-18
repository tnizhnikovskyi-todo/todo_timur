import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

CATEGORIES = [
    ("0", "Інше"),
    ("1", "Діагностика"),
    ("2", "Інформація"),
    ("3", "Попередження"),
    ("4", "Тривога"),
    ("5", "Помилка"),
]


class F3dMachineEvent(models.Model):
    _name = "f3d.machine.event"
    _description = "Верстати: подія верстата"
    _order = "ts desc, id desc"

    machine_id = fields.Many2one("f3d.machine", required=True, index=True, ondelete="cascade")
    workcenter_id = fields.Many2one("mrp.workcenter", related="machine_id.workcenter_id", store=True)
    ts = fields.Datetime(string="Час", required=True, index=True)
    kind = fields.Selection([("event", "Подія"), ("alarm", "Тривога")], required=True)
    message_id = fields.Char(string="Код", size=16, index=True)
    message_name = fields.Char(string="Назва", size=64)
    category = fields.Selection(CATEGORIES, string="Категорія", required=True)
    severity = fields.Integer(string="Важливість")
    text = fields.Char(string="Текст", size=256)
    path = fields.Char(string="Вузол", size=256)
    active = fields.Boolean(string="Активна", default=True)
    acked = fields.Boolean(string="Квитовано")
    ext_event_id = fields.Char(string="Ідентифікатор події", size=64, required=True, index=True)
    payload = fields.Json(string="Дані")
    message_rec_id = fields.Many2one(
        "f3d.machine.message", compute="_compute_message_rec", store=True, string="Довідник повідомлень"
    )
    downtime_id = fields.Many2one("f3d.downtime", ondelete="set null")

    _f3d_machine_event_uniq = models.Constraint("UNIQUE(ext_event_id)", "Подія вже записана.")

    @api.depends("message_id")
    def _compute_message_rec(self):
        Message = self.env["f3d.machine.message"]
        for rec in self:
            rec.message_rec_id = Message._f3d_match(rec.message_id)
