"""M-02 `td.chp.event` — журнал подій і аварій; R-01 (зв'язок), R-04 (події з показань), R-05 (аварії)."""

from datetime import timedelta

from odoo import _, api, fields, models, tools as odoo_tools
from odoo.exceptions import AccessError

from odoo.addons.td_telemetry.tools import thresholds
from odoo.addons.td_telemetry.tools.titles import fmt_num

from ..tools import alarms, bus
from ..tools.signals import PREFIX, Snapshot, cparam_bool, cparam_int, is_fresh, now

DEDUP_S = 5
STATE_SIGNAL = "chp/ctl/state"
SKIP_STATUS = {"chp/alarm/code", "chp/alarm/trip"}  # аварії й зупинки — окремі події (R-04 п. 5, 6)


class TdChpEvent(models.Model):
    _name = "td.chp.event"
    _description = "КГУ: подія"
    _order = "ts desc, id desc"

    unit_id = fields.Many2one("td.chp.unit", string="Агрегат", required=True, index=True, ondelete="cascade")
    ts = fields.Datetime(string="Час", required=True, index=True, default=fields.Datetime.now)
    level = fields.Selection(
        [("info", "Інформація"), ("warn", "Увага"), ("alarm", "Аварія")], string="Рівень", required=True, default="info"
    )
    kind = fields.Selection(
        [
            ("state", "Стан"),
            ("step", "Крок пуску"),
            ("alarm", "Аварія"),
            ("trip", "Зупинка"),
            ("warn", "Попередження"),
            ("protection", "Захист"),
            ("comm", "Зв'язок"),
            ("ack", "Квитування"),
            ("maintenance", "ТО"),
        ],
        string="Вид",
        required=True,
        default="state",
    )
    text = fields.Char(string="Текст", required=True, size=256)
    code = fields.Char(string="Код", size=48)
    signal_id = fields.Many2one("td.signal", string="Сигнал", ondelete="set null")
    ack_state = fields.Selection(
        [("none", "Не потребує"), ("new", "Не квитовано"), ("acked", "Квитовано")],
        string="Квитування",
        default="none",
        index=True,
    )
    acked_by = fields.Many2one("res.users", string="Квитував", readonly=True)
    acked_at = fields.Datetime(string="Квитовано", readonly=True)
    node = fields.Char(string="Вузол", size=16)
    request_id = fields.Many2one("maintenance.request", string="Заявка ТО", ondelete="set null")

    def init(self):
        cr = self.env.cr
        odoo_tools.sql.create_index(cr, "td_chp_event_unit_ts_idx", self._table, ["unit_id", "ts DESC"])
        odoo_tools.sql.create_index(cr, "td_chp_event_ack_level_idx", self._table, ["ack_state", "level"])

    # --- запис (лише sudo-методи) -------------------------------------------------------------------------------
    @api.model
    def _td_log(self, unit, level, kind, text, dedup_s=DEDUP_S, **kw):
        """Створити подію (sudo); `warn/alarm` → `ack_state='new'`. Дублікат `code+text` за `dedup_s` с — пропуск."""
        env = self.sudo().env
        ts = kw.pop("ts", None) or now(env)
        code = kw.get("code")
        if dedup_s and code:
            dup = self.sudo().search_count(
                [
                    ("unit_id", "=", unit.id),
                    ("code", "=", code),
                    ("text", "=", text[:256]),
                    ("ts", ">=", ts - timedelta(seconds=dedup_s)),
                ]
            )
            if dup:
                return self.browse()
        vals = {
            "unit_id": unit.id,
            "ts": ts,
            "level": level,
            "kind": kind,
            "text": text[:256],
            "ack_state": "new" if level in ("warn", "alarm") else "none",
        }
        vals.update(kw)
        rec = self.sudo().create(vals)
        bus.tick(self.env, "journal")
        return rec

    @api.model
    def _td_ack(self, ids=None):
        """R-04 п. 8: `new` → `acked` (operator) і одна `info`/`ack` «Квитування: підтверджено повідомлень — N»."""
        if not self.env.su and not self.env.user.has_group("td_chp.group_td_chp_operator"):
            raise AccessError(_("Квитувати може лише енергетик КГУ."))
        domain = [("ack_state", "=", "new")]
        if ids is not None:
            domain.append(("id", "in", list(ids)))
        events = self.sudo().search(domain)
        if not events:
            return 0
        t = now(self.env)
        events.write({"ack_state": "acked", "acked_by": self.env.user.id, "acked_at": t})
        for unit in events.unit_id:
            n = len(events.filtered(lambda e, unit=unit: e.unit_id == unit))
            self._td_log(unit, "info", "ack", f"Квитування: підтверджено повідомлень — {n}", dedup_s=0)
        return len(events)

    # --- R-04: події з показань -----------------------------------------------------------------------------------
    @api.model
    def _td_on_ingest(self, before, readings):
        """`before` — `{code: (status, last_value, last_ts)}` до прийому пакета (з `td.signal._td_ingest`)."""
        env = self.sudo().env
        unit = env["td.chp.unit"].sudo().search([], limit=1)
        if not unit or not cparam_bool(env, "read_enabled"):
            return
        sigs = {
            s["code"]: s
            for s in env["td.signal"]
            .sudo()
            .search_read(
                [("code", "in", sorted(before))],
                ["code", "name", "status", "last_value", "last_ts", "unit", "decimals"],
            )
        }
        snap = None  # знімок свіжих значень для текстів — ліниво

        def get_snap():
            nonlocal snap
            if snap is None:
                snap = Snapshot(env)
            return snap

        def val(code):
            return get_snap().get(code[len(PREFIX) :])

        # зв'язок відновлено (R-01): `ctl/state` знову свіжий
        if unit.comm_lost and unit._td_value("ctl/state") is not None:
            unit.comm_lost = False
            self._td_log(unit, "info", "comm", "Зв'язок з КГУ відновлено", dedup_s=0)
        for code, (old_status, old_val, old_ts) in before.items():
            s = sigs.get(code)
            if not s or s["last_ts"] is None:
                continue
            new = s["last_value"]
            first = old_ts is None
            changed = old_val is None or abs((new or 0) - (old_val or 0)) > 1e-9
            if code == STATE_SIGNAL:
                self._on_state(unit, old_val if not first else None, new, val)
            elif code == "chp/ctl/step" and changed and new:
                k = int(round(new))
                self._td_log(unit, "info", "step", f"Пуск, крок {k}/9: {alarms.step_name(k)}", code=f"step/{k}")
            elif code == "chp/alarm/code" and (changed or first):
                self._on_alarm(unit, 0 if first else old_val, new, get_snap())
            elif code == "chp/alarm/trip" and (changed or first):
                if new:
                    th = unit._td_th()
                    level, text, node = alarms.trip_info(new, get_snap().values(), th)
                    self._td_log(unit, level, "trip", text, code=f"trip/{int(new)}", node=node, dedup_s=0)
            elif not first and changed:
                self._on_flag(unit, code, old_val, new, val, get_snap())
            if code not in SKIP_STATUS and s["status"] != old_status and s["status"] in ("warn", "alarm"):
                self._on_status(unit, s, old_status)

    def _on_state(self, unit, old, new, val):
        new_i = int(round(new))
        names = alarms.STATE_NAMES
        if old is not None and int(round(old)) != new_i:
            old_i = int(round(old))
            self._td_log(
                unit,
                "info",
                "state",
                f"Стан КГУ: {names.get(old_i, old_i)} → {names.get(new_i, new_i)}",
                code=f"state/{old_i}-{new_i}",
            )
            if old_i == 1 and new_i == 2:
                p = val("chp/gen/p_kw")
                tail = f" P ел. = {fmt_num(p, 0)} кВт" if p is not None else ""
                self._td_log(
                    unit, "info", "state", f"Пуск завершено: КГУ в роботі,{tail}".rstrip(","), code="state/started"
                )
        if unit.state_code != new_i:
            unit.sudo().write({"state_code": new_i, "state_ts": now(self.env)})

    def _on_alarm(self, unit, old, new, snap):
        """R-04 п. 5: `alarm/code` 0→N — аварія; N→0 — «Аварію скинуто»."""
        if new:
            text, node = alarms.alarm_info(new, snap.values(), unit._td_th())
            self._td_log(unit, "alarm", "alarm", text, code=f"alarm/{int(new)}", node=node, dedup_s=0)
        elif old:
            self._td_log(unit, "info", "alarm", "Аварію скинуто", code="alarm/0", dedup_s=0)

    def _on_flag(self, unit, code, old, new, val, snap):
        """R-04 п. 3: valve proving, QF-CHP, автодолив масла, гасіння."""
        o, n = int(round(old or 0)), int(round(new or 0))
        if code == "chp/gas/vp_state" and n in (2, 3) and o != n:
            leak = fmt_num(val("chp/gas/vp_leak"), 1) if val("chp/gas/vp_leak") is not None else "—"
            if n == 2:
                self._td_log(
                    unit,
                    "info",
                    "protection",
                    f"Valve proving YV1/YV2: герметичність підтверджена (витік {leak} мбар/хв)",
                    code="vp/ok",
                )
            else:
                self._td_log(
                    unit,
                    "alarm",
                    "protection",
                    f"Valve proving YV1/YV2: виявлено витік ({leak} мбар/хв)",
                    code="vp/leak",
                    dedup_s=0,
                )
        elif code == "chp/safe/qf_closed" and o != n:
            if n == 1:
                du, df, dp = val("chp/ctl/sync_du"), val("chp/ctl/sync_df"), val("chp/ctl/sync_dphi")
                sync = ""
                if None not in (du, df, dp):
                    sync = f"ΔU {fmt_num(du, 1)} %, Δf {fmt_num(df, 2)} Гц, Δφ {fmt_num(abs(dp), 0)}° · "
                self._td_log(
                    unit,
                    "info",
                    "state",
                    f"Синхронізація з мережею S2: {sync}QF-CHP увімкнено",
                    code="qf/1",
                )
            else:
                self._td_log(unit, "info", "state", "QF-CHP відключено, двигун на холостому ході", code="qf/0")
        elif code == "chp/oil/topup" and o != n:
            level = val("chp/oil/level")
            lvl = fmt_num(level, 1) if level is not None else "—"
            if n == 1:
                self._td_log(unit, "info", "state", f"Автодолив масла: рівень картера {lvl} %", code="topup/1")
            else:
                self._td_log(unit, "info", "state", f"Автодолив масла завершено: картер {lvl} %", code="topup/0")
        elif code == "chp/safe/ext_state" and o == 0 and n == 1:
            self._td_log(
                unit,
                "alarm",
                "protection",
                "Автоматичне гасіння: випуск вогнегасної речовини в контейнер",
                code="ext/1",
                dedup_s=0,
            )

    def _on_status(self, unit, s, old_status):
        """R-04 п. 7: статус сигналу → warn/alarm — подія `warn` із порогом."""
        sig = self.env["td.signal"].sudo().search([("code", "=", s["code"])], limit=1)
        threshold, _rel = thresholds.breach_info(sig._td_cfg(), s["last_value"])
        decimals = s["decimals"] if s["decimals"] is not None else 2
        text = f"{s['name']}: {fmt_num(s['last_value'], decimals)} {s['unit'] or ''}".rstrip()
        if threshold is not None:
            text += f" (поріг {fmt_num(threshold, decimals)})"
        self._td_log(
            unit,
            "alarm" if s["status"] == "alarm" else "warn",
            "warn",
            text,
            code=s["code"][len(PREFIX) :],
            signal_id=sig.id,
            dedup_s=0,
        )

    # --- крони --------------------------------------------------------------------------------------------------
    @api.model
    def _cron_stale(self):
        """R-01: `ctl/state` застарів → один `warn`/`comm`; перше свіже значення логує `_td_on_ingest`."""
        if not cparam_bool(self.env, "read_enabled"):
            return 0
        n = 0
        t = now(self.env)
        stale_s = cparam_int(self.env, "stale_s")
        for unit in self.env["td.chp.unit"].sudo().search([]):
            sig = unit._td_signal("ctl/state")
            if not sig or not sig.last_ts or unit.comm_lost:
                continue
            if not is_fresh(sig.last_ts, sig.period_s, t, stale_s):
                age = int((t - sig.last_ts).total_seconds())
                unit.comm_lost = True
                self._td_log(unit, "warn", "comm", f"Втрата зв'язку з КГУ: немає даних {age} с", dedup_s=0)
                bus.tick(self.env, "state")
                n += 1
        return n

    @api.model
    def _cron_gc(self):
        """Видалити події старше `event_keep_days`."""
        if not cparam_bool(self.env, "read_enabled"):
            return 0
        limit = now(self.env) - timedelta(days=cparam_int(self.env, "event_keep_days"))
        old = self.sudo().search([("ts", "<", limit)])
        n = len(old)
        old.unlink()
        return n

    def action_ack_selected(self):
        """«Квитувати вибране» (V-03)."""
        self.env["td.chp.event"]._td_ack(self.ids)
        return True
