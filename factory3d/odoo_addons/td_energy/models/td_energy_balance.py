import logging
from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.td_telemetry.tools.titles import fmt_num

from ..tools import balance as balance_tools
from ..tools import dates
from ..tools.dates import param_bool, param_float

_logger = logging.getLogger(__name__)
HOUR = timedelta(hours=1)
MAX_BACKLOG_H = 48


class F3dEnergyBalance(models.Model):
    """M-08. Погодинна перевірка балансу обліку (R-07)."""

    _name = "td.energy.balance"
    _inherit = ["td.energy.day.mixin"]
    _description = "Енергетика: баланс обліку"
    _order = "hour desc, node_id"
    _log_access = False

    node_id = fields.Many2one("td.energy.node", string="Вузол", required=True, ondelete="cascade", index=True)
    hour = fields.Datetime(string="Година (UTC)", required=True, index=True)
    day = fields.Date(string="Дата (Київ)", required=True)
    measured_kwh = fields.Float(string="Виміряно, кВт·год", digits=(12, 3))
    expected_kwh = fields.Float(string="Очікувано, кВт·год", digits=(12, 3))
    diff_kwh = fields.Float(string="Різниця, кВт·год", digits=(12, 3))
    diff_pct = fields.Float(string="Різниця, %", digits=(8, 2))
    state = fields.Selection(
        [("ok", "Норма"), ("deviation", "Відхилення"), ("skipped", "Не перевірено")],
        string="Стан",
        required=True,
        index=True,
    )
    reason = fields.Char(string="Причина", size=256)

    _f3d_energy_balance_uniq = models.Constraint("UNIQUE(node_id, hour)", "Баланс за цю годину вже є.")

    # --- крон -----------------------------------------------------------------------------------------
    @api.model
    def _cron_balance(self):
        if not param_bool(self.env, "read_enabled"):
            return 0
        now = dates.now_utc(self.env)
        last_end = dates.floor15(now - timedelta(seconds=param_float(self.env, "settle_s", 120)))
        h_max = last_end.replace(minute=0, second=0, microsecond=0) - HOUR
        last = self.sudo().search([], order="hour desc", limit=1)
        start = max(last.hour + HOUR if last else h_max - 23 * HOUR, h_max - (MAX_BACKLOG_H - 1) * HOUR)
        count = 0
        hour = start
        while hour <= h_max:
            try:
                with self.env.cr.savepoint():
                    count += len(self._td_balance_hour(hour, now))
            except Exception:
                _logger.exception("f3d_energy: баланс за %s", hour)
            hour += HOUR
        return count

    @api.model
    def _td_balance_hour(self, hour, now=None):
        """R-07 для закритої години `hour` (UTC, `[hour, hour + 1 год)`); повертає записи балансу."""
        env = self.env
        now = now or dates.now_utc(env)
        h_end = hour + HOUR
        Meter = env["td.energy.meter"].sudo()
        tol_pct = param_float(env, "balance_tol_pct", 3.0)
        tol_kwh = param_float(env, "balance_tol_kwh", 2.0)
        by_meter = {}
        for r in (
            env["td.energy.interval"]
            .sudo()
            .search_read(
                [("ts_start", ">=", hour), ("ts_start", "<", h_end)], ["meter_id", "kwh", "kwh_export", "quality"]
            )
        ):
            by_meter.setdefault(r["meter_id"][0], []).append(r)
        outage = False
        if "td.energy.outage" in env:
            outage = bool(
                env["td.energy.outage"]
                .sudo()
                .search_count([("ts_start", "<", h_end), "|", ("ts_end", "=", False), ("ts_end", ">", hour)])
            )
        meters = Meter.search([("active", "=", True), ("e_import_signal_id", "!=", False)])
        nodes = (
            env["td.energy.node"]
            .sudo()
            .search([("kind", "=", "cell"), ("cell_type", "in", ("incomer", "feeder", "cable"))])
        )
        result = self.browse()
        readings = []
        for node in nodes:
            own = meters.filtered(lambda m, n=node: m.node_id == n)[:1]
            if not own:
                continue
            if node.cell_type == "incomer":
                feeders = meters.filtered(
                    lambda m, n=node: (
                        m.node_id.kind == "cell"
                        and m.node_id.cell_type in ("feeder", "cable")
                        and m.node_id.section == n.section
                    )
                )
                extra = meters.filtered(lambda m: m.role in ("generation", "storage")) if node.section == 2 else Meter
                inputs = own | feeders | extra
            else:
                consumers = node._td_descendant_meters().filtered(
                    lambda m: m.role == "consumer" and m.e_import_signal_id
                )
                feeders = extra = Meter
                inputs = own | consumers
            reason = False
            if outage:
                state, reason = "skipped", "відключення мережі"
            elif node.cell_type != "incomer" and not consumers:
                state, reason = "skipped", "немає лічильників споживачів"
            else:
                reason = self._td_missing_reason(inputs, by_meter)
                state = "skipped" if reason else "ok"
            measured = expected = diff = pct = 0.0
            if state != "skipped":
                if node.cell_type == "incomer":
                    measured = self._td_sum(own, by_meter, net=True)
                    if node.section == 2:
                        expected = balance_tools.expected_q2(
                            [self._td_sum(m, by_meter) for m in feeders],
                            [self._td_sum(m, by_meter) for m in extra if m.model == "sun2000"],
                            sum(self._td_sum(m, by_meter) for m in extra if m.model == "tedom"),
                            sum(self._td_sum(m, by_meter) for m in extra if m.role == "storage"),
                            sum(self._td_sum(m, by_meter, field="kwh_export") for m in extra if m.role == "storage"),
                        )
                    else:
                        expected = balance_tools.expected_q1([self._td_sum(m, by_meter) for m in feeders])
                else:
                    measured = self._td_sum(own, by_meter)
                    expected = sum(self._td_sum(m, by_meter) for m in consumers)
                diff, pct, state = balance_tools.evaluate(measured, expected, tol_pct, tol_kwh)
            vals = {
                "measured_kwh": measured, "expected_kwh": expected, "diff_kwh": diff, "diff_pct": pct,
                "state": state, "reason": reason, "day": dates.to_local(hour).date(),
            }  # fmt: skip
            rec = self.sudo().search([("node_id", "=", node.id), ("hour", "=", hour)])
            if rec:
                rec.write(vals)
            else:
                rec = self.sudo().create(dict(vals, node_id=node.id, hour=hour))
            result |= rec
            if state == "skipped":
                continue
            line = node.child_ids.filtered(lambda n: n.kind == "line")[:1]
            name = line.code if line and node.cell_type != "incomer" else node.code
            prefix = "energy/cells" if node.cell_type == "incomer" else "energy/lines"
            readings.append({"code": "%s/%s/imbalance_pct" % (prefix, name), "ts": h_end, "value": round(pct, 2),
                             "q": "good"})  # fmt: skip
            if state == "deviation":
                env["td.energy.event"]._td_log(
                    "warn",
                    "balance",
                    node.code,
                    "Небаланс обліку %s: %s %% (%s проти %s кВт·год за %s–%s)"
                    % (
                        name,
                        fmt_num(pct, 2),
                        fmt_num(measured, 1),
                        fmt_num(expected, 1),
                        dates.to_local(hour).strftime("%H:%M"),
                        dates.to_local(h_end).strftime("%H:%M"),
                    ),
                    ts=now,
                    node=node,
                    dedup_min=60,
                )
            elif state == "ok":  # W1 R-25: наступна година в нормі — відкриті події `balance` вузла вирішено
                env["td.energy.event"]._td_auto_resolve("balance", node=node)
        if not env.context.get("td_backfill_mute"):  # R-36: історія не пише показань імбалансу
            env["td.signal"].sudo()._td_energy_put(readings)
        return result

    @api.model
    def _td_sum(self, meters, by_meter, net=False, field="kwh"):
        total = 0.0
        for m in meters:
            for r in by_meter.get(m.id, []):
                total += r[field] - (r["kwh_export"] if net else 0.0)
        return total

    @api.model
    def _td_missing_reason(self, meters, by_meter):
        parts = []
        for m in meters.sorted("code"):
            rows = by_meter.get(m.id, [])
            missing = sum(1 for r in rows if r["quality"] == "missing")
            if missing:
                word = "інтервал" if missing == 1 else ("інтервали" if missing in (2, 3, 4) else "інтервалів")
                parts.append("%s (%d %s)" % (m.code, missing, word))
            elif len(rows) < 4:
                parts.append("%s (немає інтервалів)" % m.code)
        if not parts:
            return False
        text = "немає даних: " + ", ".join(parts[:4]) + (" …" if len(parts) > 4 else "")
        return text[:256]
