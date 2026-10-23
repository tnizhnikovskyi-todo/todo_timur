import logging
import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ProjectProject(models.Model):
    _inherit = "project.project"

    td_claude_context = fields.Html(string="Контекст проєкту для Claude")
    td_claude_project_url = fields.Char(string="Проєкт Claude (claude.ai)", copy=False)
    td_claude_repo = fields.Char(string="Репозиторій (owner/repo)", help="Наприклад, todo-ltd/factory3d")
    td_claude_branch = fields.Char(string="Гілка за замовчуванням")
    td_claude_skill_ids = fields.Many2many(
        "td.claude.skill",
        "td_claude_project_skill_rel",
        "project_id",
        "skill_id",
        string="Скіли проєкту",
        domain="[('scope', '=', 'project')]",
    )

    @api.constrains("td_claude_repo")
    def _check_td_claude_repo(self):
        for project in self:
            if project.td_claude_repo and not REPO_RE.match(project.td_claude_repo):
                raise ValidationError(_("Репозиторій вказуйте у форматі owner/repo (наприклад, todo-ltd/factory3d)."))

    def _td_claude_project_info(self):
        """Вказівник на проєкт для Claude: id, назва, репозиторій, гілка, посилання на проєкт claude.ai, контекст."""
        self.ensure_one()
        project = self.sudo()
        return {
            "id": project.id,
            "name": project.display_name,
            "repo": project.td_claude_repo or None,
            "branch": project.td_claude_branch or None,
            "claude_url": project.td_claude_project_url or None,
            "context_text": html2plaintext(project.td_claude_context or "").strip(),
        }

    def _td_claude_project_skills(self):
        """Активні скіли, прив'язані до проєкту (scope=project)."""
        self.ensure_one()
        return self.sudo().td_claude_skill_ids.filtered(lambda s: s.scope == "project" and s.state == "active")

    def td_claude_project_brief(self):
        """Бриф проєкту для людини й агента (лише читання): проєкт + скіли (корпоративні й проєкту, без тіл)."""
        self.ensure_one()
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("Бриф проєкту доступний лише внутрішнім користувачам."))
        self.check_access("read")
        Skill = self.env["td.claude.skill"].sudo()
        corporate = Skill.search([("state", "=", "active"), ("scope", "=", "corporate")])
        skills = corporate | self._td_claude_project_skills()
        return {"project": self._td_claude_project_info(), "skills": Skill._td_brief_items(skills)}

    def td_claude_append_context(self, text):
        """Агент або людина (учасник проєкту з доступом на читання) дописує пункт у контекст проєкту."""
        self.ensure_one()
        Agent = self.env["td.claude.agent"]
        if not Agent._td_is_agent_user(self.env.uid) and not self.env.user.has_group("base.group_user"):
            raise AccessError(_("Дописувати контекст проєкту можуть лише внутрішні користувачі."))
        self.check_access("read")
        entry = Markup("<p>%s — %s</p>") % (fields.Date.context_today(self), text or "")
        self.sudo().td_claude_context = Markup(self.td_claude_context or "") + entry
        return True

    def action_td_claude_project_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Інструкція для проєкту Claude"),
            "res_model": "td.claude.project.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_project_id": self.id},
        }


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    td_claude_role_id = fields.Many2one(
        "td.claude.role",
        string="Роль Claude",
        ondelete="set null",
        help="Зміна стадії задачі на цю запускає агента цієї ролі (того ж власника).",
    )


class ProjectTask(models.Model):
    _inherit = "project.task"

    td_claude_paused = fields.Boolean(
        string="Пауза Claude", copy=False, help="Агенти не запускаються автоматично; згадка власника працює."
    )
    td_claude_hops_today = fields.Integer(string="Запусків Claude за добу", compute="_compute_td_claude_hops_today")

    td_claude_session_url = fields.Char(string="Claude-сесія", compute="_compute_td_claude_session_url")

    def _compute_td_claude_hops_today(self):
        Request = self.env["td.claude.request"]
        for task in self:
            task.td_claude_hops_today = Request._td_hops_today(task) if task.id else 0

    @api.depends_context("uid")
    def _compute_td_claude_session_url(self):
        self.td_claude_session_url = False
        tasks = self.filtered("id")
        if not tasks:
            return
        sessions = (
            self.env["td.claude.session"]
            .sudo()
            .search(
                [
                    ("owner_id", "=", self.env.user.id),
                    ("res_model", "=", "project.task"),
                    ("res_id", "in", tasks.ids),
                    ("session_url", "!=", False),
                ]
            )
        )
        urls = {}
        for session in sessions:  # впорядковано: свіжіша сесія першою
            urls.setdefault(session.res_id, session.session_url)
        for task in tasks:
            task.td_claude_session_url = urls.get(task.id, False)

    def action_td_open_claude_session(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.td_claude_session_url, "target": "new"}

    # ------------------------------------------------------------------
    # Табель агента
    # ------------------------------------------------------------------
    def td_claude_log_time(self, hours, description, actual_minutes=0):
        """Агент списує час на задачу: hours — людський еквівалент (вгору до 0,25; 0,25..8), опис за стандартом.

        Повертає id рядка табеля (account.analytic.line).
        """
        self.ensure_one()
        agent = self.env["td.claude.agent"]._td_current_agent()
        Line = self.env["account.analytic.line"]
        hours = Line._td_claude_round_hours(hours)
        text = Line._td_claude_clean_description(description)
        try:
            minutes = int(actual_minutes or 0)
        except (TypeError, ValueError) as exc:
            raise UserError(_("Реальний час має бути числом хвилин.")) from exc
        if minutes < 0:
            raise UserError(_("Реальний час не може бути від'ємним."))
        self.check_access("read")
        if not self.project_id.allow_timesheets:
            raise UserError(_("У проєкті «%s» вимкнено табель.", self.project_id.display_name))
        employee = self.env["hr.employee"].sudo().search(
            [("user_id", "=", agent.agent_user_id.id), ("company_id", "in", self.company_id.ids + [False])], limit=1
        ) or self.env["hr.employee"].sudo().search([("user_id", "=", agent.agent_user_id.id)], limit=1)
        if not employee:
            raise UserError(_("Для агента немає співробітника: табель неможливий."))
        request = (
            self.env["td.claude.request"]
            .sudo()
            .search(
                [
                    ("agent_id", "=", agent.id),
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("kind", "!=", "ping"),
                ],
                limit=1,
            )
        )
        today = fields.Date.context_today(self.with_context(tz=self.env.user.tz or "UTC"))
        line = Line.create(
            {
                "task_id": self.id,
                "project_id": self.project_id.id,
                "employee_id": employee.id,
                "name": text,
                "unit_amount": hours,
                "date": today,
                "td_claude_is_ai": True,
                "td_claude_actual_minutes": minutes,
                "td_claude_request_id": request.id,
            }
        )
        return line.id

    # ------------------------------------------------------------------
    # Призначення задачі агенту
    # ------------------------------------------------------------------
    def _td_claude_agents(self):
        """Активні агенти контуру поточного користувача (власника або агента-колеги)."""
        Agent = self.env["td.claude.agent"].sudo()
        owner = Agent._td_owner_of(self.env.user)
        return Agent.search([("owner_id", "=", owner.id), ("active", "=", True)])

    def _td_claude_notify_assigned(self, previous):
        """previous: {task_id: set(user_id)}; створює запити для нових виконавців-агентів контуру."""
        agents = self._td_claude_agents()
        for agent in agents:
            agent_uid = agent.agent_user_id.id
            for task in self:
                if agent_uid in task.user_ids.ids and agent_uid not in previous.get(task.id, set()):
                    self._td_claude_launch_safe(agent, "assign", task)

    def _td_claude_notify_stage(self, previous):
        """previous: {task_id: stage}; запускає агента ролі нової стадії того ж власника."""
        agents = self._td_claude_agents()
        if not agents:
            return
        for task in self:
            stage = task.stage_id
            if not stage.td_claude_role_id or previous.get(task.id) == stage:
                continue
            for agent in agents.filtered(lambda a, role=stage.td_claude_role_id: a.role_id == role):
                self._td_claude_launch_safe(agent, "stage", task)

    def _td_claude_launch_safe(self, agent, kind, task):
        try:
            with self.env.cr.savepoint():
                self.env["td.claude.request"]._td_launch(agent, kind, record=task)
        except Exception:
            _logger.exception("td_claude_agent: не вдалося створити запит %s для задачі %s", kind, task.id)

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        if any(vals.get("user_ids") for vals in vals_list):
            tasks._td_claude_notify_assigned({})
        return tasks

    def write(self, vals):
        previous = {task.id: set(task.user_ids.ids) for task in self} if "user_ids" in vals else None
        stages = {task.id: task.stage_id for task in self} if "stage_id" in vals else None
        res = super().write(vals)
        if previous is not None:
            self._td_claude_notify_assigned(previous)
        if stages is not None:
            self._td_claude_notify_stage(stages)
        return res
