"""Інфраструктура навколо цеху: територія й охорона, резервне живлення та сонячна станція, вода й
стоки, робочі місця Odoo й мережа, димовидалення, блискавкозахист. Координати й демо-стан
(без Blender) — для site2.py і odoo_demo.py.
"""
import math

from .layout import D, MACHINES, OPERATOR, W
from .ventilation import AHU_POS, CHG_EXHAUST, ROOFVENTS

ROOF_Z = 9.0

# ---------------------------------------------------------------- територія
SITE = (-32.0, -30.0, 182.0, 100.0)
GATES = [("GATE-W", -20.0, 8.0, "Ворота приймання"), ("GATE-E", 168.0, 8.0, "Ворота відвантаження")]
KPP = (98.4, -27.0)  # прохідна персоналу навпроти входу EX-IN
STAFF_ENTRANCE_X = 98.4
PARKING = (106.0, -27.0, 150.0, -6.0)
TRUCK_SCALE = (172.0, -14.0)  # уздовж Y, 18 × 3 м
WASTE = (158.0, 78.0, 176.0, 92.0)
CAMERAS = [  # code, x, y, z, напрям у плані (°)
    ("CAM-01", -0.4, -0.4, 6.0, 225), ("CAM-02", W + 0.4, -0.4, 6.0, -45), ("CAM-03", -0.4, D + 0.4, 6.0, 135),
    ("CAM-04", W + 0.4, D + 0.4, 6.0, 45), ("CAM-05", -20.0, -28.5, 5.0, 90), ("CAM-06", 168.0, -28.5, 5.0, 90),
    ("CAM-07", KPP[0] + 3.5, KPP[1] + 2.5, 3.5, -90), ("CAM-08", -0.4, 36.0, 6.5, 180),
    ("CAM-09", W + 0.4, 36.0, 6.5, 0), ("CAM-10", 66.0, D + 0.4, 6.5, 90), ("CAM-11", 130.0, D + 0.4, 6.5, 90),
    ("CAM-12", 167.0, 85.0, 4.5, 180)]
DOOR_READERS = [("ACR-ELEC", 129.0, 62.25, "Електрощитова"), ("ACR-CHG", 117.0, 59.88, "Зарядна"),
                ("ACR-PAINT", 61.0, 65.88, "Склад ЛФМ"), ("ACR-SRV", 99.6, 48.6, "Серверна"),
                ("ACR-IN", STAFF_ENTRANCE_X + 0.9, 0.12, "Вхід персоналу")]

# ---------------------------------------------------------------- резервне живлення і СЕС
GENSET_POS = (128.5, D + 4.2)  # контейнер уздовж X за електрощитовою
BESS_POS = (140.0, D + 3.4)
ATS_POS = (135.1, 68.5)
PV_INVERTERS_X = [95.0 + 1.6 * k for k in range(8)]  # 8 × 115 кВт на зовнішній північній стіні за офісом
MODULE = (2.278, 1.134)  # placeholder до паспорта: довжина, ширина, м
PV_TILT = 10.0

# ---------------------------------------------------------------- вода
WATER_INLET = (30.0, D + 3.5)
WATER_MAIN = [(30.0, D + 3.5, -0.8), (30.0, D + 0.4, -0.8), (30.0, D - 0.45, 0.5), (30.0, D - 0.45, 4.2),
              (121.5, D - 0.45, 4.2)]
EYEWASH = [("EYE-CHG", 121.3, 61.2, "Зарядна станція"), ("EYE-PAINT", 68.5, 66.6, "Дільниця фарбування")]
WASTEWATER = (73.0, 69.6)

# ---------------------------------------------------------------- димовидалення
SMOKE_PANEL = (102.6, 58.37)
VENT = (1.2, 1.2)  # LAMILUX Smoke Lift F100: 1200 × 1200 мм


def _roof_blocked(x, y, hx, hy, margin=1.0):
    """Перетин прямокутника (центр, півширини) з тим, що вже стоїть на покрівлі."""
    obst = [(rx, ry, 1.3, 1.0) for _, rx, ry, _ in ROOFVENTS]
    obst += [(AHU_POS[0], AHU_POS[1], 3.7, 1.3), (AHU_POS[0] + 2.0, (49.0 + 64.2) / 2, 0.5, 8.0)]
    obst += [(sx, sy, 0.5, 0.5) for sx, sy in ((46.0, 60.7), (57.9, 52.0), (70.4, 61.4), (78.3, 62.0), CHG_EXHAUST)]
    return any(abs(x - ox) < hx + w + margin and abs(y - oy) < hy + h + margin for ox, oy, w, h in obst)


# Зони димовидалення ≤ 1600 м² (ДБН В.2.5-56, п. 10.4.2), між ними — димові завіси; фарбування — окрема зона
SMOKE_ZONES = [("SZ-1", (0.0, 0.0, 20.0, D)), ("SZ-2", (20.0, 0.0, 42.0, D)), ("SZ-3", (42.0, 0.0, 62.0, 46.0)),
               ("SZ-4", (62.0, 0.0, 92.0, 46.0)), ("SZ-5", (42.0, 46.0, 92.0, D)), ("SZ-6", (92.0, 0.0, 112.0, D)),
               ("SZ-7", (112.0, 0.0, 132.0, D)), ("SZ-8", (132.0, 0.0, W, D))]
CURTAINS = [((20.0, 0.0), (20.0, D)), ((42.0, 0.0), (42.0, D)), ((62.0, 0.0), (62.0, 46.0)),
            ((42.0, 46.0), (92.0, 46.0)), ((92.0, 0.0), (92.0, D)), ((112.0, 0.0), (112.0, D)),
            ((132.0, 0.0), (132.0, D))]
CURTAIN_BOTTOM = 7.9
VENT_AA = 1.02  # м² аеродинамічної площі клапана (LAMILUX F100, 1200 × 1200)
AA_PER_400 = 1.5  # орієнтир — 1,5 м² Aa на кожні 400 м² (Industriebaurichtlinie, п. 5.7)


# Клапани стоять рядами вздовж ферм (x = 12k ± 1,8) — по ряду на зону; між рядами лишаються суцільні поля СЕС
VENT_LINES = {"SZ-1": [13.8], "SZ-2": [25.8], "SZ-3": [49.8], "SZ-4": [73.8], "SZ-5": [49.8, 73.8],
              "SZ-6": [97.8], "SZ-7": [121.8], "SZ-8": [145.8]}
PV_LANE_Y = 36.0  # поперечний прохід для пожежників посередині покрівлі
PV_LANE_W = 1.5
PV_EDGE = 1.2  # від краю покрівлі
PV_VENT_GAP = 2.5  # від клапанів димовидалення (VdS 2098)


def _vent_ok(x, y, rect):
    x0, y0, x1, y1 = rect
    if not (x0 + 1.5 < x < x1 - 1.5 and y0 + 1.5 < y < y1 - 1.5):
        return False
    if min(abs(y - c) for c in (15, 30, 45, 60)) < 0.9:
        return False  # над прогонами
    return not _roof_blocked(x, y, VENT[0] / 2, VENT[1] / 2)


def smoke_zone_vents():
    """Клапани по зонах: кількість — з орієнтиру по Aa, рівномірно вздовж рядів зони з обходом установок."""
    out = {}
    for code, rect in SMOKE_ZONES:
        x0, y0, x1, y1 = rect
        area = (x1 - x0) * (y1 - y0)
        n = math.ceil(area / 400 * AA_PER_400 / VENT_AA)
        lines = VENT_LINES[code]
        per = [n // len(lines) + (1 if k < n % len(lines) else 0) for k in range(len(lines))]
        pts = []
        for lx, cnt in zip(lines, per):
            for k in range(cnt):
                by = y0 + (y1 - y0) * (k + 0.5) / cnt
                for dy in (0, 1.5, -1.5, 3.0, -3.0, 4.5, -4.5, 6.0, -6.0):
                    if _vent_ok(lx, by + dy, rect) and all(abs(by + dy - py) > 3.0 for px, py in pts if px == lx):
                        pts.append((lx, by + dy))
                        break
        out[code] = dict(rect=rect, area=round(area), need=n, points=pts)
    return out


def smoke_vents():
    return [p for z in smoke_zone_vents().values() for p in z["points"]]


PV_MAX_KWP = 900.0  # більше — лише на експорт: удень цех бере ≈ 630 кВт, ще й когенерація
# Когенераційна установка TEDOM Quanto D800 поруч із генератором: модуль 7,2 × 2,5 м, модуль вихлопу,
# сухий охолоджувач для літнього скидання тепла, шафовий ГРП на газопроводі середнього тиску
CHP_POS = (118.6, D + 4.6)
CHP_EXH_POS = (117.6, D + 6.6)
CHP_COOLER_POS = (118.6, D + 9.6)
CHP_GRP_POS = (112.5, D + 9.0)
CHP_HEAT_Y, CHP_HEAT_Z = D + 5.6, 3.0  # естакада теплотраси до котельні
CHP_LOAD_NOW = 0.5  # удень світить СЕС — установка на мінімальному тривалому навантаженні


def pv_rows(vents, wp=580, max_kwp=PV_MAX_KWP):
    """Модулі суцільними полями (схід-захід, 10°): ряди вздовж X, проходи по рядах клапанів (≤ 24 м між ними)
    і посередині покрівлі, ≥ 2,5 м від клапанів, оминаючи установки. Повертає [(x, y, нахил ±1)]."""
    lx, ly = MODULE
    pitch = ly + 0.15
    lanes_x = sorted({x for v in VENT_LINES.values() for x in v})
    out = []
    j = 0
    y = PV_EDGE
    while y + ly <= D - PV_EDGE:
        if not (y + ly < PV_LANE_Y - PV_LANE_W / 2 or y > PV_LANE_Y + PV_LANE_W / 2):
            y = PV_LANE_Y + PV_LANE_W / 2 + 0.01
            continue
        x = PV_EDGE
        while x + lx <= W - PV_EDGE:
            cx, cy = x + lx / 2, y + ly / 2
            lane = next((lxx for lxx in lanes_x if abs(cx - lxx) < lx / 2 + PV_LANE_W / 2), None)
            if lane is not None:
                x = lane + PV_LANE_W / 2 + 0.01
                continue
            if not _roof_blocked(cx, cy, lx / 2, ly / 2, margin=0.8) and not any(
                    abs(cx - vx) < lx / 2 + VENT[0] / 2 + PV_VENT_GAP
                    and abs(cy - vy) < ly / 2 + VENT[1] / 2 + PV_VENT_GAP
                    for vx, vy in vents):
                out.append((round(x, 3), round(y, 3), 1 if j % 2 else -1))
                if len(out) * wp / 1000 >= max_kwp:
                    return out
            x += lx + 0.02
        y += pitch
        j += 1
    return out


def pv_kwp(rows, wp=580):
    return len(rows) * wp / 1000


def pv_fields():
    """Поля СЕС для підсумків: між проходами (смуги між рядами клапанів × половини покрівлі)."""
    lanes = [0.0] + sorted({x for v in VENT_LINES.values() for x in v}) + [W]
    return [(a, b) for a, b in zip(lanes, lanes[1:])]


# ---------------------------------------------------------------- Odoo і мережа
def tablets():
    """Планшет Shop Floor біля кожного робочого центру з оператором: (code, x, y, rz)."""
    out = []
    for m in MACHINES:
        code, typ, _, x, y = m[:5]
        rz = m[6] if len(m) > 6 else 0
        if OPERATOR.get(typ) is None:
            continue
        ox, oy, prz = OPERATOR[typ]
        a = math.radians(rz)
        px, py = x + ox * math.cos(a) - oy * math.sin(a), y + ox * math.sin(a) + oy * math.cos(a)
        b = math.radians(prz + rz)
        out.append((code, px - 0.75 * math.sin(b), py + 0.75 * math.cos(b) - 0.0, prz + rz))
    return out


SCANNERS = [("OP-W1", 22.0, 50.2), ("OP-W2", 18.0, 58.6), ("OP-W3", 8.0, 12.0), ("OP-W6", 116.0, 44.0),
            ("OP-W7", 140.0, 24.0)]
PRINTERS = [("PRN-RCV", 9.6, 30.0, "Приймання: етикетки партій"), ("PRN-PACK1", 112.6, 7.6, "Пакування 1"),
            ("PRN-PACK2", 112.6, 14.0, "Пакування 2"), ("PRN-OUT", 145.0, 70.0, "Відвантаження: палетні етикетки")]
SCALES = [("SCALE-OUT1", 139.2, 29.0, "Відвантаження"), ("SCALE-OUT2", 139.2, 51.0, "Відвантаження"),
          ("SCALE-RCV", 6.0, 40.0, "Приймання")]
IOT_BOXES = [("IOT-RCV", 9.6, 30.6, ["PRN-RCV", "SCALE-RCV"]), ("IOT-PACK", 112.6, 10.8, ["PRN-PACK1", "PRN-PACK2"]),
             ("IOT-OUT", 145.0, 70.6, ["PRN-OUT", "SCALE-OUT1", "SCALE-OUT2"])]
SERVER_ROOM = (101.0, 47.6, 2.4, 2.0)  # центр, розмір — у ремонтній зоні, засклена, з кондиціонером


def wifi_aps():
    """Точки доступу під покрівлею: сітка ~24 × 24 м, оминаючи ферми, прогони, спринклери й установки."""
    pts = []
    for x in (6.0, 30.0, 54.0, 78.0, 102.0, 126.0, 144.0):
        for y in (11.5, 36.5, 61.5):
            for dx, dy in ((0, 0), (2.5, 0), (-2.5, 0), (0, 2.0), (0, -2.0), (2.5, 2.0), (-2.5, -2.0)):
                px, py = x + dx, y + dy
                if abs(px / 12 - round(px / 12)) * 12 < 0.6 or min(abs(py - 5 * round(py / 5)), 9) < 0.5:
                    continue
                if any(math.hypot(px - rx, py - ry) < 2.0 for _, rx, ry, _ in ROOFVENTS):
                    continue
                pts.append((px, py))
                break
    return pts


# ---------------------------------------------------------------- блискавкозахист
MESH = 10.0  # клас II за ДСТУ EN 62305: сітка 10 × 10 м
DOWN_STEP = 10.0  # струмовідводи кожні 10 м


def down_conductors():
    pts = []
    for x in [k * DOWN_STEP for k in range(int(W / DOWN_STEP) + 1)]:
        pts += [(x, -0.18), (x, D + 0.18)]
    for y in [k * DOWN_STEP for k in range(1, int(D / DOWN_STEP) + 1)] + [D]:
        pts += [(-0.18, min(y, D)), (W + 0.18, min(y, D))]
    return pts


# Паспорти: код об'єкта → роль у equipment_specs.json
INFRA_ROLES = {
    "GENSET": ("genset", []), "ATS-1": ("ats", []), "BESS": ("bess", []), "PV-ROOF": ("pv_module", ["pv_inverter"]),
    "PV-INV": ("pv_inverter", []), "CHP": ("chp", []), "SMOKE-VENTS": ("smoke_vent", []),
    "SMOKE-CTRL": ("smoke_control", []),
    "EXITS": ("exit_door", ["panic_bar"]), "LPS": ("lightning_air", ["earthing"]),
    "WATER": ("water_meter", ["eyewash", "wastewater"]), "ODOO-TABLETS": ("shopfloor_tablet", []),
    "ODOO-SCANNERS": ("handheld_scanner", []), "WIFI": ("wifi_ap", []),
    "SERVER": ("server_rack", ["network_switch", "nvr"]), "TURNSTILES": ("turnstile", ["access_reader"]),
    "ACCESS": ("access_reader", []), "CCTV": ("cctv_camera", ["nvr"]), "TRUCK-SCALE": ("truck_scale", []),
    "GATE-W": ("barrier", []), "GATE-E": ("barrier", []),
}
for _c, *_ in PRINTERS:
    INFRA_ROLES[_c] = ("label_printer", [])
for _c, *_ in SCALES:
    INFRA_ROLES[_c] = ("scale", [])
for _c, *_ in IOT_BOXES:
    INFRA_ROLES[_c] = ("iot_box", [])
for _c, *_ in EYEWASH:
    INFRA_ROLES[_c] = ("eyewash", [])


# ---------------------------------------------------------------- демо-стан («з диспетчеризації»)
CRITICAL = ["LP-1", "LP-2", "LP-3", "DUST-1", "COMPRESSOR", "BOILER", "OFFICE", "EF-ELEC", "EF-CHG", "BW-1-LINE"]


def _fmt(v, d=0):
    s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def infra_data(specs, energy, vent):
    """Картки інфраструктурних об'єктів: {code: dict(rows=[[назва, значення]], note, warn, items)} + підсумки."""
    cards, cons = {}, energy["consumers"]
    gen, bess, pvm, inv, chp = (specs.get(k, {}) for k in ("genset", "bess", "pv_module", "pv_inverter", "chp"))
    # сонячна станція
    vents = smoke_vents()
    wp = pvm.get("wp") or 580
    n_mod = len(pv_rows(vents, wp))
    kwp = n_mod * wp / 1000
    n_inv = len(PV_INVERTERS_X)
    inv_kw = inv.get("kw_ac") or 115
    pv_now = round(min(kwp * 0.52, n_inv * inv_kw))  # 12 жовтня, 10:30, ясно — ≈ 52 % від піку
    pv_today = round(kwp * 1.35)  # з 07:30 до 10:30
    load = energy["totals"]["p_now"]
    # когенерація: удень на мінімумі, тепло — в теплову мережу замість котлів
    chp_kw = chp.get("power_kw") or 800
    chp_now = round(chp_kw * CHP_LOAD_NOW)
    chp_heat = chp.get("heat_kw_50") or 497
    chp_gas = chp.get("gas_m3h_50") or 109
    heat_need = vent["totals"]["heat_kw"]
    # баланс: СЕС + КГУ → цех, надлишок → накопичувач (до 200 кВт), решта — у мережу
    surplus = pv_now + chp_now - load
    bess_kw = round(max(0.0, min(200.0, surplus)))
    export = round(max(0.0, surplus - bess_kw))
    grid = round(max(0.0, -surplus))
    cards["PV-ROOF"] = dict(rows=[["Модулів", f"{n_mod} × {wp} Вт"], ["Потужність", f"{_fmt(kwp)} кВт пік"],
                                  ["Зараз", f"{_fmt(pv_now)} кВт"], ["Сьогодні", f"{_fmt(pv_today)} кВт·год"],
                                  ["Частка СЕС зараз", f"{round(pv_now / load * 100)} % споживання"]],
                            note="Ряди модулів схід-захід по 10° з проходами 1,5 м для пожежників уздовж рядів "
                                 "клапанів димовидалення й посередині даху; від клапанів — не ближче 2,5 м. "
                                 "Удень разом із когенерацією покриває цех, надлишок заряджає накопичувач.")
    cards["PV-INV"] = dict(rows=[["Інверторів", f"{n_inv} × {inv_kw} кВт"],
                                 ["Навантаження", f"{round(pv_now / (n_inv * inv_kw) * 100)} %"],
                                 ["Стан", "усі в мережі"]])
    cards["CHP"] = dict(rows=[["Потужність", f"{chp_kw} кВт ел. · {chp.get('heat_kw') or 856} кВт тепла"],
                              ["Зараз", f"{chp_now} кВт ел. · {chp_heat} кВт тепла ({round(CHP_LOAD_NOW * 100)} %)"],
                              ["Тепло", f"мережі потрібно {round(heat_need)} кВт, надлишок "
                                        f"{max(0, round(chp_heat - heat_need))} кВт — у сухий охолоджувач"],
                              ["Газ", f"{chp_gas} м³/год (при 100 % — {chp.get('gas_m3h') or 199})"],
                              ["ККД", f"{_fmt((chp.get('eta_el') or 0.425) * 100, 1)} % ел. + "
                                      f"{_fmt((chp.get('eta_th') or 0.455) * 100, 1)} % тепл."],
                              ["Мотогодини", "3 412 · до капремонту 80 000"]],
                        note="Працює паралельно з мережею. Удень, поки світить СЕС, тримає мінімум 50 %, увечері й "
                             "узимку — до 100 %. Тепло йде в теплову мережу цеху, котли на відходах — у резерві "
                             "й на пікові морози. Надлишок електрики — у накопичувач, далі в мережу "
                             "(статус активного споживача).")
    # генератор, АВР, накопичувач
    crit = [c for c in CRITICAL if c in cons]
    crit_kw = sum(cons[c]["p_now"] for c in crit) + energy["lines"]["BW-1"]["p_now"]
    kva, kw = gen.get("kva") or 634, gen.get("power_kw") or 507
    fuel, tank = 0.82, gen.get("tank_l") or 610
    lph = gen.get("fuel_lph_75") or 103.8
    cards["GENSET"] = dict(rows=[["Потужність", f"{kva} кВА / {kw} кВт (основна)"], ["Стан", "резерв, автостарт"],
                                 ["Паливо", f"{round(fuel * 100)} % · {round(fuel * tank)} л"],
                                 ["Автономність", f"≈ {_fmt(fuel * tank / lph, 1)} год при 75 %"],
                                 ["Критичні споживачі зараз", f"{_fmt(crit_kw)} кВт з {kw} кВт"],
                                 ["Остання перевірка", "сьогодні 07:30 — щотижневий пуск 15 хв, норма"]],
                           items=[cons[c]["name"] for c in crit] + [energy["lines"]["BW-1"]["name"]],
                           note="Під час відключення генератор тримає пожежну сигналізацію, освітлення, аспірацію, "
                                "компресори, котельню, офіс із серверною і лінії A–B. Для довгих відключень "
                                "потрібен додатковий паливний бак.")
    cards["ATS-1"] = dict(rows=[["Положення", "Мережа (T1/T2)"], ["Номінал", "1600 А"],
                                ["Переключення", "після пуску генератора, 10–15 с"],
                                ["Останнє спрацювання", "05.10, 18:42 — відключення мережі 2 год 11 хв"]])
    kwh = (bess.get("kwh") or 193.5) * 2
    soc = 0.76
    cards["BESS"] = dict(rows=[["Ємність", f"{_fmt(kwh, 0)} кВт·год (2 шафи)"], ["Потужність", "200 кВт"],
                               ["Заряд", f"{round(soc * 100)} % · {_fmt(kwh * soc)} кВт·год"],
                               ["Зараз", f"заряджається {bess_kw} кВт (надлишок СЕС і КГУ)" if bess_kw
                                         else "очікування"],
                               ["Режим", "зрізання піків понад 600 кВт + резерв на пуск генератора"],
                               ["Тримає критичні", f"≈ {round(kwh * soc / max(crit_kw, 1) * 60)} хв"]])
    # вода
    cards["WATER"] = dict(rows=[["Лічильник", "18 642 м³"], ["Сьогодні", "6,8 м³"], ["Витрата зараз", "2,1 м³/год"],
                                ["Аварійні душі", "перевірка щотижня — 12.10 норма"],
                                ["Шламова вода", "бак очищення заповнений на 64 %"]],
                          note="Ввід із водомірним вузлом; вода йде до водяних завіс фарбування, побутових і "
                               "аварійних душів.")
    # Odoo й мережа
    tabs = tablets()
    cards["ODOO-TABLETS"] = dict(rows=[["Планшетів", str(len(tabs))], ["У мережі", f"{len(tabs) - 1}"],
                                       ["Офлайн", "TAB-VSAW-1 — розряджений (верстат у простої)"]],
                                 note="Оператор бачить завдання, креслення й інструкції, стартує і завершує операцію "
                                      "в Odoo Shop Floor, фіксує брак і простої.")
    cards["ODOO-SCANNERS"] = dict(rows=[["Терміналів", str(len(SCANNERS))], ["Заряд", "92 %, 81 %, 64 %, 57 %, 23 %"],
                                        ["Сьогодні сканувань", "1 486"]],
                                  warn="ТЗД OP-W7 (відвантаження): заряд 23 % — замінити акумулятор.")
    for code, _, _, note in PRINTERS:
        cards[code] = dict(rows=[["Місце", note], ["Друкує", "ZPL з Odoo через IoT Box"],
                                 ["Сьогодні етикеток", {"PRN-RCV": "214", "PRN-PACK1": "96", "PRN-PACK2": "88",
                                                        "PRN-OUT": "41"}[code]]])
    cards["PRN-OUT"]["warn"] = "Закінчується риббон (≈ 8 %) — заміна до кінця зміни."
    last = {"SCALE-OUT1": "412 кг · WH/OUT/00413", "SCALE-OUT2": "388 кг · WH/OUT/00416",
            "SCALE-RCV": "1 920 кг · WH/IN/00129"}
    for code, _, _, note in SCALES:
        cards[code] = dict(rows=[["Місце", note], ["Остання вага", last[code]]])
    for code, _, _, devs in IOT_BOXES:
        cards[code] = dict(rows=[["Пристрої", ", ".join(devs)], ["Стан", "у мережі"]])
    aps = wifi_aps()
    cards["WIFI"] = dict(rows=[["Точок доступу", str(len(aps))], ["У мережі", str(len(aps))],
                               ["Клієнтів зараз", "71 (планшети, ТЗД, навантажувачі, ноутбуки)"]])
    cards["SERVER"] = dict(rows=[["Шафа", "42U"], ["ДБЖ", "від мережі, заряд 100 %"], ["Температура", "22 °C"],
                                 ["Резервна копія", "сьогодні 02:00 — успішно"],
                                 ["Відеоархів", "30 діб, 12 камер"]])
    # охорона, територія
    cards["TURNSTILES"] = dict(rows=[["На території зараз", "146 працівників · 3 відвідувачі"],
                                     ["Сьогодні проходів", "312"],
                                     ["Odoo Attendances", "відмітки входу й виходу щохвилини"]])
    cards["ACCESS"] = dict(rows=[["Дверей з рідерами", str(len(DOOR_READERS))],
                                 ["Останній доступ", "електрощитова, 09:51 — черговий електрик"]])
    cards["CCTV"] = dict(rows=[["Камер", str(len(CAMERAS))], ["Записують", str(len(CAMERAS))], ["Архів", "30 діб"]])
    cards["TRUCK-SCALE"] = dict(rows=[["Остання машина", "АА 4512 КТ · брутто 21 380 кг · WH/OUT/00413"],
                                      ["Сьогодні зважувань", "9"]])
    for code, *_ in GATES:
        cards[code] = dict(rows=[["Стан", "закритий"], ["Сьогодні проїздів", "7" if code == "GATE-W" else "6"]])
    # димовидалення, блискавкозахист
    zones = smoke_zone_vents()
    aa = f"{len(vents)} × {_fmt(VENT_AA, 2)} м² Aa = {_fmt(len(vents) * VENT_AA, 1)} м²"
    cards["SMOKE-VENTS"] = dict(rows=[["Клапанів", aa],
                                      ["Зон димовидалення", f"{len(zones)} (кожна ≤ 1 600 м², між ними — завіси)"],
                                      ["Стан", "закриті"], ["Остання перевірка", "30.09 — усі відкрились за ≤ 60 с"]],
                                items=[f"{c}: {z['area']} м² — {len(z['points'])} клапанів (потрібно {z['need']})"
                                       for c, z in zones.items()],
                                note="Кількість — за орієнтиром 1,5 м² Aa на 400 м² підлоги; в Україні площу визначає "
                                     "розрахунок. Дільниця фарбування — окрема зона.")
    n_panels = math.ceil(len(vents) * 7.5 / 80)
    cards["SMOKE-CTRL"] = dict(rows=[["Щитів", f"{n_panels} × 80 А (по 7,5 А на привод)"],
                                     ["Стан", "норма, живлення від мережі"], ["Акумулятори", "72 год резерву"]])
    cards["LPS"] = dict(rows=[["Опір заземлення", "4,2 Ом (виміряно 14.05.2026)"], ["Крок сітки", f"{_fmt(MESH)} м"]])
    totals = dict(pv_kwp=round(kwp), pv_now=pv_now, pv_today=pv_today, grid_kw=grid, export_kw=export,
                  bess_kw=bess_kw, chp_kw=chp_now, chp_rated=chp_kw, chp_heat=chp_heat, chp_load=CHP_LOAD_NOW,
                  load_kw=round(load), bess_kwh=round(kwh),
                  bess_soc=soc, genset_kva=kva, critical_kw=round(crit_kw), vents=len(vents), n_modules=n_mod,
                  vent_area=round(len(vents) * VENT_AA, 1))
    return dict(cards=cards, totals=totals)
