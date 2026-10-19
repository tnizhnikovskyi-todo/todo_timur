"""Перевірки будівлі: inside, aisle_width, height (F18-08, N-07; MERGE.md §2.4 O-08); реєструються в CHECKS.

Дзеркало — `core/constructor/building_core.js`; еталон — `static/tests/fixtures/s5_golden.json` (тест `test_s5_checks`).

* `inside` — місця й обладнання шарів зі списку `INSIDE_KINDS` лежать усередині контуру будівлі (`bounds` шару
  `building`, інакше габарит площадки) і не перетинають колони, стіни, офіс, зарядку техніки (ворота, док, двері —
  прорізи) та колони сітки `site.column_grid` (0,4 × 0,4 м у вузлах, як бачить авторозкладка; `grid_nodes`).
* `aisle_width` — мінімальна ширина за технікою (`site.aisle_tech`, `slot.tech` зони; N-06): проходи шарів (`aisles`,
  ширина = менша сторона) і проїзди між рядами стелажів (зазор між лицьовими сторонами; зазор до 0,6 м — «спина до
  спини», не проїзд).
* `height` — верх складування не вище стелі будівлі й не ближче 0,5 м до спринклерів (`site.sprinkler_height`, 0 —
  немає).
"""

import math

from . import geometry as geo
from .building import (
    ANGLE_TOLERANCE_DEG,
    GRID_COLUMN_HALF,
    INSIDE_KINDS,
    MAX_NEED_M,
    MIN_FACE_OVERLAP_M,
    OBSTACLE_ACCUSATIVE,
    OBSTACLE_KINDS,
    ROW_TEMPLATES,
    SPACER_M,
    SPRINKLER_CLEARANCE_M,
    building_items,
    contour_polygon,
    grid_nodes,
    item_obb,
    slot_height,
    tech_at,
    tech_label,
    tech_min,
)
from .registry import CHECKS


def _issue(check, severity, layer_id, codes, message):
    return {'check': check, 'severity': severity, 'layer_id': layer_id, 'codes': list(codes), 'message': message}


def _layer(scene, layer_id):
    return scene.layers.get(layer_id) or {}


# --- inside ------------------------------------------------------------------------------------------------------


def check_inside(scene, config, eps):
    sev = config['mode']
    contour = contour_polygon(scene)
    items = [item for item in building_items(scene) if item.get('kind') in OBSTACLE_KINDS]
    obstacles = [
        (
            item_obb(item),
            geo.obb_aabb(item_obb(item)),
            OBSTACLE_ACCUSATIVE[item['kind']] + (" «%s»" % item['name'] if item.get('name') else ""),
        )
        for item in items
    ]
    # колони сітки `site.column_grid` — ті самі вузли, що бачить авторозкладка (`obstacleRects`); не items, тож окремо
    grid = {'building': scene.building, 'column_grid': (scene._state.get('site') or {}).get('column_grid')}
    for x, y in grid_nodes(grid, [item for item in items if item['kind'] == 'column']):
        obb = geo.make_obb(x, y, GRID_COLUMN_HALF, GRID_COLUMN_HALF, 0.0)
        what = "%s сітки (%s; %s)" % (OBSTACLE_ACCUSATIVE['column'], _fix2(x), _fix2(y))
        obstacles.append((obb, geo.obb_aabb(obb), what))
    issues = []
    for obj in scene.objects():
        layer = _layer(scene, obj['layer_id'])
        if layer.get('kind') not in INSIDE_KINDS:
            continue
        if len(contour) >= 3 and not geo.obb_inside_polygon(obj['obb'], contour, eps):
            issues.append(
                _issue('inside', sev, obj['layer_id'], [obj['code']], "%s: поза контуром будівлі" % obj['code'])
            )
        box = geo.obb_aabb(obj['obb'])
        for obb, item_box, what in obstacles:
            if geo.aabb_overlap(box, item_box, eps) and geo.sat_penetration(obj['obb'], obb) > eps:
                issues.append(
                    _issue('inside', sev, obj['layer_id'], [obj['code']], "%s: перетинає %s" % (obj['code'], what))
                )
    return issues


# --- aisle_width -------------------------------------------------------------------------------------------------


def _fix2(value):
    return '%.2f' % value


def _row_gap(ra, rb, group, eps):
    """Проїзд між лицьовими сторонами рядів `ra`, `rb` шару `group`: (зазор, середина проїзду) або None."""
    a, b = ra['obb'], rb['obb']
    rel = (a['rot'] - b['rot']) % 180.0
    if min(rel, 180.0 - rel) > ANGLE_TOLERANCE_DEG:
        return None
    if (
        math.hypot(b['cx'] - a['cx'], b['cy'] - a['cy'])
        > math.hypot(a['a'], a['b']) + math.hypot(b['a'], b['b']) + MAX_NEED_M
    ):
        return None
    dx, dy = geo.rotate(b['cx'] - a['cx'], b['cy'] - a['cy'], -a['rot'])
    x_lo, x_hi = max(-a['a'], dx - b['a']), min(a['a'], dx + b['a'])
    if x_hi - x_lo < MIN_FACE_OVERLAP_M:
        return None
    gap = abs(dy) - (a['b'] + b['b'])
    if gap < SPACER_M:
        return None
    sign = 1.0 if dy > 0 else -1.0
    y_lo, y_hi = sorted((sign * a['b'], dy - sign * b['b']))
    for other in (o['obb'] for o in group if o is not ra and o is not rb):  # між рядами щось стоїть — не проїзд
        pts = [geo.rotate(px - a['cx'], py - a['cy'], -a['rot']) for px, py in geo.obb_corners(other)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if min(max(xs), x_hi) - max(min(xs), x_lo) > eps and min(max(ys), y_hi) - max(min(ys), y_lo) > eps:
            return None
    mid = geo.rotate((x_lo + x_hi) / 2.0, (y_lo + y_hi) / 2.0, a['rot'])
    return gap, (a['cx'] + mid[0], a['cy'] + mid[1])


def check_aisle_width(scene, config, eps):
    sev = config['mode']
    issues = []
    for layer in scene.layers.values():
        for aisle in layer.get('aisles') or []:
            width = min(aisle['x1'] - aisle['x0'], aisle['y1'] - aisle['y0'])
            raw = tech_at(scene, (aisle['x0'] + aisle['x1']) / 2.0, (aisle['y0'] + aisle['y1']) / 2.0)
            need = tech_min(raw)
            if need is not None and width < need - eps:
                name = aisle.get('name') or aisle['id']
                issues.append(
                    _issue(
                        'aisle_width',
                        sev,
                        layer['id'],
                        [name],
                        "Прохід «%s»: ширина %s м, потрібно ≥ %s м (%s)"
                        % (name, _fix2(width), _fix2(need), tech_label(raw)),
                    )
                )
    by_layer = {}
    for obj in scene.objects():
        by_layer.setdefault(obj['layer_id'], []).append(obj)
    for layer_id, group in by_layer.items():
        rows = [o for o in group if o['kind'] == 'slot' and scene.slots[o['id']]['template'] in ROW_TEMPLATES]
        for i, ra in enumerate(rows):
            for rb in rows[i + 1 :]:
                found = _row_gap(ra, rb, group, eps)
                if found is None:
                    continue
                gap, (mx, my) = found
                raw = tech_at(scene, mx, my)
                need = tech_min(raw)
                if need is None or gap >= need - eps:
                    continue
                x, y = sorted([ra['code'], rb['code']])
                issues.append(
                    _issue(
                        'aisle_width',
                        sev,
                        layer_id,
                        [x, y],
                        "Вузький проїзд між рядами %s і %s: %s м, потрібно ≥ %s м (%s)"
                        % (x, y, _fix2(gap), _fix2(need), tech_label(raw)),
                    )
                )
    return issues


# --- height ------------------------------------------------------------------------------------------------------


def check_height(scene, config, eps):
    sev = config['mode']
    ceiling = scene.building.get('height') or 0.0
    sprinkler = (scene._state.get('site') or {}).get('sprinkler_height') or 0.0
    issues = []

    def verify(layer_id, code, top):
        if ceiling > 0 and top > ceiling + eps:
            issues.append(
                _issue(
                    'height',
                    sev,
                    layer_id,
                    [code],
                    "%s: висота %s м перевищує стелю будівлі %s м" % (code, _fix2(top), _fix2(ceiling)),
                )
            )
        elif sprinkler > 0 and top > sprinkler - SPRINKLER_CLEARANCE_M + eps:
            issues.append(
                _issue(
                    'height',
                    sev,
                    layer_id,
                    [code],
                    "%s: верх %s м ближче %s м до спринклерів (%s м)"
                    % (code, _fix2(top), _fix2(SPRINKLER_CLEARANCE_M), _fix2(sprinkler)),
                )
            )

    for slot in scene.slots.values():
        layer = _layer(scene, slot['layer_id'])
        if slot['template'] == 'zone' or layer.get('kind') not in INSIDE_KINDS:
            continue
        verify(
            slot['layer_id'],
            slot['code_prefix'],
            (layer.get('elevation') or 0.0) + slot_height(slot['template'], slot.get('params')),
        )
    for placement in scene.placements:
        layer = _layer(scene, placement['layer_id'])
        if placement['id'] in scene.dynamic or layer.get('kind') not in INSIDE_KINDS:
            continue
        height = (scene.variants[placement['variant_id']].get('height') or 0.0) / 1000.0
        if math.isfinite(height):
            verify(placement['layer_id'], placement['code'], (layer.get('elevation') or 0.0) + height)
    return issues


CHECKS.register('inside', check_inside, sequence=100)
CHECKS.register('aisle_width', check_aisle_width, sequence=110)
CHECKS.register('height', check_height, sequence=120)
