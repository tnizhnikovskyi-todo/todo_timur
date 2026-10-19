"""Будівля: контур, колони, стіни, проходи, техніка складу (F18, N-06; MERGE.md §2.8 O-05).

Чистий Python без ORM (дзеркало — `core/constructor/building_core.js`; золоті фікстури
`static/tests/fixtures/s5_golden.json`).

* Об'єкти будівлі шару `kind=building` — Json `layer.items` (R-22): `{id, kind, name, x, y, w, d, rot, [th],
  location_uid, [h]}`. Усі об'єкти — прямокутники (OBB): центр `(x, y)`, довжина `w` уздовж осі `rot` (°), глибина `d`;
  стіна — відрізок довжиною `w` і товщиною `th` (= `d`) під будь-яким кутом (Q10). `location_uid` мають лише ворота й
  док (зв'язок із локацією Odoo).
* Контур будівлі — `bounds` шару `building` (многокутник ≥ 3 точок); без нього — прямокутник `building.length × width`.
* Техніка (N-06): значення в `site.aisle_tech` / `slot.tech` зони — `ключ` або `ключ:мін_м` (свій мінімум ширини
  проїзду); порожнє значення зони — «як у складу», порожнє значення складу — «не перевіряти».
"""

import math

from . import cells as cells_mod
from . import geometry as geo
from . import schemas

ITEM_KINDS = {
    'column': "Колона",
    'wall': "Стіна",
    'gate': "Ворота",
    'dock': "Док",
    'door': "Двері",
    'office': "Офіс",
    'charger': "Зарядка техніки",
}
# об'єкти, з якими не можна перетинатися місцям і обладнанню (ворота, док, двері — прорізи, не перешкоди)
OBSTACLE_KINDS = ('column', 'wall', 'office', 'charger')
OBSTACLE_ACCUSATIVE = {'column': "колону", 'wall': "стіну", 'office': "офіс", 'charger': "зарядку техніки"}
LINK_KINDS = ('gate', 'dock')
# умовний розмір нового об'єкта (w, d), м
ITEM_DEFAULT_SIZE = {
    'column': (0.4, 0.4),
    'wall': (5.0, 0.2),
    'gate': (3.5, 0.3),
    'dock': (3.0, 0.5),
    'door': (1.0, 0.2),
    'office': (6.0, 4.0),
    'charger': (1.2, 0.8),
}
MAX_ITEMS = 5000
MAX_COORD = 10000.0
MAX_SIZE = 1000.0
GRID_COLUMN_HALF = 0.2  # колона сітки — квадрат 0,4 × 0,4 м у вузлі

# N-06: техніка складу й мінімальна ширина проїзду, м (значення можна змінити числом: `ключ:мін_м`)
TECHS = {
    'hand': ("Ручний візок", 1.2),
    'stacker': ("Штабелер", 2.0),
    'reach': ("Ричтрак", 2.8),
    'vna': ("Вузькопрохідний", 1.8),
    'forklift': ("Навантажувач", 3.5),
    'custom': ("Свій мінімум", None),
    'none': ("Не перевіряти", None),
}
SPRINKLER_CLEARANCE_M = 0.5  # зазор від верху складування до спринклерів
SPACER_M = 0.6  # менший зазор між рядами — це «спина до спини», а не проїзд
MIN_FACE_OVERLAP_M = 1.0  # ряди звернені одне до одного, якщо спільна довжина не менша
MAX_NEED_M = 12.0  # пари рядів далі за цей зазор не розглядаються (відбір до точного розрахунку)
INSIDE_KINDS = (
    'storage',
    'production',
    'custom',
)  # шари, об'єкти яких мають бути в будівлі (двір, мережі й будівля — ні)
ROW_TEMPLATES = ('pallet_rack', 'cantilever', 'shelf')
ANGLE_TOLERANCE_DEG = 1.0


# --- R-22: items --------------------------------------------------------------------------------------------------


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalize_items(value):
    """`layer.items` → нормалізований список; хибне — SchemaError (українською, з номером елемента)."""
    if value in (None, False):
        return []
    if not isinstance(value, (list, tuple)):
        raise schemas.SchemaError("Об'єкти будівлі: очікується список.")
    if len(value) > MAX_ITEMS:
        raise schemas.SchemaError("Об'єкти будівлі: не більше %d." % MAX_ITEMS)
    out, seen = [], set()
    for index, item in enumerate(value, 1):
        label = "Об'єкт будівлі %d" % index
        if not isinstance(item, dict):
            raise schemas.SchemaError("%s: очікується об'єкт." % label)
        rid = item.get('id')
        if not isinstance(rid, str) or not 1 <= len(rid) <= 32:
            raise schemas.SchemaError("%s: некоректний id." % label)
        if rid in seen:
            raise schemas.SchemaError("%s: id «%s» повторюється." % (label, rid))
        seen.add(rid)
        kind = item.get('kind')
        if kind not in ITEM_KINDS:
            raise schemas.SchemaError("%s: вид має бути одним із %s." % (label, ", ".join(ITEM_KINDS)))
        name = item.get('name', '')
        if name is None:
            name = ''
        if not isinstance(name, str) or len(name) > 64:
            raise schemas.SchemaError("%s: назва — рядок до 64 символів." % label)
        bad = "%s: некоректні координати чи розміри." % label
        x, y = item.get('x'), item.get('y')
        if not (_finite(x) and _finite(y)) or abs(x) > MAX_COORD or abs(y) > MAX_COORD:
            raise schemas.SchemaError(bad)
        w = item.get('w')
        d = item.get('th') if kind == 'wall' and item.get('th') is not None else item.get('d')
        if not (_finite(w) and _finite(d)) or not 0 < w <= MAX_SIZE or not 0 < d <= MAX_SIZE:
            raise schemas.SchemaError(bad)
        rot = item.get('rot', 0)
        if rot is None:
            rot = 0
        if not _finite(rot) or abs(rot) > 3600:
            raise schemas.SchemaError(bad)
        clean = {
            'id': rid,
            'kind': kind,
            'name': name,
            'x': float(x),
            'y': float(y),
            'w': float(w),
            'd': float(d),
            'rot': float(rot),
        }
        if kind == 'wall':
            clean['th'] = float(d)
        uid = item.get('location_uid')
        if uid in (None, False, ''):
            uid = None
        elif not isinstance(uid, str) or len(uid) > 64:
            raise schemas.SchemaError("%s: зв'язок із локацією — рядок до 64 символів." % label)
        clean['location_uid'] = uid if kind in LINK_KINDS else None
        height = item.get('h')
        if height not in (None, False):
            if not _finite(height) or not 0 < height <= 100:
                raise schemas.SchemaError("%s: висота — число від 0 до 100 м." % label)
            clean['h'] = float(height)
        out.append(clean)
    return out


def item_obb(item):
    return geo.make_obb(item['x'], item['y'], item['w'] / 2.0, item['d'] / 2.0, item.get('rot') or 0.0)


# --- контур ----------------------------------------------------------------------------------------------------------


def polygon_area(points):
    n = len(points)
    return abs(sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1] for i in range(n))) / 2


def polygon_perimeter(points):
    n = len(points)
    return sum(
        math.hypot(points[(i + 1) % n][0] - points[i][0], points[(i + 1) % n][1] - points[i][1]) for i in range(n)
    )


def contour_polygon(scene):
    """Контур будівлі: `bounds` шару `building` (≥ 3 точок), інакше прямокутник габариту площадки."""
    for layer in scene.layers.values():
        bounds = layer.get('bounds')
        if layer.get('kind') == 'building' and bounds and len(bounds) >= 3:
            return [tuple(p) for p in bounds]
    return geo.rect_polygon(scene.building.get('length') or 0.0, scene.building.get('width') or 0.0)


def building_items(scene):
    return [it for layer in scene.layers.values() if layer.get('kind') == 'building' for it in layer.get('items') or []]


def grid_nodes(site, explicit=()):
    """Вузли колон сітки `site.column_grid` у межах `site.building`: [(x, y), …]; вузли, зайняті явними колонами
    `explicit` (`items` kind=column) ближче 5 см, пропущено. Дзеркало `gridNodes` ядра: ті самі вузли бачить
    авторозкладка (`obstacleRects`) і перевірка `inside`."""
    building = (site or {}).get('building') or {}
    grid = (site or {}).get('column_grid') or {}
    step_x = grid.get('step_x') or 0
    step_y = grid.get('step_y') or 0
    out = []
    length, width = building.get('length'), building.get('width')
    if step_x > 1 and step_y > 1 and length and width:
        xs, ys = [], []
        x = step_x
        while x < length - 0.01:
            xs.append(x)
            x += step_x
        y = step_y
        while y < width - 0.01:
            ys.append(y)
            y += step_y
        if len(xs) * len(ys) < 2000:
            for x in xs:
                for y in ys:
                    if not any(math.hypot(c['x'] - x, c['y'] - y) < 0.05 for c in explicit):
                        out.append((x, y))
    return out


# --- техніка (N-06) ----------------------------------------------------------------------------------------------


def parse_tech(value):
    """`'reach'` → ('reach', None); `'custom:3.2'` → ('custom', 3.2); порожнє/невідоме → (None, None)."""
    if not value or not isinstance(value, str):
        return None, None
    key, _, rest = value.partition(':')
    key = key.strip()
    if key not in TECHS:
        return None, None
    minimum = None
    if rest.strip():
        try:
            minimum = float(rest.replace(',', '.'))
        except ValueError:
            minimum = None
        if minimum is not None and (not math.isfinite(minimum) or minimum <= 0):
            minimum = None
    return key, minimum


def tech_min(value):
    """Мінімальна ширина проїзду для значення техніки; None — не перевіряти (або не задано)."""
    key, minimum = parse_tech(value)
    if key is None or key == 'none':
        return None
    if minimum is not None:
        return minimum
    return TECHS[key][1]


def tech_label(value):
    key, _minimum = parse_tech(value)
    return TECHS[key][0] if key else ""


def _site(scene):
    state = getattr(scene, '_state', None) or {}
    return state.get('site') or {}


def zones(scene):
    """Зони площадки з многокутниками (світові координати): [(slot, poly, area)], від найменшої до найбільшої."""
    cached = getattr(scene, '_s5_zones', None)
    if cached is None:
        cached = []
        for slot in scene.slots.values():
            if slot['template'] != 'zone':
                continue
            try:
                poly = [tuple(p) for p in cells_mod.normalize_params('zone', slot.get('params') or {})['polygon']]
            except (cells_mod.CellsError, KeyError, TypeError):
                continue
            cached.append((slot, poly, polygon_area(poly)))
        cached.sort(key=lambda row: row[2])
        scene._s5_zones = cached
    return cached


def tech_at(scene, x, y):
    """Техніка в точці: найменша зона з власною технікою, що містить точку, інакше техніка складу (може бути None)."""
    for slot, poly, _area in zones(scene):
        if slot.get('tech') and geo.polygon_contains(poly, (x, y)):
            return slot['tech']
    return _site(scene).get('aisle_tech') or None


# --- висоти ------------------------------------------------------------------------------------------------------


def slot_height(template, params):
    """Висота місця (м): дзеркало `slotHeight` ядра (data.js) за нормалізованими параметрами."""
    try:
        p = cells_mod.normalize_params(template, params or {})
    except cells_mod.CellsError:
        p = dict(params or {})
    lift = cells_mod.BOTTOM_LIFT if p.get('bottom_on_floor') is False else 0.0
    heights = p.get('level_heights')
    if template in ('pallet_rack', 'cantilever'):
        base = sum(heights) if heights else (p.get('levels') or 1) * (p.get('level_height') or 1.5)
        return base + lift + 0.25
    if template == 'shelf':
        base = sum(heights) if heights else (p.get('shelves') or 1) * (p.get('cell_h') or 0.4)
        return base + lift + 0.1
    if template == 'floor_stack':
        return p.get('max_height') or 1.5
    if template == 'floor_spot':
        height = p.get('height')
        return 1.5 if height is None else height
    if template == 'machine_spot':
        return 0.05
    return 0.02
