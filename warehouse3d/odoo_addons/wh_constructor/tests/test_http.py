from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import HttpCase, tagged

from .common import G_DESIGN, G_VIEW, make_user, project_data

INDEX = '<!doctype html><html><head><meta charset="utf-8"><title>WH</title></head><body><div id="app"></div></body></html>'
READ_INDEX = "odoo.addons.wh_constructor.controllers.main._read_index"
API = "/wh_constructor/api"


@tagged("post_install", "-at_install")
class TestWhConstructorHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = make_user(cls.env, "wh_http_designer", G_DESIGN)
        cls.viewer = make_user(cls.env, "wh_http_viewer", G_VIEW)
        cls.plain = make_user(cls.env, "wh_http_plain")

    def login(self, user):
        self.authenticate(user.login, f"{user.login}-pass-1")

    def rpc(self, route, **params):
        return self.make_jsonrpc_request(API + route, params)

    # ------------------------------------------------------------ приложение
    def test_app_route(self):
        self.login(self.viewer)
        with patch(READ_INDEX, return_value=INDEX):
            res = self.url_open("/wh_constructor/app")
        self.assertEqual(res.status_code, 200)
        self.assertIn('<base href="/wh_constructor/static/app/">', res.text)
        self.assertIn("window.__WH_ODOO__", res.text)
        self.assertIn('<div id="app">', res.text)
        self.assertLess(res.text.index("<base"), res.text.index("<meta charset"))

    def test_app_route_without_build(self):
        self.login(self.viewer)
        with patch(READ_INDEX, return_value=None):
            res = self.url_open("/wh_constructor/app")
        self.assertEqual(res.status_code, 404)
        self.assertIn("npm run build:odoo", res.text)

    def test_app_route_needs_group_and_login(self):
        with patch(READ_INDEX, return_value=INDEX):
            res = self.url_open("/wh_constructor/app", allow_redirects=False)
            self.assertIn(res.status_code, (302, 303))
            self.assertIn("/web/login", res.headers["Location"])
            self.login(self.plain)
            self.assertEqual(self.url_open("/wh_constructor/app").status_code, 403)

    # ------------------------------------------------------------ JSON
    def test_me(self):
        self.login(self.designer)
        me = self.rpc("/me")
        self.assertEqual((me["uid"], me["rights"]), (self.designer.id, {"view": True, "design": True, "apply": False}))
        self.login(self.viewer)
        self.assertEqual(self.rpc("/me")["rights"], {"view": True, "design": False, "apply": False})
        self.login(self.plain)
        self.assertEqual(self.rpc("/me")["rights"], {"view": False, "design": False, "apply": False})

    def test_projects_cycle(self):
        self.login(self.designer)
        self.assertEqual(self.rpc("/projects"), {"status": "ok", "projects": []})
        saved = self.rpc("/project/save", key="p-1", data=project_data(marks=1), base_rev=None, comment="перше")
        self.assertEqual((saved["status"], saved["rev"]), ("ok", 1))
        listed = self.rpc("/projects")["projects"]
        self.assertEqual([(p["id"], p["name"], p["rev"]) for p in listed], [("p-1", "Тестовий склад", 1)])
        loaded = self.rpc("/project/load", key="p-1")
        self.assertEqual((loaded["found"], loaded["rev"], loaded["data"]["id"]), (True, 1, "p-1"))
        self.assertFalse(self.rpc("/project/load", key="нема")["found"])
        # устаревшее сохранение
        ok = self.rpc("/project/save", key="p-1", data=project_data(marks=2), base_rev=1)
        self.assertEqual(ok["rev"], 2)
        stale = self.rpc("/project/save", key="p-1", data=project_data(marks=3), base_rev=1)
        self.assertEqual((stale["status"], stale["rev"]), ("stale", 2))
        # версии и восстановление
        versions = self.rpc("/project/versions", key="p-1")["versions"]
        self.assertEqual([v["rev"] for v in versions], [2, 1])
        self.assertEqual(versions[1]["comment"], "перше")
        back = self.rpc("/project/restore", key="p-1", version_id=versions[1]["id"], base_rev=2)
        self.assertEqual((back["status"], back["rev"], back["data"]["warehouses"][0]["saved"]), ("ok", 3, {"marks": 1}))
        self.assertEqual(self.rpc("/project/delete", key="p-1")["deleted"], True)
        self.assertEqual(self.rpc("/projects")["projects"], [])

    def test_viewer_cannot_write(self):
        self.login(self.designer)
        self.rpc("/project/save", key="p-1", data=project_data(), base_rev=None)
        self.login(self.viewer)
        self.assertEqual(len(self.rpc("/projects")["projects"]), 1)
        self.assertEqual(self.rpc("/project/load", key="p-1")["found"], True)
        self.assertEqual(self.rpc("/project/save", key="p-1", data=project_data(marks=5), base_rev=1)["status"], "denied")
        self.assertEqual(self.rpc("/project/delete", key="p-1")["status"], "denied")
        self.assertEqual(self.rpc("/lock/acquire", key="p-1", warehouse="wh-1", zone="Z1")["status"], "denied")
        self.login(self.plain)
        self.assertEqual(self.rpc("/projects")["status"], "denied")

    def test_locks(self):
        self.login(self.designer)
        self.rpc("/project/save", key="p-1", data=project_data(), base_rev=None)
        got = self.rpc("/lock/acquire", key="p-1", warehouse="wh-1", zone="Z1", warehouse_code="WH")
        self.assertTrue(got["ok"] and got["mine"])
        self.assertEqual([lk["zone"] for lk in self.rpc("/lock/list", key="p-1")["locks"]], ["Z1"])
        # зона, занятая другим пользователем: ответ с именем и сроком
        other = make_user(self.env, "wh_http_other", G_DESIGN)
        lock = self.env["wh.zone.lock"].search([("zone_key", "=", "Z1")])
        lock.write({"user_id": other.id, "expires": fields.Datetime.now() + timedelta(minutes=5)})
        busy = self.rpc("/lock/acquire", key="p-1", warehouse="wh-1", zone="Z1")
        self.assertFalse(busy["ok"])
        self.assertEqual((busy["owner"], busy["mine"]), (other.name, False))
        self.assertTrue(busy["expires"])
        self.assertEqual(self.rpc("/lock/release", key="p-1", warehouse="wh-1", zone="Z1")["released"], 0)  # чужую не снять
        lock.expires = fields.Datetime.now() - timedelta(seconds=1)
        self.assertTrue(self.rpc("/lock/acquire", key="p-1", warehouse="wh-1", zone="Z1")["ok"])
        self.assertEqual(self.rpc("/lock/release", key="p-1")["released"], 1)
