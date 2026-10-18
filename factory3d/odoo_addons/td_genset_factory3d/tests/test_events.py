from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .test_rules import TD, GensetCase

LINK = "odoo.addons.td_genset_factory3d.models.genset_link_events.F3dGensetLinkEvents"


@tagged("post_install", "-at_install")
class TestEvents(GensetCase):
    def setUp(self):
        super().setUp()
        self.events = []
        self.t0 = fields.Datetime.now().replace(microsecond=0) - timedelta(hours=1)

        def events_since(gen, since=None, limit=200):
            rows = [e for e in self.events if since is None or e["ts"] > since]
            return rows[:limit]

        patcher = mock.patch(TD + ".events_since", side_effect=events_since)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.Request = self.env["maintenance.request"]
        self.Map = self.env["td.genset.event.map"]

    def ev(self, id_, name, severity, code="", value=None, unit=None, threshold=None, text=""):
        event = {
            "id": id_,
            "ts": self.t0 + timedelta(seconds=id_),
            "code": code,
            "severity": severity,
            "name": name,
            "value": value,
            "unit": unit,
            "threshold": threshold,
            "text": text,
        }
        self.events.append(event)
        return event

    def requests(self, key=None):
        domain = [("equipment_id", "=", self.genset_eq.id), ("td_genset_event_key", "!=", False)]
        if key:
            domain = [("equipment_id", "=", self.genset_eq.id), ("td_genset_event_key", "=", key)]
        return self.Request.search(domain)

    def run_events(self):
        self.env["td.genset.link"]._cron_events()

    def done_stage(self):
        return self.env["maintenance.stage"].search([("done", "=", True)], limit=1)

    def test_shutdown_request(self):  # AC-12
        self.ev(1, "Low Oil Pressure", "shutdown", "LOP_SD", 0.8, "бар", 1.0)
        self.run_events()
        req = self.requests()
        self.assertEqual(len(req), 1)
        self.assertEqual(
            req.name, "Генератор GENSET: аварійна зупинка — низький тиск оливи 0,8 бар при нормі ≥ 1,0 бар"
        )
        self.assertEqual(req.priority, "3")
        self.assertEqual(req.maintenance_type, "corrective")
        self.assertEqual(req.equipment_id, self.genset_eq)
        self.assertEqual(req.td_equipment_code, "GENSET")
        self.assertTrue(req.td_signal_id.code.endswith("/alarm_level"))
        self.assertEqual(req.td_value, 0.8)
        self.assertEqual(req.td_threshold, 1.0)
        self.assertEqual(req.td_genset_event_key, "GENSET:LOW_OIL_PRESSURE_SD")
        self.assertTrue(req.maintenance_team_id)
        self.assertLess(abs((req.schedule_date - fields.Datetime.now()).total_seconds()), 120)

    def test_repeat_and_reopen(self):  # AC-13
        self.ev(1, "Low Oil Pressure", "shutdown", "LOP_SD", 0.8, "бар", 1.0)
        self.run_events()
        self.ev(2, "Low Oil Pressure", "shutdown", "LOP_SD", 0.8, "бар", 1.0)
        self.run_events()
        req = self.requests()
        self.assertEqual(len(req), 1)
        self.assertIn("Повтор:", " ".join(req.message_ids.mapped("body")))
        req.write({"stage_id": self.done_stage().id})
        self.ev(3, "Low Oil Pressure", "shutdown", "LOP_SD", 0.8, "бар", 1.0)
        self.run_events()
        self.assertEqual(len(self.requests()), 2)

    def test_bus_only(self):  # AC-14
        self.ev(1, "Genset Over Current", "warning")
        with mock.patch(LINK + "._notify_bus_state") as notify:
            self.run_events()
        self.assertFalse(self.requests())
        notify.assert_called()

    def test_default_shutdown(self):  # AC-15
        self.ev(1, "Щось нове", "shutdown")
        self.run_events()
        req = self.requests()
        self.assertEqual(req.td_genset_event_key, "GENSET:DEFAULT_SHUTDOWN")
        self.assertEqual(req.name, "Генератор GENSET: аварійна зупинка — Щось нове")
        self.assertEqual((req.priority, req.maintenance_type), ("3", "corrective"))

    def test_requests_disabled(self):  # AC-16
        self.set_param("requests_enabled", "False")
        self.ev(1, "Low Oil Pressure", "shutdown")
        self.run_events()
        self.assertFalse(self.requests())
        self.assertFalse(self.link.last_event_ts)

    def test_batch_200(self):  # AC-17
        for i in range(1, 251):
            self.ev(i, "Genset Over Current", "warning")
        self.run_events()
        self.assertEqual(self.link.last_event_id, 200)
        self.run_events()
        self.assertEqual(self.link.last_event_id, 250)

    def test_map_data(self):  # AC-63
        rows = self.Map.search([])
        self.assertEqual(len(rows), 48)
        for table, count in (("warning", 17), ("shutdown", 24), ("other", 7)):
            self.assertEqual(len(rows.filtered(lambda r, t=table: r.hgm_table == t)), count, table)
        for row in rows.filtered(lambda r: r.hgm_table == "shutdown"):
            self.assertEqual((row.action, row.priority), ("request_corrective", "3"), row.key)
        self.assertTrue(all(rows.mapped("name_tpl")))

    def test_match_severity(self):  # AC-63
        self.assertEqual(
            self.Map._match({"name": "Low Oil Pressure", "severity": "warning", "code": ""}).key, "LOW_OIL_PRESSURE_W"
        )
        self.assertEqual(
            self.Map._match({"name": "Low Oil Pressure", "severity": "shutdown", "code": ""}).key, "LOW_OIL_PRESSURE_SD"
        )
        self.assertEqual(
            self.Map._match({"name": "low oil pressure", "severity": "shutdown", "code": ""}).key, "LOW_OIL_PRESSURE_SD"
        )
        by_code = self.Map._match({"name": "x", "severity": "warning", "code": "high_temp_warning"})
        self.assertEqual(by_code.key, "HIGH_TEMP_W")  # td_code (Q-13)
        regex = self.Map.create(
            {"key": "RX", "severity": "warning", "name_tpl": "x", "match_regex": r"^zz\d+$", "sequence": 5}
        )
        self.assertEqual(self.Map._match({"name": "ZZ12", "severity": "warning", "code": ""}), regex)
        regex.active = False
        self.assertEqual(self.Map._match({"name": "ZZ12", "severity": "warning", "code": ""}).key, "DEFAULT_WARNING")

    def test_command_ignored(self):  # AC-63
        ev = {"id": 1, "ts": self.t0, "name": "Remote start", "severity": "command", "code": ""}
        row = self.Map._match(ev)
        self.assertFalse(row)
        with mock.patch(LINK + "._notify_bus_state") as notify:
            self.link._apply_event(ev, row)
        self.assertFalse(self.requests())
        notify.assert_not_called()

    def test_template_validation(self):  # AC-61
        Map = self.Map.with_user(self.user_manager)
        for tpl in ("{name.__class__}", "{value[0]}", "{foo}"):
            with self.assertRaises(ValidationError, msg=tpl) as cm:
                Map.create({"key": "T-" + tpl, "severity": "warning", "name_tpl": tpl})
            self.assertIn("дозволені лише поля", str(cm.exception))
        ok = Map.create({"key": "T-OK", "severity": "warning", "name_tpl": "{code}: {name} {value}"})
        self.assertTrue(ok)
        with self.assertRaises(AccessError):
            self.Map.with_user(self.user_reader).create({"key": "T-R", "severity": "warning", "name_tpl": "x"})

    def test_injection_event(self):  # AC-61
        self.ev(1, "<script>alert(1)</script>", "shutdown", "../x; DROP TABLE", text="a" * 10240)
        self.run_events()
        req = self.requests()
        self.assertEqual(req.td_genset_event_key, "GENSET:DEFAULT_SHUTDOWN")
        self.assertIn("&lt;script&gt;", req.description)
        self.assertNotIn("<script>", req.description)
        self.assertLessEqual(len(req.name), 120)

    def test_close_request_status(self):  # R-08, AC-55
        self.ev(1, "Low Oil Pressure", "shutdown", "LOP_SD", 0.8, "бар", 1.0)
        self.run_events()
        req = self.requests()
        signal = req.td_signal_id
        self.snap(alarms=[{"code": "low_oil_pressure_shutdown", "name": "x", "severity": "shutdown"}])
        self.link._publish_one()
        self.assertEqual(signal.status, "alarm")
        req.write({"stage_id": self.done_stage().id})
        self.assertEqual(signal.status, "alarm")
        self.assertIn("закрито", " ".join(self.link.message_ids.mapped("body")))
        self.snap(ts=fields.Datetime.now().replace(microsecond=0) + timedelta(seconds=30))
        self.link._publish_one()
        self.assertEqual(signal.status, "ok")

    def test_comm_lost_once(self):  # AC-40
        self.link._on_comm_lost()
        self.link._on_comm_lost()
        req = self.requests("GENSET:COMM_LOST")
        self.assertEqual(len(req), 1)
        self.assertIn("втрачено зв'язок з контролером", req.name)
        self.assertTrue(req.td_signal_id.code.endswith("/online"))
        self.link._on_comm_restored()
        self.assertIn("Зв'язок відновлено", " ".join(req.message_ids.mapped("body")))
        self.assertFalse(req.stage_id.done)
