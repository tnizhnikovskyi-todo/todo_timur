# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас (заглушки): W0.
"""``td.genset`` (inherit): забір показань і стан зв'язку — ТР 2.6.2, 2.8.6, 2.8.7, А.7, А.8; SPEC 9.

Одна сторінка ``/readings`` = одна транзакція (``_notify_progress`` → планувальник комітить і кличе метод
знову); у тестах і при кількох генераторах сторінка кожного генератора — у власному savepoint. Жоден виняток
не виходить назовні cron (інакше Odoo деактивує задачу після 5 невдач за 7 днів).
"""
import logging
from datetime import datetime, time, timedelta

import pytz
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools import SQL

from .genset_alarm import hhmm
from .genset_event import parse_utc
from .genset_reading import KYIV, READING_FIELD_MAP, ts_to_datetime
from .relay_client import RelayAuthError, RelayError, RelayNotFound, RelayUnavailable

_logger = logging.getLogger(__name__)

PAGE_SIZE = 500
CATCHUP_AGE_MIN = 15          # знімок старший за 15 хв → режим догону (2.6.2 п. 4)
OHM_KEYS = ('fuel_level_sensor_ohm', 'water_temp_sensor_ohm', 'oil_pressure_sensor_ohm')
RAW_VERSION = (1, 1, 3)       # з цієї версії ретранслятор віддає оми ключами (ФВ-31)
TECH_RELAY_CODES = ('relay_unavailable', 'relay_auth')
# Поля стану, що копіюються з останнього знімка в генератор (2.16)
APPLY_FIELDS = (
    'controller_mode', 'genset_status', 'genset_status_delay', 'is_running', 'mains_ok', 'feed_source',
    'gen_on_load', 'mains_on_load', 'remote_lock', 'common_alarm', 'common_warning', 'common_shutdown', 'speed',
    'active_power', 'oil_pressure', 'water_temp', 'battery_v', 'dplus_v', 'fuel_level', 'fuel_liters', 'fuel_source',
    'fuel_sensor_ohm', 'water_temp_sensor_ohm', 'oil_pressure_sensor_ohm', 'mains_uab', 'mains_ubc', 'mains_uca',
    'mains_freq', 'gen_uab', 'gen_ubc', 'gen_uca', 'gen_freq', 'current_a', 'current_b', 'current_c',
    'power_factor', 'load_pct', 'run_hours', 'run_minutes', 'run_hours_total', 'start_count', 'energy_kwh',
)


class TdGensetMonitoring(models.Model):
    _inherit = 'td.genset'
    # Будь-хто з правом читання генератора може «Записати примітку» в чатер (AC-63; запис полів — лише Т)
    _mail_post_access = 'read'

    # ------------------------------------------------------------------ cron «Генератори: забір показань і стан»
    @api.model
    def _cron_pull_readings(self):
        """Точка входу cron ``cron_pull_readings`` (1 хв, priority 5).

        ``/status`` один раз → ``_apply_status`` для всіх генераторів з ``relay_enabled``; далі
        ``_pull_readings_page`` по генераторах (рядок генератора — ``FOR NO KEY UPDATE SKIP LOCKED``);
        після сторінки — ``ir.cron._notify_progress(done=n, remaining=1 if n == 500 else 0)``;
        усі винятки перехоплені (cron не падає, А.7). Недоступність API рахується від
        ``td.genset.config.relay_unavailable_since``; 401 — тривога тех. адміністратору (AC-10).
        """
        done, remaining = 0, 0
        try:
            gensets = self.search([('relay_enabled', '=', True), ('relay_hostid', '!=', False)])
            if not gensets:
                return None
            client = self.env['td.genset.relay.client']
            try:
                status = client.status()
            except RelayError as exc:
                gensets._td_relay_failed(exc)
                return None
            for genset in gensets:
                if not genset._td_try_lock():
                    continue
                try:
                    with self.env.cr.savepoint():
                        genset._apply_status(status)
                except Exception as exc:  # noqa: BLE001
                    _logger.warning('td_genset: %s: стан /status не застосовано: %s', genset.name, exc)
                try:
                    with self.env.cr.savepoint():
                        count = genset.with_context(td_genset_status=status)._pull_readings_page(client)
                except RelayError as exc:
                    genset._td_relay_failed(exc)
                    continue
                except Exception as exc:  # noqa: BLE001
                    _logger.warning('td_genset: %s: сторінку знімків не збережено: %s', genset.name, exc)
                    continue
                done += count
                if count >= PAGE_SIZE:
                    remaining = 1
        except Exception as exc:  # noqa: BLE001 — cron не має падати (А.7)
            _logger.warning('td_genset: забір показань не вдався: %s', exc)
        finally:
            self.env['ir.cron']._notify_progress(done=done, remaining=remaining)
        return None

    def _td_try_lock(self):
        """``SELECT … FOR NO KEY UPDATE SKIP LOCKED``: другий воркер пропускає зайнятий генератор (А.7)."""
        self.ensure_one()
        self.env.cr.execute(SQL("SELECT id FROM td_genset WHERE id = %s FOR NO KEY UPDATE SKIP LOCKED", self.id))
        return bool(self.env.cr.fetchone())

    def _td_relay_failed(self, exc):
        """Помилка API: 401 → тривога ``relay_auth``; таймаут/5xx → лічильник ``relay_unavailable_since`` і
        через ``relay_unavailable_alarm_min`` хв — тривога ``relay_unavailable`` (тех.). Курсор не змінюється."""
        _logger.warning('td_genset: ретранслятор: %s', exc)
        alarm_model = self.env['td.genset.alarm']
        if isinstance(exc, RelayAuthError):
            for genset in self:
                with self.env.cr.savepoint():
                    alarm_model._raise(genset, 'relay_auth', 'warn', _('Ретранслятор відхилив токен (401)'),
                                       _('Ретранслятор відхилив токен (401). Перевірте токен у Налаштуваннях.'),
                                       tech=True)
            return
        if isinstance(exc, RelayNotFound) and 'hostid' in (exc.error or ''):
            for genset in self:
                with self.env.cr.savepoint():
                    alarm_model._raise(genset, 'relay_hostid', 'warn', _('Ретранслятор не знає hostid генератора'),
                                       _('Ретранслятор не знає ID модуля «%s» (404 unknown hostid). Перевірте ID '
                                         'модуля в картці генератора.', genset.relay_hostid), tech=True)
            return
        if not isinstance(exc, RelayUnavailable):
            return
        config = self.env['td.genset.config'].sudo().get()
        now = fields.Datetime.now()
        if not config.relay_unavailable_since:
            config.relay_unavailable_since = now
            return
        minutes = int((now - config.relay_unavailable_since).total_seconds() // 60)
        if minutes < (config.relay_unavailable_alarm_min or 10):
            return
        for genset in self:
            with self.env.cr.savepoint():
                alarm_model._raise(genset, 'relay_unavailable', 'warn', _('Ретранслятор недоступний %s хв', minutes),
                                   _('Ретранслятор недоступний %s хв (таймаут/5xx).', minutes), tech=True)

    # ------------------------------------------------------------------ /status
    def _apply_status(self, status):
        """Записує ``relay_*`` з ``/status``; викликає ``_update_link_state``, ``_check_relay_health``,
        ``td.genset.event._detect_external_control(genset, cloud=device['cloud_commands_seen'])``;
        скидає ``td.genset.config.relay_unavailable_since`` і тривоги недоступності/токена.

        :param dict status: тіло ``GET /status``.
        """
        status = status or {}
        relay = status.get('relay') or {}
        client = self.env['td.genset.relay.client']
        config = self.env['td.genset.config'].sudo().get()
        if config.relay_unavailable_since:
            config.relay_unavailable_since = False
        now = fields.Datetime.now()
        for genset in self.sudo():
            for code in TECH_RELAY_CODES:
                self.env['td.genset.alarm']._clear(genset, code)
            device = client.device_status(status, genset.relay_hostid)
            vals = {
                'relay_version': relay.get('version') or False,
                'relay_commands_enabled': bool(relay.get('commands_enabled')),
                'relay_snapshot_sec': int(relay.get('snapshot_sec') or 0),
                'relay_time_utc': parse_utc(relay.get('time_utc')) or False,
            }
            if device:
                last = device.get('last_reading') or {}
                vals.update({
                    'relay_online': bool(device.get('online')),
                    'relay_seconds_since_seen': int(device.get('seconds_since_seen') or 0),
                    'relay_long_connection': bool(device.get('long_connection')),
                    'relay_commands_ready': bool(device.get('commands_ready')),
                    'relay_registers_known': int(device.get('registers_known') or 0),
                    'relay_coils_known': int(device.get('coils_known') or 0),
                    'relay_last_reading_id': int(last.get('id') or 0),
                    'relay_last_reading_at': parse_utc(last.get('time_utc')) or False,
                })
                self.env['td.genset.alarm']._clear(genset, 'relay_hostid')
            changed = {key: value for key, value in vals.items() if genset[key] != value}
            if changed:
                genset.write(changed)
            genset._check_relay_health(status)
            genset._update_link_state(device.get('online') if device else None, now=now)
            if device:
                self.env['td.genset.event']._detect_external_control(
                    genset, cloud=device.get('cloud_commands_seen') or [])
            if 'relay_commands_enabled' in changed or 'relay_commands_ready' in changed:
                genset._notify_bus('status')
        return None

    def _check_relay_health(self, status):
        """2.8.7: ``registers_known``/``coils_known`` = 0 → тривога ``relay_health`` (тех.); формат команд ще не
        вивчено → ``relay_cmd_format`` (тех.); ``relay.commands_enabled`` — бейдж на картці (поле, AC-11)."""
        client = self.env['td.genset.relay.client']
        relay = (status or {}).get('relay') or {}
        alarm_model = self.env['td.genset.alarm']
        for genset in self.sudo():
            device = client.device_status(status, genset.relay_hostid)
            if not device:
                continue
            broken = [key for key in ('registers_known', 'coils_known') if not device.get(key)]
            if broken:
                text = _('Ретранслятор не розбирає дані (%s)', ', '.join('%s=0' % key for key in broken))
                alarm_model._raise(genset, 'relay_health', 'warn', text, '%s.' % text, tech=True)
            else:
                alarm_model._clear(genset, 'relay_health')
            if relay.get('commands_enabled') and 'command_format' in device and not device.get('command_format'):
                alarm_model._raise(genset, 'relay_cmd_format', 'warn', _('Ретранслятор ще не вивчив формат команд'),
                                   _('Ретранслятор ще не вивчив формат команд.'), tech=True)
            else:
                alarm_model._clear(genset, 'relay_cmd_format')
        return None

    # ------------------------------------------------------------------ сторінка /readings
    def _pull_readings_page(self, client):
        """Одна сторінка ``/readings`` для ``self`` (один генератор) в одній транзакції:
        ``_create_from_payload`` → ``_mark_journal`` → ``_apply_reading(last)`` → ``_process_readings``
        → ``readings_cursor = next_since``. Перший забір (курсор 0) починається з ``catchup_from_date`` (А.7);
        знімки старші за 15 хв — режим догону (події без тривог), після догону — ``_finish_catchup``.

        :param client: ``env['td.genset.relay.client']``.
        :return: кількість знімків у сторінці (int).
        """
        self.ensure_one()
        genset = self.sudo()
        status = self.env.context.get('td_genset_status')
        cursor = genset.readings_cursor or 0
        if not cursor and genset.catchup_from_date and genset.relay_last_reading_id:
            cursor = genset._find_cursor_for_date(client, genset.catchup_from_date)
        payloads, next_since = client.readings(genset.relay_hostid, cursor, limit=PAGE_SIZE,
                                               raw=genset._need_raw(status))
        reading_model = self.env['td.genset.reading']
        readings = reading_model._create_from_payload(genset, payloads)
        if readings:
            reading_model._mark_journal(genset, set(readings.mapped('slot_15')))
            now = fields.Datetime.now()
            if not genset.catchup_mode and min(readings.mapped('ts')) < now - timedelta(minutes=CATCHUP_AGE_MIN):
                genset.write({'catchup_mode': True, 'catchup_stats': {'readings': 0, 'events': 0,
                                                                      'first_ts': fields.Datetime.to_string(
                                                                          min(readings.mapped('ts')))}})
            last = readings[-1]
            payload = next((item for item in payloads if int(item['id']) == last.relay_id), None)
            values = reading_model._td_values_with_ohms(payload) if payload else None
            genset.with_context(td_genset_values=values)._apply_reading(last)
            stats = self.env['td.genset.event']._td_process(genset, readings)
            if stats['refuel']:
                self.env['td.genset.refuel']._reconcile_pending()
            if genset.catchup_mode:
                summary = dict(genset.catchup_stats or {})
                summary['readings'] = summary.get('readings', 0) + len(readings)
                summary['events'] = summary.get('events', 0) + stats['events']
                summary['last_ts'] = fields.Datetime.to_string(last.ts)
                genset.catchup_stats = summary
        if next_since and next_since != genset.readings_cursor:
            genset.readings_cursor = next_since
        elif cursor != genset.readings_cursor:
            genset.readings_cursor = cursor
        if genset.catchup_mode and (len(payloads) < PAGE_SIZE
                                    or (genset.relay_last_reading_id
                                        and genset.readings_cursor >= genset.relay_last_reading_id)):
            genset._finish_catchup(dict(genset.catchup_stats or {}))
        return len(payloads)

    def _find_cursor_for_date(self, client, date):
        """Бінарний пошук ``id`` першого знімка з ``ts ≥ date`` (``GET /readings?since=X&limit=1``, А.7).

        Дата — київська (початок доби); id ретранслятора монотонні в часі. ≈ log2(id) запитів.

        :return: курсор (int) для ``readings_cursor``: знімки з ``id > курсор`` не старші за дату.
        """
        self.ensure_one()
        if not date:
            return 0
        target = KYIV.localize(datetime.combine(date, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        high = int(self.relay_last_reading_id or 0)
        if high <= 0:
            return 0

        def first_after(since):
            page, _next = client.readings(self.relay_hostid, since, limit=1)
            if not page:
                return None
            return ts_to_datetime(page[0].get('ts'), page[0].get('time_utc'))

        first = first_after(0)
        if first is None or first >= target:
            return 0
        low = 0
        while low < high:
            middle = (low + high) // 2
            stamp = first_after(middle)
            if stamp is None or stamp >= target:
                high = middle
            else:
                low = middle + 1
        return low

    def _need_raw(self, status):
        """Чи потрібен ``raw=1``: ``config.raw_regs_mode`` ``yes`` → True; ``no`` → False;
        ``auto`` → ``relay.version`` < 1.1.3 або в останньому знімку немає ключів ``*_sensor_ohm`` (ФВ-31, AC-68).

        :param dict|None status: тіло ``/status`` (без нього — збережена ``relay_version``).
        :rtype: bool
        """
        mode = self.env['td.genset.config'].sudo().get().raw_regs_mode or 'auto'
        if mode in ('yes', 'no'):
            return mode == 'yes'
        version = ((status or {}).get('relay') or {}).get('version') or self[:1].relay_version
        if not version or version_tuple(version) < RAW_VERSION:
            return True
        values = self[:1].last_values_json
        if isinstance(values, dict) and values and not any(key in values for key in OHM_KEYS):
            return True
        return False

    def _apply_reading(self, reading):
        """Копіює стан останнього знімка в поля генератора (2.16): режим, стан, ``is_running``,
        ``feed_source``, лічильники, оми, ``fuel_liters``/``fuel_source``, ``last_reading_id``,
        ``last_values_json``; ``_notify_bus('reading')``; ``_check_maintenance()`` (W4).

        ``values`` знімка (з ``null`` і без відсутніх ключів) — з контексту ``td_genset_values``, інакше
        відновлюються з полів знімка (NULL → ключа немає).

        :param reading: запис ``td.genset.reading``.
        """
        self.ensure_one()
        if not reading:
            return None
        genset = self.sudo()
        if genset.last_reading_id and genset.last_reading_id.relay_id > reading.relay_id:
            return None
        values = self.env.context.get('td_genset_values')
        if values is None:
            values = genset._td_values_from_reading(reading)
        vals = {name: reading[name] for name in APPLY_FIELDS}
        vals['controller_mode'] = reading.controller_mode or 'unknown'
        vals['last_values_json'] = values
        changed = {key: value for key, value in vals.items() if genset[key] != value}
        if genset.last_reading_id != reading:
            changed['last_reading_id'] = reading.id
        if changed:
            genset.write(changed)
        genset._check_maintenance()
        genset._notify_bus('reading', {'reading_id': reading.id})
        return None

    def _td_values_from_reading(self, reading):
        """``values`` зі збереженого знімка (для ``last_values_json``, коли payload недоступний)."""
        reading.flush_recordset()
        columns = sorted({field_name for field_name, _type in READING_FIELD_MAP.values()})
        self.env.cr.execute(SQL("SELECT %s FROM td_genset_reading WHERE id = %s",
                                SQL(', ').join(SQL.identifier(column) for column in columns), reading.id))
        row = dict(zip(columns, self.env.cr.fetchone()))
        values = {}
        for key, (field_name, field_type) in READING_FIELD_MAP.items():
            value = row.get(field_name)
            if value is None:
                continue
            if field_type == 'selection' and key == 'genset_status':
                value = int(value)
            values[key] = value
        values.update(reading.values_extra or {})
        return values

    # ------------------------------------------------------------------ зв'язок (2.8.6)
    def _update_link_state(self, online, now=None):
        """Правило 2.8.6: «онлайн» — модуль на зв'язку і знімки свіжіші за ``link_lost_min``; «немає зв'язку» —
        ``online=False`` ≥ ``link_lost_min`` або немає знімків ≥ ``link_lost_min`` (останній знімок — і в Odoo,
        і на ретрансляторі, тож догон історії не вважається втратою зв'язку).

        Момент переходу в «Немає зв'язку» (``link_changed_at``) — коли минуло ``link_lost_min`` без даних
        (останні дані + 3 хв), незалежно від того, коли саме відпрацював cron; тривога ``link_lost`` — через
        ``link_alarm_min`` від цього моменту (останні дані + 3 + 10 хв). Подія ``link`` охоплює весь час без даних
        (від останніх даних до відновлення). Відновлення → подія закрита, ``_clear('link_lost')``, чатер
        «Зв'язок відновлено після N хв без даних», ``_notify_bus('link')``, крок cron команд для ``waiting_link``
        (AC-09).

        :param bool|None online: стан модуля з ``/status`` (None — невідомо).
        :param datetime now: «зараз» (UTC naive) для тестів.
        """
        now = now or fields.Datetime.now()
        config = self.env['td.genset.config'].sudo().get()
        lost_after = timedelta(minutes=config.link_lost_min or 3)
        event_model = self.env['td.genset.event']
        alarm_model = self.env['td.genset.alarm']
        for genset in self.sudo():
            stamps = [stamp for stamp in (genset.last_reading_at, genset.relay_last_reading_at) if stamp]
            last_data = max(stamps) if stamps else None
            if last_data is None:
                continue
            fresh = now - last_data < lost_after
            silent_for = timedelta(seconds=genset.relay_seconds_since_seen or 0)
            moments = []            # коли настала умова «немає зв'язку» (за кожною з ознак)
            if not fresh:
                moments.append(last_data + lost_after)
            if online is False and silent_for >= lost_after:
                moments.append(now - silent_for + lost_after)
            if genset.link_state != 'offline' and moments:
                genset.write({'link_state': 'offline', 'link_changed_at': min(min(moments), now)})
                event_model._open(genset, 'link', last_data, reason=_("Немає зв'язку з модулем"))
                genset._notify_bus('link', {'state': 'offline'})
            elif genset.link_state != 'online' and online is not False and fresh:
                was_offline = genset.link_state == 'offline'
                lost_since = genset.link_changed_at
                genset.write({'link_state': 'online', 'link_changed_at': now})
                if was_offline:
                    events = event_model.sudo().search([('genset_id', '=', genset.id), ('event_type', '=', 'link'),
                                                        ('date_end', '=', False)])
                    no_data_since = min(events.mapped('date_start')) if events else lost_since
                    minutes = int(round((now - no_data_since).total_seconds() / 60.0)) if no_data_since else 0
                    text = _("Зв'язок відновлено після %s хв без даних.", minutes)
                    for event in events:
                        event_model._close(event, now, summary=text)
                    alarm_model._clear(genset, 'link_lost')
                    genset._td_post_info(text)
                    waiting = self.env['td.genset.command'].sudo().search_count(
                        [('genset_id', '=', genset.id), ('state', '=', 'waiting_link')])
                    if waiting:
                        self.env.ref('td_genset.cron_commands').sudo()._trigger()
                genset._notify_bus('link', {'state': 'online'})
            if genset.link_state == 'offline' and genset.link_changed_at \
                    and now - genset.link_changed_at >= timedelta(minutes=config.link_alarm_min or 10):
                minutes = int((now - genset.link_changed_at).total_seconds() // 60)
                alarm_model._raise(genset, 'link_lost', 'crit', _("Немає зв'язку з модулем"),
                                   _("Немає зв'язку з модулем з %(time)s (%(minutes)s хв). Пульт недоступний.",
                                     time=hhmm(genset.link_changed_at), minutes=minutes))
        return None

    # ------------------------------------------------------------------ догон (А.7)
    def _finish_catchup(self, summary):
        """Вихід із ``catchup_mode``: ``td.genset.alarm._evaluate_current(self)``, підсумок у чатер
        «Догнано історію: N днів, M знімків, K подій» (якщо ``config.catchup_summary``, AC-45).

        :param dict summary: ``{'days': N, 'readings': M, 'events': K}`` (або ``first_ts``/``last_ts`` замість днів).
        """
        config = self.env['td.genset.config'].sudo().get()
        for genset in self.sudo():
            genset.write({'catchup_mode': False, 'catchup_stats': False})
            self.env['td.genset.alarm']._evaluate_current(genset)
            if not config.catchup_summary:
                continue
            days = summary.get('days')
            if days is None:
                first, last = summary.get('first_ts'), summary.get('last_ts')
                days = 0
                if first and last:
                    span = fields.Datetime.to_datetime(last) - fields.Datetime.to_datetime(first)
                    days = int(round(span.total_seconds() / 86400.0))
            genset._message_log(body=_('Догнано історію: %(days)s днів, %(readings)s знімків, %(events)s подій.',
                                       days=days, readings=summary.get('readings', 0),
                                       events=summary.get('events', 0)))
        return None

    # ------------------------------------------------------------------ інформаційні повідомлення (2.8.2, 2.8.5)
    def _td_post_info(self, body):
        """Інформаційна подія в чатер генератора за правилом ``notify_info``: «Лише в чаті» → нотатка;
        «Завжди»/«Крім тихих годин» → повідомлення з підтипом «Подія» + сповіщення рівню 1; за наявності —
        пост у канал «Обговорень»."""
        config = self.env['td.genset.config'].sudo().get()
        rule = config.notify_info or 'chatter'
        for genset in self.sudo():
            if rule == 'chatter':
                genset._message_log(body=body)
            else:
                genset.message_post(body=Markup('<p>%s</p>') % body, subtype_xmlid='td_genset.mt_event')
                if not (rule == 'not_quiet' and config._quiet_now()):
                    level = config.level_ids.sorted(lambda item: (item.sequence, item.id)).filtered('user_id')[:1]
                    if level:
                        genset.message_notify(partner_ids=level.user_id.partner_id.ids, subject=genset.name,
                                              body=Markup('<p>%s</p>') % body, subtype_xmlid='td_genset.mt_event')
            if config.discuss_channel_id:
                config.discuss_channel_id.message_post(body=Markup('<p>%s: %s</p>') % (genset.name, body),
                                                       message_type='comment', subtype_xmlid='mail.mt_comment')

    # ------------------------------------------------------------------ кнопки
    def action_check_relay(self):
        """Кнопка «Перевірити зв'язок» (``group_tech``): ``/status`` + ``/latest``; результат —
        ``display_notification`` з версією, ``online``, ``seconds_since_seen``, ``commands_enabled``,
        ``commands_ready``, ``registers_known/coils_known`` (AC-02). Помилки — коротким текстом без токена
        і трасування (AC-57)."""
        self._td_check_group('td_genset.group_tech')
        self.ensure_one()
        client = self.env['td.genset.relay.client']
        try:
            status = client.status()
            device = client.device_status(status, self.relay_hostid) if self.relay_hostid else None
            latest = client.latest(self.relay_hostid) if device else None
        except RelayAuthError:
            return self._td_notification(_('Ретранслятор відхилив токен (401). Перевірте токен у Налаштуваннях.'),
                                         notif_type='danger')
        except RelayUnavailable:
            return self._td_notification(_('Ретранслятор недоступний (таймаут %s с).', client._timeout()),
                                         notif_type='danger')
        except RelayError as exc:
            return self._td_notification(_('Ретранслятор повернув помилку: %s', exc), notif_type='danger')
        relay = status.get('relay') or {}
        yes, no = _('так'), _('ні')
        lines = [_('Ретранслятор %(version)s; команди на ретрансляторі: %(enabled)s.',
                   version=relay.get('version') or '?', enabled=yes if relay.get('commands_enabled') else no)]
        if not self.relay_hostid:
            lines.append(_('Вкажіть hostid модуля в картці генератора.'))
        elif not device:
            lines.append(_('Ретранслятор не знає модуль %s.', self.relay_hostid))
        else:
            lines.append(_('Модуль: %(state)s, бачили %(seconds)s с тому; готовий до команд: %(ready)s.',
                           state=_('онлайн') if device.get('online') else _("немає зв'язку"),
                           seconds=device.get('seconds_since_seen'),
                           ready=yes if device.get('commands_ready') else no))
            lines.append(_('Розбирає регістрів: %(regs)s, сигналів: %(coils)s.',
                           regs=device.get('registers_known'), coils=device.get('coils_known')))
            if latest:
                stamp = parse_utc(latest.get('time_utc'))
                lines.append(_('Останній знімок: %s.', hhmm(stamp) if stamp else '?'))
            else:
                lines.append(_('Знімків ще немає — очікуємо перший знімок.'))
            vals = {
                'relay_version': relay.get('version') or False,
                'relay_commands_enabled': bool(relay.get('commands_enabled')),
                'relay_online': bool(device.get('online')),
                'relay_seconds_since_seen': int(device.get('seconds_since_seen') or 0),
                'relay_commands_ready': bool(device.get('commands_ready')),
                'relay_registers_known': int(device.get('registers_known') or 0),
                'relay_coils_known': int(device.get('coils_known') or 0),
            }
            self.sudo().write(vals)
        ok = bool(device and device.get('online'))
        return self._td_notification(' '.join(lines), title=_("Перевірка зв'язку"),
                                     notif_type='success' if ok else 'warning')

    def action_refresh(self):
        """Кнопка «Оновити дані»: примусовий забір — ``env.ref('td_genset.cron_pull_readings')._trigger()``;
        форма оновиться через bus після збереження знімка."""
        self._td_check_group('td_genset.group_user')
        self.env.ref('td_genset.cron_pull_readings').sudo()._trigger()
        return self._td_notification(_('Запит надіслано: дані оновляться за кілька секунд.'))

    def _td_notification(self, message, title=None, notif_type='info'):
        """Допоміжне: дія ``display_notification`` (W1 може використовувати й змінювати)."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title or _('Генератори'),
                'message': message,
                'type': notif_type,
                'sticky': notif_type in ('danger', 'warning'),
            },
        }


def version_tuple(version):
    """«1.1.3» → (1, 1, 3); нечислові частини — 0."""
    parts = []
    for part in str(version).split('.')[:3]:
        digits = ''.join(char for char in part if char.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)
