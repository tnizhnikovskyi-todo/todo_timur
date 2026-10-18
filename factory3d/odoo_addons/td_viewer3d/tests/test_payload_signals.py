from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.td_viewer3d.models import viewer_provider_signals as sig

from .common import F3dViewerBase, F3dViewerCase

PROV = "td.viewer.provider.signals"


def _row(code, value, unit="", mode="noise", charging=False, updated=None, state="норма"):
    return {"x_code": code, "x_value": value, "x_unit": unit, "x_mode": mode, "x_charging": charging,
            "x_updated": updated, "x_state": state}


def _payload():
    return {
        "meta": {}, "energy": {"consumers": {"SAW-1": {"p_now": 0.0}}, "transformers": {}, "totals": {}},
        "equipment": {"FL-1": {"state": "idle", "battery": 1.0}},
        "ventilation": {"units": {}}, "fire": {"groups": {}},
        "infra": {"totals": {"pv_now": 55.5, "chp_kw": 120.0}},
    }


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestSignalsMocked(F3dViewerBase):
    """Алгоритм M-01h з підміненим читанням: працює і без td_iot_sim."""

    def _run(self, rows, payload=None, user=None):
        payload = payload if payload is not None else _payload()
        ctx = {"sections": {}, "changes": {}}
        env = self.env(user=user or self.user_f3d)
        with patch.object(sig, "SIGNAL_MODEL", "res.partner"), \
                patch.object(type(env[PROV]), "_f3d_signal_rows", lambda s, codes=None: rows):
            env[PROV]._f3d_viewer_collect(payload, ctx)
        return payload, ctx

    def test_paths_applied(self):
        """AC-17."""
        data, ctx = self._run([_row("energy/consumers/SAW-1/p_now", 13.1234, "кВт"),
                               _row("equipment/FL-1/battery", 57.1, "%", "drain", True)])
        self.assertEqual(data["energy"]["consumers"]["SAW-1"]["p_now"], 13.12)
        self.assertEqual(data["equipment"]["FL-1"]["battery"], 0.571)
        self.assertEqual(data["equipment"]["FL-1"]["state"], "charging")
        self.assertEqual(data["meta"]["iot"]["signals"], 2)
        self.assertEqual(ctx["sections"]["signals"], "live")

    def test_missing_node_skipped(self):
        data, _ctx = self._run([_row("energy/consumers/NOPE-1/p_now", 5.0), _row("lighting/x/y", 1.0)])
        self.assertNotIn("NOPE-1", data["energy"]["consumers"])
        self.assertNotIn("lighting", data)

    def test_percent_to_fraction(self):
        self.assertEqual(sig.signal_value(_row("a/b/c", 57.1, "%")), 0.571)
        self.assertEqual(sig.signal_value(_row("a/b/c", 100.0, "%")), 1.0)

    def test_rounding(self):
        self.assertEqual(sig.signal_value(_row("a/b/c", 19.999)), 20.0)
        self.assertEqual(sig.signal_value(_row("a/b/c", 123.456)), 123.5)
        self.assertEqual(sig.signal_value(_row("a/b/c", -3.456)), -3.46)

    def test_drain_state(self):
        data, _ctx = self._run([_row("equipment/FL-1/battery", 40.0, "%", "drain", False)])
        self.assertEqual(data["equipment"]["FL-1"]["state"], "busy")

    def test_totals_copied(self):
        data, _ctx = self._run([])
        self.assertEqual(data["energy"]["totals"], {"pv_kw": 55.5, "chp_kw": 120.0})

    def test_meta_iot(self):
        from datetime import datetime
        rows = [_row("energy/consumers/SAW-1/p_now", 1.0, state="тривога", updated=datetime(2026, 10, 12, 7, 30, 0)),
                _row("equipment/FL-1/battery", 50.0, "%", updated=datetime(2026, 10, 12, 7, 20, 0))]
        data, _ctx = self._run(rows)
        self.assertEqual(data["meta"]["iot"], {"source": sig.IOT_SOURCE, "signals": 2, "alarms": 1,
                                               "updated": "2026-10-12 10:30"})

    def test_missing_model(self):
        payload = _payload()
        ctx = {"sections": {}}
        with patch.object(sig, "SIGNAL_MODEL", "x_f3d_nonexistent"):
            self.env[PROV]._f3d_viewer_collect(payload, ctx)
        self.assertEqual(ctx["sections"]["signals"], "missing")
        self.assertNotIn("iot", payload["meta"])
        self.assertEqual(payload["energy"]["consumers"]["SAW-1"]["p_now"], 0.0)

    def test_delta_signals(self):
        rows = [_row("energy/consumers/SAW-1/p_now", 13.1, "кВт")]
        env = self.env(user=self.user_f3d)
        patch_ = {}
        ctx = {"changes": {"res.partner": {"energy/consumers/SAW-1/p_now"}}}
        with patch.object(sig, "SIGNAL_MODEL", "res.partner"), \
                patch.object(type(env[PROV]), "_f3d_signal_rows", lambda s, codes=None: rows):
            env[PROV]._f3d_viewer_delta(patch_, ctx)
        self.assertEqual(patch_["signals"], [{"path": "energy/consumers/SAW-1/p_now", "value": 13.1}])
        self.assertEqual(patch_["meta"]["iot"]["signals"], 1)

    def test_registered(self):
        self.assertEqual(self.env[PROV]._f3d_sequence, 90)


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestSignals(F3dViewerCase):
    """З демо-базою і `x_f3d_signal` (td_iot_sim)."""

    def setUp(self):
        super().setUp()
        if "x_f3d_signal" not in self.env:
            self.skipTest("немає x_f3d_signal")

    def _set(self, code, **vals):
        rec = self.env["x_f3d_signal"].sudo().search([("x_code", "=", code)], limit=1)
        if not rec:
            self.skipTest(f"немає сигналу {code}")
        rec.write(vals)

    def test_live_paths(self):
        """AC-17."""
        self._set("energy/consumers/SAW-1/p_now", x_value=13.1)
        self._set("equipment/FL-1/battery", x_value=57.1, x_mode="drain", x_charging=True)
        data = self.payload(self.user_f3d)
        self.assertEqual(data["energy"]["consumers"]["SAW-1"]["p_now"], 13.1)
        self.assertEqual(data["equipment"]["FL-1"]["battery"], 0.571)
        self.assertEqual(data["equipment"]["FL-1"]["state"], "charging")
        self.assertEqual(data["meta"]["iot"]["signals"], 196)
        self.assertEqual(data["meta"]["sections"]["signals"], "live")
