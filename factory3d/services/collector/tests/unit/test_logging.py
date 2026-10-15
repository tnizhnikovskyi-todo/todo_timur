"""AC-82: SecretFilter, JSON-логи, /metrics без секретів."""
from __future__ import annotations

import io
import json
import logging

from collector.core.logging_conf import SecretFilter, mask, setup_logging
from collector.core.metrics import Metrics

TOKEN = "T0kenValue" + "x" * 33


def test_secret_filter_masks(caplog, monkeypatch):
    monkeypatch.setenv("F3D_COLLECTOR_TOKEN", TOKEN)
    monkeypatch.setenv("F3D_MQTT_PASSWORD", "Hunter22")
    caplog.handler.addFilter(SecretFilter())
    log = logging.getLogger("collector.test")
    with caplog.at_level(logging.INFO):
        log.info("GET http://odoo/x?password=Secr3t&token=abc999 Authorization: Bearer abc123def")
        log.info("headers %s", {"X-F3D-Token": "zzz-secret"})
        log.warning("token is %s and pass %s", TOKEN, "Hunter22")
    text = caplog.text
    for secret in ("Secr3t", "abc999", "abc123def", "zzz-secret", TOKEN, "Hunter22"):
        assert secret not in text
    assert "***" in text


def test_mask_plain():
    assert mask("nothing to hide") == "nothing to hide"
    assert mask("Authorization: Bearer abc123") == "Authorization: ***"


def test_json_format_and_extra(monkeypatch):
    monkeypatch.setenv("F3D_COLLECTOR_TOKEN", TOKEN)
    buf = io.StringIO()
    handler = setup_logging("INFO", True, stream=buf)
    try:
        logging.getLogger("collector.x").info("hello %s", TOKEN, extra={"source": "S1", "cmd": 3})
    finally:
        logging.getLogger().removeHandler(handler)
    rec = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert rec["level"] == "INFO" and rec["logger"] == "collector.x" and rec["source"] == "S1" and rec["cmd"] == 3
    assert TOKEN not in buf.getvalue() and rec["msg"] == "hello ***" and rec["ts"].endswith("Z")


def test_metrics_no_secrets(monkeypatch):
    monkeypatch.setenv("F3D_COLLECTOR_TOKEN", TOKEN)
    m = Metrics()
    m.readings.labels("S1").inc()
    m.config_etag_info.labels("abc").set(1)
    out = m.render().decode()
    assert TOKEN not in out and "password" not in out.lower() and "token" not in out.lower()
