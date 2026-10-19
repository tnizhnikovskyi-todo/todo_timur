"""AC-166…AC-168, AC-175: GET /td/energy/automation/config (API-24)."""

import json

from odoo.tests import HttpCase, tagged

from ..tools import config_builder
from .common import NOW, TAGS, TestControlCommon

KEYS = {"schema", "config_version", "etag", "server_time", "tz", "flags", "engine", "plant", "scenarios", "shed",
        "never_shed", "slots", "tariff", "bms", "signals", "inputs", "interlocks", "limits"}  # fmt: skip


@tagged(*TAGS)
class TestConfigApi(TestControlCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.col, cls.token = cls._collector()

    def get(self, token="default", headers=None):
        token = self.token if token == "default" else token
        hdrs = dict(headers or {})
        if token:
            hdrs["Authorization"] = "Bearer " + token
        return self.url_open("/td/energy/automation/config", headers=hdrs)

    def test_config_response(self):  # AC-166
        resp = self.get()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(KEYS <= set(data), KEYS - set(data))
        self.assertEqual(data["schema"], 1)
        etag = resp.headers["ETag"].strip('"')
        self.assertEqual(etag, data["etag"])
        self.assertEqual(self.get(headers={"If-None-Match": '"%s"' % etag}).status_code, 304)
        peak = self.Scenario.search([("code", "=", "peak")])
        peak.sudo()._td_apply_change({"params": {**peak._td_params(), "limit_kw": 700}})
        again = self.get(headers={"If-None-Match": '"%s"' % etag})
        self.assertEqual(again.status_code, 200)
        self.assertNotEqual(again.json()["etag"], etag)
        self.assertEqual(again.json()["scenarios"]["peak"]["params"]["limit_kw"], 700)
        self.assertEqual(self.get(token="bad").status_code, 401)
        self.assertEqual(self.get(token=None).status_code, 401)
        self.col.active = False
        self.assertEqual(self.get().status_code, 403)
        self.col.active = True
        post = self.url_open(
            "/td/energy/automation/config",
            data="{}",
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post.json()["error"]["code"], "method_not_allowed")
        text = json.dumps(data).lower()
        for word in ("cost", "password", "secret", "token"):
            self.assertNotIn(word, text)

    def test_etag_and_size(self):  # AC-167
        cfg = config_builder.build(self.env)
        e = config_builder.etag(cfg)
        cfg2 = dict(cfg, server_time="2030-01-01T00:00:00Z", config_version=999)
        self.assertEqual(config_builder.etag(dict(reversed(list(cfg2.items())))), e)
        cfg3 = json.loads(json.dumps(cfg))
        cfg3["scenarios"]["peak"]["params"]["limit_kw"] = 1
        self.assertNotEqual(config_builder.etag(cfg3), e)
        self.assertLess(len(json.dumps(cfg, ensure_ascii=False).encode()), 64 * 1024)

    def test_bms_targets(self):  # AC-168
        bms = config_builder.bms_targets(self.env)
        units = self.env["td.bms.hvac.unit"].sudo().search([("kind", "=", "roofvent"), ("mode_signal_id", "!=", False)])
        self.assertEqual(len(bms["night"]["vent"]), len(units))
        self.assertTrue(all(v["mode_signal"] for v in bms["night"]["vent"]))
        groups = self.env["td.bms.light.group"].sudo().search([("scene_signal_id", "!=", False)])
        aisle = {g.code for g in groups if g.fixture_kind == "highbay_rack"}
        self.assertEqual({g["group"] for g in bms["night"]["light"] if g["aisle"]}, aisle)
        self.assertFalse(any(g["aisle"] for g in bms["light_break"]["light"]))
        self.env["td.bms.hvac.unit"].sudo().search([]).write({"mode_signal_id": False, "sp_night_signal_id": False})
        self.env["td.bms.light.group"].sudo().search([]).write({"scene_signal_id": False})
        empty = config_builder.bms_targets(self.env)
        self.assertEqual((empty["night"]["vent"], empty["night"]["light"], empty["light_break"]["light"]), ([], [], []))

    def test_shed_and_flags(self):  # AC-175, AC-310
        data = self.get().json()
        self.assertEqual([s["seq"] for s in data["shed"]], [1, 2, 3, 4, 5])
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.energy_control.remote_switching_enabled", "False")
        self.assertFalse(self.get().json()["flags"]["remote_switching_enabled"])
        self.assertEqual(NOW.year, 2026)

    # --- D-47: блок `derived` ------------------------------------------------------------------------------------
    @staticmethod
    def evaluate(formula, get):
        """Семантика плагіна: будь-який терм відсутній → None (fail-closed)."""
        if formula["op"] == "ge":
            val = get(formula["code"])
            return None if val is None else (1.0 if val >= formula["value"] else 0.0)
        total = 0.0
        for term in formula["terms"]:
            val = get(term["code"])
            if val is None:
                return None
            total += term["k"] * (max(term["min"], val) if "min" in term else val)
        zero = formula.get("zero_if")
        if zero and get(zero["code"]) == zero["eq"]:
            return 0.0
        return max(formula["clamp_min"], total) if "clamp_min" in formula else total

    def test_derived_block(self):  # D-47
        derived = config_builder.build(self.env)["derived"]
        self.assertEqual(
            set(derived),
            {"energy/totals/p_now", "energy/sections/S1/p_kw", "energy/sections/S2/p_kw", "infra/ats/src1_ok",
             "infra/totals/grid_kw", "infra/totals/export_kw", "infra/totals/pv_now"},
        )  # fmt: skip
        lines = self.env["td.energy.node"].sudo().search([("kind", "=", "line")])
        self.assertEqual(
            {t["code"] for t in derived["energy/totals/p_now"]["terms"]},
            {"energy/lines/%s/p_now" % n.code for n in lines},
        )
        self.assertEqual(derived["infra/ats/src1_ok"], {"op": "ge", "code": "infra/ats/src1_state", "value": 1})
        self.assertEqual(
            [t["code"] for t in derived["infra/totals/grid_kw"]["terms"]],
            ["energy/cells/Q1/p_now", "energy/cells/Q2/p_now"],
        )
        self.assertEqual([t["k"] for t in derived["infra/totals/export_kw"]["terms"]], [-1.0, -1.0])
        self.assertTrue(all(t["min"] == 0.0 for t in derived["infra/totals/pv_now"]["terms"]))
        # блок входить до ETag: зміна формул (нова лінія) змінює ETag
        e0 = config_builder.etag(config_builder.build(self.env))
        line = self.env["td.energy.node"].sudo().search([("kind", "=", "line"), ("section", "=", 1)], limit=1)
        self.assertTrue(line)
        line.write({"section": 2})
        self.assertNotEqual(config_builder.etag(config_builder.build(self.env)), e0)

    def test_derived_matches_td_energy(self):  # D-47: формули дають ті самі значення, що td_energy (R-06, R-14)
        derived = config_builder.build(self.env)["derived"]
        Signal = self.env["td.signal"].sudo()
        codes = {t["code"] for f in derived.values() for t in f.get("terms", [])}
        codes |= {"infra/ats/src1_state", "infra/ats/position"}
        missing = [c for c in codes if not Signal.search_count([("code", "=", c)])]
        self.assertFalse(missing, missing)
        values = {}
        for i, code in enumerate(sorted(codes)):
            values[code] = float(i % 7) * 11.5 - (3.0 if code.startswith("infra/pv/") and i % 2 else 0.0)
        values.update(
            {
                "infra/ats/src1_state": 2.0,
                "infra/ats/position": 2.0,
                "energy/cells/Q1/p_now": 140.0,
                "energy/cells/Q2/p_now": -26.0,
            }
        )
        for code, val in values.items():
            self._fresh(code, val)
        Live = self.env["td.energy.node"]
        snap = Live._td_live_snapshot()
        get = values.get
        ev = self.evaluate
        self.assertEqual(snap["stale_feeders"], 0)
        self.assertAlmostEqual(ev(derived["energy/totals/p_now"], get), snap["totals"]["p_now"], places=6)
        for section in (1, 2):
            self.assertAlmostEqual(
                ev(derived["energy/sections/S%d/p_kw" % section], get),
                snap["totals"]["sections"][section]["p"],
                places=6,
            )
        self.assertAlmostEqual(ev(derived["infra/totals/pv_now"], get), snap["pv_now"], places=6)
        self.assertAlmostEqual(ev(derived["infra/totals/grid_kw"], get), snap["grid_kw"], places=6)
        self.assertAlmostEqual(ev(derived["infra/totals/export_kw"], get), snap["export_kw"], places=6)
        self.assertEqual(ev(derived["infra/ats/src1_ok"], get), 1.0)
        values["infra/ats/src1_state"] = 0.0
        self.assertEqual(ev(derived["infra/ats/src1_ok"], get), 0.0)
        values["infra/ats/position"] = 3.0  # острів: мережа 0, експорт 0
        self.assertEqual(
            (ev(derived["infra/totals/grid_kw"], get), ev(derived["infra/totals/export_kw"], get)), (0.0, 0.0)
        )
        del values["energy/cells/Q2/p_now"]  # відсутній терм → вхід відсутній
        self.assertIsNone(ev(derived["infra/totals/grid_kw"], get))
        values["infra/ats/position"] = 2.0
        self.assertEqual(ev(derived["infra/totals/export_kw"], get), None)
