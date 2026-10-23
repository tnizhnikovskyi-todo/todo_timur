from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TdClaudeTeamWizard(models.TransientModel):
    _name = "td.claude.team.wizard"
    _description = "Створити команду Claude"

    role_ids = fields.Many2many("td.claude.role", string="Ролі", default=lambda self: self._default_role_ids())
    state = fields.Selection([("draft", "Вибір"), ("done", "Готово")], default="draft")
    result = fields.Text(string="Логіни й ключі", readonly=True)

    @api.model
    def _default_role_ids(self):
        Agent = self.env["td.claude.agent"].sudo().with_context(active_test=False)
        existing = Agent.search([("owner_id", "=", self.env.user.id)]).role_id
        return self.env["td.claude.role"].search([("id", "not in", existing.ids)])

    def action_create(self):
        self.ensure_one()
        if not self.role_ids:
            raise UserError(_("Оберіть хоча б одну роль."))
        Agent = self.env["td.claude.agent"]
        owner = Agent._td_check_can_create()
        lines = []
        for role in self.role_ids.sorted("sequence"):
            agent = Agent._td_create_agent(owner, role)
            key, expires = agent._td_generate_key()
            lines.append(f"{role.name}: логін {agent.agent_user_id.login}, ключ {key} (діє до {expires:%Y-%m-%d})")
        self.write({"state": "done", "result": "\n".join(lines)})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
