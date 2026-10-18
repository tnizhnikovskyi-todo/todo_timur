"""Збирання статичних асетів модуля td_viewer3d (SPEC §8.5, Додаток B).

    python3 plant/export_viewer_assets.py odoo_addons/td_viewer3d [--dist dist] [--no-three]

Без Blender. Для бандла three потрібні node/npm (esbuild@0.21.5, three@0.160.0 ставляться в тимчасовий каталог).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

THREE_VERSION = "0.160.0"
ESBUILD_VERSION = "0.21.5"
SCHEMA = "1.1"

ENTRY_JS = """export * as THREE from "three";
export { OrbitControls } from "three/addons/controls/OrbitControls.js";
export { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
export { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
export { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
"""

# Додаток B: ключі, яких немає в model_static.json
DROP_KEYS = ["products", "productions", "workorders", "sale_orders", "purchase_orders", "pickings",
             "quality_checks", "maintenance_requests", "employees", "docks", "sheet_chain", "ship_chain",
             "material_paths", "full_cycle_mo"]
EQUIP_KEEP = ("name", "category", "manufacturer", "model", "boilers", "busy", "total", "last_inspection",
              "leak_check")


def git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def pick(d, keys):
    return {k: d[k] for k in keys if k in d}


def build_layout():
    from plant import layout as L
    zones = {c: dict(name=n, rect=list(r), color=col, desc=desc) for c, n, r, col, desc in L.ZONES}
    for lst in (getattr(L, "DOOR_ZONES_W", []), getattr(L, "DOOR_ZONES_E", [])):
        for item in lst:
            c, n, r, col, desc = item[:5]
            zones.setdefault(c, dict(name=n, rect=list(r), color=col, desc=desc))
    machines = {}
    for m in L.MACHINES:
        code, typ, name, x, y, desc = m[:6]
        e = dict(type=typ, name=name, x=x, y=y, desc=desc)
        for zc, zn, (x0, y0, x1, y1), *_ in L.ZONES:
            if x0 <= x <= x1 and y0 <= y <= y1:
                e["zone"] = zc
                break
        if len(m) > 6:
            e["rot"] = m[6]
        machines[code] = e
    return dict(
        dims=dict(W=L.W, D=L.D, H=L.H), zones=zones, machines=machines,
        doors=[dict(side=s, y=y, w=w) for s, y, w in L.DOORS],
        rcv_goods={str(k): v for k, v in L.RCV_GOODS.items()},
        layers=[dict(key=k, label=lb, group=g) for k, lb, g in L.LAYERS])


def build_static(demo, sha, built_at):
    d = {k: v for k, v in demo.items() if k not in DROP_KEYS}
    d["locations"] = {c: pick(v, ("complete_name", "kind", "capacity")) for c, v in demo["locations"].items()}
    d["workcenters"] = {c: pick(v, ("name", "code", "manufacturer", "model")) for c, v in demo["workcenters"].items()}
    d["equipment"] = {c: pick(v, EQUIP_KEEP) for c, v in demo["equipment"].items()}
    d["zones"] = {c: pick(v, ("name", "odoo_location", "locations", "workcenters")) for c, v in demo["zones"].items()}
    for g in d["fire"].get("groups", {}).values():
        g.pop("maintenance_request", None)
    for u in d["ventilation"].get("units", {}).values():
        u.pop("maintenance_request", None)
    d["energy"]["events"] = []
    d["fire"]["events"] = []
    from plant import cycle_check
    layout = build_layout()
    layout["locations"] = {c: dict(pick(v, ("complete_name", "kind", "capacity")))
                           for c, v in demo["locations"].items()}
    d["layout"] = layout
    d["path_templates"] = {
        "плита": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "QC-PLT-{k}", "{rack}", "{gantry}"],
        "фурнітура": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "QC-1", "SCALE-RCV", "PRN-RCV", "{bin}",
                      "{kit_or_Z-PRE if to startswith ASM}", "TUGGER-1"],
        "крайка": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "{shelf}"],
        "ЛФМ": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "PAINT-STORE"],
        "плівка ПВХ": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "PAINT-STORE"],
        "пакування": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "PACK-STORE", "PAL-1", "{BOX-1 if to != BOX-1}"],
    }
    d["door_goods"] = {str(k): list(v) for k, v in cycle_check.DOOR_GOODS.items()}
    d["meta"] = dict(schema=SCHEMA, built_at=built_at, git=sha,
                     source="plant/odoo_demo.py Demo().build()", live=False)
    return d


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False), encoding="utf-8")


def build_three(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="f3d_three_") as tmp:
        tmp = Path(tmp)
        (tmp / "package.json").write_text(json.dumps({"name": "f3d-three-build", "private": True}))
        subprocess.check_call(["npm", "install", "--no-audit", "--no-fund", "--silent",
                               f"three@{THREE_VERSION}", f"esbuild@{ESBUILD_VERSION}"], cwd=tmp)
        (tmp / "entry.js").write_text(ENTRY_JS)
        subprocess.check_call([str(tmp / "node_modules/.bin/esbuild"), "entry.js", "--bundle", "--format=esm",
                               "--minify", "--sourcemap", f"--outfile={out_dir / 'three-bundle.esm.js'}"], cwd=tmp)
        shutil.copy(tmp / "node_modules/three/LICENSE", out_dir / "LICENSE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("addon")
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--no-three", action="store_true")
    a = ap.parse_args()
    addon = Path(a.addon)
    if not addon.is_absolute():
        addon = Path.cwd() / addon
    dist = Path(a.dist)
    if not dist.is_absolute():
        dist = ROOT / dist
    static = addon / "static"
    sha = git_sha()
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    from plant.odoo_demo import Demo
    demo = Demo().build()
    dump(static / "data/demo_payload.json", demo)
    dump(static / "data/model_static.json", build_static(Demo().build(), sha, built_at))

    parts_out = static / "model/parts"
    parts_out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((dist / "parts/manifest.json").read_text(encoding="utf-8"))
    for p in manifest["parts"]:
        src = dist / "parts" / Path(p["file"]).name
        shutil.copy(src, parts_out / src.name)
        p["hash"] = hashlib.sha1(src.read_bytes()).hexdigest()[:12]
    (parts_out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                                             encoding="utf-8")

    if not a.no_three:
        build_three(static / "lib/three")

    dump(static / "data/BUILD.json", dict(built_at=built_at, git=sha, three=THREE_VERSION, schema=SCHEMA))
    print("OK", addon)


if __name__ == "__main__":
    main()
