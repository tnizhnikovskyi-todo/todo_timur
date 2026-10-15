from odoo import models


class F3dFirePassageSourceAccess(models.AbstractModel):
    _name = 'f3d.fire.passage.source.access'   # БЕЗ _inherit: factory3d_fire_safety не є залежністю
    _description = 'СКУД: проходи для навчальної тривоги'
    _f3d_priority = 10

    def _f3d_on_site(self, at):
        res = self.env['f3d.access.event'].f3d_on_site_at(at)
        Event = self.env['f3d.access.event'].sudo()
        out = []
        for emp in res['employees']:
            last = Event.search([('employee_id', '=', emp.id), ('is_perimeter', '=', True),
                                 ('event_type', '=', 'pass'), ('direction', '=', 'in'), ('ts', '<=', at)],
                                order='ts desc, id desc', limit=1)
            out.append({'employee_id': emp.id, 'since': last.ts or emp.f3d_access_last_in,
                        'point': last.door_id.code or ''})
        return out

    def _f3d_passages(self, start, end):
        events = self.env['f3d.access.event'].sudo().f3d_passes_between(start, end).filtered(
            lambda e: e.is_perimeter and e.employee_id)
        return [{'employee_id': e.employee_id.id, 'ts': e.ts, 'point': e.door_id.code or '',
                 'direction': e.direction} for e in events]

    def _f3d_drill_active(self, ts):
        return self.env['f3d.access.event']._f3d_drill_active(ts)
