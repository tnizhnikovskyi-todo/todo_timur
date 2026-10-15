"""Генератор `data/signal_catalog.csv` (SPEC §5.2, Додаток C.2): 56 рядків, детерміновано.

Запуск: `python tools/gen_signal_data.py [шлях.csv]` (за замовчуванням — `data/signal_catalog.csv`).
Колонки й сенс порожніх клітинок — SPEC §5.2: `new=1` — створюється (`origin=catalog`), `new=0` — прив'язка
мігрованого сигналу (порожньо = «не змінювати»).
"""

import csv
import json
import os
import sys

COLUMNS = [
    "code",
    "name",
    "quantity",
    "kind",
    "unit",
    "equipment",
    "workcenter",
    "source",
    "address",
    "period_s",
    "store_period_s",
    "scale",
    "decimals",
    "nominal",
    "warn_low",
    "warn_high",
    "alarm_low",
    "alarm_high",
    "alarm_states",
    "alarm_title",
    "hysteresis",
    "min_duration_s",
    "states",
    "viewer_visible",
    "derived_from",
    "derive_rule",
    "origin",
    "module",
    "sim_mode",
    "sim_params",
    "new",
]
MOBILE = ["FL-1", "FL-2", "FL-3", "FL-4", "FL-5", "FL-C1", "FL-C2", "TUGGER-1"]
MQTT = "MQTT-MOBILE"
U70, U84, U90, U96, BAC = "MB-U70-COMPRESSOR", "MB-U84-IO5", "MB-U90-AI1", "MB-U96-RTD1", "BAC-140-BOILER"
SCALE16 = 0.0002441444
RTD = {"fc": 3, "type": "u16", "scale": 0.0030518044, "offset": -50, "range": [-50, 150], "count": 3, "agg": "max"}


def _mqtt(device, path, **extra):
    return {"topic": "f3d/mobile/%s/telemetry" % device, "path": path, "ts_path": "$.ts", "device": device, **extra}


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _module(code):
    head = code.split("/")[0]
    if head == "infra" and code.startswith("infra/water/"):
        return "telemetry"
    return {"energy": "energy", "infra": "energy", "equipment": "telemetry"}.get(head, "other")


def _row(code, **vals):
    """Рядок каталогу; `new=1` дістає `origin`/`module` автоматично."""
    row = {"code": code, "new": vals.pop("new", 0)}
    row.update(vals)
    if row["new"]:
        row.setdefault("origin", "catalog")
        row.setdefault("module", _module(code))
    return row


def build_rows():
    rows = []
    # 1–8, 9–16: прив'язка мігрованих MQTT-сигналів техніки
    for c in MOBILE:
        rows.append(
            _row(
                "equipment/%s/battery" % c,
                source=MQTT,
                address=_mqtt(c, "$.battery_pct"),
                period_s=5,
                store_period_s=300,
                decimals=1,
                warn_low=25,
                alarm_low=15,
                hysteresis=1,
                alarm_title="Зарядити АКБ: заряд {value} % при нормі від {threshold}",
            )
        )
    for c in MOBILE:
        rows.append(
            _row(
                "equipment/%s/hours" % c,
                source=MQTT,
                address=_mqtt(c, "$.hours"),
                period_s=5,
                store_period_s=300,
                decimals=1,
            )
        )
    # 17–27: прив'язка мігрованих сигналів компресора, аспірації, трансформаторів, котельні
    rows += [
        _row(
            "equipment/COMPRESSOR/pressure_bar",
            source=U70,
            period_s=10,
            store_period_s=300,
            decimals=2,
            hysteresis=0.1,
            min_duration_s=30,
            address={
                "fc": 3,
                "addr": 3001,
                "type": "u16",
                "scale": 0.001,
                "range": [0, 16],
                "doc": "HR 3002 Outlet pressure",
            },
        ),
        _row(
            "equipment/COMPRESSOR/load",
            source=U70,
            period_s=10,
            store_period_s=300,
            decimals=0,
            address={"fc": 3, "addr": 3009, "type": "u16", "range": [0, 100], "doc": "HR 3010 Load (VSD output)"},
        ),
        _row(
            "equipment/COMPRESSOR/hours",
            source=U70,
            period_s=60,
            store_period_s=300,
            decimals=1,
            address={"fc": 3, "addr": 3019, "type": "u32", "doc": "HR 3020–3021 Running hours"},
        ),
        _row(
            "equipment/DUST-1/airflow_m3h",
            source=U90,
            period_s=10,
            store_period_s=300,
            decimals=0,
            address={
                "fc": 3,
                "addr": 0,
                "type": "u16",
                "scale": 0.4882887,
                "offset": 0,
                "range": [0, 32000],
                "doc": "HR 40001 AI0 4–20 мА = 0…32 000 м³/год",
            },
        ),
        _row(
            "equipment/DUST-1/filter_dp_kpa",
            source=U90,
            period_s=10,
            store_period_s=300,
            decimals=2,
            address={
                "fc": 3,
                "addr": 1,
                "type": "u16",
                "scale": 0.0000610361,
                "range": [0, 4],
                "doc": "HR 40002 AI1 4–20 мА = 0…4 кПа",
            },
        ),
        _row(
            "equipment/SPRINKLERS/pressure_bar",
            source=U90,
            period_s=10,
            store_period_s=300,
            decimals=2,
            address={
                "fc": 3,
                "addr": 2,
                "type": "u16",
                "scale": SCALE16,
                "range": [0, 16],
                "doc": "HR 40003 AI2 4–20 мА = 0…16 бар",
            },
        ),
        _row(
            "equipment/AIR-RING/pressure_bar",
            source=U90,
            period_s=10,
            store_period_s=300,
            decimals=2,
            address={
                "fc": 3,
                "addr": 3,
                "type": "u16",
                "scale": SCALE16,
                "range": [0, 16],
                "doc": "HR 40004 AI3 4–20 мА = 0…16 бар",
            },
        ),
        _row(
            "energy/transformers/T1/temp_c",
            source=U96,
            period_s=30,
            store_period_s=300,
            decimals=1,
            address={**RTD, "addr": 0, "doc": "HR 40001–40003 RTD0–2, макс."},
        ),
        _row(
            "energy/transformers/T2/temp_c",
            source=U96,
            period_s=30,
            store_period_s=300,
            decimals=1,
            address={**RTD, "addr": 3, "doc": "HR 40004–40006 RTD3–5, макс."},
        ),
        _row(
            "equipment/BOILER/supply_c",
            source=BAC,
            period_s=30,
            store_period_s=300,
            decimals=1,
            address={
                "object": "analog-input",
                "instance": 1,
                "property": "present-value",
                "mode": "cov",
                "cov_increment": 0.2,
                "doc": "AI:1 BOILER_SupplyTemp",
            },
        ),
        _row(
            "equipment/BOILER/silo_fill",
            source=BAC,
            period_s=30,
            store_period_s=300,
            decimals=0,
            address={
                "object": "analog-input",
                "instance": 3,
                "mode": "cov",
                "cov_increment": 1,
                "doc": "AI:3 BOILER_SiloLevel",
            },
        ),
    ]
    # 28–35: стан техніки; 36–51: координати X, Y
    for c in MOBILE:
        rows.append(
            _row(
                "equipment/%s/state" % c,
                new=1,
                name="%s: стан" % c,
                quantity="Стан",
                kind="state",
                equipment=c,
                source=MQTT,
                address=_mqtt(c, "$.state", map={"to_charge": "busy"}),
                period_s=5,
                store_period_s=300,
                decimals=0,
                states=["idle", "busy", "charging", "offline", "fault"],
                alarm_states=["fault"],
                alarm_title="{equipment}: несправність (стан «{text}»)",
            )
        )
    for axis in ("x", "y"):
        for c in MOBILE:
            rows.append(
                _row(
                    "equipment/%s/%s" % (c, axis),
                    new=1,
                    name="%s: координата %s" % (c, axis.upper()),
                    quantity="Координата",
                    kind="gauge",
                    unit="м",
                    equipment=c,
                    source=MQTT,
                    address=_mqtt(c, "$." + axis),
                    period_s=5,
                    store_period_s=60,
                    decimals=1,
                    viewer_visible=False,
                )
            )
    # 52–56
    rows += [
        _row(
            "equipment/COMPRESSOR/state",
            new=1,
            name="Компресор: стан",
            quantity="Стан",
            kind="state",
            equipment="COMPRESSOR",
            source=U70,
            period_s=10,
            store_period_s=300,
            decimals=0,
            address={
                "fc": 3,
                "addr": 3000,
                "type": "u16",
                "map": {"0": "stopped", "1": "loaded", "2": "unloaded", "3": "fault", "4": "standby"},
                "doc": "HR 3001 Machine status",
            },
            states=["stopped", "loaded", "unloaded", "fault", "standby"],
            alarm_states=["fault"],
            alarm_title="Компресор: стан «{text}»",
        ),
        _row(
            "equipment/COMPRESSOR/temp_c",
            new=1,
            name="Компресор: температура гвинтового блока",
            quantity="Температура",
            kind="gauge",
            unit="°C",
            equipment="COMPRESSOR",
            source=U70,
            period_s=10,
            store_period_s=300,
            decimals=1,
            address={
                "fc": 3,
                "addr": 3002,
                "type": "u16",
                "scale": 0.1,
                "range": [0, 150],
                "doc": "HR 3003 Element outlet temperature",
            },
            alarm_high=110,
            hysteresis=2,
            alarm_title="{equipment}: температура {value} °C при нормі до {threshold}",
        ),
        _row(
            "equipment/DUST-1/state",
            new=1,
            name="Аспірація: стан",
            quantity="Стан",
            kind="state",
            equipment="DUST-1",
            source=U84,
            period_s=10,
            store_period_s=300,
            decimals=0,
            address={
                "fc": 2,
                "states": [
                    {"addr": 1, "eq": 1, "text": "fault"},
                    {"addr": 0, "eq": 1, "text": "running"},
                    {"addr": 0, "eq": 0, "text": "stopped"},
                ],
                "doc": "DI0 вентилятори в роботі, DI1 аварія",
            },
            states=["running", "stopped", "fault"],
            alarm_states=["fault"],
            alarm_title="Аспірація: аварія вентиляторів (стан «{text}»)",
        ),
        _row(
            "infra/water/m3_total",
            new=1,
            name="Водомірний вузол: показник лічильника",
            quantity="Об'єм",
            kind="counter",
            unit="м³",
            equipment="WATER",
            source=U84,
            period_s=60,
            store_period_s=300,
            decimals=2,
            address={
                "fc": 3,
                "addr": 16,
                "count": 2,
                "type": "u32",
                "wordorder": "little",
                "scale": 0.01,
                "doc": "HR 40017–40018 лічильник DI8, 1 імп = 10 л",
            },
        ),
        _row(
            "infra/water/flow_m3h",
            new=1,
            name="Водомірний вузол: витрата",
            quantity="Витрата",
            kind="gauge",
            unit="м³/год",
            equipment="WATER",
            period_s=60,
            store_period_s=300,
            decimals=2,
            derived_from="infra/water/m3_total",
            derive_rule="rate_h",
        ),
    ]
    return rows


def write_csv(path):
    rows = build_rows()
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([_cell(row.get(col)) for col in COLUMNS])
    return len(rows)


if __name__ == "__main__":
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "signal_catalog.csv")
    print("%d рядків" % write_csv(sys.argv[1] if len(sys.argv) > 1 else default))
