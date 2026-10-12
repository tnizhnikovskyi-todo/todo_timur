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
    ex = specs.get("ex_fan", {})
    q_req = ex.get("required_m3h") or 160
    units["EF-CHG"] = dict(name="Витяжка зарядної станції (Ex)", kind="exfan", zone="Z-CHG",
                           mode=f"Безперервно під час заряджання, не менше {round(q_req)} м³/год",
                           airflow_m3h=round(q_req), airflow_nom=ex.get("airflow_m3h") or 644,
                           p_inst=ex.get("power_kw") or 0.18, p_now=round((ex.get("power_kw") or 0.18) * 0.6, 3),
                           state="on",
                           note="Видаляє водень над зарядними пристроями. Потрібна витрата — за EN IEC 62485-3: "
                                "Q = 0,055 · 24 елементи · 40 А (40 % струму зарядного 100 А) × 3 батареї. "
                                "Вентилятор вибухозахищений (IIB+H2), реле термозахисту й перетворювач частоти — "
                                "поза небезпечною зоною.")
    heat_total = sum(u.get("heat_kw", 0) for u in units.values())
    chp = specs.get("chp", {})
    chp_heat = chp.get("heat_kw_50") or 0  # КГУ вдень на 50 % — тепло в мережу першим
    design = heat_balance(units, chp.get("heat_kw") or 0)
    boil = max(0.0, heat_total - chp_heat)
    totals = dict(units=len(units), airflow_m3h=round(sum(u["airflow_m3h"] for u in units.values()), -2),
                  heat_kw=round(heat_total), p_now=round(sum(u["p_now"] for u in units.values()), 1),
                  p_inst=round(sum(u["p_inst"] for u in units.values()), 1),
                  outdoor_c=OUTDOOR_C, indoor_set_c=INDOOR_SET_C,
                  boilers=BOILERS, boiler_kw=BOILER_KW,
                  boilers_on=0 if boil <= 0 else 1 if boil <= 0.85 * BOILER_KW else 2,
                  boiler_load=round(boil / BOILER_KW, 2), design_heat_kw=design["total"],
                  chp_heat_kw=round(min(chp_heat, heat_total)), chp_heat_now=chp_heat,
                  chp_heat_rated=chp.get("heat_kw") or 0)
    return dict(units=units, totals=totals, heat_balance=design)


# Котельня: два котли Kalvis K-500M каскадом
BOILERS, BOILER_KW = 2, 495
T_OUT_DESIGN = -15.0  # розрахункова зимова температура (як у паспорті RoofVent)
# Припущення для оцінки тепловтрат (не проєкт): U-коефіцієнти огороджень, Вт/(м²·К)
U_WALL, U_ROOF, U_FLOOR = 0.35, 0.25, 0.15
INFILTRATION_ACH = 0.1  # ворота з докшелтерами
WINTER_OA_SHARE = 0.5  # частка зовнішнього повітря в установках узимку
HEAT_RECOVERY = 0.78  # RoofVent RH-9C, суха рекуперація за паспортом


def heat_balance(units, chp_kw=0):
    """Оцінка зимового теплового навантаження при −15 °C (без внутрішніх теплонадходжень)."""
    from .layout import H, W
    dt = INDOOR_SET_C - T_OUT_DESIGN
    walls = 2 * (W + D) * H
    trans = (walls * U_WALL + W * D * U_ROOF + W * D * U_FLOOR) * dt / 1000
    infil = W * D * H * INFILTRATION_ACH * 0.34 * dt / 1000
    rv_q = sum(u["airflow_nom"] for u in units.values() if u["kind"] == "roofvent")
    vent = rv_q * WINTER_OA_SHARE * 0.34 * dt * (1 - HEAT_RECOVERY) / 1000
    ahu = units["AHU-1"]
    ahu_kw = ahu["airflow_m3h"] * 0.34 * (ahu["supply_c"] - T_OUT_DESIGN) / 1000
    items = [("Тепловтрати через стіни, покрівлю й підлогу", trans),
             (f"Інфільтрація крізь ворота ({INFILTRATION_ACH:g} обміну/год)".replace(".", ","), infil),
             (f"Дахові установки: {round(WINTER_OA_SHARE * 100)} % зовнішнього повітря, рекуперація "
              f"{round(HEAT_RECOVERY * 100)} %", vent),
             ("Приплив дільниці фасадів (без рекуперації — витяжка з фарбування)", ahu_kw)]
    total = sum(v for _, v in items)
    return dict(t_out=T_OUT_DESIGN, items=[dict(name=n, kw=round(v)) for n, v in items], total=round(total),
                capacity=BOILERS * BOILER_KW, chp_kw=chp_kw,
                reserve=round((BOILERS * BOILER_KW + chp_kw) / total - 1, 2),
                note=(f"Оцінка, не проєкт: U стін {U_WALL}, покрівлі {U_ROOF}, підлоги {U_FLOOR} Вт/(м²·К); "
                      .replace("0.", "0,")) + "внутрішні теплонадходження від верстатів (сотні кВт у зміну) "
                                              "не враховано — це запас.")
