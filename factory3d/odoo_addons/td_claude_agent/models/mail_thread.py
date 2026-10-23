import logging

from markupsafe import Markup

from odoo import models
from odoo.tools import html_sanitize

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
        if message.author_id != user.partner_id:
            return
        direct_chat = self._name == "discuss.channel" and len(self) == 1 and self.channel_type == "chat"
        if not direct_chat and not message.partner_ids:
            return
        Agent = self.env["td.claude.agent"].sudo()
        owner = Agent._td_owner_of(user)
        # згадати можна лише агентів свого контуру; агент ніколи не запускає сам себе (перевіряє _td_launch)
        agents = Agent.search([("owner_id", "=", owner.id), ("active", "=", True)])
        if direct_chat:
            # особистий чат з агентом: кожне повідомлення в ньому — звернення до агента, згадка не потрібна
            addressed = self.sudo().channel_member_ids.partner_id
        else:
            addressed = message.partner_ids
        for agent in agents.filtered(lambda a: a.agent_user_id.partner_id in addressed):
            self.env["td.claude.request"]._td_launch(agent, "mention", record=self, message=message)

    def td_claude_post(self, body, partner_ids=None):
        """Відповідь агента в чатер (через RPC): HTML після санітизації, а не екранований текст."""
        self.ensure_one()
        self.env["td.claude.agent"]._td_check_agent_user()
        message = self.message_post(
            body=Markup(html_sanitize(body or "")),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids or [],
        )
        return message.id
