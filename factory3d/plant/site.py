"""Будівля, зони, склади, інженерія, люди, транспорт і маршрути — усе, що не є верстатом."""
import math

from .geom import (LAYER_OBJ, Mesh, cartons, empty, forklift, hazard, instance, legs_frame, pallet,
                   person, rack_cart, roller_table, rounded_path, shared, sheet_stack)
from .layout import (D, DOOR_H, DOORS, DUCT_MAIN_Y, DUCT_NORTH_X, DUCT_POINTS, DUCT_Z, EXHAUST_POINTS,
                     FG_BAYS, FG_LEVELS, FG_PRODUCTS, FG_ROWS, FOOTPRINT, GANTRY_COLS, GANTRY_X, GANTRY_Y, H,
                     HW_LEVELS, HW_ROWS, HW_SECTIONS, MACHINES, SHEET_COLS_X, SHEET_DECORS, SHEET_ROWS_Y,
                     STATUS, W, ZONES, blocked, edge_slot, fg_slot, hw_state, obst, sheet_slot)
from .energy import (BUS_Z, PFC_H, BUSWAYS, CABLE_Z, CELL_X, EMS_POS, RM6_POS, ROOM, SWB_CELLS, SWB_D, SWB_H, SWB_X0,
                     SWB_X1, SWB_Y, TRAFO_Y, TRAFOS, TRAY_Y, TRAY_Z, energy_passport, taps)
from .equipment import body_scale, load_specs, passport
from .machines import MACHINE_BUILDERS, OPERATOR, TOWER_POS

SPECS = load_specs()


def rot2(lx, ly, rz):
    a = math.radians(rz)
    return lx * math.cos(a) - ly * math.sin(a), lx * math.sin(a) + ly * math.cos(a)


def machine_rz(m):
    return m[6] if len(m) > 6 else 0.0


# ---------------------------------------------------------------- будівля
def wall_x(m, x, y0, y1, h, openings=(), t=0.2, lintel=2.6):
    """Стіна вздовж Y на координаті x з прорізами (центр, ширина)."""
    y = y0
    for yc, w in sorted(openings):
        if yc - w / 2 > y:
            m.box_lo(x, (y + yc - w / 2) / 2, 0, t, yc - w / 2 - y, h, "wall")
        m.box_lo(x, yc, lintel, t, w, h - lintel, "wall")
        y = yc + w / 2
    if y1 > y:
        m.box_lo(x, (y + y1) / 2, 0, t, y1 - y, h, "wall")
    m.box_lo(x, (y0 + y1) / 2, h, t + 0.02, y1 - y0, 0.12, "wall_band")


def wall_y(m, y, x0, x1, h, openings=(), t=0.2, lintel=2.6):
    """Стіна вздовж X на координаті y з прорізами (центр, ширина)."""
    x = x0
    for xc, w in sorted(openings):
        if xc - w / 2 > x:
            m.box_lo((x + xc - w / 2) / 2, y, 0, xc - w / 2 - x, t, h, "wall")
        m.box_lo(xc, y, lintel, w, t, h - lintel, "wall")
        x = xc + w / 2
    if x1 > x:
        m.box_lo((x + x1) / 2, y, 0, x1 - x, t, h, "wall")
    m.box_lo((x0 + x1) / 2, y, h, x1 - x0, t + 0.02, 0.12, "wall_band")


def build_building():
    m = Mesh()
    m.box((W / 2, D / 2, -0.06), (W + 60, D + 40, 0.1), "ground")
    m.box((W / 2, D / 2, -0.1), (W, D, 0.2), "floor")
    m.build("Майданчик і підлога", "building")

    walls = Mesh()
    t = 0.3
    # північна стіна на всю висоту, південна — розріз (низький парапет), щоб було видно всередину
    walls.box_lo(W / 2, D + t / 2, 0, W + 2 * t, t, H, "wall")
    walls.box_lo(W / 2, D + t / 2 + 0.01, 0, W + 2 * t, t, 1.0, "wall_band")
    for k in range(int(W / 6)):
        walls.box_lo(3 + k * 6, D - 0.005, 5.6, 4.4, 0.02, 1.6, "glass")
    walls.box_lo(W / 2, -t / 2, 0, W + 2 * t, t, 1.0, "wall_band")
    for side, x in (("W", -t / 2), ("E", W + t / 2)):
        wall_x(walls, x, 0.0, D, H, [(y, w) for s, y, w in DOORS if s == side], t=t, lintel=DOOR_H)
        walls.box_lo(x + (0.01 if side == "E" else -0.01), D / 2, 0, t, D, 1.0, "wall_band")
    walls.build("Стіни", "building")

    rf = Mesh()
    for x in range(0, int(W) + 1, 12):
        rf.box_lo(x, D / 2, H - 0.6, 0.25, D, 0.6, "steel")
        for k in range(int(D / 6)):
            rf.box((x, 3 + k * 6, H - 0.3), (0.06, 0.06, 0.7), "steel", rot=(40 if k % 2 else -40, 0, 0))
    for y in (15.0, 30.0, 45.0, 60.0):
        rf.box_lo(W / 2, y, H - 0.3, W, 0.14, 0.3, "steel_dark")
    for x in range(3, int(W), 6):
        for y in range(5, int(D), 10):
            rf.cyl((x, y, H - 0.9), 0.03, 0.6, "steel_dark", segs=6)
            rf.cyl((x, y, H - 1.25), 0.32, 0.1, "machine_mid", segs=20)
            rf.cyl((x, y, H - 1.31), 0.28, 0.02, "led", segs=20)
    rf.build("Ферми та світильники", "roof")

    # перегородки: дільниця фасадів (окреме приміщення), склад ЛФМ, компресорна, зарядна
    pw = Mesh()
    wall_y(pw, 46.0, 42.0, 92.0, 3.4, [(48.5, 4.0), (66.0, 3.0), (89.0, 4.0)])
    wall_x(pw, 42.0, 46.0, D, 3.4, [(64.0, 2.0)])
    wall_x(pw, 92.0, 46.0, D, 3.4, [(52.0, 2.0)])
    wall_x(pw, 58.0, 66.0, D, 3.4)
    wall_x(pw, 66.0, 66.0, D, 3.4)
    wall_y(pw, 66.0, 58.0, 66.0, 3.4, [(62.0, 1.6)])
    wall_y(pw, 60.0, 110.0, 122.0, 3.4, [(113.0, 1.6), (119.0, 3.6)])
    wall_x(pw, 110.0, 60.0, D, 3.4)
    wall_x(pw, 116.0, 60.0, D, 3.4)
    pw.build("Перегородки", "building")

    # офіс: два поверхи із суцільним склінням на південь
    of = Mesh()
    x0, y0, x1, y1 = 92.6, 58.4, 107.8, 71.0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for z in (0.0, 3.2):
        of.box_lo(cx, cy, z, x1 - x0, y1 - y0, 3.0, "wall")
        of.box_lo(cx, y0 - 0.01, z + 0.9, x1 - x0 - 0.6, 0.05, 1.7, "glass")
        for k in range(1, 10):
            of.box_lo(x0 + 0.3 + k * (x1 - x0 - 0.6) / 10, y0 - 0.03, z + 0.9, 0.06, 0.05, 1.7, "steel_dark")
        of.box_lo(cx, cy, z + 3.0, x1 - x0 + 0.2, y1 - y0 + 0.2, 0.2, "wall_band")
    of.box_lo(x0 + 1.4, y0 - 0.01, 0, 1.0, 0.06, 2.1, "steel_dark")
    for i in range(11):
        of.box_lo(x1 + 0.8, y0 + 0.6 + i * 0.3, i * 0.3, 1.1, 0.3, 0.3, "steel")
    of.build("OFFICE", "building", code="OFFICE", kind="building", label="Офіс",
             desc="Двоповерховий модуль біля північної стіни: майстри, технологи, планування змін.")
    obst(x0, y0, x1 + 1.4, y1)

    so = Mesh()
    x0, y0, x1, y1 = 104.2, 46.6, 109.4, 57.4
    so.box_lo((x0 + x1) / 2, (y0 + y1) / 2, 0, x1 - x0, y1 - y0, 3.4, "wall")
    so.box_lo((x0 + x1) / 2, (y0 + y1) / 2, 3.4, x1 - x0 + 0.2, y1 - y0 + 0.2, 0.2, "wall_band")
    for k in range(2):
        so.box_lo(x0 + 1.4 + k * 2.4, y0 - 0.01, 1.0, 1.6, 0.05, 1.4, "glass")
    so.build("SOCIAL", "building", code="SOCIAL", kind="building", label="Побутові приміщення",
             desc="Роздягальні, душові, їдальня, медпункт.")
    obst(x0, y0, x1, y1)

    for side, yc, w in DOORS:
        d = Mesh()
        inside = 1 if side == "W" else -1
        x = 0.0 if side == "W" else W
        d.box_lo(x - inside * 0.4, yc, 0, 0.5, w + 0.8, DOOR_H + 0.4, "dock_shelter", bev=0.05)
        d.box_lo(x + inside * 1.2, yc, 0.0, 2.4, w - 0.4, 0.03, "steel")
        hazard(d, yc - w / 2 + 0.2, yc + w / 2 - 0.2, x + inside * 2.4, 0.0, depth=0.1, h=0.032,
               along="Y")
        for dy in (-1, 1):
            d.box_lo(x + inside * 0.17, yc + dy * (w / 2 + 0.1), 0, 0.2, 0.2, DOOR_H, "marking")
            d.box_lo(x - inside * 0.68, yc + dy * 0.9, 0.9, 0.12, 0.25, 0.3, "rubber", bev=0.02)
        d.box_lo(x + inside * 0.45, yc, DOOR_H - 0.1, 0.5, w, 0.25, "machine_mid", bev=0.03)
        layer = "receiving" if side == "W" else "shipping"
        idx = sum(1 for s, yy, _ in DOORS if s == side and yy <= yc)
        kind_ua = "Ворота приймання" if side == "W" else "Ворота відвантаження"
        d.build(f"DOCK-{side}{idx}", layer, code=f"DOCK-{side}{idx}", kind="dock",
                label=f"{kind_ua} {idx}", desc="Докшелтер, секційні ворота, вирівнювальна платформа.")


def build_columns():
    m = Mesh()
    for x in range(12, int(W), 12):
        for y in (15, 30, 45, 60):
            if blocked(x, y):
                continue
            m.box_lo(x, y, 0, 0.45, 0.45, H, "column")
            m.box_lo(x, y, 0, 0.6, 0.6, 1.2, "marking")
            hazard(m, x - 0.3, x + 0.3, y - 0.305, 1.05, h=0.12, w=0.12)
            m.box_lo(x + 0.23, y, 1.3, 0.12, 0.3, 0.6, "fire_red", bev=0.01)
    m.build("Колони", "building")


def build_zones():
    for code, name, (x0, y0, x1, y1), _, desc in ZONES:
        m = Mesh()
        m.box(((x0 + x1) / 2, (y0 + y1) / 2, 0.006), (x1 - x0, y1 - y0, 0.012), "zone_" + code)
        w = 0.1
        for (cx, cy, sx, sy) in (((x0 + x1) / 2, y0, x1 - x0, w), ((x0 + x1) / 2, y1, x1 - x0, w),
                                 (x0, (y0 + y1) / 2, w, y1 - y0), (x1, (y0 + y1) / 2, w, y1 - y0)):
            m.box((cx, cy, 0.014), (sx, sy, 0.016), "marking")
        m.build(code, "zones", code=code, kind="zone", label=name, desc=desc,
                rect=[x0, y0, x1, y1])


# ---------------------------------------------------------------- приймання і склади сировини
def stack_mesh(decor, n):
    thick = 0.003 if decor == 6 else 0.016

    def fn(m):
        sheet_stack(m, 0, 0, 0, n, decor, thick)
        m.box_lo(-1.5, 0, 0.01, 0.06, 2.15, 0.02, "marking")
    return shared(f"stack_{decor}_{n}", fn)


def build_receiving():
    """Приймання вздовж усієї західної стіни: перед кожними воротами — коридор розвантаження."""
    m = Mesh()
    # ворота 1–3: плити; 4: фурнітура; 5: крайка; 6: ЛФМ; 7: пакувальні матеріали
    for k, y in enumerate((5.0, 15.0, 25.0)):
        for j, x in enumerate((5.0, 9.5)):
            n = (30, 40, 22, 55, 18, 35)[k * 2 + j]
            sheet_stack(m, x, y, 0.0, n, (k + j) % 3)
            m.box_lo(x, y, 0.08, 2.86, 2.13, n * 0.016 + 0.04, "wrap")
    for y, layers in ((44.0, 2), (46.0, 3), (54.0, 1), (56.0, 2), (64.0, 3), (66.0, 2)):
        for x in (4.5, 6.2, 9.5):
            pallet(m, x, y)
            cartons(m, x, y, 0.146, 1.15, 0.75, layers)
    for x in (11.0, 12.0):  # рулони крайки біля воріт 5
        for y in (53.6, 54.4, 55.2, 56.0):
            m.cyl((x, y, 0.3), 0.3, 0.06, "edge_roll", axis="Y", segs=20)
    for k in range(4):  # пунктир коридорів
        for y in (10.0, 20.0, 30.0, 40.0, 50.0, 60.0):
            m.box((2.0 + k * 3.0, y, 0.022), (1.5, 0.08, 0.02), "marking")
    m.build("IN-STAGE", "receiving", code="IN-STAGE", kind="stock",
            label="Вантажі на розвантаженні",
            desc="Плити біля воріт 1–3, фурнітура й крайка біля 4–5, ЛФМ біля 6, "
                 "пакувальні матеріали біля 7. Чекають на звірку з накладною.")

    q = Mesh()
    for qy in (33.0, 37.0):
        q.box_lo(10.0, qy, 0.84, 2.0, 1.0, 0.05, "table_top", bev=0.01)
        legs_frame(q, 10.0, qy, 2.0, 1.0, 0.84)
        q.box_lo(10.1, qy, 0.89, 0.8, 0.6, 0.016, "decor0")
        q.box_lo(9.4, qy + 0.2, 0.89, 0.3, 0.2, 0.04, "machine_dark", bev=0.005)
    sheet_stack(q, 4.5, 35.0, 0.0, 25, 2)
    for dx in (-1.45, 1.45):
        for dy in (-1.05, 1.05):
            q.box_lo(4.5 + dx, 35.0 + dy, 0, 0.08, 0.08, 1.0, "status_red")
    q.box_lo(4.5, 33.9, 0.85, 3.0, 0.02, 0.06, "status_red")
    q.build("QC-1", "receiving", code="QC-1", kind="stock", label="Вхідний контроль і карантин",
            desc="Столи замірів біля воріт 4; стос на карантині (червоні стійки — не пройшов перевірку).")
    obst(0, 0, 14.0, D)


def build_sheets():
    """Портальний склад: колії вздовж Y, міст уздовж X, стоси сіткою, портал подає лист прямо на
    підйомні столи розкрійних центрів і нестингу."""
    for j, y in enumerate(SHEET_ROWS_Y):
        for i, x in enumerate(SHEET_COLS_X):
            code, decor, n = sheet_slot(i, j)
            name = SHEET_DECORS[decor][0] if n else "порожньо"
            where = "під порталом" if i >= len(SHEET_COLS_X) - GANTRY_COLS else "буфер, навантажувач"
            instance(code, "sheets", stack_mesh(decor, n), loc=(x, y, 0), code=code, kind="stock",
                     label=f"Стос {code}",
                     desc=(f"{name}, {n} арк." if n else "Місце вільне.") + f" ({where})")

    g = Mesh()
    xa, xb = GANTRY_X
    ya, yb = GANTRY_Y
    zr = 6.2
    post_y = (ya, 9.5, 18.5, 28.0, 36.0, yb)
    for x in (xa, xb):
        for y in post_y:
            g.box_lo(x, y, 0, 0.35, 0.35, zr, "machine_accent", bev=0.03)
            g.box_lo(x, y, 0, 0.6, 0.6, 0.03, "steel_dark")
            g.box_lo(x, y, 0, 0.5, 0.5, 1.1, "marking")
        g.box_lo(x, (ya + yb) / 2, zr, 0.45, yb - ya + 0.4, 0.55, "machine_accent", bev=0.04)
        g.box_lo(x, (ya + yb) / 2, zr + 0.55, 0.12, yb - ya + 0.2, 0.08, "steel")
    by = 22.0  # міст порталу
    for dy in (-0.45, 0.45):
        g.box_lo((xa + xb) / 2, by + dy, zr + 0.6, xb - xa + 0.8, 0.35, 0.7, "machine", bev=0.05)
    for x in (xa, xb):
        g.box_lo(x, by, zr + 0.55, 0.8, 1.6, 0.8, "machine_mid", bev=0.05)
    tx = 34.0  # візок і вакуумне захоплення над стосом
    g.box_lo(tx, by, zr + 1.3, 1.4, 1.5, 0.6, "machine_accent", bev=0.05)
    g.box_lo(tx, by, 3.1, 0.35, 0.35, zr - 1.8, "alu", bev=0.02)
    g.box_lo(tx, by, 2.85, 0.5, 0.5, 0.3, "machine_dark", bev=0.03)
    g.box_lo(tx, by, 2.7, 2.6, 1.8, 0.12, "machine_mid", bev=0.02)
    for i in range(4):
        for j in range(3):
            g.cyl((tx - 1.05 + i * 0.7, by - 0.6 + j * 0.6, 2.66), 0.1, 0.06, "rubber", segs=14)
    g.box_lo(tx, by, 2.6, 2.8, 2.07, 0.016, "decor1")
    for y in range(2, 44, 3):  # огородження зони порталу з боку буфера плит
        g.box_lo(xa - 0.4, y, 0, 0.06, 0.06, 2.0, "marking")
        g.box_lo(xa - 0.4, y + 1.5, 0.1, 0.02, 2.9, 1.8, "guard_glass")
    g.build("GANTRY-1", "sheets", code="GANTRY-1", kind="equipment", label="Портальний склад плит",
            desc="Портал над трьома рядами стосів із вакуумною траверсою: бере лист і кладе прямо на "
                 "підйомні столи розкрійних центрів і нестингу (колії заходять над ними). Буфер плит "
                 "поруч поповнює навантажувач.")
    obst(14.6, ya - 0.5, xb + 0.5, yb + 0.5)  # разом із буфером плит — без колон усередині


def build_hardware():
    sec_w, nsec, x0 = 2.0, HW_SECTIONS, 15.5
    levels = [0.12, 0.72, 1.32, 1.92][:HW_LEVELS]
    depth = 0.6
    rows = {f"R{k + 1}": 48.0 + 4.2 * k for k in range(HW_ROWS)}

    def frame(m):
        for s in range(nsec + 1):
            for dy in (-depth / 2, depth / 2):
                m.box_lo(s * sec_w, dy, 0, 0.06, 0.06, 2.5, "rack_upright")
            for z in (0.4, 1.2, 2.0):
                m.box((s * sec_w, 0, z), (0.02, depth, 0.02), "rack_upright", rot=(30, 0, 0))
        for z in levels:
            m.box_lo(nsec * sec_w / 2, 0, z - 0.03, nsec * sec_w, depth, 0.03, "shelf")
            for dy in (-depth / 2, depth / 2):
                m.box_lo(nsec * sec_w / 2, dy, z - 0.08, nsec * sec_w, 0.04, 0.08, "rack_beam")

    def bins(state):
        mat = {"ok": "bin", "low": "bin_yellow", "out": "bin_red"}[state]

        def fn(m):
            if state != "out":
                for b in range(4):
                    bx = -sec_w / 2 + 0.27 + b * 0.49
                    m.box_lo(bx, 0, 0, 0.44, 0.5, 0.26, mat, bev=0.012)
                    m.box_lo(bx, -0.24, 0.16, 0.2, 0.03, 0.08, mat, bev=0.008)
            m.box_lo(0, -depth / 2 - 0.03, -0.075, 0.24, 0.01, 0.06,
                     mat if state != "ok" else "phenolic")
        return shared("bins_" + state, fn)

    me_frame = shared("hw_rack", frame)
    for ri, (row, y) in enumerate(rows.items()):
        instance(f"RACK-{row}", "hardware", me_frame, loc=(x0, y, 0), code=f"RACK-{row}",
                 kind="rack", label=f"Стелаж {row}",
                 desc=f"{nsec} секцій × {len(levels)} яруси, комірки з лотками.")
        obst(x0, y - 0.4, x0 + nsec * sec_w, y + 0.4)
        for s in range(1, nsec + 1):
            for li, z in enumerate(levels, 1):
                code = f"FUR-{row}-S{s:02d}-L{li}"
                state = hw_state(ri, s, li)
                instance(code, "hardware", bins(state), loc=(x0 + (s - 0.5) * sec_w, y, z),
                         code=code, kind="bin", state=state, label=f"Комірка {code}",
                         desc={"ok": "Запас у нормі.", "low": "Запас нижче мінімуму.",
                               "out": "Комірка порожня."}[state])


def build_edge():
    ys, ye, nsec = 47.5, 70.5, 4
    sec = (ye - ys) / nsec
    levels = (0.1, 0.9, 1.7)

    def frame(m):
        for k in range(nsec + 1):
            for dx in (-0.45, 0.45):
                m.box_lo(dx, ys + k * sec, 0, 0.06, 0.06, 2.4, "rack_upright")
        for z in levels:
            m.box_lo(0, (ys + ye) / 2, z - 0.04, 0.9, ye - ys, 0.04, "shelf")

    def rolls(decor, n):
        def fn(m):
            for k in range(n):
                cy = -sec / 2 + 0.45 + k * 0.42
                m.cyl((0, cy, 0.32), 0.3, 0.06, "edge%d" % decor, axis="Y", segs=24)
                m.cyl((0, cy, 0.32), 0.08, 0.065, "carton", axis="Y", segs=12)
        return shared(f"rolls_{decor}_{n}", fn)

    me_frame = shared("edge_rack", frame)
    for ui, x in enumerate((30.5, 33.7), 1):
        u = f"U{ui}"
        instance(f"EB-{u}", "edge", me_frame, loc=(x, 0, 0), code=f"EB-{u}", kind="rack",
                 label=f"Стелаж крайки {u}", desc="Рулони крайки ПВХ стоять на ребрі.")
        obst(x - 0.5, ys, x + 0.5, ye)
        for s in range(1, nsec + 1):
            for li, z in enumerate(levels, 1):
                decor, n = edge_slot(ui, s, li)
                code = f"EB-{u}-S{s}-L{li}"
                instance(code, "edge", rolls(decor, n), loc=(x, ys + (s - 0.5) * sec, z),
                         code=code, kind="stock", label=f"Полиця {code}",
                         desc=f"{n} рулонів крайки по 200 м." if n else "Полиця порожня.")


def build_packstore():
    pk = Mesh()
    for j in range(8):
        y = 48.0 + j * 1.35
        for x in (37.0, 38.3):
            pk.box_lo(x, y, 0, 1.15, 1.0, 0.12, "pallet")
            pk.box_lo(x, y, 0.12, 1.1, 0.95, 0.6 + 0.2 * ((j + int(x)) % 4), "carton")
    for j in range(4):
        y = 59.5 + j * 1.4
        pallet(pk, 37.6, y, sx=1.2, sy=0.8)
        for a in range(2):
            for b in range(3):
                pk.cyl((37.6 - 0.3 + a * 0.6, y, 0.25 + b * 0.22), 0.1, 0.5, "film_roll", axis="X", segs=14)
    pk.box_lo(40.6, 59.0, 0, 0.9, 10.0, 2.4, "shelf", bev=0.01)
    for z in (0.6, 1.2, 1.8):
        pk.box_lo(40.5, 59.0, z, 0.5, 9.6, 0.3, "carton", bev=0.005)

    def pallet_stack(m):
        for k in range(14):
            pallet(m, 0, 0, k * 0.144)
    ps = shared("pallet_stack", pallet_stack)
    for i in range(3):
        code = f"PAL-{i + 1}"
        instance(code, "edge", ps, loc=(37.6, 66.5 + i * 1.3, 0), code=code, kind="stock",
                 label="Стос порожніх палет", desc="14 європалет для готової продукції.")
    pk.build("PACK-STORE", "edge", code="PACK-STORE", kind="stock", label="Пакувальні матеріали",
             desc="Фанфолд-гофрокартон для розкрою коробок, стрейч-плівка, кутики, скотч. "
                  "На пакування возить тягач.")


# ---------------------------------------------------------------- верстати
def build_machines():
    for mch in MACHINES:
        code, typ, name, x, y, desc = mch[:6]
        rz = machine_rz(mch)
        pp = passport(code, SPECS)
        extra = {"maker": pp["manufacturer"], "model": pp["model"]} if pp else {}
        root = empty(code, "facade" if y > 46 else "line", loc=(x, y, 0), rz=rz, code=code,
                     kind="machine", label=name, desc=desc, status=STATUS[code], **extra)
        scale = body_scale(typ, pp)
        tx, ty, tz = TOWER_POS[typ]
        layer = "facade" if y > 46 else "line"

        def body(m, typ=typ, tx=tx, ty=ty, tz=tz):
            from .geom import signal_tower
            MACHINE_BUILDERS[typ](m)
            signal_tower(m, tx, ty, tz)
        instance(code + "_body", layer, shared("machine_" + typ, body), parent=root).scale = scale
        st = STATUS[code]

        def lamp(m, st=st, tx=tx, ty=ty, tz=tz):
            lv = {"work": 0, "idle": 1, "stop": 2}[st]
            m.cyl((tx, ty, tz + 0.34 + lv * 0.075), 0.048, 0.072,
                  {"work": "status_green", "idle": "status_amber", "stop": "status_red"}[st], segs=16)
        instance(code + "_lamp", layer, shared(f"lamp_{typ}_{st}", lamp), parent=root,
                 role="status").scale = scale
        fx, fy = FOOTPRINT[typ]
        if rz % 180:
            fx, fy = fy, fx
        obst(x - fx / 2, y - fy / 2, x + fx / 2, y + fy / 2)


def build_line_conveyors():
    """Рольганги між верстатами ліній A–C і до сортування — щоб потік читався на плані."""
    m = Mesh()
    for y in (5.0, 14.0, 23.0):
        roller_table(m, 51.9, y, 5.0, 1.2, 0.85, pitch=0.35, axis="Y")   # розкрій → крайка
        roller_table(m, 68.5, y + 0.4, 2.2, 1.0, 0.85, pitch=0.35, axis="Y")  # крайка → присадка
    for y in (5.0, 14.0):
        roller_table(m, 79.9, y, 7.2, 1.0, 0.85, pitch=0.35, axis="Y")   # присадка → сортування
    roller_table(m, 91.5, 14.0, 4.0, 1.0, 0.85, pitch=0.35, axis="Y")    # сортування → збирання
    m.build("CONVEYORS", "line", code="CONVEYORS", kind="equipment", label="Рольганги ліній",
            desc="Рольганги передачі деталей: розкрій → крайка → присадка → сортування → збирання.")


def build_maintenance():
    """Ремонтна дільниця між лініями та офісом: верстаки, інструментальні шафи, заточування,
    балансування, стелажі запчастин."""
    m = Mesh()
    for x in (94.2, 97.2):
        m.box_lo(x, 56.6, 0.86, 2.0, 0.8, 0.05, "table_top", bev=0.01)
        legs_frame(m, x, 56.6, 2.0, 0.8, 0.86, mat="steel")
        m.box_lo(x - 0.6, 56.75, 0.91, 0.3, 0.2, 0.15, "machine_dark", bev=0.02)
    m.cyl((97.2, 56.6, 0.93), 0.3, 0.01, "steel", segs=32)
    for x, mat in ((99.6, "status_red"), (100.9, "machine_dark"), (102.2, "machine_dark")):
        m.box_lo(x, 56.9, 0, 1.0, 0.6, 2.0, mat, bev=0.02)
        m.box_lo(x, 56.59, 0.2, 0.01, 0.9, 1.6, "steel_dark")
    m.box_lo(95.0, 50.0, 0, 0.8, 0.6, 0.9, "machine_mid", bev=0.02)  # заточувальний верстат
    m.cyl((95.0, 50.0, 1.05), 0.15, 0.05, "steel_dark", axis="X", segs=20)
    m.box_lo(98.6, 50.0, 0, 1.6, 1.2, 1.3, "machine_mid", bev=0.03)  # балансувальний стенд
    m.cyl((98.6, 50.0, 1.45), 0.2, 0.25, "steel", segs=16)
    for k in range(4):  # стелажі запчастин
        m.box_lo(103.0, 47.6 + k * 2.2, 0, 0.6, 2.0, 2.2, "shelf", bev=0.01)
    m.build("MAINT", "line", code="MAINT-1", kind="building", label="Ремонтна дільниця",
            desc="Поруч із лініями: верстаки, шафи з інструментом, заточування пил, балансування "
                 "фрез, запчастини.")


def build_buffer():
    def cart(k):
        def fn(m):
            m.box_lo(0, 0, 0.15, 1.3, 2.2, 0.04, "steel", bev=0.01)
            for dx in (-0.55, 0.55):
                for dy in (-1.0, 1.0):
                    m.cyl((dx, dy, 0.075), 0.075, 0.05, "rubber", axis="X", segs=14)
            for dy in (-1.05, 1.05):
                m.box_lo(0, dy, 0.19, 1.3, 0.05, 1.1, "steel", bev=0.01)
            m.cyl((0, -1.25, 1.3), 0.025, 1.0, "machine_dark", axis="X", segs=8)
            for j in range(k):
                for i in range(3):
                    m.box_lo(-0.4 + i * 0.4, -0.7 + j * 0.5, 0.19, 0.34, 0.44, 0.2,
                             ("bin", "bin_yellow", "bin")[(i + j) % 3], bev=0.01)
                    m.box_lo(-0.4 + i * 0.4, -0.7 + j * 0.5, 0.6, 0.34, 0.44, 0.18, "carton", bev=0.005)
        return shared(f"cart_{k}", fn)

    k_i = 0
    for row_y in (33.5, 41.5):
        for x in (94.0, 96.5, 99.0, 101.5, 104.0, 106.5):
            k_i += 1
            k = 1 if k_i == 12 else 2 + k_i % 3
            code = f"KIT-{k_i:02d}"
            instance(code, "buffer", cart(k), loc=(x, row_y, 0), code=code, kind="kit",
                     label=f"Візок {code}",
                     desc="Комплект фурнітури під одне замовлення." if k > 1
                     else "Візок майже порожній, чекає на комплектацію.")
    rc = shared("rack_cart", lambda m: rack_cart(m, 0, 0))
    for i, (x, y) in enumerate(((95.0, 37.5), (97.5, 37.5), (100.0, 37.5), (88.5, 66.0), (88.5, 69.0),
                                (88.5, 63.0)), 1):
        code = f"FRONTS-{i}"
        instance(code, "buffer" if y < 46 else "facade", rc, loc=(x, y, 0), code=code, kind="kit",
                 label=f"Етажерка {code}", desc="Готові фасади з завісами, чекають на збирання.")


def build_paint_store():
    ps_ = Mesh()
    for i in range(2):
        for j in range(2):
            x, y = 60.0 + i * 1.6, 68.0 + j * 1.6
            pallet(ps_, x, y)
            for a in (-0.27, 0.27):
                for b in (-0.18, 0.18):
                    ps_.cyl((x + a, y + b, 0.146 + 0.44), 0.27, 0.88, "drum_blue", segs=18)
    for i in range(2):
        x = 64.0
        y = 67.6 + i * 1.6
        pallet(ps_, x, y)
        ps_.box_lo(x, y, 0.15, 1.0, 1.15, 1.0, "ibc")
        for z in (0.4, 0.75, 1.1):
            ps_.box_lo(x, y, z, 1.04, 1.19, 0.03, "steel")
    ps_.box_lo(65.3, 70.8, 0, 1.0, 0.5, 2.0, "shelf", bev=0.01)
    ps_.box_lo(58.4, 67.0, 0.9, 0.2, 0.25, 0.6, "fire_red", bev=0.02)
    ps_.build("PAINT-STORE", "facade", code="PAINT-STORE", kind="stock", label="Склад ЛФМ",
              desc="Фарби, лаки, розчинники, клей: бочки, єврокуби, стелаж банок. "
                   "Окреме вогнестійке приміщення поруч із фарбуванням.")


# ---------------------------------------------------------------- аспірація
def build_dust():
    m = Mesh()
    trunk_x = []
    for mch in MACHINES:
        code, typ, _, mx, my = mch[:5]
        rz = machine_rz(mch)
        for (lx, ly, lz) in DUCT_POINTS.get(typ, []):
            ox, oy = rot2(lx, ly, rz)
            px, py = mx + ox, my + oy
            if py > 46:  # дільниця фасадів — гілка вздовж X до північної ділянки магістралі
                pts = [(px, py, lz), (px, py, DUCT_Z - 0.7), (DUCT_NORTH_X, py, DUCT_Z - 0.7),
                       (DUCT_NORTH_X, py, DUCT_Z)]
            else:
                trunk_x.append(px)
                pts = [(px, py, lz), (px, py, DUCT_Z - 0.7), (px, DUCT_MAIN_Y, DUCT_Z - 0.7),
                       (px, DUCT_MAIN_Y, DUCT_Z)]
            m.tube(rounded_path(pts, radius=0.35), 0.11, "galv", segs=14)
            m.cyl((px, py, lz + 0.1), 0.15, 0.2, "galv", segs=16)
            m.cyl((px, py, DUCT_Z - 1.9), 0.14, 0.12, "steel_dark", segs=16)
    x0, x1 = min(trunk_x) - 0.5, max(trunk_x) + 0.5
    m.tube([(x0, DUCT_MAIN_Y, DUCT_Z), (x1, DUCT_MAIN_Y, DUCT_Z)], 0.38, "galv", segs=22, caps=True)
    fy = D + 5.0
    north = rounded_path([(DUCT_NORTH_X, DUCT_MAIN_Y, DUCT_Z), (DUCT_NORTH_X, fy - 1.5, DUCT_Z),
                          (DUCT_NORTH_X, fy - 1.5, 7.0)], radius=1.2, n=8)
    m.tube(north, 0.4, "galv", segs=22, caps=True)
    for x in range(int(x0) + 2, int(x1), 3):
        m.box_lo(x, DUCT_MAIN_Y, DUCT_Z + 0.38, 0.03, 0.03, H - DUCT_Z - 0.95, "steel_dark")
        m.cyl((x, DUCT_MAIN_Y, DUCT_Z), 0.4, 0.05, "steel_dark", axis="X", segs=22)
    for y in range(int(DUCT_MAIN_Y) + 3, int(D), 3):
        m.box_lo(DUCT_NORTH_X, y, DUCT_Z + 0.4, 0.03, 0.03, H - DUCT_Z - 0.95, "steel_dark")
    fx = DUCT_NORTH_X
    for dx in (-1.4, 1.4):
        for dy in (-1.4, 1.4):
            m.box_lo(fx + dx, fy + dy, 0, 0.16, 0.16, 2.6, "steel_dark")
    m.box_lo(fx, fy, 2.6, 3.2, 3.2, 4.6, "galv", bev=0.05)
    for k in range(7):
        m.box_lo(fx, fy - 1.61, 3.0 + k * 0.6, 3.2, 0.02, 0.05, "steel")
    m.cyl((fx, fy, 2.0), 1.55, 1.2, "galv", r2=0.25, segs=24, rot=(180, 0, 0))
    m.box_lo(fx, fy, 0, 1.1, 1.1, 1.0, "machine_accent", bev=0.03)
    m.box_lo(fx - 3.0, fy, 0, 1.6, 1.3, 1.4, "machine_accent", bev=0.04)
    m.cyl((fx - 3.0, fy, 1.9), 0.45, 1.0, "galv", segs=20)
    m.cyl((fx - 3.0, fy, 5.0), 0.35, 5.2, "galv", segs=20)
    m.box_lo(fx, fy, 7.2, 3.5, 3.5, 0.08, "steel_dark")
    for mch in MACHINES:  # витяжка фарбувальних дільниць крізь покрівлю
        code, typ, _, mx, my = mch[:5]
        rz = machine_rz(mch)
        for (lx, ly, lz) in EXHAUST_POINTS.get(typ, []):
            ox, oy = rot2(lx, ly, rz)
            px, py = mx + ox, my + oy
            m.tube([(px, py, lz), (px, py, H + 1.6)], 0.22, "galv", segs=16)
            m.cone_dir((px, py, H + 2.0), (0, 0, 1), 0.4, 0.3, "galv", segs=16)
            m.box_lo(px, py, H - 1.6, 0.6, 0.6, 0.5, "machine_mid", bev=0.03)
    m.build("DUST", "dust", code="DUST-1", kind="equipment", label="Аспірація",
            desc="Магістраль уздовж ліній між B і C, гілка на північ через дільницю фасадів до "
                 "рукавного фільтра надворі; окремі витяжки фарбувальних дільниць крізь покрівлю.")


# ---------------------------------------------------------------- готова продукція і відвантаження


def build_fg():
    bay_w, nbay, y0 = 2.7, FG_BAYS, 3.0
    levels = [0.0, 1.9, 3.8, 5.7][:FG_LEVELS]
    depth = 1.1

    def frame(m):
        for b in range(nbay + 1):
            for dx in (-depth / 2, depth / 2):
                m.box_lo(dx, b * bay_w, 0, 0.09, 0.07, 7.4, "rack_upright")
                m.box_lo(dx, b * bay_w, 0, 0.18, 0.14, 0.01, "steel_dark")
            for k, z in enumerate((0.6, 1.5, 2.4, 3.3, 4.2, 5.1, 6.0, 6.9)):
                m.box((0, b * bay_w, z), (depth, 0.03, 0.03), "rack_upright",
                      rot=(0, 30 if k % 2 else -30, 0))
        for yy in (0, nbay * bay_w):
            m.box_lo(-depth / 2 - 0.12, yy, 0, 0.12, 0.2, 0.4, "marking", bev=0.01)
            m.box_lo(depth / 2 + 0.12, yy, 0, 0.12, 0.2, 0.4, "marking", bev=0.01)
        for z in levels[1:]:
            for dx in (-depth / 2, depth / 2):
                m.box_lo(dx, nbay * bay_w / 2, z - 0.12, 0.06, nbay * bay_w, 0.12, "rack_beam")

    def load(n, l0, l1):
        def fn(m):
            for p, layers in zip(range(n), (l0, l1)):
                py = -0.65 + p * 1.3
                pallet(m, 0, py, 0.02, sx=1.0, sy=1.2)
                cartons(m, 0, py, 0.166, 0.95, 1.15, layers)
            m.box_lo(-depth / 2 - 0.02, 0, 0.05, 0.01, 0.3, 0.08, "phenolic" if n else "status_amber")
        return shared(f"fg_{n}_{l0}_{l1}", fn)

    me_frame = shared("fg_rack", frame)
    for ri, x in enumerate(FG_ROWS, 1):
        row = f"R{ri}"
        instance(f"FG-RACK-{row}", "fg", me_frame, loc=(x, y0, 0), code=f"FG-RACK-{row}",
                 kind="rack", label=f"Палетний стелаж {row}",
                 desc=f"{nbay} прольотів × {len(levels)} яруси.")
        obst(x - depth / 2 - 0.2, y0, x + depth / 2 + 0.2, y0 + nbay * bay_w)
        for b in range(1, nbay + 1):
            for li, z in enumerate(levels, 1):
                code = f"FG-{row}-B{b:02d}-L{li}"
                n, l0, l1, pi = fg_slot(ri, b, li)
                prod = FG_PRODUCTS[pi]
                instance(code, "fg", load(n, l0 if n else 0, l1 if n > 1 else 0),
                         loc=(x, y0 + (b - 0.5) * bay_w, z), code=code, kind="stock",
                         label=f"Комірка {code}", desc=f"{prod}: {n} палет." if n else "Вільно.")


def build_post_and_shipping():
    m = Mesh()
    for j, y in enumerate((36.0, 40.0, 44.0, 48.0, 52.0, 56.0)):
        for i, x in enumerate((112.0, 113.7, 115.4, 117.1, 118.8, 120.5)):
            if (i + j) % 4 == 3:
                continue
            pallet(m, x, y)
            cartons(m, x, y, 0.146, 1.15, 0.75, 2 + (i + j) % 2)
    m.build("POST-STAGE", "fg", code="POST-STAGE", kind="stock", label="Готово до розміщення",
            desc="Запаковані палети чекають, поки навантажувач поставить їх у стелаж.")

    s = Mesh()
    for j, (_, y, _) in enumerate(d for d in DOORS if d[0] == "E"):
        for k in range(6):
            x = 138.5 + k * 1.7
            if (j * 3 + k) % 5 == 4:
                continue
            pallet(s, x, y)
            cartons(s, x, y, 0.146, 1.15, 0.75, 2 + (j + k) % 2)
        for dy in (-0.75, 0.75):
            s.box((143.0, y + dy, 0.022), (11.0, 0.08, 0.02), "marking")
    s.build("OUT-STAGE", "shipping", code="OUT-STAGE", kind="stock",
            label="Відвантаження на сьогодні",
            desc="Перед кожними з семи воріт — коридор із палетами, зібраними під машину.")
    obst(136.0, 0.0, W, D)


# ---------------------------------------------------------------- інженерія
def build_utilities():
    c = Mesh()
    for y in (64.0, 67.2):
        c.box_lo(111.6, y, 0, 1.0, 1.9, 1.7, "machine_accent", bev=0.05)
        for k in range(6):
            c.box_lo(112.11, y, 0.3 + k * 0.2, 0.02, 1.5, 0.06, "steel")
        c.cyl((111.6, y, 1.75), 0.35, 0.1, "machine_dark", segs=20)
    for dx in (-0.4, 0.4):
        for dy in (-0.4, 0.4):
            c.box_lo(114.2 + dx, 70.2 + dy, 0, 0.08, 0.08, 0.5, "steel_dark")
    c.cyl((114.2, 70.2, 1.6), 0.62, 2.2, "galv", segs=24)
    c.sphere((114.2, 70.2, 2.7), 0.62, "galv", scale=(1, 1, 0.4))
    c.sphere((114.2, 70.2, 0.5), 0.62, "galv", scale=(1, 1, 0.4))
    c.box_lo(114.6, 62.0, 0, 1.2, 0.8, 1.3, "machine_mid", bev=0.04)
    c.tube(rounded_path([(112.1, 64.0, 1.8), (113.0, 64.0, 2.6), (113.0, 70.2, 2.6), (113.6, 70.2, 2.6)],
                        radius=0.25), 0.05, "air_blue", segs=10)
    c.tube(rounded_path([(114.2, 70.2, 3.0), (114.2, 70.2, 8.15), (114.2, 61.0, 8.15)], radius=0.3),
           0.06, "air_blue", segs=10)
    c.build("COMPRESSOR", "utilities", code="COMPRESSOR", kind="equipment", label="Компресорна станція",
            desc="Два гвинтові компресори, ресивер 2 м³, рефрижераторний осушувач і фільтри.")

    a = Mesh()
    ring = [(114.2, 61.0, 8.15), (109.8, 61.0, 8.15), (109.8, 1.5, 8.15), (42.6, 1.5, 8.15),
            (42.6, 45.8, 8.15), (109.8, 45.8, 8.15)]
    a.tube(rounded_path(ring, radius=0.6), 0.06, "air_blue", segs=10)
    for x in range(46, 108, 6):
        a.tube([(x, 1.5, 8.15), (x, 1.5, 2.0)], 0.03, "air_blue", segs=8)
        a.box_lo(x, 1.5, 1.2, 0.15, 0.12, 0.3, "machine_dark")
    a.build("AIR-RING", "utilities", code="AIR-RING", kind="equipment", label="Пневмомагістраль",
            desc="Кільце стисненого повітря 6 бар над виробничою зоною з опусками до дільниць.")

    z = Mesh()
    for k in range(3):
        x = 117.4 + k * 1.8
        z.box_lo(x, 71.0, 0.6, 0.6, 0.35, 1.0, "machine_mid", bev=0.03)
        z.box((x, 70.82, 1.3), (0.3, 0.02, 0.18), "screen_on")
        z.tube([(x, 70.8, 0.7), (x, 70.0, 0.3), (x, 69.0, 0.6)], 0.025, "rubber", segs=8)
        z.box((x - 0.9, 66.0, 0.022), (0.08, 9.0, 0.02), "marking")
    z.build("CHARGING", "utilities", code="CHARGING", kind="equipment", label="Зарядна станція",
            desc="Зарядні пристрої для тягових АКБ навантажувачів, витяжна вентиляція.")
    for i, x in enumerate((117.4, 119.2)):
        instance(f"FL-C{i + 1}", "transport", shared("fl_empty", forklift), loc=(x, 67.5, 0), rz=-90,
                 code=f"FL-C{i + 1}", kind="vehicle", label="Навантажувач на зарядці",
                 desc="Акумулятор заряджається.")

    s = Mesh()
    s.box_lo(1.0, D / 2, H - 0.75, 0.12, D - 2, 0.12, "fire_red")
    for y in range(5, int(D), 5):
        s.box_lo(W / 2, y, H - 0.7, W - 1.5, 0.05, 0.05, "fire_red")
        for x in range(4, int(W), 4):
            s.box_lo(x, y, H - 0.8, 0.03, 0.03, 0.1, "steel")
    s.build("SPRINKLERS", "roof", code="SPRINKLERS", kind="equipment", label="Спринклерне пожежогасіння",
            desc="Розподільні трубопроводи під покрівлею, зрошувачі з кроком 4 × 5 м.")

    o = Mesh()
    sx, sy = DUCT_NORTH_X + 7.0, D + 6.0
    for dx in (-1.4, 1.4):
        for dy in (-1.4, 1.4):
            o.box_lo(sx + dx, sy + dy, 0, 0.18, 0.18, 3.0, "steel_dark")
    o.cyl((sx, sy, 6.5), 2.0, 7.0, "galv", segs=28)
    o.cyl((sx, sy, 2.4), 2.0, 1.2, "galv", r2=0.3, segs=28, rot=(180, 0, 0))
    o.cone_dir((sx, sy, 11.6), (0, 0, 1), 2.05, 0.6, "galv", segs=28)
    o.tube([(DUCT_NORTH_X + 1.0, D + 5.0, 6.8), (sx - 1.5, sy, 10.6)], 0.25, "galv", segs=14)
    bx, by = sx + 9.0, D + 6.0
    o.box_lo(bx, by, 0, 8.0, 6.0, 4.5, "wall")
    o.box_lo(bx, by, 4.5, 8.2, 6.2, 0.2, "wall_band")
    o.box_lo(bx - 2.0, by - 3.01, 0, 2.4, 0.05, 3.0, "steel_dark")
    for k in range(4):
        o.box_lo(bx + 1.0 + k * 0.8, by - 3.01, 1.8, 0.5, 0.04, 1.2, "glass")
    o.cyl((bx + 3.0, by + 2.0, 7.7), 0.45, 15.4, "steel", segs=20)
    o.cyl((bx + 3.0, by + 2.0, 15.5), 0.5, 0.2, "steel_dark", segs=20)
    o.tube([(sx + 0.3, sy, 1.9), (sx + 1.5, sy, 1.2), (bx - 4.0, by, 1.2)], 0.2, "steel", segs=12)
    px, py = sx - 1.0, D + 10.0
    o.box_lo(px, py, 0, 2.4, 1.1, 1.3, "machine_accent", bev=0.05)
    o.box((px - 0.6, py, 1.75), (1.0, 1.0, 0.9), "galv")
    o.box((px + 1.6, py, 0.75), (1.0, 0.3, 0.06), "steel", rot=(0, 20, 0))
    for k in range(3):
        pallet(o, px + 3.0 + k * 1.4, py, sx=1.2, sy=1.0)
        o.box_lo(px + 3.0 + k * 1.4, py, 0.146, 0.95, 0.9, 0.9, "carton_bag", bev=0.08)
    for tx in (8.0, 17.0):
        o.cyl((tx, D + 7.0, 4.0), 3.5, 8.0, "galv", segs=32)
        o.cyl((tx, D + 7.0, 8.1), 3.55, 0.2, "steel", segs=32)
        for k in range(10):
            o.box_lo(tx + 3.55, D + 7.0, k * 0.8, 0.05, 0.5, 0.04, "steel_dark")
    o.box_lo(25.0, D + 5.5, 0, 4.0, 3.0, 3.0, "wall")
    o.box_lo(25.0, D + 5.5, 3.0, 4.2, 3.2, 0.15, "fire_red")
    o.tube([(20.5, D + 7.0, 1.0), (23.0, D + 5.5, 1.0)], 0.12, "fire_red", segs=12)
    o.tube([(25.0, D + 4.0, 1.0), (25.0, D + 0.3, 1.0)], 0.12, "fire_red", segs=12)
    o.build("OUTSIDE", "utilities", code="BOILER", kind="equipment", label="Котельня, силос, брикетування",
            desc="Котельня на деревних відходах, силос стружки від аспірації, брикетувальний прес; "
                 "два пожежні резервуари по 300 м³ і насосна пожежогасіння.")


# ---------------------------------------------------------------- електропостачання
def duct(m, pts, w, h, mat="busbar", joint=3.0, hang=True):
    """Короб шинопроводу вздовж ортогональної ламаної: стики кожні joint м, підвіси до ферм."""
    for a, b in zip(pts, pts[1:]):
        dx, dy, dz = (b[i] - a[i] for i in range(3))
        ln = abs(dx) + abs(dy) + abs(dz)
        if ln < 1e-6:
            continue
        c = tuple((a[i] + b[i]) / 2 for i in range(3))
        if abs(dx) > 1e-6:
            size, ax = (ln + w, w, h), 0
        elif abs(dy) > 1e-6:
            size, ax = (w, ln + w, h), 1
        else:
            size, ax = (w, h, ln + h), 2
        m.box(c, size, mat)
        if ax == 2:
            continue
        n = int(ln // joint)
        for k in range(1, n + 1):
            t = k * joint / ln
            p = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
            js = [w + 0.04, w + 0.04, h + 0.04]
            js[ax] = 0.1
            m.box(p, tuple(js), "steel_dark")
            if hang:
                m.box_lo(p[0], p[1], p[2] + h / 2, 0.025, 0.025, H - 0.6 - p[2] - h / 2, "steel_dark")


def build_energy():
    def ex(code):
        pp = energy_passport(code, SPECS)
        return {"maker": pp["manufacturer"], "model": pp["model"]} if pp else {}

    # електрощитова: сітчасте огородження з дверима, діелектричний килим перед ГРЩ
    rm = Mesh()
    x0, y0, x1, y1 = ROOM
    for pts in ([(x0, y1), (x0, y0), (EMS_POS[0] - 0.8, y0)], [(EMS_POS[0] + 0.8, y0), (x1, y0), (x1, y1)]):
        for a, b in zip(pts, pts[1:]):
            n = max(1, round(math.dist(a, b) / 2.0))
            for k in range(n + 1):
                px, py = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
                rm.box_lo(px, py, 0, 0.06, 0.06, 2.4, "steel_dark")
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            sx, sy = (abs(b[0] - a[0]) or 0.02), (abs(b[1] - a[1]) or 0.02)
            rm.box_lo(mx, my, 0.1, sx, sy, 2.25, "mesh_fence")
            rm.box_lo(mx, my, 2.35, sx or 0.05, sy or 0.05, 0.05, "steel_dark")
    for sx in (EMS_POS[0] - 2.2, EMS_POS[0] + 2.2, x0 + 1.5):  # знаки «Обережно! Електрична напруга»
        rm.cone_dir((sx, y0 - 0.04, 1.75), (0, 0, -1), 0.2, 0.34, "marking", segs=3)
    rm.box_lo((SWB_X0 + SWB_X1) / 2, SWB_Y - SWB_D / 2 - 0.55, 0, SWB_X1 - SWB_X0, 1.0, 0.012, "rubber")
    rm.build("Огородження електрощитової", "energy")
    obst(x0 - 0.3, y0 - 0.3, x1 + 0.3, y1)

    # комірки 10 кВ
    v = Mesh()
    vx, vy = RM6_POS
    vw, vd, vh = 1.62, 0.71, 1.14  # RM6 NE-QIQI за паспортом
    v.box_lo(vx, vy, 0, vw, vd, vh, "elec_cab", bev=0.02)
    for k in range(4):
        cx = vx - 0.6 + k * 0.4
        v.box_lo(cx, vy - vd / 2 - 0.005, 0.55, 0.34, 0.01, 0.5, "machine_mid")
        v.box_lo(cx, vy - vd / 2 - 0.01, 0.85, 0.3, 0.01, 0.025, "steel_dark")  # мнемосхема
        v.cyl((cx, vy - vd / 2 - 0.02, 0.7), 0.035, 0.03, "estop", axis="Y", segs=12)
        v.box_lo(cx, vy - vd / 2 - 0.005, 0.12, 0.3, 0.01, 0.3, "steel_dark")  # кабельний відсік
    for tx, _ in TRAFOS.values():  # кабелі 10 кВ у кабельному каналі до трансформаторів
        v.box_lo((vx + tx) / 2 + 0.3, vy - 1.15, 0, abs(tx - vx) + 0.6, 0.5, 0.015, "steel_dark")
        v.box_lo(tx, (vy + TRAFO_Y) / 2 - 0.3, 0, 0.5, vy - 1.15 - TRAFO_Y + 0.25, 0.015, "steel_dark")
    v.build("RM6-1", "energy", code="RM6-1", kind="power", label="Комірки 10 кВ", **ex("RM6-1"),
            desc="Ввід 10 кВ від мережі і дві трансформаторні комірки з вимикачами навантаження та "
                 "запобіжниками; кабелі до Т1 і Т2 — у каналі під плитами підлоги.")

    # трансформатори в захисних кожухах + шинопроводи до вводів ГРЩ
    for code, (tx, ty) in TRAFOS.items():
        t = Mesh()
        cw, cd, ch = 2.0, 1.17, 2.4  # кожух IP31 Trihal 1000 кВА за паспортом
        t.box_lo(tx, ty, 0, cw + 0.1, cd + 0.1, 0.12, "steel_dark")
        for dx in (-cw / 2, cw / 2):
            for dy in (-cd / 2, cd / 2):
                t.box_lo(tx + dx, ty + dy, 0.12, 0.06, 0.06, ch - 0.12, "elec_cab")
        t.box_lo(tx, ty, ch - 0.06, cw + 0.06, cd + 0.06, 0.08, "elec_cab")
        t.box_lo(tx, ty + cd / 2, 0.12, cw, 0.03, ch - 0.18, "elec_cab")
        t.box_lo(tx, ty - cd / 2, 0.15, cw - 0.08, 0.02, ch - 0.25, "mesh_fence")  # оглядова сітка
        for sx in (-1, 1):
            t.box_lo(tx + sx * cw / 2, ty, 0.12, 0.03, cd, ch - 0.18, "elec_cab")
            for k in range(8):
                t.box_lo(tx + sx * (cw / 2 + 0.01), ty, 1.2 + k * 0.12, 0.01, cd - 0.3, 0.04, "steel_dark")
        t.box_lo(tx, ty, 0.12, 1.8, 0.7, 0.18, "steel_dark")  # візок
        for k in range(3):
            cx = tx - 0.62 + k * 0.62
            t.cyl((cx, ty, 1.05), 0.27, 1.25, "trafo_coil", segs=24)
            t.cyl((cx, ty, 1.72), 0.12, 0.1, "copper", segs=12)
        for z in (0.32, 1.78):
            t.box_lo(tx, ty, z, 1.75, 0.3, 0.14, "steel_dark")  # ярма магнітопроводу
        t.box_lo(tx, ty - cd / 2 - 0.02, 1.9, 0.36, 0.01, 0.22, "alu")  # табличка
        # шинопровід трансформатор → ввід ГРЩ
        duct(t, [(tx, ty, ch), (tx, ty, 3.1), (tx, SWB_Y, 3.1), (tx, SWB_Y, SWB_H)], 0.14, 0.164, hang=False)
        q = "Q1" if code == "T1" else "Q2"
        t.build(code, "energy", code=code, kind="power", label=f"Трансформатор {code}", **ex(code),
                desc=f"Сухий трансформатор 1000 кВА 10/0,4 кВ у захисному кожусі; шинопровід "
                     f"над проходом заходить зверху у ввідну шафу {q}.")

    # ГРЩ: кожна шафа — окремий об'єкт, щоб клік показував свій фідер
    root = empty("SWB-1", "energy", code="SWB-1", kind="power", label="ГРЩ 0,4 кВ", **ex("SWB-1"),
                 desc="Головний розподільний щит: дві секції шин, два вводи, секційний вимикач, "
                      "фідери шинопроводів і кабельних ліній, установки компенсації.")
    for code, name, w, typ, feeds in SWB_CELLS:
        c = Mesh()
        x = CELL_X[code]
        fy = SWB_Y - SWB_D / 2
        ch = PFC_H if typ == "pfc" else SWB_H
        c.box_lo(x, SWB_Y, 0, w - 0.012, SWB_D, 0.1, "steel_dark")
        c.box_lo(x, SWB_Y, 0.1, w - 0.012, SWB_D, ch - 0.1, "elec_cab")
        c.box_lo(x, fy - 0.005, 0.12, 0.012, 0.01, ch - 0.2, "machine_mid")
        if typ in ("incomer", "coupler"):
            c.box_lo(x, fy - 0.01, 0.95, w * 0.6, 0.02, 0.45, "machine_dark", bev=0.01)  # ACB
            c.box_lo(x, fy - 0.03, 1.12, w * 0.3, 0.02, 0.1, "screen_on")
            c.cyl((x + w * 0.22, fy - 0.03, 1.05), 0.03, 0.03, "status_green", axis="Y", segs=10)
        if typ == "incomer":
            for k in range(3):
                c.box_lo(x - 0.25 + k * 0.25, fy - 0.01, 1.7, 0.16, 0.01, 0.12, "screen_on")
        if typ in ("feeder", "cable"):
            for k in range(4 if typ == "cable" else 2):
                c.box_lo(x, fy - 0.01, 0.4 + k * 0.4, w * 0.55, 0.02, 0.24, "machine_dark", bev=0.01)
                c.box_lo(x + w * 0.18, fy - 0.025, 0.47 + k * 0.4, 0.06, 0.02, 0.1, "estop")
            c.box_lo(x, fy - 0.015, 1.8, 0.16, 0.02, 0.14, "screen_on")  # лічильник фідера
        if typ == "pfc":
            for k in range(10):
                c.box_lo(x, fy - 0.005, 0.25 + k * 0.08, w * 0.7, 0.01, 0.03, "steel_dark")
            c.box_lo(x, fy - 0.015, 1.75, 0.16, 0.02, 0.14, "screen_on")
            c.box_lo(x, SWB_Y, ch, w * 0.5, SWB_D * 0.5, 0.08, "steel_dark")  # вентилятор
        c.box_lo(x, fy - 0.01, ch - 0.12, w * 0.7, 0.01, 0.07, "phenolic")  # бирка
        c.build("SWB_" + code, "energy", parent=root, code=code, kind="power", label=f"Шафа {code}", desc=name,
                **ex(code))

    # розподільні шинопроводи з відгалужувальними коробками й кабелями до верстатів
    tp = taps()
    for b in BUSWAYS:
        m = Mesh()
        pts = [(x, y, BUS_Z) for x, y in b["path"]]
        x, y = b["path"][0]
        duct(m, [(x, y, SWB_H)] + pts, 0.113, 0.146)  # Canalis KSA: переріз 113 × 146 мм
        for code, t in tp.items():
            if t["bus"] != b["code"]:
                continue
            tx, ty = t["tap"]
            cx, cy, cz = t["conn"]
            zb = BUS_Z - 0.073 - 0.31  # коробка KSB…DC4: 450 × 310 × 246 мм під шинопроводом
            m.box_lo(tx, ty, zb, 0.45, 0.246, 0.31, "elec_cab", bev=0.01)
            m.box_lo(tx + 0.12, ty - 0.13, zb + 0.08, 0.06, 0.03, 0.15, "machine_dark")
            path = [(tx, ty, zb), (tx, ty, CABLE_Z), (tx, cy, CABLE_Z), (cx, cy, CABLE_Z), (cx, cy, cz)]
            path = [p for i, p in enumerate(path) if i == 0 or math.dist(p, path[i - 1]) > 0.05]
            m.tube(rounded_path(path, radius=0.3), 0.025, "rubber", segs=8)
        m.build(b["code"], "energy", code=b["code"], kind="power", label=b["name"], **ex(b["code"]),
                desc=f"Розподільний шинопровід {b['rating']} А від фідера {b['feeder']}; відгалужувальні "
                     "коробки з автоматами живлять верстати кабелями зверху.")

    # кабельні фідери: лоток уздовж північної стіни, щити компресорної й зарядної, виходи надвір
    tr = Mesh()
    west = 57.0
    for code in ("QF-C1", "QF-C2"):
        x = CELL_X[code]
        duct(tr, [(x, SWB_Y, SWB_H), (x, SWB_Y, TRAY_Z), (x, TRAY_Y, TRAY_Z)], 0.3, 0.1, mat="galv", hang=False)
    xe = CELL_X["QF-C2"]
    tr.box((((xe + west) / 2), TRAY_Y, TRAY_Z), (xe - west, 0.3, 0.08), "galv")
    tr.box((((xe + west) / 2), TRAY_Y, TRAY_Z + 0.06), (xe - west, 0.22, 0.05), "rubber")
    for k in range(int((xe - west) // 2.5) + 1):
        bx = west + 0.5 + k * 2.5
        tr.box_lo(bx, (TRAY_Y + D) / 2, TRAY_Z - 0.06, 0.04, D - TRAY_Y + 0.2, 0.04, "steel_dark")
    for px, top, bottom in ((113.2, 2.4, 1.4), (118.3, 2.8, 2.0)):  # щити компресорної та зарядної
        tr.box_lo(px, 71.8, bottom, 0.6, 0.25, top - bottom, "elec_cab", bev=0.01)
        tr.box_lo(px, 71.67, bottom + 0.3, 0.1, 0.01, 0.12, "screen_on")
        tr.tube(rounded_path([(px, TRAY_Y, TRAY_Z - 0.04), (px, 71.8, TRAY_Z - 0.4), (px, 71.8, top)],
                             radius=0.2), 0.03, "rubber", segs=8)
    tr.tube(rounded_path([(west, TRAY_Y, TRAY_Z), (west - 0.5, TRAY_Y, TRAY_Z), (west - 0.5, D + 0.6, TRAY_Z),
                          (west - 0.5, D + 0.6, 2.2), (53.0, D + 0.6, 2.2), (53.0, D + 1.4, 1.8)], radius=0.3),
            0.05, "rubber", segs=10)
    tr.box_lo(53.0, D + 1.4, 0, 0.8, 0.4, 1.8, "elec_cab", bev=0.02)  # щит аспірації надворі
    tr.box_lo(53.0, D + 1.19, 1.3, 0.12, 0.01, 0.1, "screen_on")
    bxx = DUCT_NORTH_X + 7.0 + 9.0 + 1.2
    tr.tube(rounded_path([(bxx, TRAY_Y, TRAY_Z), (bxx, D + 0.6, TRAY_Z), (bxx, D + 0.6, 3.2), (bxx, D + 3.0, 3.2)],
                         radius=0.3), 0.05, "rubber", segs=10)
    tr.build("CABLES", "energy", code="CABLES", kind="power", label="Кабельні фідери",
             desc="Кабельний лоток уздовж північної стіни: компресорна, зарядна, офіс, освітлення, "
                  "вентиляція; через стіну — до щита аспірації та котельні.")

    # АРМ енергетика: стіл, два монітори з мнемосхемою і графіком споживання
    e = Mesh()
    qx, qy = EMS_POS
    e.box_lo(qx, qy, 0.72, 1.6, 0.8, 0.04, "table_top", bev=0.01)
    legs_frame(e, qx, qy, 1.6, 0.8, 0.72, mat="steel_dark")
    for dx in (-0.36, 0.36):
        e.box_lo(qx + dx, qy + 0.2, 0.76, 0.08, 0.08, 0.3, "steel_dark")
        e.box((qx + dx, qy + 0.17, 1.28), (0.62, 0.04, 0.38), "machine_dark", rot=(-8, 0, 0))
        e.box((qx + dx, qy + 0.145, 1.28), (0.58, 0.01, 0.34), "screen_on", rot=(-8, 0, 0))
    e.box_lo(qx, qy - 0.1, 0.76, 0.45, 0.15, 0.02, "machine_dark")
    e.box_lo(qx, qy - 0.75, 0, 0.5, 0.5, 0.48, "machine_dark", bev=0.05)
    e.box_lo(qx, qy - 0.98, 0.48, 0.5, 0.06, 0.6, "machine_dark", bev=0.03)
    e.build("EMS-1", "energy", code="EMS-1", kind="power", label="АРМ енергетика", **ex("EMS-1"),
            desc="Мнемосхема ГРЩ, графік споживання, журнал подій; дані — з лічильників на кожному "
                 "фідері по Modbus TCP.")


# ---------------------------------------------------------------- люди, транспорт, маршрути
def build_people():
    def body(vest, arms):
        return shared(f"person_{vest}_{arms}", lambda m: person(m, 0, 0, 0, vest, arms))

    people = []
    for mch in MACHINES:
        code, typ, name, x, y = mch[:5]
        rz = machine_rz(mch)
        st = STATUS[code]
        if st == "idle" or OPERATOR.get(typ) is None:
            continue
        ox, oy, prz = OPERATOR[typ]
        ox, oy = rot2(ox, oy, rz)
        vest = "hivis_or" if st == "stop" else "hivis"
        if typ in ("spray", "glue", "autospray", "uv"):
            vest = "phenolic"
        label = "Налагоджувальник" if st == "stop" else "Оператор"
        people.append((f"OP-{code}", f"{label} · {name}", x + ox, y + oy, prz + rz, vest,
                       "down" if st == "stop" else "front",
                       "Діагностика зупинки верстата." if st == "stop" else f"Працює на дільниці «{name}»."))
    people += [
        ("OP-W1", "Комірник", 22.0, 50.2, -90, "hivis", "front", "Комплектування фурнітури."),
        ("OP-W2", "Комірник", 18.0, 58.6, 90, "hivis", "front", "Комплектування фурнітури."),
        ("OP-W3", "Приймальник", 8.0, 12.0, 180, "hivis_or", "down", "Звірка поставки з накладною."),
        ("OP-W4", "Контролер ВТК", 10.0, 32.2, 90, "hivis", "front", "Заміри товщини й декору."),
        ("OP-W5", "Оператор порталу", 40.0, 44.8, -90, "hivis", "front", "Керує портальним складом."),
        ("OP-W6", "Комірник ГП", 116.0, 44.0, 0, "hivis_or", "down", "Маркування запакованих палет."),
        ("OP-W7", "Комплектувальник", 140.0, 24.0, 180, "hivis_or", "down", "Збирає відвантаження."),
    ]
    for code, label, x, y, rz, vest, arms, desc in people:
        instance(code, "people", body(vest, arms), loc=(x, y, 0), rz=rz, code=code,
                 kind="person", label=label, desc=desc)


def build_transport():
    def fl_pallet(m):
        forklift(m)
        pallet(m, 1.45, 0, 0.14)
        cartons(m, 1.45, 0, 0.286, 1.1, 0.75, 1)

    def fl_sheets(m):
        forklift(m)
        sheet_stack(m, 1.6, 0, 0.14, 22, 1)

    for code, label, x, y, rz, fn, desc in (
            ("FL-1", "Навантажувач ГП 1", 125.4, 30.0, 90, fl_pallet,
             "Ставить палету в стелаж, висота підйому 6 м."),
            ("FL-2", "Навантажувач приймання", 11.5, 21.0, 0, fl_sheets,
             "Везе стос плит із фури до зони порталу."),
            ("FL-3", "Навантажувач відвантаження", 145.5, 45.0, 0, fl_pallet,
             "Вантажить палету в машину біля воріт 5."),
            ("FL-4", "Навантажувач ГП 2", 131.2, 40.0, -90, fl_pallet,
             "Знімає палету з третього ярусу."),
            ("FL-5", "Навантажувач пакування", 120.5, 16.0, 90, fl_pallet,
             "Відвозить запаковані палети в зону виходу.")):
        key = "fl_sheets" if fn is fl_sheets else "fl_pallet"
        instance(code, "transport", shared(key, fn), loc=(x, y, 0), rz=rz, code=code,
                 kind="vehicle", label=label, desc=desc)

    def tugger(m):
        """Електротягач із трьома візками — возить комплекти й пакматеріали за маршрутом."""
        m.box_lo(0, 0, 0.15, 1.4, 0.9, 0.9, "forklift", bev=0.08)
        m.box_lo(-0.2, 0, 1.05, 0.5, 0.5, 0.15, "machine_dark", bev=0.04)
        for dx in (-0.5, 0.5):
            for dy in (-0.4, 0.4):
                m.cyl((dx, dy, 0.2), 0.2, 0.15, "rubber", axis="Y", segs=14)
        for k in range(3):
            cx = -2.0 - k * 1.9
            m.box_lo(cx, 0, 0.3, 1.6, 0.9, 0.05, "steel", bev=0.01)
            for dx in (-0.6, 0.6):
                for dy in (-0.35, 0.35):
                    m.cyl((cx + dx, dy, 0.12), 0.1, 0.08, "rubber", axis="Y", segs=10)
            m.box_lo(cx, 0, 0.35, 1.3, 0.8, 0.5 + 0.2 * k, "carton", bev=0.01)
    instance("TUGGER-1", "transport", shared("tugger", tugger), loc=(90.0, 45.9, 0), rz=0,
             code="TUGGER-1", kind="vehicle", label="Електротягач із візками",
             desc="Возить фурнітуру й пакувальні матеріали зі складів на збирання та пакування.")

    def truck(m, length=13.6):
        m.box_lo(0, 0, 1.1, length, 2.5, 2.9, "trailer", bev=0.04)
        for k in range(1, 12):
            m.box_lo(-length / 2 + k * length / 12, -1.255, 1.15, 0.04, 0.01, 2.8, "machine_mid")
        m.box_lo(-length / 2 - 1.15, 0, 0.6, 2.2, 2.4, 2.6, "truck_cab", bev=0.12)
        m.box_lo(-length / 2 - 2.2, 0, 1.9, 0.1, 2.1, 1.0, "glass")
        m.box_lo(-length / 2 - 2.25, 0, 0.6, 0.1, 2.2, 0.4, "machine_dark", bev=0.03)
        m.box_lo(-1.0, 0, 0.6, length, 1.0, 0.5, "steel_dark")
        for x in (-length / 2 - 1.5, length / 2 - 3.6, length / 2 - 2.3, length / 2 - 1.0):
            for dy in (-1.0, 1.0):
                m.cyl((x, dy, 0.5), 0.5, 0.35, "rubber", axis="Y", segs=20)
                m.cyl((x, dy * 1.01, 0.5), 0.28, 0.36, "steel", axis="Y", segs=14)

    me = shared("truck", truck)
    for code, label, x, y, rz in (("TRUCK-IN-1", "Фура на розвантаженні", -7.3, 5.0, 0),
                                  ("TRUCK-IN-2", "Фура на розвантаженні", -7.3, 25.0, 0),
                                  ("TRUCK-IN-3", "Фура на розвантаженні", -7.3, 45.0, 0),
                                  ("TRUCK-OUT-1", "Машина під навантаженням", W + 7.3, 15.0, 180),
                                  ("TRUCK-OUT-2", "Машина під навантаженням", W + 7.3, 45.0, 180),
                                  ("TRUCK-OUT-3", "Машина під навантаженням", W + 7.3, 65.0, 180)):
        instance(code, "transport", me, loc=(x, y, 0), rz=rz, code=code, kind="vehicle",
                 label=label, desc="Напівпричіп 13,6 м біля воріт.")


def build_all():
    LAYER_OBJ["building"].parent["dims"] = f"{W:.0f} × {D:.0f} м · h {H:.0f} м"
    build_building()
    build_zones()
    build_receiving()
    build_sheets()
    build_hardware()
    build_edge()
    build_packstore()
    build_machines()
    build_line_conveyors()
    build_maintenance()
    build_buffer()
    build_paint_store()
    build_dust()
    build_fg()
    build_post_and_shipping()
    build_utilities()
    build_energy()
    build_transport()
    build_people()
    build_columns()
