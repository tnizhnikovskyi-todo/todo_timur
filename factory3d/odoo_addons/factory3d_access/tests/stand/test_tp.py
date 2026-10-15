"""ТП-01…ТП-04 (SPEC §13.4) на стенді. Порядок: ТП-02, ТП-01 (лавина), ТП-03, ТП-04.

Результати друкуються рядками ``TP <id> <json>`` (pytest -s / -rA) і заносяться до TEST_REPORT.md.
Межі: ТП-01 ≤ 60 с і 20 запитів; ТП-02 опитування ≤ 2 с, CPU воркера < 5 %; ТП-03 collect ≤ 200 мс,
f3d_people_now (45 зон) ≤ 50 мс, Index Scan по ts; ТП-04 ротація 130 000 подій ≤ 120 с.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from helpers import kyiv_iso

pytestmark = pytest.mark.stand
HERE = Path(__file__).resolve().parent
PROXY_LOG = os.environ.get("F3D_PROXY_LOG")


def report(tp: str, data: dict):
    print(f"TP {tp} {json.dumps(data, ensure_ascii=False)}")


def odoo_cpu_seconds() -> float | None:
    """CPU-секунди процесу Odoo (utime+stime з /proc), pid — F3D_ODOO_PID або файл F3D_ODOO_PID_FILE."""
    pid = os.environ.get("F3D_ODOO_PID")
    path = os.environ.get("F3D_ODOO_PID_FILE")
    if not pid and path and os.path.exists(path):
        pid = Path(path).read_text().strip()
    if not pid:
        return None
    parts = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return (int(parts[11]) + int(parts[12])) / os.sysconf("SC_CLK_TCK")


def proxy_lines() -> int:
    return len(Path(PROXY_LOG).read_text().splitlines()) if PROXY_LOG and os.path.exists(PROXY_LOG) else 0


def shell_perf(mode: str, **env_extra) -> dict:
    """Запускає perf_shell.py в ``odoo-bin shell`` тієї ж бази (потрібні env.sh фабрики: F3D_ENV_SH)."""
    env_sh = os.environ.get("F3D_ENV_SH")
    if not env_sh:
        pytest.skip("F3D_ENV_SH (factory3d/tools/odoo/env.sh) не задано: odoo shell недоступний")
    cmd = (f'source "{env_sh}" && "$ODOO_PY" "$ODOO_BIN" shell -c "$ODOO_CONF" --addons-path="$ODOO_ADDONS_PATH" '
           f'-d "{os.environ["F3D_ODOO_DB"]}" --no-http --log-level=warn < "{HERE / "perf_shell.py"}"')
    res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=1500,
                         env={**os.environ, "PERF_MODE": mode, **env_extra})
    lines = [x for x in res.stdout.splitlines() if x.startswith("PERF ")]
    assert lines, (res.stdout[-500:], res.stderr[-500:])
    return json.loads(lines[-1][5:])


# ---------------------------------------------------------------------------------------------- ТП-02
def test_tp02_daily_volume(odoo, sim, server_id):
    """1 400 подій/добу по 1 хв: час одного опитування і CPU Odoo на опитування (екстраполяція на 1 440 прогонів)."""
    people = [e["barcode"] for e in odoo.k("hr.employee", "search_read", [("barcode", "like", "OPSAW")], ["barcode"])]
    durations, rows = [], []
    cpu0 = odoo_cpu_seconds()
    wall0 = time.perf_counter()
    for i in range(30):
        sim.access_event("ACR-ELEC", people[i % len(people)], 4102, "", door_open=True)
        time.sleep(1.3)
        t0 = time.perf_counter()
        odoo.poll(server_id)
        durations.append(time.perf_counter() - t0)
        rows.append(odoo.k("f3d.access.server", "read", [server_id], ["last_poll_rows"])[0]["last_poll_rows"])
    cpu1 = odoo_cpu_seconds()
    data = {"polls": len(durations), "mean_s": round(statistics.mean(durations), 3),
            "max_s": round(max(durations), 3), "p95_s": round(sorted(durations)[int(0.95 * len(durations)) - 1], 3),
            "rows_per_poll_mean": round(statistics.mean(rows), 1)}
    if cpu0 is not None:
        per_poll = (cpu1 - cpu0) / len(durations)
        data["cpu_s_per_poll"] = round(per_poll, 3)
        data["cpu_pct_at_1_poll_per_min"] = round(100 * per_poll / 60, 2)
    data["wall_s"] = round(time.perf_counter() - wall0, 1)
    report("02", data)
    assert data["max_s"] <= 2.0, data
    if "cpu_pct_at_1_poll_per_min" in data:
        assert data["cpu_pct_at_1_poll_per_min"] < 5, data


# ---------------------------------------------------------------------------------------------- ТП-01
def test_tp01_avalanche(odoo, sim, server_id, bs_http):
    """Лавина після «простою»: ≥ 10 000 рядків у BioStar, одне `action_poll_now` (20 сторінок × 500) ≤ 60 с."""
    q = {"Query": {"limit": 1, "offset": 0, "orders": [{"column": "datetime", "descending": False}]}}

    def total():
        return int(bs_http.post("/api/events/search", json=q).json()["EventCollection"]["total"])
    first_day = day = datetime.now() - timedelta(days=60)
    while total() < 10_500 and day < datetime.now() - timedelta(days=2):
        sim.set_time(kyiv_iso(day.strftime("%Y-%m-%d"), "23:30"), 10)
        time.sleep(1.6)           # tick 1 с: розклад доби викидається одразу (події мають свої `when`)
        day += timedelta(days=1)
    rows_in_sim = total()
    assert rows_in_sim >= 10_000, rows_in_sim
    odoo.param("max_pages_per_run", "20")
    odoo.param("page_size", "500")
    # initial_lookback_h обмежено 168 год (R-04): «простій» моделюється курсором на добу до першої події лавини
    cursor = (first_day - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
    odoo.k("f3d.access.server", "write", [server_id], {"last_event_ts": cursor, "last_event_biostar_id": False})
    lines0 = proxy_lines()
    cpu0 = odoo_cpu_seconds()
    t0 = time.perf_counter()
    odoo.poll(server_id)
    elapsed = time.perf_counter() - t0
    srv = odoo.k("f3d.access.server", "read", [server_id], ["last_poll_rows", "last_poll_new", "last_poll_more"])[0]
    data = {"sim_rows": rows_in_sim, "poll_s": round(elapsed, 2), "rows": srv["last_poll_rows"],
            "new": srv["last_poll_new"], "more": srv["last_poll_more"]}
    if PROXY_LOG:
        new_lines = Path(PROXY_LOG).read_text().splitlines()[lines0:]
        data["search_requests"] = sum(1 for x in new_lines if x.startswith("POST /api/events/search"))
    if cpu0 is not None:
        data["cpu_s"] = round(odoo_cpu_seconds() - cpu0, 1)
    report("01", data)
    assert elapsed <= 60, data
    assert srv["last_poll_rows"] >= 9_000, data
    if "search_requests" in data:
        assert data["search_requests"] <= 21, data


# ---------------------------------------------------------------------------------------------- ТП-03
def test_tp03_provider_and_people_now(odoo, server_id):
    """130 000 подій у таблиці: `_f3d_viewer_collect` ≤ 200 мс, `f3d_people_now` 45 зон ≤ 50 мс, Index Scan по ts."""
    res = shell_perf("collect")
    report("03", res)
    assert res["events_total"] >= 130_000
    assert min(res["collect_ms"]) <= 200 and statistics.median(res["collect_ms"]) <= 200, res
    assert statistics.median(res["people_now_ms"]) <= 50, res
    assert res["explain_today_index"], res
    # через RPC (з мережею й сериалізацією) — довідково
    t0 = time.perf_counter()
    zones = odoo.k("f3d.zone", "search_read", [], ["f3d_people_now"])
    report("03-rpc", {"zones": len(zones), "rpc_ms": round((time.perf_counter() - t0) * 1000, 1)})


# ---------------------------------------------------------------------------------------------- ТП-04
def test_tp04_housekeeping(odoo, server_id):
    """130 000 подій старших за keep_days: `_cron_housekeeping` ≤ 120 с, пакети по 5 000."""
    res = shell_perf("gc")
    report("04", res)
    assert res["old_before"] >= 130_000
    assert res["old_after"] == 0
    assert res["housekeeping_s"] <= 120, res
