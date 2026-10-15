from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from .common import G_DESIGN, G_VIEW, make_user, project_data

NODE = "WH/Сировина/Фурнітура/R1"


@tagged("post_install", "-at_install")
class TestWhComment(TransactionCase):
    """Комментарии на объектах (W-18, I3): «перегляд» читает и пишет, «проєктування» решает; вне группы и вне компании — нет."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer = make_user(cls.env, "wh_c_viewer", G_VIEW)
        cls.viewer2 = make_user(cls.env, "wh_c_viewer2", G_VIEW)
        cls.designer = make_user(cls.env, "wh_c_designer", G_DESIGN)
        cls.plain = make_user(cls.env, "wh_c_plain")
        cls.Project = cls.env["wh.project"]
        cls.Comment = cls.env["wh.comment"]
        cls.Project.with_user(cls.designer).api_save("p-1", project_data(), base_rev=None)

    def add(self, user, text="Перевірити висоту полиць", **kw):
        return self.Comment.with_user(user).api_add("p-1", "wh-1", kw.pop("node", NODE), text, label=kw.pop("label", "R1"), **kw)

    def test_view_group_reads_and_writes(self):
        c = self.add(self.viewer, kind="task")
        self.assertEqual((c["state"], c["kind"], c["by"], c["node"], c["wh"], c["label"]), ("open", "task", self.viewer.name, NODE, "wh-1", "R1"))
        self.assertTrue(c["at"] and c["doneBy"] == "" and c["doneAt"] == "")
        # читает любой с правом «перегляд», в том числе чужие комментарии
        listed = self.Comment.with_user(self.viewer2).api_list("p-1")
        self.assertEqual([x["id"] for x in listed], [c["id"]])
        # прямой доступ к модели: читать и создавать можно, менять и удалять — нет
        rec = self.Comment.with_user(self.viewer).browse(int(c["id"]))
        self.assertEqual(rec.text, "Перевірити висоту полиць")
        with self.assertRaises(AccessError):
            rec.write({"state": "done"})
        with self.assertRaises(AccessError):
            rec.unlink()

    def test_unknown_kind_becomes_note_and_text_checked(self):
        self.assertEqual(self.add(self.viewer, kind="шось")["kind"], "note")
        with self.assertRaises(ValidationError):
            self.add(self.viewer, text="   ")
        with self.assertRaises(ValidationError):
            self.add(self.viewer, text="я" * 2001)
        with self.assertRaises(ValidationError):
            self.Comment.with_user(self.viewer).api_add("нема", "wh-1", NODE, "текст")

    def test_no_group_no_access(self):
        with self.assertRaises(AccessError):
            self.add(self.plain)
        with self.assertRaises(AccessError):
            self.Comment.with_user(self.plain).api_list("p-1")

    def test_resolve_only_design(self):
        c = self.add(self.viewer)
        with self.assertRaises(AccessError):
            self.Comment.with_user(self.viewer).api_resolve("p-1", c["id"])
        self.assertEqual(self.Comment.api_list("p-1")[0]["state"], "open")
        done = self.Comment.with_user(self.designer).api_resolve("p-1", c["id"])
        self.assertEqual((done["state"], done["doneBy"]), ("done", self.designer.name))
        self.assertTrue(done["doneAt"])
        back = self.Comment.with_user(self.designer).api_resolve("p-1", c["id"], state="open")
        self.assertEqual((back["state"], back["doneBy"], back["doneAt"]), ("open", "", ""))
        with self.assertRaises(ValidationError):
            self.Comment.with_user(self.designer).api_resolve("p-1", 999999)

    def test_remove_own_or_design(self):
        mine, other = self.add(self.viewer), self.add(self.viewer2)
        self.assertEqual(self.Comment.with_user(self.viewer).api_remove("p-1", mine["id"]), {"removed": True})
        with self.assertRaises(AccessError):
            self.Comment.with_user(self.viewer).api_remove("p-1", other["id"])
        self.assertEqual(self.Comment.with_user(self.designer).api_remove("p-1", other["id"]), {"removed": True})
        self.assertEqual(self.Comment.api_list("p-1"), [])

    def test_company_rule_and_project_scope(self):
        c = self.add(self.viewer)
        other_project = self.Project.with_user(self.designer).api_save("p-2", project_data(), base_rev=None)
        self.assertEqual(other_project["status"], "ok")
        self.assertEqual(self.Comment.api_list("p-2"), [])  # комментарии другого проекта не видны
        with self.assertRaises(ValidationError):
            self.Comment.with_user(self.designer).api_resolve("p-2", c["id"])  # чужой проект
        company2 = self.env["res.company"].create({"name": "Друга компанія"})
        foreign = self.Project.sudo().create({"name": "Чужий", "key": "p-x", "company_id": company2.id, "data": project_data()})
        self.assertFalse(foreign.with_user(self.viewer).search([("key", "=", "p-x")]))
        self.assertEqual(self.Comment.with_user(self.viewer).api_list("p-x"), [])
        # комментарии удаляются вместе с проектом
        self.Project.api_delete("p-1")
        self.assertFalse(self.Comment.sudo().search([("id", "=", int(c["id"]))]))


@tagged("post_install", "-at_install")
class TestWhCommentHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = make_user(cls.env, "wh_ch_designer", G_DESIGN)
        cls.viewer = make_user(cls.env, "wh_ch_viewer", G_VIEW)
        cls.plain = make_user(cls.env, "wh_ch_plain")

    def login(self, user):
        self.authenticate(user.login, f"{user.login}-pass-1")

    def rpc(self, route, **params):
        return self.make_jsonrpc_request("/wh_constructor/api" + route, params)

    def test_comment_routes(self):
        self.login(self.designer)
        self.rpc("/project/save", key="p-1", data=project_data(), base_rev=None, comment="v1")
        self.login(self.viewer)
        added = self.rpc("/comment/add", key="p-1", warehouse="wh-1", node=NODE, text="Задача", kind="task", label="R1")
        self.assertEqual((added["status"], added["comment"]["kind"], added["comment"]["by"]), ("ok", "task", self.viewer.name))
        cid = added["comment"]["id"]
        self.assertEqual([c["id"] for c in self.rpc("/comment/list", key="p-1")["comments"]], [cid])
        self.assertEqual(self.rpc("/comment/resolve", key="p-1", comment_id=cid)["status"], "denied")
        self.assertEqual(self.rpc("/comment/remove", key="p-1", comment_id="999999")["status"], "error")
        self.login(self.designer)
        done = self.rpc("/comment/resolve", key="p-1", comment_id=cid, state="done")
        self.assertEqual((done["status"], done["comment"]["state"]), ("ok", "done"))
        # просмотр версии: данные версии (только чтение, читает «перегляд»)
        versions = self.rpc("/project/versions", key="p-1")["versions"]
        self.login(self.viewer)
        v = self.rpc("/project/version", key="p-1", version_id=versions[0]["id"])
        self.assertEqual((v["status"], v["data"]["id"], v["comment"]), ("ok", "p-1", "v1"))
        self.assertEqual(self.rpc("/project/version", key="p-1", version_id=999999)["status"], "missing")
        self.login(self.designer)
        self.assertEqual(self.rpc("/comment/remove", key="p-1", comment_id=cid), {"status": "ok", "removed": True})
        self.login(self.plain)
        self.assertEqual(self.rpc("/comment/list", key="p-1")["status"], "denied")
        self.assertEqual(self.rpc("/comment/add", key="p-1", warehouse="wh-1", node=NODE, text="x")["status"], "denied")
