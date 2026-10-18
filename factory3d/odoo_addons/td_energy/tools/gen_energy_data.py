"""Генератор `data/energy_*.csv` (SPEC §5.2, Додатки B–D): детерміновано, без часових міток, Odoo не вантажить.

Запуск (з кореня репозиторію): `python3 odoo_addons/factory3d_energy/tools/gen_energy_data.py --root .`
Читає `plant/energy.py` (`consumers`, `taps`, `PROFILE`, `IDLE_K`, `IDLE_DEFAULT`, `SWB_CELLS`, `SECTION`, `BUSWAYS`,
`CABLE_FEEDERS`), `plant/layout.py:MACHINES`, `plant/infra.py:CRITICAL`, `plant/equipment_specs.json` (через
`plant.equipment.load_specs`). Список unit id і адреси регістрів — зашиті таблиці Додатків A і D.

Колонка `origin` у `energy_signals.csv` має три значення: `sim_data` (сигнал існує з міграції рівня 0; хук його не
створює, а за відсутності — створює з `origin='catalog'`), `catalog`, `module` (Додаток C, колонка «Походження»).
"""

import argparse
import csv
import json
import os
import sys

NODE_COLS = [
    "code", "name", "kind", "cell_type", "line_kind", "gen_kind", "parent", "cabinet", "peer", "section", "sequence",
    "equipment", "workcenter", "rating_a", "rating_kva", "rating_kvar", "voltage_kv", "p_inst_kw", "p_inst_source",
    "load_factor", "idle_factor", "cos_phi", "is_critical", "alloc_role", "pool", "group", "unit", "note",
]  # fmt: skip
SOURCE_COLS = ["code", "name", "unit", "equipment", "host", "port", "timeout_s", "retries", "max_block", "gap_max"]
SIGNAL_COLS = [
    "code", "name", "quantity", "kind", "unit", "equipment", "source", "address", "period_s", "store_period_s",
    "decimals", "states", "warn_low", "warn_high", "alarm_low", "alarm_high", "alarm_states", "alarm_title",
    "hysteresis", "min_duration_s", "viewer_visible", "derived_from", "origin", "binding",
]  # fmt: skip
METER_COLS = [
    "code",
    "name",
    "node",
    "model",
    "role",
    "source",
    "p_signal",
    "e_import_signal",
    "e_export_signal",
    "ct_ratio",
]
POOL_COLS = ["code", "name", "sequence", "driver", "workcenters"]

DERIVED = "EN-DERIVED"
RTD_SOURCE = "MB-U96-RTD1"
RTD = {"fc": 3, "type": "u16", "scale": 0.0030518044, "offset": -50, "range": [-50, 150], "count": 3, "agg": "max"}

# Карти станів (Додаток A.2): ім'я -> (map, states, alarm_states)
MAPS = {
    "breaker": ({"0": "open", "1": "closed", "2": "tripped"}, ["open", "closed", "tripped"], ["tripped"]),
    "pv_status": (
        {"0": "standby", "1": "standby", "2": "standby", "3": "standby", "256": "starting", "512": "on_grid",
         "513": "limited", "768": "fault", "769": "stopped", "771": "no_grid", "40960": "no_sun"},
        ["standby", "starting", "on_grid", "limited", "fault", "stopped", "no_grid", "no_sun"], ["fault"]),
    "bess_state": (
        {"0": "offline", "1": "standby", "2": "running", "3": "fault", "4": "sleep"},
        ["offline", "standby", "running", "fault", "sleep"], ["fault"]),
    "chp_state": (
        {"0": "stop", "1": "starting", "2": "running", "3": "fault", "4": "cooling"},
        ["stop", "starting", "running", "fault", "cooling"], ["fault"]),
    "ats_mode": (
        {"0": "manual", "1": "locked", "16": "auto", "32": "remote", "64": "inhibit"},
        ["manual", "locked", "auto", "remote", "inhibit"], []),
    "ats_position": (
        {"0": "unknown", "1": "pos_0", "2": "pos_I", "3": "pos_II"}, ["unknown", "pos_0", "pos_I", "pos_II"], []),
    "onoff": ({"0": "off", "1": "on"}, ["off", "on"], []),
    "ats_source": ({"0": "under", "1": "present", "2": "available"}, ["under", "present", "available"], []),
}  # fmt: skip

PM = "Schneider PM5560"
# Регістри PM5560 (Додаток A.1): ключ -> (PDU, тип, scale, номер у документі, назва)
PM_REG = {
    "p": (2999 + 60, "f32", None, 3060, "Active Power Total"),
    "i_now": (3009, "f32", None, 3010, "Current Avg"),
    "i_a": (2999, "f32", None, 3000, "Current A"),
    "i_b": (3001, "f32", None, 3002, "Current B"),
    "i_c": (3003, "f32", None, 3004, "Current C"),
    "q": (3067, "f32", None, 3068, "Reactive Power Total"),
    "s": (3075, "f32", None, 3076, "Apparent Power Total"),
    "cos": (3083, "f32", None, 3084, "Power Factor Total"),
    "e_imp": (3203, "i64", 0.001, 3204, "Active Energy Delivered (Into Load)"),
    "e_exp": (3207, "i64", 0.001, 3208, "Active Energy Received (Out of Load)"),
    "state": (2017, "u16", None, 2018, "Breaker state (ПРИПУЩЕННЯ iot_sim)"),
}
PM_REG["p"] = (3059, "f32", None, 3060, "Active Power Total")


def _addr(vendor, reg, mapname=None):
    pdu, typ, scale, doc_no, title = reg
    a = {"fc": 3, "addr": pdu, "type": typ}
    if scale is not None:
        a["scale"] = scale
    if mapname:
        a["map"] = MAPS[mapname][0]
    a["doc"] = "%s %s %s" % (vendor, doc_no, title)
    return a


def _pm(key, mapname=None):
    return _addr(PM, PM_REG[key], mapname)


def _reg(vendor, pdu, typ, doc_no, title, scale=None, mapname=None):
    return _addr(vendor, (pdu, typ, scale, doc_no, title), mapname)


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    return str(v)


def _write(path, cols, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([_cell(r.get(c)) for c in cols])


# --------------------------------------------------------------------------- вузли (Додаток B)
POOL_OF = {
    "GANTRY-1": "POOL-GANTRY", "COMPRESSOR": "POOL-AIR", "DUST-1": "POOL-DUST", "LP-1": "POOL-LIGHT",
    "LP-2": "POOL-LIGHT", "LP-3": "POOL-LIGHT", "RV-ALL": "POOL-HVAC", "AHU-1": "POOL-HVAC",
}  # fmt: skip
OVERHEAD = ["BOILER", "CHARGING", "OFFICE", "EF-ELEC", "EF-CMP", "EF-CHG"]
NO_EQUIPMENT = ("OFFICE", "RV-ALL")
CELL_RATING = {"incomer": 1600, "coupler": 1600, "feeder": 630, "cable": 630, "pfc": None}
LINE_RATING = {"BW-1": 630, "BW-2": 630, "BW-3": 630, "BW-4": 630, "C1": 630, "C2": 400}
SYN_UNITS = {}  # unit id: консументи — 11…59 у порядку Додатка B (GANTRY-1 = 46)


def build_nodes(plant):
    energy, layout, infra = plant["energy"], plant["layout"], plant["infra"]
    cons = energy.consumers(plant["specs"])
    taps = energy.taps()
    types = {m[0]: m[1] for m in layout.MACHINES}
    machine_order = [m[0] for m in layout.MACHINES]
    crit = {("BW-1" if c == "BW-1-LINE" else c) for c in infra.CRITICAL}
    cells = {c[0]: c for c in energy.SWB_CELLS}
    seq = {c[0]: (i + 1) * 10 for i, c in enumerate(energy.SWB_CELLS)}
    rows = []

    def add(**kw):
        kw.setdefault("is_critical", 1 if kw["code"] in crit else None)
        rows.append(kw)

    add(code="GRID-10KV", name="Ввід 10 кВ", kind="input", voltage_kv=10)
    add(code="RM6-1", name="Комірки СН RM6", kind="substation", parent="GRID-10KV", equipment="RM6-1", voltage_kv=10)
    for t in ("T1", "T2"):
        add(code=t, name="Трансформатор " + t, kind="transformer", parent="RM6-1", equipment=t,
            rating_kva=energy.TRAFO_KVA)  # fmt: skip
    add(code="SWB-1", name="ГРЩ 0,4 кВ", kind="switchboard", equipment="SWB-1")
    parent_of_cell = {"Q1": "T1", "Q2": "T2", "PFC-1": "SEC-1", "QF-3": "SEC-1", "QF-2": "SEC-1", "QF-C1": "SEC-1",
                      "QS": "SEC-1", "QF-1": "SEC-2", "QF-4": "SEC-2", "QF-C2": "SEC-2", "PFC-2": "SEC-2"}  # fmt: skip
    section = {"SEC-1": 1, "SEC-2": 2}

    def cell_row(code):
        _, name, _, ctype, feeds = cells[code]
        rating = LINE_RATING.get(feeds) if code in ("QF-C1", "QF-C2") else CELL_RATING[ctype]
        if code in ("QF-C1", "QF-C2"):
            rating = LINE_RATING["C1" if code == "QF-C1" else "C2"]
        sec = 0 if ctype == "coupler" else energy.SECTION.get(code)
        section[code] = sec
        add(code=code, name=name, kind="cell", cell_type=ctype, parent=parent_of_cell[code], cabinet="SWB-1",
            peer="SEC-2" if ctype == "coupler" else None, section=sec, sequence=seq[code], equipment=code,
            rating_a=rating if ctype != "pfc" else None, rating_kvar=energy.PFC_KVAR if ctype == "pfc" else None)  # fmt: skip

    cell_row("Q1")
    cell_row("Q2")
    add(code="SEC-1", name="Секція шин 1", kind="section", parent="Q1", section=1)
    add(code="SEC-2", name="Секція шин 2", kind="section", parent="Q2", section=2)
    for c in energy.SWB_CELLS:
        if c[3] != "incomer":
            cell_row(c[0])
    for b in energy.BUSWAYS:
        section[b["code"]] = section[b["feeder"]]
        add(code=b["code"], name=b["name"], kind="line", line_kind="busway", parent=b["feeder"], equipment=b["code"],
            section=section[b["code"]], rating_a=LINE_RATING[b["code"]])  # fmt: skip
    for lc, (feeder, name) in energy.CABLE_FEEDERS.items():
        section[lc] = section[feeder]
        add(code=lc, name=name, kind="line", line_kind="cable", parent=feeder, section=section[lc],
            rating_a=LINE_RATING[lc])  # fmt: skip
    tap_codes = machine_order + ["GANTRY-1"]
    for code in tap_codes:
        bus = taps[code]["bus"]
        section["TAP-" + code] = section[bus]
        add(code="TAP-" + code, name="Відгалуження: " + cons[code]["name"], kind="tapoff", parent=bus,
            section=section[bus])  # fmt: skip
    line_of_feeder = {f: lc for lc, (f, _) in energy.CABLE_FEEDERS.items()}
    unit = 11
    for code, c in cons.items():
        typ = types.get(code)
        if typ:
            kf, _ = energy.PROFILE.get(typ, (0.5, 0.86))
            idle = energy.IDLE_K.get(typ, energy.IDLE_DEFAULT)
            parent = "TAP-" + code
            role, pool, wc = "direct", None, code
        else:
            kf, idle = round(c["p_now"] / c["p_inst"], 3), None
            parent = "TAP-" + code if code == "GANTRY-1" else line_of_feeder[c["feeder"]]
            wc = None
            pool = POOL_OF.get(code)
            role = "shared" if pool else "overhead"
        sec = section["TAP-" + code] if parent.startswith("TAP-") else section[parent]
        section[code] = sec
        add(code=code, name=c["name"], kind="consumer", parent=parent, section=sec,
            equipment=None if code in NO_EQUIPMENT else code, workcenter=wc, p_inst_kw=c["p_inst"],
            p_inst_source=c["source"], load_factor=kf, idle_factor=idle, cos_phi=c["cos_phi"], alloc_role=role,
            pool=pool, group=c.get("group"), unit=unit, note=c.get("note"))  # fmt: skip
        unit += 1
    add(code="PV-INV", name="Інвертори СЕС", kind="generator", gen_kind="pv_inverters", parent="SEC-2",
        section=2, equipment="PV-INV", p_inst_kw=920)  # fmt: skip
    for k in range(1, 9):
        add(code="PV-INV-%d" % k, name="Інвертор СЕС %d" % k, kind="generator", gen_kind="pv_inverter",
            parent="PV-INV", section=2, equipment="PV-INV", p_inst_kw=115, unit=60 + k)  # fmt: skip
    add(code="PV-ROOF", name="Поле СЕС (дах)", kind="generator", gen_kind="pv_field", parent="PV-INV", section=2,
        equipment="PV-ROOF", p_inst_kw=900)  # fmt: skip
    add(code="CHP", name="КГУ TEDOM Quanto D800", kind="generator", gen_kind="chp", parent="SEC-2", section=2,
        equipment="CHP", p_inst_kw=800, unit=72)  # fmt: skip
    add(code="BESS", name="Накопичувач Huawei LUNA2000", kind="storage", parent="SEC-2", section=2, equipment="BESS",
        p_inst_kw=200, unit=69)  # fmt: skip
    add(code="ATS-1", name="АВР Socomec ATyS p", kind="ats", parent="SWB-1", equipment="ATS-1", unit=71)
    add(code="GENSET", name="Дизель-генератор", kind="generator", gen_kind="genset", parent="ATS-1",
        equipment="GENSET", p_inst_kw=507)  # fmt: skip
    return rows


# --------------------------------------------------------------------------- джерела й лічильники (Додатки D.1, D.2)
def build_sources_meters(nodes):
    by = {n["code"]: n for n in nodes}
    cons = [n for n in nodes if n["kind"] == "consumer"]
    sources, meters = [], []

    def src(unit, code, equipment, desc):
        sources.append(dict(code=code, name=desc, unit=unit, equipment=equipment, host="iot-sim", port=502,
                            timeout_s=3, retries=2, max_block=125, gap_max=8))  # fmt: skip

    cell_list = [("Q1", "Q1", "incomer", "ввід", "energy/cells/Q1"), ("Q2", "Q2", "incomer", "ввід", "energy/cells/Q2")]
    for i, bw in enumerate(("BW-1", "BW-2", "BW-3", "BW-4"), 1):
        cell_list.append(("QF-%d" % i, "QF-%d" % i, "feeder", "фідер", "energy/lines/" + bw))
    cell_list += [("QF-C1", "QF-C1", "feeder", "фідер", "energy/lines/C1"),
                  ("QF-C2", "QF-C2", "feeder", "фідер", "energy/lines/C2")]  # fmt: skip
    for u, (node, _, role, word, base) in enumerate(cell_list, 1):
        scode = "MB-U%02d-PM-%s" % (u, node)
        src(u, scode, node, "PM5560 %s %s" % (word, node))
        rating = by[node]["rating_a"]
        exp = base + "/kwh_export" if role == "incomer" else None
        meters.append(dict(code="PM-" + node, name="PM5560 %s %s" % (word, node), node=node, model="pm5560", role=role,
                           source=scode, p_signal=base + "/p_now", e_import_signal=base + "/kwh_total",
                           e_export_signal=exp, ct_ratio="%d/5" % rating))  # fmt: skip
    for c in cons:
        u = c["unit"]
        scode = "MB-U%02d-PM-%s" % (u, c["code"])
        src(u, scode, c["equipment"], "PM5560 " + c["name"])
        base = "energy/consumers/" + c["code"]
        meters.append(dict(code="PM-" + c["code"], name="PM5560 " + c["name"], node=c["code"], model="pm5560",
                           role="consumer", source=scode, p_signal=base + "/p_now",
                           e_import_signal=base + "/kwh_total", ct_ratio="100/5"))  # fmt: skip
    for k in range(1, 9):
        scode = "MB-U%d-SUN-%d" % (60 + k, k)
        src(60 + k, scode, "PV-INV", "Huawei SUN2000 PV-INV-%d" % k)
        base = "infra/pv/PV-INV-%d" % k
        meters.append(dict(code="SUN-%d" % k, name="Huawei SUN2000 PV-INV-%d" % k, node="PV-INV-%d" % k,
                           model="sun2000", role="generation", source=scode, p_signal=base + "/p_kw",
                           e_import_signal=base + "/kwh_total"))  # fmt: skip
    src(69, "MB-U69-BESS", "BESS", "Huawei LUNA2000")
    meters.append(dict(code="LUNA-1", name="Huawei LUNA2000", node="BESS", model="luna2000", role="storage",
                       source="MB-U69-BESS", p_signal="infra/totals/bess_kw",
                       e_import_signal="infra/bess/kwh_charge_total",
                       e_export_signal="infra/bess/kwh_discharge_total"))  # fmt: skip
    src(71, "MB-U71-ATS-1", "ATS-1", "Socomec ATyS p")
    src(72, "MB-U72-CHP", "CHP", "TEDOM Quanto D800")
    meters.append(dict(code="TEDOM-1", name="TEDOM Quanto D800", node="CHP", model="tedom", role="generation",
                       source="MB-U72-CHP", p_signal="infra/totals/chp_kw", e_import_signal="infra/chp/kwh_total"))  # fmt: skip
    return sources, meters


# --------------------------------------------------------------------------- сигнали (Додаток C)
T_I = "{equipment}: струм {value} А при номіналі {threshold} А"
T_S = "Перевантаження трансформатора {code}: {value} кВА при номіналі {threshold}"
T_TEMP = "Перегрів трансформатора {code}: {value} °C при нормі до {threshold}"
T_COS = "Низький cos φ на вводах: {value} при нормі від {threshold}"
T_UNBAL = "Асиметрія струмів {code}: {value} % при нормі до {threshold}"
T_IMB = "Небаланс обліку {code}: {value} % при допуску {threshold}"
T_GRID = "Перевищення договірної потужності: {value} кВт при ліміті {threshold} кВт"
T_TRIP = "{equipment}: автомат вимкнувся аварійно"
T_PV = "Інвертор СЕС {equipment}: аварійна зупинка ({text})"
T_FAULT = "{equipment}: аварія ({text})"
T_HOURS = "КГУ: {value} мотогодин — капремонт при {threshold}"
T_FAIL = "АВР: генератор не запустився (FAIL START)"
KWH, KW = "кВт·год", "кВт"


def build_signals(nodes):
    by = {n["code"]: n for n in nodes}
    cons = [n for n in nodes if n["kind"] == "consumer"]
    rows = []

    def sig(code, name, quantity, kind, unit, equipment, source, address, period, dec, origin, viewer, **kw):
        r = dict(code=code, name=name, quantity=quantity, kind=kind, unit=unit, equipment=equipment, source=source,
                 address=address, period_s=period[0], store_period_s=period[1], decimals=dec,
                 viewer_visible=1 if viewer else 0, origin=origin, binding="full")  # fmt: skip
        r.update(kw)
        rows.append(r)

    def state(mapname, r):
        m, states, alarm = MAPS[mapname]
        r["states"] = states
        r["alarm_states"] = alarm or None
        return r

    sim_equipment_free = ("OFFICE", "LP-1", "LP-2", "LP-3", "RV-ALL", "AHU-1", "EF-ELEC", "EF-CMP", "EF-CHG")
    for c in cons:
        code, nm = c["code"], c["name"]
        sc = "MB-U%02d-PM-%s" % (c["unit"], code)
        base = "energy/consumers/" + code
        o = "module" if code in sim_equipment_free else "sim_data"
        sig(base + "/p_now", nm + ": потужність", "Потужність", "gauge", KW, c["equipment"], sc, _pm("p"), (10, 300), 2,
            o, True)  # fmt: skip
        sig(base + "/kwh_total", nm + ": лічильник енергії", "Енергія", "counter", KWH, c["equipment"], sc,
            _pm("e_imp"), (60, 60), 3, "module", False)  # fmt: skip
        sig(base + "/kwh_shift", nm + ": енергія за зміну", "Енергія", "counter", KWH, c["equipment"], DERIVED, None,
            (300, 300), 2, o, True, derived_from=base + "/kwh_total")  # fmt: skip

    def cell_block(code, node, tcode=None):
        n = by[node]
        sc = "MB-U%02d-PM-%s" % ({"Q1": 1, "Q2": 2}[node], node)
        base = "energy/cells/" + code
        nm = n["name"]
        rating = n["rating_a"]
        sig(base + "/p_now", nm + ": потужність", "Потужність", "gauge", KW, node, sc, _pm("p"), (10, 300), 2,
            "catalog", True)  # fmt: skip
        sig(base + "/i_now", nm + ": струм", "Струм", "gauge", "А", node, sc, _pm("i_now"), (10, 300), 0, "catalog",
            True, warn_high=round(rating * 0.9), alarm_high=rating, alarm_title=T_I, hysteresis=5,
            min_duration_s=60)  # fmt: skip
        for ph in "abc":
            sig("%s/i_%s" % (base, ph), "%s: струм фази %s" % (nm, ph.upper()), "Струм", "gauge", "А", node, sc,
                _pm("i_" + ph), (30, 300), 0, "module", False)  # fmt: skip
        sig(base + "/q_kvar", nm + ": реактивна потужність", "Реактивна потужність", "gauge", "квар", node, sc,
            _pm("q"), (10, 300), 1, "module", False)  # fmt: skip
        sig(base + "/kwh_total", nm + ": лічильник енергії", "Енергія", "counter", KWH, node, sc, _pm("e_imp"),
            (60, 60), 3, "module", False)  # fmt: skip
        sig(base + "/kwh_export", nm + ": віддано в мережу", "Енергія", "counter", KWH, node, sc, _pm("e_exp"),
            (60, 60), 3, "module", False)  # fmt: skip
        sig(base + "/state", nm + ": стан автомата", "Стан", "state", None, node, sc, _pm("state", "breaker"),
            (10, 300), 0, "module", False, alarm_title=T_TRIP, min_duration_s=0)  # fmt: skip
        state("breaker", rows[-1])
        tb = "energy/transformers/" + tcode
        tn = by[tcode]["name"]
        sig(tb + "/p_kw", tn + ": потужність", "Потужність", "gauge", KW, tcode, sc, _pm("p"), (10, 300), 2,
            "sim_data", True)  # fmt: skip
        sig(tb + "/i_a", tn + ": струм", "Струм", "gauge", "А", tcode, sc, _pm("i_now"), (10, 300), 0, "catalog",
            True)  # fmt: skip
        sig(tb + "/cos_phi", tn + ": cos φ", "cos φ", "gauge", None, tcode, sc, _pm("cos"), (10, 300), 2, "catalog",
            True)  # fmt: skip
        sig(tb + "/s_kva", tn + ": повна потужність", "Повна потужність", "gauge", "кВА", tcode, sc, _pm("s"),
            (10, 300), 0, "catalog", True, warn_high=900, alarm_high=1000, alarm_title=T_S, hysteresis=10,
            min_duration_s=60)  # fmt: skip
        k = 0 if tcode == "T1" else 3
        sig(tb + "/temp_c", tn + ": температура", "Температура", "gauge", "°C", tcode, RTD_SOURCE,
            {**RTD, "addr": k, "doc": "HR 4000%d–4000%d RTD%d–%d, макс." % (k + 1, k + 3, k, k + 2)}, (30, 300), 1,
            "sim_data", True, warn_high=130, alarm_high=140, alarm_title=T_TEMP, hysteresis=2, min_duration_s=60,
            binding="thresholds")  # fmt: skip
        sig(base + "/imbalance_pct", nm + ": небаланс обліку", "Небаланс", "gauge", "%", node, DERIVED, None,
            (3600, 0), 2, "module", False, warn_high=3, alarm_high=5, alarm_title=T_IMB, hysteresis=0,
            min_duration_s=3600)  # fmt: skip
        sig(base + "/i_unbal_pct", nm + ": асиметрія струмів", "Асиметрія", "gauge", "%", node, DERIVED, None,
            (300, 300), 2, "module", False, warn_high=10, alarm_high=20, alarm_title=T_UNBAL, hysteresis=1,
            min_duration_s=900)  # fmt: skip

    cell_block("Q1", "Q1", "T1")
    cell_block("Q2", "Q2", "T2")

    def line_block(line, cell, unit):
        n = by[line]
        sc = "MB-U%02d-PM-%s" % (unit, cell)
        base = "energy/lines/" + line
        nm = n["name"]
        rating = n["rating_a"]
        sig(base + "/p_now", nm + ": потужність", "Потужність", "gauge", KW, cell, sc, _pm("p"), (10, 300), 2,
            "catalog", True)  # fmt: skip
        sig(base + "/i_now", nm + ": струм", "Струм", "gauge", "А", cell, sc, _pm("i_now"), (10, 300), 0, "catalog",
            True, warn_high=round(rating * 0.9), alarm_high=rating, alarm_title=T_I, hysteresis=5,
            min_duration_s=60)  # fmt: skip
        sig(base + "/cos_phi", nm + ": cos φ", "cos φ", "gauge", None, cell, sc, _pm("cos"), (10, 300), 2, "catalog",
            True, warn_low=0.85, hysteresis=0.01, min_duration_s=900)  # fmt: skip
        for ph in "abc":
            sig("%s/i_%s" % (base, ph), "%s: струм фази %s" % (nm, ph.upper()), "Струм", "gauge", "А", cell, sc,
                _pm("i_" + ph), (30, 300), 0, "module", False)  # fmt: skip
        sig(base + "/kwh_total", nm + ": лічильник енергії", "Енергія", "counter", KWH, cell, sc, _pm("e_imp"),
            (60, 60), 3, "module", False)  # fmt: skip
        sig(base + "/state", nm + ": стан автомата", "Стан", "state", None, cell, sc, _pm("state", "breaker"),
            (10, 300), 0, "module", False, alarm_title=T_TRIP, min_duration_s=0)  # fmt: skip
        state("breaker", rows[-1])
        sig(base + "/imbalance_pct", nm + ": небаланс обліку", "Небаланс", "gauge", "%", cell, DERIVED, None,
            (3600, 0), 2, "module", False, warn_high=3, alarm_high=5, alarm_title=T_IMB, hysteresis=0,
            min_duration_s=3600)  # fmt: skip
        sig(base + "/i_unbal_pct", nm + ": асиметрія струмів", "Асиметрія", "gauge", "%", cell, DERIVED, None,
            (300, 300), 2, "module", False, warn_high=10, alarm_high=20, alarm_title=T_UNBAL, hysteresis=1,
            min_duration_s=900)  # fmt: skip

    for i, bw in enumerate(("BW-1", "BW-2", "BW-3", "BW-4"), 1):
        line_block(bw, "QF-%d" % i, 2 + i)
    line_block("C1", "QF-C1", 7)
    line_block("C2", "QF-C2", 8)

    sun = "Huawei SUN2000"
    for k in range(1, 9):
        base = "infra/pv/PV-INV-%d" % k
        sc = "MB-U%d-SUN-%d" % (60 + k, k)
        nm = "СЕС PV-INV-%d" % k
        sig(base + "/p_kw", nm + ": потужність", "Потужність", "gauge", KW, "PV-INV", sc,
            _reg(sun, 32080, "i32", 32080, "Active power", 0.001), (10, 300), 2, "catalog", True)  # fmt: skip
        sig(base + "/status", nm + ": стан", "Стан", "state", None, "PV-INV", sc,
            _reg(sun, 32089, "u16", 32089, "Device status", None, "pv_status"), (30, 300), 0, "catalog", True,
            alarm_title=T_PV, min_duration_s=60)  # fmt: skip
        state("pv_status", rows[-1])
        sig(base + "/kwh_today", nm + ": за добу", "Енергія", "gauge", KWH, "PV-INV", sc,
            _reg(sun, 32114, "u32", 32114, "Daily energy yield", 0.01), (60, 300), 2, "catalog", True)  # fmt: skip
        sig(base + "/kwh_total", nm + ": накопичено", "Енергія", "counter", KWH, "PV-INV", sc,
            _reg(sun, 32106, "u32", 32106, "Accumulated energy yield", 0.01), (60, 300), 3, "module", False)  # fmt: skip

    lu = "Huawei LUNA2000"
    bs = "MB-U69-BESS"
    sig("infra/totals/bess_soc", "Накопичувач: заряд (SOC)", "Заряд", "gauge", "%", "BESS", bs,
        _reg(lu, 37004, "u16", 37004, "SOC", 0.1), (30, 300), 2, "sim_data", True)  # fmt: skip
    sig("infra/totals/bess_kw", "Накопичувач: потужність", "Потужність", "gauge", KW, "BESS", bs,
        _reg(lu, 37001, "i32", 37001, "Charge/discharge power", 0.001), (10, 300), 2, "catalog", True)  # fmt: skip
    sig("infra/bess/state", "Накопичувач: стан", "Стан", "state", None, "BESS", bs,
        _reg(lu, 37000, "u16", 37000, "Running status", None, "bess_state"), (10, 300), 0, "catalog", True,
        alarm_title=T_FAULT, min_duration_s=30)  # fmt: skip
    state("bess_state", rows[-1])
    sig("infra/bess/kwh_charge_total", "Накопичувач: заряджено всього", "Енергія", "counter", KWH, "BESS", bs,
        _reg(lu, 37014, "u32", 37014, "Total charge", 0.01), (60, 300), 3, "module", False)  # fmt: skip
    sig("infra/bess/kwh_discharge_total", "Накопичувач: розряджено всього", "Енергія", "counter", KWH, "BESS", bs,
        _reg(lu, 37016, "u32", 37016, "Total discharge", 0.01), (60, 300), 3, "module", False)  # fmt: skip

    te = "TEDOM"
    cs = "MB-U72-CHP"
    sig("infra/totals/chp_kw", "КГУ: потужність", "Потужність", "gauge", KW, "CHP", cs,
        _reg(te, 40001, "u16", 40001, "Electric power"), (10, 300), 2, "sim_data", True)  # fmt: skip
    sig("infra/chp/heat_kw", "КГУ: теплова потужність", "Потужність", "gauge", KW, "CHP", cs,
        _reg(te, 40002, "u16", 40002, "Heat power"), (30, 300), 2, "catalog", True)  # fmt: skip
    sig("infra/chp/gas_m3h", "КГУ: витрата газу", "Витрата", "gauge", "м³/год", "CHP", cs,
        _reg(te, 40003, "u16", 40003, "Gas flow", 0.1), (30, 300), 1, "catalog", True)  # fmt: skip
    sig("infra/chp/state", "КГУ: стан", "Стан", "state", None, "CHP", cs,
        _reg(te, 40000, "u16", 40000, "State", None, "chp_state"), (10, 300), 0, "catalog", True,
        alarm_title=T_FAULT, min_duration_s=30)  # fmt: skip
    state("chp_state", rows[-1])
    sig("infra/chp/hours", "КГУ: мотогодини", "Напрацювання", "counter", "год", "CHP", cs,
        _reg(te, 40010, "u32", 40010, "Running hours"), (300, 300), 0, "catalog", True, warn_high=76000,
        alarm_high=80000, alarm_title=T_HOURS, hysteresis=0, min_duration_s=0)  # fmt: skip
    sig("infra/chp/kwh_total", "КГУ: вироблено всього", "Енергія", "counter", KWH, "CHP", cs,
        _reg(te, 40014, "u32", 40014, "Total energy"), (60, 300), 3, "module", False)  # fmt: skip

    so = "Socomec ATyS p"
    ac = "MB-U71-ATS-1"
    ats = [
        ("mode", "режим", 20482, "ats_mode", (10, 300), "module", False),
        ("position", "положення", 20483, "ats_position", (5, 300), "catalog", True),
        ("gen_start", "пуск генератора", 20484, "onoff", (5, 300), "module", False),
        ("src1_state", "джерело 1", 20486, "ats_source", (5, 300), "module", False),
        ("src2_state", "джерело 2", 20487, "ats_source", (5, 300), "module", False),
    ]
    for key, title, reg, mp, per, org, v in ats:
        sig("infra/ats/" + key, "АВР: " + title, "Стан", "state", None, "ATS-1", ac,
            _reg(so, reg, "u16", reg, key, None, mp), per, 0, org, v)  # fmt: skip
        state(mp, rows[-1])
    for k in (1, 2):
        sig("infra/ats/src%d_ok" % k, "АВР: джерело %d в нормі" % k, "Стан", "gauge", None, "ATS-1", DERIVED, None,
            (10, 300), 0, "catalog", True)  # fmt: skip
    sig("infra/ats/fail_start", "АВР: невдалий пуск генератора", "Стан", "gauge", None, "ATS-1", DERIVED, None,
        (10, 300), 0, "module", False, alarm_high=0.5, alarm_title=T_FAIL, hysteresis=0, min_duration_s=0)  # fmt: skip

    sig("infra/totals/pv_now", "СЕС: потужність", "Потужність", "gauge", KW, "PV-INV", DERIVED, None, (60, 300), 2,
        "sim_data", True)  # fmt: skip
    sig("infra/totals/grid_kw", "Мережа: потужність", "Потужність", "gauge", KW, "SWB-1", DERIVED, None, (60, 300), 2,
        "catalog", True)  # fmt: skip
    sig("infra/totals/export_kw", "Мережа: віддача", "Потужність", "gauge", KW, "SWB-1", DERIVED, None, (60, 300), 2,
        "catalog", True)  # fmt: skip
    sig("energy/totals/p_now", "Завод: споживання", "Потужність", "gauge", KW, "SWB-1", DERIVED, None, (60, 300), 2,
        "module", True)  # fmt: skip
    sig("energy/totals/load15_kw", "Завод: 15-хвилинне навантаження", "Потужність", "gauge", KW, "SWB-1", DERIVED,
        None, (900, 0), 2, "module", False)  # fmt: skip
    sig("energy/totals/grid15_kw", "Завод: 15-хвилинний пік з мережі", "Потужність", "gauge", KW, "SWB-1", DERIVED,
        None, (900, 0), 2, "module", False, alarm_title=T_GRID, hysteresis=0, min_duration_s=0)  # fmt: skip
    sig("energy/totals/cos_phi", "Завод: cos φ на вводах", "cos φ", "gauge", None, "SWB-1", DERIVED, None, (60, 300),
        2, "module", False, warn_low=0.95, alarm_low=0.90, alarm_title=T_COS, hysteresis=0.01,
        min_duration_s=900)  # fmt: skip
    return rows


POOLS = [
    ("POOL-AIR", "Стиснене повітря", 10, "kwh", ""),
    ("POOL-DUST", "Аспірація", 20, "kwh", ""),
    ("POOL-GANTRY", "Подача плит (портал)", 30, "kwh", "SAW-1;SAW-2;SAW-3;NEST-1"),
    ("POOL-LIGHT", "Освітлення цеху", 40, "time", ""),
    ("POOL-HVAC", "Вентиляція", 50, "time", ""),
]


def load_plant(root):
    sys.path.insert(0, os.path.abspath(root))
    from plant import energy, equipment, infra, layout

    return {"energy": energy, "layout": layout, "infra": infra, "specs": equipment.load_specs()}


def generate(root, out_dir):
    plant = load_plant(root)
    nodes = build_nodes(plant)
    sources, meters = build_sources_meters(nodes)
    signals = build_signals(nodes)
    pools = [dict(zip(POOL_COLS, p, strict=True)) for p in POOLS]
    os.makedirs(out_dir, exist_ok=True)
    _write(os.path.join(out_dir, "energy_nodes.csv"), NODE_COLS, nodes)
    _write(os.path.join(out_dir, "energy_sources.csv"), SOURCE_COLS, sources)
    _write(os.path.join(out_dir, "energy_signals.csv"), SIGNAL_COLS, signals)
    _write(os.path.join(out_dir, "energy_meters.csv"), METER_COLS, meters)
    _write(os.path.join(out_dir, "energy_pools.csv"), POOL_COLS, pools)
    return {"nodes": len(nodes), "sources": len(sources), "signals": len(signals), "meters": len(meters),
            "pools": len(pools)}  # fmt: skip


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".", help="корінь репозиторію factory3d (де лежить plant/)")
    ap.add_argument("--out", default=os.path.join(here, "..", "data"), help="каталог виводу")
    args = ap.parse_args(argv)
    print(json.dumps(generate(args.root, os.path.abspath(args.out))))


if __name__ == "__main__":
    main()
