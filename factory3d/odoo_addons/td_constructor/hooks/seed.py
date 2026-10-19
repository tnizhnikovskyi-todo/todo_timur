"""Seed «Меблеве підприємство» з data/seed_site.json (SPEC §5.2, DEC-13).

Створення площадки, шарів, варіантів, місць, розміщень."""

import json
import logging
import re

from odoo import Command
from odoo.tools import file_open

from ..services import cells as cells_mod, snapshot
from ..services.schemas import SCENE_ROLE_PREFIX
from . import link

_logger = logging.getLogger(__name__)

SEED_FILE = 'td_constructor/data/seed_site.json'
ROTATION_MODES = {'q': 'q', 'h': 'h', 'z': 'z', 'any': 'any'}


def read_seed():
    with file_open(SEED_FILE, 'rb') as handle:
        return json.loads(handle.read().decode('utf-8'))


def _rotation_mode(value):
    """`rotations` із прототипу ([0, 90, 180, 270] / [0, 180] / [0] / ['any']) або вже режим ('q', 'h', 'z', 'any')."""
    if isinstance(value, str):
        return ROTATION_MODES.get(value, 'q')
    value = sorted({v for v in value or [] if isinstance(v, (int, float))})
    if value == [0]:
        return 'z'
    if value == [0, 180]:
        return 'h'
    if not value and 'any' in (value or []):
        return 'any'
    return 'q'


def _utilities(items):
    out = []
    for item in items or []:
        out.append(
            {
                'kind': item.get('kind'),
                'x_mm': item.get('x_mm', item.get('x', 0)),
                'y_mm': item.get('y_mm', item.get('y', 0)),
                'z_mm': item.get('z_mm', item.get('z', 0)),
            }
        )
    return out


def normalize_seed(data):
    """Адаптер схеми: повертає словник у цільовій схемі §5.2.

    Допускає варіанти з прототипу: `variants[].length/width/height` у метрах (евристика `length < 50 → ×1000`),
    `rotations` списком кутів, `front_side` великими літерами, точки підключення `x/y/z`.
    """
    data = dict(data)
    meta = data.setdefault('meta', {})
    meta.setdefault('name', "Меблеве підприємство")
    meta.setdefault('seed_key', 'main_demo')
    meta.setdefault('code', 'MAIN')
    data.setdefault('site', {}).setdefault('building', {'length': 150, 'width': 72, 'height': 9})
    data['site'].setdefault('column_grid', {'step_x': 6, 'step_y': 6})
    variants = []
    for variant in data.get('variants') or []:
        variant = dict(variant)
        if variant['length'] < 50:  # метри → міліметри
            for key in ('length', 'width', 'height'):
                variant[key] = int(round(variant[key] * 1000))
        variant['rotations'] = _rotation_mode(variant.get('rotations', variant.get('rotation_mode', 'q')))
        variant['front_side'] = (variant.get('front_side') or 's').lower()
        variant['utilities'] = _utilities(variant.get('utilities'))
        # зведені варіанти сцени (паспорт scene_*) не створюють maintenance.equipment, решта — створюють
        variant.setdefault(
            'create_equipment', not str(variant.get('passport_role') or '').startswith(SCENE_ROLE_PREFIX)
        )
        variant.setdefault('layer_kinds', variant.get('allowed_layer_kinds') or [])
        variant.setdefault('slot_types', variant.get('allowed_slot_types') or [])
        variants.append(variant)
    data['variants'] = variants
    data.setdefault('layers', [])
    data.setdefault('slots', [])
    data.setdefault('placements', [])
    return data


def seed_exists(env, data):
    return env['td.site'].with_context(active_test=False).search([('seed_key', '=', data['meta']['seed_key'])], limit=1)


def _ref_group(env, role):
    return env.ref('td_constructor.group_td_constructor_%s' % role, raise_if_not_found=False)


def ensure_variants(env, data):
    """Варіанти seed (за `passport_role` + назвою): знайти або створити.

    Повертає ({key: variant}, [ролі без паспорта])."""
    Passport = env['td.equipment.passport'].with_context(active_test=False)
    Variant = env['td.equipment.variant'].with_context(active_test=False)
    terms = {(t.term_type, t.key): t.id for t in env['td.term'].search([])}
    resolved, skipped = {}, []
    for item in data['variants']:
        passport = Passport.search([('role', '=', item['passport_role'])], limit=1)
        spec = item.get('passport')
        if (
            not passport and spec
        ):  # автопаспорт «Об'єкти сцени» на вид об'єкта 3D-моделі (немає паспорта в каталозі base)
            passport = Passport.create(
                {
                    'role': item['passport_role'],
                    'manufacturer': spec.get('manufacturer') or "—",
                    'model': spec['model'],
                    'td_category': spec.get('category') or 'other',
                }
            )
        if not passport:
            if item['passport_role'] not in skipped:
                skipped.append(item['passport_role'])
            continue
        variant = Variant.search([('passport_id', '=', passport.id), ('name', '=', item['name'])], limit=1)
        if not variant:
            service = item.get('service') or {}
            variant = Variant.create(
                {
                    'passport_id': passport.id,
                    'name': item['name'],
                    'length_mm': item['length'],
                    'width_mm': item['width'],
                    'height_mm': item['height'],
                    'service_front_mm': service.get('front', 0),
                    'service_back_mm': service.get('back', 0),
                    'service_left_mm': service.get('left', 0),
                    'service_right_mm': service.get('right', 0),
                    'front_side': item.get('front_side') or 's',
                    'anchor': item.get('anchor') or 'center',
                    'rotation_mode': item['rotations'],
                    'allowed_layer_kind_ids': [
                        Command.set(
                            [terms[('layer_kind', k)] for k in item['layer_kinds'] if ('layer_kind', k) in terms]
                        )
                    ],
                    'allowed_slot_type_ids': [
                        Command.set([terms[('slot_type', k)] for k in item['slot_types'] if ('slot_type', k) in terms])
                    ],
                    'utilities': item['utilities'],
                    'power_kw': item.get('power_kw') or 0.0,
                    'panel': item.get('panel') or False,
                    'weight_kg': item.get('weight_kg') or 0.0,
                    'create_workcenter': bool(item.get('create_workcenter')),
                    'create_equipment': bool(item['create_equipment']),
                }
            )
        resolved[item['key']] = variant
    return resolved, skipped


# --- узгодження сіда з наявними записами Odoo (R-24) -------------------------------------------------------------


def _short_model(passport):
    """Коротка назва моделі паспорта (як у назвах варіантів верстатів сіда)."""
    return re.split(r'[,(]| з | — ', passport.model or passport.role or '')[0].strip()[:42] or passport.role


def existing_equipment(env, codes):
    """{код: maintenance.equipment} для кодів розміщень: збіг за td_code, потім за td_alias, потім за serial_no
    (лише записи без td_code) — так само, як це робить план публікації."""
    Equipment = env['maintenance.equipment'].with_context(active_test=False)
    codes = list(codes)
    if not codes:
        return {}
    found = Equipment.search(
        ['|', '|', ('td_code', 'in', codes), ('td_alias', 'in', codes), ('serial_no', 'in', codes)]
    )
    out = {}
    for key in ('td_code', 'td_alias'):
        for rec in found:
            if rec[key] in codes:
                out.setdefault(rec[key], rec)
    for rec in found.filtered(lambda r: not r.td_code):
        if rec.serial_no in codes:
            out.setdefault(rec.serial_no, rec)
    return out


def passport_variant(env, base, passport, cache):
    """Варіант паспорта `passport` з геометрією `base` (зведеного варіанта сцени): знайти або створити.

    Об'єкт, що вже має обладнання Odoo зі справжнім паспортом, не повинен лишатися на зведеному паспорті
    «Об'єкти сцени»: інакше публікація понизила б паспорт обладнання до зведеного."""
    name = "%s (%d×%d×%d)" % (_short_model(passport), base.length_mm, base.width_mm, base.height_mm)
    key = (passport.id, name)
    if key not in cache:
        Variant = env['td.equipment.variant'].with_context(active_test=False)
        variant = Variant.search([('passport_id', '=', passport.id), ('name', '=', name)], limit=1)
        if not variant:
            variant = Variant.create(
                {
                    'passport_id': passport.id,
                    'name': name,
                    'length_mm': base.length_mm,
                    'width_mm': base.width_mm,
                    'height_mm': base.height_mm,
                    'service_front_mm': base.service_front_mm,
                    'service_back_mm': base.service_back_mm,
                    'service_left_mm': base.service_left_mm,
                    'service_right_mm': base.service_right_mm,
                    'front_side': base.front_side,
                    'anchor': base.anchor,
                    'rotation_mode': base.rotation_mode,
                    'allowed_layer_kind_ids': [Command.set(base.allowed_layer_kind_ids.ids)],
                    'allowed_slot_type_ids': [Command.set(base.allowed_slot_type_ids.ids)],
                    'utilities': base.utilities or [],
                    'power_kw': base.power_kw,
                    'panel': base.panel or False,
                    'weight_kg': base.weight_kg,
                    'create_workcenter': base.create_workcenter,
                }
            )
        cache[key] = variant
    return cache[key]


def placement_variants(env, data, variants):
    """{uid розміщення: варіант}: варіант сіда, а для розміщення з наявним обладнанням, що має паспорт, — варіант
    ЦЬОГО паспорта (геометрія зведеного варіанта зберігається: габарити, повороти, види шарів)."""
    equipment = existing_equipment(env, [item['code'] for item in data['placements']])
    cache, out = {}, {}
    for item in data['placements']:
        variant = variants.get(item['variant'])
        if not variant:
            continue
        passport = (equipment.get(item['code']) or env['maintenance.equipment']).td_passport_id
        if passport and passport != variant.passport_id:
            variant = passport_variant(env, variant, passport, cache)
        out[item['uid']] = variant
    return out


def adapt_slots(env, data):
    """Місця на одну комірку (code_style='exact'): вид локації береться з наявної локації Odoo того самого коду
    (td_code, потім td_alias, потім barcode), тож незмінена розкладка не пропонує оновлення локацій."""
    exact = [
        item
        for item in data['slots']
        if item['template'] == 'floor_stack' and (item.get('params') or {}).get('code_style') == 'exact'
    ]
    codes = [item['code_prefix'] for item in exact]
    if not codes:
        return 0
    Loc = env['stock.location'].with_context(active_test=False)
    found = Loc.search(['|', '|', ('td_code', 'in', codes), ('td_alias', 'in', codes), ('barcode', 'in', codes)])
    by_code = {}
    for key in ('td_code', 'td_alias', 'barcode'):
        for rec in found:
            if rec[key]:
                by_code.setdefault(rec[key], rec)
    changed = 0
    for item in exact:
        kind = by_code.get(item['code_prefix'], env['stock.location']).td_loc_kind
        if kind in cells_mod.LOC_KINDS and item['params'].get('loc_kind') != kind:
            item['params'] = dict(item['params'], loc_kind=kind)
            changed += 1
    return changed


def load_seed(env, data):
    """Створює площадку seed (якщо її ще немає).

    Повертає `(site, created: dict, skipped_variants: list, variants: dict)`.

    Ідемпотентно за `seed_key`: наявну площадку не чіпає (правки користувача не перезаписуються).
    Четвертий елемент — `{key: variant}` усіх варіантів seed, що знайдені/створені.
    """
    data = normalize_seed(data)
    env = env(su=True, context=dict(env.context, f3d_no_touch=True, tracking_disable=True))
    site = seed_exists(env, data)
    variants, skipped = ensure_variants(env, data)
    if site:
        return site, {}, skipped, variants
    adapt_slots(env, data)
    by_placement = placement_variants(env, data, variants)
    Layer, Slot, Placement = env['td.layer'], env['td.slot'], env['td.placement']
    terms = {(t.term_type, t.key): t.id for t in env['td.term'].search([])}
    building = data['site']['building']
    grid = data['site']['column_grid']
    parent = env['stock.location'].search(
        [('complete_name', '=', data['site'].get('default_parent') or 'WH/Stock')], limit=1
    )
    site = env['td.site'].create(
        {
            'name': data['meta']['name'],
            'code': data['meta']['code'],
            'seed_key': data['meta']['seed_key'],
            'building_length_m': building['length'],
            'building_width_m': building['width'],
            'building_height_m': building['height'],
            'column_step_x_m': grid['step_x'],
            'column_step_y_m': grid['step_y'],
            'default_parent_location_id': parent.id or False,
        }
    )
    layers = {}
    for index, item in enumerate(data['layers'], 1):
        groups = [
            g.id for g in (_ref_group(env, role) for role in item.get('edit_roles') or [] if role != 'manager') if g
        ]
        layers[item['uid']] = Layer.create(
            {
                'uid': item['uid'],
                'site_id': site.id,
                'name': item['name'],
                'kind': item['kind'],
                'group_name': item.get('group') or False,
                'sequence': index * 10,
                'elevation_m': item.get('elevation', 0.0),
                'grid_step_m': item.get('grid_step', 0.5),
                'aisle_width_m': item.get('aisle_width', 3.0),
                'max_floor_load_kn_m2': item.get('max_floor_load', 0.0),
                'bounds': item.get('bounds') or None,
                'color': item.get('color', '#8d99ae'),
                'opacity': item.get('opacity', 1.0),
                'visible': bool(item.get('visible', True)),
                'allowed_slot_type_ids': [
                    Command.set(
                        [terms[('slot_type', k)] for k in item.get('slot_types') or [] if ('slot_type', k) in terms]
                    )
                ],
                'edit_group_ids': [Command.set(groups)],
                'aisles': item.get('aisles') or [],
                'fire_paths': item.get('fire_paths') or [],
                'utilities': item.get('utilities') or [],
            }
        )
    slots, cells = {}, 0
    for item in data['slots']:
        location = env['stock.location']
        if item.get('parent'):
            location = env['stock.location'].search([('complete_name', '=', item['parent'])], limit=1)
        slot = Slot.create(
            {
                'uid': item['uid'],
                'layer_id': layers[item['layer']].id,
                'template': item['template'],
                'code_prefix': item['code_prefix'],
                'x_m': item['x'],
                'y_m': item['y'],
                'rotation': item.get('rotation', 0),
                'params': item.get('params') or {},
                'overrides': item.get('overrides') or {},
                'parent_location_id': location.id or False,
                'note': item.get('note') or False,
            }
        )
        slots[item['uid']] = slot
        cells += slot.cell_count
    placed, skipped_placements = 0, []
    for item in data['placements']:
        variant = by_placement.get(item['uid'])
        if not variant:
            skipped_placements.append(item['code'])
            continue
        Placement.create(
            {
                'uid': item['uid'],
                'layer_id': layers[item['layer']].id,
                'variant_id': variant.id,
                'slot_id': slots[item['slot']].id if item.get('slot') else False,
                'code': item['code'],
                'name': item['name'],
                'x_m': item['x'],
                'y_m': item['y'],
                'rotation': item.get('rotation', 0.0),
                'dynamic': bool(item.get('dynamic')),
            }
        )
        placed += 1
    created = {
        'layers': len(layers),
        'slots': len(slots),
        'cells': cells,
        'placements': placed,
        'variants': len(variants),
    }
    if skipped_placements:
        _logger.warning("Seed: пропущено розміщення без паспорта: %s", ", ".join(skipped_placements))
    return site, created, skipped, variants


def seed_state_problem(site):
    """None, якщо площадка ще в стані сіда (чернетка не змінена відносно версії-імпорту v1), інакше — причина."""
    versions = site.version_ids
    if len(versions) != 1 or not versions.is_seed:
        return "є версії, окрім імпорту з макета"
    if site.active_version_id != versions or site.draft_base_version_id != versions:
        return "діюча версія не є імпортом з макета"
    if site.has_changes or site.draft_changes:
        return "чернетка змінена відносно версії-імпорту"
    return None


def resync_site(env, data=None):
    """Виправляє посіяну площадку на місці (міграція 19.0.1.0.1), ідемпотентно.

    Лише поки площадка в стані сіда (`seed_state_problem`). Переписує видимість шарів за замовчуванням (`visible` сіда),
    варіанти (прапорець create_equipment, варіант справжнього паспорта для розміщень з наявним обладнанням), параметри й
    перевизначення місць (вид локації, відключена комірка без локації Odoo), перебудовує знімок v1 (baseline
    зберігається). Записи Odoo (обладнання, локації, паспорти) не видаляє й не змінює, крім службових полів зв'язку;
    чернетка (`draft_rev`) не зсувається.
    Повертає звіт `{'status': 'fixed'|'skipped'|'no_site', ...}`."""
    data = normalize_seed(data or read_seed())
    env = env(su=True, context=dict(env.context, f3d_no_touch=True, tracking_disable=True))
    site = seed_exists(env, data)
    if not site:
        return {'status': 'no_site'}
    problem = seed_state_problem(site)
    if problem:
        return {'status': 'skipped', 'reason': problem}
    variants, skipped = ensure_variants(env, data)
    report = {'status': 'fixed', 'flags': 0, 'slots': 0, 'placements': 0, 'layers': 0, 'skipped_variants': skipped}
    layers = {x.uid: x for x in env['td.layer'].with_context(active_test=False).search([('site_id', '=', site.id)])}
    for item in data['layers']:  # старий сід ігнорував `visible`: усі 31 шар вмикались одразу й закривали верстати
        layer = layers.get(item['uid'])
        if layer and layer.visible != bool(item.get('visible', True)):
            layer.write({'visible': bool(item.get('visible', True))})
            report['layers'] += 1
    for item in data['variants']:
        variant = variants.get(item['key'])
        if variant and variant.create_equipment != item['create_equipment']:
            variant.write({'create_equipment': item['create_equipment']})
            report['flags'] += 1
    adapt_slots(env, data)
    slots = {s.uid: s for s in env['td.slot'].with_context(active_test=False).search([('site_id', '=', site.id)])}
    for item in data['slots']:
        slot = slots.get(item['uid'])
        if not slot:
            continue
        vals = {}
        params = cells_mod.normalize_params(item['template'], item.get('params') or {})
        if (slot.params or {}) != params:
            vals['params'] = params
        overrides = cells_mod.normalize_overrides(item.get('overrides') or {})
        if (slot.overrides or {}) != overrides:
            vals['overrides'] = overrides
        if vals:
            slot.write(vals)
            report['slots'] += 1
    placements = {
        p.uid: p for p in env['td.placement'].with_context(active_test=False).search([('site_id', '=', site.id)])
    }
    for uid, variant in placement_variants(env, data, variants).items():
        placement = placements.get(uid)
        if placement and placement.variant_id != variant:
            placement.write({'variant_id': variant.id})
            report['placements'] += 1
    link.link_existing(env, site)
    snapshot.rebuild_version(site, site.version_ids)
    return report
