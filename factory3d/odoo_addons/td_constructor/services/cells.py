"""R-01: генерація комірок за шаблоном місця (чистий Python; дзеркало — static/src/editor/cells.js).

Локальна система місця: початок — центр габариту, X — вздовж довжини L, Y — вздовж ширини W;
світові координати комірки: `P + Rot(θ)·(lx, ly)`; `z0` рахується від відмітки шару (`elevation`).
Нумерація: пролети/секції/колонки — зліва направо (+X), яруси/полиці — знизу вгору, ряди — з −Y.
Комірки НЕ зберігаються (DEC-15): обчислюються на льоту.
"""

import math

from . import addr as addr_mod
from .geometry import make_obb, rotate

CODE_MAX_LEN = 32  # CB-01: довжина коду сцени
PREFIX_MAX_LEN = 22  # суфікс комірки до 9 символів
# значення stock.location.td_loc_kind (td_factory3d): вид комірки шаблону floor_stack береться з наявної локації
LOC_KINDS = ('stack', 'area', 'kit', 'bin', 'shelf', 'pallet_cell')
# форми 3D (реєстр shapes ядра): '' — каркас генератора за замовчуванням (MERGE.md §2.2, F08-04: 9 форм)
SHAPE_KEYS = ('', 'rack', 'roll_rack', 'stack', 'zone', 'fence', 'cylinder', 'cabinet', 'mobile', 'gate')
BOTTOM_LIFT = 0.15  # м: нижній ярус не на підлозі (`bottom_on_floor=false`) стоїть на першій балці

# Параметри шаблонів: ключ → (мін, макс, умовчання, тип). Умовчання — ПРИПУЩЕННЯ для нового місця з UI.
# `params` завжди потрапляють у нормалізований словник; `opt` (MERGE.md §2.2, F08-02) — лише коли задані явно, тож
# старі місця (і золоті фікстури R-01) лишаються байт-в-байт як були; тип `bool`/`list` — прапорець/список по ярусах.
_OPT_RACK = {
    'bottom_on_floor': (None, None, True, bool),
    'double_sided': (None, None, False, bool),
    'gap_x': (0.0, 2.0, 0.0, float),
    'gap_y': (0.0, 2.0, 0.0, float),
    'beam_th': (0.0, 0.3, 0.0, float),
    'slope': (0.0, 20.0, 0.0, float),
    'cells_per_level': (1, 12, 1, int),
    'level_heights': (0.1, 3.0, None, list),
}
SLOT_TEMPLATES = {
    'pallet_rack': {
        'label': "Паллетний стелаж",
        'cells': True,
        'params': {
            'bays': (1, 200, 6, int),
            'levels': (1, 12, 4, int),
            'bay_width': (0.3, 6.0, 2.7, float),
            'depth': (0.2, 3.0, 1.1, float),
            'level_height': (0.1, 3.0, 1.5, float),
            'positions_per_bay': (1, 8, 3, int),
            'max_load_kg': (0.0, None, 1000.0, float),
            'index_digits': (1, 4, 2, int),
        },
        'opt': dict(_OPT_RACK, deep=(1, 6, 1, int)),
        'choices': {'code_style': (('default', 'bay_letter', 'exact'), 'default')},
        'opt_choices': {'shape': (SHAPE_KEYS, '')},
    },
    'cantilever': {
        'label': "Консольний стелаж",
        'cells': True,
        'params': {
            'arms': (1, 100, 4, int),
            'levels': (1, 12, 3, int),
            'arm_length': (0.3, 2.0, 1.0, float),
            'length': (0.5, 60.0, 6.0, float),
            'level_height': (0.1, 3.0, 1.2, float),
            'max_load_kg': (0.0, None, 500.0, float),
            'index_digits': (1, 4, 2, int),
        },
        'opt': {k: v for k, v in _OPT_RACK.items() if k != 'gap_x'},
        'choices': {'code_style': (('default', 'exact'), 'default')},
        'opt_choices': {'shape': (SHAPE_KEYS, '')},
    },
    'shelf': {
        'label': "Полицевий стелаж / комірки фурнітури",
        'cells': True,
        'params': {
            'sections': (1, 100, 4, int),
            'shelves': (1, 20, 5, int),
            'cell_w': (0.1, 8.0, 0.9, float),
            'cell_d': (0.1, 2.0, 0.4, float),
            'cell_h': (0.05, 2.0, 0.4, float),
            'index_digits': (1, 4, 2, int),
        },
        'opt': dict(_OPT_RACK),
        'choices': {'loc_kind': (('bin', 'shelf'), 'bin'), 'code_style': (('default', 'exact'), 'default')},
        'opt_choices': {'shape': (SHAPE_KEYS, '')},
    },
    'floor_stack': {
        'label': "Підлогове штабелювання",
        'cells': True,
        'params': {
            'rows': (1, 50, 2, int),
            'cols': (1, 26, 4, int),
            'cell_l': (0.3, 6.0, 1.2, float),
            'cell_w': (0.3, 4.0, 0.8, float),
            'max_height': (0.1, 6.0, 1.5, float),
            'index_digits': (1, 4, 2, int),
        },
        'opt': {'gap_x': (0.0, 2.0, 0.0, float), 'gap_y': (0.0, 2.0, 0.0, float)},
        'choices': {
            'code_style': (('default', 'exact'), 'default'),
            'loc_kind': (LOC_KINDS, 'stack'),  # вид локації Odoo (td_loc_kind): стос, майданчик, візок тощо
        },
        'opt_choices': {'shape': (SHAPE_KEYS, '')},
    },
    # прямокутник на підлозі = ОДНА локація (MERGE.md §2.3): буферні й спеціальні зони, мобільні носії, зона на підлозі
    'floor_spot': {
        'label': "Місце на підлозі (одна локація)",
        'cells': True,
        'params': {
            'length': (0.1, 200.0, 1.2, float),
            'width': (0.1, 200.0, 0.8, float),
            'height': (0.0, 30.0, 1.5, float),
            'max_load_kg': (0.0, None, 0.0, float),
            'capacity': (0.0, None, 0.0, float),
        },
        'choices': {'loc_kind': (LOC_KINDS, 'area'), 'shape': (SHAPE_KEYS, 'zone')},
    },
    'machine_spot': {
        'label': "Місце під верстат",
        'cells': False,
        'params': {'length': (0.3, 30.0, 3.0, float), 'width': (0.3, 30.0, 1.5, float)},
        'service': True,
    },
    'zone': {
        'label': "Зона-контур",
        'cells': False,
        'params': {},
        'polygon': True,
    },
}

# code_style='exact': якщо шаблон дає рівно одну комірку, її код = code_prefix; для floor_stack такі місця (стос,
# комплект, зона видачі) можуть бути завбільшки з усю зону — межі розмірів ширші
EXACT_RANGES = {
    'cell_l': (0.1, 200.0, 1.2, float),
    'cell_w': (0.1, 200.0, 0.8, float),
    'max_height': (0.05, 30.0, 1.5, float),
}

PARAM_LABELS = {
    'bays': "Прольотів",
    'levels': "Ярусів",
    'bay_width': "Ширина прольоту, м",
    'depth': "Глибина, м",
    'level_height': "Висота ярусу, м",
    'positions_per_bay': "Палетомісць у прольоті",
    'max_load_kg': "Макс. вага комірки, кг",
    'arms': "Секцій",
    'arm_length': "Виліт консолі, м",
    'length': "Довжина, м",
    'sections': "Секцій",
    'shelves': "Полиць",
    'cell_w': "Ширина комірки, м",
    'cell_d': "Глибина комірки, м",
    'cell_h': "Висота комірки, м",
    'rows': "Рядів",
    'cols': "Колонок",
    'cell_l': "Довжина комірки, м",
    'max_height': "Макс. висота штабеля, м",
    'width': "Ширина, м",
    'height': "Висота, м",
    'capacity': "Місткість, місць",
    'index_digits': "Розрядів у номері",
    'code_style': "Стиль кодів",
    'loc_kind': "Вид локацій",
    'deep': "Глибина в палетах",
    'bottom_on_floor': "Нижній ярус на підлозі",
    'double_sided': "Двосторонній ряд",
    'gap_x': "Зазор між секціями, м",
    'gap_y': "Зазор між сторонами, м",
    'beam_th': "Товщина балки, м",
    'slope': "Ухил, °",
    'cells_per_level': "Комірок на ярусі",
    'level_heights': "Висоти ярусів, м",
    'shape': "Форма 3D",
}

# F03-05: `usage` (internal | view) і `replenish_location` — прапорці локації, що їх записує публікація
OVERRIDE_KEYS = ('disabled', 'max_load_kg', 'capacity', 'name', 'usage', 'replenish_location')
LOCATION_USAGES = ('internal', 'view')
SERVICE_SIDES = ('front', 'back', 'left', 'right')
# ключ параметра «кількість ярусів» і «базова висота ярусу» генераторів із ярусами
LEVEL_KEYS = {
    'pallet_rack': ('levels', 'level_height'),
    'cantilever': ('levels', 'level_height'),
    'shelf': ('shelves', 'cell_h'),
}


class CellsError(ValueError):
    """Помилка параметрів шаблону (текст — українською, показується користувачу)."""


def _num(value, kind):
    if kind is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        raise TypeError
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError
    if not math.isfinite(value):
        raise TypeError
    if kind is int:
        if int(value) != value:
            raise TypeError
        return int(value)
    return float(value)


def _check_range(key, value, lo, hi):
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        label = PARAM_LABELS.get(key, key)
        raise CellsError("Параметр «%s»: допустимо від %s%s." % (label, lo, (" до %s" % hi) if hi is not None else ""))


def normalize_params(template, params):
    """Параметри шаблону з умовчаннями; невідомі ключі відкидаються; значення поза діапазоном → CellsError."""
    spec = SLOT_TEMPLATES.get(template)
    if spec is None:
        raise CellsError("Невідомий шаблон місця «%s»." % template)
    params = params or {}
    if not isinstance(params, dict):
        raise CellsError("Параметри шаблону мають бути об'єктом.")
    out = {}
    ranges = spec['params']
    if template == 'floor_stack' and params.get('code_style') == 'exact':
        ranges = dict(ranges, **EXACT_RANGES)  # одна комірка на весь габарит (стос, комплект, зона видачі): межі ширші
    for key, (lo, hi, default, kind) in ranges.items():
        label = PARAM_LABELS.get(key, key)
        value = params.get(key, default)
        try:
            value = _num(value, kind)
        except TypeError:
            raise CellsError("Параметр «%s»: некоректне значення." % label) from None
        _check_range(key, value, lo, hi)
        out[key] = value
    for key, (allowed, default) in (spec.get('choices') or {}).items():
        value = params.get(key, default)
        if value not in allowed:
            raise CellsError("Параметр «%s»: допустимо %s." % (PARAM_LABELS.get(key, key), ", ".join(allowed)))
        out[key] = value
    _normalize_optional(spec, params, out)
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


def _normalize_optional(spec, params, out):
    """Необов'язкові параметри (`opt`, `opt_choices`): потрапляють у результат, лише якщо задані (не null)."""
    for key, (lo, hi, _default, kind) in (spec.get('opt') or {}).items():
        value = params.get(key)
        if value is None:
            continue
        label = PARAM_LABELS.get(key, key)
        if kind is list:
            out_list = _normalize_level_heights(spec, params, out, value, lo, hi)
            if out_list:
                out[key] = out_list
            continue
        try:
            value = _num(value, kind)
        except TypeError:
            raise CellsError("Параметр «%s»: некоректне значення." % label) from None
        if kind is not bool:
            _check_range(key, value, lo, hi)
        out[key] = value
    for key, (allowed, _default) in (spec.get('opt_choices') or {}).items():
        value = params.get(key)
        if value in (None, ''):
            continue
        if value not in allowed:
            raise CellsError(
                "Параметр «%s»: допустимо %s." % (PARAM_LABELS.get(key, key), ", ".join(a for a in allowed if a))
            )
        out[key] = value


def _normalize_level_heights(spec, params, out, value, lo, hi):
    """Висоти ярусів: числа в межах, довжина підганяється під число ярусів (бракуючі — базова висота)."""
    count_key, height_key = LEVEL_KEYS[next(t for t, s in SLOT_TEMPLATES.items() if s is spec)]
    if not isinstance(value, (list, tuple)):
        raise CellsError("Параметр «%s»: очікується список." % PARAM_LABELS['level_heights'])
    heights = []
    for item in value:
        try:
            item = _num(item, float)
        except TypeError:
            raise CellsError("Параметр «%s»: некоректне значення." % PARAM_LABELS['level_heights']) from None
        _check_range('level_heights', item, lo, hi)
        heights.append(item)
    if not heights:
        return []
    count = out[count_key]
    return (heights + [out[height_key]] * count)[:count]


def validate_params(template, params):
    """Повертає нормалізовані параметри або кидає CellsError (R-01, M-03)."""
    return normalize_params(template, params)


def _sides(p):
    return 2 if p.get('double_sided') else 1


def footprint(template, params):
    """Габарит у локальній системі: (L, W) в метрах."""
    p = normalize_params(template, params)
    gap_x, gap_y = p.get('gap_x', 0.0), p.get('gap_y', 0.0)
    if template == 'pallet_rack':
        d = p['depth'] * p.get('deep', 1)
        return p['bays'] * p['bay_width'] + (p['bays'] - 1) * gap_x, _sides(p) * d + (_sides(p) - 1) * gap_y
    if template == 'cantilever':
        return p['length'], _sides(p) * p['arm_length'] + (_sides(p) - 1) * gap_y
    if template == 'shelf':
        return p['sections'] * p['cell_w'] + (p['sections'] - 1) * gap_x, _sides(p) * p['cell_d'] + (
            _sides(p) - 1
        ) * gap_y
    if template == 'floor_stack':
        return p['cols'] * p['cell_l'] + (p['cols'] - 1) * gap_x, p['rows'] * p['cell_w'] + (p['rows'] - 1) * gap_y
    if template in ('machine_spot', 'floor_spot'):
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


def _width(count, digits=2):
    """Ширина індексу: `max(index_digits, цифр(N))`; за замовчуванням 2 (`B01`)."""
    return max(digits, len(str(count)))


def count_cells(template, prefix, params, overrides=None, ctx=None):
    """Кількість недисаблених комірок (R-01: `cell_count = len(generate_cells(...))`)."""
    return len(generate_cells(template, prefix, 0.0, 0.0, 0.0, params, overrides, 0.0, ctx))


def _levels(p, n, base_h):
    """Ярус → (dz, h): базова висота або `level_heights`, відступ нижнього ярусу, мінус товщина балки."""
    heights = p.get('level_heights')
    lift = 0.0 if p.get('bottom_on_floor', True) else BOTTOM_LIFT
    beam = p.get('beam_th', 0.0)
    out, z = [], lift
    for i in range(n):
        h = heights[i] if heights else base_h
        dz = z if heights else lift + i * base_h
        out.append((dz, max(h - beam, 0.05) if beam else h))
        z += h
    return out


def _raw_cells(template, p, prefix):
    """Комірки в локальній системі без поворотів (коди — legacy).

    [{code, name, level, index, lx, ly, dz, l, w, h, capacity, max_load_kg, kind, k, side, pos, pos_n, pos_x}]:
    `k` — номер секції вздовж X, `side` — сторона двостороннього ряду (1|2), `pos` — позиція (`floor_stack`: ряд)."""
    cells = []
    gap_x, gap_y = p.get('gap_x', 0.0), p.get('gap_y', 0.0)
    sides = _sides(p)
    if template == 'pallet_rack':
        deep = p.get('deep', 1)
        d = p['depth'] * deep
        length = p['bays'] * p['bay_width'] + (p['bays'] - 1) * gap_x
        full_w = sides * d + (sides - 1) * gap_y
        width_n = _width(p['bays'] * sides, p['index_digits'])
        levels = _levels(p, p['levels'], p['level_height'])
        for side in range(1, sides + 1):
            ly = 0.0 if sides == 1 else (-(full_w - d) / 2.0 if side == 1 else (full_w - d) / 2.0)
            for bay in range(1, p['bays'] + 1):
                bay_no = bay + (side - 1) * p['bays']
                for lvl in range(1, p['levels'] + 1):
                    code = (
                        "%s-%0*d%s" % (prefix, width_n, bay_no, chr(ord('A') + lvl - 1))
                        if p['code_style'] == 'bay_letter'
                        else "%s-B%0*d-L%d" % (prefix, width_n, bay_no, lvl)
                    )
                    cells.append(
                        {
                            'code': code,
                            'level': lvl,
                            'index': bay_no,
                            'lx': -length / 2.0 + (bay - 0.5) * p['bay_width'] + (bay - 1) * gap_x,
                            'ly': ly,
                            'dz': levels[lvl - 1][0],
                            'l': p['bay_width'],
                            'w': d,
                            'h': levels[lvl - 1][1],
                            'capacity': float(p['positions_per_bay']) * deep,
                            'max_load_kg': p['max_load_kg'],
                            'kind': 'pallet_cell',
                            'k': bay,
                            'side': side,
                        }
                    )
    elif template == 'cantilever':
        length = p['length']
        arm_l = length / p['arms']
        full_w = sides * p['arm_length'] + (sides - 1) * gap_y
        width_n = _width(p['arms'] * sides, p['index_digits'])
        levels = _levels(p, p['levels'], p['level_height'])
        for side in range(1, sides + 1):
            ly = (
                0.0
                if sides == 1
                else (-(full_w - p['arm_length']) / 2.0 if side == 1 else (full_w - p['arm_length']) / 2.0)
            )
            for arm in range(1, p['arms'] + 1):
                arm_no = arm + (side - 1) * p['arms']
                for lvl in range(1, p['levels'] + 1):
                    cells.append(
                        {
                            'code': "%s-A%0*d-L%d" % (prefix, width_n, arm_no, lvl),
                            'level': lvl,
                            'index': arm_no,
                            'lx': -length / 2.0 + (arm - 0.5) * arm_l,
                            'ly': ly,
                            'dz': levels[lvl - 1][0],
                            'l': arm_l,
                            'w': p['arm_length'],
                            'h': levels[lvl - 1][1],
                            'capacity': 0.0,
                            'max_load_kg': p['max_load_kg'],
                            'kind': 'shelf',
                            'k': arm,
                            'side': side,
                        }
                    )
    elif template == 'shelf':
        length = p['sections'] * p['cell_w'] + (p['sections'] - 1) * gap_x
        full_w = sides * p['cell_d'] + (sides - 1) * gap_y
        width_n = _width(p['sections'] * sides, p['index_digits'])
        levels = _levels(p, p['shelves'], p['cell_h'])
        for side in range(1, sides + 1):
            ly = 0.0 if sides == 1 else (-(full_w - p['cell_d']) / 2.0 if side == 1 else (full_w - p['cell_d']) / 2.0)
            for sec in range(1, p['sections'] + 1):
                sec_no = sec + (side - 1) * p['sections']
                for lvl in range(1, p['shelves'] + 1):
                    cells.append(
                        {
                            'code': "%s-S%0*d-L%d" % (prefix, width_n, sec_no, lvl),
                            'level': lvl,
                            'index': sec_no,
                            'lx': -length / 2.0 + (sec - 0.5) * p['cell_w'] + (sec - 1) * gap_x,
                            'ly': ly,
                            'dz': levels[lvl - 1][0],
                            'l': p['cell_w'],
                            'w': p['cell_d'],
                            'h': levels[lvl - 1][1],
                            'capacity': 0.0,
                            'max_load_kg': 0.0,
                            'kind': p['loc_kind'],
                            'k': sec,
                            'side': side,
                        }
                    )
    elif template == 'floor_stack':
        length = p['cols'] * p['cell_l'] + (p['cols'] - 1) * gap_x
        width = p['rows'] * p['cell_w'] + (p['rows'] - 1) * gap_y
        width_n = _width(p['rows'], p['index_digits'])
        for row in range(1, p['rows'] + 1):
            for col in range(1, p['cols'] + 1):
                cells.append(
                    {
                        'code': "%s-%0*d%s" % (prefix, width_n, row, chr(ord('A') + col - 1)),
                        'level': 1,
                        'index': (row - 1) * p['cols'] + col,
                        'lx': -length / 2.0 + (col - 0.5) * p['cell_l'] + (col - 1) * gap_x,
                        'ly': -width / 2.0 + (row - 0.5) * p['cell_w'] + (row - 1) * gap_y,
                        'dz': 0.0,
                        'l': p['cell_l'],
                        'w': p['cell_w'],
                        'h': p['max_height'],
                        'capacity': 0.0,
                        'max_load_kg': 0.0,
                        'kind': p['loc_kind'],
                        'k': col,
                        'side': 1,
                        'pos': row,
                        'pos_n': p['rows'],
                    }
                )
    elif template == 'floor_spot':
        cells.append(
            {
                'code': prefix,
                'level': 1,
                'index': 1,
                'lx': 0.0,
                'ly': 0.0,
                'dz': 0.0,
                'l': p['length'],
                'w': p['width'],
                'h': p['height'],
                'capacity': p['capacity'],
                'max_load_kg': p['max_load_kg'],
                'kind': p['loc_kind'],
                'k': 1,
                'side': 1,
            }
        )
    if p.get('code_style') == 'exact' and len(cells) == 1:  # одиничне місце зберігання: код комірки = code_prefix
        cells[0]['code'] = prefix
    return cells


def _split_cells(cells, n):
    """Глибина локацій «комірка» (F01-10): ярус ділиться на n локацій `<код ярусу>-1…n` уздовж X."""
    out = []
    for cell in cells:
        for j in range(1, n + 1):
            sub = dict(cell)
            sub.update(
                code="%s-%d" % (cell['code'], j),
                lx=cell['lx'] - cell['l'] / 2.0 + (j - 0.5) * cell['l'] / n,
                l=cell['l'] / n,
                capacity=cell['capacity'] / n,
                max_load_kg=cell['max_load_kg'] / n,
                pos=j,
                pos_n=n,
                pos_x=True,
            )
            out.append(sub)
    return out


def _addressed_cells(template, p, prefix, rot, ctx):
    """Комірки з кодами за контекстом адресації `ctx` ({addr, zone, row, spot, depth_mode}); без `ctx` — legacy-коди."""
    cells = _raw_cells(template, p, prefix)
    if not ctx:
        return cells
    if ctx.get('depth_mode') == 'cell' and template in LEVEL_KEYS:
        cells = _split_cells(cells, p.get('cells_per_level', 1))
    addr = ctx.get('addr')
    if not addr or p.get('code_style') == 'exact':
        return cells
    if template == 'floor_spot':
        for cell in cells:
            cell['code'] = addr_mod.render_code(addr, addr_mod.spot_vals(ctx, prefix))
        return cells
    sizes = {'sides': _sides(p), 'levels': 1}
    if template in LEVEL_KEYS:
        sizes['levels'] = p[LEVEL_KEYS[template][0]]
    sizes['bays'] = {'pallet_rack': 'bays', 'cantilever': 'arms', 'shelf': 'sections', 'floor_stack': 'cols'}[template]
    sizes['bays'] = p[sizes['bays']]
    for cell in cells:
        raw = dict(cell, level=cell['level'] if template in LEVEL_KEYS else None)
        cell['code'] = addr_mod.render_code(addr, addr_mod.cell_vals(ctx, prefix, rot, raw, sizes))
    return cells


def template_codes(template, params, prefix, ctx=None):
    """Усі коди комірок шаблону (до перевизначень) — для перевірки ключів `overrides`."""
    spec = SLOT_TEMPLATES.get(template)
    if spec is None or not spec['cells']:
        return []
    return [c['code'] for c in _addressed_cells(template, normalize_params(template, params), prefix, 0.0, ctx)]


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
            if key in ('disabled', 'replenish_location'):
                if not isinstance(value, bool):
                    raise CellsError("Комірка %s: «%s» має бути true/false." % (code, key))
            elif key == 'usage':
                if value not in LOCATION_USAGES:
                    raise CellsError("Комірка %s: «usage» має бути одним із: %s." % (code, ", ".join(LOCATION_USAGES)))
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


def generate_cells(template, prefix, x, y, rot, params, overrides=None, elevation=0.0, ctx=None):
    """R-01: список комірок `{code, name, template, level, index, x, y, z0, l, w, h, rot, capacity, max_load_kg, kind}`.

    `overrides[code]`: `disabled` — комірка не повертається; `max_load_kg`, `capacity`, `name` замінюють значення;
    `usage`, `replenish_location` (F03-05) потрапляють у комірку лише коли задані.
    `ctx` — контекст адресації місця (`addr.address_context`): без нього коди legacy (`ПРЕФІКС-B01-L1`)."""
    spec = SLOT_TEMPLATES.get(template)
    if spec is None:
        raise CellsError("Невідомий шаблон місця «%s»." % template)
    if not spec['cells']:
        return []
    p = normalize_params(template, params)
    overrides = normalize_overrides(overrides)
    out = []
    try:
        raws = _addressed_cells(template, p, prefix, rot, ctx)
    except addr_mod.AddrError as exc:
        raise CellsError(str(exc)) from None
    for raw in raws:
        code = raw['code']
        if len(code) > CODE_MAX_LEN:
            raise CellsError("Код комірки %s довший за %d символів." % (code, CODE_MAX_LEN))
        ov = overrides.get(code, {})
        if ov.get('disabled'):
            continue
        wx, wy = rotate(raw['lx'], raw['ly'], rot)
        cell = {
            'code': code,
            'name': ov.get('name') or code,
            'template': template,
            'level': raw['level'],
            'index': raw['index'],
            'x': x + wx,
            'y': y + wy,
            'z0': elevation + raw['dz'],
            'l': raw['l'],
            'w': raw['w'],
            'h': raw['h'],
            'rot': float(rot),
            'capacity': ov.get('capacity', raw['capacity']),
            'max_load_kg': ov.get('max_load_kg', raw['max_load_kg']),
            'kind': raw['kind'],
        }
        cell.update({key: ov[key] for key in ('usage', 'replenish_location') if key in ov})
        out.append(cell)
    return out
