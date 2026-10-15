import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ENERGY_UNIT = "кВт·год"
POWER_UNIT = "кВт"


class F3dEnergyMeter(models.Model):
    """M-02. Методи `_f3d_counter_series`, `_f3d_kwh`, `_f3d_update_state` (R-03, R-21) додає W2."""

    _name = "f3d.energy.meter"
    _description = "Енергетика: лічильник"
    _inherit = ["mail.thread"]
    _order = "node_id, code"
    _rec_name = "code"
    _rec_names_search = ["code", "name"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")

    code = fields.Char(string="Код", size=32, required=True, index=True, copy=False)
    name = fields.Char(string="Назва", size=128)
    active = fields.Boolean(default=True)
    node_id = fields.Many2one("f3d.energy.node", string="Вузол", required=True, ondelete="restrict", index=True)
    model = fields.Selection(
        [
            ("pm5560", "Schneider PowerLogic PM5560"),
            ("sun2000", "Huawei SUN2000"),
            ("luna2000", "Huawei LUNA2000"),
            ("tedom", "TEDOM ProCon"),
            ("other", "Інший"),
        ],
        required=True,
        default="pm5560",
    )
    role = fields.Selection(
        [
            ("incomer", "Ввід"),
            ("feeder", "Фідер"),
            ("consumer", "Споживач"),
            ("generation", "Генерація"),
            ("storage", "Накопичувач"),
        ],
        string="Роль",
        required=True,
    )
    source_id = fields.Many2one("f3d.source", string="Джерело", ondelete="set null")
    p_signal_id = fields.Many2one("f3d.signal", string="Сигнал потужності, кВт", ondelete="set null")
    e_import_signal_id = fields.Many2one(
        "f3d.signal",
        string="Лічильник енергії (споживання / вироблення), кВт·год",
        domain="[('kind', '=', 'counter')]",
        ondelete="set null",
    )
    e_export_signal_id = fields.Many2one(
        "f3d.signal",
        string="Лічильник енергії (віддача), кВт·год",
        domain="[('kind', '=', 'counter')]",
        ondelete="set null",
    )
    counter_offset = fields.Float(
        string="Поправка після скидань (імпорт)", digits=(16, 3), default=0, readonly=True
    )
    counter_offset_export = fields.Float(
        string="Поправка після скидань (експорт)", digits=(16, 3), default=0, readonly=True
    )
    data_state = fields.Selection(
        [
            ("no_data", "Ще не було даних"),
            ("ok", "Норма"),
            ("stale", "Немає даних"),
            ("gap", "Пропуск"),
            ("reset", "Скидання лічильника"),
        ],
        string="Стан даних",
        default="no_data",
        readonly=True,
        index=True,
        tracking=True,
    )
    data_state_since = fields.Datetime(string="Стан з", readonly=True)
    last_interval_start = fields.Datetime(string="Останній побудований інтервал", readonly=True)
    last_value = fields.Float(related="e_import_signal_id.last_value", string="Показник, кВт·год")
    last_ts = fields.Datetime(related="e_import_signal_id.last_ts", string="Час показника")
    p_now = fields.Float(related="p_signal_id.last_value", string="Потужність, кВт")
    max_kw = fields.Float(
        string="Максимальна потужність, кВт",
        digits=(10, 1),
        required=True,
        default=10,
        help="Правдоподібність показань після скидання лічильника (R-03 п. 2).",
    )
    ct_ratio = fields.Char(string="Трансформатори струму", size=16)
    unit_id = fields.Integer(related="node_id.unit_id", string="Modbus unit")
    company_id = fields.Many2one(related="node_id.company_id", store=True)
    note = fields.Text(string="Примітка")

    _f3d_energy_meter_code_uniq = models.Constraint("UNIQUE(code)", "Код лічильника має бути унікальним.")

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError(
                    _("Код лічильника %s: великі латинські літери, цифри, дефіс (напр. PM-SAW-1).", rec.code)
                )

    @api.constrains("e_import_signal_id", "e_export_signal_id", "p_signal_id")
    def _check_signals(self):
        for rec in self:
            for signal in (rec.e_import_signal_id, rec.e_export_signal_id):
                if not signal:
                    continue
                if signal.kind != "counter":
                    raise ValidationError(
                        _("Лічильник %s: сигнал енергії має бути накопичувальним (counter).", rec.code)
                    )
                if signal.unit != ENERGY_UNIT:
                    raise ValidationError(_("Лічильник %s: сигнал енергії має бути в кВт·год.", rec.code))
            if rec.p_signal_id and rec.p_signal_id.unit != POWER_UNIT:
                raise ValidationError(_("Лічильник %s: потужність має бути в кВт.", rec.code))

    def action_view_intervals(self):
        """Графік 15-хв профілю за останні 2 доби (M-03)."""
        self.ensure_one()
        since = fields.Datetime.subtract(fields.Datetime.now(), hours=48)
        return {
            "type": "ir.actions.act_window",
            "name": _("Профіль"),
            "res_model": "f3d.energy.interval",
            "view_mode": "graph,pivot,list",
            "domain": [("meter_id", "=", self.id), ("ts_start", ">=", since)],
        }
