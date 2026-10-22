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
        cls.wc = cls.env["mrp.workcenter"].create({"name": "ZZ центр", "td_code": "ZZ-WC-1"})

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
        for qs in (
            "full=2",
            "lite=yes",
            "codes=A,B C",
            "codes=" + ",".join("C%d" % i for i in range(201)),
            "sections=Bad-Key",
        ):
            with self.subTest(qs=qs):
                res = self._get("/f3d/viewer/data?" + qs)
                self.assertEqual(res.status_code, 400)
                self.assertEqual(res.json()["error"]["code"], "bad_request")

    def test_data_code_traversal_rejected(self):  # V-2
        for codes in ("../../etc", "..", "/etc", "A//B", "A/../B", ".hidden"):
            with self.subTest(codes=codes):
                res = self._get("/f3d/viewer/data?codes=" + codes)
                self.assertEqual(res.status_code, 400)
                self.assertEqual(res.json()["error"]["code"], "bad_request")
        for codes in ("WH/MO/00231", "TST/MR/00031", "SAW-1,ZZ-WC-1", "PLT-04.C_1"):
            with self.subTest(codes=codes):
                self.assertEqual(self._get("/f3d/viewer/data?codes=" + codes).status_code, 200)

    def test_snapshot_bad_id_404(self):  # V-3
        for sid in ("abc", "-1", "1.5", "0", "99999999999"):
            with self.subTest(sid=sid):
                res = self._get("/f3d/viewer/snapshot/" + sid)
                self.assertEqual(res.status_code, 404)
                self.assertEqual(res.json()["error"]["code"], "not_found")

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

    def test_delta_many_codes(self):
        """Клієнт накопичує коди з повідомлень шини: 201–260 (і до 2000) кодів — 200, а не 400; 2001 — 400."""
        for n in (200, 201, 260, 2000):
            with self.subTest(n=n):
                codes = ",".join("C%d" % i for i in range(n))
                res = self._get("/f3d/viewer/delta?since=2026-10-12T07:30:12Z&codes=" + codes)
                self.assertEqual(res.status_code, 200)
                self.assertIn("ts", res.json())
        codes = ",".join("C%d" % i for i in range(2001))
        res = self._get("/f3d/viewer/delta?since=2026-10-12T07:30:12Z&codes=" + codes)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"]["code"], "bad_request")
        res = self._get("/f3d/viewer/delta?since=2026-10-12T07:30:12Z&codes=A,../x")
        self.assertEqual(res.status_code, 400)

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

    def test_resolve_group(self):
        """R-16 п. 5: `codes` — дочірні коди об'єкта без власного запису."""
        stock = self.env.ref("stock.stock_location_stock")
        bins = self.env["stock.location"].create(
            [{"name": f"ZZ-GB{i}", "location_id": stock.id, "td_code": f"ZZ-GB{i}"} for i in (1, 2)]
        )
        res = self._get("/f3d/viewer/resolve?code=ZZ-RACK-G&codes=ZZ-GB1,ZZ-GB2,ZZ-NONE")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual((data["model"], data["res_id"], data["kind"]), ("stock.location", None, "group"))
        self.assertEqual(sorted(data["res_ids"]), sorted(bins.ids))
        res = self._get("/f3d/viewer/resolve?code=ZZ-RACK-G&codes=ZZ-NONE")
        self.assertEqual(res.json()["reason"], "not_found")
        # власний запис — як раніше, без res_ids
        res = self._get("/f3d/viewer/resolve?code=ZZ-WC-1&codes=ZZ-GB1")
        self.assertEqual(res.json()["res_id"], self.wc.id)

    def test_resolve_group_bad_codes(self):
        too_many = ",".join(f"C{i}" for i in range(201))
        for qs in (
            "code=A&codes=bad%20code",
            "name=WH/IN/00001&codes=A",
            "code=A&codes=" + too_many,
            "code=A&codes=../x",
        ):
            with self.subTest(qs=qs[:40]):
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
        res2 = self.url_open(
            "/f3d/viewer/parts/manifest.json", headers={"If-None-Match": res.headers["ETag"]}, allow_redirects=False
        )
        self.assertEqual(res2.status_code, 304)

    # --- API-10 ---
    def test_cycle_check(self):
        from .common import _has_demo_data

        if not _has_demo_data(self.env):
            raise unittest.SkipTest("потрібна демо-база: на порожній payload неповний")
        # payload будується з правами користувача: менеджеру «3D Завод» потрібен ще й доступ до складу/МО
        self.user_manager.group_ids = [
            (4, self.env.ref("stock.group_stock_user").id),
            (4, self.env.ref("mrp.group_mrp_user").id),
        ]
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
