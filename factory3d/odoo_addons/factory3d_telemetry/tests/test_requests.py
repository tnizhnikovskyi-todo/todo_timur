from datetime import timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from ..tools.titles import fmt_num, render_title
from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d_telemetry")
NOW = "2026-10-14 06:00:00"


class RequestCase(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def setUp(self):
        super().setUp()
        frozen = freeze_time(NOW)
        self.frozen = frozen.start()
        self.addCleanup(frozen.stop)

    def requests(self, sig):
        return self.env["maintenance.request"].search([("f3d_signal_id", "=", sig.id)])

    def chatter(self, rec):
        return " | ".join(rec.message_ids.mapped("body"))


@tagged(*TAGS)
class TestOpenRequest(RequestCase):
    def test_request_fields(self):
        res = self.push([self.rd(self.sig_rv, 285.2)])
        self.assertEqual(res["alarms_opened"], 1)
        req = self.requests(self.sig_rv)
        self.assertEqual(len(req), 1)
        self.assertEqual(req.name, "Заміна фільтрів: перепад тиску 285 Па при нормі до 250")
        self.assertEqual(req.equipment_id, self.eq_rv)
        self.assertEqual(req.maintenance_type, "corrective")
        self.assertEqual(req.maintenance_team_id, self.team_mech)
        self.assertEqual(req.priority, "2")
        first = self.env["maintenance.stage"].search([("done", "=", False)], order="sequence, id", limit=1)
        self.assertEqual(req.stage_id, first)
        self.assertEqual(req.f3d_equipment_code, "RV-05-T")
        self.assertEqual(req.f3d_origin, "threshold")
        self.assertAlmostEqual(req.f3d_value, 285.2)
        self.assertEqual(req.f3d_threshold, 250)
        self.assertEqual(req.request_date, fields.Date.today())
        for part in ("ventilation/units/RV-05-T/filter_dp_pa", "BAC-T-105", "14.10.2026 09:00"):
            self.assertIn(part, req.description)
        self.assertEqual(self.sig_rv.maintenance_request_id, req)

    def test_default_team(self):
        self.sig_rv.equipment_id = self.eq_other
        self.push([self.rd(self.sig_rv, 285.2)])
        self.assertEqual(self.requests(self.sig_rv).maintenance_team_id, self.team_default)


@tagged(*TAGS)
class TestTitles(RequestCase):
    def test_titles(self):
        sig = self.sig_bat
        self.assertEqual(render_title(sig, 14.2, "від", 15.0), "Зарядити АКБ: заряд 14,2 % при нормі від 15")
        self.assertEqual(
            render_title(self.sig_press, 5.9, "від", 6.0), "Компресорна станція: тиск 5,9 бар при нормі від 6"
        )
        self.sig_press.alarm_title = False
        self.sig_press.name = "Тиск на виході"
        self.assertEqual(render_title(self.sig_press, 5.9, "від", 6.0), "Тиск на виході: 5,9 бар при нормі від 6 бар")
        self.sig_cstate.alarm_title = False
        self.sig_cstate.name = "Компресор"
        self.assertEqual(render_title(self.sig_cstate, 0, "від", 0, "fault"), "Компресор: стан «fault»")
        self.sig_rv.alarm_title = "Запиленість {value} % при нормі до {threshold}"
        self.assertEqual(render_title(self.sig_rv, 92, "до", 90), "Запиленість 92 % при нормі до 90")

    def test_fmt_num(self):
        self.assertEqual(fmt_num(17900.2, 0), "17 900")
        self.assertEqual(fmt_num(18000, 0), "18 000")
        self.assertEqual(fmt_num(29761.2, 1), "29 761,2")
        self.assertEqual(fmt_num(-71.9, 1), "-71,9")
        self.assertEqual(fmt_num(6.0, 2), "6")
        self.assertEqual(fmt_num(0.0005, 2), "0")

    def test_unknown_placeholder(self):
        self.sig_rv.alarm_title = "{foo} {value}"
        self.assertEqual(render_title(self.sig_rv, 285.2, "до", 250.0), "{foo} 285")

    def test_truncate_256(self):
        self.sig_rv.alarm_title = "x" * 400 + " {value}"
        self.assertEqual(len(render_title(self.sig_rv, 285.2, "до", 250.0)), 256)


@tagged(*TAGS)
class TestDedup(RequestCase):
    def test_one_open_request(self):
        for i, v in enumerate((300, 260, 300, 239, 285)):
            self.push([self.rd(self.sig_rv, v, at=i * 10)])
        self.assertEqual(len(self.requests(self.sig_rv)), 1)

    def test_no_equipment(self):
        self.sig_rv.equipment_id = False
        self.push([self.rd(self.sig_rv, 300)])
        self.assertEqual(self.sig_rv.status, "alarm")
        self.assertFalse(self.requests(self.sig_rv))
        self.assertIn("Тривога без обладнання — заявку не створено", self.chatter(self.sig_rv))

    def test_create_request_off(self):
        self.sig_rv.create_request = False
        self.push([self.rd(self.sig_rv, 300)])
        self.assertEqual(self.sig_rv.status, "alarm")
        self.assertFalse(self.requests(self.sig_rv))


@tagged(*TAGS)
class TestClose(RequestCase):
    def test_close_back_to_ok(self):
        self.push([self.rd(self.sig_rv, 300)])
        req = self.sig_rv.maintenance_request_id
        self.set_sql(self.sig_rv, last_value=120.0)
        self.close(req)
        self.assertFalse(self.sig_rv.maintenance_request_id)
        self.assertEqual(self.sig_rv.request_closed_at, fields.Datetime.now())
        self.assertEqual(self.sig_rv.status, "ok")
        self.assertIn("Заявку %s закрито; стан: Норма" % req.name, self.chatter(self.sig_rv))

    def test_close_still_alarm_cooldown(self):
        self.push([self.rd(self.sig_rv, 300)])
        req = self.sig_rv.maintenance_request_id
        self.close(req)
        self.assertEqual(self.sig_rv.status, "alarm")
        self.assertIn("Тривога триває, нова заявка не раніше 14.10.2026 10:00", self.chatter(self.sig_rv))
        self.frozen.move_to("2026-10-14 06:30:00")
        self.push([self.rd(self.sig_rv, 300, at=1800)])
        self.assertEqual(len(self.requests(self.sig_rv)), 1)
        self.frozen.move_to("2026-10-14 07:00:01")
        self.push([self.rd(self.sig_rv, 300, at=3601)])
        self.assertEqual(len(self.requests(self.sig_rv)), 2)


@tagged(*TAGS)
class TestReopenDelete(RequestCase):
    def test_reopen_relinks(self):
        self.push([self.rd(self.sig_rv, 300)])
        req = self.sig_rv.maintenance_request_id
        self.close(req)
        self.assertFalse(self.sig_rv.maintenance_request_id)
        self.reopen(req)
        self.assertEqual(self.sig_rv.maintenance_request_id, req)

    def test_delete_sets_closed_at(self):
        self.push([self.rd(self.sig_rv, 300)])
        req = self.sig_rv.maintenance_request_id
        req.with_user(self.user_admin).sudo().unlink()
        self.assertFalse(self.sig_rv.maintenance_request_id)
        self.assertEqual(self.sig_rv.request_closed_at, fields.Datetime.now())
        self.assertTrue(self.sig_rv.request_closed_at - timedelta(seconds=1) <= fields.Datetime.now())
