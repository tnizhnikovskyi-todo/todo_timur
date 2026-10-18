"""M-35 `td.energy.control` — API екрана «Керування» (AbstractModel): API-16…API-23, API-27, API-28."""

import logging
from datetime import date as date_cls
from datetime import datetime

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy.tools import dates

from .. import tools
from ..tools import config_builder, interlocks, journal, kinds

_logger = logging.getLogger(__name__)

G_USER = "td_energy.group_td_energy_user"
G_MANAGER = "td_energy.group_td_energy_manager"
G_CHIEF = "td_energy.group_td_energy_chief"
ADVICE_INTENT_ALIASES = kinds.ADVICE_INTENT_ALIASES  # R-55 п.6 (контракт із W3)


class TdEnergyControl(models.AbstractModel):
    _name = "td.energy.control"
    _description = "Енергетика: дані екрана Керування"

    # --- права -------------------------------------------------------------------------------------------------
    @api.model
    def _td_require_user(self):
        if not self.env.user.has_group(G_USER):
            raise AccessError(_("Немає доступу до Енергетики."))

    @api.model
    def _td_require_manager(self):
        self._td_require_user()
        if not self.env.user.has_group(G_MANAGER):
            raise AccessError(_("Керувати енергетикою може лише енергетик."))

    # --- API-16 --------------------------------------------------------------------------------------------------
    @api.model
    def get_control(self):
        self._td_require_user()
        env, user = self.env, self.env.user
        now = dates.now_utc(env)
        state = env["td.energy.control.state"].get()
        plant = config_builder.plant(env)
        peak = env["td.energy.scenario"].sudo().search([("code", "=", "peak")], limit=1)
        role = "chief" if user.has_group(G_CHIEF) else ("manager" if user.has_group(G_MANAGER) else "viewer")
        write_on = tools.cparam_bool(env, "write_enabled")
        auto_on = tools.cparam_bool(env, "automation_enabled")
        remote_on = tools.cparam_bool(env, "remote_switching_enabled")
        data = {
            "ts": tools.iso(now),
            "now_local": tools.local_hhmm(now),
            "meta": {
                "role": role,
                "can_prepare": role != "viewer",
                "can_confirm_b": role == "chief",
                "write_enabled": write_on,
                "automation_enabled": auto_on,
                "remote_switching_enabled": remote_on,
                "limit_kw": peak._td_params().get("limit_kw") if peak else None,
                "contract_kw": plant["contract_kw"],
                "refresh_s": 30,
            },
            "engine": self._td_part_engine(state, now, auto_on),
        }
        parts = (
            ("scenarios", lambda: self._td_part_scenarios(role, plant)),
            ("shed", lambda: self._td_part_shed(role, peak)),
            ("commands", lambda: self._td_part_commands(role, remote_on, write_on)),
            ("pending", lambda: self._td_part_pending(role)),
            ("schedule", lambda: self._td_part_schedule(now)),
        )
        for name, fn in parts:
            data[name] = self._td_safe(name, fn)
        page = self._td_safe("journal", lambda: journal.get_journal(env))
        data["journal"] = page["items"] if isinstance(page, dict) and "items" in page else page
        data["journal_more"] = bool(page.get("more")) if isinstance(page, dict) else False
        data.update(self._td_control_extra())
        return data

    @api.model
    def _td_control_extra(self):
        """Хук розширення: додаткові блоки відповіді `get_control` (порожній у базі)."""
        return {}

    @api.model
    def _td_safe(self, name, fn):
        try:
            with self.env.cr.savepoint():
                return fn()
        except Exception:
            _logger.exception("td_energy_control: частина %s", name)
            return {"error": "Не вдалося завантажити: %s" % name}

    @api.model
    def _td_part_engine(self, state, now, auto_on):
        hb = state.heartbeat_at
        age = int((now - hb).total_seconds()) if hb else None
        connected = bool(hb and age <= state._stale_s())
        mode = state.engine_mode
        if not auto_on:
            level, label = "warn", "Автоматику призупинено"
        elif not connected:
            level, label = "bad", "Збирач не на зв'язку · %s" % _age_text(age)
        elif mode == "auto":
            level, label = "ok", "Контролер ГРЩ і збирач на зв'язку · %s" % tools.local_hhmm(hb)
        else:
            level = "warn"
            label = "Автоматику призупинено" + (": %s" % state.engine_reason if state.engine_reason else "")
        return {
            "connected": connected,
            "mode": mode,
            "reason": state.engine_reason or None,
            "heartbeat_at": tools.iso(hb),
            "age_s": age,
            "config_version": state.config_version,
            "applied_version": state.applied_version,
            "label": label,
            "level": level,
        }

    @api.model
    def _td_part_scenarios(self, role, plant):
        env = self.env
        scs = env["td.energy.scenario"].sudo().search([])
        pending = (
            env["td.energy.action"]
            .sudo()
            .search([("state", "=", "awaiting_second"), ("kind_code", "in", ("scenario_toggle", "scenario_params"))])
        )
        pend = {a.params.get("scenario"): a.id for a in pending if isinstance(a.params, dict)}
        plant2 = {"contract_kw": plant["contract_kw"], "cos_target": plant["cos_phi_target"], "pfc_step_kvar": 35}
        node = env["td.energy.node"].sudo().search([("code", "=", "PFC-1")], limit=1)
        if node:
            plant2["pfc_step_kvar"] = node.pfc_step_kvar
        items = []
        for sc in scs:
            text, kind = sc._td_state_text()
            items.append(
                {
                    "id": sc.id,
                    "code": sc.code,
                    "title": sc.name,
                    "text": sc.description,
                    "enabled": bool(sc.enabled),
                    "applied": bool(sc.applied),
                    "state": sc.engine_state,
                    "state_kind": kind,
                    "status": text,
                    "chips": sc._td_chips(plant2),
                    "params": sc._td_params(),
                    "schema": sc._td_schema(),
                    "can_toggle": role != "viewer",
                    "pending_action_id": pend.get(sc.code),
                }
            )
        return {"on_count": sum(1 for i in items if i["enabled"]), "total": len(items), "items": items}

    @api.model
    def _td_part_shed(self, role, peak):
        env = self.env
        rows = env["td.energy.shed.item"].sudo().search([("active", "=", True)])
        shed_nodes = rows.mapped("node_id").ids
        crit = (
            env["td.energy.node"]
            .sudo()
            .search([("is_critical", "=", True), ("id", "not in", shed_nodes)], order="code")
        )
        return {
            "items": [
                {
                    "id": it.id,
                    "n": n,
                    "name": it.name,
                    "how": it.how,
                    "kw": it.kw_reducible,
                    "p_now_kw": round(it.p_now_kw, 1),
                    "node_code": it.node_id.code,
                    "active": it.active,
                }
                for n, it in enumerate(rows, 1)
            ],
            "sum_kw": sum(rows.mapped("kw_reducible")),
            "never": list(kinds.NEVER_TEXT),
            "never_nodes": crit.mapped("code"),
            "can_reorder": role != "viewer",
            "limit_kw": peak._td_params().get("limit_kw") if peak else None,
        }

    @api.model
    def _td_part_commands(self, role, remote_on, write_on):
        Kind = self.env["td.energy.command.kind"].sudo()
        base = Kind._td_base_values()
        return [k._td_tile(role != "viewer", remote_on, write_on, base) for k in Kind.search([("tile", "=", True)])]

    @api.model
    def _td_part_pending(self, role):
        if role == "viewer":
            return []
        user = self.env.user
        acts = self.env["td.energy.action"].sudo().search([("state", "=", "awaiting_second")])
        return [
            {
                "id": a.id,
                "summary": a.summary or a.kind_code,
                "prepared_by": a.prepared_by.name,
                "second_expires_at": tools.iso(a.second_expires_at),
                "can_confirm_second": user.id not in (a.prepared_by.id, a.confirmed_by.id),
            }
            for a in acts
        ]

    @api.model
    def _td_part_schedule(self, now):
        day = dates.local_day(now)
        Slot = self.env["td.energy.schedule.slot"]
        return {"now": Slot._td_now_hours(now), "rows": Slot._td_schedule_rows(day)}

    # --- API-17 prepare -------------------------------------------------------------------------------------------
    @api.model
    def _td_resolve_kind(self, kind, params):
        """Ключ вида або інтент рекомендації W3 (R-55 п.6) → (запис вида, параметри)."""
        if params is not None and not isinstance(params, dict):
            raise UserError(_("Параметри команди мають бути об'єктом."))
        params = dict(params or {})
        code = kind
        if kind in ADVICE_INTENT_ALIASES:
            alias = ADVICE_INTENT_ALIASES[kind]
            if alias is None:
                raise UserError(_("Команда «%s» не підтримується в цій версії.", kind))
            code, alias_params = alias
            params = {**params, **alias_params} if code == "scenario_toggle" else {**alias_params, **params}
            params.pop("intent", None)
            if code == "air_setpoint" and "setpoint_bar" not in params:
                sig = self.env["td.signal"].sudo().search([("code", "=", kinds.SIGNALS["air_sp"])], limit=1)
                if sig and sig.last_ts:
                    params["setpoint_bar"] = round(sig.last_value, 1)
        rec = self.env["td.energy.command.kind"].sudo().search([("code", "=", code)], limit=1)
        if not rec or not rec.active:
            raise UserError(_("Невідома команда: %s.", kind))
        return rec, params

    @api.model
    def prepare(self, kind, params=None, advice_id=None):
        self._td_require_manager()
        rec_kind, params = self._td_resolve_kind(kind, params)
        advice = self.env["td.energy.advice"].sudo().browse(advice_id).exists() if advice_id else None
        origin = "advice" if advice else "manual"
        action, token, rendered, blocked, reason = self.env["td.energy.action"]._td_prepare(
            rec_kind, params, origin=origin, advice=advice
        )
        return self._td_prepare_response(action, token, rendered, blocked, reason)

    @api.model
    def _td_prepare_response(self, action, token, rendered, blocked, reason):
        chief = self.env.user.has_group(G_CHIEF)
        return {
            "action_id": action.id,
            "token": token,
            "ttl_s": tools.cparam_int(self.env, "confirm_ttl_s", 60),
            "verify_timeout_s": tools.cparam_int(self.env, "verify_timeout_s", 30),
            "kind": action.kind_code,
            "cls": action.cls,
            "title": rendered["title"],
            "text": rendered["text"],
            "sub": rendered["sub"],
            "checks": action.checks or [],
            "blocked": bool(blocked),
            "blocked_reason": reason,
            "needs_second": bool(action.needs_second),
            "confirm_label": "Підтвердити (1/2)" if (action.cls == "B" and not chief) else "Виконати",
            "disabled_reason": reason if blocked else None,
        }

    # --- API-18…API-22 -----------------------------------------------------------------------------------------------
    @api.model
    def confirm(self, token):
        self._td_require_manager()
        return self.env["td.energy.action"]._td_confirm(token)

    @api.model
    def confirm_second(self, action_id):
        self._td_require_manager()
        return self.env["td.energy.action"].sudo().browse(action_id).exists()._td_confirm_second()

    @api.model
    def cancel(self, token):
        self._td_require_manager()
        return self.env["td.energy.action"]._td_cancel(token)

    @api.model
    def undo(self, action_id):
        self._td_require_manager()
        orig = self.env["td.energy.action"].sudo().browse(action_id).exists()
        if not orig:
            raise UserError(_("Дію не знайдено."))
        reason = orig._td_undo_reason()
        if reason:
            raise UserError(_("Скасування недоступне: %s.", reason))
        kind = orig.kind_id.undo_kind_id
        action, token, rendered, blocked, why = self.env["td.energy.action"]._td_prepare(
            kind, dict(orig.undo_params or {}), origin="undo", undo_of=orig
        )
        return self._td_prepare_response(action, token, rendered, blocked, why)

    @api.model
    def get_action(self, action_id):
        self._td_require_user()
        rec = self.env["td.energy.action"].sudo().browse(action_id).exists()
        if not rec:
            raise UserError(_("Дію не знайдено."))
        return rec._td_get_dict()

    # --- API-23, API-27, API-28 --------------------------------------------------------------------------------------
    @api.model
    def get_schedule(self, day=None):
        self._td_require_user()
        now = dates.now_utc(self.env)
        if isinstance(day, str):
            day = datetime.strptime(day, "%Y-%m-%d").date()
        elif not isinstance(day, date_cls):
            day = dates.local_day(now)
        Slot = self.env["td.energy.schedule.slot"]
        return {"day": day.isoformat(), "now": Slot._td_now_hours(now), "rows": Slot._td_schedule_rows(day)}

    @api.model
    def get_journal(self, limit=None, before_id=None, origin=None):
        self._td_require_user()
        return journal.get_journal(self.env, limit, before_id, origin)

    @api.model
    def get_node_actions(self, code):
        """API-27: кнопки панелі вузла (QS, BESS); інші вузли — `[]`."""
        self._td_require_user()
        env = self.env
        role_ok = env.user.has_group(G_MANAGER)
        remote_on = tools.cparam_bool(env, "remote_switching_enabled")
        write_on = tools.cparam_bool(env, "write_enabled")
        Kind = env["td.energy.command.kind"].sudo()
        ctx = interlocks.Ctx.from_env(env, dates.now_utc(env))
        if code == "QS":
            kind_code = "qs_open" if (ctx.t("qs_state") or "") == "closed" else "qs_close"
        elif code == "BESS":
            kind_code = "bess_stop" if ctx.v("bess_mode") == 1 else "bess_charge"
        else:
            return []
        kind = Kind.search([("code", "=", kind_code)], limit=1)
        tile = kind._td_tile(role_ok, remote_on, write_on)
        label = {
            "qs_close": "Увімкнути QS…",
            "qs_open": "Вимкнути QS…",
            "bess_charge": "Зарядити 50 кВт",
            "bess_stop": "Зупинити заряд",
        }[kind_code]
        return [
            {
                "code": kind_code,
                "label": label,
                "kind": kind_code,
                "cls": kind.cls,
                "enabled": tile["enabled"],
                "disabled_reason": tile["disabled_reason"],
            }
        ]


def _age_text(age):
    if age is None:
        return "немає звітів"
    if age < 60:
        return "%d с" % age
    if age < 3600:
        return "%d хв" % (age // 60)
    return "%d год" % (age // 3600)
