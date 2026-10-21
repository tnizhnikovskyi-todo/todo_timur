"""`td.energy.action` (розширення): виконавець `chp` — 7 видів КГУ (D-15), верифікація за показаннями (R-09)."""

import hashlib
from datetime import timedelta

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.td_chp.tools import alarms, bus as chp_bus, command_flow as flow
from odoo.addons.td_chp.tools.signals import cparam_int as chp_cparam_int, write_off_reason
from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy_control import tools as control_tools
from odoo.addons.td_energy_control.models.td_energy_action import ACTIVE_RESOURCE, WRITE_OFF
from odoo.addons.td_telemetry.tools.ingest import parse_ts

from ..tools import energy_route as route

EXECUTING = ("executing",)


class TdEnergyAction(models.Model):
    _inherit = "td.energy.action"

    def _td_is_chp(self):
        """Дія моста: вид з виконавцем `chp`."""
        self.ensure_one()
        return self.kind_id.executor == route.EXECUTOR

    # --- prepare / запис / конфлікти -------------------------------------------------------------------------------
    def _td_prepare(self, kind, params, origin="manual", advice=None, undo_of=None):
        if kind.executor == route.EXECUTOR and not control_tools.cparam_bool(self.env, "write_enabled"):
            raise UserError(_(WRITE_OFF))
        return super()._td_prepare(kind, params, origin=origin, advice=advice, undo_of=undo_of)

    def _td_write_blocked_reason(self):
        """R-40 п.6 для `chp`: `td.energy_control.write_enabled`, далі засув запису td_chp (телеметрія, сигнал)."""
        if not self.ensure_one()._td_is_chp():
            return super()._td_write_blocked_reason()
        if not control_tools.cparam_bool(self.env, "write_enabled"):
            return "td.energy_control.write_enabled"
        return write_off_reason(self.env, route.target_signal(route.chp_kind(self.kind_code)))

    def _td_resource_conflict(self):
        """Одна активна дія на КГУ (R-08 п. 4); `chp_estop` дозволено завжди — він скасовує інші `queued`."""
        if not self.ensure_one()._td_is_chp():
            return super()._td_resource_conflict()
        others = self.sudo().search([("id", "!=", self.id), ("kind_id.resource", "=", "chp")])
        if self.kind_code == "chp_estop":
            for other in others.filtered(lambda r: r.state == "queued"):
                other._td_cancel_record()
            return self.browse()
        return others.filtered(lambda r: r.state in ACTIVE_RESOURCE)[:1]

    # --- виконання ------------------------------------------------------------------------------------------------
    def _td_enqueue(self):
        """`executor='chp'`: `td.command` (`origin='energy'`) у сигнал цілі `chp/ctl/*`; далі `_td_chp_verify`."""
        if not self.ensure_one()._td_is_chp():
            return super()._td_enqueue()
        env, me = self.env, self._me()
        now = dates.now_utc(env)
        kind = route.chp_kind(self.kind_code)
        why = self._td_write_blocked_reason()
        if why:
            return me._td_close("blocked", "заблоковано", _("Запис вимкнено: %s", why))
        sig = env["td.signal"].sudo().search([("code", "=", "chp/" + route.target_signal(kind))], limit=1)
        if not sig:
            return me._td_close("blocked", "заблоковано", _("Запис вимкнено: сигнал chp/%s", route.target_signal(kind)))
        value = flow.target_value(kind, self.params or {})
        ttl = chp_cparam_int(env, "command_ttl_s")
        cmd = (
            env["td.command"]
            .sudo()
            .with_context(td_energy_control_internal=True, mail_create_nolog=True)
            .create(
                {
                    "signal_id": sig.id,
                    "value": value,
                    "origin": "energy",
                    "expires_at": now + timedelta(seconds=ttl),
                    "requested_by": (self.second_by or self.confirmed_by or env.user).id,
                    "note": (self.summary or "")[:128],
                    "energy_action_id": self.id,
                }
            )
        )
        idem = hashlib.sha1(f"{self.id}:{self.kind_code}".encode()).hexdigest()
        me.write({"idem": idem, "state": "queued", "started_at": now, "command_id": cmd.id})
        me._td_close_activities()
        return True

    # --- верифікація (R-09) і строки ----------------------------------------------------------------------------------
    @api.model
    def _td_chp_verify(self, readings):
        """`estop/reset` — `chp/ctl/ack` (1 → done, 2 → failed з причиною R-06); `set_*` — цільовий сигнал."""
        by_code = {}
        for r in readings or ():
            if not isinstance(r, dict) or not str(r.get("code", "")).startswith("chp/") or r.get("value") is None:
                continue
            ts, reason = parse_ts(r.get("ts"))
            if not reason:
                by_code.setdefault(r["code"], []).append((ts, float(r["value"])))
        if not by_code:
            return
        recs = self.sudo().search([("kind_id.executor", "=", route.EXECUTOR), ("state", "in", EXECUTING)])
        for rec in recs:
            done_at = rec.command_id.done_at
            kind = route.chp_kind(rec.kind_code)
            sig = rec.command_id.signal_id
            if not done_at or not kind:
                continue
            exp = route.expectation(kind, rec.params or {}, (sig.address or {}).get("scale") or 1.0)
            me = rec._me()
            for ts, value in sorted(by_code.get(exp["signal"], [])):
                if ts < done_at:
                    continue
                if exp["kind"] == "ack":
                    if int(round(value)) == 1:
                        me._td_close("done", "Контролер прийняв команду")
                    elif int(round(value)) == 2:
                        unit = self.env["td.chp.unit"].sudo().search([], limit=1)
                        code = unit._td_value("ctl/ack_reason") if unit else None
                        why = alarms.ACK_REASONS.get(int(code or 0), "причина не вказана")
                        me._td_close("failed", "Контролер відхилив команду", f"Контролер відхилив команду: {why}")
                elif abs(value - exp["value"]) <= exp["tol"] + 1e-9:
                    me._td_close("done", "Значення прийнято контролером")
                if rec.state not in ACTIVE_RESOURCE:
                    break

    @api.model
    def _td_chp_expire(self):
        """Строк верифікації `td.chp.verify_timeout_s`: активна дія моста без підтвердження → `failed`."""
        t = dates.now_utc(self.env)
        timeout = chp_cparam_int(self.env, "verify_timeout_s")
        n = 0
        for rec in self.sudo().search(
            [("kind_id.executor", "=", route.EXECUTOR), ("state", "in", ACTIVE_RESOURCE), ("started_at", "!=", False)]
        ):
            if rec.started_at + timedelta(seconds=timeout) < t:
                cmd = rec.command_id
                rec._me()._td_close("failed", "не підтверджено", _("Контролер не підтвердив команду за %s с", timeout))
                if cmd and cmd.state == "queued":  # дія вже `failed`: хук td.command її не чіпає
                    cmd.sudo().action_cancel()
                n += 1
        return n

    # --- пульт КГУ: тік шини при зміні стану дії ------------------------------------------------------------------
    def write(self, vals):
        res = super().write(vals)
        if "state" in vals and any(r.kind_code in route.ENERGY_KINDS for r in self):
            chp_bus.tick(self.env, "command")
            chp_bus.tick(self.env, "journal")
        return res
