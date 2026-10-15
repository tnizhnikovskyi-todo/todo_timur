from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged

from .common import G_DESIGN, G_VIEW, make_user

LIB = {"types": [{"id": "X1", "name": "Мій тип", "form": "shelf"}], "templates": [{"id": "t1", "name": "Секція 3 яруси"}]}


@tagged("post_install", "-at_install")
class TestWhLibrary(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer = make_user(cls.env, "wh_lib_viewer", G_VIEW)
        cls.designer = make_user(cls.env, "wh_lib_designer", G_DESIGN)
        cls.Lib = cls.env["wh.library"]

    def test_cycle_and_stale(self):
        lib = self.Lib.with_user(self.designer)
        self.assertEqual(lib.api_load(), {"found": False, "data": None, "rev": 0})
        self.assertEqual(lib.api_save(LIB, base_rev=None), {"status": "ok", "rev": 1})
        got = lib.api_load()
        self.assertEqual((got["found"], got["rev"], got["data"]), (True, 1, LIB))
        self.assertEqual(lib.api_save({"types": [], "templates": []}, base_rev=1)["rev"], 2)
        stale = lib.api_save(LIB, base_rev=1)
        self.assertEqual((stale["status"], stale["rev"], stale["data"]), ("stale", 2, {"types": [], "templates": []}))
        self.assertEqual(self.Lib.search_count([]), 1)  # одна запись на компанию

    def test_unknown_keys_dropped(self):
        self.Lib.with_user(self.designer).api_save({**LIB, "evil": [1]}, base_rev=None)
        self.assertEqual(sorted(self.Lib.api_load()["data"]), ["templates", "types"])

    def test_rights(self):
        self.Lib.with_user(self.designer).api_save(LIB, base_rev=None)
        viewer = self.Lib.with_user(self.viewer)
        self.assertEqual(viewer.api_load()["data"], LIB)  # читать «перегляд» может
        with self.assertRaises(AccessError):
            viewer.api_save({"types": [], "templates": []}, base_rev=1)


@tagged("post_install", "-at_install")
class TestWhLibraryHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = make_user(cls.env, "wh_libh_designer", G_DESIGN)
        cls.viewer = make_user(cls.env, "wh_libh_viewer", G_VIEW)
        cls.plain = make_user(cls.env, "wh_libh_plain")

    def login(self, user):
        self.authenticate(user.login, f"{user.login}-pass-1")

    def rpc(self, route, **params):
        return self.make_jsonrpc_request("/wh_constructor/api" + route, params)

    def test_library_routes(self):
        self.login(self.designer)
        self.assertEqual(self.rpc("/library/load"), {"status": "ok", "found": False, "data": None, "rev": 0})
        self.assertEqual(self.rpc("/library/save", data=LIB, base_rev=None), {"status": "ok", "rev": 1})
        self.assertEqual(self.rpc("/library/save", data=LIB, base_rev=0)["status"], "stale")
        self.login(self.viewer)
        got = self.rpc("/library/load")
        self.assertEqual((got["status"], got["data"], got["rev"]), ("ok", LIB, 1))
        self.assertEqual(self.rpc("/library/save", data=LIB, base_rev=1)["status"], "denied")
        self.login(self.plain)
        self.assertEqual(self.rpc("/library/load")["status"], "denied")
