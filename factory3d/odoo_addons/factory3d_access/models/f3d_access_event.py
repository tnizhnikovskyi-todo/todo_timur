import logging
from copy import deepcopy
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..tools import params as P
from ..tools.dates import local_date, parse_bs_dt, to_local_str
from ..tools.event_codes import classify

_logger = logging.getLogger(__name__)

SECURITY = 'factory3d_access.group_f3d_access_security'
SCOPE = 'factory3d_access.group_f3d_access_security,hr_attendance.group_hr_attendance_user'
FIRE_CODE = 26368
GC_BATCH = 5000


class F3dAccessEvent(models.Model):
    _name = 'f3d.access.event'
    _description = 'СКУД: подія BioStar'
    _order = 'ts desc, id desc'
    _log_access = False

    server_id = fields.Many2one('f3d.access.server', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='server_id.company_id', store=True, index=True)
    biostar_id = fields.Char(string='ID події BioStar', required=True, size=64)
    ts = fields.Datetime(string='Час', required=True, index=True)
    server_ts = fields.Datetime(string='Час сервера')
    received_at = fields.Datetime(string='Отримано', required=True, default=fields.Datetime.now)
    code = fields.Integer(string='Код події', required=True, index=True)
    code_name = fields.Char(string='Назва коду', compute='_compute_code_name')
    event_type = fields.Selection(
        [('pass', 'Прохід'), ('fail', 'Невдала ідентифікація'), ('denied', 'Відмова'), ('door', 'Двері'),
         ('alarm', 'Тривога'), ('system', 'Система'), ('other', 'Інше')],
        string='Тип', required=True, index=True)
    credential = fields.Selection(
        [('card', 'Картка'), ('face', 'Обличчя'), ('finger', 'Відбиток'), ('id_face', 'ID + обличчя'),
         ('id_finger', 'ID + відбиток'), ('pin', 'ID + PIN'), ('other', 'Інше')], string='Спосіб')
    deny_reason = fields.Selection(
        [('access_group', 'Немає в групі доступу'), ('disabled', 'Користувач вимкнений'),
         ('expired', 'Строк дії минув'), ('blacklist', 'Чорний список'), ('apb', 'Антипрохід'),
         ('timed_apb', 'Антипрохід за часом'), ('scheduled_lock', 'Заблоковано розкладом'),
         ('other', 'Інше')], string='Причина відмови')
    tna_key = fields.Char(string='Клавіша T&A', size=4)
    direction = fields.Selection(
        [('in', 'Вхід'), ('out', 'Вихід'), ('none', '—')], string='Напрямок', required=True, default='none')
    raw_device_id = fields.Char(string='ID пристрою BioStar', size=64)
    raw_door_id = fields.Char(string='ID дверей BioStar', size=64)
    raw_user_id = fields.Char(string='Користувач BioStar', size=64, index=True, groups=SCOPE)
    device_id = fields.Many2one('f3d.access.device', string='Пристрій', index=True, ondelete='set null')
    door_id = fields.Many2one('f3d.access.door', string='Двері', index=True, ondelete='set null')
    is_perimeter = fields.Boolean(string='Периметр', index=True)
    zone_from_id = fields.Many2one('f3d.zone', ondelete='set null')
    zone_to_id = fields.Many2one('f3d.zone', ondelete='set null')
    link_id = fields.Many2one('f3d.access.user.link', ondelete='set null')
    employee_id = fields.Many2one('hr.employee', string='Працівник', index=True, ondelete='set null')
    # W3: visitor_id (Many2one f3d.access.visitor, index, ondelete set null) — у models/f3d_access_visitor.py
    unknown_user = fields.Boolean(string='Нерозпізнаний', index=True)
    process_state = fields.Selection(
        [('new', 'Нова'), ('done', 'Оброблена'), ('error', 'Помилка')], required=True, default='new', index=True)
    attendance_action = fields.Selection(
        [('none', '—'), ('checked_in', 'Вхід: нова відмітка'), ('attached', "Прив'язано до відкритої відмітки"),
         ('checked_out', 'Вихід: відмітку закрито'), ('merged', 'Злито з попередньою відміткою'),
         ('duplicate', 'Повторний вхід'), ('no_open', 'Вихід без відкритої відмітки'),
         ('drill', 'Навчальна тривога'), ('late', 'Запізніла подія'),
         ('future', 'Відкладено: час у майбутньому'), ('not_employee', 'Не працівник')],
        string='Дія з відміткою', required=True, default='none')
    attendance_id = fields.Many2one('hr.attendance', string='Відмітка', ondelete='set null')
    presence_changed = fields.Boolean(string='Змінено присутність/зону')
    apb_suspect = fields.Boolean(string='Підозра на антипрохід', index=True)
    zone_violation = fields.Boolean(string='Порушення дозволених зон', index=True)
    error_message = fields.Char(string='Помилка обробки', size=255)
    raw = fields.Json(groups='factory3d_base.group_f3d_admin')

    _f3d_access_event_uniq = models.Constraint(
        "UNIQUE(server_id, biostar_id)", "Подія BioStar уже збережена (дублікат).")
    _f3d_access_event_emp_ts_idx = models.Index("(employee_id, ts)")
    _f3d_access_event_door_ts_idx = models.Index("(door_id, ts)")

    @api.depends('code')
    def _compute_code_name(self):
        for ev in self:
            ev.code_name = classify(ev.code)['name']

    @api.depends('ts', 'door_id', 'device_id', 'raw_device_id', 'code')
    def _compute_display_name(self):
        for ev in self:
            where = ev.door_id.code or ev.device_id.code or ev.raw_device_id or ''
            ev.display_name = "%s · %s · %s" % (to_local_str(ev.ts), where, classify(ev.code)['name'])

    # ------------------------------------------------------------------ приймання рядків (R-11 крок 5)
    @api.model
    def _f3d_parse_row(self, server, row, cache=None):
        """Рядок API-06 -> vals події; невалідний рядок -> ValueError."""
        row_id = str(row.get('id') or '')
        if not P.BSID_RE.match(row_id):
            raise ValueError("Невалідний id події: %r" % row_id)
        ts = parse_bs_dt(row.get('datetime'))
        if not ts:
            raise ValueError("Немає datetime")
        code = int(row['event_type_id']['code'])
        cls = classify(code)
        door_raw = row.get('door_id')
        if isinstance(door_raw, list):
            door_raw = door_raw[0] if door_raw else {}
        door_raw = door_raw or {}
        raw_device = str((row.get('device_id') or {}).get('id') or '')
        raw_door = str(door_raw.get('id') or '')
        raw_user = str((row.get('user_id') or {}).get('user_id') or '')
        if cache is None:
            cache = self._f3d_ref_cache(server)
        device = cache['devices'].get(raw_device)
        door = cache['doors'].get(raw_door) if raw_door else None
        if not door and device:
            door = cache['by_device'].get(device.id)
        vals = {
            'server_id': server.id, 'biostar_id': row_id, 'ts': ts,
            'server_ts': parse_bs_dt(row.get('server_datetime')) or False, 'code': code,
            'event_type': cls['event_type'], 'credential': cls['credential'] or False,
            'deny_reason': cls['deny_reason'] or False, 'tna_key': str(row.get('tna_key') or ''),
            'raw_device_id': raw_device, 'raw_door_id': raw_door, 'raw_user_id': raw_user,
            'device_id': device.id if device else False, 'door_id': door.id if door else False,
        }
        if cache['keep_raw']:
            raw = deepcopy(row)
            if isinstance(raw.get('user_id'), dict):
                raw['user_id'].pop('name', None)
                raw['user_id'].pop('photo_exists', None)
            raw.pop('hint', None)
            vals['raw'] = raw
        return vals

    @api.model
    def _f3d_ref_cache(self, server):
        devices = self.env['f3d.access.device'].sudo().search([('server_id', '=', server.id)])
        doors = self.env['f3d.access.door'].sudo().search([('server_id', '=', server.id)])
        by_device = {}
        for door in doors:
            for dev in (door.entry_device_id | door.exit_device_id):
                by_device.setdefault(dev.id, door)
        return {'devices': {d.biostar_id: d for d in devices if d.biostar_id},
                'doors': {d.biostar_id: d for d in doors if d.biostar_id},
                'by_device': by_device, 'keep_raw': P.get_flag(self.env, 'keep_raw')}

    @api.model
    def _f3d_ingest_rows(self, server, rows):
        """Зберегти рядки; -> {'created', 'duplicates', 'invalid', 'records'}."""
        server = server.sudo()
        cache = self._f3d_ref_cache(server)
        parsed, seen, duplicates, invalid = [], set(), 0, 0
        for row in rows:
            try:
                vals = self._f3d_parse_row(server, row, cache)
            except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
                invalid += 1
                _logger.warning("СКУД: невалідний рядок події id=%s: %s", row.get('id') if isinstance(row, dict)
                                else None, exc)
                continue
            if vals['biostar_id'] in seen:
                duplicates += 1
                continue
            seen.add(vals['biostar_id'])
            parsed.append(vals)
        existing = set()
        ids = [v['biostar_id'] for v in parsed]
        for i in range(0, len(ids), 1000):
            for rec in self.sudo().search_read(
                    [('server_id', '=', server.id), ('biostar_id', 'in', ids[i:i + 1000])], ['biostar_id']):
                existing.add(rec['biostar_id'])
        fresh = [v for v in parsed if v['biostar_id'] not in existing]
        duplicates += len(parsed) - len(fresh)
        records = self.browse()
        for i in range(0, len(fresh), 500):
            records |= self.sudo().create(fresh[i:i + 500])
        return {'created': len(records), 'duplicates': duplicates, 'invalid': invalid, 'records': records}

    # ------------------------------------------------------------------ обробка (R-02…R-10)
    def _f3d_process(self, force=False):
        """Обробити події у порядку (ts, id); кожна — у savepoint; помилка -> process_state='error'."""
        collector = {}
        events = self.sudo().with_context(f3d_bus_collector=collector)
        events = events.filtered(lambda e: force or e.process_state == 'new').sorted(lambda e: (e.ts, e.id))
        params = {
            'dup': P.get_int(self.env, 'dup_window_min', 20, 0, 1440),
            'merge_gap': P.get_int(self.env, 'merge_gap_min', 0, 0, 1440),
            'max_shift': P.get_int(self.env, 'max_shift_h', 16, 1, 72),
            'stale': P.get_flag(self.env, 'stale_close_enabled'),
        }
        for ev in events:
            try:
                with self.env.cr.savepoint():
                    ev._f3d_process_one(params)
            except Exception as exc:  # noqa: BLE001 - будь-яка помилка події ізолюється
                _logger.error("СКУД: помилка обробки події %s: %s", ev.biostar_id, exc, exc_info=True)
                ev.write({'process_state': 'error', 'error_message': str(exc)[:255]})
        for model, codes in collector.items():
            self._f3d_bus(model, codes)

    def _f3d_link_and_door(self, vals):
        """R-03 (кроки 1) і R-02/копії з дверей (крок 2) -> vals події."""
        self.ensure_one()
        server = self.server_id
        link = self.link_id
        if self.raw_user_id and (not link or link.match == 'none'):
            link = self.env['f3d.access.user.link']._f3d_match_employee(self.raw_user_id, server)
        employee = link.employee_id if link else self.env['hr.employee']
        visitor = link['visitor_id'] if link and 'visitor_id' in link._fields else False
        vals['link_id'] = link.id if link else False
        vals['employee_id'] = employee.id if employee else False
        if 'visitor_id' in self._fields:
            vals['visitor_id'] = visitor.id if visitor else False
        vals['unknown_user'] = bool(self.raw_user_id) and not (employee or visitor)
        door, device = self.door_id, self.device_id
        vals['is_perimeter'] = door.is_perimeter
        vals['zone_from_id'] = door.zone_from_id.id
        vals['zone_to_id'] = door.zone_to_id.id
        direction = 'none'
        if self.event_type in ('pass', 'denied', 'fail') and door and device:
            if device == door.exit_device_id:
                direction = 'out'
            elif device.direction == 'tna':
                if self.tna_key == '1':
                    direction = 'in'
                elif self.tna_key == '2':
                    direction = 'out'
                else:
                    vals['error_message'] = "Невідомий напрямок: tna_key порожній"
            else:
                direction = device.direction
        vals['direction'] = direction if direction in ('in', 'out') else 'none'
        return employee, visitor

    def _f3d_door_state(self):
        """R-10 для подій door/alarm."""
        self.ensure_one()
        cls = classify(self.code)
        doors = self.door_id
        if self.code == FIRE_CODE:  # пожежна тривога зони стосується всіх дверей сервера (рішення W2)
            doors = self.env['f3d.access.door'].sudo().search(
                [('server_id', '=', self.server_id.id), ('active', '=', True)])
        if not doors:
            return
        reason = cls['alarm_reason'] or False
        state = cls['door_state'] or None
        if self.code == FIRE_CODE:
            state = None
        if not state and not reason:
            return
        doors._f3d_set_state(state, self.ts, alarm=True if reason else None, reason=reason or None)

    def _f3d_process_one(self, params):
        """Конвеєр R-04 для однієї події."""
        self.ensure_one()
        now = fields.Datetime.now()
        vals = {'attendance_action': 'none', 'error_message': False, 'presence_changed': False,
                'apb_suspect': False, 'zone_violation': False}
        employee, visitor = self._f3d_link_and_door(vals)
        self.write(dict(vals))
        # крок 3: стан пристрою
        device = self.device_id
        if device and (not device.last_event_ts or self.ts >= device.last_event_ts):
            device.sudo().write({'last_event_ts': self.ts, 'last_event_code': self.code})
        # крок 4
        if self.event_type in ('door', 'alarm'):
            self._f3d_door_state()
        if self.event_type != 'pass':
            return self._f3d_finish(vals)
        # крок 5
        if not employee:
            if visitor:
                vals.update(self._f3d_visitor_pass(visitor))
            return self._f3d_finish(vals)
        # крок 6
        if self.ts > now:
            vals['attendance_action'] = 'future'
            self.write(vals)
            return None
        # крок 7
        last = employee.f3d_access_last_event_id
        if last and last != self and last.ts > self.ts:
            vals['attendance_action'] = 'late'
            return self._f3d_finish(vals)
        tz = employee._get_tz()
        Attendance = self.env['hr.attendance'].sudo()
        open_att = Attendance.browse()
        # крок 8
        if self.is_perimeter:
            open_att = Attendance.search(
                [('employee_id', '=', employee.id), ('check_out', '=', False)], order='check_in desc', limit=1)
            if (open_att and params['stale'] and self.ts - open_att.check_in > timedelta(hours=params['max_shift'])):
                open_att._f3d_close_by_rule()
                open_att = Attendance.browse()
        # крок 9
        was_present = employee.f3d_access_present
        same_day = bool(employee.f3d_access_last_in
                        and local_date(employee.f3d_access_last_in, tz) == local_date(self.ts, tz))
        # крок 10
        attendance = Attendance.browse()
        if self.is_perimeter:
            if vals['direction'] == 'in':
                attendance = self._f3d_perimeter_in(employee, open_att, was_present, same_day, params, vals)
            elif vals['direction'] == 'out':
                attendance = self._f3d_perimeter_out(open_att, vals)
        if attendance:
            vals['attendance_id'] = attendance.id
        # крок 11
        self._f3d_presence(employee, was_present, same_day, vals)
        return self._f3d_finish(vals)

    def _f3d_finish(self, vals):
        vals['process_state'] = 'done'
        self.write(vals)

    def _f3d_visitor_pass(self, visitor):
        """Прохід відвідувача (R-14 кроки 3–4) — розширюється в W3; тут лише журнал."""
        return {'attendance_action': 'not_employee'}

    def _f3d_perimeter_in(self, employee, open_att, was_present, same_day, params, vals):
        Attendance = self.env['hr.attendance'].sudo()
        device = self.device_id
        if self._f3d_drill_active(self.ts):
            vals['attendance_action'] = 'drill'
            return Attendance.browse()
        if open_att:
            gap = abs(self.ts - open_att.check_in)
            if not open_att.f3d_in_event_id and gap <= timedelta(minutes=params['dup']):
                open_att.write({'f3d_in_event_id': self.id, 'f3d_in_device_id': device.id})
                vals['attendance_action'] = 'attached'
            elif was_present and same_day:
                vals['attendance_action'] = 'duplicate'
                vals['apb_suspect'] = True
            else:
                if not open_att.f3d_in_event_id:
                    open_att.write({'f3d_in_event_id': self.id, 'f3d_in_device_id': device.id})
                vals['attendance_action'] = 'attached'
            return open_att
        merged = self._f3d_try_merge(employee, params['merge_gap'])
        if merged:
            vals['attendance_action'] = 'merged'
            return merged
        vals['attendance_action'] = 'checked_in'
        if was_present and same_day:
            vals['apb_suspect'] = True
        return Attendance.create({
            'employee_id': employee.id, 'check_in': self.ts, 'in_mode': 'biostar',
            'f3d_in_event_id': self.id, 'f3d_in_device_id': device.id})

    def _f3d_try_merge(self, employee, merge_gap):
        """R-06: повернути закриту біостар-відмітку, якщо вихід був менше за merge_gap хв тому."""
        if merge_gap <= 0:
            return self.env['hr.attendance']
        Attendance = self.env['hr.attendance'].sudo()
        last = Attendance.search([
            ('employee_id', '=', employee.id), ('check_out', '!=', False), ('out_mode', '=', 'biostar'),
            ('check_out', '>=', self.ts - timedelta(minutes=merge_gap)), ('check_out', '<=', self.ts)],
            order='check_out desc', limit=1)
        tz = employee._get_tz()
        if last and local_date(last.check_in, tz) == local_date(self.ts, tz):
            last.write({'check_out': False, 'out_mode': 'manual', 'f3d_out_event_id': False,
                        'f3d_out_device_id': False})
            return last
        return self.env['hr.attendance']

    def _f3d_perimeter_out(self, open_att, vals):
        Attendance = self.env['hr.attendance'].sudo()
        if self._f3d_drill_active(self.ts):
            vals['attendance_action'] = 'drill'
            return Attendance.browse()
        if not open_att:
            vals['attendance_action'] = 'no_open'
            return Attendance.browse()
        if self.ts <= open_att.check_in:
            vals['attendance_action'] = 'no_open'
            vals['error_message'] = "Вихід раніше за вхід відмітки"
            return Attendance.browse()
        open_att.write({'check_out': self.ts, 'out_mode': 'biostar', 'f3d_out_event_id': self.id,
                        'f3d_out_device_id': self.device_id.id})
        vals['attendance_action'] = 'checked_out'
        return open_att

    def _f3d_presence(self, employee, was_present, same_day, vals):
        """R-08: присутність і зона працівника за графом дверей."""
        door, ts, direction = self.door_id, self.ts, vals['direction']
        home = employee.f3d_home_zone_id
        upd = {}
        if self.is_perimeter:
            if direction == 'in':
                zone = home or door.zone_to_id
                upd = {'f3d_access_present': True, 'f3d_access_zone_id': zone.id, 'f3d_access_zone_since': ts,
                       'f3d_access_zone_door_id': False, 'f3d_access_last_in': ts}
                if was_present and same_day:
                    vals['apb_suspect'] = True
            elif direction == 'out':
                upd = {'f3d_access_present': False, 'f3d_access_zone_id': False,
                       'f3d_access_zone_since': False, 'f3d_access_zone_door_id': False,
                       'f3d_access_last_out': ts}
                if not was_present:
                    vals['apb_suspect'] = True
        elif direction == 'in' and door.zone_to_id:
            changed_zone = employee.f3d_access_zone_id != door.zone_to_id or not was_present
            upd = {'f3d_access_present': True, 'f3d_access_zone_id': door.zone_to_id.id,
                   'f3d_access_zone_door_id': door.id if door.dwell_min > 0 else False}
            if changed_zone:
                upd['f3d_access_zone_since'] = ts
            if not was_present:
                vals['apb_suspect'] = True
        elif direction == 'out' and door.zone_from_id:
            zone = home or door.zone_from_id
            upd = {'f3d_access_present': True, 'f3d_access_zone_id': zone.id, 'f3d_access_zone_since': ts,
                   'f3d_access_zone_door_id': False}
        changed = self._f3d_diff(employee, upd)
        vals['presence_changed'] = bool(changed)
        upd['f3d_access_last_event_id'] = self.id
        employee._f3d_access_set(upd)

    @staticmethod
    def _f3d_diff(employee, upd):
        diff = {}
        for name, value in upd.items():
            current = employee[name]
            current = current.id if hasattr(current, 'id') else current
            if (current or False) != (value or False):
                diff[name] = value
        return diff

    # ------------------------------------------------------------------ повторна обробка
    def action_reprocess(self):
        self._check_admin()
        todo = self.sudo().filtered(lambda e: e.process_state in ('new', 'error'))
        todo._f3d_process(force=True)
        for ev in (self.sudo() - todo).filtered(lambda e: not e.attendance_id):
            ev._f3d_process(force=True)
        for ev in (self.sudo() - todo).filtered('attendance_id'):
            vals = {}
            ev._f3d_link_and_door(vals)
            ev.write(vals)
        return True

    def _check_admin(self):
        if not self.env.su and not self.env.user.has_group('factory3d_access.group_f3d_access_admin'):
            raise AccessError("Обробляти події повторно може лише адміністратор СКУД.")

    # ------------------------------------------------------------------ службові методи (R-21)
    @api.model
    def f3d_on_site_at(self, ts, company=None):
        """Хто був на території о `ts`: {'employees', 'visitors', 'ts'}."""
        hours = P.get_int(self.env, 'max_shift_h', 16, 1, 72)
        cids = (company.ids if company else self.env.companies.ids) or [self.env.company.id]
        self.flush_model()
        self.env['hr.employee'].flush_model()
        self.env.cr.execute("""
            SELECT employee_id FROM (
              SELECT DISTINCT ON (employee_id) employee_id, direction
                FROM f3d_access_event
               WHERE employee_id IS NOT NULL AND is_perimeter AND event_type = 'pass'
                 AND direction IN ('in', 'out') AND ts <= %(ts)s
                 AND ts >= %(ts)s - make_interval(hours => %(h)s) AND company_id = ANY(%(cids)s)
               ORDER BY employee_id, ts DESC, id DESC) last
             WHERE direction = 'in'""", {'ts': ts, 'h': hours, 'cids': cids})
        ids = {r[0] for r in self.env.cr.fetchall()}
        self.env.cr.execute("""
            SELECT e.id FROM hr_employee e
             WHERE e.active AND e.f3d_access_present AND e.f3d_access_last_in <= %(ts)s
               AND e.company_id = ANY(%(cids)s)
               AND NOT EXISTS (SELECT 1 FROM f3d_access_event ev WHERE ev.employee_id = e.id
                                  AND ev.is_perimeter AND ev.event_type = 'pass')""", {'ts': ts, 'cids': cids})
        ids |= {r[0] for r in self.env.cr.fetchall()}
        return {'employees': self.env['hr.employee'].sudo().browse(sorted(ids)),
                'visitors': self._f3d_on_site_visitors(ts, cids, hours), 'ts': ts}

    @api.model
    def _f3d_on_site_visitors(self, ts, cids, hours):
        """Відвідувачі на території о `ts` — розширюється в W3."""
        return self.env['hr.employee'].browse() if 'f3d.access.visitor' not in self.env \
            else self.env['f3d.access.visitor'].browse()

    @api.model
    def f3d_passes_between(self, t0, t1, door_codes=None, direction=None):
        domain = [('event_type', '=', 'pass'), ('ts', '>=', t0), ('ts', '<=', t1)]
        if door_codes:
            domain.append(('door_id.code', 'in', list(door_codes)))
        if direction:
            domain.append(('direction', '=', direction))
        return self.search(domain, order='ts, id')

    @api.model
    def _f3d_drill_active(self, ts):
        """CA-09: навчальна тривога активна о `ts` (контракт до factory3d_fire_safety)."""
        if 'f3d.fire.drill' not in self.env or not hasattr(self.env['f3d.fire.drill'], '_f3d_is_active_at'):
            return False
        return bool(self.env['f3d.fire.drill'].sudo()._f3d_is_active_at(ts))

    @api.model
    def _f3d_last_events(self, limit=20):
        return self.sudo().search_read(
            [('event_type', 'in', ('pass', 'denied', 'fail', 'door', 'alarm'))],
            ['ts', 'door_id', 'device_id', 'direction', 'event_type', 'code', 'employee_id'],
            order='ts desc, id desc', limit=limit)

    @api.model
    def _f3d_bus(self, model, codes):
        """R-12 крок 6: сповістити переглядач; окремий метод — тести його підміняють."""
        if not codes or 'f3d.viewer.event' not in self.env:
            return
        self.env['f3d.viewer.event'].sudo()._notify(model, codes, 'state')

    # ------------------------------------------------------------------ крони й господарство (R-17, R-20)
    @api.model
    def _gc(self, keep_days):
        cutoff = fields.Datetime.now() - timedelta(days=keep_days)
        total = 0
        while True:
            batch = self.sudo().search([('ts', '<', cutoff)], limit=GC_BATCH)
            if not batch:
                break
            batch.unlink()
            total += len(batch)
            if not self.env.context.get('f3d_no_commit') and not self.env.registry.in_test_mode():
                self.env.cr.commit()
        return total

    @api.model
    def _cron_zone_dwell(self):
        """R-17: повернення з технічних приміщень у домашню зону."""
        now = fields.Datetime.now()
        collector = {}
        employees = self.env['hr.employee'].sudo().with_context(f3d_bus_collector=collector).search(
            [('f3d_access_present', '=', True), ('f3d_access_zone_door_id', '!=', False)])
        for emp in employees:
            door = emp.f3d_access_zone_door_id
            if door.dwell_min > 0 and emp.f3d_access_zone_since \
                    and emp.f3d_access_zone_since + timedelta(minutes=door.dwell_min) <= now:
                emp._f3d_access_set({
                    'f3d_access_zone_id': (emp.f3d_home_zone_id or door.zone_from_id).id,
                    'f3d_access_zone_since': now, 'f3d_access_zone_door_id': False})
        self._f3d_dwell_visitors(now, collector)
        for model, codes in collector.items():
            self._f3d_bus(model, codes)

    @api.model
    def _f3d_dwell_visitors(self, now, collector):
        """R-17 для відвідувачів — розширюється в W3."""
        return None

    @api.model
    def _f3d_housekeeping_visitors(self, now, keep_days):
        """R-20 кроки 3, 5, 6 (відвідувачі й картки) — розширюється в W3."""
        return None

    @api.model
    def _cron_housekeeping(self):
        """R-20: ротація, закриття відміток, відвідувачі, перевірка вікна, картки."""
        now = fields.Datetime.now()
        keep_days = P.get_int(self.env, 'keep_days', 90, 1, 3650)
        steps = [
            ('ротація подій', lambda: self._gc(keep_days)),
            ('закриття відміток', lambda: self._f3d_close_stale_attendances(now)),
            ('відвідувачі й картки', lambda: self._f3d_housekeeping_visitors(now, keep_days)),
        ]
        if P.get_flag(self.env, 'read_enabled'):
            steps.append(('перевірка вікна', lambda: self._f3d_recheck_window(now)))
        for name, step in steps:
            try:
                with self.env.cr.savepoint():
                    step()
            except Exception:  # noqa: BLE001 - крок не повинен зупиняти решту
                _logger.error("СКУД: господарство, крок «%s» не виконано", name, exc_info=True)

    @api.model
    def _f3d_close_stale_attendances(self, now):
        """R-20 крок 2 (R-07 б)."""
        if not P.get_flag(self.env, 'stale_close_enabled'):
            return 0
        max_shift = timedelta(hours=P.get_int(self.env, 'max_shift_h', 16, 1, 72))
        links = self.env['f3d.access.user.link'].sudo().search(
            [('employee_id', '!=', False), ('in_biostar', '=', True)])
        open_atts = self.env['hr.attendance'].sudo().search(
            [('check_out', '=', False), ('employee_id', 'in', links.employee_id.ids),
             ('check_in', '<', now - max_shift)])
        todo = open_atts.filtered(
            lambda a: local_date(a.check_in, a.employee_id._get_tz()) < local_date(now, a.employee_id._get_tz()))
        todo._f3d_close_by_rule()
        return len(todo)

    @api.model
    def _f3d_recheck_window(self, now):
        """R-20 крок 4: повторне опитування вікна recheck_hours для кожного активного сервера."""
        hours = P.get_int(self.env, 'recheck_hours', 24, 1, 168)
        for server in self.env['f3d.access.server'].sudo().search([('active', '=', True)]):
            try:
                with self.env.cr.savepoint():
                    server._poll_window(now - timedelta(hours=hours), now)
            except Exception as exc:  # noqa: BLE001 - недоступний сервер не зупиняє господарство
                _logger.warning("СКУД: перевірка вікна %s: %s", server.name, exc)
