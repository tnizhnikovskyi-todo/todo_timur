from datetime import datetime

import requests
from odoo.tests import tagged

from .common import SIM_TOKEN, SIM_URL, TAG_ARGS, FakeResponse, SimCase

LOGGER = "odoo.addons.td_iot_sim.models.sim_device"
OK = {"ok": 0, "unknown": []}


class NotJsonResponse(FakeResponse):
    def json(self):
        raise ValueError("not json")


@tagged(*TAG_ARGS)
class TestPushMachineTargets(SimCase):
    """C-LP-01: `td.sim.device._td_push_machine_targets(targets)` — клієнт `POST /api/v1/machines/targets`."""

    def setUp(self):
        super().setUp()
        self.http = []  # запити до емулятора: dict(method, url, json, headers, timeout)
        self.reply = (200, {"ok": 2, "unknown": []})
        self.request_mock.side_effect = self._targets_request
        self.targets = [
            {"code": "SAW-1", "state": "working", "reason": None, "until": "2026-10-21T10:15:00Z"},
            {"code": "CNC-2", "state": "down", "reason": "spindle", "until": "2026-10-21T10:30:00Z"},
        ]

    def _targets_request(self, method, url, **kwargs):
        self.http.append(dict(kwargs, method=method, url=url))
        if isinstance(self.reply, Exception):
            raise self.reply
        status, data = self.reply
        return NotJsonResponse(status) if isinstance(data, Exception) else FakeResponse(status, data)

    def push(self, targets=None):
        return self.env["td.sim.device"]._td_push_machine_targets(self.targets if targets is None else targets)

    def test_posts_body_with_sim_token_to_configured_url(self):
        self.reply = (200, {"ok": 1, "unknown": ["CNC-2"]})
        result = self.push()
        self.assertEqual(result, {"ok": 1, "unknown": ["CNC-2"]})
        (call,) = self.http
        self.assertEqual((call["method"], call["url"]), ("POST", SIM_URL + "/api/v1/machines/targets"))
        self.assertEqual(call["json"], self.targets)
        self.assertEqual(call["headers"]["Authorization"], "Bearer " + SIM_TOKEN)
        self.assertEqual(call["timeout"], 5)

    def test_trailing_slash_in_url_and_datetime_until(self):
        self.set_params(url=SIM_URL + "/")
        self.push([{"code": "SAW-1", "state": "idle", "until": datetime(2026, 10, 21, 10, 15, 0)}])
        (call,) = self.http
        self.assertEqual(call["url"], SIM_URL + "/api/v1/machines/targets")
        self.assertEqual(
            call["json"], [{"code": "SAW-1", "state": "idle", "reason": None, "until": "2026-10-21T10:15:00Z"}]
        )

    def test_connection_error_returns_zero_with_warning(self):
        for exc in (requests.ConnectionError("refused"), requests.Timeout("slow")):
            with self.subTest(exc=exc.__class__.__name__):
                self.reply = exc
                with self.assertLogs(LOGGER, level="WARNING") as logs:
                    self.assertEqual(self.push(), OK)
                self.assertNotIn(SIM_TOKEN, "\n".join(logs.output))

    def test_http_error_returns_zero_with_warning(self):
        for status in (401, 403, 422, 423, 500):
            with self.subTest(status=status):
                self.reply = (status, {"detail": "x"})
                with self.assertLogs(LOGGER, level="WARNING"):
                    self.assertEqual(self.push(), OK)

    def test_garbage_response_returns_zero(self):
        for data in (ValueError("not json"), ["list"], {"ok": "abc"}):
            with self.subTest(data=data):
                self.reply = (200, data)
                with self.assertLogs(LOGGER, level="WARNING"):
                    self.assertEqual(self.push(), OK)

    def test_write_stop_crane_off_sends_nothing(self):
        self.set_params(write_enabled="False")
        self.assertEqual(self.push(), OK)
        self.assertFalse(self.http)

    def test_no_url_sends_nothing(self):
        self.set_params(url="")
        self.assertEqual(self.push(), OK)
        self.assertFalse(self.http)

    def test_empty_targets_send_nothing(self):
        self.assertEqual(self.push([]), OK)
        self.assertEqual(self.env["td.sim.device"]._td_push_machine_targets(None), OK)
        self.assertFalse(self.http)

    def test_input_is_not_mutated_and_no_command_event(self):
        before = [dict(t) for t in self.targets]
        events = self.env["td.sim.event"].search_count([("kind", "=", "command")])
        self.push()
        self.assertEqual(self.targets, before)
        self.assertEqual(self.env["td.sim.event"].search_count([("kind", "=", "command")]), events)
