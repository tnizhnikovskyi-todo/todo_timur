"""W1-A: R-36 — генератор історії (backfill) для демо-стенда: 15-хв інтервали за `days` діб (API-15, A-35).

Детермінований за `seed` (SHA-1 від ключа, без глобального `random`); запис по добах пакетами ≤ 5 000 рядків
`INSERT … ON CONFLICT (meter_id, ts_start) DO NOTHING` — реальні слоти не чіпаються, повтор безпечний.
"""

import hashlib
import logging
import math
import time
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError

from . import dates
from . import tariff as tariff_tools

_logger = logging.getLogger(__name__)

SLOT = timedelta(minutes=15)
BATCH = 5000
INSERT_SQL = """
INSERT INTO td_energy_interval (meter_id, node_id, role, ts_start, ts_end, day, hour_local, e_start, e_end, kwh,
    kwh_export, kw_avg, zone_id, price, cost, quality, built_at, is_backfill)
VALUES %s
ON CONFLICT (meter_id, ts_start) DO NOTHING
"""
COST_ROLES = ("incomer", "feeder", "consumer")
SHARED_ACTIVITY = ("COMPRESSOR", "DUST-1", "GANTRY-1")
SHARED_HVAC = ("RV-ALL", "AHU-1")
RV_OFFSHIFT_RATIO = 0.9
ATS_TEXT = "Тест АВР і ДГУ пройдено. Перемикання на ДГУ 8,4 с, повернення на мережу без зауважень."


def rnd(seed, *key):
    """R-36 п. 2: `hash(seed, *key) → [0, 1)` (SHA-1, перші 8 байт)."""
    digest = hashlib.sha1(("%s|%s" % (seed, "|".join(str(k) for k in key))).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2.0**64


def target_p(h, weekday):
    """R-36 п. 3: цільове навантаження заводу `P(t)`, кВт (h — місцева година, weekday: 0 = пн)."""
    if weekday == 6:
        return 210.0
    if weekday == 5:
        return 430.0 if 7 <= h < 14 else 210.0
    if h < 6.5:
        return 210.0
    if h < 7.5:
        return 210.0 + (h - 6.5) * 440.0
    if h < 12:
        return 650.0
    if h < 12.75:
        return 430.0
    if h < 16:
        return 667.0
    if h < 16.5:
        return 520.0
    if h < 22.5:
        return 560.0
    if h < 23.5:
        return 560.0 - (h - 22.5) * 350.0
    return 210.0


def sun_factor(h, doy):
    """R-36 п. 6: `sin(π(h−sr)/(ss−sr))^1,3` для `sr < h < ss`, інакше 0."""
    length = 12.0 + 4.5 * math.cos(2 * math.pi * (doy - 172) / 365.0)
    rise, set_ = 13.2 - length / 2, 13.2 + length / 2
    if not rise < h < set_:
        return 0.0
    return math.sin(math.pi * (h - rise) / (set_ - rise)) ** 1.3


class Plan:
    """Знімок мережі: лічильники за ролями, споживачі, фідери, тариф."""

    def __init__(self, env, meter_filter=None):
        Meter = env["td.energy.meter"].sudo()
        self.meters = Meter.search([("active", "=", True), ("e_import_signal_id", "!=", False)], order="code")
        self.filter = set(meter_filter) if meter_filter else None
        self.index = {m.id: i for i, m in enumerate(self.meters)}
        by_role = {}
        for m in self.meters:
            by_role.setdefault(m.role, []).append(m)
        self.consumers = by_role.get("consumer", [])
        self.feeders = by_role.get("feeder", [])
        self.incomers = sorted(by_role.get("incomer", []), key=lambda m: m.node_id.section or 0)
        self.suns = [m for m in by_role.get("generation", []) if m.model == "sun2000"]
        self.chps = [m for m in by_role.get("generation", []) if m.model == "tedom"]
        self.bess = (by_role.get("storage") or [None])[0]
        self.cons_cfg = [self._consumer_cfg(m.node_id) for m in self.consumers]
        self.feeder_members = []
        for f in self.feeders:
            path = f.node_id.parent_path or ""
            self.feeder_members.append(
                [i for i, c in enumerate(self.consumers) if (c.node_id.parent_path or "").startswith(path)]
            )
        self.pv_kwp = float(env["ir.config_parameter"].sudo().get_param("td.energy.pv_kwp", "920") or 920)
        self.tariffs = env["td.energy.tariff"].sudo().search([("active", "=", True)], order="date_from")
        self.contract_kw = (self.tariffs[-1:].contract_kw if self.tariffs else 0.0) or 800.0

    @staticmethod
    def _consumer_cfg(node):
        code, role, p = node.code, node.alloc_role, node.p_inst_kw or 0.0
        if role == "direct":
            kind = "direct"
        elif code in SHARED_ACTIVITY:
            kind = "activity"
        elif code in SHARED_HVAC:
            kind = "hvac"
        elif code.startswith("LP-"):
            kind = "light"
        else:
            kind = "overhead"
        return {
            "code": code,
            "kind": kind,
            "p": p,
            "load": p * (node.load_factor or 0.75),
            "idle": p * (node.idle_factor or 0.05),
        }

    def price_at(self, local_dt):
        """(zone_id, ціна) на місцевий час: тариф за датою, зона за днем тижня й годиною."""
        day = local_dt.date()
        for tariff in reversed(self.tariffs):
            if tariff.date_from <= day and (not tariff.date_to or tariff.date_to >= day):
                zone = tariff_tools.zone_for(local_dt, tariff.zone_ids.sorted("sequence"))
                return (zone.id, zone.price) if zone is not None else (False, 0.0)
        return False, 0.0


def _range(env, days, until):
    now = dates.now_utc(env)
    if until:
        until = dates.floor15(fields.Datetime.to_datetime(until))
    else:
        self_cr = env.cr
        self_cr.execute(
            """SELECT MIN(r.ts) FROM td_reading r JOIN td_signal s ON s.id = r.signal_id
                 JOIN td_energy_meter m ON m.e_import_signal_id = s.id WHERE m.active"""
        )
        first = self_cr.fetchone()[0]
        until = dates.ceil15(first) if first else dates.floor15(now)
        if until > now:
            until = dates.floor15(now)
        if not first:
            _logger.warning("td_energy: backfill: немає td.reading лічильників, until = %s", until)
    return until - timedelta(days=days), until


def _purge(env, since, until):
    cr = env.cr
    cr.execute(
        """DELETE FROM td_energy_balance b WHERE b.hour >= %s AND b.hour < %s AND NOT EXISTS (
               SELECT 1 FROM td_energy_interval i WHERE i.is_backfill = false AND i.ts_start >= b.hour
                  AND i.ts_start < b.hour + interval '1 hour')""",
        (since, until),
    )
    balance = cr.rowcount
    cr.execute("DELETE FROM td_energy_event WHERE is_backfill AND ts >= %s AND ts < %s", (since, until))
    events = cr.rowcount
    cr.execute("DELETE FROM td_energy_interval WHERE is_backfill AND ts_start >= %s AND ts_start < %s", (since, until))
    rows = cr.rowcount
    env["td.energy.interval"].invalidate_model()
    return {"purged_rows": rows, "purged_events": events, "purged_balance": balance}


def _simulate(plan, seed, since, until):
    """Генератор рядків по слотах: `(slot_index, ts_start, local_dt, {meter_id: (kwh, kwh_export)})`."""
    soc = 60.0
    on_cache = {}
    slots = int((until - since) / SLOT)
    for i in range(slots):
        ts = since + SLOT * i
        local = dates.to_local(ts)
        hs = local.hour + local.minute / 60.0
        weekday = local.weekday()
        h_mid = hs + 0.125
        day_no = (local.date() - dates.to_local(since).date()).days
        shift = (weekday < 5 and 7 <= hs < 23) or (weekday == 5 and 7 <= hs < 14)
        p_target = target_p(hs, weekday)
        kd = 1.0 + 0.05 * math.sin(1.7 * day_no)
        total_p = (210.0 + (p_target - 210.0) * kd) * (1.0 + 0.02 * (2 * rnd(seed, "slot", i) - 1))
        activity = max(0.0, (p_target - 210.0) / (667.0 - 210.0))
        hour_abs = i // 4
        raws = []
        for n, cfg in enumerate(plan.cons_cfg):
            kind = cfg["kind"]
            if kind == "direct":
                key = (n, hour_abs)
                if key not in on_cache:
                    on_cache[key] = rnd(seed, "m", cfg["code"], hour_abs)
                prob = 0.8 if weekday < 5 and shift else 0.5 if weekday == 5 and shift else 0.0
                raw = cfg["load"] if on_cache[key] < prob else cfg["idle"]
            elif kind == "activity":
                raw = cfg["p"] * (0.05 + 0.75 * activity)
            elif kind == "hvac":
                raw = 0.45 * cfg["p"] * (1.0 if shift else RV_OFFSHIFT_RATIO)
            elif kind == "light":
                raw = cfg["p"] * (0.7 if shift else 0.3)
            else:
                raw = cfg["p"] * (0.7 if 7 <= hs < 23 else 0.5)
            raws.append(raw)
        norm = total_p / (sum(raws) or 1.0)
        cons_kwh = [r * norm * 0.25 for r in raws]
        out = {}
        for m, kwh in zip(plan.consumers, cons_kwh, strict=True):
            out[m.id] = (kwh, 0.0)
        feeder_kwh = {}
        for f, members in zip(plan.feeders, plan.feeder_members, strict=True):
            eps = 0.008 + 0.004 * (2 * rnd(seed, f.code, i) - 1)
            if day_no % 11 == 5 and weekday < 5 and f.node_id.code == "QF-1" and 10 <= hs < 11:
                eps = 0.035  # аномалія обліку: породжує `deviation` у R-07
            kwh = sum(cons_kwh[j] for j in members) * (1.0 + eps)
            feeder_kwh[f.id] = kwh
            out[f.id] = (kwh, 0.0)
        pv_total = 0.0
        if plan.suns:
            cloud = 0.25 + 0.75 * rnd(seed, "day", local.date().isoformat()) ** 0.7
            pv_total = plan.pv_kwp * 0.8 * sun_factor(h_mid, local.timetuple().tm_yday) * cloud
            for k, m in enumerate(plan.suns, 1):
                out[m.id] = (pv_total / len(plan.suns) * (1 + 0.02 * (2 * rnd(seed, "sun", k, i) - 1)) * 0.25, 0.0)
        chp_kw = 0.0
        day_key = local.date().isoformat()
        if plan.chps and weekday < 5 and 16 <= hs < 19 and rnd(seed, day_key, "chp") < 0.1:
            chp_kw = 400.0
        for m in plan.chps:
            out[m.id] = (chp_kw * 0.25, 0.0)
        sec = {1: 0.0, 2: 0.0}
        for f in plan.feeders:
            sec[f.node_id.section or 1] = sec.get(f.node_id.section or 1, 0.0) + feeder_kwh[f.id]
        charge = discharge = 0.0
        if plan.bess is not None:
            surplus2 = sec.get(2, 0.0) * 4 - pv_total - chp_kw
            grid_net = sum(feeder_kwh.values()) * 4 - pv_total - chp_kw
            if surplus2 < -5 and soc < 95:
                charge = min(-surplus2, 100.0)
            elif grid_net > 0.95 * plan.contract_kw and soc > 15:
                discharge = min(grid_net - 0.95 * plan.contract_kw, 100.0)
            elif weekday < 5 and 7.5 <= hs < 11 and soc > 40:
                discharge = 60.0
            soc = min(95.0, max(10.0, soc + (charge * 0.95 - discharge / 0.95) * 0.25 / 200.0 * 100.0))
            out[plan.bess.id] = (charge * 0.25, discharge * 0.25)
        bess_net = (charge - discharge) * 0.25
        for n, m in enumerate(plan.incomers):
            noise = 1.0 + 0.002 * (2 * rnd(seed, m.code, i) - 1)
            section = m.node_id.section or (n + 1)
            if section == 1:
                out[m.id] = (sec.get(1, 0.0) * noise, 0.0)
            else:
                net2 = (sec.get(2, 0.0) - sum(out[s.id][0] for s in plan.suns) - chp_kw * 0.25 + bess_net) * noise
                out[m.id] = (max(0.0, net2), max(0.0, -net2))
        yield i, ts, local, out


def _write(env, plan, rows, stats):
    env.cr.execute_values(INSERT_SQL, rows, page_size=len(rows))
    stats["rows"] += env.cr.rowcount
    stats["attempted"] += len(rows)


def _events(env, plan, seed, since, until, stats):
    """R-36 п. 10 `with_events`: щоденний пік, тест АВР буднями 07:02, аномалії небалансу (`is_backfill`)."""
    Event, Node = env["td.energy.event"].sudo(), env["td.energy.node"].sudo()
    swb = Node.search([("code", "=", "SWB-1")], limit=1)
    ats = Node.search([("code", "=", "ATS-1")], limit=1)
    qf1 = Node.search([("code", "=", "QF-1")], limit=1)
    cr = env.cr
    cr.execute(
        """SELECT day, MAX(net) FROM (
               SELECT day, ts_start, SUM(kwh - kwh_export) * 4 AS net FROM td_energy_interval
                WHERE role = 'incomer' AND ts_start >= %s AND ts_start < %s GROUP BY day, ts_start) s
            GROUP BY day ORDER BY day""",
        (since, until),
    )
    vals = []
    contract = plan.contract_kw
    for day, peak in cr.fetchall():
        if peak is None:
            continue
        ts = dates.to_utc(datetime(day.year, day.month, day.day, 23, 55))
        if ts >= until:
            continue  # доба ще не завершилась: події «з майбутнього» не пишемо
        text = "Пік доби %d кВт. %d %% договірної потужності %d кВт." % (
            round(peak), round(peak / contract * 100), round(contract)
        )  # fmt: skip
        vals.append({"ts": ts, "level": "info", "kind": "peak", "code": "SWB-1", "text": text,
                     "node_id": swb.id, "state": "na", "is_backfill": True})  # fmt: skip
        if day.weekday() < 5:
            ts = dates.to_utc(datetime(day.year, day.month, day.day, 7, 2))
            if ts >= until:
                continue
            vals.append({"ts": ts, "level": "info", "kind": "ats", "code": "ATS-1", "text": ATS_TEXT,
                         "node_id": ats.id, "state": "na", "is_backfill": True})  # fmt: skip
    first = dates.to_local(since).date()
    for d in range((dates.to_local(until).date() - first).days + 1):
        day = first + timedelta(days=d)
        if d % 11 == 5 and day.weekday() < 5 and qf1:
            ts = dates.to_utc(datetime(day.year, day.month, day.day, 11, 0))
            if since <= ts < until:
                text = "Небаланс обліку BW-1: 3,5 %% (за 10:00–11:00, %s)" % day.strftime("%d.%m")
                vals.append(
                    {"ts": ts, "level": "warn", "kind": "balance", "code": "QF-1", "text": text, "node_id": qf1.id,
                     "state": "resolved", "resolved_at": ts, "is_backfill": True}
                )  # fmt: skip
    cr.execute("DELETE FROM td_energy_event WHERE is_backfill AND ts >= %s AND ts < %s", (since, until))
    Event.with_context(tracking_disable=True).create(vals)
    stats["events"] = len(vals)


def _balance(env, until, stats):
    """`with_balance`: `td.energy.balance` за закриті години останніх 7 діб (R-07)."""
    Balance = env["td.energy.balance"].sudo().with_context(td_backfill_mute=True)
    hour = dates.floor15(until).replace(minute=0) - timedelta(hours=1)
    count = 0
    for k in range(7 * 24):
        result = Balance._td_balance_hour(hour - timedelta(hours=k))
        count += len(result)
    stats["balance"] = count


def run(env, days=90, until=None, seed=20261018, purge=False, with_balance=True, with_events=True, with_advice=False,
        meters=None):  # fmt: skip
    """API-15: заповнити БД синтетичними інтервалами (R-36 п. 1–10); повертає статистику."""
    started = time.monotonic()
    days = int(days)
    if not 1 <= days <= 400:
        raise UserError(env._("Кількість діб має бути від 1 до 400."))
    since, until = _range(env, days, until)
    stats = {"meters": 0, "slots": 0, "rows": 0, "skipped": 0, "events": 0, "balance": 0,
             "since": fields.Datetime.to_string(since), "until": fields.Datetime.to_string(until), "seconds": 0.0,
             "attempted": 0}  # fmt: skip
    if purge:
        stats.update(_purge(env, since, until))
        stats["seconds"] = round(time.monotonic() - started, 2)
        return stats
    plan = Plan(env, meters)
    chosen = [m for m in plan.meters if not plan.filter or m.code in plan.filter]
    chosen_ids = {m.id for m in chosen}
    stats["meters"] = len(chosen)
    now = dates.now_utc(env)
    counters = {m.id: 50000.0 + 137.0 * plan.index[m.id] for m in chosen}
    price_cache = {}
    batch, last_slot = [], None
    for _i, ts, local, out in _simulate(plan, seed, since, until):
        key = (local.date().weekday(), local.hour, local.date())
        if key not in price_cache:
            price_cache[key] = plan.price_at(local)
        zone, price = price_cache[key]
        stats["slots"] += 1
        last_slot = ts
        end = ts + SLOT
        for m in chosen:
            kwh, exp = out.get(m.id, (0.0, 0.0))
            e_start = counters[m.id]
            counters[m.id] = e_end = e_start + kwh
            cost = round(kwh * price, 2) if m.role in COST_ROLES else 0.0
            batch.append(
                (m.id, m.node_id.id, m.role, ts, end, local.date(), local.hour, round(e_start, 3), round(e_end, 3),
                 round(kwh, 3), round(exp, 3), round(kwh * 4, 2), zone or None, price, cost, "measured", now, True)
            )  # fmt: skip
        if len(batch) >= BATCH:
            _write(env, plan, batch, stats)
            batch = []
    if batch:
        _write(env, plan, batch, stats)
    stats["skipped"] = stats["attempted"] - stats["rows"]
    stats.pop("attempted")
    env["td.energy.interval"].invalidate_model()
    if last_slot is not None:
        _touch_meters(env, chosen_ids, last_slot, until)
    if with_events:
        _events(env, plan, seed, since, until, stats)
    if with_balance:
        _balance(env, until, stats)
    if with_advice:
        env["td.energy.advice"]._td_demo_seed()
    try:
        env["td.energy.interval"]._td_after_build(now)
    except Exception:
        _logger.exception("td_energy: backfill: після побудови (R-11, R-15)")
    stats["seconds"] = round(time.monotonic() - started, 2)
    return stats


def _touch_meters(env, meter_ids, last_slot, until):
    """`last_interval_start = max(існуюче, останній слот)` — лише для лічильників без реальних слотів пізніше."""
    env.cr.execute(
        """UPDATE td_energy_meter m SET last_interval_start = GREATEST(COALESCE(m.last_interval_start, %s), %s)
            WHERE m.id IN %s AND NOT EXISTS (SELECT 1 FROM td_energy_interval i
                  WHERE i.meter_id = m.id AND NOT i.is_backfill AND i.ts_start >= %s)""",
        (last_slot, last_slot, tuple(meter_ids), until),
    )
    env["td.energy.meter"].invalidate_model(["last_interval_start"])
