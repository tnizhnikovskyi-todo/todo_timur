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
