#!/usr/bin/env python3
"""Будує data/seed_site.json («Меблеве підприємство», SPEC §5.2) із вихідних даних макета factory3d.

Джерела (у репозиторії): `factory3d_viewer/static/data/model_static.json` (layout, evacuation, passports),
`plant/layout.py` (габарити, точки аспірації), прикладна розкладка — порт прикладу прототипу
(`build/constructor/PROTOTYPE.md`): стелажі ГП/сировини/фурнітури/крайки, місця під верстати, проходи, виходи, мережі.

Запуск (із кореня репозиторію):  python3 factory3d/odoo_addons/factory3d_constructor/tools/extract_seed.py
Результат детермінований: `uid` — читабельні ключі, а не випадкові UUID (ідемпотентність seed).
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
FACTORY3D = MODULE.parents[1]
OUT = MODULE / 'data' / 'seed_site.json'
STATIC = FACTORY3D / 'odoo_addons' / 'factory3d_viewer' / 'static' / 'data' / 'model_static.json'

sys.path.insert(0, str(FACTORY3D))
from plant import layout as LY  # noqa: E402  (plant/layout.py: FOOTPRINT, DUCT_POINTS, …)


def _load_cells():
    """services/cells.py без імпорту модуля Odoo: рахуємо кількість комірок тим самим кодом, що й сервер."""
    pkg = 'f3d_seed_services'
    spec = importlib.util.spec_from_file_location(
        pkg, MODULE / 'services' / '__init__.py', submodule_search_locations=[str(MODULE / 'services')]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[pkg] = mod
    spec.loader.exec_module(mod)
    return importlib.import_module(pkg + '.cells')


cells_mod = _load_cells()
D = json.loads(STATIC.read_text(encoding='utf-8'))
P = D['passports']
L = D['layout']

ROLE_NAME = {
    'beam_saw': "Розкрійний центр",
    'beam_saw_book': "Пакетний розкрій",
    'sliding_table_saw': "Форматно-розкрійний верстат",
    'vertical_panel_saw': "Вертикальна панельна пила",
    'nesting_cnc': "Нестинг ЧПК",
    'edgebander_laser': "Кромкооблицювальний верстат (лазер)",
    'edgebander': "Кромкооблицювальний верстат",
    'ptp_cnc': "Обробний центр ЧПК",
    'throughfeed_drilling': "Прохідний свердлильний верстат",
    'dowel_inserting': "Верстат шкантування",
    'hinge_insertion': "Установка завіс",
    'sorting_cell': "Сортувальна робот-комірка",
    'wide_belt_sander': "Широкострічковий шліфувальний верстат",
    'membrane_press': "Мембранно-вакуумний прес",
    'glue_spray_booth': "Кабіна нанесення клею",
    'manual_spray_booth': "Фарбувальна камера",
    'automatic_spraying': "Автомат фарбування",
    'drying': "Сушильна камера",
    'uv_line': "Лінія УФ-лакування",
    'case_clamp_auto': "Автоматична лінія збирання",
    'case_clamp_manual': "Корпусна вайма",
    'box_machine': "Розкрій гофрокартону",
    'stretch_wrapper': "Палетообмотувач",
    'shrink_line': "Лінія термоусадки й обв’язки",
    'forklift': "Навантажувач",
    'board_forklift': "Навантажувач для плит",
    'tugger': "Електротягач",
    'board_rack': "Палетний стелаж",
    'main_switchboard': "Головний розподільний щит",
    'compressor': "Компресорна станція",
    'dust_extraction': "Аспіраційна установка",
}
CAT = {role: 'machine' for role in ROLE_NAME}
CAT.update(
    {
        'case_clamp_auto': 'conveyor',
        'shrink_line': 'conveyor',
        'sorting_cell': 'robot',
        'forklift': 'forklift',
        'board_forklift': 'forklift',
        'tugger': 'forklift',
        'board_rack': 'rack',
        'main_switchboard': 'panel',
        'compressor': 'other',
        'dust_extraction': 'other',
    }
)
H_TYPE = {
    'saw': 2300,
    'saw_book': 2300,
    'slide': 1300,
    'vsaw': 3018,
    'nest': 2850,
    'edge': 1900,
    'edge_robot': 2600,
    'cnc': 2407,
    'bore': 2120,
    'dowel': 1880,
    'hinge': 1500,
    'sortbot': 3000,
    'sand': 2030,
    'press': 2250,
    'glue': 3250,
    'spray': 3300,
    'autospray': 2895,
    'dry': 4524,
    'uv': 1900,
    'asmline': 2000,
    'asm': 1100,
    'pack': 2000,
    'box': 2200,
    'packline': 2300,
}
PW = {
    'saw': 11,
    'saw_book': 30,
    'slide': 5.5,
    'vsaw': 5.5,
    'nest': 10,
    'edge': 22,
    'edge_robot': 45,
    'cnc': 20,
    'bore': 19.5,
    'dowel': 11,
    'hinge': 1.1,
    'sortbot': 12,
    'sand': 11,
    'press': 28,
    'glue': 2.2,
    'spray': 5.1,
    'autospray': 18,
    'dry': 17,
    'uv': 2.9,
    'asmline': 25,
    'asm': 1.5,
    'pack': 1.9,
    'box': 10,
    'packline': 19.75,
}
WT = {
    'saw': 12000,
    'saw_book': 15000,
    'slide': 1200,
    'vsaw': 1500,
    'nest': 9000,
    'edge': 4000,
    'edge_robot': 7000,
    'cnc': 5500,
    'bore': 5500,
    'dowel': 2000,
    'hinge': 47,
    'sortbot': 6000,
    'sand': 3200,
    'press': 8800,
    'glue': 495,
    'spray': 910,
    'autospray': 7000,
    'dry': 4500,
    'uv': 3500,
    'asmline': 5500,
    'asm': 2200,
    'pack': 1500,
    'box': 2500,
    'packline': 3000,
}
PANEL = {
    'saw': 'QF-1',
    'saw_book': 'QF-1',
    'slide': 'QF-1',
    'vsaw': 'QF-1',
    'nest': 'QF-1',
    'edge': 'QF-2',
    'edge_robot': 'QF-2',
    'cnc': 'QF-3',
    'bore': 'QF-3',
    'dowel': 'QF-3',
    'sortbot': 'QF-3',
    'sand': 'QF-4',
    'press': 'QF-4',
    'glue': 'QF-4',
    'spray': 'QF-4',
    'autospray': 'QF-4',
    'dry': 'QF-4',
    'uv': 'QF-4',
    'hinge': 'QF-4',
    'asmline': 'QF-C1',
    'asm': 'QF-C1',
    'pack': 'QF-C2',
    'box': 'QF-C2',
    'packline': 'QF-C2',
}
AIR = {
    'saw',
    'saw_book',
    'edge',
    'edge_robot',
    'cnc',
    'bore',
    'dowel',
    'hinge',
    'asm',
    'asmline',
    'pack',
    'press',
    'nest',
    'sortbot',
    'autospray',
    'spray',
}
SERVICE = {'machine': (1000, 300, 300, 300), 'conveyor': (800, 400, 300, 300), 'robot': (1000, 500, 500, 500)}
LAYER_KINDS = {
    'machine': ['production'],
    'conveyor': ['production'],
    'robot': ['production'],
    'forklift': ['production', 'storage', 'yard'],
    'rack': ['storage'],
    'panel': ['production', 'storage', 'engineering'],
    'other': ['production', 'engineering', 'yard'],
}
WORKCENTER_CATS = ('machine', 'conveyor', 'robot')


def short(model):
    return re.split(r'[,(]| з | — ', model)[0].strip()[:42]


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower().encode('ascii', 'ignore').decode()).strip('-') or 'm'


def parse_mass(text):
    m = re.search(r'(\d[\d\s]*(?:[.,]\d+)?)\s*(кг|т)\b', text)
    if not m:
        return None
    value = float(m.group(1).replace(' ', '').replace(',', '.'))
    return int(value * (1000 if m.group(2) == 'т' else 1))


variants = {}  # key → variant


def add_variant(code, typ=None, role=None, dims=None, weight=None, height=None, power=None):
    passport = P[code]
    role = role or passport['role']
    cat = CAT[role]
    key = '%s.%s' % (role, slug(short(passport['model'])))
    if key in variants:
        return key
    if dims is None:
        fx, fy = LY.FOOTPRINT[typ]
        dims = (int(fx * 1000), int(fy * 1000))
    length, width = dims
    spec_mass = None
    for name, value in passport['specs'].items():
        if name.startswith(('Маса', 'Вага')):
            spec_mass = parse_mass(str(value))
    util = []
    if cat in ('machine', 'conveyor', 'robot', 'panel'):
        util.append({'kind': 'electric', 'x_mm': -length // 2 + 300, 'y_mm': width // 2 - 300, 'z_mm': 1800})
    if typ in AIR:
        util.append({'kind': 'air', 'x_mm': length // 2 - 300, 'y_mm': width // 2 - 300, 'z_mm': 1200})
    for dx, dy, dz in LY.DUCT_POINTS.get(typ, []):
        util.append({'kind': 'dust', 'x_mm': int(dx * 1000), 'y_mm': int(dy * 1000), 'z_mm': int(dz * 1000)})
    svc = SERVICE.get(cat, (1000, 300, 300, 300))
    variants[key] = {
        'key': key,
        'passport_role': role,
        'name': short(passport['model']),
        'category': cat,
        'length': length,
        'width': width,
        'height': int(height or passport['dimensions_mm'].get('H') or H_TYPE.get(typ, 2000)),
        'service': dict(zip(('front', 'back', 'left', 'right'), svc, strict=True)),
        'rotations': 'any' if cat == 'forklift' else 'q',
        'layer_kinds': LAYER_KINDS[cat],
        'slot_types': ['machine_spot'] if cat in WORKCENTER_CATS else [],
        'utilities': util,
        'power_kw': power if power is not None else (passport.get('power_kw') or PW.get(typ, 0)),
        'panel': PANEL.get(typ, ''),
        'weight_kg': int(weight or spec_mass or WT.get(typ, 1000)),
        'anchor': 'center',
        'front_side': 'e' if cat == 'forklift' else 's',
        'create_workcenter': cat in WORKCENTER_CATS,
    }
    return key


machines = []
for code, m in L['machines'].items():
    machines.append((code, m['name'], add_variant(code, typ=m['type']), m['x'], m['y'], m.get('rot', 0)))
# обладнання без точних позицій у layout — лише в каталозі (як у прототипі)
add_variant('FL-1', role='forklift', dims=(3144, 1085), height=2210, weight=3800, power=0)
add_variant('FL-2', role='board_forklift', dims=(5173, 1448), height=3230, weight=7800, power=0)
add_variant('TUGGER-1', role='tugger', dims=(1390, 810), height=1320, weight=700, power=2.8)
add_variant('BOARD-RACKS', role='board_rack', dims=(3390, 2000), height=4700, weight=900, power=0)
add_variant('SWB-1', role='main_switchboard', dims=(800, 600), height=2000, weight=350, power=0)
add_variant('COMPRESSOR', role='compressor', dims=(1273, 780), height=1590, weight=950, power=37)
add_variant('DUST-1', role='dust_extraction', dims=(4320, 1920), height=5180, weight=3500, power=45)
variants['board_rack.' + slug(short(P['BOARD-RACKS']['model']))]['name'] = "PR 600 (3 прольоти)"
variants['board_rack.' + slug(short(P['BOARD-RACKS']['model']))]['rotations'] = 'q'
forklift_key = next(k for k in variants if k.startswith('forklift.'))

# --- шари ---------------------------------------------------------------------------------------------------
W, DEPTH, H = L['dims']['W'], L['dims']['D'], L['dims']['H']


def layer(uid, name, kind, elevation, grid_step, aisle_width, slot_types, roles, color, opacity, max_load, **extra):
    data = {
        'uid': uid,
        'name': name,
        'kind': kind,
        'elevation': elevation,
        'grid_step': grid_step,
        'aisle_width': aisle_width,
        'max_floor_load': max_load,
        'bounds': None,
        'slot_types': slot_types,
        'edit_roles': roles,
        'color': color,
        'opacity': opacity,
        'aisles': [],
        'fire_paths': [],
        'utilities': [],
    }
    data.update(extra)
    return data


ly_building = layer('seed-ly-building', "Будівля", 'building', 0.0, 1.0, 3.0, ['zone'], [], '#6f8396', 0.35, 0.0)
ly_storage = layer(
    'seed-ly-storage',
    "Склади",
    'storage',
    0.0,
    0.1,
    3.3,
    ['pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'zone'],
    ['storekeeper'],
    '#3f9b6a',
    0.55,
    30.0,
)
ly_prod = layer(
    'seed-ly-prod',
    "Виробництво",
    'production',
    0.0,
    0.5,
    3.6,
    ['machine_spot', 'zone'],
    ['technologist'],
    '#2f78b5',
    0.55,
    40.0,
)
ly_eng = layer(
    'seed-ly-eng', "Інженерні мережі", 'engineering', 6.0, 1.0, 1.0, ['zone'], ['engineer'], '#d08a1e', 0.4, 5.0
)
ly_yard = layer(
    'seed-ly-yard', "Двір", 'yard', 0.0, 1.0, 5.0, ['floor_stack', 'machine_spot', 'zone'], [], '#8a8f6a', 0.45, 80.0
)
ly_mezz = layer('seed-ly-mezz', "Антресоль офісу", 'custom', 3.6, 0.3, 1.2, ['zone'], [], '#9a6bb3', 0.45, 5.0)
layers = [ly_building, ly_storage, ly_prod, ly_eng, ly_yard, ly_mezz]

slots = []


def r2(value):
    return round(value, 3)


def zone(ly, code, name, x0, y0, x1, y1):
    slots.append(
        {
            'uid': 'seed-sl-' + code.lower(),
            'layer': ly['uid'],
            'template': 'zone',
            'code_prefix': code,
            'x': 0.0,
            'y': 0.0,
            'rotation': 0,
            'params': {'polygon': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]},
            'overrides': {},
            'parent': None,
            'note': name,
        }
    )


for code, z in L['zones'].items():
    x0, y0, x1, y1 = z['rect']
    zone(ly_building, code, z['name'], x0, y0, x1, y1)
zone(ly_mezz, 'MZ-OFFICE', "Антресоль офісу", 93.0, 58.4, 109.0, 71.0)


def rack(code, template, x, y, rotation, params, parent):
    slots.append(
        {
            'uid': 'seed-sl-' + code.lower(),
            'layer': ly_storage['uid'],
            'template': template,
            'code_prefix': code,
            'x': r2(x),
            'y': r2(y),
            'rotation': rotation,
            'params': params,
            'overrides': {},
            'parent': parent,
        }
    )


FG_PARENT, FUR_PARENT, EB_PARENT = "WH/Готова продукція", "WH/Сировина/Фурнітура", "WH/Сировина/Крайка"
for i, x in enumerate(LY.FG_ROWS):
    rack(
        'FG-R%d' % (i + 1),
        'pallet_rack',
        x,
        27.3,
        90,
        {
            'bays': 18,
            'levels': 4,
            'bay_width': 2.7,
            'depth': 1.1,
            'level_height': 1.9,
            'positions_per_bay': 2,
            'max_load_kg': 2000,
        },
        FG_PARENT,
    )
for i, y in enumerate([1.8, 9.6, 11.9, 19.7, 22.0, 29.8, 32.1, 39.9]):
    # RCK-Rn: стоси плит 3 × 4 (коди RCK-R1-1A…3D, вид «стос»); габарит 10,17 × 2,0 м
    rack(
        'RCK-R%d' % (i + 1),
        'floor_stack',
        20.085,
        y,
        0,
        {'rows': 3, 'cols': 4, 'cell_l': 2.5425, 'cell_w': 0.6667, 'max_height': 1.25, 'index_digits': 1},
        "WH/Сировина/Плити/Стелажі/R%d" % (i + 1),
    )
for k in range(6):
    rack(
        'FUR-R%d' % (k + 1),
        'shelf',
        21.5,
        48 + 4.2 * k,
        0,
        {'sections': 6, 'shelves': 4, 'cell_w': 2.0, 'cell_d': 0.6, 'cell_h': 0.6},
        FUR_PARENT,
    )
for i, x in enumerate([30.5, 33.7]):  # EB-Un: коди EB-U1-S1-L1 (1 розряд)
    rack(
        'EB-U%d' % (i + 1),
        'shelf',
        x,
        59,
        90,
        {
            'sections': 4,
            'shelves': 3,
            'cell_w': 5.75,
            'cell_d': 0.9,
            'cell_h': 0.8,
            'index_digits': 1,
            'loc_kind': 'shelf',
        },
        EB_PARENT,
    )
service = {'front': 1.0, 'back': 0.3, 'left': 0.3, 'right': 0.3}
slots.append(
    {
        'uid': 'seed-sl-ms-1',
        'layer': ly_prod['uid'],
        'template': 'machine_spot',
        'code_prefix': 'MS-1',
        'x': 73.0,
        'y': 41.0,
        'rotation': 0,
        'params': {'length': 6.6, 'width': 4.4, 'service': service},
        'overrides': {},
        'parent': None,
    }
)
slots.append(
    {
        'uid': 'seed-sl-ms-2',
        'layer': ly_prod['uid'],
        'template': 'machine_spot',
        'code_prefix': 'MS-2',
        'x': 61.0,
        'y': 41.0,
        'rotation': 0,
        'params': {'length': 12.6, 'width': 3.8, 'service': service},
        'overrides': {},
        'parent': None,
    }
)

ly_storage['aisles'] = [
    {'id': 'ai_r%d' % i, 'name': "Прохід %d" % (i + 1), 'x0': 13.4, 'y0': a[0], 'x1': 41.4, 'y1': a[1]}
    for i, a in enumerate([(2.8, 8.6), (12.9, 18.7), (23.0, 28.8), (33.1, 38.9)])
]
ly_storage['aisles'] += [
    {'id': 'ai_fg1', 'name': "Прохід ГП 1", 'x0': 123.75, 'y0': 3.0, 'x1': 127.05, 'y1': 51.6},
    {'id': 'ai_fg2', 'name': "Прохід ГП 2", 'x0': 129.25, 'y0': 3.0, 'x1': 132.55, 'y1': 51.6},
]
ly_prod['aisles'] = [{'id': 'ai_main', 'name': "Головний проїзд", 'x0': 42.0, 'y0': 44.2, 'x1': 92.0, 'y1': 47.8}]

# виходи (евакуація): прямокутник 2.0 × 2.5 м біля стіни
for ex in D['evacuation']['exits']:
    x, y, side = ex['x'], ex['y'], ex['side']
    if side in ('S', 'N'):
        x0, x1 = x - 1.0, x + 1.0
        y0, y1 = (0.0, 2.5) if side == 'S' else (DEPTH - 2.5, DEPTH)
    else:
        y0, y1 = y - 1.0, y + 1.0
        x0, x1 = (0.0, 2.5) if side == 'W' else (W - 2.5, W)
    ly_building['fire_paths'].append(
        {
            'id': 'fp_' + ex['code'].lower(),
            'kind': 'exit',
            'name': "Вихід " + ex['code'],
            'x0': r2(x0),
            'y0': r2(y0),
            'x1': r2(x1),
            'y1': r2(y1),
        }
    )

# інженерні точки: щити/магістралі
utils, counter = [], [0]


def put(kind, x, y):
    counter[0] += 1
    utils.append(
        {
            'id': 'u%d' % counter[0],
            'kind': kind,
            'name': {'electric': "Електрика", 'air': "Повітря", 'dust': "Аспірація"}[kind],
            'x': float(x),
            'y': float(y),
            'z': 0.0,
        }
    )


for x in (45, 59, 74, 88, 100, 112, 120):
    for y in (9, 28, 47, 66):
        put('electric', x, y)
for x in (42, 66, 90, 112, 120):
    for y in (4, 22, 40, 56, 68):
        put('air', x, y)
for x in (43, 51, 59, 67, 75, 83):
    put('dust', x, 18.5)
for y in (26.5, 34.5, 42.5, 50.5, 58.5, 66.5):
    put('dust', 55.6, y)
for y in (26.5, 34.5):
    put('dust', 75, y)
ly_eng['utilities'] = utils

# --- розміщення ---------------------------------------------------------------------------------------------
placements = []
for code, name, key, x, y, rot in machines:
    placements.append(
        {
            'uid': 'seed-pl-' + code.lower(),
            'layer': ly_prod['uid'],
            'variant': key,
            'slot': None,
            'x': x,
            'y': y,
            'rotation': rot,
            'code': code,
            'name': name,
        }
    )
for code, name, y in (
    ('FL-1', "Навантажувач ГП 1", 62.6),
    ('FL-4', "Навантажувач ГП 2", 65.0),
    ('FL-5', "Навантажувач пакування", 67.4),
):
    placements.append(
        {
            'uid': 'seed-pl-' + code.lower(),
            'layer': ly_prod['uid'],
            'variant': forklift_key,
            'slot': None,
            'x': 118.5,
            'y': y,
            'rotation': 0,
            'code': code,
            'name': name,
        }
    )

cell_total = sum(cells_mod.count_cells(s['template'], s['code_prefix'], s['params'], s['overrides']) for s in slots)
seed = {
    'meta': {
        'name': "Меблеве підприємство",
        'seed_key': 'main_demo',
        'schema': 1,
        'source': 'factory3d model_static.json + plant/layout.py (приклад прототипу конструктора)',
        'counts': {
            'layers': len(layers),
            'slots': len(slots),
            'cells': cell_total,
            'placements': len(placements),
            'variants': len(variants),
        },
    },
    'site': {
        'building': {'length': W, 'width': DEPTH, 'height': H},
        'column_grid': {'step_x': 12.0, 'step_y': 12.0},
        'default_parent': 'WH/Stock',
    },
    'layers': layers,
    'slots': slots,
    'variants': list(variants.values()),
    'placements': placements,
}


def dump(data):
    """Верхній рівень — за ключами, кожен елемент списків в одному рядку (читабельний diff)."""

    def one(value):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

    parts = []
    for key, value in data.items():
        if isinstance(value, list):
            parts.append('%s:[\n%s\n]' % (one(key), ",\n".join(one(item) for item in value)))
        else:
            parts.append('%s:%s' % (one(key), one(value)))
    return "{\n" + ",\n".join(parts) + "\n}\n"


if __name__ == '__main__':
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dump(seed), encoding='utf-8')
    print(OUT, seed['meta']['counts'])
