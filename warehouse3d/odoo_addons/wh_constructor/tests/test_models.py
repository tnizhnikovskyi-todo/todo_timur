from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from .common import G_APPLY, G_DESIGN, G_VIEW, make_user, project_data


@tagged("post_install", "-at_install")
class TestWhConstructor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer = make_user(cls.env, "wh_viewer", G_VIEW)
        cls.designer = make_user(cls.env, "wh_designer", G_DESIGN)
        cls.designer2 = make_user(cls.env, "wh_designer2", G_DESIGN)
        cls.applier = make_user(cls.env, "wh_applier", G_APPLY)
        cls.Project = cls.env["wh.project"]

    def save(self, user=None, key="p-1", marks=0, base_rev=None, **kw):
        return (self.Project.with_user(user) if user else self.Project).api_save(key, project_data(marks=marks), base_rev=base_rev, **kw)

    # ------------------------------------------------------------ группы
    def test_groups_chain(self):
        self.assertTrue(self.applier.has_group(G_DESIGN) and self.applier.has_group(G_VIEW))
        self.assertTrue(self.designer.has_group(G_VIEW))
        self.assertFalse(self.designer.has_group(G_APPLY))
        self.assertFalse(self.viewer.has_group(G_DESIGN))

    def test_menu(self):
        menu = self.env.ref("wh_constructor.menu_wh_constructor")
        self.assertEqual(menu.parent_id, self.env.ref("stock.menu_stock_config_settings"))
        self.assertEqual(menu.action.url, "/wh_constructor/app")

    def test_rights_by_group(self):
        self.save(self.designer)
        project = self.Project.search([("key", "=", "p-1")])
        # просмотр: читает, но не пишет, не создаёт и не удаляет
        as_viewer = project.with_user(self.viewer)
        self.assertEqual(as_viewer.name, "Тестовий склад")
        with self.assertRaises(AccessError):
            as_viewer.write({"name": "x"})
        with self.assertRaises(AccessError):
            self.Project.with_user(self.viewer).create({"name": "n", "key": "k"})
        with self.assertRaises(AccessError):
            as_viewer.unlink()
        with self.assertRaises(AccessError):
            self.save(self.viewer, key="p-2")
        # версии: просмотр читает, но не создаёт
        self.assertEqual(len(self.env["wh.project.version"].with_user(self.viewer).search([("project_id", "=", project.id)])), 1)
        with self.assertRaises(AccessError):
            self.env["wh.project.version"].with_user(self.viewer).create({"project_id": project.id, "rev": 9})
        # проектирование пишет; применение включает проектирование
        project.with_user(self.designer).write({"name": "Новий"})
        self.assertEqual(self.save(self.applier, key="p-3")["status"], "ok")

    def test_company_rule(self):
        company2 = self.env["res.company"].create({"name": "Друга компанія"})
        other = make_user(self.env, "wh_other_company", G_DESIGN, company=company2)
        self.save(self.designer)
        self.assertTrue(self.Project.with_user(self.designer).search([("key", "=", "p-1")]))
        self.assertFalse(self.Project.with_user(other).search([("key", "=", "p-1")]))
        self.assertEqual(self.Project.with_user(other).api_list(), [])
        self.assertEqual(self.Project.with_user(other).api_load("p-1"), {"found": False})

    # ------------------------------------------------------------ проекты и версии
    def test_save_load_list(self):
        r = self.save(self.designer, marks=1)
        self.assertEqual((r["status"], r["rev"]), ("ok", 1))
        project = self.Project.search([("key", "=", "p-1")])
        self.assertEqual((project.schema, project.company_id), (2, self.env.company))
        self.assertEqual(project.data["warehouses"][0]["saved"], {"marks": 1})
        loaded = self.Project.with_user(self.viewer).api_load("p-1")
        self.assertTrue(loaded["found"])
        self.assertEqual((loaded["rev"], loaded["data"]["name"]), (1, "Тестовий склад"))
        summary = self.Project.with_user(self.viewer).api_list()
        self.assertEqual([(s["id"], s["name"], s["warehouses"], s["rev"]) for s in summary], [("p-1", "Тестовий склад", 1, 1)])
        self.assertFalse(self.Project.api_load("нема")["found"])

    def test_warehouses_linked_by_code(self):
        self.save(self.designer)
        project = self.Project.search([("key", "=", "p-1")])
        wh = self.env["stock.warehouse"].search([("code", "=", "WH")])
        self.assertEqual(project.warehouse_ids, wh)

    def test_version_conflict(self):
        self.assertEqual(self.save(self.designer, marks=1)["rev"], 1)
        self.assertEqual(self.save(self.designer, marks=2, base_rev=1)["rev"], 2)
        stale = self.save(self.designer2, marks=3, base_rev=1)
        self.assertEqual((stale["status"], stale["rev"], stale["by"]), ("stale", 2, self.designer.name))
        self.assertEqual(self.save(self.designer2, marks=3, base_rev=None)["status"], "stale")  # проект уже есть
        project = self.Project.search([("key", "=", "p-1")])
        self.assertEqual((project.rev, project.data["warehouses"][0]["saved"]), (2, {"marks": 2}))
        self.assertEqual(self.save(self.designer2, marks=3, base_rev=2)["rev"], 3)

    def test_versions_limited_to_50(self):
        rev = None
        for i in range(55):
            rev = self.save(self.designer, marks=i, base_rev=rev, comment=f"c{i}")["rev"]
        versions = self.Project.api_versions("p-1")
        self.assertEqual(len(versions), 50)
        self.assertEqual((versions[0]["rev"], versions[-1]["rev"]), (55, 6))
        self.assertEqual(versions[0]["comment"], "c54")
        self.env["ir.config_parameter"].sudo().set_param("wh_constructor.max_versions", "3")
        self.save(self.designer, marks=99, base_rev=rev)
        self.assertEqual([v["rev"] for v in self.Project.api_versions("p-1")], [56, 55, 54])

    def test_draft_saves_make_no_versions(self):
        rev = self.save(self.designer)["rev"]
        rev = self.save(self.designer, marks=1, base_rev=rev, commit=False)["rev"]
        self.assertEqual(rev, 2)
        self.assertEqual(len(self.Project.api_versions("p-1")), 1)

    def test_restore_version(self):
        rev = self.save(self.designer, marks=1)["rev"]
        rev = self.save(self.designer, marks=2, base_rev=rev)["rev"]
        first = self.Project.api_versions("p-1")[-1]
        self.assertEqual(self.Project.api_restore("p-1", first["id"], base_rev=1)["status"], "stale")
        r = self.Project.with_user(self.designer).api_restore("p-1", first["id"], base_rev=rev)
        self.assertEqual((r["status"], r["rev"], r["data"]["warehouses"][0]["saved"]), ("ok", 3, {"marks": 1}))
        versions = self.Project.api_versions("p-1")
        self.assertEqual(len(versions), 3)  # история не переписывается
        self.assertIn(str(first["rev"]), versions[0]["comment"])
        with self.assertRaises(AccessError):
            self.Project.with_user(self.viewer).api_restore("p-1", first["id"], base_rev=3)

    def test_delete(self):
        self.save(self.designer)
        self.assertTrue(self.Project.with_user(self.designer).api_delete("p-1")["deleted"])
        self.assertFalse(self.env["wh.project.version"].search([("project_id.key", "=", "p-1")]))
        self.assertEqual(self.Project.api_list(), [])

    # ------------------------------------------------------------ блокировки
    def lock(self, user, zone="Z1", wh="wh-1"):
        return self.env["wh.zone.lock"].with_user(user).api_acquire("p-1", wh, zone, warehouse_code="WH")

    def test_lock_foreign_zone(self):
        self.save(self.designer)
        mine = self.lock(self.designer)
        self.assertTrue(mine["ok"] and mine["mine"])
        busy = self.lock(self.designer2)
        self.assertFalse(busy["ok"])
        self.assertEqual((busy["owner"], busy["zone"]), (self.designer.name, "Z1"))
        self.assertTrue(busy["expires"].endswith("Z"))
        self.assertTrue(self.lock(self.designer2, zone="Z2")["ok"])  # другая зона свободна
        self.assertTrue(self.lock(self.designer2, zone="Z1", wh="wh-2")["ok"])  # тот же ключ в другом складе
        lock = self.env["wh.zone.lock"].search([("zone_key", "=", "Z1"), ("warehouse_key", "=", "wh-1")])
        self.assertEqual((len(lock), lock.warehouse_id), (1, self.env["stock.warehouse"].search([("code", "=", "WH")])))

    def test_lock_renew_release(self):
        self.save(self.designer)
        self.lock(self.designer)
        lock = self.env["wh.zone.lock"].search([("zone_key", "=", "Z1")])
        lock.expires = fields.Datetime.now() + timedelta(seconds=10)
        renewed = self.lock(self.designer)
        self.assertTrue(renewed["ok"])
        self.assertGreater(lock.expires, fields.Datetime.now() + timedelta(seconds=100))  # продлена на TTL
        # чужой освободить не может
        self.env["wh.zone.lock"].with_user(self.designer2).api_release("p-1", "wh-1", "Z1")
        self.assertFalse(self.lock(self.designer2)["ok"])
        self.assertEqual(self.env["wh.zone.lock"].with_user(self.designer).api_release("p-1", "wh-1", "Z1")["released"], 1)
        self.assertTrue(self.lock(self.designer2)["ok"])

    def test_lock_expires(self):
        self.save(self.designer)
        self.lock(self.designer)
        lock = self.env["wh.zone.lock"].search([("zone_key", "=", "Z1")])
        self.assertEqual(len(self.env["wh.zone.lock"].api_list("p-1")), 1)
        lock.expires = fields.Datetime.now() - timedelta(seconds=1)
        self.assertEqual(self.env["wh.zone.lock"].api_list("p-1"), [])
        taken = self.lock(self.designer2)
        self.assertTrue(taken["ok"] and taken["owner"] == self.designer2.name)
        self.assertEqual(len(self.env["wh.zone.lock"].search([("zone_key", "=", "Z1")])), 1)

    def test_lock_release_all_and_rights(self):
        self.save(self.designer)
        self.lock(self.designer, "Z1")
        self.lock(self.designer, "Z2")
        self.assertEqual(self.env["wh.zone.lock"].with_user(self.designer).api_release("p-1")["released"], 2)
        with self.assertRaises(AccessError):
            self.lock(self.viewer)
        self.assertFalse(self.env["wh.zone.lock"].with_user(self.designer).api_acquire("нема", "wh-1", "Z1")["ok"])
