#!/usr/bin/env python3
"""Генерує catalog/devices.yaml, catalog/zones.json, catalog/passports.json (SPEC §5.2, §5.3 крок 2).

  python tools/gen_devices.py          # згенерувати три файли
  python tools/gen_devices.py --check  # звірити (код виходу 0/1)

Джерела: ``dist/odoo_demo.json`` (паспорти, обладнання, зони), ``plant/equipment_specs.json`` (ролі),
``plant/layout.py`` (полігони зон), ``plant/fire.py`` (сповіщувачі), ``catalog/signals.csv``
(протоколи/unit id). Очікувано: 210 + 5 ACR + TURN-1 + 2 CAM + 8 PV-INV + SWB-CTRL + 49 PM + CUTOPT + GAS-MAIN + AIR-MAIN = 279.
``driver`` пишеться лише для драйверів цього воркера (machine, io_machine, gantry, mobile, facp,
facp_zone, spark, smoke, access, yard); решту визначає ``registry.driver_for``.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve()
SERVICE = HERE.parents[1]
FACTORY3D = HERE.parents[3]
CATALOG = SERVICE / "catalog"
sys.path.insert(0, str(FACTORY3D))

# SPEC §5.2: ролі -> драйвер
P01_ROLES = {"beam_saw", "beam_saw_book", "nesting_cnc", "edgebander_laser", "edgebander", "ptp_cnc",
             "throughfeed_drilling", "dowel_inserting", "sorting_cell", "case_clamp_auto"}
P02_ROLES = {"sliding_table_saw", "vertical_panel_saw", "wide_belt_sander", "membrane_press",
             "glue_spray_booth", "manual_spray_booth", "automatic_spraying", "drying", "uv_line",
             "hinge_insertion", "box_machine", "stretch_wrapper", "shrink_line", "case_clamp_manual"}
# R-16: хв/шт за роллю (маршрути макета)
PER_UNIT = {"beam_saw": 2.2, "sliding_table_saw": 2.2, "vertical_panel_saw": 2.2, "beam_saw_book": 0.9,
            "nesting_cnc": 1.5, "edgebander_laser": 1.6, "edgebander": 1.6, "ptp_cnc": 2.0,
            "throughfeed_drilling": 0.8, "dowel_inserting": 1.0, "sorting_cell": 0.5,
            "case_clamp_auto": 6.0, "case_clamp_manual": 6.0, "box_machine": 3.0,
            "stretch_wrapper": 3.0, "shrink_line": 3.0}
# R-19: маршрути техніки (зони)
MOBILE_ROUTE = {"FL-1": ["Z-POST", "Z-FG"], "FL-2": ["Z-RCV-1", "Z-SHEETS"], "FL-3": ["Z-FG", "Z-OUT-2"],
                "FL-4": ["Z-FG", "Z-OUT-5"], "FL-5": ["Z-PACK", "Z-POST"],
                "TUGGER-1": ["Z-HW", "Z-PRE", "Z-ASM"], "FL-C1": ["Z-CHG"], "FL-C2": ["Z-CHG"]}
GATES = {"GATE-W": {"di_open": 0, "di_loop": 1, "di_photo": 4, "do_open": 0, "do_close": 2, "do_hold": 4},
         "GATE-E": {"di_open": 2, "di_loop": 3, "di_photo": 5, "do_open": 1, "do_close": 3, "do_hold": 5}}
ACR = ["ACR-IN", "ACR-ELEC", "ACR-CHG", "ACR-PAINT", "ACR-SRV"]


def load_inputs() -> tuple[dict, list[dict], list[dict]]:
    demo = json.loads((FACTORY3D / "dist/odoo_demo.json").read_text(encoding="utf-8"))
    specs = json.loads((FACTORY3D / "plant/equipment_specs.json").read_text(encoding="utf-8"))
    with (CATALOG / "signals.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return demo, specs, rows


def _modbus(addr: str) -> tuple[int, int, int] | None:
    m = re.search(r"u(\d+) fc(\d+) pdu(\d+)", addr)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def build_devices(demo: dict, rows: list[dict]) -> list[dict]:
    from plant import fire as fire_mod

    pas, cons = demo["passports"], demo["energy"]["consumers"]
    wcs, equip = demo["workcenters"], demo["equipment"]
    zone_of = {w: z for z, v in demo["zones"].items() for w in v.get("workcenters", [])}
    by_dev: dict[str, list[dict]] = {}
    for r in rows:
        by_dev.setdefault(r["device"], []).append(r)

    def protocols(code: str) -> list[str]:
        out: list[str] = []
        for r in by_dev.get(code, []):
            if r["protocol"] != "—" and r["protocol"] not in out:
                out.append(r["protocol"])
        return out

    def unit(code: str) -> int | None:
        for r in by_dev.get(code, []):
            m = _modbus(r["address"]) if r["protocol"] != "—" else None
            if m:
                return m[0]
        return None

    def sig_addr(code: str, suffix: str) -> tuple[int, int, int] | None:
        for r in by_dev.get(code, []):
            if r["code"].endswith(suffix):
                return _modbus(r["address"])
        return None

    # FA-зони: LSZ 1…35 у порядку fire.groups, адреси LSP за fire R-23
    groups = list(demo["fire"]["groups"])
    lsz = {g: i + 1 for i, g in enumerate(groups)}
    dets = fire_mod.detectors()
    det_addr: dict[str, list[str]] = {}
    for z, d in dets.items():
        g = "FA-" + z[2:]
        det_addr[g] = [f"{fire_mod.loop_of(x)}.{g[3:]}.{n:02d}"
                       for n, (x, *_) in enumerate(d["points"], 1)]

    def seq(pts: list, tag: str) -> list[str]:
        cnt: dict[int, int] = {}
        out = []
        for x, *_ in pts:
            lp = fire_mod.loop_of(x)
            cnt[lp] = cnt.get(lp, 0) + 1
            out.append(f"{lp}.{tag}.{cnt[lp]:02d}")
        return out

    facp_params = {"detectors": sum(len(v) for v in det_addr.values()),
                   "mcp": seq(fire_mod.call_points(), "MCP"), "sounders": seq(fire_mod.sounders(), "SND"),
                   "flame": [f"2.FLM.{i:02d}" for i in range(1, len(fire_mod.FLAME) + 1)],
                   "loops": [1, 2, 3, 4]}

    base = list(pas) + [c for c in ("CHARGING", "SPRINKLERS", "AIR-RING") if c not in pas]
    devs: list[dict] = []
    for code in base:
        role = pas[code]["role"] if code in pas else "equipment"
        name = (wcs.get(code, {}).get("name") or cons.get(code, {}).get("name")
                or equip.get(code, {}).get("name") or pas.get(code, {}).get("model") or code)
        d: dict = {"code": code, "name": name, "role": role}
        prot = protocols(code)
        if prot:
            d["protocols"] = prot
        u = unit(code)
        if u is not None:
            d["unit_id"] = u
        params: dict = {}
        if code in wcs and role in P01_ROLES | P02_ROLES:
            d["driver"] = "machine" if role in P01_ROLES else "io_machine"
            params = {"zone": zone_of.get(code), "per_unit": PER_UNIT.get(role, 1.5),
                      "p_inst": cons.get(code, {}).get("p_inst")}
            if d["driver"] == "machine":
                params["address"] = f"ns=2;s={code}"
            else:
                run, flt, cnt = (sig_addr(code, "/state"), sig_addr(code, "/alarm"),
                                 sig_addr(code, "/pieces_out"))
                if run and flt and cnt:
                    params.update(unit=run[0], di_run=run[2], di_fault=flt[2], counter=cnt[2])
        elif code == "GANTRY-1":
            d["driver"] = "gantry"
            stacks = []
            for sid, loc in demo["locations"].items():
                if sid.startswith("PLT-") and loc.get("quants"):
                    q = loc["quants"][0]
                    stacks.append({"id": sid, "row": int(sid[4:6]), "col": ord(sid[6]) - 64,
                                   "product": q["product"], "lot": q.get("lot"), "qty": int(q["qty"]),
                                   "max": loc.get("capacity", 60), "reserved": int(q.get("reserved", 0))})
            params = {"per_unit": 2.2, "address": "http://iot-sim:8082/api/v1", "aisles": 9, "stacks": stacks}
        elif code in MOBILE_ROUTE:
            d["driver"] = "mobile"
            params = {"route": MOBILE_ROUTE[code], "home": "Z-CHG", "address": f"f3d/mobile/{code}"}
        elif code == "FL-6":
            d["driver"] = "passive"
        elif code == "FACP-1":
            d["driver"] = "facp"
            d["instance"] = "200"
            params = facp_params
        elif code in lsz:
            d["driver"] = "facp_zone"
            d["instance"] = f"LSZ:{lsz[code]}"
            params = {"lsz": lsz[code], "detectors": det_addr.get(code, [])}
            if code == "FA-FAC":  # R-25: PIV:21607 = запиленість 2.FAC.07 (демо: 82 %)
                params.update(dust_detector="2.FAC.07", dust_initial=82)
        elif code == "SPARK-1":
            d["driver"] = "spark"
            params = {"di_spark": 0, "di_ext": 1, "di_fault": 2}
        elif code == "SMOKE-CTRL":
            d["driver"] = "smoke"
            params = {"di_open": 4, "di_fault": 5, "do_open": 0}
        elif code in GATES:
            d["driver"] = "yard"
            params = dict(GATES[code])
        elif code == "TRUCK-SCALE":
            d["driver"] = "yard"
            params = {"address": "iot-sim:4001"}
        elif code in ("ACCESS", "TURNSTILES"):
            d["driver"] = "access"
        elif code in ("PV-ROOF", "SMOKE-VENTS"):
            d["driver"] = "passive"
        if params:
            d["params"] = params
        devs.append(d)
    # похідні пристрої
    for i, c in enumerate(ACR):
        devs.append({"code": c, "name": f"Зчитувач {c}", "driver": "access", "protocols": ["P-10"],
                     "params": {"biostar_device_id": 5390001 + i, "door": i + 1}})
    devs.append({"code": "TURN-1", "name": "Турнікет TURN-1", "driver": "access", "protocols": ["P-10"],
                 "params": {"reader": "ACR-IN"}})
    for i, (c, gate) in enumerate((("CAM-05", "GATE-W"), ("CAM-06", "GATE-E"))):
        devs.append({"code": c, "name": f"Камера LPR {c}", "driver": "yard", "protocols": ["P-11"],
                     "params": {"gate": gate, "direction": "in" if i == 0 else "out"}})
    for k in range(1, 9):
        devs.append({"code": f"PV-INV-{k}", "name": f"Інвертор PV-INV-{k}", "driver": "passive",
                     "protocols": ["P-07"], "unit_id": 60 + k, "params": {"inverter": k}})
    # W1 «Енергетика» (§8.1): контролер ГРЩ — паспорта в odoo_demo.json немає, пристрій похідний; unit/протокол — з каталогу
    devs.append({"code": "SWB-CTRL", "name": "Контролер ГРЩ 0,4 кВ (QS, конденсаторні установки PFC-1/PFC-2; "
                 "карта регістрів — ПРИПУЩЕННЯ A-24)", "role": "switchboard_ctrl", "protocols": protocols("SWB-CTRL"),
                 "unit_id": unit("SWB-CTRL"), "driver": "swb"})
    for code in sorted(cons):
        pm = {"code": f"{code}-PM", "name": f"PM5560 {code}", "driver": "passive", "protocols": ["P-05"],
              "params": {"consumer": code}}
        u = sig_addr(code, "/p_now")
        if u:
            pm["unit_id"] = u[0]
        devs.append(pm)
    devs.append({"code": "CUTOPT", "name": "Оптимізатор розкрою", "driver": "passive", "protocols": [],
                 "params": {"protocol": "none"}})
    # W3 «Енергоресурси» (§8.1): корректор газу і витратомір повітря — паспортів немає, пристрої похідні; unit/протокол — з каталогу
    devs.append({"code": "GAS-MAIN", "name": "Корректор газу GAS-MAIN (u74; карта регістрів — ПРИПУЩЕННЯ Q-02)",
                 "role": "gas_meter", "protocols": protocols("GAS-MAIN"), "unit_id": unit("GAS-MAIN"), "driver": "gas",
                 "params": {"dry_nom": 6.0, "canteen": 1.0}})
    devs.append({"code": "AIR-MAIN", "name": "Витратомір стисненого повітря AIR-MAIN (u75; карта регістрів — ПРИПУЩЕННЯ Q-02)",
                 "role": "air_meter", "protocols": protocols("AIR-MAIN"), "unit_id": unit("AIR-MAIN"), "driver": "air",
                 "params": {"leak": 1.6, "q_ref": 9.8, "load_ref": 66.0, "load_min": 25.0, "drop": 0.1}})
    return devs


def build_zones() -> dict:
    from plant.layout import ZONES

    out = []
    for code, name, (x0, y0, x1, y1), *_ in ZONES:
        out.append({"code": code, "name": name, "polygon": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                    "centroid": [round((x0 + x1) / 2, 2), round((y0 + y1) / 2, 2)]})
    return {"zones": out}


def build_passports(demo: dict) -> dict:
    cons = demo["energy"]["consumers"]
    out = {}
    for code, p in demo["passports"].items():
        e = {k: p.get(k) for k in ("role", "manufacturer", "model", "power_kw", "connected_kw")}
        if code in cons:
            e.update(p_inst=cons[code].get("p_inst"), cos_phi=cons[code].get("cos_phi"),
                     feeder=cons[code].get("feeder"), p_now=cons[code].get("p_now"))
        out[code] = e
    return {"passports": out}


def render() -> dict[str, str]:
    demo, _specs, rows = load_inputs()
    devs = build_devices(demo, rows)
    head = ("# Реєстр пристроїв (генерує tools/gen_devices.py з dist/odoo_demo.json + plant/*; не правити вручну).\n"
            f"# {len(devs)} пристроїв; driver — лише для моделей цього воркера, решту визначає registry.driver_for.\n")
    ydoc = head + yaml.safe_dump({"devices": devs}, allow_unicode=True, sort_keys=False, width=120)
    dump = {"devices.yaml": ydoc,
            "zones.json": json.dumps(build_zones(), ensure_ascii=False, indent=1) + "\n",
            "passports.json": json.dumps(build_passports(demo), ensure_ascii=False, indent=1) + "\n"}
    return dump


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    files = render()
    bad = 0
    for name, text in files.items():
        p = CATALOG / name
        if args.check:
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                print(f"{name}: розходиться з джерелами")
                bad = 1
        else:
            p.write_text(text, encoding="utf-8")
    n = yaml.safe_load(files["devices.yaml"])["devices"]
    print(f"devices={len(n)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
