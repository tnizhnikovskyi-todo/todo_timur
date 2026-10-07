# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас (поля, заглушки): W0.
"""Подія ``td.genset.event`` — ТР 2.3.3, 2.8.1; SPEC 5.3, 9.

Обробник подій проходить знімки сторінки в порядку ``relay_id`` (стан між сторінками — службові поля
генератора ``prev_reading_id``, ``open_run_event_id``, ``open_outage_event_id``, ``open_alarm_codes``).
Значення знімків читаються SQL-ем з NULL (ORM показує NULL як 0/False): «немає даних» не породжує подій.
У ``catchup_mode`` події створюються заднім числом, тривоги й сповіщення — ні (ФВ-3, А.7).
"""
from collections import deque
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.tools import SQL

from .genset import CONTROLLER_MODES
from .genset_alarm import GEN_SIGNALS, SHUTDOWN_SIGNALS, WARNING_SIGNALS, fmt_liters, hhmm

GAP_MIN = 3                 # пропуск між знімками > 3 хв → подія «Немає даних» (ФВ-25)
REFUEL_WINDOW_MIN = 10      # сумарний приріст рівня за ≤ 10 хв → «Заправка» (2.8.1)
MODE_COMMANDS = ('auto', 'manual', 'stop', 'test')
BREAKER_COMMANDS = {'gen_on_load': 'gen_close_open', 'mains_on_load': 'mains_close_open'}
ODOO_COMMAND_STATES = ('sent', 'awaiting', 'retry', 'waiting_link', 'done', 'done_late', 'failed')
OUTAGE_KIND_SIGNALS = (    # вид відключення: від конкретного до загального (2.8.1)
    ('mains_loss_phase', 'loss_phase'),
    ('mains_undervoltage', 'undervoltage'),
    ('mains_overvoltage', 'overvoltage'),
    ('mains_blackout', 'blackout'),
    ('mains_fault', 'fault'),
)
# Колонки знімка, потрібні правилам (читаються з NULL)
ROW_COLUMNS = tuple(dict.fromkeys(
    ['id', 'relay_id', 'ts', 'reason', 'is_running', 'mains_ok', 'genset_status', 'speed', 'energy_kwh',
     'active_power', 'fuel_level', 'fuel_liters', 'fuel_source', 'battery_v', 'controller_mode', 'gen_on_load',
     'mains_on_load', 'common_shutdown', 'common_warning', 'stop_failure_warning', 'remote_lock']
    + [column for column, _kind in OUTAGE_KIND_SIGNALS]
    + list(SHUTDOWN_SIGNALS) + list(WARNING_SIGNALS) + list(GEN_SIGNALS)))

EVENT_TYPES = [
    ('run', 'Робота генератора'),
    ('outage', 'Відключення мережі'),
    ('refuel', 'Заправка'),
    ('drain', 'Падіння рівня палива'),
    ('external_control', 'Керування не з Odoo'),
    ('alarm', 'Тривога контролера'),
    ('link', "Зв'язок"),
    ('gap', 'Немає даних'),
    ('maintenance', 'ТО'),
]
OUTAGE_KINDS = [
    ('blackout', 'Відсутність мережі'),
    ('loss_phase', 'Обрив фази'),
    ('fault', 'Аварія мережі'),
    ('undervoltage', 'Недонапруга'),
    ('overvoltage', 'Перенапруга'),
]


class TdGensetEvent(models.Model):
    _name = 'td.genset.event'
    _description = 'Генератори: подія'
    _order = 'date_start desc, id desc'
    _rec_name = 'event_type'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, index=True, ondelete='cascade',
        help='Генератор, з показань якого сформовано подію.')
    event_type = fields.Selection(
        EVENT_TYPES, string='Подія', index=True,
        help='Тип події. Формується автоматично з показань і /status (правила ТР 2.8.1).')
    date_start = fields.Datetime(
        string='Початок', index=True,
        help='Початок події.')
    date_end = fields.Datetime(
        string='Кінець',
        help='Кінець події; порожньо, поки триває.')
    duration = fields.Float(
        string='Тривалість', compute='_compute_duration', store=True, aggregator='sum',
        help='Тривалість події, години (кінець − початок).')
    is_open = fields.Boolean(
        string='Триває', compute='_compute_duration', store=True, index=True,
        help='Подія ще не закрита.')
    reason = fields.Char(
        string='Причина / джерело',
        help='Чому сталася подія або хто її спричинив.')
    summary = fields.Char(
        string='Підсумок',
        help='Короткий висновок по події.')
    is_bad = fields.Boolean(
        string='Увага',
        help='Подія потребує уваги (пуск не з першої спроби, генератор не підхопив навантаження …).')
    energy_kwh = fields.Float(
        string='Вироблено, kWh', aggregator='sum',
        help='Вироблено за час роботи (різниця лічильника 03H 0048–0049).')
    peak_kw = fields.Float(
        string='Пік, kW', aggregator='max',
        help='Найбільше навантаження за подію.')
    fuel_delta_l = fields.Float(
        string='Зміна палива, L', aggregator='sum',
        help='Зміна палива в баку за подію, L (знакова).')
    crank_attempts = fields.Integer(
        string='Спроб пуску', aggregator='max',
        help='Кількість спроб прокрутки стартером (переходи стану 3 → 4, плюс 1).')
    crank_min_battery_v = fields.Float(
        string='АКБ при прокрутці, V', aggregator='min',
        help='Мінімальна напруга АКБ серед знімків зі станом «Прокрутка стартером». Точність обмежена '
             'інтервалом знімків: справжній мінімум під час прокрутки може бути нижчим (ФВ-26).')
    time_to_pickup_s = fields.Integer(
        string='Підхопив за, с', aggregator='avg',
        help='Від зникнення мережі до першого знімка з генератором під навантаженням.')
    outage_kind = fields.Selection(
        OUTAGE_KINDS, string='Вид відключення',
        help='З сигналів мережі 01H 0064–0069.')
    mode_from = fields.Selection(
        CONTROLLER_MODES, string='Режим був',
        help='Режим до зміни (керування не з Odoo).')
    mode_to = fields.Selection(
        CONTROLLER_MODES, string='Режим став',
        help='Режим після зміни (керування не з Odoo).')
    alarm_id = fields.Many2one(
        'td.genset.alarm', string='Тривога', ondelete='set null',
        help='Тривога, пов\'язана з подією «Тривога контролера».')
    reading_start_id = fields.Many2one(
        'td.genset.reading', string='Знімок початку', ondelete='set null',
        help='Знімок, з якого почалася подія.')
    reading_end_id = fields.Many2one(
        'td.genset.reading', string='Знімок кінця', ondelete='set null',
        help='Знімок, яким подія закрилася.')
    refuel_id = fields.Many2one(
        'td.genset.refuel', string='Запис заправки', ondelete='set null',
        help='Запис заправки, з яким звірено подію «Заправка».')
    command_id = fields.Many2one(
        'td.genset.command', string='Команда', ondelete='set null',
        help='Команда Odoo, з якої почалася робота (кнопка «Пуск», тест).')

    @api.depends('event_type', 'fuel_delta_l', 'summary', 'reason')
    def _compute_display_name(self):
        """Тип події; для заправки/падіння рівня — «Заправка +87 L (51 → 138 L)» (AC-40), для керування не з
        Odoo — «Керування не з Odoo: Авто → Ручний (застосунок SmartGen)» (AC-27), для тривоги — її назва."""
        labels = dict(self._fields['event_type']._description_selection(self.env))
        for event in self:
            label = labels.get(event.event_type) or _('Подія')
            if event.event_type in ('refuel', 'drain') and event.fuel_delta_l:
                levels = (event.summary or '').split(' — ')[0]
                label = '%s %s L (%s)' % (label, signed_liters(event.fuel_delta_l), levels) if levels else \
                    '%s %s L' % (label, signed_liters(event.fuel_delta_l))
            elif event.event_type == 'external_control' and event.summary:
                label = '%s: %s' % (label, event.summary)
            elif event.event_type == 'alarm' and event.reason:
                label = '%s: %s' % (label, event.reason)
            event.display_name = label

    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for event in self:
            if event.date_start and event.date_end:
                event.duration = (event.date_end - event.date_start).total_seconds() / 3600.0
            else:
                event.duration = 0.0
            event.is_open = not event.date_end

    # ------------------------------------------------------------------ движок подій (W1)
    @api.model
    def _process_readings(self, genset, readings):
        """Прогін правил 2.8.1 (``run/outage/refuel/drain/external_control/alarm/gap``) по знімках у порядку
        ``relay_id`` зі станом на генераторі (``prev_reading_id``, ``open_*_event_id``, ``open_alarm_codes``);
        у ``catchup_mode`` не кличе ``_raise`` і не пише інформаційних повідомлень.

        :param genset: запис ``td.genset``.
        :param readings: нові знімки ``td.genset.reading`` (будь-який порядок).
        """
        self._td_process(genset, readings)
        return None

    def _td_process(self, genset, readings):
        """Реалізація ``_process_readings``; повертає статистику ``{'events': N, 'refuel': bool}``."""
        stats = {'events': 0, 'refuel': False}
        genset = genset.sudo()
        readings = readings.filtered(lambda reading: reading.genset_id == genset)
        prev_reading = genset.prev_reading_id
        if prev_reading:
            readings = readings.filtered(lambda reading: reading.relay_id > prev_reading.relay_id)
        if not readings:
            return stats
        events_before = self.sudo().search_count([('genset_id', '=', genset.id)])
        rows = self._td_rows(readings)
        config = self.env['td.genset.config'].sudo().get()
        catchup = genset.catchup_mode
        prev = self._td_rows(prev_reading)[0] if prev_reading else None
        window_min = max(REFUEL_WINDOW_MIN, config.drain_window_min or 0)
        history = deque(self._td_window_rows(genset, rows[0]['ts'] - timedelta(minutes=window_min), rows[0]['ts'],
                                             exclude_ids=[row['id'] for row in rows]))
        state = {
            'run': genset.open_run_event_id,
            'outage': genset.open_outage_event_id,
            'codes': dict(genset.open_alarm_codes or {}),
            'running': self._td_initial(prev, 'is_running', genset.open_run_event_id),
            'mains': self._td_initial(prev, 'mains_ok', genset.open_outage_event_id, inverse=True),
            'refuel': self._td_recent_fuel_event(genset, 'refuel', rows[0]['ts'] - timedelta(minutes=REFUEL_WINDOW_MIN)),
            'drain': self._td_recent_fuel_event(genset, 'drain',
                                                rows[0]['ts'] - timedelta(minutes=config.drain_window_min or 60)),
        }
        for row in rows:
            if prev and (row['ts'] - prev['ts']) > timedelta(minutes=GAP_MIN):
                minutes = int(round((row['ts'] - prev['ts']).total_seconds() / 60.0))
                self._open(genset, 'gap', prev['ts'], date_end=row['ts'], reading_start_id=prev['id'],
                           reading_end_id=row['id'], summary=_('Немає даних %s хв', minutes))
            self._td_rule_outage(genset, row, state, catchup)
            self._td_rule_run(genset, row, state, catchup)
            self._td_sync_signal_codes(genset, row, state['codes'], raise_alarms=not catchup)
            if prev:
                self._detect_external_control(genset, prev=prev, cur=row)
            if self._td_rule_fuel(genset, history, row, state, catchup, config):
                stats['refuel'] = True
            history.append(row)
            cutoff = row['ts'] - timedelta(minutes=window_min)
            while history and history[0]['ts'] < cutoff:
                history.popleft()
            prev = row
        genset.write({
            'prev_reading_id': rows[-1]['id'],
            'open_run_event_id': state['run'].id if state['run'] else False,
            'open_outage_event_id': state['outage'].id if state['outage'] else False,
            'open_alarm_codes': state['codes'],
        })
        if not catchup and genset.last_reading_id.id == rows[-1]['id']:
            self.env['td.genset.alarm']._td_apply_state_alarms(genset, rows[-1], genset.last_values_json)
        stats['events'] = self.sudo().search_count([('genset_id', '=', genset.id)]) - events_before
        return stats

    # ------------------------------------------------------------------ дані знімків з NULL
    @api.model
    def _td_rows(self, readings):
        """Значення знімків для правил (dict на знімок, ``None`` = NULL) у порядку ``relay_id``."""
        if not readings:
            return []
        readings.flush_recordset()
        self.env.cr.execute(SQL(
            "SELECT %s FROM td_genset_reading WHERE id IN %s ORDER BY relay_id, id",
            SQL(', ').join(SQL.identifier(column) for column in ROW_COLUMNS), tuple(readings.ids)))
        return [dict(zip(ROW_COLUMNS, values)) for values in self.env.cr.fetchall()]

    @api.model
    def _td_window_rows(self, genset, ts_from, ts_to, exclude_ids=()):
        """Знімки генератора з ``ts_from ≤ ts ≤ ts_to`` (з NULL) у порядку часу."""
        self.env['td.genset.reading'].flush_model()
        self.env.cr.execute(SQL(
            "SELECT %s FROM td_genset_reading WHERE genset_id = %s AND ts >= %s AND ts <= %s "
            "AND NOT (id = ANY(%s)) ORDER BY ts, relay_id",
            SQL(', ').join(SQL.identifier(column) for column in ROW_COLUMNS), genset.id, ts_from, ts_to,
            list(exclude_ids)))
        return [dict(zip(ROW_COLUMNS, values)) for values in self.env.cr.fetchall()]

    def _td_event_rows(self, genset, event, row, include_end=True):
        """Знімки події від знімка початку до ``row`` включно — за ``relay_id`` (кілька знімків ``change`` можуть
        мати ту саму секунду, тож межі за часом недостатньо)."""
        start = event.reading_start_id
        if not start:
            return self._td_window_rows(genset, event.date_start, row['ts'],
                                        exclude_ids=[] if include_end else [row['id']])
        self.env['td.genset.reading'].flush_model()
        self.env.cr.execute(SQL(
            "SELECT %s FROM td_genset_reading WHERE genset_id = %s AND relay_id >= %s AND relay_id %s %s "
            "ORDER BY relay_id",
            SQL(', ').join(SQL.identifier(column) for column in ROW_COLUMNS), genset.id, start.relay_id,
            SQL('<=') if include_end else SQL('<'), row['relay_id']))
        return [dict(zip(ROW_COLUMNS, values)) for values in self.env.cr.fetchall()]

    @staticmethod
    def _td_initial(prev, key, open_event, inverse=False):
        """Останнє відоме значення ознаки перед сторінкою: зі знімка P, інакше — з відкритої події."""
        if prev is None:
            return None
        if prev[key] is not None:
            return prev[key]
        return (not open_event) if inverse else bool(open_event)

    # ------------------------------------------------------------------ відкриття / закриття
    @api.model
    def _open(self, genset, event_type, date_start, **vals):
        """Створює подію (``date_end = NULL``, якщо не передано) і повертає її."""
        values = {'genset_id': genset.id, 'event_type': event_type, 'date_start': date_start}
        values.update(vals)
        return self.sudo().create(values)

    @api.model
    def _close(self, event, date_end, **vals):
        """Закриває подію: ``date_end``, атрибути (``energy_kwh``, ``peak_kw``, ``fuel_delta_l``, ``summary`` …)."""
        if not event:
            return None
        values = {'date_end': date_end}
        values.update(vals)
        event.sudo().write(values)
        return None

    # ------------------------------------------------------------------ відключення мережі
    def _td_rule_outage(self, genset, row, state, catchup):
        current, last = row['mains_ok'], state['mains']
        if current is None:
            return
        state['mains'] = current
        if last is None:
            return
        if last and not current and not state['outage']:
            state['outage'] = self._open(genset, 'outage', row['ts'], reading_start_id=row['id'])
            if not catchup:
                genset._td_post_info(_('Зникла мережа о %s.', hhmm(row['ts'])))
        elif not last and current and state['outage']:
            event = state['outage']
            self._td_close_outage(genset, event, row)
            state['outage'] = self.browse()
            if not catchup:
                genset._td_post_info(_('Мережа повернулася: %(summary)s (без мережі %(duration)s).',
                                       summary=event.summary, duration=fmt_duration(self.env, event.duration)))

    def _td_close_outage(self, genset, event, row):
        rows = self._td_event_rows(genset, event, row, include_end=False)
        kind = False
        for column, value in OUTAGE_KIND_SIGNALS:
            if any(item[column] for item in rows):
                kind = value
                break
        pickup = next((item for item in rows if item['gen_on_load']), None)
        last = rows[-1] if rows else None
        full = bool(pickup and last and last['gen_on_load'])
        start_mode = rows[0]['controller_mode'] if rows else genset.controller_mode
        if pickup and full:
            seconds = int((pickup['ts'] - event.date_start).total_seconds())
            summary = _('Генератор підхопив за %s с', seconds)
        elif pickup:
            seconds = int((pickup['ts'] - event.date_start).total_seconds())
            summary = _('Генератор працював частково — до кінця вікна розкладу')
        elif start_mode and start_mode not in ('auto', 'unknown'):
            seconds = False
            mode_label = dict(self._fields['mode_from']._description_selection(self.env)).get(start_mode, start_mode)
            summary = _('Генератор не запускався — поза розкладом (режим %s)', mode_label)
        else:
            seconds = False
            summary = _('Генератор не запускався')
        kinds = dict(self._fields['outage_kind']._description_selection(self.env))
        self._close(event, row['ts'], reading_end_id=row['id'], outage_kind=kind, time_to_pickup_s=seconds,
                    summary=summary, is_bad=not (pickup and full), reason=kinds.get(kind, False))

    # ------------------------------------------------------------------ робота генератора
    def _td_rule_run(self, genset, row, state, catchup):
        current, last = row['is_running'], state['running']
        if current is None:
            return
        state['running'] = current
        if last is None:
            return
        if not last and current and not state['run']:
            event = self._open(genset, 'run', row['ts'], reading_start_id=row['id'],
                               **self._td_run_reason(genset, row, state))
            state['run'] = event
            if not catchup:
                genset._td_post_info(_('Генератор запущено о %(time)s: %(reason)s.',
                                       time=hhmm(row['ts']), reason=event.reason))
        elif last and not current and state['run']:
            event = state['run']
            self._td_close_run(genset, event, row, state)
            state['run'] = self.browse()
            if not catchup:
                genset._td_post_info(_('Генератор зупинено о %(time)s: %(summary)s.',
                                       time=hhmm(row['ts']), summary=event.summary))

    def _td_run_reason(self, genset, row, state):
        """Причина пуску (2.8.1): команда Odoo ``start``/``test`` → «Тест · хто» / «Кнопка «Пуск» · хто»;
        відкрите відключення в Авто → «Зникла мережа · режим Авто за розкладом|таймером»; інакше «Пуск не з Odoo»."""
        command = self._td_odoo_command(genset, ('start', 'test'), row['ts'])
        if command:
            who = command.user_id.name or _('Система')
            if command.command == 'test' or command.source == 'test':
                return {'reason': _('Тест · %s', who), 'command_id': command.id}
            return {'reason': _('Кнопка «Пуск» · %s', who), 'command_id': command.id}
        if state['outage'] and row['controller_mode'] == 'auto':
            by_timer = genset.control_source == 'timer' or (genset.timer_end and genset.timer_end > row['ts'])
            return {'reason': _('Зникла мережа · режим Авто за таймером') if by_timer
                    else _('Зникла мережа · режим Авто за розкладом')}
        return {'reason': _('Пуск не з Odoo')}

    def _td_close_run(self, genset, event, row, state):
        rows = self._td_event_rows(genset, event, row)
        energies = [item['energy_kwh'] for item in rows if item['energy_kwh'] is not None]
        powers = [item['active_power'] for item in rows if item['active_power'] is not None]
        fuel_rows = [item for item in rows if item['fuel_liters'] is not None]
        statuses = [item['genset_status'] for item in rows if item['genset_status'] is not None]
        attempts = 1 + sum(1 for before, after in zip(statuses, statuses[1:]) if before == '3' and after == '4')
        crank_volts = [item['battery_v'] for item in rows if item['genset_status'] == '3'
                       and item['battery_v'] is not None]
        loaded = any(item['gen_on_load'] for item in rows)
        if state['outage']:
            summary = _('Пуск з %(n)s-ї спроби; зупинено о %(time)s за розкладом — мережі ще не було',
                        n=attempts, time=hhmm(row['ts']))
        elif loaded:
            summary = _('Пуск з %s-ї спроби, навантаження прийнято', attempts)
        else:
            summary = _('Пуск з %s-ї спроби, без навантаження', attempts)
        self._close(event, row['ts'],
                    reading_end_id=row['id'],
                    energy_kwh=(energies[-1] - energies[0]) if len(energies) > 1 else 0.0,
                    peak_kw=max(powers) if powers else 0.0,
                    fuel_delta_l=self._td_fuel_delta(genset, fuel_rows[0], fuel_rows[-1]) if fuel_rows else 0.0,
                    crank_attempts=attempts,
                    crank_min_battery_v=min(crank_volts) if crank_volts else False,
                    summary=summary,
                    is_bad=attempts > 1)

    @api.model
    def _td_fuel_delta(self, genset, start, end):
        """ΔL між знімками: для літрів «за %» — з різниці відсотків (без подвійного округлення, AC-38), інакше —
        різниця літрів (0,1 L)."""
        if start['fuel_source'] == 'pct' and end['fuel_source'] == 'pct' \
                and start['fuel_level'] is not None and end['fuel_level'] is not None:
            return float(round((end['fuel_level'] - start['fuel_level']) / 100.0 * (genset.tank_volume_l or 0.0)))
        return round(end['fuel_liters'] - start['fuel_liters'], 1)

    # ------------------------------------------------------------------ тривоги контролера (2.8.3)
    @api.model
    def _td_sync_signal_codes(self, genset, row, codes, raise_alarms=True):
        """Фронти сигналів 01H за знімком: подія «Тривога контролера» відкривається/закривається;
        ``raise_alarms`` (поза догоном) — ще й ``_raise``/``_clear``. ``codes`` (``open_alarm_codes``) змінюється."""
        alarm_model = self.env['td.genset.alarm']
        active, unknown = alarm_model._td_signal_state(row)
        for code, (level, name, description) in active.items():
            entry = codes.get(code)
            event = self.sudo().browse(entry['event']).exists() if entry and entry.get('event') else self.browse()
            if not event:
                event = self._open(genset, 'alarm', row['ts'], reading_start_id=row['id'], reason=name,
                                   is_bad=level == 'crit')
                entry = {'event': event.id, 'alarm': False}
                codes[code] = entry
            if raise_alarms and not entry.get('alarm'):
                alarm = alarm_model._raise(genset, code, level, name, description, source=event)
                entry['alarm'] = alarm.id
                event.sudo().alarm_id = alarm
        for code in list(codes):
            if code in active or code in unknown:
                continue
            entry = codes.pop(code)
            event = self.sudo().browse(entry.get('event')).exists() if entry.get('event') else self.browse()
            if event and event.is_open:
                self._close(event, row['ts'], reading_end_id=row['id'],
                            summary=_('знято о %s', hhmm(row['ts'])))
            if raise_alarms:
                alarm_model._clear(genset, code)
        return codes

    # ------------------------------------------------------------------ заправка і падіння рівня
    def _td_rule_fuel(self, genset, history, row, state, catchup, config):
        """Заправка (приріст ≥ порога за ≤ 10 хв) і падіння рівня без роботи (≥ порога за ≤ ``drain_window_min``).

        :return: True, якщо створено/подовжено подію «Заправка».
        """
        liters = row['fuel_liters']
        if liters is None:
            return False
        refuel = False
        since = row['ts'] - timedelta(minutes=REFUEL_WINDOW_MIN)
        candidates = [item for item in history if item['ts'] >= since and item['fuel_liters'] is not None]
        if candidates:
            base = min(candidates, key=lambda item: (item['fuel_liters'], item['ts']))
            if liters - base['fuel_liters'] >= (config.refuel_threshold_l or 0.0):
                refuel = self._td_fuel_event(genset, 'refuel', base, row, state, since, catchup)
        if row['is_running'] is not True:
            since = row['ts'] - timedelta(minutes=config.drain_window_min or 60)
            tail = []
            for item in history:
                if item['ts'] < since:
                    continue
                tail = [] if item['is_running'] else tail + [item]
            tail = [item for item in tail if item['fuel_liters'] is not None]
            if tail:
                base = max(tail, key=lambda item: (item['fuel_liters'], -item['ts'].timestamp()))
                if base['fuel_liters'] - liters >= (config.drain_threshold_l or 0.0):
                    self._td_fuel_event(genset, 'drain', base, row, state, since, catchup)
        return refuel

    def _td_fuel_event(self, genset, kind, base, row, state, since, catchup):
        """Створити або подовжити подію ``refuel``/``drain`` (пороги — у літрах, ФВ-31)."""
        recent = state.get(kind)
        if recent and recent['event'].exists() and recent['event'].date_end and recent['event'].date_end >= since:
            end = recent['end']
            better = row['fuel_liters'] > end['fuel_liters'] if kind == 'refuel' else \
                row['fuel_liters'] < end['fuel_liters']
            if not better:
                return False
            start = recent['start']
            recent['event'].sudo().write(self._td_fuel_vals(genset, kind, start, row))
            recent['end'] = row
            return kind == 'refuel'
        vals = self._td_fuel_vals(genset, kind, base, row)
        event = self._open(genset, kind, base['ts'], reading_start_id=base['id'], **vals)
        state[kind] = {'event': event, 'start': base, 'end': row}
        if catchup:
            return kind == 'refuel'
        alarm_model = self.env['td.genset.alarm']
        if kind == 'drain':
            lost = fmt_liters(abs(event.fuel_delta_l))
            text = _('Рівень палива впав на %(lost)s L без роботи двигуна (%(before)s → %(after)s L). '
                     'Можливий злив — перевірте бак.', lost=lost, before=fmt_liters(base['fuel_liters']),
                     after=fmt_liters(row['fuel_liters']))
            alarm_model._clear(genset, 'drain', note=_('Нове падіння рівня.'))
            alarm_model._raise(genset, 'drain', 'crit', _('Рівень палива впав на %s L без роботи двигуна', lost),
                               text, source=event)
        else:
            genset._td_post_info(_('Рівень палива зріс: %(delta)s L (%(before)s → %(after)s L).',
                                   delta=signed_liters(event.fuel_delta_l), before=fmt_liters(base['fuel_liters']),
                                   after=fmt_liters(row['fuel_liters'])))
        return kind == 'refuel'

    def _td_fuel_vals(self, genset, kind, start, end):
        delta = self._td_fuel_delta(genset, start, end)
        levels = '%s → %s L' % (fmt_liters(start['fuel_liters']), fmt_liters(end['fuel_liters']))
        if kind == 'drain':
            return {'date_end': end['ts'], 'reading_end_id': end['id'], 'fuel_delta_l': delta, 'is_bad': True,
                    'reason': _('Двигун не працював'), 'summary': _('%s — можливий злив', levels)}
        return {'date_end': end['ts'], 'reading_end_id': end['id'], 'fuel_delta_l': delta,
                'reason': _('Рівень палива різко зріс'), 'summary': levels}

    def _td_recent_fuel_event(self, genset, kind, since):
        """Остання подія ``refuel``/``drain`` генератора, що закінчилася не раніше ``since`` (для подовження)."""
        event = self.sudo().search([('genset_id', '=', genset.id), ('event_type', '=', kind),
                                    ('date_end', '>=', since)], order='date_end desc, id desc', limit=1)
        if not event or not event.reading_start_id or not event.reading_end_id:
            return None
        rows = {row['id']: row for row in self._td_rows(event.reading_start_id | event.reading_end_id)}
        start, end = rows.get(event.reading_start_id.id), rows.get(event.reading_end_id.id)
        if not start or not end or start['fuel_liters'] is None or end['fuel_liters'] is None:
            return None
        return {'event': event, 'start': start, 'end': end}

    # ------------------------------------------------------------------ керування не з Odoo
    @api.model
    def _detect_external_control(self, genset, prev=None, cur=None, cloud=None):
        """Правило ``external_control`` 2.8.1 (зі знімків ``prev``/``cur`` або з ``cloud_commands_seen``):
        подія, ``control_source='external'``, ``_raise('external_control')`` поза догоном (AC-27).

        :param prev: попередній знімок (запис ``td.genset.reading`` або dict ``_td_rows``).
        :param cur: поточний знімок (так само).
        :param list cloud: ``/status.devices[].cloud_commands_seen``.
        """
        genset = genset.sudo()
        if cloud is not None:
            self._td_external_from_cloud(genset, cloud)
        if prev is not None and cur is not None:
            if not isinstance(prev, dict):
                prev = self._td_rows(prev)[0] if prev else None
            if not isinstance(cur, dict):
                cur = self._td_rows(cur)[0] if cur else None
            if prev and cur:
                self._td_external_from_rows(genset, prev, cur)
        return None

    def _td_external_from_rows(self, genset, prev, cur):
        mode_from, mode_to = prev['controller_mode'], cur['controller_mode']
        if mode_from and mode_to and 'unknown' not in (mode_from, mode_to) and mode_from != mode_to:
            if not self._td_odoo_command(genset, (mode_to,), cur['ts']):
                self._td_external_event(genset, cur['ts'], 'panel', mode_from=mode_from, mode_to=mode_to,
                                        reading=cur)
            return
        if mode_to != 'manual' or mode_from != 'manual' or prev['is_running'] != cur['is_running'] \
                or prev['mains_ok'] != cur['mains_ok']:
            return
        for column, command in BREAKER_COMMANDS.items():
            if prev[column] is None or cur[column] is None or prev[column] == cur[column]:
                continue
            if not self._td_odoo_command(genset, (command,), cur['ts']):
                self._td_external_event(genset, cur['ts'], 'panel', breaker=column, closed=cur[column], reading=cur)

    def _td_external_from_cloud(self, genset, cloud):
        entries = []
        for entry in cloud or []:
            stamp = parse_utc(entry.get('time_utc'))
            if stamp:
                entries.append((stamp, entry))
        entries.sort(key=lambda item: item[0])
        last = genset.cloud_cmd_last_utc
        if not last:
            # перший /status: старі записи — історія, подій не створюємо
            genset.cloud_cmd_last_utc = entries[-1][0] if entries else (genset.relay_time_utc or fields.Datetime.now())
            return
        new = [(stamp, entry) for stamp, entry in entries if stamp > last]
        if not new:
            return
        for stamp, entry in new:
            command = entry.get('command')
            if command in MODE_COMMANDS:
                before = self.env['td.genset.reading'].sudo().search(
                    [('genset_id', '=', genset.id), ('ts', '<=', stamp)], order='ts desc, id desc', limit=1)
                mode_from = before.controller_mode if before else genset.controller_mode
                self._td_external_event(genset, stamp, 'cloud', mode_from=mode_from, mode_to=command)
            elif command in BREAKER_COMMANDS.values():
                column = next(key for key, value in BREAKER_COMMANDS.items() if value == command)
                self._td_external_event(genset, stamp, 'cloud', breaker=column)
            else:
                self._td_external_event(genset, stamp, 'cloud')
        genset.cloud_cmd_last_utc = new[-1][0]

    def _td_external_event(self, genset, stamp, source, mode_from=None, mode_to=None, breaker=None, closed=None,
                           reading=None):
        """Подія «Керування не з Odoo» (+ тривога-попередження поза догоном); дубль зі знімка і з хмари
        (``cloud_commands_seen``) в межах вікна повторів об'єднується в одну подію."""
        config = self.env['td.genset.config'].sudo().get()
        window = timedelta(minutes=(config.retry_window_min or 10) + 2)
        source_label = _('застосунок SmartGen') if source == 'cloud' else _('панель контролера')
        modes = dict(self._fields['mode_from']._description_selection(self.env))
        if mode_to:
            change = '%s → %s' % (modes.get(mode_from, _('невідомо')) if mode_from else _('невідомо'),
                                  modes.get(mode_to, mode_to))
        elif breaker:
            name = _('Автомат генератора') if breaker == 'gen_on_load' else _('Автомат мережі')
            if closed is None:
                change = name
            else:
                change = '%s: %s' % (name, _('замкнено') if closed else _('розімкнено'))
        else:
            change = _('команда')
        summary = '%s (%s)' % (change, source_label)
        domain = [('genset_id', '=', genset.id), ('event_type', '=', 'external_control'),
                  ('date_start', '>=', stamp - window), ('date_start', '<=', stamp + window)]
        if mode_to:
            domain.append(('mode_to', '=', mode_to))
        duplicate = self.sudo().search(domain, order='date_start desc', limit=1) if (mode_to or breaker) else None
        if duplicate:
            if source == 'cloud' and duplicate.reason != source_label:
                duplicate.write({'reason': source_label, 'summary': summary})
            return duplicate
        event = self._open(genset, 'external_control', stamp, date_end=stamp, reason=source_label, summary=summary,
                           mode_from=mode_from if mode_from in modes else False,
                           mode_to=mode_to if mode_to in modes else False,
                           reading_start_id=reading['id'] if reading else False)
        changed = bool(mode_to and mode_from != mode_to) or bool(breaker)
        if changed:
            genset.control_source = 'external'
        if changed and not genset.catchup_mode:
            alarm_model = self.env['td.genset.alarm']
            name = _('Керування не з Odoo: %s', summary)
            alarm_model._clear(genset, 'external_control', note=_('Нова зміна не з Odoo.'))
            alarm_model._raise(genset, 'external_control', 'warn', name,
                               _('%s. Режим не повертається до наступного переходу.', name), source=event)
        return event

    @api.model
    def _td_odoo_command(self, genset, commands, stamp):
        """Команда Odoo (надіслана/виконана) з одним із ``commands`` за останні ``retry_window_min + 2`` хв."""
        config = self.env['td.genset.config'].sudo().get()
        since = stamp - timedelta(minutes=(config.retry_window_min or 10) + 2)
        return self.env['td.genset.command'].sudo().search([
            ('genset_id', '=', genset.id), ('command', 'in', list(commands)), ('state', 'in', ODOO_COMMAND_STATES),
            '|', ('sent_at', '>=', since), ('first_sent_at', '>=', since),
        ], order='id desc', limit=1)


# --------------------------------------------------------------------------- допоміжні функції
def parse_utc(text):
    """``'2026-10-07T15:57:22Z'`` → naive UTC ``datetime`` (``None``, якщо порожньо/не розібрано)."""
    if not text:
        return None
    try:
        return datetime.strptime(str(text)[:19], '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return None


def signed_liters(value):
    """«+87» / «−12» для літрів (знак мінус — типографський)."""
    text = fmt_liters(abs(value or 0.0))
    return ('+%s' % text) if (value or 0.0) >= 0 else ('−%s' % text)


def fmt_duration(env, hours):
    """Тривалість у годинах → «1 год 56 хв» / «25 хв»."""
    minutes = int(round((hours or 0.0) * 60))
    if minutes >= 60:
        return env._('%(hours)s год %(minutes)s хв', hours=minutes // 60, minutes=minutes % 60)
    return env._('%s хв', minutes)
