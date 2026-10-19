"""Синхронізація станів моделей із сигналами (SPEC R-19; правила R-10…R-13, R-22).

`FireSync(env).run(codes=None, full=False)` викликається з `td.signal._td_ingest` (коди змін) і крона (`full=True`).
Усе читається з БД (`search_read`), стани пишуть методи моделей (`_set_state`, `_set_dust`) — вони ж ведуть журнал.
"""

import logging

from odoo import fields

from . import states

_logger = logging.getLogger(__name__)

SIGNAL_FIELDS = ["code", "last_value", "last_text", "last_ts", "status", "last_quality"]
PANEL_ROLES = (
    ("state", "signal_state_id"),
    ("system", "signal_system_id"),
    ("alarms", "signal_alarms_id"),
    ("faults", "signal_faults_id"),
    ("disabled", "signal_disabled_id"),
    ("sounders", "signal_sounders_id"),
    ("brigade", "signal_brigade_id"),
)
SYSTEM_ROLES = (
    ("state", "signal_state_id"),
    ("active", "signal_active_id"),
    ("fault", "signal_fault_id"),
    ("water", "signal_water_id"),
    ("battery", "signal_battery_id"),
    ("count", "signal_count_id"),
    ("pressure", "pressure_signal_id"),
)


def _fmt(value):
    return ("%g" % round(value or 0.0, 2)).replace(".", ",")


class FireSync:
    def __init__(self, env):
        self.env = env(su=True)
        self.rows = {}
        self.affected = None  # None → усе
        self.changed = 0

    # --- допоміжне ----------------------------------------------------------------------------------------
    def row(self, signal):
        return self.rows.get(signal.id) if signal else None

    @staticmethod
    def fresh(row):
        """Показання придатне для зміни стану: є значення, не `stale`/`unknown`, якість не `bad`."""
        return bool(
            row and row["last_ts"] and row["status"] not in ("stale", "unknown") and row["last_quality"] != "bad"
        )

    def hit(self, *signals):
        if self.affected is None:
            return True
        return any(s.id in self.affected for s in signals if s)

    def _prev_on(self, system, on_type, off_type):
        ev = self.env["td.fire.event"].search(
            [("system_id", "=", system.id), ("etype", "in", (on_type, off_type))], order="ts desc, id desc", limit=1
        )
        return bool(ev) and ev.etype == on_type

    # --- запуск -------------------------------------------------------------------------------------------
    def run(self, codes=None, full=False):
        env = self.env
        Panel = env["td.fire.panel"]
        panels = Panel.search([])
        now = fields.Datetime.now()
        if not Panel._get_param("read_enabled", True):
            for panel in panels:
                panel._set_comm("off", now)
            return {"skipped": "read_disabled"}
        env["td.signal"].invalidate_model(SIGNAL_FIELDS + ["status_since"])
        Event = env["td.fire.event"]
        events0 = Event.search_count([])

        loops = panels.loop_ids
        zones = env["td.fire.zone"].search([("panel_id", "in", panels.ids)])
        devices = env["td.fire.device"].search(
            [("panel_id", "in", panels.ids), "|", ("state_signal_id", "!=", False), ("dust_signal_id", "!=", False)]
        )
        systems = env["td.fire.system"].search([("panel_id", "in", panels.ids)])
        signals = env["td.signal"]
        for panel in panels:
            signals |= panel.mapped(
                lambda p: (
                    p.signal_state_id
                    | p.signal_system_id
                    | p.signal_alarms_id
                    | p.signal_faults_id
                    | p.signal_disabled_id
                    | p.signal_sounders_id
                    | p.signal_brigade_id
                )
            )
        signals |= loops.signal_id | zones.signal_id | devices.state_signal_id | devices.dust_signal_id
        for system in systems:
            signals |= (
                system.signal_state_id
                | system.signal_active_id
                | system.signal_fault_id
                | system.signal_water_id
                | system.signal_battery_id
                | system.signal_count_id
                | system.pressure_signal_id
            )
        rows = env["td.signal"].with_context(active_test=False).search_read([("id", "in", signals.ids)], SIGNAL_FIELDS)
        self.rows = {r["id"]: r for r in rows}
        if codes:
            self.affected = {r["id"] for r in rows if r["code"] in set(codes)}
        n_signals = len(self.affected) if self.affected is not None else len(rows)

        for device in devices:
            self._device(device)
        for zone in zones:
            self._zone(zone)
        for loop in loops:
            self._loop(loop)
        for panel in panels:
            self._panel(panel)
        for system in systems:
            self._system(system)
        for panel in panels:
            if full or self._comm_hit(panel, loops, zones):
                self._comm(panel, loops, zones, now)
        # заявку telemetry створює до звірки, тож подію журналу (R-22 п. 1) прив'язуємо тут
        env["maintenance.request"].search(
            [("td_signal_id", "in", list(self.rows)), ("td_fire_event_id", "=", False), ("stage_id.done", "=", False)]
        )._td_fire_link_events()
        return {"signals": n_signals, "changed": self.changed, "events": Event.search_count([]) - events0}

    # --- пристрої (R-11, R-13 п. 1) -----------------------------------------------------------------------
    def _device(self, device):
        row = self.row(device.state_signal_id)
        if row and self.hit(device.state_signal_id) and self.fresh(row):
            text = row["last_text"] or ""
            if text and text != device.raw_state:
                device._set_state(states.device_state(text), text, row["last_ts"])
                self.changed += 1
        row = self.row(device.dust_signal_id)
        if (
            row
            and self.hit(device.dust_signal_id)
            and self.fresh(row)
            and row["last_value"] is not None
            and (not device.dust_ts or row["last_ts"] > device.dust_ts)
        ):
            device._set_dust(row["last_value"], row["last_ts"])
            self.changed += 1

    # --- зони (R-11) --------------------------------------------------------------------------------------
    def _zone(self, zone):
        sig = zone.signal_id
        row = self.row(sig)
        if not row or not self.hit(sig) or row["status"] == "unknown" or row["last_quality"] == "bad":
            return
        if row["status"] == "stale":
            if not zone.stale:
                zone.write({"stale": True})
                self.changed += 1
            return
        if zone.stale:
            zone.write({"stale": False})
            self.changed += 1
        text = row["last_text"] or ""
        if not row["last_ts"] or not text or text == zone.raw_state:
            return
        new = states.zone_state(text)
        device = None
        for dev in zone.device_ids:
            drow = self.row(dev.state_signal_id)
            if drow and self.fresh(drow) and states.device_state(drow["last_text"]) == new:
                device = dev
                break
        zone._set_state(new, text, row["last_ts"], device)
        self.changed += 1

    # --- шлейфи (R-11) ------------------------------------------------------------------------------------
    def _loop(self, loop):
        row = self.row(loop.signal_id)
        if not self.hit(loop.signal_id) or not self.fresh(row):
            return
        text = row["last_text"]
        if not text:
            text = "on" if row["last_value"] else "off"
        new = "fault" if text == "on" else "ok"
        if new != loop.state:
            loop._set_state(new, row["last_ts"])
            self.changed += 1

    # --- прилад (R-10) ------------------------------------------------------------------------------------
    def _panel(self, panel):
        roles = {role: self.row(panel[field]) for role, field in PANEL_ROLES}
        sigs = [panel[field] for _role, field in PANEL_ROLES]
        if not self.hit(*sigs) or not any(self.fresh(r) for r in roles.values()):
            return
        Event = self.env["td.fire.event"]
        vals = {}
        for role, fname in (("alarms", "alarms_count"), ("faults", "faults_count"), ("disabled", "disabled_count")):
            r = roles[role]
            if self.fresh(r) and r["last_value"] is not None:
                v = int(round(r["last_value"]))
                if v != panel[fname]:
                    vals[fname] = v
        ts_all = [r["last_ts"] for r in roles.values() if self.fresh(r)]
        ts = max(ts_all)
        for role, fname, on_type, off_type in (
            ("sounders", "sounders_active", "sounders_on", "sounders_off"),
            ("brigade", "brigade_transmitted", "brigade_on", "brigade_off"),
        ):
            r = roles[role]
            if not self.fresh(r):
                continue
            on = r["last_text"] == "on"
            if on != panel[fname]:
                vals[fname] = on
                if on_type == "sounders_on":
                    n = self.env["td.fire.device"].search_count([("panel_id", "=", panel.id), ("type", "=", "sounder")])
                    text = "Оповіщувачі увімкнено (%d шт.)" % n if on else "Оповіщувачі вимкнено"
                else:
                    text = "Сигнал «Пожежа» передано на пульт ДСНС" if on else "Передачу на пульт завершено"
                Event._log(
                    on_type if on else off_type,
                    panel.code,
                    r["last_ts"],
                    text,
                    panel_id=panel.id,
                    signal_id=panel[dict(PANEL_ROLES)[role]].id,
                )
        s0 = s1 = None
        t0 = None
        r0 = roles["state"]
        if self.fresh(r0) and r0["last_text"]:
            t0 = r0["last_text"]
            s0 = states.zone_state(t0)
        r1 = roles["system"]
        v = None
        if self.fresh(r1):
            text = (r1["last_text"] or "").strip().lower()
            if text in states.MSV_STATES.values():
                v = {name: key for key, name in states.MSV_STATES.items()}[text]
            elif text.isdigit():
                v = int(text)
            elif r1["last_value"] is not None:
                v = int(round(r1["last_value"]))
            if v is not None:
                s1 = states.MSV_STATES.get(v)
                if v != panel.system_state:
                    vals["system_state"] = v
        known = [s for s in (s0, s1) if s]
        state = max(known, key=states.PRIORITY.get) if known else "unknown"
        if vals:
            panel.write(vals)
            self.changed += 1
        old = (panel.state, panel.raw_state)
        panel._set_state(state, t0 if t0 is not None else panel.raw_state, ts)
        if (panel.state, panel.raw_state) != old:
            self.changed += 1

    # --- системи (R-12 п. 7, R-13 п. 5–8) -----------------------------------------------------------------
    def _system(self, system):
        sigs = [system[field] for _role, field in SYSTEM_ROLES]
        if not any(sigs) and system.system_type != "sprinkler":
            return
        if not self.hit(*sigs):
            return
        if system.system_type == "sprinkler":
            return self._sprinkler(system)
        roles = {role: self.row(system[field]) for role, field in SYSTEM_ROLES if system[field]}
        present = [r for r in roles.values() if r]
        if not present:
            return
        Event = self.env["td.fire.event"]
        panel = system.panel_id
        source = system.source_id.code or panel.io_source_id.code or ""
        if all(r["status"] == "stale" for r in present):
            if not system.stale:
                system.write({"stale": True})
                ts = (
                    max(r["last_ts"] for r in present if r["last_ts"])
                    if any(r["last_ts"] for r in present)
                    else fields.Datetime.now()
                )
                system._set_state("unknown", ts)
                Event._log(
                    "comm_lost",
                    system.code,
                    fields.Datetime.now(),
                    "Немає даних від модуля вводу %s: %s" % (source, system.code),
                    level="warn",
                    system_id=system.id,
                    panel_id=panel.id,
                )
                self.changed += 1
            return
        fresh = {k: r for k, r in roles.items() if self.fresh(r)}
        if not fresh:
            return
        ts = max(r["last_ts"] for r in fresh.values())
        if system.stale:
            system.write({"stale": False})
            Event._log(
                "comm_restored",
                system.code,
                ts,
                "Дані модуля вводу %s відновлено: %s" % (source, system.code),
                system_id=system.id,
                panel_id=panel.id,
            )
            self.changed += 1

        def on(role, text="on"):
            r = fresh.get(role)
            return bool(r and r["last_text"] == text)

        def log(etype, text):
            Event._log(etype, system.code, ts, text, system_id=system.id, panel_id=panel.id)

        if system.system_type == "spark":
            fault_on, water_low = on("fault"), on("water", "low")
            if "fault" in fresh and fault_on != self._prev_on(system, "spark_fault", "spark_fault_ok"):
                log(
                    "spark_fault" if fault_on else "spark_fault_ok",
                    "Несправність іскрогасіння %s" % system.code
                    if fault_on
                    else "Іскрогасіння %s: несправність усунено" % system.code,
                )
            if "water" in fresh and water_low != self._prev_on(system, "spark_water_low", "spark_water_ok"):
                log(
                    "spark_water_low" if water_low else "spark_water_ok",
                    "Іскрогасіння %s: немає тиску води гасіння" % system.code
                    if water_low
                    else "Іскрогасіння %s: тиск води в нормі" % system.code,
                )
            r = fresh.get("count")
            if r and r["last_value"] is not None:
                c = int(round(r["last_value"]))
                if c != system.count_today:
                    if c > system.count_today:
                        log(
                            "spark",
                            "Іскрогасіння: іскру виявлено на магістралі аспірації (%d шт.), "
                            "гасіння спрацювало; за добу — %d." % (c - system.count_today, c),
                        )
                    system.write({"count_today": c, "count_ts": r["last_ts"]})
                    self.changed += 1
            if fault_on or water_low:
                new = "fault"
            elif on("state") or on("active"):
                new = "active"
            else:
                new = "ok"
        else:  # smoke
            opened, fault_on, battery = on("state", "open"), on("fault", "fault"), on("battery", "battery")
            if "state" in fresh and opened != self._prev_on(system, "smoke_open", "smoke_closed"):
                log(
                    "smoke_open" if opened else "smoke_closed",
                    "Димовидалення: клапани відкрито (%d шт.)" % system.vent_count
                    if opened
                    else "Димовидалення: клапани закрито",
                )
            if "fault" in fresh and fault_on != self._prev_on(system, "smoke_fault", "smoke_fault_ok"):
                log(
                    "smoke_fault" if fault_on else "smoke_fault_ok",
                    "Несправність щита димовидалення %s" % system.code
                    if fault_on
                    else "Щит димовидалення: несправність усунено",
                )
            if "battery" in fresh and battery != self._prev_on(system, "smoke_battery", "smoke_mains"):
                log(
                    "smoke_battery" if battery else "smoke_mains",
                    "Щит димовидалення %s працює від акумуляторів" % system.code
                    if battery
                    else "Щит димовидалення: живлення від мережі відновлено",
                )
            new = "fault" if fault_on else "battery" if battery else "active" if opened else "ok"
        if new != system.state or not system.state_ts:
            system._set_state(new, ts)
            self.changed += 1

    def _sprinkler(self, system):
        sig = system.pressure_signal_id
        row = self.row(sig)
        if not sig or not row or not row["last_ts"] or row["status"] in ("stale", "unknown"):
            new, ts = "unknown", (row or {}).get("last_ts") or fields.Datetime.now()
        else:
            new, ts = ("low_pressure" if row["status"] == "alarm" else "ok"), row["last_ts"]
        old = system.state
        if new == old and system.state_ts:
            return
        system._set_state(new, ts)
        self.changed += 1
        if new == old:
            return
        p = _fmt(row["last_value"]) if row else ""
        Event = self.env["td.fire.event"]
        if new == "low_pressure":
            Event._log(
                "sprinkler_low",
                system.code,
                ts,
                "Спринклерна система: тиск %s бар нижче норми %s бар" % (p, _fmt(sig.alarm_low)),
                system_id=system.id,
                panel_id=system.panel_id.id,
            )
        elif new == "ok" and old == "low_pressure":
            Event._log(
                "sprinkler_ok",
                system.code,
                ts,
                "Спринклерна система: тиск у нормі (%s бар)" % p,
                system_id=system.id,
                panel_id=system.panel_id.id,
            )

    # --- зв'язок (R-12) -----------------------------------------------------------------------------------
    def _comm_signals(self, panel, loops, zones):
        sigs = self.env["td.signal"]
        for _role, field in PANEL_ROLES:
            sigs |= panel[field]
        return (
            sigs
            | loops.filtered(lambda x: x.panel_id == panel).signal_id
            | zones.filtered(lambda z: z.panel_id == panel).signal_id
        )

    def _comm_hit(self, panel, loops, zones):
        return self.hit(*self._comm_signals(panel, loops, zones))

    def _comm(self, panel, loops, zones, now):
        source = panel.source_id
        if source and not source.read_enabled:
            panel._set_comm("off", now)
            return
        sigs = self._comm_signals(panel, loops, zones)
        stamps = []
        for sig in sigs:
            r = self.row(sig)
            if r and r["last_ts"] and r["status"] != "unknown" and r["last_quality"] != "bad":
                stamps.append(r["last_ts"])
        last_seen = max(stamps) if stamps else False
        if last_seen != panel.last_seen:
            panel.write({"last_seen": last_seen})
        if not last_seen:
            new = "lost"
        else:
            age = (now - last_seen).total_seconds()
            if age <= panel._get_param("comm_stale_after_s", 90):
                new = "online"
            elif age <= panel._get_param("comm_lost_after_s", 180):
                new = "stale"
            else:
                new = "lost"
        old = panel.comm
        panel._set_comm(new, now)
        if panel.comm != old:
            self.changed += 1
