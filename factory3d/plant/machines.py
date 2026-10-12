"""Процедурні моделі верстатів. Кожна функція будує верстат у локальних координатах:
центр на підлозі в (0, 0), потік матеріалу вздовж +X, оператор зазвичай з боку −Y."""
import math

from .geom import (cabinet, console, estop, fence, floor_frame, hazard, legs_frame, pallet, cartons,
                   rack_cart, robot, roller_table)


def machine_saw(m):
    """Розкрійний центр: задній підйомний стіл, програмний штовхач, притискна балка,
    передні пневмостоли з отворами, кутовий упор, пульт."""
    # задній підйомний стіл зі стосом
    m.box_lo(-1.75, 0, 0, 2.9, 3.6, 0.35, "machine_mid", bev=0.03)
    for dx in (-0.9, 0.0, 0.9):
        m.box((-1.75 + dx, 0, 0.42), (0.08, 3.4, 0.14), "steel_dark", rot=(0, 0, 0))
    m.box_lo(-1.75, 0, 0.5, 2.82, 3.4, 0.04, "steel", bev=0.01)
    m.box_lo(-1.75, 0, 0.54, 2.8, 2.07, 0.3, "decor0")
    m.box((-1.75, -1.036, 0.69), (2.8, 0.004, 0.004), "machine_dark")
    # програмний штовхач: напрямні + портал із цангами
    for dy in (-2.1, 2.1):
        m.box_lo(-1.8, dy, 0, 3.6, 0.22, 1.05, "machine", bev=0.03)
        m.box_lo(-1.8, dy, 1.05, 3.6, 0.14, 0.06, "alu", bev=0.01)
        hazard(m, -3.55, -0.05, dy + (0.12 if dy > 0 else -0.12), 0.0, depth=0.01, h=0.12)
    m.box_lo(-2.6, 0, 1.0, 0.32, 4.5, 0.26, "machine_accent", bev=0.04)
    m.box_lo(-2.6, 0, 1.26, 0.25, 4.3, 0.08, "machine_dark", bev=0.01)
    for k in range(8):
        m.box_lo(-2.38, -1.75 + k * 0.5, 0.82, 0.12, 0.08, 0.2, "machine_dark", bev=0.01)
    # корпус пильної лінії та притискна балка
    m.box_lo(0.25, 0, 0, 0.9, 4.7, 0.86, "machine", bev=0.04)
    m.box_lo(0.25, 0, 0.86, 0.9, 4.5, 0.03, "steel")
    m.box((0.25, 0, 0.895), (0.03, 4.4, 0.01), "hazard_black")
    for dy in (-2.55, 2.55):
        m.box_lo(0.25, dy, 0, 0.75, 0.5, 1.6, "machine_accent", bev=0.05)
    m.box_lo(0.25, 0, 1.5, 0.95, 5.6, 0.52, "machine_accent", bev=0.08)
    m.box_lo(0.72, 0, 1.58, 0.02, 4.9, 0.36, "machine", bev=0.01)  # передня кришка
    m.box_lo(0.25, 0, 1.04, 0.3, 4.6, 0.1, "steel", bev=0.01)        # притискна шина
    for k in range(6):
        m.cyl((0.25, -1.9 + k * 0.76, 1.27), 0.05, 0.38, "alu", segs=12)  # пневмоциліндри
    m.box_lo(0.25, 3.0, 0.2, 0.7, 0.5, 0.7, "machine_dark", bev=0.04)  # двигун пили
    m.cyl((0.25, 2.65, 1.05), 0.16, 0.12, "steel_dark", axis="Y", segs=24)
    # передні пневмостоли
    for dy in (-1.45, 0.0, 1.45):
        legs_frame(m, 1.95, dy, 2.3, 1.15, 0.84)
        m.box_lo(1.95, dy, 0.84, 2.3, 1.15, 0.05, "phenolic", bev=0.01)
        for i in range(5):
            for j in range(3):
                m.cyl((1.1 + i * 0.42, dy - 0.38 + j * 0.38, 0.892), 0.012, 0.004, "machine_dark",
                      segs=8)
    m.box_lo(1.95, -2.08, 0.89, 2.3, 0.08, 0.1, "alu", bev=0.01)  # кутовий упор
    for i in range(4):
        m.box_lo(1.0 + i * 0.6, -2.08, 0.99, 0.02, 0.09, 0.012, "hazard_black")
    # нарізані деталі на столах
    for i, (dy, n) in enumerate(((-1.4, 4), (-0.15, 6), (1.25, 3))):
        m.box_lo(1.7 + 0.1 * i, dy, 0.89, 1.4, 0.72, 0.016 * n, "decor0")
    # світлова завіса та шафа керування
    for dy in (-2.4, 2.4):
        m.box_lo(-3.4, dy, 0, 0.07, 0.07, 1.8, "marking", bev=0.01)
        m.box_lo(-3.4, dy, 0, 0.2, 0.2, 0.02, "machine_dark")
    m.box_lo(-1.2, 3.35, 0, 1.2, 0.55, 2.0, "machine_mid", bev=0.02)
    m.box_lo(-1.2, 3.07, 0.2, 0.01, 0.4, 1.6, "machine_dark")
    m.box_lo(-1.0, 3.07, 1.0, 0.02, 0.03, 0.2, "steel_dark")
    m.box_lo(-1.2, 3.35, 2.0, 1.25, 0.6, 0.05, "machine_dark")
    # килимок оператора
    m.box_lo(2.0, -2.75, 0, 2.2, 0.8, 0.015, "rubber")
    console(m, 0.9, -3.05, 1.0, facing=90)
    # принтер етикеток зі штрихкодом для кожної деталі
    m.box_lo(3.25, -2.05, 0, 0.1, 0.1, 1.15, "steel_dark")
    m.box_lo(3.25, -2.05, 1.15, 0.35, 0.3, 0.25, "machine_dark", bev=0.02)
    m.box((3.25, -2.21, 1.3), (0.2, 0.01, 0.08), "screen_on")
    floor_frame(m, 7.4, 7.2)


def machine_edge(m):
    """Крайкооблицювальний верстат: секційна станина, гусениця подачі, верхня
    притискна балка з роликами, кожухи агрегатів з оглядовими вікнами, клейова
    ванна, магазин крайки, опорна консоль, конвеєри."""
    L = 8.0
    for i in range(6):  # станина секціями з дверцятами
        sx = L / 6
        cx = -L / 2 + (i + 0.5) * sx
        m.box_lo(cx, 0, 0.06, sx - 0.02, 0.95, 0.82, "machine", bev=0.02)
        m.box_lo(cx, -0.478, 0.35, 0.03, 0.01, 0.2, "steel_dark")
        m.box_lo(cx, -0.476, 0.12, sx - 0.12, 0.004, 0.66, "machine_mid")
    for x in (-L / 2 + 0.2, L / 2 - 0.2):
        for dy in (-0.35, 0.35):
            m.cyl((x, dy, 0.03), 0.06, 0.06, "machine_dark", segs=10)
    m.box_lo(0, -0.22, 0.88, L, 0.3, 0.06, "hazard_black")  # гусениця
    for k in range(40):
        m.box_lo(-L / 2 + 0.1 + k * 0.2, -0.22, 0.94, 0.16, 0.28, 0.01, "steel_dark")
    # верхня притискна балка
    for x in (-3.2, 0.0, 3.2):
        m.box_lo(x, 0.15, 0.88, 0.25, 0.22, 0.65, "machine_mid", bev=0.02)
    m.box_lo(0, -0.12, 1.4, L - 0.2, 0.45, 0.14, "machine_mid", bev=0.03)
    for k in range(36):
        m.cyl((-L / 2 + 0.25 + k * 0.215, -0.22, 1.12), 0.045, 0.12, "rubber", axis="Y", segs=12)
    # кожухи агрегатів
    hoods = [(-2.6, 1.3, "machine_accent"), (-1.15, 1.3, "machine"), (0.3, 1.3, "machine_accent"),
             (1.75, 1.3, "machine"), (3.15, 1.2, "machine_accent")]
    for x, w, mat in hoods:
        m.box_lo(x, 0.22, 0.95, w, 0.5, 0.55, mat, bev=0.06)
        m.box_lo(x, -0.035, 1.05, w * 0.7, 0.02, 0.32, "guard_glass", bev=0.01)
    # прозорий захисний козирок
    m.box((0, -0.55, 1.2), (L - 0.4, 0.02, 0.45), "guard_glass", rot=(-25, 0, 0))
    # клейова ванна
    m.box_lo(-3.6, 0.25, 0.95, 0.5, 0.45, 0.35, "machine_dark", bev=0.03)
    m.cyl((-3.6, 0.25, 1.38), 0.16, 0.08, "steel", segs=20)
    # магазин крайки на кронштейні
    m.box_lo(-4.15, -0.75, 0, 0.1, 0.1, 1.05, "steel_dark")
    m.box((-4.0, -0.62, 1.05), (0.35, 0.06, 0.06), "steel_dark", rot=(0, 0, 40))
    m.cyl((-3.85, -0.48, 1.1), 0.36, 0.02, "alu", segs=28)
    m.cyl((-3.85, -0.48, 1.13), 0.3, 0.04, "edge_roll", segs=28)
    m.cyl((-3.85, -0.48, 1.13), 0.08, 0.045, "carton", segs=12)
    # опорна консоль спереду
    m.box_lo(0, -1.0, 0.82, L, 0.06, 0.06, "alu", bev=0.01)
    for x in (-3.5, -1.5, 0.5, 2.5):
        m.box((x, -0.75, 0.8), (0.05, 0.5, 0.05), "steel_dark")
        m.cyl((x, -1.0, 0.9), 0.04, 0.03, "rubber", axis="Y", segs=10)
    # конвеєри: подача, вихід, повертальний позаду
    roller_table(m, -5.0, 0, 2.0, 1.1, 0.92, axis="Y")
    roller_table(m, 5.0, 0, 2.0, 1.1, 0.92, axis="Y")
    roller_table(m, 0, 1.25, 10.0, 0.6, 0.82, pitch=0.3, axis="Y")
    # пульт на поворотній консолі
    m.box_lo(-4.3, 0.55, 0.88, 0.1, 0.1, 0.7, "steel_dark")
    m.box((-4.05, 0.2, 1.58), (0.6, 0.08, 0.08), "steel_dark", rot=(0, 0, -50))
    m.box((-3.85, -0.05, 1.55), (0.06, 0.4, 0.3), "machine_dark", rot=(0, 15, 0), bev=0.01)
    m.box((-3.82, -0.05, 1.55), (0.01, 0.34, 0.24), "screen_on", rot=(0, 15, 0))
    estop(m, -3.6, -0.3, 0.88)
    # деталі на гусениці та на виході
    m.box_lo(-1.6, -0.15, 0.95, 1.4, 0.72, 0.016, "decor0")
    m.box_lo(4.9, 0.05, 0.92, 1.4, 0.72, 0.016 * 3, "decor0")
    floor_frame(m, 12.6, 3.8)


def machine_cnc(m):
    """Портальний обробний центр: станина, консолі з вакуумними присосками,
    портал, Z-каретка зі свердлильною головою і шпинделем, магазин
    інструменту, кабель-канал, бампери безпеки, огорожа, вакуум-насос."""
    m.box_lo(0, 0, 0, 4.4, 2.2, 0.72, "machine", bev=0.05)
    m.box_lo(0, -1.11, 0.1, 4.0, 0.01, 0.5, "machine_mid")
    m.box_lo(0, 0, 0.72, 4.2, 2.0, 0.04, "machine_dark")
    for x in (-1.9, 1.9):
        for dy in (-0.9, 0.9):
            m.cyl((x, dy, 0.03), 0.07, 0.06, "machine_dark", segs=10)
    # консолі з присосками
    for i in range(6):
        x = -1.75 + i * 0.7
        m.box_lo(x, 0, 0.76, 0.14, 1.9, 0.08, "alu", bev=0.01)
        for dy in (-0.55, 0.15):
            m.box_lo(x, dy, 0.84, 0.14, 0.12, 0.05, "machine_dark", bev=0.01)
    m.box_lo(-0.35, -0.2, 0.89, 1.6, 0.7, 0.016, "decor1")
    m.box_lo(-0.35, -0.2, 0.89 + 0.016, 1.6, 0.004, 0.001, "machine_dark")
    # напрямні порталу
    for dy in (-1.08, 1.08):
        m.box_lo(0, dy, 0.72, 4.3, 0.1, 0.14, "steel", bev=0.01)
    # портал
    gx = 0.5
    for dy in (-1.2, 1.2):
        m.box_lo(gx, dy, 0.76, 0.6, 0.32, 1.5, "machine_accent", bev=0.05)
    m.box_lo(gx, 0, 2.15, 0.66, 2.9, 0.5, "machine_accent", bev=0.07)
    m.box_lo(gx - 0.34, 0, 2.2, 0.01, 2.5, 0.38, "machine", bev=0.005)
    # кабель-канал на порталі
    for k in range(16):
        m.box_lo(gx + 0.12, -1.3 + k * 0.17, 2.65, 0.22, 0.14, 0.1, "machine_dark", bev=0.01)
    # Z-каретка та голова
    m.box_lo(gx - 0.42, 0.2, 1.2, 0.3, 0.45, 1.05, "machine", bev=0.03)
    m.box_lo(gx - 0.45, 0.2, 1.02, 0.36, 0.42, 0.2, "machine_dark", bev=0.02)
    for i in range(4):
        for j in range(3):
            m.cyl((gx - 0.55 + i * 0.07, 0.08 + j * 0.12, 0.97), 0.008, 0.1, "alu", segs=6)
    m.cyl((gx - 0.45, -0.18, 1.4), 0.12, 0.45, "machine_mid", segs=20)
    m.cyl((gx - 0.45, -0.18, 1.1), 0.05, 0.16, "steel", segs=12)
    m.cyl((gx - 0.45, 0.2, 0.98), 0.22, 0.05, "rubber", segs=24)  # щітка аспірації
    # магазин інструменту
    m.cyl((-2.0, -1.3, 1.25), 0.38, 0.06, "machine_mid", segs=28)
    for k in range(10):
        a = 2 * math.pi * k / 10
        m.cyl((-2.0 + 0.3 * math.cos(a), -1.3 + 0.3 * math.sin(a), 1.15), 0.03, 0.14, "alu", segs=8)
    m.box_lo(-2.0, -1.3, 0, 0.12, 0.12, 1.2, "steel_dark")
    # бампери безпеки та огорожа позаду
    m.box_lo(0, -1.45, 0.25, 4.4, 0.12, 0.12, "marking", bev=0.03)
    hazard(m, -2.2, 2.2, -1.52, 0.25, depth=0.005, h=0.12)
    for x in (-2.4, -0.8, 0.8, 2.4):
        m.box_lo(x, 1.9, 0, 0.06, 0.06, 1.9, "marking")
    for x in (-1.6, 0.0, 1.6):
        m.box_lo(x, 1.9, 0.15, 1.5, 0.02, 1.7, "guard_glass")
    m.box_lo(0, 1.9, 1.88, 4.86, 0.05, 0.05, "marking")
    # шафа керування, вакуум-насос, пульт
    m.box_lo(-2.85, 1.2, 0, 0.7, 0.6, 2.0, "machine_mid", bev=0.02)
    m.box_lo(-2.49, 1.2, 0.2, 0.01, 0.45, 1.6, "machine_dark")
    m.box_lo(2.8, 1.25, 0, 0.8, 0.6, 0.7, "machine_dark", bev=0.03)
    for k in range(6):
        m.box_lo(2.8, 0.94, 0.12 + k * 0.09, 0.7, 0.02, 0.03, "steel")
    console(m, 2.4, -1.9, 1.0, facing=-90)
    floor_frame(m, 6.6, 4.4)


def machine_asm(m):
    """Збиральна дільниця: корпусна вайма з пневмоприжимами та верстак."""
    # вайма: рама, ролики стола, стійки, приводи
    m.box_lo(0, 0, 0.6, 2.8, 1.3, 0.08, "steel", bev=0.01)
    legs_frame(m, 0, 0, 2.8, 1.3, 0.6, mat="machine_accent", t=0.08)
    for i in range(10):
        m.cyl((-1.25 + i * 0.28, 0, 0.71), 0.025, 1.2, "galv", axis="Y", segs=10)
    for dx in (-1.5, 1.5):
        m.box_lo(dx, -0.1, 0, 0.14, 0.14, 2.3, "machine_accent", bev=0.02)
        for z in (0.95, 1.35):
            m.cyl((dx * 0.86, -0.1, z), 0.04, 0.4, "alu", axis="X", segs=12)
            m.box((dx * 0.7, -0.1, z), (0.03, 0.3, 0.2), "steel_dark", bev=0.005)
    m.box_lo(0, -0.1, 2.3, 3.14, 0.16, 0.16, "machine_accent", bev=0.02)
    for dx in (-0.5, 0.5):
        m.cyl((dx, -0.1, 2.1), 0.045, 0.4, "alu", segs=12)
        m.box_lo(dx, -0.1, 1.8, 0.4, 0.4, 0.03, "steel_dark")
    # корпус шафи у ваймі
    cz = 0.75
    for dx in (-0.39, 0.39):
        m.box_lo(dx, 0, cz, 0.018, 0.56, 0.9, "decor0")
    for z in (cz, cz + 0.88):
        m.box_lo(0, 0, z, 0.8, 0.56, 0.018, "decor0")
    m.box_lo(0, 0, cz + 0.44, 0.76, 0.52, 0.016, "decor0")
    m.box_lo(0, 0.27, cz, 0.8, 0.005, 0.9, "decor6")
    # верстак
    bx, by = 0.0, 1.35
    m.box_lo(bx, by, 0.86, 2.2, 0.75, 0.05, "table_top", bev=0.01)
    legs_frame(m, bx, by, 2.2, 0.75, 0.86, mat="steel")
    m.box_lo(bx - 0.6, by, 0.1, 0.6, 0.7, 0.7, "machine_mid", bev=0.01)  # тумба з шухлядами
    for k in range(4):
        m.box_lo(bx - 0.6, by - 0.355, 0.15 + k * 0.17, 0.5, 0.01, 0.14, "machine", bev=0.003)
        m.box_lo(bx - 0.6, by - 0.365, 0.21 + k * 0.17, 0.16, 0.01, 0.02, "steel_dark")
    m.box_lo(bx, by + 0.35, 0.91, 2.2, 0.03, 1.0, "pegboard")
    for k in range(6):  # інструмент на перфопанелі
        m.box_lo(bx - 0.8 + k * 0.32, by + 0.32, 1.35, 0.05, 0.03, 0.25, "machine_dark")
    for k in range(5):  # лотки з фурнітурою
        m.box_lo(bx - 0.8 + k * 0.4, by + 0.25, 1.15, 0.3, 0.15, 0.12,
                 ("bin", "bin_yellow", "bin", "status_red", "bin")[k], bev=0.008)
    m.box_lo(bx + 0.5, by - 0.05, 0.91, 0.08, 0.2, 0.18, "machine_accent", bev=0.02)  # шуруповерт
    m.cyl((bx + 0.5, by - 0.17, 1.06), 0.02, 0.08, "machine_dark", axis="Y", segs=10)
    m.box_lo(bx + 0.5, by - 0.05, 0.91, 0.12, 0.12, 0.05, "machine_dark", bev=0.01)
    # котушка пневмошланга
    m.box_lo(1.7, 1.2, 0, 0.08, 0.08, 1.8, "steel_dark")
    m.cyl((1.7, 1.1, 1.6), 0.22, 0.12, "machine_accent", axis="Y", segs=20)
    # візок із деталями та готова шафа
    m.box_lo(-2.25, 0, 0.12, 1.0, 0.7, 0.04, "steel")
    for dx in (-0.4, 0.4):
        for dy in (-0.28, 0.28):
            m.cyl((-2.25 + dx, dy, 0.06), 0.06, 0.04, "rubber", axis="X", segs=12)
    for k in range(4):
        m.box_lo(-2.25, 0, 0.16 + k * 0.017, 0.8, 0.5, 0.016, "decor0")
    m.box_lo(2.35, -0.3, 0, 0.6, 0.58, 0.82, "decor0", bev=0.004)
    m.box_lo(2.35, -0.6, 0.02, 0.58, 0.02, 0.78, "decor1", bev=0.003)
    m.box_lo(2.35, -0.62, 0.6, 0.16, 0.02, 0.02, "steel")
    floor_frame(m, 6.0, 3.6)


def machine_pack(m):
    """Пакування: роликовий стіл, розмотувач гофрокартону, палетообмотувач."""
    roller_table(m, -0.9, 0, 2.2, 1.2, 0.88, axis="Y")
    m.box_lo(-1.2, 0, 0.88, 0.9, 0.65, 0.4, "carton", bev=0.008)
    m.box_lo(-1.2, -0.02, 1.28, 0.9, 0.05, 0.003, "tape")
    m.box_lo(-0.4, 0.1, 0.88, 0.5, 0.4, 0.03, "carton")
    # розмотувач гофрокартону
    for dx in (-1.9, 0.1):
        m.box_lo(dx, 0.85, 0, 0.06, 0.06, 1.15, "steel_dark")
    m.cyl((-0.9, 0.85, 1.1), 0.25, 1.8, "carton", axis="X", segs=24)
    m.cyl((-0.9, 0.85, 1.1), 0.03, 2.1, "steel", axis="X", segs=8)
    m.box((-0.9, 0.6, 0.98), (1.8, 0.4, 0.004), "carton", rot=(30, 0, 0))
    # палетообмотувач
    m.box_lo(1.5, 0, 0, 1.9, 1.9, 0.07, "machine_dark", bev=0.02)
    m.box((1.5, -1.15, 0.035), (1.9, 0.5, 0.02), "steel", rot=(-8, 0, 0))
    m.cyl((1.5, 0, 0.09), 0.85, 0.05, "steel", segs=36)
    m.box_lo(1.5, 1.1, 0, 0.22, 0.22, 2.5, "machine_accent", bev=0.03)
    m.box_lo(1.5, 1.32, 0.3, 0.3, 0.2, 0.6, "machine", bev=0.02)
    m.box((1.5, 1.425, 0.75), (0.2, 0.01, 0.12), "screen_on")
    m.box_lo(1.5, 0.9, 1.1, 0.34, 0.2, 0.45, "machine", bev=0.03)
    m.cyl((1.5, 0.78, 1.33), 0.07, 0.5, "film_roll", segs=16)
    pallet(m, 1.5, 0, 0.115)
    cartons(m, 1.5, 0, 0.26, 1.15, 0.75, 3)
    floor_frame(m, 5.2, 3.2)


def machine_nest(m):
    """Нестинг-центр: підйомний стіл завантаження зі стосом МДФ, стіл із жертовною
    плитою, портал зі шпинделем і витяжним ковпаком, лінійний магазин інструменту,
    стрічковий конвеєр вивантаження, принтер етикеток, шафа керування."""
    # завантаження
    m.box_lo(-4.0, 0, 0, 2.9, 2.3, 0.45, "machine_mid", bev=0.03)
    m.box_lo(-4.0, 0, 0.45, 2.8, 2.07, 0.018 * 14, "decor5")
    for dy in (-1.3, 1.3):
        m.box_lo(-3.4, dy, 0, 4.0, 0.2, 1.0, "machine", bev=0.03)
    m.box_lo(-3.2, 0, 1.0, 0.25, 2.8, 0.2, "machine_accent", bev=0.03)  # штовхач
    # станина та стіл
    m.box_lo(0.3, 0, 0, 4.4, 2.5, 0.8, "machine", bev=0.05)
    m.box_lo(0.3, 0, 0.8, 4.2, 2.3, 0.05, "machine_dark")
    m.box_lo(0.3, 0, 0.85, 4.1, 2.2, 0.03, "table_top")
    m.box_lo(0.0, 0, 0.88, 2.8, 2.07, 0.018, "decor5")
    for k in range(1, 4):
        m.box((0.0 - 1.4 + k * 0.7, 0, 0.899), (0.006, 2.0, 0.002), "machine_dark")
    m.box((0.0, 0, 0.899), (2.7, 0.006, 0.002), "machine_dark")
    for dy in (-1.2, 1.2):
        m.box_lo(0.3, dy, 0.8, 4.4, 0.1, 0.14, "steel", bev=0.01)
    # портал
    gx = 0.6
    for dy in (-1.4, 1.4):
        m.box_lo(gx, dy, 0.8, 0.6, 0.32, 1.5, "machine_accent", bev=0.05)
    m.box_lo(gx, 0, 2.2, 0.7, 3.1, 0.55, "machine_accent", bev=0.07)
    for k in range(18):
        m.box_lo(gx + 0.14, -1.45 + k * 0.17, 2.75, 0.22, 0.14, 0.1, "machine_dark", bev=0.01)
    m.box_lo(gx - 0.45, -0.3, 1.25, 0.32, 0.5, 1.1, "machine", bev=0.03)
    m.cyl((gx - 0.45, -0.3, 1.45), 0.14, 0.5, "machine_mid", segs=20)
    m.cyl((gx - 0.45, -0.3, 1.0), 0.26, 0.2, "guard_glass", segs=24)  # витяжний ковпак
    m.cyl((gx - 0.45, -0.3, 0.93), 0.27, 0.05, "rubber", segs=24)
    m.cyl((gx - 0.45, -0.3, 0.98), 0.03, 0.14, "alu", segs=8)
    # лінійний магазин інструменту
    m.box_lo(-1.8, 1.45, 0.8, 1.0, 0.25, 0.25, "machine_mid", bev=0.02)
    for k in range(8):
        m.cyl((-2.2 + k * 0.12, 1.45, 1.12), 0.035, 0.12, "alu", segs=8)
    # вивантаження: стрічковий конвеєр
    legs_frame(m, 4.4, 0, 3.0, 2.3, 0.82)
    m.box_lo(4.4, 0, 0.82, 3.0, 2.3, 0.06, "rubber", bev=0.02)
    for dx in (-1.5, 1.5):
        m.cyl((4.4 + dx, 0, 0.85), 0.06, 2.3, "steel", axis="Y", segs=12)
    for i, (dx, dy) in enumerate(((-0.8, -0.5), (0.1, 0.6), (0.9, -0.4))):
        m.box_lo(4.4 + dx, dy, 0.88, 0.7, 0.5, 0.018, "decor5")
        m.box_lo(4.4 + dx, dy, 0.898, 0.1, 0.06, 0.002, "phenolic")  # етикетка
    m.box_lo(5.3, -1.5, 0, 0.12, 0.12, 1.3, "steel_dark")
    m.box_lo(5.3, -1.4, 1.3, 0.35, 0.3, 0.25, "machine_dark", bev=0.02)  # принтер етикеток
    # шафа керування, бампер, пульт
    m.box_lo(-1.8, 1.95, 0, 0.9, 0.5, 2.0, "machine_mid", bev=0.02)
    m.box_lo(-1.8, 1.69, 0.2, 0.7, 0.01, 1.6, "machine_dark")
    m.box_lo(0.3, -1.6, 0.25, 4.4, 0.12, 0.12, "marking", bev=0.03)
    hazard(m, -1.9, 2.5, -1.67, 0.25, depth=0.005, h=0.12)
    console(m, 2.3, -2.35, 1.0, facing=90)
    floor_frame(m, 11.2, 4.6)


def machine_saw_book(m):
    machine_saw(m)
    m.box_lo(-1.75, 0, 0.84, 2.8, 2.07, 0.36, "decor1")  # вищий стос на підйомному столі
    for dy in (-1.4, -0.15, 1.25):
        m.box_lo(1.8, dy, 0.98, 1.3, 0.7, 0.096, "decor1")  # «книги» деталей


def machine_edge_robot(m):
    machine_edge(m)
    robot(m, 5.9, 1.25, rz=-125.8)
    fence(m, [(4.3, 2.05), (6.45, 2.05), (6.45, 0.65)])


def machine_slide(m):
    """Форматно-розкрійний верстат із кареткою."""
    m.box_lo(0, 0, 0, 1.1, 0.9, 0.85, "machine_mid", bev=0.03)
    m.box_lo(0, 0.1, 0.85, 1.2, 1.1, 0.05, "steel", bev=0.01)
    m.cyl((0.0, 0.1, 0.86), 0.17, 0.004, "steel", rot=(90, 0, 0), segs=24)
    m.box_lo(-0.2, -0.55, 0.7, 3.2, 0.35, 0.2, "alu", bev=0.02)
    m.box_lo(-0.2, -0.55, 0.9, 3.2, 0.38, 0.02, "steel")
    m.box_lo(-0.9, -1.2, 0.88, 0.12, 1.3, 0.05, "alu")
    m.box_lo(-0.9, -1.8, 0, 0.06, 0.06, 0.88, "steel_dark")
    m.box_lo(-0.6, -1.25, 0.93, 0.06, 1.2, 0.1, "alu")
    m.box_lo(0, 0.45, 0.9, 1.2, 0.06, 0.1, "alu")
    m.box_lo(0, 0.78, 0.85, 1.3, 0.08, 0.06, "steel")
    m.box_lo(0.55, 0.9, 0, 0.12, 0.12, 1.9, "steel_dark")
    m.box((0.28, 0.5, 1.85), (0.7, 0.08, 0.08), "steel_dark", rz=-55)
    m.box_lo(0, 0.1, 1.05, 0.35, 0.12, 0.18, "machine_accent", bev=0.02)
    m.tube([(0, 0.1, 1.23), (0.1, 0.25, 1.75), (0.55, 0.9, 1.95)], 0.04, "rubber")
    m.box_lo(-0.4, -0.9, 0.92, 2.0, 0.9, 0.018, "decor0")
    estop(m, 0.45, -0.42, 0.85)
    floor_frame(m, 3.8, 3.2)


def machine_vsaw(m):
    """Вертикальна панельна пила: рама з нахилом назад, опорна балка з роликами,
    вертикальна напрямна з пильним агрегатом."""
    m.box((0, 0.35, 1.3), (5.4, 0.12, 2.4), "machine_accent", rot=(-6, 0, 0), bev=0.03)
    for z in (0.6, 1.1, 1.6, 2.1):
        m.box((0, 0.25 + (z - 0.3) * 0.105, z), (5.2, 0.06, 0.06), "alu", rot=(-6, 0, 0))
    m.box_lo(0, -0.15, 0, 5.6, 0.5, 0.3, "machine_mid", bev=0.02)
    for k in range(14):
        m.cyl((-2.6 + k * 0.4, -0.1, 0.32), 0.04, 0.3, "rubber", axis="Y", segs=10)
    m.box((0.6, 0.18, 1.45), (0.25, 0.2, 2.9), "steel", rot=(-6, 0, 0), bev=0.02)
    m.box((0.6, 0.02, 1.2), (0.35, 0.25, 0.35), "machine_dark", rot=(-6, 0, 0), bev=0.03)
    m.box((-0.5, 0.2, 1.37), (2.8, 0.018, 2.07), "decor2", rot=(-6, 0, 0))
    for x in (-2.75, 2.75):
        m.box_lo(x, 0.6, 0, 0.15, 0.7, 0.1, "machine_dark")
    m.box_lo(2.4, -0.7, 0, 0.3, 0.3, 1.2, "machine_dark")
    m.box((2.4, -0.86, 1.35), (0.4, 0.04, 0.3), "screen_on")
    floor_frame(m, 6.0, 2.2)


def machine_dowel(m):
    """Свердлильно-присадний верстат із забиванням шкантів."""
    legs_frame(m, 0, 0, 3.4, 1.0, 0.85)
    m.box_lo(0, 0, 0.85, 3.4, 1.0, 0.05, "phenolic", bev=0.01)
    m.box_lo(0, 0.7, 0, 1.4, 0.5, 1.35, "machine", bev=0.04)
    m.box_lo(0, 0.6, 1.35, 1.5, 0.7, 0.35, "machine_accent", bev=0.05)
    m.box_lo(0, 0.3, 0.9, 1.0, 0.3, 0.25, "machine_dark", bev=0.02)
    for k in range(6):
        m.cyl((-0.4 + k * 0.16, 0.12, 1.0), 0.012, 0.12, "alu", axis="Y", segs=6)
    m.cyl((0.45, 0.6, 1.85), 0.25, 0.18, "steel", segs=24)  # вібробункер шкантів
    m.cyl((0.45, 0.6, 1.76), 0.08, 0.15, "steel_dark", segs=10)
    m.tube([(0.45, 0.45, 1.75), (0.3, 0.35, 1.35), (0.1, 0.3, 1.1)], 0.02, "guard_glass")
    for k in range(3):
        m.cyl((-1.2 + k * 1.2, -0.1, 1.15), 0.04, 0.3, "alu", segs=10)
    m.box_lo(-0.3, -0.1, 0.9, 2.2, 0.6, 0.018, "decor0")
    m.box((-0.6, 0.44, 1.15), (0.4, 0.02, 0.3), "screen_on")
    m.box_lo(0, -0.85, 0, 3.4, 0.6, 0.015, "rubber")
    floor_frame(m, 3.8, 2.4)


def machine_bore(m):
    """Прохідний свердлильний верстат: стрічка подачі, чотири свердлильні агрегати."""
    m.box_lo(0, 0, 0, 5.0, 1.4, 0.85, "machine", bev=0.04)
    m.box_lo(0, -0.2, 0.85, 5.0, 0.6, 0.03, "rubber")
    for k in range(4):
        m.box_lo(-1.6 + k * 1.05, 0.3, 0.88, 0.7, 0.6, 0.7, "machine_accent" if k % 2 else "machine_mid",
                 bev=0.04)
    m.box_lo(0, -0.62, 0.95, 4.6, 0.02, 0.45, "guard_glass")
    m.box_lo(0, 0.0, 1.58, 5.0, 1.3, 0.12, "machine", bev=0.03)
    roller_table(m, -3.4, 0, 1.6, 1.3, 0.88, axis="Y")
    roller_table(m, 3.4, 0, 1.6, 1.3, 0.88, axis="Y")
    m.box_lo(-3.4, -0.1, 0.88, 0.9, 0.6, 0.018, "decor1")
    m.box_lo(3.3, 0.0, 0.88, 0.9, 0.6, 0.036, "decor1")
    m.box_lo(2.0, -1.0, 0, 0.35, 0.3, 1.3, "machine_dark")
    m.box((2.0, -1.16, 1.45), (0.45, 0.05, 0.3), "screen_on")
    floor_frame(m, 7.2, 2.6)


def machine_hinge(m):
    """Верстат для встановлення завіс і монтажних планок: дві пневмоголови з бункерами."""
    legs_frame(m, 0, 0, 2.2, 0.9, 0.85)
    m.box_lo(0, 0, 0.85, 2.2, 0.9, 0.05, "phenolic", bev=0.01)
    for x in (-0.55, 0.55):
        m.box_lo(x, 0.38, 0.9, 0.25, 0.2, 0.85, "machine_accent", bev=0.03)
        m.box_lo(x, 0.2, 1.55, 0.25, 0.45, 0.2, "machine_accent", bev=0.03)
        m.cyl((x, 0.05, 1.38), 0.05, 0.3, "alu", segs=12)
        m.box_lo(x, 0.05, 1.08, 0.12, 0.12, 0.12, "machine_dark")
        m.cyl((x, 0.5, 1.95), 0.16, 0.12, "steel", segs=20)
    m.box_lo(0, -0.05, 0.9, 1.6, 0.5, 0.018, "decor1")
    m.box_lo(-1.4, 0, 0, 0.5, 0.5, 0.9, "steel", bev=0.02)
    floor_frame(m, 3.4, 2.0)


def machine_sortbot(m):
    """Роботизована комірка сортування: робот на лінійній колії між стелажами з деталями."""
    L = 7.0
    m.box_lo(0, 0, 0, L, 0.5, 0.12, "steel_dark")
    m.box_lo(0, 0, 0.12, L, 0.18, 0.06, "alu")
    m.box_lo(-1.0, 0, 0.18, 0.9, 0.8, 0.15, "machine_mid", bev=0.03)
    robot(m, -1.0, 0, rz=90, z=0.33)
    for side in (-1, 1):
        yy = side * 2.1
        for k in range(9):
            for dy in (-0.42, 0.42):
                m.box_lo(-L / 2 + 0.02 + k * 0.87, yy + dy, 0, 0.06, 0.06, 2.6, "rack_upright")
        for s in range(8):
            x = -L / 2 + 0.455 + s * 0.87
            for lv in range(4):
                z = 0.3 + lv * 0.6
                m.box_lo(x, yy, z - 0.04, 0.8, 0.9, 0.04, "steel")
                for k in range((s * 3 + lv * 5 + side) % 5):
                    m.box_lo(x - 0.3 + k * 0.15, yy, z, 0.018, 0.8, 0.42, "decor%d" % ((s + k) % 3))
    roller_table(m, -L / 2 - 0.9, 0, 1.4, 1.2, 0.85, axis="X")
    roller_table(m, L / 2 + 0.9, 0, 1.4, 1.2, 0.85, axis="X")
    x0, x1, y0, y1 = -L / 2 - 0.3, L / 2 + 0.3, -2.75, 2.75
    fence(m, [(x0, -0.75), (x0, y0), (x1, y0), (x1, -0.75)])
    fence(m, [(x0, 0.75), (x0, y1), (x1, y1), (x1, 0.75)])
    console(m, L / 2 - 0.5, y0 - 0.5, 1.0, facing=90)
    floor_frame(m, 9.8, 6.4)


def machine_asmline(m):
    """Автоматична лінія збирання корпусів: подача, станція клею і шкантів,
    автоматична вайма, поворотний пристрій, вихідний конвеєр."""
    roller_table(m, -9.5, 0, 5.0, 1.4, 0.85, pitch=0.3, axis="Y")
    m.box_lo(-10.0, 0, 0.86, 1.0, 0.6, 0.1, "decor0")
    m.box_lo(-5.6, 0, 0, 2.4, 1.6, 0.85, "machine", bev=0.04)
    m.box_lo(-5.6, 0.55, 0.85, 2.4, 0.5, 1.0, "machine_accent", bev=0.05)
    m.box_lo(-5.6, 0.1, 1.5, 2.4, 0.4, 0.3, "machine_accent", bev=0.04)
    for k in range(5):
        m.cyl((-6.5 + k * 0.45, 0.1, 1.3), 0.03, 0.35, "alu", segs=8)
    cx = -1.0
    m.box_lo(cx, 0, 0, 3.6, 1.8, 0.75, "machine_mid", bev=0.04)
    for dx in (-1.9, 1.9):
        for dy in (-1.0, 1.0):
            m.box_lo(cx + dx, dy, 0, 0.2, 0.2, 2.8, "machine_accent", bev=0.03)
    m.box_lo(cx, 0, 2.8, 4.0, 2.2, 0.25, "machine_accent", bev=0.05)
    for dy in (-0.95, 0.95):
        m.box_lo(cx, dy, 0.75, 3.4, 0.03, 1.9, "guard_glass")
    for k in range(4):
        m.cyl((cx - 1.2 + k * 0.8, 0, 2.55), 0.05, 0.4, "alu", segs=12)
    m.box_lo(cx, 0, 2.0, 3.2, 1.2, 0.08, "steel_dark")
    for dx in (-1.6, 1.6):
        m.cyl((cx + dx, 0, 1.4), 0.05, 0.5, "alu", axis="X", segs=12)
    cabinet(m, cx, 0, 0.75, w=1.0, d=0.6, h=1.2)
    m.cyl((3.2, 0, 0.4), 0.9, 0.8, "machine_mid", segs=28)
    m.cyl((3.2, 0, 0.82), 0.85, 0.04, "steel", segs=28)
    cabinet(m, 3.2, 0, 0.84, w=0.8, d=0.56, h=0.8)
    roller_table(m, 7.8, 0, 6.6, 1.4, 0.85, pitch=0.3, axis="Y")
    for x in (6.0, 8.4, 10.6):
        cabinet(m, x, 0, 0.86, w=0.8, d=0.56, h=0.8)
    console(m, -3.6, -1.4, 1.0, facing=90)
    floor_frame(m, 24.4, 3.4)


def machine_box(m):
    """Станок розкрою гофрокартону: коробка під розмір виробу з фанфолд-пачок."""
    m.box_lo(0, 0, 0, 2.6, 1.3, 1.25, "machine", bev=0.05)
    m.box_lo(0, 0, 1.25, 2.6, 1.3, 0.25, "machine_accent", bev=0.05)
    m.box_lo(0, -0.66, 0.6, 2.2, 0.02, 0.5, "guard_glass")
    m.box((0.9, -0.66, 1.1), (0.35, 0.02, 0.25), "screen_on")
    legs_frame(m, 0, -1.0, 2.6, 0.7, 0.85)
    m.box_lo(0, -1.0, 0.85, 2.6, 0.7, 0.03, "steel")
    m.box_lo(0.2, -1.0, 0.88, 1.8, 0.6, 0.004, "carton")
    for k, dx in enumerate((-0.9, 0.0, 0.9)):
        m.box_lo(dx, 1.45, 0, 0.85, 1.0, 0.12, "pallet")
        m.box_lo(dx, 1.45, 0.12, 0.8, 0.95, 0.9 - k * 0.2, "carton")
        m.box((dx, 0.95, 1.35), (0.75, 0.7, 0.004), "carton", rot=(-35, 0, 0))
    floor_frame(m, 3.2, 4.0)


def machine_packline(m):
    """Лінія термоусадки та обв'язки: L-зварювач, термотунель, обв'язувальна арка."""
    roller_table(m, 0, 0, 9.0, 1.3, 0.85, pitch=0.35, axis="Y")
    m.box_lo(-2.8, 0.75, 0, 0.4, 0.3, 1.4, "machine_mid", bev=0.02)
    m.box((-2.8, 0, 1.15), (1.4, 1.4, 0.06), "machine_accent", bev=0.02)
    m.cyl((-2.8, 0.95, 1.55), 0.15, 1.2, "film_roll", axis="X", segs=16)
    m.box_lo(0.6, 0, 0.85, 2.6, 1.6, 1.1, "machine", bev=0.05)
    m.box_lo(0.6, 0, 1.95, 2.2, 1.2, 0.25, "machine_accent", bev=0.05)
    for xe in (0.6 - 1.31, 0.6 + 1.31):
        for k in range(6):
            m.box_lo(xe, -0.55 + k * 0.22, 1.0, 0.01, 0.2, 0.85, "rubber")
    for dy in (-0.85, 0.85):
        m.box_lo(3.4, dy, 0, 0.3, 0.3, 2.2, "machine_mid", bev=0.03)
    m.box_lo(3.4, 0, 2.2, 0.3, 2.0, 0.3, "machine_mid", bev=0.03)
    m.box_lo(3.4, -1.25, 0, 0.6, 0.5, 1.0, "machine_accent", bev=0.03)
    m.cyl((3.4, -1.55, 0.6), 0.3, 0.15, "machine_dark", axis="Y", segs=20)
    m.box_lo(-3.8, 0, 0.85, 1.0, 0.6, 0.5, "carton", bev=0.008)
    m.box_lo(2.4, 0, 0.85, 1.02, 0.62, 0.52, "wrap")
    m.box_lo(2.4, 0, 0.86, 1.0, 0.6, 0.5, "carton", bev=0.008)
    floor_frame(m, 10.0, 3.6)


def machine_sand(m):
    """Широкострічковий шліфувальний верстат із рольгангами."""
    m.box_lo(0, 0, 0, 1.8, 2.6, 0.75, "machine_mid", bev=0.04)
    m.box_lo(0, 0, 0.75, 1.9, 2.2, 0.06, "rubber")
    for dy in (-1.35, 1.35):
        m.box_lo(0, dy, 0, 1.8, 0.3, 1.05, "machine", bev=0.03)
    m.box_lo(0, 0, 1.05, 1.8, 3.0, 1.25, "machine", bev=0.06)
    m.box_lo(0, 0, 2.3, 1.4, 2.6, 0.25, "machine_accent", bev=0.05)
    m.box_lo(0.91, 0, 1.25, 0.02, 2.4, 0.8, "machine_mid")
    for dy in (-0.6, 0.6):
        m.cyl((0, dy, 2.7), 0.18, 0.3, "galv", segs=16)
    roller_table(m, -2.0, 0, 2.0, 2.2, 0.8, axis="Y")
    roller_table(m, 2.0, 0, 2.0, 2.2, 0.8, axis="Y")
    for dy in (-0.45, 0.45):
        m.box_lo(-2.0, dy, 0.8, 0.7, 0.5, 0.019, "decor5")
        m.box_lo(2.1, dy, 0.8, 0.7, 0.5, 0.019, "phenolic")
    m.box_lo(0.6, -1.85, 0, 0.35, 0.3, 1.4, "machine_dark")
    m.box((0.6, -2.01, 1.5), (0.4, 0.04, 0.3), "screen_on")
    floor_frame(m, 6.2, 4.0)


def machine_glue(m):
    """Кабіна розпилення клею перед мембранним пресом: фільтрова стінка, поворотний стіл."""
    m.box_lo(0, 1.1, 0, 3.2, 0.12, 2.6, "machine")
    m.box_lo(0, 1.0, 0.4, 2.8, 0.06, 1.9, "filter")
    for x in (-1.55, 1.55):
        m.box_lo(x, 0, 0, 0.1, 2.3, 2.6, "machine")
    m.box_lo(0, 0, 2.6, 3.2, 2.3, 0.12, "machine")
    m.box_lo(0, 0, 2.55, 2.4, 1.4, 0.04, "led")
    m.cyl((0, 0.1, 0.35), 0.08, 0.7, "steel_dark", segs=10)
    m.cyl((0, 0.1, 0.72), 0.6, 0.04, "steel", segs=28)
    m.box_lo(0, 0.1, 0.74, 0.9, 0.6, 0.019, "decor5")
    m.box_lo(1.0, -0.8, 0, 0.5, 0.5, 0.8, "machine_dark", bev=0.03)
    m.cyl((1.0, -0.8, 0.95), 0.18, 0.3, "steel", segs=16)
    m.tube([(1.0, -0.8, 1.0), (0.6, -0.5, 1.1), (0.3, -0.3, 1.15)], 0.015, "rubber")
    floor_frame(m, 3.8, 3.0)


def machine_press(m):
    """Мембранно-вакуумний прес: прес із піднятою кришкою ІЧ-нагрівачів,
    два човникові столи з фасадами, вакуум-насос, стійка з плівкою ПВХ."""
    m.box_lo(0, 0, 0, 3.8, 2.1, 1.0, "machine_mid", bev=0.05)
    for dx in (-1.95, 1.95):
        for dy in (-1.0, 1.0):
            m.box_lo(dx, dy, 1.0, 0.2, 0.2, 1.3, "machine_accent", bev=0.03)
    m.box_lo(0, 0, 1.85, 4.0, 2.2, 0.55, "machine_accent", bev=0.06)
    m.box_lo(0, 0, 1.8, 3.6, 1.9, 0.04, "heater")
    m.box_lo(0, 0, 1.0, 3.6, 1.9, 0.05, "rubber")
    for sx in (-1, 1):
        x = sx * 4.0
        legs_frame(m, x, 0, 3.8, 1.9, 0.85)
        m.box_lo(x, 0, 0.85, 3.8, 1.9, 0.15, "steel", bev=0.02)
        for i in range(3):
            for j in range(2):
                m.box_lo(x - 1.2 + i * 1.2, -0.45 + j * 0.9, 1.0, 1.0, 0.7, 0.022,
                         "decor2" if sx > 0 else "decor5", bev=0.006)
    m.box_lo(2.4, 1.4, 0, 0.8, 0.6, 0.9, "machine_dark", bev=0.03)
    m.cyl((2.4, 1.4, 1.05), 0.15, 0.3, "steel", segs=16)
    m.box_lo(-2.2, 1.35, 0, 0.1, 0.1, 1.3, "steel_dark")
    m.cyl((-2.2, 1.35, 1.35), 0.15, 1.5, "decor2", axis="X", segs=16)
    console(m, 0.8, -1.6, 1.0, facing=90)
    floor_frame(m, 12.4, 3.4)


def machine_spray(m):
    """Фарбувальна камера з водяною завісою та етажеркою фасадів."""
    w, d, h = 5.0, 3.6, 3.0
    m.box_lo(0, d / 2, 0, w, 0.12, h, "machine")
    m.box_lo(0, d / 2 - 0.1, 0.2, w - 0.4, 0.06, 2.4, "water_glass")
    m.box_lo(0, d / 2 - 0.45, 0, w - 0.2, 0.6, 0.35, "machine_mid")
    for x in (-w / 2, w / 2):
        m.box_lo(x, 0, 0, 0.12, d, h, "machine")
    m.box_lo(0, 0, h, w + 0.12, d, 0.15, "machine")
    for x in (-1.5, 0, 1.5):
        m.box_lo(x, 0, h - 0.06, 1.2, 0.4, 0.05, "led")
    rack_cart(m, -1.2, 0.3)
    m.cyl((1.2, 0.4, 0.45), 0.06, 0.9, "steel_dark", segs=10)
    m.cyl((1.2, 0.4, 0.92), 0.55, 0.04, "steel", segs=24)
    m.box_lo(1.2, 0.4, 0.94, 0.8, 0.5, 0.019, "phenolic")
    m.box_lo(-2.0, -1.5, 0, 0.6, 0.5, 0.9, "machine_dark", bev=0.03)
    m.tube([(-2.0, -1.5, 0.9), (-1.4, -1.0, 1.1), (0.4, -0.7, 1.0)], 0.015, "rubber")
    floor_frame(m, 5.6, 4.2)


def machine_autospray(m):
    """Автомат фарбування: кабіна з робочими пістолетами, зона відкритого випаровування."""
    roller_table(m, -5.0, 0, 2.2, 1.5, 0.9, axis="Y")
    m.box_lo(-2.1, 0, 0, 3.6, 2.4, 2.4, "machine", bev=0.05)
    m.box_lo(-2.1, -1.21, 0.9, 2.6, 0.02, 1.0, "guard_glass")
    m.box_lo(-2.1, 0, 2.4, 3.0, 1.8, 0.4, "machine_accent", bev=0.05)
    m.box_lo(-2.1, 0, 0.88, 3.8, 1.4, 0.04, "rubber")
    m.box_lo(2.2, 0, 0, 4.8, 1.9, 1.4, "machine_mid", bev=0.05)
    m.box_lo(2.2, 0, 1.4, 4.6, 1.7, 0.2, "machine_accent", bev=0.04)
    m.box_lo(2.2, -0.96, 0.9, 4.2, 0.02, 0.35, "guard_glass")
    roller_table(m, 5.6, 0, 1.6, 1.5, 0.9, axis="Y")
    m.box_lo(-5.0, 0, 0.9, 0.9, 0.6, 0.019, "decor5")
    m.box_lo(5.6, 0, 0.9, 0.9, 0.6, 0.019, "decor1")
    m.box_lo(-2.1, 1.55, 0, 0.8, 0.5, 1.6, "machine_dark", bev=0.03)
    console(m, -3.6, -1.6, 1.0, facing=90)
    floor_frame(m, 13.2, 3.6)


def machine_dry(m):
    """Сушильна камера з відчиненими дверима та етажерками всередині."""
    w, d, h = 6.0, 4.4, 3.0
    m.box_lo(0, d / 2, 0, w, 0.12, h, "wall")
    for x in (-w / 2, w / 2):
        m.box_lo(x, 0, 0, 0.12, d, h, "wall")
    m.box_lo(0, 0, h, w + 0.12, d + 0.12, 0.12, "wall_band")
    for x in (-2.55, 2.55):
        m.box_lo(x, -d / 2, 0, 0.9, 0.12, h, "wall")
    m.box_lo(0, -d / 2, 2.6, 4.2, 0.12, 0.4, "wall")
    for x in (-2.05, 2.05):
        m.box_lo(x, -d / 2 - 0.8, 0, 0.06, 1.6, 2.55, "machine_mid")
    for x in (-1.8, -0.6, 0.6, 1.8):
        rack_cart(m, x, 0.6)
    m.box_lo(1.5, 0.8, h + 0.12, 2.0, 1.4, 1.0, "machine_mid", bev=0.04)
    m.cyl((-1.5, 1.0, h + 0.5), 0.3, 0.75, "galv", segs=18)
    m.box((2.8, -d / 2 - 0.07, 1.4), (0.5, 0.02, 0.4), "screen_on")
    floor_frame(m, 6.6, 5.0)


def machine_uv(m):
    """Лінія лакування з УФ-сушінням: вальцьовий лаконаносний верстат і два УФ-тунелі."""
    roller_table(m, -4.0, 0, 2.0, 1.4, 0.9, axis="Y")
    m.box_lo(-1.9, 0, 0, 1.6, 1.8, 1.2, "machine", bev=0.05)
    m.cyl((-1.9, 0, 1.05), 0.12, 1.5, "rubber", axis="Y", segs=16)
    m.cyl((-1.9, 0, 1.3), 0.09, 1.5, "steel", axis="Y", segs=14)
    m.box_lo(-1.9, 0, 1.35, 1.6, 1.8, 0.35, "machine_accent", bev=0.05)
    for x in (0.6, 2.4):
        m.box_lo(x, 0, 0, 1.5, 1.6, 0.85, "machine_mid", bev=0.04)
        m.box_lo(x, 0, 0.85, 1.5, 1.6, 0.7, "machine_dark", bev=0.05)
        m.box_lo(x, -0.81, 0.9, 1.2, 0.01, 0.12, "uv")
        m.box_lo(x, 0, 1.55, 0.9, 0.8, 0.3, "machine_mid", bev=0.03)
    m.box_lo(1.5, 0, 0.85, 4.0, 1.3, 0.03, "rubber")
    roller_table(m, 4.4, 0, 1.8, 1.4, 0.9, axis="Y")
    m.box_lo(-4.0, 0, 0.9, 0.9, 0.6, 0.019, "decor5")
    m.box_lo(4.4, 0, 0.9, 0.9, 0.6, 0.02, "decor1")
    floor_frame(m, 10.8, 2.6)


MACHINE_BUILDERS = {"saw": machine_saw, "edge": machine_edge, "cnc": machine_cnc,
                    "asm": machine_asm, "pack": machine_pack, "nest": machine_nest,
                    "saw_book": machine_saw_book, "edge_robot": machine_edge_robot,
                    "slide": machine_slide, "vsaw": machine_vsaw, "dowel": machine_dowel,
                    "bore": machine_bore, "hinge": machine_hinge, "sortbot": machine_sortbot,
                    "asmline": machine_asmline, "box": machine_box, "packline": machine_packline,
                    "sand": machine_sand, "glue": machine_glue, "press": machine_press,
                    "spray": machine_spray, "autospray": machine_autospray, "dry": machine_dry,
                    "uv": machine_uv}
TOWER_POS = {"saw": (-0.4, 2.55, 2.02), "edge": (3.85, -0.35, 1.55), "cnc": (-2.85, 1.2, 2.05),
             "asm": (1.5, -0.1, 2.46), "pack": (1.5, 1.1, 2.5), "nest": (-1.8, 1.95, 2.02),
             "saw_book": (-0.4, 2.55, 2.02), "edge_robot": (3.85, -0.35, 1.55),
             "slide": (0.55, 0.9, 1.9), "vsaw": (2.6, 0.5, 2.45), "dowel": (-0.55, 0.75, 1.7),
             "bore": (2.3, 0.5, 1.7), "hinge": (-1.4, 0.0, 0.9), "sortbot": (4.0, -2.75, 1.9),
             "asmline": (0.9, 1.0, 3.05), "box": (-1.1, 0.4, 1.5), "packline": (3.4, 0.85, 2.5),
             "sand": (0.6, -1.2, 2.55), "glue": (1.4, -1.0, 2.72), "press": (1.95, 1.0, 2.3),
             "spray": (2.3, -1.6, 3.15), "autospray": (-0.5, -1.0, 2.8), "dry": (2.55, -2.2, 3.12),
             "uv": (-1.3, 0.7, 1.7)}
OPERATOR = {"saw": (0.9, -3.65, 90), "edge": (-5.0, -0.95, 90), "cnc": (2.4, -2.55, 90),
            "asm": (0.0, -1.0, 90), "pack": (-0.9, -0.95, 90), "nest": (2.3, -2.9, 90),
            "saw_book": (0.9, -3.65, 90), "edge_robot": (-5.0, -0.95, 90), "slide": (0.9, -1.0, 90),
            "vsaw": (0.6, -1.1, 90), "dowel": (0.0, -0.95, 90), "bore": (-3.4, -1.05, 90),
            "hinge": (0.0, -0.85, 90), "sortbot": None, "asmline": (-3.6, -2.0, 90),
            "box": (0.4, -1.65, 90), "packline": (-3.8, -1.15, 90), "sand": (-2.0, -1.6, 90),
            "glue": (0.0, -0.7, 90), "press": (0.8, -2.15, 90), "spray": (0.6, -0.6, 90),
            "autospray": (-5.0, -1.1, 90), "dry": None, "uv": (4.4, -1.1, 90)}
