from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.tests import tagged

from ..adapters import telemetry
from .test_rules import SERVICE_DEFAULT, TD, GensetCase


@tagged("post_install", "-at_install")
class TestService(GensetCase):
    def setUp(self):
        super().setUp()
        self.Request = self.env["maintenance.request"]
        self.hours_sig = self.env["td.signal"].search([("code", "=", telemetry.prefix("GENSET") + "hours")])

    def requests(self, key=None):
        domain = [("equipment_id", "=", self.genset_eq.id), ("td_genset_event_key", "like", key or "GENSET:")]
        return self.Request.search(domain)

    def service(self, **over):
        return mock.patch(TD + ".service_info", return_value={**SERVICE_DEFAULT, **over})

    def old_reading(self):
        ts = fields.Datetime.now().replace(microsecond=0) - timedelta(days=29, hours=23)
        self.env["td.signal"]._f3d_ingest(
            [{"code": self.hours_sig.code, "ts": ts, "value": 1177.0, "q": "good"}], src="module"
        )

    def test_planned_request(self):  # AC-18
        self.old_reading()
        with self.service():
            self.env["td.genset3d.link"]._cron_service()
            req = self.requests()
            self.assertEqual(len(req), 1)
            self.assertEqual(
                req.name, "Генератор GENSET: планове ТО через 37 мотогодин (наступне на 1 250, зараз 1 213)"
            )
            self.assertEqual((req.priority, req.maintenance_type), ("1", "preventive"))
            self.assertEqual(req.td_genset_event_key, "GENSET:SERVICE:1250")
            self.assertEqual(req.td_signal_id, self.hours_sig)
            days = (req.schedule_date - fields.Datetime.now()).total_seconds() / 86400
            self.assertAlmostEqual(days, 30.8, delta=1.0)
            self.env["td.genset3d.link"]._cron_service()
            self.assertEqual(len(self.requests()), 1)

    def test_overdue_and_not_due(self):  # AC-19
        with self.service(hours_left=-12.0, hours_now=1262.0, due=True):
            self.env["td.genset3d.link"]._cron_service()
            req = self.requests()
            self.assertEqual(len(req), 1)
            self.assertIn("прострочено на 12 мотогодин", req.name)
            self.assertEqual(req.priority, "3")
            self.assertLess(abs((req.schedule_date - fields.Datetime.now()).total_seconds()), 120)
        req.unlink()
        with self.service(hours_left=120.0, due=False):
            self.env["td.genset3d.link"]._cron_service()
        self.assertFalse(self.requests())

    def test_requests_disabled(self):
        self.set_param("requests_enabled", "False")
        with self.service(hours_left=-12.0, due=True):
            self.env["td.genset3d.link"]._cron_service()
        self.assertFalse(self.requests())

    def test_td_creates_requests(self):  # AC-21, R-09 крок 1
        td_req = self.Request.create(
            {"name": "ТО-1: кожні 250 мотогодин", "maintenance_type": "preventive", "equipment_id": self.genset_eq.id}
        )
        self.assertFalse(td_req.td_signal_id)
        total = self.Request.search_count([("equipment_id", "=", self.genset_eq.id)])
        with mock.patch(TD + ".SERVICE_REQUESTS_BY_TD", True), self.service(hours_left=-12.0, due=True):
            self.env["td.genset3d.link"]._cron_service()
        self.assertEqual(td_req.td_signal_id, self.hours_sig)
        self.assertEqual(td_req.td_equipment_code, "GENSET")
        self.assertEqual(self.Request.search_count([("equipment_id", "=", self.genset_eq.id)]), total)
        self.assertFalse(self.requests())

    def test_service_event(self):  # AC-64
        t0 = fields.Datetime.now().replace(microsecond=0) - timedelta(hours=1)
        events = [
            {
                "id": i,
                "ts": t0 + timedelta(seconds=i),
                "code": "",
                "severity": "warning",
                "name": "Maintenance Due Warning",
                "value": None,
                "unit": None,
                "threshold": None,
                "text": "",
            }
            for i in (1, 2)
        ]
        with (
            mock.patch(TD + ".events_since", return_value=events),
            self.service(hours_left=37.0, due=True),
            mock.patch(
                "odoo.addons.td_genset_factory3d.models.genset_link_events.F3dGensetLinkEvents._notify_bus_state"
            ) as notify,
        ):
            self.env["td.genset3d.link"]._cron_events()
        self.assertEqual(len(self.requests("GENSET:MAINTENANCE_DUE_W")), 0)
        self.assertEqual(len(self.requests("GENSET:SERVICE:1250")), 1)
        notify.assert_called()
