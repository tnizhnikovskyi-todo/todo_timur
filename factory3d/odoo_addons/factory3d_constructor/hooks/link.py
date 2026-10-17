"""Крок «link» хука (R-24): зв'язування площадки з наявними stock.location / maintenance.equipment /
mrp.workcenter за кодом.

Нічого не створюється й не змінюється, крім службових полів: f3d_site_id, f3d_slot_uid, f3d_placement_uid,
placement.equipment_id / workcenter_id.

Збіг — за f3d_code, потім за другим кодом сцени f3d_alias (ворота DOCK-W1 = майданчик UNLOAD-1), потім за barcode.
"""

MAX_REPORTED_CODES = 2000


def link_existing(env, site):
    """Повертає `{'linked': {locations, equipment, workcenters}, 'unlinked': {locations: [...], equipment: [...]}}`."""
    env = env(su=True, context=dict(env.context, f3d_no_touch=True, tracking_disable=True, active_test=False))
    Loc, Equipment, Workcenter = env['stock.location'], env['maintenance.equipment'], env['mrp.workcenter']
    linked = {'locations': 0, 'equipment': 0, 'workcenters': 0}
    unlinked = {'locations': [], 'equipment': []}
    slots = env['f3d.slot'].search([('site_id', '=', site.id)])
    wanted = {}
    for slot in slots:
        for cell in slot._f3d_cells():
            wanted.setdefault(cell['code'], slot)
    if wanted:
        codes = list(wanted)
        found = Loc.search(['|', '|', ('f3d_code', 'in', codes), ('f3d_alias', 'in', codes), ('barcode', 'in', codes)])
        by_f3d = {r.f3d_code: r for r in found if r.f3d_code}
        by_alias = {r.f3d_alias: r for r in found if r.f3d_alias}
        by_barcode = {}
        for rec in found:
            if rec.barcode and rec.barcode not in by_barcode:
                by_barcode[rec.barcode] = rec
        for code, slot in wanted.items():
            rec = by_f3d.get(code) or by_alias.get(code) or by_barcode.get(code)
            if not rec or (rec.f3d_site_id and rec.f3d_site_id != site):
                unlinked['locations'].append(code)
                continue
            vals = {}
            if rec.f3d_site_id != site:
                vals['f3d_site_id'] = site.id
            if rec.f3d_slot_uid != slot.uid:
                vals['f3d_slot_uid'] = slot.uid
            if vals:
                rec.write(vals)
            linked['locations'] += 1
    has_wc_field = 'workcenter_id' in Equipment._fields
    for placement in env['f3d.placement'].search([('site_id', '=', site.id)]):
        code = placement.code
        eq = Equipment.search([('f3d_code', '=', code)], limit=1) or Equipment.search(
            [('f3d_alias', '=', code)], limit=1
        )
        if eq and not (eq.f3d_site_id and eq.f3d_site_id != site):
            vals = {}
            if eq.f3d_site_id != site:
                vals['f3d_site_id'] = site.id
            if eq.f3d_placement_uid != placement.uid:
                vals['f3d_placement_uid'] = placement.uid
            if vals:
                eq.write(vals)
            if placement.equipment_id != eq:
                placement.write({'equipment_id': eq.id})
            linked['equipment'] += 1
        else:
            unlinked['equipment'].append(code)
        wc = Workcenter.search(['|', ('f3d_code', '=', code), ('code', '=', code)], limit=1)
        if wc and not (wc.f3d_site_id and wc.f3d_site_id != site):
            if wc.f3d_site_id != site:
                wc.write({'f3d_site_id': site.id})
            if placement.workcenter_id != wc:
                placement.write({'workcenter_id': wc.id})
            linked['workcenters'] += 1
            if has_wc_field and eq and eq.workcenter_id != wc and not eq.workcenter_id:
                pass  # зв'язок equipment.workcenter_id — на розсуд mrp_maintenance; seed його не змінює
    unlinked['locations'] = unlinked['locations'][:MAX_REPORTED_CODES]
    return {'linked': linked, 'unlinked': unlinked}
