"""M-29 `td.energy.scenario` — сценарій автоматики (6 записей): параметри, стан рушія, текст чипа."""

import copy
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.td_energy.tools import dates

from .. import tools
from ..tools import bus, kinds, status_text

ENGINE_STATES = ("off", "armed", "active", "warn")


class TdEnergyScenario(models.Model):
    _name = "td.energy.scenario"
    _description = "Енергетика: сценарій автоматики"
    _order = "sequence, id"

    _td_scenario_code_uniq = models.Constraint("UNIQUE(code)", "Код сценарію має бути унікальним.")

    code = fields.Selection(
        [(c, kinds.SCENARIO_TITLES[c]) for c in kinds.SCENARIO_CODES], string="Код", required=True, index=True,
        readonly=True,
    )  # fmt: skip
    name = fields.Char(string="Назва", size=64, required=True)
    description = fields.Text(string="Опис", required=True)
    sequence = fields.Integer(string="Порядок", default=10)
    enabled = fields.Boolean(string="Увімкнено", default=False, readonly=True)
    params = fields.Json(string="Параметри", default=dict)
    params_text = fields.Text(string="Параметри (JSON)", compute="_compute_params_text", inverse="_inverse_params_text")
    config_version = fields.Integer(string="Версія конфігурації", readonly=True)
    applied = fields.Boolean(string="Застосовано збирачем", compute="_compute_applied")
    engine_state = fields.Selection(
        [
            ("unknown", "Немає даних"),
            ("off", "Вимкнено"),
            ("armed", "Чергування"),
            ("active", "Активний"),
            ("warn", "Збій"),
        ],
        string="Стан рушія",
        default="unknown",
        readonly=True,
    )
    engine_facts = fields.Json(string="Факти рушія", readonly=True)
    engine_ts = fields.Datetime(string="Звіт рушія", readonly=True)
    state_signal_id = fields.Many2one("td.signal", string="Сигнал стану", readonly=True, ondelete="set null")
    state_kind = fields.Selection(
        [("act", "act"), ("arm", "arm"), ("warn", "warn"), ("off", "off")],
        string="Вид чипа",
        compute="_compute_state_text",
    )
    state_text = fields.Char(string="Текст чипа", compute="_compute_state_text")
    changed_by = fields.Many2one("res.users", string="Змінив", readonly=True, ondelete="set null")
    changed_at = fields.Datetime(string="Змінено", readonly=True)

    # --- обчислювані -----------------------------------------------------------------------------------------
    @api.depends("params")
    def _compute_params_text(self):
        for rec in self:
            rec.params_text = json.dumps(rec.params or {}, ensure_ascii=False, indent=2)

    def _inverse_params_text(self):
        for rec in self:
            try:
                rec.params = json.loads(rec.params_text) if (rec.params_text or "").strip() else {}
            except ValueError as e:
                raise ValidationError(_("Параметри (JSON): %s", e)) from e

    @api.depends("config_version")
    def _compute_applied(self):
        applied = self.env["td.energy.control.state"].get().applied_version
        for rec in self:
            rec.applied = applied >= rec.config_version

    @api.depends("enabled", "engine_state", "engine_facts", "engine_ts", "params")
    def _compute_state_text(self):
        for rec in self:
            rec.state_text, rec.state_kind = rec._td_state_text()

    def _td_state_text(self):
        """R-43 п.5: (текст, вид). Немає звіту рушія ≥ `2·heartbeat_stale_s` → «Немає даних від рушія»."""
        self.ensure_one()
        stale = tools.cparam_float(self.env, "heartbeat_stale_s", 30.0) * 2
        now = dates.now_utc(self.env)
        fresh = bool(self.engine_ts and (now - self.engine_ts).total_seconds() <= stale)
        text, kind = status_text.state_text(
            self.code, self.enabled, self.engine_state, self.engine_facts, fresh, self.params
        )
        return text, kind

    def _td_plant(self):
        """Заводські числа для чипів: договірна потужність, ціль cos φ, крок PFC."""
        env = self.env
        tariff = env["td.energy.tariff"].sudo()._td_tariff_at(dates.now_utc(env))
        node = env["td.energy.node"].sudo().search([("code", "=", "PFC-1")], limit=1)
        return {
            "contract_kw": tariff.contract_kw if tariff else 800.0,
            "cos_target": dates.param_float(env, "cos_phi_target", 0.95),
            "pfc_step_kvar": node.pfc_step_kvar if node else 35,
        }

    def _td_chips(self, plant=None):
        self.ensure_one()
        return status_text.chips(self.code, self._td_params(), plant or self._td_plant())

    def _td_params(self):
        """Параметри з доповненням значеннями за замовчуванням."""
        self.ensure_one()
        return {**copy.deepcopy(kinds.PARAM_DEFAULTS.get(self.code, {})), **(self.params or {})}

    # --- перевірки -------------------------------------------------------------------------------------------
    @api.constrains("params")
    def _check_params(self):
        for rec in self:
            _clean, errors = kinds.validate(kinds.SCENARIO_PARAMS.get(rec.code, []), rec.params or {})
            if errors:
                key, err = errors[0]
                raise ValidationError(
                    _("Сценарій %(name)s: параметр %(key)s — %(err)s.", name=rec.name, key=key, err=err)
                )

    # --- запис -----------------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not tools.is_internal(self.env) and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Сценарії створює лише адміністратор."))
        for vals in vals_list:
            if vals.get("params") is None:
                vals["params"] = copy.deepcopy(kinds.PARAM_DEFAULTS.get(vals.get("code"), {}))
        return super().create(vals_list)

    def write(self, vals):
        internal = tools.is_internal(self.env)
        if not internal and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Зміна сценарію можлива лише дією керування (клас B)."))
        res = super().write(vals)
        if not internal and ({"enabled", "params", "params_text"} & set(vals)):
            self._td_after_admin_change()
        return res

    def unlink(self):
        if not tools.is_internal(self.env) and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Сценарії видаляє лише адміністратор."))
        return super().unlink()

    def _td_after_admin_change(self):
        version = self.env["td.energy.control.state"].bump()
        self.sudo().with_context(td_energy_control_internal=True).write(
            {"config_version": version, "changed_by": self.env.uid, "changed_at": dates.now_utc(self.env)}
        )
        bus.tick(self.env, "scenario")

    def _td_apply_change(self, vals, action=None):
        """Внутрішня зміна `enabled`/`params` дією керування; `config_version = state.bump()` (R-43 п.1)."""
        self.ensure_one()
        me = self.sudo().with_context(td_energy_control_internal=True)
        allowed = {k: v for k, v in vals.items() if k in ("enabled", "params")}
        me.write(allowed)
        version = me.env["td.energy.control.state"].bump()
        me.write(
            {
                "config_version": version,
                "changed_by": (action.confirmed_by.id if action and action.confirmed_by else self.env.uid),
                "changed_at": dates.now_utc(self.env),
            }
        )
        me.invalidate_recordset(["applied", "state_text", "state_kind"])
        bus.tick(self.env, "scenario")
        return version

    @api.model
    def _td_engine_update(self, code, item, applied_version=0):
        """API-25: стан сценарію від рушія (ігнорує звіт, що ще не знає поточної версії `enabled`)."""
        rec = self.sudo().search([("code", "=", code)], limit=1)
        if not rec or not isinstance(item, dict):
            return False
        if applied_version < rec.config_version:
            return False
        state = item.get("state") if item.get("state") in ENGINE_STATES else "unknown"
        rec.with_context(td_energy_control_internal=True).write(
            {
                "engine_state": state,
                "engine_facts": item.get("facts") or {},
                "engine_ts": dates.now_utc(self.env),
            }
        )
        return True

    # --- API-16: схема для діалогу параметрів ---------------------------------------------------------------
    def _td_schema(self):
        self.ensure_one()
        return [
            {k: v for k, v in spec.items() if v is not None and k != "default"}
            for spec in kinds.resolve_bounds(kinds.SCENARIO_PARAMS.get(self.code, []), {})
        ]
