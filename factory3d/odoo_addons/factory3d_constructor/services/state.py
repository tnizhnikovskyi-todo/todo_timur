"""Стан площадки у форматі API-03 (`load`): спільний для контролера, перевірок (R-04…R-10) і плану публікації (R-12).

Працює з записами ORM (на відміну від чистих geometry/cells/checks): читає від імені поточного середовища.
Метри — для шарів/місць/розміщень, міліметри — для варіантів.
"""

from . import checks as checks_mod


def etag_of(record):
    return record.write_date.strftime('%Y-%m-%d %H:%M:%S.%f') if record.write_date else ''


def layer_dict(layer, env_xmlids=None):
    underlay = None
    if layer.underlay_attachment_id:
        underlay = {
            'url': '/web/content/%d' % layer.underlay_attachment_id.id,
            'name': layer.underlay_attachment_id.name,
            'format': layer.underlay_format,
            'status': layer.underlay_status,
            'params': layer.underlay_params or {},
        }
    groups = []
    for group in layer.sudo().edit_group_ids:
        xmlid = (env_xmlids or {}).get(group.id) or ''
        groups.append({'id': group.id, 'name': group.name, 'role': xmlid.rsplit('_', 1)[-1] if xmlid else ''})
    return {
        'id': layer.id,
        'uid': layer.uid,
        'name': layer.name,
        'kind': layer.kind,
        'group': layer.group_name or None,
        'sequence': layer.sequence,
        'elevation': layer.elevation_m,
        'grid_step': layer.grid_step_m,
        'aisle_width': layer.aisle_width_m,
        'max_floor_load': layer.max_floor_load_kn_m2,
        'bounds': layer.bounds or None,
        'slot_types': layer.allowed_slot_type_ids.mapped('key'),
        'edit_groups': groups,
        'color': layer.color,
        'opacity': layer.opacity,
        'style': layer.style,
        'visible': layer.visible,
        'aisles': layer.aisles or [],
        'fire_paths': layer.fire_paths or [],
        'utilities': layer.utilities or [],
        'underlay': underlay,
        'etag': etag_of(layer),
    }


def slot_dict(slot):
    return {
        'id': slot.id,
        'uid': slot.uid,
        'layer_id': slot.layer_id.id,
        'template': slot.template,
        'code_prefix': slot.code_prefix,
        'x': slot.x_m,
        'y': slot.y_m,
        'rotation': slot.rotation,
        'params': slot.params or {},
        'overrides': slot.overrides or {},
        'parent_location_id': slot.parent_location_id.id or None,
        'cell_count': slot.cell_count,
        'etag': etag_of(slot),
    }


def placement_dict(placement):
    equipment = placement.equipment_id
    return {
        'id': placement.id,
        'uid': placement.uid,
        'layer_id': placement.layer_id.id,
        'variant_id': placement.variant_id.id,
        'slot_id': placement.slot_id.id or None,
        'cell_code': placement.cell_code or None,
        'x': placement.x_m,
        'y': placement.y_m,
        'rotation': placement.rotation,
        'dynamic': placement.dynamic,
        'code': placement.code,
        'name': placement.name,
        'equipment': {'id': equipment.id, 'name': equipment.name} if equipment else None,
        'etag': etag_of(placement),
    }


def variant_dict(variant):
    data = variant._f3d_local_geometry()
    model = None
    if variant.model_status != 'none':
        meta = variant.model_meta or {}
        model = {
            'status': variant.model_status,
            'meta': meta,
            'warning': variant.model_warning or None,
            'glb_url': ('/f3d/constructor/model/%d/glb' % variant.id) if variant.model_glb_id else None,
        }
    data.update({'model': model, 'etag': etag_of(variant)})
    return data


def checks_state(site):
    """Стан чернетки для `run_checks`: лише активні шари, місця й розміщення; варіанти — ті, що використані."""
    layers = site.layer_ids.filtered('active')
    slots = site.env['f3d.slot'].search([('site_id', '=', site.id), ('layer_id', 'in', layers.ids)])
    placements = site.env['f3d.placement'].search([('site_id', '=', site.id), ('layer_id', 'in', layers.ids)])
    variants = placements.mapped('variant_id')
    layer_data = []
    for layer in layers:
        data = layer_dict(layer)
        layer_data.append(data)
    return {
        'site': {
            'building': {
                'length': site.building_length_m,
                'width': site.building_width_m,
                'height': site.building_height_m,
            }
        },
        'layers': layer_data,
        'slots': [slot_dict(s) for s in slots],
        'placements': [placement_dict(p) for p in placements],
        'variants': [variant._f3d_local_geometry() for variant in variants],
    }


def check_configs(site):
    return [
        {'check': c.check_key, 'enabled': c.enabled, 'mode': c.mode, 'params': c.params or {}}
        for c in site.check_config_ids.sorted('sequence')
    ]


def eps_m(env):
    try:
        return float(env['ir.config_parameter'].sudo().get_param('factory3d.constructor.eps_mm', 1)) / 1000.0
    except ValueError:
        return checks_mod.DEFAULT_EPS_M


def run_site_checks(site, layer_id=None):
    """Перевірки чернетки площадки (R-04…R-10) для API-05 і публікації; повертає список issue."""
    issues = checks_mod.run_checks(checks_state(site), check_configs(site), eps_m(site.env))
    if layer_id:
        issues = [i for i in issues if i['layer_id'] == layer_id]
    return issues
