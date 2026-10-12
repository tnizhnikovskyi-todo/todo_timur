"""Геометрія сцени: матеріали, збирач мешів, спільні меші та дрібні типові вузли
(палети, коробки, пульти, огорожі, роботи, люди, навантажувачі)."""
import math

import bpy  # noqa: I001 — bpy має імпортуватися раніше за bmesh/mathutils
import bmesh
from mathutils import Euler, Matrix, Vector

from .layout import EDGE_DECORS, LAYERS, SHEET_DECORS, ZONES

# --------------------------------------------------------------------------
# Матеріали: колір (sRGB), шорсткість, металевість, [прозорість], [світіння]
# --------------------------------------------------------------------------
PALETTE = {
    "ground": ("#3a3d40", 0.95, 0.0),
    "floor": ("#aeb2b3", 0.6, 0.0),
    "wall": ("#d9dee2", 0.7, 0.1),
    "wall_band": ("#4f6679", 0.6, 0.2),
    "steel": ("#7d8a95", 0.4, 0.75),
    "steel_dark": ("#3c4650", 0.5, 0.6),
    "column": ("#8a96a0", 0.5, 0.5),
    "alu": ("#c7ccd1", 0.3, 0.85),
    "galv": ("#b4bcc3", 0.35, 0.9),
    "marking": ("#f2c230", 0.6, 0.0),
    "hazard_black": ("#1e1f21", 0.6, 0.0),
    "rack_upright": ("#2f5d8a", 0.45, 0.4),
    "rack_beam": ("#e8742a", 0.45, 0.3),
    "shelf": ("#9aa4ad", 0.5, 0.4),
    "bin": ("#2e86c1", 0.55, 0.0),
    "bin_red": ("#c0392b", 0.55, 0.0),
    "bin_yellow": ("#e5b223", 0.55, 0.0),
    "pallet": ("#b8925a", 0.9, 0.0),
    "carton": ("#c49a64", 0.85, 0.0),
    "tape": ("#9c7444", 0.5, 0.0),
    "wrap": ("#e6eef2", 0.15, 0.0, 0.35),
    "machine": ("#e3e6e8", 0.35, 0.15),
    "machine_mid": ("#b9c0c6", 0.4, 0.2),
    "machine_accent": ("#1d6a86", 0.35, 0.25),
    "machine_dark": ("#2b3036", 0.45, 0.3),
    "phenolic": ("#f1f1ec", 0.35, 0.0),
    "guard_glass": ("#bcd9e6", 0.05, 0.0, 0.28),
    "table_top": ("#c8a878", 0.7, 0.0),
    "rubber": ("#1c1d1f", 0.9, 0.0),
    "forklift": ("#f0a224", 0.45, 0.1),
    "glass": ("#8fb8cf", 0.1, 0.0),
    "truck_cab": ("#c8ced3", 0.4, 0.5),
    "trailer": ("#eef1f3", 0.5, 0.2),
    "dock_shelter": ("#232629", 0.9, 0.0),
    "lamp_off_g": ("#2f5a3f", 0.4, 0.0),
    "lamp_off_a": ("#6b5222", 0.4, 0.0),
    "lamp_off_r": ("#5e2a26", 0.4, 0.0),
    "status_green": ("#27ae60", 0.3, 0.0),
    "status_amber": ("#f39c12", 0.3, 0.0),
    "status_red": ("#e74c3c", 0.3, 0.0),
    "estop": ("#d0281d", 0.4, 0.0),
    "screen": ("#10303f", 0.2, 0.0),
    "screen_on": ("#1d3d52", 0.2, 0.0, 1.0, ("#3aa0d8", 0.8)),
    "led": ("#f4f7fa", 0.3, 0.0, 1.0, ("#ffffff", 2.0)),
    "flow": ("#18a6c9", 0.3, 0.0),
    "flow2": ("#b05fd8", 0.3, 0.0),
    "edge_roll": ("#c9a46f", 0.6, 0.0),
    "trousers": ("#2b3a55", 0.85, 0.0),
    "shirt": ("#4a5563", 0.85, 0.0),
    "hivis": ("#d7e62f", 0.6, 0.0),
    "hivis_or": ("#f07c22", 0.6, 0.0),
    "skin": ("#d6a27f", 0.7, 0.0),
    "hair": ("#3b2a20", 0.9, 0.0),
    "pegboard": ("#8e969c", 0.7, 0.2),
    "film_roll": ("#e9eef1", 0.2, 0.0, 0.8),
    "robot": ("#e8822a", 0.4, 0.2),
    "heater": ("#5a1c10", 0.4, 0.0, 1.0, ("#ff5a2a", 2.5)),
    "uv": ("#2a1a50", 0.3, 0.0, 1.0, ("#8a5cff", 4.0)),
    "fire_red": ("#c62828", 0.5, 0.1),
    "air_blue": ("#2f78c4", 0.4, 0.3),
    "water_glass": ("#7fb6d6", 0.05, 0.0, 0.45),
    "filter": ("#d7d2c4", 0.9, 0.0),
    "drum_blue": ("#2459a8", 0.45, 0.3),
    "ibc": ("#eef1f3", 0.2, 0.0, 0.7),
    "carton_bag": ("#e9e4d6", 0.9, 0.0),
    "elec_cab": ("#d5d7d2", 0.5, 0.15),
    "busbar": ("#a9afb0", 0.4, 0.55),
    "copper": ("#b8733a", 0.35, 0.9),
    "trafo_coil": ("#3a4b5c", 0.45, 0.1),
    "mesh_fence": ("#9aa3aa", 0.4, 0.6, 0.35),
    "exit_green": ("#1e9e57", 0.3, 0.0, 1.0, ("#2bd67f", 1.5)),
    "pipe_red": ("#b8392e", 0.6, 0.1),
    "pipe_blue": ("#2f6db5", 0.6, 0.1),
    "fabric_blue": ("#5b8fc4", 0.9, 0.0),
    "asphalt": ("#55595d", 0.95, 0.0),
    "pv_cell": ("#1b2a44", 0.15, 0.4),
    "water_pipe": ("#2a9d8f", 0.5, 0.2),
    "smoke_curtain": ("#c9ccc4", 0.9, 0.0, 0.55),
    "roof_deck": ("#8d959b", 0.75, 0.3),
    "gas_yellow": ("#e3b81c", 0.5, 0.1),
    "chp_body": ("#2f6f4f", 0.5, 0.2),
}
for i, (_, hex_) in enumerate(SHEET_DECORS):
    PALETTE[f"decor{i}"] = (hex_, 0.7, 0.0)
for code, _, _, hex_, _ in ZONES:
    PALETTE["zone_" + code] = (hex_, 0.9, 0.0)
for i, hex_ in enumerate(EDGE_DECORS):
    PALETTE[f"edge{i}"] = (hex_, 0.6, 0.0)

MAT = {}
LAYER_OBJ = {}
LAYER_COLL = {}
MESHES = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_lin(hex_):
    h = hex_.lstrip("#")
    return [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]


def make_materials():
    for name, spec in PALETTE.items():
        hex_, rough, metal = spec[:3]
        alpha = spec[3] if len(spec) > 3 else 1.0
        emit = spec[4] if len(spec) > 4 else None
        rgb = hex_to_lin(hex_)
        m = bpy.data.materials.new(name)
        if hasattr(m, "use_nodes") and not m.node_tree:
            m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            if hasattr(m, "surface_render_method"):
                m.surface_render_method = "BLENDED"
            else:
                m.blend_method = "BLEND"
        if emit:
            bsdf.inputs["Emission Color"].default_value = (*hex_to_lin(emit[0]), 1.0)
            bsdf.inputs["Emission Strength"].default_value = emit[1]
        m.diffuse_color = (*rgb, alpha)
        MAT[name] = m


class Mesh:
    """Набирає багато примітивів в один меш (менше об'єктів — швидша сцена)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _paint(self, faces, mat, smooth=False):
        mi = self._mi(mat)
        for f in faces:
            f.material_index = mi
            f.smooth = smooth

    @staticmethod
    def _faces_of(verts):
        return {f for v in verts for f in v.link_faces}

    def box(self, c, s, mat, rz=0.0, rot=None, bev=0.0):
        """c — центр, s — розміри (x, y, z), rz — поворот навколо Z у градусах,
        rot — (rx, ry, rz) у градусах, bev — радіус скруглення ребер."""
        rx, ry, rzz = rot if rot else (0.0, 0.0, rz)
        m = (Matrix.Translation(Vector(c))
             @ Euler((math.radians(rx), math.radians(ry), math.radians(rzz))).to_matrix().to_4x4()
             @ Matrix.Diagonal((*s, 1.0)))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        verts = r["verts"]
        self._paint(self._faces_of(verts), mat)
        bev = min(bev, min(s) * 0.45)
        if bev > 0.004:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bev, offset_type="OFFSET",
                                  segments=2 if bev >= 0.02 else 1, profile=0.5,
                                  affect="EDGES", clamp_overlap=True)
            self._paint(res["faces"], mat, smooth=True)

    def box_lo(self, x, y, z0, sx, sy, sz, mat, rz=0.0, bev=0.0):
        """Коробка, що стоїть основою на висоті z0."""
        self.box((x, y, z0 + sz / 2), (sx, sy, sz), mat, rz, bev=bev)

    def cyl(self, c, r, h, mat, axis="Z", segs=20, r2=None, rot=None):
        if rot:
            R = Euler(tuple(math.radians(a) for a in rot)).to_matrix().to_4x4()
        else:
            R = {"Z": Matrix.Identity(4),
                 "X": Matrix.Rotation(math.radians(90), 4, "Y"),
                 "Y": Matrix.Rotation(math.radians(90), 4, "X")}[axis]
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                    radius1=r, radius2=r if r2 is None else r2, depth=h,
                                    matrix=Matrix.Translation(Vector(c)) @ R)
        faces = self._faces_of(res["verts"])
        self._paint(faces, mat, smooth=True)
        for f in faces:  # торці пласкі
            if len(f.verts) > 4:
                f.smooth = False

    def sphere(self, c, r, mat, subdiv=2, scale=(1, 1, 1)):
        m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal((*scale, 1.0))
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=r, matrix=m)
        self._paint(self._faces_of(res["verts"]), mat, smooth=True)

    def cone_dir(self, tip, direction, r, h, mat, segs=16):
        d = Vector(direction).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        center = Vector(tip) - d * (h / 2)
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                    radius1=r, radius2=0.0, depth=h,
                                    matrix=Matrix.Translation(center) @ rot)
        self._paint(self._faces_of(res["verts"]), mat, smooth=True)

    def tube(self, pts, r, mat, segs=10, caps=False):
        """Труба вздовж ламаної pts (кільця орієнтуються за дотичною)."""
        rings = []
        prev_n = None
        for i, p in enumerate(pts):
            p = Vector(p)
            a = Vector(pts[max(i - 1, 0)])
            b = Vector(pts[min(i + 1, len(pts) - 1)])
            t = (b - a).normalized()
            if prev_n is None:
                n = t.orthogonal().normalized()
            else:  # переносимо нормаль, щоб труба не перекручувалась
                n = (prev_n - t * prev_n.dot(t)).normalized()
            prev_n = n
            bn = t.cross(n)
            rings.append([self.bm.verts.new(p + (n * math.cos(2 * math.pi * k / segs)
                                                 + bn * math.sin(2 * math.pi * k / segs)) * r)
                          for k in range(segs)])
        mi = self._mi(mat)
        for r0, r1 in zip(rings, rings[1:]):
            for k in range(segs):
                f = self.bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
                f.material_index = mi
                f.smooth = True
        if caps:
            for ring in (rings[0], rings[-1][::-1]):
                f = self.bm.faces.new(ring[::-1])
                f.material_index = mi

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
    for order, (key, label, group) in enumerate(LAYERS):
        coll = bpy.data.collections.new(label)
        bpy.context.scene.collection.children.link(coll)
        LAYER_COLL[key] = coll
        ob = bpy.data.objects.new("LAYER_" + key, None)
        coll.objects.link(ob)
        ob.parent = root
        ob["layer"] = key
        ob["label"] = label
        ob["group"] = group
        ob["order"] = order  # glTF-експортер сортує вузли за іменем, тож порядок зберігаємо явно
        LAYER_OBJ[key] = ob


def rounded_path(pts, radius=0.4, n=6):
    """Ламана із заокругленими кутами (для повітроводів)."""
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        d1, d2 = (b - a), (c - b)
        r = min(radius, d1.length / 2, d2.length / 2)
        p0, p1 = b - d1.normalized() * r, b + d2.normalized() * r
        for i in range(n + 1):
            t = i / n
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1)
    out.append(pts[-1])
    return [tuple(p) for p in out]


def pallet(m, x, y, z=0.0, sx=1.2, sy=0.8):
    """Європалета: нижні дошки, бобишки, поперечки, верхній настил."""
    ys = (-sy / 2 + 0.05, 0.0, sy / 2 - 0.05)
    xs = (-sx / 2 + 0.07, 0.0, sx / 2 - 0.07)
    if sx < sy:  # палета повернута довгою стороною вздовж Y
        for xx in (-sx / 2 + 0.05, 0.0, sx / 2 - 0.05):
            m.box_lo(x + xx, y, z, 0.1, sy, 0.022, "pallet")
        for xx in (-sx / 2 + 0.05, 0.0, sx / 2 - 0.05):
            for yy in (-sy / 2 + 0.07, 0.0, sy / 2 - 0.07):
                m.box_lo(x + xx, y + yy, z + 0.022, 0.1, 0.14, 0.078, "pallet")
        for yy in (-sy / 2 + 0.07, 0.0, sy / 2 - 0.07):
            m.box_lo(x, y + yy, z + 0.1, sx, 0.14, 0.022, "pallet")
        for k in range(5):
            m.box_lo(x - sx / 2 + 0.05 + k * (sx - 0.1) / 4, y, z + 0.122, 0.1, sy, 0.022, "pallet")
        return
    for yy in ys:
        m.box_lo(x, y + yy, z, sx, 0.1, 0.022, "pallet")
    for xx in xs:
        for yy in ys:
            m.box_lo(x + xx, y + yy, z + 0.022, 0.14, 0.1, 0.078, "pallet")
    for xx in xs:
        m.box_lo(x + xx, y, z + 0.1, 0.14, sy, 0.022, "pallet")
    for k in range(5):
        m.box_lo(x, y - sy / 2 + 0.05 + k * (sy - 0.1) / 4, z + 0.122, sx, 0.1, 0.022, "pallet")


def cartons(m, x, y, z, sx, sy, layers, wrap=True):
    """Шари коробок 2×2 зі скотчем; за потреби — стрейч-плівка."""
    bx, by, bh = sx / 2 - 0.01, sy / 2 - 0.01, 0.4
    for k in range(layers):
        for i in (-1, 1):
            for j in (-1, 1):
                cx, cy, cz = x + i * sx / 4, y + j * sy / 4, z + k * (bh + 0.005)
                m.box_lo(cx, cy, cz, bx, by, bh, "carton", bev=0.008)
                m.box_lo(cx, cy, cz + bh, bx * 0.98, 0.05, 0.003, "tape")
    if wrap:
        m.box_lo(x, y, z - 0.01, sx + 0.03, sy + 0.03, layers * (bh + 0.005) + 0.02, "wrap")


def hazard(m, x0, x1, y, z, depth=0.02, h=0.06, along="X", w=0.12):
    """Жовто-чорна смуга безпеки."""
    n = max(1, int(abs(x1 - x0) / w))
    for i in range(n):
        c = x0 + (i + 0.5) * (x1 - x0) / n
        mat = "marking" if i % 2 == 0 else "hazard_black"
        if along == "X":
            m.box_lo(c, y, z, abs(x1 - x0) / n, depth, h, mat)
        else:
            m.box_lo(y, c, z, depth, abs(x1 - x0) / n, h, mat)


def estop(m, x, y, z):
    m.box_lo(x, y, z, 0.09, 0.09, 0.07, "marking", bev=0.01)
    m.cyl((x, y, z + 0.09), 0.035, 0.04, "estop", segs=14)


def console(m, x, y, z_top, facing=-90.0, w=0.62):
    """Пульт оператора на стійці: нахилена панель, екран, кнопка аварійної зупинки."""
    m.box_lo(x, y, 0, 0.22, 0.22, z_top - 0.05, "machine_mid", bev=0.02)
    m.box_lo(x, y, 0, 0.45, 0.45, 0.04, "machine_dark", bev=0.01)
    a = math.radians(facing)
    ox, oy = math.cos(a), math.sin(a)
    tilt = 25
    m.box((x, y, z_top + 0.12), (0.42, w, 0.07), "machine", rot=(0, -tilt, facing + 90), bev=0.015)
    m.box((x + ox * 0.03, y + oy * 0.03, z_top + 0.15), (0.3, w * 0.55, 0.02), "screen_on",
          rot=(0, -tilt, facing + 90))
    m.box((x + ox * 0.18, y + oy * 0.18, z_top + 0.33), (0.05, w * 0.9, 0.36), "machine_dark",
          rot=(0, 10, facing + 90), bev=0.01)
    m.box((x + ox * 0.205, y + oy * 0.205, z_top + 0.33), (0.01, w * 0.8, 0.3), "screen_on",
          rot=(0, 10, facing + 90))
    estop(m, x - oy * w * 0.38, y + ox * w * 0.38, z_top + 0.12)


def signal_tower(m, x, y, z):
    m.cyl((x, y, z + 0.02), 0.05, 0.04, "machine_dark", segs=14)
    m.cyl((x, y, z + 0.17), 0.012, 0.26, "alu", segs=8)
    for i, mat in enumerate(("lamp_off_g", "lamp_off_a", "lamp_off_r")):
        m.cyl((x, y, z + 0.34 + i * 0.075), 0.045, 0.07, mat, segs=16)
    m.cyl((x, y, z + 0.57), 0.045, 0.02, "machine_dark", segs=16)


def floor_frame(m, sx, sy, mat="marking", w=0.08):
    for (cx, cy, a, b) in ((0, -sy / 2, sx, w), (0, sy / 2, sx, w),
                           (-sx / 2, 0, w, sy), (sx / 2, 0, w, sy)):
        m.box((cx, cy, 0.022), (a, b, 0.02), mat)


def legs_frame(m, x, y, sx, sy, h, mat="machine_mid", t=0.06):
    for dx in (-sx / 2 + t, sx / 2 - t):
        for dy in (-sy / 2 + t, sy / 2 - t):
            m.box_lo(x + dx, y + dy, 0, t, t, h, mat)
            m.box_lo(x + dx, y + dy, 0, 0.12, 0.12, 0.02, "machine_dark")
    for dy in (-sy / 2 + t, sy / 2 - t):
        m.box_lo(x, y + dy, 0.15, sx - 2 * t, t * 0.8, t * 0.8, mat)


def roller_table(m, x, y, sx, sy, h, pitch=0.25, axis="Y"):
    legs_frame(m, x, y, sx, sy, h - 0.06)
    if axis == "Y":
        for dy in (-sy / 2, sy / 2):
            m.box_lo(x, y + dy, h - 0.1, sx, 0.05, 0.1, "alu", bev=0.006)
        n = int(sx / pitch)
        for i in range(n):
            m.cyl((x - sx / 2 + (i + 0.5) * sx / n, y, h - 0.03), 0.03, sy - 0.04, "galv",
                  axis="Y", segs=10)
    else:
        for dx in (-sx / 2, sx / 2):
            m.box_lo(x + dx, y, h - 0.1, 0.05, sy, 0.1, "alu", bev=0.006)
        n = int(sy / pitch)
        for i in range(n):
            m.cyl((x, y - sy / 2 + (i + 0.5) * sy / n, h - 0.03), 0.03, sx - 0.04, "galv",
                  axis="X", segs=10)


def shared(key, fn):
    """Меш, спільний для всіх об'єктів з тим самим ключем (у glTF зберігається один раз)."""
    me = MESHES.get(key)
    if me is None:
        m = Mesh()
        fn(m)
        me = bpy.data.meshes.new(key)
        m.bm.normal_update()
        m.bm.to_mesh(me)
        m.bm.free()
        for mt in m.mats:
            me.materials.append(MAT[mt])
        MESHES[key] = me
    return me


def instance(name, layer, me, parent=None, loc=(0, 0, 0), rz=0.0, **props):
    ob = bpy.data.objects.new(name, me)
    place(ob, layer, parent, loc, rz, props)
    return ob


def sheet_stack(m, x, y, z, n, decor, thick=0.016):
    """Стос плит на піддоні з прокладками; кожні 10 листів — тонка лінія для об'єму."""
    m.box_lo(x, y, z, 2.9, 2.15, 0.03, "pallet")
    for dx in (-1.2, -0.4, 0.4, 1.2):
        m.box_lo(x + dx, y, z + 0.03, 0.1, 2.15, 0.07, "pallet")
    if not n:
        return
    h = n * thick
    m.box_lo(x, y, z + 0.1, 2.8, 2.07, h, "decor%d" % decor)
    for k in range(1, int(n / 10) + 1):
        zz = z + 0.1 + k * 10 * thick
        if zz < z + 0.1 + h - 0.005:
            m.box((x, y - 1.036, zz), (2.8, 0.004, 0.004), "machine_dark")


def robot(m, x, y, rz=0.0, z=0.0, part=True):
    """Шестиосьовий промисловий робот у фіксованій позі (рука витягнута вздовж локальної X)."""
    a = math.radians(rz)
    ca, sa = math.cos(a), math.sin(a)

    def P(lx, ly, lz):
        return (x + lx * ca - ly * sa, y + lx * sa + ly * ca, z + lz)
    m.cyl(P(0, 0, 0.03), 0.42, 0.06, "machine_dark", segs=20)
    m.cyl(P(0, 0, 0.22), 0.34, 0.32, "robot", segs=24)
    m.box(P(0, 0, 0.55), (0.55, 0.5, 0.35), "robot", rot=(0, 0, rz), bev=0.06)
    m.cyl(P(0, 0, 0.75), 0.17, 0.62, "robot", segs=18, rot=(90, 0, rz))
    m.box(P(0.25, 0, 1.175), (0.24, 0.28, 1.0), "robot", rot=(0, 30.5, rz), bev=0.06)
    m.cyl(P(0.5, 0, 1.6), 0.14, 0.45, "robot", segs=18, rot=(90, 0, rz))
    m.box(P(0.95, 0, 1.525), (0.92, 0.2, 0.2), "robot", rot=(0, 9.5, rz), bev=0.05)
    m.box(P(0.42, 0, 1.78), (0.32, 0.24, 0.24), "machine_dark", rot=(0, 0, rz), bev=0.04)
    m.cyl(P(1.42, 0, 1.38), 0.07, 0.16, "robot", segs=14)
    m.cyl(P(1.42, 0, 1.28), 0.1, 0.04, "machine_dark", segs=16)
    m.box(P(1.42, 0, 1.24), (0.7, 0.45, 0.05), "alu", rot=(0, 0, rz), bev=0.01)
    for i in (-1, 1):
        for j in (-1, 1):
            m.cyl(P(1.42 + i * 0.25, j * 0.15, 1.2), 0.04, 0.04, "rubber", segs=10)
    if part:
        m.box(P(1.42, 0, 1.17), (0.9, 0.6, 0.016), "decor0", rot=(0, 0, rz))


def fence(m, pts, h=1.9, step=1.6):
    """Захисна огорожа: стійки + прозорі панелі вздовж ламаної."""
    for a, b in zip(pts, pts[1:]):
        a, b = Vector((*a, 0)), Vector((*b, 0))
        n = max(1, round((b - a).length / step))
        ang = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        for k in range(n + 1):
            p = a + (b - a) * (k / n)
            m.box_lo(p.x, p.y, 0, 0.06, 0.06, h, "marking")
        mid, ln = (a + b) / 2, (b - a).length
        m.box((mid.x, mid.y, 0.15 + (h - 0.3) / 2), (ln, 0.02, h - 0.3), "guard_glass", rz=ang)
        m.box((mid.x, mid.y, h - 0.03), (ln, 0.05, 0.05), "marking", rz=ang)


def cabinet(m, x, y, z, w=0.8, d=0.56, h=0.8, decor="decor0"):
    """Зібраний корпус шафи."""
    for dx in (-w / 2 + 0.009, w / 2 - 0.009):
        m.box_lo(x + dx, y, z, 0.018, d, h, decor)
    for zz in (z, z + h - 0.018):
        m.box_lo(x, y, zz, w, d, 0.018, decor)
    m.box_lo(x, y + d / 2 - 0.003, z, w, 0.004, h, "decor6")


def rack_cart(m, x, y, n=6):
    """Етажерка на колесах із фасадами на полицях."""
    for dx in (-0.6, 0.6):
        for dy in (-0.3, 0.3):
            m.box_lo(x + dx, y + dy, 0.1, 0.03, 0.03, 1.8, "steel")
            m.cyl((x + dx, y + dy, 0.05), 0.05, 0.04, "rubber", axis="X", segs=10)
    for k in range(n):
        z = 0.25 + k * 0.27
        m.box_lo(x, y, z, 1.2, 0.6, 0.02, "steel")
        m.box_lo(x, y, z + 0.02, 1.0, 0.5, 0.019, "decor5" if k % 2 else "phenolic")


def forklift(m):
    m.box_lo(0, 0, 0.15, 1.6, 1.05, 0.72, "forklift", bev=0.06)
    m.box_lo(-0.65, 0, 0.15, 0.42, 1.05, 0.95, "machine_dark", bev=0.08)  # противага
    for dx in (-0.55, 0.55):
        for dy in (-0.48, 0.48):
            m.cyl((dx, dy, 0.24), 0.24, 0.2, "rubber", axis="Y", segs=18)
            m.cyl((dx, dy * 1.02, 0.24), 0.12, 0.21, "steel", axis="Y", segs=12)
    for dx in (-0.5, 0.35):
        for dy in (-0.45, 0.45):
            m.box_lo(dx, dy, 0.87, 0.06, 0.06, 1.18, "machine_dark")
    m.box_lo(-0.07, 0, 2.05, 0.95, 1.0, 0.05, "machine_dark", bev=0.01)
    m.box_lo(-0.15, 0, 0.87, 0.45, 0.5, 0.12, "machine_dark", bev=0.04)  # сидіння
    m.box((-0.36, 0, 1.2), (0.08, 0.48, 0.5), "machine_dark", rot=(0, -12, 0), bev=0.03)
    m.cyl((0.22, 0, 1.25), 0.15, 0.03, "machine_dark", rot=(0, -40, 0), segs=16)  # кермо
    m.cyl((0.12, 0, 1.05), 0.025, 0.4, "machine_dark", rot=(0, -40, 0), segs=8)
    for dy in (-0.32, 0.32):
        m.box_lo(0.88, dy, 0.05, 0.08, 0.1, 2.4, "steel_dark", bev=0.01)  # щогла
    m.box_lo(0.88, 0, 2.3, 0.08, 0.74, 0.08, "steel_dark")
    m.box_lo(0.95, 0, 0.1, 0.06, 0.9, 0.5, "steel_dark")  # каретка
    for dy in (-0.25, 0.25):
        m.box_lo(1.5, dy, 0.1, 1.1, 0.12, 0.04, "steel_dark")
    m.cyl((-0.1, 0, 2.12), 0.06, 0.08, "status_amber", segs=12)  # маячок


def person(m, x, y, rz=0.0, vest="hivis", arms="front"):
    """Низькополігональна фігура оператора (зріст ~1,75 м)."""
    a = math.radians(rz)
    ca, sa = math.cos(a), math.sin(a)

    def P(lx, ly, z):
        return (x + lx * ca - ly * sa, y + lx * sa + ly * ca, z)
    for s in (-1, 1):
        m.box(P(0, s * 0.1, 0.43), (0.16, 0.15, 0.82), "trousers", rz=rz, bev=0.05)
        m.box(P(0.04, s * 0.1, 0.04), (0.27, 0.12, 0.08), "rubber", rz=rz, bev=0.03)
    m.box(P(0, 0, 1.13), (0.24, 0.42, 0.62), "shirt", rz=rz, bev=0.08)
    m.box(P(0, 0, 1.15), (0.27, 0.45, 0.46), vest, rz=rz, bev=0.08)
    for s in (-1, 1):
        if arms == "front":
            m.box(P(0.18, s * 0.26, 1.08), (0.48, 0.1, 0.1), "shirt", rot=(0, 35, rz), bev=0.04)
            m.sphere(P(0.38, s * 0.24, 0.94), 0.05, "skin", subdiv=1)
        else:
            m.box(P(0, s * 0.27, 1.08), (0.1, 0.1, 0.58), "shirt", rz=rz, bev=0.04)
            m.sphere(P(0, s * 0.27, 0.76), 0.05, "skin", subdiv=1)
    m.cyl(P(0, 0, 1.5), 0.05, 0.1, "skin", segs=10)
    m.sphere(P(0.01, 0, 1.64), 0.11, "skin", scale=(1.0, 0.9, 1.12))
    m.sphere(P(-0.01, 0, 1.69), 0.112, "hair", scale=(1.0, 0.92, 0.85))
    for s in (-1, 1):  # навушники
        m.cyl(P(0, s * 0.11, 1.64), 0.045, 0.04, "status_red", axis="Y", segs=12, rot=(90, 0, rz))
