"""M-39 `td.energy.control.state` — стан керування (singleton): версія конфігурації, ETag, heartbeat, режим рушія."""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.td_energy.tools import dates

from .. import tools
from ..tools import bus, config_builder

_logger = logging.getLogger(__name__)
XMLID = "td_energy_control.state_main"
MODES = ("unknown", "off", "hold", "auto")


class TdEnergyControlState(models.Model):
    _name = "td.energy.control.state"
    _description = "Енергетика: стан керування"

    config_version = fields.Integer(string="Версія конфігурації", default=1, readonly=True)
    config_etag = fields.Char(string="ETag конфігурації", size=64, readonly=True)
    applied_version = fields.Integer(string="Застосована версія", default=0, readonly=True)
    engine_mode = fields.Selection(
        [("unknown", "Невідомо"), ("off", "Вимкнено"), ("hold", "Призупинено"), ("auto", "Автоматика")],
        string="Режим рушія",
        default="unknown",
        readonly=True,
    )
    engine_reason = fields.Char(string="Причина", size=128, readonly=True)
    engine_info = fields.Json(string="Дані рушія", readonly=True)
    heartbeat_at = fields.Datetime(string="Heartbeat", readonly=True)
    last_state_at = fields.Datetime(string="Останній звіт", readonly=True)
    last_config_pull_at = fields.Datetime(string="Остання вибірка конфігурації", readonly=True)
    collector_id = fields.Many2one("td.collector", string="Збирач", readonly=True, ondelete="set null")
    connected = fields.Boolean(string="На зв'язку", compute="_compute_connected")

    # --- права: пряма зміна лише з методів модуля ---------------------------------------------------------
    def write(self, vals):
        if not tools.is_internal(self.env):
            raise AccessError(_("Стан керування змінюється лише діями модуля."))
        return super().write(vals)

    def unlink(self):
        if not tools.is_internal(self.env):
            raise AccessError(_("Стан керування змінюється лише діями модуля."))
        return super().unlink()

    # --- обчислюване ----------------------------------------------------------------------------------------
    @api.depends("heartbeat_at")
    def _compute_connected(self):
        now = dates.now_utc(self.env)
        stale = self._stale_s()
        for rec in self:
            rec.connected = bool(rec.heartbeat_at and (now - rec.heartbeat_at).total_seconds() <= stale)

    @api.model
    def _stale_s(self):
        return tools.cparam_float(self.env, "heartbeat_stale_s", 30.0)

    # --- singleton ------------------------------------------------------------------------------------------
    @api.model
    def get(self):
        rec = self.env.ref(XMLID, raise_if_not_found=False)
        if rec and rec.exists():
            return rec.sudo().with_context(td_energy_control_internal=True)
        rec = self.sudo().with_context(td_energy_control_internal=True).search([], limit=1)
        if not rec:
            rec = self.sudo().with_context(td_energy_control_internal=True).create({})
        self.env["ir.model.data"]._update_xmlids([{"xml_id": XMLID, "record": rec, "noupdate": True}])
        return rec

    def bump(self):
        """config_version += 1 (атомарно) і перерахунок ETag; повертає нову версію (R-43 п.1)."""
        state = self.get()
        self.env.cr.execute(
            "UPDATE td_energy_control_state SET config_version = config_version + 1 WHERE id = %s "
            "RETURNING config_version",
            [state.id],
        )
        version = self.env.cr.fetchone()[0]
        state.invalidate_recordset(["config_version"])
        state._td_refresh_etag()
        return version

    def _td_refresh_etag(self):
        """Канонічний JSON конфігу → sha256 → `config_etag` (R-43 п.2). Повертає (cfg, etag)."""
        cfg = config_builder.build(self.env)
        etag = config_builder.etag(cfg)
        if self.config_etag != etag:
            self.write({"config_etag": etag})
        return cfg, etag

    # --- API-25 ---------------------------------------------------------------------------------------------
    @api.model
    def _td_report(self, body, collector=None):
        """Прийом звіту збирача (SPEC 7.4). Повертає `{"accepted_actions","accepted_events","rejected",…}`."""
        state = self.get()
        now = dates.now_utc(self.env)
        engine = body.get("engine") or {}
        prev_hb = state.heartbeat_at
        mode = engine.get("mode") if engine.get("mode") in MODES else "unknown"
        info = {
            k: engine.get(k)
            for k in ("started_at", "ticks", "tick_ms_p95", "writes_last_min", "controller_remote")
            if k in engine
        }
        info["collector"] = body.get("collector")
        applied = int(body.get("config_version_applied") or 0)
        vals = {
            "heartbeat_at": now,
            "last_state_at": now,
            "engine_mode": mode,
            "engine_reason": (engine.get("reason") or False) and str(engine["reason"])[:128],
            "engine_info": info,
            "applied_version": max(state.applied_version, applied),
        }
        if collector:
            vals["collector_id"] = collector.id
        state.write(vals)
        Scenario = self.env["td.energy.scenario"].sudo()
        for code, item in (body.get("scenarios") or {}).items():
            Scenario._td_engine_update(code, item, applied)
        Action = self.env["td.energy.action"].sudo()
        rejected, accepted_actions = [], 0
        for item in body.get("actions") or []:
            res = Action._td_on_engine(item)
            if res is True:
                accepted_actions += 1
            else:
                rejected.append({"id": item.get("id"), "reason": res})
        accepted_events = 0
        for ev in body.get("events") or []:
            res = Action._td_log_auto(ev)
            if res is True:
                accepted_events += 1
            else:
                rejected.append({"event_id": ev.get("event_id"), "reason": res})
        if not prev_hb or (now - prev_hb).total_seconds() > self._stale_s() * 4:
            self.env["td.energy.event"]._td_auto_resolve("control", code="CTRL-HEARTBEAT")
        bus.tick(self.env, "engine")
        bus.tick(self.env, "scenario")
        if accepted_actions:
            bus.tick(self.env, "action")
        return {
            "accepted_actions": accepted_actions,
            "accepted_events": accepted_events,
            "rejected": rejected,
            "config_version": state.config_version,
            "config_etag": state.config_etag or self._td_refresh_etag()[1],
            "server_time": tools.iso(now),
        }

    # --- крон нагляду (разд. 6) -----------------------------------------------------------------------------
    @api.model
    def _cron_watch(self):
        try:
            with self.env.cr.savepoint():
                self._td_watch()
        except Exception:
            _logger.exception("td_energy_control: крон нагляду")
        return True

    @api.model
    def _td_watch(self):
        if not dates.param_bool(self.env, "read_enabled"):
            return
        state = self.get()
        now = dates.now_utc(self.env)
        Event = self.env["td.energy.event"]
        auto = tools.cparam_bool(self.env, "automation_enabled")
        stale = self._stale_s() * 4
        if auto and (not state.heartbeat_at or (now - state.heartbeat_at).total_seconds() > stale):
            Event._td_log("bad", "control", "CTRL-HEARTBEAT", "Рушій автоматики не на зв'язку", dedup_min=15)
        elif state.heartbeat_at and (now - state.heartbeat_at).total_seconds() <= stale:
            Event._td_auto_resolve("control", code="CTRL-HEARTBEAT")
        old = Event.sudo().search(
            [("kind", "=", "control"), ("state", "in", ("active", "acked")), ("ts", "<", now - timedelta(hours=24))]
        )
        old = old.filtered(lambda e: e.code != "CTRL-HEARTBEAT")
        if old:
            old.write({"state": "resolved", "resolved_at": now})
        etag = config_builder.etag(config_builder.build(self.env))
        if state.config_etag and etag != state.config_etag:  # зміна зовнішніх даних (цілі BMS, тариф, критичність)
            state.bump()
        elif not state.config_etag:
            state._td_refresh_etag()
        bus.tick(self.env, "engine")
