"""Паспорти обладнання: реальні моделі виробників і їхні опубліковані параметри.

Дані лежать у plant/equipment_specs.json (зібрані з сайтів і каталогів виробників, у кожного
запису є посилання на джерела). Тут — прив'язка кодів об'єктів сцени до ролей обладнання.
Без Blender: використовується і в site.py (габарити, підписи), і в odoo_demo.py (картки).
"""
import json
import os

SPECS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equipment_specs.json")

# код об'єкта сцени → роль (ключ у equipment_specs.json)
ROLE_BY_CODE = {
    "SAW-1": "beam_saw", "SAW-2": "beam_saw", "SAW-3": "beam_saw_book",
    "SLIDE-1": "sliding_table_saw", "VSAW-1": "vertical_panel_saw", "NEST-1": "nesting_cnc",
    "GANTRY-1": "board_storage",
    "EDGE-1": "edgebander_laser", "EDGE-2": "edgebander", "EDGE-3": "edgebander",
    "CNC-1": "ptp_cnc", "CNC-2": "ptp_cnc", "CNC-3": "ptp_cnc", "CNC-4": "ptp_cnc",
    "BORE-1": "throughfeed_drilling", "DOWEL-1": "dowel_inserting", "HINGE-1": "hinge_insertion",
    "SORT-1": "sorting_cell",
    "SAND-1": "wide_belt_sander", "PRESS-1": "membrane_press", "GLUE-1": "glue_spray_booth",
    "SPRAY-1": "manual_spray_booth", "AUTOSPRAY-1": "automatic_spraying", "DRY-1": "drying",
    "UV-1": "uv_line",
    "ASMLINE-1": "case_clamp_auto", "BOX-1": "box_machine",
    "PACK-1": "stretch_wrapper", "PACK-2": "stretch_wrapper", "PACKLINE-1": "shrink_line",
    "COMPRESSOR": "compressor", "DUST-1": "dust_extraction", "BOILER": "biomass_boiler",
    "TUGGER-1": "tugger",
    "BOARD-RACKS": "board_rack",
    "FL-2": "board_forklift", "FL-6": "board_forklift",
}
for _i in range(1, 7):
    ROLE_BY_CODE[f"ASM-{_i}"] = "case_clamp_manual"
for _c in ("FL-1", "FL-3", "FL-4", "FL-5", "FL-C1", "FL-C2"):
    ROLE_BY_CODE[_c] = "forklift"
# допоміжні одиниці, що входять до складу основної (показуються в тому самому паспорті)
EXTRA_ROLES = {"EDGE-1": ["robot_return"], "SPRAY-1": ["paint_pump"], "PACKLINE-1": ["strapping"], "UV-1": ["uv_oven"],
               "BOILER": ["briquetting_press"]}


# Габарити наших процедурних моделей (мм, уздовж потоку × поперек × висота) — щоб підігнати
# їх під паспортні. Для «пакування» і «лінії термоусадки» модель — це кілька одиниць, не масштабуємо.
NOMINAL_MM = {
    "saw": (6300, 5600, 1950), "saw_book": (6300, 5600, 1950), "edge": (8000, 1600, 1450),
    "edge_robot": (8000, 1600, 1450), "cnc": (4400, 2600, 2650), "nest": (10900, 3100, 2950),
    "slide": (3200, 3000, 1950), "vsaw": (5600, 1400, 2500), "dowel": (3400, 1500, 2000),
    "bore": (8400, 1400, 1700), "hinge": (2700, 900, 2100), "sortbot": (9600, 5500, 2600),
    "sand": (1800, 3000, 2550), "glue": (3200, 2300, 2700), "press": (11800, 2200, 2400),
    "spray": (5000, 3600, 3150), "autospray": (12600, 2400, 2800), "dry": (6000, 4400, 4100),
    "uv": (10000, 1800, 1700), "asmline": (23000, 2200, 3050), "asm": (3100, 1300, 2450),
    "box": (2600, 1300, 1500),
}
SCALE_LIMITS = (0.8, 1.2)  # ширше не можна — зламається планування


def body_scale(typ, rec):
    """Масштаб (x, y, z) тіла верстата за паспортними габаритами, або (1, 1, 1)."""
    nom = NOMINAL_MM.get(typ)
    dims = (rec or {}).get("dimensions_mm") or {}
    num = lambda k: isinstance(dims.get(k), (int, float)) and dims.get(k) > 0  # noqa: E731
    lo, hi = SCALE_LIMITS
    clamp = lambda v: max(lo, min(hi, v))  # noqa: E731
    if not nom or not num("L"):
        return (1.0, 1.0, 1.0)
    if not num("W"):  # опублікована лише довжина (напр., крайкооблицювальні) — тягнемо вздовж потоку
        return (clamp(dims["L"] / nom[0]), 1.0, 1.0)
    real_long, real_short = max(dims["L"], dims["W"]), min(dims["L"], dims["W"])
    nx, ny, nz = nom
    if nx >= ny:
        sx, sy = real_long / nx, real_short / ny
    else:
        sx, sy = real_short / nx, real_long / ny
    sz = dims["H"] / nz if isinstance(dims.get("H"), (int, float)) and dims.get("H") else 1.0
    return (clamp(sx), clamp(sy), clamp(sz))


def load_specs():
    if not os.path.exists(SPECS_PATH):
        return {}
    with open(SPECS_PATH, encoding="utf-8") as f:
        return {rec["role"]: rec for rec in json.load(f)}


def passport(code, specs=None):
    """Паспорт для об'єкта: основна модель + допоміжні одиниці (або None)."""
    specs = specs if specs is not None else load_specs()
    role = ROLE_BY_CODE.get(code)
    if not role or role not in specs:
        return None
    main = dict(specs[role])
    main["units"] = [specs[r] for r in EXTRA_ROLES.get(code, []) if r in specs]
    return main
