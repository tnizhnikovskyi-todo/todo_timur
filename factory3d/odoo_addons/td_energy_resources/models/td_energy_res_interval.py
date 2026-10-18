"""M-06 `td.energy.res.interval` — 15-хв ряд неелектричних ресурсів і `metric='react'` (FR-05, FR-07, FR-18)."""

import logging
import time
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError

from odoo.addons.td_energy.tools import bus, dates
from odoo.addons.td_energy.tools.dates import param_bool, param_float

from ..tools import backfill_resources, build

_logger = logging.getLogger(__name__)

COST_GROUP = "td_energy.group_td_energy_cost"
ROTATE_BATCH = 10000


class TdEnergyResInterval(models.Model):
    _name = "td.energy.res.interval"
    _inherit = ["td.energy.day.mixin"]
    _description = "Енергетика: 15-хвилинний інтервал ресурсу"
    _order = "ts_start desc, meter_id"
    _log_access = False
    _rec_name = "ts_start"

    meter_id = fields.Many2one("td.energy.meter", string="Лічильник", required=True, ondelete="cascade", index=True)
    resource_id = fields.Many2one(related="meter_id.resource_id", store=True, index=True)
    point_id = fields.Many2one(related="meter_id.point_id", store=True, index=True)
    metric = fields.Selection(
        [("main", "Основна"), ("react", "Реактивна")], string="Метрика", required=True, default="main"
    )
    ts_start = fields.Datetime(string="Початок (UTC)", required=True, index=True)
    ts_end = fields.Datetime(string="Кінець (UTC)", required=True)
    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    hour_local = fields.Integer(string="Година (Київ)", required=True)
    qty = fields.Float(string="Кількість (од. ресурсу)", digits=(14, 3))
    rate_avg = fields.Float(string="Середня швидкість", digits=(12, 3))
    kwh_eq = fields.Float(string="кВт·год-еквівалент", digits=(14, 3))
    price = fields.Float(string="Ціна", digits=(12, 4), groups=COST_GROUP)
    cost = fields.Float(string="Вартість, ₴", digits=(14, 2), groups=COST_GROUP)
    quality = fields.Selection(
        [
            ("measured", "Виміряно"),
            ("estimated", "Оцінено"),
            ("interpolated", "Інтерпольовано"),
            ("missing", "Немає даних"),
        ],
        string="Якість",
        required=True,
        default="measured",
        index=True,
    )
    built_at = fields.Datetime(string="Побудовано", required=True)
    is_backfill = fields.Boolean(string="Синтетичні дані", default=False, index=True, readonly=True)

    _td_res_interval_uniq = models.Constraint(
        "UNIQUE(meter_id, metric, ts_start)", "Інтервал ресурсу для лічильника вже є."
    )

    def init(self):
        tools.sql.create_index(self.env.cr, "td_energy_res_interval_day_res_idx", self._table, ["day", "resource_id"])
        tools.sql.create_index(
            self.env.cr, "td_energy_res_interval_point_ts_idx", self._table, ["point_id", "ts_start"]
        )

    # --- R-05: крон -----------------------------------------------------------------------------------
    @api.model
    def _cron_build(self):
        """R-05: слоти всіх активних неелектричних лічильників і `react` вводів; потім `bus.tick('kpi')`."""
        if not param_bool(self.env, "read_enabled"):
            return 0
        now = dates.now_utc(self.env)
        total = 0
        try:
            with self.env.cr.savepoint():
                total = build.SlotBuilder(self.env, now).build_all()
        except Exception:
            _logger.exception("td_energy_resources: побудова інтервалів ресурсів")
        bus.tick(self.env, "kpi")
        return total

    @api.model
    def _cron_rotate(self):
        """R-05 п. 6: видалити `ts_start` старші за `td.energy.keep_interval_days` пакетами 10 000, не довше 60 с."""
        now = dates.now_utc(self.env)
        deadline = time.monotonic() + 60
        cutoff = now - timedelta(days=int(param_float(self.env, "keep_interval_days", 400)))
        deleted = 0
        while time.monotonic() < deadline:
            self.env.cr.execute(
                "DELETE FROM td_energy_res_interval WHERE id IN "
                "(SELECT id FROM td_energy_res_interval WHERE ts_start < %s LIMIT %s)",
                (cutoff, ROTATE_BATCH),
            )
            deleted += self.env.cr.rowcount
            if self.env.cr.rowcount < ROTATE_BATCH:
                break
        self.env.invalidate_all()
        return deleted

    # --- R-22: backfill ---------------------------------------------------------------------------------
    @api.model
    def _td_backfill(self, days=90, until=None, seed=20261018, purge=False, resources=None):
        """API-08: історія ресурсів за `days` діб (стик з електричним backfill W1); лише адміністратор."""
        if not (self.env.is_superuser() or self.env.user.has_group("td_factory3d.group_td_admin")):
            raise AccessError(_("Генерувати історію може лише адміністратор."))
        env = self.env(su=True, context=dict(self.env.context, tracking_disable=True))
        return backfill_resources.run(env, days=days, until=until, seed=seed, purge=purge, resources=resources)

    @api.model
    def _td_backfill_extra(self, plan, seed, since, until):
        """Хук (R-22, R-B5): додаткові ряди backfill. У ядрі порожній; міст `td_energy_resources_bms` генерує тепло.
        Рядки пише через `plan.write(rows)` (статистика рахується сама); повертає `{"meter_ids": [id, …]}` —
        лічильники, що отримали ряди (для `res_last_interval_start`) — або `{}`."""
        return {}
