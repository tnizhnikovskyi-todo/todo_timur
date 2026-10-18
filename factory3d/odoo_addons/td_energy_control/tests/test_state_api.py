"""AC-170, AC-223…AC-225: POST /td/energy/automation/state (API-25), стан рушія в `get_control`."""

import json
from datetime import timedelta

from odoo.tests import HttpCase, tagged

from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestStateApi(TestControlCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.col, cls.token = cls._collector()

    def post(self, body, token="default", raw=None):
        token = self.token if token == "default" else token
        hdrs = {"Content-Type": "application/json"}
        if token:
            hdrs["Authorization"] = "Bearer " + token
        return self.url_open(
            "/td/energy/automation/state", data=raw if raw is not None else json.dumps(body), headers=hdrs
        )

    def body(self, **kw):
        base = {"collector": self.col.code, "config_version_applied": 1, "engine": {"mode": "auto", "ticks": 5},
                "scenarios": {"peak": {"state": "armed", "facts": {"margin_kw": 402}}}, "actions": [], "events": []}  # fmt: skip
        base.update(kw)
        return base

    def test_report(self):  # AC-223
        act = self.run_action("bess_charge", user=self.u_en1)
        ev = {"event_id": "ab" * 16, "scenario": "peak", "kind": "auto_step", "text": "BESS · розряд 62 кВт",
              "signal": "energy_control/bess/mode", "value": 2}  # fmt: skip
        version = self.State.get().config_version
        resp = self.post(self.body(
            config_version_applied=version,
            actions=[{"id": act.id, "idem": act.idem, "state": "executing", "step": 1, "steps_total": 4},
                     {"id": 999999, "state": "done"}],
            events=[ev],
        ))  # fmt: skip
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual((data["accepted_actions"], data["accepted_events"]), (1, 1))
        self.assertEqual(data["rejected"], [{"id": 999999, "reason": "unknown_action"}])
        state = self.State.get()
        self.assertEqual((state.engine_mode, state.applied_version), ("auto", version))
        self.assertTrue(state.heartbeat_at)
        self.assertEqual(act.state, "executing")
        peak = self.Scenario.search([("code", "=", "peak")])
        self.assertEqual((peak.engine_state, peak.engine_facts["margin_kw"]), ("armed", 402))
        again = self.post(self.body(config_version_applied=version, events=[ev])).json()
        self.assertEqual(again["accepted_events"], 0)
        self.assertEqual(again["rejected"][0]["reason"], "duplicate")
        done = self.post(self.body(actions=[{"id": act.id, "idem": act.idem, "state": "done", "result": "ok"}])).json()
        self.assertEqual(done["accepted_actions"], 1)
        back = self.post(self.body(actions=[{"id": act.id, "idem": act.idem, "state": "failed"}])).json()
        self.assertEqual(back["rejected"][0]["reason"], "already_final")

    def test_limits_and_auth(self):  # AC-224
        self.assertEqual(self.post(self.body(actions=[{"id": 1, "state": "done"}] * 101)).status_code, 400)
        self.assertEqual(self.post(self.body(events=[{"event_id": "x", "text": "t"}] * 201)).status_code, 400)
        big = self.body(events=[{"event_id": "e%d" % i, "text": "x" * 1400} for i in range(200)])
        self.assertEqual(self.post(big).status_code, 413)
        self.assertEqual(self.post(None, raw="не json").status_code, 400)
        self.assertEqual(self.post(self.body(collector="OTHER")).status_code, 403)
        self.assertEqual(self.post(self.body(), token=None).status_code, 401)
        get = self.url_open("/td/energy/automation/state", headers={"Authorization": "Bearer " + self.token})
        self.assertEqual(get.status_code, 405)

    def test_control_events(self):  # AC-225
        evs = [{"event_id": "%032x" % i, "scenario": "peak", "kind": kind, "text": "Подія %s" % kind}
               for i, kind in enumerate(["interlock", "failsafe", "mode", "auto_step", "auto_release"])]  # fmt: skip
        self.post(self.body(events=evs))
        Event = self.env["td.energy.event"]
        kinds_ = Event.search([("kind", "=", "control")]).mapped("text")
        self.assertEqual(sorted(kinds_), sorted(["Подія interlock", "Подія failsafe", "Подія mode"]))
        self.assertEqual(
            self.Action.search_count([("origin", "=", "auto"), ("idem", "in", [e["event_id"] for e in evs])]), 5
        )
        old = Event.search([("kind", "=", "control")], limit=1)
        self.State.with_context(f3d_now=NOW + timedelta(hours=25))._td_watch()
        self.assertTrue(old.exists())

    def test_engine_label(self):  # AC-170
        state = self.State.get()
        ctl = self.ctl(self.u_view)
        state.write({"heartbeat_at": NOW - timedelta(seconds=2), "engine_mode": "auto"})
        eng = ctl.get_control()["engine"]
        self.assertEqual((eng["level"], eng["connected"]), ("ok", True))
        self.assertEqual(eng["label"], "Контролер ГРЩ і збирач на зв'язку · 14:19")
        state.write({"engine_mode": "hold", "engine_reason": "контролер у місцевому режимі"})
        self.assertEqual(ctl.get_control()["engine"]["level"], "warn")
        state.write({"heartbeat_at": NOW - timedelta(seconds=300)})
        eng = ctl.get_control()["engine"]
        self.assertEqual(eng["level"], "bad")
        self.assertEqual(eng["label"], "Збирач не на зв'язку · 5 хв")
        self._enable_control(automation=False)
        eng = ctl.get_control()["engine"]
        self.assertEqual(eng["level"], "warn")
        self.assertIn("автоматику призупинено", eng["label"].lower())
