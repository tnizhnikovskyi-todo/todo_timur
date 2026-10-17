"""R-14: знімок версії (JSON-вкладення) і відновлення чернетки за `uid`. Записи Odoo (stock.location тощо) не чіпаються."""
import hashlib
import json

from odoo import Command, fields
from odoo.exceptions import UserError


SCHEMA = 1


def _xmlids(groups):
    ids = groups.get_external_id()
    return [ids[g.id] for g in groups if ids.get(g.id)]


def _canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def build_snapshot(site):
    """Шаблони місць (не комірки): шари, місця, розміщення, налаштування перевірок. `active` лише для діючих записів."""
    env = site.env
    layers = env['f3d.layer'].search([('site_id', '=', site.id)], order='sequence, id')
    slots = env['f3d.slot'].search([('site_id', '=', site.id)], order='layer_id, code_prefix')
    placements = env['f3d.placement'].search([('site_id', '=', site.id)], order='layer_id, code')
    parent = site.default_parent_location_id
    snap = {
        'schema': SCHEMA,
        'site': {
            'name': site.name, 'code': site.code,
            'building': {'length': site.building_length_m, 'width': site.building_width_m, 'height': site.building_height_m},
            'column_grid': {'step_x': site.column_step_x_m, 'step_y': site.column_step_y_m},
            'default_parent_location_id': parent.id or None, 'default_parent_location': parent.complete_name or None,
        },
        'layers': [{
            'uid': layer.uid, 'name': layer.name, 'kind': layer.kind, 'sequence': layer.sequence,
            'elevation_m': layer.elevation_m, 'grid_step_m': layer.grid_step_m, 'aisle_width_m': layer.aisle_width_m,
            'max_floor_load_kn_m2': layer.max_floor_load_kn_m2, 'bounds': layer.bounds or None,
            'allowed_slot_types': sorted(layer.allowed_slot_type_ids.mapped('key')),
            'edit_groups': sorted(_xmlids(layer.sudo().edit_group_ids)),
            'color': layer.color, 'opacity': layer.opacity, 'style': layer.style, 'visible': layer.visible,
            'aisles': layer.aisles or [], 'fire_paths': layer.fire_paths or [], 'utilities': layer.utilities or [],
            'underlay_params': layer.underlay_params or {}, 'active': layer.active,
        } for layer in layers],
        'slots': [{
            'uid': slot.uid, 'layer_uid': slot.layer_id.uid, 'template': slot.template, 'code_prefix': slot.code_prefix,
            'x_m': slot.x_m, 'y_m': slot.y_m, 'rotation': slot.rotation, 'params': slot.params or {},
            'overrides': slot.overrides or {}, 'parent_location': slot.parent_location_id.complete_name or None,
            'active': slot.active,
        } for slot in slots],
        'placements': [{
            'uid': p.uid, 'layer_uid': p.layer_id.uid, 'variant_id': p.variant_id.id,
            'variant_ref': {'passport_role': p.variant_id.passport_id.role, 'name': p.variant_id.name},
            'slot_uid': p.slot_id.uid or None, 'cell_code': p.cell_code or None, 'code': p.code, 'name': p.name,
            'x_m': p.x_m, 'y_m': p.y_m, 'rotation': p.rotation, 'active': p.active,
        } for p in placements],
        'check_configs': [{'check': c.check_key, 'enabled': c.enabled, 'mode': c.mode, 'params': c.params or {}}
                          for c in site.check_config_ids.sorted('sequence')],
    }
    live_slots = [s for s in slots if s.active and s.layer_id.active]
    snap['counts'] = {
        'layers': len([layer for layer in layers if layer.active]), 'slots': len(live_slots),
        'cells': sum(s.cell_count for s in live_slots),
        'placements': len([p for p in placements if p.active and p.layer_id.active]),
    }
    return snap


def dump_snapshot(snap):
    raw = _canonical(snap).encode('utf-8')
    return raw, hashlib.sha1(raw).hexdigest()  # noqa: S324 - контрольна сума знімка, не криптографія


def create_version(site, note='', report=None, is_seed=False, counts=None):
    """Нова версія: знімок, n = max+1, попередня `superseded`, сайт: active/base/published_rev/draft_changes."""
    env = site.env
    Version = env['f3d.layout.version'].sudo()
    previous = Version.search([('site_id', '=', site.id)], order='n desc', limit=1)
    n = (previous.n if previous else 0) + 1
    snap = build_snapshot(site)
    raw, sha1 = dump_snapshot(snap)
    version = Version.create({
        'site_id': site.id, 'n': n, 'note': note or False, 'published_by_id': env.user.id,
        'published_at': fields.Datetime.now(), 'state': 'active', 'snapshot_sha1': sha1, 'draft_rev': site.draft_rev,
        'layer_count': snap['counts']['layers'], 'slot_count': snap['counts']['slots'],
        'cell_count': snap['counts']['cells'], 'placement_count': snap['counts']['placements'],
        'created_count': len((report or {}).get('created') or []), 'updated_count': len((report or {}).get('updated') or []),
        'archived_count': len((report or {}).get('archived') or []), 'report': report or {}, 'is_seed': is_seed,
    })
    attachment = env['ir.attachment'].sudo().create({
        'name': 'f3d_layout_%s_v%d.json' % (site.code, n), 'raw': raw, 'mimetype': 'application/json',
        'res_model': 'f3d.layout.version', 'res_id': version.id, 'type': 'binary',
    })
    version.snapshot_id = attachment
    Version.search([('site_id', '=', site.id), ('state', '=', 'active'), ('id', '!=', version.id)]).write(
        {'state': 'superseded'})
    site.sudo().write({
        'active_version_id': version.id, 'draft_base_version_id': version.id,
        'published_rev': site.draft_rev, 'draft_changes': 0,
    })
    return version


def load_snapshot(version):
    raw = version.snapshot_id.raw if version.snapshot_id else None
    if not raw:
        raise UserError("У версії немає знімка.")
    return json.loads(raw.decode('utf-8'))


def _entity_map(items):
    return {item['uid']: _canonical(item) for item in items}


def count_differences(snap, base):
    """Кількість сутностей (за uid), чий канонічний JSON відрізняється: додані + змінені + видалені (R-14)."""
    total = 0
    for key in ('layers', 'slots', 'placements'):
        new, old = _entity_map(snap[key]), _entity_map(base[key])
        total += sum(1 for uid in new if uid not in old or new[uid] != old[uid]) + sum(1 for uid in old if uid not in new)
    new_c = {c['check']: _canonical(c) for c in snap['check_configs']}
    old_c = {c['check']: _canonical(c) for c in base['check_configs']}
    total += sum(1 for k in new_c if new_c[k] != old_c.get(k))
    return total


def _resolve_variant(env, item):
    Variant = env['f3d.equipment.variant'].with_context(active_test=False)
    variant = Variant.browse(item['variant_id']).exists() if item.get('variant_id') else Variant
    if variant:
        return variant
    ref = item.get('variant_ref') or {}
    return Variant.search([('passport_id.role', '=', ref.get('passport_role')), ('name', '=', ref.get('name'))], limit=1)


def apply_snapshot(site, snap):
    """Відновити чернетку за знімком (за uid): оновити/створити, зайве видалити; Odoo-записи не чіпати."""
    site = site.sudo().with_context(f3d_no_touch=True, active_test=False)
    env = site.env
    Layer, Slot, Placement = env['f3d.layer'], env['f3d.slot'], env['f3d.placement']
    # 1) варіанти розміщень мають існувати — інакше нічого не змінюємо
    variants, missing = {}, []
    for item in snap['placements']:
        variant = _resolve_variant(env, item)
        if variant:
            variants[item['uid']] = variant
        else:
            ref = item.get('variant_ref') or {}
            missing.append("%s (%s · %s)" % (item['code'], ref.get('passport_role'), ref.get('name')))
    if missing:
        raise UserError("Не знайдено варіанти обладнання для розміщень: %s." % ", ".join(missing))
    # 2) поля площадки
    info = snap['site']
    site_vals = {
        'building_length_m': info['building']['length'], 'building_width_m': info['building']['width'],
        'building_height_m': info['building']['height'], 'column_step_x_m': info['column_grid']['step_x'],
        'column_step_y_m': info['column_grid']['step_y'],
    }
    parent = env['stock.location']
    if info.get('default_parent_location'):
        parent = env['stock.location'].search([('complete_name', '=', info['default_parent_location'])], limit=1)
    if not parent and info.get('default_parent_location_id'):
        parent = env['stock.location'].browse(info['default_parent_location_id']).exists()
    site_vals['default_parent_location_id'] = parent.id or False
    site.write(site_vals)
    # 3) видалити зайве: розміщення → місця → шари
    Placement.search([('site_id', '=', site.id), ('uid', 'not in', [p['uid'] for p in snap['placements']])]).unlink()
    Slot.search([('site_id', '=', site.id), ('uid', 'not in', [s['uid'] for s in snap['slots']])]).unlink()
    Layer.search([('site_id', '=', site.id), ('uid', 'not in', [layer['uid'] for layer in snap['layers']])]).unlink()
    # 4) шари
    terms = {t.key: t.id for t in env['f3d.term'].search([('term_type', '=', 'slot_type')])}
    layers = {layer.uid: layer for layer in Layer.search([('site_id', '=', site.id)])}
    for item in snap['layers']:
        groups = []
        for xmlid in item.get('edit_groups') or []:
            group = env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups.append(group.id)
        vals = {
            'name': item['name'], 'kind': item['kind'], 'sequence': item['sequence'], 'elevation_m': item['elevation_m'],
            'grid_step_m': item['grid_step_m'], 'aisle_width_m': item['aisle_width_m'],
            'max_floor_load_kn_m2': item['max_floor_load_kn_m2'], 'bounds': item.get('bounds') or None,
            'allowed_slot_type_ids': [Command.set([terms[k] for k in item.get('allowed_slot_types') or [] if k in terms])],
            'edit_group_ids': [Command.set(groups)], 'color': item['color'], 'opacity': item['opacity'],
            'style': item['style'], 'visible': item['visible'], 'aisles': item['aisles'],
            'fire_paths': item['fire_paths'], 'utilities': item['utilities'],
            'underlay_params': item.get('underlay_params') or {}, 'active': item.get('active', True),
        }
        layer = layers.get(item['uid'])
        if layer:
            layer.write(vals)
        else:
            layers[item['uid']] = Layer.create(dict(vals, uid=item['uid'], site_id=site.id))
    # 5) місця
    slots = {s.uid: s for s in Slot.search([('site_id', '=', site.id)])}
    for item in snap['slots']:
        location = env['stock.location']
        if item.get('parent_location'):
            location = env['stock.location'].search([('complete_name', '=', item['parent_location'])], limit=1)
        vals = {
            'layer_id': layers[item['layer_uid']].id, 'template': item['template'], 'code_prefix': item['code_prefix'],
            'x_m': item['x_m'], 'y_m': item['y_m'], 'rotation': item['rotation'], 'params': item['params'],
            'overrides': item['overrides'], 'parent_location_id': location.id or False, 'active': item.get('active', True),
        }
        slot = slots.get(item['uid'])
        if slot:
            slot.write(vals)
        else:
            slots[item['uid']] = Slot.create(dict(vals, uid=item['uid']))
    # 6) розміщення
    placements = {p.uid: p for p in Placement.search([('site_id', '=', site.id)])}
    for item in snap['placements']:
        slot = slots.get(item['slot_uid']) if item.get('slot_uid') else None
        vals = {
            'layer_id': layers[item['layer_uid']].id, 'variant_id': variants[item['uid']].id,
            'slot_id': slot.id if slot else False, 'cell_code': item.get('cell_code') or False, 'code': item['code'],
            'name': item['name'], 'x_m': item['x_m'], 'y_m': item['y_m'], 'rotation': item['rotation'],
            'active': item.get('active', True),
        }
        placement = placements.get(item['uid'])
        if placement:
            placement.write(vals)
        else:
            placements[item['uid']] = Placement.create(dict(vals, uid=item['uid']))
    # 7) налаштування перевірок
    configs = {c.check_key: c for c in site.check_config_ids}
    for item in snap['check_configs']:
        vals = {'enabled': item['enabled'], 'mode': item['mode'], 'params': item['params']}
        if item['check'] in configs:
            configs[item['check']].write(vals)
        else:
            env['f3d.check.config'].create(dict(vals, site_id=site.id, check_key=item['check']))


def restore_draft(version):
    """R-14: чернетка = знімок версії; `draft_base_version_id = version`; лічильники — за правилом R-14."""
    site = version.site_id.sudo()
    snap = load_snapshot(version)
    apply_snapshot(site, snap)
    active = site.active_version_id
    if version == active:
        site.write({'draft_base_version_id': version.id, 'draft_rev': site.published_rev, 'draft_changes': 0})
    else:
        changes = count_differences(snap, load_snapshot(active)) if active and active.snapshot_id else 0
        site.write({'draft_base_version_id': version.id, 'draft_rev': site.draft_rev + 1, 'draft_changes': changes})
    return site
