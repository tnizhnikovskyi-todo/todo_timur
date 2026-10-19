"""W2-D: AC-287 — киоск і користувач без `group_td_energy_user`: розфарбування є, картки немає."""

from odoo.tests import tagged

from .common import TAGS, LayerCase


@tagged(*TAGS)
class TestKiosk(LayerCase):
    def test_kiosk_layer(self):  # AC-287
        layer = self.layer(kiosk=True)
        self.assertTrue(layer["nodes"])
        self.assertEqual(self.node(layer, "C2")["state"], "alarm")
        self.assertTrue(layer["alarms"])
        self.assertFalse(any(n["card"] for n in layer["nodes"]))
        self.assertIs(layer["can_pult"], False)  # у киоску кнопки «Відкрити пульт» немає
        text = " ".join(a["title"] for a in layer["alarms"]) + " " + str(self.node(layer, "C2")["title"])
        self.assertNotIn("PM-QF-C2", text)  # без технічних деталей діагностики
        self.assertNotIn("modbus", text)
        self.assertEqual(layer["alarms"][0]["title"], "Немає зв'язку з лічильником")

    def test_kiosk_user_payload(self):  # AC-287: справжній користувач-киоск через збирач
        user = self.env.ref("td_viewer3d.user_kiosk")
        res = self.payload(user, full=True, kiosk=True)
        layer = res["energy"]["layer"]
        self.assertFalse(any(n["card"] for n in layer["nodes"]))
        self.assertIs(layer["can_pult"], False)
        self.assertEqual(self.node(layer, "C2")["state"], "alarm")

    def test_card_flag_by_group(self):  # AC-287
        self.assertTrue(all(n["card"] for n in self.layer(self.u_view)["nodes"]))  # group_td_energy_user
        self.assertIs(self.layer(self.u_view)["can_pult"], True)
        self.assertIs(self.layer(self.u_viewer_only)["can_pult"], False)  # без групи — без кнопки «Відкрити пульт»
        res = self.payload(self.u_viewer, full=True)  # лише group_td_user
        self.assertEqual(res["meta"]["sections"]["energy"], "live")
        self.assertFalse(any(n["card"] for n in res["energy"]["layer"]["nodes"]))
        self.assertIs(res["energy"]["layer"]["can_pult"], False)
        self.assertEqual(self.node(res["energy"]["layer"], "C2")["state"], "alarm")
        # звичайний (не киоск) користувач бачить назву тривоги, як у Пульті
        self.assertEqual(self.node(res["energy"]["layer"], "C2")["title"], "Лічильник PM-QF-C2 не на зв'язку")
