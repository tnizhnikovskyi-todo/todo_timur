"""M-06 `td.chp.pult` — API пульта (AbstractModel): API-01…07 (SPEC §7), хуки C-chp-03.

Читання — `group_td_chp_user`; `ack`, `command`, `maintenance_done` — operator; `sim` — `td_factory3d.group_td_manager`.

Хуки (D-15): у базі працює потік `td.chp.command`; міст `td_chp_factory3d` (за наявності `td.energy.control`)
перевизначає `_td_route/_td_dispatch/_td_command_rows/_td_pending_rows/_td_flags` ЦІЛКОМ — усі 9 видів команд ідуть
у `td_energy_control` (єдиний механізм і журнал команд із пультом енергетики), `td.chp.command` не створюється.
"""

import hashlib
import json
import re

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from ..tools import alarms, bus, interlocks, kpi, trend
from ..tools import command_flow as flow
from ..tools.signals import Snapshot, cparam_bool, cparam_int, iso, now, parse_iso

G_USER = "td_chp.group_td_chp_user"
G_OPERATOR = "td_chp.group_td_chp_operator"
G_CHIEF = "td_chp.group_td_chp_chief"
G_MANAGER = "td_factory3d.group_td_manager"
CYL_IDS = [f"{row}{n}" for row in "AB" for n in range(1, 9)]
REF_RE = re.compile(r"^(chp|energy):\d+$")
SIM_CODES = (  # UI-09: сценарії блоку «Імітація»
    "chp_overheat",
    "chp_hot_return",
    "chp_gas_leak",
    "chp_fire",
    "chp_rocof",
    "chp_no_permit",
    "chp_no_gas",
    "ctl_local",
    "blackout",
)
SIM_ACTIVE = ("running", "stopping")
OPS = ("prepare", "confirm", "confirm_second", "cancel", "get")
JOURNAL_LIMIT_MAX = 200


class TdChpPult(models.AbstractModel):
    _name = "td.chp.pult"
    _description = "КГУ: API пульта"

    # --- права й розбір аргументів ---------------------------------------------------------------------------------
    @api.model
    def _td_require_user(self):
        if not self.env.user.has_group(G_USER):
            raise AccessError(_("Немає доступу до Когенерації."))

    @api.model
    def _td_require_operator(self):
        self._td_require_user()
        if not self.env.user.has_group(G_OPERATOR):
            raise AccessError(_("Виконувати дії з КГУ може лише енергетик."))

    @api.model
    def _td_unit(self, code=None):
        return self.env["td.chp.unit"]._td_get(code)

    # --- API-01 -----------------------------------------------------------------------------------------------------
    @api.model
    def get_state(self, unit=None, etag=None):
        self._td_require_user()
        unit = self._td_unit(unit)
        env = self.env
        if not cparam_bool(env, "read_enabled"):
            return {"read_disabled": True}
        t = now(env)
        snap = Snapshot(env, t)
        v, th = snap.values(), unit._td_th()
        user = env.user
        flags = self._td_flags(unit)
        routed = self._td_route("start") is not None
        checks = interlocks.build_checks(unit, "start", snap, routed=routed)
        blocked, _reason = interlocks.verdict(checks, "start")
        body = {
            "read_enabled": True,
            "stale": snap.get("ctl/state") is None,
            "unit": {
                "code": unit.code,
                "name": unit.name,
                "p_nom_kw": unit.p_nom_kw,
                "cylinders": unit.cylinders,
                "passport": unit._td_passport(),
                "assumption": bool(unit.is_assumption),
                "th": th,
            },
            "caps": {
                "operate": user.has_group(G_OPERATOR),
                "chief": user.has_group(G_CHIEF),
                "sim": user.has_group(G_MANAGER),
                "write": cparam_bool(env, "write_enabled"),
                "rsw": bool(flags.get("remote_switching")),
                "bridge": bool(flags.get("bridge")),
            },
            "v": v,
            "u": snap.units(),
            "st": snap.statuses(),
            "k": kpi.compute(v, th["lhv_kwh_m3"], th["co2_kg_m3"]),
            "cyl": kpi.cylinders(CYL_IDS, v, th),
            "alarm": self._td_alarm_dto(unit, v.get("alarm/code"), v, th),
            "trip": self._td_trip_dto(v.get("alarm/trip"), v, th),
            "il": {"ok": not blocked, "list": checks},
            "pending": self._td_pending_rows(unit),
            "jr": self._td_journal(unit, 8, None)["items"],
            "to": self.get_maintenance(unit.code),
        }
        ver = hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
        if etag and etag == ver:
            return {"not_modified": True}
        return {"ver": ver, "ts": iso(t), "age_s": snap.age("ctl/state"), **body}

    @api.model
    def _td_alarm_dto(self, unit, code, v, th):
        if not code:
            return None
        text, node = alarms.alarm_info(code, v, th)
        last = (
            self.env["td.chp.event"]
            .sudo()
            .search([("unit_id", "=", unit.id), ("kind", "=", "alarm"), ("level", "=", "alarm")], limit=1)
        )
        return {"code": int(code), "text": text, "node": node, "acked": bool(last) and last.ack_state != "new"}

    @api.model
    def _td_trip_dto(self, code, v, th):
        if not code:
            return None
        _level, text, _node = alarms.trip_info(code, v, th)
        return {"code": int(code), "text": text}

    # --- API-02 -----------------------------------------------------------------------------------------------------
    @api.model
    def get_trend(self, unit=None, range_h=24):
        self._td_require_user()
        self._td_unit(unit)
        if range_h not in trend.STEP_S:
            raise UserError(_("Період тренда: 1 або 24 години."))
        return trend.build(self.env, range_h)

    # --- API-03 -----------------------------------------------------------------------------------------------------
    @api.model
    def get_journal(self, unit=None, limit=50, before=None):
        self._td_require_user()
        return self._td_journal(self._td_unit(unit), limit, parse_iso(before))

    @api.model
    def _td_journal(self, unit, limit, before):
        """R-12: події + рядки-команди з хука `_td_command_rows`, `ts desc, id desc`; `before` — naive UTC datetime."""
        limit = max(1, min(int(limit or 50), JOURNAL_LIMIT_MAX))
        domain = [("unit_id", "=", unit.id)]
        if before:
            domain.append(("ts", "<", before))
        events = self.env["td.chp.event"].sudo().search(domain, order="ts desc, id desc", limit=limit + 1)
        rows = [
            {
                "type": "event",
                "id": e.id,
                "ref": f"event:{e.id}",
                "ts": iso(e.ts),
                "level": e.level,
                "text": e.text,
                "ack_state": e.ack_state,
                "state": None,
            }
            for e in events
        ]
        rows += self._td_command_rows(unit, limit + 1, before)
        rows.sort(key=lambda r: (r["ts"], r["id"]), reverse=True)
        return {"items": rows[:limit], "more": len(rows) > limit}

    # --- API-04 -----------------------------------------------------------------------------------------------------
    @api.model
    def ack(self, unit=None, ids=None):
        self._td_require_operator()
        self._td_unit(unit)
        if ids is not None and (not isinstance(ids, list) or not all(isinstance(i, int) for i in ids)):
            raise UserError(_("Невірний перелік повідомлень."))
        return {"acked": self.env["td.chp.event"]._td_ack(ids)}

    # --- API-05 -----------------------------------------------------------------------------------------------------
    @api.model
    def command(self, op, unit=None, kind=None, params=None, ref=None, token=None):
        self._td_require_operator()
        unit = self._td_unit(unit)
        if op not in OPS:
            raise UserError(_("Невідома операція: %s.", op))
        if op == "prepare":
            flow.kind_info(kind)
        else:
            if not isinstance(ref, str) or not REF_RE.match(ref):
                raise UserError(_("Невірне посилання на команду."))
            if op in ("confirm", "cancel") and (not isinstance(token, str) or not token):
                raise UserError(_("Не вказано токен підтвердження."))
        return self._td_dispatch(op, unit, kind=kind, params=params, ref=ref, token=token)

    # --- API-06 -----------------------------------------------------------------------------------------------------
    @api.model
    def get_maintenance(self, unit=None):
        self._td_require_user()
        unit = self._td_unit(unit)
        return [r._td_dto() for r in unit.rule_ids.sudo()]

    @api.model
    def maintenance_done(self, rule_id):
        self._td_require_operator()
        rule = self.env["td.chp.maintenance.rule"].sudo().browse(rule_id if isinstance(rule_id, int) else 0).exists()
        if not rule:
            raise UserError(_("Правило ТО не знайдено."))
        rule.action_td_done()
        return self.get_maintenance(rule.unit_id.code)

    # --- API-07 -----------------------------------------------------------------------------------------------------
    @api.model
    def sim(self, op, code=None, params=None):
        self._td_require_user()
        if not self.env.user.has_group(G_MANAGER):
            raise AccessError(_("Імітація доступна лише менеджеру."))
        if "td.sim.scenario" not in self.env:
            if op == "list":
                return {"available": False, "scenarios": []}
            raise UserError(_("Емулятор недоступний: модуль td_iot_sim не встановлено."))
        Scenario = self.env["td.sim.scenario"]
        if op == "list":
            rows = Scenario.sudo().search([("code", "in", SIM_CODES)], order="sequence, id")
            return {"available": True, "scenarios": [{"code": s.code, "label": s.name} for s in rows]}
        if op == "reset":
            runs = self._td_sim_runs()
            if runs:
                runs.action_stop()
            return {"ok": True, "stopped": len(runs)}
        if code not in SIM_CODES:
            raise UserError(_("Невідомий сценарій: %s.", code))
        scenario = Scenario.sudo().search([("code", "=", code)], limit=1)
        if not scenario:
            raise UserError(_("Сценарій %s не знайдено.", code))
        if op == "start":
            if params is not None and not isinstance(params, dict):
                raise UserError(_("Параметри сценарію мають бути об'єктом."))
            wizard = self.env["td.sim.run.wizard"].create(
                {"scenario_id": scenario.id, "params_text": json.dumps(params or scenario.params_default or {})}
            )
            res = wizard.action_confirm() or {}
            return {"ok": True, "code": code, "run_id": res.get("res_id")}
        if op == "stop":
            runs = self._td_sim_runs(code)
            if runs:
                runs.action_stop()
            return {"ok": True, "stopped": len(runs)}
        raise UserError(_("Невідома операція: %s.", op))

    @api.model
    def _td_sim_runs(self, code=None):
        codes = [code] if code else list(SIM_CODES)
        return self.env["td.sim.run"].search([("scenario_id.code", "in", codes), ("state", "in", SIM_ACTIVE)])

    # --- хуки для мосту (C-chp-03, D-15) ----------------------------------------------------------------------------
    @api.model
    def _td_route(self, kind):
        """Куди йде вид команди: `None` — потік td_chp (`td.chp.command`), `'energy'` — td_energy_control (міст).

        Міст повертає `'energy'` для ВСІХ 9 видів, якщо є `td.energy.control`. Від результату залежать R-07 (для
        `'energy'` не перевіряються `rsw` і `write_enabled`) і `caps.bridge`.
        """
        return None

    @api.model
    def _td_dispatch(self, op, unit, kind=None, params=None, ref=None, token=None):
        """Єдина точка диспетчеризації `command(op, …)`: `op ∈ prepare|confirm|confirm_second|cancel|get` → DTO API-05.
        Викликається ПІСЛЯ перевірки груп (operator) і розбору `unit` (запис `td.chp.unit`); `ref` — `chp:<id>` або
        `energy:<id>`. База — потік `td.chp.command`; міст перевизначає метод цілком (усі 9 видів → td_energy_control).
        """
        Command = self.env["td.chp.command"]
        if op == "prepare":
            rec, tok, rendered, blocked, reason = Command._td_prepare(unit, kind, params)
            return self._td_prepare_response(rec, tok, rendered, blocked, reason)
        if not ref.startswith("chp:"):
            raise UserError(_("Команда не належить КГУ: %s.", ref))
        rec = Command.sudo().browse(int(ref.split(":")[1])).exists()
        if not rec or rec.unit_id != unit:
            raise UserError(_("Команду не знайдено."))
        if op == "get":
            return rec._td_get_dict()
        if op == "confirm_second":
            return rec._td_confirm_second()
        if Command._td_by_token(token) != rec:
            raise UserError(_("Токен не відповідає команді."))
        return Command._td_confirm(token) if op == "confirm" else Command._td_cancel(token)

    @api.model
    def _td_prepare_response(self, rec, token, rendered, blocked, reason):
        """DTO `prepare` (td_energy_control 7.2 + `ref`); `confirm_label` — «Виконати» (клас A або chief) / «1/2»."""
        chief = self.env.user.has_group(G_CHIEF)
        return {
            "ref": rec._td_ref,
            "action_id": rec.id,
            "token": token,
            "ttl_s": cparam_int(self.env, "confirm_ttl_s"),
            "verify_timeout_s": cparam_int(self.env, "verify_timeout_s"),
            "kind": rec.kind_code,
            "cls": rec.cls,
            "title": rendered["title"],
            "text": rendered["text"],
            "sub": rendered["sub"],
            "checks": rec.checks or [],
            "blocked": bool(blocked),
            "blocked_reason": reason,
            "needs_second": bool(rec.needs_second),
            "confirm_label": "Підтвердити (1/2)" if (rec.cls == "B" and not chief) else "Виконати",
            "disabled_reason": reason if blocked else None,
        }

    @api.model
    def _td_command_rows(self, unit, limit, before):
        """Рядки-команди для API-03 (R-12): `list[dict]` `{type:'command', id, ref, ts, level, text, ack_state, state}`
        у порядку `ts desc, id desc`, не більше `limit`, лише з `ts < before` (naive UTC datetime або `None`).
        Єдине джерело журналу команд: у базі `td.chp.command`, з мостом (перевизначення) — `td.energy.action`."""
        return self.env["td.chp.command"]._td_journal_rows(unit, limit, before)

    @api.model
    def _td_pending_rows(self, unit):
        """Команди, що очікують 2/2, для `pending` у `get_state`: `[{ref, kind, title, prepared_by, can_second,
        second_expires_at}]` — з того самого сховища, що й `_td_dispatch`."""
        return self.env["td.chp.command"]._td_pending_rows(unit)

    @api.model
    def _td_flags(self, unit):
        """`{"bridge": bool, "remote_switching": bool}` → `caps.bridge`, `caps.rsw`."""
        return {"bridge": False, "remote_switching": bool(unit._td_remote_switching())}

    @api.model
    def _td_bus_tick(self, kind):
        """Для мосту: повідомити пульт (`td_chp/update`) про зміну з боку td_energy_control."""
        bus.tick(self.env, kind)
