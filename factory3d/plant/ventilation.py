"""Вентиляція й опалення: дахові припливно-витяжні установки з рекуперацією і водяним нагрівом
(тепло — від котельні на відходах), припливна установка дільниці фасадів із тканинними
повітроводами, витяжні вентилятори електрощитової, компресорної та зарядної, теплова мережа.

Без Blender: координати бере site.py, режими й навантаження — odoo_demo.py та energy.py.
"""
from .layout import D

# Дахові установки: code, x, y, зона, яку обслуговує. Місця підібрано так, щоб корпус під
# покрівлею (до ~6,3 м) не перетинав аспірацію, шинопроводи, міст порталу, стелажі й спринклери.
ROOFVENTS = [
    ("RV-01", 7.0, 12.0, "Z-RCV"), ("RV-02", 7.0, 36.0, "Z-RCV"), ("RV-03", 7.0, 62.5, "Z-RCV"),
    ("RV-04", 21.5, 12.0, "Z-SHEETS"), ("RV-05", 21.5, 33.5, "Z-SHEETS"),
    ("RV-06", 21.5, 58.5, "Z-HW"), ("RV-07", 35.0, 62.5, "Z-EDGE"),
    ("RV-08", 50.0, 23.0, "Z-CUT"), ("RV-09", 51.5, 36.5, "Z-CUT"),
    ("RV-10", 67.0, 23.0, "Z-EB"), ("RV-11", 66.5, 36.5, "Z-EB"),
    ("RV-12", 77.0, 23.0, "Z-CNC"), ("RV-13", 77.0, 36.5, "Z-CNC"),
    ("RV-14", 87.0, 8.0, "Z-SORT"), ("RV-15", 87.0, 36.5, "Z-SORT"),
    ("RV-16", 101.0, 8.0, "Z-ASM"), ("RV-17", 101.0, 31.0, "Z-PRE"),
    ("RV-18", 114.0, 8.0, "Z-PACK"), ("RV-19", 114.0, 31.0, "Z-PACK"), ("RV-20", 114.0, 52.0, "Z-POST"),
    ("RV-21", 125.4, 57.0, "Z-FG"), ("RV-22", 130.9, 57.0, "Z-FG"),
    ("RV-23", 142.5, 12.0, "Z-OUT"), ("RV-24", 142.5, 36.0, "Z-OUT"), ("RV-25", 142.5, 62.5, "Z-OUT"),
]
RV_BODY = 1.3  # м, півширина корпусу під покрівлею з запасом (для обходу світильниками)
RV_BOTTOM = 6.4  # низ повітророзподільника

# Теплова мережа: подача й зворотка під фермами
HEAT_Z, HEAT_RET_Z, HEAT_R = 8.15, 8.04, 0.05  # подача над зворотком: так труби не перетинаються
HEAT_MAIN_Y = 46.3  # магістраль уздовж будівлі над перегородкою дільниці фасадів
HEAT_ENTRY_X = 73.5  # введення від котельні крізь північну стіну
HEAT_PAIR = 0.25  # зсув зворотка в плані
AIR_RING_Z = 8.26  # пневмокільце над тепловою мережею, спринклери ще вище (8,345)
SPRINKLER_Z = 8.345

# Дільниця фасадів: припливна установка на даху + два тканинні повітроводи
AHU_POS = (66.0, 56.5)
FABRIC_DUCTS = [(49.0, 43.2, 90.6), (64.2, 43.2, 90.6)]  # y, x0, x1
FABRIC_Z, FABRIC_R = 6.8, 0.3

# Витяжні вентилятори: code, назва, x, y, z, що обслуговує
WALL_FANS = [
    ("EF-ELEC", "Витяжні вентилятори електрощитової", [(124.9, 3.2), (134.8, 3.2)],
     "Відводять тепло трансформаторів (≈ 2 × 12 кВт втрат під навантаженням); приплив — крізь сітку."),
    ("EF-CMP", "Витяжний вентилятор компресорної", [(111.0, 3.4)],
     "Відводить тепло компресорів, коли рекуперація тепла не працює."),
]
CHG_EXHAUST = (119.0, 70.5)  # витяжка над зарядними пристроями (водень) крізь покрівлю

OUTDOOR_C = 9.0  # 12 жовтня, 10:30
INDOOR_SET_C = 18.0


def obstacles():
    """Точки, які мають оминати світильники: (x, y, радіус)."""
    pts = [(x, y, RV_BODY) for _, x, y, _ in ROOFVENTS]
    pts += [(AHU_POS[0], y, 0.8) for y, *_ in FABRIC_DUCTS]
    pts.append((*CHG_EXHAUST, 0.6))
    return pts


def heat_paths():
    """Траси теплової мережі: [(подача, зворотка)] — ламані (x, y, z). Зворотка нижче й зсунута в плані."""
    xs = [x for _, x, _, _ in ROOFVENTS]
    p, x0, x1, ym, xe = HEAT_PAIR, min(xs), max(xs), HEAT_MAIN_Y, HEAT_ENTRY_X
    out = [([(x0, ym, HEAT_Z), (x1, ym, HEAT_Z)], [(x0 + p, ym + p, HEAT_RET_Z), (x1 + p, ym + p, HEAT_RET_Z)]),
           ([(xe, D + 3.0, 3.0), (xe, D + 0.6, 3.0), (xe, D + 0.6, HEAT_Z), (xe, ym, HEAT_Z)],
            [(xe + p, D + 3.0, 2.7), (xe + p, D + 0.6, 2.7), (xe + p, D + 0.6, HEAT_RET_Z),
             (xe + p, ym + p, HEAT_RET_Z)])]
    for _, x, y, _ in ROOFVENTS:
        out.append(([(x, ym, HEAT_Z), (x, y, HEAT_Z)], [(x + p, ym + p, HEAT_RET_Z), (x + p, y, HEAT_RET_Z)]))
    return out


def _h(*xs, mod=1000):
    h = 2166136261
    for ch in "|".join(map(str, xs)):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % mod


def ventilation_data(specs):
    """Стан установок «з диспетчеризації»: режим, витрата, температура припливу, нагрів, фільтр."""
    rv = specs.get("roofvent", {})
    ahu = specs.get("make_up_ahu", {})
    fan = specs.get("wall_fan", {})
    q_nom = rv.get("airflow_m3h") or 8000
    heat_nom = rv.get("heat_kw") or 60.0
    p_nom = rv.get("power_kw") or 4.0
    units = {}
    for code, x, y, zone in ROOFVENTS:
        k = 0.55 + _h(code, mod=30) / 100  # частка номінальної витрати (за CO₂ / вологістю)
        mode = "Рекуперація" if zone not in ("Z-OUT", "Z-RCV") else "Приплив і витяжка"
        if code in ("RV-21", "RV-22"):
            mode, k = "Рециркуляція", 0.45
        heat = heat_nom * k * (INDOOR_SET_C - OUTDOOR_C) / (INDOOR_SET_C + 15) * (0.3 if mode == "Рекуперація" else 0.8)
        units[code] = dict(
            name=f"Дахова установка {code}", kind="roofvent", zone=zone, mode=mode,
            airflow_m3h=round(q_nom * k, -1), airflow_nom=q_nom, supply_c=round(19.5 + _h(code, 1, mod=15) / 10, 1),
            indoor_c=round(17.5 + _h(code, 2, mod=20) / 10, 1), heating_valve=round(min(1.0, heat / heat_nom), 2),
            heat_kw=round(heat, 1), p_inst=p_nom, p_now=round(p_nom * k ** 3 + 0.1, 2),
            filter_dp_pa=120 + _h(code, 3, mod=90), state="on")
    units["RV-05"]["filter_dp_pa"] = 285  # фільтр забитий — привід для заявки на ТО
    q_ahu = ahu.get("airflow_m3h") or 20000
    p_ahu = ahu.get("power_kw") or 15.0
    units["AHU-1"] = dict(name="Припливна установка дільниці фасадів", kind="ahu", zone="Z-FAC",
                          mode="Приплив під витяжку фарбувальних камер", airflow_m3h=round(q_ahu * 0.85, -1),
                          airflow_nom=q_ahu, supply_c=21.0, indoor_c=20.4, heating_valve=0.46,
                          heat_kw=round(q_ahu * 0.85 * 1.2 / 3600 * (21 - OUTDOOR_C), 1), p_inst=p_ahu,
                          p_now=round(p_ahu * 0.62, 1), filter_dp_pa=160, state="on",
                          note="Подає підігріте повітря стільки, скільки витягують камери фарбування й сушка — "
                               "у дільниці невелике розрідження, пил і пари не йдуть у цех.")
    q_fan = fan.get("airflow_m3h") or 6000
    p_fan = fan.get("power_kw") or 0.6
    for code, name, pts, note in WALL_FANS:
        n = len(pts)
        on = n if code == "EF-ELEC" else 0
        units[code] = dict(name=name, kind="fan", zone="Z-ELEC" if code == "EF-ELEC" else "Z-CMP",
                           mode=f"Увімкнено {on} з {n} (термостат)" if on else "Чекає (термостат)",
                           airflow_m3h=q_fan * on, airflow_nom=q_fan * n, p_inst=round(p_fan * n, 2),
                           p_now=round(p_fan * on, 2), state="on" if on else "standby", note=note,
                           indoor_c=29.5 if code == "EF-ELEC" else 24.0)
    units["EF-CHG"] = dict(name="Витяжка зарядної станції", kind="fan", zone="Z-CHG",
                           mode="Безперервно під час заряджання", airflow_m3h=1500, airflow_nom=1500,
                           p_inst=0.25, p_now=0.25, state="on",
                           note="Видаляє водень над зарядними пристроями крізь покрівлю. Потрібен вибухозахищений "
                                "(Ex) вентилятор — модель ще не вибрано, цифри орієнтовні.")
    heat_total = sum(u.get("heat_kw", 0) for u in units.values())
    totals = dict(units=len(units), airflow_m3h=round(sum(u["airflow_m3h"] for u in units.values()), -2),
                  heat_kw=round(heat_total), p_now=round(sum(u["p_now"] for u in units.values()), 1),
                  p_inst=round(sum(u["p_inst"] for u in units.values()), 1),
                  outdoor_c=OUTDOOR_C, indoor_set_c=INDOOR_SET_C,
                  boiler_load=round(heat_total / 495, 2))
    return dict(units=units, totals=totals)
