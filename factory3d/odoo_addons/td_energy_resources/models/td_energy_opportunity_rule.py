"""M-09 `td.energy.opportunity.rule` — правило резерву економії (FR-13, FR-14; W3-B).

Правило задає вкладку, пороги (`params` + `params_schema`), вікно аналізу й дії за контрактом C-32 (W1 M-26).
Детектор — функція `tools/detectors/<code>.py` (реєстр `DETECTORS`) або метод `_td_detect_<code>(now)` у
`_inherit` цієї моделі (міст `td_energy_resources_bms`, A-08). Прогін, upsert і життєвий цикл знахідок —
`td.energy.opportunity` (R-13); тут — реєстр, перевірки й запуск вручну (API-05).
"""

import copy
import logging
import re
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.td_energy.tools import dates

from ..tools.detectors import DETECTORS, common

_logger = logging.getLogger(__name__)

COST_GROUP = "td_energy.group_td_energy_cost"
MANAGER_GROUP = "td_energy.group_td_energy_manager"
ACTION_KINDS = ("link", "ticket", "control")
ACTION_CODE_RE = re.compile(r"^[a-z0-9_]{1,32}$")
DETECT_PREFIX = "_td_detect_"
DEFAULT_FALLBACK = {
    "code": "open",
    "label": "Відкрити",
    "kind": "link",
    "params": {"xmlid": "td_energy_resources.action_td_energy_opportunity"},
}


class TdEnergyOpportunityRule(models.Model):
    _name = "td.energy.opportunity.rule"
    _description = "Енергетика: правило резерву економії"
    _order = "sequence, code"

    code = fields.Char(string="Код", size=32, required=True, index=True, copy=False)
    name = fields.Char(string="Назва", size=128, required=True)
    sequence = fields.Integer(default=10)
    enabled = fields.Boolean(string="Увімкнено", default=True)
    resource_id = fields.Many2one(
        "td.energy.resource", string="Вкладка, де показується", required=True, ondelete="restrict"
    )
    lookback_days = fields.Integer(string="Вікно аналізу, діб", default=7)
    min_saving_uah = fields.Float(
        string="Мінімальна економія, ₴/міс", default=1000.0, digits=(14, 2), groups=COST_GROUP
    )
    params = fields.Json(string="Пороги", default=dict)
    params_schema = fields.Json(string="Схема порогів", default=list)
    actions = fields.Json(string="Дії (C-32)", default=list)
    fallback_action = fields.Json(string="Запасна дія", default=lambda self: dict(DEFAULT_FALLBACK))
    control_intent = fields.Char(string="Намір керування", size=48)
    control_label = fields.Char(string="Підпис кнопки керування", size=48)
    cooldown_days = fields.Integer(string="Пауза після «Виконано», діб", default=14)
    dismiss_days = fields.Integer(string="Пауза після «Відхилено», діб", default=30)
    requires = fields.Char(string="Потрібні модулі/сигнали", size=64)
    last_run = fields.Datetime(string="Останній прогін", readonly=True)
    last_count = fields.Integer(string="Знахідок", readonly=True)
    last_error = fields.Char(string="Остання помилка", size=256, readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", default=lambda self: self.env.company)

    _td_energy_opportunity_rule_code_uniq = models.Constraint("UNIQUE(code)", "Код правила має бути унікальним.")

    # --- перевірки ------------------------------------------------------------------------------------
    @api.constrains("lookback_days")
    def _check_lookback(self):
        for rec in self:
            if not 1 <= rec.lookback_days <= 60:
                raise ValidationError(_("Вікно аналізу має бути від 1 до 60 діб."))

    @api.constrains("params", "params_schema")
    def _check_params(self):
        for rec in self:
            for key, kind, lo, hi in common.check_params(rec.params_schema, rec.params):
                raise ValidationError(
                    _(
                        "Параметр %(key)s: очікується %(kind)s у діапазоні %(lo)s…%(hi)s.",
                        key=key, kind=kind, lo="—" if lo is None else lo, hi="—" if hi is None else hi,
                    )
                )  # fmt: skip

    @api.constrains("actions", "fallback_action")
    def _check_actions(self):
        for rec in self:
            for action in (rec.actions or []) + ([rec.fallback_action] if rec.fallback_action else []):
                if not isinstance(action, dict) or action.get("kind") not in ACTION_KINDS:
                    raise ValidationError(_("Дія правила: вид має бути link, ticket або control."))
                if not ACTION_CODE_RE.match(str(action.get("code") or "")):
                    raise ValidationError(_("Дія правила: код має відповідати ^[a-z0-9_]{1,32}$."))
                if len(str(action.get("label") or "")) > 48:
                    raise ValidationError(_("Дія правила: підпис не довший за 48 символів."))

    # --- реєстр детекторів (A-08) ---------------------------------------------------------------------
    @api.model
    def _td_detector_methods(self):
        """`{код правила: callable(rule, now) -> list[dict]}`: функції ядра (`DETECTORS`) і методи
        `_td_detect_<code>(now)` моделі (міст)."""
        methods = {code: (lambda rule, now, fn=fn: fn(rule.env, rule, now)) for code, fn in DETECTORS.items()}
        for name in dir(type(self)):
            if name.startswith(DETECT_PREFIX) and callable(getattr(type(self), name, None)):
                methods[name[len(DETECT_PREFIX) :]] = lambda rule, now, name=name: getattr(rule, name)(now)
        return methods

    def _td_detect(self, now):
        """R-14: знахідки одного правила від детектора; немає детектора — `KeyError`. `DetectorNote` іде нагору."""
        self.ensure_one()
        return self._td_detector_methods()[self.code](self.sudo(), now)

    def _td_build_actions(self, opp, finding):
        """R-13 п. 5: дії резерву — `finding["actions"]` або `rule.actions`, плюс `control` (за `control_intent`).
        У `ticket` підставляються вузол знахідки й тег `[OPP-<id>]` в `description`."""
        self.ensure_one()
        raw = finding.get("actions")
        out = []
        for source in self.actions or [] if raw is None else raw:
            action = copy.deepcopy(source)
            action.setdefault("class", None)
            params = action.setdefault("params", {})
            if action.get("kind") == "ticket":
                params.setdefault("node_code", finding.get("node_code") or "")
                params.setdefault("title", self.name)
                text = str(params.get("description") or action.get("label") or self.name)
                tag = "[OPP-%d]" % opp.id
                params["description"] = (
                    text.replace("{id}", str(opp.id))
                    if "{id}" in text
                    else (text if tag in text else "%s %s" % (text, tag))
                )
            out.append(action)
        if self.control_intent:
            out.append(
                {
                    "code": "control", "label": self.control_label or "Керувати", "kind": "control", "class": None,
                    "params": {"intent": self.control_intent},
                }
            )  # fmt: skip
        return out

    # --- запуск вручну (API-05) -----------------------------------------------------------------------
    def action_run(self):
        """Запускає правило(а) як крон: `{"found", "created", "expired", "seconds"}` (сума по записах)."""
        if not (self.env.is_superuser() or self.env.user.has_group(MANAGER_GROUP)):
            raise AccessError(_("Керувати резервами може лише енергетик."))
        started = time.monotonic()
        now = dates.now_utc(self.env)
        total = {"found": 0, "created": 0, "expired": 0}
        Opportunity = self.env["td.energy.opportunity"]
        for rule in self:
            for key, value in Opportunity._td_run_rule(rule, now).items():
                total[key] += value
        total["seconds"] = round(time.monotonic() - started, 3)
        return total
