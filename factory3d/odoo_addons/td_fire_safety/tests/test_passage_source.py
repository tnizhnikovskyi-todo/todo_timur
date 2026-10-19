"""AC-53, AC-54, AC-75 (M-12, M-12a, CF-02, CF-06): джерела проходів людей."""

from unittest import mock

from freezegun import freeze_time
from odoo.tests import tagged

from .common import FireCase


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestSources(FireCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["hr.attendance"].sudo().search([]).unlink()
        cls.env["td.fire.drill"].sudo().search([("origin", "!=", "demo")]).unlink()
        cls.Base = cls.env["td.fire.passage.source"]

    def setUp(self):
        super().setUp()
        # без td_access: інакше його джерело (пріоритет 10) перекриває hr_attendance (AC-53)
        Base = type(self.env["td.fire.passage.source"])
        real = Base._td_source_names
        self.real_source_names = lambda: real(self.env["td.fire.passage.source"])
        patcher = mock.patch.object(
            Base, "_td_source_names", lambda model: [n for n in real(model) if n != "td.fire.passage.source.access"]
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def passages(self, emps):
        return [
            {"employee_id": emps[0].id, "ts": self.at(-600), "point": "D-1", "direction": "in"},
            {"employee_id": emps[1].id, "ts": self.at(-500), "point": "D-1", "direction": "in"},
            {"employee_id": emps[1].id, "ts": self.at(-100), "point": "D-2", "direction": "out"},
            {"employee_id": emps[2].id, "ts": self.at(-300), "point": "D-1", "direction": "in"},
            {"employee_id": emps[2].id, "ts": self.at(-200), "point": "D-2", "direction": "out"},
            {"employee_id": emps[2].id, "ts": self.at(-50), "point": "D-3", "direction": "in"},
        ]

    # --- AC-53 -------------------------------------------------------------------------------------------
    def test_hr_attendance(self):
        e = [self.make_employee("Відмітка %d" % i) for i in range(3)]
        self.make_att(e[0], self.at(-3600))
        self.make_att(e[1], self.at(-3600), self.at(-100))
        self.make_att(e[2], self.at(-3600), self.at(100))
        src = self.Base._td_get_source()
        self.assertEqual(src._name, "td.fire.passage.source.hr_attendance")
        self.assertEqual(self.Base._td_source_key(src), "hr_attendance")
        on_site = src._td_on_site(self.at(0))
        self.assertEqual(sorted(p["employee_id"] for p in on_site), sorted([e[0].id, e[2].id]))
        self.assertEqual(on_site[0]["point"], "Відмітка входу")
        passages = src._td_passages(self.at(-200), self.at(200))
        self.assertEqual(
            [(p["employee_id"], p["ts"], p["direction"]) for p in passages],
            [(e[1].id, self.at(-100), "out"), (e[2].id, self.at(100), "out")],
        )
        self.assertEqual(self.Base._td_people_at(src, self.at(0)), on_site)

    # --- AC-54 -------------------------------------------------------------------------------------------
    def test_prefix_source_without_inherit(self):
        if "td.fire.passage.source.zz_test" not in self.env:
            self.skipTest("тестовий модуль не встановлено")
        self.assertIn("td.fire.passage.source.zz_test", self.Base._td_source_names())
        zz = self.env["td.fire.passage.source.zz_test"]
        self.assertFalse(hasattr(zz, "_td_on_site"))
        Base = self.Base.with_context(f3d_test_passage_source=True)
        src = Base._td_get_source()
        self.assertEqual(src._name, "td.fire.passage.source.zz_test")
        self.assertEqual(Base._td_source_key(src), "zz_test")

    def test_people_from_passages(self):
        if "td.fire.passage.source.zz_test" not in self.env:
            self.skipTest("тестовий модуль не встановлено")
        e = [self.make_employee("Прохід %d" % i) for i in range(3)]
        Base = self.Base.with_context(f3d_test_passage_source=True, f3d_test_passages=self.passages(e))
        src = Base._td_get_source()
        people = Base._td_people_at(src, self.at(0))
        self.assertEqual(sorted(p["employee_id"] for p in people), sorted([e[0].id, e[2].id]))
        self.assertEqual({p["employee_id"]: p["point"] for p in people}, {e[0].id: "D-1", e[2].id: "D-3"})
        # навчання з цим джерелом
        out = [
            {"employee_id": e[0].id, "ts": self.at(40), "point": "T-1", "direction": "out"},
            {"employee_id": e[2].id, "ts": self.at(50), "point": "T-1", "direction": "in"},
        ]
        drill = self.new_drill(zone_id=self.z_cnc.id).with_context(
            f3d_test_passage_source=True, f3d_test_passages=self.passages(e)
        )
        with freeze_time(self.at(0)):
            drill.action_start()
        self.assertEqual(drill.passage_source, "zz_test")
        self.assertEqual(drill.on_site_count, 2)
        with freeze_time(self.at(60)):
            drill.with_context(f3d_test_passages=out)._tick()
        self.assertEqual(drill.evacuated_count, 1)
        person = drill.sudo().person_ids.filtered(lambda p: p.employee_id == e[0])
        self.assertEqual((person.exit_ts, person.exit_point), (self.at(40), "T-1"))

    def test_unavailable_falls_back(self):
        src = self.Base._td_get_source()
        self.assertEqual(self.Base._td_source_key(src), "hr_attendance")
        if "td.fire.passage.source.zz_test" in self.env:
            src = self.Base.with_context(f3d_test_passage_source=False)._td_get_source()
            self.assertEqual(src._name, "td.fire.passage.source.hr_attendance")

    def test_access_if_installed(self):
        if "td.fire.passage.source.access" not in self.env:
            self.assertNotIn("td.fire.passage.source.access", self.Base._td_source_names())
            self.skipTest("td_access не встановлено")
        access = self.env["td.fire.passage.source.access"]
        self.assertIn(access._name, self.real_source_names())
        self.assertEqual(getattr(access, "_td_priority", 1000), 10)
        with mock.patch.object(type(self.Base), "_td_source_names", lambda model: self.real_source_names()):
            self.assertEqual(self.Base._td_get_source()._name, access._name)

    # --- AC-75 -------------------------------------------------------------------------------------------
    def test_is_active_at(self):
        Drill = self.env["td.fire.drill"]
        d = self.new_drill(zone_id=self.z_cnc.id)
        self.assertFalse(Drill._td_is_active_at(self.at(0)))
        d.sudo().write({"state": "done", "start_ts": self.at(0), "end_ts": self.at(330)})
        self.assertTrue(Drill._td_is_active_at(self.at(180)))
        self.assertFalse(Drill._td_is_active_at(self.at(360)))
        self.assertFalse(Drill._td_is_active_at(self.at(-1)))
        d.sudo().write({"state": "running", "end_ts": False})
        self.assertTrue(Drill._td_is_active_at(self.at(5000)))
