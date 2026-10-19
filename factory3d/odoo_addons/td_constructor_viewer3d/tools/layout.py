"""Розділ `layout` payload переглядача: чим діюча версія конструктора відрізняється від бази (PHASE2_VIEWER).

База (baseline) — версія-імпорт seed (`is_seed`): те, що запечено в GLB «Переглядача». Діюча — остання опублікована.
Порівнюються розміщення (код = `td_code` обладнання) і місця зі стелажами (префікс і коди комірок).
Коди й одиниці — як у конструкторі: метри, градуси проти годинникової стрілки при погляді зверху (Blender X/Y);
переклад у three.js (x, z, −y) робить клієнт.

Формат (bridge SPEC R-01):
`{site, version, base_version, moved, added, hidden, replaced, frames}`.
"""

import json
import logging

from odoo.exceptions import UserError
from odoo.tools import file_open

from odoo.addons.td_constructor.services import cells as cells_svc
from odoo.addons.td_constructor.services import geometry, snapshot

_logger = logging.getLogger(__name__)

MODELS = ("td.site", "td.layout.version", "td.slot", "td.placement", "td.equipment.variant")
CELL_TEMPLATES = ("pallet_rack", "cantilever", "shelf", "floor_stack")
MODEL_URL = "/f3d/constructor/model/%d/glb"
EPS = 1e-6
INVENTORY_PATH = "td_constructor/data/scene_inventory.json"


def _r(value):
    return round(float(value), 4)


def _norm_deg(value):
    """Різниця кутів у (−180, 180]."""
    value = (float(value) + 180.0) % 360.0 - 180.0
    return 180.0 if value == -180.0 else value


def load_inventory():
    """Опис запечених у GLB об'єктів `{код: {x, y, z, L, W, H, yaw}}` (координати заводу, м, °) або {} — файла ще немає.

    Файл `scene_inventory.json` кладе конструктор (повніший seed); поза ним база — знімок версії-імпорту.
    Допускається обгортка `{"objects": {…}}`."""
    try:
        with file_open(INVENTORY_PATH, "rb") as fh:
            data = json.load(fh)
    except (FileNotFoundError, OSError, ValueError):
        return {}
    if isinstance(data, dict) and isinstance(data.get("objects"), dict):
        data = data["objects"]
    return data if isinstance(data, dict) else {}


def pick_versions(env):
    """(площадка, база, діюча) для першої площадки з діючою версією, відмінною від бази; інакше None."""
    Version = env["td.layout.version"]
    for site in env["td.site"].search([("active_version_id", "!=", False)], order="sequence, id"):
        base = Version.search([("site_id", "=", site.id), ("is_seed", "=", True)], order="n", limit=1)
        active = site.active_version_id
        if base and active and active != base:
            return site, base, active
    return None


def _load(version):
    try:
        return snapshot.load_snapshot(version.sudo())
    except (UserError, ValueError):
        _logger.warning("layout: немає знімка версії %s", version.display_name)
        return None


def _live(snap):
    """(розміщення за кодом, місця за префіксом, висоти шарів за uid) лише з діючих записів знімка."""
    layers = {layer["uid"]: layer for layer in snap.get("layers", [])}
    elev = {uid: float(layer.get("elevation_m") or 0.0) for uid, layer in layers.items()}

    def alive(item):
        layer = layers.get(item.get("layer_uid"))
        return item.get("active", True) and layer is not None and layer.get("active", True)

    placements = {p["code"]: p for p in snap.get("placements", []) if alive(p)}
    slots = {s["code_prefix"]: s for s in snap.get("slots", []) if alive(s)}
    return placements, slots, elev


def _variants(env, snaps):
    ids = {p.get("variant_id") for snap in snaps for p in snap.get("placements", []) if p.get("variant_id")}
    out = {}
    for variant in env["td.equipment.variant"].with_context(active_test=False).browse(sorted(ids)).exists():
        geom = variant._td_local_geometry()
        out[variant.id] = {
            "geom": geom,
            "category": variant.category or "other",
            "model": bool(variant.model_status == "ok" and variant.model_glb_id),
        }
    return out


def _slot_cells(slot, x, y, rot, elevation):
    return cells_svc.generate_cells(
        slot["template"],
        slot["code_prefix"],
        x,
        y,
        rot,
        slot.get("params") or {},
        slot.get("overrides") or {},
        elevation,
    )


def _slot_sig(slot):
    """Ознака «параметри шаблону не змінились»: нормалізовані параметри й перевизначення."""
    template = slot["template"]
    return (
        template,
        sorted(cells_svc.normalize_params(template, slot.get("params") or {}).items()),
        sorted(cells_svc.normalize_overrides(slot.get("overrides") or {}).items()),
    )


def _placement_entry(p, variant, elev, obb):
    dims = variant["geom"]
    return {
        "code": p["code"],
        "kind": "placement",
        "name": p.get("name") or p["code"],
        "category": variant["category"],
        "dims": {"L": _r(dims["length"] / 1000.0), "W": _r(dims["width"] / 1000.0), "H": _r(dims["height"] / 1000.0)},
        "x": _r(obb["cx"]),
        "y": _r(obb["cy"]),
        "rot": _r(p.get("rotation") or 0.0),
        "elev": _r(elev),
        "front": dims.get("front_side") or "s",
        "variant_id": dims["id"],
        "model_url": MODEL_URL % dims["id"] if variant["model"] else None,
        "template": None,
        "params": None,
        "cells": [],
    }


def _slot_entry(slot, elev):
    template, prefix = slot["template"], slot["code_prefix"]
    params = cells_svc.normalize_params(template, slot.get("params") or {})
    cells = _slot_cells(slot, 0.0, 0.0, 0.0, 0.0)
    length, width = cells_svc.footprint(template, params)
    return {
        "code": prefix,
        "kind": "slot",
        "name": prefix,
        "category": "rack",
        "dims": {
            "L": _r(length),
            "W": _r(width),
            "H": _r(max((c["z0"] + c["h"] for c in cells), default=0.0)),
        },
        "x": _r(slot["x_m"]),
        "y": _r(slot["y_m"]),
        "rot": _r(slot.get("rotation") or 0),
        "elev": _r(elev),
        "model_url": None,
        "template": template,
        "params": params,
        "cells": [
            {
                "code": c["code"],
                "lx": _r(c["x"]),
                "ly": _r(c["y"]),
                "lz": _r(c["z0"]),
                "w": _r(c["l"]),
                "d": _r(c["w"]),
                "h": _r(c["h"]),
                "kind": c["kind"],
            }
            for c in cells
        ],
    }


def _frame_hint(slot, elev):
    template = slot["template"]
    length, width = cells_svc.footprint(template, slot.get("params") or {})
    return {
        "x": _r(slot["x_m"]),
        "y": _r(slot["y_m"]),
        "rot": _r(slot.get("rotation") or 0),
        "L": _r(length),
        "W": _r(width),
        "template": template,
    }


def _base_pose(code, pb, inventory):
    """Положення розміщення в базі: з опису сцени (запечене в GLB), інакше зі знімка версії-імпорту."""
    inv = inventory.get(code) or {}
    if "x" in inv and "y" in inv:
        return float(inv["x"]), float(inv["y"]), float(inv.get("yaw", pb.get("rotation") or 0.0))
    return pb["x_m"], pb["y_m"], pb.get("rotation") or 0.0


def diff(snap_base, snap_active, variants, inventory=None):
    """Чиста функція: різниця двох знімків → {moved, added, hidden, replaced, frames} (без ORM, крім `variants`).

    `inventory` — опис сцени `{код: {x, y, yaw, …}}`: коли код у ньому є, база розміщення — з нього."""
    inventory = inventory or {}
    pl_b, sl_b, el_b = _live(snap_base)
    pl_a, sl_a, el_a = _live(snap_active)
    layer_of_b = {p["code"]: p["layer_uid"] for p in snap_base.get("placements", [])}
    layer_of_a = {p["code"]: p["layer_uid"] for p in snap_active.get("placements", [])}
    moved, added, hidden, replaced, frames = {}, [], [], [], {}

    # --- розміщення обладнання -------------------------------------------------------------------
    for code, pb in sorted(pl_b.items()):
        pa = pl_a.get(code)
        if pa is None:
            hidden.append(code)
            continue
        vb, va = variants.get(pb.get("variant_id")), variants.get(pa.get("variant_id"))
        if va is None:
            continue
        elev_a = el_a.get(layer_of_a.get(code), 0.0)
        obb_a = geometry.placement_obb(va["geom"], pa["x_m"], pa["y_m"], pa.get("rotation") or 0.0)
        if pa.get("variant_id") != pb.get("variant_id") or vb is None:
            replaced.append(code)
            added.append(_placement_entry(pa, va, elev_a, obb_a))
            continue
        bx, by, brot = _base_pose(code, pb, inventory)
        obb_b = geometry.placement_obb(vb["geom"], bx, by, brot)
        shift = {
            "dx": obb_a["cx"] - obb_b["cx"],
            "dy": obb_a["cy"] - obb_b["cy"],
            "drot": _norm_deg((pa.get("rotation") or 0.0) - brot),
            "delev": elev_a - el_b.get(layer_of_b.get(code), 0.0),
        }
        if any(abs(v) > EPS for v in shift.values()):
            moved[code] = {k: _r(v) for k, v in shift.items()}
    for code, pa in sorted(pl_a.items()):
        if code in pl_b:
            continue
        va = variants.get(pa.get("variant_id"))
        if va is None:
            continue
        obb_a = geometry.placement_obb(va["geom"], pa["x_m"], pa["y_m"], pa.get("rotation") or 0.0)
        added.append(_placement_entry(pa, va, el_a.get(layer_of_a.get(code), 0.0), obb_a))

    # --- місця з комірками (стелажі) --------------------------------------------------------------
    layer_sl_b = {s["code_prefix"]: s["layer_uid"] for s in snap_base.get("slots", [])}
    layer_sl_a = {s["code_prefix"]: s["layer_uid"] for s in snap_active.get("slots", [])}
    for prefix, sb in sorted(sl_b.items()):
        if sb["template"] not in CELL_TEMPLATES:
            continue
        sa = sl_a.get(prefix)
        elev_b = el_b.get(layer_sl_b.get(prefix), 0.0)
        try:
            cells_b = _slot_cells(sb, sb["x_m"], sb["y_m"], sb.get("rotation") or 0, elev_b)
            same = sa is not None and sa["template"] in CELL_TEMPLATES and _slot_sig(sa) == _slot_sig(sb)
        except cells_svc.CellsError:
            _logger.warning("layout: некоректне місце %s у базі", prefix)
            continue
        if sa is None or sa["template"] not in CELL_TEMPLATES:
            hidden.extend(c["code"] for c in cells_b)
            frames[prefix] = _frame_hint(sb, elev_b)
            hidden.append(prefix)
            continue
        elev_a = el_a.get(layer_sl_a.get(prefix), 0.0)
        if not same:
            replaced.append(prefix)
            hidden.extend(c["code"] for c in cells_b)
            frames[prefix] = _frame_hint(sb, elev_b)
            added.append(_slot_entry(sa, elev_a))
            continue
        cells_a = {c["code"]: c for c in _slot_cells(sa, sa["x_m"], sa["y_m"], sa.get("rotation") or 0, elev_a)}
        drot = _norm_deg((sa.get("rotation") or 0) - (sb.get("rotation") or 0))
        delev = elev_a - elev_b
        centre = {
            "dx": sa["x_m"] - sb["x_m"],
            "dy": sa["y_m"] - sb["y_m"],
            "drot": drot,
            "delev": delev,
        }
        if any(abs(v) > EPS for v in centre.values()):
            moved[prefix] = {k: _r(v) for k, v in centre.items()}
            frames[prefix] = _frame_hint(sb, elev_b)
            for cb in cells_b:
                ca = cells_a.get(cb["code"])
                if ca is not None:
                    moved[cb["code"]] = {
                        "dx": _r(ca["x"] - cb["x"]),
                        "dy": _r(ca["y"] - cb["y"]),
                        "drot": _r(drot),
                        "delev": _r(delev),
                    }
    for prefix, sa in sorted(sl_a.items()):
        if prefix in sl_b or sa["template"] not in CELL_TEMPLATES:
            continue
        try:
            added.append(_slot_entry(sa, el_a.get(layer_sl_a.get(prefix), 0.0)))
        except cells_svc.CellsError:
            _logger.warning("layout: некоректне нове місце %s", prefix)
    return {
        "moved": moved,
        "added": added,
        "hidden": sorted(set(hidden)),
        "replaced": sorted(set(replaced)),
        "frames": frames,
    }


def build_layout(env):
    """Розділ `layout` для користувача `env`; None — немає опублікованої версії, відмінної від бази, або немає прав."""
    if any(model not in env or not env[model].has_access("read") for model in MODELS):
        return None
    picked = pick_versions(env)
    if not picked:
        return None
    site, base, active = picked
    snap_base, snap_active = _load(base), _load(active)
    if snap_base is None or snap_active is None:
        return None
    result = diff(snap_base, snap_active, _variants(env, (snap_base, snap_active)), load_inventory())
    return {
        "site": {"id": site.id, "code": site.code, "name": site.name},
        "version": {"id": active.id, "n": active.n, "published_at": str(active.published_at or "")},
        "base_version": {"id": base.id, "n": base.n},
        **result,
    }
