"""M-08 `td.energy.daily` — добові факти (W4-A): `_td_build_days`, `action_rebuild`, `_cron_daily`, `_cron_rotate`."""

import logging
import time
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy.tools import dates

from ..tools import daily as daily_tools
from ..tools import periods

_logger = logging.getLogger(__name__)

COST = "td_energy.group_td_energy_cost"
MANAGER = "td_energy.group_td_energy_manager"
MAX_DAYS = 400
CRON_BUDGET_S = 20
ROTATE_BUDGET_S = 30
UNIQUE_INDEXES = (
    (
        "td_energy_daily_node_uniq",
        "(day, COALESCE(resource_id, 0), node_id) WHERE node_id IS NOT NULL",
    ),
    (
        "td_energy_daily_scope_uniq",
        "(day, scope, COALESCE(resource_id, 0)) WHERE node_id IS NULL",
    ),
)  # fmt: skip


class TdEnergyDaily(models.Model):
    _name = "td.energy.daily"
    _description = "Енергетика: добовий факт"
    _inherit = ["td.energy.day.mixin"]
    _log_access = False
    _order = "day desc, scope, node_id"

    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    scope = fields.Selection(
        [("plant", "Завод"), ("node", "Вузол"), ("resource", "Ресурс")], string="Рівень", required=True, index=True
    )
    resource_id = fields.Many2one("td.energy.resource", string="Ресурс")
    node_id = fields.Many2one("td.energy.node", string="Вузол", index=True)
    area_id = fields.Many2one("td.energy.area", string="Ділянка", index=True)
    qty = fields.Float(string="Кількість", digits=(16, 3))
    cost = fields.Float(string="Вартість, ₴", digits=(14, 2), groups=COST)
    co2_kg = fields.Float(string="CO₂, кг", digits=(14, 2))
    import_qty = fields.Float(string="Імпорт, кВт·год")
    export_qty = fields.Float(string="Експорт, кВт·год")
    gen_pv_qty = fields.Float(string="СЕС, кВт·год")
    gen_chp_qty = fields.Float(string="КГУ, кВт·год")
    shift1_qty = fields.Float(string="Зміна 1, кВт·год")
    shift2_qty = fields.Float(string="Зміна 2, кВт·год")
    off_qty = fields.Float(string="Поза змінами, кВт·год")
    cost_s1 = fields.Float(string="Вартість, зміна 1", digits=(14, 2), groups=COST)
    cost_s2 = fields.Float(string="Вартість, зміна 2", digits=(14, 2), groups=COST)
    cost_off = fields.Float(string="Вартість поза змінами", digits=(14, 2), groups=COST)
    direct_s1 = fields.Float(string="Прямі, зміна 1")
    direct_s2 = fields.Float(string="Прямі, зміна 2")
    direct_off = fields.Float(string="Прямі поза змінами")
    plate_s1 = fields.Float(string="Плити, зміна 1")
    plate_s2 = fields.Float(string="Плити, зміна 2")
    plate_off = fields.Float(string="Плити поза змінами")
    minutes = fields.Float(string="Хвилин роботи")
    idle_qty = fields.Float(string="Простій, кВт·год")
    quality = fields.Selection([("ok", "Повні"), ("partial", "Неповні")], string="Якість", default="ok")
    built_at = fields.Datetime(string="Побудовано", required=True)

    def init(self):
        cr, table = self.env.cr, self._table
        tools.sql.create_index(cr, "td_energy_daily_day_scope_idx", table, ["day", "scope"])
        tools.sql.create_index(cr, "td_energy_daily_day_area_idx", table, ["day", "area_id"])
        tools.sql.create_index(cr, "td_energy_daily_node_day_idx", table, ["node_id", "day"])
        for name, definition in UNIQUE_INDEXES:
            cr.execute("CREATE UNIQUE INDEX IF NOT EXISTS %s ON %s %s" % (name, table, definition))

    # --- доступ ---------------------------------------------------------------------------------------
    @api.model
    def _td_check_build(self):
        if not (self.env.is_superuser() or self.env.user.has_group(MANAGER)):
            raise AccessError(_("Перераховувати добові факти може лише енергетик."))

    # --- API-13 ---------------------------------------------------------------------------------------
    @api.model
    def _td_build_days(self, days):
        """R-02: побудувати факти за `days` (київські дати); `{"days": n, "rows": n, "seconds": f}`."""
        self._td_check_build()
        days = sorted({fields.Date.to_date(d) for d in days})
        if len(days) > MAX_DAYS:
            raise UserError(_("Не більше 400 діб."))
        return daily_tools.build(self.sudo().env, days, now=dates.now_utc(self.env))

    @api.model
    def action_rebuild(self, date_from, date_to):
        """API-13: перерахунок діб `[date_from, date_to]` (до 400); право «Енергетик»."""
        self._td_check_build()
        date_from, date_to = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        count = (date_to - date_from).days + 1
        if count < 1:
            raise UserError(_("Кінець діапазону раніше початку."))
        if count > MAX_DAYS:
            raise UserError(_("Не більше 400 діб."))
        return self._td_build_days([date_from + timedelta(days=i) for i in range(count)])

    # --- крони ----------------------------------------------------------------------------------------
    @api.model
    def _cron_daily(self):
        """R-02: сьогодні — завжди; вчора — до `daily_close_h` (місцевий час) або без `plant`; догон `catchup_days`."""
        if not dates.param_bool(self.env, "read_enabled"):
            return {}
        started = time.monotonic()
        now = dates.now_utc(self.env)
        local = dates.to_local(now)
        today = local.date()
        close_h = periods.param_int(self.env, "daily_close_h", 2)
        catchup = max(1, periods.param_int(self.env, "catchup_days", 14))
        env = self.sudo().env
        env.cr.execute(
            "SELECT day FROM td_energy_daily WHERE scope = 'plant' AND day >= %s AND day < %s",
            (today - timedelta(days=catchup), today),
        )
        have = {row[0] for row in env.cr.fetchall()}
        yesterday = today - timedelta(days=1)
        first = [today]
        if local.hour < close_h or yesterday not in have:
            first.append(yesterday)
        stats = {"days": 0, "rows": 0}
        try:
            with env.cr.savepoint():
                res = daily_tools.build(env, first, now=now)
            stats["days"], stats["rows"] = res["days"], res["rows"]
        except Exception:
            _logger.exception("Енергетика: добові факти (сьогодні/вчора)")
        for back in range(2, catchup + 1):
            day = today - timedelta(days=back)
            if day in have:
                continue
            if time.monotonic() - started > CRON_BUDGET_S:
                break
            try:
                with env.cr.savepoint():
                    res = daily_tools.build(env, [day], now=now)
                stats["days"] += res["days"]
                stats["rows"] += res["rows"]
            except Exception:
                _logger.exception("Енергетика: добові факти, доба %s", day)
        return stats

    @api.model
    def _cron_rotate(self):
        """Видалити `daily`, `enpi`, `driver.value` старші за `td.energy.keep_interval_days` (≤ 30 с)."""
        now = dates.now_utc(self.env)
        cutoff = dates.local_day(now) - timedelta(days=int(dates.param_float(self.env, "keep_interval_days", 400)))
        deadline = time.monotonic() + ROTATE_BUDGET_S
        cr, removed = self.env.cr, 0
        self.env.flush_all()
        for table in ("td_energy_daily", "td_energy_enpi", "td_energy_driver_value"):
            while time.monotonic() < deadline:
                cr.execute(
                    "DELETE FROM %s WHERE id IN (SELECT id FROM %s WHERE day < %%s LIMIT 50000)" % (table, table),
                    (cutoff,),
                )
                removed += cr.rowcount
                if cr.rowcount < 50000:
                    break
        self.env.invalidate_all()
        return removed
