"""W4-C: значення пункту й норма (R-H4): AC-H06, AC-H08 + чисті функції `tools/value.py`."""

from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged

from ..tools import value
from .common import T1, T2, TAGS, TestWHCommon


@tagged(*TAGS)
class TestWHValueTools(TransactionCase):
    def test_parse_and_walk(self):
        self.assertEqual(value.parse_source("signal:energy/x"), ("signal", "energy/x"))
        self.assertEqual(value.parse_source("pult:kpis.a.b"), ("pult", "kpis.a.b"))
        for bad in (None, "", "foo:x", "signal:", "pult"):
            self.assertIsNone(value.parse_source(bad), bad)
        data = {"kpis": {"generation": {"genset": {"fuel_pct": 78}}}}
        self.assertEqual(value.walk_path(data, "kpis.generation.genset.fuel_pct"), 78.0)
        self.assertIsNone(value.walk_path(data, "kpis.generation.genset.x"))
        self.assertIsNone(
            value.walk_path({"kpis": {"generation": {"genset": None}}}, "kpis.generation.genset.fuel_pct")
        )
        self.assertIsNone(value.walk_path({"a": "text"}, "a"))

    def test_fresh(self):
        now = datetime(2026, 10, 20, 11, 20)
        self.assertTrue(value.is_fresh(now - timedelta(seconds=120), now, 10, 120))
        self.assertFalse(value.is_fresh(now - timedelta(seconds=121), now, 10, 120))
        self.assertTrue(value.is_fresh(now - timedelta(seconds=300), now, 120, 120))  # 3·period_s = 360 с
        self.assertFalse(value.is_fresh(None, now, 10, 120))

    def test_format(self):
        self.assertEqual(value.fmt_number(58.0), "58")
        self.assertEqual(value.fmt_number(58.46, 1), "58,5")
        self.assertEqual(value.fmt_value(58.0, "°C"), "58 °C")
        self.assertEqual(value.fmt_value(None, "°C"), "немає даних")
        self.assertEqual(value.norm_text("max", 0, 85, "°C"), "до 85 °C")
        self.assertEqual(value.norm_text("min", 60, 0, "%"), "від 60 %")
        self.assertEqual(value.norm_text("range", 10, 20.5, "°C"), "10–20,5 °C")
        self.assertEqual(value.hint("стат", False, "none", 0, 0, "", 0, None), "стат")
        self.assertEqual(value.hint("", True, "none", 0, 0, "кВт", 0, 12.0), "зараз 12 кВт")
        self.assertEqual(value.hint("", True, "max", 0, 85, "°C", 0, None), "норма до 85 °C · зараз —")

    def test_evaluate(self):
        ev = value.evaluate
        self.assertEqual(ev("max", 0, 85, 85.0), "ok")
        self.assertEqual(ev("max", 0, 85, 85.1), "deviation")
        self.assertEqual(ev("min", 60, 0, 60.0), "ok")
        self.assertEqual(ev("min", 60, 0, 59.9), "deviation")
        self.assertEqual((ev("range", 10, 20, 10.0), ev("range", 10, 20, 20.0)), ("ok", "ok"))
        self.assertEqual((ev("range", 10, 20, 9.9), ev("range", 10, 20, 20.1)), ("deviation", "deviation"))
        self.assertEqual((ev("max", 0, 85, None), ev("none", 0, 0, 999.0)), ("ok", "ok"))


@tagged(*TAGS)
class TestWHValue(TestWHCommon):
    def _items(self, rnd):
        return {i.code: i for i in rnd.item_ids}

    def test_ac_h06_hints(self):
        self._signal(T1, 58.0)  # свіжий
        self.stale(T2, minutes=33)  # несвіжий
        rnd = self._round(self.slot1)
        with self._pult_patch(78) as pult:
            data = self.R(user=self.u_eng).get_mobile()
        hints = {i["code"]: i["hint"] for i in data["round"]["items"]}
        self.assertEqual(hints["t1"], "норма до 85 °C · зараз 58 °C")
        self.assertEqual(hints["t2"], "норма до 85 °C · зараз —")
        self.assertEqual(hints["swb"], "тепловізор, точки Q1, Q2, QS")
        self.assertEqual(hints["dgu"], "норма від 60 % · зараз 78 %")
        self.assertEqual(hints["pfc"], "ступені, контактори, запобіжники")
        self.assertEqual(data["round"]["id"], rnd.id)
        pult.assert_called_once()  # один виклик get_pult на всі пункти
        self.assertEqual(pult.call_args.kwargs, {"period": "now", "parts": ["kpis"]})

    def test_ac_h06_no_pult_data(self):
        self._round(self.slot1)
        with self._pult_patch(None):
            hints = {i["code"]: i["hint"] for i in self.R(user=self.u_eng).get_mobile()["round"]["items"]}
        self.assertEqual(hints["dgu"], "норма від 60 % · зараз —")

    def test_ac_h08_norm_boundaries(self):
        rnd = self._round(self.slot1)
        eng = self.R(user=self.u_eng)
        t1 = self._items(rnd)["t1"]
        for temp, result in ((85.0, "ok"), (85.1, "deviation"), (84.9, "ok")):
            self._signal(T1, temp)
            eng.action_toggle_item(t1.id, True)
            self.assertEqual((t1.result, t1.value), (result, temp), temp)
            eng.action_toggle_item(t1.id, False)
        self._signal(T1, 58.0)
        eng.action_toggle_item(t1.id, True)
        self.assertEqual((t1.value_text, t1.result), ("58 °C", "ok"))
        dgu = self._items(rnd)["dgu"]
        for fuel, result in ((60.0, "ok"), (59.9, "deviation"), (78.0, "ok")):
            with self._pult_patch(fuel):
                eng.action_toggle_item(dgu.id, True)
            self.assertEqual((dgu.result, dgu.value), (result, fuel), fuel)
            eng.action_toggle_item(dgu.id, False)
        # немає даних → ok із «немає даних»
        with self._pult_patch(None):
            eng.action_toggle_item(dgu.id, True)
        self.assertEqual((dgu.result, dgu.value_text), ("ok", "немає даних"))
        self.stale(T2, minutes=33)
        t2 = self._items(rnd)["t2"]
        eng.action_toggle_item(t2.id, True)
        self.assertEqual((t2.result, t2.value_text), ("ok", "немає даних"))
        # без джерела — ok, текст значення порожній
        swb = self._items(rnd)["swb"]
        eng.action_toggle_item(swb.id, True, comment="гарячий контакт Q2")
        self.assertEqual((swb.result, swb.value_text, swb.comment), ("ok", "", "гарячий контакт Q2"))

    def test_ac_h08_range(self):
        tpl = self.Template.create(
            {
                "name": "Діапазон",
                "code": "T-RNG",
                "slot_ids": [(0, 0, {"name": "Д", "time_from": 0.0, "time_to": 24.0, "weekdays": "0,1,2,3,4,5,6"})],
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "code": "r",
                            "title": "R",
                            "source": "signal:" + T1,
                            "norm_kind": "range",
                            "norm_min": 10.0,
                            "norm_max": 20.0,
                            "unit": "°C",
                        },
                    )
                ],
            }
        )
        rnd = self._round(template=tpl)
        item, eng = rnd.item_ids, self.R(user=self.u_eng)
        for temp, result in ((10.0, "ok"), (20.0, "ok"), (9.9, "deviation"), (20.1, "deviation"), (15.0, "ok")):
            self._signal(T1, temp)
            eng.action_toggle_item(item.id, True)
            self.assertEqual(item.result, result, temp)
            eng.action_toggle_item(item.id, False)
        self.assertEqual(rnd.state, "in_progress")
