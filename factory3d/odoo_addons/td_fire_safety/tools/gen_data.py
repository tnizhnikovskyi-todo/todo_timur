"""Генератор data-файлів td_fire_safety з макета (SPEC §5.2, Додатки A-D).

Запуск з каталогу factory3d (корінь макета):
    python3 odoo_addons/td_fire_safety/tools/gen_data.py [--root .] [--out odoo_addons/td_fire_safety/data]

Читає: plant/fire.py, plant/infra.py, plant/evacuation.py, plant/layout.py, plant/odoo_rpc.py (slug),
plant/evac_routes.json, plant/fire_rules.json, plant/evac_rules.json, dist/odoo_demo.json (fire.groups,
evacuation.drill_steps).
Пише детерміновано (сортування за макетом, без часових міток, перенос рядка \\n, числа — round(v, 2) без зайвих нулів).
Самоперевірки кидають SystemExit(2) з текстом.
"""

import argparse
import csv
import io
import json
import os
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_OUT = os.path.abspath(os.path.join(HERE, "..", "data"))

BASE = "td_factory3d"
PANEL = "panel_facp_1"
SRC_B = "source_bacnet_facp_1"
SRC_M = "source_mb_u85_io6"
SYS_SPARK, SYS_SMOKE, SYS_SPR = "system_spark_1", "system_smoke_ctrl", "system_sprinklers"
EXPECTED = {
    "zones": 35,
    "detectors": 222,
    "smoke": 138,
    "multi": 82,
    "heat": 2,
    "mcp": 36,
    "sounders": 41,
    "flame": 3,
    "spark_detectors": 4,
    "nozzles": 3,
    "vents": 44,
    "smoke_zones": 8,
    "exits": 12,
    "routes": 32,
    "steps": 8,
    "devices": 353,
    "norms": 27,
    "signals": 54,
}
LOOP_SUMS = {"detectors": (64, 68, 44, 46), "mcp": (10, 10, 7, 9), "sounders": (11, 13, 7, 10)}
Z_VENT = 9.0
Z_MCP, Z_SND = 1.35, 2.9
SIDE_NAME = {"S": "південна", "N": "північна", "W": "західна", "E": "східна"}

# Додаток D: key -> (група, назва, коротка одиниця); порядок = порядок рядків; ref/note/sources — з JSON макета
NORMS = [
    ("smoke_spacing_6_12m", "detection", "Відстань між димовими сповіщувачами (висота до 12 м)", "м"),
    ("smoke_wall_6_12m", "detection", "Відстань від димового сповіщувача до стіни (висота до 12 м)", "м"),
    ("smoke_area_6_12m", "detection", "Площа на один димовий сповіщувач (висота 6–12 м)", "м²"),
    ("heat_spacing", "detection", "Відстань між тепловими сповіщувачами", "м"),
    ("heat_wall", "detection", "Відстань від теплового сповіщувача до стіни", "м"),
    ("heat_area", "detection", "Площа на один тепловий сповіщувач", "м²"),
    ("mcp_spacing", "detection", "Найбільший шлях до ручного сповіщувача", "м"),
    ("mcp_height", "detection", "Висота встановлення ручного сповіщувача", "м"),
    ("flame_detector_note", "detection", "Розміщення сповіщувачів полум'я", "—"),
    ("spark_detection_required", "detection", "Система виявлення й гасіння іскор", "—"),
    ("sounder_level", "alerting", "Рівень звуку оповіщення, мінімум", "дБА"),
    ("sounder_bg_production", "alerting", "Фоновий шум: механічні цехи", "дБА"),
    ("sounder_bg_storage", "alerting", "Фоновий шум: виробничі приміщення", "дБА"),
    ("sounder_bg_office", "alerting", "Фоновий шум: офіси", "дБА"),
    ("evac_distance_prod_B", "evacuation", "Найбільша відстань до евакуаційного виходу (кат. В, ≥ 80 тис. м³)", "м"),
    ("evac_distance_polymer", "evacuation", "Найбільша відстань до виходу при полімерному утеплювачі панелей", "м"),
    ("evac_exits_min", "evacuation", "Мінімальна кількість евакуаційних виходів", "шт."),
    ("exit_width_min", "evacuation", "Мінімальна ширина шляху евакуації", "м"),
    ("door_width_min", "evacuation", "Мінімальна ширина евакуаційних дверей у просвіті", "м"),
    ("exit_dispersal_k", "evacuation", "Коефіцієнт розосередженості виходів (L = k·√П)", "—"),
    ("smoke_exhaust_required", "smoke", "Обов'язковість димовидалення", "так/ні"),
    ("smoke_zone_max_area", "smoke", "Найбільша площа димової зони", "м²"),
    ("smoke_vent_area", "smoke", "Аеродинамічна площа люків на 400 м² підлоги (орієнтир)", "м² Aa"),
    ("smoke_vent_aa", "smoke", "Аеродинамічна площа одного люка LAMILUX F100", "м²"),
    ("lightning_class", "other", "Клас (рівень) блискавкозахисту", "клас"),
    ("eyewash_required", "other", "Фонтан для промивання очей", "так/ні"),
    ("pv_roof_fire", "other", "Відстані для дахової ФЕС", "м"),
]
# 7 авторських норм (немає в JSON макета): key -> (значення, ref, note)
AUTHORED = {
    "heat_wall": (
        3.2,
        "= ref heat_spacing",
        "Додано автором модуля: половина відстані між тепловими сповіщувачами (heat_spacing / 2).",
    ),
    "sounder_bg_production": (
        85,
        "ДБН В.2.5-56:2014 зі Зміною № 2, п. 9.3.10",
        "Додано автором модуля: фоновий шум механічних цехів для оцінки рівня оповіщення (A-26).",
    ),
    "sounder_bg_storage": (
        80,
        "ДБН В.2.5-56:2014 зі Зміною № 2, п. 9.3.10",
        "Додано автором модуля: фоновий шум виробничих приміщень для оцінки рівня оповіщення (A-26).",
    ),
    "sounder_bg_office": (
        55,
        "ДБН В.2.5-56:2014 зі Зміною № 2, п. 9.3.10",
        "Додано автором модуля: фоновий шум офісів для оцінки рівня оповіщення (A-26).",
    ),
    "evac_distance_polymer": (
        50,
        "ДБН В.2.2-27:2025 п. 8.2.11 — якщо стінові й покрівельні панелі з полімерним "
        "утеплювачем; тупики — не довше 25 м (п. 8.2.9); ворота не рахуються виходами "
        "(п. 8.2.6).",
        "Додано автором модуля: альтернативна норма відстані до виходу (параметр polymer_panels).",
    ),
    "exit_dispersal_k": (
        1.5,
        "ДБН В.1.1-7:2016 п. 7.2.6",
        "Додано автором модуля: коефіцієнт розосередженості виходів L = k·√П (R-06).",
    ),
    "smoke_vent_aa": (
        1.02,
        "Паспорт smoke_vent (plant/equipment_specs.json): LAMILUX Smoke Lift Glass Skylight F100 1200×1200, EN 12101-2",
        "Додано автором модуля: аеродинамічна площа одного люка для R-09.",
    ),
}

# шаблон навчання (M-11c): (auto_key, text із плейсхолдерами)
TEMPLATE_STEPS = [
    ("detector", "Сповіщувач {detector} ({zone}): дим і тепло — тривога на приладі."),
    ("sounders", "Увімкнено {sounders} сирен-маяків по всьому цеху."),
    ("brigade", "Сигнал «Пожежа» передано на пульт ДСНС і черговому."),
    ("ventilation", "Зупинено дахові установки й приплив фасадів, щоб не роздувати вогонь."),
    ("smoke", "Відкрито клапани димовидалення на покрівлі."),
    ("doors", "Розблоковано двері з контролем доступу й турнікети, шлагбауми — вгору."),
    ("evacuation", "Люди йдуть зеленими маршрутами до найближчих виходів; збір — на паркуванні."),
    ("machines", "Аварійна зупинка верстатів у зоні пожежі; аспірація — іскрогасіння в готовності."),
]

SOURCES = [
    (
        SRC_B,
        "BAC-200-FACP-1",
        "Cerberus PRO FACP-1 (BACnet dev 200, лише читання)",
        "bacnet_ip",
        {
            "host": "iot-sim",
            "port": 47808,
            "device": 200,
            "network": 2,
            "read_only": True,
            "timeout_s": 5,
            "rpm": True,
            "rpm_max": 50,
        },
        10,
    ),
    (
        SRC_M,
        "MB-U85-IO6",
        "ADAM-6050 IO-6: GreCon BS 7 і D+H (лише читання)",
        "modbus_tcp",
        {"host": "iot-sim", "port": 502, "unit": 85, "timeout_s": 3, "retries": 1},
        2,
    ),
]


def fail(text):
    print("ПОМИЛКА gen_data: %s" % text, file=sys.stderr)
    raise SystemExit(2)


def num(v):
    """round(v, 2) без зайвих нулів."""
    s = ("%.2f" % round(float(v), 2)).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def py(v):
    """Детермінований Python-літерал для eval=\"...\" (числа — через num)."""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return num(v) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "[%s]" % ", ".join(py(x) for x in v)
    if isinstance(v, dict):
        return "{%s}" % ", ".join("%s: %s" % (py(k), py(x)) for k, x in v.items())
    fail("невідомий тип %r" % (v,))


def attr(text):
    return escape(text, {'"': "&quot;"})


class Xml:
    def __init__(self, noupdate=False):
        self.lines = ['<?xml version="1.0" encoding="utf-8"?>', '<odoo noupdate="1">' if noupdate else "<odoo>"]

    def raw(self, text):
        self.lines.append(text)

    def record(self, rid, model, fields):
        """fields: список (имя, kind, значение); kind: v — текст, ref, eval."""
        self.lines.append('    <record id="%s" model="%s">' % (rid, model))
        for name, kind, value in fields:
            if kind == "v":
                self.lines.append('        <field name="%s">%s</field>' % (name, escape(str(value))))
            elif kind == "ref":
                self.lines.append('        <field name="%s" ref="%s"/>' % (name, value))
            else:
                self.lines.append('        <field name="%s" eval="%s"/>' % (name, attr(value)))
        self.lines.append("    </record>")

    def text(self):
        return "\n".join(self.lines + ["</odoo>", ""])


def csv_text(header, rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return out.getvalue()


def load_plant(root):
    sys.path.insert(0, root)
    try:
        from plant import evacuation, fire, infra, layout, odoo_rpc
    finally:
        sys.path.remove(root)
    return fire, infra, evacuation, layout, odoo_rpc


def read_json(root, *parts):
    with open(os.path.join(root, *parts), encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------------------------------- модель макета
def collect(root):
    fire, infra, evacuation, layout, rpc = load_plant(root)
    demo = read_json(root, "dist", "odoo_demo.json")
    groups = demo["fire"]["groups"]
    loops_demo = demo["fire"]["loops"]
    dets = fire.detectors()
    zones = []
    zrect = {z[0]: z[2] for z in layout.ZONES}
    for lsz, (fa, g) in enumerate(groups.items(), 1):
        pz = g["zone"] if g["zone"].startswith("Z-") else "Z-" + g["zone"]
        if fa != "FA-" + pz[2:]:
            fail("група %s не відповідає зоні %s" % (fa, pz))
        d = dets[pz]
        if pz == "Z-BOILER":
            rect, z_m = fire.BOILER_HOUSE, fire.Z_BOILER
        elif pz in fire.ROOMS:
            rect, z_m = fire.ROOMS[pz]["rect"], fire.ROOMS[pz]["levels"][0]
        else:
            rect, z_m = zrect[pz], fire.Z_DET
        loop = fire.loop_of(d["points"][0][0])
        zones.append(
            dict(
                fa=fa,
                pz=pz,
                name=g["zone_name"],
                kind=d["kind"],
                lsz=lsz,
                loop=loop,
                rect=rect,
                z_m=z_m,
                spacing=d["spacing"],
                wall=3.2 if d["kind"] == "heat" else 4.4,
                points=d["points"],
                zs=d.get("zs"),
            )
        )
    return dict(
        fire=fire,
        infra=infra,
        evacuation=evacuation,
        layout=layout,
        rpc=rpc,
        demo=demo,
        zones=zones,
        loops_demo=loops_demo,
    )


def build_devices(m):
    fire, infra, rpc = m["fire"], m["infra"], m["rpc"]
    devs = []
    for z in m["zones"]:
        code = z["fa"][3:]
        for nn, (x, y) in enumerate(z["points"], 1):
            lp = fire.loop_of(x)
            if lp != z["loop"]:
                fail("сповіщувач %s.%s.%02d (x=%s) не в шлейфі зони %s" % (lp, code, nn, x, z["loop"]))
            zz = z["zs"][nn - 1] if z["zs"] else z["z_m"]
            devs.append(
                dict(
                    address="%d.%s.%02d" % (lp, code, nn),
                    type=z["kind"],
                    loop=lp,
                    zone=z["fa"],
                    lsp=lp * 10000 + z["lsz"] * 100 + nn,
                    seq=nn,
                    x=x,
                    y=y,
                    z=zz,
                )
            )
    counters = {}

    def seq_in_loop(kind, lp):
        counters[(kind, lp)] = counters.get((kind, lp), 0) + 1
        return counters[(kind, lp)]

    for x, y, side in fire.call_points():
        lp = fire.loop_of(x)
        nn = seq_in_loop("mcp", lp)
        devs.append(
            dict(
                address="%d.MCP.%02d" % (lp, nn),
                type="mcp",
                loop=lp,
                lsp=lp * 10000 + 9000 + nn,
                seq=nn,
                x=x,
                y=y,
                z=Z_MCP,
                side=side,
            )
        )
    for x, y, side in fire.sounders():
        lp = fire.loop_of(x)
        nn = seq_in_loop("snd", lp)
        devs.append(
            dict(
                address="%d.SND.%02d" % (lp, nn),
                type="sounder",
                loop=lp,
                lsp=lp * 10000 + 9100 + nn,
                seq=nn,
                x=x,
                y=y,
                z=Z_SND,
                side=side,
            )
        )
    for nn, (x, y, z, heading) in enumerate(fire.FLAME, 1):
        lp = fire.loop_of(x)
        devs.append(
            dict(
                address="%d.FLM.%02d" % (lp, nn),
                type="flame",
                loop=lp,
                lsp=lp * 10000 + 9200 + nn,
                seq=nn,
                x=x,
                y=y,
                z=z,
                heading=heading,
            )
        )
    for nn, (x, y) in enumerate(fire.SPARK_DETECTORS, 1):
        devs.append(
            dict(
                address="0.SPK.%02d" % nn,
                type="spark_detector",
                loop=0,
                lsp=0,
                seq=nn,
                x=x,
                y=y,
                z=fire.DUCT_TOP,
                system=SYS_SPARK,
            )
        )
    for nn, (x, y, side) in enumerate(fire.SPARK_EXTINGUISH, 1):
        devs.append(
            dict(
                address="0.NOZ.%02d" % nn,
                type="spark_nozzle",
                loop=0,
                lsp=0,
                seq=nn,
                x=x,
                y=y,
                z=fire.DUCT_TOP,
                side=side,
                system=SYS_SPARK,
            )
        )
    nn = 0
    for sz, zd in infra.smoke_zone_vents().items():
        for x, y in zd["points"]:
            nn += 1
            devs.append(
                dict(
                    address="0.SV.%02d" % nn,
                    type="smoke_vent",
                    loop=0,
                    lsp=0,
                    seq=nn,
                    x=x,
                    y=y,
                    z=infra.ROOF_Z,
                    system=SYS_SMOKE,
                    smoke_zone=sz,
                    note="SV-%02d" % nn,
                )
            )
    return devs


def self_check(m, devs, norms, routes, exits):
    fire = m["fire"]
    cnt = {}
    for d in devs:
        cnt[d["type"]] = cnt.get(d["type"], 0) + 1
    got = {
        "zones": len(m["zones"]),
        "detectors": sum(cnt.get(k, 0) for k in ("smoke", "multi", "heat")),
        "smoke": cnt.get("smoke", 0),
        "multi": cnt.get("multi", 0),
        "heat": cnt.get("heat", 0),
        "mcp": cnt.get("mcp", 0),
        "sounders": cnt.get("sounder", 0),
        "flame": cnt.get("flame", 0),
        "spark_detectors": cnt.get("spark_detector", 0),
        "nozzles": cnt.get("spark_nozzle", 0),
        "vents": cnt.get("smoke_vent", 0),
        "smoke_zones": len(m["infra"].SMOKE_ZONES),
        "exits": len(exits),
        "routes": len(routes),
        "steps": len(m["demo"]["evacuation"]["drill_steps"]),
        "devices": len(devs),
        "norms": len(norms),
    }
    for k, v in got.items():
        if EXPECTED[k] != v:
            fail("кількість %s: очікується %s, отримано %s" % (k, EXPECTED[k], v))
    for key, field in (("detectors", ("smoke", "multi", "heat")), ("mcp", ("mcp",)), ("sounders", ("sounder",))):
        for lp, want in enumerate(LOOP_SUMS[key], 1):
            have = sum(1 for d in devs if d["loop"] == lp and d["type"] in field)
            demo_have = m["loops_demo"][str(lp)][key]
            if have != want or demo_have != want:
                fail("шлейф %d, %s: розрахунок %d, макет %d, очікується %d" % (lp, key, have, demo_have, want))
    for attr_name in ("address", "lsp"):
        seen = set()
        for d in devs:
            v = d[attr_name]
            if attr_name == "lsp" and v == 0:
                continue
            if v in seen:
                fail("дубль %s: %r" % (attr_name, v))
            seen.add(v)
    by = {d["address"]: d for d in devs}
    control = {
        "2.FAC.07": (62.78, 50.57, 8.85),
        "2.CNC.05": (72.75, 34.2, 8.85),
        "1.SHEETS.01": (17.95, 4.33, 8.85),
        "2.BOILER.02": (76.6, 78.0, 4.35),
        "3.SOC.01": (106.8, 49.3, 3.35),
        "3.OFFICE.01": (96.4, 61.55, 2.95),
        "3.OFFICE.05": (96.4, 61.55, 6.15),
    }
    for addr, want in control.items():
        have = tuple(round(by[addr][k], 2) for k in "xyz")
        if have != want:
            fail("контрольна точка %s: %s != %s" % (addr, have, want))
    if by["2.FAC.07"]["lsp"] != 21607 or by["3.OFFICE.08"]["lsp"] != 33508:
        fail("LSP за R-23")
    # маршрути перетинають перегородки лише в прорізах (A-25)
    for code, r in routes.items():
        pts = r["path"]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for wx0, wy0, wx1, wy1, gaps in m["evacuation"].WALLS:
                cross = _crossing(x0, y0, x1, y1, wx0, wy0, wx1, wy1)
                if cross is None:
                    continue
                if not any(abs(cross - c) <= w / 2 + 0.3 for c, w in gaps):
                    fail("маршрут %s перетинає перегородку (%s,%s)-(%s,%s) поза прорізом" % (code, wx0, wy0, wx1, wy1))
    return got


def _crossing(x0, y0, x1, y1, wx0, wy0, wx1, wy1):
    """Координата перетину відрізка шляху з осьовою перегородкою вздовж її довжини або None."""
    if wy0 == wy1:  # горизонтальна
        if (y0 - wy0) * (y1 - wy0) >= 0 or y0 == y1:
            return None
        x = x0 + (x1 - x0) * (wy0 - y0) / (y1 - y0)
        return x if wx0 <= x <= wx1 else None
    if (x0 - wx0) * (x1 - wx0) >= 0 or x0 == x1:
        return None
    y = y0 + (y1 - y0) * (wx0 - x0) / (x1 - x0)
    return y if wy0 <= y <= wy1 else None


# ----------------------------------------------------------------------------------------------- файли
def f_norm(root):
    rules = {}
    for fn in ("fire_rules.json", "evac_rules.json"):
        rules.update(read_json(root, "plant", fn))
    known = {k for k, *_ in NORMS}
    for k in rules:
        if k not in known:
            fail("невідомий ключ норми %r у JSON макета" % k)
    rows, seq = [], {}
    for key, group, name, unit in NORMS:
        seq[group] = seq.get(group, 0) + 10
        if key in rules:
            r = rules[key]
            value, ref, note = r["value"], r["ref"], r.get("note") or ""
            sources = "\n".join(r.get("sources") or [])
            if r["unit"] != unit:
                note = ("(%s) %s" % (r["unit"], note)).rstrip()
        elif key in AUTHORED:
            value, ref, note = AUTHORED[key]
            sources = ""
        else:
            fail("норма %r без джерела" % key)
        rows.append(
            [
                "norm_" + key,
                key,
                name,
                group,
                seq[group],
                "" if value is None else num(value),
                0 if value is None else 1,
                unit,
                ref,
                note,
                sources,
            ]
        )
    header = ["id", "key", "name", "group", "sequence", "value", "value_set", "unit", "ref", "note", "sources"]
    return csv_text(header, rows), len(rows)


def zone_ref(m, pz):
    return "%s.zone_%s" % (BASE, m["rpc"].key(pz))


def f_panel(m, root):
    ev = read_json(root, "plant", "evac_routes.json")
    fire = m["fire"]
    x = Xml()
    wx, wy = ev["worst_point"]
    x.record(
        PANEL,
        "td.fire.panel",
        [
            ("name", "v", "Приймально-контрольний прилад"),
            ("code", "v", "FACP-1"),
            ("zone_id", "ref", "%s.zone_z_office" % BASE),
            ("x", "v", num(fire.FACP_POS[0])),
            ("y", "v", num(fire.FACP_POS[1])),
            ("evac_max_distance_m", "v", num(ev["max_distance"])),
            ("evac_worst_x", "v", num(wx)),
            ("evac_worst_y", "v", num(wy)),
        ],
    )
    for n, a, b in fire.LOOPS:
        x.record(
            "loop_%d" % n,
            "td.fire.loop",
            [
                ("panel_id", "ref", PANEL),
                ("number", "v", n),
                ("from_x_m", "v", num(a)),
                ("to_x_m", "v", num(b)),
                ("modules_count", "v", m["loops_demo"][str(n)]["modules"]),
            ],
        )
    return x.text(), 1 + len(fire.LOOPS)


def f_zone(m):
    rows = []
    for z in m["zones"]:
        x0, y0, x1, y1 = z["rect"]
        rows.append(
            [
                "fire_zone_" + m["rpc"].key(z["fa"]),
                z["fa"],
                z["name"],
                PANEL,
                "loop_%d" % z["loop"],
                zone_ref(m, z["pz"]),
                z["lsz"],
                z["kind"],
                num(z["spacing"]),
                num(z["wall"]),
                num(x0),
                num(y0),
                num(x1),
                num(y1),
                num(z["z_m"]),
            ]
        )
    header = [
        "id",
        "code",
        "name",
        "panel_id:id",
        "loop_id:id",
        "zone_id:id",
        "lsz_instance",
        "kind",
        "spacing_m",
        "wall_m",
        "x0",
        "y0",
        "x1",
        "y1",
        "z_m",
    ]
    return csv_text(header, rows), len(rows)


def f_system():
    x = Xml()
    for rid, code, name, seq, typ, date, extra in (
        (SYS_SPARK, "SPARK-1", "Іскрогасіння аспірації (GreCon BS 7)", 10, "spark", "2026-10-11", []),
        (
            SYS_SMOKE,
            "SMOKE-CTRL",
            "Димовидалення (D+H CPS-M1, люки LAMILUX F100)",
            20,
            "smoke",
            "2026-09-30",
            [("drive_current_a", "v", "7.5"), ("panel_current_a", "v", "80")],
        ),
        (SYS_SPR, "SPRINKLERS", "Спринклерна система", 30, "sprinkler", "2026-09-30", []),
    ):
        x.record(
            rid,
            "td.fire.system",
            [
                ("code", "v", code),
                ("name", "v", name),
                ("sequence", "v", seq),
                ("system_type", "v", typ),
                ("panel_id", "ref", PANEL),
                ("last_test_date", "v", date),
            ]
            + extra,
        )
    return x.text(), 3


def f_smoke_zone(m):
    rows = []
    for code, (x0, y0, x1, y1) in m["infra"].SMOKE_ZONES:
        rows.append(
            [
                "smoke_zone_" + m["rpc"].key(code),
                code,
                "Димова зона %s" % code,
                SYS_SMOKE,
                num(x0),
                num(y0),
                num(x1),
                num(y1),
            ]
        )
    return csv_text(["id", "code", "name", "system_id:id", "x0", "y0", "x1", "y1"], rows), len(rows)


def f_device(m, devs):
    rows = []
    key = m["rpc"].key
    for d in devs:
        rows.append(
            [
                "dev_" + key(d["address"]),
                d["address"],
                d["type"],
                "" if d.get("system") else PANEL,
                "loop_%d" % d["loop"] if d["loop"] else "",
                "fire_zone_" + key(d["zone"]) if d.get("zone") else "",
                d.get("system", ""),
                "smoke_zone_" + key(d["smoke_zone"]) if d.get("smoke_zone") else "",
                d["lsp"],
                d["seq"],
                num(d["x"]),
                num(d["y"]),
                num(d["z"]),
                d.get("side", ""),
                num(d["heading"]) if "heading" in d else "",
                d.get("note", ""),
            ]
        )
    header = [
        "id",
        "address",
        "type",
        "panel_id:id",
        "loop_id:id",
        "zone_id:id",
        "system_id:id",
        "smoke_zone_id:id",
        "lsp_instance",
        "seq",
        "x",
        "y",
        "z",
        "side",
        "heading_deg",
        "note",
    ]
    return csv_text(header, rows), len(rows)


def build_exits(m):
    ev = m["evacuation"]
    exits = []
    for code, x, y, side in ev.EXITS:
        if code == "EX-IN":
            kind, name = "staff", "Вхід персоналу %s, %s стіна" % (code, SIDE_NAME[side])
        elif code == "EX-N5":
            kind, name = "emergency", "Аварійний вихід %s з компресорної, %s стіна" % (code, SIDE_NAME[side])
        else:
            kind, name = "emergency", "Аварійний вихід %s, %s стіна" % (code, SIDE_NAME[side])
        exits.append((code, name, kind, x, y, side))
    return exits


def f_exit(m, exits):
    rows = [
        ["exit_" + m["rpc"].key(c), c, name, kind, num(x), num(y), side, num(m["evacuation"].DOOR_W), ""]
        for c, name, kind, x, y, side in exits
    ]
    return csv_text(["id", "code", "name", "kind", "x", "y", "side", "width_m", "note"], rows), len(rows)


def build_routes(m, root):
    raw = read_json(root, "plant", "evac_routes.json")["routes"]
    out = {}
    for z in m["layout"].ZONES:
        if z[0] in raw:
            out[z[0]] = raw[z[0]]
    if len(out) != len(raw):
        fail("маршрути макета не відповідають layout.ZONES")
    return out


def f_route(m, routes):
    x = Xml()
    key = m["rpc"].key
    for zc, r in routes.items():
        x.record(
            "route_" + key(zc),
            "td.fire.route",
            [
                ("code", "v", "EVAC-" + zc[2:]),
                ("name", "v", r["name"]),
                ("zone_id", "ref", zone_ref(m, zc)),
                ("exit_id", "ref", "exit_" + key(r["exit"])),
                ("length_m", "v", num(r["length"])),
                ("path", "eval", py([[round(a, 2), round(b, 2)] for a, b in r["path"]])),
                ("width_min_m", "v", "1.2"),
            ],
        )
    return x.text(), len(routes)


def f_template(m):
    steps = m["demo"]["evacuation"]["drill_steps"]
    if len(steps) != len(TEMPLATE_STEPS):
        fail("кроків навчання %d" % len(steps))
    x = Xml()
    x.record(
        "drill_template_default",
        "td.fire.drill.template",
        [
            ("name", "v", "Евакуація цеху: сценарій макета"),
            ("sequence", "v", 10),
            ("is_default", "eval", "True"),
            ("duration_s", "v", 300),
            ("default_zone_id", "ref", "fire_zone_fa_cnc"),
            ("default_device_id", "ref", "dev_2_cnc_05"),
        ],
    )
    for i, (st, (auto_key, text)) in enumerate(zip(steps, TEMPLATE_STEPS), 1):
        x.record(
            "drill_template_step_%02d" % i,
            "td.fire.drill.template.step",
            [
                ("template_id", "ref", "drill_template_default"),
                ("sequence", "v", 10 * i),
                ("t_plan_s", "v", st["t"]),
                ("who", "v", st["who"]),
                ("text", "v", text),
                ("auto_key", "v", auto_key),
            ],
        )
    return x.text(), 1 + len(steps)


def f_source():
    x = Xml(noupdate=True)
    for rid, code, name, typ, params, period in SOURCES:
        x.record(
            rid,
            "td.source",
            [
                ("code", "v", code),
                ("name", "v", name),
                ("type", "v", typ),
                ("params", "eval", py(params)),
                ("collector_id", "ref", "td_telemetry.collector_main"),
                ("module", "v", "fire_safety"),
                ("read_enabled", "eval", "True"),
                ("write_enabled", "eval", "False"),
                ("td_fire_readonly", "eval", "True"),
                ("period_s_default", "v", period),
            ],
        )
    return x.text(), len(SOURCES)


BACNET_FAULT = ["fault", "tamper", "abnormal", "emergency-power", "supervisory"]
OFF_ON = {"0": "off", "1": "on"}


def build_signals(m):
    """Додаток B: список сигналів (dict) у порядку № 1…54."""
    sig = []

    def add(
        code,
        name,
        kind,
        src,
        address,
        period,
        unit="",
        states=None,
        alarm_states=None,
        title="",
        create=False,
        store=3600,
    ):
        sig.append(
            dict(
                code=code,
                name=name,
                kind=kind,
                unit=unit,
                src=src,
                address=address,
                period=period,
                states=states,
                alarm_states=alarm_states,
                title=title,
                create=create,
                store=store,
            )
        )

    def zone_signal(z):
        add(
            "fire/groups/%s/state" % z["fa"],
            "Стан зони %s (%s)" % (z["fa"], z["name"]),
            "state",
            SRC_B,
            {"object": "LSZ", "instance": z["lsz"], "mode": "poll"},
            10,
            alarm_states=list(BACNET_FAULT),
            title="Несправність зони %s (%s): стан «{text}»" % (z["fa"], z["name"]),
            create=True,
        )

    zones = m["zones"]
    for z in zones[:33]:
        zone_signal(z)
    add(
        "fire/totals/state",
        "Прилад FACP-1: стан (LSZ:0)",
        "state",
        SRC_B,
        {"object": "LSZ", "instance": 0, "mode": "poll"},
        10,
        alarm_states=[],
    )
    add(
        "fire/totals/system_state",
        "Прилад FACP-1: системний стан (MSV:1)",
        "state",
        SRC_B,
        {
            "object": "MSV",
            "instance": 1,
            "mode": "poll",
            "map": {"1": "normal", "2": "alarm", "3": "fault", "4": "test", "5": "disabled"},
        },
        10,
        states=["normal", "alarm", "fault", "test", "disabled"],
        alarm_states=[],
    )
    for key, name, inst in (
        ("alarms", "активні тривоги", 1),
        ("faults", "несправності", 2),
        ("disabled", "вимкнення", 3),
    ):
        add(
            "fire/totals/" + key,
            "Прилад FACP-1: " + name,
            "gauge",
            SRC_B,
            {"object": "PIV", "instance": inst, "mode": "poll"},
            10,
            unit="шт",
        )
    for n in range(1, 5):
        add(
            "fire/loops/%d/state" % n,
            "Шлейф %d: несправність" % n,
            "state",
            SRC_B,
            {"object": "BV", "instance": n, "mode": "poll", "map": dict(OFF_ON)},
            10,
            states=["off", "on"],
            alarm_states=["on"],
            title="Несправність шлейфу %d приладу FACP-1" % n,
            create=True,
        )
    add(
        "fire/totals/sounders_active",
        "Оповіщувачі увімкнено (BV:10)",
        "state",
        SRC_B,
        {"object": "BV", "instance": 10, "mode": "poll", "map": dict(OFF_ON)},
        10,
        states=["off", "on"],
        alarm_states=[],
    )
    add(
        "fire/totals/brigade",
        "Передано на пульт ДСНС (BV:11)",
        "state",
        SRC_B,
        {"object": "BV", "instance": 11, "mode": "poll", "map": dict(OFF_ON)},
        10,
        states=["off", "on"],
        alarm_states=[],
    )

    def mb(addr, **kw):
        return dict({"fc": 2, "addr": addr}, **kw)

    add(
        "fire/spark/SPARK-1/state",
        "Іскрогасіння: іскра (DI0)",
        "state",
        SRC_M,
        mb(0, map=dict(OFF_ON)),
        2,
        states=["off", "on"],
        alarm_states=[],
    )
    add(
        "fire/spark/SPARK-1/extinguishing",
        "Іскрогасіння: гасіння (DI1)",
        "state",
        SRC_M,
        mb(1, map=dict(OFF_ON)),
        2,
        states=["off", "on"],
        alarm_states=[],
    )
    add(
        "fire/spark/SPARK-1/fault",
        "Іскрогасіння: несправність (DI2)",
        "state",
        SRC_M,
        mb(2, map=dict(OFF_ON)),
        2,
        states=["off", "on"],
        alarm_states=["on"],
        title="Несправність іскрогасіння SPARK-1 (пульт GreCon BS 7)",
        create=True,
    )
    add(
        "fire/spark/SPARK-1/water_ok",
        "Іскрогасіння: тиск води (DI3)",
        "state",
        SRC_M,
        mb(3, map={"0": "low", "1": "ok"}),
        2,
        states=["low", "ok"],
        alarm_states=["low"],
        title="Іскрогасіння SPARK-1: немає тиску води гасіння",
        create=True,
    )
    add(
        "fire/spark/SPARK-1/count_today",
        "Іскрогасіння: іскор за добу",
        "gauge",
        SRC_M,
        {"fc": 3, "addr": 0, "count": 2, "type": "u32", "wordorder": "little", "unit": 85},
        10,
        unit="шт",
        store=300,
    )
    add(
        "fire/smoke/SMOKE-VENTS/state",
        "Люки димовидалення відкриті (DI4)",
        "state",
        SRC_M,
        mb(4, map={"0": "closed", "1": "open"}),
        2,
        states=["closed", "open"],
        alarm_states=[],
    )
    add(
        "fire/smoke/SMOKE-CTRL/fault",
        "Щит D+H: несправність (DI5)",
        "state",
        SRC_M,
        mb(5, map={"0": "ok", "1": "fault"}),
        2,
        states=["ok", "fault"],
        alarm_states=["fault"],
        title="Несправність щита димовидалення SMOKE-CTRL (D+H CPS-M1): АКБ або живлення",
        create=True,
    )
    add(
        "fire/smoke/SMOKE-CTRL/battery",
        "Щит D+H: живлення від АКБ (DI6)",
        "state",
        SRC_M,
        mb(6, map={"0": "mains", "1": "battery"}),
        2,
        states=["mains", "battery"],
        alarm_states=[],
    )
    for z in zones[33:]:
        zone_signal(z)
    return sig


def f_signal(m):
    sigs = build_signals(m)
    if len(sigs) != EXPECTED["signals"]:
        fail("сигналів %d, очікується %d" % (len(sigs), EXPECTED["signals"]))
    key = m["rpc"].key
    sid = {s["code"]: "sig_" + key(s["code"]) for s in sigs}
    x = Xml()
    x.raw('    <data noupdate="1">')
    for s in sigs:
        f = [("code", "v", s["code"]), ("name", "v", s["name"]), ("kind", "v", s["kind"])]
        if s["unit"]:
            f.append(("unit", "v", s["unit"]))
        f += [
            ("source_id", "ref", SRC_B if s["src"] == SRC_B else SRC_M),
            ("address", "eval", py(s["address"])),
            ("period_s", "v", s["period"]),
            ("store_period_s", "v", s["store"]),
        ]
        if s["states"]:
            f.append(("states", "eval", py(s["states"])))
        if s["alarm_states"] is not None:
            f.append(("alarm_states", "eval", py(s["alarm_states"])))
        if s["title"]:
            f.append(("alarm_title", "v", s["title"]))
        f += [
            ("alarm_priority", "v", "2"),
            ("decimals", "v", 0),
            ("hysteresis", "v", 0),
            ("min_duration_s", "v", 0),
            ("create_request", "eval", py(s["create"])),
            ("write_enabled", "eval", "False"),
            ("viewer_visible", "eval", "False"),
            ("module", "v", "fire_safety"),
            ("origin", "v", "module"),
        ]
        x.record(sid[s["code"]], "td.signal", f)
    x.raw("    </data>")
    x.raw("    <!-- Прив'язки signal_* моделей модуля (оновлюються при апгрейді) -->")
    x.raw("    <data>")

    def bind(rid, model, pairs):
        x.record(rid, model, [(n, "ref", v) for n, v in pairs])

    bind(
        PANEL,
        "td.fire.panel",
        [
            ("source_id", SRC_B),
            ("io_source_id", SRC_M),
            ("signal_state_id", sid["fire/totals/state"]),
            ("signal_system_id", sid["fire/totals/system_state"]),
            ("signal_alarms_id", sid["fire/totals/alarms"]),
            ("signal_faults_id", sid["fire/totals/faults"]),
            ("signal_disabled_id", sid["fire/totals/disabled"]),
            ("signal_sounders_id", sid["fire/totals/sounders_active"]),
            ("signal_brigade_id", sid["fire/totals/brigade"]),
        ],
    )
    for n in range(1, 5):
        bind("loop_%d" % n, "td.fire.loop", [("signal_id", sid["fire/loops/%d/state" % n])])
    for z in m["zones"]:
        bind("fire_zone_" + key(z["fa"]), "td.fire.zone", [("signal_id", sid["fire/groups/%s/state" % z["fa"]])])
    bind(
        SYS_SPARK,
        "td.fire.system",
        [
            ("source_id", SRC_M),
            ("signal_state_id", sid["fire/spark/SPARK-1/state"]),
            ("signal_active_id", sid["fire/spark/SPARK-1/extinguishing"]),
            ("signal_fault_id", sid["fire/spark/SPARK-1/fault"]),
            ("signal_water_id", sid["fire/spark/SPARK-1/water_ok"]),
            ("signal_count_id", sid["fire/spark/SPARK-1/count_today"]),
        ],
    )
    bind(
        SYS_SMOKE,
        "td.fire.system",
        [
            ("source_id", SRC_M),
            ("signal_state_id", sid["fire/smoke/SMOKE-VENTS/state"]),
            ("signal_fault_id", sid["fire/smoke/SMOKE-CTRL/fault"]),
            ("signal_battery_id", sid["fire/smoke/SMOKE-CTRL/battery"]),
        ],
    )
    x.raw("    </data>")
    return x.text(), len(sigs)


def build(root, counts=None):
    """Повертає {ім'я файлу: текст}. counts (dict) — заповнюється кількістю записів по файлах."""
    root = os.path.abspath(root)
    m = collect(root)
    devs = build_devices(m)
    exits = build_exits(m)
    routes = build_routes(m, root)
    norm, n_norm = f_norm(root)
    self_check(m, devs, range(n_norm), routes, exits)
    files = {}

    def put(name, pair):
        files[name] = pair[0]
        if counts is not None:
            counts[name] = pair[1]

    put("td.fire.norm.csv", (norm, n_norm))
    put("td_fire_panel.xml", f_panel(m, root))
    put("td.fire.zone.csv", f_zone(m))
    put("td_fire_system.xml", f_system())
    put("td.fire.smoke.zone.csv", f_smoke_zone(m))
    put("td.fire.device.csv", f_device(m, devs))
    put("td.fire.exit.csv", f_exit(m, exits))
    put("td_fire_route.xml", f_route(m, routes))
    put("td_fire_drill_template.xml", f_template(m))
    put("td_source_data.xml", f_source())
    put("td_signal_data.xml", f_signal(m))
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=DEFAULT_ROOT, help="каталог factory3d (де dist/ і plant/)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="куди писати data-файли")
    args = parser.parse_args(argv)
    counts = {}
    files = build(args.root, counts)
    os.makedirs(args.out, exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print("%s: %d записів" % (name, counts[name]))


if __name__ == "__main__":
    main()
