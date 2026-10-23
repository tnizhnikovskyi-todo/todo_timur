import json

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

GOOD = "Виправлено баг Odoo у compute_pickings упаковки, перевірено на тестовій базі"
ROLE_CODES = ("manager", "architect", "coder", "tester", "methodologist")
STAGES = {
    "pm": "Відставання (PM)",
    "an": "Специфікації (AN)",
    "dv": "Розробка (DV)",
    "qa": "Тест (QA)",
}


@tagged("post_install", "-at_install", "f3d", "f3d_claude", "f3d_claude_v2")
class TestClaudeV2(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        groups = cls.env.ref("base.group_user") | cls.env.ref("project.group_project_user")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.owner = Users.create({"name": "Owner V2", "login": "owner.v2", "group_ids": [(6, 0, groups.ids)]})
        cls.other = Users.create({"name": "Other V2", "login": "other.v2", "group_ids": [(6, 0, groups.ids)]})
        cls.roles = {r.code: r for r in cls.env["td.claude.role"].search([])}
        Agent = cls.env["td.claude.agent"]
        cls.team = {code: Agent._td_create_agent(cls.owner, role) for code, role in cls.roles.items()}
        cls.other_team = {code: Agent._td_create_agent(cls.other, role) for code, role in cls.roles.items()}
        for agent in list(cls.team.values()) + list(cls.other_team.values()):
            agent.write({"fire_url": "https://api.anthropic.com/v1/fire", "fire_token": "sk-secret"})
        cls.project = cls.env["project.project"].create({"name": "Проєкт V2"})
        cls.stages = {
            key: cls.env["project.task.type"].create({"name": name, "project_ids": [(6, 0, cls.project.ids)]})
            for key, name in STAGES.items()
        }
        cls.env["td.claude.role"]._td_map_stages()
        cls.task = cls.env["project.task"].create(
            {"name": "Задача V2", "project_id": cls.project.id, "stage_id": cls.stages["pm"].id}
        )
        cls.Skill = cls.env["td.claude.skill"]

    # ------------------------------------------------------------------
    def _user(self, code, team=None):
        return (team or self.team)[code].agent_user_id

    def _requests(self, code=None, kind=None, team=None):
        domain = [("agent_id", "in", [a.id for a in (team or self.team).values()])]
        if code:
            domain = [("agent_id", "=", (team or self.team)[code].id)]
        if kind:
            domain.append(("kind", "=", kind))
        return self.env["td.claude.request"].sudo().search(domain)

    def _move(self, user, stage_key):
        self.task.with_user(user).write({"stage_id": self.stages[stage_key].id})

    def _flush_requests(self):
        """Прибрати склеювання: усі запити вважаємо відправленими давно."""
        self.env.cr.execute("UPDATE td_claude_request SET create_date = create_date - interval '5 minutes'")
        self.env.invalidate_all()

    # ------------------------------------------------------------------
    # Ролі, агенти, майстер
    # ------------------------------------------------------------------
    def test_seed_roles_and_instructions(self):
        self.assertEqual(set(self.roles), set(ROLE_CODES))
        for code, role in self.roles.items():
            self.assertIn("td_claude_log_time", role.instructions.rsplit("##", 1)[-1], code)
            self.assertIn("actual_minutes", role.instructions.rsplit("##", 1)[-1], code)
        self.assertEqual(self.roles["manager"].model_hint, "opus")
        self.assertEqual(self.roles["coder"].model_hint, "sonnet")

    def test_agent_unique_per_owner_and_role(self):
        agent = self.team["coder"]
        self.assertEqual(agent.role_id.code, "coder")
        self.assertEqual(agent.role_code, "coder")
        self.assertEqual(len(self.team), 5)
        user = self.env["res.users"].with_context(no_reset_password=True).create({"name": "Dup", "login": "dup.v2"})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["td.claude.agent"].create(
                {"owner_id": self.owner.id, "agent_user_id": user.id, "role_id": self.roles["coder"].id}
            )
        with self.assertRaises(ValidationError):
            self.env["td.claude.agent"].create({"owner_id": self.owner.id, "agent_user_id": user.id})
        with self.assertRaises(UserError):
            self.env["td.claude.agent"]._td_create_agent(self.owner, self.roles["coder"])

    def test_team_wizard(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {"name": "Wiz V2", "login": "wiz.v2", "group_ids": [(6, 0, self.env.ref("base.group_user").ids)]}
        )
        Wizard = self.env["td.claude.team.wizard"].with_user(user)
        wizard = Wizard.create({})
        self.assertEqual(wizard.role_ids, self.env["td.claude.role"].search([]))
        wizard.role_ids = self.roles["manager"] | self.roles["coder"]
        wizard.action_create()
        agents = self.env["td.claude.agent"].sudo().search([("owner_id", "=", user.id)])
        self.assertEqual(set(agents.mapped("role_code")), {"manager", "coder"})
        self.assertEqual(wizard.state, "done")
        for agent in agents:
            self.assertIn(agent.agent_user_id.login, wizard.result)
            self.assertTrue(agent.agent_user_id.has_group("hr_timesheet.group_hr_timesheet_user"))
            self.assertTrue(self.env["hr.employee"].sudo().search([("user_id", "=", agent.agent_user_id.id)]))
        self.assertEqual(Wizard.create({}).role_ids.mapped("code"), ["architect", "tester", "methodologist"])
        with self.assertRaises(UserError):
            Wizard.create({"role_ids": [(5, 0, 0)]}).action_create()
        # агент не створює команду
        with self.assertRaises(UserError):
            self.env["td.claude.agent"].with_user(self._user("coder")).action_create_team()

    def test_stage_role_mapping(self):
        mapping = {
            "pm": "manager",
            "an": "architect",
            "dv": "coder",
            "qa": "tester",
        }
        for key, code in mapping.items():
            self.assertEqual(self.stages[key].td_claude_role_id.code, code, key)
        Role = self.env["td.claude.role"]
        self.assertEqual(Role._td_stage_role_code("Тест (AN)"), "tester")
        self.assertEqual(Role._td_stage_role_code("Тестування"), "tester")
        self.assertEqual(Role._td_stage_role_code("Погодження клієнта (PM)"), "manager")
        self.assertEqual(Role._td_stage_role_code("Оцінка розробником (DV)"), "coder")
        self.assertIsNone(Role._td_stage_role_code("Готово"))
        # наявні налаштування не перезаписуються
        self.stages["an"].td_claude_role_id = self.roles["methodologist"]
        Role._td_map_stages()
        self.assertEqual(self.stages["an"].td_claude_role_id.code, "methodologist")
        self.stages["an"].td_claude_role_id = self.roles["architect"]

    # ------------------------------------------------------------------
    # Бриф і скіли
    # ------------------------------------------------------------------
    def test_brief_per_role(self):
        corporate = set(self.Skill.search([("scope", "=", "corporate"), ("state", "=", "active")]).mapped("code"))
        self.assertTrue({"odoo19-standards", "chatter-etiquette", "safety-gates", "timesheet"} <= corporate)
        for code in ROLE_CODES:
            brief = self.env["td.claude.agent"].with_user(self._user(code)).td_claude_brief()
            self.assertEqual(brief["role"]["code"], code)
            self.assertEqual(brief["role"]["instructions"], self.roles[code].instructions)
            codes = {s["code"] for s in brief["skills"]}
            role_skills = set(
                self.Skill.search([("scope", "=", "role"), ("role_ids", "in", self.roles[code].ids)]).mapped("code")
            )
            self.assertEqual(len(role_skills), 1, code)
            self.assertEqual(codes, corporate | role_skills, code)
            for skill in brief["skills"]:
                self.assertEqual(set(skill), {"code", "name", "description", "version"})
                self.assertTrue(skill["description"])
                self.assertGreaterEqual(skill["version"], 1)

    def test_read_skills(self):
        res = self.Skill.with_user(self._user("coder")).td_claude_read(["timesheet", "nope", "odoo19-standards"])
        self.assertEqual([r["code"] for r in res], ["timesheet", "odoo19-standards"])
        self.assertIn("Добрі приклади", res[0]["body"])
        self.assertTrue(res[0]["version"] >= 1)
        self.assertEqual(self.Skill.with_user(self._user("coder")).td_claude_read("timesheet")[0]["code"], "timesheet")

    def test_timesheet_skill_examples(self):
        body = self.Skill.search([("code", "=", "timesheet")]).body
        good = body.split("## Добрі приклади")[1].split("## Погані приклади")[0]
        bad = body.split("## Погані приклади")[1]
        self.assertEqual(len([ln for ln in good.splitlines() if ln.strip()[:2] in ("1.", "2.", "3.")]), 3)
        self.assertEqual(len([ln for ln in bad.splitlines() if ln.strip()[:2] in ("1.", "2.", "3.")]), 3)
        self.assertIn("теуствання", bad)

    def test_non_agent_cannot_call_agent_api(self):
        Agent, Skill = self.env["td.claude.agent"], self.Skill
        for user in (self.owner, self.other, self.env.ref("base.user_admin")):
            with self.assertRaises(AccessError):
                Agent.with_user(user).td_claude_brief()
            with self.assertRaises(AccessError):
                Skill.with_user(user).td_claude_read(["timesheet"])
            with self.assertRaises(AccessError):
                Skill.with_user(user).td_claude_propose("timesheet", "x", "y")
            with self.assertRaises(AccessError):
                Skill.with_user(user).td_claude_propose_new("n", "N", "corporate", [], "d", "b")
            with self.assertRaises(AccessError):
                self.task.with_user(user).td_claude_log_time(1, GOOD)

    def test_skills_visibility_and_human_edit(self):
        skill = self.Skill.search([("code", "=", "chatter-etiquette")])
        self.assertEqual(skill.with_user(self.other).name, skill.name)
        self.assertEqual(skill.with_user(self._user("tester")).name, skill.name)
        self.assertEqual(len(skill.version_ids), 1)
        skill.with_user(self.owner).write({"body": "# Нова редакція"})
        self.assertEqual((skill.version, len(skill.version_ids)), (2, 2))
        self.assertEqual(skill.version_ids.sorted("version")[-1].body, "# Нова редакція")
        new = self.Skill.with_user(self.owner).create({"name": "Мій", "code": "my-skill", "body": "# Мій"})
        self.assertEqual((new.version, len(new.version_ids)), (1, 1))
        with self.assertRaises(ValidationError):
            self.Skill.with_user(self.owner).create({"name": "Bad", "code": "Bad Code", "body": "x"})

    def test_agents_cannot_edit_roles_and_skills(self):
        skill = self.Skill.search([("code", "=", "timesheet")])
        agent_skill = skill.with_user(self._user("methodologist"))
        with self.assertRaises(AccessError):
            agent_skill.write({"body": "hack"})
        with self.assertRaises(AccessError):
            agent_skill.unlink()
        with self.assertRaises(AccessError):
            self.Skill.with_user(self._user("manager")).create({"name": "x", "code": "x-y", "body": "b"})
        with self.assertRaises(AccessError):
            self.roles["coder"].with_user(self._user("coder")).write({"instructions": "hack"})
        self.roles["coder"].with_user(self.owner).write({"model_hint": "sonnet"})

    # ------------------------------------------------------------------
    # Пропозиції
    # ------------------------------------------------------------------
    def test_propose_approve_with_history(self):
        skill = self.Skill.search([("code", "=", "chatter-etiquette")])
        old_body, old_version = skill.body, skill.version
        proposer = self._user("methodologist")
        res = self.Skill.with_user(proposer).td_claude_propose("chatter-etiquette", "# Нова\nкоротше", "Занадто довго")
        self.assertEqual(res, skill.id)
        self.assertEqual((skill.body, skill.version), (old_body, old_version))
        self.assertEqual(skill.proposal_body, "# Нова\nкоротше")
        self.assertEqual(skill.proposal_note, "Занадто довго")
        self.assertEqual(skill.proposal_author_id, proposer)
        self.assertTrue(skill.has_proposal)
        self.assertEqual(self.Skill.search_count([("has_proposal", "=", True)]), 1)
        # агент не затверджує і не відхиляє
        for agent_code in ("methodologist", "manager"):
            with self.assertRaises(AccessError):
                skill.with_user(self._user(agent_code)).action_approve_proposal()
            with self.assertRaises(AccessError):
                skill.with_user(self._user(agent_code)).action_reject_proposal()
        self.assertTrue(skill.has_proposal)
        skill.with_user(self.owner).action_approve_proposal()
        self.assertEqual((skill.body, skill.version), ("# Нова\nкоротше", old_version + 1))
        self.assertFalse(skill.has_proposal)
        self.assertFalse(skill.proposal_author_id)
        versions = skill.version_ids.sorted("version")
        self.assertEqual([v.version for v in versions], [old_version, old_version + 1])
        self.assertEqual(versions[-1].body, "# Нова\nкоротше")
        self.assertEqual(versions[-1].note, "Занадто довго")
        self.assertEqual(versions[-1].author_id, proposer)
        with self.assertRaises(UserError):
            skill.with_user(self.owner).action_approve_proposal()

    def test_propose_reject(self):
        skill = self.Skill.search([("code", "=", "safety-gates")])
        old_body, old_version = skill.body, skill.version
        self.Skill.with_user(self._user("manager")).td_claude_propose("safety-gates", "інше", "")
        skill.with_user(self.owner).action_reject_proposal()
        self.assertEqual((skill.body, skill.version, skill.has_proposal), (old_body, old_version, False))
        self.assertEqual(len(skill.version_ids), 1)

    def test_only_methodologist_and_manager_propose(self):
        for code in ("coder", "tester", "architect"):
            with self.assertRaises(AccessError):
                self.Skill.with_user(self._user(code)).td_claude_propose("timesheet", "x", "y")
            with self.assertRaises(AccessError):
                self.Skill.with_user(self._user(code)).td_claude_propose_new("a-b", "A", "corporate", [], "d", "b")
        with self.assertRaises(UserError):
            self.Skill.with_user(self._user("manager")).td_claude_propose("no-such", "x", "y")
        with self.assertRaises(UserError):
            self.Skill.with_user(self._user("manager")).td_claude_propose("timesheet", "  ", "y")

    def test_propose_new_skill(self):
        agent = self._user("methodologist")
        skill_id = self.Skill.with_user(agent).td_claude_propose_new(
            "retro-notes", "Нотатки ретро", "role", ["coder", "tester"], "Після закриття задач.", "# Ретро", "Щоб було"
        )
        skill = self.Skill.browse(skill_id)
        self.assertEqual((skill.state, skill.version, skill.scope), ("proposed", 0, "role"))
        self.assertEqual(skill.role_ids.mapped("code"), ["coder", "tester"])
        # до затвердження в брифі й td_claude_read її немає
        coder_brief = self.env["td.claude.agent"].with_user(self._user("coder")).td_claude_brief()
        self.assertNotIn("retro-notes", [s["code"] for s in coder_brief["skills"]])
        self.assertFalse(self.Skill.with_user(self._user("coder")).td_claude_read(["retro-notes"]))
        with self.assertRaises(UserError):
            self.Skill.with_user(agent).td_claude_propose_new("retro-notes", "X", "corporate", [], "d", "b")
        with self.assertRaises(UserError):
            self.Skill.with_user(agent).td_claude_propose_new("zzz", "X", "role", ["nope"], "d", "b")
        skill.with_user(self.owner).action_approve_proposal()
        self.assertEqual((skill.state, skill.version, len(skill.version_ids)), ("active", 1, 1))
        coder_brief = self.env["td.claude.agent"].with_user(self._user("coder")).td_claude_brief()
        self.assertIn("retro-notes", [s["code"] for s in coder_brief["skills"]])
        architect_brief = self.env["td.claude.agent"].with_user(self._user("architect")).td_claude_brief()
        self.assertNotIn("retro-notes", [s["code"] for s in architect_brief["skills"]])
        # відхилення нової пропозиції архівує скіл
        other_id = self.Skill.with_user(agent).td_claude_propose_new("tmp-skill", "T", "corporate", [], "d", "b")
        self.Skill.browse(other_id).with_user(self.owner).action_reject_proposal()
        self.assertEqual(self.Skill.browse(other_id).state, "archived")

    # ------------------------------------------------------------------
    # Запуски за стадією
    # ------------------------------------------------------------------
    def test_stage_change_launches_mapped_role(self):
        self._move(self.owner, "an")
        req = self._requests("architect", "stage")
        self.assertEqual(len(req), 1)
        self.assertEqual(self._requests().filtered(lambda r: r != req).mapped("kind"), [])
        payload = json.loads(req.payload)
        self.assertEqual(payload["kind"], "stage")
        self.assertEqual(payload["role"], {"code": "architect", "name": "Архітектор"})
        self.assertEqual(payload["hops_today"], 1)
        self.assertEqual(payload["res_id"], self.task.id)
        self.assertEqual(payload["agent"]["user_id"], self._user("architect").id)
        # чужа команда не запускається
        self.assertFalse(self._requests(team=self.other_team))
        # та сама стадія ще раз (без зміни) нічого не створює
        self.task.with_user(self.owner).write({"stage_id": self.stages["an"].id})
        self.assertEqual(len(self._requests("architect")), 1)

    def test_stage_without_role_does_nothing(self):
        self.stages["an"].td_claude_role_id = False
        self._move(self.owner, "an")
        self.assertFalse(self._requests())
        self.stages["an"].td_claude_role_id = self.roles["architect"]

    def test_handoff_within_same_owner(self):
        self._move(self._user("architect"), "dv")
        self.assertEqual(len(self._requests("coder", "stage")), 1)
        self.assertFalse(self._requests(team=self.other_team))
        # колега з іншого контуру (власник other) переносить задачу: запускаються лише агенти other
        self._flush_requests()
        self._move(self.other, "qa")
        self.assertEqual(len(self._requests("tester", team=self.other_team)), 1)
        self.assertEqual(len(self._requests("tester")), 0)
        # агент чужого власника не запускає агентів цього власника
        self._move(self._user("manager", self.other_team), "an")
        self.assertEqual(len(self._requests("architect")), 0)
        self.assertEqual(len(self._requests("architect", team=self.other_team)), 1)

    def test_agent_does_not_trigger_itself(self):
        self._move(self._user("coder"), "dv")
        self.assertFalse(self._requests("coder"))
        self.assertFalse(self._requests("coder", team=self.other_team))
        # згадка себе
        coder = self._user("coder")
        self.task.with_user(coder).message_post(
            body="себе", message_type="comment", subtype_xmlid="mail.mt_comment", partner_ids=coder.partner_id.ids
        )
        self.assertFalse(self._requests("coder"))
        # призначення агентом самого себе
        self.task.with_user(coder).write({"user_ids": [(4, coder.id)]})
        self.assertFalse(self._requests("coder"))

    def test_agent_mention_of_colleague(self):
        architect, coder = self._user("architect"), self._user("coder")
        self.task.with_user(architect).message_post(
            body="передаю", message_type="comment", subtype_xmlid="mail.mt_comment", partner_ids=coder.partner_id.ids
        )
        self.assertEqual(len(self._requests("coder", "mention")), 1)
        # колега чужого контуру не запускається
        other_coder = self._user("coder", self.other_team)
        self.task.with_user(architect).message_post(
            body="чужому",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=other_coder.partner_id.ids,
        )
        self.assertFalse(self._requests(team=self.other_team))

    def test_assignment_by_agent_colleague(self):
        coder = self._user("coder")
        self.task.with_user(self._user("manager")).write({"user_ids": [(4, coder.id)]})
        self.assertEqual(len(self._requests("coder", "assign")), 1)

    def test_hop_limit(self):
        self.env["ir.config_parameter"].sudo().set_param("td.claude.max_hops_per_day", "2")
        self._move(self.owner, "an")
        self._move(self.owner, "dv")
        self.assertEqual(len(self._requests()), 2)
        self.assertEqual(self.task.td_claude_hops_today, 2)
        self._move(self.owner, "qa")
        self.assertFalse(self._requests("tester"))
        notes = self.task.message_ids.filtered(lambda m: "ліміт запусків" in (m.body or ""))
        self.assertEqual(len(notes), 1)
        # згадка власника не обмежується
        self.task.with_user(self.owner).message_post(
            body="терміново",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=self._user("manager").partner_id.ids,
        )
        self.assertEqual(len(self._requests("manager", "mention")), 1)
        # за замовчуванням — 6
        self.env["ir.config_parameter"].sudo().search([("key", "=", "td.claude.max_hops_per_day")]).unlink()
        self.assertEqual(self.env["td.claude.request"]._td_max_hops(), 6)

    def test_pause_flag(self):
        self.task.td_claude_paused = True
        self._move(self.owner, "an")
        self.task.with_user(self.owner).write({"user_ids": [(4, self._user("coder").id)]})
        self.assertFalse(self._requests())
        # згадка власника працює і на паузі
        self.task.with_user(self.owner).message_post(
            body="ти тут?",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=self._user("architect").partner_id.ids,
        )
        self.assertEqual(len(self._requests("architect", "mention")), 1)
        self.task.td_claude_paused = False
        self._move(self.owner, "dv")
        self.assertEqual(len(self._requests("coder", "stage")), 1)

    def test_dedup_60s(self):
        self._move(self.owner, "an")
        self._move(self.owner, "pm")
        self._move(self.owner, "an")
        self.assertEqual(len(self._requests("architect", "stage")), 1)
        self.assertEqual(len(self._requests("manager", "stage")), 1)
        # мінуло більше 60 с: новий запит дозволено
        self._flush_requests()
        self._move(self.owner, "pm")
        self._move(self.owner, "an")
        self.assertEqual(len(self._requests("architect", "stage")), 2)
        # згадки не склеюються
        architect = self._user("architect")
        for _i in range(2):
            self.task.with_user(self.owner).message_post(
                body="ще", message_type="comment", subtype_xmlid="mail.mt_comment", partner_ids=architect.partner_id.ids
            )
        self.assertEqual(len(self._requests("architect", "mention")), 2)

    def test_task_fields(self):
        self.assertFalse(self.task.td_claude_paused)
        self.assertEqual(self.task.td_claude_hops_today, 0)
        self.assertEqual(self.env["project.task"].new({}).td_claude_hops_today, 0)

    # ------------------------------------------------------------------
    # Табель
    # ------------------------------------------------------------------
    def _log(self, hours, description=GOOD, minutes=0, code="coder"):
        task = self.task.with_user(self._user(code))
        return self.env["account.analytic.line"].sudo().browse(task.td_claude_log_time(hours, description, minutes))

    def test_log_time_line_fields(self):
        self.task.with_user(self.owner).write({"user_ids": [(4, self._user("coder").id)]})
        request = self._requests("coder", "assign")
        user = self._user("coder")
        user.tz = "Pacific/Auckland"
        line = self._log(1.1, minutes=37)
        self.assertEqual(line.unit_amount, 1.25)
        self.assertEqual(line.name, GOOD)
        self.assertTrue(line.td_claude_is_ai)
        self.assertEqual(line.td_claude_actual_minutes, 37)
        self.assertEqual(line.td_claude_request_id, request)
        self.assertEqual(line.task_id, self.task)
        self.assertEqual(line.project_id, self.project)
        self.assertEqual(line.employee_id.user_id, user)
        self.assertEqual(line.date, fields.Date.context_today(self.task.with_context(tz="Pacific/Auckland")))
        self.assertTrue(user.has_group("hr_timesheet.group_hr_timesheet_user"))
        # звичайний рядок людини не позначається
        human = self.env["account.analytic.line"].sudo().search([("td_claude_is_ai", "=", False)], limit=1)
        self.assertFalse(human.td_claude_request_id)

    def test_log_time_rounding_and_limits(self):
        for given, expected in ((0.01, 0.25), (0.25, 0.25), (0.26, 0.5), (1, 1), (1.01, 1.25), (7.9, 8), (8, 8)):
            self.assertEqual(self._log(given).unit_amount, expected, given)
        for bad in (0, -1, 8.01, 9, "abc", None):
            with self.assertRaises(UserError, msg=str(bad)):
                self._log(bad)
        with self.assertRaises(UserError):
            self._log(1, minutes=-5)
        with self.assertRaises(UserError):
            self._log(1, minutes="x")

    def test_log_time_description_validation(self):
        for bad in (
            "/",
            "-",
            ".",
            "",
            "   ",
            "Розробка",
            "тестування",
            "Аналіз.",
            "Зустріч",
            "коротко зроблено",  # < 20 символів
            "теуствання",
            "/" * 25,
            "1234567890 1234567890",
            "а" * 251,
        ):
            with self.assertRaises(UserError, msg=bad) as cm:
                self._log(1, bad)
            self.assertIn("Стандарт опису табеля", str(cm.exception.args[0]), bad)
        # межі довжини
        self.assertTrue(self._log(1, "Виправлено помилку #12" + "а" * 0))
        self.assertTrue(self._log(1, ("Додано тест AC-01 " * 20)[:250]))
        # нормалізація пробілів
        line = self._log(1, "  Виправлено   баг   у   compute_pickings  ")
        self.assertEqual(line.name, "Виправлено баг у compute_pickings")

    def test_log_time_requires_timesheets_and_employee(self):
        self.project.allow_timesheets = False
        with self.assertRaises(UserError):
            self._log(1)
        self.project.allow_timesheets = True
        self.env["hr.employee"].sudo().search([("user_id", "=", self._user("coder").id)]).write({"user_id": False})
        with self.assertRaises(UserError):
            self._log(1)

    def test_log_time_all_roles(self):
        for code in ROLE_CODES:
            self.assertEqual(self._log(0.5, code=code).employee_id.user_id, self._user(code))
