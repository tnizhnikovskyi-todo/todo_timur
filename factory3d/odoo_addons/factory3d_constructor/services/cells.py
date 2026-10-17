"""R-01: генерація комірок за шаблоном місця (чистий Python; дзеркало — static/src/editor/cells.js).

Локальна система місця: початок — центр габариту, X — вздовж довжини L, Y — вздовж ширини W;
світові координати комірки: `P + Rot(θ)·(lx, ly)`; `z0` рахується від відмітки шару (`elevation`).
Нумерація: пролети/секції/колонки — зліва направо (+X), яруси/полиці — знизу вгору, ряди — з −Y.
Комірки НЕ зберігаються (DEC-15): обчислюються на льоту.
"""
import math

from .geometry import make_obb, rotate

CODE_MAX_LEN = 32          # CB-01: довжина коду сцени
PREFIX_MAX_LEN = 22        # суфікс комірки до 9 символів

# Параметри шаблонів: ключ → (мін, макс, умовчання, тип). Умовчання — ПРИПУЩЕННЯ для нового місця з UI.
SLOT_TEMPLATES = {
    'pallet_rack': {
        'label': "Паллетний стелаж", 'cells': True,
        'params': {
            'bays': (1, 200, 6, int), 'levels': (1, 12, 4, int), 'bay_width': (0.3, 6.0, 2.7, float),
            'depth': (0.2, 3.0, 1.1, float), 'level_height': (0.1, 3.0, 1.5, float),
            'positions_per_bay': (1, 8, 3, int), 'max_load_kg': (0.0, None, 1000.0, float)},
    },
    'cantilever': {
        'label': "Консольний стелаж", 'cells': True,
        'params': {
            'arms': (1, 100, 4, int), 'levels': (1, 12, 3, int), 'arm_length': (0.3, 2.0, 1.0, float),
            'length': (0.5, 60.0, 6.0, float), 'level_height': (0.1, 3.0, 1.2, float),
            'max_load_kg': (0.0, None, 500.0, float)},
    },
    'shelf': {
        'label': "Полицевий стелаж / комірки фурнітури", 'cells': True,
        'params': {
            'sections': (1, 100, 4, int), 'shelves': (1, 20, 5, int), 'cell_w': (0.1, 3.0, 0.9, float),
            'cell_d': (0.1, 2.0, 0.4, float), 'cell_h': (0.05, 2.0, 0.4, float)},
    },
    'floor_stack': {
        'label': "Підлогове штабелювання", 'cells': True,
        'params': {
            'rows': (1, 50, 2, int), 'cols': (1, 26, 4, int), 'cell_l': (0.3, 6.0, 1.2, float),
            'cell_w': (0.3, 4.0, 0.8, float), 'max_height': (0.1, 6.0, 1.5, float)},
    },
    'machine_spot': {
        'label': "Місце під верстат", 'cells': False,
        'params': {'length': (0.3, 30.0, 3.0, float), 'width': (0.3, 30.0, 1.5, float)},
        'service': True,
    },
    'zone': {
        'label': "Зона-контур", 'cells': False,
        'params': {},
        'polygon': True,
    },
}

PARAM_LABELS = {
    'bays': "Прольотів", 'levels': "Ярусів", 'bay_width': "Ширина прольоту, м", 'depth': "Глибина, м",
    'level_height': "Висота ярусу, м", 'positions_per_bay': "Палетомісць у прольоті", 'max_load_kg': "Макс. вага комірки, кг",
    'arms': "Секцій", 'arm_length': "Виліт консолі, м", 'length': "Довжина, м", 'sections': "Секцій",
    'shelves': "Полиць", 'cell_w': "Ширина комірки, м", 'cell_d': "Глибина комірки, м", 'cell_h': "Висота комірки, м",
    'rows': "Рядів", 'cols': "Колонок", 'cell_l': "Довжина комірки, м", 'max_height': "Макс. висота штабеля, м",
    'width': "Ширина, м",
}

OVERRIDE_KEYS = ('disabled', 'max_load_kg', 'capacity', 'name')
SERVICE_SIDES = ('front', 'back', 'left', 'right')


class CellsError(ValueError):
    """Помилка параметрів шаблону (текст — українською, показується користувачу)."""


def _num(value, kind):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError
    if not math.isfinite(value):
        raise TypeError
    if kind is int:
        if int(value) != value:
            raise TypeError
        return int(value)
    return float(value)


def normalize_params(template, params):
    """Параметри шаблону з умовчаннями; невідомі ключі відкидаються; значення поза діапазоном → CellsError."""
    spec = SLOT_TEMPLATES.get(template)
    if spec is None:
        raise CellsError("Невідомий шаблон місця «%s»." % template)
    params = params or {}
    if not isinstance(params, dict):
        raise CellsError("Параметри шаблону мають бути об'єктом.")
    out = {}
    for key, (lo, hi, default, kind) in spec['params'].items():
        label = PARAM_LABELS.get(key, key)
        value = params.get(key, default)
        try:
            value = _num(value, kind)
        except TypeError:
            raise CellsError("Параметр «%s»: некоректне значення." % label) from None
        if value < lo or (hi is not None and value > hi):
            raise CellsError("Параметр «%s»: допустимо від %s%s." % (
                label, lo, (" до %s" % hi) if hi is not None else ""))
        out[key] = value
    if spec.get('service'):
        service = params.get('service') or {}
        if not isinstance(service, dict):
            raise CellsError("Параметр «service»: некоректне значення.")
        out['service'] = {}
        for side in SERVICE_SIDES:
            try:
                value = _num(service.get(side, 0), float)
            except TypeError:
                raise CellsError("Сервіс «%s»: некоректне значення." % side) from None
            if value < 0:
                raise CellsError("Сервіс «%s» не може бути від'ємним." % side)
            out['service'][side] = value
    if spec.get('polygon'):
        poly = params.get('polygon')
        if not isinstance(poly, (list, tuple)) or len(poly) < 3:
            raise CellsError("Зона-контур: щонайменше 3 точки.")
        points = []
        for point in poly:
            try:
                x, y = point
                points.append([_num(x, float), _num(y, float)])
            except (TypeError, ValueError):
                raise CellsError("Зона-контур: некоректна точка.") from None
        out['polygon'] = points
    return out


def validate_params(template, params):
    """Повертає нормалізовані параметри або кидає CellsError (R-01, M-03)."""
    return normalize_params(template, params)


def footprint(template, params):
    """Габарит у локальній системі: (L, W) в метрах."""
    p = normalize_params(template, params)
    if template == 'pallet_rack':
        return p['bays'] * p['bay_width'], p['depth']
    if template == 'cantilever':
        return p['length'], p['arm_length']
    if template == 'shelf':
        return p['sections'] * p['cell_w'], p['cell_d']
    if template == 'floor_stack':
        return p['cols'] * p['cell_l'], p['rows'] * p['cell_w']
    if template == 'machine_spot':
        return p['length'], p['width']
    xs = [pt[0] for pt in p['polygon']]
    ys = [pt[1] for pt in p['polygon']]
    return max(xs) - min(xs), max(ys) - min(ys)


def slot_obb(template, params, x, y, rot):
    """OBB габариту місця (R-02): центр — точка місця (для `zone` — центр bbox полігона), піврозміри L/2 × W/2."""
    length, width = footprint(template, params)
    if template == 'zone':
        poly = normalize_params(template, params)['polygon']
        xs = [pt[0] for pt in poly]
        ys = [pt[1] for pt in poly]
        return make_obb((max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0, length / 2.0, width / 2.0, 0.0)
    return make_obb(x, y, length / 2.0, width / 2.0, rot)


def _width(count):
    return max(2, len(str(count)))


def count_cells(template, prefix, params, overrides=None):
    """Кількість недисаблених комірок (R-01: `cell_count = len(generate_cells(...))`)."""
    return len(generate_cells(template, prefix, 0.0, 0.0, 0.0, params, overrides, 0.0))


def _raw_cells(template, p, prefix):
    """Комірки в локальній системі без поворотів: [{code, name, level, index, lx, ly, dz, l, w, h, capacity, max_load_kg, kind}]."""
    cells = []
    if template == 'pallet_rack':
        length = p['bays'] * p['bay_width']
        width_n = _width(p['bays'])
        for bay in range(1, p['bays'] + 1):
            for lvl in range(1, p['levels'] + 1):
                cells.append({
                    'code': "%s-B%0*d-L%d" % (prefix, width_n, bay, lvl), 'level': lvl, 'index': bay,
                    'lx': -length / 2.0 + (bay - 0.5) * p['bay_width'], 'ly': 0.0,
                    'dz': (lvl - 1) * p['level_height'], 'l': p['bay_width'], 'w': p['depth'], 'h': p['level_height'],
                    'capacity': float(p['positions_per_bay']), 'max_load_kg': p['max_load_kg'], 'kind': 'pallet_cell'})
    elif template == 'cantilever':
        length = p['length']
        arm_l = length / p['arms']
        width_n = _width(p['arms'])
        for arm in range(1, p['arms'] + 1):
            for lvl in range(1, p['levels'] + 1):
                cells.append({
                    'code': "%s-A%0*d-L%d" % (prefix, width_n, arm, lvl), 'level': lvl, 'index': arm,
                    'lx': -length / 2.0 + (arm - 0.5) * arm_l, 'ly': 0.0,
                    'dz': (lvl - 1) * p['level_height'], 'l': arm_l, 'w': p['arm_length'], 'h': p['level_height'],
                    'capacity': 0.0, 'max_load_kg': p['max_load_kg'], 'kind': 'shelf'})
    elif template == 'shelf':
        length = p['sections'] * p['cell_w']
        width_n = _width(p['sections'])
        for sec in range(1, p['sections'] + 1):
            for lvl in range(1, p['shelves'] + 1):
                cells.append({
                    'code': "%s-S%0*d-L%d" % (prefix, width_n, sec, lvl), 'level': lvl, 'index': sec,
                    'lx': -length / 2.0 + (sec - 0.5) * p['cell_w'], 'ly': 0.0,
                    'dz': (lvl - 1) * p['cell_h'], 'l': p['cell_w'], 'w': p['cell_d'], 'h': p['cell_h'],
                    'capacity': 0.0, 'max_load_kg': 0.0, 'kind': 'bin'})
    elif template == 'floor_stack':
        length = p['cols'] * p['cell_l']
        width = p['rows'] * p['cell_w']
        width_n = _width(p['rows'])
        for row in range(1, p['rows'] + 1):
            for col in range(1, p['cols'] + 1):
                cells.append({
                    'code': "%s-%0*d%s" % (prefix, width_n, row, chr(ord('A') + col - 1)), 'level': 1,
                    'index': (row - 1) * p['cols'] + col,
                    'lx': -length / 2.0 + (col - 0.5) * p['cell_l'], 'ly': -width / 2.0 + (row - 0.5) * p['cell_w'],
                    'dz': 0.0, 'l': p['cell_l'], 'w': p['cell_w'], 'h': p['max_height'],
                    'capacity': 0.0, 'max_load_kg': 0.0, 'kind': 'stack'})
    return cells


def template_codes(template, params, prefix):
    """Усі коди комірок шаблону (до перевизначень) — для перевірки ключів `overrides`."""
    spec = SLOT_TEMPLATES.get(template)
    if spec is None or not spec['cells']:
        return []
    return [cell['code'] for cell in _raw_cells(template, normalize_params(template, params), prefix)]


def normalize_overrides(overrides):
    """Лишає лише відомі ключі (R-22); типи перевіряються, помилка → CellsError."""
    if overrides in (None, False):
        return {}
    if not isinstance(overrides, dict):
        raise CellsError("Перевизначення комірок мають бути об'єктом.")
    out = {}
    for code, item in overrides.items():
        if not isinstance(item, dict):
            raise CellsError("Комірка %s: некоректне перевизначення." % code)
        clean = {}
        for key in OVERRIDE_KEYS:
            if key not in item:
                continue
            value = item[key]
            if key == 'disabled':
                if not isinstance(value, bool):
                    raise CellsError("Комірка %s: «disabled» має бути true/false." % code)
            elif key == 'name':
                if not isinstance(value, str) or len(value) > 64:
                    raise CellsError("Комірка %s: назва — рядок до 64 символів." % code)
            else:
                try:
                    value = _num(value, float)
                except TypeError:
                    raise CellsError("Комірка %s: «%s» має бути числом." % (code, key)) from None
                if value < 0:
                    raise CellsError("Комірка %s: «%s» не може бути від'ємним." % (code, key))
            clean[key] = value
        out[code] = clean
    return out


def generate_cells(template, prefix, x, y, rot, params, overrides=None, elevation=0.0):
    """R-01: список комірок `{code, name, template, level, index, x, y, z0, l, w, h, rot, capacity, max_load_kg, kind}`.

    `overrides[code]`: `disabled` — комірка не повертається; `max_load_kg`, `capacity`, `name` замінюють значення.
    """
    spec = SLOT_TEMPLATES.get(template)
    if spec is None:
        raise CellsError("Невідомий шаблон місця «%s»." % template)
    if not spec['cells']:
        return []
    p = normalize_params(template, params)
    overrides = normalize_overrides(overrides)
    out = []
    for raw in _raw_cells(template, p, prefix):
        code = raw['code']
        if len(code) > CODE_MAX_LEN:
            raise CellsError("Код комірки %s довший за %d символів." % (code, CODE_MAX_LEN))
        ov = overrides.get(code, {})
        if ov.get('disabled'):
            continue
        wx, wy = rotate(raw['lx'], raw['ly'], rot)
        out.append({
            'code': code, 'name': ov.get('name') or code, 'template': template,
            'level': raw['level'], 'index': raw['index'],
            'x': x + wx, 'y': y + wy, 'z0': elevation + raw['dz'],
            'l': raw['l'], 'w': raw['w'], 'h': raw['h'], 'rot': float(rot),
            'capacity': ov.get('capacity', raw['capacity']),
            'max_load_kg': ov.get('max_load_kg', raw['max_load_kg']),
            'kind': raw['kind'],
        })
    return out
