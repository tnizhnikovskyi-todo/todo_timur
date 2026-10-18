#!/usr/bin/env python3
"""Генератор навантаження ТП-01 (SPEC §13.4): 35 верстатів × 3…5 показань щосекунди на API-02 (`/f3d/telemetry/push`).

Кожен верстат перемикає WORKING↔READY (для I/O — run↔stop) раз на 10 с із зсувом фаз (≈ 3,5 переходи/с на 35 верстатів).
Колектор має бути зупинений; токен — `COL-MAIN` (перегенерований на копії: `odoo_rpc.py token`).

    python load_machines.py --minutes 30 --token "$(cat /tmp/f3dmc/token)" [--url http://127.0.0.1:18070] [--out stats.json]

Друкує (і пише в --out) JSON: запити, статуси, затримки p50/p95/p99 (мс), кількість переходів.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

MACHINES_CSV = (
    Path(__file__).resolve().parents[5] / "odoo_addons" / "td_machine_connect" / "data" / "mc_machines.csv"
)


def load_machines(path: Path = MACHINES_CSV) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8") as f:
        return [(r["code"], r["protocol"]) for r in csv.DictReader(f)]


def readings_for(code: str, protocol: str, working: bool, pieces: int, ts: str, extra: int) -> list[dict]:
    """3…5 показань верстата в один момент часу (`extra` — 0…2 додаткових: режим, завдання)."""
    base = f"workcenters/{code}/"
    if protocol == "opcua":
        out = [
            {
                "code": base + "state",
                "ts": ts,
                "value": 3 if working else 2,
                "text": "WORKING" if working else "READY",
                "q": "good",
            },
            {"code": base + "alarm", "ts": ts, "value": 0, "text": "off", "q": "good"},
            {"code": base + "pieces_out", "ts": ts, "value": float(pieces), "q": "good"},
        ]
        if extra >= 1:
            out.append({"code": base + "mode", "ts": ts, "value": 1, "text": "AUTOMATIC", "q": "good"})
        if extra >= 2:
            out.append({"code": base + "job", "ts": ts, "text": "-", "q": "good"})
        return out
    out = [
        {
            "code": base + "state",
            "ts": ts,
            "value": 1 if working else 0,
            "text": "run" if working else "stop",
            "q": "good",
        },
        {"code": base + "alarm", "ts": ts, "value": 0, "text": "off", "q": "good"},
        {"code": base + "pieces_out", "ts": ts, "value": float(pieces), "q": "good"},
    ]
    return out


def pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    return sorted_vals[min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1))))]


def run(url: str, token: str, minutes: float, out: str | None = None, period_s: float = 10.0) -> dict:
    machines = load_machines()
    lat: list[float] = []
    status: dict[str, int] = {}
    transitions = 0
    n = len(machines)
    t_end = time.time() + minutes * 60
    tick = 0
    prev = [None] * n
    while time.time() < t_end:
        t0 = time.time()
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"
        batch: list[dict] = []
        for i, (code, proto) in enumerate(machines):
            phase = (t0 + i * period_s / n) % period_s
            working = phase < period_s / 2
            if prev[i] is not None and prev[i] != working:
                transitions += 1
            prev[i] = working
            batch += readings_for(code, proto, working, tick, ts, extra=i % 3)
        body = json.dumps({"collector": "COL-MAIN", "readings": batch}).encode()
        req = urllib.request.Request(
            url + "/f3d/telemetry/push", data=body, method="POST",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )  # fmt: skip
        s = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
                code_s = str(r.status)
        except urllib.error.HTTPError as e:
            e.read()
            code_s = str(e.code)
        except Exception as e:  # noqa: BLE001
            code_s = type(e).__name__
        lat.append((time.time() - s) * 1000)
        status[code_s] = status.get(code_s, 0) + 1
        tick += 1
        time.sleep(max(0.0, 1.0 - (time.time() - t0)))
    lat.sort()
    res = {
        "requests": len(lat), "status": status, "transitions": transitions, "readings_per_request": len(batch),
        "p50_ms": round(pct(lat, 0.5)), "p95_ms": round(pct(lat, 0.95)), "p99_ms": round(pct(lat, 0.99)), "max_ms": round(max(lat or [0])),
    }  # fmt: skip
    if out:
        Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:18070")
    ap.add_argument("--token", required=True)
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--out")
    a = ap.parse_args()
    print(json.dumps(run(a.url, a.token, a.minutes, a.out), ensure_ascii=False))


if __name__ == "__main__":
    main()
