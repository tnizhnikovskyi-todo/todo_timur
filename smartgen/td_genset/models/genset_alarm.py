# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас (поля, заглушки): W0.
"""Тривога ``td.genset.alarm`` — ТР 2.3.4, 2.8.2–2.8.5; SPEC 5.4, 9.

Карта сигналів 01H → тривоги (2.8.3) і правила стану (датчики без даних, низький рівень палива) — тут;
події «Тривога контролера» відкриває/закриває обробник подій (``genset_event.py``), він же кличе
``_raise``/``_clear`` для фронтів сигналів поза догоном.
"""
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import SQL
from odoo.tools.translate import LazyTranslate

from .genset_reading import utc_to_kyiv

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)

# ---------------------------------------------------------------------------- карта сигналів 2.8.3
# Назви сигналів — за мокапом (FLAGS); у назві тривоги — з малої літери («Аварійна зупинка: низький рівень палива»).
SHUTDOWN_SIGNALS = {
    'emergency_stop': _lt('Аварійний стоп'),
    'overspeed_shutdown': _lt('Перевищення обертів'),
    'underspeed_shutdown': _lt('Занижені оберти'),
    'speed_signal_loss_shutdown': _lt('Втрата сигналу обертів'),
    'overfrequency_shutdown': _lt('Висока частота'),
    'underfrequency_shutdown': _lt('Низька частота'),
    'overvoltage_shutdown': _lt('Висока напруга'),
    'undervoltage_shutdown': _lt('Низька напруга'),
    'gen_overcurrent_shutdown': _lt('Перевантаження за струмом'),
    'crank_failure': _lt('Невдалий пуск'),
    'high_temp_shutdown': _lt('Висока температура ОР'),
    'low_oil_pressure_shutdown': _lt('Низький тиск оливи'),
    'frequency_loss_alarm': _lt('Втрата частоти'),
    'input_shutdown': _lt('Аварійний вхід'),
    'low_fuel_shutdown': _lt('Низький рівень палива'),
    'low_coolant_shutdown': _lt('Низький рівень ОР'),
    'temp_sensor_open_shutdown': _lt('Обрив датчика температури'),
    'oil_pressure_sensor_open_shutdown': _lt('Обрив датчика тиску'),
    'maintenance_due_shutdown': _lt('Прострочене ТО'),
    'overpower_shutdown': _lt('Перевантаження за потужністю'),
}
WARNING_SIGNALS = {
    'high_temp_warning': _lt('Висока температура ОР'),
    'low_oil_pressure_warning': _lt('Низький тиск оливи'),
    'gen_overcurrent_warning': _lt('Перевантаження за струмом'),
    'low_fuel_warning': _lt('Низький рівень палива'),
    'charging_failure_warning': _lt('Немає заряду D+'),
    'battery_undervoltage_warning': _lt('Низька напруга АКБ'),
    'battery_overvoltage_warning': _lt('Висока напруга АКБ'),
    'input_warning': _lt('Вхід попередження'),
    'speed_signal_loss_warning': _lt('Втрата сигналу обертів'),
    'low_coolant_warning': _lt('Низький рівень ОР'),
    'temp_sensor_open_warning': _lt('Обрив датчика температури'),
    'oil_pressure_sensor_open_warning': _lt('Обрив датчика тиску'),
    'maintenance_due_warning': _lt('Термін ТО'),
    'charger_fail_warning': _lt('Збій зарядного пристрою'),
    'overpower_warning': _lt('Перевантаження за потужністю'),
}
# Сигнали генератора (2.8.3; назва — як в AC-07 «Низька напруга генератора»)
GEN_SIGNALS = {
    'gen_overvoltage': _lt('Висока напруга генератора'),
    'gen_undervoltage': _lt('Низька напруга генератора'),
    'gen_overfrequency': _lt('Висока частота генератора'),
    'gen_underfrequency': _lt('Низька частота генератора'),
    'gen_overcurrent': _lt('Перевантаження генератора за струмом'),
}
GEN_RUNNING_ONLY = ('gen_undervoltage', 'gen_underfrequency')
# Коди тривог із сигналів контролера (події «Тривога контролера» + _raise/_clear за фронтами)
SIGNAL_CODES = frozenset(set(SHUTDOWN_SIGNALS) | set(WARNING_SIGNALS) | set(GEN_SIGNALS)
                         | {'common_shutdown', 'common_warning', 'stop_failure', 'remote_lock'})
# Датчики без даних (null у values) → «Немає даних з датчика …» (2.8.3)
SENSOR_RULES = {
    'oil_pressure': _lt('тиску оливи'),
    'water_temp': _lt('температури ОР'),
    'fuel_level': _lt('рівня палива'),
}
STATE_CODES = frozenset({'sensor_%s' % key for key in SENSOR_RULES} | {'low_fuel'})
LOW_FUEL_CODES = ('low_fuel', 'low_fuel_warning')

ALARM_LEVELS = [
    ('crit', 'Критична'),
    ('warn', 'Попередження'),
    ('info', 'Інформація'),
]
ALARM_STATES = [
    ('active', 'Активна'),
    ('acked', 'Прийнято'),
    ('cleared', 'Знято'),
]


class TdGensetAlarm(models.Model):
    _name = 'td.genset.alarm'
    _description = 'Генератори: тривога'
    _inherit = ['mail.thread']
    _order = 'date_raised desc, id desc'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, index=True, ondelete='cascade',
        help='Генератор, якого стосується тривога.')
    code = fields.Char(
        string='Код', index=True,
        help='Ключ правила (link_lost, cmd_unconfirmed, low_oil_pressure_warning, drain, maintenance_due, …). '
             'Активна тривога з тим самим кодом на генераторі не дублюється.')
    level = fields.Selection(
        ALARM_LEVELS, string='Рівень',
        help='Критична / Попередження / Інформація — визначає правило сповіщення (Налаштування → Сповіщення).')
    name = fields.Char(
        string='Заголовок',
        help='Короткий текст тривоги.')
    description = fields.Text(
        string='Опис',
        help='Подробиці: що сталося і що перевірити.')
    state = fields.Selection(
        ALARM_STATES, string='Стан', default='active', index=True, tracking=True,
        help='Активна → Прийнято (умова ще триває, ескалацію зупинено) → Знято.')
    date_raised = fields.Datetime(
        string='Виникла', default=fields.Datetime.now,
        help='Коли виникла тривога.')
    date_acked = fields.Datetime(
        string='Прийнято о',
        help='Коли тривогу прийняли кнопкою «Прийняв».')
    date_cleared = fields.Datetime(
        string='Знято о',
        help='Коли умова тривоги зникла.')
    acked_user_id = fields.Many2one(
        'res.users', string='Прийняв', ondelete='set null',
        help='Хто прийняв тривогу.')
    escalation_level = fields.Integer(
        string='Рівень ескалації', default=0,
        help='Скільки рівнів ланцюжка вже сповіщено.')
    next_escalation_at = fields.Datetime(
        string='Наступна ескалація', index=True,
        help='Коли сповістити наступний рівень; порожньо — ескалацію завершено.')
    notified_user_ids = fields.Many2many(
        'res.users', 'td_genset_alarm_notified_user_rel', 'alarm_id', 'user_id', string='Сповіщено',
        help='Кого вже сповіщено про тривогу.')
    source_ref = fields.Reference(
        [('td.genset.command', 'Команда'), ('td.genset.event', 'Подія'), ('maintenance.request', 'Заявка ТО')],
        string='Джерело',
        help='Запис, з яким пов\'язана тривога (команда, подія, заявка ТО).')
    can_ack = fields.Boolean(
        string='Можу прийняти', compute='_compute_can_ack',
        help='Поточний користувач — учасник ланцюжка ескалації або тех. адміністратор.')
    tech_only = fields.Boolean(
        string='Тех. тривога', readonly=True,
        help='Тривога про ретранслятор/код: адресується всім тех. адміністраторам (а не ланцюжку), '
             'правило сповіщення — як для попереджень (ТР 2.8.4).')

    @api.constrains('genset_id', 'code', 'state')
    def _check_unique_active_code(self):
        """Одна незнята тривога на ``(genset, code)`` (А.4: перевірка в ``_raise`` + цей constrains)."""
        for alarm in self:
            if not alarm.code or alarm.state == 'cleared':
                continue
            duplicates = self.search_count([
                ('id', '!=', alarm.id),
                ('genset_id', '=', alarm.genset_id.id),
                ('code', '=', alarm.code),
                ('state', '!=', 'cleared'),
            ])
            if duplicates:
                raise ValidationError(_('На генераторі вже є незнята тривога «%(code)s».', code=alarm.code))

    @api.depends_context('uid')
    def _compute_can_ack(self):
        for alarm in self:
            alarm.can_ack = alarm._can_ack(self.env.user)

    # ------------------------------------------------------------------ правила (2.8.3)
    @api.model
    def _td_signal_state(self, row):
        """Активні тривоги із сигналів контролера за знімком (2.8.3).

        :param dict row: значення знімка з NULL (``None`` — немає даних), див. ``td.genset.event._td_rows``.
        :return: ``(active, unknown)``: ``{code: (level, name, description)}`` і множина кодів без даних.
        """
        active, unknown = {}, set()
        specific_shutdown = False
        for key, lazy_label in SHUTDOWN_SIGNALS.items():
            value = row.get(key)
            if value is None:
                unknown.add(key)
            elif value:
                specific_shutdown = True
                label = self.env._(lazy_label)
                active[key] = ('crit', _('Аварійна зупинка: %s', lower_first(label)),
                               _("Контролер зупинив генератор: %s. Перевірте генератор на об'єкті.", label))
        common = row.get('common_shutdown')
        if common is None:
            unknown.add('common_shutdown')
        elif common and not specific_shutdown:
            active['common_shutdown'] = ('crit', _('Аварійна зупинка'),
                                         _('Контролер повідомляє загальну аварійну зупинку (01H 0002).'))
        stop_failure, status = row.get('stop_failure_warning'), row.get('genset_status')
        if stop_failure is None and status is None:
            unknown.add('stop_failure')
        elif stop_failure or status == '14':
            active['stop_failure'] = ('crit', _('Невдала зупинка'),
                                      _('Генератор не зупинився: стан 14 «Невдала зупинка» або сигнал 01H 0027.'))
        specific_warning = bool(stop_failure)
        for key, lazy_label in WARNING_SIGNALS.items():
            value = row.get(key)
            if value is None:
                unknown.add(key)
            elif value:
                specific_warning = True
                label = self.env._(lazy_label)
                active[key] = ('warn', _('Попередження: %s', lower_first(label)),
                               _('Попередження контролера: %s.', label))
        common = row.get('common_warning')
        if common is None:
            unknown.add('common_warning')
        elif common and not specific_warning:
            active['common_warning'] = ('warn', _('Попередження контролера'),
                                        _('Контролер повідомляє загальне попередження (01H 0001).'))
        lock = row.get('remote_lock')
        if lock is None:
            unknown.add('remote_lock')
        elif lock:
            active['remote_lock'] = ('warn', _('Дистанційне керування заблоковано на контролері'),
                                     _('На панелі контролера ввімкнено блокування дистанційного керування '
                                       '(01H 0004) — команди з Odoo не виконуються.'))
        at_run = row.get('genset_status') in ('8', '9') if row.get('genset_status') is not None else None
        for key, lazy_label in GEN_SIGNALS.items():
            value = row.get(key)
            if key in GEN_RUNNING_ONLY and value:
                # норма зупиненого (1.2): лише коли агрегат на етапі «Робота» (стан 8–9)
                value = at_run
            if value is None:
                unknown.add(key)
            elif value:
                label = self.env._(lazy_label)
                active[key] = ('warn', label, _('Сигнал контролера: %s.', label))
        return active, unknown

    @api.model
    def _td_state_alarms(self, genset, row, values):
        """Правила стану (2.8.3): датчик без даних (``null`` у ``values``), низький рівень палива.

        :return: ``(active, hold)`` — активні ``{code: (level, name, description)}`` і коди, які не знімати
            (немає даних або рівень у смузі гістерезису).
        """
        active, hold = {}, set()
        values = values if isinstance(values, dict) else {}
        for key, lazy_label in SENSOR_RULES.items():
            if key in values and values[key] is None:
                label = self.env._(lazy_label)
                active['sensor_%s' % key] = (
                    'warn', _('Немає даних з датчика %s', label),
                    _('Контролер повідомляє «немає даних» (32766) для датчика %s — можливий обрив датчика.', label))
        liters = row.get('fuel_liters') if row else None
        config = self.env['td.genset.config'].get()
        tank, pct = genset.tank_volume_l or 0.0, config.low_fuel_pct or 0
        if liters is None:
            hold.add('low_fuel')
        elif tank and pct:
            threshold = tank * pct / 100.0
            if liters < threshold:
                active['low_fuel'] = (
                    'warn', _('Низький рівень палива: %s L', fmt_liters(liters)),
                    _('Паливо в баку %(liters)s L — нижче %(pct)s %% бака (%(threshold)s L). Долийте паливо.',
                      liters=fmt_liters(liters), pct=pct, threshold=fmt_liters(threshold)))
            elif liters < threshold + max(tank * 0.02, 1.0):
                hold.add('low_fuel')
        return active, hold

    @api.model
    def _td_apply_state_alarms(self, genset, row, values):
        """Підняти/зняти тривоги правил стану за знімком (поза догоном)."""
        active, hold = self._td_state_alarms(genset, row, values)
        for code, (level, name, description) in active.items():
            self._raise(genset, code, level, name, description)
        opened = self.sudo().search([('genset_id', '=', genset.id), ('code', 'in', list(STATE_CODES)),
                                     ('state', '!=', 'cleared')])
        for code in set(opened.mapped('code')) - set(active) - hold:
            self._clear(genset, code)

    # ------------------------------------------------------------------ життєвий цикл (2.8.2)
    @api.model
    def _raise(self, genset, code, level, name, description='', source=None, tech=False):
        """Підняти тривогу: без дубля незнятої на ``(genset, code)``; ``state='active'``,
        ``next_escalation_at=now``; чатер ``mt_alarm``; ``tech=True`` → адресати — ``group_tech``;
        ``_notify_bus('alarm')``. Низький рівень палива — ще й активність «Долити паливо» (AC-63).

        Права перевіряє викликач (тривога — технічний запис, створюється через ``sudo()``).

        :return: запис ``td.genset.alarm`` (наявний або новий).
        """
        genset = genset.sudo()
        existing = self.sudo().search([('genset_id', '=', genset.id), ('code', '=', code),
                                       ('state', '!=', 'cleared')], limit=1)
        if existing:
            return existing
        now = fields.Datetime.now()
        vals = {
            'genset_id': genset.id,
            'code': code,
            'level': level if level in dict(ALARM_LEVELS) else 'warn',
            'name': name,
            'description': description or False,
            'state': 'active',
            'date_raised': now,
            'escalation_level': 0,
            'next_escalation_at': now,
            'tech_only': bool(tech),
        }
        if source:
            vals['source_ref'] = source if isinstance(source, str) else '%s,%s' % (source._name, source.id)
        alarm = self.sudo().create(vals)
        level_label = dict(self._fields['level']._description_selection(self.env)).get(alarm.level, '')
        body = Markup('<p><b>%s</b> · %s</p>') % (level_label, name)
        if description:
            body += Markup('<p>%s</p>') % description
        genset.message_post(body=body, subtype_xmlid='td_genset.mt_alarm')
        if code in LOW_FUEL_CODES:
            alarm._td_schedule_refuel_activity()
        genset._notify_bus('alarm', {'alarm_id': alarm.id, 'state': 'active', 'note': name})
        return alarm

    @api.model
    def _clear(self, genset, code, note=''):
        """Зняти тривогу: ``state='cleared'``, ``date_cleared``, ``next_escalation_at=NULL``, чатер «… — знято»,
        ``_notify_bus('alarm')``."""
        genset = genset.sudo()
        alarms = self.sudo().search([('genset_id', '=', genset.id), ('code', '=', code), ('state', '!=', 'cleared')])
        if not alarms:
            return None
        now = fields.Datetime.now()
        alarms.write({'state': 'cleared', 'date_cleared': now, 'next_escalation_at': False})
        for alarm in alarms:
            text = _('Тривога «%(name)s» — знято о %(time)s.', name=alarm.name, time=hhmm(now))
            if note:
                text = '%s %s' % (text, note)
            genset.message_post(body=Markup('<p>%s</p>') % text, subtype_xmlid='td_genset.mt_alarm')
            genset._notify_bus('alarm', {'alarm_id': alarm.id, 'state': 'cleared', 'note': alarm.name})
        return None

    def _td_schedule_refuel_activity(self):
        """Активність «Долити паливо» відповідальному за генератор (одна відкрита на генератор, AC-63)."""
        activity_type = self.env.ref('td_genset.activity_refuel', raise_if_not_found=False)
        for alarm in self.sudo():
            genset = alarm.genset_id
            if not activity_type or genset.activity_ids.filtered(lambda act: act.activity_type_id == activity_type):
                continue
            config = self.env['td.genset.config'].sudo().get()
            user = genset.user_id or config.level_ids.sorted(lambda level: (level.sequence, level.id)).user_id[:1]
            genset.activity_schedule(
                'td_genset.activity_refuel', user_id=(user or self.env.user).id,
                summary=_('Долити паливо'), note=alarm.name)

    def _can_ack(self, user):
        """Учасник ланцюжка ескалації (``config.level_ids.user_id``) або ``group_tech`` (ФВ-30, AC-43)."""
        if not user:
            return False
        if user.has_group('td_genset.group_tech'):
            return True
        config = self.env['td.genset.config'].sudo().get()
        return user in config.level_ids.user_id

    def action_ack(self):
        """Кнопка «Прийняв»: перевірка ``_can_ack`` (інакше ``AccessError`` «Прийняти тривогу може учасник
        ланцюжка ескалації або тех. адміністратор.»); ``state='acked'``, зупинка ескалації, чатер (AC-43)."""
        user = self.env.user
        if not self._can_ack(user):
            raise AccessError(_('Прийняти тривогу може учасник ланцюжка ескалації або тех. адміністратор.'))
        now = fields.Datetime.now()
        for alarm in self.sudo().filtered(lambda item: item.state == 'active'):
            alarm.write({'state': 'acked', 'acked_user_id': user.id, 'date_acked': now, 'next_escalation_at': False})
            alarm.genset_id.message_post(
                body=Markup('<p>%s</p>') % _('Прийняв тривогу «%s». Ескалацію зупинено.', alarm.name),
                author_id=user.partner_id.id, subtype_xmlid='td_genset.mt_alarm')
            alarm.genset_id._notify_bus('alarm', {'alarm_id': alarm.id, 'state': 'acked', 'note': alarm.name})
        return True

    # ------------------------------------------------------------------ ескалація (2.8.2)
    @api.model
    def _cron_escalate(self):
        """Ескалація 2.8.2 (кличе ``cron_scheduler``): для ``state='active'`` і ``next_escalation_at <= now`` —
        наступний рівень ланцюжка (або всі тех. адміністратори для тех. тривог), правила ``notify_*``,
        тихі години (``config._quiet_now()``/``_quiet_end()``), ``message_notify`` (вхідні + push).
        Рядки блокуються ``FOR NO KEY UPDATE SKIP LOCKED``; винятки перехоплюються."""
        now = fields.Datetime.now()
        self.flush_model(['state', 'next_escalation_at'])
        self.env.cr.execute(SQL("""
            SELECT id FROM td_genset_alarm
             WHERE state = 'active' AND next_escalation_at <= %s
             ORDER BY next_escalation_at, id
               FOR NO KEY UPDATE SKIP LOCKED
        """, now))
        alarms = self.sudo().browse([row[0] for row in self.env.cr.fetchall()])
        config = self.env['td.genset.config'].sudo().get()
        for alarm in alarms:
            try:
                with self.env.cr.savepoint():
                    alarm._td_escalate_step(config, now)
            except Exception as exc:  # noqa: BLE001 — cron не має падати (А.7)
                _logger.warning('td_genset: ескалація тривоги %s не вдалася: %s', alarm.id, exc)
        return None

    def _td_escalate_step(self, config, now):
        """Один крок ескалації для однієї тривоги (див. ``_cron_escalate``)."""
        self.ensure_one()
        rule = config['notify_%s' % (self.level or 'warn')] or 'always'
        if self.tech_only:
            rule = config.notify_warn or 'not_quiet'
        if rule == 'chatter':
            self.next_escalation_at = False
            return
        if rule == 'not_quiet' and config._quiet_now(now):
            self.next_escalation_at = config._quiet_end(now) or False
            return
        if self.tech_only:
            group = self.env.ref('td_genset.group_tech')
            users = group.users.filtered(lambda user: user.active and not user.share)
            self._td_notify(users, _('Тех. адміністратори'))
            self.write({'escalation_level': 1, 'next_escalation_at': False,
                        'notified_user_ids': [(4, user.id) for user in users]})
            return
        levels = config.level_ids.sorted(lambda level: (level.sequence, level.id))
        index = self.escalation_level
        if index >= len(levels):
            self.next_escalation_at = False
            return
        level = levels[index]
        vals = {'escalation_level': index + 1}
        if level.user_id:
            self._td_notify(level.user_id, level.name)
            vals['notified_user_ids'] = [(4, level.user_id.id)]
        else:
            _logger.warning('td_genset: рівень ескалації «%s» без користувача — пропущено', level.name)
        if index + 1 < len(levels):
            scheduled = self.next_escalation_at or now
            delay = max(0, levels[index + 1].delay_min - level.delay_min)
            vals['next_escalation_at'] = scheduled + timedelta(minutes=delay)
        else:
            vals['next_escalation_at'] = False
        self.write(vals)

    def _td_notify(self, users, level_name):
        """Сповіщення (вхідні Odoo + push у мобільний застосунок) користувачам рівня ланцюжка."""
        self.ensure_one()
        partners = users.mapped('partner_id')
        if not partners:
            return
        level_label = dict(self._fields['level']._description_selection(self.env)).get(self.level, '')
        body = Markup('<p><b>%s</b> · %s</p>') % (level_label, self.name)
        if self.description:
            body += Markup('<p>%s</p>') % self.description
        body += Markup('<p>%s</p>') % _('Генератор: %(genset)s · рівень ланцюжка: %(level)s',
                                        genset=self.genset_id.name, level=level_name)
        self.genset_id.sudo().message_notify(
            partner_ids=partners.ids, subject=self.name, body=body, subtype_xmlid='td_genset.mt_alarm')

    # ------------------------------------------------------------------ після догону (А.7)
    @api.model
    def _evaluate_current(self, genset):
        """Одноразова оцінка всіх правил тривог за останнім знімком після догону (А.7): сигнали контролера
        (події «Тривога контролера» + тривоги), датчики без даних, низький рівень палива; тривоги сигналів,
        умова яких минула під час простою, знімаються."""
        genset = genset.sudo()
        reading = genset.last_reading_id
        if not reading:
            return None
        event_model = self.env['td.genset.event']
        row = event_model._td_rows(reading)[0]
        codes = dict(genset.open_alarm_codes or {})
        event_model._td_sync_signal_codes(genset, row, codes, raise_alarms=True)
        genset.open_alarm_codes = codes
        active, unknown = self._td_signal_state(row)
        stale = self.search([('genset_id', '=', genset.id), ('code', 'in', list(SIGNAL_CODES)),
                             ('state', '!=', 'cleared')])
        for code in set(stale.mapped('code')) - set(active) - unknown:
            self._clear(genset, code)
        self._td_apply_state_alarms(genset, row, genset.last_values_json)
        return None


# --------------------------------------------------------------------------- допоміжні функції
def lower_first(label):
    """Назва сигналу з малої літери для «Аварійна зупинка: низький рівень палива»."""
    text = str(label)
    return text[:1].lower() + text[1:]


def hhmm(value):
    """Naive UTC → «HH:MM» за Europe/Kyiv."""
    return utc_to_kyiv(value).strftime('%H:%M') if value else ''


def fmt_liters(value):
    """Літри для текстів: ціле, якщо дробової частини немає, інакше з однією цифрою після коми."""
    value = round(float(value or 0.0), 1)
    return ('%d' % value) if value == int(value) else ('%.1f' % value).replace('.', ',')
