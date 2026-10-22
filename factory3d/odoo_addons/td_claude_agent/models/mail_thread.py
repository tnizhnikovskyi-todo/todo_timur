import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _message_post_after_hook(self, message, msg_values):
        res = super()._message_post_after_hook(message, msg_values)
        if message.message_type == "comment":
            try:
                with self.env.cr.savepoint():
                    self._td_claude_on_comment(message)
            except Exception:
                _logger.exception("td_claude_agent: не вдалося створити запит для повідомлення %s", message.id)
        return res

    def _td_claude_on_comment(self, message):
        user = self.env.user
        if not message.partner_ids or message.author_id != user.partner_id:
            return
        Agent = self.env["td.claude.agent"].sudo()
        # захист від циклів: агент ніколи не запускає агентів
        if Agent.with_context(active_test=False).search_count([("agent_user_id", "=", user.id)]):
            return
        agent = Agent.search([("owner_id", "=", user.id), ("active", "=", True)], limit=1)
        if not agent or agent.agent_user_id.partner_id not in message.partner_ids:
            return
        self.env["td.claude.request"]._td_create(agent, "mention", record=self, message=message)
