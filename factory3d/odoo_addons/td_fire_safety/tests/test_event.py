"""AC-12…AC-16, AC-68 (M-05, R-14, M-18): журнал подій."""

import re
from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import FireCase


class EventCase(FireCase):
    def log(self, etype="fault", code="FA-CUT", ts=None, text="Тест", **kw):
        return self.env["td.fire.event"]._log(etype, code, ts or self.T0, text, **kw)


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestEventLog(EventCase):
    def test_dedup_bucket(self):
        e1 = self.log(ts=self.at(0))
        e2 = self.log(ts=self.at(1))
        self.assertEqual(e1, e2)
        e3 = self.log(ts=self.at(3))
        self.assertNotEqual(e1, e3)
        self.assertEqual(
            self.env["td.fire.event"].search_count([("etype", "=", "fault"), ("object_code", "=", "FA-CUT")]), 2
        )

    def test_dedup_fills_message(self):
        e1 = self.log(ts=self.at(0))
        self.log(ts=self.at(1), message_text="від приладу")
        self.assertEqual(e1.message_text, "від приладу")

    def test_links_and_scene_code(self):
        ev = self.log("alarm", "FA-CNC", zone_id=self.z_cnc.id, device_id=self.dev_cnc05.id)
        self.assertEqual(ev.scene_code, "FA-CNC")
        self.assertEqual((ev.kind, ev.level), ("alarm", "alarm"))
        mcp = self.env["td.fire.device"].search([("type", "=", "mcp")], limit=1)
        ev2 = self.log("fault", mcp.address, device=mcp)
        self.assertEqual(ev2.scene_code, "FA-MCP")
        ev3 = self.log("loop_fault", "FACP-1", loop=self.loop2)
        self.assertEqual(ev3.scene_code, "FACP-1")

    def test_write_restricted(self):
        ev = self.log()
        with self.assertRaises(AccessError):
            ev.with_user(self.u).write({"text": "інше"})
        ev.with_user(self.u).write({"note": "коментар"})
        ev.with_user(self.u).write({"ack": True})
        self.assertTrue(ev.ack)
        self.assertEqual(ev.note, "коментар")

    def test_unlink_forbidden(self):
        ev = self.log()
        with self.assertRaises(UserError):
            ev.with_user(self.a).unlink()
        with self.assertRaises(UserError):
            ev.sudo().unlink()
        ev.sudo().with_context(f3d_fire_allow_unlink=True).unlink()
        self.assertFalse(ev.exists())

    def test_manual_create(self):
        Event = self.env["td.fire.event"]
        with self.assertRaises(AccessError):
            Event.with_user(self.u).create({"etype": "manual", "text": "x"})
        ev = Event.with_user(self.d).create({"etype": "manual", "text": "Обхід виконано"})
        self.assertEqual((ev.level, ev.source), ("info", "manual"))
        self.assertTrue(ev.dedup_key.startswith("manual:"))
        self.assertEqual(ev.object_code, "FACP-1")
        with self.assertRaises(AccessError):
            Event.with_user(self.d).create(
                {
                    "etype": "alarm",
                    "text": "x",
                    "level": "alarm",
                    "source": "manual",
                    "object_code": "FA-CUT",
                    "dedup_key": "k",
                }
            )

    def test_ack(self):
        ev = self.log("alarm", "FA-CUT", text="ТРИВОГА")
        self.assertTrue(ev.ack_required)
        self.assertFalse(self.log("fault", "FA-EB", ts=self.at(10)).ack_required)
        ev.with_user(self.u).action_ack()
        self.assertTrue(ev.ack)
        self.assertEqual(ev.ack_user_id, self.u)
        self.assertTrue(ev.ack_ts)
        with self.assertRaises(UserError):
            ev.with_user(self.u).write({"ack": False})

    def test_sanitize_payload(self):
        text = "А" * 300 + "\x00\x07" + "Б" * 300
        ev = self.log("info", "FACP-1", text=text)
        self.assertLessEqual(len(ev.text), 500)
        self.assertFalse(re.search(r"[\x00-\x08\x0a-\x1f\x7f]", ev.text))
        alarm = self.log("alarm", "FA-FAC", ts=self.at(20), text="Тривога")
        item = alarm._payload_item()
        self.assertEqual(item["level"], "bad")
        self.assertRegex(item["time"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(item["time"], "2026-10-14 10:00")  # 07:00 UTC = 10:00 за Києвом (EEST)
        self.assertEqual(item["code"], alarm.scene_code or "FA-FAC")


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestBacnetPush(EventCase):
    def setUp(self):
        super().setUp()
        self.handler = self.env["td.push.handler.fire"]
        if not self.panel.source_id and self.src_bac:
            self.panel.source_id = self.src_bac

    def payload(self, **kw):
        data = {
            "device": 200,
            "object": "LSZ",
            "instance": 14,
            "event_type": "change-of-life-safety",
            "from_state": "quiet",
            "to_state": "test-alarm",
            "mode": "on",
            "message_text": "Тест: сповіщувач 2.CNC.05, Присадка",
            "ts": "2026-10-14T07:10:02Z",
        }
        data.update(kw)
        return {"payload": data}

    def test_attach_message(self):
        ts = self.T0 + timedelta(minutes=10)
        ev = self.log("test", "FA-CNC", ts=ts, zone_id=self.z_cnc.id)
        self.handler._td_handle_push("bacnet_event", self.payload(ts="2026-10-14T07:10:03Z"))
        self.assertEqual(ev.message_text, "Тест: сповіщувач 2.CNC.05, Присадка")
        self.assertEqual(ev.device_id, self.dev_cnc05)

    def test_new_bacnet_event(self):
        before = self.env["td.fire.event"].search_count([("etype", "=", "bacnet")])
        self.handler._td_handle_push("bacnet_event", self.payload())
        self.assertEqual(self.env["td.fire.event"].search_count([("etype", "=", "bacnet")]), before + 1)

    def test_invalid_payload(self):
        data = self.payload()
        del data["payload"]["instance"]
        with self.assertRaises(ValueError):
            self.handler._td_handle_push("bacnet_event", data)

    def test_control_chars(self):
        self.handler._td_handle_push("bacnet_event", self.payload(message_text="Тест\x00\x07 зона"))
        ev = self.env["td.fire.event"].search([("etype", "=", "bacnet")], limit=1)
        self.assertFalse(re.search(r"[\x00-\x08\x0a-\x1f\x7f]", ev.message_text))
