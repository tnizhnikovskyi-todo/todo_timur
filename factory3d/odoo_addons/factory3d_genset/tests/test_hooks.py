import json
from datetime import timezone
from unittest import mock
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.tests import tagged
from odoo.tools import file_open

from .. import hooks
from ..adapters import telemetry
from .test_rules import TD, GensetCase

CRONS = ("cron_f3d_genset_publish", "cron_f3d_genset_events", "cron_f3d_genset_service")


@tagged("post_install", "-at_install")
class TestHook(GensetCase):
    def setUp(self):
        super().setUp()
        self.link.unlink()  # хук сам створює зв'язку
        self.Link = self.env["f3d.genset.link"]

    def run_hook(self):
        hooks.post_init_hook(self.env)
        return json.loads(self.env["ir.config_parameter"].sudo().get_param("factory3d.genset.migration_report"))

    def eq_link(self):
        return self.Link.search([("equipment_id", "=", self.genset_eq.id)])

    def cron(self, xml_id):
        return self.env.ref("factory3d_genset." + xml_id)

    def test_hook_single_generator(self):  # AC-01, AC-62
        report = self.run_hook()
        link = self.eq_link()
        self.assertEqual(len(link), 1)
        self.assertEqual(link.profile_id, self.profile)
        self.assertEqual(link.source_id.code, "GENSET-RELAY")
        self.assertEqual(link.source_id.type, "td_genset")
        self.assertEqual(report["link"]["created"], 1)
        self.assertEqual(self.env["f3d.signal"].search_count([("code", "=like", "infra/genset/GENSET/%")]), 26)
        self.assertEqual(self.env["f3d.genset.event.map"].with_context(active_test=False).search_count([]), 48)
        for xml_id in CRONS:
            self.assertTrue(self.cron(xml_id))

    def test_hook_two_generators(self):  # AC-02
        other = self.env["res.partner"].create({"name": "Генератор 2"})
        with mock.patch(TD + ".generators", return_value=self.td_gen | other):
            report = self.run_hook()
        self.assertFalse(self.eq_link())
        self.assertEqual(report["link"], "skipped: кілька генераторів — зв'яжіть вручну")

    def test_hook_adapter_not_verified(self):  # §11 п. 2
        with mock.patch(TD + ".generators", side_effect=NotImplementedError("ADP-02: звірити з td_genset")):
            report = self.run_hook()
        self.assertEqual(report["link"], "skipped: ADP-01 не звірено")

    def test_hook_no_equipment(self):  # §11 п. 4
        self.genset_eq.f3d_code = "GENSET-X"
        report = self.run_hook()
        self.assertEqual(report["link"], "skipped: немає обладнання з f3d_code=GENSET")

    def test_hook_prod_env(self):  # AC-09
        icp = self.env["ir.config_parameter"].sudo()
        self.run_hook()
        self.assertEqual(icp.get_param("factory3d.genset.read_enabled"), "True")
        self.assertTrue(self.cron("cron_f3d_genset_publish").active)
        icp.set_param("factory3d.base.environment", "prod")
        self.run_hook()
        self.assertEqual(icp.get_param("factory3d.genset.read_enabled"), "False")
        self.assertFalse(self.cron("cron_f3d_genset_publish").active)

    def test_hook_idempotent(self):  # AC-50
        self.run_hook()
        row = self.env["f3d.genset.event.map"].search([("key", "=", "LOW_OIL_PRESSURE_SD")])
        row.td_code = "LOP_SD"

        def counts():
            return (self.Link.search_count([("equipment_id", "=", self.genset_eq.id)]),
                    self.env["f3d.source"].search_count([("code", "=", "GENSET-RELAY")]),
                    self.env["f3d.signal"].search_count([("code", "=like", "infra/genset/GENSET/%")]),
                    self.env["f3d.genset.event.map"].with_context(active_test=False).search_count([]))

        first = counts()
        self.run_hook()
        self.assertEqual(counts(), first)
        self.assertEqual(first, (1, 1, 26, 48))
        self.assertEqual(row.td_code, "LOP_SD")
        # збережений td_code відновлюється в порожній рядок
        row.td_code = False
        report = self.run_hook()
        self.assertEqual(report["td_codes"]["LOW_OIL_PRESSURE_SD"], "LOP_SD")

    def test_hook_meter_untouched_and_nextcall(self):  # AC-20, §5.3
        report = self.run_hook()
        self.assertFalse(self.genset_eq.f3d_meter_signal_id)
        self.assertEqual(report["meter"], "skipped: A-04")
        cron = self.cron("cron_f3d_genset_service")
        self.assertTrue(cron.active)
        local = cron.nextcall.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Kyiv"))
        self.assertEqual((local.hour, local.minute), (6, 0))
        self.assertGreater(cron.nextcall, fields.Datetime.now())

    def test_neutralize_sql(self):  # AC-35
        self.run_hook()
        link = self.eq_link()
        link.write({"last_event_id": 5})
        link.flush_recordset()
        self.env.cr.execute(file_open("factory3d_genset/neutralize.sql").read())
        self.env.invalidate_all()
        for xml_id in CRONS:
            self.assertFalse(self.cron(xml_id).active)
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("factory3d.genset.read_enabled"), "False")
        self.assertEqual(icp.get_param("factory3d.genset.requests_enabled"), "False")
        self.assertEqual(link.last_event_id, 0)

    def test_uninstall_hook(self):  # AC-35
        self.run_hook()
        req = self.env["maintenance.request"].create({
            "name": "Заявка GENSET", "equipment_id": self.genset_eq.id, "f3d_genset_event_key": "GENSET:X"})
        hooks.uninstall_hook(self.env)
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.search_count([("key", "=like", "factory3d.genset.%")]), 0)
        source = self.env["f3d.source"].with_context(active_test=False).search([("code", "=", "GENSET-RELAY")])
        self.assertFalse(source.active)
        self.assertEqual(self.env["f3d.signal"].search_count([("code", "=like", "infra/genset/GENSET/%")]), 26)
        self.assertTrue(req.exists())

    def test_signals_appendix_a_fields(self):  # AC-62 (Додаток A)
        from ..adapters import telemetry
        self.run_hook()
        signals = self.env["f3d.signal"].search([("code", "=like", "infra/genset/GENSET/%")])
        by_leaf = {s.code.rsplit("/", 1)[1]: s for s in signals}
        self.assertEqual(sorted(by_leaf), sorted(row[0] for row in telemetry.SIGNALS))
        for leaf, name, unit, kind, _stale in telemetry.SIGNALS:
            sig = by_leaf[leaf]
            self.assertTrue(sig.name.endswith(name), leaf)
            self.assertEqual((sig.unit or "", sig.kind), (unit, kind), leaf)
            self.assertEqual(sig.equipment_id, self.genset_eq, leaf)
            self.assertEqual((sig.source_id.code, sig.module), ("GENSET-RELAY", "genset"), leaf)
            self.assertEqual((sig.period_s, sig.store_period_s, sig.viewer_visible), (100, 0, True), leaf)
        by_leaf["p_kw"].write({"name": "змінено вручну"})
        self.run_hook()
        self.assertEqual(by_leaf["p_kw"].name, "змінено вручну")
