"""Золоті фікстури паритету Python ↔ JS (AC-12, AC-22, AC-31).

Сцени й побудова `cells_golden.json` / `checks_golden.json`.

Файли генеруються з Python-реалізації `services/*` (`F3D_UPDATE_GOLDEN=1` у тесті або `build_all()` напряму);
JS-дзеркало (W2) читає їх і перевіряє збіг: коди/координати комірок (допуск 1e-6) і множини `(check, severity, codes)`.
"""

import json
import os

from ..services import cells as cells_mod
from ..services import checks as checks_mod
from ..services import geometry as geo

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'tests', 'fixtures')
TOLERANCE = 1e-6


def _r(value):
    """Округлення до 9 знаків (стабільний текст файла), рекурсивно."""
    if isinstance(value, float):
        value = round(value, 9)
        return 0.0 if value == 0 else value
    if isinstance(value, dict):
        return {k: _r(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_r(v) for v in value]
    return value


# --- комірки (R-01) -------------------------------------------------------------------------------------


def cells_cases():
    return [
        {
            'name': 'pallet_rack_18x4',
            'template': 'pallet_rack',
            'prefix': 'FG-R1',
            'x': 60.0,
            'y': 5.0,
            'rot': 0,
            'params': {
                'bays': 18,
                'levels': 4,
                'bay_width': 2.7,
                'depth': 1.1,
                'level_height': 1.5,
                'positions_per_bay': 3,
                'max_load_kg': 1000,
            },
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'pallet_rack_rot90',
            'template': 'pallet_rack',
            'prefix': 'FG-R2',
            'x': 60.0,
            'y': 5.0,
            'rot': 90,
            'params': {
                'bays': 4,
                'levels': 2,
                'bay_width': 2.7,
                'depth': 1.1,
                'level_height': 1.5,
                'positions_per_bay': 3,
                'max_load_kg': 1000,
            },
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'pallet_rack_overrides',
            'template': 'pallet_rack',
            'prefix': 'FG-R1',
            'x': 60.0,
            'y': 5.0,
            'rot': 0,
            'params': {
                'bays': 3,
                'levels': 2,
                'bay_width': 2.7,
                'depth': 1.1,
                'level_height': 1.5,
                'positions_per_bay': 3,
                'max_load_kg': 1000,
            },
            'overrides': {
                'FG-R1-B02-L1': {'disabled': True},
                'FG-R1-B03-L1': {'max_load_kg': 1500, 'capacity': 2},
                'FG-R1-B01-L2': {'name': 'Верхня ліва'},
            },
            'elevation': 0.0,
        },
        {
            'name': 'pallet_rack_levels5_elevation',
            'template': 'pallet_rack',
            'prefix': 'ANT-R1',
            'x': 12.5,
            'y': 7.25,
            'rot': 180,
            'params': {
                'bays': 2,
                'levels': 5,
                'bay_width': 2.7,
                'depth': 1.1,
                'level_height': 1.5,
                'positions_per_bay': 3,
                'max_load_kg': 1000,
            },
            'overrides': {},
            'elevation': 3.6,
        },
        {
            'name': 'pallet_rack_defaults',
            'template': 'pallet_rack',
            'prefix': 'RCK-A',
            'x': 10.0,
            'y': 10.0,
            'rot': 0,
            'params': {},
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'pallet_rack_bay_letter_index1',
            'template': 'pallet_rack',
            'prefix': 'AB-R1',
            'x': 20.085,
            'y': 1.8,
            'rot': 0,
            'params': {
                'bays': 3,
                'levels': 4,
                'bay_width': 3.39,
                'depth': 2.0,
                'level_height': 1.25,
                'positions_per_bay': 1,
                'max_load_kg': 3000,
                'index_digits': 1,
                'code_style': 'bay_letter',
            },
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'floor_stack_index1',
            'template': 'floor_stack',
            'prefix': 'ST-R1',
            'x': 20.085,
            'y': 1.8,
            'rot': 0,
            'params': {'rows': 3, 'cols': 4, 'cell_l': 2.5425, 'cell_w': 0.6667, 'max_height': 1.25, 'index_digits': 1},
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'shelf_index_digits_1_kind_shelf',
            'template': 'shelf',
            'prefix': 'EB-U1',
            'x': 30.5,
            'y': 59.0,
            'rot': 90,
            'params': {
                'sections': 4,
                'shelves': 3,
                'cell_w': 5.75,
                'cell_d': 0.9,
                'cell_h': 0.8,
                'index_digits': 1,
                'loc_kind': 'shelf',
            },
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'cantilever_270',
            'template': 'cantilever',
            'prefix': 'CNT-1',
            'x': 30.0,
            'y': 20.0,
            'rot': 270,
            'params': {
                'arms': 3,
                'levels': 2,
                'arm_length': 1.0,
                'length': 6.0,
                'level_height': 1.2,
                'max_load_kg': 500,
            },
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'shelf_fur',
            'template': 'shelf',
            'prefix': 'FUR-R1',
            'x': 100.0,
            'y': 60.5,
            'rot': 0,
            'params': {'sections': 12, 'shelves': 4, 'cell_w': 0.9, 'cell_d': 0.4, 'cell_h': 0.4},
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'floor_stack_rot90',
            'template': 'floor_stack',
            'prefix': 'PLT',
            'x': 20.0,
            'y': 40.0,
            'rot': 90,
            'params': {'rows': 4, 'cols': 3, 'cell_l': 1.2, 'cell_w': 0.8, 'max_height': 1.5},
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'floor_stack_exact',
            'template': 'floor_stack',
            'prefix': 'UNLOAD-4',
            'x': 5.35,
            'y': 35.0,
            'rot': 0,
            'params': {
                'rows': 1,
                'cols': 1,
                'cell_l': 3.58,
                'cell_w': 8.88,
                'max_height': 1.371,
                'code_style': 'exact',
            },
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'floor_stack_exact_rot90_elevated',
            'template': 'floor_stack',
            'prefix': 'PLT-01B',
            'x': 33.96,
            'y': 1.8,
            'rot': 90,
            'params': {'rows': 1, 'cols': 1, 'cell_l': 2.98, 'cell_w': 2.15, 'max_height': 0.82, 'code_style': 'exact'},
            'overrides': {},
            'elevation': 0.5,
        },
        {
            'name': 'machine_spot',
            'template': 'machine_spot',
            'prefix': 'SPOT-1',
            'x': 25.0,
            'y': 12.0,
            'rot': 90,
            'params': {'length': 4.0, 'width': 1.5, 'service': {'front': 1.0, 'back': 0.5, 'left': 0.5, 'right': 0.5}},
            'overrides': {},
            'elevation': 0.0,
        },
        {
            'name': 'zone_polygon',
            'template': 'zone',
            'prefix': 'ZN-1',
            'x': 0.0,
            'y': 0.0,
            'rot': 0,
            'params': {'polygon': [[10, 10], [30, 10], [30, 25], [10, 25]]},
            'overrides': {},
            'elevation': 0.0,
        },
    ]


def build_cells_golden():
    cases = []
    for case in cells_cases():
        cells = cells_mod.generate_cells(
            case['template'],
            case['prefix'],
            case['x'],
            case['y'],
            case['rot'],
            case['params'],
            case['overrides'],
            case['elevation'],
        )
        length, width = cells_mod.footprint(case['template'], case['params'])
        cases.append(dict(case, footprint={'l': length, 'w': width}, cell_count=len(cells), cells=cells))
    return _r(
        {
            'meta': {
                'schema': 1,
                'tolerance': TOLERANCE,
                'source': 'services/cells.py (R-01)',
                'templates': list(cells_mod.SLOT_TEMPLATES),
                'notes': [
                    "Комірка: {code, name, template, level, index, x, y, z0, l, w, h, rot, capacity, max_load_kg, "
                    "kind}.",
                    "x,y — світовий центр комірки; z0 = elevation + зсув ярусу; rot — кут місця.",
                    "Порожній `params` → умовчання шаблону (SLOT_TEMPLATES).",
                    "index_digits (1…4, умовчання 2): мінімальна ширина номера прольоту/секції/ряду: "
                    "max(index_digits, цифр(N)).",
                    "code_style (лише pallet_rack): 'default' → {p}-B{bb}-L{l}; "
                    "'bay_letter' → {p}-{bay}{A+level-1} (приклад AB-R1-1A).",
                    "loc_kind (лише shelf): 'bin' (умовчання) або 'shelf' — вид локації `kind` комірки.",
                    "code_style 'exact' (усі шаблони з комірками): якщо шаблон дає рівно одну комірку, її код = {p}; "
                    "для floor_stack 1×1 cell_l/cell_w до 200 м, max_height до 30 м.",
                ],
            },
            'cases': cases,
        }
    )


# --- перевірки (R-03…R-10) ------------------------------------------------------------------------------


def _variants():
    return [
        {
            'id': 1,
            'name': "Верстат 4000×1200",
            'length': 4000,
            'width': 1200,
            'height': 1800,
            'service': {'front': 1000, 'back': 0, 'left': 0, 'right': 0},
            'front_side': 's',
            'anchor': 'front',
            'rotations': 'q',
            'layer_kinds': ['production'],
            'slot_types': ['machine_spot', 'zone'],
            'utilities': [{'kind': 'electric', 'x_mm': -1900, 'y_mm': 0, 'z_mm': 500}],
            'weight_kg': 6000,
            'floor_load': 12.26,
        },
        {
            'id': 2,
            'name': "Простий 2000×1000",
            'length': 2000,
            'width': 1000,
            'height': 1000,
            'service': {'front': 0, 'back': 0, 'left': 0, 'right': 0},
            'front_side': 's',
            'anchor': 'center',
            'rotations': 'any',
            'layer_kinds': [],
            'slot_types': [],
            'utilities': [],
            'weight_kg': 500,
            'floor_load': 0.25,
        },
        {
            'id': 3,
            'name': "Навантажувач",
            'length': 2600,
            'width': 1200,
            'height': 2200,
            'service': {'front': 1500, 'back': 0, 'left': 0, 'right': 0},
            'front_side': 'e',
            'anchor': 'corner',
            'rotations': 'h',
            'layer_kinds': [],
            'slot_types': [],
            'utilities': [],
            'weight_kg': 4500,
            'floor_load': 1.4,
        },
        {
            'id': 4,
            'name': "Палета 1200×800",
            'length': 1200,
            'width': 800,
            'height': 1000,
            'service': {'front': 0, 'back': 0, 'left': 0, 'right': 0},
            'front_side': 's',
            'anchor': 'center',
            'rotations': 'q',
            'layer_kinds': [],
            'slot_types': [],
            'utilities': [],
            'weight_kg': 1200,
            'floor_load': 1.2,
        },
        {
            'id': 5,
            'name': "Станок з повітрям",
            'length': 3000,
            'width': 1500,
            'height': 1800,
            'service': {'front': 500, 'back': 500, 'left': 500, 'right': 500},
            'front_side': 'n',
            'anchor': 'back',
            'rotations': 'z',
            'layer_kinds': ['production'],
            'slot_types': [],
            'utilities': [
                {'kind': 'electric', 'x_mm': 0, 'y_mm': 600, 'z_mm': 500},
                {'kind': 'air', 'x_mm': 1000, 'y_mm': 0, 'z_mm': 400},
            ],
            'weight_kg': 3000,
            'floor_load': 6.5,
        },
    ]


def _layers():
    return [
        {
            'id': 1,
            'name': "Будівля",
            'kind': 'building',
            'elevation': 0.0,
            'max_floor_load': 0.0,
            'bounds': None,
            'slot_types': ['zone'],
            'aisles': [],
            'fire_paths': [],
            'utilities': [],
        },
        {
            'id': 2,
            'name': "Склади",
            'kind': 'storage',
            'elevation': 0.0,
            'max_floor_load': 0.0,
            'bounds': None,
            'slot_types': [],
            'aisles': [],
            'fire_paths': [],
            'utilities': [],
        },
        {
            'id': 3,
            'name': "Виробництво",
            'kind': 'production',
            'elevation': 0.0,
            'max_floor_load': 0.0,
            'bounds': None,
            'slot_types': [],
            'aisles': [],
            'fire_paths': [],
            'utilities': [],
        },
        {
            'id': 4,
            'name': "Антресоль",
            'kind': 'custom',
            'elevation': 3.6,
            'max_floor_load': 0.0,
            'bounds': None,
            'slot_types': [],
            'aisles': [],
            'fire_paths': [],
            'utilities': [],
        },
    ]


def _state(**over):
    state = {
        'site': {'building': {'length': 60.0, 'width': 30.0, 'height': 8.0}},
        'layers': _layers(),
        'slots': [],
        'placements': [],
        'variants': _variants(),
    }
    for key, value in over.items():
        if key.startswith('layer'):
            index = int(key[5:])
            state['layers'][index - 1].update(value)
        else:
            state[key] = value
    return state


def _pl(pid, code, variant_id, x, y, rotation=0.0, layer_id=3, slot_id=None, cell_code=None):
    return {
        'id': pid,
        'layer_id': layer_id,
        'variant_id': variant_id,
        'slot_id': slot_id,
        'cell_code': cell_code,
        'code': code,
        'name': code,
        'x': x,
        'y': y,
        'rotation': rotation,
    }


def _slot(sid, layer_id, template, prefix, x, y, rotation=0, params=None, overrides=None):
    return {
        'id': sid,
        'layer_id': layer_id,
        'template': template,
        'code_prefix': prefix,
        'x': x,
        'y': y,
        'rotation': rotation,
        'params': params or {},
        'overrides': overrides or {},
    }


def _configs(only=None, **modes):
    """7 перевірок за R-04; `only` лишає увімкненими лише вказані; `modes`: collide='warn', load=False (вимкнено)."""
    out = []
    for key, enabled, mode, params in checks_mod.CHECK_DEFAULTS:
        if only is not None and key not in only:
            enabled = False
        value = modes.get(key)
        if value is False:
            enabled = False
        elif value:
            mode = value
        out.append({'check': key, 'enabled': enabled, 'mode': mode, 'params': dict(params)})
    return out


def check_scenes():
    scenes = []

    def add(name, state, configs=None, only=None):
        """Сцена: за замовчуванням увімкнена лише перевірка з префікса імені (fits_*, collide_*, …)."""
        if configs is None:
            prefix = next((k for k in checks_mod.CHECK_KEYS if name.startswith(k)), None)
            configs = _configs(only=only if only is not None else ((prefix,) if prefix else None))
        scenes.append({'name': name, 'state': state, 'configs': configs})

    poly = [[0, 0], [20, 0], [20, 20], [0, 20]]
    # fits
    add('fits_inside_bounds_ok', _state(layer3={'bounds': poly}, placements=[_pl(1, 'M-1', 1, 10, 10)]))
    add('fits_outside_bounds', _state(layer3={'bounds': poly}, placements=[_pl(1, 'M-1', 1, 19, 10)]))
    add('fits_outside_building', _state(placements=[_pl(1, 'M-1', 2, 59.5, 15)]))
    add('fits_rotation_45_mode_q', _state(placements=[_pl(1, 'M-1', 1, 30, 15, 45)]))
    add('fits_rotation_90_mode_h', _state(placements=[_pl(1, 'F-1', 3, 30, 15, 90)]))
    add('fits_rotation_mode_z', _state(placements=[_pl(1, 'P-1', 5, 30, 15, 90)]))
    add('fits_layer_kind_not_allowed', _state(placements=[_pl(1, 'M-1', 1, 30, 15, layer_id=2)]))
    add(
        'fits_slot_type_not_allowed',
        _state(
            slots=[_slot(1, 3, 'pallet_rack', 'RK-1', 30, 15, params={'bays': 2, 'levels': 1})],
            placements=[_pl(1, 'M-1', 1, 30, 15, slot_id=1)],
        ),
    )
    rack = {
        'bays': 2,
        'levels': 2,
        'bay_width': 2.7,
        'depth': 1.1,
        'level_height': 1.5,
        'positions_per_bay': 3,
        'max_load_kg': 1000,
    }
    add(
        'fits_cell_ok',
        _state(
            slots=[_slot(1, 2, 'pallet_rack', 'RK-1', 30, 15, params=rack)],
            placements=[_pl(1, 'PAL-1', 4, 28.65, 15, 0, 2, 1, 'RK-1-B01-L1')],
        ),
    )
    add(
        'fits_cell_overflow_rot90',
        _state(
            slots=[_slot(1, 2, 'pallet_rack', 'RK-1', 30, 15, params=rack)],
            placements=[_pl(1, 'PAL-1', 4, 28.65, 15, 90, 2, 1, 'RK-1-B01-L1')],
        ),
    )
    add('fits_slot_outside_building', _state(slots=[_slot(1, 2, 'pallet_rack', 'RK-9', 58, 15, params=rack)]))
    # collide
    add('collide_overlap_0_3', _state(placements=[_pl(1, 'A-1', 2, 10, 10), _pl(2, 'A-2', 2, 11.7, 10)]))
    add('collide_touching_no_issue', _state(placements=[_pl(1, 'A-1', 2, 10, 10), _pl(2, 'A-2', 2, 12, 10)]))
    add(
        'collide_different_layers_no_issue',
        _state(placements=[_pl(1, 'A-1', 2, 10, 10, layer_id=3), _pl(2, 'A-2', 2, 11.7, 10, layer_id=4)]),
    )
    add('collide_rotated_45', _state(placements=[_pl(1, 'A-1', 2, 10, 10), _pl(2, 'A-2', 2, 12.0, 10, 45)]))
    add(
        'collide_slot_inside_own_spot_ignored',
        _state(
            slots=[_slot(1, 3, 'machine_spot', 'SP-1', 20, 10, params={'length': 5.0, 'width': 2.0})],
            placements=[_pl(1, 'M-1', 1, 20, 10, slot_id=1), _pl(2, 'A-1', 2, 20, 10)],
        ),
    )
    add(
        'collide_warn_mode',
        _state(placements=[_pl(1, 'A-1', 2, 10, 10), _pl(2, 'A-2', 2, 11.7, 10)]),
        _configs(only=('collide',), collide='warn'),
    )
    add(
        'collide_disabled',
        _state(placements=[_pl(1, 'A-1', 2, 10, 10), _pl(2, 'A-2', 2, 11.7, 10)]),
        _configs(only=('fits', 'collide'), collide=False),
    )
    # service_free
    add('service_free_neighbor_in_front', _state(placements=[_pl(1, 'M-1', 1, 20, 10), _pl(2, 'A-1', 2, 20, 9.2)]))
    add(
        'service_free_rotated_90_zone_east',
        _state(placements=[_pl(1, 'M-1', 1, 20, 10, 90), _pl(2, 'A-1', 2, 21.5, 10)]),
    )
    add(
        'service_free_rotated_90_no_issue', _state(placements=[_pl(1, 'M-1', 1, 20, 10, 90), _pl(2, 'A-1', 2, 20, 7.3)])
    )
    add('service_free_far_no_issue', _state(placements=[_pl(1, 'M-1', 1, 20, 10), _pl(2, 'A-1', 2, 20, 6.0)]))
    # aisles_free / fire
    aisle = {'id': 'a1', 'name': "Центральний прохід", 'x0': 0.0, 'y0': 14.0, 'x1': 60.0, 'y1': 17.0}
    add('aisles_free_blocked', _state(layer3={'aisles': [aisle]}, placements=[_pl(1, 'M-1', 2, 20, 15)]))
    add('aisles_free_clear', _state(layer3={'aisles': [aisle]}, placements=[_pl(1, 'M-1', 2, 20, 5)]))
    add(
        'aisles_free_slot_blocked',
        _state(
            layer3={'aisles': [aisle]},
            slots=[_slot(1, 3, 'machine_spot', 'SP-1', 20, 15, params={'length': 4, 'width': 2})],
        ),
    )
    exit_zone = {'id': 'x1', 'kind': 'exit', 'name': "Евакуаційний вихід 1", 'x0': 0.0, 'y0': 0.0, 'x1': 4.0, 'y1': 4.0}
    path = {'id': 'p1', 'kind': 'path', 'name': "Шлях 1", 'x0': 10.0, 'y0': 0.0, 'x1': 12.0, 'y1': 30.0}
    add('fire_exit_blocked', _state(layer3={'fire_paths': [exit_zone]}, placements=[_pl(1, 'M-1', 2, 3, 3)]))
    add('fire_path_blocked', _state(layer3={'fire_paths': [path]}, placements=[_pl(1, 'M-1', 2, 11, 10)]))
    add('fire_clear', _state(layer3={'fire_paths': [path, exit_zone]}, placements=[_pl(1, 'M-1', 2, 30, 10)]))
    # load
    add('load_floor_exceeded', _state(layer3={'max_floor_load': 4.0}, placements=[_pl(1, 'M-1', 1, 30, 15)]))
    add('load_floor_unlimited_ok', _state(layer3={'max_floor_load': 0.0}, placements=[_pl(1, 'M-1', 1, 30, 15)]))
    heavy = {
        'bays': 2,
        'levels': 2,
        'bay_width': 2.7,
        'depth': 1.1,
        'level_height': 1.5,
        'positions_per_bay': 3,
        'max_load_kg': 1000,
    }
    add(
        'load_cell_exceeded',
        _state(
            slots=[_slot(1, 2, 'pallet_rack', 'RK-1', 30, 15, params=heavy)],
            placements=[_pl(1, 'PAL-1', 4, 28.65, 15, 0, 2, 1, 'RK-1-B01-L1')],
        ),
    )
    # utility_reach
    panel = {'id': 'u1', 'kind': 'panel', 'name': "ГРЩ-1", 'x': 0.0, 'y': 15.0, 'z': 0.0}
    add('utility_reach_far', _state(layer3={'utilities': [panel]}, placements=[_pl(1, 'M-1', 1, 22, 15)]))
    add('utility_reach_near_ok', _state(layer3={'utilities': [panel]}, placements=[_pl(1, 'M-1', 1, 12, 15)]))
    add('utility_reach_missing_kind', _state(layer3={'utilities': [panel]}, placements=[_pl(1, 'M-2', 5, 5, 15)]))
    add(
        'utility_reach_custom_limit',
        _state(layer3={'utilities': [panel]}, placements=[_pl(1, 'M-1', 1, 12, 15)]),
        [
            dict(c, params={'max_m': 5}) if c['check'] == 'utility_reach' else c
            for c in _configs(only=('utility_reach',))
        ],
    )
    # комбінована сцена
    add(
        'mixed_all_checks',
        _state(
            layer3={'aisles': [aisle], 'fire_paths': [path], 'utilities': [panel], 'max_floor_load': 5.0},
            slots=[_slot(1, 3, 'machine_spot', 'SP-1', 40, 6, params={'length': 5, 'width': 2})],
            placements=[
                _pl(1, 'M-1', 1, 40, 6, 0, 3, 1),
                _pl(2, 'M-2', 5, 20, 15),
                _pl(3, 'A-1', 2, 11, 20),
                _pl(4, 'F-1', 3, 50, 25, 90),
            ],
        ),
        _configs(),
    )
    return scenes


def _expected(issues):
    return sorted(
        ({'check': i['check'], 'severity': i['severity'], 'codes': i['codes']} for i in issues),
        key=lambda i: (i['check'], i['severity'], i['codes']),
    )


def sat_cases():
    obb = geo.make_obb
    pairs = [
        ('example1_overlap', obb(0, 0, 1, 0.5, 0), obb(1.5, 0, 1, 0.5, 0)),
        ('example1_touching', obb(0, 0, 1, 0.5, 0), obb(2, 0, 1, 0.5, 0)),
        ('example1_separated', obb(0, 0, 1, 0.5, 0), obb(2.5, 0, 1, 0.5, 0)),
        ('example2_rot45', obb(0, 0, 1, 1, 0), obb(2.2, 0, 1, 1, 45)),
        ('rot30_vs_rot60', obb(0, 0, 2, 0.5, 30), obb(1.0, 0.8, 1.5, 0.7, 60)),
        ('contained', obb(5, 5, 3, 2, 0), obb(5, 5, 1, 1, 90)),
    ]
    return [{'name': n, 'a': a, 'b': b, 'penetration': geo.sat_penetration(a, b)} for n, a, b in pairs]


def geometry_cases():
    cases = []
    base = {
        'length': 4000,
        'width': 1200,
        'height': 1800,
        'service': {'front': 1000, 'back': 300, 'left': 200, 'right': 400},
        'utilities': [{'kind': 'electric', 'x_mm': -1900, 'y_mm': 300, 'z_mm': 500}],
    }
    for front in ('s', 'n', 'e', 'w'):
        for anchor in ('center', 'front', 'back', 'corner'):
            variant = dict(base, front_side=front, anchor=anchor)
            for rotation in (0, 90, 30):
                x, y = 10.0, 5.0
                body = geo.placement_obb(variant, x, y, rotation)
                service = geo.service_obb(variant, x, y, rotation)
                cases.append(
                    {
                        'name': 'front_%s_anchor_%s_rot_%d' % (front, anchor, rotation),
                        'variant': variant,
                        'x': x,
                        'y': y,
                        'rotation': rotation,
                        'body': body,
                        'service': service,
                        'utility_points': [list(p) for p in geo.utility_points(variant, x, y, rotation)],
                    }
                )
    return cases


def polygon_cases():
    poly = [[0, 0], [10, 0], [10, 6], [4, 6], [4, 10], [0, 10]]  # Г-подібний
    points = [
        ('inside', (2, 2)),
        ('inside_notch_side', (8, 3)),
        ('outside_notch', (8, 8)),
        ('on_edge', (10, 3)),
        ('on_vertex', (0, 0)),
        ('outside', (-1, 5)),
        ('near_edge_within_eps', (10.0005, 3)),
    ]
    contains = [
        {'name': n, 'poly': poly, 'point': list(p), 'contains': geo.polygon_contains(poly, p, 0.001)} for n, p in points
    ]
    obbs = [
        ('rect_inside', geo.make_obb(2, 2, 1, 1, 0)),
        ('rect_touching_wall', geo.make_obb(1, 5, 1, 1, 0)),
        ('crossing_notch', geo.make_obb(6, 6, 3, 1.5, 0)),
        ('rot45_inside', geo.make_obb(2, 7, 1, 0.5, 45)),
        ('outside', geo.make_obb(15, 15, 1, 1, 0)),
        ('rot30_crossing_edge', geo.make_obb(9.5, 3, 1.5, 0.5, 30)),
    ]
    inside = [{'name': n, 'obb': o, 'poly': poly, 'inside': geo.obb_inside_polygon(o, poly, 0.001)} for n, o in obbs]
    return contains, inside


def build_checks_golden():
    scenes = []
    for scene in check_scenes():
        issues = checks_mod.run_checks(scene['state'], scene['configs'], 0.001)
        scenes.append(dict(scene, expected=_expected(issues)))
    contains, inside = polygon_cases()
    return _r(
        {
            'meta': {
                'schema': 1,
                'tolerance': 1e-3,
                'eps_m': 0.001,
                'source': 'services/geometry.py, services/checks.py (R-02…R-10)',
                'checks': checks_mod.CHECK_KEYS,
                'notes': [
                    "Стан сцени — формат API-03 (`load`): метри для шарів/місць/розміщень, мм для варіантів; "
                    "`rotations` = rotation_mode.",
                    "Порівнюється множина (check, severity, codes); коди пар `collide` відсортовані за алфавітом.",
                    "`sat.penetration` — min по 4 осях (від'ємне = розділені); перетин, якщо > eps.",
                    "geometry: body/service — OBB {cx, cy, a, b, rot}; service = null, якщо сервісу немає.",
                ],
            },
            'sat': sat_cases(),
            'geometry': geometry_cases(),
            'polygon_contains': contains,
            'obb_inside_polygon': inside,
            'scenes': scenes,
        }
    )


# --- запис / звірка -------------------------------------------------------------------------------------


def _dump(data):
    """JSON: ключі верхнього рівня за алфавітом, кожен елемент списку — в одному рядку (читабельний diff)."""

    def one(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

    parts = []
    for key in sorted(data):
        value = data[key]
        if isinstance(value, list):
            body = "[\n" + ",\n".join(one(item) for item in value) + "\n]"
        else:
            body = one(value)
        parts.append('%s:%s' % (one(key), body))
    return "{\n" + ",\n".join(parts) + "\n}\n"


def build_all():
    """{ім'я файла: текст} для обох фікстур."""
    return {'cells_golden.json': _dump(build_cells_golden()), 'checks_golden.json': _dump(build_checks_golden())}


def write_all(directory=FIXTURES_DIR):
    os.makedirs(directory, exist_ok=True)
    for name, text in build_all().items():
        with open(os.path.join(directory, name), 'w', encoding='utf-8') as handle:
            handle.write(text)
