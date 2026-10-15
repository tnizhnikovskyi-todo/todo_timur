"""AC-83: CLI check-config, dump-config, drain-buffer."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from conftest import T0

from collector.core.buffer import Buffer
from collector.core.types import Reading

from . import sig_json, src_json

ROOT = Path(__file__).resolve().parents[2]


async def _cli(*args: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "collector",
        *args,
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await asyncio.wait_for(proc.communicate(), 30)
    return proc.returncode or 0, out.decode(), err.decode()


async def test_check_config_ok(fake_odoo, settings):
    code, out, _ = await _cli("check-config")
    assert code == 0 and "ok" in out
    assert any(c[1].endswith("/health") for c in fake_odoo.calls)


async def test_check_config_401(fake_odoo, settings, monkeypatch):
    monkeypatch.setenv("F3D_COLLECTOR_TOKEN", "x" * 43)
    code, _, err = await _cli("check-config")
    assert code == 1 and "x" * 43 not in err


async def test_dump_config_no_secrets(fake_odoo, settings):
    fake_odoo.config = {
        "sources": [
            src_json(
                "MQ",
                type_="mqtt",
                params={"host": "mosquitto", "password_ref": "F3D_MQTT_PASSWORD", "token_ref": "F3D_X"},
                signals=[sig_json("equipment/A/x")],
            )
        ]
    }
    code, out, _ = await _cli("dump-config")
    assert code == 0
    data = json.loads(out)
    assert data["sources"][0]["params"] == {"host": "mosquitto"}
    assert "password" not in out.lower() and "token" not in out.lower()


async def test_drain_buffer(fake_odoo, settings):
    b = Buffer(settings.buffer_dir / "buffer.sqlite", 10)
    await b.put_many([Reading(f"equipment/A/c{i}", T0, value=1.0) for i in range(5)])
    await b.close()
    code, out, _ = await _cli("drain-buffer")
    assert code == 0 and "drained 5" in out
    b = Buffer(settings.buffer_dir / "buffer.sqlite", 10)
    assert await b.count() == 0
    await b.close()
    assert any(c[1].endswith("/push") for c in fake_odoo.calls)


async def test_app_smoke(fake_odoo, settings):
    from collector.core.app import Collector

    settings.metrics_port = 0
    fake_odoo.config = {"read_enabled": True, "write_enabled": False, "sources": []}
    app = Collector(settings)
    await app.start()
    try:
        assert app.registry.etag == "etag-1" and app.metrics.health()["status"] == "ok"
        await app.pusher.push_once()
    finally:
        await app.stop()
