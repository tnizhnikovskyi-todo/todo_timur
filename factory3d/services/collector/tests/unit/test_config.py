"""AC-74, AC-82: конфігурація з env, код виходу 2, відсутній секрет."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import TOKEN, VirtualClock

from collector.core.config import Settings
from collector.core.metrics import Metrics
from collector.core.odoo_client import OdooClient
from collector.core.registry import Registry

from . import FakePlugin, sig_json, src_json

ROOT = Path(__file__).resolve().parents[2]
BASE_ENV = {
    "F3D_ODOO_URL": "http://127.0.0.1:1",
    "F3D_COLLECTOR_CODE": "COL-T",
    "F3D_COLLECTOR_TOKEN": TOKEN,
    "F3D_ALLOW_HOSTS": "iot-sim",
}


def _run(env_over: dict, drop: tuple = ()):
    env = {k: v for k, v in os.environ.items() if not k.startswith("F3D_")}
    env.update({k: v for k, v in BASE_ENV.items() if k not in drop})
    env.update(env_over)
    return subprocess.run(
        [sys.executable, "-m", "collector", "run"],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_token_too_short_exit2():
    short = "s" * 20
    p = _run({"F3D_COLLECTOR_TOKEN": short})
    assert p.returncode == 2
    assert short not in p.stdout + p.stderr and "F3D_COLLECTOR_TOKEN" in p.stderr


@pytest.mark.parametrize("name", ["F3D_ODOO_URL", "F3D_COLLECTOR_CODE", "F3D_COLLECTOR_TOKEN", "F3D_ALLOW_HOSTS"])
def test_required_env(name):
    p = _run({}, drop=(name,))
    assert p.returncode == 2 and name in p.stderr


def test_settings_defaults_and_csv(monkeypatch):
    for k, v in BASE_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("F3D_ALLOW_HOSTS", "iot-sim, mosquitto,10.0.3.0/24")
    monkeypatch.setenv("F3D_HTTP_PUSH_TOKEN_LPR", "whatever")  # динамічні змінні ігноруються
    s = Settings()
    assert s.allow_hosts == ["iot-sim", "mosquitto", "10.0.3.0/24"]
    assert (s.config_poll_s, s.push_interval_s, s.push_max, s.status_interval_s, s.commands_poll_s) == (
        60,
        5,
        1000,
        60,
        5,
    )
    assert s.write_enabled is False and s.metrics_port == 9108 and s.http_push_port == 8080
    assert s.buffer_max_mb == 200 and s.log_json is True and s.clock_skew_warn_s == 30
    monkeypatch.setenv("F3D_WRITE_ENABLED", "1")
    assert Settings().write_enabled is True


async def test_missing_secret_ref(fake_odoo, settings, monkeypatch):
    monkeypatch.delenv("F3D_MQTT_PASSWORD", raising=False)
    fake_odoo.config = {
        "sources": [
            src_json("MQ", params={"password_ref": "F3D_MQTT_PASSWORD"}, signals=[sig_json("equipment/A/x")]),
            src_json("OK", signals=[sig_json("equipment/B/x")]),
        ]
    }
    client = OdooClient(fake_odoo.url, TOKEN, clock=VirtualClock())
    reg = Registry(client, settings, lambda s: None, VirtualClock(), Metrics(), plugin_classes={"fake": FakePlugin})
    await reg.load()
    await client.close()
    assert reg.errors["MQ"].state == "error"
    assert reg.errors["MQ"].error == "secret F3D_MQTT_PASSWORD not set"
    assert "OK" in reg.connected and "MQ" not in reg.plugins
