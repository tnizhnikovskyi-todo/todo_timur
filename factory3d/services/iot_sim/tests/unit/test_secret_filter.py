"""ТБ-06: SecretFilter не пропускає секрети в логи (SPEC §8.16)."""

import io
import json
import logging

from iot_sim.config import Settings
from iot_sim.logging_conf import MASK, SecretFilter, collect_secrets, setup_logging

SECRETS = {"api_token": "T" * 40, "biostar_pass": "bio-pass-123", "odoo_apikey": "odoo-key-xyz"}


def make_logger(settings=None):
    buf = io.StringIO()
    setup_logging(settings, stream=buf)
    return logging.getLogger("iot_sim.test"), buf


def test_redacts_values_and_headers():
    f = SecretFilter(list(SECRETS.values()))
    assert f.redact("token=" + SECRETS["api_token"]) == f"token={MASK}"
    assert SECRETS["biostar_pass"] not in f.redact("login pass " + SECRETS["biostar_pass"])
    assert f.redact("bs-session-id: 123e4567-e89b") == f"bs-session-id: {MASK}"
    assert f.redact("Authorization: Bearer abcdef") == f"Authorization: {MASK}"
    assert f.redact('{"Authorization": "Bearer zzz"}') == '{"Authorization": "***"}'
    assert f.redact("нічого секретного") == "нічого секретного"


def test_json_log_format_and_masking():
    s = Settings(_env_file=None, **SECRETS)
    log, buf = make_logger(s)
    log.setLevel(logging.DEBUG)
    log.warning(
        "auth %s with %s", SECRETS["api_token"], SECRETS["odoo_apikey"], extra={"proto": "biostar", "device": "ACR-IN"}
    )
    try:
        raise RuntimeError("boom " + SECRETS["biostar_pass"])
    except RuntimeError:
        log.exception("failed bs-session-id=abc-def")
    out = buf.getvalue()
    for secret in SECRETS.values():
        assert secret not in out
    first = json.loads(out.splitlines()[0])
    assert set(first) >= {"ts", "level", "logger", "msg", "device", "signal", "run", "proto"}
    assert first["level"] == "WARNING" and first["proto"] == "biostar" and first["device"] == "ACR-IN"
    assert first["msg"] == f"auth {MASK} with {MASK}"
    assert "abc-def" not in out


def test_collects_env_secrets(monkeypatch):
    monkeypatch.setenv("SIM_JOBS_APIKEY", "jobs-key-777")
    monkeypatch.setenv("SIM_ODOO_EXPORT_TOKEN", "exp-tok-888")
    monkeypatch.setenv("SIM_TZ", "Europe/Kyiv")
    found = collect_secrets()
    assert "jobs-key-777" in found and "exp-tok-888" in found and "Europe/Kyiv" not in found


def test_plain_format_when_log_json_off():
    s = Settings(_env_file=None, log_json=False, **SECRETS)
    log, buf = make_logger(s)
    log.warning("pw %s", SECRETS["biostar_pass"])
    assert SECRETS["biostar_pass"] not in buf.getvalue() and MASK in buf.getvalue()
