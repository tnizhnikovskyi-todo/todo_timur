import ast

from lxml import etree

from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tests import Form, tagged

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")


@tagged(*TAGS)
class TestEquipmentTab(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def test_counts(self):
        """AC-63: лічильники сигналів і тривог на обладнанні."""
        self.assertEqual((self.eq_comp.td_signal_count, self.eq_comp.td_alarm_count), (3, 0))
        self.set_sql(self.sig_press, status="alarm")
        self.eq_comp.invalidate_recordset()
        self.assertEqual(self.eq_comp.td_alarm_count, 1)

    def test_page_present(self):
        arch = self.env["maintenance.equipment"].get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertIn('name="f3d_signals"', arch)
        self.assertIn('name="td_signal_ids"', arch)
        self.assertIn('name="action_f3d_view_signals"', arch)
        self.assertIn('name="action_f3d_view_readings"', arch)

    def test_actions(self):
        action = self.eq_comp.action_f3d_view_signals()
        self.assertEqual(action["domain"], [("equipment_id", "=", self.eq_comp.id)])
        self.assertEqual(self.eq_comp.action_f3d_view_readings()["domain"], [("equipment_id", "=", self.eq_comp.id)])


@tagged(*TAGS)
class TestViewsLoad(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def test_all_views_load(self):
        """AC-64: get_views для кожної дії модуля (усі типи з view_mode)."""
        self.env.cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = 'td_telemetry' AND model = 'ir.actions.act_window'"
        )
        actions = self.env["ir.actions.act_window"].browse([r[0] for r in self.env.cr.fetchall()])
        self.assertGreaterEqual(len(actions), 10)
        for action in actions:
            views = [(False, t) for t in action.view_mode.split(",")] + [(False, "search")]
            with self.subTest(action=action.name, model=action.res_model):
                self.env[action.res_model].get_views(views)
        for model in (
            "maintenance.equipment",
            "maintenance.request",
            "res.config.settings",
            "td.collector.token.wizard",
        ):
            with self.subTest(model=model):
                self.env[model].get_views([(False, "form")])

    def test_signal_form_create(self):
        form = Form(self.env["td.signal"].with_user(self.user_manager))
        form.code = "equipment/FORM-T/pressure_bar"
        form.name = "Форма: тиск"
        form.source_id = self.src_mb
        form.address_text = '{"fc": 3, "addr": 3001, "type": "u16"}'
        signal = form.save()
        self.assertEqual(signal.source_id, self.src_mb)
        self.assertEqual(signal.address, {"fc": 3, "addr": 3001, "type": "u16"})

    def test_source_bad_params_text(self):
        form = Form(self.env["td.source"].with_user(self.user_manager))
        form.code = "MB-FORM"
        form.name = "Форма"
        form.type = "modbus_tcp"
        form.collector_id = self.col
        form.params_text = '{"host": '
        with self.assertRaises(ValidationError):
            form.save()

    def _default_filters_domain(self, action):
        """Домен типових фільтрів дії, як його будує клієнт: фільтри одного блоку — OR, блоки (між `separator`) —
        AND."""
        ctx = ast.literal_eval(action.context)
        arch = self.env["td.signal"].get_views([(False, "search")])["views"]["search"]["arch"]
        blocks, current = [], []
        for node in etree.fromstring(arch):
            if node.tag == "separator":
                blocks.append(current)
                current = []
            elif node.tag == "filter" and node.get("domain"):
                if ctx.get("search_default_" + node.get("name")):
                    current.append(Domain(ast.literal_eval(node.get("domain"))))
        blocks.append(current)
        return Domain.AND([Domain.OR(b) for b in blocks if b])

    def test_alarm_action_shows_only_alarms(self):
        """T-4: дія «Телеметрія» (`search_default_alarm`) показує лише тривоги, а не всі сигнали."""
        action = self.env.ref("td_telemetry.action_td_signal_alarm")
        self.set_sql(self.sig_press, status="alarm")
        self.set_sql(self.sig_bat, status="ok")
        signals = self.env["td.signal"].search(self._default_filters_domain(action))
        self.assertIn(self.sig_press, signals)
        self.assertNotIn(self.sig_bat, signals)
        self.assertEqual(set(signals.mapped("status")), {"alarm"})
        # типова дія «Сигнали» лишає всі увімкнені сигнали
        base = self.env.ref("td_telemetry.action_td_signal")
        self.assertIn(self.sig_bat, self.env["td.signal"].search(self._default_filters_domain(base)))

    def test_reading_action_context(self):
        action = self.env.ref("td_telemetry.action_td_reading")
        self.assertEqual(ast.literal_eval(action.context)["search_default_last_48h"], 1)
        self.assertTrue(action.view_mode.startswith("graph"))
        self.assertEqual(self.sig_press.action_view_readings()["context"]["search_default_last_48h"], 1)


@tagged(*TAGS)
class TestMenus(F3DTelemetryCase):
    CHILDREN = {  # xml-id -> (sequence, група)
        "menu_td_telemetry_overview": (10, "group_td_user"),
        "menu_td_telemetry_signal": (20, "group_td_user"),
        "menu_td_telemetry_reading": (30, "group_td_user"),
        "menu_td_telemetry_reading_hour": (35, "group_td_user"),
        "menu_td_telemetry_source": (40, "group_td_manager"),
        "menu_td_telemetry_collector": (50, "group_td_admin"),
        "menu_td_telemetry_command": (60, "group_td_manager"),
        "menu_td_telemetry_push_event": (70, "group_td_manager"),
    }

    def test_menu_tree(self):
        root = self.env.ref("td_telemetry.menu_td_telemetry")
        self.assertEqual((root.parent_id, root.sequence), (self.env.ref("td_factory3d.menu_td_root"), 30))
        self.assertIn(self.env.ref("td_factory3d.group_td_user"), root.group_ids)
        for xmlid, (sequence, group) in self.CHILDREN.items():
            with self.subTest(menu=xmlid):
                menu = self.env.ref("td_telemetry." + xmlid)
                self.assertEqual((menu.parent_id, menu.sequence), (root, sequence))
                self.assertIn(self.env.ref("td_factory3d." + group), menu.group_ids)
        maint = self.env.ref("td_telemetry.menu_td_telemetry_maint")
        self.assertEqual((maint.parent_id, maint.sequence), (self.env.ref("maintenance.menu_maintenance_title"), 6))

    def test_reader_menus(self):
        visible = self.env["ir.ui.menu"].with_user(self.user_reader)._visible_menu_ids()
        for xmlid in ("overview", "signal", "reading", "reading_hour"):
            self.assertIn(self.env.ref("td_telemetry.menu_td_telemetry_" + xmlid).id, visible, xmlid)
        for xmlid in ("source", "collector", "command", "push_event"):
            self.assertNotIn(self.env.ref("td_telemetry.menu_td_telemetry_" + xmlid).id, visible, xmlid)
