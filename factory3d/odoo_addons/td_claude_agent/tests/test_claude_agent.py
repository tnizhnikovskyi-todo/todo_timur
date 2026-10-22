import json
import requests
from unittest.mock import MagicMock, patch

from markupsafe import Markup
from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

POST = "odoo.addons.td_claude_agent.models.td_claude_agent.requests.post"
FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/trig_test/fire"


def fake_response(status=200, body=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = json.dumps(body) if body is not None else ""
    return resp


@tagged("post_install", "-at_install", "f3d", "f3d_claude")
class TestClaudeAgent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref("base.group_user")
        group_project = cls.env.ref("project.group_project_user")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.owner = Users.create(
            {"name": "Owner One", "login": "owner.one", "group_ids": [(6, 0, (group_user | group_project).ids)]}
        )
        cls.other = Users.create(
            {"name": "Other Two", "login": "other.two", "group_ids": [(6, 0, (group_user | group_project).ids)]}
        )
        cls.agent_user = Users.create(
            {
                "name": "Claude · Owner One",
                "login": "claude.owner.one",
                "group_ids": [(6, 0, (group_user | group_project).ids)],
            }
        )
        cls.agent = cls.env["td.claude.agent"].create(
            {
                "owner_id": cls.owner.id,
                "agent_user_id": cls.agent_user.id,
                "fire_url": FIRE_URL,
                "fire_token": "sk-secret-token",
            }
        )
        cls.project = cls.env["project.project"].create({"name": "Проєкт A"})
        cls.task = cls.env["project.task"].create({"name": "Задача 1", "project_id": cls.project.id})
        cls.env["ir.config_parameter"].sudo().set_param("web.base.url", "https://erp.example.com")

    def _requests(self, kind=None):
        domain = [("agent_id", "=", self.agent.id)]
        if kind:
            domain.append(("kind", "=", kind))
        return self.env["td.claude.request"].sudo().search(domain)

    def _post(self, user, body=None, partners=None):
        body = body or Markup("<p>Привіт, <b>Claude</b></p>")
        partners = self.agent_user.partner_id if partners is None else partners
        return self.task.with_user(user).message_post(
            body=body, message_type="comment", subtype_xmlid="mail.mt_comment", partner_ids=partners.ids
        )

    # ------------------------------------------------------------------
    # Тригер: чатер
    # ------------------------------------------------------------------
    def test_owner_mention_creates_request_with_payload(self):
        message = self._post(self.owner)
        request = self._requests("mention")
        self.assertEqual(len(request), 1)
        self.assertEqual(request.state, "pending")
        self.assertEqual(request.message_id, message)
        self.assertEqual(request.res_model, "project.task")
        self.assertEqual(request.res_id, self.task.id)
        payload = json.loads(request.payload)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["kind"], "mention")
        self.assertEqual(payload["request_id"], request.id)
        self.assertEqual(payload["db"], self.env.cr.dbname)
        self.assertEqual(payload["base_url"], "https://erp.example.com")
        self.assertEqual(payload["model"], "project.task")
        self.assertEqual(payload["res_id"], self.task.id)
        self.assertEqual(payload["record_name"], "Задача 1")
        self.assertEqual(payload["record_url"], f"https://erp.example.com/odoo/project.task/{self.task.id}")
        self.assertEqual(payload["project"], {"id": self.project.id, "name": "Проєкт A"})
        self.assertEqual(payload["author"], {"user_id": self.owner.id, "name": "Owner One"})
        self.assertEqual(
            payload["agent"],
            {"user_id": self.agent_user.id, "login": "claude.owner.one", "partner_id": self.agent_user.partner_id.id},
        )
        self.assertEqual(payload["message"]["id"], message.id)
        self.assertEqual(payload["message"]["text"], "Привіт, *Claude*")
        self.assertTrue(payload["message"]["date"])
        self.assertIsNone(payload["session"])

    def test_non_owner_mention_does_nothing(self):
        self._post(self.other)
        self.assertFalse(self._requests())

    def test_agent_own_message_does_nothing(self):
        self._post(self.agent_user, partners=self.agent_user.partner_id)
        self.assertFalse(self._requests())

    def test_mention_without_agent_partner_does_nothing(self):
        self._post(self.owner, partners=self.other.partner_id)
        self._post(self.owner, partners=self.env["res.partner"])
        self.assertFalse(self._requests())

    def test_note_and_inactive_agent(self):
        self.task.with_user(self.owner).message_post(
            body="x", message_type="notification", partner_ids=self.agent_user.partner_id.ids
        )
        self.assertFalse(self._requests())
        self.agent.active = False
        self._post(self.owner)
        self.assertFalse(self._requests())

    def test_payload_contains_existing_session(self):
        self.env["td.claude.session"].create(
            {
                "agent_id": self.agent.id,
                "res_model": "project.task",
                "res_id": self.task.id,
                "record_name": "Задача 1",
                "session_id": "session_abc",
                "session_url": "https://claude.ai/code/session_abc",
            }
        )
        self._post(self.owner)
        payload = json.loads(self._requests("mention").payload)
        self.assertEqual(
            payload["session"], {"session_id": "session_abc", "session_url": "https://claude.ai/code/session_abc"}
        )

    # ------------------------------------------------------------------
    # Тригер: призначення
    # ------------------------------------------------------------------
    def test_task_assignment_fires(self):
        task = self.env["project.task"].with_user(self.owner).create({"name": "Нова", "project_id": self.project.id})
        self.assertFalse(self._requests("assign"))
        task.write({"user_ids": [(4, self.agent_user.id)]})
        request = self._requests("assign")
        self.assertEqual(len(request), 1)
        payload = json.loads(request.payload)
        self.assertEqual(payload["kind"], "assign")
        self.assertIsNone(payload["message"])
        self.assertEqual(payload["res_id"], task.id)
        # повторне збереження без зміни виконавців не дублює запит
        task.write({"user_ids": [(4, self.agent_user.id)], "name": "Нова 2"})
        self.assertEqual(len(self._requests("assign")), 1)

    def test_task_creation_with_agent_and_foreign_assignment(self):
        self.env["project.task"].with_user(self.owner).create(
            {"name": "З агентом", "project_id": self.project.id, "user_ids": [(6, 0, [self.agent_user.id])]}
        )
        self.assertEqual(len(self._requests("assign")), 1)
        # чужий користувач призначає агента власника: запиту немає
        self.task.with_user(self.other).write({"user_ids": [(4, self.agent_user.id)]})
        self.assertEqual(len(self._requests("assign")), 1)

    # ------------------------------------------------------------------
    # Відправка
    # ------------------------------------------------------------------
    def test_send_now_success(self):
        self._post(self.owner)
        request = self._requests("mention")
        body = {"claude_code_session_id": "session_1", "claude_code_session_url": "https://claude.ai/code/session_1"}
        with patch(POST, return_value=fake_response(200, body)) as post:
            request._send_now()
        self.assertEqual(request.state, "sent")
        self.assertEqual(request.http_status, 200)
        self.assertEqual(request.session_url, "https://claude.ai/code/session_1")
        self.assertTrue(self.agent.last_fire_at)
        args, kwargs = post.call_args
        self.assertEqual(args[0], FIRE_URL)
        self.assertEqual(kwargs["timeout"], 15)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-secret-token")
        self.assertEqual(kwargs["headers"]["anthropic-beta"], "experimental-cc-routine-2026-04-01")
        self.assertEqual(kwargs["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(json.loads(kwargs["json"]["text"])["request_id"], request.id)

    def test_send_now_failure_and_retry(self):
        self.env["ir.config_parameter"].sudo().set_param("td_claude_agent.beta_header", "beta-x")
        self._post(self.owner)
        request = self._requests("mention")
        with patch(POST, return_value=fake_response(500, None)) as post:
            request._send_now()
        self.assertEqual(request.state, "failed")
        self.assertEqual(request.http_status, 500)
        self.assertEqual(post.call_args.kwargs["headers"]["anthropic-beta"], "beta-x")
        with patch(POST, side_effect=requests.ConnectionError("boom")):
            request._send_now()
        self.assertEqual((request.state, request.http_status), ("failed", 0))
        self.assertNotIn("sk-secret-token", request.response or "")
        with patch(POST, return_value=fake_response(200, {})):
            request.with_user(self.owner).action_retry()
        self.assertEqual((request.state, request.http_status), ("sent", 200))

    def test_postcommit_scheduled(self):
        self._post(self.owner)
        self.assertEqual(self._requests("mention").state, "pending")

    def test_ping_button(self):
        with patch(POST, return_value=fake_response(200, {})) as post:
            action = self.agent.with_user(self.owner).action_ping()
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(json.loads(post.call_args.kwargs["json"]["text"])["kind"], "ping")
        self.assertEqual(self._requests("ping").state, "sent")

    @mute_logger("odoo.sql_db")
    def test_fire_url_must_be_https(self):
        with self.assertRaises(ValidationError):
            self.agent.fire_url = "http://example.com/x"

    # ------------------------------------------------------------------
    # Доступ
    # ------------------------------------------------------------------
    def test_token_access(self):
        self.assertEqual(self.agent.with_user(self.owner).fire_token, "sk-secret-token")
        with self.assertRaises(AccessError):
            self.agent.with_user(self.other).read(["fire_token"])
        with self.assertRaises(AccessError):
            self.agent.with_user(self.agent_user).read(["fire_token"])
        self.assertFalse(self.env["td.claude.agent"].with_user(self.other).search([]))

    def test_request_and_session_visibility(self):
        self._post(self.owner)
        session = self.env["td.claude.session"].create(
            {"agent_id": self.agent.id, "res_model": "project.task", "res_id": self.task.id}
        )
        Request = self.env["td.claude.request"]
        self.assertEqual(len(Request.with_user(self.owner).search([])), 1)
        self.assertEqual(len(Request.with_user(self.agent_user).search([])), 1)
        self.assertFalse(Request.with_user(self.other).search([]))
        self.assertFalse(self.env["td.claude.session"].with_user(self.other).search([]))
        # агент пише посилання на сесію через ORM/XML-RPC
        session.with_user(self.agent_user).write(
            {"session_id": "session_x", "session_url": "https://claude.ai/code/session_x"}
        )
        self.assertEqual(session.session_id, "session_x")
        with self.assertRaises(AccessError):
            session.with_user(self.other).write({"session_id": "hack"})

    def test_task_session_url_for_owner(self):
        self.env["td.claude.session"].create(
            {
                "agent_id": self.agent.id,
                "res_model": "project.task",
                "res_id": self.task.id,
                "session_url": "https://claude.ai/code/session_x",
            }
        )
        self.assertEqual(self.task.with_user(self.owner).td_claude_session_url, "https://claude.ai/code/session_x")
        self.assertFalse(self.task.with_user(self.other).td_claude_session_url)
        action = self.task.with_user(self.owner).action_td_open_claude_session()
        self.assertEqual(action["type"], "ir.actions.act_url")

    @mute_logger("odoo.sql_db")
    def test_session_unique(self):
        vals = {"agent_id": self.agent.id, "res_model": "project.task", "res_id": self.task.id}
        self.env["td.claude.session"].create(vals)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["td.claude.session"].create(vals)

    # ------------------------------------------------------------------
    # Створення агента
    # ------------------------------------------------------------------
    def test_create_my_agent(self):
        dept = self.env["hr.department"].create({"name": "Відділ"})
        owner_emp = self.env["hr.employee"].create(
            {"name": "Other Two", "user_id": self.other.id, "department_id": dept.id}
        )
        action = self.env["td.claude.agent"].with_user(self.other).action_create_my_agent()
        self.assertEqual(action["res_model"], "td.claude.agent.wizard")
        ctx = action["context"]
        agent = self.env["td.claude.agent"].sudo().browse(ctx["default_agent_id"])
        self.assertEqual(agent.owner_id, self.other)
        user = agent.agent_user_id
        self.assertEqual(user.name, "Claude · Other Two")
        self.assertEqual(user.login, "claude.other.two")
        self.assertFalse(user.share)
        self.assertTrue(user.has_group("project.group_project_user"))
        self.assertFalse(user.has_group("base.group_system"))
        employee = self.env["hr.employee"].sudo().search([("user_id", "=", user.id)])
        self.assertEqual(len(employee), 1)
        self.assertEqual(employee.department_id, dept)
        self.assertEqual(employee.parent_id, owner_emp)
        self.assertEqual(employee.job_title, "AI-агент")
        key = ctx["default_api_key"]
        self.assertTrue(key)
        # ключ справді діє для RPC від імені агента
        uid = self.env["res.users.apikeys"]._check_credentials(scope="rpc", key=key)
        self.assertEqual(uid, user.id)
        # ідемпотентність
        with self.assertRaises(UserError):
            self.env["td.claude.agent"].with_user(self.other).action_create_my_agent()
        self.assertTrue(self.other.with_user(self.other).td_claude_has_agent)

    def test_create_my_agent_login_collision(self):
        self.env["res.users"].with_context(no_reset_password=True).create(
            {"name": "Squat", "login": "claude.other.two"}
        )
        action = self.env["td.claude.agent"].with_user(self.other).action_create_my_agent()
        self.assertEqual(action["context"]["default_agent_login"], "claude.other.two-2")

    def test_create_from_res_users_button(self):
        with self.assertRaises(AccessError):
            self.owner.with_user(self.other).action_td_create_claude_agent()
        self.assertFalse(self.other.td_claude_has_agent)
        self.other.with_user(self.other).action_td_create_claude_agent()
        self.assertTrue(self.other.td_claude_has_agent)
