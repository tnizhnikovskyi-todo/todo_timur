import json

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

CLAUDE_URL = "https://claude.ai/project/abc-123"


@tagged("post_install", "-at_install", "f3d", "f3d_claude", "f3d_claude_project")
class TestClaudeProject(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        groups = cls.env.ref("base.group_user") | cls.env.ref("project.group_project_user")
        cls.owner = Users.create({"name": "Owner P", "login": "owner.p", "group_ids": [(6, 0, groups.ids)]})
        cls.member = Users.create({"name": "Member P", "login": "member.p", "group_ids": [(6, 0, groups.ids)]})
        cls.outsider = Users.create({"name": "Outsider P", "login": "outsider.p", "group_ids": [(6, 0, groups.ids)]})
        cls.portal = Users.create(
            {"name": "Portal P", "login": "portal.p", "group_ids": [(6, 0, cls.env.ref("base.group_portal").ids)]}
        )
        cls.env["ir.config_parameter"].sudo().set_param("web.base.url", "https://erp.example.com")
        cls.Skill = cls.env["td.claude.skill"]
        cls.project = cls.env["project.project"].create(
            {"name": "Проєкт P", "td_claude_repo": "todo-ltd/factory3d", "td_claude_branch": "feature/x"}
        )
        cls.corp = cls.Skill.create({"name": "Корп P", "code": "corp-p", "scope": "corporate", "body": "x"})
        cls.role_skill = cls.Skill.create(
            {
                "name": "Роль P",
                "code": "role-p",
                "scope": "role",
                "body": "x",
                "role_ids": [Command.set(cls.env["td.claude.role"].search([("code", "=", "coder")]).ids)],
            }
        )
        cls.pskill = cls.Skill.create(
            {"name": "Проєктний P", "code": "proj-p", "scope": "project", "body": "x", "description": "Для P"}
        )
        cls.other_pskill = cls.Skill.create({"name": "Чужий P", "code": "proj-other", "scope": "project", "body": "x"})
        cls.project.td_claude_skill_ids = cls.pskill
        coder = cls.env["td.claude.role"].search([("code", "=", "coder")])
        cls.agent = cls.env["td.claude.agent"]._td_create_agent(cls.owner, coder)

    def _wizard(self, user, project=None):
        project = project or self.project
        action = project.with_user(user).action_td_claude_project_wizard()
        return self.env[action["res_model"]].with_user(user).with_context(**action["context"]).create({})

    def test_skill_relation_both_ways(self):
        self.assertEqual(self.pskill.project_ids, self.project)
        self.assertFalse(self.other_pskill.project_ids)
        self.other_pskill.project_ids = self.project
        self.assertIn(self.other_pskill, self.project.td_claude_skill_ids)

    def test_repo_validation(self):
        for bad in ("factory3d", "a/b/c", "owner/ repo", "/repo"):
            with self.subTest(bad), mute_logger("odoo.sql_db"), self.assertRaises(ValidationError):
                self.project.td_claude_repo = bad
        self.project.td_claude_repo = "Todo-ltd/factory3d.v2"
        self.project.td_claude_repo = False
        self.project.td_claude_branch = "feature/любе значення"

    def test_wizard_generates_text_for_internal_user(self):
        wizard = self._wizard(self.member)
        text = wizard.instruction
        self.assertIn("Проєкт P", text)
        self.assertIn(f"id {self.project.id}", text)
        self.assertIn(self.env.cr.dbname, text)
        self.assertIn("https://erp.example.com", text)
        needles = (
            "odoo-mcp",
            "td_claude_project_brief",
            "td_claude_context",
            "td_claude_append_context",
            "українською",
        )
        for needle in needles:
            self.assertIn(needle, text)
        self.assertLessEqual(len(text.splitlines()), 40)

    def test_wizard_saves_url(self):
        wizard = self._wizard(self.member)
        self.assertFalse(wizard.claude_url)
        wizard.claude_url = CLAUDE_URL
        wizard.action_save_url()
        self.assertEqual(self.project.td_claude_project_url, CLAUDE_URL)
        self.assertEqual(self._wizard(self.member).claude_url, CLAUDE_URL)

    def test_wizard_url_must_be_http(self):
        wizard = self._wizard(self.member)
        wizard.claude_url = "javascript:alert(1)"
        with self.assertRaises(Exception):  # noqa: B017
            wizard.action_save_url()

    def test_project_brief(self):
        self.project.td_claude_project_url = CLAUDE_URL
        self.project.td_claude_context = "<p>Контекст P</p>"
        brief = self.project.with_user(self.member).td_claude_project_brief()
        self.assertEqual(
            brief["project"],
            {
                "id": self.project.id,
                "name": "Проєкт P",
                "repo": "todo-ltd/factory3d",
                "branch": "feature/x",
                "claude_url": CLAUDE_URL,
                "context_text": "Контекст P",
            },
        )
        codes = {s["code"] for s in brief["skills"]}
        self.assertIn("corp-p", codes)
        self.assertIn("proj-p", codes)
        self.assertNotIn("role-p", codes)
        self.assertNotIn("proj-other", codes)
        proj = next(s for s in brief["skills"] if s["code"] == "proj-p")
        self.assertEqual(proj["description"], "Для P")
        self.assertNotIn("body", proj)

    def test_project_brief_skips_archived_skill_and_portal(self):
        self.pskill.state = "archived"
        brief = self.project.with_user(self.owner).td_claude_project_brief()
        self.assertNotIn("proj-p", {s["code"] for s in brief["skills"]})
        with self.assertRaises(AccessError):
            self.project.with_user(self.portal).td_claude_project_brief()

    def test_project_brief_for_agent(self):
        brief = self.project.with_user(self.agent.agent_user_id).td_claude_project_brief()
        self.assertEqual(brief["project"]["repo"], "todo-ltd/factory3d")

    def test_agent_brief_with_project(self):
        agent_env = self.env["td.claude.agent"].with_user(self.agent.agent_user_id)
        plain = agent_env.td_claude_brief()
        self.assertNotIn("project", plain)
        self.assertNotIn("proj-p", {s["code"] for s in plain["skills"]})
        brief = agent_env.td_claude_brief(project_id=self.project.id)
        codes = [s["code"] for s in brief["skills"]]
        self.assertIn("proj-p", codes)
        self.assertIn("role-p", codes)
        self.assertIn("corp-p", codes)
        self.assertNotIn("proj-other", codes)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(brief["project"]["id"], self.project.id)
        self.assertEqual(brief["project"]["branch"], "feature/x")
        self.assertEqual(brief["role"]["code"], "coder")

    def test_payload_project_fields(self):
        self.project.td_claude_project_url = CLAUDE_URL
        task = self.env["project.task"].create({"name": "Задача P", "project_id": self.project.id})
        request = self.env["td.claude.request"]._td_create(self.agent, "assign", record=task, schedule=False)
        project = json.loads(request.payload)["project"]
        self.assertEqual(
            project,
            {
                "id": self.project.id,
                "name": "Проєкт P",
                "repo": "todo-ltd/factory3d",
                "branch": "feature/x",
                "claude_url": CLAUDE_URL,
            },
        )

    def test_append_context_human_member(self):
        self.project.with_user(self.member).td_claude_append_context("Рішення від людини")
        self.assertIn("Рішення від людини", self.project.td_claude_context)
        self.project.with_user(self.agent.agent_user_id).td_claude_append_context("Рішення агента")
        self.assertIn("Рішення агента", self.project.td_claude_context)

    def test_append_context_denied(self):
        private = self.env["project.project"].create({"name": "Закритий P", "privacy_visibility": "followers"})
        private.message_follower_ids.sudo().unlink()
        private.message_subscribe(partner_ids=self.member.partner_id.ids)
        private.with_user(self.member).td_claude_append_context("ок")
        with self.assertRaises(AccessError):
            private.with_user(self.outsider).td_claude_append_context("не можна")
        with self.assertRaises(AccessError):
            self.project.with_user(self.portal).td_claude_append_context("не можна")
        self.assertNotIn("не можна", (private.td_claude_context or "") + (self.project.td_claude_context or ""))
