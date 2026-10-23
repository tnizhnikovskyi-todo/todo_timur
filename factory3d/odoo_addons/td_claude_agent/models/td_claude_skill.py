import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

CODE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PROPOSER_ROLES = ("methodologist", "manager")


class TdClaudeSkill(models.Model):
    _name = "td.claude.skill"
    _description = "Скіл Claude (інструкція, що зберігається в Odoo)"
    _inherit = ["mail.thread"]
    _order = "scope, code"

    name = fields.Char(string="Назва", required=True, tracking=True)
    code = fields.Char(string="Код (slug)", required=True, copy=False, tracking=True)
    scope = fields.Selection(
        [("corporate", "Корпоративний"), ("role", "Рольовий")], string="Охоплення", required=True, default="corporate"
    )
    role_ids = fields.Many2many("td.claude.role", string="Ролі", help="Для рольового скіла")
    description = fields.Text(string="Коли застосовувати", help="1-2 речення, як frontmatter SKILL.md")
    body = fields.Text(string="Інструкція (Markdown)")
    version = fields.Integer(string="Версія", default=0, readonly=True, copy=False, tracking=True)
    state = fields.Selection(
        [("proposed", "Пропозиція"), ("active", "Активний"), ("archived", "Архівний")],
        string="Стан",
        required=True,
        default="active",
        tracking=True,
    )
    proposal_body = fields.Text(string="Запропонований текст", copy=False)
    proposal_note = fields.Char(string="Пояснення пропозиції", copy=False)
    proposal_author_id = fields.Many2one("res.users", string="Автор пропозиції", copy=False)
    proposal_date = fields.Datetime(string="Дата пропозиції", copy=False)
    has_proposal = fields.Boolean(string="Є пропозиція", compute="_compute_has_proposal", store=True)
    version_ids = fields.One2many("td.claude.skill.version", "skill_id", string="Історія")

    _code_uniq = models.Constraint("UNIQUE(code)", "Скіл з таким кодом уже існує.")

    @api.depends("proposal_body")
    def _compute_has_proposal(self):
        for skill in self:
            skill.has_proposal = bool(skill.proposal_body)

    @api.constrains("code")
    def _check_code(self):
        for skill in self:
            if not CODE_RE.match(skill.code or ""):
                raise ValidationError(_("Код скіла: латинські малі літери, цифри й дефіс (slug)."))

    # ------------------------------------------------------------------
    # Права: змінює лише людина
    # ------------------------------------------------------------------
    @api.model
    def _td_is_human(self, uid=None):
        user = self.env["res.users"].sudo().browse(uid or self.env.uid)
        return bool(user.has_group("base.group_user")) and not self.env["td.claude.agent"]._td_is_agent_user(user.id)

    def _td_check_human(self):
        if not self._td_is_human():
            raise AccessError(_("Затверджувати й змінювати скіли можуть лише люди (не користувачі-агенти)."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            self._td_check_human()
        skills = super().create(vals_list)
        for skill in skills.filtered(lambda s: s.state == "active" and s.body):
            if not skill.version:
                skill.sudo().write({"version": 1})
            skill._td_add_version(skill.body, _("Початкова версія"), self.env.user)
        return skills

    def write(self, vals):
        if not self.env.su:
            self._td_check_human()
        if "body" in vals and "version" not in vals:
            # пряма правка людиною = нова версія з записом в історію
            res = True
            for skill in self:
                if skill.version >= 1 and (vals["body"] or "") != (skill.body or ""):
                    res &= super(TdClaudeSkill, skill).write(dict(vals, version=skill.version + 1))
                    skill._td_add_version(vals["body"] or "", _("Редагування"), self.env.user)
                else:
                    res &= super(TdClaudeSkill, skill).write(vals)
            return res
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            self._td_check_human()
        return super().unlink()

    def _td_add_version(self, body, note, author, version=None):
        self.ensure_one()
        return (
            self.env["td.claude.skill.version"]
            .sudo()
            .create(
                {
                    "skill_id": self.id,
                    "version": version or self.version,
                    "body": body,
                    "note": note,
                    "author_id": author.id,
                    "date": fields.Datetime.now(),
                }
            )
        )

    # ------------------------------------------------------------------
    # Дії власника
    # ------------------------------------------------------------------
    def action_approve_proposal(self):
        self._td_check_human()
        for skill in self:
            if not skill.proposal_body:
                raise UserError(_("У скіла «%s» немає пропозиції.", skill.name))
            version = skill.version + 1
            author = skill.proposal_author_id or self.env.user
            note = skill.proposal_note or ""
            skill.sudo().write(
                {
                    "body": skill.proposal_body,
                    "version": version,
                    "state": "active" if skill.state == "proposed" else skill.state,
                    "proposal_body": False,
                    "proposal_note": False,
                    "proposal_author_id": False,
                    "proposal_date": False,
                }
            )
            skill._td_add_version(skill.body, note, author, version=version)
            skill.message_post(body=_("Пропозицію затверджено: версія %s.", version))
        return True

    def action_reject_proposal(self):
        self._td_check_human()
        for skill in self:
            if not skill.proposal_body:
                continue
            skill.sudo().write(
                {
                    "proposal_body": False,
                    "proposal_note": False,
                    "proposal_author_id": False,
                    "proposal_date": False,
                    "state": "archived" if skill.state == "proposed" else skill.state,
                }
            )
            skill.message_post(body=_("Пропозицію відхилено."))
        return True

    def action_archive_skill(self):
        self._td_check_human()
        self.sudo().write({"state": "archived"})
        return True

    def action_activate_skill(self):
        self._td_check_human()
        self.filtered("version").sudo().write({"state": "active"})
        return True

    # ------------------------------------------------------------------
    # API для агентів (RPC)
    # ------------------------------------------------------------------
    @api.model
    def _td_agent_domain(self, agent):
        return [
            ("state", "=", "active"),
            "|",
            ("scope", "=", "corporate"),
            ("role_ids", "in", agent.role_id.ids),
        ]

    @api.model
    def td_claude_read(self, codes):
        """Тіла скілів за кодами (лише агент). Повертає [{code, version, body}] для активних скілів."""
        self.env["td.claude.agent"]._td_check_agent_user()
        if isinstance(codes, str):
            codes = [codes]
        skills = self.search([("code", "in", list(codes or [])), ("state", "=", "active")])
        by_code = {s.code: s for s in skills}
        return [
            {"code": c, "version": by_code[c].version, "body": by_code[c].body or ""} for c in codes if c in by_code
        ]

    @api.model
    def _td_check_proposer(self):
        agent = self.env["td.claude.agent"]._td_current_agent()
        if agent.role_id.code not in PROPOSER_ROLES:
            raise AccessError(_("Пропонувати зміни скілів можуть лише ролі Методолог і Менеджер."))
        return agent

    def _td_notify_owner(self, agent, text):
        self.message_post(body=text, partner_ids=agent.owner_id.partner_id.ids, subtype_xmlid="mail.mt_note")

    @api.model
    def td_claude_propose(self, code, body, note=None):
        """Агент (Методолог/Менеджер) пропонує нову редакцію скіла; власник затверджує в Odoo."""
        agent = self._td_check_proposer()
        skill = self.sudo().search([("code", "=", code), ("state", "!=", "archived")], limit=1)
        if not skill:
            raise UserError(_("Скіл «%s» не знайдено.", code))
        if not (body or "").strip():
            raise UserError(_("Порожня пропозиція."))
        skill.write(
            {
                "proposal_body": body,
                "proposal_note": note or False,
                "proposal_author_id": self.env.uid,
                "proposal_date": fields.Datetime.now(),
            }
        )
        skill._td_notify_owner(agent, _("%s пропонує нову редакцію скіла: %s", self.env.user.name, note or "—"))
        return skill.id

    @api.model
    def td_claude_propose_new(self, code, name, scope, role_codes, description, body, note=None):
        """Агент пропонує новий скіл (стан «Пропозиція», версія 0 до затвердження)."""
        agent = self._td_check_proposer()
        if scope not in ("corporate", "role"):
            raise UserError(_("Охоплення: corporate або role."))
        if not (body or "").strip():
            raise UserError(_("Порожня пропозиція."))
        roles = self.env["td.claude.role"].sudo().search([("code", "in", list(role_codes or []))])
        if scope == "role" and not roles:
            raise UserError(_("Для рольового скіла вкажіть існуючі ролі."))
        if self.sudo().with_context(active_test=False).search_count([("code", "=", code)]):
            raise UserError(_("Скіл із кодом «%s» уже існує.", code))
        skill = self.sudo().create(
            {
                "name": name,
                "code": code,
                "scope": scope,
                "role_ids": [(6, 0, roles.ids if scope == "role" else [])],
                "description": description,
                "state": "proposed",
                "proposal_body": body,
                "proposal_note": note or False,
                "proposal_author_id": self.env.uid,
                "proposal_date": fields.Datetime.now(),
            }
        )
        skill._td_notify_owner(agent, _("%s пропонує новий скіл «%s»: %s", self.env.user.name, name, note or "—"))
        return skill.id


class TdClaudeSkillVersion(models.Model):
    _name = "td.claude.skill.version"
    _description = "Версія скіла Claude"
    _order = "skill_id, version desc"

    skill_id = fields.Many2one("td.claude.skill", string="Скіл", required=True, ondelete="cascade", index=True)
    version = fields.Integer(string="Версія", required=True)
    body = fields.Text(string="Текст")
    note = fields.Char(string="Примітка")
    author_id = fields.Many2one("res.users", string="Автор")
    date = fields.Datetime(string="Дата")
