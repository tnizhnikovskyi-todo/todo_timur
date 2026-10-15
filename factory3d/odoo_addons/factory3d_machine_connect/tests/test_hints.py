"""AC-21…AC-24: підказки причини з подій верстата, режиму й черги; заявка ТО з тривоги (R-07, R-08)."""

from unittest.mock import patch

from odoo.tests import tagged

from .common import F3DMachineCase, kt
from .test_downtime import DowntimeMixin


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestHints(DowntimeMixin, F3DMachineCase):
    def ev(self, *args, **kw):
        """EV-01 як від плагіна. Обхід дефекту telemetry: `_f3d_handler_models` не знаходить обробників
        (`registry.descendants` повертає імена, а не класи) — підставляємо обробник модуля."""
        handler = type(self.env["f3d.push.handler"])
        with patch.object(handler, "_f3d_handler_models", lambda self, route: ["f3d.push.handler.machine_connect"]):
            return self.ev_ua(*args, **kw)

    def _assert_e0421(self, m, dt):
        self.assertEqual(dt.loss_id, self.env.ref("mrp.block_reason1"))
        self.assertEqual((dt.reason_source, dt.reason_state), ("hint", "to_confirm"))
        self.assertEqual(dt.hint_text, "E0421 Помилка шпинделя осі Z")
        event = self.env["f3d.machine.event"].search([("machine_id", "=", m.id)])
        self.assertEqual(len(event), 1)
        self.assertEqual(dt.event_id, event)
        self.assertEqual(event.downtime_id, dt)

    def test_event_after_state(self):
        """AC-21: ERROR @09:42:00, EV-01 @09:42:01 → причина «Поломка» з підказки; дублікат ігнорується."""
        m = self.m_ua
        self.feed(self.ua(m, "09:42:00", state="ERROR"))
        self.ev(m, "E0421", 5, "Помилка шпинделя осі Z", "09:42:01")
        self.env.invalidate_all()
        self._assert_e0421(m, m.current_downtime_id)
        self.ev(m, "E0421", 5, "Помилка шпинделя осі Z", "09:42:01")
        self.assertEqual(self.env["f3d.push.event"].sudo().search_count([("route", "=", "mc_opcua")]), 1)
        self.assertEqual(self.env["f3d.machine.event"].search_count([("machine_id", "=", m.id)]), 1)

    def test_event_before_state(self):
        """AC-21 (зворотний порядок): подія раніше за стан на ≤ 120 с — те саме."""
        m = self.m_ua
        self.ev(m, "E0421", 5, "Помилка шпинделя осі Z", "09:41:30")
        self.feed(self.ua(m, "09:42:00", state="ERROR"))
        self._assert_e0421(m, m.current_downtime_id)

    def test_setup_hint(self):
        """AC-22: READY + SETUP → простій setup, причина «Налагодження»; закриття → запис із завданням."""
        m = self.m_ua
        wo = self.make_mo(self.wc_ua).workorder_ids[:1]
        self.set_sql(m, active_workorder_id=wo.id)
        self.feed(self.ua(m, "09:00:00", state="READY", mode="SETUP"))
        dt = m.current_downtime_id
        self.assertEqual(dt.state_kind, "setup")
        self.assertEqual(dt.loss_id, self.env.ref("mrp.block_reason2"))
        self.assertEqual(dt.reason_source, "hint")
        self.feed(self.ua(m, "09:10:00", state="WORKING", mode="AUTOMATIC"))
        rec = self.records(dt)
        self.assertEqual(len(rec), 1)
        self.assertEqual((rec.workorder_id, rec.loss_id), (wo, self.env.ref("mrp.block_reason2")))
        self.assertEqual((rec.date_start, rec.date_end), (kt("09:00"), kt("09:10")))

    def test_idle_blocked_hint_not_applied(self):
        """AC-23: на РЦ лише `blocked` → підказка «Очікування матеріалу» без застосування."""
        m = self.m_ua
        mo = self.make_mo(self.wc_ua)
        mo.workorder_ids[:1].write({"state": "blocked"})
        self.feed(self.ua(m, "09:00:00", state="READY"))
        dt = m.current_downtime_id
        self.assertEqual(dt.state_kind, "idle")
        self.assertEqual(dt.hint_loss_id, self.env.ref("mrp.block_reason0"))
        self.assertIn(mo.name, dt.hint_text)
        self.assertEqual(dt.loss_id, self.env.ref("factory3d_machine_connect.loss_unknown"))
        self.assertEqual(dt.reason_state, "to_classify")

    def test_alarm_request_linked_once(self):
        """AC-24: тривога + ERROR → одна заявка ТО, прив'язана до простою; EV-01 дописується в чатер."""
        m = self.m_ua
        self.feed(self.ua(m, "09:42:00", state="ERROR", alarm=True))
        requests = self.env["maintenance.request"].search([("equipment_id", "=", self.eq_ua.id)])
        self.assertEqual(len(requests), 1)
        dt = m.current_downtime_id
        self.assertEqual(dt.maintenance_request_id, requests)
        self.ev(m, "E0421", 5, "Помилка шпинделя осі Z", "09:42:01")
        self.env.invalidate_all()
        bodies = " ".join(requests.message_ids.mapped("body"))
        self.assertIn("Подія верстата: E0421 Помилка шпинделя осі Z", bodies)
        self.assertEqual(self.env["maintenance.request"].search_count([("equipment_id", "=", self.eq_ua.id)]), 1)

    def test_plain_event_is_not_archived(self):
        """Стенд ТК-02: звичайна подія (не тривога) з `active=false` не архівується, лишається у «Подіях верстатів»."""
        m = self.m_ua
        self.ev(m, "", 0, "CNC-2: Помилка шпинделя осі Z", "09:42:01", kind="event", active=False)
        self.assertEqual(self.env["f3d.machine.event"].search_count([("machine_id", "=", m.id)]), 1)

    def test_request_before_fault_goes_to_fault_downtime(self):
        """Стенд ТК-02: заявка з тривоги, створена до переходу в `fault`, не прив'язується до простою «Очікування»."""
        m = self.m_ua
        self.feed(self.ua(m, "09:40:00", state="READY"))
        idle = m.current_downtime_id
        self.assertEqual(idle.state_kind, "idle")
        req = self.env["maintenance.request"].create(
            {
                "name": "Верстат: аварія",
                "equipment_id": self.eq_ua.id,
                "f3d_signal_id": m.sig_alarm_id.id,
                "maintenance_team_id": self.team_mech.id,
            }
        )
        self.assertFalse(idle.maintenance_request_id)
        self.feed(self.ua(m, "09:42:00", state="ERROR", alarm=True))
        self.assertEqual(m.current_downtime_id.state_kind, "fault")
        self.assertEqual(m.current_downtime_id.maintenance_request_id, req)
