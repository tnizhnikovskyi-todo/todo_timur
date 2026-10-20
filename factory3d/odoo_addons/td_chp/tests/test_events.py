"""AC-08 (стан і кроки), AC-09 (аварії, квитування); R-04 (інші події)."""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TAGS, ChpCase

STEPS = [
    "Вентиляція контейнера",
    "Попередній підігрів ОЖ",
    "Попереднє змащення",
    "Перевірка герметичності клапанів",
    "Прокрутка стартером",
    "Запалювання",
    "Холостий хід",
    "Синхронізація з мережею",
    "Набір навантаження",
]


@tagged(*TAGS)
class TestEvents(ChpCase):
    def texts(self, **domain):
        return self.events(**domain).sorted("id").mapped("text")

    def test_start_sequence(self):  # AC-08
        self.idle()
        self.assertEqual(self.unit.state_code, 0)
        self.assertFalse(self.events(kind="state"))  # перше показання — без події
        self.put({"ctl/state": 1})
        for k in range(1, 10):
            self.put({"ctl/step": k})
        self.put({"gen/p_kw": 612.0, "ctl/step": 0, "ctl/state": 2})
        self.assertEqual(self.texts(kind="step"), [f"Пуск, крок {k}/9: {name}" for k, name in enumerate(STEPS, 1)])
        self.assertEqual(
            self.texts(kind="state"),
            [
                "Стан КГУ: Резерв → Пуск",
                "Стан КГУ: Пуск → Робота",
                "Пуск завершено: КГУ в роботі, P ел. = 612 кВт",
            ],
        )
        self.assertEqual(self.unit.state_code, 2)
        # повтор того самого значення подій не створює
        n = len(self.events())
        self.put({"ctl/state": 2})
        self.assertEqual(len(self.events()), n)
        self.put({"ctl/state": 4})
        self.assertEqual(self.texts(kind="state")[-1], "Стан КГУ: Робота → Охолодження")

    def test_alarm_ack_reset(self):  # AC-09
        self.idle()
        self.put({"gas/p_in": 1.15, "alarm/code": 111})
        alarm = self.events(kind="alarm")
        self.assertEqual(len(alarm), 1)
        self.assertEqual(
            (alarm.level, alarm.ack_state, alarm.node, alarm.text),
            ("alarm", "new", "gasramp", "Низький тиск газу: 1,15 бар < 1,5 бар"),
        )
        warn = self.events(kind="warn")  # статус сигналу ok → alarm (R-04 п. 7)
        self.assertEqual(len(warn), 1)
        self.assertIn("поріг 1,5", warn.text)
        dto = self.pult(self.u_user).get_state()
        self.assertEqual((dto["alarm"]["code"], dto["alarm"]["node"], dto["alarm"]["acked"]), (111, "gasramp", False))
        with self.assertRaises(AccessError):
            self.Event.with_user(self.u_user)._td_ack()
        self.assertEqual(self.Event.with_user(self.u_op1)._td_ack(), 2)
        self.assertEqual(set(self.events(kind="alarm").mapped("ack_state")), {"acked"})
        self.assertEqual(self.events(kind="alarm").acked_by, self.u_op1)
        acks = self.events(kind="ack")
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks.text, "Квитування: підтверджено повідомлень — 2")
        self.assertEqual(self.Event.with_user(self.u_op1)._td_ack(), 0)  # нічого квитувати — без запису
        self.assertEqual(len(self.events(kind="ack")), 1)
        self.assertTrue(self.pult(self.u_user).get_state()["alarm"]["acked"])
        self.put({"alarm/code": 0, "gas/p_in": 2.1})
        self.assertEqual(self.texts(kind="alarm")[-1], "Аварію скинуто")
        self.assertIsNone(self.pult(self.u_user).get_state()["alarm"])

    def test_alarm_texts_and_trip(self):
        self.idle()
        self.put({"eng/t_jacket_out": 99.0, "alarm/code": 112})
        self.assertEqual(self.events(kind="alarm").text, "Перегрів ОЖ: 99 °C ≥ 97 °C")
        self.put({"alarm/code": 0})
        self.put({"alarm/code": 999})
        self.assertEqual(self.events(kind="alarm", ack_state="new").sorted("id")[-1].text, "Невідома аварія 999")
        self.put({"alarm/trip": 2, "safe/rocof_dfdt": 2.4, "safe/rocof_dphi": 14.0})
        trip = self.events(kind="trip")
        self.assertEqual((trip.level, trip.node, trip.ack_state), ("alarm", "qf", "new"))
        self.assertIn("df/dt = 2,4 Гц/с", trip.text)
        self.assertEqual(self.pult(self.u_user).get_state()["trip"]["code"], 2)
        self.put({"alarm/trip": 3})
        self.assertEqual(self.events(kind="trip").sorted("id")[-1].level, "warn")

    def test_protection_and_flag_events(self):
        self.idle()
        self.put({"gas/vp_state": 0, "safe/qf_closed": 0, "oil/topup": 0, "safe/ext_state": 0, "oil/level": 64.0})
        self.put({"gas/vp_leak": 0.3, "gas/vp_state": 2})
        self.put({"ctl/sync_du": 0.4, "ctl/sync_df": 0.02, "ctl/sync_dphi": -2.0, "safe/qf_closed": 1})
        self.put({"oil/topup": 1})
        self.put({"oil/level": 74.0, "oil/topup": 0})
        self.put({"safe/qf_closed": 0})
        self.put({"safe/ext_state": 1})
        texts = self.texts()
        self.assertIn("Valve proving YV1/YV2: герметичність підтверджена (витік 0,3 мбар/хв)", texts)
        self.assertIn("Синхронізація з мережею S2: ΔU 0,4 %, Δf 0,02 Гц, Δφ 2° · QF-CHP увімкнено", texts)
        self.assertIn("Автодолив масла: рівень картера 64 %", texts)
        self.assertIn("Автодолив масла завершено: картер 74 %", texts)
        self.assertIn("QF-CHP відключено, двигун на холостому ході", texts)
        ext = self.events(kind="protection").filtered(lambda e: "гасіння" in e.text)
        self.assertEqual((ext.level, ext.ack_state), ("alarm", "new"))

    def test_threshold_warn_event(self):
        self.idle()
        self.put({"eng/t_jacket_out": 93.0})
        warn = self.events(kind="warn")
        self.assertEqual((warn.level, warn.ack_state), ("warn", "new"))
        self.assertEqual(warn.text, "КГУ: температура ОЖ на виході: 93 °C (поріг 92)")
        self.put({"eng/t_jacket_out": 93.5})  # той самий статус — без нової події
        self.assertEqual(len(self.events(kind="warn")), 1)

    def test_no_events_when_read_disabled(self):
        self.idle()
        self.env["ir.config_parameter"].sudo().set_param("td.chp.read_enabled", "False")
        self.put({"ctl/state": 1})
        self.assertFalse(self.events(kind="state"))

    def test_gc(self):
        self.idle()
        old = self.Event._td_log(
            self.unit, "info", "state", "стара", ts=self.later(0).context["td_chp_now"].replace(year=2020)
        )
        self.Event._td_log(self.unit, "info", "state", "нова")
        self.assertEqual(self.Event._cron_gc(), 1)
        self.assertFalse(old.exists())
