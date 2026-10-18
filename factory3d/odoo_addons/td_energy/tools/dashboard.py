"""W1-A: збирання відповіді Пульту (`get_pult`, R-27, R-28), списку тривог (`get_alarms`) і бічних блоків (R-41).

`Pult` рахує лише запитані частини; помилка однієї частини не ламає решту (розд. 11 SPEC).
"""

import logging
from datetime import timedelta
from functools import cached_property

from odoo import fields
from odoo.exceptions import UserError

from . import dates, forecast, sld
from . import tariff as tariff_tools
from .dates import param_float
from .sld import fmt, rnd

_logger = logging.getLogger(__name__)

PERIODS = ("now", "shift", "day", "month")
PARTS = ("kpis", "sld", "profile", "alarms", "side", "advice")
MONTHS = ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень",
          "жовтень", "листопад", "грудень"]  # fmt: skip
OPEN_STATES = ("active", "acked")
LEVEL_UI = {"bad": "alarm", "warn": "warn", "info": "info"}
COLLECTOR_STATE = {"online": "на зв'язку", "offline": "не на зв'язку", "never": "ще не підключався"}
SUBTITLE = (
    "Меблеве підприємство · ввід 10 кВ · T1 і T2 по %s кВА · ГРЩ 0,4 кВ, дві секції · договірна потужність %s кВт"
)


def rel_time(ts, now):
    """R-30 п. 13: сьогодні — `HH:MM`, вчора — «учора HH:MM», раніше — `DD.MM HH:MM` (Київ)."""
    if not ts:
        return None
    local, today = dates.to_local(ts), dates.local_day(now)
    if local.date() == today:
        return local.strftime("%H:%M")
    if local.date() == today - timedelta(days=1):
        return "учора " + local.strftime("%H:%M")
    return local.strftime("%d.%m %H:%M")


def iso(dt):
    return fields.Datetime.to_string(dt) if dt else None


def _round1(arr):
    return [None if v is None else round(v, 1) for v in arr]


class Pult:
    def __init__(self, env, period="now", hooks=None):
        if period not in PERIODS:
            raise UserError(env._("Невідомий період: %s.", period))
        self.env, self.period, self.hooks = env, period, hooks
        self.sudo = env(su=True)
        self.now = dates.now_utc(env)
        self.cost = env.user.has_group("td_energy.group_td_energy_cost")
        self.manager = env.user.has_group("td_energy.group_td_energy_manager")
        self.snap = sld.Snap(self.sudo, self.now)
        self.today = dates.local_day(self.now)
        self.day0, self.day1 = dates.local_day_bounds(self.today)
        self.cur = dates.floor15(self.now)
        self.now_slot = forecast.day_start_slot(self.now)
        self.snap.contract_kw = self.contract_kw

    # --- спільні вхідні дані ----------------------------------------------------------------------------
    @cached_property
    def tariff(self):
        return self.sudo["td.energy.tariff"]._f3d_tariff_at(self.now)

    @cached_property
    def contract_kw(self):
        return self.tariff.contract_kw or 0.0

    @cached_property
    def zones(self):
        return self.tariff.zone_ids.sorted("sequence") if self.tariff else []

    def price_at(self, local_dt):
        zone = tariff_tools.zone_for(local_dt, self.zones) if self.zones else None
        return zone.price if zone is not None else 0.0

    @cached_property
    def price_now(self):
        return self.price_at(dates.to_local(self.now))

    @cached_property
    def fact(self):
        return forecast.slot_table(self.env.cr, self.day0, min(self.day1, self.cur))

    @cached_property
    def arrays(self):
        return forecast.day_arrays(self.fact)

    @cached_property
    def typical(self):
        return forecast.typical_day(
            self.env.cr,
            self.today,
            param_float(self.env, "forecast_weeks", 8),
            param_float(self.env, "forecast_min_days", 3),
        )

    @cached_property
    def live(self):
        v = self.snap.v
        return {"cons": v("energy/totals/p_now"), "pv": v("infra/totals/pv_now"), "grid": v("infra/totals/grid_kw")}

    @cached_property
    def fc(self):
        cons, pv, _net = self.arrays
        return forecast.forecast(self.typical, pv, self.now_slot, self.live["cons"], self.live["pv"], self.live["grid"])

    @cached_property
    def partial(self):
        """Поточний неповний слот: Σ delta(cur, now) вводів (R-27)."""
        if self.now <= self.cur:
            return 0.0
        Meter, total = self.sudo["td.energy.meter"], 0.0
        for row in self.snap.meter_rows:
            if row["role"] != "incomer":
                continue
            meter = Meter.browse(row["id"])
            imp, _q = meter._f3d_counter_series(self.cur, self.now).delta(self.cur, self.now)
            exp = 0.0
            if meter.e_export_signal_id:
                exp, _q = meter._f3d_counter_series(self.cur, self.now, export=True).delta(self.cur, self.now)
            total += (imp or 0.0) - (exp or 0.0)
        return total

    @cached_property
    def window(self):
        """R-27: вікно періоду `(start, label_kwh, label_peak, subtitle_time)` у UTC."""
        local = dates.to_local(self.now)
        if self.period == "shift":
            start = dates.shift_start(self.now, self.sudo["td.energy.interval"]._f3d_shift_hours())
            hhmm = dates.to_local(start).strftime("%H:%M")
            return start, "З мережі за зміну (з %s)" % hhmm, "Пік зміни"
        if self.period == "month":
            start = dates.to_utc(local.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None))
            return start, "З мережі за %s" % MONTHS[local.month - 1], "Пік місяця"
        if self.period == "day":
            return self.day0, "Прогноз на добу", "Пік доби з прогнозом"
        return self.day0, "З мережі сьогодні", "Пік доби (15 хв)"

    @cached_property
    def window_net(self):
        """Слоти вікна: `[(ts_start, net_kwh, price)]` вводів до поточного слота (виключно)."""
        start = self.window[0]
        table = self.fact if start == self.day0 else forecast.slot_table(self.env.cr, start, self.cur)
        return [(ts, row["net"], row["price"] or 0.0) for ts, row in sorted(table.items()) if row["net"] is not None]

    @cached_property
    def energy(self):
        """R-27 п. 1–3: імпорт, експорт, вартість, пік вікна (факт; `day` — з прогнозом)."""
        imp = exp = cost = 0.0
        peak_kw, peak_ts = None, None
        for ts, net, price in self.window_net:
            imp += max(0.0, net)
            exp += max(0.0, -net)
            cost += max(0.0, net) * price
            if peak_kw is None or net * 4 > peak_kw:
                peak_kw, peak_ts = net * 4, ts
        part = max(0.0, self.partial)
        imp += part
        cost += part * self.price_now
        return {"import": imp, "export": exp, "cost": cost, "peak_kw": peak_kw, "peak_ts": peak_ts}

    def forecast_extra(self):
        """`(кВт·год, вартість, пік кВт, слот піку)` прогнозної частини доби або `None`."""
        _cons_fc, grid_fc, _k = self.fc
        if grid_fc is None:
            return None
        base = dates.to_local(self.day0)
        kwh = cost = 0.0
        peak, peak_slot = None, None
        for s in range(self.now_slot + 1, forecast.SLOTS):
            g = grid_fc[s]
            if g is None:
                continue
            kwh += max(0.0, g) * forecast.SLOT_H
            cost += max(0.0, g) * forecast.SLOT_H * self.price_at(base + timedelta(minutes=15 * s))
            if peak is None or g > peak:
                peak, peak_slot = g, s
        return kwh, cost, peak, peak_slot

    # --- відповідь -------------------------------------------------------------------------------------
    @cached_property
    def data_state(self):
        snap = self.snap
        no_total = snap.v("energy/totals/p_now") is None
        no_incomers = snap.v("energy/cells/Q1/p_now") is None and snap.v("energy/cells/Q2/p_now") is None
        if no_total and no_incomers:
            return "stale"
        lines = [n for n in snap.nodes.values() if n["kind"] == "line"]
        if any(snap.v("energy/lines/%s/p_now" % n["code"]) is None for n in lines):
            return "partial"
        return "ok"

    def meta(self):
        snap = self.snap
        ts = snap.ts("energy/totals/p_now")
        tf = snap.by_code.get("T1")
        meta = {
            "now": iso(self.now),
            "now_local": dates.to_local(self.now).strftime("%H:%M"),
            "period": self.period,
            "data_state": self.data_state,
            "age_s": int((self.now - ts).total_seconds()) if ts else None,
            "subtitle": SUBTITLE % (fmt(tf["rating_kva"]) if tf else "1000", fmt(self.contract_kw)),
            "contract_kw": rnd(self.contract_kw),
            "refresh_s": int(param_float(self.env, "pult_refresh_s", 30)),
            "control_available": self.sudo["td.energy.advice"]._td_control_available(),
            "capabilities": {"ack": self.manager, "take": self.manager, "outage_plan": self.manager, "report": False},
        }
        if self.cost:
            meta["tariff_uah"] = round(self.price_now, 2)
            meta["capabilities"]["cost"] = True
        return meta

    def kpis(self):
        v, snap = self.snap.v, self.snap
        stale = self.data_state == "stale"
        contract = self.contract_kw
        grid_kw, export_kw = v("infra/totals/grid_kw"), v("infra/totals/export_kw")
        load_kw, pv = v("energy/totals/p_now"), v("infra/totals/pv_now")
        warn = snap.cos_warn
        sections = [v("energy/sections/S%d/cos_phi" % s) for s in (1, 2)]
        label_energy, label_peak = self.window[1], self.window[2]
        energy = self.energy
        kwh, cost, peak_kw, peak_ts = energy["import"], energy["cost"], energy["peak_kw"], energy["peak_ts"]
        if self.period == "day":
            extra = self.forecast_extra()
            if extra is None:
                label_energy, label_peak = "З мережі сьогодні", "Пік доби (15 хв)"
            else:
                kwh, cost = kwh + extra[0], cost + extra[1]
                if extra[2] is not None and (peak_kw is None or extra[2] > peak_kw):
                    peak_kw = extra[2]
                    peak_ts = self.day0 + timedelta(minutes=15 * extra[3])
        note = None
        if peak_kw is not None and peak_ts is not None:
            local = dates.to_local(peak_ts)
            when = (
                ("%s о %s" % (local.strftime("%d.%m"), local.strftime("%H:%M")))
                if self.period == "month"
                else ("о %s" % local.strftime("%H:%M"))
            )
            pct = rnd(peak_kw / contract * 100) if contract else None
            note = "%s · %s %% договірної" % (when, pct) if pct is not None else when
        e = {"label": label_energy, "kwh": None if stale else rnd(kwh)}
        if self.cost:
            e["cost_uah"] = None if stale else rnd(cost)
            e["price_uah"] = round(self.price_now, 2)
        out = {
            "grid": {
                "kw": rnd(grid_kw) if grid_kw is not None else None,
                "pct": rnd(grid_kw / contract * 100) if grid_kw is not None and contract else None,
                "reserve_kw": rnd(contract - grid_kw) if grid_kw is not None and contract else None,
                "export_kw": rnd(export_kw) if export_kw is not None else None,
            },
            "load": {
                "kw": rnd(load_kw) if load_kw is not None else None,
                "pv_share_pct": min(100, rnd(pv / load_kw * 100)) if pv is not None and load_kw else None,
                "chp_state": snap.t("infra/chp/state"),
            },
            "energy": e,
            "peak": {"label": label_peak, "kw": None if stale or peak_kw is None else rnd(peak_kw), "note": note},
            "generation": {
                "pv_kw": rnd(pv) if pv is not None else None,
                "pv_pct_kwp": rnd(pv / snap.pv_kwp * 100) if pv is not None and snap.pv_kwp else None,
                "bess_soc_pct": rnd(v("infra/totals/bess_soc")) if v("infra/totals/bess_soc") is not None else None,
                "bess_kw": rnd(v("infra/totals/bess_kw")) if v("infra/totals/bess_kw") is not None else None,
                "genset": self.hooks._td_genset_summary() if self.hooks is not None else None,
            },
            "cos_phi": {
                "plant": _r2(v("energy/totals/cos_phi")),
                "sections": [_r2(c) for c in sections],
                "target": param_float(self.env, "cos_phi_target", 0.95),
                "warn": warn,
                "alarm": snap.cos_alarm,
                "low_sections": [s for s, c in enumerate(sections, 1) if c is not None and c < warn],
            },
        }
        return out

    def sld_part(self):
        snap = self.snap
        Node = self.sudo["td.energy.node"]
        nodes = []
        for row in sorted(snap.sld_rows(), key=lambda r: (r["sld_y"], r["sld_x"], r["code"])):
            extra = self.hooks._td_node_facts_extra(Node.browse(row["id"])) if self.hooks is not None else []
            parent = snap.visible_parent(row) if row["sld_shape"] in sld.SHOWN_SHAPES else None
            nodes.append(
                {
                    "code": row["code"],
                    "label": row["sld_label"] or row["name"],
                    "shape": row["sld_shape"],
                    "x": row["sld_x"],
                    "y": row["sld_y"],
                    "w": row["sld_w"],
                    "h": row["sld_h"],
                    "state": snap.state(row),
                    "lines": snap.lines(row),
                    "title": row["name"],
                    "facts": snap.facts(row, extra),
                    "card": row["kind"] in sld.CARD_KINDS,
                    "anchor": parent["code"] if parent else None,
                }
            )
        return {"canvas": [1320, 452], "nodes": nodes, "edges": snap.edges()}

    def profile_part(self):
        cons, pv, net = self.arrays
        slot = self.now_slot
        live = self.live
        cons_arr = list(cons)
        pv_arr = list(pv)
        grid_arr = [None if n is None else max(0.0, n) for n in net]
        for s in range(slot, forecast.SLOTS):
            cons_arr[s] = pv_arr[s] = grid_arr[s] = None
        cons_arr[slot], pv_arr[slot], grid_arr[slot] = live["cons"], live["pv"], live["grid"]
        cons_fc, grid_fc, _k = self.fc
        peak_kw, peak_idx = None, None
        for s, n in enumerate(net):
            if s < slot and n is not None and (peak_kw is None or n > peak_kw):
                peak_kw, peak_idx = n, s
        profile = {
            "step_min": 15,
            "now_slot": slot,
            "contract_kw": rnd(self.contract_kw),
            "cons": _round1(cons_arr),
            "grid": _round1(grid_arr),
            "pv": _round1(pv_arr),
            "cons_fc": _round1(cons_fc) if cons_fc is not None else [None] * forecast.SLOTS,
            "grid_fc": _round1(grid_fc) if grid_fc is not None else [None] * forecast.SLOTS,
            "peak": {"kw": rnd(peak_kw) if peak_kw is not None else None, "slot": peak_idx},
            "forecast_days_used": self.typical["days_used"],
        }
        today = self._today_energy()
        extra = forecast.forecast_energy(grid_fc, slot)
        foot = {
            "forecast_kwh": None if extra is None else rnd(today["import"] + extra),
            "export_kwh": rnd(today["export"]),
            "imbalance": self._imbalance(),
        }
        return {"profile": profile, "foot": foot}

    def _today_energy(self):
        """Імпорт/експорт від 00:00 Київ до зараз (незалежно від `period`)."""
        if self.window[0] == self.day0:
            return self.energy
        imp = exp = 0.0
        for _ts, row in self.fact.items():
            if row["net"] is not None:
                imp += max(0.0, row["net"])
                exp += max(0.0, -row["net"])
        return {"import": imp + max(0.0, self.partial), "export": exp}

    def _imbalance(self):
        Balance = self.sudo["td.energy.balance"]
        hour_start = dates.floor15(self.now).replace(minute=0)
        rows = Balance.search(
            [("node_id.code", "in", ("Q1", "Q2")), ("state", "in", ("ok", "deviation")), ("hour", "<", hour_start)],
            order="hour desc, id desc",
            limit=4,
        )
        if not rows:
            return None
        last = rows.filtered(lambda r: r.hour == rows[0].hour)
        best = max(last, key=lambda r: abs(r.diff_pct))
        local = dates.to_local(best.hour)
        end = dates.to_local(best.hour + timedelta(hours=1))
        return {
            "pct": round(best.diff_pct, 1),
            "hour": "%s–%s" % (local.strftime("%H:00"), end.strftime("%H:00")),
            "tol_pct": param_float(self.env, "balance_tol_pct", 3.0),
        }

    def alarms_part(self):
        return alarms(self.env, self.snap, self.now, limit=None, scope="all")

    def advice_part(self):
        return self.env["td.energy.advice"].get_open()

    def side_part(self):
        return {"top": self._top(), "mo": self._mo(), "maint": self._maint()}

    # --- R-41: найбільші споживачі, енергія на виробництво, ТО й відключення -----------------------------
    def _top(self, limit=6):
        rows = []
        for n in self.snap.nodes.values():
            if n["kind"] != "consumer":
                continue
            kw = self.snap.v("energy/consumers/%s/p_now" % n["code"])
            if kw is not None and kw > 0:
                rows.append({"code": n["code"], "name": n["name"], "kw": rnd(kw)})
        rows.sort(key=lambda r: (-r["kw"], r["code"]))
        return rows[:limit]

    def _mo(self, limit=5):
        env = self.sudo
        Alloc = env["td.energy.alloc"]
        domain = [("day", "=", self.today)]
        groups = Alloc._read_group(
            domain + [("production_id", "!=", False), ("kind", "in", ("direct", "shared"))],
            ["production_id"],
            ["kwh:sum", "cost:sum"],
        )
        pools = Alloc._read_group(domain + [("kind", "=", "shared")], [], ["kwh:sum"])
        total = self._today_energy()["import"]
        rows = []
        for production, kwh, cost in sorted(groups, key=lambda g: -g[1])[:limit]:
            row = {
                "name": production.name,
                "product": production.product_id.display_name or "",
                "kwh": rnd(kwh),
                "share_pct": round(kwh / total * 100, 1) if total else None,
            }
            if self.cost:
                row["cost_uah"] = rnd(cost)
            rows.append(row)
        return {"rows": rows, "pools_kwh": rnd(pools[0][0] or 0.0) if pools else 0}

    def _maint(self, limit=8):
        env, now = self.sudo, self.now
        rows = []
        equipment = [n["equipment"] for n in self.snap.nodes.values() if n["equipment"]]
        Request = env["maintenance.request"]
        requests = Request.search(
            [
                ("stage_id.done", "=", False),
                "|",
                ("equipment_id", "in", equipment),
                ("td_signal_id.module", "=", "energy"),
            ],
            order="create_date desc, id desc",
            limit=limit,
        )
        for r in requests:
            origin = "заявка з тривоги" if r.td_origin in ("threshold", "stale", "meter") else "заявка"
            rows.append(
                {
                    "title": r.name,
                    "sub": "%s · %s" % (origin, dates.to_local(r.create_date).strftime("%H:%M")),
                    "state": r.stage_id.name,
                    "kind": "request",
                    "id": r.id,
                }
            )
        for plan in env["td.energy.outage.plan"].search(
            [("state", "in", ("draft", "pending", "approved")), ("end", ">=", now)], order="start", limit=limit
        ):
            label = plan.node_id.sld_label or plan.node_id.name
            sub = "%s · %s" % (plan._td_when().replace(" · ", " "), _orders_text(plan))
            rows.append(
                {
                    "title": "%s · планове відключення" % label,
                    "sub": sub,
                    "state": dict(plan._fields["state"].selection)[plan.state],
                    "kind": "outage",
                    "id": plan.id,
                }
            )
        warn_days = int(param_float(self.env, "verify_warn_days", 30))
        limit_date = self.today + timedelta(days=warn_days)
        for meter in env["td.energy.meter"].search(
            [("active", "=", True), ("next_verification", "!=", False), ("next_verification", "<=", limit_date)],
            order="next_verification",
            limit=limit,
        ):
            rows.append(
                {
                    "title": "Повірка лічильника %s" % meter.code,
                    "sub": "до %s" % meter.next_verification.strftime("%d.%m.%Y"),
                    "state": "Заплановано",
                    "kind": "verification",
                    "id": meter.id,
                }
            )
        return rows[:limit]

    # --- збирання --------------------------------------------------------------------------------------
    def _handlers(self):
        return {
            "kpis": lambda: {"kpis": self.kpis()},
            "sld": lambda: {"sld": self.sld_part()},
            "profile": self.profile_part,
            "alarms": lambda: {"alarms": self.alarms_part()},
            "side": self.side_part,
            "advice": lambda: {"advice": self.advice_part()},
        }

    def build(self, parts=None):
        """Усі частини під одним savepoint (2 запити замість 12); збій — повтор по частинах (R-11, розд. 11)."""
        wanted = [p for p in PARTS if parts is None or p in parts]
        try:
            with self.env.cr.savepoint():
                handlers = self._handlers()
                out = {"meta": self.meta()}
                for part in wanted:
                    out.update(handlers[part]())
                return out
        except Exception:
            _logger.exception("td_energy: Пульт — повтор по частинах")
        retry = Pult(self.env, self.period, hooks=self.hooks)
        handlers = retry._handlers()
        out = {"meta": retry.meta()}
        for part in wanted:
            try:
                with self.env.cr.savepoint():
                    out.update(handlers[part]())
            except Exception as exc:  # частина не ламає решту
                _logger.exception("td_energy: частина Пульту %s", part)
                out[ERROR_KEYS[part]] = {"error": str(exc) or exc.__class__.__name__}
        return out


ERROR_KEYS = {"kpis": "kpis", "sld": "sld", "profile": "profile", "alarms": "alarms", "side": "top", "advice": "advice"}


def _r2(x):
    return None if x is None else round(x, 2)


def _orders_text(plan):
    if plan.state == "approved":
        return "%d замовлень перенесено" % plan.production_count
    status = {"draft": "чернетка", "pending": "на узгодженні"}.get(plan.state, "")
    return "%d замовлень, %s" % (plan.production_count, status)


# --- тривоги (R-24, R-25, R-37) ---------------------------------------------------------------------------
def diag_text(env, event, now):
    """D-07: стан джерела лічильника події `kind='meter'` (джерело, `host:port`, unit, колектор, остання відповідь)."""
    meter = env["td.energy.meter"].sudo().search([("code", "=", event.code)], limit=1)
    source = meter.source_id
    if not meter or not source:
        return None
    params = source.params or {}
    last_ok = source.last_ok or meter.last_ts
    since = "немає відповіді з %s" % dates.to_local(last_ok).strftime("%H:%M:%S") if last_ok else "ще не відповідало"
    collector = source.collector_id
    coll = ""
    if collector:
        coll = " · колектор %s %s" % (collector.code, COLLECTOR_STATE.get(collector.state, collector.state))
    cell = meter.code[3:] if meter.code.startswith("PM-") else meter.code
    return "Джерело %s (%s:%s, unit %s): %s%s · перевірте лінію й комірку %s." % (
        source.code, params.get("host", "—"), params.get("port", "—"), params.get("unit", "—"), since, coll, cell,
    )  # fmt: skip


def _alarm_item(env, rec, now):
    uid = env.uid
    action_code = rec.action_code
    actions = []
    if action_code == "diag":
        actions.append({"code": "diag", "label": "Діагностика"})
    elif action_code == "request":
        actions.append({"code": "request", "label": "Заявка ТО"})
    if rec.kind == "meter" and rec.state != "resolved" and not (rec.code or "").startswith("VERIFY-"):
        if not rec.request_id:
            actions.append({"code": "ticket", "label": "Створити заявку"})
    request = rec.request_id
    return {
        "id": rec.id,
        "level": LEVEL_UI.get(rec.level, rec.level),
        "time": rel_time(rec.ts, now),
        "title": rec.title or rec.text,
        "detail": rec.detail or "",
        "state": rec.state,
        "acked_by": rec.acked_by.name or None,
        "acked_by_me": bool(rec.acked_by) and rec.acked_by.id == uid,
        "acked_at": rel_time(rec.acked_at, now),
        "assigned": rec.assigned_user_id.name or None,
        "taken_by_me": bool(rec.assigned_user_id) and rec.assigned_user_id.id == uid,
        "node_code": rec.node_id.code or None,
        "request_id": request.id or None,
        "request_assignable": bool(request) and not request.user_id,
        "actions": actions,
        "diag": diag_text(env, rec, now) if action_code == "diag" else None,
    }


def alarms(env, snap, now, limit=None, scope="all"):
    """API-06: `{"active_count", "items": [alarm…]}`; порядок: active bad, active warn, acked, далі info/resolved."""
    if scope not in ("all", "active", "mine"):
        scope = "all"
    sudo = env(su=True)
    Event = sudo["td.energy.event"]
    limit = int(limit) if limit else int(param_float(env, "alarm_list_limit", 8))
    since = now - timedelta(hours=24)
    domain = ["|", ("state", "in", OPEN_STATES), ("ts", ">=", since)]
    if scope == "active":
        domain = [("state", "in", OPEN_STATES)]
    elif scope == "mine":
        domain = [("assigned_user_id", "=", env.uid), ("state", "in", OPEN_STATES)]
    events = Event.search(domain, order="ts desc, id desc", limit=300)

    severity = {"bad": 0, "warn": 1, "info": 2}

    def rank(rec):
        """Єдиний порядок: активні, підтверджені (аварія раніше за увагу), решта; усередині — час спадно."""
        group = {"active": 0, "acked": 1}.get(rec.state, 2)
        return group, severity.get(rec.level, 3) if group < 2 else 0

    ordered = sorted(events, key=rank)  # стабільне: усередині групи — за ts спадно
    active_count = Event.search_count([("state", "=", "active")])
    items = [_alarm_item(env, rec, now) for rec in ordered[:limit]]
    return {"active_count": active_count, "items": items}


# --- мобільний екран (R-37) -------------------------------------------------------------------------------
SCHEME_KINDS = ("input", "transformer", "line", "generator", "storage", "ats")


def _bess_text(kw):
    if kw is None:
        return "—"
    if kw > 1:
        return "Заряджається %s кВт" % fmt(kw)
    if kw < -1:
        return "Розряджається %s кВт" % fmt(-kw)
    return "Очікування, 0 кВт"


def mobile(pult, tab=None):
    """API-12: `{"meta", "state"?, "alarms"?, "scheme"?}` — лише запитані вкладки (`tab=None` — усі три)."""
    env, snap, hooks = pult.env, pult.snap, pult.hooks
    tabs = ("state", "alarms", "scheme") if tab is None else (tab,)
    out = {"meta": {k: pult.meta()[k] for k in ("now", "now_local", "data_state", "age_s", "refresh_s")}}
    meta = pult.meta()
    out["meta"]["control_available"] = meta["control_available"]
    out["meta"]["capabilities"] = {k: v for k, v in meta["capabilities"].items() if k in ("ack", "take", "cost")}
    if "state" in tabs:
        k = pult.kpis()
        summary = hooks._td_genset_summary() if hooks is not None else None
        ats = "ДГУ" if snap.v("infra/ats/position") == 3 else "мережа"
        text = "ДГУ · АВР: %s" % ats
        if summary:
            text = "ДГУ · %s" % summary["label"]
            if summary.get("fuel_pct") is not None:
                text += ", паливо %s %%" % summary["fuel_pct"]
            text += " · АВР: %s" % ats
        out["state"] = {
            "contract_kw": meta["contract_kw"],
            "grid_kw": k["grid"]["kw"],
            "pct": k["grid"]["pct"],
            "pv_kw": k["generation"]["pv_kw"],
            "bess": {
                "soc_pct": k["generation"]["bess_soc_pct"],
                "kw": k["generation"]["bess_kw"],
                "text": _bess_text(snap.v("infra/totals/bess_kw")),
            },
            "genset_ats": {"text": text},
            "cos_phi": {"plant": k["cos_phi"]["plant"], "low_sections": k["cos_phi"]["low_sections"]},
        }
    if "alarms" in tabs:
        data = alarms(env, snap, pult.now, limit=50, scope="all")
        active = [i for i in data["items"] if i["state"] in OPEN_STATES]
        infos = env(su=True)["td.energy.event"].search(
            [("level", "=", "info"), ("ts", ">=", pult.day0)], order="ts desc, id desc", limit=20
        )
        out["alarms"] = {
            "active_count": data["active_count"],
            "active": active,
            "info_today": [{"time": dates.to_local(e.ts).strftime("%H:%M"), "text": e.title or e.text} for e in infos],
            "advice": env["td.energy.advice"].get_open(),
        }
    if "scheme" in tabs:
        rows = []
        for row in sorted(snap.sld_rows(), key=lambda r: (r["sld_y"], r["sld_x"], r["code"])):
            show = row["kind"] in SCHEME_KINDS or (row["kind"] == "cell" and row["cell_type"] == "pfc")
            if not show:
                continue
            lines = snap.lines(row)
            rows.append(
                {
                    "code": row["code"],
                    "name": row["sld_label"] or row["name"],
                    "value": lines[1] if len(lines) > 1 else "",
                    "state": snap.state(row),
                }
            )
        out["scheme"] = rows
    return out


# --- «Генерація й резерв» (R-38) --------------------------------------------------------------------------
def _kpi(label, value, unit=""):
    return {"label": label, "value": value, "unit": unit}


def generation_cards(pult):
    """Базові картки СЕС, КГУ, BESS, АВР (без `td_genset`); міст додає «ДГУ» перевизначенням хука."""
    snap = pult.snap
    v, t = snap.v, snap.t

    def node(code):
        return snap.by_code.get(code)

    cards = []
    pv = node("PV-INV")
    if pv:
        _cons, pv_arr, _net = pult.arrays
        peak = (
            max((x, s) for s, x in enumerate(pv_arr) if x is not None) if any(x is not None for x in pv_arr) else None
        )
        total = sum(1 for c in snap.rows if sld.PV_STATUS_RE.match(c)) or 8
        alive = sum(1 for c in snap.fresh if sld.PV_STATUS_RE.match(c))
        today = [x[0] for c, x in snap.fresh.items() if sld.PV_TODAY_RE.match(c) and x[0] is not None]
        pv_now = v("infra/totals/pv_now")
        cards.append(
            {
                "code": "PV-INV",
                "title": pv["sld_label"] or pv["name"],
                "kind": "pv",
                "state": snap.state(pv),
                "kpis": [
                    _kpi("Потужність", fmt(pv_now), "кВт"),
                    _kpi(
                        "% піку СЕС",
                        fmt(pv_now / snap.pv_kwp * 100) if pv_now is not None and snap.pv_kwp else "—",
                        "%",
                    ),
                    _kpi("Виробіток сьогодні", fmt(sum(today)) if today else "—", "кВт·год"),
                    _kpi("Інверторів на зв'язку", "%d з %d" % (alive, total)),
                ],
                "facts": ["Пік сьогодні %s кВт о %02d:%02d" % (fmt(peak[0]), peak[1] // 4, peak[1] % 4 * 15)]
                if peak
                else [],
                "node_code": "PV-INV",
                "can_3d": bool(pv["equipment"]),
            }
        )
    chp = node("CHP")
    if chp:
        cards.append(
            {
                "code": "CHP",
                "title": chp["sld_label"] or chp["name"],
                "kind": "chp",
                "state": snap.state(chp),
                "kpis": [
                    _kpi("Стан", sld.CHP_STATES.get(t("infra/chp/state"), "—")),
                    _kpi("Потужність", fmt(v("infra/totals/chp_kw")), "кВт"),
                    _kpi("Мотогодини", fmt(v("infra/chp/hours")), "год"),
                    _kpi("Витрата газу", fmt(v("infra/chp/gas_m3h"), 1), "м³/год"),
                ],
                "facts": [chp["note"]] if chp["note"] else [],
                "node_code": "CHP",
                "can_3d": bool(chp["equipment"]),
            }
        )
    bess = node("BESS")
    if bess:
        kw = v("infra/totals/bess_kw")
        mode = "заряд" if (kw or 0) > 1 else "розряд" if (kw or 0) < -1 else "очікування"
        cards.append(
            {
                "code": "BESS",
                "title": bess["sld_label"] or bess["name"],
                "kind": "bess",
                "state": snap.state(bess),
                "kpis": [
                    _kpi("Заряд", fmt(v("infra/totals/bess_soc")), "%"),
                    _kpi("Потужність", fmt(kw), "кВт"),
                    _kpi("Режим", mode),
                ],
                "facts": ["Резерв на відключення мережі %s %%" % fmt(snap.bess_reserve)],
                "node_code": "BESS",
                "can_3d": bool(bess["equipment"]),
            }
        )
    ats = node("ATS-1")
    if ats:
        critical = [
            v("energy/%s/%s/p_now" % ("consumers" if n["kind"] == "consumer" else "lines", n["code"]))
            for n in snap.nodes.values()
            if n["is_critical"] and n["kind"] in ("consumer", "line")
        ]
        facts = ["Критичне навантаження %s кВт" % fmt(sum(c for c in critical if c is not None))] if critical else []
        cards.append(
            {
                "code": "ATS-1",
                "title": ats["sld_label"] or ats["name"],
                "kind": "ats",
                "state": snap.state(ats),
                "kpis": [
                    _kpi("Положення", "ДГУ" if v("infra/ats/position") == 3 else "мережа"),
                    _kpi("Режим АВР", t("infra/ats/mode") or "—"),
                    _kpi(
                        "Джерело 1 / 2",
                        "%s / %s" % (t("infra/ats/src1_state") or "—", t("infra/ats/src2_state") or "—"),
                    ),
                ],
                "facts": facts,
                "node_code": "ATS-1",
                "can_3d": bool(ats["equipment"]),
            }
        )
    return cards
