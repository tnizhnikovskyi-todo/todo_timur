from odoo import _, api, fields, models
from odoo.exceptions import AccessError

ROLE_CODES = [
    ("manager", "Менеджер (PM)"),
    ("architect", "Архітектор (AN)"),
    ("coder", "Кодер (DV)"),
    ("tester", "Тестувальник (QA)"),
    ("methodologist", "Методолог"),
]


class TdClaudeRole(models.Model):
    _name = "td.claude.role"
    _description = "Роль Claude-агента"
    _order = "sequence, id"

    name = fields.Char(string="Назва", required=True, translate=False)
    code = fields.Selection(ROLE_CODES, string="Код", required=True)
    sequence = fields.Integer(default=10)
    instructions = fields.Text(string="Інструкція ролі", help="Базовий промпт ролі (Markdown)")
    model_hint = fields.Selection(
        [("opus", "Opus"), ("sonnet", "Sonnet")], string="Модель", help="Підказка, яку модель використати Routine"
    )
    active = fields.Boolean(default=True)
    group_ids = fields.Many2many(
        "res.groups", string="Додаткові права агентів", help="Групи, які отримують користувачі-агенти цієї ролі"
    )

    _code_uniq = models.Constraint("UNIQUE(code)", "Роль з таким кодом уже існує.")

    @api.model
    def _td_check_human_editor(self):
        """Роль і скіл змінює лише людина: користувачі-агенти заборонені (виняток — sudo в API агента)."""
        if not self.env.su and self.env["td.claude.agent"]._td_is_agent_user(self.env.uid):
            raise AccessError(_("Користувачі-агенти Claude не можуть змінювати ролі й скіли напряму."))

    @api.model_create_multi
    def create(self, vals_list):
        self._td_check_human_editor()
        return super().create(vals_list)

    def write(self, vals):
        self._td_check_human_editor()
        old = {role.id: role.group_ids for role in self} if "group_ids" in vals else {}
        res = super().write(vals)
        for role in self.filtered(lambda r: r.id in old):
            role._td_sync_agent_groups(removed=old[role.id] - role.group_ids)
        return res

    def _td_sync_agent_groups(self, removed=None):
        """Додає групи ролі її користувачам-агентам; зняті з ролі групи забирає."""
        for role in self:
            agents = self.env["td.claude.agent"].sudo().with_context(active_test=False).search(
                [("role_id", "=", role.id)]
            )
            commands = [(4, g.id) for g in role.group_ids] + [(3, g.id) for g in (removed or [])]
            if agents and commands:
                agents.agent_user_id.sudo().write({"group_ids": commands})

    def unlink(self):
        self._td_check_human_editor()
        return super().unlink()

    @api.model
    def _td_stage_role_code(self, stage_name):
        """Код ролі за міткою в назві стадії: (QA) або «Тест …» → tester, (PM), (AN), (DV)."""
        name = (stage_name or "").strip()
        if "(QA)" in name or name.lower().startswith("тест"):
            return "tester"
        for marker, code in (("(PM)", "manager"), ("(AN)", "architect"), ("(DV)", "coder")):
            if marker in name:
                return code
        return None

    @api.model
    def _td_map_stages(self):
        """Заповнює порожнє td_claude_role_id у стадій за мітками; наявні налаштування не чіпає."""
        roles = {r.code: r for r in self.sudo().search([])}
        stages = self.env["project.task.type"].sudo().with_context(active_test=False).search(
            [("td_claude_role_id", "=", False)]
        )
        for stage in stages:
            role = roles.get(self._td_stage_role_code(stage.name))
            if role:
                stage.td_claude_role_id = role
        return True
