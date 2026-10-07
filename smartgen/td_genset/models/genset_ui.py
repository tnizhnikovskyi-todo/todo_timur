# Part of td_genset (ToDo). Власник файлу: W3 «UI».
"""``td.genset`` (inherit): дані для форми і пульта — ТР 2.10, 2.11, А.9; SPEC 9, 10, 11.

* ``get_pult_state`` — стан OWL-віджета ``td_genset_pult`` (формат А.9 + службові ключі ``notes``,
  ``link``, ``mode``, ``limits``); права на кнопки — ``group_tech`` (AC-24), серверні перевірки — у W2.
* ``current_data_html`` — вкладка «Поточні дані»: усі значення останнього знімка з ``last_values_json``
  (null або відсутній ключ → «немає даних», AC-06), оми датчиків поруч із °C / kPa / %, літри з джерелом
  ``fuel_source`` (ФВ-31), сигнали 01H і блок «Ретранслятор».
* KPI вкладки «Аналітика» за 7/30 днів (``_read_group`` по подіях і знімках).
"""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.tools.misc import formatLang

from .genset import CONTROL_SOURCES, CONTROLLER_MODES, FEED_SOURCES, FUEL_SOURCES, GENSET_STAGES, GENSET_STATUS, \
    LINK_STATES, TEST_MODES

PULT_BUTTONS = ('auto', 'manual', 'start', 'stop', 'test')
KPI_FIELDS = (
    'kpi_run_hours_7d', 'kpi_run_hours_30d', 'kpi_starts_7d', 'kpi_starts_30d',
    'kpi_energy_kwh_7d', 'kpi_energy_kwh_30d', 'kpi_outages_7d', 'kpi_outages_30d',
    'kpi_covered_pct_7d', 'kpi_covered_pct_30d', 'kpi_avg_load_pct_7d', 'kpi_avg_load_pct_30d',
    'kpi_first_try_pct_7d', 'kpi_first_try_pct_30d', 'kpi_crank_battery_min_7d', 'kpi_crank_battery_min_30d',
)
# Прилади і параметри пульта: ключ values знімка (А.9 ``gauges`` + параметри мокапа)
GAUGE_KEYS = (
    'speed', 'active_power', 'oil_pressure', 'water_temp', 'battery_v', 'dplus_v', 'load_pct', 'fuel_level',
    'current_a', 'current_b', 'current_c', 'gen_uab', 'gen_ubc', 'gen_uca', 'gen_freq', 'power_factor',
    'mains_uab', 'mains_ubc', 'mains_uca', 'mains_freq',
)
# Сигнали 01H за групами (мокап «Сигнали · 01H»; адреси — relay_api.md 5.2): (ключ, адреса, тип)
SIGNAL_GROUPS = (
    ('state', (
        ('common_alarm', 0), ('common_warning', 1), ('common_shutdown', 2), ('remote_mode', 3), ('remote_lock', 4),
        ('mains_on_load', 6), ('gen_on_load', 7), ('test_mode', 40), ('auto_mode', 41), ('manual_mode', 42),
        ('stop_mode', 43), ('scheduled_not_run', 78))),
    ('crit', (
        ('emergency_stop', 8), ('overspeed_shutdown', 9), ('underspeed_shutdown', 10),
        ('speed_signal_loss_shutdown', 11), ('overfrequency_shutdown', 12), ('underfrequency_shutdown', 13),
        ('overvoltage_shutdown', 14), ('undervoltage_shutdown', 15), ('gen_overcurrent_shutdown', 16),
        ('crank_failure', 17), ('high_temp_shutdown', 18), ('low_oil_pressure_shutdown', 19),
        ('frequency_loss_alarm', 20), ('input_shutdown', 21), ('low_fuel_shutdown', 22), ('low_coolant_shutdown', 23),
        ('temp_sensor_open_shutdown', 44), ('oil_pressure_sensor_open_shutdown', 45), ('maintenance_due_shutdown', 46),
        ('overpower_shutdown', 47))),
    ('warn', (
        ('high_temp_warning', 24), ('low_oil_pressure_warning', 25), ('gen_overcurrent_warning', 26),
        ('stop_failure_warning', 27), ('low_fuel_warning', 28), ('charging_failure_warning', 29),
        ('battery_undervoltage_warning', 30), ('battery_overvoltage_warning', 31), ('input_warning', 32),
        ('speed_signal_loss_warning', 33), ('low_coolant_warning', 34), ('temp_sensor_open_warning', 35),
        ('oil_pressure_sensor_open_warning', 36), ('maintenance_due_warning', 37), ('charger_fail_warning', 38),
        ('overpower_warning', 39))),
    ('mains', (
        ('mains_fault', 64), ('mains_normal', 65), ('mains_overvoltage', 66), ('mains_undervoltage', 67),
        ('mains_loss_phase', 68), ('mains_blackout', 69))),
    ('gen', (
        ('gen_normal', 72), ('gen_overvoltage', 73), ('gen_undervoltage', 74), ('gen_overfrequency', 75),
        ('gen_underfrequency', 76), ('gen_overcurrent', 77))),
    ('io', (
        ('emergency_stop_input', 48), ('aux_input_1', 49), ('aux_input_2', 50), ('aux_input_3', 51),
        ('aux_input_4', 52), ('aux_input_5', 53), ('crank_relay', 56), ('fuel_relay', 57), ('aux_output_1', 58),
        ('aux_output_2', 59), ('aux_output_3', 60), ('aux_output_4', 61))),
)
# Префікси підписів полів знімка, зайві всередині групи з такою ж назвою
SIGNAL_PREFIXES = ('Аварія: ', 'Попередження: ', 'Мережа: ', 'Генератор: ')
ANALYTICS_ACTIONS = {
    'run_outage': 'td_genset.action_td_genset_analytics_run_outage',
    'energy': 'td_genset.action_td_genset_analytics_energy',
    'cranks': 'td_genset.action_td_genset_analytics_cranks',
    'fuel_used': 'td_genset.action_td_genset_analytics_fuel_used',
    'fuel_level': 'td_genset.action_td_genset_analytics_fuel_level',
    'battery': 'td_genset.action_td_genset_analytics_battery',
}
REMOTE_START_TEXT = {0: 'No Delay', 1: 'Start Delay', 2: 'Stop Delay'}
MAINS_STATUS_TEXT = {0: 'Normal', 1: 'Abnormal', 2: 'No Delay'}
MISSING = object()


def _iso(value):
    """naive UTC datetime → ``'2026-10-07T16:35:25Z'`` (або None)."""
    return value.strftime('%Y-%m-%dT%H:%M:%SZ') if value else None


class TdGensetUi(models.Model):
    _inherit = 'td.genset'

    # ================================================================== службові
    def _td_values(self):
        """``values`` останнього знімка (dict; порожній, якщо знімків ще не було)."""
        self.ensure_one()
        values = self.last_values_json
        return values if isinstance(values, dict) else {}

    def _td_value(self, key, values=None):
        """Значення ключа ``values``: ``None`` — «немає даних» (null у знімку або ключа немає), SPEC 4."""
        values = self._td_values() if values is None else values
        value = values.get(key)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    def _td_local(self, value, fmt='%d.%m %H:%M'):
        """naive UTC → рядок у часовому поясі користувача (для підказок «дані на HH:MM»)."""
        if not value:
            return ''
        return fields.Datetime.context_timestamp(self, value).strftime(fmt)

    def _td_role_label(self):
        user = self.env.user
        if user.has_group('td_genset.group_tech'):
            return _('Тех. адміністратор')
        if user.has_group('td_genset.group_admin'):
            return _('Адміністратор')
        return _('Співробітник')

    def _td_pult_access(self):
        """``(can_control, block_reason, notes)`` для поточного користувача (AC-24, AC-23, AC-66, ФВ-15/17).

        Плитки й автомати неактивні без hostid/опитування, без зв'язку, при вимкнених командах на
        ретрансляторі і для не тех. адміністратора. Блокування на контролері і вимкнений перемикач
        «Дозволити команди» не блокують плитки: команда записується зі станом «Не надіслано: …» (ФВ-15,
        AC-23, AC-66) — віджет показує пояснення (``notes``).
        """
        self.ensure_one()
        is_tech = self.env.user.has_group('td_genset.group_tech')
        role_text = _('Ваша роль — %(role)s: пульт і автомати доступні тех. адміністратору. Вам доступна '
                      'робота поза графіком.', role=self._td_role_label())
        reasons = []
        if not self.relay_hostid or not self.relay_enabled:
            reasons.append(_('Вкажіть hostid і ввімкніть опитування — до цього пульт неактивний.'))
        elif self.link_state != 'online':
            text = _("Немає зв'язку з модулем — команди неможливо доставити.")
            if self.last_reading_at:
                text = '%s %s' % (text, _('Показано останні отримані дані (%(when)s).',
                                          when=self._td_local(self.last_reading_at)))
            reasons.append(text)
        elif not self.relay_commands_enabled:
            reasons.append(_('Керування вимкнено на ретрансляторі (RELAY_COMMANDS_ENABLED=0): плитки неактивні до '
                             'зміни налаштування ретранслятора.'))
        if not is_tech:
            reasons.append(role_text)
        notes = []
        if self.remote_lock:
            notes.append({'level': 'warning', 'text': _('Дистанційне керування заблоковано на контролері (01H 0004): '
                                                         'команди з пульта, розкладу і таймера не надсилаються.')})
        if not self.sudo().commands_allowed:
            notes.append({'level': 'info', 'text': _('Команди вимкнено в Odoo (перемикач «Дозволити команди» на '
                                                      'картці): команда буде записана як «Не надіслано: команди '
                                                      'вимкнено в Odoo».')})
        block_reason = reasons[0] if reasons else None
        notes = [{'level': 'muted', 'text': text} for text in reasons[1:]] + notes
        return not reasons, block_reason, notes

    # ================================================================== пульт (А.9)
    def get_pult_state(self):
        """Стан пульта для OWL-віджета ``td_genset_pult`` (А.9). Перевіряє ``check_access('read')``.

        Формат А.9: ``{can_control, block_reason, buttons{auto,manual,start,stop,test: {enabled, active}},
        breakers{gen, mains}, gauges{…}, status{code,label,stage,delay}, feed, timer, test, server_now}``;
        додатково: ``notes`` (пояснення — блокування, вимкнені команди), ``is_tech``, ``mode``, ``source``,
        ``link``, ``reading_at``, ``limits``, ``controller``, ``timer_rule``. Значення приладів — з
        ``last_values_json`` (``None`` — «немає даних», AC-06). AC-24, AC-62.
        """
        self.ensure_one()
        self.check_access('read')
        can_control, block_reason, notes = self._td_pult_access()
        values = self._td_values()
        mode = self.controller_mode or 'unknown'
        stage = self.genset_stage
        active = {
            'auto': mode == 'auto',
            'manual': mode == 'manual',
            'test': mode == 'test',
            'start': stage in ('start', 'run'),
            'stop': stage == 'stop',
        }
        gauges = {key: self._td_value(key, values) for key in GAUGE_KEYS}
        has_fuel = self.last_reading_id and gauges['fuel_level'] is not None or self.fuel_source == 'ohm'
        gauges['fuel_liters'] = self.fuel_liters if self.last_reading_id and has_fuel else None
        gauges['fuel_sensor_ohm'] = self._td_value('fuel_level_sensor_ohm', values)
        gauges['water_temp_sensor_ohm'] = self._td_value('water_temp_sensor_ohm', values)
        gauges['oil_pressure_sensor_ohm'] = self._td_value('oil_pressure_sensor_ohm', values)
        status_labels = dict(GENSET_STATUS)
        timer = None
        if self.timer_end:
            timer = {
                'end': _iso(self.timer_end),
                'started_at': _iso(self.timer_started_at),
                'started_by': self.timer_user_id.name or '',
                'progress': round((self.timer_progress or 0.0) / 100.0, 4),
            }
        test = None
        if self.test_end:
            test = {
                'end': _iso(self.test_end),
                'mode': self.test_mode or None,
                'mode_label': dict(TEST_MODES).get(self.test_mode, ''),
                'after': self.next_event_text or '',
            }
        has_mains_breaker = bool(self.controller_model_id.has_mains_breaker)
        rated_current = (self.power_kw or 0.0) * 1000.0 / (3 ** 0.5 * 400.0) if self.power_kw else 0.0
        return {
            'can_control': can_control,
            'block_reason': block_reason,
            'notes': notes,
            'is_tech': self.env.user.has_group('td_genset.group_tech'),
            'buttons': {name: {'enabled': can_control, 'active': active[name]} for name in PULT_BUTTONS},
            'breakers': {
                'gen': {
                    'closed': bool(self.gen_on_load),
                    'target_label': _('Розімкнути') if self.gen_on_load else _('Замкнути'),
                    'enabled': can_control,
                },
                'mains': {
                    'closed': bool(self.mains_on_load),
                    'target_label': _('Розімкнути') if self.mains_on_load else _('Замкнути'),
                    'enabled': can_control and has_mains_breaker,
                    'available': has_mains_breaker,
                },
            },
            'gauges': gauges,
            'status': {
                'code': self.genset_status or None,
                'label': status_labels.get(self.genset_status) if self.genset_status else None,
                'stage': stage or None,
                'stage_label': dict(GENSET_STAGES).get(stage) if stage else None,
                'delay': self.genset_status_delay or 0,
                'is_running': bool(self.is_running),
            },
            'feed': self.feed_source or 'none',
            'feed_label': dict(FEED_SOURCES).get(self.feed_source or 'none'),
            'mode': {'value': mode, 'label': dict(CONTROLLER_MODES).get(mode)},
            'source': {'value': self.control_source or None,
                       'label': dict(CONTROL_SOURCES).get(self.control_source) if self.control_source else None},
            'link': {'state': self.link_state or 'none', 'label': dict(LINK_STATES).get(self.link_state or 'none'),
                     'changed_at': _iso(self.link_changed_at)},
            'reading_at': _iso(self.last_reading_at) if self.last_reading_id else None,
            'has_reading': bool(self.last_reading_id),
            'fuel_source': self.fuel_source or None,
            'fuel_source_label': dict(FUEL_SOURCES).get(self.fuel_source) if self.fuel_source else None,
            'limits': {
                'power_kw': self.power_kw or 0.0,
                'tank_l': self.tank_volume_l or 0.0,
                'current_a': round(rated_current, 1),
            },
            'controller': self.controller_model_id.name or '',
            'timer': timer,
            'test': test,
            'timer_rule': self.retry_rule_text or '',
            'server_now': _iso(fields.Datetime.now()),
        }

    # ================================================================== обчислювані поля UI
    @api.depends_context('uid')
    def _compute_ui_texts(self):
        """«Отримувачі тривог» (ланцюжок з налаштувань) і правило повторів з ``retry_*`` (ТР 2.10)."""
        config = self.env['td.genset.config'].get().sudo()
        names = [level.user_id.name for level in config.level_ids.sorted(lambda level: (level.sequence, level.id))
                 if level.user_id]
        recipients = ' → '.join(names) if names else _('ланцюжок не заповнено')
        rule = _("Після кожної команди система читає режим контролера; якщо він не змінився — повтор кожні "
                 "%(every)s хв протягом %(window)s хв, потім тривога. Якщо зв'язок зник до підтвердження — "
                 "перевіряємо після відновлення.",
                 every=config.retry_every_min or 2, window=config.retry_window_min or 10)
        for genset in self:
            genset.alarm_recipients_text = recipients
            genset.retry_rule_text = rule

    @api.depends('timer_end', 'timer_started_at')
    def _compute_timer_progress(self):
        """Прогрес таймера 0–100: частка часу від ``timer_started_at`` до ``timer_end``, що минула (AC-31)."""
        now = fields.Datetime.now()
        for genset in self:
            start, end = genset.timer_started_at, genset.timer_end
            if not end or not start or end <= start:
                genset.timer_progress = 100.0 if end and end <= now else 0.0
                continue
            share = (now - start).total_seconds() / (end - start).total_seconds()
            genset.timer_progress = round(min(1.0, max(0.0, share)) * 100.0, 1)

    @api.depends_context('uid')
    def _compute_is_tech(self):
        """Поточний користувач — «Генератори: Тех. адміністратор» (видимість кнопок, AC-24, AC-55)."""
        is_tech = self.env.user.has_group('td_genset.group_tech')
        for genset in self:
            genset.is_tech = is_tech

    @api.depends_context('uid')
    def _compute_is_admin(self):
        """Поточний користувач — «Генератори: Адміністратор» (редагування розкладу, AC-29, AC-56)."""
        is_admin = self.env.user.has_group('td_genset.group_admin')
        for genset in self:
            genset.is_admin = is_admin

    # ================================================================== «Поточні дані» (AC-05, AC-06, AC-60)
    @api.depends('last_reading_id', 'last_values_json', 'last_reading_at', 'fuel_source', 'fuel_liters', 'link_state',
                 'relay_hostid', 'relay_enabled')
    @api.depends_context('lang', 'tz')
    def _compute_current_data_html(self):
        """HTML вкладки «Поточні дані» з ``last_values_json``: картки «Мережа», «Генератор», «Навантаження»,
        «Двигун» (оми датчиків поруч із °C / kPa / %, літри з позначкою ``fuel_source``), «Стан і таймери»,
        «Лічильники і ТО», «Контролер», сигнали 01H, «Ретранслятор». null / відсутній ключ — «немає даних».
        """
        for genset in self:
            genset.current_data_html = genset._td_render_current_data()

    def _td_render_current_data(self):
        self.ensure_one()
        if not self.relay_hostid or not self.relay_enabled:
            hint = Markup('<div class="alert alert-info mb-3" role="status">%s</div>') % _(
                'Вкажіть hostid і ввімкніть опитування на вкладці «Підключення» — після першого знімка тут '
                "з'являться всі значення контролера.")
        else:
            hint = Markup('')
        if not self.last_reading_id:
            return Markup('<div class="o_td_genset_current_data">%s<p class="o_td_genset_no_data mb-0">%s</p></div>') % (
                hint, _('Очікуємо перший знімок: дані з\'являться після першого забору показань (раз на хвилину).'))
        values = self._td_values()
        parts = [hint]
        if self.link_state != 'online':
            parts.append(Markup('<div class="alert alert-warning mb-3" role="status">%s</div>') % _(
                "Немає зв'язку з модулем: показано дані на %(when)s.", when=self._td_local(self.last_reading_at)))
        else:
            parts.append(Markup('<p class="text-muted small mb-2">%s</p>') % _(
                'Знімок %(when)s · усе, що віддає контролер %(model)s через ретранслятор.',
                when=self._td_local(self.last_reading_at, '%d.%m.%Y %H:%M:%S'),
                model=self.controller_model_id.name or ''))
        cards = [self._td_card(title, addr, rows) for title, addr, rows in self._td_value_groups(values)]
        cards.append(self._td_signals_card(values))
        cards.append(self._td_relay_card())
        extra = {key: val for key, val in values.items() if key not in self.env['td.genset.reading'].READING_FIELD_MAP
                 and not key.endswith('_text')}
        if extra:
            rows = [('', escape(key), self._td_fmt_extra(val)) for key, val in sorted(extra.items())]
            cards.append(self._td_card(_('Інші значення'), _('нові ключі ретранслятора'), rows))
        grid = Markup('<div class="row g-3">%s</div>') % Markup('').join(
            Markup('<div class="col-12 col-lg-6 col-xxl-4">%s</div>') % card for card in cards)
        css = 'o_td_genset_current_data' + (' o_td_genset_stale' if self.link_state != 'online' else '')
        return Markup('<div class="%s">%s%s</div>') % (css, Markup('').join(parts), grid)

    # ------------------------------------------------------------------ форматування
    def _td_no_data(self, title=None):
        return Markup('<span class="badge text-bg-secondary fw-normal o_td_genset_no_data_badge" title="%s">%s</span>') % (
            title or _('null у знімку («###» на панелі) або значення ще не передається ретранслятором'),
            _('немає даних'))

    def _td_num(self, value, digits=0):
        return formatLang(self.env, value, digits=digits)

    def _td_fmt(self, values, keys, unit='', digits=0):
        """Значення ключів через « / » з одиницею; усі порожні — «немає даних»."""
        nums = [self._td_value(key, values) for key in keys]
        if all(num is None for num in nums):
            missing = all(key not in values for key in keys)
            return self._td_no_data(_("Ключа немає у знімку (з'явиться з версією ретранслятора 1.1.3).")
                                    if missing else None)
        text = ' / '.join('—' if num is None else self._td_num(num, digits) for num in nums)
        return escape('%s %s' % (text, unit) if unit else text)

    def _td_fmt_extra(self, value):
        if value is None:
            return self._td_no_data()
        if isinstance(value, bool):
            return escape(_('Так') if value else _('Ні'))
        return escape(str(value))

    def _td_sensor(self, values, key, addr):
        """Підрядок «датчик N Ом (03H addr)» для омів датчиків (ФВ-31, AC-68)."""
        ohm = self._td_value(key, values)
        if ohm is None:
            text = _('датчик: немає даних (03H %(addr)s)', addr=addr)
        else:
            text = _('датчик: %(ohm)s Ом (03H %(addr)s)', ohm=self._td_num(ohm, 1), addr=addr)
        return Markup('<div class="small text-muted o_td_genset_ohm">%s</div>') % text

    def _td_fuel_value(self, values):
        level = self._td_value('fuel_level', values)
        if level is None and self.fuel_source != 'ohm':
            main = self._td_no_data()
        else:
            pieces = []
            if level is not None:
                pieces.append('%s %%' % self._td_num(level, 0))
            pieces.append('%s L' % self._td_num(self.fuel_liters or 0.0, 1))
            main = escape(' · '.join(pieces))
        source = dict(FUEL_SOURCES).get(self.fuel_source)
        if source:
            main = Markup('%s <span class="badge text-bg-light border fw-normal ms-1" title="%s">%s</span>') % (
                main, _('Літри за калібруванням датчика (Ом → L) або за % контролера × об\'єм бака.'), source)
        return main + self._td_sensor(values, 'fuel_level_sensor_ohm', '0022')

    def _td_card(self, title, subtitle, rows):
        body = Markup('').join(
            Markup('<tr><td class="text-muted small font-monospace text-nowrap">%s</td><td>%s</td>'
                   '<td class="text-end">%s</td></tr>') % (addr, label, value)
            for addr, label, value in rows)
        return Markup('<div class="card h-100"><div class="card-header d-flex justify-content-between '
                      'align-items-baseline py-2"><span class="fw-bold">%s</span><small class="text-muted">%s</small>'
                      '</div><div class="table-responsive"><table class="table table-sm mb-0 align-middle"><tbody>'
                      '%s</tbody></table></div></div>') % (title, subtitle, body)

    def _td_value_groups(self, values):
        """Картки значень 03H (мокап «Поточні дані»): ``[(назва, підпис, [(адреса, підпис, значення)])]``."""
        fmt = self._td_fmt
        status = values.get('genset_status')
        if isinstance(status, int) and not isinstance(status, bool):
            status_text = escape('%s · %s' % (status, dict(GENSET_STATUS).get(str(status), '')))
        else:
            status_text = self._td_no_data()
        mains_status = self._td_value('mains_status', values)
        mains_status_text = (escape('%s · %s' % (int(mains_status), MAINS_STATUS_TEXT.get(int(mains_status), '')))
                             if mains_status is not None else self._td_no_data())
        remote = self._td_value('remote_start_status', values)
        remote_text = (escape('%s · %s' % (int(remote), REMOTE_START_TEXT.get(int(remote), '')))
                       if remote is not None else self._td_no_data())
        mode = values.get('controller_mode')
        mode_text = escape(dict(CONTROLLER_MODES).get(mode, _('Невідомо')) if mode else _('Невідомо'))
        mains_ok = values.get('mains_normal')
        mains_ok_text = (self._td_no_data() if mains_ok is None
                         else escape(_('Так') if mains_ok else _('Ні')))
        run_h, run_m = self._td_value('run_hours', values), self._td_value('run_minutes', values)
        run_text = (self._td_no_data() if run_h is None
                    else escape(_('%(h)s год %(m)s хв', h=int(run_h), m=int(run_m or 0))))
        maint_h, maint_m = self._td_value('maint_h', values), self._td_value('maint_min', values)
        maint_text = (self._td_no_data() if maint_h is None
                      else escape(_('%(h)s год %(m)s хв', h=int(maint_h), m=int(maint_m or 0))))
        temp = fmt(values, ('water_temp',), '°C') + self._td_sensor(values, 'water_temp_sensor_ohm', '0018')
        oil = fmt(values, ('oil_pressure',), 'kPa') + self._td_sensor(values, 'oil_pressure_sensor_ohm', '0020')
        sw, hw = values.get('controller_sw'), values.get('controller_hw')
        if sw is None and hw is None:
            versions = self._td_no_data(_('Версії контролера передаються з ретранслятора 1.1.3.'))
        else:
            versions = escape('%s / %s' % (sw if sw is not None else '—', hw if hw is not None else '—'))
        return [
            (_('Мережа'), '03H', [
                ('0000–0002', _('UA / UB / UC'), fmt(values, ('mains_ua', 'mains_ub', 'mains_uc'), 'V')),
                ('0003–0005', _('UAB / UBC / UCA'), fmt(values, ('mains_uab', 'mains_ubc', 'mains_uca'), 'V')),
                ('0006', _('Частота'), fmt(values, ('mains_freq',), 'Hz', 1)),
                ('01H 0065', _('Мережа в нормі'), mains_ok_text),
                ('0040', _('Стан мережі'), mains_status_text),
                ('0041', _('Відлік стану мережі'), fmt(values, ('mains_status_delay',), 'с')),
            ]),
            (_('Генератор'), '03H', [
                ('0007–0009', _('UA / UB / UC'), fmt(values, ('gen_ua', 'gen_ub', 'gen_uc'), 'V')),
                ('0010–0012', _('UAB / UBC / UCA'), fmt(values, ('gen_uab', 'gen_ubc', 'gen_uca'), 'V')),
                ('0013', _('Частота'), fmt(values, ('gen_freq',), 'Hz', 1)),
                ('0034', _('Стан агрегату'), status_text),
                ('0035', _('Відлік стану'), fmt(values, ('genset_status_delay',), 'с')),
            ]),
            (_('Навантаження'), '03H', [
                ('0014–0016', _('Струм A / B / C'), fmt(values, ('current_a', 'current_b', 'current_c'), 'A', 1)),
                ('0026', _('Активна потужність'), fmt(values, ('active_power',), 'kW', 1)),
                ('0052–0054', _('Активна по фазах A / B / C'), fmt(values, ('power_a', 'power_b', 'power_c'), 'kW', 1)),
                ('0027', _('Реактивна потужність'), fmt(values, ('reactive_power',), 'kvar', 1)),
                ('0028', _('Повна потужність'), fmt(values, ('apparent_power',), 'kVA', 1)),
                ('0029', _('cos φ'), fmt(values, ('power_factor',), '', 2)),
                ('0055', _('Завантаження'), fmt(values, ('load_pct',), '%')),
            ]),
            (_('Двигун'), '03H', [
                ('0023', _('Оберти'), fmt(values, ('speed',), _('об/хв'))),
                ('0017', _('Температура ОР'), temp),
                ('0019', _('Тиск оливи'), oil),
                ('0021', _('Рівень палива'), self._td_fuel_value(values)),
                ('0024', _('Напруга АКБ'), fmt(values, ('battery_v',), 'V', 1)),
                ('0025', _('Напруга D+ (зарядка)'), fmt(values, ('dplus_v',), 'V', 1)),
            ]),
            (_('Стан і таймери'), '03H', [
                ('01H 0040–0043', _('Режим контролера'), mode_text),
                ('0036', _('Дистанційний пуск'), remote_text),
                ('0037', _('Відлік дистанційного пуску'), fmt(values, ('remote_start_delay',), 'с')),
                ('0038', _('Стан ATS (код)'), fmt(values, ('ats_status',))),
                ('0039', _('Відлік ATS'), fmt(values, ('ats_status_delay',), 'с')),
            ]),
            (_('Лічильники і ТО'), '03H', [
                ('0042–0044', _('Мотогодини'), run_text),
                ('0046–0047', _('Кількість пусків'), fmt(values, ('start_count',))),
                ('0048–0049', _('Вироблено енергії'), fmt(values, ('energy_kwh',), 'kWh')),
                ('0030–0031', _('До ТО (контролер)'), maint_text),
            ]),
            (_('Контролер'), '03H', [
                ('', _('Модель'), escape(self.controller_model_id.name or '—')),
                ('0050 / 0051', _('Версія ПЗ / апаратна'), versions),
            ]),
        ]

    def _td_signals_card(self, values):
        reading_fields = self.env['td.genset.reading']._fields
        titles = {
            'state': _('Режим і стан'), 'crit': _('Аварійні зупинки'), 'warn': _('Попередження'),
            'mains': _('Мережа'), 'gen': _('Генератор'), 'io': _('Входи і виходи'),
        }
        status = values.get('genset_status')
        running = isinstance(status, int) and status not in (0, 15) or bool(self._td_value('speed', values))

        def active_css(kind, key):
            if kind == 'crit' or key in ('common_alarm', 'common_shutdown'):
                return 'text-bg-danger'
            if kind == 'warn' or key in ('common_warning', 'remote_lock', 'scheduled_not_run'):
                return 'text-bg-warning'
            if key in ('mains_normal', 'gen_normal'):
                return 'text-bg-success'
            if kind == 'mains':
                return 'text-bg-danger'
            if kind == 'gen':
                # недонапруга/низька частота зупиненого генератора — норма, не аварія (SPEC 4)
                return 'text-bg-warning' if running else 'text-bg-secondary'
            return 'text-bg-info' if kind == 'state' else 'text-bg-success'

        blocks = []
        for kind, items in SIGNAL_GROUPS:
            chips = []
            active_count = 0
            for key, addr in items:
                label = reading_fields[key]._description_string(self.env) if key in reading_fields else key
                for prefix in SIGNAL_PREFIXES:
                    if label.startswith(prefix):
                        label = label[len(prefix):]
                        label = label[:1].upper() + label[1:]
                value = values.get(key)
                if value is True:
                    active_count += 1
                    css = active_css(kind, key)
                elif value is None:
                    css = 'border text-body-secondary fw-normal opacity-50'
                else:
                    css = 'border text-body-secondary fw-normal'
                title = _('Сигнал 01H, адреса %(addr)s', addr='%04d' % addr)
                if value is None:
                    title = '%s · %s' % (title, _('немає даних'))
                chips.append(Markup('<span class="badge %s me-1 mb-1" title="%s">%s <span class="opacity-75 '
                                    'font-monospace">%s</span></span>') % (css, title, label, '%04d' % addr))
            blocks.append(Markup('<div class="mb-2"><div class="small fw-bold mb-1">%s <span class="text-muted '
                                 'fw-normal">· %s</span></div>%s</div>') % (
                titles[kind], _('%(on)s з %(all)s активні', on=active_count, all=len(items)), Markup('').join(chips)))
        return Markup('<div class="card h-100"><div class="card-header d-flex justify-content-between '
                      'align-items-baseline py-2"><span class="fw-bold">%s</span><small class="text-muted">01H</small>'
                      '</div><div class="card-body py-2">%s</div></div>') % (_('Сигнали'), Markup('').join(blocks))

    def _td_relay_card(self):
        yes, no = _('Так'), _('Ні')

        def yes_no(flag):
            return escape(yes if flag else no)

        rows = [
            ('', _('ID модуля (hostid)'), escape(self.relay_hostid or '—')),
            ('', _('Модуль онлайн'), yes_no(self.relay_online)),
            ('', _('Модуль бачили, с тому'), escape(self._td_num(self.relay_seconds_since_seen or 0))),
            ('', _("Довге з'єднання"), yes_no(self.relay_long_connection)),
            ('', _('Команди дозволено на ретрансляторі'), yes_no(self.relay_commands_enabled)),
            ('', _('Готовий до команд'), yes_no(self.relay_commands_ready)),
            ('', _('Версія ретранслятора'), escape(self.relay_version or '—')),
            ('', _('Регістрів / сигналів в образі'), escape('%s / %s' % (self.relay_registers_known or 0,
                                                                         self.relay_coils_known or 0))),
            ('', _('Інтервал знімків, с'), escape(self._td_num(self.relay_snapshot_sec or 0))),
            ('', _('Час ретранслятора'), escape(self._td_local(self.relay_time_utc, '%d.%m.%Y %H:%M:%S') or '—')),
            ('', _("Зв'язок змінився"), escape(self._td_local(self.link_changed_at, '%d.%m.%Y %H:%M') or '—')),
        ]
        return self._td_card(_('Ретранслятор'), '/status', rows)

    # ================================================================== KPI «Аналітики» (2.10)
    def _compute_kpi(self):
        """KPI вкладки «Аналітика» за 7 і 30 днів (``_read_group`` по подіях ``run``/``outage`` і знімках, 2.10):
        мотогодини, пуски, вироблено, відключення, покрито генератором (% знімків без мережі з живленням від
        генератора), середнє навантаження під час роботи, пуск з 1-ї спроби, мінімум АКБ при прокрутці.
        """
        for genset in self:
            for name in KPI_FIELDS:
                genset[name] = 0
        gensets = self.filtered('id')
        if not gensets:
            return
        now = fields.Datetime.now()
        Event = self.env['td.genset.event'].sudo()
        Reading = self.env['td.genset.reading'].sudo()
        for days in (7, 30):
            since = now - timedelta(days=days)
            base = [('genset_id', 'in', gensets.ids), ('date_start', '>=', since)]
            stats = {(genset, kind): (count, duration, energy) for genset, kind, count, duration, energy in
                     Event._read_group(base + [('event_type', 'in', ('run', 'outage'))], ['genset_id', 'event_type'],
                                       ['__count', 'duration:sum', 'energy_kwh:sum'])}
            open_runs = Event.search(base + [('event_type', '=', 'run'), ('date_end', '=', False)])
            first_try = dict(Event._read_group(base + [('event_type', '=', 'run'), ('crank_attempts', '=', 1)],
                                               ['genset_id'], ['__count']))
            cranks = {genset: (count, min_v) for genset, count, min_v in Event._read_group(
                base + [('event_type', '=', 'run'), ('crank_attempts', '>', 0)], ['genset_id'],
                ['__count', 'crank_min_battery_v:min'])}
            reading_base = [('genset_id', 'in', gensets.ids), ('ts', '>=', since)]
            no_mains = {}
            for genset, feed, count in Reading._read_group(reading_base + [('mains_ok', '=', False)],
                                                           ['genset_id', 'feed_source'], ['__count']):
                total, covered = no_mains.get(genset, (0, 0))
                no_mains[genset] = (total + count, covered + (count if feed == 'genset' else 0))
            load = dict(Reading._read_group(reading_base + [('is_running', '=', True)], ['genset_id'],
                                            ['load_pct:avg']))
            suffix = '_%dd' % days
            for genset in gensets:
                run_count, run_hours, energy = stats.get((genset, 'run'), (0, 0.0, 0.0))
                run_hours = (run_hours or 0.0) + sum(
                    (now - event.date_start).total_seconds() / 3600.0
                    for event in open_runs if event.genset_id == genset and event.date_start)
                outages = stats.get((genset, 'outage'), (0, 0.0, 0.0))[0]
                total, covered = no_mains.get(genset, (0, 0))
                crank_count, crank_min = cranks.get(genset, (0, 0.0))
                genset['kpi_run_hours' + suffix] = round(run_hours, 2)
                genset['kpi_starts' + suffix] = run_count
                genset['kpi_energy_kwh' + suffix] = round(energy or 0.0, 1)
                genset['kpi_outages' + suffix] = outages
                genset['kpi_covered_pct' + suffix] = round(covered * 100.0 / total, 1) if total else 0.0
                genset['kpi_avg_load_pct' + suffix] = round(load.get(genset) or 0.0, 1)
                genset['kpi_first_try_pct' + suffix] = (round(first_try.get(genset, 0) * 100.0 / crank_count, 1)
                                                        if crank_count else 0.0)
                genset['kpi_crank_battery_min' + suffix] = round(crank_min or 0.0, 1)

    # ================================================================== кнопки картки (дії з інших файлів)
    def action_open_canisters(self):
        """Smart-кнопка «У каністрах»: каністри (kanban), дія ``action_td_genset_canister``."""
        self.ensure_one()
        return self.env['ir.actions.act_window']._for_xml_id('td_genset.action_td_genset_canister')

    def action_open_escalation(self):
        """Посилання «Отримувачі тривог» → налаштування модуля (ланцюжок ескалації)."""
        self.ensure_one()
        return self.env['ir.actions.act_window']._for_xml_id('td_genset.action_td_genset_config')

    def action_open_analytics(self):
        """Кнопки вкладки «Аналітика»: дія з ``context['td_analytics']`` з фільтром за цим генератором (2.10)."""
        self.ensure_one()
        key = self.env.context.get('td_analytics')
        xmlid = ANALYTICS_ACTIONS.get(key, ANALYTICS_ACTIONS['run_outage'])
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['context'] = {'search_default_genset_id': self.id, 'search_default_last_30_days': 1}
        return action

    def action_open_last_run_load(self):
        """«Навантаження під час останньої роботи»: знімки між ``reading_start_id`` і ``reading_end_id``
        (або ``date_start``/``date_end``) останньої події «Робота генератора» (2.10)."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('td_genset.action_td_genset_analytics_last_run')
        event = self.env['td.genset.event'].search([('genset_id', '=', self.id), ('event_type', '=', 'run')],
                                                   order='date_start desc, id desc', limit=1)
        if not event:
            action['domain'] = [('id', '=', 0)]
            return action
        start = event.reading_start_id.ts or event.date_start
        end = event.reading_end_id.ts or event.date_end or fields.Datetime.now()
        action['domain'] = [('genset_id', '=', self.id), ('ts', '>=', start), ('ts', '<=', end)]
        action['context'] = {'search_default_genset_id': self.id}
        action['name'] = _('Навантаження під час останньої роботи (%(start)s – %(end)s)',
                           start=self._td_local(start), end=self._td_local(end))
        return action
