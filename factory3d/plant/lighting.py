"""Освітлення: LED-світильники рядами по зонах, кількість — з розрахунку освітленості за нормою
(EN 12464-1 / ДБН В.2.5-28), щити освітлення, аварійні покажчики «Вихід».

Метод коефіцієнта використання: E = N · Φ · UF · MF / A. Для кожної зони беремо норму, рахуємо
потрібну кількість світильників, розставляємо їх сіткою (у стелажних зонах — над проходами)
й оминаємо аспірацію, витяжні труби, установки вентиляції та колони.
"""
import json
import math
import os

from .layout import ZONES
from .ventilation import obstacles as vent_obstacles

UF, MF = 0.7, 0.8  # коефіцієнт використання (високий цех, світлі стіни) і коефіцієнт експлуатації
Z_LIGHT = 7.55  # низ світильника
Z_LIGHT_GANTRY = 8.12  # над мостом портального складу світильники кріпляться впритул до ферм

# Норми освітленості за видом робіт (лк); уточнюються з lux_norms.json, якщо він є
NORMS = {
    "woodworking_machine": 500, "woodworking_bench": 300, "spraying": 750, "storage_racks": 200,
    "storage_floor": 100, "packing_dispatch": 300, "loading_ramps": 150, "switchgear_room": 200,
    "compressor_room": 200, "battery_charging": 150, "corridors_traffic": 150,
}
NORM_NAMES = {
    "woodworking_machine": "верстатна обробка деревини", "woodworking_bench": "збирання, верстакові роботи",
    "spraying": "фарбування, оздоблення", "storage_racks": "стелажні проходи з персоналом",
    "storage_floor": "складування", "packing_dispatch": "пакування й відвантаження",
    "loading_ramps": "рампи завантаження", "switchgear_room": "електрощитова", "compressor_room": "компресорна",
    "battery_charging": "заряджання акумуляторів", "corridors_traffic": "проходи й проїзди",
}

# zone, вид робіт, тип світильника, щит освітлення, рівень зараз (диммування), ряди над проходами
LIGHT_ZONES = [
    ("Z-RCV", "packing_dispatch", "highbay", "LP-1", 1.0, None),
    ("Z-SHEETS", "storage_floor", "highbay", "LP-1", 0.8, None),
    ("Z-HW", "storage_racks", "highbay_rack", "LP-1", 0.7, ("y", [50.1, 54.3, 58.5, 62.7, 66.9])),
    ("Z-EDGE", "storage_racks", "highbay_rack", "LP-1", 0.7, ("x", [32.1])),
    ("Z-PKS", "storage_floor", "highbay", "LP-1", 0.6, None),
    ("Z-CUT", "woodworking_machine", "highbay", "LP-2", 1.0, None),
    ("Z-EB", "woodworking_machine", "highbay", "LP-2", 1.0, None),
    ("Z-CNC", "woodworking_machine", "highbay", "LP-2", 1.0, None),
    ("Z-SORT", "woodworking_bench", "highbay", "LP-2", 1.0, None),
    ("Z-FAC", "spraying", "highbay", "LP-2", 1.0, None),
    ("Z-ASM", "woodworking_bench", "highbay", "LP-3", 1.0, None),
    ("Z-PRE", "storage_racks", "highbay", "LP-3", 0.8, None),
    ("Z-MAINT", "woodworking_bench", "highbay", "LP-3", 1.0, None),
    ("Z-PACK", "packing_dispatch", "highbay", "LP-3", 1.0, None),
    ("Z-POST", "storage_floor", "highbay", "LP-3", 0.8, None),
    ("Z-CMP", "compressor_room", "highbay", "LP-3", 0.5, None),
    ("Z-CHG", "battery_charging", "highbay", "LP-3", 0.5, None),
    ("Z-FG", "storage_racks", "highbay_rack", "LP-3", 0.6, ("x", [125.4, 130.9, 135.4])),
    ("Z-ELEC", "switchgear_room", "highbay", "LP-3", 0.5, None),
    ("Z-OUT", "packing_dispatch", "highbay", "LP-3", 1.0, None),
]
# щити освітлення: code, x на північній стіні, назва
PANELS = [("LP-1", 40.0, "Щит освітлення ЩО-1 · склади сировини, приймання"),
          ("LP-2", 90.6, "Щит освітлення ЩО-2 · лінії й дільниця фасадів"),
          ("LP-3", 135.0, "Щит освітлення ЩО-3 · збирання, пакування, склад ГП, відвантаження")]
DEFAULT_FIX = {"highbay": (24000, 160), "highbay_rack": (19000, 130)}  # лм, Вт — доки немає паспорта

# Що оминати: аспірація (магістраль і гілка на північ), витяжні труби, колони
DUCT_MAIN = (44.0, 82.5, 18.5)  # x0, x1, y
DUCT_NORTH_X = 55.6
STACKS = [(46.0, 60.7), (57.9, 52.0), (70.4, 61.4), (78.3, 62.0)]
GANTRY = (28.4, 44.3, 0.6, 45.0)


NORMS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lux_norms.json")


def load_lux_norms():
    if not os.path.exists(NORMS_PATH):
        return {}
    with open(NORMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def fixture(specs, kind):
    rec = specs.get(kind) or {}
    lm, w = DEFAULT_FIX[kind]
    return (rec.get("lumen") or lm), (rec.get("watt") or w)


def norms(lux_norms=None):
    out = dict(NORMS)
    for k, v in (lux_norms or {}).items():
        if isinstance(v.get("lux"), (int, float)):
            out[k] = v["lux"]
    return out


def _blocked(x, y, in_gantry):
    if DUCT_MAIN[0] < x < DUCT_MAIN[1] and abs(y - DUCT_MAIN[2]) < 0.9:
        return True
    if abs(x - DUCT_NORTH_X) < 0.9 and y > DUCT_MAIN[2]:
        return True
    if any(math.hypot(x - sx, y - sy) < 0.9 for sx, sy in STACKS):
        return True
    if any(math.hypot(x - ox, y - oy) < r + 0.3 for ox, oy, r in vent_obstacles()):
        return True
    if abs(x / 12 - round(x / 12)) * 12 < 0.6 and min(abs(y - c) for c in (15, 30, 45, 60)) < 0.6:
        return True  # колона
    if in_gantry and (min(abs(y - 5 * round(y / 5)), 9) < 0.5 or abs(x - 42.6) < 0.6):
        return True  # спринклери й пневмокільце над мостом
    return False


def _place(x, y, rect, in_gantry):
    """Найближче вільне місце в межах зони."""
    x0, y0, x1, y1 = rect
    for dx, dy in ((0, 0), (0, 1.0), (0, -1.0), (1.0, 0), (-1.0, 0), (0, 1.6), (0, -1.6), (1.6, 0),
                   (-1.6, 0), (1.2, 1.2), (-1.2, -1.2), (1.2, -1.2), (-1.2, 1.2)):
        px, py = x + dx, y + dy
        if x0 + 0.4 < px < x1 - 0.4 and y0 + 0.4 < py < y1 - 0.4 and not _blocked(px, py, in_gantry):
            return px, py
    return None


def layout(specs, lux_norms=None):
    """Групи освітлення по зонах: світильники, розрахункова освітленість, потужність."""
    nm = norms(lux_norms)
    rects = {z[0]: (z[1], z[2]) for z in ZONES}
    groups = {}
    for zone, task, kind, panel, level, aisles in LIGHT_ZONES:
        name, (x0, y0, x1, y1) = rects[zone]
        area = (x1 - x0) * (y1 - y0)
        lm, w = fixture(specs, kind)
        e_norm = nm[task]
        n_req = max(1, math.ceil(e_norm * area / (lm * UF * MF)))
        pts = []
        if aisles:
            axis, lines = aisles
            per = math.ceil(n_req / len(lines))
            span = (y0, y1) if axis == "x" else (x0, x1)
            step = (span[1] - span[0]) / per
            for c in lines:
                for k in range(per):
                    t = span[0] + step * (k + 0.5)
                    pts.append((c, t) if axis == "x" else (t, c))
        else:
            lx, ly = x1 - x0, y1 - y0
            nx = max(1, round(math.sqrt(n_req * lx / ly)))
            ny = max(1, math.ceil(n_req / nx))
            pts = [(x0 + lx * (i + 0.5) / nx, y0 + ly * (j + 0.5) / ny) for i in range(nx) for j in range(ny)]
        placed = []
        for x, y in pts:
            g = GANTRY[0] < x < GANTRY[1] and GANTRY[2] < y < GANTRY[3]
            p = _place(x, y, (x0, y0, x1, y1), g)
            if p and all(math.dist(p, q[:2]) > 1.2 for q in placed):
                placed.append((p[0], p[1], Z_LIGHT_GANTRY if g else Z_LIGHT))
        n = len(placed)
        e_calc = n * lm * UF * MF / area
        groups["LT-" + zone[2:]] = dict(
            zone=zone, zone_name=name, task=task, task_name=NORM_NAMES[task], kind=kind, panel=panel,
            fixtures=placed, n=n, lumen=lm, watt=w, area=round(area), e_norm=e_norm, e_calc=round(e_calc),
            level=level, e_now=round(e_calc * level), p_inst=round(n * w / 1000, 2),
            p_now=round(n * w * level / 1000, 2), control="DALI: присутність і денне світло" if level < 1
            else "DALI: зміна, 100 %")
    return groups


def panels_load(groups):
    out = {}
    for code, _, name in PANELS:
        gs = [g for g in groups.values() if g["panel"] == code]
        out[code] = dict(name=name, groups=[k for k, g in groups.items() if g["panel"] == code],
                         n=sum(g["n"] for g in gs), p_inst=round(sum(g["p_inst"] for g in gs), 1),
                         p_now=round(sum(g["p_now"] for g in gs), 1))
    return out
