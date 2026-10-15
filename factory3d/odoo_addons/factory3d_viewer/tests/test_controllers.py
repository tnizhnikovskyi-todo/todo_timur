import re
import unittest

from odoo.tests import HttpCase, JsonRpcException, tagged

from .common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestControllers(HttpCase, F3dViewerBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for user in (cls.user_f3d, cls.user_nobody, cls.user_manager, cls.user_mrp_only):
            user.password = user.login
        cls.wc = cls.env["mrp.workcenter"].create({"name": "ZZ центр", "f3d_code": "ZZ-WC-1"})

    def _get(self, url, user="f3d_user", **kw):
        if user:
            self.authenticate(user, user)
        return self.url_open(url, allow_redirects=False, **kw)

    # --- API-01 ---
    def test_static_etag_304(self):
        """AC-10."""
        res = self._get("/f3d/viewer/static")
        self.assertEqual(res.status_code, 200)
        etag = res.headers["ETag"]
        self.assertIn("max-age=3600", res.headers["Cache-Control"])
        doc = res.json()
        for key in ("passports", "energy", "layout", "path_templates"):
            self.assertIn(key, doc)
        self.assertEqual(doc["meta"]["schema"], "1.1")
        self.assertEqual(len(doc["meta"]["static_etag"]), 16)
        self.assertEqual(etag.strip('"')[:16], doc["meta"]["static_etag"])
        res2 = self.url_open("/f3d/viewer/static", headers={"If-None-Match": etag}, allow_redirects=False)
        self.assertEqual(res2.status_code, 304)

    def test_static_forbidden_and_anonymous(self):
        self.assertEqual(self._get("/f3d/viewer/static", user="f3d_nobody").status_code, 403)
        self.logout()
        res = self.url_open("/f3d/viewer/static", allow_redirects=False)
        self.assertIn(res.status_code, (303, 401))

    # --- API-02 ---
    def test_data(self):
        res = self._get("/f3d/viewer/data")
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/json", res.headers["Content-Type"])
        self.assertEqual(res.headers["Cache-Control"], "no-store")
        meta = res.json()["meta"]
        self.assertEqual((meta["schema"], meta["live"], meta["kiosk"]), ("1.1", True, False))
        self.assertEqual(meta["user"], self.user_f3d.name)
        full = self._get("/f3d/viewer/data?full=1&lite=1").json()
        self.assertTrue(full["meta"]["lite"])
        self.assertEqual(full["meta"]["sections"]["passports"], "static")
        self.assertIn("passports", full)
        self.assertEqual(list(full)[0], "meta")

    def test_data_validation(self):
        for qs in ("full=2", "lite=yes", "codes=A,B C", "codes=" + ",".join("C%d" % i for i in range(201)),
                   "sections=Bad-Key"):
            with self.subTest(qs=qs):
                res = self._get("/f3d/viewer/data?" + qs)
                self.assertEqual(res.status_code, 400)
                self.assertEqual(res.json()["error"]["code"], "bad_request")

    def test_data_forbidden(self):
        res = self._get("/f3d/viewer/data", user="f3d_nobody")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["error"]["code"], "forbidden")

    # --- API-03 ---
    def test_delta(self):
        res = self._get("/f3d/viewer/delta")
        self.assertEqual(res.status_code, 400)
        res = self._get("/f3d/viewer/delta?since=yesterday")
        self.assertEqual(res.status_code, 400)
        res = self._get("/f3d/viewer/delta?since=2026-10-12T07:30:12Z&codes=SAW-1")
        self.assertEqual(res.status_code, 200)
        self.assertIn("ts", res.json())
        self.assertEqual(self._get("/f3d/viewer/delta?since=2026-10-12T07:30:12", user="f3d_nobody").status_code, 403)

    # --- API-04 ---
    def test_resolve(self):
        res = self._get("/f3d/viewer/resolve?code=ZZ-WC-1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["model"], "mrp.workcenter")
        self.assertEqual(res.json()["res_id"], self.wc.id)
        res = self._get("/f3d/viewer/resolve?code=ZZ-NOPE")
        self.assertEqual(res.json(), {"model": None, "res_id": None, "reason": "not_found"})

    def test_resolve_bad_code(self):
        """AC-40."""
        for qs in ("code=PLT-04C'; DROP", "", "code=A&name=B", "name=" + "x" * 65):
            with self.subTest(qs=qs):
                res = self._get("/f3d/viewer/resolve?" + qs)
                self.assertEqual(res.status_code, 400)
                self.assertEqual(res.json()["error"]["code"], "bad_request")

    def test_resolve_forbidden(self):
        self.assertEqual(self._get("/f3d/viewer/resolve?code=A", user="f3d_nobody").status_code, 403)

    # --- API-07 ---
    def test_manifest(self):
        res = self._get("/f3d/viewer/parts/manifest.json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("max-age=3600", res.headers["Cache-Control"])
        for part in res.json()["parts"]:
            self.assertRegex(part["file"], r"\.glb\?v=[0-9a-f]{12}$")
        res2 = self.url_open("/f3d/viewer/parts/manifest.json", headers={"If-None-Match": res.headers["ETag"]},
                             allow_redirects=False)
        self.assertEqual(res2.status_code, 304)

    # --- API-10 ---
    def test_cycle_check(self):
        from odoo.addons.factory3d_viewer.hooks import is_demo_db
        if not is_demo_db(self.env):
            raise unittest.SkipTest("потрібна демо-база: на порожній payload неповний")
        self.authenticate("f3d_manager", "f3d_manager")
        res = self.make_jsonrpc_request("/f3d/viewer/cycle_check", {})
        self.assertEqual(res, {"ok": True, "issues": []})

    def test_cycle_check_access(self):
        self.authenticate("f3d_user", "f3d_user")
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request("/f3d/viewer/cycle_check", {})
        self.authenticate("f3d_manager", "f3d_manager")
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request("/f3d/viewer/cycle_check", {"as_user": self.user_f3d.id})
