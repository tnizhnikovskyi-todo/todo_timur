"""M-06 `td.chp.pult` — API пульта (AbstractModel). Scaffold: сигнатури публічних методів і хуків (C-chp-03).

Публічні методи (`@api.model`, права — SPEC §2 M-06) — реалізація в основному коміті W1.
Хуки: у базі працює потік `td.chp.command`; міст `td_chp_factory3d` (за наявності `td_energy_control`) перевизначає
їх ЦІЛКОМ — усі 9 видів команд ідуть в `td.energy.control`/`td.energy.action` (єдиний механізм і журнал команд з
пультом енергетики), тому `td.chp.command` при мосту не створюється.
"""

from odoo import api, models
from odoo.exceptions import UserError


class TdChpPult(models.AbstractModel):
    _name = "td.chp.pult"
    _description = "КГУ: API пульта"

    # --- публічний API (SPEC §7, API-01…07) --------------------------------------------------------------------
    @api.model
    def get_state(self, unit=None, etag=None):
        raise UserError("scaffold: get_state не реалізовано")

    @api.model
    def get_trend(self, unit=None, range_h=24):
        raise UserError("scaffold: get_trend не реалізовано")

    @api.model
    def get_journal(self, unit=None, limit=50, before=None):
        raise UserError("scaffold: get_journal не реалізовано")

    @api.model
    def ack(self, unit=None, ids=None):
        raise UserError("scaffold: ack не реалізовано")

    @api.model
    def command(self, op, unit=None, kind=None, params=None, ref=None, token=None):
        raise UserError("scaffold: command не реалізовано")

    @api.model
    def get_maintenance(self, unit=None):
        raise UserError("scaffold: get_maintenance не реалізовано")

    @api.model
    def maintenance_done(self, rule_id):
        raise UserError("scaffold: maintenance_done не реалізовано")

    @api.model
    def sim(self, op, code=None, params=None):
        raise UserError("scaffold: sim не реалізовано")

    # --- хуки для мосту (C-chp-03) -----------------------------------------------------------------------------
    @api.model
    def _td_route(self, kind):
        """Куди йде вид команди: `None` — потік td_chp (`td.chp.command`), `'energy'` — td_energy_control (міст).

        Міст повертає `'energy'` для ВСІХ 9 видів (start, stop, estop, reset, set_*), якщо є `td.energy.control`.
        Від результату залежать R-07 (для `'energy'` не перевіряються `rsw` і `write_enabled`) і `caps.bridge`.
        """
        return None

    @api.model
    def _td_dispatch(self, op, unit, kind=None, params=None, ref=None, token=None):
        """Єдина точка диспетчеризації `command(op, …)`: `op ∈ prepare|confirm|confirm_second|cancel|get` →
        DTO API-05 (SPEC §7). Викликається ПІСЛЯ перевірки груп (operator) і розбору `unit` (запис `td.chp.unit`).

        База — потік `td.chp.command`; `ref` — `chp:<id>` або `energy:<id>`. Міст перевизначає метод цілком
        (для `_td_route(kind)='energy'` — `td.energy.control`, інакше `super()`).
        """
        raise UserError("scaffold: _td_dispatch не реалізовано")

    @api.model
    def _td_command_rows(self, unit, limit, before):
        """Рядки-команди для API-03 (R-12): `list[dict]` форми `{type:'command', id, ref, ts, level, text, ack_state,
        state}` у порядку `ts desc, id desc`, не більше `limit`, лише з `ts < before` (ISO або `None`).
        Єдине джерело журналу команд: у базі `td.chp.command`, з мостом (перевизначення) — `td.energy.action`."""
        return []

    @api.model
    def _td_pending_rows(self, unit):
        """Команди, що очікують 2/2, для `pending` у `get_state`: `[{ref, kind, title, prepared_by, can_second,
        second_expires_at}]` — з того самого сховища, що й `_td_dispatch`."""
        return []

    @api.model
    def _td_flags(self, unit):
        """`{"bridge": bool, "remote_switching": bool}` → `caps.bridge`, `caps.rsw`."""
        return {"bridge": False, "remote_switching": False}
