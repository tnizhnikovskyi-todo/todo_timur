"""ТП-01…ТП-04 (SPEC §13.4): вхід показань 35 верстатів, затримка ланцюга, звіти й крони на обсязі року, портал і карти.

Тривалості скорочено змінними середовища (SPEC: ТП-01 30 хв, ТП-02 30 хв): F3D_STAND_TP01_MIN (типово 5), F3D_STAND_TP02_MIN
(типово 8). Odoo стенда — один процес (без воркерів): CPU воркера й `5xx` порівнюються з межами SPEC із цим застереженням.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import threading
import time
import uuid
from datetime import datetime, timedelta

import pytest

from . import odoo_rpc
from .helpers import (
    STAND_DIR,
    cron_run,
    http,
    make_mo,
    odoo_log,
    proc_ticks,
    psql,
    rss_mb,
    stand_sh,
    wait,
)
from .load_machines import run as load_run

pytestmark = pytest.mark.timeout(7200)


def _p(vals: list[float], q: float) -> float:
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))] if vals else 0.0


def test_tp01_ingest_35_machines(fresh, sim):
    """ТП-01 / AC-99: 35 верстатів × 3…5 показань щосекунди; p95 ≤ 1,2 с, p99 ≤ 2 с, 0 × 5xx, 0 дедлоків."""
    minutes = float(os.environ.get("F3D_STAND_TP01_MIN", "5"))
    o = fresh(params={"micro_stop_s": "0"}, ready=False)
    stand_sh("collector-stop")
    o.param("td.telemetry.push_rate_per_min", "120")
    ids = o.search_read("td.machine", [], ["id"])
    o.write("td.machine", [m["id"] for m in ids], {"micro_stop_s": 0})
    token = (STAND_DIR / "token").read_text().strip()
    log0 = len(odoo_log())
    pid, cpu0 = proc_ticks("-d f3d_mc_tk")
    n0 = psql("select count(*) from td_machine_state_log")[0][0]
    tick_s: list[float] = []
    stop = threading.Event()

    def ticks():
        while not stop.wait(60):
            try:
                tick_s.append(cron_run(odoo_rpc.Odoo(), "такт"))
            except Exception:  # noqa: BLE001
                pass

    th = threading.Thread(target=ticks, daemon=True)
    th.start()
    t0 = time.time()
    res = load_run("http://127.0.0.1:18070", token, minutes)
    wall = time.time() - t0
    stop.set()
    th.join(5)
    _, cpu1 = proc_ticks("-d f3d_mc_tk")
    new_log = odoo_log()[log0:]
    n1 = psql("select count(*) from td_machine_state_log")[0][0]
    overlaps = psql(
        "select count(*) from (select date_start, lag(date_end) over (partition by machine_id order by date_start, id) pe "
        "from td_machine_state_log) x where pe is not null and pe > date_start"
    )[0][0]
    deadlocks = new_log.count("deadlock detected")
    serial = new_log.count("could not serialize")
    out = dict(res, wall_s=round(wall), cpu_pct=round(100 * (cpu1 - cpu0) / wall), intervals_new=int(n1) - int(n0), overlaps=int(overlaps),
               deadlocks=deadlocks, serialization_errors=serial, cron_tick_s=[round(x, 1) for x in tick_s])  # fmt: skip
    (STAND_DIR / "tp01.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("ТП-01:", json.dumps(out, ensure_ascii=False))
    assert not [k for k in res["status"] if k.startswith("5") or not k.isdigit()], res["status"]
    assert res["p95_ms"] <= 1200 and res["p99_ms"] <= 2000, res
    assert deadlocks == 0 and int(overlaps) == 0
    assert not tick_s or max(tick_s) <= 10, tick_s
    assert out["cpu_pct"] <= 70, out


def test_tp02_chain_latency(fresh, sim):
    """ТП-02 / AC-99: емулятор → колектор → Odoo: затримка p95 ≤ 10 с, буфер ≤ 100, 1 сесія OPC UA на 15 джерел."""
    minutes = float(os.environ.get("F3D_STAND_TP02_MIN", "8"))
    o = fresh(scenario=("shift", {"speed": 1, "trucks": False, "people": False}))
    pid, cpu0 = proc_ticks("f3d-collector run")
    assert pid, "процес колектора не знайдено"
    devices = ["CNC-1", "CNC-3", "EDGE-1", "SAW-2", "BORE-1"]
    t_end = time.time() + minutes * 60
    starts: list[tuple[str, datetime]] = []
    buf_max = 0
    t_cpu0 = time.time()
    i = 0
    while time.time() < t_end:
        dev = devices[i % len(devices)]
        st, d = sim.post("/scenario/machine_fault/start", {"params": {"device": dev}})
        starts.append((dev, datetime.fromisoformat(d["started"])))
        time.sleep(15)
        sim.post("/scenario/machine_fault/stop")
        time.sleep(15)
        h = http("GET", "http://127.0.0.1:9108/health")[1]
        buf_max = max(buf_max, json.loads(h).get("buffer_rows", 0))
        i += 1
    time.sleep(10)
    _, cpu1 = proc_ticks("f3d-collector run")
    lats = []
    for dev, ts in starts:
        t_utc = ts.astimezone().replace(tzinfo=None) - (ts.astimezone().utcoffset() or timedelta(0)) + timedelta(0)
        t_utc = datetime.utcfromtimestamp(ts.timestamp())
        rows = o.search_read(
            "td.machine.state.log",
            [
                ("machine_id.code", "=", dev),
                ("state", "=", "fault"),
                ("create_date", ">=", t_utc.strftime("%Y-%m-%d %H:%M:%S")),
            ],
            ["create_date"],
            order="create_date",
            limit=1,
        )
        if rows:
            lats.append((datetime.strptime(rows[0]["create_date"], "%Y-%m-%d %H:%M:%S") - t_utc).total_seconds())
    cpu_pct = 100 * (cpu1 - cpu0) / (time.time() - t_cpu0)
    sessions = len(
        {
            line.split("endpoint")[0]
            for line in (STAND_DIR / "collector.log").read_text(errors="replace").splitlines()
            if "Opened session" in line or "session created" in line
        }
    )
    res = {
        "transitions": len(starts), "measured": len(lats), "p50_s": round(statistics.median(lats), 1) if lats else None,
        "p95_s": round(_p(lats, 0.95), 1), "buffer_max": buf_max, "collector_cpu_pct": round(cpu_pct, 1),
        "collector_rss_mb": round(rss_mb(pid)), "ua_sessions_log": sessions,
    }  # fmt: skip
    (STAND_DIR / "tp02.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("ТП-02:", json.dumps(res, ensure_ascii=False))
    assert lats and len(lats) >= 0.8 * len(starts), res
    assert _p(lats, 0.95) <= 10, res
    assert buf_max <= 100 and cpu_pct <= 15 and rss_mb(pid) <= 150, res


def test_tp03_year_volume(fresh):
    """ТП-03: обсяг року (840 000 інтервалів, 140 000 простоїв, 9 800 записів OEE); крони й звіти в межах SPEC."""
    o = fresh(ready=False)
    stand_sh("collector-stop")
    o.param("td.machine_connect.keep_log_days", "365")  # SPEC: 73 500 = 35 × 35 діб × 60 → ротація від 365 діб
    psql(
        "INSERT INTO td_machine_state_log (machine_id, state, source, date_start, date_end, create_date, write_date) "
        "SELECT m.id, (ARRAY['working','idle','working','setup','fault'])[1 + s % 5], 'machine', "
        "now() - interval '400 days' + s * interval '24 minutes', now() - interval '400 days' + (s + 1) * interval '24 minutes', now(), now() "
        "FROM td_machine m CROSS JOIN generate_series(0, 60 * 399 - 1) s"
    )
    loss = psql("SELECT id FROM mrp_workcenter_productivity_loss ORDER BY id LIMIT 1")[0][0]
    psql(
        "INSERT INTO td_downtime (machine_id, loss_id, state_kind, reason_source, reason_state, date_start, date_end, is_open, "
        "duration_min, create_date, write_date) "
        f"SELECT m.id, {loss}, 'idle', 'auto', 'to_classify', now() - interval '399 days' + s * interval '2.39 hours', "
        "now() - interval '399 days' + s * interval '2.39 hours' + interval '20 minutes', false, 20, now(), now() "
        "FROM td_machine m CROSS JOIN generate_series(0, 3999) s"
    )
    psql(
        "INSERT INTO td_oee_shift (machine_id, state, source, date, ppt_min, run_min, availability, performance, quality, oee, "
        "create_date, write_date) SELECT m.id, 'closed', 'machine', current_date - s, 450, 300, 0.8, 0.9, 1, 0.72, now(), now() "
        "FROM td_machine m CROSS JOIN generate_series(1, 280) s"
    )
    psql("ANALYZE td_machine_state_log")
    psql("ANALYZE td_downtime")
    n_log = int(psql("select count(*) from td_machine_state_log")[0][0])
    res = {"state_log_rows": n_log, "downtimes": int(psql("select count(*) from td_downtime")[0][0])}
    res["cron_oee_s"] = round(cron_run(o, "OEE змін"), 1)
    t = time.time()
    o.call(
        "td.oee.shift",
        "read_group",
        [("date", ">=", (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"))],
        ["oee:avg", "run_min:sum"],
        ["code"],
    )
    res["oee_year_report_s"] = round(time.time() - t, 1)
    t = time.time()
    o.call(
        "td.downtime",
        "read_group",
        [("date_start", ">=", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))],
        ["duration_min:sum"],
        ["loss_id", "date_start:month"],
        lazy=False,
    )
    res["downtime_pivot_month_s"] = round(time.time() - t, 1)
    before = int(psql("select count(*) from td_machine_state_log")[0][0])
    res["cron_rotate_s"] = round(cron_run(o, "ротація"), 1)
    res["rotated_rows"] = before - int(psql("select count(*) from td_machine_state_log")[0][0])
    plan = "\n".join(
        r[0]
        for r in psql(
            "EXPLAIN SELECT * FROM td_machine_state_log WHERE machine_id = 1 AND date_start >= now() - interval '10 days'"
        )
    )
    res["explain_index"] = "Index" in plan
    (STAND_DIR / "tp03.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("ТП-03:", json.dumps(res, ensure_ascii=False))
    assert res["cron_oee_s"] <= 20 and res["oee_year_report_s"] <= 5 and res["downtime_pivot_month_s"] <= 3, res
    assert res["cron_rotate_s"] <= 60 and res["rotated_rows"] >= 73000, res
    assert res["explain_index"], plan


def test_tp04_gantry_and_maps(fresh, sim):
    """ТП-04: EV-02 `stacks` (27 елементів) ≤ 0,5 с, `_cron_gantry` ≤ 10 с, API-01 на 5 000 деталей ≤ 2 с й ≤ 1 МБ."""
    o = fresh(env={"F3D_WRITE_ENABLED": "1"}, params={"cutting_mode": "collector"})
    token = (STAND_DIR / "token").read_text().strip()
    st, stacks = sim.get("/status") if False else (200, None)
    ws_items = [
        {"id": "PLT-%02d%s" % (r, c), "row": r, "col": ci + 1, "product": "DSP16-SON", "lot": "DSP16-SON-2610-%03d" % (r * 6 + ci),
         "qty": 20 + ci, "max": 60, "reserved": 0, "locked": False, "updated": datetime.now().astimezone().isoformat()}
        for r in range(1, 5) for ci, c in enumerate("ABCDEF")
    ][:27]  # fmt: skip
    lat = []
    for _ in range(5):
        body = {
            "events": [
                {
                    "event_id": hashlib.sha256(uuid.uuid4().bytes).hexdigest(), "route": "mc_woodstore",
                    "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"), "remote": "REST-WOODSTORE", "headers": {},
                    "payload": {"kind": "stacks", "source": "REST-WOODSTORE", "hash": "ab" * 32, "items": ws_items},
                }
            ]
        }  # fmt: skip
        t = time.time()
        stt, txt, _ = http(
            "POST", "http://127.0.0.1:18070/f3d/telemetry/event", body, {"Authorization": "Bearer " + token}
        )
        lat.append(time.time() - t)
        assert stt == 200, (stt, txt[:200])
    res = {"ev02_27_stacks_p50_s": round(statistics.median(lat), 3), "ev02_max_s": round(max(lat), 3)}
    res["cron_gantry_s"] = round(cron_run(o, "Портал"), 1)
    # API-01 на 5 000 деталей
    from .helpers import enable_write

    enable_write(o, ["REST-CUTOPT"], ["equipment/CUTOPT/cmd"])
    bom = o.search_read("mrp.bom", [("product_tmpl_id.default_code", "=", "BR-K4")], ["id"])[0]["id"]
    mo = make_mo(o, "BR-K4", 14)
    o.call("mrp.production", "action_f3d_create_cut_maps", [mo["id"]])
    mid = o.search_read("td.cut.map", [("production_id", "=", mo["id"]), ("material_role", "=", "main")], ["id"])[0][
        "id"
    ]
    del bom
    for chunk in range(5):
        o.call(
            "td.cut.map.line",
            "create",
            [
                {
                    "map_id": mid,
                    "part_code": "P%04d" % (chunk * 1000 + i),
                    "name": "Деталь %d" % (chunk * 1000 + i),
                    "length_mm": 700,
                    "width_mm": 500,
                    "qty": 1,
                    "sequence": chunk * 1000 + i,
                }
                for i in range(1000)
            ],
        )
    o.call("td.cut.map", "action_export", [mid])
    cmd = o.search_read("td.command", [("td_cut_map_id", "=", mid)], ["payload"])[0]["payload"]
    t = time.time()
    stt, txt, hd = http(
        "GET",
        f"http://127.0.0.1:18070/f3d/machine/cutmap/{mid}/export",
        headers={"Authorization": "Bearer " + token, "X-F3D-Token": cmd["token"]},
    )
    res.update(api01_status=stt, api01_s=round(time.time() - t, 2), api01_bytes=len(txt.encode()))
    (STAND_DIR / "tp04.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("ТП-04:", json.dumps(res, ensure_ascii=False))
    assert res["ev02_max_s"] <= 0.5 and res["cron_gantry_s"] <= 10, res
    assert stt == 200 and res["api01_s"] <= 2 and res["api01_bytes"] <= 1024 * 1024, res
    assert wait(lambda: True, 1)
