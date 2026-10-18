# ruff: noqa: E501
"""ТП-01…ТП-05 (SPEC §13.4). Тривалості вікон налаштовуються: F3D_TP01_WINDOW_S (за замовч. 600 с замість 1800 с)."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import time


from conftest import HERE

PLUGIN_TESTS = HERE.parents[3] / "services" / "collector_plugins" / "f3d_collector_bms" / "tests"


def _hist_p95(text, name, label_filter=None):
    """p95 за кумулятивною гістограмою Prometheus `name` (верхня межа бакета, що покриває 95 %)."""
    buckets, total = {}, 0.0
    for line in text.splitlines():
        if not line.startswith(name + "_bucket") or (label_filter and label_filter not in line):
            continue
        le = re.search(r'le="([^"]+)"', line).group(1)
        v = float(line.rsplit(" ", 1)[1])
        buckets[le] = buckets.get(le, 0.0) + v
    total = buckets.get("+Inf", 0.0)
    if not total:
        return None, 0
    for le in sorted((k for k in buckets if k != "+Inf"), key=float):
        if buckets[le] >= 0.95 * total:
            return float(le), int(total)
    return float("inf"), int(total)


def _metric(text, name):
    return sum(
        float(ln.rsplit(" ", 1)[1])
        for ln in text.splitlines()
        if ln.startswith(name) and not ln.startswith("#") and ln.split("{")[0].split(" ")[0] == name
    )


def test_tp01_poll_cycle(metrics):
    """ТП-01: цикл опитування пристрою p95 ≤ 2 с, collector_poll_overrun_total не росте за вікно."""
    window = int(os.environ.get("F3D_TP01_WINDOW_S", "600"))
    t0 = metrics.text()
    o0 = _metric(t0, "collector_poll_overrun_total")
    time.sleep(window)
    t1 = metrics.text()
    p95, n = _hist_p95(t1, "collector_poll_seconds", 'source="BAC-')
    o1 = _metric(t1, "collector_poll_overrun_total")
    print(f"TP01 вікно {window} с: BACnet poll_seconds p95 ≤ {p95} с (n={n}); overrun {o0:.0f} → {o1:.0f}")
    assert p95 is not None and p95 <= 2.0
    assert o1 - o0 == 0


def test_tp02_helvar_320(tmp_path):
    """ТП-02 (PT): 32 групи × 10 пристроїв: обхід несправностей ≤ 30 с при rate 20/с; рівні/потужність/сцена ≤ 10 с."""
    sys.path.insert(0, str(PLUGIN_TESTS))
    sys.path.insert(0, str(PLUGIN_TESTS.parent))
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("bms_plugin_conftest", PLUGIN_TESTS / "conftest.py")
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)  # плагінний conftest: make_ctx/make_signal/make_source (ім'я conftest зайняте стендом)
    make_ctx, make_signal, make_source = pc.make_ctx, pc.make_signal, pc.make_source
    from fake_helvar_router import FakeHelvarRouter  # noqa: PLC0415
    from f3d_collector_bms.connection import POOL  # noqa: PLC0415
    from f3d_collector_bms.helvarnet import HelvarNetPlugin  # noqa: PLC0415

    routers = {1: {"groups": {}}, 2: {"groups": {}}, 3: {"groups": {}}}
    members = {}
    for g in range(1, 33):
        r = 1 + (g - 1) % 3
        addrs = [f"@1.{r}.{g}.{d}" for d in range(1, 11)]
        routers[r]["groups"][g] = addrs
        members[g] = (r, addrs)

    async def run(rate, kinds):
        POOL.reset()
        fake = await FakeHelvarRouter(routers=routers, push=False).start()
        out = {}
        try:
            plugins = {}
            for r in (1, 2, 3):
                sigs = []
                for g, (rr, addrs) in members.items():
                    if rr != r:
                        continue
                    for k in kinds:
                        extra = {"devices": addrs} if k in ("faults", "faulty", "level") else {}
                        sigs.append(make_signal(g, k, code=f"g{g}/{k}", **extra))
                p = HelvarNetPlugin(
                    make_source(fake.port, sigs, code=f"HN-LP-{r}", router=r, rate_per_s=rate, timeout_s=3), make_ctx()
                )
                p.verify_extra_s = 0.05
                await p.connect()
                plugins[r] = (p, sigs)
            t = time.perf_counter()
            await asyncio.gather(*(p.poll(s) for p, s in plugins.values()))
            out["s"] = time.perf_counter() - t
            out["frames"] = sum(fake.queries.values())
        finally:
            for p, _ in plugins.values():
                await p.disconnect()
            await fake.stop()
            POOL.reset()
        return out

    sweep = asyncio.run(run(20, ["faults", "faulty"]))
    live = asyncio.run(run(100, ["level", "power", "scene"]))
    print(
        f"TP02 обхід несправностей 320 пристроїв, rate 20/с: {sweep['s']:.1f} с ({sweep['frames']} кадрів); "
        f"рівень+потужність+сцена 32 груп, rate 100/с: {live['s']:.1f} с ({live['frames']} кадрів)"
    )
    assert sweep["s"] <= 30
    assert live["s"] <= 10


def test_tp03_push_latency(metrics):
    """ТП-03: collector_push_latency_seconds p95 ≤ 1 с (пакети колектора; навантаження bms ≈ 12 показань/с)."""
    p95, n = _hist_p95(metrics.text(), "collector_push_latency_seconds")
    print(f"TP03 push latency p95 ≤ {p95} с, пакетів {n}")
    assert p95 is not None and p95 <= 1.0


def test_tp04_cron_perf(odoo):
    """ТП-04: крон перевірок ≤ 2 с на прогін, get_overview_data ≤ 0,5 с (odoo shell на базі стенда)."""
    stand = HERE / "stand.sh"
    with open(HERE / "perf_odoo.py", "rb") as f:
        r = subprocess.run([str(stand), "shell"], stdin=f, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    print(out.strip())
    cron = re.search(r"cron_check_s=.*max=([0-9.]+)", out)
    ov = re.search(r"overview_s=.*max=([0-9.]+)", out)
    assert cron and ov, out
    assert float(cron.group(1)) <= 2.0 and float(ov.group(1)) <= 0.5


def test_tp05_readings_rate(odoo):
    """ТП-05: нові `td.reading` сигналів module='bms' за вікно (F3D_TP05_WINDOW_S, за замовч. 600 с) × (86 400/вікно)."""
    window = int(os.environ.get("F3D_TP05_WINDOW_S", "600"))
    dom = [("signal_id.module", "=", "bms")]
    last = odoo.search_read("td.reading", dom, ["id"], order="id desc", limit=1)[0]["id"]
    time.sleep(window)
    n = odoo.count("td.reading", dom + [("id", ">", last)])
    day = round(n * 86400 / window)
    print(f"TP05 за {window} с {n} рядків → ≈ {day} за добу (норма ≤ 60 000)")
    assert day <= 60000
