"""Пожежна сигналізація: адресний приймально-контрольний прилад, сповіщувачі за типом зони,
ручні сповіщувачі біля виходів, оповіщувачі, система виявлення й гасіння іскор в аспірації.

Без Blender: координати бере site.py, стан і журнал — odoo_demo.py. Норми розстановки
підтягуються з fire_rules.json (якщо є), інакше — типові значення нижче.
"""
import json
import math
import os

from .layout import D, DOOR_Y, GANTRY_X, DUCT_MAIN_Y, DUCT_NORTH_X, DUCT_Z, W, ZONES
from .ventilation import AHU_POS, CHG_EXHAUST, FABRIC_DUCTS, ROOFVENTS

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fire_rules.json")
# ДБН В.2.5-56:2014 зі Зміною № 2 (табл. 7.1, 7.2), ДСТУ-Н CEN/TS 54-14 (ручні сповіщувачі)
DEFAULT_RULES = {"smoke_spacing_6_12m": 8.8, "smoke_wall_6_12m": 4.4, "smoke_area_6_12m": None,
                 "heat_spacing": 6.4, "heat_area": None, "mcp_spacing": 30.0, "mcp_height": None,
                 "sounder_level": 65}
Z_DET = 8.85  # під покрівлею, між фермами (нижній пояс 8,4)

# зона → тип сповіщувачів: multi — пил деревини (оптико-тепловий), smoke — склади, heat — котельня/компресорна
ZONE_DETECTOR = {
    "Z-RCV": "smoke", "Z-SHEETS": "smoke", "Z-HW": "smoke", "Z-EDGE": "smoke", "Z-PKS": "smoke",
    "Z-CUT": "multi", "Z-EB": "multi", "Z-CNC": "multi", "Z-SORT": "multi", "Z-FAC": "multi",
    "Z-ASM": "multi", "Z-PRE": "smoke", "Z-MAINT": "multi", "Z-PACK": "smoke", "Z-POST": "smoke",
    # компресорна й зарядна без власної стелі: під покрівлею 9 м точкові теплові заборонені (табл. 7.1 — до 7,5 м)
    "Z-CMP": "multi", "Z-CHG": "multi", "Z-FG": "smoke", "Z-ELEC": "smoke", "Z-OUT": "smoke",
}
BOILER_HOUSE = (67.6, D + 3.0, 79.6, D + 9.0)  # котельня має власне перекриття 4,5 м — теплові сповіщувачі
Z_BOILER = 4.35
KIND_NAME = {"multi": "оптико-теплові (пил деревини)", "smoke": "димові оптичні", "heat": "теплові"}
# шлейфи: межі по X
LOOPS = [(1, 0, 42), (2, 42, 92), (3, 92, 122), (4, 122, W + 1)]
# полум'я у фарбувальній частині: x, y, z, куди дивиться (кут у плані)
FLAME = [(46.0, 71.8, 5.0, -90), (64.0, 71.8, 5.0, -90), (76.0, 71.8, 5.0, -90)]
FACP_POS = (97.2, 58.25)  # на фасаді офісу біля входу (пост охорони на першому поверсі)
# іскрогасіння: датчики на магістралі аспірації та гілці на північ, гасіння — перед виходом надвір
# іскрогасіння: форсунки за 4–6 м після датчика по ходу повітря (GreCon); магістраль тече до гілки на x = 55,6
SPARK_DETECTORS = [(47.0, DUCT_MAIN_Y), (66.0, DUCT_MAIN_Y), (79.0, DUCT_MAIN_Y), (DUCT_NORTH_X, 60.5)]
SPARK_EXTINGUISH = [(52.5, DUCT_MAIN_Y, "X"), (60.5, DUCT_MAIN_Y, "X"), (DUCT_NORTH_X, 66.0, "Y")]
SPARK_PANEL = (52.0, 71.75)
DUCT_TOP = DUCT_Z + 0.38


def load_rules():
    rules = dict(DEFAULT_RULES)
    if os.path.exists(RULES_PATH):
        with open(RULES_PATH, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if isinstance(v.get("value"), (int, float)) or k not in rules:
                    rules[k] = v["value"]
    return rules


def loop_of(x):
    return next(n for n, a, b in LOOPS if a <= x < b)


def max_mcp_distance(step=2.0):
    """Найбільша відстань по прямій від точки цеху до найближчого ручного сповіщувача (перевірка ≤ 30 м)."""
    pts = [(x, y) for x, y, _ in call_points()]
    worst = (0, None)
    for i in range(int(W / step) + 1):
        for j in range(int(D / step) + 1):
            p = (i * step, j * step)
            d = min(math.dist(p, q) for q in pts)
            if d > worst[0]:
                worst = (d, p)
    return round(worst[0], 1), worst[1]


def _blocked(x, y):
    if abs(x / 12 - round(x / 12)) * 12 < 0.45:  # ферми
        return True
    if min(abs(y - c) for c in (15, 30, 45, 60)) < 0.4:  # прогони
        return True
    if any(math.hypot(x - rx, y - ry) < 1.5 for _, rx, ry, _ in ROOFVENTS):
        return True
    pts = [(46.0, 60.7), (57.9, 52.0), (70.4, 61.4), (78.3, 62.0), CHG_EXHAUST]
    pts += [(AHU_POS[0] + 2.0, y) for y, *_ in FABRIC_DUCTS]
    return any(math.hypot(x - px, y - py) < 0.8 for px, py in pts)


def _nudge(x, y, rect):
    x0, y0, x1, y1 = rect
    for dx, dy in ((0, 0), (0.8, 0), (-0.8, 0), (0, 0.8), (0, -0.8), (1.2, 1.2), (-1.2, -1.2), (1.2, -1.2),
                   (-1.2, 1.2), (1.6, 0), (-1.6, 0)):
        px, py = x + dx, y + dy
        if x0 + 0.3 < px < x1 - 0.3 and y0 + 0.3 < py < y1 - 0.3 and not _blocked(px, py):
            return px, py
    return None


def detectors(rules=None):
    """Сповіщувачі по зонах: {zone: dict(kind, points, spacing)}."""
    r = rules or load_rules()
    out = {}
    for code, name, (x0, y0, x1, y1), *_ in ZONES:
        kind = ZONE_DETECTOR.get(code)
        if not kind:
            continue
        s = min(r["smoke_spacing_6_12m"], 2 * r["smoke_wall_6_12m"])
        if r.get("smoke_area_6_12m"):
            s = min(s, math.sqrt(r["smoke_area_6_12m"]))
        nx, ny = max(1, math.ceil((x1 - x0) / s)), max(1, math.ceil((y1 - y0) / s))
        pts = []
        for i in range(nx):
            for j in range(ny):
                p = _nudge(x0 + (x1 - x0) * (i + 0.5) / nx, y0 + (y1 - y0) * (j + 0.5) / ny, (x0, y0, x1, y1))
                if p:
                    pts.append(p)
        out[code] = dict(name=name, kind=kind, points=pts, spacing=round(s, 1), area=(x1 - x0) * (y1 - y0), z=Z_DET)
    x0, y0, x1, y1 = BOILER_HOUSE
    s = r["heat_spacing"]
    nx, ny = math.ceil((x1 - x0) / s), math.ceil((y1 - y0) / s)
    out["Z-BOILER"] = dict(name="Котельня", kind="heat", spacing=s, area=(x1 - x0) * (y1 - y0), z=Z_BOILER,
                           points=[(x0 + (x1 - x0) * (i + 0.5) / nx, y0 + (y1 - y0) * (j + 0.5) / ny)
                                   for i in range(nx) for j in range(ny)])
    return out


# Колони, що є в будівлі (решту прибрано під верстати й склади) — на них ручні сповіщувачі й оповіщувачі
COLUMN_MCP = [(48, 30), (60, 30), (84, 30), (96, 30), (108, 30), (120, 15), (120, 45), (36, 60), (84, 60),
              (132, 60)]
MCP_POSTS = [30.0, 60.0, 90.0, 118.0]
COLUMN_SOUNDER = [(48, 45), (60, 45), (72, 45), (84, 45), (96, 45), (108, 45), (120, 15), (120, 60)]


def call_points():
    """Ручні сповіщувачі (x, y, бік стіни/колони): біля кожних воріт і дверей, на колонах уздовж проїздів."""
    pts = []
    for y in DOOR_Y:
        pts.append((0.04, y + 2.3, "W"))
        pts.append((W - 0.04, y + 2.3, "E"))
    pts += [(50.5, 45.88, "S"), (68.0, 45.88, "S"), (91.0, 45.88, "S"),  # двері дільниці фасадів
            (98.6, 58.37, "S"), (131.3, 62.37, "S"), (114.5, 59.88, "S")]  # офіс, електрощитова, компресорна
    pts += [(x, y - 0.25, "S") for x, y in COLUMN_MCP]
    pts += [(GANTRY_X[0] - 0.18, 9.5, "E"), (GANTRY_X[1] + 0.18, 9.5, "W")]  # на стійках порталу складу плит
    pts += [(x, 0.6, "P") for x in MCP_POSTS]  # південна стіна в моделі зрізана — на окремих стійках
    return pts


def sounders():
    """Сирени-маяки (W-3.2-10 — покриття 10 м): кожні 10 м по стінах і перегородках, на колонах.
    Фон у цеху 80–85 дБА, тож потрібно 85–90 дБА — точну кількість дає акустичний розрахунок."""
    pts = [(x, y - 0.25, "S") for x, y in COLUMN_SOUNDER]
    pts += [(x, D - 0.04, "N") for x in range(5, int(W), 10)]
    pts += [(0.04, y, "W") for y in range(10, int(D), 10)] + [(W - 0.04, y, "E") for y in range(10, int(D), 10)]
    pts += [(x, 45.88, "S") for x in range(45, 92, 10) if all(abs(x - d) > 1.8 for d in (48.5, 66.0, 89.0))]
    return pts


def fire_data(specs):
    """Стан системи «з приладу»: пристрої по шлейфах, попередження, журнал."""
    r = load_rules()
    dets = detectors(r)
    mcp, snd = call_points(), sounders()
    loops = {n: dict(detectors=0, mcp=0, sounders=0, flame=0, modules=0) for n, *_ in LOOPS}
    for z, d in dets.items():
        for x, _ in d["points"]:
            loops[loop_of(x)]["detectors"] += 1
    for x, *_ in mcp:
        loops[loop_of(x)]["mcp"] += 1
    for x, *_ in snd:
        loops[loop_of(x)]["sounders"] += 1
    loops[2]["flame"] = len(FLAME)
    loops[2]["modules"] += len(FLAME) + 1  # модулі входу для полум'я й іскрогасіння
    groups = {}
    for z, d in dets.items():
        zone = "BOILER" if z == "Z-BOILER" else z
        groups["FA-" + z[2:]] = dict(zone=zone, zone_name=d["name"], kind=d["kind"], kind_name=KIND_NAME[d["kind"]],
                                     n=len(d["points"]), spacing=d["spacing"], area=round(d["area"]),
                                     loop=loop_of(d["points"][0][0]) if d["points"] else None, state="ok")
    groups["FA-FAC"].update(
        state="warn", warning="Сповіщувач 2.FAC.07 біля шліфування: запиленість камери 82 % — очистити до кінця "
                              "зміни, інакше прилад переведе його в несправність.")
    events = [
        dict(time="2026-10-12 08:47", level="warn", code="SPARK-1",
             text="Іскрогасіння: іскру виявлено на магістралі аспірації над лінією A, гасіння 0,6 с, "
                  "лінію не зупиняли."),
        dict(time="2026-10-12 09:58", level="warn", code="FA-FAC",
             text="Попередження про запиленість: сповіщувач 2.FAC.07 (дільниця фасадів, шліфування)."),
        dict(time="2026-10-12 07:00", level="info", code="FACP-1",
             text="Щотижнева перевірка оповіщувачів: усі 4 шлейфи — норма."),
        dict(time="2026-10-11 23:10", level="info", code="SPARK-1",
             text="Самотест іскрогасіння: датчики й клапан гасіння — норма."),
    ]
    return dict(rules=r, loops=loops, groups=groups,
                totals=dict(detectors=sum(g["n"] for g in groups.values()), mcp=len(mcp), sounders=len(snd),
                            mcp_max_m=max_mcp_distance()[0],
                            flame=len(FLAME), spark_detectors=len(SPARK_DETECTORS),
                            state="Норма, 1 попередження", sprinkler="Спринклерна система в режимі очікування"),
                events=events)


# Паспорти: код об'єкта → роль у equipment_specs.json
FIRE_ROLES = {"FACP-1": ("facp", []), "FA-MCP": ("mcp", []), "FA-SND": ("sounder_beacon", []),
              "FA-FLAME": ("flame_detector", []), "SPARK-1": ("spark_detection", [])}
_DET_ROLE = {"multi": "multi_detector", "smoke": "smoke_detector", "heat": "heat_detector"}
for _z, _k in ZONE_DETECTOR.items():
    FIRE_ROLES["FA-" + _z[2:]] = (_DET_ROLE[_k], [])
FIRE_ROLES["FA-BOILER"] = ("heat_detector", [])
