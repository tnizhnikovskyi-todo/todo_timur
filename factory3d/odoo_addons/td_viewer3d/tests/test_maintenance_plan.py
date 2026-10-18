"""API-11 і R-22: «Запланувати ТО», поля заявок і обладнання в payload, null-поля delta."""
from unittest.mock import patch

from odoo.models import BaseModel
from odoo.tests import HttpCase, tagged

from odoo.addons.td_viewer3d.tools import dates
from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder

from .common import F3dViewerBase

PROVIDER = "td.viewer.provider.maintenance"
URL = "/f3d/viewer/maintenance/plan"


class MaintenanceFixtures:
    """Стадії, команда, виконавець і допоміжні конструктори обладнання/заявок."""

    @classmethod
    def _fixtures(cls):
        env = cls.env
        cls.user_maint = cls._make_user("f3d_mplan", [
            "base.group_user", "td_factory3d.group_td_user", "maintenance.group_equipment_manager"])
        cls.user_tech = cls._make_user("f3d_mtech", ["base.group_user"])
        cls.stage_new = env["maintenance.stage"].create({"name": "TST Нова", "sequence": 1})
        cls.stage_done = env["maintenance.stage"].create({"name": "TST Виконано", "sequence": 90, "done": True})
        cls.team = env["maintenance.team"].create({"name": "TST команда ТО"})
        cls.equipment = cls._eq("TST-SAW-2", "TST Розкрій 2", team=cls.team, tech=cls.user_tech)

    @classmethod
    def _eq(cls, code, name, team=None, tech=None):
        vals = {"name": name, "td_code": code}
        if team:
            vals["maintenance_team_id"] = team.id
        if tech:
            vals["technician_user_id"] = tech.id
        return cls.env["maintenance.equipment"].create(vals)

    def _req(self, eq, name="Планове ТО", mtype="preventive", sched=None, done=False, **kw):
        vals = {"name": name, "equipment_id": eq.id, "maintenance_type": mtype, "maintenance_team_id": self.team.id,
                "stage_id": (self.stage_done if done else self.stage_new).id}
        if sched:
            vals["schedule_date"] = dates.utc(sched)
        vals.update(kw)
        return self.env["maintenance.request"].create(vals)

    def _recurring(self, eq, sched, unit="week", **kw):
        """Закрита повторювана профілактична заявка: Odoo не копіює її при create, тож відкритої заявки немає."""
        kw.setdefault("repeat_type", "forever")
        return self._req(eq, name="TST повторюване ТО", sched=sched, done=True, recurring_maintenance=True,
                         repeat_interval=1, repeat_unit=unit, **kw)

    def _open_prev(self, eq):
        return self.env["maintenance.request"].search([
            ("equipment_id", "=", eq.id), ("maintenance_type", "=", "preventive"), ("stage_id.done", "=", False)])


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestMaintenanceProviderFields(MaintenanceFixtures, F3dViewerBase):
    """R-22: поля `maintenance_requests[]` і `equipment[]` у payload та null-поля delta."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixtures()

    def setUp(self):
        super().setUp()
        self.demo_clock("2026-10-16 10:30")

    def _data(self):
        return self.payload(self.user_maint)

    @staticmethod
    def _rec(data, code, name=None):
        return next(r for r in data["maintenance_requests"] if r["equipment"] == code and (not name or r["name"] == name))

    def test_request_fields_and_overdue_days(self):
        late = self._req(self.equipment, sched="2026-10-14 08:00")
        rec = self._rec(self._data(), "TST-SAW-2")
        self.assertEqual((rec["res_id"], rec["equipment_name"], rec["done"], rec["stage"]),
                         (late.id, "TST Розкрій 2", False, "TST Нова"))
        self.assertEqual(rec["schedule_date"], "2026-10-14 08:00")
        self.assertEqual(rec["overdue_days"], 2)

    def test_overdue_today_is_zero_days_future_and_done_have_none(self):
        today_early = self._req(self._eq("TST-E1", "TST E1"), sched="2026-10-16 07:00")
        future = self._req(self._eq("TST-E2", "TST E2"), sched="2026-10-20 08:00")
        closed = self._req(self._eq("TST-E3", "TST E3"), sched="2026-10-01 08:00", done=True)
        data = self._data()
        self.assertEqual(self._rec(data, "TST-E1")["overdue_days"], 0)
        self.assertEqual(self._rec(data, "TST-E1")["res_id"], today_early.id)
        self.assertNotIn("overdue_days", self._rec(data, "TST-E2"))
        self.assertEqual(self._rec(data, "TST-E2")["res_id"], future.id)
        rec3 = [r for r in data["maintenance_requests"] if r["res_id"] == closed.id]
        if rec3:  # закрита заявка потрапляє в payload лише 7 днів
            self.assertTrue(rec3[0]["done"])
            self.assertNotIn("overdue_days", rec3[0])

    def test_equal_names_resolve_by_res_id(self):
        """Назви заявок не унікальні («Планове ТО» у всіх): рядок обладнання вказує на свою заявку за res_id."""
        other = self._eq("TST-SAW-3", "TST Розкрій 3")
        r1 = self._req(self.equipment, sched="2026-10-14 08:00")
        r2 = self._req(other, sched="2026-10-18 08:00")
        data = self._data()
        self.assertEqual(r1.name, r2.name)
        self.assertEqual(data["equipment"]["TST-SAW-2"]["maintenance_request_id"], r1.id)
        self.assertEqual(data["equipment"]["TST-SAW-3"]["maintenance_request_id"], r2.id)
        self.assertEqual({self._rec(data, "TST-SAW-2")["res_id"], self._rec(data, "TST-SAW-3")["res_id"]}, {r1.id, r2.id})

    def test_open_request_blocks_due_flag(self):
        self._req(self.equipment, sched="2026-10-01 08:00")
        eq = self._data()["equipment"]["TST-SAW-2"]
        self.assertNotIn("maintenance_due", eq)
        self.assertEqual(eq["next_maintenance"], "2026-10-01")

    def test_due_without_open_request(self):
        """Odoo 19 без next_action_date: наступна дата — остання закрита повторювана профілактична заявка + період."""
        over, soon, far, ended = (self._eq(c, c) for c in ("TST-D1", "TST-D2", "TST-D3", "TST-D4"))
        self._recurring(over, "2026-10-02 08:00")                    # +1 тиждень = 09.10 → минуло
        self._recurring(soon, "2026-10-12 08:00")                    # 19.10 → за 3 дні
        self._recurring(far, "2026-10-15 08:00", unit="month")       # 15.11 → не скоро
        self._recurring(ended, "2026-10-02 08:00", repeat_type="until", repeat_until="2026-10-05")  # повтор закінчився
        eqs = self._data()["equipment"]
        self.assertEqual((eqs["TST-D1"]["maintenance_due"], eqs["TST-D1"]["next_maintenance"]), ("overdue", "2026-10-09"))
        self.assertEqual((eqs["TST-D2"]["maintenance_due"], eqs["TST-D2"]["next_maintenance"]), ("soon", "2026-10-19"))
        self.assertEqual(eqs["TST-D3"]["next_maintenance"], "2026-11-15")
        self.assertNotIn("maintenance_due", eqs["TST-D3"])
        self.assertNotIn("next_maintenance", eqs["TST-D4"])
        self.assertNotIn("maintenance_request_id", eqs["TST-D1"])

    def test_workcenter_gets_request_id(self):
        self.env["mrp.workcenter"].create({"name": "TST WC", "td_code": "TST-WC-9"})
        req = self._req(self._eq("TST-WC-9", "TST Центр 9"), sched="2026-10-14 08:00")
        rec = self.payload(self.user_f3d)["workcenters"]["TST-WC-9"]
        self.assertEqual((rec["maintenance_request"], rec["maintenance_request_id"]), (req.name, req.id))

    def test_delta_nulls_resolved_keys(self):
        """R-14 п. 4 для R-22: після закриття заявки delta скидає id заявки й прапорці в null."""
        req = self._req(self.equipment, sched="2026-10-14 08:00")
        req.stage_id = self.stage_done
        changes = {"maintenance.request": {req.name, "TST-SAW-2"}}
        res = DeltaBuilder(self.env(user=self.user_maint), None, changes=changes).build()
        eq = res["patch"]["equipment"]["TST-SAW-2"]
        for key in ("maintenance_request", "maintenance_request_id", "maintenance_due"):
            self.assertIn(key, eq)
            self.assertIsNone(eq[key])
        rec = next(r for r in res["patch"]["maintenance_requests"] if r["res_id"] == req.id)
        self.assertTrue(rec["done"])
        self.assertIsNone(rec["overdue_days"])


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestMaintenancePlanApi(MaintenanceFixtures, HttpCase, F3dViewerBase):
    """API-11: створення, ідемпотентність, 403 (права, кіоск), 400/404 (параметри)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixtures()
        cls.user_portal = cls._make_user("f3d_mportal", ["base.group_portal"])
        cls.user_kiosk.password = "f3d_kiosk_pw"  # без пароля вхід неможливий; тест перевіряє відмову на рівні API
        for user in (cls.user_maint, cls.user_portal):
            user.password = user.login

    def _plan(self, params, login="f3d_mplan", password=None):
        self.authenticate(login, password or login)
        return self.make_jsonrpc_request(URL, params)

    def _assert_error(self, res, status, code):
        self.assertFalse(res["ok"], res)
        self.assertEqual((res["status"], res["error"]["code"]), (status, code))
        self.assertTrue(res["error"]["message"])

    # --- створення
    def test_creates_request(self):
        res = self._plan({"code": "TST-SAW-2"})
        self.assertTrue(res["ok"] and res["created"], res)
        req = self.env["maintenance.request"].browse(res["request"]["res_id"])
        self.assertEqual((req.name, req.maintenance_type, req.equipment_id), ("Планове ТО · TST Розкрій 2", "preventive", self.equipment))
        self.assertEqual((req.maintenance_team_id, req.user_id), (self.team, self.user_tech))
        self.assertTrue(req.schedule_date and not req.stage_id.done)
        self.assertEqual(res["request"]["name"], req.name)
        self.assertEqual(res["request"]["equipment_name"], "TST Розкрій 2")
        patch_eq = res["equipment"]["TST-SAW-2"]
        self.assertEqual((patch_eq["maintenance_request"], patch_eq["maintenance_request_id"]), (req.name, req.id))
        self.assertIsNone(patch_eq["maintenance_due"])

    def test_equipment_id_param(self):
        res = self._plan({"equipment_id": self.equipment.id})
        self.assertTrue(res["ok"] and res["created"], res)
        self.assertEqual(len(self._open_prev(self.equipment)), 1)

    def test_schedule_follows_next_preventive_date(self):
        self._recurring(self.equipment, "2026-10-02 08:00")  # наступна — 09.10
        res = self._plan({"code": "TST-SAW-2"})
        self.assertTrue(res["created"], res)
        self.assertEqual(res["request"]["schedule_date"], "2026-10-09 08:00")
        self.assertEqual(res["equipment"]["TST-SAW-2"]["next_maintenance"], "2026-10-09")

    def test_planned_request_shows_up_in_payload(self):
        self.demo_clock("2026-10-16 10:30")
        self._recurring(self.equipment, "2026-10-02 08:00")
        self.assertEqual(self.payload(self.user_maint)["equipment"]["TST-SAW-2"]["maintenance_due"], "overdue")
        res = self._plan({"code": "TST-SAW-2"})
        eq = self.payload(self.user_maint)["equipment"]["TST-SAW-2"]
        self.assertEqual(eq["maintenance_request_id"], res["request"]["res_id"])
        self.assertNotIn("maintenance_due", eq)

    # --- ідемпотентність
    def test_idempotent(self):
        first = self._plan({"code": "TST-SAW-2"})
        second = self._plan({"code": "TST-SAW-2"})
        self.assertTrue(first["created"] and second["ok"] and not second["created"], second)
        self.assertEqual(first["request"]["res_id"], second["request"]["res_id"])
        self.assertEqual(len(self._open_prev(self.equipment)), 1)

    def test_existing_open_preventive_is_returned(self):
        mine = self._req(self.equipment, sched="2026-10-14 08:00")
        res = self._plan({"code": "TST-SAW-2"})
        self.assertTrue(res["ok"] and not res["created"], res)
        self.assertEqual(res["request"]["res_id"], mine.id)
        self.assertEqual(len(self._open_prev(self.equipment)), 1)

    def test_corrective_or_done_request_does_not_block(self):
        self._req(self.equipment, name="Поломка", mtype="corrective")
        self._req(self.equipment, name="Старе ТО", done=True)
        res = self._plan({"code": "TST-SAW-2"})
        self.assertTrue(res["created"], res)

    # --- права
    def test_forbidden_without_create_access(self):
        orig = BaseModel.has_access

        def fake(this, operation):
            if this._name == "maintenance.request" and operation == "create":
                return False
            return orig(this, operation)

        with patch.object(BaseModel, "has_access", fake):
            res = self._plan({"code": "TST-SAW-2"})
        self._assert_error(res, 403, "forbidden")
        self.assertFalse(self._open_prev(self.equipment))

    def test_forbidden_for_user_outside_viewer_group(self):
        res = self._plan({"code": "TST-SAW-2"}, login="f3d_mportal")
        self._assert_error(res, 403, "forbidden")
        self.assertFalse(self._open_prev(self.equipment))

    def test_kiosk_user_refused(self):
        res = self._plan({"code": "TST-SAW-2"}, login="f3d_kiosk", password="f3d_kiosk_pw")
        self._assert_error(res, 403, "kiosk")
        self.assertFalse(self._open_prev(self.equipment))

    def test_kiosk_context_refused_in_model(self):
        for env in (self.env(user=self.user_kiosk), self.env(user=self.user_maint, context={"kiosk": True})):
            res = env[PROVIDER]._f3d_plan_maintenance(code="TST-SAW-2")
            self._assert_error(res, 403, "kiosk")
        self.assertFalse(self._open_prev(self.equipment))

    def test_kiosk_url_has_no_plan_route(self):
        res = self.url_open("/f3d/kiosk/any-token/maintenance/plan", data="{}", headers={"Content-Type": "application/json"},
                            allow_redirects=False)
        self.assertEqual(res.status_code, 404)

    # --- параметри
    def test_bad_params(self):
        no_code = self.env["maintenance.equipment"].create({"name": "TST без коду"})
        cases = [
            ({}, 400), ({"code": "../x"}, 400), ({"code": ""}, 400), ({"code": 5}, 400), ({"code": "A" * 65}, 400),
            ({"equipment_id": "5"}, 400), ({"equipment_id": True}, 400), ({"equipment_id": -3}, 400),
            ({"equipment_id": 0}, 400), ({"equipment_id": 2 ** 40}, 400),
            ({"code": "TST-SAW-2", "equipment_id": self.equipment.id}, 400),
            ({"code": "NO-SUCH-1"}, 404), ({"equipment_id": 987654}, 404), ({"equipment_id": no_code.id}, 404),
        ]
        self.authenticate("f3d_mplan", "f3d_mplan")
        for params, status in cases:
            with self.subTest(params=params):
                res = self.make_jsonrpc_request(URL, params)
                self._assert_error(res, status, "bad_request" if status == 400 else "not_found")
        self.assertFalse(self._open_prev(self.equipment))
