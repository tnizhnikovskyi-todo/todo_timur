"""Специфікація стелажів: рами, балки, полиці, стійки, консолі, зв'язки, стяжки (F15-01, F15-04).

Чистий Python без ORM (дзеркало — `core/constructor/spec.js`; золоті фікстури
`static/tests/fixtures/s5_golden.json`).
Формули відновлено за інструкцією «Документи» (Q12: еталонних файлів «Конструктора складу» немає). Усе рахується
за НОРМАЛІЗОВАНИМИ параметрами місця (`cells.normalize_params`); `sides = 2` для двосторонніх (`double_sided`) —
кожен бік рахується окремо.

* палетний (`pallet_rack`, `B` прольотів, `N` ярусів): рам `(B+1)·sides` розміром В×Г (В — висота, Г = `depth·deep`),
  балок `B·N·2·sides` довжиною `bay_width`, зв'язок `2·B·sides`;
* полицевий (`shelf`, `S` секцій, `K` полиць): стійок `(S+1)·2·sides`, полиць `S·K·sides` (`cell_w × cell_d`, м²),
  зв'язок `S·sides`;
* консольний (`cantilever`, `A` секцій, `N` ярусів): стійок `(A+1)·sides`, консолей `(A+1)·N·sides` довжиною
  `arm_length`, зв'язок `A·sides`;
* стяжки двосторонніх рядів: у одного двостороннього стелажа `секцій+1` штук довжиною `gap_y` (не менше 0,05 м); для
  двох окремих стелажів «спина до спини» (зазор < 0,6 м, паралельні, спільна довжина ≥ 90 %) — `секцій+1` на пару.

Висота рами/стійки = висота місця (`building.slot_height`): сума ярусів (+0,15 м, якщо нижній ярус не на підлозі)
+ 0,25 м (палетний, консольний) або 0,1 м (полицевий).
"""

import math

from . import cells as cells_mod
from . import geometry as geo
from .building import SPACER_M, polygon_area, slot_height

RACK_TEMPLATES = ('pallet_rack', 'shelf', 'cantilever')
TEMPLATE_NAMES = {'pallet_rack': "Палетний стелаж", 'shelf': "Полицевий стелаж", 'cantilever': "Консольний стелаж"}
LINE_ORDER = ('frame', 'post', 'beam', 'console', 'shelf', 'brace', 'tie')
LINE_NAMES = {
    'frame': "Рама",
    'post': "Стійка",
    'beam': "Балка",
    'console': "Консоль",
    'shelf': "Полиця (настил)",
    'brace': "Зв'язки секції",
    'tie': "Стяжка двостороннього ряду",
}
MIN_TIE_M = 0.05
PAIR_OVERLAP = 0.9
PAIR_TOLERANCE_M = 0.001  # дотик країв (похибка обчислень) вважається зазором 0
COLUMNS = ["Позиція", "Типорозмір", "Од.", "К-сть", "Площа, м²"]
RACK_COLUMNS = ["Стелаж", "Зона", "Тип", "Позиція", "Типорозмір", "Од.", "К-сть", "Площа, м²"]


def _f2(value):
    """Число з двома знаками: округлення «половина вгору» (той самий результат у JS: `Math.floor(v·100 + 0.5)`)."""
    return '%.2f' % (math.floor(value * 100 + 0.5) / 100)


def _line(key, qty, size, w=None, d=None):
    """Рядок специфікації: `size` — підпис типорозміру (він же ключ групування), `w`, `d` — для площі полиць."""
    out = {'key': key, 'name': LINE_NAMES[key], 'size': size, 'unit': "шт.", 'qty': int(qty), 'area': None}
    if w is not None and d is not None:
        out['area'] = round(qty * w * d, 4)
    return out


def rack_lines(template, params):
    """(sides, sections, levels, height, lines) для стелажа; None — шаблон не стелаж."""
    if template not in RACK_TEMPLATES:
        return None
    p = cells_mod.normalize_params(template, params or {})
    sides = 2 if p.get('double_sided') else 1
    height = slot_height(template, p)
    gap = max(p.get('gap_y') or 0.0, MIN_TIE_M)
    lines = []
    if template == 'pallet_rack':
        bays, levels = p['bays'], p['levels']
        depth = p['depth'] * p.get('deep', 1)
        lines.append(_line('frame', (bays + 1) * sides, "%s × %s м" % (_f2(height), _f2(depth))))
        lines.append(_line('beam', bays * levels * 2 * sides, "%s м" % _f2(p['bay_width'])))
        lines.append(_line('brace', 2 * bays * sides, "%s м" % _f2(p['bay_width'])))
        sections = bays
    elif template == 'shelf':
        sections, levels = p['sections'], p['shelves']
        lines.append(_line('post', (sections + 1) * 2 * sides, "%s м" % _f2(height)))
        lines.append(
            _line(
                'shelf',
                sections * levels * sides,
                "%s × %s м" % (_f2(p['cell_w']), _f2(p['cell_d'])),
                p['cell_w'],
                p['cell_d'],
            )
        )
        lines.append(_line('brace', sections * sides, "%s м" % _f2(p['cell_w'])))
    else:
        sections, levels = p['arms'], p['levels']
        lines.append(_line('post', (sections + 1) * sides, "%s м" % _f2(height)))
        lines.append(_line('console', (sections + 1) * levels * sides, "%s м" % _f2(p['arm_length'])))
        lines.append(_line('brace', sections * sides, "%s м" % _f2(p['length'] / sections)))
    if sides == 2:
        lines.append(_line('tie', sections + 1, "%s м" % _f2(gap)))
    return sides, sections, levels, height, lines


def _zones(slots):
    out = []
    for slot in slots:
        if slot.get('template') != 'zone':
            continue
        try:
            poly = [tuple(p) for p in cells_mod.normalize_params('zone', slot.get('params') or {})['polygon']]
        except (cells_mod.CellsError, KeyError, TypeError):
            continue
        out.append(((slot.get('params') or {}).get('title') or slot.get('code_prefix') or '', poly, polygon_area(poly)))
    out.sort(key=lambda row: row[2])
    return out


def zone_name(zones, x, y):
    for title, poly, _area in zones:
        if geo.polygon_contains(poly, (x, y)):
            return title
    return ''


def _back_to_back(a, b):
    """Зазор між двома стелажами «спина до спини» (паралельні, спільна довжина ≥ 90 %) або None; a, b — OBB."""
    rel = (a['rot'] - b['rot']) % 180.0
    if min(rel, 180.0 - rel) > 1.0:
        return None
    dx, dy = geo.rotate(b['cx'] - a['cx'], b['cy'] - a['cy'], -a['rot'])
    overlap = min(a['a'], dx + b['a']) - max(-a['a'], dx - b['a'])
    if overlap < PAIR_OVERLAP * 2 * min(a['a'], b['a']):
        return None
    gap = abs(dy) - (a['b'] + b['b'])
    return gap if -PAIR_TOLERANCE_M <= gap < SPACER_M else None


def _code_key(row):
    return (row['code'], str(row.get('id')))


def build_spec(slots):
    """Специфікація стелажів: `slots` — місця (стелажі й зони для визначення зони); результат — словник:

    `racks` (рядки по стелажах), `pairs` (стяжки між окремими стелажами «спина до спини»), `totals` (за позицією й
    типорозміром), `types` (типорозміри стелажів), `summary`."""
    zones = _zones(slots)
    racks = []
    for slot in slots:
        calc = rack_lines(slot.get('template'), slot.get('params'))
        if calc is None:
            continue
        sides, sections, levels, height, lines = calc
        p = cells_mod.normalize_params(slot['template'], slot.get('params') or {})
        length, width = cells_mod.footprint(slot['template'], p)
        racks.append(
            {
                'id': slot.get('id'),
                'code': slot.get('code_prefix') or '',
                'zone': zone_name(zones, slot.get('x') or 0.0, slot.get('y') or 0.0),
                'template': slot['template'],
                'type': TEMPLATE_NAMES[slot['template']],
                'sides': sides,
                'sections': sections,
                'levels': levels,
                'size': "%s × %s × %s м" % (_f2(length), _f2(width), _f2(height)),
                'lines': lines,
                '_obb': cells_mod.slot_obb(
                    slot['template'], p, slot.get('x') or 0.0, slot.get('y') or 0.0, slot.get('rotation') or 0.0
                ),
            }
        )
    racks.sort(key=_code_key)
    pairs = []
    for i, ra in enumerate(racks):
        for rb in racks[i + 1 :]:
            if ra['template'] != rb['template']:
                continue
            gap = _back_to_back(ra['_obb'], rb['_obb'])
            if gap is None:
                continue
            count = min(ra['sections'], rb['sections']) + 1
            pairs.append(
                {
                    'codes': [ra['code'], rb['code']],
                    'zone': ra['zone'],
                    'lines': [_line('tie', count, "%s м" % _f2(max(gap, MIN_TIE_M)))],
                }
            )
    for rack in racks:
        del rack['_obb']
    totals = {}
    for rows in [r['lines'] for r in racks] + [p['lines'] for p in pairs]:
        for line in rows:
            key = (line['key'], line['size'])
            cur = totals.setdefault(
                key,
                {
                    'key': line['key'],
                    'name': line['name'],
                    'size': line['size'],
                    'unit': line['unit'],
                    'qty': 0,
                    'area': None,
                },
            )
            cur['qty'] += line['qty']
            if line['area'] is not None:
                cur['area'] = round((cur['area'] or 0.0) + line['area'], 4)
    ordered = sorted(totals.values(), key=lambda t: (LINE_ORDER.index(t['key']), t['size']))
    types = {}
    for rack in racks:
        key = (rack['template'], rack['size'], rack['sections'], rack['levels'], rack['sides'])
        cur = types.setdefault(
            key,
            {
                'type': rack['type'],
                'size': rack['size'],
                'sections': rack['sections'],
                'levels': rack['levels'],
                'sides': rack['sides'],
                'count': 0,
            },
        )
        cur['count'] += 1
    summary = {'racks': len(racks), 'pairs': len(pairs)}
    for key in LINE_ORDER:
        summary[key] = sum(t['qty'] for t in ordered if t['key'] == key)
    summary['shelf_area'] = round(sum(t['area'] or 0.0 for t in ordered if t['key'] == 'shelf'), 4)
    return {
        'racks': racks,
        'pairs': pairs,
        'totals': ordered,
        'types': sorted(types.values(), key=lambda t: (t['type'], t['size'], t['sections'], t['levels'], t['sides'])),
        'summary': summary,
    }


def tables(spec):
    """Таблиці для PDF/XLSX: [{name, columns, rows}] — «Специфікація» (по стелажах), «Підсумок», «Типорозміри»."""
    detail = []
    for rack in spec['racks']:
        for line in rack['lines']:
            detail.append(
                [
                    rack['code'],
                    rack['zone'],
                    rack['type'],
                    line['name'],
                    line['size'],
                    line['unit'],
                    line['qty'],
                    line['area'],
                ]
            )
    for pair in spec['pairs']:
        for line in pair['lines']:
            detail.append(
                [
                    " + ".join(pair['codes']),
                    pair['zone'],
                    "Пара «спина до спини»",
                    line['name'],
                    line['size'],
                    line['unit'],
                    line['qty'],
                    line['area'],
                ]
            )
    total = [[t['name'], t['size'], t['unit'], t['qty'], t['area']] for t in spec['totals']]
    kinds = [
        [
            t['type'],
            t['size'],
            "%d × %d%s" % (t['sections'], t['levels'], ", двосторонній" if t['sides'] == 2 else ""),
            t['count'],
        ]
        for t in spec['types']
    ]
    return [
        {'name': "Специфікація", 'columns': RACK_COLUMNS, 'rows': detail},
        {'name': "Підсумок", 'columns': COLUMNS, 'rows': total},
        {
            'name': "Типорозміри",
            'columns': ["Тип", "Габарит (Д × Г × В)", "Секцій × ярусів", "Стелажів"],
            'rows': kinds,
        },
    ]


def spec_slots(state):
    """Місця зі стану API-03 (`checks_state`): стелажі й зони."""
    return [s for s in state.get('slots') or [] if s.get('template') in RACK_TEMPLATES or s.get('template') == 'zone']


# --- золоті фікстури -------------------------------------------------------------------------------------------------
_CASE_SLOTS = [
    {
        'id': 1,
        'template': 'zone',
        'code_prefix': 'Z1',
        'x': 0,
        'y': 0,
        'rotation': 0,
        'params': {'polygon': [[0, 0], [30, 0], [30, 20], [0, 20]], 'title': 'Зона А'},
    },
    {
        'id': 2,
        'template': 'pallet_rack',
        'code_prefix': 'R1',
        'x': 10,
        'y': 5,
        'rotation': 0,
        'params': {'bays': 4, 'levels': 3, 'bay_width': 2.7, 'depth': 1.1, 'level_height': 1.5},
    },
    {
        'id': 3,
        'template': 'pallet_rack',
        'code_prefix': 'R2',
        'x': 10,
        'y': 6.3,
        'rotation': 0,
        'params': {'bays': 4, 'levels': 3, 'bay_width': 2.7, 'depth': 1.1, 'level_height': 1.5},
    },
    {
        'id': 4,
        'template': 'pallet_rack',
        'code_prefix': 'R3',
        'x': 10,
        'y': 12,
        'rotation': 0,
        'params': {
            'bays': 2,
            'levels': 5,
            'bay_width': 2.7,
            'depth': 1.1,
            'level_height': 1.5,
            'double_sided': True,
            'gap_y': 0.2,
            'deep': 2,
        },
    },
    {
        'id': 5,
        'template': 'shelf',
        'code_prefix': 'S1',
        'x': 40,
        'y': 5,
        'rotation': 0,
        'params': {'sections': 3, 'shelves': 5, 'cell_w': 0.9, 'cell_d': 0.4, 'cell_h': 0.4},
    },
    {
        'id': 6,
        'template': 'shelf',
        'code_prefix': 'S2',
        'x': 40,
        'y': 5.4,
        'rotation': 0,
        'params': {'sections': 3, 'shelves': 5, 'cell_w': 0.9, 'cell_d': 0.4, 'cell_h': 0.4},
    },
    {
        'id': 7,
        'template': 'cantilever',
        'code_prefix': 'C1',
        'x': 45,
        'y': 15,
        'rotation': 90,
        'params': {'arms': 4, 'levels': 3, 'arm_length': 1.0, 'length': 6.0, 'level_height': 1.2, 'double_sided': True},
    },
    {
        'id': 8,
        'template': 'floor_stack',
        'code_prefix': 'F1',
        'x': 5,
        'y': 25,
        'rotation': 0,
        'params': {'rows': 1, 'cols': 2},
    },
    {
        'id': 9,
        'template': 'pallet_rack',
        'code_prefix': 'R4',
        'x': 12,
        'y': 25,
        'rotation': 0,
        'params': {
            'bays': 3,
            'levels': 2,
            'bay_width': 2.7,
            'depth': 1.1,
            'level_height': 1.5,
            'bottom_on_floor': False,
            'level_heights': [1.2, 1.8],
        },
    },
]


def golden_cases():
    """Еталон специфікації для ядра (JS): вхідні місця й результат `build_spec` (без внутрішніх полів)."""
    spec = build_spec(_CASE_SLOTS)
    return {
        'slots': _CASE_SLOTS,
        'spec': spec,
        'tables': tables(spec),
        'finite': all(math.isfinite(t['qty']) for t in spec['totals']),
    }
