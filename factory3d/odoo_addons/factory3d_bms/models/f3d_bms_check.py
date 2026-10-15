import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.addons.factory3d_telemetry.tools import thresholds

from ..tools import rules, schedule, titles
from .f3d_bms_hvac_unit import SIGNAL_FIELDS as _UNIT_FIELDS
from .f3d_bms_light_group import SIGNAL_FIELDS as GROUP_SIGNAL_FIELDS

_logger = logging.getLogger(__name__)

P = "factory3d.bms."
MAINS_CODE = "infra/ats/src1_ok"
FIRE_CODE = "fire/totals/system_state"
DERIVED_CODE = "BMS-DERIVED"
UNIT_SIGNAL_FIELDS = [f for f, _label in _UNIT_FIELDS]


class F3dBmsCheck(models.AbstractModel):
    """Перевірки відхилень (R-18…R-24): крон кожну хвилину + хук після прийому показань (R-20)."""

    _name = "f3d.bms.check"
    _description = "Будівля: перевірки відхилень"

    # --- параметри й контекст ----------------------------------------------------------------------
    @api.model
    def _f3d_params(self):
        icp = self.env["ir.config_parameter"].sudo()

        def num(key, default):
            try:
                return float(icp.get_param(P + key, default))
            except (TypeError, ValueError):
                return float(default)

        cal = (icp.get_param(P + "calendar_id") or "").strip()
        return {
            "read_enabled": icp.get_param(P + "read_enabled", "False") in ("True", "true", "1"),
            "calendar_id": int(cal) if cal.isdigit() else 0,
            "light_delay": num("light_check_delay_min", 10),
            "tol": num("light_norm_tolerance_pct", 5) / 100.0,
            "tol_pct": num("light_norm_tolerance_pct", 5),
            "hvac_delay": num("hvac_check_delay_min", 10),
            "cold_delay": num("cold_delay_min", 30),
            "min_work": num("indoor_min_work_c", 16.0),
            "min_off": num("indoor_min_off_c", 10.0),
            "deficit_kw": num("heat_deficit_kw", 20),
            "deficit_delay": num("heat_deficit_delay_min", 30),
            "heartbeat": num("check_heartbeat_min", 10),
        }

    @api.model
    def _calendar(self, obj, params):
        """R-18: календар об'єкта → параметр модуля → календар компанії."""
        if obj and obj.calendar_id:
            return obj.calendar_id
        if params["calendar_id"]:
            cal = self.env["resource.calendar"].sudo().browse(params["calendar_id"]).exists()
            if cal:
                return cal
        return self.env.company.resource_calendar_id

    @api.model
    def _suppression(self, now):
        """R-21: `(mains_lost, fire_active)`."""
        sigs = self.env["f3d.signal"].sudo().search([("code", "in", [MAINS_CODE, FIRE_CODE])])
        by_code = {s.code: s for s in sigs}
        mains = by_code.get(MAINS_CODE)
        fire = by_code.get(FIRE_CODE)
        mains_lost = bool(mains and rules.is_live(mains.status) and mains.last_value == 0)
        fire_active = bool(fire and rules.is_live(fire.status) and fire.last_text in ("alarm", "test"))
        if not fire_active and "f3d.fire.drill" in self.env:
            fire_active = bool(self.env["f3d.fire.drill"].sudo()._f3d_is_active_at(now))
        return mains_lost, fire_active

    # --- «з якого часу» (R-20) -----------------------------------------------------------------------
    @api.model
    def _sync_group(self, group, ts, params, mains_lost):
        sig = group.level_signal_id
        live = bool(sig) and rules.is_live(sig.status)
        level = min(100.0, max(0.0, sig.last_value)) if live else 0.0
        off, low = rules.light_since(
            live=live,
            level_pct=level,
            e_calc_raw=group.e_calc_raw,
            e_norm=group.e_norm,
            tol=params["tol"],
            off_since=group.off_since,
            low_since=group.low_since,
            ts=ts or fields.Datetime.now(),
            suppressed=mains_lost,
        )
        vals = {}
        if (group.off_since or False) != (off or False):
            vals["off_since"] = off
        if (group.low_since or False) != (low or False):
            vals["low_since"] = low
        if vals:
            group.with_context(tracking_disable=True, mail_notrack=True).write(vals)

    @api.model
    def _unit_inputs(self, unit):
        def live(sig):
            return bool(sig) and rules.is_live(sig.status)

        state = unit.state_signal_id.last_text if live(unit.state_signal_id) else None
        mode = unit.mode_signal_id.last_text if live(unit.mode_signal_id) else None
        indoor = unit.indoor_signal_id.last_value if live(unit.indoor_signal_id) else None
        any_live = any(live(s) for s in (unit.airflow_signal_id, unit.state_signal_id, unit.mode_signal_id))
        return state, mode, indoor, any_live

    @api.model
    def _sync_unit(self, unit, ts_off, ts_cold, params, mains_lost, fire_active):
        state, mode, indoor, _live = self._unit_inputs(unit)
        running_off = rules.not_running(state, mode)
        off, cold, cold_off = rules.unit_since(
            running_off=running_off,
            indoor=indoor,
            min_work=params["min_work"],
            min_off=params["min_off"],
            off_since=unit.off_since,
            cold_since=unit.cold_since,
            cold_off_since=unit.cold_off_since,
            ts_off=ts_off,
            ts_cold=ts_cold,
            suppressed=mains_lost or (fire_active and running_off),
        )
        vals = {}
        for name, new in (("off_since", off), ("cold_since", cold), ("cold_off_since", cold_off)):
            if (unit[name] or False) != (new or False):
                vals[name] = new
        if vals:
            unit.with_context(tracking_disable=True, mail_notrack=True).write(vals)

    @api.model
    def _f3d_bms_on_ingest(self, codes):
        """R-20: хук після `_f3d_ingest` — час початку умов за `last_ts` показань."""
        now = fields.Datetime.now()
        params = self._f3d_params()
        mains_lost, fire_active = self._suppression(now)
        parts = [c.split("/") for c in codes]
        groups = {p[2] for p in parts if p[0] == "lighting" and p[-1] == "level"}
        if groups:
            for group in self.env["f3d.bms.light.group"].sudo().search([("code", "in", sorted(groups))]):
                self._sync_group(group, group.level_signal_id.last_ts, params, mains_lost)
        units = {p[2] for p in parts if p[0] == "ventilation" and p[-1] in ("state", "mode", "indoor_c")}
        if units:
            for unit in (
                self.env["f3d.bms.hvac.unit"]
                .sudo()
                .search([("code", "in", sorted(units)), ("kind", "in", ("roofvent", "ahu"))])
            ):
                off_sigs = (unit.state_signal_id | unit.mode_signal_id).filtered("last_ts")
                ts_off = max(off_sigs.mapped("last_ts")) if off_sigs else now
                ts_cold = unit.indoor_signal_id.last_ts or now
                self._sync_unit(unit, ts_off, ts_cold, params, mains_lost, fire_active)

    # --- крон ---------------------------------------------------------------------------------------
    @api.model
    def _cron_check(self):
        """§6: один прогін перевірок (кожну хвилину)."""
        env = self.sudo()
        params = env._f3d_params()
        if not params["read_enabled"]:
            return False
        now = fields.Datetime.now()
        source = env.env["f3d.source"].search([("code", "=", DERIVED_CODE)], limit=1)
        try:
            with env.env.cr.savepoint():
                env._run_checks(now, params)
                env._notify_commands(now)
        except Exception as exc:
            _logger.exception("bms check")
            env.env.invalidate_all()
            if source:
                source.write({"state": "error", "last_error": str(exc)[:512]})
            return False
        if source:
            source.write({"state": "online", "last_ok": now, "last_error": False})
        return True

    def _notify_commands(self, now):
        """§11 п. 11: чаттер групи/установки для команд `origin='bms'` у стані `failed`/`expired` (один раз)."""
        Command = self.env["f3d.command"]
        cmds = Command.search(
            [
                ("origin", "=", "bms"),
                ("state", "in", ("failed", "expired")),
                ("write_date", ">=", now - timedelta(days=2)),
            ]
        )
        labels = dict(Command._fields["state"]._description_selection(self.env))
        for cmd in cmds:
            sig = cmd.signal_id
            group = self.env["f3d.bms.light.group"].search(
                ["|"] * (len(GROUP_SIGNAL_FIELDS) - 1) + [(f, "=", sig.id) for f in GROUP_SIGNAL_FIELDS], limit=1
            )
            unit = self.env["f3d.bms.hvac.unit"].search(
                ["|"] * (len(UNIT_SIGNAL_FIELDS) - 1) + [(f, "=", sig.id) for f in UNIT_SIGNAL_FIELDS], limit=1
            )
            obj = group or unit
            if not obj:
                continue
            marker = "Команда #%d: %s" % (cmd.id, labels.get(cmd.state, cmd.state))
            if self.env["mail.message"].search_count(
                [("model", "=", obj._name), ("res_id", "=", obj.id), ("body", "like", marker)]
            ):
                continue
            obj.message_post(
                body="%s — %s" % (_escape(marker), _escape(cmd.error or "без опису помилки")),
                subtype_xmlid="mail.mt_note",
            )

    def _reading(self, sig, text, now, params):
        """Показання стан-сигналу: лише при зміні тексту або через heartbeat (R-19, §10.1)."""
        if not sig:
            return None
        if sig.last_text == text and sig.last_ts and now - sig.last_ts < timedelta(minutes=params["heartbeat"]):
            return None
        return {"code": sig.code, "ts": now, "text": text, "q": "good"}

    def _run_checks(self, now, params):
        Group = self.env["f3d.bms.light.group"]
        Unit = self.env["f3d.bms.hvac.unit"]
        cache = {}
        mains_lost, fire_active = self._suppression(now)
        readings = []

        for group in Group.search([]):
            self._sync_group(group, now, params, mains_lost)
            sig = group.level_signal_id
            live = bool(sig) and rules.is_live(sig.status)
            level = min(100.0, max(0.0, sig.last_value)) if live else 0.0
            text = rules.light_check(
                live=live,
                level_pct=level,
                e_now_raw=group.e_calc_raw * level / 100.0,
                e_norm=group.e_norm,
                tol=params["tol"],
                interval=schedule.work_interval_at(self._calendar(group, params), now, cache),
                mains_lost=mains_lost,
                off_since=group.off_since,
                low_since=group.low_since,
                delay_min=params["light_delay"],
                now=now,
                check_off=group.check_off,
                check_norm=group.check_norm,
            )
            readings.append(self._reading(group.check_signal_id, text, now, params))

        units = Unit.search([("kind", "in", ("roofvent", "ahu"))])
        for unit in units:
            self._sync_unit(unit, now, now, params, mains_lost, fire_active)
            state, mode, indoor, live = self._unit_inputs(unit)
            text = rules.unit_check(
                live=live,
                mains_lost=mains_lost,
                fire_active=fire_active,
                running_off=rules.not_running(state, mode),
                interval=schedule.work_interval_at(self._calendar(unit, params), now, cache),
                indoor=indoor,
                min_work=params["min_work"],
                min_off=params["min_off"],
                required_in_work=unit.required_in_work,
                off_since=unit.off_since,
                cold_since=unit.cold_since,
                cold_off_since=unit.cold_off_since,
                hvac_delay_min=params["hvac_delay"],
                cold_delay_min=params["cold_delay"],
                now=now,
            )
            readings.append(self._reading(unit.check_signal_id, text, now, params))

        balance = self.env["f3d.bms.heat.balance"].search([], limit=1)
        if balance and balance.check_signal_id:
            n_live = len(units.filtered(lambda u: u.heat_signal_id and rules.is_live(u.heat_signal_id.status)))
            deficit = balance._f3d_bms_live()["deficit_kw"]
            text, since = rules.heat_check(
                live=bool(units) and n_live * 2 >= len(units),
                deficit=deficit,
                threshold=params["deficit_kw"],
                deficit_since=balance.deficit_since,
                delay_min=params["deficit_delay"],
                now=now,
            )
            if (balance.deficit_since or False) != (since or False):
                balance.with_context(tracking_disable=True, mail_notrack=True).write({"deficit_since": since})
            readings.append(self._reading(balance.check_signal_id, text, now, params))

        readings = [r for r in readings if r]
        if readings:
            self.env["f3d.signal"].with_context(f3d_bms_internal=True).sudo()._f3d_ingest(readings, src="module")
        self._enrich_requests(now, params, cache)
        self._journal(now)

    # --- заявки: доповнення назв (R-22 п. 3) -------------------------------------------------------------
    def _enrich_requests(self, now, params, cache):
        Request = self.env["maintenance.request"].sudo()
        reqs = Request.search(
            [
                ("f3d_bms_enriched", "=", False),
                ("f3d_signal_id.module", "=", "bms"),
                "|",
                ("f3d_signal_id.code", "=like", "%/check"),
                ("f3d_signal_id.code", "=like", "lighting/groups/%/faults"),
            ]
        )
        for req in reqs:
            sig = req.f3d_signal_id
            kind, obj_code = rules.object_of(sig.code)
            vals = {"f3d_bms_enriched": True}
            try:
                info = self._request_texts(req, kind, obj_code, now, params, cache)
            except Exception:
                _logger.exception("bms enrich %s", req.id)
                info = None
            if info:
                if info.get("name"):
                    vals.update(name=info["name"], f3d_value=info["value"], f3d_threshold=info["threshold"])
                if info.get("line"):
                    vals["description"] = (req.description or "") + "\n" + _escape(info["line"])
            req.with_context(mail_notrack=True, tracking_disable=True).write(vals)

    def _request_texts(self, req, kind, obj_code, now, params, cache):
        rule = req.f3d_bms_rule
        if kind == "group":
            g = self.env["f3d.bms.light.group"].search([("code", "=", obj_code)], limit=1)
            if not g:
                return None
            zone, level = g.zone_id.name or "", g.level_pct
            if rule == "light_off":
                return titles.light_off(
                    g.code, zone, level, g.e_norm, g.e_now, g.dali_group, g.panel_id.code, g.off_since
                )
            if rule == "light_low":
                return titles.light_low(
                    g.code, zone, level, g.e_norm, g.e_now, g.e_calc, params["tol_pct"], g.low_since
                )
            if rule == "light_fault":
                return {"line": titles.faults_line(g.faulty, g.panel_id.code, g.dali_group)}
        elif kind == "unit":
            u = self.env["f3d.bms.hvac.unit"].search([("code", "=", obj_code)], limit=1)
            if not u:
                return None
            zone = u.zone_id.name or ""
            if rule == "unit_off":
                return titles.unit_off(u.code, zone, u.mode_label, u.airflow_m3h, u.state, u.off_since)
            if rule == "cold":
                in_work = schedule.work_interval_at(self._calendar(u, params), now, cache) is not None
                state, mode, indoor, _live = self._unit_inputs(u)
                indoor = u.indoor_c if indoor is None else indoor
                return titles.cold(
                    u.code,
                    zone,
                    indoor,
                    params["min_work"] if in_work else params["min_off"],
                    u.setpoint_day_c,
                    u.cold_since if in_work else u.cold_off_since,
                )
        elif kind == "boiler" and rule == "heat_deficit":
            b = self.env["f3d.bms.heat.balance"].search([], limit=1)
            if not b:
                return None
            live = b._f3d_bms_live()
            return titles.heat_deficit(
                live["deficit_kw"],
                live["heat_need_kw"],
                live["heat_need_kw"] - live["deficit_kw"],
                params["deficit_kw"],
                live["chp_heat_now_kw"],
                live["chp_source"],
                live["boilers_on"],
                b.boilers,
                live["boiler_state"],
            )
        return None

    # --- журнал відхилень (R-22 п. 2) ----------------------------------------------------------------
    def _object_zones(self):
        zones = {}
        for model in ("f3d.bms.light.group", "f3d.bms.hvac.unit", "f3d.bms.light.panel"):
            for rec in self.env[model].search([]):
                zones[(model, rec.code)] = rec.zone_id.id
        return zones

    def _journal(self, now):
        Dev = self.env["f3d.bms.deviation"]
        Signal = self.env["f3d.signal"]
        open_eps = Dev.search([("state", "=", "open")])
        by_signal = {ep.signal_id.id: ep for ep in open_eps}
        alarmed = Signal.search([("module", "=", "bms"), ("status", "=", "alarm")])
        zones = None
        for sig in alarmed:
            req = sig.maintenance_request_id
            cfg = sig._f3d_cfg()
            threshold, rel = thresholds.breach_info(cfg, sig.last_value) if sig.kind != "state" else (None, "")
            ep = by_signal.get(sig.id)
            if ep:
                vals = {}
                if req and ep.request_id != req:
                    vals["request_id"] = req.id
                if sig.kind != "state" and rel:
                    value = rules.worst(ep.value, sig.last_value, rel)
                    if value != ep.value:
                        vals["value"] = value
                if vals:
                    ep.write(vals)
                continue
            if zones is None:
                zones = self._object_zones()
            kind, obj_code = rules.object_of(sig.code)
            model = {"group": "f3d.bms.light.group", "unit": "f3d.bms.hvac.unit", "panel": "f3d.bms.light.panel"}.get(
                kind
            )
            if sig.kind == "state":
                value, threshold = (req.f3d_value, req.f3d_threshold) if req else (0.0, 0.0)
            else:
                value = sig.last_value
            Dev.create(
                {
                    "name": (req.name if req else "%s: %s" % (sig.name, sig.last_text or ""))[:256],
                    "signal_id": sig.id,
                    "rule": rules.rule_of(sig.code, sig.last_text),
                    "object_kind": kind or False,
                    "object_code": obj_code or False,
                    "zone_id": zones.get((model, obj_code)) or False,
                    "started": sig.status_since or now,
                    "state": "open",
                    "value": value,
                    "threshold": threshold or 0.0,
                    "unit": sig.unit or False,
                    "request_id": req.id if req else False,
                }
            )
        for ep in open_eps:
            sig = ep.signal_id
            if sig.status == "alarm":
                continue
            vals = {"state": "closed", "ended": max(sig.status_since or now, ep.started)}
            if sig.status == "stale":
                vals["note"] = "закрито: немає даних"
            ep.write(vals)

    # --- повторна установка даних (§4.4) ---------------------------------------------------------------
    @api.model
    def f3d_bms_reinstall_data(self):
        if not self.env.user.has_group("factory3d_base.group_f3d_admin"):
            raise AccessError("Повторну установку даних будівлі виконує лише адміністратор «Завод 3D».")
        from .. import hooks  # noqa: PLC0415

        data = hooks.run_install(self.sudo().env)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Будівля",
                "message": "Установку даних виконано: %s" % data.get("state", "—"),
                "type": "success",
                "sticky": False,
            },
        }


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
