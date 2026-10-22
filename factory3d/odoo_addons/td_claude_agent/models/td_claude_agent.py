import json
import logging
import re
from datetime import datetime, timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_BETA_HEADER = "experimental-cc-routine-2026-04-01"
FIRE_TIMEOUT = 15


class TdClaudeAgent(models.Model):
    _name = "td.claude.agent"
    _description = "Claude-агент"
    _rec_name = "name"

    owner_id = fields.Many2one(
        "res.users", string="Власник", required=True, default=lambda self: self.env.user, index=True, ondelete="cascade"
    )
    agent_user_id = fields.Many2one(
        "res.users", string="Користувач-агент", required=True, ondelete="restrict", index=True
    )
    name = fields.Char(related="agent_user_id.name", string="Назва", readonly=True)
    fire_url = fields.Char(string="Fire URL", help="Адреса API «fire» вашої Claude Code Routine")
    fire_token = fields.Char(string="Токен Routine", copy=False)
    active = fields.Boolean(default=True)
    last_fire_at = fields.Datetime(string="Останній запуск", readonly=True)
    last_fire_status = fields.Char(string="Статус останнього запуску", readonly=True)
    request_count = fields.Integer(compute="_compute_request_count", string="Запитів")

    _owner_uniq = models.Constraint("UNIQUE(owner_id)", "Кожен користувач може мати лише одного агента Claude.")
    _agent_user_uniq = models.Constraint("UNIQUE(agent_user_id)", "Цей користувач уже є агентом Claude.")

    @api.constrains("fire_url")
    def _check_fire_url(self):
        for agent in self:
            if agent.fire_url and not agent.fire_url.lower().startswith("https://"):
                raise ValidationError(_("Fire URL має починатися з https://"))

    def _compute_request_count(self):
        data = (
            self.env["td.claude.request"].sudo()._read_group([("agent_id", "in", self.ids)], ["agent_id"], ["__count"])
        )
        counts = {agent.id: count for agent, count in data}
        for agent in self:
            agent.request_count = counts.get(agent.id, 0)

    # ------------------------------------------------------------------
    # Виклик Routine
    # ------------------------------------------------------------------
    def _fire(self, payload):
        """POST payload у fire API Routine власника. Повертає (http_status, text); при збої мережі status = 0."""
        self.ensure_one()
        agent = self.sudo()
        if not agent.fire_url or not agent.fire_token:
            return 0, _("Не задано Fire URL або токен.")
        beta = self.env["ir.config_parameter"].sudo().get_param("td_claude_agent.beta_header") or DEFAULT_BETA_HEADER
        headers = {
            "Authorization": f"Bearer {agent.fire_token}",
            "anthropic-beta": beta,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {"text": json.dumps(payload, ensure_ascii=False)}
        try:
            response = requests.post(agent.fire_url, json=body, headers=headers, timeout=FIRE_TIMEOUT)
        except requests.RequestException as exc:
            # токен не друкуємо: лише тип помилки
            _logger.warning("td_claude_agent: fire agent %s failed: %s", agent.id, type(exc).__name__)
            return 0, f"{type(exc).__name__}"
        return response.status_code, response.text or ""

    def action_ping(self):
        self.ensure_one()
        request = self.env["td.claude.request"]._td_create(self, "ping", schedule=False)
        request._send_now()
        ok = request.state == "sent"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Перевірка з'єднання"),
                "message": _(
                    "HTTP %(status)s: %(state)s", status=request.http_status, state=_("успішно") if ok else _("помилка")
                ),
                "type": "success" if ok else "danger",
                "sticky": not ok,
            },
        }

    def action_view_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Журнал запитів"),
            "res_model": "td.claude.request",
            "view_mode": "list,form",
            "domain": [("agent_id", "=", self.id)],
        }

    # ------------------------------------------------------------------
    # Створення агента для поточного користувача
    # ------------------------------------------------------------------
    @api.model
    def _td_unique_login(self, owner):
        base = "claude." + re.sub(r"[^a-z0-9._@+-]", "-", (owner.login or str(owner.id)).lower())
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        login, n = base, 1
        while Users.search_count([("login", "=", login)]):
            n += 1
            login = f"{base}-{n}"
        return login

    @api.model
    def action_create_my_agent(self):
        """Створює агента для поточного користувача (лише для себе). Повертає діалог із одноразовим API-ключем."""
        owner = self.env.user
        if owner.share or owner._is_public():
            raise UserError(_("Агента можуть створити лише внутрішні користувачі."))
        existing = self.sudo().with_context(active_test=False).search_count([("owner_id", "=", owner.id)])
        if existing:
            raise UserError(_("У вас уже є агент Claude."))
        Users = self.env["res.users"].sudo()
        groups = self.env.ref("base.group_user") | self.env.ref("project.group_project_user")
        login = self._td_unique_login(owner)
        agent_user = Users.create(
            {
                "name": f"Claude · {owner.name}",
                "login": login,
                "company_id": owner.company_id.id,
                "company_ids": [(6, 0, owner.company_ids.ids)],
                "group_ids": [(6, 0, groups.ids)],
                "notification_type": "inbox",
                "tz": owner.tz,
            }
        )
        self._td_create_agent_employee(owner, agent_user)
        agent = self.sudo().create({"owner_id": owner.id, "agent_user_id": agent_user.id})
        return agent._td_issue_api_key(_("Агент Claude створено"))

    def action_new_api_key(self):
        """Відкликає ключі odoo-mcp агента і видає новий (лише власник)."""
        self.ensure_one()
        if self.owner_id != self.env.user:
            raise UserError(_("Новий ключ може отримати лише власник агента."))
        self.env["res.users.apikeys"].sudo().search(
            [("user_id", "=", self.agent_user_id.id), ("name", "=", "odoo-mcp")]
        )._remove()
        return self._td_issue_api_key(_("Новий API-ключ агента"))

    def _td_issue_api_key(self, title):
        agent, agent_user = self, self.agent_user_id
        login = agent_user.login
        max_days = max(agent_user.all_group_ids.mapped("api_key_duration") or [0.0]) or 1.0
        expiration = datetime.now() + timedelta(days=max_days) - timedelta(minutes=1)
        key = self.env["res.users.apikeys"].with_user(agent_user).sudo()._generate("rpc", "odoo-mcp", expiration)
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "td.claude.agent.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_agent_id": agent.id,
                "default_agent_login": login,
                "default_api_key": key,
                "default_api_key_expires": fields.Datetime.to_string(expiration),
            },
        }

    @api.model
    def _td_create_agent_employee(self, owner, agent_user):
        Employee = self.env["hr.employee"].sudo()
        owner_emp = Employee.search([("user_id", "=", owner.id), ("company_id", "=", owner.company_id.id)], limit=1)
        owner_emp = owner_emp or Employee.search([("user_id", "=", owner.id)], limit=1)
        return Employee.create(
            {
                "name": agent_user.name,
                "user_id": agent_user.id,
                "company_id": owner.company_id.id,
                "department_id": owner_emp.department_id.id,
                "parent_id": owner_emp.id,
                "job_title": "AI-агент",
            }
        )
