"""Генератор data-файлів td_bms з макета (SPEC §5.2, Додатки A…C).

Запуск з каталогу factory3d (корінь макета):
    python3 odoo_addons/td_bms/tools/gen_data.py [--root .] [--out odoo_addons/td_bms]

Імпортує plant.lighting, plant.ventilation, plant.layout, читає plant/lux_norms.json, plant/equipment_specs.json,
dist/odoo_demo.json. Пише детерміновано (порядок макета, без часових міток) у `<out>/data/*` і
`<out>/tests/data/static_bms.json`. Невідомий ключ макета (нова зона освітлення, нова установка) — генератор падає.
"""

import argparse
import csv
import importlib.util
import io
import json
import os
import re
import sys
from xml.sax.saxutils import escape, quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_OUT = os.path.abspath(os.path.join(HERE, ".."))

BANNER = "<!-- Згенеровано tools/gen_data.py з макета (SPEC §5.2). Не редагувати вручну. -->"
COLLECTOR_REF = "td_telemetry.collector_main"
PANEL_Y = 71.0  # біля північної стіни всередині зони (Додаток A.2)
PANEL_ZONES = {"LP-1": "Z-PKS", "LP-2": "Z-FAC", "LP-3": "Z-ELEC"}
NORM_NAME_OVERRIDES = {"sanding": "шліфування, оздоблення фасадів", "quality_control": "контроль якості"}
SCENES = [
    (1, "Зміна", 100),
    (2, "Прибирання", 75),
    (3, "Половина", 50),
    (4, "Чергове освітлення", 25),
    (5, "Ніч", 10),
    (6, "Вимкнено", 0),
]
SCENE_NOTE = "Припущення: сцени програмуються в Helvar Designer (Q-05); iot_sim R-24 / §8.10.4."
HELVAR_PARAMS = {
    "host": "iot-sim",
    "port": 50000,
    "protocol": "tcp",
    "timeout_s": 3,
    "cluster": 1,
    "router": 1,
    "version": 2,
    "rate_per_s": 20,
    "push": True,
    "membership_ttl_s": 3600,
}
BACNET_PARAMS = {
    "host": "iot-sim",
    "port": 47808,
    "device": 0,
    "network": 2,
    "timeout_s": 5,
    "rpm": True,
    "rpm_max": 50,
    "cov_lifetime_s": 300,
}
PASSPORT_BY_KIND = {
    "roofvent": "passport_roofvent",
    "ahu": "passport_make_up_ahu",
    "fan": "passport_wall_fan",
    "exfan": "passport_ex_fan",
}
RV_MODE_BY_TEXT = {"Рекуперація": "AQ", "Приплив і витяжка": "VE", "Рециркуляція": "REC"}
LIGHT_CHECK_STATES = [
    "норма",
    "поза робочим часом",
    "вимкнено в робочий час",
    "нижче норми",
    "немає даних",
    "немає мережі (живлення від резерву)",
]
UNIT_CHECK_STATES = [
    "норма",
    "поза робочим часом",
    "не працює в робочий час",
    "холодно в зоні",
    "немає даних",
    "зупинено пожежною сигналізацією",
    "немає мережі (живлення від резерву)",
]
CSV_COLUMNS = [
    "code",
    "name",
    "quantity",
    "kind",
    "unit",
    "object",
    "role",
    "equipment",
    "source",
    "address",
    "period_s",
    "store_period_s",
    "scale",
    "decimals",
    "states",
    "alarm_low",
    "alarm_high",
    "warn_high",
    "alarm_states",
    "alarm_title",
    "hysteresis",
    "min_duration_s",
    "viewer_visible",
    "create_request",
    "origin",
    "writable",
    "new",
]


def die(msg):
    raise SystemExit("gen_data: " + msg)


def slug(code):
    return re.sub(r"[^0-9A-Za-z]+", "_", code).strip("_").lower()


# --- макет -----------------------------------------------------------------------------------------------
def load_plant(root):
    """Імпорт plant.* з кореня макета; повертає namespace з модулями й даними."""
    if root not in sys.path:
        sys.path.insert(0, root)
    from plant import layout, lighting, ventilation
    from plant.equipment import load_specs

    with open(os.path.join(root, "plant", "lux_norms.json"), encoding="utf-8") as f:
        lux_json = json.load(f)
    with open(os.path.join(root, "dist", "odoo_demo.json"), encoding="utf-8") as f:
        demo = json.load(f)
    spec = importlib.util.spec_from_file_location("f3d_bms_tools_lighting", os.path.join(HERE, "lighting.py"))
    tools_lighting = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools_lighting)
    specs = load_specs()
    return {
        "layout": layout,
        "lighting": lighting,
        "ventilation": ventilation,
        "lux": lux_json,
        "demo": demo,
        "specs": specs,
        "pack_dali": tools_lighting.pack_dali,
    }


def build_groups(P):
    """Групи освітлення за порядком каталогу (Додаток A.1) + розклад DALI."""
    lighting = P["lighting"]
    zone_names = {z[0]: z[1] for z in P["layout"].ZONES}
    calc = lighting.layout(P["specs"], P["lux"])
    groups = []
    for n, (zone, task, kind, panel, level, _aisles) in enumerate(lighting.LIGHT_ZONES, 1):
        if zone not in zone_names:
            die("зона %s немає в plant.layout.ZONES" % zone)
        if task not in P["lux"]:
            die("вид робіт %s немає в lux_norms.json" % task)
        code = "LT-" + zone[2:]
        if code not in calc:
            die("група %s не розрахована plant.lighting.layout" % code)
        c = calc[code]
        groups.append(
            {
                "no": n,
                "code": code,
                "zone": zone,
                "zone_name": zone_names[zone],
                "task": task,
                "kind": kind,
                "panel": panel,
                "n": c["n"],
                "level": level,
                "control": "shift" if level == 1.0 else "presence",
            }
        )
    for panel in P["panels"]:
        rows = [g for g in groups if g["panel"] == panel["code"]]
        devs = P["pack_dali"]([(g["code"], g["n"]) for g in rows], cluster=1, router=panel["router"])
        for g in rows:
            g["devices"] = devs[g["code"]]
    return groups


def build_panels(P):
    out = []
    for code, x, name in P["lighting"].PANELS:
        if code not in PANEL_ZONES:
            die("невідомий щит %s" % code)
        out.append(
            {
                "code": code,
                "name": name,
                "x": x,
                "y": PANEL_Y,
                "router": int(code.split("-")[1]),
                "zone": PANEL_ZONES[code],
            }
        )
    return out


def build_units(P):
    """29 установок вентиляції: 25 RV, AHU-1, EF-ELEC, EF-CMP, EF-CHG (Додаток A.3)."""
    vent = P["ventilation"]
    data = vent.ventilation_data(P["specs"])["units"]
    heat_rv = (P["specs"].get("roofvent") or {}).get("heat_kw") or 0.0
    units = []

    def add(code, device, x, y, zone, **kw):
        u = data[code]
        units.append(
            {
                "code": code,
                "name": u["name"],
                "device": device,
                "x": x,
                "y": y,
                "zone": zone,
                "airflow_nom": float(u["airflow_nom"]),
                "p_inst": float(u["p_inst"]),
                "note": u.get("note", ""),
                "fan_count": 1,
                "required_in_work": True,
                "heat_nom": 0.0,
                "t_supply": 0.0,
                "required_m3h": 0.0,
                **kw,
            }
        )

    for code, x, y, zone in vent.ROOFVENTS:
        m = re.fullmatch(r"RV-(\d\d)", code)
        if not m:
            die("невідомий код дахової установки %s" % code)
        mode_text = data[code]["mode"]
        if mode_text not in RV_MODE_BY_TEXT:
            die("невідомий режим макета «%s» (%s)" % (mode_text, code))
        add(
            code,
            100 + int(m.group(1)),
            x,
            y,
            zone,
            kind="roofvent",
            mode_design=RV_MODE_BY_TEXT[mode_text],
            heat_nom=float(heat_rv),
        )
    ax, ay = vent.AHU_POS
    add(
        "AHU-1",
        130,
        ax,
        ay,
        data["AHU-1"]["zone"],
        kind="ahu",
        mode_design="VE",
        t_supply=float(data["AHU-1"]["supply_c"]),
    )
    fan_dev = {"EF-ELEC": 131, "EF-CMP": 132}
    for code, _name, pts, _note in vent.WALL_FANS:
        if code not in fan_dev:
            die("невідомий вентилятор %s" % code)
        add(
            code,
            fan_dev[code],
            pts[0][0],
            71.4,
            data[code]["zone"],
            kind="fan",
            mode_design="thermostat",
            fan_count=len(pts),
            required_in_work=False,
        )
    cx, cy = vent.CHG_EXHAUST
    ex = P["specs"].get("ex_fan") or {}
    add(
        "EF-CHG",
        133,
        cx,
        cy,
        data["EF-CHG"]["zone"],
        kind="exfan",
        mode_design="charging",
        required_in_work=False,
        required_m3h=float(ex.get("required_m3h") or 160),
    )
    if len(units) != 29:
        die("очікувано 29 установок, є %d" % len(units))
    return units


# --- XML -------------------------------------------------------------------------------------------------
def pyrepr(v):
    """Детермінований Python-літерал для `eval` (словники зберігають порядок ключів)."""
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (pyrepr(k), pyrepr(x)) for k, x in v.items()) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(pyrepr(x) for x in v) + "]"
    return repr(v)


def ftxt(name, value):
    return '        <field name="%s">%s</field>' % (name, escape(str(value)))


def fref(name, ref):
    return '        <field name="%s" ref="%s"/>' % (name, ref)


def fev(name, value):
    return "        <field name=%s eval=%s/>" % (quoteattr(name), quoteattr(pyrepr(value)))


def record(rid, model, fields):
    return '    <record id="%s" model="%s">\n%s\n    </record>' % (rid, model, "\n".join(fields))


def xml_doc(records):
    return '<?xml version="1.0" encoding="utf-8"?>\n<odoo noupdate="1">\n    %s\n%s\n</odoo>\n' % (
        BANNER,
        "\n".join(records),
    )


def gen_norms(P):
    lighting, lux = P["lighting"], P["lux"]
    recs = []
    for i, (key, v) in enumerate(lux.items(), 1):
        name = NORM_NAME_OVERRIDES.get(key) or lighting.NORM_NAMES.get(key)
        if not name:
            die("немає назви норми %s" % key)
        recs.append(
            record(
                "norm_" + key,
                "td.bms.light.norm",
                [
                    ftxt("key", key),
                    ftxt("name", name),
                    fev("sequence", i * 10),
                    fev("lux", int(v["lux"])),
                    fev("ugr", int(v["ugr"])),
                    fev("ra", int(v["ra"])),
                    ftxt("ref_en", v.get("ref") or ""),
                    ftxt("note", v.get("note") or ""),
                    ftxt("sources", "\n".join(v.get("sources") or [])),
                ],
            )
        )
    if len(recs) != 13:
        die("очікувано 13 норм, є %d" % len(recs))
    return xml_doc(recs)


def gen_scenes():
    recs = [
        record(
            "scene_%d" % n,
            "td.bms.light.scene",
            [ftxt("number", n), ftxt("name", name), fev("level_pct", lvl), fev("block", 1), ftxt("note", SCENE_NOTE)],
        )
        for n, name, lvl in SCENES
    ]
    return xml_doc(recs)


def source_defs(units):
    """32 джерела модуля (Додаток C): [(xml-id, code, type, name, params, period)]."""
    out = []
    for r in (1, 2, 3):
        out.append(
            (
                "source_hn_lp_%d" % r,
                "HN-LP-%d" % r,
                "helvarnet",
                "Helvar Imagine 950 · щит LP-%d" % r,
                {**HELVAR_PARAMS, "router": r},
                60,
            )
        )
    for u in units:
        dev = u["device"]
        if u["kind"] == "roofvent":
            name = "Hoval RoofVent %s (BACnet dev %d)" % (u["code"], dev)
        elif u["code"] == "AHU-1":
            name = "VTS VENTUS AHU-1 (BACnet dev 130)"
        else:
            name = {
                "EF-ELEC": "Вентилятори електрощитової EF-ELEC (dev 131)",
                "EF-CMP": "Вентилятор компресорної EF-CMP (dev 132)",
                "EF-CHG": "Витяжка зарядної EF-CHG (dev 133)",
            }[u["code"]]
        out.append(
            (
                "source_bac_%d" % dev,
                "BAC-%d-%s" % (dev, u["code"]),
                "bacnet_ip",
                name,
                {**BACNET_PARAMS, "device": dev},
                30,
            )
        )
    return out


def gen_sources(units):
    recs = []
    for rid, code, typ, name, params, period in source_defs(units):
        recs.append(
            record(
                rid,
                "td.source",
                [
                    ftxt("code", code),
                    ftxt("name", name),
                    ftxt("type", typ),
                    fref("collector_id", COLLECTOR_REF),
                    ftxt("module", "bms"),
                    fev("params", params),
                    fev("read_enabled", True),
                    fev("write_enabled", False),
                    fev("period_s_default", period),
                ],
            )
        )
    return xml_doc(recs)


def zone_ref(code):
    return "td_factory3d.zone_" + slug(code)


def gen_light(panels, groups):
    recs = []
    for p in panels:
        recs.append(
            record(
                "panel_lp_%d" % p["router"],
                "td.bms.light.panel",
                [
                    ftxt("code", p["code"]),
                    ftxt("name", p["name"]),
                    fev("cluster", 1),
                    fev("router", p["router"]),
                    fev("x", p["x"]),
                    fev("y", p["y"]),
                    fref("zone_id", zone_ref(p["zone"])),
                    fref("source_id", "source_hn_lp_%d" % p["router"]),
                ],
            )
        )
    for g in groups:
        recs.append(
            record(
                "group_" + slug(g["code"]),
                "td.bms.light.group",
                [
                    ftxt("code", g["code"]),
                    ftxt("name", "Освітлення: " + g["zone_name"]),
                    fev("sequence", g["no"] * 10),
                    fref("zone_id", zone_ref(g["zone"])),
                    fref("norm_id", "norm_" + g["task"]),
                    fref("panel_id", "panel_lp_" + g["panel"].split("-")[1]),
                    fref(
                        "passport_id",
                        "td_factory3d.passport_highbay_rack"
                        if g["kind"] == "highbay_rack"
                        else "td_factory3d.passport_highbay",
                    ),
                    ftxt("fixture_kind", g["kind"]),
                    fev("n_fixtures", g["n"]),
                    fev("level_design", g["level"]),
                    ftxt("control_mode", g["control"]),
                    fev("dali_group", g["no"]),
                    ftxt("dali_devices", g["devices"]),
                ],
            )
        )
    return xml_doc(recs)


def gen_hvac(units):
    recs = []
    for i, u in enumerate(units, 1):
        fields = [
            ftxt("code", u["code"]),
            ftxt("name", u["name"]),
            fev("sequence", i * 10),
            ftxt("kind", u["kind"]),
            fref("zone_id", zone_ref(u["zone"])),
            fev("x", u["x"]),
            fev("y", u["y"]),
            fref("passport_id", "td_factory3d." + PASSPORT_BY_KIND[u["kind"]]),
            fref("source_id", "source_bac_%d" % u["device"]),
            fev("bacnet_device", u["device"]),
            fev("fan_count", u["fan_count"]),
            fev("airflow_nom", u["airflow_nom"]),
            fev("heat_nom_kw", u["heat_nom"]),
            fev("p_inst_kw", u["p_inst"]),
            ftxt("mode_design", u["mode_design"]),
            fev("required_in_work", u["required_in_work"]),
        ]
        if u["t_supply"]:
            fields.append(fev("t_supply_design", u["t_supply"]))
        if u["required_m3h"]:
            fields.append(fev("required_m3h", u["required_m3h"]))
        if u["note"]:
            fields.append(ftxt("note", u["note"]))
        recs.append(record("unit_" + slug(u["code"]), "td.bms.hvac.unit", fields))
    recs.append(
        record(
            "heat_balance_main",
            "td.bms.heat.balance",
            [ftxt("name", "Тепловий баланс цеху"), fref("company_id", "base.main_company")],
        )
    )
    return xml_doc(recs)


# --- сигнали (Додаток B) ---------------------------------------------------------------------------------
def jc(obj):
    """Компактний JSON для колонок CSV."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def bacnet_addr(obj, inst, unit, name, **extra):
    addr = {"object": obj, "instance": inst}
    addr.update(extra)
    addr["property"] = "present-value"
    addr["mode"] = "poll"
    addr["doc"] = "%s:%d %s_%s" % (obj, inst, unit, name)
    return addr


def make_row(**kw):
    row = {c: "" for c in CSV_COLUMNS}
    row.update(scale=1, viewer_visible=1, create_request=1, writable=0)
    row.update(kw)
    for key in ("address", "states", "alarm_states"):
        if not isinstance(row[key], str):
            row[key] = jc(row[key])
    return row


def unit_rows(u):
    code, dev = u["code"], u["device"]
    src = "BAC-%d-%s" % (dev, code)
    base = "ventilation/units/%s/" % code
    rows = []

    def add(role, path, name, quantity, kind, unit, addr, period, store, dec, origin, new, **kw):
        rows.append(
            make_row(
                code=base + path,
                name="%s: %s" % (code, name) if "{U}" not in name else name.replace("{U}", code),
                quantity=quantity,
                kind=kind,
                unit=unit,
                object=code,
                role=role,
                equipment=code,
                source=src,
                address=addr,
                period_s=period,
                store_period_s=store,
                decimals=dec,
                origin=origin,
                new=new,
                **kw,
            )
        )

    def ai(inst, nm, obj="AI", **extra):
        return bacnet_addr(obj, inst, code, nm, **extra)

    if u["kind"] in ("roofvent", "ahu"):
        add(
            "airflow",
            "airflow_m3h",
            "витрата повітря",
            "Витрата",
            "gauge",
            "м³/год",
            ai(3, "SupplyAirFlow"),
            30,
            600,
            0,
            "sim_data",
            0,
        )
        add(
            "supply",
            "supply_c",
            "температура припливу",
            "Температура",
            "gauge",
            "°C",
            ai(1, "SupplyAirTemp"),
            30,
            600,
            1,
            "sim_data",
            0,
        )
        add(
            "filter",
            "filter_dp_pa",
            "перепад на фільтрі припливу",
            "Перепад",
            "gauge",
            "Па",
            ai(4, "FreshAirFilterDp"),
            30,
            600,
            0,
            "sim_data",
            0,
            alarm_high=265,  # норма до 250 Па; тривога — лише від суттєвого перевищення (+6 %), а не 250,07 проти 250
            hysteresis=5,
            alarm_title="Заміна фільтрів: перепад {value} Па, понад допуск {threshold} Па (норма до 250 Па)",
        )
        add(
            "indoor",
            "indoor_c",
            "температура в зоні",
            "Температура",
            "gauge",
            "°C",
            ai(2, "ExtractAirTemp"),
            30,
            600,
            1,
            "catalog",
            1,
        )
        add(
            "valve",
            "heating_valve",
            "клапан нагрівача",
            "Положення",
            "gauge",
            "%",
            ai(1, "HeatingValve", obj="AO"),
            30,
            600,
            0,
            "catalog",
            1,
        )
        add(
            "mode",
            "mode",
            "режим роботи",
            "Режим",
            "state",
            "",
            bacnet_addr(
                "MSV",
                1,
                code,
                "OperatingMode",
                map={str(i): m for i, m in enumerate(["VE", "VEL", "AQ", "REC", "EA", "SA", "ST", "Off"], 1)},
            ),
            30,
            3600,
            0,
            "catalog",
            1,
            states=["VE", "VEL", "AQ", "REC", "EA", "SA", "ST", "Off"],
            alarm_states=[],
            create_request=0,
            viewer_visible=0,
            writable=1,
        )
        add(
            "state",
            "state",
            "стан установки",
            "Стан",
            "state",
            "",
            bacnet_addr(
                "BI",
                1,
                code,
                "Running",
                states=[
                    {"object": "BI", "instance": 2, "eq": 1, "text": "fault"},
                    {"object": "BI", "instance": 5, "eq": 1, "text": "frost"},
                    {"object": "BI", "instance": 1, "eq": 1, "text": "running"},
                    {"object": "BI", "instance": 1, "eq": 0, "text": "stopped"},
                ],
            ),
            30,
            3600,
            0,
            "catalog",
            1,
            states=["running", "stopped", "fault", "frost"],
            alarm_states=["fault", "frost"],
            alarm_title="{equipment}: аварія установки (стан «{text}»)",
            viewer_visible=0,
        )
        add(
            "filter_extract",
            "filter_extract_dp_pa",
            "перепад на фільтрі витяжки",
            "Перепад",
            "gauge",
            "Па",
            ai(5, "ExtractAirFilterDp"),
            30,
            600,
            0,
            "module",
            1,
            alarm_high=370,  # норма до 350 Па; тривога — від +6 %
            hysteresis=10,
            alarm_title="Заміна фільтрів витяжки: перепад {value} Па, понад допуск {threshold} Па (норма до 350 Па)",
        )
        add(
            "heat",
            "heat_kw",
            "теплова потужність",
            "Потужність",
            "gauge",
            "кВт",
            ai(7, "HeatOutput"),
            30,
            600,
            1,
            "module",
            1,
        )
        add(
            "power",
            "p_now",
            "потужність вентиляторів",
            "Потужність",
            "gauge",
            "кВт",
            ai(8, "FanPower"),
            30,
            600,
            2,
            "module",
            1,
        )
        add(
            "sp_day",
            "setpoint_day_c",
            "уставка день",
            "Температура",
            "gauge",
            "°C",
            ai(1, "RoomSetpointDay", obj="AV"),
            300,
            3600,
            1,
            "module",
            1,
            writable=1,
        )
        add(
            "sp_night",
            "setpoint_night_c",
            "уставка ніч",
            "Температура",
            "gauge",
            "°C",
            ai(2, "RoomSetpointNight", obj="AV"),
            300,
            3600,
            1,
            "module",
            1,
            writable=1,
        )
        rows.append(
            make_row(
                code=base + "check",
                name="%s: перевірка роботи" % code,
                quantity="Перевірка",
                kind="state",
                object=code,
                role="check",
                equipment=code,
                source="BMS-DERIVED",
                address={},
                period_s=60,
                store_period_s=3600,
                decimals=0,
                states=UNIT_CHECK_STATES,
                alarm_states=["не працює в робочий час", "холодно в зоні"],
                alarm_title="{equipment}: {text}",
                viewer_visible=0,
                origin="module",
                new=1,
            )
        )
        if code == "AHU-1":
            add(
                "pressure",
                "room_pressure_pa",
                "тиск у дільниці фасадів",
                "Тиск",
                "gauge",
                "Па",
                ai(9, "RoomPressure"),
                30,
                600,
                0,
                "module",
                1,
                alarm_high=0,
                hysteresis=1,
                min_duration_s=300,
                alarm_title="Дільниця фасадів: тиск {value} Па при нормі до {threshold} (має бути розрідження)",
            )
            add(
                "interlock",
                "booth_interlock",
                "витяжка фарбувальних камер працює",
                "Стан",
                "state",
                "",
                bacnet_addr("BI", 6, code, "BoothExtractInterlock", map={"0": "off", "1": "on"}),
                30,
                3600,
                0,
                "module",
                1,
                states=["off", "on"],
                create_request=0,
                viewer_visible=0,
            )
        return rows
    # вентилятори (B.2)
    add(
        "airflow",
        "airflow_m3h",
        "витрата повітря",
        "Витрата",
        "gauge",
        "м³/год",
        ai(3, "AirFlow"),
        30,
        600,
        0,
        "sim_data",
        0,
    )
    if code == "EF-CHG":
        add(
            "state",
            "state",
            "стан витяжки",
            "Стан",
            "state",
            "",
            bacnet_addr(
                "BI",
                1,
                code,
                "Running",
                states=[
                    {"object": "BI", "instance": 1, "eq": 1, "text": "running"},
                    {"object": "BI", "instance": 7, "eq": 1, "text": "stopped_charging"},
                    {"object": "BI", "instance": 1, "eq": 0, "text": "stopped"},
                ],
            ),
            30,
            3600,
            0,
            "catalog",
            1,
            states=["running", "stopped", "stopped_charging"],
            alarm_states=["stopped_charging"],
            min_duration_s=60,
            alarm_title="{equipment}: не працює під час заряджання — водень!",
            viewer_visible=0,
        )
    else:
        add(
            "state",
            "state",
            "стан вентилятора",
            "Стан",
            "state",
            "",
            bacnet_addr("BI", 1, code, "Running", map={"0": "stopped", "1": "running"}),
            30,
            3600,
            0,
            "catalog",
            1,
            states=["running", "stopped"],
            create_request=0,
            viewer_visible=0,
        )
    extra = {}
    if code == "EF-ELEC":
        extra = {
            "alarm_high": 35,
            "hysteresis": 1,
            "min_duration_s": 600,
            "alarm_title": "Електрощитова: температура {value} °C при нормі до {threshold}",
        }
    elif code == "EF-CMP":
        extra = {"warn_high": 35}
    add(
        "indoor",
        "indoor_c",
        "температура приміщення",
        "Температура",
        "gauge",
        "°C",
        ai(2, "RoomTemp"),
        30,
        600,
        0,
        "module",
        1,
        **extra,
    )
    return rows


def boiler_rows():
    def r(code, name, quantity, kind, unit, source, addr, period, store, dec, origin, role, obj, equipment, **kw):
        return make_row(
            code=code,
            name=name,
            quantity=quantity,
            kind=kind,
            unit=unit,
            object=obj,
            role=role,
            equipment=equipment,
            source=source,
            address=addr,
            period_s=period,
            store_period_s=store,
            decimals=dec,
            origin=origin,
            new=1,
            **kw,
        )

    return [
        r(
            "ventilation/totals/outdoor_c",
            "Зовнішня температура (RV-01)",
            "Температура",
            "gauge",
            "°C",
            "BAC-101-RV-01",
            bacnet_addr("AI", 6, "RV-01", "OutdoorTemp"),
            60,
            900,
            1,
            "module",
            "outdoor",
            "BALANCE",
            "RV-01",
        ),
        r(
            "equipment/BOILER/return_c",
            "Котельня: температура зворотної води",
            "Температура",
            "gauge",
            "°C",
            "BAC-140-BOILER",
            bacnet_addr("AI", 2, "BOILER", "ReturnTemp"),
            30,
            600,
            1,
            "catalog",
            "boiler_return",
            "BALANCE",
            "BOILER",
        ),
        r(
            "equipment/BOILER/state",
            "Котельня: стан",
            "Стан",
            "state",
            "",
            "BAC-140-BOILER",
            bacnet_addr("MSV", 1, "BOILER", "State", map={"1": "standby", "2": "K1", "3": "K1+K2", "4": "fault"}),
            30,
            3600,
            0,
            "catalog",
            "boiler_state",
            "BALANCE",
            "BOILER",
            states=["standby", "K1", "K1+K2", "fault"],
            alarm_states=["fault"],
            alarm_title="{equipment}: аварія котельні (стан «{text}»)",
            viewer_visible=0,
        ),
        r(
            "equipment/BOILER/heat_kw",
            "Котельня: теплова потужність",
            "Потужність",
            "gauge",
            "кВт",
            "BAC-140-BOILER",
            bacnet_addr("AI", 5, "BOILER", "HeatOutput"),
            30,
            600,
            1,
            "module",
            "boiler_heat",
            "BALANCE",
            "BOILER",
        ),
        r(
            "ventilation/heat_plant/check",
            "Котельня: перевірка теплового балансу",
            "Перевірка",
            "state",
            "",
            "BMS-DERIVED",
            {},
            60,
            3600,
            0,
            "module",
            "check",
            "BALANCE",
            "BOILER",
            states=["норма", "дефіцит тепла", "немає даних"],
            alarm_states=["дефіцит тепла"],
            alarm_title="Котельня: {text}",
            viewer_visible=0,
        ),
    ]


def light_rows(groups):
    rows = []
    for g in groups:
        code, no, devs = g["code"], g["no"], g["devices"]
        router = int(g["panel"].split("-")[1])
        src = "HN-LP-%d" % router
        base = "lighting/groups/%s/" % code
        devl = devs.split(";")

        def add(
            role,
            path,
            name,
            quantity,
            kind,
            unit,
            addr,
            period,
            store,
            dec,
            origin,
            base=base,
            code=code,
            src=src,
            **kw,
        ):
            rows.append(
                make_row(
                    code=base + path,
                    name="%s: %s" % (code, name),
                    quantity=quantity,
                    kind=kind,
                    unit=unit,
                    object=code,
                    role=role,
                    equipment=code,
                    source=src,
                    address=addr,
                    period_s=period,
                    store_period_s=store,
                    decimals=dec,
                    origin=origin,
                    new=1,
                    **kw,
                )
            )

        add(
            "level",
            "level",
            "рівень освітлення",
            "Рівень",
            "gauge",
            "%",
            {"group": no, "query": "level", "devices": devl, "sample": 3, "fade_s": 2.0},
            60,
            900,
            0,
            "catalog",
            writable=1,
        )
        add(
            "power",
            "p_now",
            "потужність",
            "Потужність",
            "gauge",
            "кВт",
            {"group": no, "query": "power", "scale": 0.001},
            60,
            900,
            2,
            "catalog",
        )
        add(
            "faults",
            "faults",
            "несправних світильників",
            "Кількість",
            "gauge",
            "шт",
            {"group": no, "query": "faults", "devices": devl, "mask": 134217742},
            300,
            3600,
            0,
            "module",
            alarm_high=0,
            alarm_title="Аварія світильників {code}: несправних {value} шт. при нормі {threshold}",
        )
        add(
            "faulty",
            "faulty",
            "адреси несправних світильників",
            "Адреси",
            "state",
            "",
            {"group": no, "query": "faulty", "devices": devl, "mask": 134217742},
            300,
            3600,
            0,
            "module",
            states=[],
            create_request=0,
            viewer_visible=0,
        )
        add(
            "scene",
            "scene",
            "остання сцена",
            "Сцена",
            "gauge",
            "",
            {"group": no, "query": "scene", "block": 1, "fade_s": 2.0},
            60,
            3600,
            0,
            "module",
            writable=1,
        )
        rows.append(
            make_row(
                code=base + "check",
                name="%s: перевірка освітлення" % code,
                quantity="Перевірка",
                kind="state",
                object=code,
                role="check",
                equipment=code,
                source="BMS-DERIVED",
                address={},
                period_s=60,
                store_period_s=3600,
                decimals=0,
                states=LIGHT_CHECK_STATES,
                alarm_states=["вимкнено в робочий час", "нижче норми"],
                alarm_title="{equipment}: {text}",
                viewer_visible=0,
                origin="module",
                new=1,
            )
        )
    return rows


def panel_rows(panels):
    return [
        make_row(
            code="lighting/panels/%s/state" % p["code"],
            name="%s: стан щита (роутер Imagine 950)" % p["code"],
            quantity="Стан",
            kind="state",
            object=p["code"],
            role="state",
            equipment=p["code"],
            source="HN-LP-%d" % p["router"],
            address={"device": "@1.%d.0.0" % p["router"], "query": "router"},
            period_s=60,
            store_period_s=3600,
            decimals=0,
            states=["ok", "fault", "offline"],
            create_request=0,
            viewer_visible=0,
            origin="catalog",
            new=1,
        )
        for p in panels
    ]


def gen_signals(units, groups, panels):
    rows = []
    for u in units:
        rows += unit_rows(u)
    rows += boiler_rows()
    rows += light_rows(groups)
    rows += panel_rows(panels)
    codes = [r["code"] for r in rows]
    if len(rows) != 549 or len(set(codes)) != 549:
        die("очікувано 549 унікальних сигналів, є %d / %d" % (len(rows), len(set(codes))))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def gen_static(P):
    demo = P["demo"]
    return (
        json.dumps({"lighting": demo["lighting"], "ventilation": demo["ventilation"]}, ensure_ascii=False, indent=1)
        + "\n"
    )


def generate(root=DEFAULT_ROOT):
    """Повертає {відносний шлях у модулі: текст}; детерміновано."""
    root = os.path.abspath(root)
    P = load_plant(root)
    P["panels"] = build_panels(P)
    groups = build_groups(P)
    units = build_units(P)
    return {
        "data/td_bms_light_norm_data.xml": gen_norms(P),
        "data/td_bms_light_scene_data.xml": gen_scenes(),
        "data/td_bms_source_data.xml": gen_sources(units),
        "data/td_bms_light_data.xml": gen_light(P["panels"], groups),
        "data/td_bms_hvac_data.xml": gen_hvac(units),
        "data/bms_signals.csv": gen_signals(units, groups, P["panels"]),
        "tests/data/static_bms.json": gen_static(P),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=DEFAULT_ROOT, help="корінь макета (каталог factory3d)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="корінь модуля: пише <out>/data/* і <out>/tests/data/*")
    args = ap.parse_args(argv)
    files = generate(args.root)
    for rel, text in files.items():
        path = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("%-40s %7d байт" % (rel, len(text.encode("utf-8"))))


if __name__ == "__main__":
    main()
