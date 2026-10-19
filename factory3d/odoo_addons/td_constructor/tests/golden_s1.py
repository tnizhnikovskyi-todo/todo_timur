"""Золоті фікстури слайса S1 (F01 адресація, F08 нові генератори): Python ↔ JS.

    python3 factory3d/odoo_addons/td_constructor/tests/golden_s1.py --write   # перегенерувати fixtures/*.json

`static/tests/fixtures/addr_golden.json` і `cells_s1_golden.json` будує ЦЕЙ файл із чистих сервісів (без Odoo);
тест `test_s1_golden` стежить, щоб файли не розійшлися з кодом, а `node tools/test_core.mjs` звіряє з ними ядро (JS)."""

import json
import sys
from pathlib import Path

try:
    from ..services import addr, cells
except ImportError:  # запуск як скрипта: пакет td_constructor без Odoo
    import types

    ROOT = Path(__file__).resolve().parents[1]
    pkg = types.ModuleType('td_constructor')
    pkg.__path__ = [str(ROOT)]
    sub = types.ModuleType('td_constructor.services')
    sub.__path__ = [str(ROOT / 'services')]
    sys.modules.update({'td_constructor': pkg, 'td_constructor.services': sub})
    from td_constructor.services import addr, cells  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / 'static' / 'tests' / 'fixtures'
PREC = 6


def _round(value):
    """Числа в JSON — з округленням до 6 знаків (той самий допуск у Python і JS), -0.0 → 0.0."""
    if isinstance(value, float):
        value = round(value, PREC)
        return 0.0 if value == 0 else value
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    return value


# --- cells_s1_golden ---------------------------------------------------------------------------------------
RACK = {'bays': 3, 'levels': 3, 'bay_width': 2.7, 'depth': 1.1, 'level_height': 1.5, 'positions_per_bay': 3}
FULL = addr.normalize_addr({'tpl': addr.DEFAULT_TPL})


def _ctx(**kw):
    base = {'addr': FULL, 'zone': None, 'row': 1, 'spot': None, 'depth_mode': 'level'}
    base.update(kw)
    return base


def cell_cases():
    cases = [
        (
            'rack_deep2_double',
            'pallet_rack',
            'A-R1',
            10,
            4,
            0,
            dict(RACK, deep=2, double_sided=True, gap_x=0.1, gap_y=0.3),
            None,
            0.0,
        ),
        (
            'rack_levels_lift_beam',
            'pallet_rack',
            'A-R2',
            0,
            0,
            90,
            dict(RACK, level_heights=[1.2, 1.6], bottom_on_floor=False, beam_th=0.1),
            None,
            3.0,
        ),
        (
            'rack_overrides_disabled',
            'pallet_rack',
            'A-R3',
            1,
            1,
            0,
            dict(RACK, code_style='bay_letter'),
            {'A-R3-01A': {'disabled': True}},
            0.0,
        ),
        (
            'shelf_double_heights',
            'shelf',
            'SH1',
            5,
            5,
            180,
            {'sections': 2, 'shelves': 3, 'double_sided': True, 'gap_y': 0.2, 'level_heights': [0.3, 0.4]},
            None,
            0.0,
        ),
        (
            'cantilever_double',
            'cantilever',
            'CL1',
            0,
            0,
            270,
            {'arms': 2, 'levels': 2, 'double_sided': True, 'gap_y': 0.1, 'beam_th': 0.05},
            None,
            0.0,
        ),
        (
            'floor_stack_gaps',
            'floor_stack',
            'ST1',
            2,
            2,
            0,
            {'rows': 2, 'cols': 3, 'gap_x': 0.2, 'gap_y': 0.4, 'loc_kind': 'area'},
            None,
            0.0,
        ),
        ('floor_spot_default', 'floor_spot', 'BF-IN', 7, 8, 0, {}, None, 0.0),
        (
            'floor_spot_custom',
            'floor_spot',
            'CELL1',
            3,
            3,
            90,
            {
                'length': 4.0,
                'width': 3.0,
                'height': 2.4,
                'loc_kind': 'stack',
                'capacity': 6,
                'max_load_kg': 5000,
                'shape': 'fence',
            },
            None,
            1.0,
        ),
        (
            'rack_depth_cell_3',
            'pallet_rack',
            'A-R4',
            0,
            0,
            0,
            dict(RACK, cells_per_level=3),
            None,
            0.0,
            _ctx(addr=None, depth_mode='cell'),
        ),
        ('rack_addr_default', 'pallet_rack', 'A-R5', 0, 0, 0, RACK, None, 0.0, _ctx(zone='B', row=2)),
        (
            'rack_addr_rot90_snake',
            'pallet_rack',
            'A-R5',
            0,
            0,
            90,
            RACK,
            None,
            0.0,
            _ctx(
                addr=addr.normalize_addr(
                    {'tpl': '{prefix} {bay}{level}', 'seg': {'level': {'kind': 'alpha'}}, 'row_mode': 'snake'}
                ),
                row=2,
            ),
        ),
        (
            'rack_addr_odd_even_double',
            'pallet_rack',
            'A-R6',
            0,
            0,
            0,
            dict(RACK, double_sided=True),
            None,
            0.0,
            _ctx(
                addr=addr.normalize_addr({'tpl': '{zone} {row} {bay} {level}', 'bay_dir': 'odd_even'}), zone='A', row=3
            ),
        ),
        (
            'rack_addr_level_down_cell',
            'pallet_rack',
            'A-R7',
            0,
            0,
            180,
            dict(RACK, cells_per_level=2),
            None,
            0.0,
            _ctx(
                addr=addr.normalize_addr({'tpl': '{row} {bay} {level} {pos}', 'level_dir': 'down', 'bay_dir': 'rtl'}),
                depth_mode='cell',
            ),
        ),
        ('shelf_addr', 'shelf', 'SH2', 0, 0, 0, {'sections': 2, 'shelves': 2}, None, 0.0, _ctx(zone='Z1', row=4)),
        ('floor_stack_addr', 'floor_stack', 'ST2', 0, 0, 0, {'rows': 2, 'cols': 2}, None, 0.0, _ctx(zone='A', row=1)),
        (
            'floor_spot_addr_pos',
            'floor_spot',
            'FS1',
            0,
            0,
            0,
            {},
            None,
            0.0,
            _ctx(addr=addr.normalize_addr({'tpl': '{zone} {pos}', 'sep': '.'}), zone='A', row=None, spot=7),
        ),
        ('floor_spot_addr_row_first', 'floor_spot', 'FS2', 0, 0, 0, {}, None, 0.0, _ctx(zone=None, row=None, spot=3)),
    ]
    out = []
    for name, template, prefix, x, y, rot, params, overrides, elevation, *rest in cases:
        ctx = rest[0] if rest else None
        got = cells.generate_cells(template, prefix, x, y, rot, params, overrides, elevation, ctx)
        length, width = cells.footprint(template, params)
        out.append(
            _round(
                {
                    'name': name,
                    'template': template,
                    'prefix': prefix,
                    'x': x,
                    'y': y,
                    'rot': rot,
                    'params': params,
                    'overrides': overrides,
                    'elevation': elevation,
                    'ctx': ctx,
                    'footprint': {'l': length, 'w': width},
                    'cells': got,
                }
            )
        )
    return {
        'meta': {'tolerance': 1e-5, 'about': "S1: нові генератори, параметри й адресація; еталон — Python"},
        'cases': out,
    }


# --- addr_golden -------------------------------------------------------------------------------------------
def _rect_zone(uid, x, y, length, width, addr_value=None, **extra):
    return dict(
        {
            'uid': uid,
            'layer_id': 1,
            'template': 'zone',
            'code_prefix': uid,
            'x': x,
            'y': y,
            'rotation': 0,
            'params': {'length': length, 'width': width},
            'addr': addr_value or {},
        },
        **extra,
    )


def _poly_zone(uid, poly, addr_value=None, **extra):
    return dict(
        {
            'uid': uid,
            'layer_id': 1,
            'template': 'zone',
            'code_prefix': uid,
            'x': 0,
            'y': 0,
            'rotation': 0,
            'params': {'polygon': poly},
            'addr': addr_value or {},
        },
        **extra,
    )


def _slot(uid, template, prefix, x, y, rot=0, params=None, addr_value=None, **extra):
    return dict(
        {
            'uid': uid,
            'layer_id': 1,
            'template': template,
            'code_prefix': prefix,
            'x': x,
            'y': y,
            'rotation': rot,
            'params': params or {},
            'addr': addr_value or {},
        },
        **extra,
    )


def scenes():
    rack = {'bays': 2, 'levels': 2}
    return [
        {
            'name': 'без адресації: legacy',
            'site_addr': {},
            'slots': [_slot('s1', 'pallet_rack', 'AB-R1', 0, 0, 0, rack), _slot('s2', 'floor_spot', 'DOCK', 9, 9)],
        },
        {
            'name': 'площадка: ряди за Y, дві зони, закріплений номер',
            'site_addr': {'tpl': '{zone} {row} {bay} {level}', 'row_from': 'up'},
            'slots': [
                _rect_zone('zA', 0, 0, 20, 20),
                _poly_zone('zB', [[30, 0], [50, 0], [50, 20], [30, 20]], {'zone_code': 'X1'}),
                _slot('r1', 'pallet_rack', 'P1', 5, 12, 0, rack),
                _slot('r2', 'pallet_rack', 'P2', 5, 3, 0, rack),
                _slot('r3', 'shelf', 'P3', 5, 7, 0, {'sections': 2, 'shelves': 2}, {'row_no': 5}),
                _slot('r4', 'pallet_rack', 'P4', 40, 10, 90, rack),
                _slot('f1', 'floor_spot', 'FS1', 38, 15),
                _slot('f2', 'floor_spot', 'FS2', 38, 5),
                _slot('r5', 'pallet_rack', 'P5', 100, 100, 0, rack),
            ],
        },
        {
            'name': 'власні налаштування зони, вкладена зона, глибина «комірка»',
            'site_addr': {'tpl': '{row} {bay} {level}', 'sep': '/'},
            'site_depth_mode': 'level',
            'slots': [
                _rect_zone('zOuter', 0, 0, 40, 40),
                _rect_zone(
                    'zInner',
                    0,
                    0,
                    10,
                    10,
                    {'tpl': '{prefix} {bay}{level} {pos}', 'seg': {'level': {'kind': 'alpha'}}},
                    depth_mode='cell',
                ),
                _slot('a', 'pallet_rack', 'IN1', 1, 1, 0, dict(rack, cells_per_level=2)),
                _slot('b', 'pallet_rack', 'OUT1', 15, 15, 0, rack),
                _slot('c', 'pallet_rack', 'OWN', 1, 2, 0, rack, {'tpl': '{level} {bay}', 'sep': '', 'bay_dir': 'rtl'}),
            ],
        },
        {
            'name': 'напрями рядів: right, повернуті місця',
            'site_addr': {'tpl': '{row} {bay} {level} {pos}', 'row_from': 'right', 'row_mode': 'snake'},
            'slots': [
                _slot('p1', 'pallet_rack', 'Q1', 10, 0, 0, rack),
                _slot('p2', 'pallet_rack', 'Q2', 5, 0, 270, rack),
                _slot('p3', 'pallet_rack', 'Q3', 0, 0, 180, rack),
                _slot('p4', 'floor_stack', 'Q4', -5, 0, 90, {'rows': 2, 'cols': 2}),
            ],
        },
    ]


def addr_golden():
    spec_num = {'kind': 'num', 'width': 3, 'start': 0}
    spec_alpha = {'kind': 'alpha', 'width': 1, 'start': 1}
    fmt = [
        {'spec': spec_num, 'n': 1, 'expected': '000'},
        {'spec': spec_num, 'n': 12, 'expected': '011'},
        {'spec': spec_alpha, 'n': 1, 'expected': 'A'},
        {'spec': spec_alpha, 'n': 26, 'expected': 'Z'},
        {'spec': spec_alpha, 'n': 27, 'expected': 'AA'},
        {'spec': spec_alpha, 'n': 702, 'expected': 'ZZ'},
        {'spec': spec_alpha, 'n': 703, 'expected': 'AAA'},
        {'spec': {'kind': 'num', 'width': 2, 'start': 5}, 'n': 3, 'expected': '07'},
    ]
    normalize = []
    for value in (
        None,
        {},
        'legacy',
        {'tpl': ''},
        {'row_no': 3},
        {'zone_code': 'A-1'},
        {'tpl': '{prefix} B{bay} L{level}'},
        {
            'tpl': '{ряд} {секція} {ярус}',
            'sep': '.',
            'seg': {'bay': {'kind': 'alpha', 'width': 3, 'start': 2}},
            'bay_dir': 'odd_even',
        },
        {'tpl': '{aisle} {section} {tier} {position}', 'row_from': 'left', 'row_mode': 'snake', 'level_dir': 'down'},
    ):
        normalize.append({'input': value, 'expected': addr.normalize_addr(value)})
    for bad in (
        {'tpl': 'abc'},
        {'tpl': '{foo}'},
        {'tpl': '{bay} {bay}'},
        {'tpl': '{bay}', 'sep': 'abcd'},
        {'tpl': '{bay}', 'sep': ' '},
        {'tpl': '{bay}', 'row_from': 'sideways'},
        {'tpl': '{bay}', 'seg': {'bay': {'width': 9}}},
        {'tpl': '{bay}', 'seg': {'bay': {'kind': 'alpha', 'start': 0}}},
        {'tpl': 'ря{bay}'},
        {'row_no': 0},
        {'zone_code': 'TOOLONGCODE'},
        'x',
    ):
        try:
            addr.normalize_addr(bad)
        except addr.AddrError:
            normalize.append({'input': bad, 'error': True})
        else:
            raise AssertionError('очікували AddrError: %r' % (bad,))
    full = addr.normalize_addr({'tpl': '{prefix} B{bay} L{level} {pos} {zone}', 'sep': '-'})
    render = [
        {'addr': full, 'vals': {'prefix': 'AB-R1', 'bay': 3, 'level': 2}, 'expected': 'AB-R1-B03-L2'},
        {
            'addr': full,
            'vals': {'prefix': 'AB-R1', 'bay': 3, 'level': 2, 'pos': 4, 'zone': 'Z'},
            'expected': 'AB-R1-B03-L2-4-Z',
        },
        {'addr': full, 'vals': {'prefix': 'AB-R1', 'bay': 3}, 'expected': 'AB-R1-B03'},
        {
            'addr': addr.normalize_addr({'tpl': '{zone}{row}.{bay}', 'sep': ''}),
            'vals': {'zone': 2, 'row': 7, 'bay': 12},
            'expected': 'B07.12',
        },
    ]
    parse = []
    for tpl_addr, code, prefix in (
        ({'tpl': '{prefix} B{bay} L{level}'}, 'AB-R1-B03-L2', 'AB-R1'),
        ({'tpl': '{prefix} B{bay} L{level}'}, 'AB-R1-B03-L2', None),
        ({'tpl': '{zone} {row} {bay} {level}', 'sep': '.'}, 'B.07.12.3', None),
        ({'tpl': '{zone} {row} {bay} {level}', 'sep': '.'}, '07.12.3', None),
        ({'tpl': '{row} {bay} {level}'}, 'xx', None),
    ):
        norm = addr.normalize_addr(tpl_addr)
        parse.append({'addr': norm, 'code': code, 'prefix': prefix, 'expected': addr.parse_code(norm, code, prefix)})
    out_scenes = []
    for scene in scenes():
        contexts = addr.address_context(scene['slots'], scene['site_addr'], scene.get('site_depth_mode', 'level'))
        codes = addr.scene_codes(scene['slots'], scene['site_addr'], scene.get('site_depth_mode', 'level'))
        out_scenes.append(dict(scene, context=contexts, codes=codes))
    return _round(
        {
            'meta': {'about': "S1: адресація (F01); еталон — services/addr.py"},
            'format': fmt,
            'normalize': normalize,
            'render': render,
            'parse': parse,
            'scenes': out_scenes,
        }
    )


def build():
    """{ім'я файла без розширення: JSON-значення}."""
    return {'addr_golden': addr_golden(), 'cells_s1_golden': cell_cases()}


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + '\n'


if __name__ == '__main__':
    if '--write' in sys.argv:
        for fname, data in build().items():
            (FIXTURES / (fname + '.json')).write_text(dump(data), encoding='utf-8')
            print('записано', fname)
    else:
        print("Використання: golden_s1.py --write")
