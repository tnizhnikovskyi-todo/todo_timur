"""Мебельный цех и склад — процедурная 3D-сцена.

Запуск (Blender как Python-модуль, pip install bpy):
    python build_scene.py dist/
или в Blender:
    blender -b -P build_scene.py -- dist/

Результат: factory.glb, factory.usdz, factory.blend.

Координаты в метрах. Оси Blender: X — вдоль здания (поток материала слева
направо), Y — поперёк, Z — вверх. При экспорте в glTF ось Y становится вверх.

Структура сцены:
  LAYER_<key>         пустышка-слой (в просмотрщике — переключатель слоя)
    <объект>          у каждого кликабельного объекта есть свойства
                      code / kind / label / desc (в glTF это extras)
"""
import json
import math
import os
import shutil
import sys

import bpy  # noqa: I001 — bpy должен импортироваться раньше bmesh/mathutils
import bmesh
from mathutils import Matrix, Vector

# --------------------------------------------------------------------------
# Планировка
# --------------------------------------------------------------------------
W, D, H = 60.0, 30.0, 7.0  # здание: длина, ширина, высота

LAYERS = [
    ("building", "Здание"),
    ("roof", "Кровля и фермы"),
    ("zones", "Разметка зон"),
    ("receiving", "Приёмка и ОТК"),
    ("sheets", "Склад плит"),
    ("hardware", "Склад фурнитуры"),
    ("edge", "Склад кромки"),
    ("buffer", "Буфер у линии"),
    ("line", "Производственная линия"),
    ("fg", "Склад готовой продукции"),
    ("shipping", "Отгрузка"),
    ("transport", "Транспорт"),
    ("flow", "Маршрут изделия"),
]

# code, название, (x0, y0, x1, y1), цвет заливки, описание
ZONES = [
    ("Z-RCV", "Приёмка", (0.6, 0.6, 8.4, 13.4), "#7fb3d5",
     "Разгрузка фур с плитой и фурнитурой, сверка с накладной."),
    ("Z-QC", "Входной контроль", (0.6, 14.0, 8.4, 20.4), "#c39bd3",
     "Проверка декора, толщины и геометрии плит перед размещением."),
    ("Z-EDGE", "Склад кромки", (0.6, 21.0, 8.4, 29.4), "#f5cba7",
     "Рулоны кромки ПВХ по декорам и толщинам."),
    ("Z-SHEETS", "Склад плит", (8.9, 0.6, 22.6, 15.2), "#d7bde2",
     "Напольное хранение ДСП, МДФ и ХДФ стопами по декорам."),
    ("Z-HW", "Склад фурнитуры", (8.9, 15.8, 22.6, 29.4), "#a9dfbf",
     "Стеллажи с ячейками: петли, направляющие, крепёж, ручки."),
    ("Z-PRE", "Буфер у линии", (23.0, 0.6, 27.4, 29.4), "#f9e79f",
     "Тележки с комплектами деталей и фурнитуры под заказ."),
    ("Z-LINE", "Производство", (27.8, 0.6, 48.4, 22.6), "#aed6f1",
     "Раскрой → кромкооблицовка → присадка → сборка → упаковка."),
    ("Z-OFFICE", "Офис мастера", (27.8, 23.2, 36.6, 29.4), "#d5d8dc",
     "Мастер участка, планирование смены."),
    ("Z-MAINT", "Ремонтный участок", (37.0, 23.2, 48.4, 29.4), "#d5d8dc",
     "Обслуживание станков, заточка и замена инструмента."),
    ("Z-POST", "Выход с линии", (48.9, 9.8, 59.4, 13.8), "#f9e79f",
     "Упакованные изделия ждут размещения на складе."),
    ("Z-FG", "Склад готовой продукции", (48.9, 14.4, 59.4, 29.4), "#abebc6",
     "Паллетные стеллажи, 3 яруса."),
    ("Z-OUT", "Отгрузка", (48.9, 0.6, 59.4, 9.2), "#f5b7b1",
     "Сборка отгрузок по заказам и погрузка в машины."),
]

# Ворота: стена, центр по Y, ширина
DOORS = [("W", 4.0, 3.2), ("W", 9.0, 3.2), ("E", 3.0, 3.2), ("E", 7.0, 3.2)]
DOOR_H = 4.2

COLUMNS = [(x, y) for x in (12, 24, 36, 48) for y in (10, 20)]

SHEET_DECORS = [
    ("ДСП 16 мм Дуб Сонома", "#c9a46f"),
    ("ДСП 16 мм Белый", "#efede6"),
    ("ДСП 16 мм Антрацит", "#45484c"),
    ("ДСП 16 мм Венге", "#4b3426"),
    ("ДСП 18 мм Бетон", "#a7a39b"),
    ("МДФ 18 мм под покраску", "#b08a5a"),
    ("ХДФ 3 мм белый", "#e8e4da"),
]
# стопы плит: ряд (y) × колонка (x); индекс декора, число листов
SHEET_ROWS_Y = {"A": 3.0, "B": 7.5, "C": 12.0}
SHEET_COLS_X = [10.7, 14.1, 17.5, 20.9]
SHEET_STACKS = {
    "A": [(0, 58), (0, 34), (1, 61), (1, 22)],
    "B": [(2, 40), (2, 9), (3, 27), (4, 45)],
    "C": [(5, 30), (6, 110), (0, 0), (1, 48)],
}

MACHINES = [
    # code, тип, название, x, y, описание
    ("SAW-1", "saw", "Раскрой 1", 31.5, 4.8,
     "Форматно-раскроечный центр с прижимной балкой. Режет плиту 2800×2070 на детали."),
    ("SAW-2", "saw", "Раскрой 2", 31.5, 12.6,
     "Второй раскроечный центр, работает на МДФ и ХДФ."),
    ("EDGE-1", "edge", "Кромкооблицовка", 41.5, 4.5,
     "Проходной кромкооблицовочный станок: торцовка, фрезеровка свесов, циклёвка."),
    ("CNC-1", "cnc", "Присадка ЧПУ", 41.5, 12.6,
     "Сверлильно-присадочный центр: отверстия под конфирматы, петли и эксцентрики."),
    ("ASM-1", "asm", "Сборка 1", 40.5, 19.0,
     "Стол сборки корпусов, установка фурнитуры и фасадов."),
    ("ASM-2", "asm", "Сборка 2", 34.5, 19.0,
     "Второй стол сборки."),
    ("PACK-1", "pack", "Упаковка", 45.4, 18.6,
     "Упаковка в гофрокартон и обмотка паллет стрейч-плёнкой."),
]

# Маршрут изделия: точки привязки дуг (x, y, z)
FLOW = [
    ("Z-RCV", "Приёмка", (4.5, 7.0, 1.2)),
    ("Z-SHEETS", "Склад плит", (15.5, 7.5, 1.5)),
    ("Z-PRE", "Буфер", (25.2, 6.5, 1.4)),
    ("SAW-1", "Раскрой", (31.5, 4.8, 2.0)),
    ("EDGE-1", "Кромка", (41.5, 4.5, 1.6)),
    ("CNC-1", "Присадка", (41.5, 12.6, 2.4)),
    ("ASM-1", "Сборка", (40.5, 19.0, 1.6)),
    ("PACK-1", "Упаковка", (45.4, 18.6, 1.8)),
    ("Z-POST", "Выход с линии", (53.0, 11.8, 1.2)),
    ("Z-FG", "Склад ГП", (52.0, 22.0, 2.5)),
    ("Z-OUT", "Отгрузка", (55.0, 5.0, 1.2)),
]

# --------------------------------------------------------------------------
# Материалы
# --------------------------------------------------------------------------
PALETTE = {
    "ground": ("#3a3d40", 0.95, 0.0),
    "floor": ("#b9bcbd", 0.85, 0.0),
    "wall": ("#d9dee2", 0.7, 0.1),
    "wall_band": ("#5a7184", 0.6, 0.2),
    "steel": ("#6c7a86", 0.45, 0.7),
    "steel_dark": ("#3c4650", 0.5, 0.6),
    "column": ("#8a96a0", 0.5, 0.5),
    "marking": ("#f2c230", 0.6, 0.0),
    "rack_upright": ("#2f5d8a", 0.45, 0.4),
    "rack_beam": ("#e8742a", 0.45, 0.3),
    "shelf": ("#9aa4ad", 0.5, 0.4),
    "bin": ("#2e86c1", 0.55, 0.0),
    "bin_red": ("#c0392b", 0.55, 0.0),
    "bin_yellow": ("#e5b223", 0.55, 0.0),
    "pallet": ("#b8925a", 0.9, 0.0),
    "carton": ("#c49a64", 0.85, 0.0),
    "machine": ("#e6e8ea", 0.45, 0.2),
    "machine_accent": ("#1f6f8b", 0.4, 0.3),
    "machine_dark": ("#2b3036", 0.5, 0.3),
    "table_top": ("#c8a878", 0.7, 0.0),
    "rubber": ("#1c1d1f", 0.9, 0.0),
    "forklift": ("#f0a224", 0.5, 0.1),
    "glass": ("#8fb8cf", 0.1, 0.0),
    "truck_cab": ("#c8ced3", 0.4, 0.5),
    "trailer": ("#eef1f3", 0.5, 0.2),
    "dock_shelter": ("#232629", 0.9, 0.0),
    "status_green": ("#27ae60", 0.4, 0.0),
    "status_amber": ("#f39c12", 0.4, 0.0),
    "status_red": ("#e74c3c", 0.4, 0.0),
    "flow": ("#18a6c9", 0.3, 0.0),
    "edge_roll": ("#c9a46f", 0.6, 0.0),
    "screen": ("#10303f", 0.2, 0.0),
}
for i, (_, hex_) in enumerate(SHEET_DECORS):
    PALETTE[f"decor{i}"] = (hex_, 0.75, 0.0)
for code, _, _, hex_, _ in ZONES:
    PALETTE["zone_" + code] = (hex_, 0.9, 0.0)

EDGE_DECORS = ["#c9a46f", "#efede6", "#45484c", "#4b3426", "#a7a39b", "#efede6"]
for i, hex_ in enumerate(EDGE_DECORS):
    PALETTE[f"edge{i}"] = (hex_, 0.6, 0.0)

MAT = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_materials():
    for name, (hex_, rough, metal) in PALETTE.items():
        h = hex_.lstrip("#")
        rgb = [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*rgb, 1.0)
        MAT[name] = m


# --------------------------------------------------------------------------
# Построение геометрии
# --------------------------------------------------------------------------
LAYER_OBJ = {}
LAYER_COLL = {}


class Mesh:
    """Набирает несколько примитивов в один меш (меньше объектов — быстрее сцена)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _paint(self, verts, mat, smooth=False):
        mi = self._mi(mat)
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = mi
            f.smooth = smooth

    def box(self, c, s, mat, rz=0.0):
        """c — центр, s — размеры (x, y, z), rz — поворот вокруг Z в градусах."""
        m = (Matrix.Translation(Vector(c)) @ Matrix.Rotation(math.radians(rz), 4, "Z")
             @ Matrix.Diagonal((*s, 1.0)))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        self._paint(r["verts"], mat)

    def box_lo(self, x, y, z0, sx, sy, sz, mat, rz=0.0):
        """Коробка, стоящая основанием на высоте z0."""
        self.box((x, y, z0 + sz / 2), (sx, sy, sz), mat, rz)

    def cyl(self, c, r, h, mat, axis="Z", segs=20, r2=None):
        rot = {"Z": Matrix.Identity(4),
               "X": Matrix.Rotation(math.radians(90), 4, "Y"),
               "Y": Matrix.Rotation(math.radians(90), 4, "X")}[axis]
        m = Matrix.Translation(Vector(c)) @ rot
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                    radius1=r, radius2=r if r2 is None else r2, depth=h, matrix=m)
        self._paint(res["verts"], mat, smooth=True)

    def cone_dir(self, tip, direction, r, h, mat, segs=16):
        d = Vector(direction).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        center = Vector(tip) - d * (h / 2)
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                    radius1=r, radius2=0.0, depth=h,
                                    matrix=Matrix.Translation(center) @ rot)
        self._paint(res["verts"], mat, smooth=True)

    def tube(self, pts, r, mat, segs=8):
        """Труба вдоль ломаной pts."""
        rings = []
        for i, p in enumerate(pts):
            p = Vector(p)
            a = Vector(pts[max(i - 1, 0)])
            b = Vector(pts[min(i + 1, len(pts) - 1)])
            t = (b - a).normalized()
            n = t.orthogonal().normalized()
            bn = t.cross(n)
            ring = []
            for k in range(segs):
                ang = 2 * math.pi * k / segs
                ring.append(self.bm.verts.new(p + (n * math.cos(ang) + bn * math.sin(ang)) * r))
            rings.append(ring)
        mi = self._mi(mat)
        for r0, r1 in zip(rings, rings[1:]):
            for k in range(segs):
                f = self.bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
                f.material_index = mi
                f.smooth = True

    def build(self, name, layer, parent=None, loc=(0, 0, 0), rz=0.0, **props):
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(MAT[m])
        ob = bpy.data.objects.new(name, me)
        place(ob, layer, parent, loc, rz, props)
        return ob


def place(ob, layer, parent, loc, rz, props):
    LAYER_COLL[layer].objects.link(ob)
    ob.parent = parent or LAYER_OBJ[layer]
    ob.location = loc
    ob.rotation_euler = (0, 0, math.radians(rz))
    for k, v in props.items():
        ob[k] = v


def empty(name, layer, loc=(0, 0, 0), rz=0.0, parent=None, **props):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.5
    place(ob, layer, parent, loc, rz, props)
    return ob


def make_layers():
    root = bpy.data.objects.new("FACTORY", None)
    bpy.context.scene.collection.objects.link(root)
    for key, label in LAYERS:
        coll = bpy.data.collections.new(label)
        bpy.context.scene.collection.children.link(coll)
        LAYER_COLL[key] = coll
        ob = bpy.data.objects.new("LAYER_" + key, None)
        coll.objects.link(ob)
        ob.parent = root
        ob["layer"] = key
        ob["label"] = label
        LAYER_OBJ[key] = ob


# ---------------------------------------------------------------- здание
def build_building():
    m = Mesh()
    m.box((W / 2, D / 2, -0.06), (W + 40, D + 24, 0.1), "ground")
    m.box((W / 2, D / 2, -0.1), (W, D, 0.2), "floor")
    m.build("Площадка и пол", "building")

    walls = Mesh()
    t = 0.25
    # северная стена — во всю высоту, южная — разрез (низкий парапет), чтобы было видно внутрь
    walls.box_lo(W / 2, D + t / 2, 0, W + 2 * t, t, H, "wall")
    walls.box_lo(W / 2, D + t / 2 + 0.01, 0, W + 2 * t, t, 0.9, "wall_band")
    walls.box_lo(W / 2, -t / 2, 0, W + 2 * t, t, 1.0, "wall_band")
    for side, x in (("W", -t / 2), ("E", W + t / 2)):
        doors = sorted((y, w) for s, y, w in DOORS if s == side)
        y0 = 0.0
        for yc, w in doors:
            a, b = yc - w / 2, yc + w / 2
            walls.box_lo(x, (y0 + a) / 2, 0, t, a - y0, H, "wall")
            walls.box_lo(x, yc, DOOR_H, t, w, H - DOOR_H, "wall")
            y0 = b
        walls.box_lo(x, (y0 + D) / 2, 0, t, D - y0, H, "wall")
        walls.box_lo(x + (0.01 if side == "E" else -0.01), D / 2, 0, t, D, 0.9, "wall_band")
    walls.build("Стены", "building")

    st = Mesh()
    for x, y in COLUMNS:
        st.box_lo(x, y, 0, 0.4, 0.4, H, "column")
        st.box_lo(x, y, 0, 0.55, 0.55, 1.2, "marking")
    st.build("Колонны", "building")
    rf = Mesh()
    for x in range(0, int(W) + 1, 12):
        rf.box_lo(x, D / 2, H - 0.45, 0.2, D, 0.45, "steel")
    for y in (10.0, 20.0):
        rf.box_lo(W / 2, y, H - 0.25, W, 0.12, 0.25, "steel_dark")
    rf.build("Фермы", "roof")

    # офис мастера: два этажа со сплошным остеклением на юг
    of = Mesh()
    x0, y0, x1, y1 = 28.0, 23.6, 36.4, 29.6
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for z in (0.0, 3.1):
        of.box_lo(cx, cy, z, x1 - x0, y1 - y0, 2.9, "wall")
        of.box_lo(cx, y0 - 0.01, z + 0.9, x1 - x0 - 0.6, 0.05, 1.6, "glass")
        of.box_lo(cx, cy, z + 2.9, x1 - x0 + 0.2, y1 - y0 + 0.2, 0.2, "wall_band")
    for i in range(10):  # лестница
        of.box_lo(x1 + 0.6, y0 + 0.4 + i * 0.3, i * 0.31, 1.0, 0.3, 0.31, "steel")
    of.build("OFFICE", "building", code="OFFICE", kind="building",
             label="Офис мастера", desc="Двухэтажный модуль: мастер участка и технолог.")

    for side, yc, w in DOORS:
        d = Mesh()
        inside = 1 if side == "W" else -1
        x = 0.0 if side == "W" else W
        d.box_lo(x - inside * 0.35, yc, 0, 0.5, w + 0.8, DOOR_H + 0.4, "dock_shelter")
        d.box_lo(x + inside * 1.2, yc, 0.0, 2.4, w - 0.4, 0.03, "steel")
        for dy in (-1, 1):
            d.box_lo(x + inside * 0.15, yc + dy * (w / 2 + 0.1), 0, 0.2, 0.2, DOOR_H, "marking")
        layer = "receiving" if side == "W" else "shipping"
        idx = sum(1 for s, yy, _ in DOORS if s == side and yy <= yc)
        kind_ru = "Ворота приёмки" if side == "W" else "Ворота отгрузки"
        d.build(f"DOCK-{side}{idx}", layer, code=f"DOCK-{side}{idx}", kind="dock",
                label=f"{kind_ru} {idx}", desc="Докшелтер и уравнительная платформа.")


# ---------------------------------------------------------------- зоны
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


# ---------------------------------------------------------------- склады
def pallet(m, x, y, z=0.0, rz=0.0, sx=1.2, sy=0.8):
    m.box_lo(x, y, z, sx, sy, 0.144, "pallet", rz)


def build_receiving():
    m = Mesh()
    for i, (y, n) in enumerate(((3.0, 30), (6.0, 40), (9.5, 22))):
        m.box_lo(4.0, y, 0, 2.9, 2.1, 0.12, "pallet")
        m.box_lo(4.0, y, 0.12, 2.8, 2.07, n * 0.016, "decor%d" % (i % 2))
    m.build("IN-STAGE", "receiving", code="IN-STAGE", kind="stock",
            label="Плита на разгрузке", desc="Три стопы с фуры: ДСП Дуб Сонома и Белый, ждут сверки.")

    q = Mesh()
    q.box_lo(4.5, 17.0, 0, 2.0, 1.0, 0.9, "table_top")
    q.box_lo(4.5, 17.0, 0.9, 0.8, 0.6, 0.02, "decor0")
    q.box_lo(2.5, 17.0, 0, 2.9, 2.1, 0.12, "pallet")
    q.box_lo(2.5, 17.0, 0.12, 2.8, 2.07, 0.4, "decor2")
    for dx in (-1.45, 1.45):
        for dy in (-1.05, 1.05):
            q.box_lo(2.5 + dx, 17.0 + dy, 0, 0.08, 0.08, 1.0, "status_red")
    q.build("QC-1", "receiving", code="QC-1", kind="stock", label="Входной контроль",
            desc="Стол замеров и стопа на карантине (красные стойки — не прошла проверку).")


def build_sheets():
    for row, y in SHEET_ROWS_Y.items():
        for i, x in enumerate(SHEET_COLS_X):
            decor, n = SHEET_STACKS[row][i]
            code = f"PLT-{row}{i + 1}"
            m = Mesh()
            m.box_lo(x, y, 0, 2.9, 2.15, 0.1, "pallet")
            if n:
                m.box_lo(x, y, 0.1, 2.8, 2.07, n * 0.016 if decor != 6 else n * 0.003 + 0.02,
                         "decor%d" % decor)
            m.box_lo(x - 1.5, y, 0.01, 0.06, 2.15, 0.02, "marking")
            name = SHEET_DECORS[decor][0] if n else "пусто"
            m.build(code, "sheets", code=code, kind="stock", label=f"Стопа {code}",
                    desc=f"{name}, {n} лист." if n else "Место свободно.")


def build_hardware():
    rows_y = {"R1": 17.4, "R2": 21.6, "R3": 25.8}
    sec_w, nsec, x0 = 2.0, 5, 10.5
    levels = [0.12, 0.72, 1.32, 1.92]
    depth = 0.6
    # состояние ячеек для наглядности: синие — норма, жёлтые — мало, красные — пусто
    low = {("R1", 2, 3), ("R2", 4, 1), ("R3", 1, 4), ("R2", 2, 2)}
    out = {("R3", 5, 2), ("R1", 5, 4)}
    for row, y in rows_y.items():
        fr = Mesh()
        for s in range(nsec + 1):
            for dy in (-depth / 2, depth / 2):
                fr.box_lo(x0 + s * sec_w, y + dy, 0, 0.06, 0.06, 2.5, "rack_upright")
        for z in levels:
            fr.box_lo(x0 + nsec * sec_w / 2, y, z - 0.03, nsec * sec_w, depth, 0.03, "shelf")
            for dy in (-depth / 2, depth / 2):
                fr.box_lo(x0 + nsec * sec_w / 2, y + dy, z - 0.08, nsec * sec_w, 0.04, 0.08,
                          "rack_beam")
        fr.build(f"RACK-{row}", "hardware", code=f"RACK-{row}", kind="rack",
                 label=f"Стеллаж {row}", desc=f"{nsec} секций × {len(levels)} яруса, ячейки с лотками.")
        for s in range(1, nsec + 1):
            for li, z in enumerate(levels, 1):
                code = f"FUR-{row}-S{s}-L{li}"
                m = Mesh()
                state = "out" if (row, s, li) in out else "low" if (row, s, li) in low else "ok"
                mat = {"ok": "bin", "low": "bin_yellow", "out": "bin_red"}[state]
                nb = 0 if state == "out" else 4
                for b in range(nb):
                    bx = x0 + (s - 1) * sec_w + 0.27 + b * 0.49
                    m.box_lo(bx, y, z, 0.44, 0.5, 0.26, mat)
                m.box_lo(x0 + (s - 0.5) * sec_w, y - depth / 2 - 0.03, z - 0.075, 0.24, 0.01, 0.06,
                         mat if state != "ok" else "screen")
                m.build(code, "hardware", code=code, kind="bin", state=state,
                        label=f"Ячейка {code}",
                        desc={"ok": "Запас в норме.", "low": "Запас ниже минимума.",
                              "out": "Ячейка пуста."}[state])


def build_edge():
    for u, x in (("U1", 2.4), ("U2", 6.4)):
        fr = Mesh()
        ys, ye = 22.2, 28.6
        for yy in (ys, (ys + ye) / 2, ye):
            for dx in (-0.45, 0.45):
                fr.box_lo(x + dx, yy, 0, 0.06, 0.06, 2.4, "rack_upright")
        for z in (0.1, 0.9, 1.7):
            fr.box_lo(x, (ys + ye) / 2, z - 0.04, 0.9, ye - ys, 0.04, "shelf")
        fr.build(f"EB-{u}", "edge", code=f"EB-{u}", kind="rack", label=f"Стеллаж кромки {u}",
                 desc="Рулоны кромки ПВХ стоят на ребре.")
        for li, z in enumerate((0.1, 0.9, 1.7), 1):
            m = Mesh()
            decor = (li + (3 if u == "U2" else 0)) % len(EDGE_DECORS)
            n = [9, 14, 6, 11, 4, 12][(li - 1) + (3 if u == "U2" else 0)]
            for k in range(n):
                m.cyl((x, ys + 0.45 + k * 0.42, z + 0.32), 0.3, 0.08, "edge%d" % decor, axis="Y")
            code = f"EB-{u}-L{li}"
            m.build(code, "edge", code=code, kind="stock", label=f"Полка {code}",
                    desc=f"{n} рулонов кромки по 200 м.")


def build_buffer():
    for i, y in enumerate((4.0, 8.6, 13.4, 17.8, 22.4), 1):
        m = Mesh()
        x = 25.2
        m.box_lo(x, y, 0.15, 1.3, 2.2, 0.05, "steel")
        for dx in (-0.55, 0.55):
            for dy in (-1.0, 1.0):
                m.cyl((x + dx, y + dy, 0.075), 0.075, 0.05, "rubber", axis="X", segs=12)
        m.box_lo(x, y - 1.05, 0.2, 1.3, 0.05, 1.1, "steel")
        for k in range(4 if i != 5 else 1):
            m.box_lo(x - 0.1, y + 0.1, 0.2 + k * 0.1, 0.9, 1.6, 0.016, "decor%d" % ((i + k) % 4))
        m.box_lo(x + 0.45, y + 0.6, 0.2, 0.3, 0.4, 0.2, "bin")
        code = f"KIT-{i}"
        m.build(code, "buffer", code=code, kind="kit", label=f"Тележка {code}",
                desc="Комплект деталей и фурнитуры под один заказ." if i != 5
                else "Тележка почти пустая, ждёт комплектации.")


# ---------------------------------------------------------------- станки
def status_tower(m, x, y, h=2.2):
    m.box_lo(x, y, 0, 0.05, 0.05, h, "steel_dark")
    for i, mat in enumerate(("status_green", "status_amber", "status_red")):
        m.cyl((x, y, h + 0.07 + i * 0.13), 0.06, 0.12, mat, segs=12)


def outline(m, sx, sy, mat="marking", w=0.08):
    for (cx, cy, a, b) in ((0, -sy / 2, sx, w), (0, sy / 2, sx, w), (-sx / 2, 0, w, sy), (sx / 2, 0, w, sy)):
        m.box((cx, cy, 0.02), (a, b, 0.02), mat)


def machine_saw(m):
    m.box_lo(-1.4, 0, 0, 2.6, 3.8, 0.88, "machine")
    m.box_lo(-1.4, 0, 0.88, 2.6, 3.8, 0.02, "machine_dark")
    m.box_lo(0.25, 0, 0, 0.8, 4.5, 1.25, "machine")
    m.box_lo(0.25, 0, 1.25, 0.6, 4.7, 0.4, "machine_accent")
    m.box_lo(0.25, -2.45, 0, 0.8, 0.4, 1.9, "machine_dark")
    for dy in (-1.4, 0, 1.4):
        m.box_lo(1.75, dy, 0, 2.0, 1.1, 0.88, "machine")
        m.box_lo(1.75, dy, 0.88, 2.0, 1.1, 0.015, "machine_dark")
    m.box_lo(-0.3, -2.95, 0, 0.4, 0.4, 1.25, "machine_dark")
    m.box((-0.3, -2.95, 1.45), (0.55, 0.12, 0.4), "screen", rz=0)
    # стопа плиты на подаче и нарезанные детали на выходе
    m.box_lo(-1.4, 0, 0.9, 2.5, 2.07, 0.24, "decor0")
    for i, dy in enumerate((-1.4, -0.1, 1.2)):
        m.box_lo(1.6, dy, 0.9, 1.4, 0.7, 0.016 * (3 + i), "decor0")
    outline(m, 6.0, 6.6)


def machine_edge(m):
    m.box_lo(0, 0, 0, 8.0, 1.0, 1.0, "machine")
    for i in range(5):
        m.box_lo(-3.2 + i * 1.6, 0.05, 1.0, 1.45, 0.9, 0.35, "machine_accent" if i % 2 else "machine")
    m.box_lo(-5.0, 0, 0, 2.0, 1.2, 0.9, "steel")
    m.box_lo(5.0, 0, 0, 2.0, 1.2, 0.9, "steel")
    m.box_lo(0, 1.25, 0, 10.0, 0.6, 0.8, "steel")
    for i in range(20):
        m.cyl((-4.75 + i * 0.5, 1.25, 0.82), 0.03, 0.55, "steel_dark", axis="Y", segs=8)
    m.cyl((-3.9, -0.75, 1.15), 0.3, 0.06, "edge_roll")
    m.box_lo(-3.9, -0.75, 0, 0.1, 0.1, 0.85, "steel_dark")
    m.box_lo(3.2, -0.75, 0, 0.4, 0.3, 1.3, "machine_dark")
    m.box((3.2, -0.92, 1.45), (0.5, 0.06, 0.35), "screen")
    for i in range(3):
        m.box_lo(-5.0, 0, 0.9 + i * 0.02, 1.4, 0.7, 0.016, "decor0")
    outline(m, 12.4, 3.6)


def machine_cnc(m):
    m.box_lo(0, 0, 0, 3.4, 1.9, 0.82, "machine")
    m.box_lo(0, 0, 0.82, 3.2, 1.7, 0.06, "machine_dark")
    for dy in (-1.1, 1.1):
        m.box_lo(0.3, dy, 0, 0.45, 0.35, 2.0, "machine_accent")
    m.box_lo(0.3, 0, 2.0, 0.55, 2.6, 0.45, "machine_accent")
    m.box_lo(0.3, 0, 1.3, 0.45, 0.5, 0.7, "machine")
    m.cyl((0.3, 0, 1.2), 0.05, 0.2, "steel_dark", segs=10)
    m.box_lo(-0.6, 0, 0.88, 1.4, 0.7, 0.016, "decor1")
    m.box_lo(-2.4, -1.3, 0, 0.7, 0.6, 2.0, "machine_dark")
    m.box_lo(-1.9, -1.4, 0, 0.35, 0.35, 1.2, "machine_dark")
    m.box((-1.9, -1.58, 1.4), (0.5, 0.05, 0.35), "screen")
    outline(m, 5.6, 3.8)


def machine_asm(m):
    m.box_lo(0, 0, 0, 3.0, 1.6, 0.8, "steel")
    m.box_lo(0, 0, 0.8, 3.0, 1.6, 0.05, "table_top")
    # корпус шкафа на столе
    for dx in (-0.29, 0.29):
        m.box_lo(dx, 0, 0.85, 0.016, 0.56, 0.72, "decor0")
    m.box_lo(0, 0, 0.85, 0.6, 0.56, 0.016, "decor0")
    m.box_lo(0, 0, 1.55, 0.6, 0.56, 0.016, "decor0")
    m.box_lo(0, 0.27, 0.85, 0.6, 0.01, 0.72, "decor6")
    m.box_lo(0, 1.25, 0, 2.6, 0.08, 2.0, "steel")
    m.box_lo(0, 1.2, 0.9, 2.4, 0.02, 1.0, "machine")
    m.box_lo(-2.2, 0, 0, 1.0, 0.7, 0.9, "steel")
    for k in range(3):
        m.box_lo(-2.2, 0, 0.9 + k * 0.016, 0.8, 0.5, 0.016, "decor0")
    outline(m, 5.6, 3.4)


def machine_pack(m):
    m.box_lo(-0.7, 0, 0, 2.2, 1.4, 0.85, "steel")
    m.box_lo(-0.7, 0, 0.85, 2.2, 1.4, 0.04, "table_top")
    m.cyl((-0.7, 0.75, 1.05), 0.2, 1.3, "carton", axis="X")
    m.box_lo(-0.9, -0.1, 0.89, 0.9, 0.7, 0.4, "carton")
    m.cyl((1.4, 0, 0.06), 0.8, 0.12, "steel_dark", segs=28)
    m.box_lo(1.4, 1.0, 0, 0.2, 0.2, 2.3, "machine_accent")
    m.box_lo(1.4, 0.88, 1.0, 0.25, 0.1, 0.4, "machine")
    pallet(m, 1.4, 0, 0.12)
    for k in range(3):
        m.box_lo(1.4, 0, 0.27 + k * 0.42, 1.15, 0.75, 0.4, "carton")
    outline(m, 5.0, 3.0)


MACHINE_BUILDERS = {"saw": machine_saw, "edge": machine_edge, "cnc": machine_cnc,
                    "asm": machine_asm, "pack": machine_pack}
TOWER_POS = {"saw": (-0.3, 2.6), "edge": (3.8, -1.3), "cnc": (1.9, -1.4),
             "asm": (1.6, -0.9), "pack": (-1.9, -0.9)}
STATUS = {"SAW-1": "work", "SAW-2": "idle", "EDGE-1": "work", "CNC-1": "stop",
          "ASM-1": "work", "ASM-2": "idle", "PACK-1": "work"}


def build_machines():
    for code, typ, name, x, y, desc in MACHINES:
        root = empty(code, "line", loc=(x, y, 0), code=code, kind="machine", label=name,
                     desc=desc, status=STATUS[code])
        body = Mesh()
        MACHINE_BUILDERS[typ](body)
        tx, ty = TOWER_POS[typ]
        status_tower(body, tx, ty)
        body.build(code + "_body", "line", parent=root)
        lamp = Mesh()
        lamp.cyl((tx, ty, 2.66), 0.1, 0.16, {"work": "status_green", "idle": "status_amber",
                                              "stop": "status_red"}[STATUS[code]], segs=16)
        lamp.build(code + "_lamp", "line", parent=root, role="status")


def build_maintenance():
    m = Mesh()
    for x in (39.0, 42.0):
        m.box_lo(x, 28.6, 0, 2.0, 0.8, 0.9, "steel")
        m.box_lo(x, 28.6, 0.9, 2.0, 0.8, 0.04, "table_top")
    m.box_lo(45.5, 28.8, 0, 1.0, 0.6, 2.0, "status_red")
    m.box_lo(46.8, 28.8, 0, 1.0, 0.6, 2.0, "machine_dark")
    m.cyl((42.0, 28.6, 0.98), 0.3, 0.01, "steel", segs=32)
    m.build("MAINT", "line", code="MAINT-1", kind="building", label="Ремонтный участок",
            desc="Верстаки, шкафы с инструментом, заточка пил.")


# ---------------------------------------------------------------- готовая продукция
FG_ROWS = {"R1": 50.15, "R2": 54.05, "R3": 55.15}
FG_PRODUCTS = ["Шкаф нижний 600", "Шкаф верхний 800", "Пенал 400", "Тумба 3 ящика",
               "Стол офисный 1400", "Шкаф для документов 800"]


def build_fg():
    bay_w, nbay, y0 = 2.7, 5, 15.0
    levels = [0.0, 1.9, 3.8]
    depth = 1.1
    filled = 0
    for row, x in FG_ROWS.items():
        fr = Mesh()
        for b in range(nbay + 1):
            for dx in (-depth / 2, depth / 2):
                fr.box_lo(x + dx, y0 + b * bay_w, 0, 0.09, 0.09, 5.4, "rack_upright")
            for z in (1.0, 2.0, 3.0, 4.0, 5.0):
                fr.box_lo(x, y0 + b * bay_w, z, depth, 0.04, 0.04, "rack_upright")
        for z in levels[1:]:
            for dx in (-depth / 2, depth / 2):
                fr.box_lo(x + dx, y0 + nbay * bay_w / 2, z - 0.12, 0.06, nbay * bay_w, 0.12,
                          "rack_beam")
        fr.build(f"FG-RACK-{row}", "fg", code=f"FG-RACK-{row}", kind="rack",
                 label=f"Паллетный стеллаж {row}", desc=f"{nbay} пролётов × {len(levels)} яруса.")
        for b in range(1, nbay + 1):
            for li, z in enumerate(levels, 1):
                code = f"FG-{row}-B{b}-L{li}"
                seed = (sum(map(ord, code)) + b * 3 + li * 5) % 7
                n = 0 if seed in (0, 4) else (1 if seed == 3 else 2)
                m = Mesh()
                for p in range(n):
                    py = y0 + (b - 1) * bay_w + 0.7 + p * 1.3
                    pallet(m, x, py, z + 0.02, sx=1.0, sy=1.2)
                    layers = 2 + (seed + p) % 2
                    for k in range(layers):
                        m.box_lo(x, py, z + 0.17 + k * 0.42, 0.95, 1.15, 0.4, "carton")
                    filled += 1
                prod = FG_PRODUCTS[(b + li + len(row)) % len(FG_PRODUCTS)]
                m.box_lo(x - depth / 2 - 0.02, y0 + (b - 0.5) * bay_w, z + 0.05 if z else 0.05,
                         0.01, 0.3, 0.08, "screen" if n else "status_amber")
                m.build(code, "fg", code=code, kind="stock",
                        label=f"Ячейка {code}",
                        desc=f"{prod}: {n} паллет." if n else "Свободно.")


def build_post_and_shipping():
    m = Mesh()
    for i, x in enumerate((50.5, 52.2, 53.9)):
        pallet(m, x, 11.8)
        for k in range(2 + i % 2):
            m.box_lo(x, 11.8, 0.15 + k * 0.42, 1.15, 0.75, 0.4, "carton")
    m.build("POST-STAGE", "fg", code="POST-STAGE", kind="stock", label="Готово к размещению",
            desc="Упакованные паллеты с линии, ждут размещения в стеллаже.")

    s = Mesh()
    for j, y in enumerate((2.4, 4.0, 6.4, 8.0)):
        for i, x in enumerate((54.0, 55.6)):
            if (i + j) % 3 == 2:
                continue
            pallet(s, x, y)
            for k in range(2 + (i + j) % 2):
                s.box_lo(x, y, 0.15 + k * 0.42, 1.15, 0.75, 0.4, "carton")
    s.build("OUT-STAGE", "shipping", code="OUT-STAGE", kind="stock", label="Отгрузка на сегодня",
            desc="Паллеты, собранные под машины к воротам 1 и 2.")


# ---------------------------------------------------------------- транспорт
def forklift(m):
    m.box_lo(0, 0, 0.15, 1.6, 1.05, 0.75, "forklift")
    m.box_lo(-0.65, 0, 0.15, 0.4, 1.05, 0.95, "machine_dark")
    for dx in (-0.55, 0.55):
        for dy in (-0.48, 0.48):
            m.cyl((dx, dy, 0.24), 0.24, 0.22, "rubber", axis="Y", segs=16)
    for dx in (-0.5, 0.35):
        for dy in (-0.45, 0.45):
            m.box_lo(dx, dy, 0.9, 0.06, 0.06, 1.15, "machine_dark")
    m.box_lo(-0.07, 0, 2.05, 0.95, 1.0, 0.05, "machine_dark")
    m.box_lo(-0.1, 0, 0.9, 0.5, 0.5, 0.45, "machine_dark")
    for dy in (-0.3, 0.3):
        m.box_lo(0.9, dy, 0.05, 0.08, 0.1, 2.3, "steel_dark")
    for dy in (-0.25, 0.25):
        m.box_lo(1.45, dy, 0.1, 1.1, 0.12, 0.04, "steel_dark")


def build_transport():
    f1 = Mesh()
    forklift(f1)
    f1.box_lo(1.45, 0, 0.14, 1.2, 0.8, 0.144, "pallet")
    f1.box_lo(1.45, 0, 0.28, 1.1, 0.75, 0.5, "carton")
    f1.build("FL-1", "transport", loc=(52.0, 21.0, 0), rz=-90, code="FL-1", kind="vehicle",
             label="Погрузчик 1", desc="Электропогрузчик 1,6 т, высота подъёма 4,5 м.")
    f2 = Mesh()
    forklift(f2)
    f2.box_lo(1.6, 0, 0.14, 2.9, 2.1, 0.1, "pallet")
    f2.box_lo(1.6, 0, 0.24, 2.8, 2.07, 0.35, "decor1")
    f2.build("FL-2", "transport", loc=(16.0, 5.3, 0), rz=180, code="FL-2", kind="vehicle",
             label="Погрузчик 2", desc="Перевозит стопу плиты с приёмки на склад.")

    def truck(m, length=8.5):
        m.box_lo(0, 0, 1.1, length, 2.5, 2.9, "trailer")
        m.box_lo(-length / 2 - 1.15, 0, 0.6, 2.2, 2.4, 2.6, "truck_cab")
        m.box_lo(-length / 2 - 2.0, 0, 1.9, 0.5, 2.2, 1.0, "glass")
        m.box_lo(-1.0, 0, 0.6, length, 1.0, 0.5, "steel_dark")
        for x in (-length / 2 - 1.5, length / 2 - 2.6, length / 2 - 1.3):
            for dy in (-1.0, 1.0):
                m.cyl((x, dy, 0.5), 0.5, 0.35, "rubber", axis="Y", segs=18)

    t1 = Mesh()
    truck(t1)
    t1.build("TRUCK-IN", "transport", loc=(-4.6, 4.0, 0), rz=0, code="TRUCK-IN", kind="vehicle",
             label="Фура на разгрузке", desc="Поставка плиты у ворот приёмки 1.")
    t2 = Mesh()
    truck(t2)
    t2.build("TRUCK-OUT", "transport", loc=(W + 4.6, 3.0, 0), rz=180, code="TRUCK-OUT",
             kind="vehicle", label="Машина под погрузкой", desc="Отгрузка у ворот 1.")


# ---------------------------------------------------------------- маршрут
def arc_points(p0, p1, n=24):
    a, b = Vector(p0), Vector(p1)
    lift = 1.6 + 0.12 * (b - a).length
    c = (a + b) / 2 + Vector((0, 0, lift))
    return [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * c + t ** 2 * b)
            for t in (i / n for i in range(n + 1))]


def build_flow():
    m = Mesh()
    for (_, _, p0), (_, _, p1) in zip(FLOW, FLOW[1:]):
        pts = arc_points(p0, p1)
        m.tube(pts[:-2], 0.07, "flow")
        tip = Vector(pts[-1])
        m.cone_dir(tip, tip - Vector(pts[-3]), 0.22, 0.6, "flow")
    for _, _, p in FLOW:
        m.cyl(p, 0.18, 0.12, "flow", segs=16)
    m.build("FLOW", "flow", code="FLOW", kind="flow", label="Маршрут изделия",
            desc="Приёмка → склад плит → буфер → раскрой → кромка → присадка → сборка → "
                 "упаковка → склад ГП → отгрузка.",
            route=json.dumps([{"code": c, "label": n, "p": p} for c, n, p in FLOW],
                             ensure_ascii=False))


# --------------------------------------------------------------------------
def main(out_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    make_materials()
    make_layers()
    build_building()
    build_zones()
    build_receiving()
    build_sheets()
    build_hardware()
    build_edge()
    build_buffer()
    build_machines()
    build_maintenance()
    build_fg()
    build_post_and_shipping()
    build_transport()
    build_flow()

    # камера и свет — для тех, кто откроет .blend
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (8, -32, 38)
    cam.rotation_euler = (math.radians(52), 0, math.radians(-25))
    bpy.context.scene.camera = cam
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(30))
    bpy.context.scene.collection.objects.link(sun)

    os.makedirs(out_dir, exist_ok=True)
    glb = os.path.join(out_dir, "factory.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_extras=True,
                              export_yup=True, export_apply=True, export_cameras=False,
                              export_lights=False)
    bpy.ops.wm.usd_export(filepath=os.path.join(out_dir, "factory.usdz"),
                          export_materials=True, generate_preview_surface=True,
                          convert_orientation=True, export_global_forward_selection="NEGATIVE_Z",
                          export_global_up_selection="Y", export_lights=False,
                          export_cameras=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(out_dir, "factory.blend")))
    viewer = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer", "index.html")
    shutil.copy(viewer, os.path.join(out_dir, "index.html"))
    n = sum(1 for o in bpy.data.objects if o.type == "MESH")
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons)
               for o in bpy.data.objects if o.type == "MESH")
    print(f"meshes={n} tris={tris}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv[0] if argv else "dist")
