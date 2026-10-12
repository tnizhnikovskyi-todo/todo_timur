"""Геометрія інфраструктури: евакуація, димовидалення, блискавкозахист, резервне живлення й СЕС,
вода й стоки, робочі місця Odoo й мережа, територія, охорона й доступ."""
import math

from .evacuation import EXITS
from .evacuation import compute as evac_compute
from .evacuation import save as evac_save
from .geom import Mesh, empty, instance, rounded_path, shared
from .infra import (ATS_POS, BESS_POS, CAMERAS, CHP_COOLER_POS, CHP_EXH_POS, CHP_GRP_POS, CHP_HEAT_Y, CHP_HEAT_Z,
                    CHP_POS, CURTAIN_BOTTOM, CURTAINS, DOOR_READERS, EYEWASH, GATES, GENSET_POS, IOT_BOXES, KPP, MESH,
                    MODULE, PARKING, PRINTERS, PV_INVERTERS_X, PV_TILT, ROOF_Z, SCALES, SCANNERS, SERVER_ROOM, SITE,
                    SMOKE_PANEL, TRUCK_SCALE, VENT, WASTE, WASTEWATER, WATER_INLET, WATER_MAIN, down_conductors,
                    pv_rows, smoke_vents, tablets, wifi_aps)
from .layout import D, H, OBST, W


def _passport_extra(code):
    from .energy import energy_passport
    from .site import SPECS
    pp = energy_passport(code, SPECS)
    return {"maker": pp["manufacturer"], "model": pp["model"]} if pp else {}


# ---------------------------------------------------------------- евакуація
def build_evacuation():
    data = evac_compute(OBST)
    evac_save(data)
    d = Mesh()
    for code, x, y, side in EXITS:
        out = -1 if side == "S" else 1  # назовні
        inner = 0.0 if side == "S" else D  # внутрішня грань стіни
        wy = inner + out * 0.15  # вісь стіни товщиною 0,3 м
        if side == "S":  # південна стіна в моделі зрізана до парапета — біля дверей лишаємо її фрагмент
            for k in (-1, 1):
                d.box_lo(x + k * 1.0, wy, 1.0, 0.6, 0.3, 1.9, "wall")
            d.box_lo(x, wy, 2.3, 1.4, 0.3, 0.6, "wall")
            d.box_lo(x, wy, 2.9, 2.62, 0.32, 0.06, "wall_band")
        for k in (-1, 1):  # коробка по зовнішній грані
            d.box_lo(x + k * 0.65, inner + out * 0.27, 0, 0.1, 0.08, 2.25, "steel_dark")
        d.box_lo(x, inner + out * 0.27, 2.2, 1.4, 0.08, 0.1, "steel_dark")
        d.box_lo(x, inner + out * 0.25, 0.0, 1.2, 0.05, 2.2, "machine_mid")  # полотно, відчиняється назовні
        d.box_lo(x + 0.45, inner + out * 0.29, 0.95, 0.03, 0.04, 0.2, "steel")  # ручка ззовні
        d.box_lo(x, inner + out * 0.17, 1.0, 1.0, 0.05, 0.06, "steel")  # антипанічна штанга з боку цеху
        for k in (-1, 1):
            d.box_lo(x + k * 0.48, inner + out * 0.2, 0.98, 0.04, 0.06, 0.1, "steel")
        d.box_lo(x, inner - out * 0.03, 2.4, 0.42, 0.05, 0.18, "exit_green")  # «Вихід» над дверима всередині
    d.build("EXITS", "evacuation", code="EXITS", kind="safety", label="Аварійні виходи",
            desc="Двері з антипанічними штангами на обох довгих стінах; над кожними — покажчик «Вихід».")
    # маршрути евакуації — зелені стрілки на підлозі
    for zone, r in data["routes"].items():
        m = Mesh()
        pts = r["path"]
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            n = max(1, int(L / 2.5))
            for k in range(n):
                t = (k + 0.5) / n
                px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                m.box((px, py, 0.018), (0.6, 0.12, 0.012), "exit_green", rz=ang + 35)
                m.box((px, py, 0.018), (0.6, 0.12, 0.012), "exit_green", rz=ang - 35)
        m.build("EVAC-" + zone[2:], "evacuation", code="EVAC-" + zone[2:], kind="safety",
                label=f"Шлях евакуації · {r['name']}", desc=f"До виходу {r['exit']}: {r['length']} м.")


# ---------------------------------------------------------------- димовидалення
def build_smoke():
    vx, vy = VENT

    def vent(m):  # LAMILUX F100: скляний ліхтар 1200 × 1200 на обичайці, привод 24 В
        m.box_lo(0, 0, ROOF_Z, vx + 0.24, vy + 0.24, 0.5, "machine_mid")
        m.box((0, 0, ROOF_Z + 0.58), (vx, vy, 0.06), "guard_glass", rot=(0, 4, 0))
        m.box_lo(0, -vy / 2 - 0.06, ROOF_Z + 0.2, 0.3, 0.1, 0.22, "fire_red")
    me = shared("smoke_vent", vent)
    root = empty("SMOKE-VENTS", "smoke", code="SMOKE-VENTS", kind="safety", label="Клапани димовидалення",
                 desc="Природне видалення диму й тепла: відчиняються від пожежної сигналізації або кнопок.",
                 **_passport_extra("SMOKE-VENTS"))
    for i, (x, y) in enumerate(smoke_vents(), 1):
        instance(f"SV-{i:02d}", "smoke", me, parent=root, loc=(x, y, 0))
    p = Mesh()
    px, py = SMOKE_PANEL
    n_panels = math.ceil(len(smoke_vents()) * 7.5 / 80)  # D+H CPS-M1: 80 А, привод 7,5 А
    for k in range(n_panels):
        cx = px + (k - (n_panels - 1) / 2) * 0.72
        p.box_lo(cx, py - 0.15, 0.9, 0.66, 0.3, 0.9, "machine_accent", bev=0.02)
        p.box_lo(cx, py - 0.31, 1.55, 0.2, 0.01, 0.1, "screen_on")
    cu = Mesh()
    for (ax, ay), (bx, by) in CURTAINS:  # димові завіси між зонами
        cu.box_lo((ax + bx) / 2, (ay + by) / 2, CURTAIN_BOTTOM, abs(bx - ax) or 0.02, abs(by - ay) or 0.02,
                  H - CURTAIN_BOTTOM, "smoke_curtain")
    cu.build("SMOKE-CURTAINS", "smoke", code="SMOKE-CURTAINS", kind="safety", label="Димові завіси",
             desc="Негорюча тканина від покрівлі до 7,9 м: ділить цех на зони димовидалення ≤ 1 600 м².")
    p.build("SMOKE-CTRL", "smoke", code="SMOKE-CTRL", kind="safety", label="Щит керування димовидаленням",
            desc="Живить приводи клапанів 24 В з акумуляторами на 72 год; команда — від пожежного приладу.",
            **_passport_extra("SMOKE-CTRL"))


# ---------------------------------------------------------------- блискавкозахист
def build_lightning():
    m = Mesh()
    z = ROOF_Z + 0.1
    xs = [k * MESH for k in range(int(W / MESH) + 1)] + [W]
    ys = [k * MESH for k in range(int(D / MESH) + 1)] + [D]
    for x in xs:
        m.box((x, D / 2, z), (0.02, D, 0.02), "galv")
    for y in ys:
        m.box((W / 2, y, z), (W, 0.02, 0.02), "galv")
    for x, y in down_conductors():
        top = ROOF_Z + 0.1 if 0 < y < D else (1.0 if y < 0 else ROOF_Z + 0.1)  # південна стіна в моделі зрізана
        m.box_lo(x, y, 0, 0.02, 0.02, top, "galv")
        m.box_lo(x, y, 0.4, 0.08, 0.05, 0.12, "steel_dark")  # вимірювальний з'єднувач
    m.box((W / 2, -1.0, 0.012), (W + 2, 0.04, 0.01), "steel_dark")  # контур заземлення
    m.box((W / 2, D + 1.0, 0.012), (W + 2, 0.04, 0.01), "steel_dark")
    m.box((-1.0, D / 2, 0.012), (0.04, D + 2, 0.01), "steel_dark")
    m.box((W + 1.0, D / 2, 0.012), (0.04, D + 2, 0.01), "steel_dark")
    from .ventilation import ROOFVENTS
    for _, x, y, _ in ROOFVENTS:  # стрижні над установками на даху
        m.box_lo(x + 1.4, y, ROOF_Z + 2.1, 0.02, 0.02, 1.5, "galv")
    m.build("LPS", "lightning", code="LPS", kind="safety", label="Блискавкозахист",
            desc="Сітка на покрівлі, стрижні над установками, струмовідводи по стінах із вимірювальними "
                 "з'єднувачами й контур заземлення навколо будівлі.", **_passport_extra("LPS"))


# ---------------------------------------------------------------- резервне живлення й СЕС
def build_backup():
    g = Mesh()
    gx, gy = GENSET_POS
    g.box_lo(gx, gy, 0, 5.4, 2.0, 0.15, "steel_dark")  # фундаментна плита
    g.box_lo(gx, gy, 0.15, 5.031, 1.69, 2.522, "machine_accent", bev=0.05)  # D700 у кожусі M230: 5031 × 1690 × 2672
    for k in range(6):
        g.box_lo(gx - 2.0 + k * 0.7, gy - 0.85, 0.6, 0.5, 0.02, 1.5, "steel_dark")  # жалюзі
    g.cyl((gx + 2.0, gy + 0.4, 3.2), 0.15, 1.0, "steel", segs=14)  # вихлоп
    g.tube(rounded_path([(gx - 2.4, gy - 0.7, 0.5), (gx - 3.0, D + 0.5, 0.5), (gx - 3.0, D + 0.5, 0.05),
                         (ATS_POS[0], D + 0.5, 0.05)], radius=0.3), 0.06, "rubber", segs=8)
    g.build("GENSET", "backup", code="GENSET", kind="power", label="Дизель-генератор",
            desc="Шумозахищений контейнер; за 10–15 с після зникнення мережі АВР переводить на нього "
                 "критичні споживачі.", **_passport_extra("GENSET"))
    a = Mesh()
    ax, ay = ATS_POS
    a.box_lo(ax, ay, 0, 0.6, 0.8, 2.0, "elec_cab", bev=0.02)
    a.box_lo(ax - 0.31, ay, 1.4, 0.01, 0.3, 0.15, "screen_on")
    a.build("ATS-1", "backup", code="ATS-1", kind="power", label="Шафа АВР",
            desc="Автоматичне введення резерву: мережа ↔ генератор для секції критичних споживачів.",
            **_passport_extra("ATS-1"))
    b = Mesh()
    bx, by = BESS_POS
    b.box_lo(bx + 1.4, by, 0, 5.8, 1.6, 0.15, "steel_dark")
    for k in range(2):  # дві шафи LUNA2000-200KWH: 2570 × 1200 × 2135 мм
        cx = bx + k * 2.8
        b.box_lo(cx, by, 0.15, 2.57, 1.2, 2.135, "phenolic", bev=0.04)
        b.box_lo(cx - 0.8, by - 0.61, 1.4, 0.3, 0.01, 0.15, "screen_on")
    b.build("BESS", "backup", code="BESS", kind="power", label="Накопичувач енергії",
            desc="Літій-залізо-фосфатний накопичувач: зрізає піки й тримає критичні споживачі, поки "
                 "запускається генератор.", **_passport_extra("BESS"))
    # сонячні модулі на покрівлі: ряди схід-захід по 10° на опорних профілях
    from .site import SPECS
    wp = SPECS.get("pv_module", {}).get("wp") or 580
    rows = pv_rows(smoke_vents(), wp)
    pv = Mesh()
    lx, ly = MODULE
    t = math.radians(PV_TILT)
    for x, y, sign in rows:
        pv.box((x + lx / 2, y + ly / 2, ROOF_Z + 0.2), (lx - 0.02, ly * math.cos(t), 0.035), "pv_cell",
               rot=(sign * PV_TILT, 0, 0))
    runs = {}
    for x, y, _ in sorted(rows, key=lambda r: (r[1], r[0])):  # суцільні відрізки ряду → профілі
        rr = runs.setdefault(y, [])
        if rr and x - rr[-1][1] < 0.1:
            rr[-1][1] = x + lx
        else:
            rr.append([x, x + lx])
    for y, rr in runs.items():
        for x0, x1 in rr:
            for dy in (0.2, ly - 0.2):
                pv.box_lo((x0 + x1) / 2, y + dy, ROOF_Z, x1 - x0, 0.04, 0.12, "alu")
    pv.build("PV-ROOF", "backup", code="PV-ROOF", kind="power", label="Сонячна станція на покрівлі",
             desc=f"{len(rows)} модулів схід-захід рядами з проходами 1,5 м для пожежників і відступом 2,5 м "
                  f"від клапанів димовидалення.", **_passport_extra("PV-ROOF"))
    inv = Mesh()
    for x in PV_INVERTERS_X:
        inv.box_lo(x, D + 0.5, 1.0, 1.035, 0.365, 0.7, "phenolic", bev=0.03)  # SUN2000-115KTL: 1035 × 700 × 365
        inv.box_lo(x - 0.3, D + 0.69, 1.5, 0.12, 0.01, 0.06, "status_green")
        inv.box_lo(x, D + 0.4, 1.75, 0.04, 0.04, ROOF_Z - 1.75, "steel_dark")  # кабелі з даху
    inv.box_lo((PV_INVERTERS_X[0] + 124.0) / 2, D + 0.4, 2.6, 124.0 - PV_INVERTERS_X[0], 0.04, 0.04,
               "rubber")  # над дверима EX-N5
    inv.build("PV-INV", "backup", code="PV-INV", kind="power", label="Інвертори СЕС",
              desc="Мережеві інвертори на зовнішній стіні за офісом; змінний струм — у ГРЩ.",
              **_passport_extra("PV-INV"))
    build_chp()


def build_chp():
    """Когенераційна установка TEDOM Quanto D800: модуль двигун-генератор, модуль вихлопу з глушником,
    сухий охолоджувач, газопровід із ГРП, теплотраса до котельні, кабель до ГРЩ."""
    c = Mesh()
    cx, cy = CHP_POS
    c.box_lo(cx, cy, 0, 8.0, 3.2, 0.2, "steel_dark")  # фундамент
    c.box_lo(cx, cy, 0.2, 7.2, 2.5, 3.1, "chp_body", bev=0.05)  # модуль 7200 × 2500 × 3300 мм
    for k in range(4):  # вентиляційні решітки й двері обслуговування
        c.box_lo(cx - 2.7 + k * 1.8, cy - 1.26, 0.6, 1.1, 0.02, 2.0, "steel_dark")
    c.box_lo(cx + 3.61, cy, 1.0, 0.02, 1.6, 1.4, "steel_dark")
    c.box_lo(cx - 3.0, cy - 1.27, 1.5, 0.4, 0.01, 0.25, "screen_on")
    c.box_lo(cx + 2.4, cy, 3.3, 1.8, 1.6, 0.9, "galv")  # повітрозабір
    ex, ey = CHP_EXH_POS
    c.box_lo(ex, ey, 0.2, 4.9, 1.0, 2.6, "machine_mid", bev=0.03)  # модуль вихлопу 4900 × 1000 × 2600
    c.tube([(cx - 1.5, cy + 1.25, 2.6), (cx - 1.5, ey - 0.5, 2.6)], 0.2, "steel", segs=12)
    c.cyl((ex + 1.8, ey, 2.8 + 4.3 / 2), 0.425, 4.3, "steel", segs=20)  # глушник Ø850 × 4300
    c.cyl((ex + 1.8, ey, 7.1 + 2.0), 0.25, 4.0, "steel", segs=16)  # труба вище покрівлі
    c.cyl((ex + 1.8, ey, 11.15), 0.3, 0.1, "steel_dark", segs=16)
    kx, ky = CHP_COOLER_POS  # сухий охолоджувач аварійного скидання тепла
    for dx in (-2.8, 2.8):
        for dy in (-1.0, 1.0):
            c.box_lo(kx + dx, ky + dy, 0, 0.12, 0.12, 1.6, "steel_dark")
    c.box_lo(kx, ky, 1.6, 6.0, 2.3, 1.0, "machine_mid", bev=0.03)
    for k in range(4):
        c.cyl((kx - 2.2 + k * 1.47, ky, 2.62), 0.6, 0.06, "steel_dark", segs=24)
    c.tube(rounded_path([(cx + 0.5, cy + 1.25, 3.0), (cx + 0.5, ky - 1.15, 3.0), (cx + 0.5, ky - 1.15, 2.2)],
                        radius=0.3), 0.08, "alu", segs=10)
    c.build("CHP", "backup", code="CHP", kind="power", label="Когенераційна установка",
            desc="Газопоршнева установка 800 кВт електрики й 856 кВт тепла: електрика — паралельно з мережею в "
                 "ГРЩ, тепло — у теплову мережу цеху через котельню; котли на відходах — резерв і піки.",
            **_passport_extra("CHP"))
    g = Mesh()
    gx, gy = CHP_GRP_POS  # шафовий ГРП: середній тиск → 8–15 кПа на вході установки
    g.box_lo(gx, gy, 0, 1.2, 0.8, 1.6, "gas_yellow", bev=0.03)
    g.tube([(gx, 100.0, 0.6), (gx, gy + 0.4, 0.6)], 0.06, "gas_yellow", segs=10)
    g.tube(rounded_path([(gx + 0.6, gy, 0.8), (cx - 3.7, gy, 0.8), (cx - 3.7, cy + 0.6, 0.8),
                         (cx - 3.6, cy + 0.6, 0.8)], radius=0.08), 0.05, "gas_yellow", segs=10)
    g.box_lo(gx, gy - 0.41, 1.2, 0.3, 0.01, 0.2, "steel_dark")
    g.build("CHP-GAS", "backup", code="CHP-GAS", kind="power", label="Газопровід і ГРП когенерації",
            desc="Введення газу середнього тиску з межі майданчика, шафовий ГРП із вузлом обліку, "
                 "≈ 199 м³/год на повній потужності.")
    h = Mesh()  # теплотраса на естакаді до котельні (подача й зворотка в ізоляції)
    for k, dz in enumerate((0.0, -0.32)):
        h.tube(rounded_path([(cx - 3.6, cy + 1.0 - k * 0.3, 1.2), (cx - 4.2, cy + 1.0 - k * 0.3, 1.2),
                             (cx - 4.2, CHP_HEAT_Y, CHP_HEAT_Z + dz), (79.6, CHP_HEAT_Y, CHP_HEAT_Z + dz)],
                            radius=0.4), 0.11, "alu", segs=10)
    for x in range(84, int(cx - 4), 6):  # стійки естакади — осторонь виходу EX-N5
        h.box_lo(x, CHP_HEAT_Y, 0, 0.16, 0.16, CHP_HEAT_Z - 0.45, "steel_dark")
        h.box_lo(x, CHP_HEAT_Y, CHP_HEAT_Z - 0.45, 0.16, 0.8, 0.08, "steel_dark")
    h.tube(rounded_path([(cx + 3.6, cy - 0.6, 0.4), (124.2, cy - 0.6, 0.4), (124.2, D + 0.4, 0.05),
                         (124.2, D + 0.4, 1.2)], radius=0.3), 0.08, "rubber", segs=8)  # кабель 4×NYY до ГРЩ
    h.build("CHP-HEAT", "backup", code="CHP-HEAT", kind="power", label="Теплотраса й кабель КГУ",
            desc="Тепло 90/70 °C — на естакаді до котельні й далі в теплову мережу цеху; кабель 1600 А — "
                 "у ГРЩ на шини 0,4 кВ.")


# ---------------------------------------------------------------- покриття даху
def roof_openings():
    """Отвори в покритті: (x, y, розмір у плані) — клапани, дахові установки, витяжки, повітроводи."""
    from .layout import EXHAUST_POINTS, MACHINES
    from .site import machine_rz, rot2
    from .ventilation import AHU_POS, CHG_EXHAUST, FABRIC_DUCTS, ROOFVENTS
    out = [(x, y, VENT[0] + 0.24) for x, y in smoke_vents()]
    out += [(x, y, 1.1) for _, x, y, _ in ROOFVENTS]
    out += [(AHU_POS[0] + 2.0, y, 0.7) for y, *_ in FABRIC_DUCTS]
    out.append((CHG_EXHAUST[0], CHG_EXHAUST[1], 0.6))
    for mch in MACHINES:
        code, typ, _, mx, my = mch[:5]
        for lx, ly, _ in EXHAUST_POINTS.get(typ, []):
            ox, oy = rot2(lx, ly, machine_rz(mch))
            out.append((mx + ox, my + oy, 0.6))
    return out


def build_roofdeck():
    """Профнастил з утеплювачем і мембраною: товщина 0,12 м, верх на 9,0 м; клітинки 0,5 м без отворів,
    злиті в прямокутники."""
    step, th = 0.5, 0.12
    nx, ny = int(W / step), int(D / step)
    holes = [(x - a / 2, y - a / 2, x + a / 2, y + a / 2) for x, y, a in roof_openings()]

    def free(i, j):
        x0, y0 = i * step, j * step
        return not any(x0 < hx1 and x0 + step > hx0 and y0 < hy1 and y0 + step > hy0
                       for hx0, hy0, hx1, hy1 in holes)

    m = Mesh()
    open_rects = {}  # (i0, i1) → j0

    def flush(key, j0, j1):
        i0, i1 = key
        m.box_lo((i0 + i1) * step / 2, (j0 + j1) * step / 2, ROOF_Z - th, (i1 - i0) * step, (j1 - j0) * step, th,
                 "roof_deck")

    for j in range(ny + 1):
        runs = set()
        if j < ny:
            i = 0
            while i < nx:
                if free(i, j):
                    i0 = i
                    while i < nx and free(i, j):
                        i += 1
                    runs.add((i0, i))
                else:
                    i += 1
        for key in list(open_rects):
            if key not in runs:
                flush(key, open_rects.pop(key), j)
        for key in runs:
            open_rects.setdefault(key, j)
    t = 0.3
    for x, y, sx, sy in ((W / 2, -t / 2, W + 2 * t, t), (W / 2, D + t / 2, W + 2 * t, t),
                         (-t / 2, D / 2, t, D), (W + t / 2, D / 2, t, D)):
        m.box_lo(x, y, ROOF_Z - th, sx, sy, 0.45 + th, "wall_band")  # парапет
    for x, y, a in roof_openings():  # обичайки отворів
        for dx, dy, sx, sy in ((0, a / 2, a + 0.1, 0.05), (0, -a / 2, a + 0.1, 0.05), (a / 2, 0, 0.05, a),
                               (-a / 2, 0, 0.05, a)):
            m.box_lo(x + dx, y + dy, ROOF_Z, sx, sy, 0.15, "steel_dark")
    m.build("ROOF-DECK", "roofdeck", code="ROOF-DECK", kind="building", label="Покриття даху",
            desc="Сталевий профнастил, мінвата й ПВХ-мембрана по фермах; отвори під клапани димовидалення, "
                 "дахові установки й витяжки, парапет по периметру.")


# ---------------------------------------------------------------- вода й стоки
def build_water():
    w = Mesh()
    ix, iy = WATER_INLET
    w.box_lo(ix, iy, 0, 1.6, 1.6, 0.06, "steel_dark")  # люк водомірного колодязя
    w.cyl((ix, iy, 0.1), 0.35, 0.08, "steel", segs=16)
    w.tube(rounded_path(WATER_MAIN, radius=0.3), 0.045, "water_pipe", segs=10)
    w.tube(rounded_path([(72.0, D - 0.45, 4.2), (72.0, 63.5, 4.2), (71.0, 63.5, 3.25)], radius=0.3), 0.03,
           "water_pipe", segs=8)  # до водяної завіси фарбувальної камери
    w.tube(rounded_path([(109.0, D - 0.45, 4.2), (109.2, 57.0, 4.2), (109.2, 57.0, 3.6)], radius=0.3), 0.035,
           "water_pipe", segs=8)  # до побутових
    for code, x, y, _ in EYEWASH:  # аварійний душ і промивка очей
        w.cyl((x, y, 1.1), 0.03, 2.2, "status_green", segs=8)
        w.cyl((x, y, 2.25), 0.15, 0.04, "status_green", segs=16)
        w.box_lo(x + 0.2, y, 1.0, 0.25, 0.25, 0.05, "status_green")
        w.cyl((x, y, 0.02), 0.25, 0.04, "status_green", segs=16)
        if code == "EYE-CHG":
            w.tube([(121.3, D - 0.45, 4.2), (121.3, y, 4.2), (x, y, 2.25)], 0.025, "water_pipe", segs=8)
        else:
            w.tube([(68.5, D - 0.45, 4.2), (x, y, 4.2), (x, y, 2.25)], 0.025, "water_pipe", segs=8)
    tx, ty = WASTEWATER  # очищення води водяних завіс
    w.box_lo(tx, ty, 0, 2.2, 1.2, 1.4, "machine_accent", bev=0.04)
    w.cyl((tx - 0.6, ty, 1.7), 0.35, 0.6, "galv", segs=16)
    w.tube([(70.6, 62.4, 0.3), (70.6, ty, 0.3), (tx - 1.1, ty, 0.3)], 0.05, "rubber", segs=8)
    w.build("WATER", "water", code="WATER", kind="equipment", label="Водопостачання й стоки",
            desc="Ввід із водомірним вузлом, магістраль уздовж північної стіни до фарбування, побутових і "
                 "аварійних душів; очищення шламової води водяних завіс.", **_passport_extra("WATER"))


# ---------------------------------------------------------------- Odoo: робочі місця й мережа
def build_odoo_it():
    def tablet(m):
        m.box_lo(0, 0, 0, 0.3, 0.3, 0.02, "steel_dark")
        m.cyl((0, 0, 0.65), 0.025, 1.3, "steel_dark", segs=8)
        m.box((0, 0.03, 1.38), (0.26, 0.03, 0.18), "machine_dark", rot=(-20, 0, 0))
        m.box((0, 0.012, 1.385), (0.23, 0.01, 0.15), "screen_on", rot=(-20, 0, 0))
    mt = shared("odoo_tablet", tablet)
    root = empty("ODOO-TABLETS", "odoo_it", code="ODOO-TABLETS", kind="it", label="Планшети Odoo Shop Floor",
                 desc="Біля кожного робочого центру: завдання, інструкції, старт/стоп операції, контроль якості.",
                 **_passport_extra("ODOO-TABLETS"))
    for code, x, y, rz in tablets():
        instance(f"TAB-{code}", "odoo_it", mt, parent=root, loc=(x, y, 0), rz=rz + 180, code=f"TAB-{code}",
                 kind="it", label=f"Планшет Shop Floor · {code}", desc="Odoo Shop Floor для цього робочого центру.")
    sc = Mesh()
    for code, x, y in SCANNERS:
        sc.box_lo(x + 0.25, y + 0.25, 1.05, 0.08, 0.17, 0.03, "machine_dark")
        sc.box_lo(x + 0.25, y + 0.25, 1.08, 0.06, 0.12, 0.005, "screen_on")
    sc.build("ODOO-SCANNERS", "odoo_it", code="ODOO-SCANNERS", kind="it", label="ТЗД комірників (Odoo Barcode)",
             desc="Мобільні термінали зі сканером 2D: приймання, переміщення, комплектація, інвентаризація.",
             **_passport_extra("ODOO-SCANNERS"))
    for code, x, y, note in PRINTERS:
        p = Mesh()
        p.box_lo(x, y, 0, 0.7, 0.5, 0.75, "table_top")
        p.box_lo(x, y, 0.75, 0.27, 0.5, 0.33, "machine_mid", bev=0.02)
        p.box_lo(x - 0.14, y, 0.95, 0.01, 0.1, 0.06, "screen_on")
        p.build(code, "odoo_it", code=code, kind="it", label=f"Принтер етикеток · {note}",
                desc="Друк етикеток ZPL прямо з Odoo (через IoT Box).", **_passport_extra(code))
    for code, x, y, note in SCALES:
        s = Mesh()
        s.box_lo(x, y, 0, 1.25, 1.25, 0.08, "steel", bev=0.01)
        s.box_lo(x + 0.9, y, 0, 0.06, 0.06, 1.2, "steel_dark")
        s.box_lo(x + 0.9, y, 1.2, 0.3, 0.1, 0.2, "machine_mid")
        s.box_lo(x + 0.9, y - 0.051, 1.27, 0.2, 0.01, 0.07, "screen_on")
        s.build(code, "odoo_it", code=code, kind="it", label=f"Палетні ваги · {note}",
                desc="Вага палети йде в документ відвантаження через IoT Box.", **_passport_extra(code))
    for code, x, y, _ in IOT_BOXES:
        b = Mesh()
        b.box_lo(x, y, 0.75, 0.2, 0.15, 0.05, "phenolic")
        b.box_lo(x - 0.06, y - 0.076, 0.76, 0.02, 0.005, 0.02, "status_green")
        b.build(code, "odoo_it", code=code, kind="it", label="Odoo IoT Box",
                desc="Підключає принтери й ваги до Odoo.", **_passport_extra(code))
    ap = Mesh()
    for x, y in wifi_aps():
        ap.box_lo(x, y, H - 0.05 - 0.12, 0.26, 0.26, 0.05, "phenolic", bev=0.02)
        ap.box_lo(x, y, H - 0.12, 0.03, 0.03, 0.12, "steel_dark")
    ap.build("WIFI", "network", code="WIFI", kind="it", label="Точки доступу Wi-Fi",
             desc="Покриття для планшетів, ТЗД і навантажувачів по всьому цеху й складах.",
             **_passport_extra("WIFI"))
    sr = Mesh()
    sx, sy, w, d = SERVER_ROOM
    sr.box_lo(sx, sy, 0, w, d, 0.05, "steel_dark")
    for k in (-1, 1):
        sr.box_lo(sx + k * w / 2, sy, 0, 0.05, d, 2.6, "guard_glass")
        sr.box_lo(sx, sy + k * d / 2, 0, w, 0.05, 2.6, "guard_glass")
    sr.box_lo(sx, sy, 2.6, w, d, 0.05, "wall_band")
    sr.box_lo(sx + 0.4, sy + 0.3, 0.05, 0.6, 1.07, 2.0, "machine_dark", bev=0.01)  # шафа 42U
    for k in range(10):
        sr.box_lo(sx + 0.4, sy + 0.3 - 0.535, 0.3 + k * 0.17, 0.5, 0.01, 0.04, "status_green" if k % 3 else "led")
    sr.box_lo(sx - 0.6, sy + 0.3, 0.05, 0.6, 0.8, 0.9, "machine_mid")  # ДБЖ
    sr.box_lo(sx - 0.6, sy + d / 2 - 0.15, 2.0, 0.9, 0.2, 0.3, "phenolic")  # кондиціонер
    sr.build("SERVER", "network", code="SERVER", kind="it", label="Серверна",
             desc="Шафа 42U: комутатор ядра, сервер, відеореєстратор; ДБЖ і кондиціонер.",
             **_passport_extra("SERVER"))


# ---------------------------------------------------------------- територія
def build_territory():
    x0, y0, x1, y1 = SITE
    t = Mesh()
    t.box(((x0 + x1) / 2, (y0 + y1) / 2, -0.025), (x1 - x0, y1 - y0, 0.04), "asphalt")
    px0, py0, px1, py1 = PARKING
    for k in range(int((px1 - px0) / 2.6)):  # розмітка паркування
        for y in (py0 + 2.5, py1 - 2.5):
            t.box((px0 + 1.3 + k * 2.6, y, 0.004), (0.1, 5.0, 0.005), "marking")
    t.box((KPP[0], (KPP[1] + 0) / 2, 0.004), (2.0, abs(KPP[1]) - 1, 0.005), "marking")  # пішохідна доріжка
    t.build("TERRITORY", "territory", code="TERRITORY", kind="building", label="Територія",
            desc="Двори фур біля воріт приймання й відвантаження, паркування персоналу, пішохідна доріжка "
                 "від прохідної до входу.")
    f = Mesh()
    gaps = {x for _, x, _, _ in GATES}
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        L = math.dist((ax, ay), (bx, by))
        n = int(L / 3)
        for k in range(n + 1):
            px, py = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
            if ay == y0 and by == y0 and (any(abs(px - g) < 4.2 for g in gaps) or abs(px - KPP[0]) < 3.2):
                continue
            f.box_lo(px, py, 0, 0.06, 0.06, 2.2, "steel_dark")
        if ay == by == y0:
            segs, pos = [], x0
            for c, w in sorted([(g, 8.4) for g in gaps] + [(KPP[0], 6.4)]):
                segs.append((pos, c - w / 2))
                pos = c + w / 2
            segs.append((pos, x1))
            for a, b in segs:
                f.box_lo((a + b) / 2, y0, 0.1, b - a, 0.02, 2.0, "mesh_fence")
        else:
            f.box_lo((ax + bx) / 2, (ay + by) / 2, 0.1, abs(bx - ax) or 0.02, abs(by - ay) or 0.02, 2.0, "mesh_fence")
    f.build("FENCE", "territory", code="FENCE", kind="building", label="Огорожа", desc="Сітчаста огорожа 2,2 м.")
    for code, x, w, label in GATES:
        g = Mesh()
        g.box_lo(x - w / 2 - 0.4, y0 + 1.0, 0, 0.4, 0.4, 1.1, "machine_mid")  # тумба шлагбаума
        g.box_lo(x, y0 + 1.0, 1.0, w, 0.08, 0.1, "phenolic")
        for k in range(6):
            g.box_lo(x - w / 2 + 0.6 + k * 1.4, y0 + 1.0, 1.0, 0.5, 0.085, 0.1, "fire_red")
        g.build(code, "security", code=code, kind="security", label=f"{label}: шлагбаум",
                desc="Автоматичний шлагбаум; номер машини звіряється з документом приймання/відвантаження.",
                **_passport_extra(code))
    s = Mesh()
    sx, sy = TRUCK_SCALE
    s.box_lo(sx, sy, 0, 3.2, 18.4, 0.12, "steel_dark")
    s.box_lo(sx, sy, 0.12, 3.0, 18.0, 0.18, "steel")
    for k in (-1, 1):
        s.box((sx, sy + k * 9.6, 0.1), (3.0, 1.2, 0.12), "steel_dark", rot=(k * -10, 0, 0))
    s.box_lo(sx - 2.6, sy + 9.0, 0, 0.1, 0.1, 1.8, "steel_dark")
    s.box_lo(sx - 2.6, sy + 9.0, 1.8, 0.6, 0.15, 0.4, "screen_on")  # табло ваги
    s.build("TRUCK-SCALE", "territory", code="TRUCK-SCALE", kind="equipment", label="Автомобільні ваги",
            desc="Зважування фур на в'їзді й виїзді; вага йде в документ відвантаження Odoo.",
            **_passport_extra("TRUCK-SCALE"))
    k = Mesh()
    kx, ky = KPP
    k.box_lo(kx + 3.0, ky, 0, 3.0, 4.0, 2.8, "wall")
    k.box_lo(kx + 3.0, ky, 2.8, 3.2, 4.2, 0.15, "wall_band")
    k.box_lo(kx + 1.49, ky, 1.0, 0.03, 3.0, 1.4, "glass")
    k.box_lo(kx - 0.2, ky, 2.8, 4.0, 4.4, 0.12, "steel_dark")  # навіс над турнікетами
    for c in (kx - 1.6, kx + 1.2):
        k.box_lo(c, ky - 2.0, 0, 0.1, 0.1, 2.8, "steel_dark")
        k.box_lo(c, ky + 2.0, 0, 0.1, 0.1, 2.8, "steel_dark")
    k.build("KPP", "territory", code="KPP", kind="building", label="Прохідна",
            desc="Пост охорони, турнікети з рідерами — облік робочого часу в Odoo Attendances.")
    wx0, wy0, wx1, wy1 = WASTE
    wm = Mesh()
    wm.box_lo((wx0 + wx1) / 2, (wy0 + wy1) / 2, 0, wx1 - wx0, wy1 - wy0, 0.1, "steel_dark")
    for i, (mat, ln) in enumerate((("machine_accent", 6.0), ("forklift", 6.0), ("fire_red", 3.0))):
        cx = wx0 + 3.5 + i * 5.5
        wm.box_lo(cx, (wy0 + wy1) / 2, 0.1, 2.4, ln, 1.8, mat, bev=0.04)
    wm.box_lo((wx0 + wx1) / 2, (wy0 + wy1) / 2, 4.0, wx1 - wx0, wy1 - wy0, 0.1, "steel")
    for cx in (wx0 + 0.3, wx1 - 0.3):
        for cy in (wy0 + 0.3, wy1 - 0.3):
            wm.box_lo(cx, cy, 0, 0.15, 0.15, 4.0, "steel_dark")
    wm.build("WASTE", "territory", code="WASTE", kind="stock", label="Майданчик відходів",
             desc="Контейнери: обрізки плит, гофрокартон, відходи ЛФМ (окремий закритий).")


# ---------------------------------------------------------------- охорона й доступ
def build_security():
    def cam(m):
        m.box_lo(0, 0, -0.06, 0.08, 0.08, 0.12, "steel_dark")
        m.box((0.16, 0, -0.08), (0.28, 0.11, 0.1), "phenolic", rot=(0, 15, 0))
        m.cyl((0.31, 0, -0.12), 0.035, 0.02, "screen", axis="X", segs=10)
    me = shared("cctv", cam)
    root = empty("CCTV", "security", code="CCTV", kind="security", label="Відеоспостереження",
                 desc="Камери по периметру будівлі, на воротах, прохідній і майданчику відходів.",
                 **_passport_extra("CCTV"))
    for code, x, y, z, ang in CAMERAS:
        if z > 3.9 and (x < 0 or x > W or y < 0 or y > D) and not (-0.5 < x < W + 0.5 and -0.5 < y < D + 0.5):
            pole = Mesh()
            pole.box_lo(0, 0, 0, 0.1, 0.1, z, "steel_dark")
            pole.build(code + "_pole", "security", parent=root, loc=(x, y, 0))
        instance(code, "security", me, parent=root, loc=(x, y, z), rz=ang)
    t = Mesh()
    kx, ky = KPP
    for c in (kx - 0.9, kx + 0.4):  # два турнікети
        t.box_lo(c, ky, 0, 0.3, 0.9, 1.0, "steel", bev=0.03)
        for a in (0, 120, 240):
            t.box((c - 0.4, ky, 0.95), (0.5, 0.04, 0.04), "steel", rot=(a, 0, 0))
        t.box_lo(c + 0.16, ky - 0.3, 1.0, 0.02, 0.1, 0.12, "screen_on")  # рідер
    t.build("TURNSTILES", "security", code="TURNSTILES", kind="security", label="Турнікети прохідної",
            desc="Вхід і вихід за картками: відмітки йдуть в Odoo Attendances.", **_passport_extra("TURNSTILES"))
    r = Mesh()
    for code, x, y, _ in DOOR_READERS:
        r.box_lo(x, y, 1.1, 0.09, 0.04, 0.14, "machine_dark")
        r.box_lo(x, y - 0.025, 1.18, 0.05, 0.01, 0.03, "status_green")
    r.build("ACCESS", "security", code="ACCESS", kind="security", label="Контроль доступу",
            desc="Рідери на дверях електрощитової, зарядної, складу ЛФМ, серверної й входу персоналу.",
            **_passport_extra("ACCESS"))


def build_infra():
    build_roofdeck()
    build_smoke()
    build_lightning()
    build_backup()
    build_water()
    build_odoo_it()
    build_territory()
    build_security()
