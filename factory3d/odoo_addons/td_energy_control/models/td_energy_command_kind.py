"""M-31 `td.energy.command.kind` — вид команди: клас A/B, виконавець, ресурс, перевірки, параметри, шаблони діалогу."""

import copy
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.tariff import to_local

from .. import tools
from ..tools import config_builder, genset_link, interlocks, kinds


class TdEnergyCommandKind(models.Model):
    _name = "td.energy.command.kind"
    _description = "Енергетика: вид команди"
    _order = "sequence, id"

    _td_kind_code_uniq = models.Constraint("UNIQUE(code)", "Код виду команди має бути унікальним.")

    code = fields.Char(string="Код", size=32, required=True, index=True)
    name = fields.Char(string="Назва", size=96, required=True)
    sub_template = fields.Char(string="Підпис", size=128)
    sequence = fields.Integer(string="Порядок", default=10)
    tile = fields.Boolean(string="Плитка на екрані")
    cls = fields.Selection([("A", "A"), ("B", "B")], string="Клас", required=True)
    executor = fields.Selection(
        [("intent", "Збирач (інтент)"), ("config", "Конфігурація Odoo"), ("genset", "ДГУ (td_genset)")],
        string="Виконавець",
        required=True,
    )
    resource = fields.Selection(
        [
            ("bess", "BESS"),
            ("qs", "QS"),
            ("chp", "КГУ"),
            ("pfc", "PFC"),
            ("air", "Повітря"),
            ("light", "Освітлення"),
            ("vent", "Вентиляція"),
            ("genset", "ДГУ"),
            ("config", "Конфігурація"),
        ],
        string="Ресурс",
        required=True,
    )
    params_schema = fields.Json(string="Схема параметрів", default=list)
    checks = fields.Json(string="Перевірки", default=list)
    confirm_title = fields.Char(string="Заголовок діалогу")
    confirm_text = fields.Text(string="Текст діалогу")
    undo_kind_id = fields.Many2one("td.energy.command.kind", string="Зворотний вид", ondelete="set null")
    valid_s = fields.Integer(string="TTL команди, с")
    active = fields.Boolean(default=True)
    remote_gated = fields.Boolean(
        string="Дистанційне перемикання",
        help="D-46: при td.energy_control.remote_switching_enabled=False команда відхиляється.",
    )
    available = fields.Boolean(string="Доступна", compute="_compute_available")
    unavailable_reason = fields.Char(string="Причина недоступності", compute="_compute_available")

    # --- доступність (R-42 п.2) -------------------------------------------------------------------------------
    @api.depends("executor", "code")
    def _compute_available(self):
        env = self.env
        bms = None
        intent_kinds = self.filtered(lambda r: r.executor == "intent")
        src = env["td.source"].sudo().search([("code", "=", "ENERGY-CTL")], limit=1) if intent_kinds else None
        sig = (
            env["td.signal"].sudo().search([("code", "=", "energy_control/intent")], limit=1) if intent_kinds else None
        )
        genset_ok = genset_link.availability(env) if self.filtered(lambda r: r.executor == "genset") else None
        for rec in self:
            ok, reason = True, ""
            if rec.executor == "genset":
                ok, reason = genset_ok
            elif rec.executor == "intent":
                if not (src and src.active and sig and sig.active):
                    ok, reason = False, "джерело ENERGY-CTL не налаштовано"
                elif rec.resource in ("light", "vent"):
                    bms = bms or config_builder.bms_targets(env)
                    if rec.code.startswith("light") and not bms["light_break"]["light"]:
                        ok, reason = False, "немає цілей освітлення BMS"
                    if rec.code.startswith("vent") and not bms["vent_eco"]["vent"]:
                        ok, reason = False, "немає цілей вентиляції BMS"
                elif rec.code == "air_setpoint":
                    codes = {kinds.SIGNALS["air_sp"], kinds.SIGNALS["air_min"]}
                    if env["td.signal"].sudo().search_count([("code", "in", list(codes))]) < len(codes):
                        ok, reason = False, "немає сигналів уставки тиску"
            rec.available, rec.unavailable_reason = ok, reason

    # --- перевірки значень -----------------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not all(c.islower() or c.isdigit() or c == "_" for c in rec.code):
                raise ValidationError(_("Код виду команди: латиниця нижнього регістру, цифри, підкреслення."))

    @api.constrains("params_schema", "checks")
    def _check_json(self):
        for rec in self:
            if not isinstance(rec.params_schema or [], list) or not isinstance(rec.checks or [], list):
                raise ValidationError(_("Схема параметрів і перевірки мають бути списками."))
            for chk in rec.checks or []:
                if not isinstance(chk, dict) or chk.get("code") not in interlocks.CHECKS:
                    raise ValidationError(_("Невідома перевірка %s.", (chk or {}).get("code")))

    # --- параметри ---------------------------------------------------------------------------------------------
    def _td_bounds_ctx(self):
        peak = self.env["td.energy.scenario"].sudo().search([("code", "=", "peak")], limit=1)
        return {"bess_max_kw": float(peak._td_params().get("bess_max_kw", 100)) if peak else 100.0}

    def normalize(self, params=None):
        """Привести параметри: типи, межі, значення за замовчуванням; `ValidationError` із українським текстом."""
        self.ensure_one()
        params = dict(params or {})
        if not isinstance(params, dict):
            raise ValidationError(_("Команда %s: параметри мають бути об'єктом.", self.name))
        if self.code == "scenario_params":
            return self._td_normalize_scenario_params(params)
        schema = kinds.resolve_bounds(self.params_schema or [], self._td_bounds_ctx())
        clean, errors = kinds.validate(schema, params, fill_defaults=True)
        by_name = {s["name"]: s for s in schema}
        if errors:
            key, err = errors[0]
            label = by_name.get(key, {}).get("label", key)
            if err.startswith("поза межами"):
                spec = by_name[key]
                err = "поза межами %s…%s%s" % (
                    kinds.fmt(spec.get("min")),
                    kinds.fmt(spec.get("max")),
                    (" " + spec["unit"]) if spec.get("unit") else "",
                )
            raise ValidationError(
                _("Команда %(name)s: параметр %(label)s %(err)s.", name=self.name, label=label, err=err)
            )
        for spec in schema:
            if spec["name"] not in clean and spec.get("default") is None and spec["type"] != "bool":
                raise ValidationError(
                    _("Команда %(name)s: потрібен параметр %(label)s.", name=self.name, label=spec["label"])
                )
        if self.code == "bess_charge":
            now_local = to_local(dates.now_utc(self.env))
            if kinds.until_seconds(clean["until"], now_local) is None:
                raise UserError(_("Час «до» має бути пізніше за поточний."))
        if self.code == "scenario_toggle" and "enabled" not in clean:
            raise ValidationError(_("Команда %s: потрібен параметр «Увімкнено».", self.name))
        if self.code == "shed_reorder":
            ids = self.env["td.energy.shed.item"].sudo().search([("active", "=", True)]).ids
            if sorted(clean.get("order") or []) != sorted(ids):
                raise ValidationError(_("Порядок скидання має містити всі активні пріоритети."))
        return clean

    def _td_normalize_scenario_params(self, params):
        code = params.get("scenario")
        if code not in kinds.SCENARIO_CODES:
            raise ValidationError(_("Команда %s: невідомий сценарій.", self.name))
        given = (
            params.get("params")
            if isinstance(params.get("params"), dict)
            else {k: v for k, v in params.items() if k != "scenario"}
        )
        scenario = self.env["td.energy.scenario"].sudo().search([("code", "=", code)], limit=1)
        merged = {**scenario._td_params(), **given}
        clean, errors = kinds.validate(kinds.SCENARIO_PARAMS[code], merged)
        if errors:
            key, err = errors[0]
            raise ValidationError(
                _("Сценарій %(name)s: параметр %(key)s — %(err)s.", name=scenario.name, key=key, err=err)
            )
        return {"scenario": code, "params": clean}

    # --- діалог ----------------------------------------------------------------------------------------------
    @api.model
    def _td_base_values(self, plant=None):
        """Спільні числа шаблонів (КГУ, тиск повітря, хвилини тесту ДГУ) — один раз на відповідь."""
        env = self.env
        plant = plant or config_builder.plant(env)
        chp = env["td.energy.scenario"].sudo().search([("code", "=", "chp")], limit=1)
        chp_p = chp._td_params() if chp else {}
        air = env["td.signal"].sudo().search([("code", "=", kinds.SIGNALS["air_sp"])], limit=1)
        minutes = None
        mod, gen = genset_link.generator(env)
        if mod and gen:
            minutes = env["td.genset.config"].sudo().get().test_minutes
        return {
            "chp_kw": plant["chp_kw"] / 2,
            "ramp_min": chp_p.get("ramp_min", 6),
            "min_run_h": chp_p.get("min_run_h", 2),
            "current_bar": air.last_value if air and air.last_ts else None,
            "test_minutes": minutes if minutes is not None else 10,
        }

    def _td_text_values(self, params, base=None):
        """Значення для шаблонів тексту: параметри + заводські числа + факти."""
        vals = dict(params or {})
        vals.update(base if base is not None else self._td_base_values())
        if "scenario" in vals:
            vals["scenario"] = kinds.SCENARIO_TITLES.get(vals["scenario"], vals["scenario"])
        if "enabled" in vals:
            vals["on_off"] = "увімкнено" if vals["enabled"] else "вимкнено"
        return vals

    def render(self, params=None):
        """→ {"title","sub","text"}: шаблони `{param}` за параметрами й фактами."""
        self.ensure_one()
        values = self._td_text_values(params)
        title = kinds.render_template(self.confirm_title or (self.name + "?"), values)
        return {
            "title": title,
            "sub": kinds.render_template(self.sub_template, values),
            "text": kinds.render_template(self.confirm_text or "", values),
            "label": kinds.render_template(self.name, values),
        }

    def build_checks(self, params=None, ctx=None):
        """R-41: перевірки Odoo для діалогу → (rows, blocked, blocked_reason)."""
        self.ensure_one()
        env = self.env
        params = params or {}
        ctx = ctx or interlocks.Ctx.from_env(env, dates.now_utc(env))
        rows = {r.code: r._td_dict() for r in env["td.energy.interlock"].sudo().search([])}
        extra = {"fresh_names": kinds.KIND_INPUTS.get(self.code, ())}
        extra.update(params)
        if self.code in ("light_break",):
            extra["lux"] = interlocks.aisle_lux(env, dates.now_utc(env))
        if self.code == "genset_test":
            extra["genset"] = genset_link.facts(env)
        return interlocks.evaluate(self.checks or [], rows, ctx, extra)

    def _td_tile(self, user_can, remote_on, write_on, base=None):
        """Плитка для `get_control().commands[]` з прапорами `enabled`/`disabled_reason`."""
        self.ensure_one()
        values = self._td_text_values({s["name"]: s.get("default") for s in (self.params_schema or [])}, base)
        reason = None
        if not user_can:
            reason = "Немає прав: потрібна роль «Енергетик»"
        elif self.remote_gated and not remote_on:
            reason = "Дистанційне перемикання вимкнено адміністратором"
        elif self.executor in ("intent", "genset") and not write_on:
            reason = "Керування вимкнено адміністратором"
        elif not self.available:
            reason = "Команда недоступна: %s" % self.unavailable_reason
        return {
            "code": self.code,
            "label": kinds.render_template(self.name, values),
            "sub": kinds.render_template(self.sub_template, values),
            "cls": self.cls,
            "resource": self.resource,
            "enabled": reason is None,
            "disabled_reason": reason,
        }

    def _td_default_params(self):
        return {
            s["name"]: copy.deepcopy(s.get("default"))
            for s in (self.params_schema or [])
            if s.get("default") is not None
        }

    def _td_check_remote(self):
        """D-46: команди дистанційного перемикання відхиляються, поки `remote_switching_enabled=False`."""
        for rec in self:
            if rec.remote_gated and not tools.cparam_bool(self.env, "remote_switching_enabled"):
                raise UserError(kinds.REMOTE_REFUSED)

    @api.model
    def _td_json(self, value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
