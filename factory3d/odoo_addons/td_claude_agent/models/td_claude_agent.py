import json
import logging
import re
from datetime import datetime, timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

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
    role_id = fields.Many2one(
        "td.claude.role", string="Роль", ondelete="restrict", index=True, help="Обов'язкова для нових агентів"
    )
    role_code = fields.Selection(related="role_id.code", string="Код ролі", store=True)
    name = fields.Char(related="agent_user_id.name", string="Назва", readonly=True)
    fire_url = fields.Char(string="Fire URL", help="Адреса API «fire» вашої Claude Code Routine")
    fire_token = fields.Char(string="Токен Routine", copy=False)
    active = fields.Boolean(default=True)
    last_fire_at = fields.Datetime(string="Останній запуск", readonly=True)
    last_fire_status = fields.Char(string="Статус останнього запуску", readonly=True)
    request_count = fields.Integer(compute="_compute_request_count", string="Запитів")

    _owner_role_uniq = models.Constraint(
        "UNIQUE(owner_id, role_id)", "Користувач уже має агента Claude з такою роллю."
    )
    _agent_user_uniq = models.Constraint("UNIQUE(agent_user_id)", "Цей користувач уже є агентом Claude.")

    @api.model_create_multi
    def create(self, vals_list):
        if any(not vals.get("role_id") for vals in vals_list):
            raise ValidationError(_("Вкажіть роль агента."))
        return super().create(vals_list)

    def write(self, vals):
        if "role_id" in vals and not vals["role_id"]:
            raise ValidationError(_("Вкажіть роль агента."))
        return super().write(vals)

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
    def _td_is_agent_user(self, uid):
        return bool(self.sudo().with_context(active_test=False).search_count([("agent_user_id", "=", uid)]))

    @api.model
    def _td_check_agent_user(self):
        if not self._td_is_agent_user(self.env.uid):
            raise AccessError(_("Дія доступна лише користувачам-агентам Claude."))

    @api.model
    def _td_current_agent(self):
        """Запис агента поточного користувача-агента (sudo; токен агенту не віддається)."""
        self._td_check_agent_user()
        return self.sudo().with_context(active_test=False).search([("agent_user_id", "=", self.env.uid)], limit=1)

    @api.model
    def _td_owner_of(self, user):
        """Власник контуру: для агента — його власник, для людини — вона сама."""
        agent = self.sudo().with_context(active_test=False).search([("agent_user_id", "=", user.id)], limit=1)
        return agent.owner_id if agent else user

    @api.model
    def td_claude_brief(self):
        """Бриф для агента на старті: роль з інструкцією та перелік скілів (без тіл — економія контексту)."""
        agent = self._td_current_agent()
        role = agent.role_id
        skills = self.env["td.claude.skill"].sudo().search(self.env["td.claude.skill"]._td_agent_domain(agent))
        return {
            "role": {
                "code": role.code,
                "name": role.name,
                "model_hint": role.model_hint or None,
                "instructions": role.instructions or "",
            },
            "skills": [
                {"code": s.code, "name": s.name, "description": s.description or "", "version": s.version}
                for s in skills
            ],
        }

    @api.model
    def _td_unique_login(self, owner, role=None):
        base = "claude." + re.sub(r"[^a-z0-9._@+-]", "-", (owner.login or str(owner.id)).lower())
        if role and role.code != "manager":
            base += "." + role.code
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        login, n = base, 1
        while Users.search_count([("login", "=", login)]):
            n += 1
            login = f"{base}-{n}"
        return login

    @api.model
    def _td_agent_user_name(self, owner, role):
        name = f"Claude · {role.name}"
        taken = self.env["res.users"].sudo().with_context(active_test=False).search_count([("name", "=", name)])
        return f"{name} · {owner.name}" if taken else name

    @api.model
    def _td_create_agent(self, owner, role):
        """Створює користувача-агента, працівника й запис агента (ключ видається окремо)."""
        if self.sudo().with_context(active_test=False).search_count(
            [("owner_id", "=", owner.id), ("role_id", "=", role.id)]
        ):
            raise UserError(_("У вас уже є агент Claude з роллю «%s».", role.name))
        Users = self.env["res.users"].sudo()
        groups = (
            self.env.ref("base.group_user")
            | self.env.ref("project.group_project_user")
            | self.env.ref("hr_timesheet.group_hr_timesheet_user")
            | role.group_ids
        )
        agent_user = Users.create(
            {
                "name": self._td_agent_user_name(owner, role),
                "login": self._td_unique_login(owner, role),
                "company_id": owner.company_id.id,
                "company_ids": [(6, 0, owner.company_ids.ids)],
                "group_ids": [(6, 0, groups.ids)],
                "notification_type": "inbox",
                "tz": owner.tz,
            }
        )
        self._td_create_agent_employee(owner, agent_user)
        return self.sudo().create({"owner_id": owner.id, "agent_user_id": agent_user.id, "role_id": role.id})

    @api.model
    def _td_check_can_create(self):
        owner = self.env.user
        if owner.share or owner._is_public():
            raise UserError(_("Агента можуть створити лише внутрішні користувачі."))
        if self._td_is_agent_user(owner.id):
            raise UserError(_("Агент Claude не може створювати агентів."))
        return owner

    @api.model
    def action_create_my_agent(self):
        """Створює агента-Менеджера для поточного користувача. Повертає діалог із одноразовим API-ключем."""
        owner = self._td_check_can_create()
        role = self.env["td.claude.role"].sudo().search([("code", "=", "manager")], limit=1)
        if not role:
            raise UserError(_("Немає ролі «Менеджер»."))
        return self._td_create_agent(owner, role)._td_issue_api_key(_("Агент Claude створено"))

    @api.model
    def action_create_team(self):
        """Відкриває майстер «Створити команду Claude»."""
        self._td_check_can_create()
        return {
            "type": "ir.actions.act_window",
            "name": _("Створити команду Claude"),
            "res_model": "td.claude.team.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_new_api_key(self):
        """Відкликає ключі odoo-mcp агента і видає новий (лише власник)."""
        self.ensure_one()
        if self.owner_id != self.env.user:
            raise UserError(_("Новий ключ може отримати лише власник агента."))
        self.env["res.users.apikeys"].sudo().search(
            [("user_id", "=", self.agent_user_id.id), ("name", "=", "odoo-mcp")]
        )._remove()
        return self._td_issue_api_key(_("Новий API-ключ агента"))

    def _td_generate_key(self):
        """Видає новий ключ odoo-mcp агента. Повертає (ключ, дата завершення)."""
        self.ensure_one()
        agent_user = self.agent_user_id
        max_days = max(agent_user.all_group_ids.mapped("api_key_duration") or [0.0]) or 1.0
        expiration = datetime.now() + timedelta(days=max_days) - timedelta(minutes=1)
        key = self.env["res.users.apikeys"].with_user(agent_user).sudo()._generate("rpc", "odoo-mcp", expiration)
        return key, expiration

    def _td_issue_api_key(self, title):
        agent, agent_user = self, self.agent_user_id
        login = agent_user.login
        key, expiration = self._td_generate_key()
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
