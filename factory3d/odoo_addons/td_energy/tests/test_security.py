"""AC-75…AC-82: меню, представлення, групи, ACL, правила компаній, стоп-крани й нейтралізація."""

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import file_open

from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin

MENUS = {  # xml-id: (sequence, parent xml-id, група)
    "menu_td_energy": (50, "td_factory3d.menu_td_root", "group_td_energy_user"),
    "menu_td_energy_overview": (10, "menu_td_energy", "group_td_energy_user"),
    "menu_td_energy_scheme": (20, "menu_td_energy", "group_td_energy_user"),
    "menu_td_energy_meter": (30, "menu_td_energy", "group_td_energy_user"),
    "menu_td_energy_alloc": (50, "menu_td_energy", "group_td_energy_user"),
    "menu_td_energy_balance": (60, "menu_td_energy", "group_td_energy_user"),
    "menu_td_energy_outage": (70, "menu_td_energy", "group_td_energy_user"),
    "menu_td_energy_event": (80, "menu_td_energy", "group_td_energy_user"),
    "menu_td_energy_config": (90, "menu_td_energy", "group_td_energy_cost"),
    "menu_td_energy_tariff": (10, "menu_td_energy_config", "group_td_energy_cost"),
    "menu_td_energy_pool": (20, "menu_td_energy_config", "group_td_energy_manager"),
    "menu_td_energy_recompute": (30, "menu_td_energy_config", "group_td_energy_manager"),
    "menu_td_energy_settings": (50, "td_factory3d.menu_td_config", "td_factory3d.group_td_admin"),
}


@tagged(*TAGS)
class TestSecurity(EnergyMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.u_sys = new_test_user(cls.env, login="en_sys", groups="base.group_user,base.group_system")

    def ref(self, xmlid, module="td_energy"):
        return self.env.ref(xmlid if "." in xmlid else "%s.%s" % (module, xmlid))

    def group(self, name):
        return name if "." in name else "td_energy." + name

    def test_menus(self):  # AC-75
        for xmlid, (seq, parent, group) in MENUS.items():
            menu = self.ref(xmlid)
            self.assertEqual(menu.sequence, seq, xmlid)
            self.assertEqual(menu.parent_id, self.ref(parent), xmlid)
            self.assertEqual(menu.group_ids, self.ref(self.group(group)), xmlid)
        self.assertTrue(self.ref("menu_td_energy_profile").action)

    def test_views_load(self):  # AC-76
        actions = self.env["ir.actions.act_window"].search(
            [("id", "in", self.env["ir.model.data"].search([("module", "=", "td_energy"),
                                                            ("model", "=", "ir.actions.act_window")]).mapped("res_id"))]
        )  # fmt: skip
        self.assertGreaterEqual(len(actions), 12)
        for action in actions:
            views = [(False, vt) for vt in action.view_mode.split(",")]
            res = self.env[action.res_model].with_user(self.u_sys).get_views(views)
            self.assertEqual(set(res["views"]), {vt for _i, vt in views}, action.name)
        arch = self.env["td.energy.node"].get_views([(False, "hierarchy")])["views"]["hierarchy"]["arch"]
        self.assertIn("parent_id", arch)

    def test_group_implications(self):  # AC-77
        has = lambda u, g: u.has_group(self.group(g))  # noqa: E731
        self.assertTrue(has(self.u_master, "group_td_energy_user"))
        self.assertFalse(has(self.u_master, "group_td_energy_cost"))
        self.assertTrue(has(self.u_account, "group_td_energy_cost"))
        self.assertTrue(has(self.u_energy, "group_td_energy_manager"))
        self.assertTrue(
            self.u_energy.has_group("td_factory3d.group_td_manager") or has(self.u_energy, "group_td_energy_cost")
        )
        menu = self.ref("menu_td_energy")
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(self.u_master)._visible_menu_ids())
        self.assertNotIn(menu.id, self.env["ir.ui.menu"].with_user(self.u_viewer)._visible_menu_ids())

    def test_acl(self):  # AC-78
        node = self.env["td.energy.node"].search([("code", "=", "SAW-1")])
        with self.assertRaises(AccessError):
            node.with_user(self.u_master).write({"note": "x"})
        node.with_user(self.u_energy).write({"note": "x"})
        for model in ("td.energy.interval", "td.energy.alloc", "td.energy.balance"):
            for user in (self.u_master, self.u_energy):
                Model = self.env[model].with_user(user)
                self.assertTrue(Model.has_access("read"), (model, user.login))
                for op in ("write", "create", "unlink"):
                    self.assertFalse(Model.has_access(op), (model, user.login, op))
            self.assertTrue(self.env[model].with_user(self.u_admin).has_access("write"), model)
        self.assertTrue(self.env["td.energy.alloc"].with_user(self.u_master).has_access("read"))  # mrp_user

    def test_company_rules(self):  # AC-79
        company = self.env["res.company"].create({"name": "Energy B"})
        parent = self.env["td.energy.node"].search([("code", "=", "SEC-1")])
        node = self.env["td.energy.node"].create(
            {"code": "CO-B", "name": "B", "kind": "consumer", "parent_id": parent.id, "company_id": company.id}
        )
        tariff = self.env["td.energy.tariff"].search([], limit=1)
        tariff.company_id = company
        self.assertTrue(node.id)
        energy = self.u_energy
        self.assertEqual(energy.company_id, self.env.company)
        self.assertFalse(self.env["td.energy.node"].with_user(energy).search([("code", "=", "CO-B")]))
        self.assertFalse(self.env["td.energy.tariff"].with_user(energy).search([("id", "=", tariff.id)]))

    def set_read(self, value):
        settings = self.env["res.config.settings"].create({"td_energy_read_enabled": value})
        settings.set_values()

    def test_read_disabled_crons(self):  # AC-80
        Source = self.env["td.source"].sudo()
        self.set_read(False)
        sources = Source.search([("module", "=", "energy")])
        self.assertEqual(len(sources.filtered(lambda s: s.type == "modbus_tcp")), 69)
        self.assertFalse(any(sources.mapped("read_enabled")))
        before = {
            m: self.env[m].search_count([]) for m in ("td.energy.interval", "td.energy.alloc", "td.energy.balance")
        }
        for model, cron in (
            ("td.energy.node", "_cron_live"), ("td.energy.interval", "_cron_build"),
            ("td.energy.alloc", "_cron_alloc"), ("td.energy.balance", "_cron_balance"),
        ):  # fmt: skip
            self.assertFalse(getattr(self.env[model], cron)())
        after = {m: self.env[m].search_count([]) for m in before}
        self.assertEqual(before, after)
        self.set_read(True)
        self.assertTrue(all(Source.search([("module", "=", "energy")]).mapped("read_enabled")))

    def test_write_forbidden(self):  # AC-81
        sig = self.mk_signal("energy/test/setpoint")
        with self.assertRaises(ValidationError):
            sig.write({"write_enabled": True})
        other = self.env["td.signal"].create(
            {"code": "telemetry/test/setpoint", "name": "t", "kind": "gauge", "module": "telemetry"}
        )
        other.write({"write_enabled": True})
        self.assertTrue(other.write_enabled)

    def test_stop_valves_admin_only(self):
        icp = self.env["ir.config_parameter"]
        for user in (self.u_energy, self.u_master, self.u_viewer):
            with self.assertRaises(AccessError):
                icp.with_user(user).search([("key", "=", "td.energy.read_enabled")])
            with self.assertRaises(AccessError):
                self.env["res.config.settings"].with_user(user).create({})
            with self.assertRaises(AccessError):
                self.env["td.energy.node"].with_user(user).action_td_energy_rebind()
        # write_enabled у формі readonly: set_values його не змінює
        settings = self.env["res.config.settings"].create({"td_energy_write_enabled": True})
        settings.set_values()
        self.assertEqual(icp.sudo().get_param("td.energy.write_enabled"), "False")

    def test_neutralize_sql(self):  # AC-82
        with file_open("td_energy/data/neutralize.sql") as fd:
            self.env.cr.execute(fd.read())
        self.env.invalidate_all()
        icp = self.env["ir.config_parameter"].sudo()
        for key in ("read_enabled", "write_enabled", "costing_enabled"):
            self.assertEqual(icp.get_param("td.energy." + key), "False", key)
        ids = self.env["ir.model.data"].search([("module", "=", "td_energy"), ("model", "=", "ir.cron")])
        crons = self.env["ir.cron"].sudo().with_context(active_test=False).browse(ids.mapped("res_id"))
        self.assertTrue(crons)
        self.assertFalse(any(crons.mapped("active")))
        sources = self.env["td.source"].sudo().search([("module", "=", "energy")])
        self.assertTrue(sources)
        self.assertEqual(set(sources.mapped("state")), {"disabled"})
        self.assertFalse(any(sources.mapped("read_enabled")))
        self.assertTrue(fields.Datetime.now())
