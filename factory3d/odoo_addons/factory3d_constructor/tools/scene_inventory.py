#!/usr/bin/env python3
"""Інвентар 3D-моделі переглядача: усі шари та всі кодовані вузли (extras.code) з реальними габаритами й позиціями.

Джерело: `factory3d_viewer/static/model/parts/{core,engineering,fire,it,site}.glb` + `manifest.json`.
Результат: `data/scene_inventory.json` (компактний; `objects` — словник `{код: {x, y, z, L, W, H, yaw, kind, layer, …}}`) і підсумок (кількість за шарами/видами) у stdout.

Алгоритм: розбираємо GLB (JSON- і BIN-чанки), обходимо ієрархію вузлів із TRS/matrix, для кожного вузла з
`extras.code` рахуємо світовий AABB усіх мешів його піддерева. Координати glTF — «three» (x, z, -y), тож
план (x вздовж, y впоперек, z вгору) = (X, -Z, Y). AABB береться з accessor.min/max (POSITION), якщо їх нема —
з вершин у BIN-чанку. `x, y` — центр AABB, `z` — низ (основа), `l, w, h` — розміри; якщо вузол повернутий
навколо вертикалі — `yaw` (град., проти годинникової у плані) і `l, w` вже у власній (повернутій) системі.

Запуск:  python3 factory3d/odoo_addons/factory3d_constructor/tools/scene_inventory.py [--check]
Лише stdlib. Результат детермінований.
"""

import collections
import json
import math
import struct
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
FACTORY3D = MODULE.parents[1]
PARTS = FACTORY3D / 'odoo_addons' / 'factory3d_viewer' / 'static' / 'model' / 'parts'
OUT = MODULE / 'data' / 'scene_inventory.json'
PART_FILES = ('core', 'engineering', 'fire', 'it', 'site')
EXTRA_KEYS = ('maker', 'model', 'status', 'state', 'rect', 'role')

_JSON, _BIN = 0x4E4F534A, 0x004E4942
_COMP = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
_NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def load_glb(path):
    data = Path(path).read_bytes()
    magic, _ver, length = struct.unpack('<4sII', data[:12])
    if magic != b'glTF':
        raise ValueError(f'{path}: не GLB')
    off, js, binc = 12, None, b''
    while off < length:
        clen, ctype = struct.unpack('<II', data[off : off + 8])
        chunk = data[off + 8 : off + 8 + clen]
        off += 8 + clen
        if ctype == _JSON:
            js = json.loads(chunk.decode('utf-8'))
        elif ctype == _BIN:
            binc = chunk
    return js, binc


# --- матриці 4×4 (рядки; column-vector: p' = M·p), без залежностей ------------------------------------------
def mat_identity():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def node_local(node):
    if 'matrix' in node:  # glTF: column-major
        m = node['matrix']
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get('translation', (0, 0, 0))
    qx, qy, qz, qw = node.get('rotation', (0, 0, 0, 1))
    sx, sy, sz = node.get('scale', (1, 1, 1))
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    r = [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]
    return [
        [r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx],
        [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
        [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def apply(m, p):
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3))


def to_plant(p):
    """three (X, Y, Z) → план (x вздовж, y впоперек, z вгору)."""
    return (p[0], -p[2], p[1])


# --- геометрія -------------------------------------------------------------------------------------------
_NORM = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}


def _denorm(acc, vals):
    """KHR_mesh_quantization: normalized-цілі → float (signed: max(v/MAX, -1))."""
    if not acc.get('normalized'):
        return list(vals)
    div = _NORM[acc['componentType']]
    signed = acc['componentType'] in (5120, 5122)
    return [max(v / div, -1.0) if signed else v / div for v in vals]


def accessor_bounds(js, binc, idx):
    """(min, max) POSITION-акcесора: з полів min/max, інакше з вершин у BIN."""
    acc = js['accessors'][idx]
    if 'min' in acc and 'max' in acc:
        return _denorm(acc, acc['min'][:3]), _denorm(acc, acc['max'][:3])
    bv = js['bufferViews'][acc['bufferView']]
    fmt, size = _COMP[acc['componentType']]
    nc = _NCOMP[acc['type']]
    stride = bv.get('byteStride') or size * nc
    base = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
    mn, mx = [math.inf] * 3, [-math.inf] * 3
    for i in range(acc['count']):
        v = _denorm(acc, struct.unpack_from('<' + fmt * nc, binc, base + i * stride))
        for k in range(3):
            mn[k] = min(mn[k], v[k])
            mx[k] = max(mx[k], v[k])
    return mn, mx


def corners(mn, mx):
    return [(x, y, z) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]


def walk(js, binc, part):
    """Повертає (шари, вузли-із-кодом). Кожен вузол — dict із world-кутами (план) усіх мешів піддерева."""
    nodes = js['nodes']
    meshes = js.get('meshes', [])
    mesh_bounds = {}
    for mi, mesh in enumerate(meshes):
        bl = []
        for prim in mesh.get('primitives', []):
            pos = prim.get('attributes', {}).get('POSITION')
            if pos is not None:
                bl.append(accessor_bounds(js, binc, pos))
        mesh_bounds[mi] = bl

    layers, coded = {}, []

    def visit(idx, parent_m, layer, coded_parent):
        node = nodes[idx]
        m = mat_mul(parent_m, node_local(node))
        ex = node.get('extras') or {}
        name = node.get('name', '')
        if name.startswith('LAYER_') or 'layer' in ex:
            layer = ex.get('layer') or name[len('LAYER_') :]
            layers[layer] = {k: ex.get(k) for k in ('label', 'group', 'order')}
        rec = None
        if 'code' in ex:
            rec = {
                'idx': idx, 'name': name, 'ex': ex, 'layer': layer, 'part': part, 'parent': coded_parent,
                'has_rot': 'rotation' in node or 'matrix' in node, 'pts': [], 'm': m,
            }
            coded.append(rec)
        own = []
        if 'mesh' in node:
            for mn, mx in mesh_bounds.get(node['mesh'], []):
                own.extend(to_plant(apply(m, c)) for c in corners(mn, mx))
        for child in node.get('children', []):
            own.extend(visit(child, m, layer, ex['code'] if 'code' in ex else coded_parent))
        if rec is not None:
            rec['pts'] = own
        return own

    for root in js['scenes'][js.get('scene', 0)]['nodes']:
        visit(root, mat_identity(), None, None)
    return layers, coded


def world_yaw(m):
    """Кут навколо вертикалі (град., проти годинникової у плані) зі світової матриці (напрям локальної осі X)."""
    vx = (m[0][0], m[1][0], m[2][0])  # three
    px, py = vx[0], -vx[2]  # план
    if math.hypot(px, py) < 1e-9:
        return 0.0
    yaw = math.degrees(math.atan2(py, px))
    return 0.0 if abs(yaw) < 1e-4 else round(yaw % 360.0 if yaw < 0 else yaw, 3)


def build_object(rec, layer_meta):
    pts = rec['pts'] or [to_plant(apply(rec['m'], (0.0, 0.0, 0.0)))]  # вузол без мешу (порожня полиця) — точка
    yaw = world_yaw(rec['m']) if rec['has_rot'] else 0.0
    cx0 = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    cy0 = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    if yaw:
        c, s = math.cos(math.radians(-yaw)), math.sin(math.radians(-yaw))
        pts = [((p[0] - cx0) * c - (p[1] - cy0) * s, (p[0] - cx0) * s + (p[1] - cy0) * c, p[2]) for p in pts]
        ox, oy = 0.0, 0.0
    else:
        ox, oy = cx0, cy0
        pts = [(p[0] - cx0, p[1] - cy0, p[2]) for p in pts]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
    lx, ly = (x0 + x1) / 2, (y0 + y1) / 2  # зсув центра у власній системі
    if yaw:
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        cx, cy = cx0 + lx * c - ly * s, cy0 + lx * s + ly * c
    else:
        cx, cy = ox + lx, oy + ly
    ex = rec['ex']
    lm = layer_meta.get(rec['layer'], {})
    obj = {
        'code': ex['code'],  # лише для обробки; у файлі — ключ словника
        'kind': ex.get('kind'),
        'label': ex.get('label') or rec['name'] or ex['code'],
        'layer': rec['layer'],
        'group': lm.get('group'),
        'part': rec['part'],
        'x': round(cx, 3), 'y': round(cy, 3), 'z': round(z0, 3),
        'L': round(x1 - x0, 3), 'W': round(y1 - y0, 3), 'H': round(z1 - z0, 3),
        'yaw': yaw or 0,
    }
    if rec['parent']:
        obj['parent'] = rec['parent']
    if rec['name'] and rec['name'] != ex['code']:
        obj['name'] = rec['name']
    for k in EXTRA_KEYS:
        if ex.get(k) not in (None, ''):
            obj[k] = ex[k]
    if ex.get('desc'):
        obj['desc'] = ex['desc']
    return obj


def build():
    manifest = json.loads((PARTS / 'manifest.json').read_text(encoding='utf-8'))
    layer_meta = {l['key']: {k: l[k] for k in ('label', 'group', 'order')} for l in manifest['layers']}
    all_layers, recs = {}, []
    for part in PART_FILES:
        js, binc = load_glb(PARTS / f'{part}.glb')
        layers, coded = walk(js, binc, part)
        for key, meta in layers.items():
            all_layers.setdefault(key, dict(meta, part=part))
        recs.extend(coded)
    for key, meta in layer_meta.items():  # manifest — істина для підписів/груп/порядку
        all_layers.setdefault(key, dict(meta))
        all_layers[key].update(meta)
    objects, skipped = [], []
    for rec in recs:
        obj = build_object(rec, all_layers)
        (objects if obj else skipped).append(obj or rec['ex']['code'])
    objects.sort(key=lambda o: (all_layers.get(o['layer'], {}).get('order', 99), o['code']))
    # висоти шарів: [мін. z, макс. z верху] за його об'єктами — підказка для elevation
    for key, meta in all_layers.items():
        zs = [(o['z'], o['z'] + o['H']) for o in objects if o['layer'] == key]
        meta['zmin'] = round(min(z[0] for z in zs), 3) if zs else 0
        meta['zmax'] = round(max(z[1] for z in zs), 3) if zs else 0
        meta['n'] = len(zs)
    layers = sorted(({'key': k, **v} for k, v in all_layers.items()), key=lambda l: l['order'])
    data = {
        'version': 1,
        'source': 'factory3d_viewer/static/model/parts/*.glb',
        'dims': manifest.get('dims'),
        'coords': 'plant: x вздовж, y впоперек, z вгору (м); x,y — ЦЕНТР світового AABB об\'єкта (не якір/початок вузла), '
                  'z — низ; L,W,H — розміри (L вздовж власної осі X до повороту, W — вздовж Y, H — висота); '
                  'yaw — поворот навколо вертикалі, град. проти годинникової у плані (0, якщо вузол не повернутий). '
                  'Сід розміщень/місць використовує ту саму конвенцію: x,y розміщення = x,y тут, rotation = yaw, якір center.',
        'layers': layers,
        'objects': objects,
    }
    return data, skipped


def dump(data):
    """Компактний JSON: один об'єкт на рядок."""
    lines = ['{']
    for key in ('version', 'source', 'dims', 'coords'):
        lines.append(f'"{key}":{json.dumps(data[key], ensure_ascii=False)},')
    lines.append('"layers":[')
    lines.append(',\n'.join(json.dumps(l, ensure_ascii=False, separators=(',', ':')) for l in data['layers']))
    lines.append('],')
    lines.append('"objects":{')  # {код: {kind, label, layer, group, part, x, y, z, L, W, H, yaw, …}}
    lines.append(',\n'.join(
        json.dumps(o['code'], ensure_ascii=False) + ':' + json.dumps({k: v for k, v in o.items() if k != 'code'}, ensure_ascii=False, separators=(',', ':'))
        for o in data['objects']))
    lines.append('}')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def summary(data, skipped):
    by_layer = collections.Counter(o['layer'] for o in data['objects'])
    by_kind = collections.Counter(o['kind'] for o in data['objects'])
    print(f"layers={len(data['layers'])} objects={len(data['objects'])} empty={len(skipped)}")
    for l in data['layers']:
        kinds = collections.Counter(o['kind'] for o in data['objects'] if o['layer'] == l['key'])
        print(f"  {l['order']:>2} {l['key']:<12} {l['group']:<22} n={by_layer[l['key']]:<4} "
              f"z[{l['zmin']}..{l['zmax']}] {dict(kinds)}")
    print('kinds:', dict(by_kind))
    nolayer = [o['code'] for o in data['objects'] if not o['layer']]
    if nolayer:
        print('WARNING без шару:', nolayer[:10])


def main(argv):
    data, skipped = build()
    summary(data, skipped)
    if skipped:
        print('без геометрії:', skipped[:20])
    if '--check' not in argv:
        OUT.write_text(dump(data), encoding='utf-8')
        print('written', OUT, OUT.stat().st_size, 'bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
