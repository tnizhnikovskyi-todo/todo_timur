"""ТК-F01…ТК-F07 (SPEC td_genset §13.3.2): fake_relay с профилем D700 и REST /sim/v1/*.

Без Odoo: сервер поднимается на свободном порту, время «прожигается» через /_sim {"advance": N}.
Запуск: cd relay && python -m pytest -q tests   (или python -m unittest discover -s tests)
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

RELAY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RELAY_DIR)

import fake_relay  # noqa: E402
import genset_model  # noqa: E402

API_TOKEN = "api-token-0123456789abcdefghij"
SIM_TOKEN = "sim-token-secret-0123456789"


class Stand:
    """Сервер fake_relay в потоке + мини-клиент."""

    def __init__(self, profile="d700", sim_token=SIM_TOKEN, **kwargs):
        self.relay = fake_relay.Relay(API_TOKEN, [fake_relay.DEFAULT_HOSTID], snapshot_sec=60, noise=False,
                                      profile=profile, sim_token=sim_token, **kwargs)
        self.server = fake_relay.make_server(self.relay, "127.0.0.1", 0, quiet=True)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.relay.stop_event.set()
        self.server.shutdown()
        self.server.server_close()

    def call(self, method, path, body=None, token=SIM_TOKEN):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if token is not None:
            req.add_header("Authorization", "Bearer " + token)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, raw

    def get(self, path, token=SIM_TOKEN):
        return self.call("GET", path, token=token)

    def post(self, path, body=None, token=SIM_TOKEN):
        return self.call("POST", path, {} if body is None else body, token=token)

    def api(self, path):
        return self.get("/api/v1" + path, token=API_TOKEN)

    def state(self):
        status, data = self.get("/sim/v1/state")
        assert status == 200, data
        return data

    def advance(self, seconds):
        status, data = self.call("POST", "/_sim", {"advance": seconds}, token=API_TOKEN)
        assert status == 200, data

    def wait_state(self, state, limit=120, step=1):
        """Прожить до состояния `state`; вернуть сколько секунд прошло по sim_time (или None)."""
        elapsed = 0
        while elapsed <= limit:
            if self.state()["state"] == state:
                return elapsed
            self.advance(step)
            elapsed += step
        return None


class SimBase(unittest.TestCase):
    sim_token = SIM_TOKEN

    def setUp(self):
        self.stand = Stand(sim_token=self.sim_token)
        self.addCleanup(self.stand.close)


class TestF01Auth(SimBase):
    def test_state_with_token(self):
        status, data = self.stand.get("/sim/v1/state")
        self.assertEqual(status, 200)
        self.assertEqual(data["profile"], "D700")
        self.assertEqual(data["fuel_l"], 500.2)
        self.assertEqual(data["hours"], 1213.0)
        self.assertEqual(data["mode"], "auto")
        self.assertEqual(data["state_code"], 1)
        self.assertEqual(data["state"], "standby")
        self.assertEqual(data["starts"], 184)
        self.assertEqual(data["last_test"], "2026-10-12T07:30:00+03:00")
        self.assertTrue(data["sim_time"].endswith("+02:00") or data["sim_time"].endswith("+03:00"))

    def test_without_or_wrong_token(self):
        self.assertEqual(self.stand.get("/sim/v1/state", token=None)[0], 401)
        self.assertEqual(self.stand.get("/sim/v1/state", token="wrong")[0], 401)
        status, data = self.stand.get("/sim/v1/state", token=None)
        self.assertIn("detail", data)
        self.assertEqual(self.stand.api("/status")[0], 200)

    def test_unknown_resource(self):
        self.assertEqual(self.stand.get("/sim/v1/nothing")[0], 404)


class TestF01Disabled(SimBase):
    sim_token = ""

    def test_router_off(self):
        for path in ("/sim/v1/state", "/sim/v1/events"):
            self.assertEqual(self.stand.get(path)[0], 404)
            self.assertEqual(self.stand.get(path, token=None)[0], 404)
        self.assertEqual(self.stand.post("/sim/v1/load", {"kw": 100})[0], 404)
        self.assertEqual(self.stand.api("/status")[0], 200)
        self.assertEqual(self.stand.api("/commands")[0], 200)


class TestF02Validation(SimBase):
    def test_validation_and_over_current(self):
        s = self.stand
        self.assertEqual(s.post("/sim/v1/load", {"kw": 600})[0], 422)
        self.assertEqual(s.post("/sim/v1/fuel", {"liters": 700})[0], 422)
        self.assertEqual(s.post("/sim/v1/time", {"factor": 100})[0], 422)
        self.assertEqual(s.post("/sim/v1/fault", {"alarm": "nope"})[0], 422)
        self.assertEqual(s.post("/sim/v1/fuel", {"liters": 5, "pct": 5})[0], 422)
        self.assertEqual(s.post("/sim/v1/mains", {"available": "no"})[0], 422)
        # remote_start в manual → 409
        status, data = s.post("/api/v1/commands", {"command": "manual", "requested_by": "test"}, token=API_TOKEN)
        self.assertEqual(status, 201, data)
        s.advance(6)
        self.assertEqual(s.state()["mode"], "manual")
        status, data = s.post("/sim/v1/remote_start", {"on": True})
        self.assertEqual(status, 409, data)
        s.post("/sim/v1/reset", {})
        # перегруз между PRP и ESP → предупреждение через 30 с
        s.post("/sim/v1/mains", {"available": False})
        self.assertIsNotNone(s.wait_state("loaded", limit=60))
        status, data = s.post("/sim/v1/load", {"kw": 530})
        self.assertEqual(status, 200, data)
        s.advance(25)
        self.assertEqual(s.get("/sim/v1/events")[1]["items"], [])
        s.advance(10)
        items = s.get("/sim/v1/events")[1]["items"]
        self.assertEqual([(e["name"], e["severity"]) for e in items], [("Genset Over Current", "warning")])
        self.assertEqual(s.state()["alarm_level"], 1)


class TestF03Amf(SimBase):
    def _blackout(self, preset=None):
        s = self.stand
        s.post("/sim/v1/reset", {"preset": preset} if preset else {})
        starts = s.state()["starts"]
        status, data = s.post("/sim/v1/mains", {"available": False})
        self.assertEqual((status, data["state"]), (200, "mains_abnormal"))
        took = s.wait_state("loaded", limit=60)
        self.assertIsNotNone(took)
        st = s.state()
        self.assertEqual((st["breaker"], st["gen_ok"], st["p_kw"], st["starts"]), ("gen", True, 348.0, starts + 1))
        return took

    def test_default_timers(self):
        took = self._blackout()
        self.assertTrue(29 <= took <= 32, took)
        s = self.stand
        status, data = s.post("/sim/v1/mains", {"available": True})
        self.assertEqual(status, 200)
        back = s.wait_state("standby", limit=80)
        self.assertIsNotNone(back)
        self.assertTrue(39 <= back <= 45, back)
        st = s.state()
        self.assertEqual((st["breaker"], st["engine"]), ("mains", "stopped"))

    def test_plant_preset(self):
        took = self._blackout("plant")
        self.assertTrue(13 <= took <= 16, took)

    def test_sequence_codes(self):
        s = self.stand
        s.post("/sim/v1/mains", {"available": False})
        seen = []
        for _ in range(35):
            seen.append(s.state()["state"])
            s.advance(1)
        order = list(dict.fromkeys(seen))
        self.assertEqual(order, ["mains_abnormal", "starting", "safety_on", "warming", "running", "loaded"])

    def test_remote_start_variant_b(self):
        s = self.stand
        status, data = s.post("/sim/v1/remote_start", {"on": True})
        self.assertEqual((status, data["state"]), (200, "starting"))
        took = s.wait_state("running", limit=40)
        self.assertTrue(23 <= took <= 26, took)
        st = s.state()
        self.assertEqual((st["breaker"], st["gen_ok"], st["p_kw"]), ("mains", True, 0.0))
        s.post("/sim/v1/load", {"kw": 348})
        self.assertEqual(s.state()["state"], "loaded")
        s.post("/sim/v1/remote_start", {"on": False})
        self.assertIsNotNone(s.wait_state("standby", limit=60))
        self.assertIsNotNone(s.state()["last_test"])


class TestF04FailToStart(SimBase):
    def test_start_fail(self):
        s = self.stand
        s.post("/sim/v1/fault", {"alarm": "start_fail"})
        s.post("/sim/v1/mains", {"available": False})
        took = s.wait_state("alarm_shutdown", limit=90)
        self.assertIsNotNone(took)
        self.assertTrue(47 <= took <= 53, took)
        st = s.state()
        self.assertEqual((st["state_code"], st["alarm_level"], st["starts"]), (10, 2, 184))
        events = s.get("/sim/v1/events")[1]["items"]
        self.assertEqual([(e["name"], e["severity"]) for e in events], [("Fail to Start", "shutdown")])
        s.post("/sim/v1/mains", {"available": True})
        status, data = s.post("/sim/v1/clear", {})
        self.assertEqual((status, data["alarms"]), (200, []))
        self.assertEqual(s.state()["state"], "standby")


class TestF05Physics(SimBase):
    def test_one_hour(self):
        s = self.stand
        s.post("/sim/v1/mains", {"available": False})
        self.assertIsNotNone(s.wait_state("loaded", limit=60))
        s.post("/sim/v1/time", {"factor": 60.0})
        s.post("/sim/v1/load", {"kw": 348})
        before = s.state()
        self.assertEqual(before["factor"], 60.0)
        s.advance(60)
        after = s.state()
        burnt = before["fuel_l"] - after["fuel_l"]
        self.assertAlmostEqual(burnt, 95.5, delta=95.5 * 0.02)
        self.assertAlmostEqual(after["hours"] - before["hours"], 1.0, delta=0.02)
        self.assertAlmostEqual(after["kwh"] - before["kwh"], 348.0, delta=348 * 0.02)
        self.assertAlmostEqual(after["coolant_c"], 85.0, delta=2)
        self.assertEqual(after["alarms"], [])
        self.assertAlmostEqual(after["i_a"], 628.0, delta=1)


class TestF06EventsReset(SimBase):
    def test_ids_survive_reset(self):
        s = self.stand
        for _ in range(5):
            s.post("/sim/v1/fault", {"alarm": "low_fuel"})
            s.post("/sim/v1/clear", {"alarm": "low_fuel"})
        before = s.get("/sim/v1/events")[1]
        self.assertEqual(len(before["items"]), 5)
        max_before = before["next"]
        s.post("/sim/v1/mains", {"available": False})
        status, data = s.post("/sim/v1/reset", {"profile": "d700", "preset": "plant"})
        self.assertEqual((status, data), (200, {"ok": True, "profile": "D700", "preset": "plant"}))
        self.assertEqual(s.get("/sim/v1/events")[1]["items"], [])
        st = s.state()
        self.assertEqual((st["state"], st["mains_ok"], st["fuel_l"], st["starts"]), ("standby", True, 500.2, 184))
        for _ in range(2):
            s.post("/sim/v1/fault", {"alarm": "low_fuel"})
            s.post("/sim/v1/clear", {"alarm": "low_fuel"})
        new = s.get("/sim/v1/events?since=%d" % max_before)[1]
        self.assertEqual(len(new["items"]), 2)
        self.assertTrue(all(e["id"] > max_before for e in s.get("/sim/v1/events")[1]["items"]))
        self.assertEqual(s.post("/sim/v1/reset", {"preset": "bogus"})[0], 422)
        self.assertEqual(s.post("/sim/v1/reset", {"profile": "office"})[0], 422)

    def test_fuel_and_time(self):
        s = self.stand
        self.assertEqual(s.post("/sim/v1/fuel", {"add_liters": 50})[1], {"fuel_l": 550.2, "fuel_pct": 90.2})
        self.assertEqual(s.post("/sim/v1/fuel", {"pct": 82})[1], {"fuel_l": 500.2, "fuel_pct": 82.0})
        status, data = s.post("/sim/v1/time", {"factor": 10.0, "set": "2026-10-12T07:00:00+03:00"})
        self.assertEqual((status, data["factor"]), (200, 10.0))
        self.assertTrue(data["sim_time"].startswith("2026-10-12T07:00:0"))
        self.assertEqual(s.post("/sim/v1/time", {"set": "2026-10-12T07:00:00"})[0], 422)

    def test_low_fuel_alarms(self):
        s = self.stand
        s.post("/sim/v1/fuel", {"pct": 20})
        st = s.state()
        self.assertEqual([a["name"] for a in st["alarms"]], ["Low Fuel Level"])
        s.post("/sim/v1/fuel", {"pct": 50})
        self.assertEqual(s.state()["alarms"], [])


class TestF07CommLost(SimBase):
    def test_comm_lost(self):
        s = self.stand
        status, data = s.post("/sim/v1/fault", {"alarm": "comm_lost"})
        self.assertEqual(status, 200)
        self.assertEqual(data["alarms"][0]["code"], "comm_lost")
        self.assertEqual(s.api("/status")[0], 503)
        self.assertEqual(s.api("/latest")[0], 503)
        status, data = s.get("/sim/v1/state")
        self.assertEqual(status, 200)
        self.assertEqual(data["alarms"], [])
        s.post("/sim/v1/clear", {"alarm": "comm_lost"})
        self.assertEqual(s.api("/status")[0], 200)


class TestRelayApiReflectsModel(SimBase):
    def test_latest_reading_follows_sim(self):
        s = self.stand
        s.post("/sim/v1/mains", {"available": False})
        self.assertIsNotNone(s.wait_state("loaded", limit=60))
        s.advance(2)
        self.assertEqual(s.call("POST", "/_sim", {"snapshot": True}, token=API_TOKEN)[0], 200)
        status, data = s.api("/latest")
        self.assertEqual(status, 200)
        values = data["values"]
        self.assertTrue(values["gen_on_load"])
        self.assertEqual(values["active_power"], 348)
        self.assertEqual(values["fuel_level"], 82)


class TestProfiles(unittest.TestCase):
    def test_d700_json_is_sorted_export(self):
        path = os.path.join(genset_model.PROFILES_DIR, "d700.json")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        data = json.loads(text)
        self.assertEqual(text, json.dumps(data, sort_keys=True, indent=2) + "\n")
        self.assertEqual(data["profile"], "D700")
        self.assertEqual(data["rated"], {"kva_prp": 634, "kw_prp": 507, "kva_esp": 697, "kw_esp": 558})
        self.assertEqual(data["tank_l"], 610)
        self.assertEqual(data["timers_plant"]["mains_abnormal_s"], 2)
        self.assertEqual(data["start"]["load_kw"], 348)

    def test_office_json_matches_code(self):
        office = genset_model.load_profile("office")
        d700 = genset_model.load_profile("d700")
        for key in d700:
            self.assertIn(key, office)
            if isinstance(d700[key], dict):
                self.assertEqual(sorted(d700[key]), sorted(office[key]), key)
        self.assertEqual(office["tank_l"], fake_relay.TANK_L)
        self.assertEqual(office["timers"]["mains_abnormal_s"], fake_relay.REMOTE_DELAY_S)
        durations = dict(fake_relay.START_SEQ)
        self.assertEqual(office["timers"]["start_delay_s"], durations[1])
        self.assertEqual(office["timers"]["crank_s"], durations[3])
        self.assertEqual(office["timers"]["safety_on_s"], durations[5])
        self.assertEqual(office["timers"]["warming_s"], durations[7])
        self.assertEqual(office["timers"]["cooling_s"], dict(fake_relay.STOP_SEQ)[10])
        genset = fake_relay.Genset(noise=False)
        self.assertEqual(office["start"]["fuel_pct"], round(genset.fuel_l / fake_relay.TANK_L * 100))
        self.assertEqual(office["start"]["starts"], genset.start_count)
        self.assertEqual(office["start"]["load_kw"], genset._load_kw())
        self.assertEqual(office["sensors"]["batt_v"], genset.battery_rest)

    def test_office_profile_has_no_sim_router(self):
        stand = Stand(profile="office", sim_token=SIM_TOKEN)
        self.addCleanup(stand.close)
        self.assertEqual(stand.get("/sim/v1/state")[0], 404)
        status, data = stand.api("/status")
        self.assertEqual(status, 200)
        status, data = stand.call("POST", "/_sim", {"mains_normal": False}, token=API_TOKEN)
        self.assertEqual(status, 200)

    def test_token_not_in_logs(self):
        import logging

        formatter = fake_relay.JsonFormatter(secrets=(SIM_TOKEN,))
        record = logging.LogRecord("fake_relay", logging.INFO, __file__, 1, "token %s", (SIM_TOKEN,), None)
        line = json.loads(formatter.format(record))
        self.assertNotIn(SIM_TOKEN, json.dumps(line))
        self.assertEqual(sorted(line), sorted(["ts", "level", "msg", "state", "mode", "p_kw", "fuel_l", "event"]))


if __name__ == "__main__":
    unittest.main()
