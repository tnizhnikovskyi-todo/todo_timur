"""Ingester: валідація пакета показань, SQL-вставка, оновлення last_*, пороги, шина (R-17).

Викликається лише з `td.signal._td_ingest` (CT-10): контролери й модулі напряму Ingester не використовують.
«Зараз» — `fields.Datetime.now()` (не SQL `now()`), щоб працював `freezegun`.
"""

import math
import re
from datetime import datetime, timedelta, timezone

from odoo import fields

from . import thresholds
from .titles import fmt_num

CODE_RE = re.compile(r"^[a-z_]+(/[A-Za-z0-9_\-\.]+)+$")
QUALITIES = ("good", "uncertain", "bad")
FUTURE_S = 60
DERIVE_WINDOW = (300, 60)

SIGNAL_FIELDS = [
    "code",
    "name",
    "active",
    "kind",
    "unit",
    "decimals",
    "equipment_id",
    "collector_id",
    "states",
    "store_period_s",
    "sim_params",
    "derive_rule",
    "derived_from_id",
    "create_request",
    "warn_low_on",
    "warn_low",
    "warn_high_on",
    "warn_high",
    "alarm_low_on",
    "alarm_low",
    "alarm_high_on",
    "alarm_high",
    "hysteresis",
    "min_duration_s",
    "alarm_states",
    "last_value",
    "last_text",
    "last_ts",
    "last_quality",
    "last_stored_ts",
    "status",
    "status_since",
    "breach_since",
    "maintenance_request_id",
    "request_closed_at",
    "last_notified_ts",
]
LAST_FIELDS = ["last_value", "last_text", "last_ts", "last_quality", "last_stored_ts"]
STATUS_LABELS = {"unknown": "невідомо", "ok": "норма", "warn": "увага", "alarm": "тривога", "stale": "немає даних"}


def parse_ts(value):
    """R-14: datetime (naive = UTC) або рядок ISO із зоною → naive UTC. Повертає (ts, reason)."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value, None
    if not isinstance(value, str) or not value:
        return None, "ts_invalid"
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        return None, "ts_invalid"
    if dt.tzinfo is None:
        return None, "ts_no_tz"
    return dt.astimezone(timezone.utc).replace(tzinfo=None), None


def _m2o(val):
    if isinstance(val, (list, tuple)):
        return val[0] if val else False
    return val or False


class Ingester:
    def __init__(self, env, src="module", collector=None):
        self.env = env
        self.cr = env.cr
        self.Signal = env["td.signal"].sudo()
        self.src = src
        self.collector = collector
        self.now = env.context.get("f3d_received_at") or fields.Datetime.now()
        icp = env["ir.config_parameter"].sudo()
        self.keep_days = int(icp.get_param("td.telemetry.keep_days", "30") or 30)
        self.bus_min = int(icp.get_param("td.telemetry.bus_min_interval_s", "10") or 10)
        self.cooldown = int(icp.get_param("td.telemetry.realarm_cooldown_s", "3600") or 3600)
        self.states = {}  # signal_id -> рабочий стан
        self.rejected = []
        self.accepted = 0
        self.stored = 0
        self.duplicates = 0
        self.maybe_dup = []
        self.stored_rows = []  # (signal_id, ts, value) збережених у цьому виклику

    # --- розбір і валідація ------------------------------------------------------------------------
    def _parse(self, i, r):
        if not isinstance(r, dict):
            return None, "bad_code_format", None
        code = r.get("code")
        if not isinstance(code, str) or len(code) > 128 or not CODE_RE.match(code):
            return None, "bad_code_format", code if isinstance(code, str) else None
        ts, reason = parse_ts(r.get("ts"))
        if reason:
            return None, reason, code
        if ts > self.now + timedelta(seconds=FUTURE_S):
            return None, "ts_future", code
        if ts < self.now - timedelta(days=self.keep_days):
            return None, "ts_too_old", code
        value, text, q = r.get("value"), r.get("text"), r.get("q") or "good"
        if q not in QUALITIES:
            return None, "value_invalid", code
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None, "value_invalid", code
            value = float(value)
            if math.isnan(value) or math.isinf(value):
                return None, "value_invalid", code
        if text is not None:
            if not isinstance(text, str):
                text = str(text)
            if len(text) > 64:
                return None, "text_too_long", code
        return {"i": i, "code": code, "ts": ts, "value": value, "text": text, "q": q, "src": self.src}, None, code

    def _load_state(self, rec):
        st = dict(rec)
        st["id"] = rec["id"]
        st["equipment_id"] = _m2o(rec["equipment_id"])
        st["collector_id"] = _m2o(rec["collector_id"])
        st["derived_from_id"] = _m2o(rec["derived_from_id"])
        st["maintenance_request_id"] = _m2o(rec["maintenance_request_id"])
        st["states"] = rec.get("states") or []
        st["alarm_states"] = rec.get("alarm_states") or []
        st["sim_params"] = rec.get("sim_params") or {}
        st["last_ts"] = rec["last_ts"] or None
        st["last_text"] = rec["last_text"] or None
        st["last_quality"] = rec["last_quality"] or None
        st["last_stored_ts"] = rec["last_stored_ts"] or None
        st["breach_since"] = rec["breach_since"] or None
        st["status_since"] = rec["status_since"] or None
        st["last_notified_ts"] = rec["last_notified_ts"] or None
        st["request_closed_at"] = rec["request_closed_at"] or None
        st["orig"] = {k: st[k] for k in ("last_value", "last_text", "status", "breach_since")}
        st.update(
            fresh=False,
            status_changed=False,
            last_dirty=False,
            seen=set(),
            batch_stored=[],
            decreased=False,
            last_bad=False,
            last_item=None,
            text_changed=False,
        )
        return st

    def _load_signals(self, domain):
        recs = self.Signal.with_context(active_test=False).search_read(domain, SIGNAL_FIELDS)
        return {r["code"]: self._load_state(r) for r in recs}

    # --- застосування одного показання в пам'яті (R-03, R-04, R-08) -------------------------------------
    def _is_stored_near(self, st, ts, period):
        lo, hi = ts - timedelta(seconds=period), ts + timedelta(seconds=period)
        if any(lo < t < hi for t in st["batch_stored"]):
            return True
        self.cr.execute(
            "SELECT 1 FROM td_reading WHERE signal_id = %s AND ts > %s AND ts < %s AND quality <> 'bad' LIMIT 1",
            (st["id"], lo, hi),
        )
        return bool(self.cr.fetchone())

    def _last_bad(self, st):
        if st["last_bad"] is False:
            self.cr.execute("SELECT max(ts) FROM td_reading WHERE signal_id = %s AND quality = 'bad'", (st["id"],))
            st["last_bad"] = self.cr.fetchone()[0]
        return st["last_bad"]

    def _apply(self, st, it):
        """Повертає рядок для td_reading або None; змінює st у пам'яті."""
        ts, v, text, q, kind = it["ts"], it["value"], it["text"], it["q"], st["kind"]
        force_last = False
        if kind == "state":
            states = st["states"]
            if states:
                if text in states:
                    v = float(states.index(text))
                else:
                    v, q, force_last = -1.0, "bad", True
                    self.rejected.append({"i": it["i"], "code": it["code"], "reason": "unknown_state"})
        elif kind == "event":
            v = 1.0
        period = st["store_period_s"] or 0
        last_ts = st["last_ts"]
        fresh = (q != "bad" or force_last) and (last_ts is None or ts > last_ts)
        if fresh and kind == "counter" and v is not None and last_ts is not None and q == "good":
            prev = st["last_value"] or 0.0
            if v < prev - abs(prev) * 0.01 and (st["sim_params"] or {}).get("reset") != "daily":
                q = "uncertain"
                st["decreased"] = True
        store = False
        text_changed = kind == "state" and text != st["last_text"]
        if kind == "event":
            store = True
        elif fresh:
            lst = st["last_stored_ts"]
            store = period == 0 or lst is None or (ts - lst).total_seconds() >= period or text_changed
        elif q == "bad":
            lb = self._last_bad(st)
            store = period == 0 or lb is None or abs((ts - lb).total_seconds()) >= period
        else:
            store = period == 0 or not self._is_stored_near(st, ts, period)
        if fresh:
            old_status = st["status"]
            new_status, since = thresholds.eval_status(
                {"status": old_status, "breach_since": st["breach_since"]},
                v,
                text,
                ts,
                st,
                quality="bad" if force_last else q,
            )
            st["breach_since"] = since
            if new_status != old_status:
                st["status"], st["status_since"] = new_status, ts
                st["status_changed"] = True
                st.setdefault("status_trail", []).append((old_status, new_status, v, text))
                if not store:
                    store = True
            if v is not None:
                st["last_value"] = v
            if text is not None:
                st["last_text"] = text
            st["last_ts"], st["last_quality"] = ts, q
            st["last_dirty"] = True
            st["last_item"] = {"ts": ts, "value": v, "text": text}
            if store:
                st["last_stored_ts"] = ts
        if not store:
            if not fresh:
                self.maybe_dup.append((st["id"], ts))
            return None
        if q == "bad":
            st["last_bad"] = (
                ts if (st["last_bad"] is None or st["last_bad"] is False or ts > st["last_bad"]) else st["last_bad"]
            )
        st["batch_stored"].append(ts)
        return (st["id"], st["equipment_id"] or None, ts, v, text, q, it["src"], self.now)

    # --- ядро ----------------------------------------------------------------------------------------
    def _process(self, items, derived=False):
        rows = []
        for it in sorted(items, key=lambda x: (x["code"], x["ts"])):
            st = it["st"]
            if not derived:
                self.accepted += 1
            if it["ts"] in st["seen"]:
                self.duplicates += 1
                continue
            st["seen"].add(it["ts"])
            row = self._apply(st, it)
            if row:
                rows.append(row)
        if rows:
            res = self.cr.execute_values(
                "INSERT INTO td_reading (signal_id, equipment_id, ts, value, text, quality, src, received_at) "
                "VALUES %s ON CONFLICT (signal_id, ts) DO NOTHING RETURNING signal_id, ts",
                rows,
                fetch=True,
            )
            got = {(r[0], r[1]) for r in res}
            self.stored += len(got)
            self.duplicates += len(rows) - len(got)
            self.stored_rows += [(r[0], r[2], r[3]) for r in rows if (r[0], r[2]) in got]
        return rows

    def _derive(self, sources):
        """R-08: похідні `rate_h` від лічильників, чиї показання збережено в цьому виклику."""
        derived = self.Signal.with_context(active_test=False).search_read(
            [("derived_from_id", "in", [s for s in sources]), ("derive_rule", "=", "rate_h")], SIGNAL_FIELDS
        )
        if not derived:
            return
        items = []
        for d in derived:
            st = self.states.get(d["code"]) or self._load_state(d)
            self.states[d["code"]] = st
            for sid, ts, v in sorted(self.stored_rows, key=lambda x: x[1]):
                if sid != st["derived_from_id"] or v is None:
                    continue
                prev = self._prev_reading(sid, ts)
                if not prev or prev[1] is None or ts <= prev[0]:
                    continue
                rate = (v - prev[1]) / ((ts - prev[0]).total_seconds() / 3600.0)
                items.append(
                    {
                        "i": -1,
                        "code": st["code"],
                        "ts": ts,
                        "value": rate,
                        "text": None,
                        "q": "good",
                        "src": self.src,
                        "st": st,
                    }
                )
        if items:
            self._process(items, derived=True)

    def _prev_reading(self, sid, ts):
        lo, hi = ts - timedelta(seconds=DERIVE_WINDOW[0]), ts - timedelta(seconds=DERIVE_WINDOW[1])
        base = "SELECT ts, value FROM td_reading WHERE signal_id = %s AND quality <> 'bad' AND value IS NOT NULL "
        self.cr.execute(base + "AND ts >= %s AND ts <= %s ORDER BY ts LIMIT 1", (sid, lo, hi))
        row = self.cr.fetchone()
        if not row:
            self.cr.execute(base + "AND ts <= %s ORDER BY ts DESC LIMIT 1", (sid, hi))
            row = self.cr.fetchone()
        return row

    def run(self, readings):
        items, parsed = [], []
        for i, r in enumerate(readings if isinstance(readings, list) else []):
            it, reason, code = self._parse(i, r)
            if reason:
                self.rejected.append({"i": i, "code": code, "reason": reason})
            else:
                parsed.append(it)
        if parsed:
            self.states = self._load_signals([("code", "in", sorted({p["code"] for p in parsed}))])
        for it in parsed:
            st = self.states.get(it["code"])
            if not st:
                self.rejected.append({"i": it["i"], "code": it["code"], "reason": "unknown_code"})
            elif not st["active"]:
                self.rejected.append({"i": it["i"], "code": it["code"], "reason": "inactive"})
            elif self.src == "collector" and self.collector and st["collector_id"] != self.collector.id:
                self.rejected.append({"i": it["i"], "code": it["code"], "reason": "foreign_signal"})
            elif st["kind"] in ("gauge", "counter") and it["value"] is None:
                self.rejected.append({"i": it["i"], "code": it["code"], "reason": "missing_value"})
            elif st["kind"] == "state" and it["text"] is None:
                self.rejected.append({"i": it["i"], "code": it["code"], "reason": "missing_value"})
            elif st["kind"] == "event" and it["text"] is None and it["value"] is None:
                self.rejected.append({"i": it["i"], "code": it["code"], "reason": "missing_value"})
            else:
                if st["kind"] in ("gauge", "counter"):
                    it["text"] = None  # числовий сигнал: зайвий `text` ігнорується (T-5), а не пишеться в last_text
                it["st"] = st
                items.append(it)
        self._process(items)
        counters = [s["id"] for s in self.states.values() if s["kind"] == "counter" and s["batch_stored"]]
        if counters:
            self._derive(counters)
        self._check_duplicates()
        changed = self._finish()
        self.rejected.sort(key=lambda r: r["i"])
        return {
            "accepted": self.accepted,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "changed_codes": changed[0],
            "alarms_opened": changed[1],
        }

    def _check_duplicates(self):
        pairs = list({p for p in self.maybe_dup})
        for k in range(0, len(pairs), 500):
            self.cr.execute(
                "SELECT count(*) FROM td_reading WHERE (signal_id, ts) IN %s", (tuple(pairs[k : k + 500]),)
            )
            self.duplicates += self.cr.fetchone()[0]

    # --- завершення: last_*, статуси, заявки, ТО, шина -----------------------------------------------
    def _finish(self):
        sts = [s for s in self.states.values() if s["last_dirty"]]
        if not sts:
            return [], 0
        rows = [
            (s["id"], s["last_value"], s["last_text"], s["last_ts"], s["last_quality"], s["last_stored_ts"])
            for s in sts
        ]
        self.cr.execute_values(
            "UPDATE td_signal AS s SET last_value = v.last_value, last_text = v.last_text, last_ts = v.last_ts, "
            "last_quality = v.last_quality, last_stored_ts = v.last_stored_ts "
            "FROM (VALUES %s) AS v(id, last_value, last_text, last_ts, last_quality, last_stored_ts) "
            "WHERE s.id = v.id AND (s.last_ts IS NULL OR s.last_ts < v.last_ts)",
            rows,
            template="(%s::int, %s::float8, %s::varchar, %s::timestamp, %s::varchar, %s::timestamp)",
        )
        self.Signal.invalidate_model(LAST_FIELDS)
        Signal = self.Signal.with_context(mail_notrack=True, mail_create_nolog=True)
        opened = 0
        changed_ids = []
        for s in sorted(sts, key=lambda x: x["code"]):
            o = s["orig"]
            rec = Signal.browse(s["id"])
            vals = {}
            if s["status_changed"]:
                vals.update(status=s["status"], status_since=s["status_since"])
            if s["breach_since"] != o["breach_since"]:
                vals["breach_since"] = s["breach_since"] or False
            if vals:
                rec.write(vals)
            for old, new, v, text in s.get("status_trail", []):
                rec.message_post(body=self._status_msg(s, old, new, v, text), subtype_xmlid="mail.mt_note")
            if s["decreased"]:
                self._post_decrease(rec, s)
            if (s["last_value"], s["last_text"], s["status"]) != (o["last_value"], o["last_text"], o["status"]):
                changed_ids.append(s["id"])
            opened += self._maybe_open_request(rec, s)
        self._meter_checks([s["id"] for s in sts])
        changed_codes = [s["code"] for s in sorted(sts, key=lambda x: x["code"]) if s["id"] in changed_ids]
        self._bus(sts, changed_ids)
        return changed_codes, opened

    def _status_msg(self, s, old, new, v, text):
        if s["kind"] == "state":
            detail = text or ""
        else:
            detail = ("%s %s" % (fmt_num(v, s["decimals"]), s["unit"] or "")).strip() if v is not None else ""
        msg = "Стан: %s → %s" % (STATUS_LABELS.get(old, old), STATUS_LABELS.get(new, new))
        return msg + (" (%s)" % detail if detail else "")

    def _post_decrease(self, rec, s):
        since = self.now - timedelta(days=1)
        exists = (
            self.env["mail.message"]
            .sudo()
            .search_count(
                [
                    ("model", "=", "td.signal"),
                    ("res_id", "=", s["id"]),
                    ("body", "ilike", "Лічильник зменшився"),
                    ("date", ">=", since),
                ]
            )
        )
        if not exists:
            rec.message_post(
                body="Лічильник зменшився: %s → %s (можливий ролловер або заміна лічильника)"
                % (fmt_num(s["orig"]["last_value"], s["decimals"]), fmt_num(s["last_value"], s["decimals"])),
                subtype_xmlid="mail.mt_note",
            )

    def _maybe_open_request(self, rec, s):
        if s["status"] != "alarm" or not s["last_item"] or not s["create_request"]:
            return 0
        if not s["equipment_id"]:
            if s["status_changed"] and s["orig"]["status"] != "alarm":
                rec.message_post(body="Тривога без обладнання — заявку не створено", subtype_xmlid="mail.mt_note")
            return 0
        req = rec.maintenance_request_id
        if req and not req.stage_id.done:
            return 0
        closed = s["request_closed_at"]
        if closed and (self.now - closed).total_seconds() < self.cooldown:
            return 0
        item = s["last_item"]
        rec._open_request(item["value"], item["text"], item["ts"])
        return 1

    def _meter_checks(self, ids):
        Equipment = self.env["maintenance.equipment"].sudo()
        if not hasattr(Equipment, "_td_meter_check") or "td_meter_signal_id" not in Equipment._fields:
            return
        Equipment.search([("td_meter_signal_id", "in", ids)])._td_meter_check()

    def _bus(self, sts, changed_ids):
        if "td.viewer.event" not in self.env:
            return
        notify = []
        for s in sts:
            if s["id"] not in changed_ids:
                continue
            o = s["orig"]
            last = s["last_notified_ts"]
            if (
                last is None
                or (self.now - last).total_seconds() >= self.bus_min
                or s["status"] != o["status"]
                or s["last_text"] != o["last_text"]
            ):
                notify.append(s)
        if not notify:
            return
        self.cr.execute(
            "UPDATE td_signal SET last_notified_ts = %s WHERE id IN %s", (self.now, tuple(s["id"] for s in notify))
        )
        self.Signal.invalidate_model(["last_notified_ts"])
        self.Signal._notify_viewer([s["code"] for s in notify])
