from datetime import datetime, time

from odoo import fields, models

from ..tools.dates import local_day_start_utc, to_local_str
from ..tools.event_codes import classify

SECURITY = 'td_access.group_td_access_security'
FMT = '%Y-%m-%d %H:%M'
BUS_MODELS = ['hr.employee', 'td.access.door', 'td.access.visitor']


def _loc(value):
    """naive UTC -> «YYYY-MM-DD HH:MM» за Києвом; порожнє -> None."""
    return to_local_str(value, fmt=FMT) if value else None


def _plural(n, forms):
    """Українська множина: (1, 2–4, 5+) за правилом n%10 / n%100."""
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def _last_event(last):
    if not last:
        return None
    return {'ts': _loc(last['ts']), 'door': last['door'], 'direction': last['direction'], 'type': last['type']}


class F3dViewerProviderAccess(models.AbstractModel):
    _name = 'td.viewer.provider.access'       # БЕЗ _inherit: td_viewer3d не є залежністю (A-19)
    _description = '3D: СКУД — люди, двері, зчитувачі'
    _td_sequence = 170
    _td_sections = ('access',)
    _td_group = 'td_factory3d.group_td_user'

    def _td_viewer_bus_models(self):
        return list(BUS_MODELS)

    def _td_day_start(self, ctx):
        """Початок «сьогодні» (naive UTC) за `ctx['today']` (доба за Києвом)."""
        today = ctx.get('today')
        if today:
            day = datetime.strptime(str(today)[:10], '%Y-%m-%d')
            return local_day_start_utc(datetime.combine(day.date(), time(12)))
        return local_day_start_utc(ctx.get('now') or fields.Datetime.now())

    def _td_viewer_collect(self, payload, ctx):
        """R-12 кроки 1–5."""
        ctx = ctx or {}
        is_sec = self.env.user.has_group(SECURITY)
        pres = self.env['hr.employee']._td_access_public_presence()
        # крок 2: працівники, що вже є у payload (чужі записи не створюються)
        for code, rec in (payload.get('employees') or {}).items():
            info = pres.get(code)
            if info is None:
                continue
            rec['present'] = bool(info['present'])
            rec['zone'] = info['zone']
            rec['zone_since'] = _loc(info['zone_since'])
            rec['last_event'] = _last_event(info['last_event'])
        data = self.env['td.access.viewer.data']._td_viewer_data(self._td_day_start(ctx), with_names=is_sec)
        zones = {code: n for code, n in data['zones'].items() if n}
        # крок 3
        for code, rec in (payload.get('zones') or {}).items():
            rec['people_now'] = zones.get(code, 0)
        # крок 4
        employees_n = data['employees_on_site']
        visitors_n = len(data['visitors'])
        server = data['server']
        today = data['today']
        now = ctx.get('now') or fields.Datetime.now()
        access = {
            'updated': ctx.get('now_local') or to_local_str(now, fmt=FMT),
            'server': {'name': server['name'], 'state': server['state'], 'stale': bool(server['stale']),
                       'last_contact': _loc(server['last_contact'])}
            if server else {'name': None, 'state': 'offline', 'stale': False, 'last_contact': None},
            'on_site': {'employees': employees_n, 'visitors': visitors_n, 'total': employees_n + visitors_n},
            'today': today,
            'zones': zones,
            'people': {code: {'present': bool(i['present']), 'zone': i['zone'], 'zone_since': _loc(i['zone_since']),
                              'last_event': _last_event(i['last_event'])} for code, i in pres.items()},
            'visitors': [self._td_visitor_item(v, is_sec) for v in data['visitors']],
            'readers': {r['code']: {
                'name': r['name'], 'zone': r['zone'], 'x': r['x'], 'y': r['y'], 'status': r['status'],
                'last_event': {'ts': _loc(r['last_event_ts']), 'code': r['last_event_code'],
                               'type': self._td_code_type(r['last_event_code'])} if r['last_event_ts'] else None,
            } for r in data['readers']},
            'doors': {d['code']: {k: v for k, v in d.items() if k != 'code'} for d in data['doors']},
            'cards': self._td_cards(data, server, is_sec),
            'last_events': [{
                'ts': _loc(e['ts']), 'door': e['door'], 'device': e['device'], 'direction': e['direction'],
                'type': e['type'], 'code': e['code'], 'person': e['person']} for e in data['last_events']],
        }
        payload['access'] = access
        # крок 5: статичні рядки карток замінюються живими
        cards = (payload.get('infra') or {}).get('cards')
        if isinstance(cards, dict):
            for key in ('TURNSTILES', 'ACCESS'):
                if key in cards and isinstance(cards[key], dict):
                    cards[key]['rows'] = access['cards'][key]['rows']
        return payload

    @staticmethod
    def _td_visitor_item(visitor, is_sec):
        item = {'code': 'V-%d' % visitor['id'], 'zone': visitor['zone'], 'since': _loc(visitor['since'])}
        if is_sec:
            item['name'] = visitor['name']
        return item

    @staticmethod
    def _td_code_type(code):
        return classify(code)['event_type']

    @staticmethod
    def _td_cards(data, server, is_sec):
        employees_n = data['employees_on_site']
        visitors_n = len(data['visitors'])
        poll = _loc(server['last_poll_at'])[11:] if server and server['last_poll_at'] else '—'
        last = data['last_pass']
        if last:
            name = last['door_name'] or ''
            text = "%s, %s" % (name[:1].lower() + name[1:], to_local_str(last['ts'], fmt='%H:%M'))
            if is_sec and last['person']:
                text += " — " + last['person']
        else:
            text = '—'
        return {
            'TURNSTILES': {'rows': [
                ['На території зараз', "%d %s · %d %s" % (
                    employees_n, _plural(employees_n, ('працівник', 'працівники', 'працівників')),
                    visitors_n, _plural(visitors_n, ('відвідувач', 'відвідувачі', 'відвідувачів')))],
                ['Сьогодні проходів', str(data['today']['passes'])],
                ['Odoo Attendances', 'відмітки входу й виходу щохвилини · опитування %s' % poll]]},
            'ACCESS': {'rows': [['Дверей з рідерами', str(data['doors_with_readers'])],
                                ['Останній доступ', text]]},
        }

    def _td_viewer_delta(self, patch, ctx):
        """R-12 п. 7: дельта шини; власний розділ — цілком, чужі розділи — лише доповнення."""
        ctx = ctx or {}
        changes = ctx.get('changes') or {}
        if not set(changes) & set(BUS_MODELS):
            return patch
        from odoo.addons.td_viewer3d.tools.payload import deep_merge  # лише коли viewer установлено (A-19)
        tmp = {
            'employees': {c: {} for c in changes.get('hr.employee', ())},
            'zones': {z: {} for z in self.env['td.zone'].search([]).mapped('td_code')},
            'infra': {'cards': {'TURNSTILES': {}, 'ACCESS': {}}},
        }
        self._td_viewer_collect(tmp, ctx)
        patch['access'] = tmp['access']
        for key in ('employees', 'zones', 'infra'):
            if tmp[key]:
                deep_merge(patch.setdefault(key, {}), tmp[key])
        return patch


class F3dAccessVisitorBus(models.Model):
    """Зміни присутності відвідувача -> шина переглядача (R-12 крок 6)."""
    _inherit = 'td.access.visitor'

    def _td_presence_set(self, vals):
        changed = super()._td_presence_set(vals)
        if changed:
            collector = self.env.context.get('f3d_bus_collector')
            codes = {'V-%d' % self.id}
            if collector is not None:
                collector.setdefault('td.access.visitor', set()).update(codes)
            else:
                self.env['td.access.event']._td_bus('td.access.visitor', codes)
        return changed


