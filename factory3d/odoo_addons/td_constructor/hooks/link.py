"""Крок «link» хука (R-24): зв'язування площадки з наявними stock.location / maintenance.equipment /
mrp.workcenter за кодом.

Нічого не створюється й не змінюється, крім службових полів: td_site_id, td_slot_uid, td_placement_uid,
placement.equipment_id / workcenter_id.

Збіг — за td_code, потім за другим кодом сцени td_alias (ворота DOCK-W1 = майданчик UNLOAD-1), потім за barcode.
"""

MAX_REPORTED_CODES = 2000


def link_existing(env, site):
    """Повертає `{'linked': {locations, equipment, workcenters}, 'unlinked': {locations: [...], equipment: [...]}}`."""
    env = env(su=True, context=dict(env.context, f3d_no_touch=True, tracking_disable=True, active_test=False))
    Loc, Equipment, Workcenter = env['stock.location'], env['maintenance.equipment'], env['mrp.workcenter']
    linked = {'locations': 0, 'equipment': 0, 'workcenters': 0}
    unlinked = {'locations': [], 'equipment': []}
    slots = env['td.slot'].search([('site_id', '=', site.id)])
    wanted = {}
    for slot in slots:
        for cell in slot._f3d_cells():
            wanted.setdefault(cell['code'], slot)
    if wanted:
        codes = list(wanted)
        found = Loc.search(['|', '|', ('td_code', 'in', codes), ('td_alias', 'in', codes), ('barcode', 'in', codes)])
        by_f3d = {r.td_code: r for r in found if r.td_code}
        by_alias = {r.td_alias: r for r in found if r.td_alias}
        by_barcode = {}
        for rec in found:
            if rec.barcode and rec.barcode not in by_barcode:
                by_barcode[rec.barcode] = rec
        for code, slot in wanted.items():
            rec = by_f3d.get(code) or by_alias.get(code) or by_barcode.get(code)
            if not rec or (rec.td_site_id and rec.td_site_id != site):
                unlinked['locations'].append(code)
                continue
            vals = {}
            if rec.td_site_id != site:
                vals['td_site_id'] = site.id
            if rec.td_slot_uid != slot.uid:
                vals['td_slot_uid'] = slot.uid
            if vals:
                rec.write(vals)
            linked['locations'] += 1
    has_wc_field = 'workcenter_id' in Equipment._fields
    for placement in env['td.placement'].search([('site_id', '=', site.id)]):
        code = placement.code
        eq = Equipment.search([('td_code', '=', code)], limit=1) or Equipment.search(
            [('td_alias', '=', code)], limit=1
        )
        if eq and not (eq.td_site_id and eq.td_site_id != site):
            vals = {}
            if eq.td_site_id != site:
                vals['td_site_id'] = site.id
            if eq.td_placement_uid != placement.uid:
                vals['td_placement_uid'] = placement.uid
            if vals:
                eq.write(vals)
            if placement.equipment_id != eq:
                placement.write({'equipment_id': eq.id})
            linked['equipment'] += 1
        else:
            unlinked['equipment'].append(code)
        wc = Workcenter.search(['|', ('td_code', '=', code), ('code', '=', code)], limit=1)
        if wc and not (wc.td_site_id and wc.td_site_id != site):
            if wc.td_site_id != site:
                wc.write({'td_site_id': site.id})
            if placement.workcenter_id != wc:
                placement.write({'workcenter_id': wc.id})
            linked['workcenters'] += 1
            if has_wc_field and eq and eq.workcenter_id != wc and not eq.workcenter_id:
                pass  # зв'язок equipment.workcenter_id — на розсуд mrp_maintenance; seed його не змінює
    unlinked['locations'] = unlinked['locations'][:MAX_REPORTED_CODES]
    return {'linked': linked, 'unlinked': unlinked}
