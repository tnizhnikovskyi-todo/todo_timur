"""R-30: вузьке місце заводу — збір даних з ORM, відповідь аналітики, плитка й вузли `flow` для 3D.

Розрахунок — у `tools/bottleneck.py` (чисті функції); тут лише читання `mrp.workorder`, журналів і OEE верстатів.
"""

import logging
import re
from datetime import datetime, timezone

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..tools import bottleneck as bn
from .td_machine import KYIV, local

_logger = logging.getLogger(__name__)

DEMO_CLOCK = "td.viewer.demo_clock"  # демо-годинник «Переглядача» (час за Києвом): на демо-базі він і є «зараз»
CLOCK_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
GROUPS = ("area", "workcenter")
DEFAULT_PERIOD = "day"
VERDICT_LABELS = {
    "growing": "черга росте",
    "queue": "є черга",
    "load": "черги немає: вузьке місце не виражене",
    "low": "завантаження нижче %d %%: імовірне, не виражене" % round(bn.LOAD_MIN * 100),
}


def _node(row, bottleneck, period):
    """Вузол `workcenters[код].flow` для ділянки (R-30 п. 5): показники рядка рейтингу."""
    return {
        "station": row["name"],
        "key": row["key"],
        "load": None if row["load"] is None else round(row["load"], 3),
        "queue": row["queue"],
        "queue_delta": row["queue_delta"],
        "wait_min": None if row["wait_min"] is None else round(row["wait_min"], 1),
        "output": round(row["output"], 1),
        "rank": row["rank"],
        "bottleneck": row["key"] == bottleneck,
        "period": period,
    }


class TdBottleneck(models.AbstractModel):
    _name = "td.bottleneck"
    _description = "Верстати: вузьке місце"

    # --- час, станції ------------------------------------------------------------------------------
    @api.model
    def _td_now(self):
        """«Зараз» аналітики: демо-годинник `td.viewer.demo_clock` (якщо заданий і валідний), інакше реальний час."""
        clock = self.env["ir.config_parameter"].sudo().get_param(DEMO_CLOCK)
        if clock and CLOCK_RE.match(clock):
            try:
                naive = datetime.strptime(clock, "%Y-%m-%d %H:%M")
                return naive.replace(tzinfo=KYIV).astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                _logger.warning("%s невалідний (%r): ігнорується", DEMO_CLOCK, clock)
        return fields.Datetime.now()

    @api.model
    def _td_station_of(self, workcenter, group_by):
        """`(ключ, назва)` ділянки РЦ: перша мітка-дільниця (`tag_ids`) або сам РЦ (без мітки і для `workcenter`)."""
        tag = workcenter.tag_ids.sorted("id")[:1] if group_by == "area" else workcenter.tag_ids.browse()
        if tag:
            return "area:%s" % tag.id, tag.name
        return "wc:%s" % workcenter.id, workcenter.name

    # --- збір даних ----------------------------------------------------------------------------------
    @api.model
    def _td_collect(self, t0, t1, group_by="area", company=None):
        """`(stations, orders)` для `tools.bottleneck.analyze` за вікно `[t0, t1]` (naive UTC)."""
        env = self.env
        company = company or env.company
        stations, station_of = {}, {}

        def station(wc):
            if wc.id not in station_of:
                key, name = self._td_station_of(wc, group_by)
                station_of[wc.id] = key
                stations.setdefault(key, {"name": name, "codes": [], "machines": 0, "run_min": 0.0, "avail_min": 0.0})
            return station_of[wc.id]

        # завантаження: робота / доступний час за OEE верстата (журнал станів, а без нього журнал часу)
        for machine in env["td.machine"].sudo().search([("active", "=", True), ("company_id", "=", company.id)]):
            st = stations[station(machine.workcenter_id.sudo())]
            oee = machine._td_oee(t0, t1)
            st["machines"] += 1
            st["run_min"] += oee["run_min"]
            st["avail_min"] += oee["ppt_min"]
            if machine.code:
                st["codes"].append(machine.code)
        return stations, self._td_orders(t0, t1, company, station)

    @api.model
    def _td_orders(self, t0, t1, company, station):
        """Завдання МО в роботі й завершені у вікні: `ready_at` (кінець попередньої), `start_at`, `finish_at`."""
        WO = self.env["mrp.workorder"].sudo()
        base = [
            ("state", "!=", "cancel"),
            ("production_id.state", "not in", ("draft", "cancel")),
            ("production_id.company_id", "=", company.id),
        ]
        scope = WO.search(base + ["|", ("state", "!=", "done"), ("date_finished", ">=", t0)])
        wos = WO.search(
            [("production_id", "in", scope.production_id.ids), ("state", "!=", "cancel")],
            order="production_id, sequence, id",
        )
        starts, ends = self._td_actuals(wos)
        start_at, finish_at = {}, {}
        for wo in wos:
            start = starts.get(wo.id) or (wo.date_start if wo.state in ("progress", "done") else None)
            finish = None
            if wo.state == "done":
                finish = ends.get(wo.id) or wo.date_finished or None
                start = start or finish
            start_at[wo.id], finish_at[wo.id] = start or None, finish
        orders = []
        for production in wos.production_id:
            steps = wos.filtered(lambda w, p=production: w.production_id == p)
            linear = not any(w.blocked_by_workorder_ids for w in steps)
            for i, wo in enumerate(steps):
                preds = steps[i - 1 : i] if linear and i else wo.blocked_by_workorder_ids
                preds = preds.filtered(lambda p: p.state != "cancel")
                if preds:
                    done = [finish_at.get(p.id) for p in preds]
                    ready = max(done) if all(done) else None
                else:
                    ready = production.date_start or production.create_date
                orders.append(
                    {
                        "id": wo.id,
                        "mo": production.id,
                        "seq": wo.sequence,
                        "station": station(wo.workcenter_id.sudo()),
                        "ready_at": ready,
                        "start_at": start_at[wo.id],
                        "finish_at": finish_at[wo.id],
                        "qty": wo.qty_produced if wo.state == "done" else 0.0,
                    }
                )
        return orders

    @api.model
    def _td_actuals(self, wos):
        """`({wo_id: перший старт}, {wo_id: останнє завершення})` за журналом станів (робота, налагодження) і часу."""
        starts, ends = {}, {}
        env = self.env

        def feed(rows):
            for row in rows:
                wo_id = row["workorder_id"][0]
                if row["date_start"] and (wo_id not in starts or row["date_start"] < starts[wo_id]):
                    starts[wo_id] = row["date_start"]
                if row["date_end"] and (wo_id not in ends or row["date_end"] > ends[wo_id]):
                    ends[wo_id] = row["date_end"]

        fields_ = ["workorder_id", "date_start", "date_end"]
        feed(env["mrp.workcenter.productivity"].sudo().search_read([("workorder_id", "in", wos.ids)], fields_))
        feed(
            env["td.machine.state.log"]
            .sudo()
            .search_read([("workorder_id", "in", wos.ids), ("state", "in", ("working", "setup"))], fields_)
        )
        return starts, ends

    # --- розрахунок й відповіді --------------------------------------------------------------------------
    @api.model
    def _td_analyze(self, period=DEFAULT_PERIOD, group_by="area", boost_pct=bn.BOOST_DEFAULT, date_to=None):
        """Повний розрахунок (`tools.bottleneck.analyze`) + `period`, `group_by`, `date_from`, `date_to`, `stations`."""
        period = period if period in bn.PERIODS else DEFAULT_PERIOD
        group_by = group_by if group_by in GROUPS else "area"
        t0, t1 = bn.period_window(period, date_to or self._td_now())
        stations, orders = self._td_collect(t0, t1, group_by)
        res = bn.analyze(stations, orders, t0, t1, boost_pct)
        res.update(period=period, group_by=group_by, date_from=t0, date_to=t1, stations=stations)
        return res

    @api.model
    def _td_can_see(self):
        return bool(self.env.su or self.env.user.has_group("td_factory3d.group_td_user"))

    @api.model
    def td_report(self, period=DEFAULT_PERIOD, group_by="area", boost_pct=bn.BOOST_DEFAULT):
        """Аналітика «Вузьке місце» (R-30 п. 2): рейтинг ділянок, вузьке місце, «що якщо». Лише `group_td_user`."""
        if not self._td_can_see():
            raise AccessError(_("Аналітика «Вузьке місце» доступна користувачам «Завод 3D»."))
        try:
            boost = min(max(float(boost_pct), 0.0), 500.0)
        except (TypeError, ValueError):
            boost = bn.BOOST_DEFAULT
        res = self._td_analyze(period, group_by, boost)
        rows = [
            {
                "key": r["key"],
                "rank": r["rank"],
                "name": r["name"],
                "machines": r["machines"],
                "load": None if r["load"] is None else round(r["load"], 3),
                "queue": r["queue"],
                "queue_delta": r["queue_delta"],
                "wait_min": None if r["wait_min"] is None else round(r["wait_min"], 1),
                "output": round(r["output"], 1),
                "done": r["done"],
                "capacity": None if r["capacity"] is None else round(r["capacity"], 1),
                "bottleneck": r["bottleneck"],
            }
            for r in res["rows"]
        ]
        wi = res["what_if"]
        return {
            "period": res["period"],
            "group_by": res["group_by"],
            "boost_pct": boost,
            "date_from": local(res["date_from"], "%d.%m.%Y %H:%M"),
            "date_to": local(res["date_to"], "%d.%m.%Y %H:%M"),
            "rows": rows,
            "bottleneck": next((r for r in rows if r["bottleneck"]), False),
            "verdict": res["verdict"],
            "verdict_label": VERDICT_LABELS.get(res["verdict"], ""),
            "hint": res["hint"],
            "gain_pct": round(wi["gain_pct"], 1) if wi else None,
            "load_min": bn.LOAD_MIN,
        }

    @api.model
    def td_tile(self):
        """Плитка «Огляд верстатів»: `{name, queue, load, queue_delta, verdict}` вузького місця або `False`."""
        if not self._td_can_see():
            return False
        res = self._td_analyze()
        row = next((r for r in res["rows"] if r["bottleneck"]), None)
        if not row:
            return False
        return {
            "name": row["name"],
            "queue": row["queue"],
            "queue_delta": row["queue_delta"],
            "load": None if row["load"] is None else round(row["load"], 3),
            "verdict": res["verdict"],
        }

    @api.model
    def _td_flow_nodes(self):
        """R-30 п. 5: `{код верстата: вузол flow}` для payload переглядача (для вузького місця ще й підказка)."""
        res = self._td_analyze()
        nodes = {}
        bottleneck, rows = res["bottleneck"], res["rows"]
        by_key = {r["key"]: r for r in rows}
        for row in rows:
            for code in row["codes"]:
                nodes[code] = _node(row, bottleneck, res["period"])
        if bottleneck:
            upstream = by_key.get(res["upstream"]) if res["upstream"] else None
            extra = {
                "verdict": res["verdict"],
                "hint": res["hint"],
                "codes": by_key[bottleneck]["codes"],
                "prev": upstream["codes"] if upstream else [],
            }
            for code in by_key[bottleneck]["codes"]:
                nodes[code].update(extra)
        return nodes
