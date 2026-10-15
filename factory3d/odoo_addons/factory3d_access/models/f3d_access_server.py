import logging
from datetime import timedelta

from psycopg2 import errors as pg_errors

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import params as P
from ..tools.biostar_client import BioStarClient, BioStarError
from ..tools.dates import parse_bs_dt

_logger = logging.getLogger(__name__)

GROUP_ADMIN = 'factory3d_access.group_f3d_access_admin'
GROUP_F3D_ADMIN = 'factory3d_base.group_f3d_admin'
READ_DISABLED = "Опитування BioStar вимкнено стоп-краном factory3d.access.read_enabled."


class F3dAccessServer(models.Model):
    _name = 'f3d.access.server'
    _description = 'СКУД: сервер BioStar 2'
    _order = 'sequence, id'

    name = fields.Char(string='Назва', required=True, size=64, default='BioStar 2')
    sequence = fields.Integer(default=10)
    url = fields.Char(
        string='URL сервера', required=True, size=255,
        help='Напр. https://iot-sim:8443 (стенд) або https://biostar.local (прод)')
    verify_ssl = fields.Boolean(string='Перевіряти сертифікат', default=True)
    timeout_connect_s = fields.Integer(string="Тайм-аут з'єднання, с", default=5)
    timeout_read_s = fields.Integer(string='Тайм-аут відповіді, с', default=30)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True, default=lambda self: self.env.company)
    session_id = fields.Char(
        string='Сесія (bs-session-id)', size=128, readonly=True, copy=False, groups=GROUP_F3D_ADMIN)
    state = fields.Selection(
        [('offline', 'Не підключено'), ('online', 'Онлайн'), ('error', 'Помилка')],
        required=True, default='offline', readonly=True, copy=False)
    stale = fields.Boolean(compute='_compute_stale')
    last_contact = fields.Datetime(string='Останній контакт', readonly=True)
    last_error = fields.Char(string='Остання помилка', size=255, readonly=True)
    last_error_ts = fields.Datetime(readonly=True)
    error_count = fields.Integer(string='Помилок поспіль', default=0, readonly=True)
    next_try_at = fields.Datetime(string='Наступна спроба', readonly=True)
    last_event_ts = fields.Datetime(string='Курсор: час останньої події', readonly=True, copy=False)
    last_event_biostar_id = fields.Char(string='Курсор: id останньої події', size=64, readonly=True, copy=False)
    last_poll_at = fields.Datetime(string='Останнє опитування', readonly=True)
    last_poll_rows = fields.Integer(string='Рядків в останньому опитуванні', readonly=True)
    last_poll_new = fields.Integer(string='Нових подій в останньому опитуванні', readonly=True)
    last_poll_more = fields.Boolean(string='Є ще сторінки', readonly=True)
    users_total = fields.Integer(string='Користувачів у BioStar', readonly=True)
    devices_total = fields.Integer(string='Пристроїв у BioStar', readonly=True)
    users_synced_at = fields.Datetime(readonly=True)
    devices_synced_at = fields.Datetime(readonly=True)
    device_ids = fields.One2many('f3d.access.device', 'server_id', string='Пристрої')
    door_ids = fields.One2many('f3d.access.door', 'server_id', string='Двері')
    link_count = fields.Integer(compute='_compute_counts')
    unlinked_count = fields.Integer(compute='_compute_counts')
    event_count = fields.Integer(compute='_compute_counts')
    error_event_count = fields.Integer(compute='_compute_counts')
    doors_without_zone = fields.Integer(compute='_compute_counts')

    _f3d_access_server_timeouts = models.Constraint(
        "CHECK(timeout_connect_s BETWEEN 1 AND 60 AND timeout_read_s BETWEEN 1 AND 300)",
        "Тайм-аути: з'єднання 1–60 с, відповідь 1–300 с.")

    # ------------------------------------------------------------------ CRUD і обмеження
    @staticmethod
    def _strip_url(vals):
        if isinstance(vals.get('url'), str):
            vals['url'] = vals['url'].strip().rstrip('/')
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._strip_url(dict(v)) for v in vals_list])

    def write(self, vals):
        return super().write(self._strip_url(dict(vals)))

    @api.constrains('url', 'verify_ssl')
    def _check_url(self):
        environment = self.env['ir.config_parameter'].sudo().get_param('factory3d.base.environment')
        for rec in self:
            if not P.URL_RE.match(rec.url or ''):
                raise ValidationError(
                    "URL сервера BioStar: очікується http(s)://хост[:порт], напр. https://iot-sim:8443")
            if not rec.verify_ssl and environment != 'test':
                raise ValidationError(
                    "Вимкнути перевірку сертифіката можна лише в тестовому середовищі "
                    "(factory3d.base.environment = test).")
            if rec.url.startswith('http://') and environment != 'test':
                raise ValidationError("HTTP без TLS дозволено лише в тестовому середовищі.")

    # ------------------------------------------------------------------ обчислювані
    @api.depends('state', 'last_contact')
    def _compute_stale(self):
        interval = P.get_int(self.env, 'poll_interval_s', 60, 10, 3600)
        limit = fields.Datetime.now() - timedelta(seconds=3 * interval)
        for rec in self:
            rec.stale = rec.state == 'online' and bool(rec.last_contact) and rec.last_contact < limit

    def _compute_counts(self):
        has_event = 'f3d.access.event' in self.env
        for rec in self:
            link = self.env['f3d.access.user.link']
            rec.link_count = link.search_count([('server_id', '=', rec.id)])
            rec.unlinked_count = link.search_count(
                [('server_id', '=', rec.id), ('match', '=', 'none'), ('in_biostar', '=', True)])
            if has_event:
                event = self.env['f3d.access.event']
                rec.event_count = event.search_count([('server_id', '=', rec.id)])
                rec.error_event_count = event.search_count(
                    [('server_id', '=', rec.id), ('process_state', '=', 'error')])
            else:
                rec.event_count = rec.error_event_count = 0
            rec.doors_without_zone = self.env['f3d.access.door'].search_count(
                [('server_id', '=', rec.id), ('active', '=', True), ('zone_to_id', '=', False)])

    # ------------------------------------------------------------------ клієнт і стан
    def _get_client(self):
        self.ensure_one()
        return BioStarClient(
            self.url, login=P.get_str(self.env, 'biostar_login', 'admin'),
            password=P.get_str(self.env, 'biostar_password', ''), verify_ssl=self.verify_ssl,
            timeout=(self.timeout_connect_s, self.timeout_read_s),
            session_id=self.sudo().session_id or None, write_enabled=P.get_flag(self.env, 'write_enabled'))

    def _save_session(self, client):
        for rec in self:
            if client.session_id != rec.sudo().session_id:
                rec.sudo().write({'session_id': client.session_id})

    def _mark_ok(self):
        self.sudo().write({'state': 'online', 'last_contact': fields.Datetime.now(), 'error_count': 0,
                           'next_try_at': False})

    def _mark_error(self, exc):
        now = fields.Datetime.now()
        for rec in self.sudo():
            count = rec.error_count + 1
            rec.write({'state': 'error', 'error_count': count, 'last_error': str(exc)[:255], 'last_error_ts': now,
                       'next_try_at': now + timedelta(seconds=min(60 * 2 ** (count - 1), 600))})
            _logger.warning("BioStar %s: %s", rec.name, exc)

    def _check_group(self, xmlid):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError("Недостатньо прав для цієї дії.")

    def _check_read_enabled(self):
        if not P.get_flag(self.env, 'read_enabled'):
            raise UserError(READ_DISABLED)

    @staticmethod
    def _notify(title, message, kind='success'):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': title, 'message': message, 'type': kind, 'sticky': kind == 'danger'}}

    def _may_commit(self):
        return not self.env.context.get('f3d_no_commit') and not self.env.registry.in_test_mode()

    # ------------------------------------------------------------------ крони
    @api.model
    def _cron_servers(self, method, *, needs_read=True):
        if needs_read and not P.get_flag(self.env, 'read_enabled'):
            _logger.info("СКУД: %s пропущено, read_enabled=False", method)
            return
        for server in self.search([('active', '=', True)]):
            now = fields.Datetime.now()
            if server.next_try_at and server.next_try_at > now:
                continue
            try:
                if method == '_poll':
                    with self.env.cr.savepoint():
                        server._poll()
                else:
                    getattr(server, method)()
            except Exception as exc:  # noqa: BLE001 - крон не падає (SPEC M-01)
                server._mark_error(exc)
            if self._may_commit():
                self.env.cr.commit()

    @api.model
    def _cron_poll(self):
        self._cron_servers('_poll')

    @api.model
    def _cron_sync_users(self):
        self._cron_servers('_sync_users')

    @api.model
    def _cron_sync_devices(self):
        self._cron_servers('_sync_devices')

    # ------------------------------------------------------------------ опитування (R-11)
    def _poll_params(self):
        mode = P.get_str(self.env, 'paging_mode', 'offset')
        if mode not in ('offset', 'hint'):
            _logger.warning("Параметр factory3d.access.paging_mode=%r поза межами, взято offset", mode)
            mode = 'offset'
        return {
            'page_size': P.get_int(self.env, 'page_size', 500, 1, 2000),
            'max_pages': P.get_int(self.env, 'max_pages_per_run', 20, 1, 100),
            'paging_mode': mode,
        }

    def _fetch_pages(self, client, since, until, max_pages=None):
        prm = self._poll_params()
        max_pages = max_pages or prm['max_pages']
        page_size = prm['page_size']
        rows_all, page, rows = [], 0, []
        while True:
            if prm['paging_mode'] == 'hint' and rows_all:
                rows, _total = client.search_events(
                    since, until, limit=page_size, offset=None, hint=rows_all[-1].get('hint'))
            else:
                rows, _total = client.search_events(since, until, limit=page_size, offset=len(rows_all))
            rows_all += rows
            page += 1
            if len(rows) < page_size or page == max_pages:
                break
        return rows_all, page == max_pages and len(rows) == page_size

    def _poll_window(self, since, until, max_pages=None, client=None):
        """R-11 кроки 3–7 без руху курсора; повертає лічильники."""
        return self._run_window(since, until, max_pages, client)[0]

    def _run_window(self, since, until, max_pages=None, client=None):
        self.ensure_one()
        client = client or self._get_client()
        try:
            rows_all, more = self._fetch_pages(client, since, until, max_pages)
        finally:
            self._save_session(client)
        event = self.env['f3d.access.event']
        res = event._f3d_ingest_rows(self, rows_all)
        pending = event.search(
            [('server_id', '=', self.id), ('process_state', '=', 'new')], order='ts, id', limit=10000)
        pending._f3d_process()
        out = {'rows': len(rows_all), 'new': res.get('created', 0), 'processed': len(pending), 'more': more,
               'duplicates': res.get('duplicates', 0), 'invalid': res.get('invalid', 0)}
        return out, rows_all, res

    def _poll(self):
        """R-11: одне опитування; `{'skipped': True}`, якщо рядок сервера заблоковано іншим прогоном."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(
                    "SELECT id FROM f3d_access_server WHERE id = %s FOR UPDATE NOWAIT", [self.id])
        except pg_errors.LockNotAvailable:
            return {'skipped': True}
        now = fields.Datetime.now()
        overlap = P.get_int(self.env, 'overlap_s', 120, 0, 3600)
        tolerance = P.get_int(self.env, 'future_tolerance_s', 300, 0, 3600)
        if self.last_event_ts:
            since = self.last_event_ts - timedelta(seconds=overlap)
        else:
            since = now - timedelta(hours=P.get_int(self.env, 'initial_lookback_h', 24, 1, 168))
        until = now + timedelta(seconds=tolerance)
        res, rows_all, ingest = self._run_window(since, until)
        self._move_cursor(rows_all, now)
        self._mark_ok()
        self.sudo().write({'last_poll_at': now, 'last_poll_rows': res['rows'], 'last_poll_new': res['new'],
                           'last_poll_more': res['more']})
        self._f3d_after_poll(ingest)
        return res

    def _move_cursor(self, rows_all, now):
        best_ts, best_id = None, False
        for row in rows_all:
            try:
                ts = parse_bs_dt(row.get('datetime'))
            except ValueError:
                continue
            if ts and (best_ts is None or ts >= best_ts):
                best_ts, best_id = ts, str(row.get('id') or '')
        if best_ts is None:
            return
        new = min(best_ts, now)
        if not self.last_event_ts or new > self.last_event_ts:
            self.sudo().write({'last_event_ts': new, 'last_event_biostar_id': best_id})

    def _f3d_after_poll(self, ingest_result):
        """Точка розширення R-18 (сигнали телеметрії) — W4."""
        return None

    def action_poll_now(self):
        self.ensure_one()
        self._check_group(GROUP_ADMIN)
        self._check_read_enabled()
        try:
            res = self._poll()
        except BioStarError as exc:
            self._mark_error(exc)
            return self._notify("Опитування BioStar", str(exc), 'danger')
        if res.get('skipped'):
            raise UserError("Опитування вже виконується. Спробуйте за хвилину.")
        return self._notify("Опитування BioStar",
                            "Рядків: %(rows)s, нових подій: %(new)s, оброблено: %(processed)s" % res)

    def action_test_connection(self):
        self.ensure_one()
        self._check_group(GROUP_F3D_ADMIN)
        client = self._get_client()
        client.session_id = None
        try:
            client.login()
            users = client.list_users_total()
            devices = client.list_devices()
            client.logout()
        except BioStarError as exc:
            self._mark_error(exc)
            return self._notify("Перевірка з'єднання", str(exc), 'danger')
        self.sudo().write({'users_total': users, 'devices_total': len(devices)})
        self._mark_ok()
        return self._notify("Перевірка з'єднання",
                            "З'єднання встановлено: користувачів %s, пристроїв %s" % (users, len(devices)))

    def action_sync_users(self):
        self.ensure_one()
        self._check_group(GROUP_ADMIN)
        self._check_read_enabled()
        res = self._sync_users()
        if res.get('error'):
            return self._notify("Синхронізація користувачів", res['error'], 'danger')
        return self._notify(
            "Синхронізація користувачів",
            "Користувачів: %(total)s, створено: %(created)s, оновлено: %(updated)s, не зв'язано: %(unlinked)s" % res)

    def action_sync_devices(self):
        self.ensure_one()
        self._check_group(GROUP_ADMIN)
        self._check_read_enabled()
        res = self._sync_devices()
        if res.get('error'):
            return self._notify("Синхронізація пристроїв", res['error'], 'danger')
        return self._notify(
            "Синхронізація пристроїв і дверей",
            "Пристроїв: %(devices_total)s (нових %(devices_created)s), дверей: %(doors_total)s "
            "(нових %(doors_created)s)" % res)

    def action_reset_cursor(self):
        self._check_group(GROUP_F3D_ADMIN)
        self.sudo().write({'last_event_ts': False, 'last_event_biostar_id': False})
        return True

    def action_open_events(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Події', 'res_model': 'f3d.access.event',
                'view_mode': 'list,form', 'domain': [('server_id', '=', self.id)]}

    def action_open_errors(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Помилки обробки', 'res_model': 'f3d.access.event',
                'view_mode': 'list,form',
                'domain': [('server_id', '=', self.id), ('process_state', '=', 'error')]}

    def action_open_links(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Користувачі BioStar',
                'res_model': 'f3d.access.user.link', 'view_mode': 'list,form',
                'domain': [('server_id', '=', self.id)]}

    # ------------------------------------------------------------------ синхронізація довідників (R-19)
    def _sync_users(self):
        self.ensure_one()
        client = self._get_client()
        Link = self.env['f3d.access.user.link'].sudo()
        now = fields.Datetime.now()
        try:
            rows = list(client.list_users(limit=100))
        except BioStarError as exc:
            self._save_session(client)
            self._mark_error(exc)
            return {'error': str(exc)}
        self._save_session(client)
        res = {'total': len(rows), 'created': 0, 'updated': 0, 'matched': 0, 'unlinked': 0, 'missing': 0}
        seen = set()
        existing = {link.biostar_user_id: link for link in Link.with_context(active_test=False).search(
            [('server_id', '=', self.id)])}
        for row in rows:
            uid = str(row.get('user_id') or '')
            if not P.BSID_RE.match(uid):
                _logger.warning("BioStar: пропущено рядок %s з невалідним id", uid)
                continue
            seen.add(uid)
            group = row.get('user_group_id')
            vals = {
                'biostar_name': row.get('name') or False,
                'user_group': (group.get('name') if isinstance(group, dict) else False) or False,
                'disabled': str(row.get('disabled')).lower() == 'true',
                'start_dt': self._safe_dt(row.get('start_datetime')),
                'expiry_dt': self._safe_dt(row.get('expiry_datetime')),
                'card_count': int(row.get('card_count') or 0),
                'has_face': int(row.get('face_count') or 0) > 0,
                'has_finger': int(row.get('fingerprint_template_count') or row.get('finger_count') or 0) > 0,
                'in_biostar': True, 'synced': True, 'last_sync': now,
            }
            link = existing.get(uid)
            if link:
                link.write(vals)
                res['updated'] += 1
            else:
                link = Link.create(dict(vals, server_id=self.id, biostar_user_id=uid))
                existing[uid] = link
                res['created'] += 1
            if link.match == 'none':
                link._f3d_rematch()
            if link.match == 'none':
                res['unlinked'] += 1
            else:
                res['matched'] += 1
        missing = Link.search([('server_id', '=', self.id), ('in_biostar', '=', True),
                               ('biostar_user_id', 'not in', list(seen))])
        missing.write({'in_biostar': False})
        res['missing'] = len(missing)
        self.sudo().write({'users_total': len(rows), 'users_synced_at': now})
        self._mark_ok()
        return res

    @staticmethod
    def _safe_dt(value):
        try:
            return parse_bs_dt(value) or False
        except ValueError:
            return False

    def _sync_devices(self):
        self.ensure_one()
        client = self._get_client()
        Device = self.env['f3d.access.device'].sudo()
        Door = self.env['f3d.access.door'].sudo()
        now = fields.Datetime.now()
        try:
            dev_rows = client.list_devices()
            door_rows = client.list_doors()
        except BioStarError as exc:
            self._save_session(client)
            for device in Device.search([('server_id', '=', self.id)]):
                fails = device.sync_fail_count + 1
                device.write({'sync_fail_count': fails, 'status': 'unknown' if fails >= 2 else device.status})
            self._mark_error(exc)
            return {'error': str(exc)}
        self._save_session(client)
        res = {'devices_total': len(dev_rows), 'devices_created': 0, 'devices_updated': 0,
               'doors_total': len(door_rows), 'doors_created': 0, 'doors_updated': 0}
        by_bsid = {d.biostar_id: d for d in Device.with_context(active_test=False).search(
            [('server_id', '=', self.id)])}
        seen = set()
        for row in dev_rows:
            bsid = str(row.get('id') or '')
            if not P.BSID_RE.match(bsid):
                _logger.warning("BioStar: пропущено рядок %s з невалідним id", bsid)
                continue
            seen.add(bsid)
            status = {'1': 'online', '0': 'offline'}.get(str(row.get('status')), 'unknown')
            dtype = row.get('device_type_id')
            device = by_bsid.get(bsid)
            if device:
                device.write({'device_type': (dtype.get('name') if isinstance(dtype, dict) else False) or False,
                              'ip': row.get('ip') or False, 'status': status, 'status_ts': now,
                              'sync_fail_count': 0})
                res['devices_updated'] += 1
            else:
                device = Device.create({
                    'code': 'BS-%s' % bsid, 'name': row.get('name') or 'BS-%s' % bsid, 'server_id': self.id,
                    'biostar_id': bsid, 'direction': 'in', 'status': status, 'status_ts': now,
                    'device_type': (dtype.get('name') if isinstance(dtype, dict) else False) or False,
                    'ip': row.get('ip') or False})
                by_bsid[bsid] = device
                res['devices_created'] += 1
                _logger.warning("Новий пристрій BioStar %s: задайте код сцени, зону й напрямок", bsid)
        for bsid, device in by_bsid.items():
            if bsid not in seen:
                device.write({'status': 'unknown'})
        doors = {d.biostar_id: d for d in Door.with_context(active_test=False).search(
            [('server_id', '=', self.id)])}

        def _dev(ref):
            device = by_bsid.get(str(ref['id'])) if isinstance(ref, dict) and ref.get('id') is not None else None
            return device.id if device else False

        for row in door_rows:
            bsid = str(row.get('id') or '')
            if not P.BSID_RE.match(bsid):
                _logger.warning("BioStar: пропущено рядок %s з невалідним id", bsid)
                continue
            vals = {}
            if 'entry_device_id' in row:
                vals['entry_device_id'] = _dev(row['entry_device_id'])
            if 'exit_device_id' in row:
                vals['exit_device_id'] = _dev(row['exit_device_id'])
            if row.get('open_duration') not in (None, ''):
                vals['open_duration_s'] = int(row['open_duration'])
            door = doors.get(bsid)
            if door:
                door.write(vals)
                res['doors_updated'] += 1
            else:
                Door.create(dict(vals, code='BSD-%s' % bsid, name=row.get('name') or 'BSD-%s' % bsid,
                                 kind='door', server_id=self.id, biostar_id=bsid))
                res['doors_created'] += 1
        self.sudo().write({'devices_total': len(dev_rows), 'devices_synced_at': now})
        self._mark_ok()
        return res
