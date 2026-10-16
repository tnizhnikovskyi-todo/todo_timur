"""M-11, R-26, R-27: провайдери переглядача (AC-17, AC-42…AC-45). Дані — з установки (хук W3) і статики макета."""

import json
import os

from odoo import fields
from odoo.tests import new_test_user, tagged

from .common import F3DBmsCase

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GROUP_KEYS = (
    "zone zone_name task task_name kind panel n lumen watt area e_norm e_calc level e_now p_inst p_now control"
).split()
UNIT_KEYS = (
    "name kind zone mode airflow_m3h airflow_nom supply_c indoor_c heating_valve heat_kw "
    "p_inst p_now filter_dp_pa state"
).split()


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestViewerProvider(F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static = _load(os.path.join(HERE, "data", "static_bms.json"))
        cls.demo = _load(os.path.join(ROOT, "dist", "odoo_demo.json"))
        cls.light = cls.env["f3d.viewer.provider.lighting"]
        cls.vent = cls.env["f3d.viewer.provider.ventilation"]

    def _ctx(self, **kw):
        return {"static": self.static, **kw}

    def test_lighting_static_equal_demo(self):
        """AC-42."""
        payload = {}
        self.light._f3d_viewer_collect(payload, self._ctx())
        lighting = payload["lighting"]
        demo = self.demo["lighting"]
        self.assertEqual(len(lighting["groups"]), 32)
        for code, want in demo["groups"].items():
            got = lighting["groups"][code]
            for key in GROUP_KEYS:
                self.assertEqual(got[key], want[key], f"{code}.{key}")
            for key in ("dali_group", "faults", "faulty", "scene", "deviation", "deviation_text", "stale"):
                self.assertIn(key, got)
        for code, want in demo["panels"].items():
            got = lighting["panels"][code]
            for key in ("name", "groups", "n", "p_inst", "p_now"):
                self.assertEqual(got[key], want[key], f"{code}.{key}")
        self.assertEqual((lighting["uf"], lighting["mf"]), (0.7, 0.8))
        self.assertEqual(lighting["norms_ref"], demo["norms_ref"])
        self.assertEqual(len(lighting["norms_ref"]), 13)

    def test_ventilation_static_equal_demo(self):
        """AC-17, AC-43."""
        payload = {}
        self.vent._f3d_viewer_collect(payload, self._ctx())
        vent = payload["ventilation"]
        demo = self.demo["ventilation"]
        self.assertEqual(len(vent["units"]), 29)
        for code, want in demo["units"].items():
            got = vent["units"][code]
            for key in UNIT_KEYS:
                if key in want:
                    self.assertEqual(got[key], want[key], f"{code}.{key}")
        want_totals = {k: v for k, v in demo["totals"].items()}
        for key, value in want_totals.items():
            self.assertEqual(vent["totals"][key], value, f"totals.{key}")
        for key in ("heat_need_kw", "boilers_on_calc", "deficit_kw", "chp_source"):
            self.assertIn(key, vent["totals"])
        hb = vent["heat_balance"]
        self.assertEqual(
            (hb["t_out"], hb["total"], hb["capacity"], hb["chp_kw"], hb["reserve"]), (-15.0, 753, 990, 856, 1.45)
        )
        self.assertEqual(len(hb["items"]), 4)
        self.assertEqual(hb["items"], demo["heat_balance"]["items"])
        self.assertEqual(hb["note"], demo["heat_balance"]["note"])

    def test_maintenance_request_key(self):
        unit = self.env["f3d.bms.hvac.unit"].search([("code", "=", "RV-05")])
        self.assertNotIn("maintenance_request", self._vent()["units"]["RV-05"])
        stage = self.env["maintenance.stage"].search([("done", "=", False)], limit=1)
        req = self.env["maintenance.request"].create(
            {"name": "Заявка RV-05 тест", "f3d_signal_id": unit.state_signal_id.id, "stage_id": stage.id}
        )
        self.env.invalidate_all()
        rec = self._vent()["units"]["RV-05"]
        self.assertEqual((rec["maintenance_request"], rec["maintenance_request_id"]), (req.name, req.id))

    def _request(self, unit, name="Планове ТО"):
        stage = self.env["maintenance.stage"].search([("done", "=", False)], limit=1)
        return self.env["maintenance.request"].create(
            {"name": name, "f3d_signal_id": unit.state_signal_id.id, "stage_id": stage.id}
        )

    def test_maintenance_request_id_same_name(self):
        """Viewer R-22: заявки з однаковою назвою на різних установках не змішуються, ключ — `maintenance_request_id`."""
        units = self.env["f3d.bms.hvac.unit"].search([("state_signal_id", "!=", False)], order="sequence, code", limit=2)
        self.assertEqual(len(units), 2)
        first, second = (self._request(u) for u in units)
        self.assertEqual(first.name, second.name)
        self.assertNotEqual(first.id, second.id)
        self.env.invalidate_all()
        got = self._vent()["units"]
        for unit, req in zip(units, (first, second)):
            self.assertEqual(
                (got[unit.code]["maintenance_request"], got[unit.code]["maintenance_request_id"]),
                (req.name, req.id),
            )
        # дві однойменні заявки на одній установці: береться найстаріша (за id), а не будь-яка з тією ж назвою
        older = self._request(units[0])
        self.env.invalidate_all()
        self.assertEqual(self._vent()["units"][units[0].code]["maintenance_request_id"], first.id)
        self.assertNotEqual(older.id, first.id)

    def test_maintenance_request_id_cleared(self):
        """Повний payload без заявки не містить ключів; delta пише null, щоб клієнт скинув стару заявку."""
        unit = self.env["f3d.bms.hvac.unit"].search([("code", "=", "RV-05")])
        self.assertNotIn("maintenance_request_id", self._vent()["units"]["RV-05"])
        req = self._request(unit)
        self.env.invalidate_all()
        self.assertEqual(self._vent()["units"]["RV-05"]["maintenance_request_id"], req.id)
        req.stage_id = self.env["maintenance.stage"].search([("done", "=", True)], limit=1)
        self.env.invalidate_all()
        self.assertNotIn("maintenance_request_id", self._vent()["units"]["RV-05"])
        rec = self._vent(self._ctx(delta=True))["units"]["RV-05"]
        self.assertIsNone(rec["maintenance_request"])
        self.assertIsNone(rec["maintenance_request_id"])

    def _vent(self, ctx=None):
        payload = {}
        self.vent._f3d_viewer_collect(payload, ctx or self._ctx())
        return payload["ventilation"]

    def test_live_values(self):
        """AC-44."""
        env = self.env
        group = env["f3d.bms.light.group"].search([("code", "=", "LT-CUT")])
        group.level_signal_id.sudo().write({"last_value": 60.0, "last_ts": fields.Datetime.now(), "status": "ok"})
        group.faults_signal_id.sudo().write({"last_value": 1.0, "last_ts": fields.Datetime.now(), "status": "ok"})
        group.faulty_signal_id.sudo().write({"last_text": "1.2.1.5", "last_ts": fields.Datetime.now(), "status": "ok"})
        unit = env["f3d.bms.hvac.unit"].search([("code", "=", "RV-05")])
        now = fields.Datetime.now()
        for sig, vals in (
            (unit.mode_signal_id, {"last_text": "ST"}),
            (unit.state_signal_id, {"last_text": "stopped"}),
            (unit.valve_signal_id, {"last_value": 12.0}),
            (unit.supply_signal_id, {"last_value": 19.337}),
            (unit.airflow_signal_id, {"last_value": 5852.544}),
        ):
            sig.sudo().write({**vals, "last_ts": now, "status": "ok"})
        env.invalidate_all()
        payload = {}
        self.light._f3d_viewer_collect(payload, self._ctx())
        cut = payload["lighting"]["groups"]["LT-CUT"]
        self.assertEqual((cut["level"], cut["e_now"], cut["faults"], cut["faulty"]), (0.6, 305, 1, "1.2.1.5"))
        rv5 = self._vent()["units"]["RV-05"]
        self.assertEqual((rv5["mode"], rv5["mode_code"], rv5["state"]), ("Очікування", "ST", "standby"))
        self.assertEqual((rv5["heating_valve"], rv5["supply_c"], rv5["airflow_m3h"]), (0.12, 19.34, 5852.5))

    def test_delta(self):
        """AC-45."""
        patch = {}
        self.light._f3d_viewer_delta(patch, self._ctx(changes={"f3d.signal": {"equipment/COMPRESSOR/pressure_bar"}}))
        self.vent._f3d_viewer_delta(patch, self._ctx(changes={"f3d.signal": {"equipment/COMPRESSOR/pressure_bar"}}))
        self.assertEqual(patch, {})
        ctx = self._ctx(changes={"f3d.signal": {"lighting/groups/LT-CUT/level"}})
        self.light._f3d_viewer_delta(patch, ctx)
        self.vent._f3d_viewer_delta(patch, ctx)
        self.assertEqual(list(patch), ["lighting"])
        self.assertEqual(len(patch["lighting"]["groups"]), 32)
        patch = {}
        ctx = self._ctx(changes={"f3d.bms": {"RV-05"}})
        self.light._f3d_viewer_delta(patch, ctx)
        self.vent._f3d_viewer_delta(patch, ctx)
        self.assertEqual(set(patch), {"lighting", "ventilation"})
        patch = {}
        self.vent._f3d_viewer_delta(patch, self._ctx(changes={"f3d.signal": {"equipment/BOILER/state"}}))
        self.assertEqual(list(patch), ["ventilation"])

    def test_contract(self):
        for name in ("f3d.viewer.provider.lighting", "f3d.viewer.provider.ventilation"):
            model = self.env[name]
            self.assertTrue(model._name.startswith("f3d.viewer.provider."))
            self.assertNotIn("f3d.viewer.provider", model._inherit)
            self.assertEqual(model._f3d_viewer_bus_models(), ["f3d.signal", "f3d.bms"])
        self.assertEqual((self.light._f3d_sequence, self.vent._f3d_sequence), (110, 120))

    def test_no_access_keeps_static(self):
        user = new_test_user(self.env, "bms_nogroup", groups="base.group_user")
        payload = {"lighting": {"groups": {"X": {"n": 1}}}}
        self.light.with_user(user)._f3d_viewer_collect(payload, self._ctx())
        self.assertEqual(payload["lighting"], {"groups": {"X": {"n": 1}}})
        payload = {}
        self.vent.with_user(user)._f3d_viewer_collect(payload, self._ctx())
        self.assertEqual(payload["ventilation"], self.static["ventilation"])
