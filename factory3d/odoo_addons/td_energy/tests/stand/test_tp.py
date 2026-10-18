"""ТП-01…ТП-06 (SPEC §13.4) на стенді: вимірювання в ``odoo-bin shell`` (perf_shell.py) на окремій базі без колектора.

Результати друкуються рядками ``TP <id> <json>`` (pytest -s) і заносяться до TEST_REPORT.md. Порядок важливий:
ТП-01 → ТП-02 (потрібні інтервали ТП-01) → ТП-03 → ТП-04 → ТП-06 → ТП-05 (останні два очищають профіль).
Межі: ТП-01 ≤ 30 с і ≤ 200 SQL; ТП-02 ≤ 5 с; ТП-03 ≤ 200 мс; ТП-04 приріст ≤ 15 %; ТП-05 ≤ 60 с/прогін і Index Scan;
ТП-06 ≤ 3 с.
"""

from __future__ import annotations

import json

import pytest

from helpers import shell_json

pytestmark = pytest.mark.stand


def perf(mode: str) -> dict:
    res = shell_json("perf_shell.py", "PERF", timeout=3000, PERF_MODE=mode)
    print(f"TP {mode} {json.dumps(res, ensure_ascii=False)}")
    return res


def test_tp01_cron_build():
    r = perf("tp01")
    assert r["readings"] == 57 * 2880 + (r["meters"] - 57) * 576
    assert r["build_s"] <= 30 and r["sql_queries"] <= 200, r


def test_tp02_alloc_day():
    r = perf("tp02")
    assert r["alloc_s"] <= 5, r


def test_tp03_payload():
    r = perf("tp03")
    assert r["median_ms"] <= 200, r


def test_tp04_ingest_override():
    r = perf("tp04")
    assert r["increase_pct"] <= 15, r


def test_tp06_read_group_year():
    r = perf("tp06")
    assert r["rows"] > 2_000_000 and max(r["read_group_s"]) <= 3, r


def test_tp05_rotation():
    r = perf("tp05")
    assert r["index_scan"], r["plan"]
    assert max(r["run_s"]) <= 60 + 5, r
