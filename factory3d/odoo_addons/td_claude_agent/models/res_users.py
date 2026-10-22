from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = "res.users"

    td_claude_has_agent = fields.Boolean(string="Є агент Claude", compute="_compute_td_claude_has_agent")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["td_claude_has_agent"]

    @api.depends_context("uid")
    def _compute_td_claude_has_agent(self):
        owners = set(
            self.env["td.claude.agent"]
            .sudo()
            .with_context(active_test=False)
            .search([("owner_id", "in", self.ids)])
            .owner_id.ids
        )
        for user in self:
            user.td_claude_has_agent = user.id in owners

    def action_td_create_claude_agent(self):
        self.ensure_one()
        if self != self.env.user:
            raise AccessError(_("Агента можна створити лише для себе."))
        return self.env["td.claude.agent"].action_create_my_agent()
