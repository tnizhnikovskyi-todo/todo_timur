"""W4-C: шаблон обходу (M-H1…M-H3): AC-H01, AC-H02."""

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .. import hooks
from .common import TAGS, TestWHCommon


@tagged(*TAGS)
class TestWHTemplate(TestWHCommon):
    def test_ac_h01_template_installed(self):
        tpl = self.Template.search([("code", "=", "TP-GRSH")])
        self.assertEqual(len(tpl), 1)
        self.assertEqual(tpl.name, "Обхід ТП і ГРЩ")
        self.assertEqual(
            [(s.name, s.time_from, s.time_to, s.weekdays) for s in tpl.slot_ids],
            [("Зміна 1", 7.0, 16.0, "0,1,2,3,4"), ("Зміна 2", 16.0, 23.0, "0,1,2,3,4")],
        )
        self.assertEqual(tpl.item_ids.mapped("code"), ["t1", "t2", "swb", "pfc", "dgu", "bess"])
        items = {i.code: i for i in tpl.item_ids}
        self.assertEqual(
            (items["t1"].source, items["t1"].norm_kind, items["t1"].norm_max, items["t1"].unit),
            ("signal:energy/transformers/T1/temp_c", "max", 85.0, "°C"),
        )
        self.assertEqual(items["t2"].source, "signal:energy/transformers/T2/temp_c")
        self.assertEqual(
            (items["dgu"].source, items["dgu"].norm_kind, items["dgu"].norm_min, items["dgu"].unit),
            ("pult:kpis.generation.genset.fuel_pct", "min", 60.0, "%"),
        )
        for code in ("swb", "pfc", "bess"):
            self.assertEqual((items[code].source, items[code].norm_kind), (False, "none"))
        self.assertEqual(items["swb"].hint, "тепловізор, точки Q1, Q2, QS")
        self.assertEqual(items["t1"].node_id.code, "T1")
        self.assertEqual(items["swb"].node_id.code, "SWB-1")

    def test_ac_h01_unique_and_idempotent(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Template.create({"name": "Дубль", "code": "TP-GRSH"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["td.energy.round.template.item"].create(
                {"template_id": self.tpl.id, "code": "t1", "title": "Дубль"}
            )
        counts = [self.Template.search_count([]), self.Slot.search_count([]), len(self.tpl.item_ids)]
        self.assertFalse(hooks._seed_template(self.env))  # повторний `-u`/хук: шаблон є — без змін
        self.assertEqual([self.Template.search_count([]), self.Slot.search_count([]), len(self.tpl.item_ids)], counts)

    def _tpl(self, **kw):
        return self.Template.create({"name": "Тест", "code": "T-TEST", **kw})

    def test_ac_h02_slot_constraints(self):
        tpl = self._tpl()
        ok = self.Slot.create(
            {"template_id": tpl.id, "name": "Ніч", "time_from": 0.0, "time_to": 24.0, "weekdays": "5,6"}
        )
        self.assertTrue(ok)
        for vals in (
            {"time_from": 10.0, "time_to": 10.0},  # time_to ≤ time_from
            {"time_from": 12.0, "time_to": 10.0},
            {"time_from": 22.0, "time_to": 26.0},  # перетинає північ
            {"time_from": -1.0, "time_to": 5.0},
            {"time_from": 7.0, "time_to": 9.0, "weekdays": "0,0"},  # повтор
            {"time_from": 7.0, "time_to": 9.0, "weekdays": "0,7"},  # цифра 7
            {"time_from": 7.0, "time_to": 9.0, "weekdays": "a"},
            {"time_from": 7.0, "time_to": 9.0, "weekdays": ""},
        ):
            with self.subTest(vals), self.assertRaises(ValidationError):
                self.Slot.create({"template_id": tpl.id, "name": "Х", **vals})
        with self.assertRaisesRegex(ValidationError, "Слот не може перетинати північ"):
            self.Slot.create({"template_id": tpl.id, "name": "Х", "time_from": 22.0, "time_to": 25.0})

    def test_ac_h02_item_constraints(self):
        tpl = self._tpl()
        Item = self.env["td.energy.round.template.item"]
        base = {"template_id": tpl.id, "title": "Пункт"}
        Item.create({**base, "code": "ok1", "norm_kind": "max", "norm_max": 85.0, "source": "signal:a/b"})
        Item.create(
            {**base, "code": "ok2", "norm_kind": "range", "norm_min": 1.0, "norm_max": 2.0, "source": "pult:a.b"}
        )
        Item.create({**base, "code": "ok3", "norm_kind": "none", "source": False})
        for i, vals in enumerate(
            (
                {"norm_kind": "max"},  # без norm_max
                {"norm_kind": "min"},  # без norm_min
                {"norm_kind": "range", "norm_min": 5.0, "norm_max": 1.0},
                {"source": "foo:bar"},
                {"source": "signal:"},
                {"source": "pult"},
            )
        ):
            with self.subTest(vals), self.assertRaises(ValidationError):
                Item.create({**base, "code": "bad%d" % i, **vals})
        with self.assertRaisesRegex(ValidationError, "Норма пункту «Пункт» некоректна"):
            Item.create({**base, "code": "bad9", "norm_kind": "max"})
        # шаблон з пунктами одразу (Command.create) — теж перевіряється
        with self.assertRaises(ValidationError):
            self.Template.create(
                {
                    "name": "Х",
                    "code": "T-X",
                    "item_ids": [Command.create({"code": "a", "title": "A", "source": "oops"})],
                }
            )
