import csv
import subprocess
import sys
from pathlib import Path

from iot_sim import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_gen_catalog_check():
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/gen_catalog.py"), "--check"], capture_output=True, text=True, check=False
    )
    assert r.returncode == 0, r.stderr


def test_catalog_rows():
    with (ROOT / "catalog/signals.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1215
    assert len({r["code"] for r in rows}) == 1215


def test_health(client):
    r = client.get("/sim/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
