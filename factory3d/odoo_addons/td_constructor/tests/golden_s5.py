"""Золоті фікстури слайса S5 (F18 будівля й проходи, N-06 техніка, N-07 перевірки, F15 специфікація): Python ↔ JS.

    python3 factory3d/odoo_addons/td_constructor/tests/golden_s5.py --write   # перегенерувати fixtures/s5_golden.json

`static/tests/fixtures/s5_golden.json` будує ЦЕЙ файл із чистих сервісів (без Odoo); тест `test_s5_checks` стежить, щоб
файл не розійшовся з кодом, а `node tools/test_core_s5.mjs` звіряє з ним ядро (JS): перевірки `inside` / `aisle_width` /
`height`, об'єкти будівлі, техніку, специфікацію стелажів."""

import json
import sys
from pathlib import Path

try:
    from ..services import building, cells, checks, checks_building, rack_spec  # noqa: F401
    from ..services.schemas import SchemaError
except ImportError:  # запуск як скрипта: пакет td_constructor без Odoo
    import types

    ROOT = Path(__file__).resolve().parents[1]
    pkg = types.ModuleType('td_constructor')
    pkg.__path__ = [str(ROOT)]
    sub = types.ModuleType('td_constructor.services')
    sub.__path__ = [str(ROOT / 'services')]
    sys.modules.update({'td_constructor': pkg, 'td_constructor.services': sub})
    from td_constructor.services import building, cells, checks, checks_building, rack_spec  # noqa: E402, F401
    from td_constructor.services.schemas import SchemaError  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / 'static' / 'tests' / 'fixtures'
NAME = 's5_golden'
PREC = 6
EPS_M = 0.001


def _round(value):
    if isinstance(value, float):
        value = round(value, PREC)
        return 0.0 if value == 0 else value
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    return value


# --- сцени перевірок ---------------------------------------------------------------------------------------------
L_CONTOUR = [[0, 0], [40, 0], [40, 15], [20, 15], [20, 30], [0, 30]]
RACK2 = {'bays': 2, 'levels': 3, 'bay_width': 2.7, 'depth': 1.1, 'level_height': 1.5}  # 5.4 × 1.1 м, висота 4.75 м
VARIANT = {
    'id': 1,
    'length': 2000,
    'width': 1000,
    'height': 1500,
    'service': {'front': 0, 'back': 0, 'left': 0, 'right': 0},
    'rotations': 'any',
    'layer_kinds': [],
    'slot_types': [],
    'utilities': [],
    'weight_kg': 0,
    'floor_load': 0,
    'anchor': 'center',
    'front_side': 's',
}


def _layer(lid, kind, name, **kw):
    out = {
        'id': lid,
        'name': name,
        'kind': kind,
        'elevation': 0.0,
        'max_floor_load': 0.0,
        'bounds': None,
        'slot_types': [],
        'aisles': [],
        'fire_paths': [],
        'utilities': [],
        'items': [],
    }
    out.update(kw)
    return out


def _item(iid, kind, x, y, w=None, d=None, rot=0, **kw):
    dw, dd = building.ITEM_DEFAULT_SIZE[kind]
    out = {'id': iid, 'kind': kind, 'name': kw.pop('name', ''), 'x': x, 'y': y, 'w': w or dw, 'd': d or dd, 'rot': rot}
    out.update(kw)
    return out


def _slot(sid, template, prefix, x, y, rot=0, params=None, layer_id=2, **kw):
    out = {
        'id': sid,
        'uid': 'u%d' % sid,
        'layer_id': layer_id,
        'template': template,
        'code_prefix': prefix,
        'x': x,
        'y': y,
        'rotation': rot,
        'params': dict(params or {}),
        'overrides': {},
        'tech': None,
    }
    out.update(kw)
    return out


def _zone(sid, title, x0, y0, x1, y1, tech=None):
    return _slot(
        sid,
        'zone',
        'Z%d' % sid,
        0,
        0,
        0,
        {'polygon': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], 'title': title},
        layer_id=2,
        tech=tech,
    )


def _state(layers, slots, placements=(), height=8.0, sprinkler=6.0, tech='reach', grid=None):
    site = {
        'building': {'length': 60.0, 'width': 30.0, 'height': height},
        'sprinkler_height': sprinkler,
        'aisle_tech': tech,
    }
    if grid is not None:  # без ключа — «сітка не задана» (старі сцени еталона)
        site['column_grid'] = dict(grid)
    return {
        'site': site,
        'layers': layers,
        'slots': slots,
        'placements': list(placements),
        'variants': [dict(VARIANT)],
    }


def _cfg(*keys, mode='block'):
    return [{'check': key, 'enabled': True, 'mode': mode, 'params': {}} for key in keys]


def scenes():
    out = []
    # 1. контур-многокутник: місця поза Г-подібним контуром
    out.append(
        (
            'inside_contour',
            _state(
                [_layer(1, 'building', "Будівля", bounds=L_CONTOUR), _layer(2, 'storage', "Склади")],
                [
                    _slot(1, 'pallet_rack', 'IN1', 10, 8, params=RACK2),
                    _slot(2, 'pallet_rack', 'OUT1', 30, 22, params=RACK2),
                    _slot(3, 'pallet_rack', 'EDGE', 20, 15, params=RACK2),
                    _slot(4, 'pallet_rack', 'IN2', 10, 25, params=RACK2),
                    _slot(5, 'zone', 'ZN', 0, 0, params={'polygon': [[30, 20], [38, 20], [38, 28], [30, 28]]}),
                ],
                [
                    {
                        'id': 1,
                        'layer_id': 2,
                        'variant_id': 1,
                        'slot_id': None,
                        'cell_code': None,
                        'code': 'M-OUT',
                        'name': 'm',
                        'x': 35.0,
                        'y': 25.0,
                        'rotation': 0,
                        'dynamic': False,
                    },
                    {
                        'id': 2,
                        'layer_id': 2,
                        'variant_id': 1,
                        'slot_id': None,
                        'cell_code': None,
                        'code': 'M-IN',
                        'name': 'm',
                        'x': 5.0,
                        'y': 5.0,
                        'rotation': 0,
                        'dynamic': False,
                    },
                    {
                        'id': 3,
                        'layer_id': 2,
                        'variant_id': 1,
                        'slot_id': None,
                        'cell_code': None,
                        'code': 'P-OUT',
                        'name': 'p',
                        'x': 35.0,
                        'y': 25.0,
                        'rotation': 0,
                        'dynamic': True,
                    },
                ],
            ),
            _cfg('inside'),
        )
    )
    # 2. перетин з об'єктами будівлі (колона, стіна під 90°, офіс, зарядка; ворота — проріз, не перешкода)
    items = [
        _item('c1', 'column', 10, 5, name='К-1'),
        _item('w1', 'wall', 30, 5, w=10, d=0.3, rot=90, name='Стіна А'),
        _item('o1', 'office', 45, 10, name='Офіс'),
        _item('g1', 'gate', 10, 1.5),
        _item('ch1', 'charger', 50, 25),
        _item('wd', 'wall', 20, 24, w=8, d=0.2, rot=45),
    ]
    out.append(
        (
            'inside_items',
            _state(
                [
                    _layer(1, 'building', "Будівля", items=items),
                    _layer(2, 'storage', "Склади"),
                    _layer(3, 'yard', "Двір"),
                ],
                [
                    _slot(1, 'pallet_rack', 'RC', 10.2, 5, params=RACK2),
                    _slot(2, 'pallet_rack', 'RW', 30, 5, params=RACK2),
                    _slot(3, 'pallet_rack', 'RO', 45, 10, params=RACK2),
                    _slot(4, 'pallet_rack', 'RG', 10, 1.5, params=RACK2),
                    _slot(5, 'pallet_rack', 'RK', 20, 12, params=RACK2),
                    _slot(6, 'pallet_rack', 'RCH', 50, 25.3, params=RACK2),
                    _slot(7, 'pallet_rack', 'RD', 20, 24, params=RACK2),
                    _slot(8, 'floor_stack', 'YARD', 10, 5, params={'rows': 1, 'cols': 1}, layer_id=3),
                ],
                [
                    {
                        'id': 1,
                        'layer_id': 2,
                        'variant_id': 1,
                        'slot_id': None,
                        'cell_code': None,
                        'code': 'M-COL',
                        'name': 'm',
                        'x': 10.0,
                        'y': 5.0,
                        'rotation': 0,
                        'dynamic': False,
                    },
                ],
            ),
            _cfg('inside', mode='warn'),
        )
    )
    # 2а. колони сітки `site.column_grid` (не items): стелаж у вузлі сітки, під 90°, під явною колоною (без дубля),
    # біля колони без дотику; шар двору не перевіряється; крок 0 (сітки немає) — лише явна колона
    grid_slots = [
        _slot(1, 'pallet_rack', 'GN', 12, 6, params=RACK2),
        _slot(2, 'pallet_rack', 'GFREE', 12, 9, params=RACK2),
        _slot(3, 'pallet_rack', 'GEXP', 24, 12, params=RACK2),
        _slot(4, 'pallet_rack', 'GROT', 30, 18, rot=90, params=RACK2),
        _slot(5, 'pallet_rack', 'GNEAR', 36, 6.9, params=RACK2),
        _slot(6, 'floor_stack', 'GYARD', 12, 12, params={'rows': 1, 'cols': 1}, layer_id=3),
    ]
    grid_layers = [
        _layer(1, 'building', "Будівля", items=[_item('c1', 'column', 24, 12, name='К-1')]),
        _layer(2, 'storage', "Склади"),
        _layer(3, 'yard', "Двір"),
    ]
    grid_placement = {
        'id': 1,
        'layer_id': 2,
        'variant_id': 1,
        'slot_id': None,
        'cell_code': None,
        'code': 'M-GRID',
        'name': 'm',
        'x': 42.0,
        'y': 24.0,
        'rotation': 0,
        'dynamic': False,
    }
    out.append(
        (
            'inside_grid',
            _state(grid_layers, grid_slots, [grid_placement], grid={'step_x': 6.0, 'step_y': 6.0}),
            _cfg('inside'),
        )
    )
    out.append(
        (
            'inside_grid_off',
            _state(grid_layers, grid_slots, [grid_placement], grid={'step_x': 0.0, 'step_y': 0.0}),
            _cfg('inside'),
        )
    )
    # 3. ширина проходів за технікою складу й зон (N-06)
    aisles = [
        {'id': 'a1', 'name': 'Вузький', 'x0': 0, 'y0': 0, 'x1': 30, 'y1': 2.0},
        {'id': 'a2', 'name': 'Достатній', 'x0': 0, 'y0': 4, 'x1': 30, 'y1': 7.0},
        {'id': 'a3', 'name': 'У зоні візків 1.0', 'x0': 40, 'y0': 2, 'x1': 41.0, 'y1': 12},
        {'id': 'a4', 'name': 'У зоні візків 1.5', 'x0': 42, 'y0': 2, 'x1': 43.5, 'y1': 12},
        {'id': 'a5', 'name': 'У зоні без перевірки', 'x0': 50, 'y0': 2, 'x1': 50.5, 'y1': 12},
        {'id': 'a6', 'name': 'У зоні 3.5', 'x0': 40, 'y0': 16, 'x1': 43.0, 'y1': 26},
        {'id': 'a7', 'name': 'Вкладена зона', 'x0': 54, 'y0': 16, 'x1': 55.0, 'y1': 26},
    ]
    out.append(
        (
            'aisle_width_aisles',
            _state(
                [_layer(1, 'building', "Будівля", aisles=aisles), _layer(2, 'storage', "Склади")],
                [
                    _zone(1, 'Візки', 38, 0, 46, 14, tech='hand'),
                    _zone(2, 'Без перевірки', 48, 0, 52, 14, tech='none'),
                    _zone(3, 'Свій мінімум', 38, 15, 46, 28, tech='custom:3.5'),
                    _zone(4, 'Велика', 52, 15, 60, 28, tech='stacker'),
                    _zone(5, 'Вкладена без техніки', 53, 17, 56, 27),
                ],
            ),
            _cfg('aisle_width', mode='warn'),
        )
    )
    # 4. проїзди між рядами: вузький, «спина до спини», достатній, ряд між рядами, поворот 90°
    big = dict(RACK2, bays=4)  # 10.8 × 1.1 м
    out.append(
        (
            'aisle_width_rows',
            _state(
                [_layer(1, 'building', "Будівля"), _layer(2, 'storage', "Склади")],
                [
                    _slot(1, 'pallet_rack', 'A1', 10, 3, params=big),
                    _slot(2, 'pallet_rack', 'A2', 10, 5.5, params=big),  # зазор 1.4 < 2.8
                    _slot(3, 'pallet_rack', 'B1', 10, 12, params=big),
                    _slot(4, 'pallet_rack', 'B2', 10, 13.3, params=big),  # зазор 0.2: спина до спини
                    _slot(5, 'pallet_rack', 'C1', 10, 20, params=big),
                    _slot(6, 'pallet_rack', 'C2', 10, 24.5, params=big),  # зазор 3.4 ≥ 2.8
                    _slot(7, 'pallet_rack', 'D1', 35, 3, params=big),
                    _slot(8, 'pallet_rack', 'D2', 35, 4.9, params=dict(big, depth=0.4)),  # між D1 і D3 — D2
                    _slot(9, 'pallet_rack', 'D3', 35, 6.3, params=big),
                    _slot(10, 'pallet_rack', 'E1', 50, 3, 90, params=big),  # поворот 90°: ряд уздовж Y
                    _slot(11, 'pallet_rack', 'E2', 52.5, 3, 90, params=big),  # зазор 1.4 < 2.8
                    _slot(12, 'pallet_rack', 'F1', 25, 20, 30, params=big),
                    _slot(13, 'pallet_rack', 'F2', 25, 22.4, 120, params=big),  # неперпендикулярні не розглядаються
                ],
            ),
            _cfg('aisle_width'),
        )
    )
    # 5. висота до стелі й спринклерів
    out.append(
        (
            'height',
            _state(
                [
                    _layer(1, 'building', "Будівля"),
                    _layer(2, 'storage', "Склади"),
                    _layer(3, 'engineering', "Мережі", elevation=6.0),
                    _layer(4, 'custom', "Антресоль", elevation=3.0),
                ],
                [
                    _slot(1, 'pallet_rack', 'H4', 10, 5, params=dict(RACK2, levels=4)),  # 6.25 м > 6.0 − 0.5
                    _slot(2, 'pallet_rack', 'H2', 20, 5, params=dict(RACK2, levels=2)),  # 3.25 м
                    _slot(3, 'pallet_rack', 'H5', 30, 5, params=dict(RACK2, levels=5, level_height=2.0)),  # 10.25 м
                    _slot(4, 'pallet_rack', 'HM', 40, 5, params=dict(RACK2, levels=3, level_heights=[1.0, 1.0, 3.0])),
                    _slot(5, 'shelf', 'SH', 10, 15, params={'sections': 2, 'shelves': 5, 'cell_h': 1.0}),
                    _slot(6, 'floor_stack', 'FS', 20, 15, params={'rows': 1, 'cols': 1, 'max_height': 6.0}),
                    _slot(
                        7, 'pallet_rack', 'EN', 30, 15, params=dict(RACK2, levels=2), layer_id=3
                    ),  # на інж. шарі не перевіряється
                    _slot(
                        8, 'pallet_rack', 'MZ', 40, 15, params=dict(RACK2, levels=2), layer_id=4
                    ),  # 3.0 + 3.25 = 6.25
                    _slot(9, 'pallet_rack', 'NB', 50, 15, params=dict(RACK2, levels=3, bottom_on_floor=False)),
                ],
                [
                    {
                        'id': 1,
                        'layer_id': 2,
                        'variant_id': 1,
                        'slot_id': None,
                        'cell_code': None,
                        'code': 'M-TALL',
                        'name': 'm',
                        'x': 5.0,
                        'y': 25.0,
                        'rotation': 0,
                        'dynamic': False,
                    },
                ],
            ),
            _cfg('height'),
        )
    )
    # 6. без спринклерів і без техніки: перевірки мовчать
    out.append(
        (
            'quiet',
            _state(
                [
                    _layer(
                        1,
                        'building',
                        "Будівля",
                        aisles=[{'id': 'a1', 'name': 'Вузький', 'x0': 0, 'y0': 0, 'x1': 30, 'y1': 0.5}],
                    ),
                    _layer(2, 'storage', "Склади"),
                ],
                [_slot(1, 'pallet_rack', 'Q1', 10, 3, params=big), _slot(2, 'pallet_rack', 'Q2', 10, 5.5, params=big)],
                sprinkler=0.0,
                tech=None,
            ),
            _cfg('aisle_width', 'height', 'inside', mode='warn'),
        )
    )
    return out


def _expected(state, configs):
    return [
        {'check': i['check'], 'severity': i['severity'], 'codes': i['codes']}
        for i in checks.run_checks(state, configs, EPS_M)
    ]


def checks_cases():
    return [
        {'name': name, 'state': state, 'configs': configs, 'expected': _expected(state, configs)}
        for name, state, configs in scenes()
    ]


# --- об'єкти й техніка ----------------------------------------------------------------------------------------------
def item_cases():
    good = [
        {'id': 'c1', 'kind': 'column', 'x': 1, 'y': 2, 'w': 0.4, 'd': 0.4},
        {'id': 'w1', 'kind': 'wall', 'name': 'Стіна', 'x': 5, 'y': 5, 'w': 8, 'th': 0.3, 'rot': 30},
        {'id': 'g1', 'kind': 'gate', 'x': 0, 'y': 10, 'w': 3.5, 'd': 0.3, 'rot': 90, 'location_uid': 'LOC-1'},
        {'id': 'o1', 'kind': 'office', 'x': 20, 'y': 20, 'w': 6, 'd': 4, 'location_uid': 'ignored', 'h': 3},
    ]
    bad = [
        ("не список", {'id': 'x'}),
        ("повторний id", [good[0], dict(good[0])]),
        ("вид", [dict(good[0], kind='tree')]),
        ("розмір", [dict(good[0], w=0)]),
        ("координата", [dict(good[0], x='1')]),
        ("довге ім'я", [dict(good[0], name='x' * 65)]),
        ("висота", [dict(good[3], h=-1)]),
    ]
    cases = {'good': good, 'normalized': building.normalize_items(good), 'bad': []}
    for label, value in bad:
        try:
            building.normalize_items(value)
        except SchemaError as exc:
            cases['bad'].append({'label': label, 'value': value, 'error': str(exc)})
        else:
            raise AssertionError(label)
    return cases


def tech_cases():
    values = [
        None,
        '',
        'reach',
        'hand',
        'forklift',
        'vna',
        'stacker',
        'none',
        'custom',
        'custom:3.2',
        'custom:abc',
        'reach:2.5',
        'reach:-1',
        'xyz',
    ]
    return [{'value': v, 'min': building.tech_min(v), 'label': building.tech_label(v)} for v in values]


def contour_cases():
    return [
        {'points': pts, 'area': building.polygon_area(pts), 'perimeter': building.polygon_perimeter(pts)}
        for pts in (L_CONTOUR, [[0, 0], [10, 0], [10, 5], [0, 5]], [[0, 0], [4, 0], [0, 3]])
    ]


def spec_cases():
    return rack_spec.golden_cases()


def build():
    """{ім'я файла без розширення: JSON-значення}."""
    data = {
        'meta': {'eps_m': EPS_M},
        'scenes': checks_cases(),
        'items': item_cases(),
        'tech': tech_cases(),
        'contours': contour_cases(),
        'spec': spec_cases(),
    }
    return {NAME: _round(data)}


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + '\n'


if __name__ == '__main__':
    if '--write' in sys.argv:
        for fname, data in build().items():
            (FIXTURES / (fname + '.json')).write_text(dump(data), encoding='utf-8')
            print('записано', fname)
    else:
        print("Використання: golden_s5.py --write")
