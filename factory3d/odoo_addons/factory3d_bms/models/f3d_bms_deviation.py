from odoo import api, fields, models
from odoo.exceptions import AccessError

RULES = [
    ("light_off", "Світло вимкнено в робочий час"),
    ("light_low", "Освітленість нижче норми"),
    ("light_fault", "Аварія світильників"),
    ("filter_supply", "Фільтр припливу"),
    ("filter_extract", "Фільтр витяжки"),
    ("unit_fault", "Аварія установки"),
    ("unit_off", "Установка не працює в робочий час"),
    ("cold", "Холодно в зоні"),
    ("overheat", "Перегрів приміщення"),
    ("charging_vent", "Витяжка зарядної не працює під час заряджання"),
    ("pressure", "Тиск у дільниці фасадів"),
    ("boiler_fault", "Аварія котельні"),
    ("heat_deficit", "Дефіцит тепла"),
    ("other", "Інше"),
]


class F3dBmsDeviation(models.Model):
    """M-08: журнал відхилень (епізоди сигналів модуля в стані `alarm`); веде лише крон (R-22)."""

    _name = "f3d.bms.deviation"
    _description = "Будівля: відхилення"
    _order = "started desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Відхилення", size=256, required=True)
    signal_id = fields.Many2one("f3d.signal", string="Сигнал", required=True, ondelete="cascade", index=True)
    code = fields.Char(related="signal_id.code")
    rule = fields.Selection(RULES, string="Правило", required=True, index=True)
    object_kind = fields.Selection(
        [("group", "Група освітлення"), ("panel", "Щит"), ("unit", "Установка"), ("boiler", "Котельня")],
        string="Вид об'єкта",
    )
    object_code = fields.Char(string="Об'єкт", size=32, index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання", related="signal_id.equipment_id", store=True
    )
    zone_id = fields.Many2one("f3d.zone", string="Зона", ondelete="set null")
    started = fields.Datetime(string="Початок", required=True, index=True)
    ended = fields.Datetime(string="Кінець")
    duration_min = fields.Float(string="Тривалість, хв", compute="_compute_duration", store=True, digits=(10, 1))
    state = fields.Selection(
        [("open", "Триває"), ("closed", "Завершено")], string="Стан", required=True, default="open", index=True
    )
    value = fields.Float(string="Показник", digits=(12, 2))
    threshold = fields.Float(string="Поріг", digits=(12, 2))
    unit = fields.Char(string="Одиниця", size=16)
    request_id = fields.Many2one("maintenance.request", string="Заявка", ondelete="set null")
    note = fields.Text(string="Примітка")

    def init(self):
        self.env.cr.execute(
            "CREATE INDEX IF NOT EXISTS f3d_bms_deviation_state_started_idx ON f3d_bms_deviation (state, started)"
        )
        self.env.cr.execute(
            "CREATE INDEX IF NOT EXISTS f3d_bms_deviation_signal_state_idx ON f3d_bms_deviation (signal_id, state)"
        )

    @api.depends("started", "ended")
    def _compute_duration(self):
        for rec in self:
            rec.duration_min = (rec.ended - rec.started).total_seconds() / 60.0 if rec.ended and rec.started else False

    def write(self, vals):
        if set(vals) - {"note"} and not self.env.su:
            raise AccessError("Журнал відхилень веде система; можна змінювати лише примітку.")
        return super().write(vals)
