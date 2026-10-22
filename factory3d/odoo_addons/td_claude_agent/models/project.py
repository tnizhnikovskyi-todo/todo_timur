import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = "project.project"

    td_claude_context = fields.Html(string="Контекст проєкту для Claude")


class ProjectTask(models.Model):
    _inherit = "project.task"

    td_claude_session_url = fields.Char(string="Claude-сесія", compute="_compute_td_claude_session_url")

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
    # Призначення задачі агенту
    # ------------------------------------------------------------------
    def _td_claude_notify_assigned(self, previous):
        """previous: {task_id: set(user_id)}; створює запити для нових виконавців-агентів власника."""
        user = self.env.user
        agents = self.env["td.claude.agent"].sudo().search([("owner_id", "=", user.id), ("active", "=", True)], limit=1)
        if not agents:
            return
        agent = agents[0]
        agent_uid = agent.agent_user_id.id
        if user.id == agent_uid:
            return
        for task in self:
            if agent_uid in task.user_ids.ids and agent_uid not in previous.get(task.id, set()):
                try:
                    with self.env.cr.savepoint():
                        self.env["td.claude.request"]._td_create(agent, "assign", record=task)
                except Exception:
                    _logger.exception("td_claude_agent: не вдалося створити запит на призначення задачі %s", task.id)

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        if any(vals.get("user_ids") for vals in vals_list):
            tasks._td_claude_notify_assigned({})
        return tasks

    def write(self, vals):
        previous = {task.id: set(task.user_ids.ids) for task in self} if "user_ids" in vals else None
        res = super().write(vals)
        if previous is not None:
            self._td_claude_notify_assigned(previous)
        return res
