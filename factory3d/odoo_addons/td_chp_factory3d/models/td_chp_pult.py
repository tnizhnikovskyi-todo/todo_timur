"""M-B2 `td.chp.pult` (розширення): хуки C-chp-03 — усі 9 видів команд КГУ йдуть через td_energy_control (D-15).

Перевизначено цілком `_td_route`, `_td_dispatch`, `_td_command_rows`, `_td_pending_rows`, `_td_flags`: команда живе в
одному сховищі й одному журналі з Пультом енергетика (`td.energy.action`), `td.chp.command` не створюється. Блокування
R-07 td_chp діють до й після викликів td_energy_control (RB-01); стоп-крани — `td.energy_control.*`.
"""

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.td_chp.tools import command_flow as flow, interlocks
from odoo.addons.td_chp.tools.signals import Snapshot, iso

from ..tools import energy_route as route

G_ENERGY_MANAGER = "td_energy.group_td_energy_manager"
REF_PREFIX = "energy:"
WARN_STATES = ("failed", "blocked", "expired")
NOT_YOURS = "Команду не знайдено."


class TdChpPult(models.AbstractModel):
    _inherit = "td.chp.pult"

    # --- хуки C-chp-03 ----------------------------------------------------------------------------------------------
    @api.model
    def _td_route(self, kind):
        """`'energy'`, якщо є `td.energy.control` і відповідний вид команди активний; інакше `None` (потік td_chp)."""
        code = route.energy_code(kind)
        if not code or "td.energy.control" not in self.env:
            return None
        found = self.env["td.energy.command.kind"].sudo().search_count([("code", "=", code), ("active", "=", True)])
        return "energy" if found else None

    @api.model
    def _td_flags(self, unit):
        return {"bridge": self._td_route("start") is not None, "remote_switching": bool(unit._td_remote_switching())}

    @api.model
    def _td_dispatch(self, op, unit, kind=None, params=None, ref=None, token=None):
        """RB-01: `prepare/confirm/confirm_second/cancel/get` → `td.energy.control`; посилання `chp:` — потік td_chp."""
        if op == "prepare":
            if self._td_route(kind) is None:
                return super()._td_dispatch(op, unit, kind=kind, params=params, ref=ref, token=token)
            return self._td_energy_prepare(unit, kind, params)
        if ref.startswith("chp:"):
            return super()._td_dispatch(op, unit, kind=kind, params=params, ref=ref, token=token)
        action = self._td_energy_action(ref)
        control = self.env["td.energy.control"]
        if op == "get":
            return self._td_energy_dto(action, control.get_action(action.id))
        if op == "cancel":
            self._td_energy_check_token(action, token)
            return self._td_energy_dto(action, control.cancel(token))
        if op == "confirm":
            self._td_energy_check_token(action, token)
            if action.state == "prepared":
                blocked = self._td_energy_gate(unit, action)
                if blocked:
                    return self._td_energy_dto(action, action._td_response(reason=blocked))
            return self._td_energy_dto(action, control.confirm(token))
        if action.state == "awaiting_second":
            blocked = self._td_energy_gate(unit, action)
            if blocked:
                return self._td_energy_dto(action, action._td_response(reason=blocked))
        return self._td_energy_dto(action, control.confirm_second(action.id))

    @api.model
    def _td_command_rows(self, unit, limit, before):
        """RB-03: `td.energy.action` видів КГУ й дій автоматики `auto_*chp*`, без `prepared/cancelled`."""
        domain = [
            "|",
            ("kind_code", "in", route.ENERGY_KINDS),
            ("kind_code", "=ilike", route.AUTO_LIKE),
            ("state", "not in", ("prepared", "cancelled")),
        ]
        if unit.energy_node_id:
            domain.append(("node_id", "=", unit.energy_node_id.id))
        rows = self.env["td.energy.action"].sudo().search(domain, order="id desc", limit=limit * 3 + 50)
        out = [self._td_energy_row(rec) for rec in rows]
        if before:
            cut = iso(before)
            out = [r for r in out if r["ts"] < cut]
        out.sort(key=lambda r: (r["ts"], r["id"]), reverse=True)
        return out[:limit]

    @api.model
    def _td_pending_rows(self, unit):
        """RB-04: дії в `awaiting_second`; `can_second` — енергетик, не ініціатор і не перший підтверджувач."""
        user = self.env.user
        can_role = user.has_group(G_ENERGY_MANAGER)
        domain = [("kind_code", "in", route.ENERGY_KINDS), ("state", "=", "awaiting_second")]
        rows = []
        for rec in self.env["td.energy.action"].sudo().search(domain):
            kind = route.chp_kind(rec.kind_code)
            rows.append(
                {
                    "ref": REF_PREFIX + str(rec.id),
                    "kind": kind,
                    "title": f"{flow.KINDS[kind]['label']} {flow.short_name(unit)}",
                    "prepared_by": rec.prepared_by.name,
                    "can_second": bool(can_role and user.id not in (rec.prepared_by.id, rec.confirmed_by.id)),
                    "second_expires_at": iso(rec.second_expires_at),
                }
            )
        return rows

    # --- допоміжні --------------------------------------------------------------------------------------------------
    @api.model
    def _td_preflight(self, unit, kind):
        """Блокування R-07 td_chp маршрутизованого виду (без `rsw` і `write_enabled`): `(checks, blocked, reason)`."""
        checks = interlocks.build_checks(unit, kind, Snapshot(self.env), routed=True)
        blocked, reason = interlocks.verdict(checks, kind)
        return checks, blocked, reason

    @api.model
    def _td_energy_action(self, ref):
        if not isinstance(ref, str) or not ref.startswith(REF_PREFIX) or not ref[len(REF_PREFIX) :].isdigit():
            raise UserError(_("Невірне посилання на команду."))
        action = self.env["td.energy.action"].sudo().browse(int(ref[len(REF_PREFIX) :])).exists()
        if not action or action.kind_code not in route.ENERGY_KINDS:
            raise UserError(_(NOT_YOURS))
        return action

    @api.model
    def _td_energy_check_token(self, action, token):
        if self.env["td.energy.action"]._td_by_token(token) != action:
            raise UserError(_("Токен не відповідає команді."))

    @api.model
    def _td_energy_gate(self, unit, action):
        """Повторний preflight td_chp перед `confirm`/`confirm_second`: невдача → дія `blocked`, повертає причину."""
        _checks, blocked, reason = self._td_preflight(unit, route.chp_kind(action.kind_code))
        if not blocked:
            return None
        action._me()._td_close("blocked", "заблоковано", reason)
        return reason

    @api.model
    def _td_energy_prepare(self, unit, kind, params):
        """RB-01 `prepare` + RB-02: preflight td_chp → `td.energy.control.prepare` → DTO API-05 (+ `ref`)."""
        params = flow.normalize(kind, params)
        checks, pre_blocked, pre_reason = self._td_preflight(unit, kind)
        res = self.env["td.energy.control"].prepare(route.energy_code(kind), params)
        action = self.env["td.energy.action"].sudo().browse(res["action_id"])
        if pre_blocked and action.state == "prepared":
            action._me()._td_close("blocked", "заблоковано", pre_reason)
            res = dict(res, token=None)
        blocked = bool(res.get("blocked") or pre_blocked)
        reason = pre_reason if pre_blocked else res.get("blocked_reason")
        texts = {"title": res["title"], "text": res["text"], "sub": res["sub"]}
        if kind not in ("start", "stop"):  # підписи видів моста — за R-08 td_chp (українські назви режимів)
            rendered = flow.render(kind, params, unit)
            texts = {"title": rendered["title"], "text": rendered["text"], "sub": rendered["sub"]}
        return {
            "ref": REF_PREFIX + str(action.id),
            "action_id": action.id,
            "token": res.get("token"),
            "ttl_s": res.get("ttl_s"),
            "verify_timeout_s": res.get("verify_timeout_s"),
            "kind": kind,
            "cls": res.get("cls"),
            **texts,
            "checks": checks + list(res.get("checks") or []),
            "blocked": blocked,
            "blocked_reason": reason,
            "needs_second": bool(res.get("needs_second")),
            "confirm_label": res.get("confirm_label"),
            "disabled_reason": reason if blocked else None,
        }

    @api.model
    def _td_energy_dto(self, action, res):
        """RB-02: відповідь `confirm/confirm_second/get/cancel` td_energy_control (API-18…22) + `ref`."""
        out = dict(res or {})
        out.pop("id", None)
        out["ref"] = REF_PREFIX + str(action.id)
        return out

    @api.model
    def _td_energy_row(self, rec):
        """Рядок API-03 для дії (RB-03)."""
        kind = route.chp_kind(rec.kind_code)
        if kind:
            text = flow.journal_text(flow.KINDS[kind]["label"], rec.state, rec.prepared_by.name, rec.second_by.name)
        else:
            text = rec.summary or rec.kind_code or ""
        return {
            "type": "command",
            "id": rec.id,
            "ref": REF_PREFIX + str(rec.id),
            "ts": iso(rec.finished_at or rec.prepared_at),
            "level": "warn" if rec.state in WARN_STATES else "info",
            "text": text,
            "ack_state": None,
            "state": rec.state,
        }
