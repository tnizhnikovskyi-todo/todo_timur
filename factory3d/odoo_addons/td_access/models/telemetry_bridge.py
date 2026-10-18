import logging

from odoo import api, fields, models

from ..tools import params as P

_logger = logging.getLogger(__name__)


class F3dAccessTelemetry(models.AbstractModel):
    _name = 'td.access.telemetry'
    _description = 'СКУД: публікація сигналів телеметрії'

    @api.model
    def _f3d_signal_model(self):
        """Модель сигналів telemetry (sudo) або None; окремий метод — тести підставляють фейк."""
        if 'td.signal' not in self.env:
            return None
        return self.env['td.signal'].sudo()

    @api.model
    def _f3d_publish(self, server, events):
        """R-18: показання телеметрії за новими подіями опитування; без персональних даних (A-28)."""
        if not events or not P.get_flag(self.env, 'publish_signals'):
            return None
        signals = self._f3d_signal_model()
        if signals is None:
            return None
        now = fields.Datetime.now()
        events = events.sudo().sorted(lambda e: (e.ts, e.id))
        readings = []
        last_by_device = {}
        for ev in events:
            if ev.event_type in ('pass', 'denied', 'fail') and ev.device_id.code:
                last_by_device[ev.device_id] = ev
        for device, ev in last_by_device.items():
            readings.append({
                'code': 'access/readers/%s/last_event' % device.code, 'ts': ev.ts, 'value': float(ev.code),
                'text': ("%s %s" % (ev.code, ev.door_id.code or '')).strip()[:64], 'q': 'good'})
        on_site = self.env['td.access.event'].f3d_on_site_at(now)
        total = len(on_site['employees']) + len(on_site['visitors'])
        counts = {kind: len(events.filtered(lambda e, k=kind: e.event_type == k))
                  for kind in ('pass', 'denied', 'door')}
        readings.append({'code': 'access/turnstiles/TURNSTILES/on_site', 'ts': now, 'value': float(total)})
        readings.append({'code': 'access/events', 'ts': now, 'value': float(len(events)),
                         'text': "pass:%(pass)d denied:%(denied)d door:%(door)d" % counts})
        return signals._f3d_ingest(readings, src='module')
