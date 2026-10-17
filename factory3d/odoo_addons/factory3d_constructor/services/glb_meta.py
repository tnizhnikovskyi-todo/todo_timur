"""R-19: метадані GLB без сторонніх бібліотек: кількість трикутників і габарит (bbox) за JSON-чанком glTF 2.0."""
import json
import math
import struct

GLB_MAGIC = 0x46546C67      # 'glTF'
CHUNK_JSON = 0x4E4F534A     # 'JSON'
MAX_NODE_DEPTH = 64
IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


class GlbError(ValueError):
    """Файл не є коректним GLB 2.0 (код API-09: bad_glb)."""


def _mat_mul(a, b):
    """Добуток 4×4 матриць у column-major (як у glTF): a · b."""
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return tuple(out)


def _trs_matrix(node):
    if node.get('matrix'):
        matrix = node['matrix']
        if len(matrix) != 16:
            raise GlbError("Некоректна матриця вузла.")
        return tuple(float(v) for v in matrix)
    tx, ty, tz = node.get('translation') or (0.0, 0.0, 0.0)
    qx, qy, qz, qw = node.get('rotation') or (0.0, 0.0, 0.0, 1.0)
    sx, sy, sz = node.get('scale') or (1.0, 1.0, 1.0)
    norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    qx, qy, qz, qw = qx / norm, qy / norm, qz / norm, qw / norm
    r00 = 1 - 2 * (qy * qy + qz * qz)
    r01 = 2 * (qx * qy - qz * qw)
    r02 = 2 * (qx * qz + qy * qw)
    r10 = 2 * (qx * qy + qz * qw)
    r11 = 1 - 2 * (qx * qx + qz * qz)
    r12 = 2 * (qy * qz - qx * qw)
    r20 = 2 * (qx * qz - qy * qw)
    r21 = 2 * (qy * qz + qx * qw)
    r22 = 1 - 2 * (qx * qx + qy * qy)
    return (r00 * sx, r10 * sx, r20 * sx, 0.0,
            r01 * sy, r11 * sy, r21 * sy, 0.0,
            r02 * sz, r12 * sz, r22 * sz, 0.0,
            tx, ty, tz, 1.0)


def _transform(matrix, point):
    x, y, z = point
    return (matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
            matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
            matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14])


def parse_gltf_json(data):
    """JSON-чанк GLB → словник glTF; кидає GlbError."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 20:
        raise GlbError("Файл не є GLB: закороткий.")
    magic, version, length = struct.unpack_from('<III', data, 0)
    if magic != GLB_MAGIC:
        raise GlbError("Файл не є GLB: немає сигнатури glTF.")
    if version != 2:
        raise GlbError("Підтримується лише glTF 2.0.")
    if length > len(data):
        raise GlbError("GLB пошкоджено: довжина в заголовку більша за файл.")
    chunk_len, chunk_type = struct.unpack_from('<II', data, 12)
    if chunk_type != CHUNK_JSON or 20 + chunk_len > len(data):
        raise GlbError("GLB пошкоджено: немає JSON-чанка.")
    try:
        return json.loads(bytes(data[20:20 + chunk_len]).decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise GlbError("GLB пошкоджено: некоректний JSON (%s)." % exc) from None


def _primitive_triangles(gltf, primitive):
    accessors = gltf.get('accessors') or []
    mode = primitive.get('mode', 4)
    try:
        if 'indices' in primitive:
            count = accessors[primitive['indices']]['count']
        else:
            count = accessors[primitive['attributes']['POSITION']]['count']
    except (IndexError, KeyError, TypeError):
        raise GlbError("GLB пошкоджено: некоректний примітив.") from None
    if mode == 4:
        return count // 3
    if mode in (5, 6):
        return max(0, count - 2)
    return 0  # точки й лінії не дають трикутників


def _primitive_box(gltf, primitive):
    try:
        acc = (gltf.get('accessors') or [])[primitive['attributes']['POSITION']]
        lo, hi = acc['min'], acc['max']
    except (IndexError, KeyError, TypeError):
        raise GlbError("GLB: у POSITION немає min/max.") from None
    if len(lo) < 3 or len(hi) < 3:
        raise GlbError("GLB: некоректні min/max у POSITION.")
    return lo[:3], hi[:3]


def glb_meta(data):
    """`{triangles, bbox_m: [x, y, z], size_mm: {x, y, z}}`; помилки розбору → GlbError."""
    gltf = parse_gltf_json(data)
    nodes = gltf.get('nodes') or []
    meshes = gltf.get('meshes') or []
    if not meshes:
        raise GlbError("GLB не містить геометрії.")
    scenes = gltf.get('scenes') or []
    if scenes:
        scene = scenes[gltf.get('scene', 0)] if gltf.get('scene', 0) < len(scenes) else scenes[0]
        roots = scene.get('nodes') or []
    else:
        children = {c for n in nodes for c in n.get('children') or []}
        roots = [i for i in range(len(nodes)) if i not in children]
    state = {'triangles': 0, 'lo': [math.inf] * 3, 'hi': [-math.inf] * 3}

    def visit(index, parent, depth):
        if depth > MAX_NODE_DEPTH:
            raise GlbError("GLB: надто глибока ієрархія вузлів.")
        try:
            node = nodes[index]
        except (IndexError, TypeError):
            raise GlbError("GLB пошкоджено: некоректний вузол.") from None
        world = _mat_mul(parent, _trs_matrix(node))
        if 'mesh' in node:
            try:
                mesh = meshes[node['mesh']]
            except (IndexError, TypeError):
                raise GlbError("GLB пошкоджено: некоректний меш.") from None
            for primitive in mesh.get('primitives') or []:
                state['triangles'] += _primitive_triangles(gltf, primitive)
                lo, hi = _primitive_box(gltf, primitive)
                for x in (lo[0], hi[0]):
                    for y in (lo[1], hi[1]):
                        for z in (lo[2], hi[2]):
                            point = _transform(world, (x, y, z))
                            for axis in range(3):
                                state['lo'][axis] = min(state['lo'][axis], point[axis])
                                state['hi'][axis] = max(state['hi'][axis], point[axis])
        for child in node.get('children') or []:
            visit(child, world, depth + 1)

    for root in roots:
        visit(root, IDENTITY, 0)
    if not all(math.isfinite(v) for v in state['lo'] + state['hi']):
        raise GlbError("GLB не містить геометрії.")
    size = [state['hi'][axis] - state['lo'][axis] for axis in range(3)]
    return {
        'triangles': state['triangles'],
        'bbox_m': [round(v, 6) for v in size],
        'size_mm': {'x': round(size[0] * 1000), 'y': round(size[1] * 1000), 'z': round(size[2] * 1000)},
    }
