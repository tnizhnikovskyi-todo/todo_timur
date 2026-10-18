"""M-10 `td.energy.opportunity` — резерв економії (FR-13…FR-15; W3-B).

R-13: `_cron_detect` / `rule.action_run` → детектор правила → фільтр (`min_saving_uah`, паузи після «Виконано» і
«Відхилено») → upsert за `dedup_key` серед `open` (`in_plan` зберігається) → невидані стають `expired` → збирання дій
(C-32) → `_td_link_requests` (заявки ТО з тегом `[OPP-<id>]`). API: `get_list` (API-02, контракт C-01 для W4),
`get_plan_summary` (API-06), `action_plan_toggle` (API-03), `action_dismiss` / `action_done` (API-04).
Записи створює лише рушій (від імені крона або через `sudo` енергетика); користувачі групи — лише читання й дії.
"""

import copy
import logging
import re
import time
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.dates import param_bool

from ..tools.detectors import common

_logger = logging.getLogger(__name__)

COST_GROUP = "td_energy.group_td_energy_cost"
USER_GROUP = "td_energy.group_td_energy_user"
MANAGER_GROUP = "td_energy.group_td_energy_manager"
STATES = [
    ("open", "Відкрите"),
    ("done", "Виконано"),
    ("dismissed", "Відхилено"),
    ("expired", "Втратило актуальність"),
]
TAG_RE = re.compile(r"\[OPP-(\d+)\]")
CRON_BUDGET_S = 60.0  # SPEC 6: ≤ 60 с суму, ≤ 10 с на правило
RULE_BUDGET_S = 10.0
LINK_LIMIT = 500


class TdEnergyOpportunity(models.Model):
    _name = "td.energy.opportunity"
    _description = "Енергетика: резерв економії"
    _inherit = ["mail.thread"]
    _order = "in_plan desc, est_saving_month desc, id"
    _rec_name = "title"

    rule_id = fields.Many2one(
        "td.energy.opportunity.rule", string="Правило", required=True, index=True, ondelete="restrict"
    )
    resource_id = fields.Many2one(related="rule_id.resource_id", store=True, index=True)
    dedup_key = fields.Char(string="Ключ дедуплікації", size=96, required=True, index=True)
    title = fields.Char(string="Заголовок", size=160, required=True)
    text = fields.Text(string="Текст", required=True)
    est_saving_month = fields.Float(string="Економія, ₴/міс", digits=(14, 2), groups=COST_GROUP)
    est_qty_month = fields.Float(string="Економія в од. ресурсу/міс", digits=(14, 2))
    evidence = fields.Json(string="Основа оцінки", default=dict)
    state = fields.Selection(STATES, string="Стан", default="open", required=True, index=True, tracking=True)
    in_plan = fields.Boolean(string="У плані", default=False, index=True, tracking=True)
    plan_user_id = fields.Many2one("res.users", string="Додав у план", readonly=True)
    plan_date = fields.Date(string="Дата плану", readonly=True)
    found_at = fields.Datetime(string="Знайдено", readonly=True)
    last_seen_at = fields.Datetime(string="Востаннє бачили", readonly=True)
    node_id = fields.Many2one("td.energy.node", string="Вузол", ondelete="set null")
    point_id = fields.Many2one("td.energy.point", string="Точка обліку", ondelete="set null")
    request_id = fields.Many2one("maintenance.request", string="Заявка ТО", ondelete="set null", readonly=True)
    actions = fields.Json(string="Дії (C-32)", default=list)
    result_note = fields.Char(string="Результат", size=256)
    resolved_at = fields.Datetime(string="Закрито", readonly=True)
    resolved_by = fields.Many2one("res.users", string="Закрив", readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", default=lambda self: self.env.company)

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS td_energy_opportunity_dedup_open_uniq ON td_energy_opportunity "
            "(dedup_key) WHERE state = 'open'"
        )
        tools.sql.create_index(
            self.env.cr, "td_energy_opportunity_state_res_idx", self._table, ["state", "resource_id"]
        )

    # --- права ----------------------------------------------------------------------------------------
    @api.model
    def _td_check_access(self):
        if not (self.env.is_superuser() or self.env.user.has_group(USER_GROUP)):
            raise AccessError(_("Немає доступу до Енергетики."))

    @api.model
    def _td_check_manager(self):
        if not (self.env.is_superuser() or self.env.user.has_group(MANAGER_GROUP)):
            raise AccessError(_("Керувати резервами може лише енергетик."))

    # --- API-02, API-06 -------------------------------------------------------------------------------
    @api.model
    def get_list(self, resource_code=None, states=("open",)):
        """API-02 (контракт C-01): `{"items": [...], "plan_sum", "all_sum"}`; суми й `save_uah_month` — лише з групою
        вартості. Сортування: `in_plan desc, est_saving_month desc` (`_order`)."""
        self._td_check_access()
        states = [states] if isinstance(states, str) else list(states or ())
        if not states or any(s not in dict(STATES) for s in states):
            raise UserError(_("Невідомий стан резерву."))
        domain = [("state", "in", states), ("company_id", "in", [False, *self.env.companies.ids])]
        if resource_code:
            if not self.env["td.energy.resource"].sudo().search_count([("code", "=", resource_code)]):
                raise UserError(_("Невідомий ресурс: %s.", resource_code))
            domain.append(("resource_id.code", "=", resource_code))
        cost = self.env.user.has_group(COST_GROUP) or self.env.is_superuser()
        control = self.env["td.energy.advice"]._td_control_available()
        records = self.sudo().search(domain)
        items = [self._td_item(rec, control, cost) for rec in records]
        out = {"items": items}
        if cost:
            out["plan_sum"] = int(round(sum(r.est_saving_month for r in records if r.in_plan)))
            out["all_sum"] = int(round(sum(records.mapped("est_saving_month"))))
        return out

    @api.model
    def _td_item(self, rec, control, cost):
        actions = [
            {
                "code": a.get("code"), "label": a.get("label"), "kind": a.get("kind"), "class": a.get("class"),
                "params": a.get("params") or {}, "enabled": a.get("kind") != "control" or control,
            }
            for a in rec.actions or []
        ]  # fmt: skip
        if not any(a["enabled"] for a in actions):
            fallback = copy.deepcopy(rec.rule_id.fallback_action or {})
            if fallback:
                params = fallback.setdefault("params", {})
                if fallback.get("kind") == "link":
                    params.setdefault("res_id", rec.id)
                fallback.setdefault("class", None)
                fallback["enabled"] = True
                actions.append(fallback)
        item = {
            "id": rec.id, "code": rec.rule_id.code, "resource": rec.resource_id.code, "title": rec.title,
            "text": rec.text, "est_qty_month": rec.est_qty_month, "in_plan": rec.in_plan, "state": rec.state,
            "found_at": rec.found_at.isoformat() if rec.found_at else None, "request_id": rec.request_id.id or None,
            "actions": actions,
        }  # fmt: skip
        if cost:
            item["save_uah_month"] = int(round(rec.est_saving_month))
        return item

    @api.model
    def get_plan_summary(self):
        """API-06: `{"plan_sum", "all_sum", "plan_count", "open_count"}` по відкритих; суми — лише з групою вартості."""
        self._td_check_access()
        records = self.sudo().search([("state", "=", "open"), ("company_id", "in", [False, *self.env.companies.ids])])
        planned = records.filtered("in_plan")
        out = {"plan_count": len(planned), "open_count": len(records)}
        if self.env.user.has_group(COST_GROUP) or self.env.is_superuser():
            out["plan_sum"] = int(round(sum(planned.mapped("est_saving_month"))))
            out["all_sum"] = int(round(sum(records.mapped("est_saving_month"))))
        return out

    # --- дії енергетика (API-03, API-04) --------------------------------------------------------------
    def _td_check_open(self):
        if any(rec.state != "open" for rec in self):
            raise UserError(_("Резерв уже закрито."))

    def action_plan_toggle(self, plan=None):
        """API-03: «У плані» (`plan=None` — інвертувати); повідомлення в чаттері."""
        self._td_check_manager()
        self._td_check_open()
        today = dates.local_day(dates.now_utc(self.env))
        for rec in self.sudo():
            new = (not rec.in_plan) if plan is None else bool(plan)
            rec.write(
                {
                    "in_plan": new,
                    "plan_user_id": self.env.uid if new else False,
                    "plan_date": today if new else False,
                }
            )
            rec.message_post(body=_("Додано до плану") if new else _("Прибрано з плану"))
        return True

    def action_dismiss(self):
        """API-04: «Відхилити» — `dismissed` (повтор знахідки пригнічується `dismiss_days`)."""
        self._td_check_manager()
        self._td_check_open()
        self._td_close("dismissed", None, _("Відхилено"))
        return True

    def action_done(self, note=None):
        """API-04: «Виконано» — `done`, `in_plan` не скидається (повтор пригнічується `cooldown_days`)."""
        self._td_check_manager()
        self._td_check_open()
        self._td_close("done", note, _("Виконано"))
        return True

    def _td_close(self, state, note, message):
        now = dates.now_utc(self.env)
        vals = {"state": state, "resolved_at": now, "resolved_by": self.env.uid}
        if note:
            vals["result_note"] = str(note)[:256]
        for rec in self.sudo():
            rec.write(vals)
            rec.message_post(body=message + (": %s" % vals["result_note"] if note else ""))

    # --- R-13: рушій ----------------------------------------------------------------------------------
    @api.model
    def _cron_detect(self):
        """R-13: усі `enabled` правила; збій правила не зупиняє решту; ≤ 60 с сумарно."""
        if not param_bool(self.env, "read_enabled"):
            return False
        now = dates.now_utc(self.env)
        started = time.monotonic()
        rules = self.env["td.energy.opportunity.rule"].sudo().search([("enabled", "=", True)])
        for rule in rules:
            if time.monotonic() - started > CRON_BUDGET_S:
                _logger.warning("td_energy_resources: крон резервів вичерпав бюджет, правило %s відкладено", rule.code)
                break
            self._td_run_rule(rule, now)
        self._td_link_requests()
        return True

    @api.model
    def _td_run_rule(self, rule, now):
        """Прогін одного правила: `{"found", "created", "expired"}`; `last_*` правила оновлюються завжди."""
        rule = rule.sudo()
        stats = {"found": 0, "created": 0, "expired": 0}
        started = time.monotonic()
        error = False
        try:
            if rule.code not in rule._td_detector_methods():
                error = "Детектор недоступний"
                rule.write({"last_run": now, "last_count": 0, "last_error": error})
                return stats
            try:
                with self.env.cr.savepoint():
                    findings = rule._td_detect(now)
                    stats = self._td_apply(rule, findings, now)
            except common.DetectorNote as note:
                with self.env.cr.savepoint():
                    stats = self._td_apply(rule, [], now)
                error = str(note)
        except Exception as exc:
            _logger.exception("td_energy_resources: детектор %s", rule.code)
            error = (str(exc) or exc.__class__.__name__)[:256]
            stats = {"found": 0, "created": 0, "expired": 0}
        if time.monotonic() - started > RULE_BUDGET_S:
            _logger.warning("td_energy_resources: детектор %s працював %.1f с", rule.code, time.monotonic() - started)
        rule.write({"last_run": now, "last_count": stats["found"], "last_error": error})
        return stats

    @api.model
    def _td_suppressed(self, key, now, rule):
        """R-13 п. 2: `dismissed` не старше `dismiss_days` або `done` не старше `cooldown_days` за тим самим ключем."""
        return bool(
            self.sudo().search_count(
                [
                    ("dedup_key", "=", key),
                    "|",
                    "&", ("state", "=", "dismissed"), ("resolved_at", ">", now - timedelta(days=rule.dismiss_days)),
                    "&", ("state", "=", "done"), ("resolved_at", ">", now - timedelta(days=rule.cooldown_days)),
                ]
            )
        )  # fmt: skip

    @api.model
    def _td_apply(self, rule, findings, now):
        """R-13 п. 2…5: фільтр, upsert, закінчення, дії. `found` — кількість збережених знахідок."""
        Opp = self.sudo()
        kept, created = {}, 0
        for item in findings or []:
            key = item["dedup_key"]
            if (item.get("est_saving_month") or 0.0) < rule.min_saving_uah or self._td_suppressed(key, now, rule):
                continue
            node = self._td_by_code("td.energy.node", item.get("node_code"))
            point = self._td_by_code("td.energy.point", item.get("point_code"), rule.resource_id)
            vals = {
                "title": item["title"][:160], "text": item["text"],
                "est_saving_month": item.get("est_saving_month") or 0.0,
                "est_qty_month": item.get("est_qty_month") or 0.0, "evidence": item.get("evidence") or {},
                "node_id": node.id or False, "point_id": point.id or False, "last_seen_at": now,
            }  # fmt: skip
            rec = Opp.search([("dedup_key", "=", key), ("state", "=", "open")], limit=1)
            if rec:
                rec.write(vals)
            else:
                rec = Opp.create(
                    dict(vals, rule_id=rule.id, dedup_key=key, state="open", found_at=now,
                         company_id=rule.company_id.id or self.env.company.id)
                )  # fmt: skip
                created += 1
            rec.actions = rule._td_build_actions(rec, item)
            kept[key] = rec.id
        stale = Opp.search([("rule_id", "=", rule.id), ("state", "=", "open"), ("dedup_key", "not in", list(kept))])
        stale.write({"state": "expired", "resolved_at": now})
        return {"found": len(kept), "created": created, "expired": len(stale)}

    @api.model
    def _td_by_code(self, model, code, resource=None):
        Model = self.env[model].sudo()
        if not code:
            return Model
        domain = [("code", "=", code)]
        if resource and model == "td.energy.point":
            domain.append(("resource_id", "=", resource.id))
        return Model.search(domain, limit=1)

    # --- R-13 п. 6: заявки ТО -------------------------------------------------------------------------
    @api.model
    def _td_link_requests(self):
        """Заявки з тегом `[OPP-<id>]` в описі → `request_id`; заявка в стадії `done` закриває резерв."""
        now = dates.now_utc(self.env)
        Opp = self.sudo()
        requests = (
            self.env["maintenance.request"]
            .sudo()
            .search([("description", "ilike", "[OPP-")], order="id desc", limit=LINK_LIMIT)
        )
        linked = 0
        for request in requests:
            for opp_id in {int(m) for m in TAG_RE.findall(request.description or "")}:
                opp = Opp.browse(opp_id).exists()
                if not opp:
                    continue
                vals = {}
                if opp.request_id != request:
                    vals["request_id"] = request.id
                if opp.state == "open" and request.stage_id.done:
                    vals.update(
                        state="done", result_note="Заявку закрито", resolved_at=now,
                        resolved_by=request.user_id.id or False,
                    )  # fmt: skip
                if vals:
                    opp.write(vals)
                    linked += 1
        return linked
