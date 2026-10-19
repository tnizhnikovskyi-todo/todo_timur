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
        'items': layer.items or [],
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
        # MERGE.md §3.3: ті самі імена, що в vals API-04 (посилання — id; null — не задано)
        'type_id': slot.type_id.id or None,
        'storage_category_id': slot.storage_category_id.id or None,
        'removal_strategy_id': slot.removal_strategy_id.id or None,
        'function_id': slot.function_id.id or None,
        'attr_ids': slot.attr_ids.ids,
        'temp_min_c': slot.temp_min_c,
        'temp_max_c': slot.temp_max_c,
        'tech': slot.tech or None,
        'addr': slot.addr or {},
        'depth_mode': slot.depth_mode or None,
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


def site_ext_dict(site):
    """Поля площадки MERGE.md §3.3 для `load` (`site.*`) і перевірок; порожні значення — типові (R-22)."""
    warehouse = site.warehouse_id
    variant = site.active_variant_id
    return {
        'warehouse': {'id': warehouse.id, 'name': warehouse.name, 'code': warehouse.code} if warehouse else None,
        'addr': site.addr or {},
        'loc_tree': site.loc_tree,
        'depth_mode': site.depth_mode,
        'sprinkler_height': site.sprinkler_height_m,
        'aisle_tech': site.aisle_tech or None,
        'parse_rules': site.parse_rules or {},
        'wizard_state': site.wizard_state or {},
        'active_variant': {'id': variant.id, 'name': variant.name} if variant else None,
        'odoo_baseline_id': site.odoo_baseline_id.id or None,
        'publish_copy_ack': site.publish_copy_ack,
    }


def type_dict(stype):
    return {
        'id': stype.id,
        'code': stype.code,
        'ref': stype.ref or None,
        'name': stype.name,
        'description': stype.description or '',
        'group': stype.group,
        'template': stype.template or None,
        'shape': stype.shape or None,
        'params': stype.params or {},
        'relevance': stype.relevance,
        'loc_kind': stype.loc_kind or None,
        'is_custom': stype.is_custom,
        'company_id': stype.company_id.id or None,
        'sequence': stype.sequence,
    }


def preset_dict(preset):
    return {
        'id': preset.id,
        'name': preset.name,
        'type_id': preset.type_id.id or None,
        'kind': preset.kind,
        'data': preset.data or {},
        'company_id': preset.company_id.id or None,
    }


def putaway_rule_dict(rule):
    return {
        'id': rule.id,
        'uid': rule.uid,
        'product_id': rule.product_id.id or None,
        'product': rule.product_id.display_name or None,
        'category_id': rule.category_id.id or None,
        'package_type_ids': rule.package_type_ids.ids,
        'in_location_id': rule.in_location_id.id or None,
        'out_code': rule.out_code or None,
        'out_location_id': rule.out_location_id.id or None,
        'sublocation': rule.sublocation,
        'storage_category_id': rule.storage_category_id.id or None,
        'sequence': rule.sequence,
        'odoo_rule_id': rule.odoo_rule_id.id or None,
        'deleted': rule.deleted,
        'etag': etag_of(rule),
    }


def replenish_rule_dict(rule):
    return {
        'id': rule.id,
        'uid': rule.uid,
        'product_id': rule.product_id.id or None,
        'product': rule.product_id.display_name or None,
        'cell_code': rule.cell_code or None,
        'location_id': rule.location_id.id or None,
        'min_qty': rule.min_qty,
        'max_qty': rule.max_qty,
        'odoo_orderpoint_id': rule.odoo_orderpoint_id.id or None,
        'deleted': rule.deleted,
        'etag': etag_of(rule),
    }


def library_state(env):
    """`types` і `presets` для `load`: активні записи, доступні користувачеві (ir.rule по компанії)."""
    return {
        'types': [type_dict(t) for t in env['td.slot.type'].search([])],
        'presets': [preset_dict(p) for p in env['td.slot.preset'].search([])],
    }


def rules_state(site):
    """`rules` для `load`: чернетки правил розміщення й поповнення площадки (разом із позначеними `deleted`)."""
    env = site.env
    return {
        'putaway': [putaway_rule_dict(r) for r in env['td.putaway.rule'].search([('site_id', '=', site.id)])],
        'replenish': [replenish_rule_dict(r) for r in env['td.replenish.rule'].search([('site_id', '=', site.id)])],
    }


def variant_dict(variant):
    data = variant._td_local_geometry()
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
    slots = site.env['td.slot'].search([('site_id', '=', site.id), ('layer_id', 'in', layers.ids)])
    placements = site.env['td.placement'].search([('site_id', '=', site.id), ('layer_id', 'in', layers.ids)])
    variants = placements.mapped('variant_id')
    layer_data = []
    for layer in layers:
        data = layer_dict(layer)
        layer_data.append(data)
    from . import capacity  # лише тут: capacity імпортує state

    return {
        'extra': lambda scene: capacity.check_extra(site, scene),
        'site': {
            'building': {
                'length': site.building_length_m,
                'width': site.building_width_m,
                'height': site.building_height_m,
            },
            'column_grid': {'step_x': site.column_step_x_m, 'step_y': site.column_step_y_m},
            'sprinkler_height': site.sprinkler_height_m,
            'aisle_tech': site.aisle_tech or None,
            'addr': site.addr or None,
            'depth_mode': site.depth_mode or 'level',
        },
        'layers': layer_data,
        'slots': [slot_dict(s) for s in slots],
        'placements': [placement_dict(p) for p in placements],
        'variants': [variant._td_local_geometry() for variant in variants],
    }


def check_configs(site):
    return [
        {'check': c.check_key, 'enabled': c.enabled, 'mode': c.mode, 'params': c.params or {}}
        for c in site.check_config_ids.sorted('sequence')
    ]


def eps_m(env):
    try:
        return float(env['ir.config_parameter'].sudo().get_param('td.constructor.eps_mm', 1)) / 1000.0
    except ValueError:
        return checks_mod.DEFAULT_EPS_M


def run_site_checks(site, layer_id=None):
    """Перевірки чернетки площадки (R-04…R-10) для API-05 і публікації; повертає список issue."""
    issues = checks_mod.run_checks(checks_state(site), check_configs(site), eps_m(site.env))
    if layer_id:
        issues = [i for i in issues if i['layer_id'] == layer_id]
    return issues
