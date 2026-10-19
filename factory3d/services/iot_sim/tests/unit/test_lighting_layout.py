"""X-65, AC-65: розкладка світильників по лініях DALI = bms Додаток A.1 дослівно."""

import csv
from pathlib import Path

from iot_sim.models.lighting import GROUPS, addresses, dali_layout, format_dali

CSV = Path(__file__).resolve().parents[1] / "data" / "bms_dali_devices.csv"


def _rows() -> list[dict[str, str]]:
    with CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_dali_layout_matches_bms():
    rows = _rows()
    assert len(rows) == 32
    layout = dali_layout()
    for r in rows:
        assert format_dali(layout[r["code"]]) == r["dali_devices"], r["code"]
    assert sum(int(r["n_fixtures"]) for r in rows) == 320
    assert [g[0] for g in GROUPS] == [r["code"] for r in rows]  # порядок каталогу, G = 1…32


def test_groups_table_matches_bms():
    for g, r in zip(GROUPS, _rows(), strict=True):
        assert (g[0], g[1], g[2], g[3], g[4]) == (
            r["code"],
            r["panel"],
            int(r["n_fixtures"]),
            float(r["level_design"]),
            r["control"],
        )


def test_documented_examples():
    layout = dali_layout()
    assert format_dali(layout["LT-EB"]) == "@1.2.1.28-54"
    assert format_dali(layout["LT-CNC"]) == "@1.2.2.1-27"  # 27 > 64 − 54
    assert format_dali(layout["LT-FAC"]) == "@1.2.3.1-64;@1.2.4.1-27"
    assert format_dali(layout["LT-OUT-1"]) == "@1.3.1.59-62"
    assert format_dali(layout["LT-OUT-2"]) == "@1.3.2.1-4"  # 4 > 64 − 62
    assert len(addresses("LT-FAC")) == 91 and addresses("LT-FAC")[64] == "@1.2.4.1"


def test_single_device_and_exact_fill():
    layout = dali_layout(
        (("A", "LP-1", 1, 1.0, "shift"), ("B", "LP-1", 64, 1.0, "shift"), ("C", "LP-1", 3, 1.0, "shift"))
    )
    assert format_dali(layout["A"]) == "@1.1.1.1"
    assert format_dali(layout["B"]) == "@1.1.2.1-64"  # 64 > 63 → нова лінія
    assert format_dali(layout["C"]) == "@1.1.3.1-3"  # лінія повна → наступна
