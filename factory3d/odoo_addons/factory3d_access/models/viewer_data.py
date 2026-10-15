from datetime import timedelta

from odoo import api, models

from ..tools import params as P


class F3dAccessViewerData(models.AbstractModel):
    """Агрегати СКУД для провайдера переглядача (A-21): читання від sudo, без персональних даних.

    Імена людей повертаються лише при `with_names=True` (охорона). Метод не публічний для RPC.
    """
    _name = 'f3d.access.viewer.data'
    _description = 'СКУД: агрегати для переглядача'

    @api.model
    def _f3d_viewer_data(self, start, with_names=False):
        """Дані розділу `access` за добу, що починається в `start` (naive UTC)."""
        env = self.sudo().env
        end = start + timedelta(hours=24)
        Event = env['f3d.access.event']
        Employee = env['hr.employee']
        has_visitor = 'f3d.access.visitor' in env
        visitors = env['f3d.access.visitor'].search(
            [('present', '=', True), ('state', '=', 'on_site')], order='id') if has_visitor else []
        zone_counts = {}
        for zone, n in Employee._read_group(
                [('f3d_access_present', '=', True), ('f3d_access_zone_id', '!=', False)],
                ['f3d_access_zone_id'], ['__count']):
            zone_counts[zone.f3d_code] = zone_counts.get(zone.f3d_code, 0) + n
        for visitor in visitors:
            if visitor.zone_id:
                code = visitor.zone_id.f3d_code
                zone_counts[code] = zone_counts.get(code, 0) + 1
        day = [('ts', '>=', start), ('ts', '<', end)]
        today = {'events': 0, 'passes': 0, 'entries': 0, 'exits': 0, 'denied': 0}
        for etype, direction, perimeter, n in Event._read_group(
                day, ['event_type', 'direction', 'is_perimeter'], ['__count']):
            today['events'] += n
            if etype == 'pass':
                today['passes'] += n
                if perimeter and direction == 'in':
                    today['entries'] += n
                elif perimeter and direction == 'out':
                    today['exits'] += n
            elif etype in ('denied', 'fail'):
                today['denied'] += n
        door_passes = {door.id: n for door, n in Event._read_group(
            day + [('event_type', '=', 'pass')], ['door_id'], ['__count']) if door}
        server = env['f3d.access.server'].search([('active', '=', True)], order='sequence, id', limit=1)
        doors = env['f3d.access.door'].search([('active', '=', True)], order='code')
        last_pass = Event.search([('event_type', '=', 'pass'), ('door_id.is_perimeter', '=', False)],
                                 order='ts desc, id desc', limit=1)
        res = {
            'server': {'name': server.name, 'state': server.state, 'stale': server.stale,
                       'last_contact': server.last_contact, 'last_poll_at': server.last_poll_at}
            if server else None,
            'employees_on_site': Employee.search_count([('f3d_access_present', '=', True)]),
            'visitors': [{'id': v.id, 'zone': v.zone_id.f3d_code or None, 'since': v.arrived_at,
                          'name': v.name if with_names else None} for v in visitors],
            'zones': zone_counts,
            'today': today,
            'readers': [{
                'code': d.code, 'name': d.name, 'zone': d.zone_id.f3d_code or None, 'x': d.x, 'y': d.y,
                'status': d.status, 'last_event_ts': d.last_event_ts, 'last_event_code': d.last_event_code,
            } for d in env['f3d.access.device'].search([('active', '=', True)], order='code')],
            'doors': [{
                'code': d.code, 'name': d.name, 'kind': d.kind, 'state': d.state, 'alarm': bool(d.alarm),
                'alarm_reason': d.alarm_reason or None, 'is_perimeter': bool(d.is_perimeter),
                'zone_from': d.zone_from_id.f3d_code or None, 'zone_to': d.zone_to_id.f3d_code or None,
                'passes_today': door_passes.get(d.id, 0),
            } for d in doors],
            'doors_with_readers': len(doors.filtered(lambda d: d.entry_device_id or d.exit_device_id)),
            'last_pass': {
                'door_name': last_pass.door_id.name, 'ts': last_pass.ts,
                'person': (last_pass.employee_id.name or (
                    last_pass['visitor_id'].name if has_visitor else '')) if with_names else None,
            } if last_pass else None,
            'last_events': [],
        }
        limit = P.get_int(env, 'last_events_limit', 20, 0, 100)
        if with_names and limit:
            for ev in Event.search([], order='ts desc, id desc', limit=limit):
                person = ev.employee_id.f3d_code or None
                if not person and has_visitor and ev['visitor_id']:
                    person = 'V-%d' % ev['visitor_id'].id
                res['last_events'].append({
                    'ts': ev.ts, 'door': ev.door_id.code or None, 'device': ev.device_id.code or None,
                    'direction': ev.direction, 'type': ev.event_type, 'code': ev.code, 'person': person})
        return res
