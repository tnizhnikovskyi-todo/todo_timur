"""R-02, R-03: геометрія розкладки (чистий Python, без ORM; дзеркало — static/src/editor/geometry.js).

Одиниці — метри, кути — градуси проти годинникової стрілки при погляді зверху (DEC-15).
OBB — словник `{'cx', 'cy', 'a', 'b', 'rot'}`: центр, піврозміри вздовж локальних X і Y, кут повороту (°).
Варіант обладнання — словник у міліметрах (формат API-03 `catalog[].variants[]`):
`{length, width, height, service: {front, back, left, right}, front_side, anchor, utilities: [{kind, x_mm, y_mm, z_mm}]}`.
"""
import math

# Одиничні вектори фронту (R-02)
FRONT_VECTORS = {'s': (0.0, -1.0), 'n': (0.0, 1.0), 'e': (1.0, 0.0), 'w': (-1.0, 0.0)}


def make_obb(cx, cy, a, b, rot=0.0):
    return {'cx': float(cx), 'cy': float(cy), 'a': float(a), 'b': float(b), 'rot': float(rot)}


def rotate(x, y, deg):
    """Поворот вектора (x, y) на deg градусів проти годинникової стрілки."""
    if not deg:
        return x, y
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return x * c - y * s, x * s + y * c


def obb_axes(obb):
    rad = math.radians(obb['rot'])
    c, s = math.cos(rad), math.sin(rad)
    return (c, s), (-s, c)


def obb_corners(obb):
    """Чотири кути OBB в порядку обходу проти годинникової стрілки."""
    (ux, uy), (vx, vy) = obb_axes(obb)
    cx, cy, a, b = obb['cx'], obb['cy'], obb['a'], obb['b']
    return [
        (cx - a * ux - b * vx, cy - a * uy - b * vy),
        (cx + a * ux - b * vx, cy + a * uy - b * vy),
        (cx + a * ux + b * vx, cy + a * uy + b * vy),
        (cx - a * ux + b * vx, cy - a * uy + b * vy),
    ]


def obb_aabb(obb):
    """Описаний прямокутник вздовж осей: (xmin, ymin, xmax, ymax)."""
    corners = obb_corners(obb)
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return min(xs), min(ys), max(xs), max(ys)


def rect_obb(x0, y0, x1, y1):
    """Осьовий прямокутник (прохід, шлях евакуації) як OBB."""
    return make_obb((x0 + x1) / 2.0, (y0 + y1) / 2.0, (x1 - x0) / 2.0, (y1 - y0) / 2.0, 0.0)


def aabb_overlap(box_a, box_b, eps=0.0):
    return not (box_a[2] < box_b[0] - eps or box_b[2] < box_a[0] - eps
                or box_a[3] < box_b[1] - eps or box_b[3] < box_a[1] - eps)


def sat_penetration(obb_a, obb_b):
    """R-03: глибина проникнення = min по 4 осях (rA + rB − |d·u|). Від'ємна — OBB розділені.

    Перетин, якщо `sat_penetration > eps` (дотик по краю — не перетин).
    """
    (a1x, a1y), (a2x, a2y) = obb_axes(obb_a)
    (b1x, b1y), (b2x, b2y) = obb_axes(obb_b)
    dx, dy = obb_b['cx'] - obb_a['cx'], obb_b['cy'] - obb_a['cy']
    best = math.inf
    for ux, uy in ((a1x, a1y), (a2x, a2y), (b1x, b1y), (b2x, b2y)):
        r_a = obb_a['a'] * abs(ux * a1x + uy * a1y) + obb_a['b'] * abs(ux * a2x + uy * a2y)
        r_b = obb_b['a'] * abs(ux * b1x + uy * b1y) + obb_b['b'] * abs(ux * b2x + uy * b2y)
        depth = r_a + r_b - abs(dx * ux + dy * uy)
        if depth < best:
            best = depth
    return best


def _dist_point_segment(px, py, p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    vx, vy = x2 - x1, y2 - y1
    length2 = vx * vx + vy * vy
    if length2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * vx + (py - y1) * vy) / length2))
    return math.hypot(px - (x1 + t * vx), py - (y1 + t * vy))


def polygon_contains(poly, point, eps=0.001):
    """Алгоритм променя; точка на ребрі (у межах eps) вважається всередині."""
    px, py = point
    n = len(poly)
    for i in range(n):
        if _dist_point_segment(px, py, poly[i], poly[(i + 1) % n]) <= eps:
            return True
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _side(p, q1, q2):
    """Знакова відстань від точки p до прямої q1→q2 (метри)."""
    vx, vy = q2[0] - q1[0], q2[1] - q1[1]
    length = math.hypot(vx, vy)
    if length == 0:
        return 0.0
    return (vx * (p[1] - q1[1]) - vy * (p[0] - q1[0])) / length


def segments_cross(p1, p2, q1, q2, eps=0.001):
    """Відрізки перетинаються «по-справжньому» (дотик або збіг у межах eps — не перетин)."""
    d1, d2 = _side(p1, q1, q2), _side(p2, q1, q2)
    e1, e2 = _side(q1, p1, p2), _side(q2, p1, p2)
    if min(abs(d1), abs(d2), abs(e1), abs(e2)) <= eps:
        return False
    return d1 * d2 < 0 and e1 * e2 < 0


def obb_inside_polygon(obb, poly, eps=0.001):
    """Усі 4 кути OBB всередині полігона і жодне ребро OBB не перетинає ребро полігона."""
    corners = obb_corners(obb)
    if not all(polygon_contains(poly, c, eps) for c in corners):
        return False
    n = len(poly)
    for i in range(4):
        c1, c2 = corners[i], corners[(i + 1) % 4]
        for j in range(n):
            if segments_cross(c1, c2, poly[j], poly[(j + 1) % n], eps):
                return False
    return True


def rect_polygon(length, width):
    """Габарит будівлі [0, L] × [0, W] як полігон."""
    return [(0.0, 0.0), (length, 0.0), (length, width), (0.0, width)]


# --- R-02: габарит, зона обслуговування, точки підключення ---------------------------------------------

def _front_frame(variant):
    """(f, r, h_f, h_l, a, b): фронт, «праворуч», півдовжини вздовж фронту й вздовж −r, піврозміри."""
    a = variant['length'] / 2000.0
    b = variant['width'] / 2000.0
    fx, fy = FRONT_VECTORS.get(variant.get('front_side') or 's', FRONT_VECTORS['s'])
    rx, ry = -fy, fx
    if fx == 0:  # фронт уздовж Y: вздовж фронту — ширина, вздовж −r (вісь X) — довжина
        h_f, h_l = b, a
    else:
        h_f, h_l = a, b
    return (fx, fy), (rx, ry), h_f, h_l, a, b


def anchor_offset(variant):
    """Зсув центру габариту відносно точки прив'язки при θ=0: o = C − P."""
    (fx, fy), (rx, ry), h_f, h_l, _a, _b = _front_frame(variant)
    anchor = variant.get('anchor') or 'center'
    if anchor == 'front':
        return -fx * h_f, -fy * h_f
    if anchor == 'back':
        return fx * h_f, fy * h_f
    if anchor == 'corner':
        return -fx * h_f + rx * h_l, -fy * h_f + ry * h_l
    return 0.0, 0.0


def placement_obb(variant, x, y, rotation):
    """OBB габариту розміщення (R-02 п. 1-2)."""
    ox, oy = anchor_offset(variant)
    wx, wy = rotate(ox, oy, rotation)
    return make_obb(x + wx, y + wy, variant['length'] / 2000.0, variant['width'] / 2000.0, rotation)


def service_total(variant):
    service = variant.get('service') or {}
    return sum(max(0, service.get(k) or 0) for k in ('front', 'back', 'left', 'right'))


def service_obb(variant, x, y, rotation):
    """OBB зони обслуговування (R-02 п. 3); None, якщо сервісу немає."""
    if service_total(variant) <= 0:
        return None
    service = variant.get('service') or {}
    (fx, fy), (rx, ry), _h_f, _h_l, a, b = _front_frame(variant)
    ext = {'+x': 0.0, '-x': 0.0, '+y': 0.0, '-y': 0.0}

    def add(vec, value):
        vx, vy = vec
        if vx > 0:
            ext['+x'] += value
        elif vx < 0:
            ext['-x'] += value
        elif vy > 0:
            ext['+y'] += value
        else:
            ext['-y'] += value

    add((fx, fy), (service.get('front') or 0) / 1000.0)
    add((-fx, -fy), (service.get('back') or 0) / 1000.0)
    add((rx, ry), (service.get('right') or 0) / 1000.0)
    add((-rx, -ry), (service.get('left') or 0) / 1000.0)
    body = placement_obb(variant, x, y, rotation)
    lx, ly = (ext['+x'] - ext['-x']) / 2.0, (ext['+y'] - ext['-y']) / 2.0
    wx, wy = rotate(lx, ly, rotation)
    return make_obb(
        body['cx'] + wx, body['cy'] + wy, a + (ext['+x'] + ext['-x']) / 2.0, b + (ext['+y'] + ext['-y']) / 2.0, rotation)


def utility_points(variant, x, y, rotation):
    """R-02 п. 4: світові координати точок підключення варіанта: [(kind, x, y)]."""
    body = placement_obb(variant, x, y, rotation)
    out = []
    for util in variant.get('utilities') or []:
        wx, wy = rotate((util.get('x_mm') or 0) / 1000.0, (util.get('y_mm') or 0) / 1000.0, rotation)
        out.append((util.get('kind'), body['cx'] + wx, body['cy'] + wy))
    return out
