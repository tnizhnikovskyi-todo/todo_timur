import hashlib
import hmac
import json
import logging
from datetime import timedelta

from odoo import fields, http
from odoo.http import request

from ..models.sim_panel import parse_iso_utc

_logger = logging.getLogger(__name__)
MODULE_VERSION = '19.0.2.0.0'
MAX_EVENTS = 100
MAX_BODY = 256 * 1024
EVENT_KINDS = ('scenario', 'fault', 'alarm', 'info', 'error')
RUN_DONE_STATES = ('done', 'failed', 'stopped')
ETAG_MODELS = ('td.sim.device', 'td.sim.signal', 'td.zone', 'stock.picking.batch', 'hr.employee')


def _json(data, status=200, headers=None):
    return request.make_json_response(data, headers=headers, status=status)


def _error(status, code, detail=''):
    return _json({'error': code, 'detail': detail}, status=status)


def _auth_error():
    """None, якщо токен вірний; інакше готова відповідь 503/401."""
    expected = (request.env['ir.config_parameter'].sudo().get_param('td.iot_sim.export_token') or '').strip()
    if not expected:
        return _json({'error': 'export token not configured'}, status=503)
    header = request.httprequest.headers.get('Authorization', '')
    token = header[7:].strip() if header.lower().startswith('bearer ') else ''
    if not hmac.compare_digest(token.encode(), expected.encode()):
        return _error(401, 'unauthorized', 'invalid token')
    return None


def _hhmm(value):
    hours = int(round(value * 60))
    return '%02d:%02d' % (hours // 60, hours % 60)


class F3dSimApi(http.Controller):

    # --- API-02 ---
    @http.route('/f3d/sim/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health(self, **kw):
        env = request.env(su=True)
        panel = env['td.sim.panel'].search([], limit=1)
        return _json({
            'ok': True, 'module': 'td_iot_sim', 'version': MODULE_VERSION,
            'devices': env['td.sim.device'].search_count([]),
            'signals': env['td.sim.signal'].search_count([]),
            'panel_state': panel.state or 'unconfigured',
        })

    # --- API-01 ---
    def _etag(self, env):
        parts = []
        for model in ETAG_MODELS:
            Model = env[model].with_context(active_test=False)
            env.cr.execute('SELECT max(write_date), count(*) FROM "%s"' % Model._table)
            last, count = env.cr.fetchone()
            parts.append('%s:%s:%s' % (model, last, count))
        return '"%s"' % hashlib.sha256('|'.join(parts).encode()).hexdigest()

    @http.route('/f3d/sim/devices', type='http', auth='public', methods=['GET'], csrf=False)
    def devices(self, protocol=None, **kw):
        denied = _auth_error()
        if denied:
            return denied
        env = request.env(su=True)
        etag = self._etag(env)
        if protocol is None:
            sent = request.httprequest.headers.get('If-None-Match', '')
            if sent.strip() == etag or sent.strip().removeprefix('W/') == etag:
                return request.make_response('', headers=[('ETag', etag)], status=304)
        domain = [('protocol', '=', protocol)] if protocol else []
        devices = env['td.sim.device'].search(domain)
        data = {
            'version': 1,
            'generated_at': fields.Datetime.now().isoformat() + 'Z',
            'odoo': self._odoo_info(env),
            'devices': self._devices(env, devices),
            'zones': self._zones(env),
            'docks': self._docks(env),
            'shifts': self._shifts(env),
            'employees': self._employees(env),
            'bookings': self._bookings(env),
        }
        return _json(data, headers=[('ETag', etag)])

    def _odoo_info(self, env):
        company = env.company
        return {'db': env.cr.dbname, 'company': company.name, 'tz': env.user.tz or 'Europe/Kyiv',
                'base_url': env['ir.config_parameter'].get_param('web.base.url')}

    def _devices(self, env, devices):
        signals = {}
        for sig in env['td.sim.signal'].search([('device_id', 'in', devices.ids)]):
            signals.setdefault(sig.device_id.id, []).append({
                'code': sig.code, 'address': sig.address, 'dtype': sig.dtype or '', 'unit': sig.unit or '',
                'scale': sig.scale or '', 'nominal': sig.nominal or '', 'thresholds': sig.thresholds or '',
                'model_rule': sig.model_rule or '', 'kind': sig.kind})
        result = []
        for dev in devices:
            eq, wc, zone = dev.equipment_id, dev.workcenter_id, dev.zone_id
            result.append({
                'code': dev.code, 'name': dev.name,
                'kind': 'workcenter' if wc else ('equipment' if eq else 'virtual'),
                'role': dev.role or None,
                'protocol': dev.protocol, 'driver': dev.driver, 'unit_id': dev.unit_id,
                'instance': dev.instance, 'address': dev.address or '', 'params': dev.params or {},
                'enabled': dev.enabled,
                'equipment': {
                    'id': eq.id, 'manufacturer': eq.td_manufacturer or None, 'model': eq.td_model or None,
                    'serial': eq.serial_no or None, 'power_kw': eq.td_power_kw, 'units': eq.td_units,
                } if eq else None,
                'workcenter': {'code': wc.td_code, 'name': wc.name, 'id': wc.id} if wc else None,
                'zone': {'code': zone.td_code, 'name': zone.name} if zone else None,
                'signals': signals.get(dev.id, []),
            })
        return result

    def _zones(self, env):
        zones = []
        for zone in env['td.zone'].search([]):
            polygon = zone.polygon or []
            if len(polygon) >= 3:
                zones.append({'code': zone.td_code, 'name': zone.name, 'type': zone.zone_type,
                              'polygon': polygon})
        return zones

    def _docks(self, env):
        docks = []
        for loc in env['stock.location'].search([('td_kind', '=', 'dock')], order='td_side, td_dock_no'):
            docks.append({'code': loc.td_code, 'side': loc.td_side, 'no': loc.td_dock_no,
                          'accepts': loc.td_accepts.mapped('name'), 'location_id': loc.id,
                          'x': loc.td_x, 'y': loc.td_y})
        return docks

    def _shifts(self, env):
        shifts = []
        for cal in env['resource.calendar'].search([('company_id', 'in', [env.company.id, False])]):
            shifts.append({
                'name': cal.name, 'tz': cal.tz or 'Europe/Kyiv',
                'attendances': [{'weekday': int(att.dayofweek), 'from': _hhmm(att.hour_from),
                                 'to': _hhmm(att.hour_to)} for att in cal.attendance_ids
                                if not att.display_type]})
        return shifts

    def _employees(self, env):
        result = []
        for emp in env['hr.employee'].search([('barcode', '!=', False)]):
            code = emp.td_code or ''
            result.append({
                'code': code or None, 'name': emp.name, 'barcode': emp.barcode,
                'job': emp.job_title or emp.job_id.name or None,
                'workcenter': code[3:] if code.startswith('OP-') else None,
                'shift': emp.resource_calendar_id.name or None})
        return result

    def _bookings(self, env):
        now = fields.Datetime.now()
        Batch = env['stock.picking.batch']
        domain = [('state', 'in', ['draft', 'in_progress']), ('dock_id', '!=', False),
                  ('scheduled_date', '>=', now - timedelta(days=2)),
                  ('scheduled_date', '<=', now + timedelta(days=2))]
        has_plate = 'td_plate' in Batch._fields
        bookings = []
        for batch in Batch.search(domain):
            incoming = batch.picking_type_id.code == 'incoming' if batch.picking_type_id else False
            bookings.append({
                'batch': batch.name, 'truck': batch.td_code or None,
                'plate': (batch.td_plate or None) if has_plate else None,
                'dock': batch.dock_id.td_code, 'type': 'incoming' if incoming else 'outgoing',
                'scheduled': batch.scheduled_date.isoformat() + 'Z' if batch.scheduled_date else None,
                'state': batch.state, 'pickings': batch.picking_ids.mapped('name'),
                'partner': batch.picking_ids[:1].partner_id.name or None})
        return bookings

    # --- API-03 ---
    @http.route('/f3d/sim/events', type='http', auth='public', methods=['POST'], csrf=False)
    def events(self, **kw):
        denied = _auth_error()
        if denied:
            return denied
        raw = request.httprequest.get_data()
        if len(raw) > MAX_BODY:
            return _error(413, 'payload_too_large', 'body > 256 KB')
        try:
            body = json.loads(raw.decode('utf-8'))
            events = body['events']
            if not isinstance(events, list):
                raise ValueError('events must be a list')
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
            return _error(400, 'bad_request', 'invalid JSON: %s' % exc)
        if len(events) > MAX_EVENTS:
            return _error(413, 'too_many_events', 'max %d events' % MAX_EVENTS)
        env = request.env(su=True)
        accepted, rejected, seen = 0, [], set()
        for index, item in enumerate(events):
            reason = self._accept_event(env, item, seen)
            if reason:
                rejected.append({'index': index, 'reason': reason})
            else:
                accepted += 1
        return _json({'accepted': accepted, 'rejected': rejected})

    def _accept_event(self, env, item, seen):
        if not isinstance(item, dict):
            return 'not an object'
        kind, message = item.get('kind'), item.get('message')
        if kind not in EVENT_KINDS:
            return 'invalid kind'
        if not message:
            return 'message required'
        ts = parse_iso_utc(item.get('ts'))
        if not ts:
            return 'invalid ts'
        payload = item.get('payload') if isinstance(item.get('payload'), dict) else {}
        event_id = payload.get('event_id')
        if event_id:
            event_id = str(event_id)
            env['td.sim.event'].flush_model()
            env.cr.execute("SELECT 1 FROM td_sim_event WHERE payload->>'event_id' = %s LIMIT 1", (event_id,))
            if event_id in seen or env.cr.fetchone():
                return 'duplicate'
            seen.add(event_id)
        Run = env['td.sim.run']
        run = Run
        if item.get('run_ref'):
            run = Run.search([('name', '=', item['run_ref'])], limit=1)
        if not run and item.get('sim_run_id'):
            run = Run.search([('sim_run_id', '=', item['sim_run_id'])], limit=1)
        env['td.sim.event'].create({
            'ts': ts, 'kind': kind, 'device_code': item.get('device') or False, 'run_id': run.id or False,
            'message': str(message)[:500], 'payload': payload})
        if run and kind == 'scenario' and payload.get('state') in RUN_DONE_STATES:
            run.write({'state': payload['state'], 'stop_ts': ts})
        return None
