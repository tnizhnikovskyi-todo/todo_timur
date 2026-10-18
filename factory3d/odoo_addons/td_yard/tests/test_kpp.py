import time
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, new_test_user, tagged

from ..tools import params as P
from .flow import at, freeze
from .gate_case import GateCase, capture_ms, lpr_event


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardKpp(GateCase):
    def _arrived(self, plate, book=True, **vals):
        visit = self._visit(plate=plate, batch_id=self._batch().id, **vals)
        if book:
            self._booking(visit, self.dock_t1, at(13), at(14), confirm=True)
        visit.action_arrive(ts=at(12, 40))
        return visit

    def _data(self, user=None):
        Visit = self.env["td.yard.visit"].with_user(user or self.user_guard)
        return Visit.kpp_data()

    def test_kpp_data(self):  # AC-56
        T = at(12, 45)
        with freeze(T):
            green = self._arrived("АА1234КТ")
            yellow = self._arrived("АА5555КТ", book=False, is_walk_in=True)
            ev = self.recv(lpr_event(1, plateText="ZZ9999ZZ", plateUnicode=None, capture_timestamp=capture_ms(T)))
            self.assertTrue(ev.kpp_alert)
            data = self._data()
        for key in (
            "now",
            "refresh_s",
            "read_enabled",
            "write_enabled",
            "can",
            "gates",
            "scale",
            "at_gate",
            "in_yard",
            "events",
        ):
            self.assertIn(key, data)
        cards = {c["visit_id"]: c for c in data["at_gate"]}
        self.assertEqual(cards[green.id]["color"], "green")
        self.assertEqual(cards[green.id]["actions"], ["admit", "reject"])
        self.assertEqual(cards[green.id]["slot"], "13:00–14:00")
        self.assertEqual(cards[yellow.id]["color"], "yellow")
        card_ev = next(e for e in data["events"] if e["id"] == ev.id)
        self.assertEqual(card_ev["actions"], ["walk_in", "reject", "link", "dismiss"])
        self.assertEqual(card_ev["color"], "yellow")
        self.assertFalse(data["can"]["command"] and data["write_enabled"] is False)
        P.set_param(self.env, "write_enabled", "False")
        with freeze(T):
            data = self._data()
        self.assertFalse(data["can"]["command"])
        self.assertIn("write_enabled", data["can"]["command_reason"])
        self.assertTrue(all("write_enabled" in (g["command_block"] or "") for g in data["gates"]))
        with self.assertRaises(AccessError):
            self.env["td.yard.visit"].with_user(self.user_reader).kpp_data()

    def test_views(self):  # AC-53
        Visit, Booking = self.env["td.yard.visit"], self.env["td.yard.booking"]
        views = Visit.get_views([(False, t) for t in ("kanban", "list", "form", "pivot", "graph", "search")])
        self.assertEqual(len(views["views"]), 6)
        views = Booking.get_views([(False, t) for t in ("calendar", "list", "form", "search")])
        self.assertEqual(len(views["views"]), 4)
        self.assertEqual(len(Visit._group_expand_states(Visit, [])), 7)

    def test_kpp_in_yard_and_colors(self):
        with freeze(at(12, 45)):
            visit = self._arrived("АА1234КТ")
            visit.action_admit(open_gate=False)
            dev = self._arrived("АА2222КТ", book=False)
            dev.action_admit(open_gate=False)
            dev.sudo().write({"weight_check": "deviation"})
            handling = self._arrived("АА3333КТ", book=False)
            handling.action_admit(open_gate=False)
            handling.action_call_to_dock()
            data = self._data()
        by_id = {c["visit_id"]: c for c in data["in_yard"]}
        self.assertEqual(by_id[visit.id]["actions"], ["call", "weigh", "leave"])
        self.assertEqual(by_id[visit.id]["color"], "green")
        self.assertEqual(by_id[dev.id]["color"], "red")
        self.assertEqual(by_id[handling.id]["color"], "blue")
        self.assertEqual(by_id[handling.id]["actions"], ["weigh", "leave"])
        self.assertEqual(data["at_gate"], [])

    def test_kpp_unassigned_weighing_card(self):
        scale = self.env.ref("td_yard.scale_truck")
        w = (
            self.env["td.yard.weighing"]
            .sudo()
            .create(
                {"scale_id": scale.id, "kind": "check", "weight_kg": 21000.0, "state": "unassigned", "source": "auto"}
            )
        )
        data = self._data()
        card = next(c for c in data["unassigned_weighings"] if c["id"] == w.id)
        self.assertEqual((card["color"], card["actions"]), ("red", ["assign_weighing"]))
        self.assertEqual(data["scale"]["code"], "TRUCK-SCALE")

    def test_kpp_action(self):  # AC-57
        Visit = self.env["td.yard.visit"].with_user(self.user_guard)
        with freeze(at(12, 45)):
            visit = self._arrived("АА1234КТ")
            P.set_param(self.env, "write_enabled", "False")
            res = Visit.kpp_action("admit", visit_id=visit.id)
            self.assertTrue(res["ok"])
            self.assertEqual(visit.state, "queued")
            res = Visit.kpp_action("weigh", visit_id=visit.id, values={"weight_kg": 25200})
            weighing = visit.weighing_ids
            self.assertEqual((weighing.source, weighing.weight_kg, weighing.kind), ("manual", 25200.0, "in"))
            self.assertIsNone(res["action"])
            other = self._arrived("АА7777КТ", book=False)
            res = Visit.kpp_action("reject", visit_id=other.id)
            self.assertEqual(res["action"]["res_model"], "td.yard.reject.wizard")
            self.assertEqual(res["action"]["context"]["kpp"], 1)
            ev = self.recv(
                lpr_event(2, plateText="ZZ9999ZZ", plateUnicode=None, capture_timestamp=capture_ms(at(12, 44)))
            )
            res = Visit.kpp_action("walk_in", event_id=ev.id)
            self.assertEqual(res["action"]["res_model"], "td.yard.walkin.wizard")
            res = Visit.kpp_action("dismiss", event_id=ev.id)
            self.assertTrue(res["ok"])
            self.assertFalse(ev.kpp_alert)
            with self.assertRaises(UserError):
                Visit.kpp_action("unknown")
            with self.assertRaises(UserError):  # команди вимкнено
                Visit.kpp_action("open", gate_id=self.gate_w.id)
            res = Visit.kpp_action("call", visit_id=visit.id)
            self.assertEqual(visit.state, "at_dock")
            res = Visit.kpp_action("leave", visit_id=visit.id)
            self.assertEqual(visit.state, "left")

    def test_kpp_action_open_and_link(self):
        Visit = self.env["td.yard.visit"].with_user(self.user_guard)
        now = at(12, 45)
        with freeze(now):
            self.put(self.gate_w, "photocell", 0, now)
            res = Visit.kpp_action("open", gate_id=self.gate_w.id)
            self.assertTrue(res["ok"])
            self.assertEqual(len(self.cmds()), 1)
            visit = self._arrived("АА1234КТ", book=False)
            ev = self.recv(lpr_event(3, plateText="ZZ9999ZZ", plateUnicode=None, capture_timestamp=capture_ms(now)))
            Visit.kpp_action("link", event_id=ev.id, visit_id=visit.id)
            self.assertEqual(ev.visit_id, visit)

    def test_bus_precommit(self):  # AC-64
        bus = self.env["bus.bus"]
        visit = self._visit(plate="АА1234КТ", batch_id=self._batch().id)
        self.env.cr.precommit.run()
        with patch.object(type(bus), "_sendone") as sendone:
            for _i in range(10):
                visit._f3d_yard_notify()
                self.gate_w._f3d_yard_notify()
            self.env.cr.precommit.run()
        calls = [c.args for c in sendone.call_args_list]
        self.assertEqual(sorted(a[2]["model"] for a in calls), ["td.yard.gate", "td.yard.visit"])
        self.assertTrue(all(a[0] == "f3d_yard" and a[1] == "f3d_yard/update" for a in calls))

    def test_viewer_notify(self):  # AC-64
        ev = MagicMock()
        visit = self._arrived("АА1234КТ", book=False)
        Visit = type(self.env["td.yard.visit"])
        with patch.object(Visit, "_f3d_yard_viewer_event", return_value=ev):
            with freeze(at(12, 50)):
                visit.action_admit(open_gate=False)
            ev._notify.assert_any_call("td.yard.visit", [visit.name, visit.scene_code, visit.dock_code], "doc")
            ev.reset_mock()
            self.gate_w._f3d_yard_notify()
            ev._notify.assert_called_once_with("td.yard.gate", ["GATE-W"], "state")
            ev.reset_mock()
            self.env.ref("td_yard.scale_truck")._f3d_yard_notify()
            ev._notify.assert_called_once_with("td.yard.scale", ["TRUCK-SCALE"], "state")

    def test_no_show_cron(self):  # R-19 п. 2
        P.set_param(self.env, "no_show_min", "120")
        visit = self._visit(plate="АА1234КТ", batch_id=self._batch().id)
        self._booking(visit, self.dock_t1, at(9), at(10), confirm=True)
        fresh = self._visit(plate="АА4321КТ", batch_id=self._batch().id)
        self._booking(fresh, self.dock_t2, at(12), at(13), confirm=True)
        with freeze(at(12, 5)):
            self.env["td.yard.visit"]._cron_queue()
        self.assertTrue(visit.is_no_show)
        self.assertFalse(fresh.is_no_show)

    def test_auto_call_next_cron(self):  # R-05 п. 4
        visit = self._arrived("АА1234КТ", book=False)
        with freeze(at(12, 50)):
            visit.action_admit(open_gate=False)
            self.env["td.yard.visit"]._cron_queue()
            self.assertEqual(visit.state, "queued")
            P.set_param(self.env, "auto_call_next", "True")
            self.env["td.yard.visit"]._cron_queue()
        self.assertEqual(visit.state, "at_dock")

    def test_kpp_data_speed(self):  # AC-58 (швидкодія)
        with freeze(at(12, 45)):
            for i in range(50):
                v = self._visit(plate="АА%04dКТ" % i)
                v.action_arrive(ts=at(12, 40))
            for i in range(20):
                self.recv(
                    lpr_event(
                        100 + i, plateText="ZZ%04dZZ" % i, plateUnicode=None, capture_timestamp=capture_ms(at(12, 44))
                    )
                )
            self._data()
            started = time.perf_counter()
            for _i in range(5):
                data = self._data()
            avg = (time.perf_counter() - started) / 5
        self.assertEqual(len(data["at_gate"]), 50)
        self.assertLess(avg, 1.0, "kpp_data занадто повільний: %.3f с" % avg)


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardKppTours(HttpCase):
    """Туры не залежать від години доби: «Сьогодні» рахує сервер за київською добою (Y-2), дата браузера (UTC на
    стенді) у фільтрі не бере участі; сам фільтр на межі діб перевіряє `TestYardTodayFilter` із замороженим годинником."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guard = new_test_user(
            cls.env,
            "yard_tour",
            groups="td_yard.group_td_yard_security,td_yard.group_td_yard_dispatcher",
        )
        P.set_param(cls.env, "write_enabled", "False")
        Visit = cls.env["td.yard.visit"]
        for plate in ("АА7310КТ", "АА7311КТ"):
            Visit.create({"visit_type": "incoming", "plate": plate}).action_arrive()

    def test_kpp_tour(self):  # AC-58
        self.start_tour("/odoo/action-td_yard.action_td_yard_kpp", "f3d_yard_kpp_tour", login="yard_tour")

    def test_dispatch_tour(self):  # AC-54
        self.start_tour(
            "/odoo/action-td_yard.action_td_yard_dispatch", "f3d_yard_dispatch_tour", login="yard_tour"
        )
