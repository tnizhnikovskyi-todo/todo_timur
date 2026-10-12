"""Електропостачання: вбудована підстанція 2 × 1000 кВА, ГРЩ біля північної стіни, шинопроводи над
дільницями, кабельні фідери інженерних систем і розрахунок навантажень.

Без Blender: геометрію бере site.py, цифри навантажень — odoo_demo.py, тож схема в 3D і дані
«лічильників» збігаються.

Схема: ввід 10 кВ → комірки СН (RM6) → два сухі трансформатори Т1, Т2 → ГРЩ з двох секцій шин
із секційним вимикачем. Від кожної секції — розподільні шинопроводи над дільницями (з них
відгалужувальні коробки з автоматами й кабелі на верстати) і кабельні фідери. Секції працюють
окремо; коли один трансформатор вимкнено, секційний вимикач замикається й увесь завод живиться
від другого (тому кожен трансформатор узято з запасом на все навантаження).
"""
import math

from .equipment import NOMINAL_MM, ROLE_BY_CODE
from .layout import FOOTPRINT, MACHINES, STATUS
from .lighting import layout as light_layout
from .lighting import LIGHT_ZONES, PANELS, load_lux_norms, panels_load
from .ventilation import ROOFVENTS, ventilation_data

U_LV = 400  # В, низька сторона
BUS_Z = 6.2  # висота розподільних шинопроводів (низ ферм 8,4; аспірація 7,6; світильники 7,7)
TRAY_Z, TRAY_Y = 5.0, 71.82  # кабельний лоток уздовж північної стіни (за стояками шинопроводів)
CABLE_Z = 5.6  # кабелі від відгалужувальних коробок ідуть під шинопроводом

# Електрощитова: сітчасте огородження в кутку складу ГП біля північної стіни
ROOM = (122.4, 62.4, 135.6, 71.7)
SWB_X0, SWB_Y, SWB_D, SWB_H = 125.6, 71.6, 0.6, 2.0  # ГРЩ: лівий край, вісь шаф по Y, глибина, висота
PFC_H = 2.2  # шафи компенсації VarSet вищі за шафи PrismaSeT P
RM6_POS = (123.75, 71.5)  # комірки 10 кВ
TRAFO_Y = 64.4
EMS_POS = (129.7, 66.8)  # АРМ енергетика

# Шафи ГРЩ із заходу на схід: code, назва, ширина (м, з ряду PrismaSeT P 650/800), тип, що живить
SWB_CELLS = [
    ("PFC-1", "Компенсація реактивної потужності · секція 1", 0.8, "pfc", None),
    ("Q1", "Ввід 1 · від трансформатора Т1", 0.8, "incomer", "T1"),
    ("QF-3", "Фідер ШР-3 · дільниця фасадів", 0.65, "feeder", "BW-3"),
    ("QF-2", "Фідер ШР-2 · лінії C–D, нестинг", 0.65, "feeder", "BW-2"),
    ("QF-C1", "Кабельні фідери: компресорна, аспірація, котельня", 0.65, "cable", "C1"),
    ("QS", "Секційний вимикач", 0.8, "coupler", None),
    ("QF-1", "Фідер ШР-1 · лінії A–B, сортування", 0.65, "feeder", "BW-1"),
    ("QF-4", "Фідер ШР-4 · збирання й пакування", 0.65, "feeder", "BW-4"),
    ("QF-C2", "Кабельні фідери: зарядна, освітлення, офіс, вентиляція", 0.65, "cable", "C2"),
    ("Q2", "Ввід 2 · від трансформатора Т2", 0.8, "incomer", "T2"),
    ("PFC-2", "Компенсація реактивної потужності · секція 2", 0.8, "pfc", None),
]


def cell_x():
    """Центр кожної шафи ГРЩ по X."""
    out, x = {}, SWB_X0
    for code, _, w, *_ in SWB_CELLS:
        out[code] = x + w / 2
        x += w
    return out


CELL_X = cell_x()
SWB_X1 = SWB_X0 + sum(c[2] for c in SWB_CELLS)
SECTION = {}  # шафа → секція шин 1/2 (до й після секційного вимикача)
_s = 1
for _c in SWB_CELLS:
    if _c[3] == "coupler":
        _s = 2
        continue
    SECTION[_c[0]] = _s
TRAFOS = {"T1": (CELL_X["Q1"], TRAFO_Y), "T2": (CELL_X["Q2"], TRAFO_Y)}


def _bus_path(feeder, d, tail):
    """Підйом із шафи, вздовж стіни на захід, потім спільною трасою на південь (x≈121–122)."""
    x = CELL_X[feeder]
    return [(x, SWB_Y - 0.2), (x, 70.0 - d), (120.8 + d, 70.0 - d)] + tail


# Розподільні шинопроводи. Порядок зсувів d підібрано так, щоб траси не перетинались.
BUSWAYS = [
    dict(code="BW-1", name="ШР-1 · лінії A–B, сортування", feeder="QF-1", rating=630, d=0.8,
         path=_bus_path("QF-1", 0.8, [(121.6, 46.8), (92.4, 46.8), (92.4, 9.5), (44.9, 9.5)])),
    dict(code="BW-2", name="ШР-2 · лінії C–D, нестинг, портал", feeder="QF-2", rating=630, d=0.4,
         path=_bus_path("QF-2", 0.4, [(121.2, 47.2), (92.0, 47.2), (92.0, 27.5), (44.9, 27.5)])),
    dict(code="BW-3", name="ШР-3 · дільниця фасадів МДФ", feeder="QF-3", rating=630, d=0.0,
         path=_bus_path("QF-3", 0.0, [(120.8, 47.6), (91.6, 47.6), (91.6, 56.0), (42.8, 56.0)])),
    dict(code="BW-4", name="ШР-4 · збирання й пакування", feeder="QF-4", rating=630, d=1.2,
         path=_bus_path("QF-4", 1.2, [(122.0, 17.0), (93.0, 17.0)])),
]
BUS_BY_CODE = {b["code"]: b for b in BUSWAYS}


def bus_for(code, x, y):
    if code == "GANTRY-1":
        return "BW-2"
    if y > 46:
        return "BW-3"
    if x > 92:
        return "BW-4"
    return "BW-1" if y < 18.5 else "BW-2"


def _rot(lx, ly, rz):
    a = math.radians(rz)
    return lx * math.cos(a) - ly * math.sin(a), lx * math.sin(a) + ly * math.cos(a)


def taps():
    """Відгалуження від шинопроводів: {code: dict(bus, tap=(x, y), conn=(x, y, z))}.
    tap — коробка на шинопроводі; conn — точка, де кабель заходить у шафу керування верстата."""
    by_bus = {}
    for m in MACHINES:
        code, typ, _, x, y = m[:5]
        rz = m[6] if len(m) > 6 else 0
        bus = bus_for(code, x, y)
        fx, fy = FOOTPRINT[typ]
        if rz % 180:
            fx, fy = fy, fx
        by_bus.setdefault(bus, []).append((code, typ, x, y, fx, fy))
    by_bus["BW-2"].append(("GANTRY-1", None, 44.3, 27.5, 0.0, 0.0))
    out = {}
    for bus, items in by_bus.items():
        b = BUS_BY_CODE[bus]
        (xa, ya), (xb, _) = b["path"][-2], b["path"][-1]  # остання ділянка — уздовж X над дільницею
        yb_ = ya
        lo, hi = min(xa, xb) + 0.4, max(xa, xb) - 0.4
        last = -1e9
        for code, typ, x, y, fx, fy in sorted(items, key=lambda t: (t[2], t[3])):
            tx = max(lo, min(hi, x))
            if tx - last < 0.7:  # кілька верстатів з однаковим X — коробки поруч
                tx = last + 0.7
            last = tx
            if typ is None:  # портал: живлення на кінець колії через кабельний ланцюг
                out[code] = dict(bus=bus, tap=(tx, yb_), conn=(44.3, 27.5, 6.2))
                continue
            h = NOMINAL_MM.get(typ, (0, 0, 2200))[2] / 1000 * 0.85 if typ in NOMINAL_MM else 1.6
            inset = min(0.5, fy / 4)
            if y - fy / 2 < yb_ < y + fy / 2:  # шинопровід над верстатом — кабель прямо вниз
                cy = yb_
            else:
                cy = y + fy / 2 - inset if yb_ > y else y - fy / 2 + inset
            cx = max(x - fx / 2 + 0.4, min(x + fx / 2 - 0.4, tx))
            out[code] = dict(bus=bus, tap=(tx, yb_), conn=(cx, cy, max(1.2, h)))
    return out


# --------------------------------------------------------------------------
# Навантаження. Встановлена потужність — з паспорта (connected_kw у equipment_specs.json), якщо
# виробник її публікує; інакше оцінка за аналогами (так і позначено в даних).
# --------------------------------------------------------------------------
ESTIMATE_KW = {  # роль → кВт (оцінка: сума двигунів, нагрівачів і керування типових конфігурацій)
    "beam_saw": 24, "beam_saw_book": 45, "sliding_table_saw": 7.5, "vertical_panel_saw": 6,
    "nesting_cnc": 45, "board_storage": 15, "edgebander_laser": 60, "edgebander": 28,
    "robot_return": 7.5, "ptp_cnc": 22, "throughfeed_drilling": 25, "dowel_inserting": 11,
    "hinge_insertion": 1.1, "sorting_cell": 20, "wide_belt_sander": 30, "membrane_press": 28,
    "glue_spray_booth": 2.2, "manual_spray_booth": 5.1, "automatic_spraying": 18, "drying": 17,
    "uv_line": 2.9, "uv_oven": 56, "case_clamp_auto": 8, "case_clamp_manual": 1.5, "box_machine": 10,
    "stretch_wrapper": 1.9, "shrink_line": 19.75, "strapping": 0.2, "compressor": 37,
    "dust_extraction": 75, "biomass_boiler": 5, "briquetting_press": 15, "charger": 4.5,
}
# Коефіцієнт завантаження в роботі (середнє за 15 хв) і cos φ за типом навантаження
PROFILE = {
    "saw": (0.55, 0.84), "saw_book": (0.6, 0.84), "slide": (0.45, 0.82), "vsaw": (0.4, 0.82),
    "nest": (0.55, 0.9), "edge": (0.65, 0.9), "edge_robot": (0.65, 0.9), "cnc": (0.5, 0.9),
    "bore": (0.5, 0.88), "dowel": (0.45, 0.86), "hinge": (0.3, 0.85), "sortbot": (0.45, 0.9),
    "sand": (0.7, 0.85), "press": (0.6, 0.97), "glue": (0.7, 0.85), "spray": (0.75, 0.85),
    "autospray": (0.6, 0.88), "dry": (0.75, 0.95), "uv": (0.7, 0.95), "asmline": (0.4, 0.86),
    "asm": (0.35, 0.85), "box": (0.45, 0.88), "pack": (0.4, 0.85), "packline": (0.65, 0.97),
}
IDLE_K = {"edge": 0.3, "edge_robot": 0.3, "uv": 0.08, "press": 0.35, "dry": 0.6}  # підігрів у простої
IDLE_DEFAULT, STOP_K = 0.12, 0.03

# Інженерні споживачі на кабельних фідерах: code, назва, фідер, роль|None, кількість, кВт (якщо без ролі),
# завантаження, cos φ, пояснення
UTILITIES = [
    ("COMPRESSOR", "Компресорна (2 × GA 37 VSD+, осушувач)", "C1", "compressor", 2, None, 0.63, 0.95,
     "Частотні компресори: навантаження = завантаження станції."),
    ("DUST-1", "Вентилятори аспірації", "C1", "dust_extraction", 2, None, 0.85, 0.88,
     "Два фільтри NESTRO NKJ на 29 800 м³/год сумарно."),
    ("BOILER", "Котельня (2 котли), шнеки, брикетування", "C1", "biomass_boiler", 2, None, 0.4, 0.85,
     "Два котли каскадом (зараз працює один), подача палива, брикетувальний прес."),
    ("CHARGING", "Зарядна станція (3 зарядні пристрої)", "C2", "charger", 3, None, 0.67, 0.95,
     "Зайнято 2 з 3 постів."),
    ("OFFICE", "Офіс, побутові приміщення, серверна", "C2", None, 1, 32.0, 0.55, 0.92,
     "Оцінка: кондиціонування, ІТ, кухня."),
]
CABLE_FEEDERS = {"C1": ("QF-C1", "Кабельні фідери 1"), "C2": ("QF-C2", "Кабельні фідери 2")}


def _h(*xs, mod=1000):
    h = 2166136261
    for ch in "|".join(map(str, xs)):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % mod


def installed_kw(role, specs, units=1):
    """(кВт, джерело): паспорт виробника або оцінка."""
    rec = specs.get(role) if role else None
    if rec and isinstance(rec.get("connected_kw"), (int, float)):
        return rec["connected_kw"] * units, "passport"
    return ESTIMATE_KW.get(role, 0) * units, "estimate"


def amps(p_kw, cos_phi):
    return p_kw * 1000 / (math.sqrt(3) * U_LV * cos_phi) if p_kw else 0.0


FAN_ROLE = {"ahu": "make_up_ahu", "exfan": "ex_fan"}


def consumers(specs):
    """Усі споживачі: {code: dict(name, feeder, bus|None, p_inst, p_now, cos_phi, i_now, source)}."""
    out = {}
    tp = taps()
    for m in MACHINES:
        code, typ, name = m[:3]
        role = ROLE_BY_CODE.get(code)
        p, src = installed_kw(role, specs)
        extra = {"EDGE-1": ["robot_return"], "UV-1": ["uv_oven"], "PACKLINE-1": ["strapping"]}.get(code, [])
        for r in extra:
            pe, se = installed_kw(r, specs)
            p += pe
            src = src if se == src else "mixed"
        kf, pf = PROFILE.get(typ, (0.5, 0.86))
        st = STATUS[code]
        k = {"work": kf * (0.9 + _h(code, mod=21) / 100), "idle": IDLE_K.get(typ, IDLE_DEFAULT),
             "stop": STOP_K}[st]
        bus = tp[code]["bus"]
        out[code] = dict(name=name, feeder=BUS_BY_CODE[bus]["feeder"], bus=bus, p_inst=round(p, 1),
                         p_now=round(p * k, 1), cos_phi=pf, source=src, status=st)
    p, src = installed_kw("board_storage", specs)
    out["GANTRY-1"] = dict(name="Портальний склад плит", feeder="QF-2", bus="BW-2", p_inst=round(p, 1),
                           p_now=round(p * 0.35, 1), cos_phi=0.86, source=src, status="work")
    for code, name, cf, role, units, kw, load, pf, note in UTILITIES:
        if role:
            p, src = installed_kw(role, specs, units)
            if code == "BOILER":
                p2, s2 = installed_kw("briquetting_press", specs)
                p, src = p + p2, src if s2 == src else "mixed"
        else:
            p, src = kw, "estimate"
        out[code] = dict(name=name, feeder=CABLE_FEEDERS[cf][0], bus=None, p_inst=round(p, 1),
                         p_now=round(p * load, 1), cos_phi=pf, source=src, status="work", note=note)
    lt = light_layout(specs, load_lux_norms())
    for code, pl in panels_load(lt).items():
        out[code] = dict(name=pl["name"], feeder="QF-C2", bus=None, p_inst=pl["p_inst"], p_now=pl["p_now"],
                         cos_phi=0.95, source="passport" if specs.get("highbay", {}).get("watt") else "estimate",
                         status="work", group="light",
                         note=f"{pl['n']} світильників; диммування DALI за присутністю й денним світлом.")
    vu = ventilation_data(specs)["units"]
    rv = [u for u in vu.values() if u["kind"] == "roofvent"]
    out["RV-ALL"] = dict(name=f"Дахові установки вентиляції ({len(rv)} шт.)", feeder="QF-C2", bus=None,
                         p_inst=round(sum(u["p_inst"] for u in rv), 1), p_now=round(sum(u["p_now"] for u in rv), 1),
                         cos_phi=0.95, source="passport" if specs.get("roofvent", {}).get("power_kw") else "estimate",
                         status="work", group="vent", note="Вентилятори з ЕС-двигунами, витрата — за датчиками CO₂.")
    for code, u in vu.items():
        if u["kind"] != "roofvent":
            out[code] = dict(name=u["name"], feeder="QF-C2", bus=None, p_inst=u["p_inst"], p_now=u["p_now"],
                             cos_phi=0.95, source="passport" if specs.get(
                                 FAN_ROLE.get(u["kind"], "wall_fan"), {}).get("power_kw")
                             else "estimate",
                             status="work" if u["state"] == "on" else "idle", group="vent")
    for c in out.values():
        c["i_now"] = round(amps(c["p_now"], c["cos_phi"]))
    return out


# --------------------------------------------------------------------------
# Дані «лічильників»: секції, лінії, трансформатори, профіль доби, журнал подій
# --------------------------------------------------------------------------
TRAFO_KVA = 1000
COS_TARGET = 0.97  # уставка регуляторів компенсації
TARIFF = 8.4  # грн/кВт·год — умовний тариф для демо
PFC_KVAR = 350


def _q(p, cos_phi):
    return p * math.tan(math.acos(cos_phi))


def lines(cons):
    """Лінії від ГРЩ: шинопроводи й кабельні групи з їхніми споживачами."""
    out = {}
    for b in BUSWAYS:
        out[b["code"]] = dict(kind="busway", name=b["name"], cell=b["feeder"], rating_a=b["rating"],
                              consumers=[c for c, v in cons.items() if v["bus"] == b["code"]])
    for code, (cell, name) in CABLE_FEEDERS.items():
        out[code] = dict(kind="cable", name=name, cell=cell, rating_a=630 if code == "C1" else 400,
                         consumers=[c for c, v in cons.items() if v["feeder"] == cell])
    for ln in out.values():
        cs = [cons[c] for c in ln["consumers"]]
        p = sum(c["p_now"] for c in cs)
        q = sum(_q(c["p_now"], c["cos_phi"]) for c in cs)
        ln.update(p_inst=round(sum(c["p_inst"] for c in cs), 1), p_now=round(p, 1),
                  cos_phi=round(p / math.hypot(p, q), 2) if p else 1.0,
                  i_now=round(math.hypot(p, q) * 1000 / (math.sqrt(3) * U_LV)))
        ln["load"] = round(ln["i_now"] / ln["rating_a"], 3)
        for c in ln["consumers"]:
            cons[c]["line"] = next(k for k, v in out.items() if v is ln)
    return out


def section_of_line(ln):
    return SECTION[ln["cell"]]


def energy_data(specs, now_h=10.5):
    cons = consumers(specs)
    lns = lines(cons)
    sections = {}
    for s in (1, 2):
        ls = [ln for ln in lns.values() if section_of_line(ln) == s]
        p = sum(ln["p_now"] for ln in ls)
        q = sum(_q(ln["p_now"], ln["cos_phi"]) for ln in ls)
        q_comp = max(0.0, q - _q(p, COS_TARGET))
        q_after = q - q_comp
        s_kva = math.hypot(p, q_after)
        sections[s] = dict(p=p, q=q, q_comp=q_comp, s=s_kva, cos_before=p / math.hypot(p, q),
                           cos_after=p / s_kva)
    trafos = {}
    for s, t in ((1, "T1"), (2, "T2")):
        sec = sections[s]
        trafos[t] = dict(name=f"Трансформатор {t}", rating_kva=TRAFO_KVA, section=s,
                         p_kw=round(sec["p"], 1), s_kva=round(sec["s"]), load=round(sec["s"] / TRAFO_KVA, 3),
                         i_a=round(sec["s"] * 1000 / (math.sqrt(3) * U_LV)),
                         temp_c=round(38 + 60 * sec["s"] / TRAFO_KVA), cos_phi=round(sec["cos_after"], 2),
                         incomer="Q1" if s == 1 else "Q2")
    cells = {}
    for code, name, _, typ, feeds in SWB_CELLS:
        c = dict(name=name, type=typ, section=SECTION.get(code), feeds=feeds)
        if typ == "incomer":
            t = trafos[feeds]
            c.update(i_now=t["i_a"], p_now=t["p_kw"], rating_a=1600, state="on")
        elif typ == "coupler":
            c.update(rating_a=1600, state="off", note="Розімкнений: секції живляться кожна від свого "
                     "трансформатора. АВР замкне його, якщо зникне напруга на одному з вводів.")
        elif typ == "pfc":  # VarSet 350 квар: ступені 50 + 3 × 100
            sec = sections[1 if code == "PFC-1" else 2]
            q_on = min(PFC_KVAR, round(sec["q_comp"] / 50) * 50)
            c.update(rating_kvar=PFC_KVAR, q_now=q_on, steps="50 + 3 × 100 квар",
                     cos_before=round(sec["cos_before"], 2), cos_after=round(sec["cos_after"], 2))
        else:
            ln = next(v for v in lns.values() if v["cell"] == code)
            line = next(k for k, v in lns.items() if v is ln)
            c.update(line=line, i_now=ln["i_now"], p_now=ln["p_now"], rating_a=ln["rating_a"],
                     state="on")
        cells[code] = c
    p_now = sum(s["p"] for s in sections.values())
    q_before = sum(s["q"] for s in sections.values())
    q_after = sum(s["q"] - s["q_comp"] for s in sections.values())
    profile, typical = day_profile(cons, now_h)
    kwh_today = round(sum(v for v in profile if v is not None))
    peak = max(v for v in profile if v is not None)
    return dict(
        meta=dict(source="Лічильники PowerLogic на вводах і фідерах ГРЩ → Modbus TCP → Odoo IoT (демо)",
                  u_kv="10 / 0,4", tariff_uah=TARIFF,
                  note="Встановлена потужність — з паспортів виробників, де вони її публікують; решта — "
                       "оцінка за аналогами (позначено). Поточна — розрахунок за станом верстатів."),
        totals=dict(p_inst=round(sum(c["p_inst"] for c in cons.values())), p_now=round(p_now),
                    s_now=round(math.hypot(p_now, q_after)),
                    cos_before=round(p_now / math.hypot(p_now, q_before), 2),
                    cos_after=round(p_now / math.hypot(p_now, q_after), 2),
                    kwh_today=kwh_today, peak_kw=round(peak * 1.06), peak_time="09:15",
                    cost_today=round(kwh_today * TARIFF), capacity_kva=2 * TRAFO_KVA),
        transformers=trafos, cells=cells, lines=lns, consumers=cons,
        profile=profile, typical=typical, events=events(cons))


def day_profile(cons, now_h):
    """Середня потужність по годинах: сьогодні до now_h і типовий робочий день (дві зміни)."""
    prod = sum(c["p_now"] for c in cons.values() if c["bus"])
    util = {k: cons[k]["p_now"] for k in ("COMPRESSOR", "DUST-1", "BOILER", "CHARGING", "OFFICE")}
    util["LIGHT"] = sum(c["p_now"] for c in cons.values() if c.get("group") == "light")
    util["HVAC"] = sum(c["p_now"] for c in cons.values() if c.get("group") == "vent")
    night = (0.25 * util["LIGHT"] + 0.35 * util["HVAC"] + util["BOILER"] + 0.25 * util["OFFICE"]
             + 1.3 * util["CHARGING"] + 0.06 * util["COMPRESSOR"] + 0.03 * prod)
    work = prod + sum(util.values())

    def at(h):
        if h < 6:
            return night
        if h < 7:
            return night + 0.35 * (work - night)
        if 11.5 <= h < 12:
            return 0.62 * work
        if h < 15.5:
            return work * (0.94 + 0.04 * math.sin(h * 1.7))
        if h < 23:
            return 0.72 * work * (0.96 + 0.03 * math.sin(h))
        return night + 0.3 * (work - night)

    typical = [round(sum(at(h + k / 4) for k in range(4)) / 4) for h in range(24)]
    today = []
    for h in range(24):
        if h + 1 <= now_h:
            today.append(round(typical[h] * (0.97 + _h("d", h, mod=7) / 100)))
        elif h < now_h:  # поточна година — частково
            today.append(round(work * (now_h - h)))
        else:
            today.append(None)
    return today, typical


def events(cons):
    cnc2 = f"{cons['CNC-2']['p_now']:.1f}".replace(".", ",")
    return [
        dict(time="2026-10-12 09:42", level="bad", code="CNC-2",
             text=f"CNC-2: аварійна зупинка, споживання впало до {cnc2} кВт."),
        dict(time="2026-10-12 09:15", level="warn", code="SWB-1",
             text="Пік 15-хвилинної потужності за добу; ліміт договірної потужності не перевищено."),
        dict(time="2026-10-12 08:05", level="info", code="PFC-2",
             text="Компенсація секції 2: увімкнено ще один ступінь 50 квар, cos φ 0,97."),
        dict(time="2026-10-12 07:02", level="info", code="DUST-1",
             text="Пуск вентиляторів аспірації з частотного перетворювача, пусковий струм у нормі."),
        dict(time="2026-10-12 06:55", level="info", code="SWB-1",
             text="Підготовка до зміни: увімкнено освітлення цеху й компресори."),
        dict(time="2026-10-11 22:40", level="info", code="CHARGING",
             text="Нічне заряджання АКБ навантажувачів за нічним тарифом."),
    ]


# Паспорти обладнання електропостачання: код об'єкта → (роль, допоміжні ролі у складі)
ENERGY_ROLES = {"RM6-1": ("substation", []), "T1": ("transformer", ["busbar_main"]),
                "T2": ("transformer", ["busbar_main"]), "SWB-1": ("main_switchboard", ["acb", "power_meter"]),
                "Q1": ("acb", ["power_meter"]), "Q2": ("acb", ["power_meter"]), "QS": ("acb", []),
                "PFC-1": ("pfc", []), "PFC-2": ("pfc", []), "EMS-1": ("power_meter", []),
                "GENSET": ("genset", [])}
for _b in BUSWAYS:
    ENERGY_ROLES[_b["code"]] = ("busbar_dist", ["tapoff"])
    ENERGY_ROLES[_b["feeder"]] = ("main_switchboard", ["power_meter"])
for _c in CABLE_FEEDERS.values():
    ENERGY_ROLES[_c[0]] = ("main_switchboard", ["power_meter"])
# освітлення й вентиляція
for _z, _t, _kind, *_ in LIGHT_ZONES:
    ENERGY_ROLES["LT-" + _z[2:]] = (_kind, ["lighting_control"])
for _p in PANELS:
    ENERGY_ROLES[_p[0]] = ("lighting_control", [])
ENERGY_ROLES["EMERGENCY"] = ("emergency", [])
for _r in ROOFVENTS:
    ENERGY_ROLES[_r[0]] = ("roofvent", [])
ENERGY_ROLES["AHU-1"] = ("make_up_ahu", ["fabric_duct"])
for _f in ("EF-ELEC", "EF-CMP"):  # для зарядної потрібен вибухозахищений вентилятор — окремо
    ENERGY_ROLES[_f] = ("wall_fan", [])
ENERGY_ROLES["EF-CHG"] = ("ex_fan", [])  # водень: вибухозахищене виконання


def energy_passport(code, specs):
    role, extra = ENERGY_ROLES.get(code, (None, []))
    if role not in specs:
        return None
    main = dict(specs[role])
    main["units"] = [specs[r] for r in extra if r in specs]
    return main


def passport_energy(specs):
    return {c: pp for c in ENERGY_ROLES if (pp := energy_passport(c, specs))}
