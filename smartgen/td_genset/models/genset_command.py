# Part of td_genset (ToDo). Власник файлу: W2 «Керування». Каркас (поля): W0.
"""Команда ``td.genset.command`` — стан-машина ТР 2.6.3, А.5; SPEC 5.5, 9.

Створення команди — лише через ``_enqueue`` / ``_enqueue_batch`` (майстер, таймер, тест, планувальник).
Крок cron ``_cron_process_commands`` бере команди з ``next_attempt_at ≤ зараз`` (з допуском у пів кроку cron,
щоб хвилинний ритм не «з'їжджав»), блокує рядки ``FOR NO KEY UPDATE SKIP LOCKED`` і просуває кожну ``_step()``:
перевірки ``_precheck`` → ``POST /commands`` → опитування ``/commands/<id>`` → підтвердження за знімком
(``_check_confirmation``: лише знімок з ``ts ≥ done_utc``; ``done`` ретранслятора ≠ режим змінився).
Два рівні повторів: транспортний (409 / 5xx / таймаут / немає зв'язку — щохвилини) і повтор підтвердження
(кожні ``retry_every_min`` протягом ``retry_window_min``); далі — тривога і політика пропущеного переходу.
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.tools import SQL

from .genset_schedule import kyiv_hhmm
from .relay_client import (RelayAuthError, RelayBadRequest, RelayBusy, RelayCommandsDisabled, RelayError,
                           RelayNotFound, RelayUnavailable)

_logger = logging.getLogger(__name__)

COMMANDS = [
    ('auto', 'Авто'),
    ('manual', 'Ручний'),
    ('start', 'Пуск'),
    ('stop', 'Стоп'),
    ('test', 'Тест'),
    ('gen_close_open', 'Автомат генератора'),
    ('mains_close_open', 'Автомат мережі'),
]
COMMAND_SOURCES = [
    ('button', 'Кнопка'),
    ('schedule', 'Розклад'),
    ('timer', 'Таймер'),
    ('test', 'Тест'),
    ('exception', 'День-виняток'),
    ('system', 'Система'),
    ('retry', 'Повтор'),
]
COMMAND_STATES = [
    ('queued_odoo', 'У черзі Odoo'),
    ('to_send', 'До надсилання'),
    ('sent', 'Надіслано'),
    ('awaiting', 'Очікує підтвердження'),
    ('retry', 'Повтор'),
    ('done', 'Підтверджено'),
    ('done_late', 'Підтверджено після відновлення зв\'язку'),
    ('not_needed', 'Не потрібно'),
    ('skipped', 'Пропущено'),
    ('waiting_link', "Очікує: немає зв'язку"),
    ('failed', 'Не підтверджено — тривога'),
    ('blocked', 'Не надіслано: блокування'),
    ('disabled_relay', 'Керування вимкнено на ретрансляторі'),
    ('disabled_odoo', 'Не надіслано: команди вимкнено в Odoo'),
    ('auth_error', 'Помилка доступу'),
    ('cancelled', 'Скасовано'),
]
RELAY_STATUSES = [
    ('queued', 'У черзі'),
    ('sent', 'Надіслано'),
    ('done', 'Виконано'),
    ('failed', 'Помилка'),
    ('timeout', 'Таймаут'),
]
# Інваріанти А.5
OPEN_STATES = ('queued_odoo', 'to_send', 'sent', 'awaiting', 'retry', 'waiting_link')
INFLIGHT_STATES = ('sent', 'awaiting', 'retry')
FINAL_STATES = ('done', 'done_late', 'not_needed', 'skipped', 'failed', 'blocked', 'disabled_relay',
                'disabled_odoo', 'auth_error', 'cancelled')
INFLIGHT_LIMIT = 2

MODE_COMMANDS = ('auto', 'manual', 'test')            # підтвердження — controller_mode (ФВ-9)
BREAKER_COMMANDS = ('gen_close_open', 'mains_close_open')
CRANK_COMMANDS = ('start', 'test')                    # crank_failure → failed без повторів (AC-26)
MANUAL_STOP = ('manual', 'stop')                      # пакет «Ручний + Стоп»: stop переводить контролер у Stop
AUTO_SOURCES = ('schedule', 'timer', 'exception', 'test')
LATE_POLICY_SOURCES = ('schedule', 'timer', 'exception')   # політика until_next (А.5)
CANCELLABLE_STATES = ('queued_odoo', 'to_send', 'retry', 'waiting_link')
CHATTER_STATES = ('done', 'done_late', 'failed', 'blocked', 'disabled_relay', 'disabled_odoo', 'auth_error',
                  'skipped', 'not_needed')
STOP_CONFIRM_STATUSES = (10, 11, 12, 13, 15, 0)       # охолодження або зупинка (рішення 07.10, ФВ-9)
START_CONFIRM_STATUSES = (5, 6, 7, 8, 9)            # двигун запущено (не прокрутка); оберти не обов'язкові
START_SEQUENCE_STATUSES = (1, 2, 3, 4)               # підігрів, паливо, прокрутка, пауза між спробами
TECH_RELAY_CODES = ('relay_cmd_disabled', 'relay_cmd_format', 'relay_auth')

STEP = timedelta(minutes=1)              # крок cron і транспортного повтору
DUE_TOLERANCE = timedelta(seconds=30)    # пів кроку cron: що настає до наступного запуску — робимо зараз
SENT_TIMEOUT = timedelta(minutes=2)      # sent без фіналу довше — як timeout (А.5)
FRESH_READING = timedelta(minutes=2)     # автомати — лише за знімком не старшим за 2 хв (ФВ-14)
DONE_GRACE = timedelta(seconds=30)       # після done контролеру треба мить на знімок «change»
MAX_STEPS_PER_RUN = 8

SYSTEM_REQUESTERS = {
    'schedule': 'Odoo: розклад',
    'exception': 'Odoo: розклад',
    'timer': 'Odoo: таймер',
    'test': 'Odoo: тест',
    'system': 'Odoo: система',
    'retry': 'Odoo: повтор',
    'button': 'Odoo',
}


def _utc_datetime(value):
    """``'2026-10-07T15:57:22Z'`` або секунди Unix → UTC naive ``datetime`` без мікросекунд (``None`` — немає)."""
    if value in (None, False, ''):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None, microsecond=0)
    try:
        moment = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    if moment.tzinfo:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.replace(microsecond=0)


def _status_code(value):
    """``genset_status`` знімка (``'9'`` / ``9`` / ``0`` / ``None``) → ``int`` або ``None``."""
    if value is None or value is False or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TdGensetCommand(models.Model):
    _name = 'td.genset.command'
    _description = 'Генератори: команда'
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Номер', readonly=True, copy=False,
        help='Номер команди з послідовності «CMD-<рік>-00001».')
    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, index=True, ondelete='cascade',
        help='Генератор, якому надсилається команда.')
    command = fields.Selection(
        COMMANDS, string='Команда',
        help='Команда 05H: 0000 Пуск, 0001 Стоп, 0002 Тест, 0003 Авто, 0004 Ручний, 0005/0006 автомати.')
    source = fields.Selection(
        COMMAND_SOURCES, string='Джерело',
        help='Звідки прийшла команда; у ретранслятор передається як «odoo:<джерело>» (повторні спроби — '
             '«odoo:retry»).')
    user_id = fields.Many2one(
        'res.users', string='Хто', ondelete='set null',
        help='Ініціатор або OdooBot для планувальника; requested_by = «<Ім\'я> (res.users <id>)» або «Odoo: розклад».')
    batch_key = fields.Char(
        string='Пакет', index=True,
        help='Спільний ключ пакета «Ручний + Стоп»; порядок — за послідовністю.')
    sequence = fields.Integer(
        string='Порядок у пакеті', default=1,
        help='Порядок надсилання в пакеті (1, 2).')
    target_breaker_closed = fields.Boolean(
        string='Цільове положення автомата',
        help='Для перемикачів автоматів: True — замкнути, False — розімкнути (ФВ-14).')
    state = fields.Selection(
        COMMAND_STATES, string='Стан', default='to_send', index=True,
        help='Стан команди (стан-машина А.5): підтвердження — лише за знімком після виконання.')
    result_note = fields.Char(
        string='Результат',
        help='Пояснення стану: «Не потрібно: уже Авто», «Пропущено: діє таймер до 20:00» …')
    relay_cmd_id = fields.Integer(
        string='ID команди ретранслятора', aggregator=None, copy=False,
        help='id запису команди на ретрансляторі (POST 201).')
    relay_status = fields.Selection(
        RELAY_STATUSES, string='Стан ретранслятора',
        help='status з GET /commands/<id>: queued → sent → done / failed / timeout.')
    relay_error = fields.Char(
        string='Помилка ретранслятора',
        help='error ретранслятора: controller rejected the command, no reply in 30 s, modem disconnected, '
             'relay restarted.')
    attempt = fields.Integer(
        string='Спроба', default=0,
        help='Скільки надісланих спроб не підтвердилося (повтори підтвердження).')
    transport_attempt = fields.Integer(
        string='Транспортна спроба', default=0,
        help='Повтори надсилання після 409 / 5xx / таймауту або коли немає зв\'язку з модулем.')
    max_attempts = fields.Integer(
        string='Макс. спроб',
        help='retry_window_min / retry_every_min на момент створення — «Спроба N з M».')
    first_sent_at = fields.Datetime(
        string='Перша спроба',
        help='Перша спроба доставки (POST або перевірка зв\'язку), навіть невдала — від неї відлічується вікно '
             'повторів (А.5).')
    sent_at = fields.Datetime(
        string='Надіслано о',
        help='Остання успішна відправка (POST 201).')
    done_at = fields.Datetime(
        string='Виконано ретранслятором о',
        help='done_utc ретранслятора; підтвердження — лише знімком з ts ≥ цього часу.')
    confirmed_at = fields.Datetime(
        string='Підтверджено о',
        help='Коли знімок підтвердив виконання.')
    deadline_at = fields.Datetime(
        string='Дедлайн вікна', index=True,
        help='Перша спроба + вікно повторів; подовжується на час без зв\'язку.')
    next_attempt_at = fields.Datetime(
        string='Наступна спроба', index=True,
        help='Крок cron бере команди з цим часом ≤ зараз.')
    late_transition_at = fields.Datetime(
        string='Перехід, що минув',
        help='Для пропущених переходів розкладу: «із запізненням (перехід 18:30)».')
    link_lost_during = fields.Boolean(
        string="Зв'язок зник до підтвердження",
        help="Під час очікування підтвердження модуль втратив зв'язок (ФВ-12).")
    confirm_reading_id = fields.Many2one(
        'td.genset.reading', string='Знімок-підтвердження', ondelete='set null',
        help='Знімок, яким підтверджено виконання.')
    alarm_id = fields.Many2one(
        'td.genset.alarm', string='Тривога', ondelete='set null',
        help='Тривога «команда не підтверджена» / помилка надсилання.')
    # ---- службові поля стан-машини (W2)
    requested_by = fields.Char(
        string='Ініціатор для ретранслятора',
        help='requested_by у POST /commands: «<Ім\'я> (res.users <id>)» або «Odoo: розклад».')
    last_attempt_at = fields.Datetime(
        string='Остання спроба',
        help='Остання спроба доставки (POST або перевірка зв\'язку) — від неї рахуються повтори після тривоги.')
    link_lost_at = fields.Datetime(
        string="Зв'язок зник о",
        help="Коли команда перейшла в «Очікує: немає зв'язку».")
    link_restored_at = fields.Datetime(
        string="Зв'язок відновлено о",
        help="Після відновлення зв'язку команда перевіряється за першим новим знімком, вікно повторів — нове.")
    transport_failure = fields.Boolean(
        string='Остання спроба — без доставки',
        help="Остання спроба не дійшла до контролера (409 / 5xx / немає зв'язку) — у тривозі «модуль не на зв'язку».")
    cancel_requested = fields.Boolean(
        string='Повторів не буде',
        help='Новий перехід, таймер, тест або команда з пульта скасували команду, коли вона вже була на '
             'ретрансляторі: підтвердження чекаємо, повторів не буде.')
    alarm_raised_at = fields.Datetime(
        string='Тривогу створено о',
        help='Коли створено тривогу «не підтверджено» (для політики «до наступного переходу» — один раз).')

    _sql_constraints = [
        ('relay_cmd_uniq', 'unique(genset_id, relay_cmd_id)',
         'Команда ретранслятора з таким ID уже прив\'язана до цього генератора.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('td.genset.command') or _('Нова')
        return super().create(vals_list)

    # ================================================================== допоміжні
    def _label(self, field_name, value=None):
        """Перекладена мітка selection-поля команди (``command``/``source``/``state``)."""
        if value is None:
            value = self[field_name]
        return dict(self._fields[field_name]._description_selection(self.env)).get(value, value or '')

    def _mode_label(self, mode):
        """Мітка режиму контролера («Авто», «Ручний» …)."""
        field = self.env['td.genset']._fields['controller_mode']
        return dict(field._description_selection(self.env)).get(mode, mode or '')

    def _config(self):
        return self.env['td.genset.config'].sudo().get()

    def _retry_every(self):
        return timedelta(minutes=max(self._config().retry_every_min or 2, 1))

    def _retry_window(self):
        config = self._config()
        return timedelta(minutes=max(config.retry_window_min or 10, config.retry_every_min or 2, 1))

    @staticmethod
    def _due(moment, now):
        """Чи настав момент для цього кроку cron (з допуском у пів кроку)."""
        return not moment or moment <= now + DUE_TOLERANCE

    @api.model
    def _requested_by_values(self, requested_by, source):
        """``requested_by`` (``res.users`` або рядок) → ``(user, текст для ретранслятора)``."""
        if isinstance(requested_by, models.BaseModel) and requested_by._name == 'res.users' and requested_by:
            user = requested_by[:1]
            return user, '%s (res.users %s)' % (user.name, user.id)
        user = self.env.ref('base.user_root')
        text = requested_by if isinstance(requested_by, str) and requested_by else SYSTEM_REQUESTERS.get(source, 'Odoo')
        return user, text

    def _late_mark(self):
        return _('із запізненням (перехід %(time)s)', time=kyiv_hhmm(self.late_transition_at))

    def _notify_command(self):
        """``_notify_bus('command')`` для кожної команди (А.9): пульт і журнал оновлюються без перезавантаження."""
        for command in self:
            command.genset_id._notify_bus('command', {
                'command_id': command.id, 'state': command.state, 'note': command.result_note or ''})

    @api.model
    def _trigger_cron(self, at=None):
        """Розбудити cron «Генератори: команди» (``ir.cron._trigger``; ``at`` — точність до хвилини)."""
        cron = self.env.ref('td_genset.cron_commands', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger(at)

    def _set_state(self, state, note=None, chatter=None, **vals):
        """Перехід стан-машини: ``result_note`` (+ позначка запізнілого переходу), bus при зміні, чатер для
        фінальних станів (А.5; ``chatter`` — власний текст повідомлення)."""
        self.ensure_one()
        old_state, old_note = self.state, self.result_note
        if note is not None:
            if self.late_transition_at:
                mark = self._late_mark()
                if mark not in note:
                    note = '%s · %s' % (note, mark)
            vals['result_note'] = note
        vals['state'] = state
        self.write(vals)
        if self.state != old_state or self.result_note != old_note:
            self._notify_command()
        if state != old_state and state in CHATTER_STATES:
            self._post_final_message(body=chatter)

    # ================================================================== створення
    @api.model
    def _enqueue(self, genset, command, source, requested_by, batch_key=None, late_transition_at=None,
                 target_breaker_closed=None):
        """Єдина точка створення команди: ``requested_by`` — ``res.users`` або рядок («Odoo: розклад»);
        стан ``to_send``/``queued_odoo`` (ліміт 2 у роботі на ретрансляторі, ФВ-13), ``next_attempt_at=now``,
        ``max_attempts``, запис у чатер; ``env.ref('td_genset.cron_commands')._trigger()``.
        Права перевіряє викликач (майстер/кнопки/планувальник); метод працює через ``sudo()``.

        Контекст: ``td_genset_sequence`` — порядок у пакеті, ``td_genset_no_chatter`` — без запису в чатер
        (пакет пише один запис).

        :return: запис ``td.genset.command`` (sudo).
        AC-12, AC-13, AC-19, AC-20, AC-21, AC-66.
        """
        commands = self.sudo()
        genset = genset.sudo()
        genset.ensure_one()
        now = fields.Datetime.now()
        config = commands._config()
        every = max(config.retry_every_min or 2, 1)
        window = max(config.retry_window_min or 10, every)
        user, requester = commands._requested_by_values(requested_by, source)
        queued = commands._count_inflight(genset) >= INFLIGHT_LIMIT
        if queued:
            note = _('У черзі Odoo: на ретрансляторі вже %(count)s команди від Odoo', count=INFLIGHT_LIMIT)
        else:
            note = _('До надсилання')
        if late_transition_at:
            note = '%s · %s' % (note, _('із запізненням (перехід %(time)s)', time=kyiv_hhmm(late_transition_at)))
        command_record = commands.create({
            'genset_id': genset.id,
            'command': command,
            'source': source,
            'user_id': user.id,
            'requested_by': requester,
            'batch_key': batch_key or False,
            'sequence': self.env.context.get('td_genset_sequence', 1),
            'target_breaker_closed': bool(target_breaker_closed) if command in BREAKER_COMMANDS else False,
            'state': 'queued_odoo' if queued else 'to_send',
            'result_note': note,
            'max_attempts': max(1, window // every),
            'next_attempt_at': now,
            'late_transition_at': late_transition_at or False,
        })
        if not self.env.context.get('td_genset_no_chatter'):
            command_record._post_enqueue_message()
        command_record._notify_command()
        commands._trigger_cron()
        return command_record

    @api.model
    def _enqueue_batch(self, genset, commands, source, requested_by, late_transition_at=None):
        """Пакет (``batch_key = f"{genset.id}-{uuid4().hex[:8]}"``, ``sequence`` 1..n), ``_enqueue`` для кожної;
        обидві команди «Ручний + Стоп» надсилаються в одному кроці cron одна за одною без очікування (ФВ-13).

        :return: recordset команд (sudo) у порядку пакета.
        AC-19, AC-28, AC-33.
        """
        batch_key = '%s-%s' % (genset.id, uuid4().hex[:8])
        records = self.sudo().browse()
        for sequence, command in enumerate(commands, start=1):
            records |= self.with_context(td_genset_sequence=sequence, td_genset_no_chatter=True)._enqueue(
                genset, command, source, requested_by, batch_key=batch_key, late_transition_at=late_transition_at)
        records._post_enqueue_message()
        return records

    @api.model
    def _log_final(self, genset, command, source, requested_by, state, note, late_transition_at=None, body=None):
        """Запис журналу без надсилання (планувальник: «Пропущено: діє таймер до 20:00», «Не потрібно: уже Авто
        за таймером», «Пропущено: іде тест») — одразу у фінальному стані, з чатером і bus (А.5, А.6 п. 4)."""
        commands = self.sudo()
        genset = genset.sudo()
        user, requester = commands._requested_by_values(requested_by, source)
        if late_transition_at:
            note = '%s · %s' % (note, _('із запізненням (перехід %(time)s)', time=kyiv_hhmm(late_transition_at)))
        record = commands.create({
            'genset_id': genset.id,
            'command': command,
            'source': source,
            'user_id': user.id,
            'requested_by': requester,
            'state': state,
            'result_note': note,
            'max_attempts': 0,
            'late_transition_at': late_transition_at or False,
        })
        record._post_final_message(body=body)
        record._notify_command()
        return record

    # ================================================================== cron
    @api.model
    def _cron_process_commands(self):
        """Точка входу cron ``cron_commands`` (1 хв, priority 1, + ``_trigger()``): вибірка
        ``FOR NO KEY UPDATE SKIP LOCKED`` (А.7) у порядку ``genset_id, id`` (порядок пакета — за id), до
        ``MAX_STEPS_PER_RUN`` кроків ``_step()`` на команду, поки наступний крок настає в цьому запуску;
        ``_trigger(at=…)`` для найближчого кроку, що настане раніше за наступний хвилинний запуск.
        Винятки перехоплюються: cron не падає (інакше Odoo деактивує задачу).

        AC-12…AC-23, AC-26, AC-66, AC-67.
        """
        now = fields.Datetime.now()
        try:
            command_ids = self._lock_due_ids(now)
        except Exception:  # noqa: BLE001 — cron не має падати (А.7)
            _logger.warning('td_genset: command selection failed', exc_info=True)
            return None
        for command in self.sudo().browse(command_ids):
            command._process_due()
        try:
            self._schedule_next_run(now)
        except Exception:  # noqa: BLE001
            _logger.warning('td_genset: command cron trigger failed', exc_info=True)
        return None

    @api.model
    def _lock_due_ids(self, now):
        """``SELECT … FOR NO KEY UPDATE SKIP LOCKED`` — два воркери не надішлють одну команду двічі (А.7)."""
        self.env['td.genset.command'].flush_model(['state', 'next_attempt_at', 'genset_id'])
        self.env.cr.execute(SQL(
            """SELECT id FROM td_genset_command
                WHERE state IN %s AND (next_attempt_at IS NULL OR next_attempt_at <= %s)
                ORDER BY genset_id, id
                FOR NO KEY UPDATE SKIP LOCKED""",
            tuple(OPEN_STATES), now + DUE_TOLERANCE))
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _schedule_next_run(self, now):
        self.env['td.genset.command'].flush_model(['state', 'next_attempt_at'])
        self.env.cr.execute(SQL(
            "SELECT MIN(next_attempt_at) FROM td_genset_command WHERE state IN %s AND next_attempt_at > %s",
            tuple(OPEN_STATES), now + DUE_TOLERANCE))
        next_at = self.env.cr.fetchone()[0]
        if next_at and next_at < now + STEP:
            self._trigger_cron(at=next_at)

    def _process_due(self):
        """Кроки однієї команди в межах запуску cron; кожен крок — у savepoint."""
        self.ensure_one()
        for _step_no in range(MAX_STEPS_PER_RUN):
            state_before = self.state
            try:
                with self.env.cr.savepoint():
                    self._step()
            except Exception:  # noqa: BLE001 — помилка однієї команди не зупиняє інші
                _logger.warning('td_genset: command %s step failed in state %s', self.id, state_before,
                                exc_info=True)
                self.env.invalidate_all()
                self.write({'next_attempt_at': fields.Datetime.now() + STEP})
                return
            if self.state in FINAL_STATES or not self._due(self.next_attempt_at, fields.Datetime.now()):
                return

    def _step(self):
        """Один крок стан-машини А.5 для ``self`` (``ensure_one``); ``result_note``, ``_notify_bus('command')``.

        AC-12…AC-18.
        """
        self.ensure_one()
        handler = {
            'queued_odoo': self._step_queued,
            'to_send': self._step_send,
            'sent': self._step_sent,
            'awaiting': self._step_awaiting,
            'retry': self._step_retry,
            'waiting_link': self._step_waiting_link,
        }.get(self.state)
        if handler:
            handler(fields.Datetime.now())
        return None

    # ------------------------------------------------------------------ стани
    def _step_queued(self, now):
        """``queued_odoo`` → ``to_send``, коли в роботі на ретрансляторі менше 2 команд (ФВ-13)."""
        if self._count_inflight(self.genset_id) < INFLIGHT_LIMIT:
            self._set_state('to_send', _('До надсилання'), next_attempt_at=now)
        else:
            self.write({'next_attempt_at': now + STEP})

    def _start_window(self, now):
        """Вікно повторів — від першої спроби доставки, навіть невдалої (А.5, AC-15)."""
        if not self.first_sent_at:
            self.write({'first_sent_at': now, 'deadline_at': now + self._retry_window()})

    def _step_send(self, now):
        """``to_send``: перевірки ``_precheck`` → ліміт 2 → ``POST /commands``."""
        result = self._precheck_result(now)
        if result:
            state, note, reason = result
            if state in FINAL_STATES:
                self._set_state(state, note, next_attempt_at=False)
                if state == 'disabled_relay':
                    self._raise_tech('relay_cmd_disabled',
                                     _('Команди вимкнено на ретрансляторі (RELAY_COMMANDS_ENABLED=0).'))
                return
            if state == 'retry':
                self._start_window(now)   # перша спроба доставки, навіть невдала (А.5, AC-15)
                self._transport_retry(note, now, link=reason == 'link')
            else:   # чекаємо свіжого знімка для автомата (ФВ-14) або кінця пуску для start — вікно ще не почалося
                self._set_state('to_send', note, next_attempt_at=now + STEP, last_attempt_at=now)
            return
        if self._count_inflight(self.genset_id) >= INFLIGHT_LIMIT:
            self._set_state('queued_odoo', _('У черзі Odoo: на ретрансляторі вже %(count)s команди від Odoo',
                                             count=INFLIGHT_LIMIT), next_attempt_at=now + STEP)
            return
        self._start_window(now)
        self._post(now)

    def _post(self, now):
        """``POST /commands`` і реакція на код відповіді (2.6.3, А.5)."""
        genset = self.genset_id.sudo()
        client = self.env['td.genset.relay.client']
        retrying = bool(self.attempt or self.transport_attempt)
        source = 'odoo:retry' if retrying else 'odoo:%s' % self.source
        requester = self.requested_by or SYSTEM_REQUESTERS.get(self.source, 'Odoo')
        try:
            body = client.post_command(genset.relay_hostid, self.command, requester, source)
        except RelayBusy as exc:
            _logger.info('td_genset: command %s POST -> 409 (%s)', self.id, exc.reason)
            if exc.reason == 'format_not_learned':
                self._raise_tech('relay_cmd_format', _('Ретранслятор ще не вивчив формат команд.'))
                reason = _('ретранслятор ще не вивчив формат команд')
            elif exc.reason == 'queue_full':
                reason = _('черга ретранслятора заповнена')
            else:
                reason = _("модуль не на зв'язку")
            self._transport_retry(reason, now, relay_error=exc.error)
            return
        except RelayCommandsDisabled as exc:
            self._set_state('disabled_relay', _('Керування вимкнено на ретрансляторі'), relay_error=exc.error,
                            last_attempt_at=now, next_attempt_at=False)
            self._raise_tech('relay_cmd_disabled', _('Команди вимкнено на ретрансляторі (RELAY_COMMANDS_ENABLED=0).'))
            return
        except RelayAuthError as exc:
            self._set_state('auth_error', _('Помилка доступу: ретранслятор відхилив токен (401)'),
                            relay_error=exc.error, last_attempt_at=now, next_attempt_at=False)
            self._raise_tech('relay_auth', _('Ретранслятор відхилив токен (401). Перевірте токен у Налаштуваннях.'))
            return
        except (RelayBadRequest, RelayNotFound) as exc:
            unknown_host = isinstance(exc, RelayNotFound) and 'hostid' in (exc.error or '')
            note = _('Не виконано: ретранслятор не прийняв команду (%(status)s: %(error)s)',
                     status=exc.status, error=exc.error or '')
            self._set_state('failed', note, relay_error=exc.error, last_attempt_at=now, next_attempt_at=False)
            if unknown_host:
                alarm = self._raise_tech('relay_unknown_hostid',
                                         _('Ретранслятор не знає модуль з цим hostid (404). Перевірте ID модуля на '
                                           'картці генератора.'))
            else:
                alarm = self._raise_tech('relay_cmd_rejected',
                                         _('Ретранслятор не прийняв команду «%(command)s» (%(status)s).',
                                           command=self._label('command'), status=exc.status),
                                         description=exc.error or '')
            if alarm:
                self.alarm_id = alarm
            return
        except RelayError as exc:   # RelayUnavailable: таймаут, 5xx, обрив
            _logger.info('td_genset: command %s POST failed: %s', self.id, exc.status)
            self._transport_retry(_('ретранслятор недоступний'), now, relay_error=exc.error)
            return
        relay_id = (body or {}).get('id') if isinstance(body, dict) else None
        if not relay_id:
            self._transport_retry(_('ретранслятор не повернув номер команди'), now)
            return
        if self.attempt:
            note = _('Надіслано · спроба %(attempt)s з %(max)s', attempt=self.attempt + 1, max=self.max_attempts)
        else:
            note = _('Надіслано')
        relay_status = body.get('status')
        self._set_state('sent', note,
                        relay_cmd_id=relay_id,
                        relay_status=relay_status if relay_status in dict(RELAY_STATUSES) else 'queued',
                        relay_error=False, sent_at=now, done_at=False, last_attempt_at=now,
                        transport_failure=False, next_attempt_at=now + STEP,
                        link_restored_at=False, link_lost_at=False)
        self._clear_tech_relay_alarms()

    def _transport_retry(self, reason, now, link=False, relay_error=None):
        """Транспортний повтор: щохвилини (крок cron) у межах вікна (ФВ-11)."""
        attempt = self.transport_attempt + 1
        vals = {
            'transport_attempt': attempt,
            'transport_failure': True,
            'last_attempt_at': now,
            'next_attempt_at': now + STEP,
        }
        if link:
            vals['link_lost_during'] = True
        if relay_error is not None:
            vals['relay_error'] = relay_error
        self._set_state('retry', _('Повтор: %(reason)s (спроба %(attempt)s)', reason=reason, attempt=attempt), **vals)

    def _step_sent(self, now):
        """``sent``: ``GET /commands/<id>`` — done → ``awaiting``; failed/timeout або > 2 хв → ``retry``."""
        client = self.env['td.genset.relay.client']
        try:
            body = client.command(self.relay_cmd_id) or {}
        except RelayNotFound as exc:
            body = {'status': 'failed', 'error': exc.error or 'no such command'}
        except RelayError as exc:
            _logger.info('td_genset: command %s status poll failed: %s', self.id, exc.status)
            # API недоступний (таймаут/5xx) — 2 хв не рахуються: команда могла виконатися, тож без нового POST
            # перечитуємо GET /commands/<id>, щойно API відповість (інакше — повтор тієї самої команди)
            if not isinstance(exc, RelayUnavailable) and self._due((self.sent_at or now) + SENT_TIMEOUT, now):
                self._relay_failed(now, _('немає відповіді ретранслятора'), relay_status='timeout')
            else:
                self.write({'next_attempt_at': now + STEP})
            return
        status = body.get('status')
        vals = {}
        if status in dict(RELAY_STATUSES):
            vals['relay_status'] = status
        if status == 'done':
            done_at = _utc_datetime(body.get('done_utc')) or _utc_datetime(body.get('done')) or now
            self._set_state('awaiting', _('Очікує підтвердження за знімком'), done_at=done_at,
                            relay_error=False, next_attempt_at=now, **vals)
        elif status in ('failed', 'timeout'):
            self._relay_failed(now, self._relay_error_reason(body.get('error')), relay_error=body.get('error') or False,
                               **vals)
        elif self._due((self.sent_at or now) + SENT_TIMEOUT, now):
            self._relay_failed(now, _('ретранслятор не завершив команду за 2 хв'), relay_status='timeout')
        else:
            self.write(dict(vals, next_attempt_at=now + STEP))

    def _relay_error_reason(self, error):
        """Причина ``failed``/``timeout`` ретранслятора українською (AC-17)."""
        text = (error or '').lower()
        if 'restart' in text:
            return _('ретранслятор перезапущено')
        if 'reject' in text:
            return _('контролер відхилив команду')
        if 'no reply' in text:
            return _('модуль не відповів за 30 с')
        if 'disconnect' in text:
            return _("модуль від'єднався")
        return error or _('помилка ретранслятора')

    def _relay_failed(self, now, reason, **vals):
        """``sent → retry``: ``attempt++``, наступна спроба через ``retry_every_min`` (А.5)."""
        attempt = self.attempt + 1
        vals.update(attempt=attempt, next_attempt_at=now + self._retry_every())
        self._set_state('retry', _('Спроба %(attempt)s з %(max)s · %(reason)s',
                                   attempt=attempt, max=self.max_attempts, reason=reason), **vals)

    def _step_awaiting(self, now):
        """``awaiting``: рішення лише за знімком з ``ts ≥ done_at`` (збережений або ``GET /latest``), ФВ-9, ФВ-12.

        * знімок підтверджує → ``done`` (після втрати зв'язку — ``done_late``); ``start``/``test`` +
          ``crank_failure`` у будь-якому знімку → ``failed`` без повторів;
        * немає зв'язку → ``waiting_link``;
        * є знімок після ``done_at``, а мети не досягнуто → повтор через ``retry_every_min`` від ``done_at``
          (``start``, поки контролер у послідовності пуску 1–4, чекаємо до кінця вікна);
        * знімків після ``done_at`` ще немає → чекаємо; зв'язок є, але знімка немає довше ``retry_every_min`` + 1 хв
          → вважаємо непідтвердженим → повтор;
        * після відновлення зв'язку вирішує перший новий знімок (немає довше ``retry_every_min`` + 1 хв → повтор).
        """
        genset = self.genset_id.sudo()
        verdict, facts, newest = self._find_confirmation()
        if verdict == 'crank':
            self._fail_crank(now, facts)
            return
        if verdict == 'done':
            self._confirm(now, facts)
            return
        if genset.link_state != 'online':
            self._set_state('waiting_link', _("Очікує: немає зв'язку"), link_lost_during=True, link_lost_at=now,
                            next_attempt_at=now + STEP)
            return
        every = self._retry_every()
        silence_limit = every + STEP
        if self.link_restored_at and (not self.done_at or self.done_at <= self.link_restored_at):
            # перше рішення після відновлення зв'язку — за першим новим знімком; після нового POST (``_post``
            # скидає ``link_restored_at``) — загальне правило: ``done_at + retry_every_min``, пуск 1–4
            if newest and self.link_lost_at and newest['ts'] > self.link_lost_at:
                self._confirmation_retry(now)
            elif now > self.link_restored_at + silence_limit:
                self._confirmation_retry(now, reason=_('немає знімка після відновлення зв\'язку'))
            else:
                self.write({'next_attempt_at': now + STEP})
            return
        base = self.done_at or self.sent_at or now
        if not newest:
            if now > base + silence_limit:
                self._confirmation_retry(now, reason=_('немає знімка після виконання'))
            else:
                self.write({'next_attempt_at': now + STEP})
            return
        if self.command == 'start' and self._start_in_progress(newest) and self.deadline_at and now < self.deadline_at:
            self._set_state('awaiting', _('Очікує підтвердження: триває пуск (стан %(status)s)',
                                          status=newest['genset_status']), next_attempt_at=now + STEP)
            return
        if self._due(base + every, now) and self._due(base + DONE_GRACE, now):
            self._confirmation_retry(now)
        else:
            self.write({'next_attempt_at': min(now + STEP, base + every)})

    def _confirmation_retry(self, now, reason=None):
        attempt = self.attempt + 1
        self._set_state('retry', _('Спроба %(attempt)s з %(max)s · %(reason)s', attempt=attempt, max=self.max_attempts,
                                   reason=reason or _('без підтвердження')),
                        attempt=attempt, next_attempt_at=now)

    @staticmethod
    def _start_in_progress(facts):
        """Контролер у послідовності пуску (1 підігрів … 4 пауза між спробами) без ``crank_failure``."""
        return facts.get('genset_status') in START_SEQUENCE_STATUSES and not facts.get('crank_failure')

    def _find_confirmation(self):
        """Знімки з ``ts ≥ done_at`` (збережені W1 і ``GET /latest``, якщо його ще немає в базі), у порядку часу:
        ``('crank' | 'done' | None, факти знімка-рішення, факти найновішого знімка або None)``.

        ``crank_failure`` у будь-якому знімку після ``done_at`` для ``start``/``test`` має пріоритет.
        """
        genset = self.genset_id.sudo()
        since = self.done_at or self.sent_at
        domain = [('genset_id', '=', genset.id)]
        if since:
            domain.append(('ts', '>=', since))
        readings = self.env['td.genset.reading'].sudo().search(domain, order='ts asc, id asc', limit=500)
        snapshots = [self._reading_facts(reading) for reading in readings]
        seen = {facts['relay_id'] for facts in snapshots}
        try:
            latest = self.env['td.genset.relay.client'].latest(genset.relay_hostid)
        except RelayError as exc:
            _logger.info('td_genset: latest snapshot unavailable: %s', exc.status)
            latest = None
        if isinstance(latest, dict) and latest.get('values') is not None and latest.get('id') not in seen:
            facts = self._reading_facts(latest)
            if facts['ts'] and (not since or facts['ts'] >= since):
                snapshots.append(facts)
        snapshots.sort(key=lambda facts: facts['ts'])
        newest = snapshots[-1] if snapshots else None
        if self.command in CRANK_COMMANDS:
            for facts in snapshots:
                if facts.get('crank_failure'):
                    return 'crank', self._with_record(facts), newest
        manual_stop_batch = self._is_manual_stop_batch()
        for facts in snapshots:
            if self._confirm_condition(facts, manual_stop_batch):
                return 'done', self._with_record(facts), newest
        return None, None, newest

    def _with_record(self, facts):
        """Для знімка з ``/latest`` — знайти вже збережений запис (``confirm_reading_id``), якщо він є."""
        if not facts.get('record') and facts.get('relay_id'):
            facts['record'] = self.env['td.genset.reading'].sudo().search(
                [('genset_id', '=', self.genset_id.id), ('relay_id', '=', facts['relay_id'])], limit=1)
        return facts

    @api.model
    def _reading_facts(self, reading):
        """Знімок (запис ``td.genset.reading`` або тіло ``/latest``) → словник фактів для умов ФВ-9."""
        if isinstance(reading, dict):
            if 'controller_mode' in reading and 'record' in reading:
                return reading   # уже факти
            values = reading.get('values') or {}
            return {
                'ts': _utc_datetime(reading.get('ts')) or _utc_datetime(reading.get('time_utc')),
                'controller_mode': values.get('controller_mode') or 'unknown',
                'genset_status': _status_code(values.get('genset_status')),
                'speed': values.get('speed'),
                'gen_on_load': values.get('gen_on_load'),
                'mains_on_load': values.get('mains_on_load'),
                'crank_failure': bool(values.get('crank_failure')),
                'relay_id': reading.get('id'),
                'record': None,
            }
        reading.ensure_one()
        return {
            'ts': reading.ts,
            'controller_mode': reading.controller_mode or 'unknown',
            'genset_status': _status_code(reading.genset_status),
            'speed': reading.speed,
            'gen_on_load': reading.gen_on_load,
            'mains_on_load': reading.mains_on_load,
            'crank_failure': bool(reading.crank_failure),
            'relay_id': reading.relay_id,
            'record': reading,
        }

    def _check_confirmation(self, reading):
        """Умова ФВ-9 для ``self.command`` за знімком (``reading.ts ≥ done_at``).

        * ``auto``/``manual``/``test`` — ``controller_mode`` цільовий (``unknown`` не підтверджує); ``manual`` у пакеті
          «Ручний + Стоп» — ``controller_mode ∈ {manual, stop}`` (``stop`` переводить контролер у режим Stop,
          ``relay_api.md`` 7.1);
        * ``stop`` — ``gen_on_load = False`` і ``genset_status ∈ {10, 11, 12, 13, 15, 0}`` (охолодження або
          зупинка; для генератора, що стоїть, — перший знімок зі станом 0/15 або, якщо стан невідомий, з режимом
          Stop);
        * ``start`` — двигун запущено: ``genset_status ∈ {5…9}``; оберти не обов'язкові (NULL/0 не заважає), а самі
          ``speed > 0`` без такого стану (прокрутка 3 з обертами ~250) — ще ні;
        * автомати — ``gen_on_load``/``mains_on_load`` = ціль.

        :param reading: запис ``td.genset.reading`` або тіло ``GET /latest``.
        :rtype: bool
        AC-12, AC-19, AC-21, AC-25, AC-26, AC-67.
        """
        self.ensure_one()
        return self._confirm_condition(reading, self._is_manual_stop_batch())

    def _confirm_condition(self, reading, manual_stop_batch):
        """Тіло ``_check_confirmation``; ``manual_stop_batch`` — команда з пакета «Ручний + Стоп»."""
        facts = self._reading_facts(reading)
        if not facts or not facts.get('ts'):
            return False
        if self.done_at and facts['ts'] < self.done_at:
            return False
        command = self.command
        if command in MODE_COMMANDS:
            if command == 'manual' and manual_stop_batch:
                return facts['controller_mode'] in MANUAL_STOP
            return facts['controller_mode'] == command
        if command == 'stop':
            if facts['gen_on_load']:
                return False
            status = facts['genset_status']
            return status in STOP_CONFIRM_STATUSES or (status is None and facts['controller_mode'] == 'stop')
        if command == 'start':
            return facts['genset_status'] in START_CONFIRM_STATUSES
        if command == 'gen_close_open':
            return facts['gen_on_load'] is not None and bool(facts['gen_on_load']) == bool(self.target_breaker_closed)
        if command == 'mains_close_open':
            return facts['mains_on_load'] is not None and \
                bool(facts['mains_on_load']) == bool(self.target_breaker_closed)
        return False

    def _confirm(self, now, facts):
        """``awaiting → done`` (або ``done_late`` після втрати зв'язку); тривога команди знімається."""
        late = self.link_lost_during
        note = _("Підтверджено після відновлення зв'язку") if late else _('Підтверджено')
        if self.attempt and not late:
            note = '%s · %s' % (note, _('зі спроби %(attempt)s', attempt=self.attempt + 1))
        record = facts.get('record') if facts else None
        self._set_state('done_late' if late else 'done', note, confirmed_at=now,
                        confirm_reading_id=record.id if record else False, next_attempt_at=False)
        if self.alarm_raised_at:
            code = 'breaker_unconfirmed' if self.command in BREAKER_COMMANDS else 'cmd_unconfirmed'
            self.env['td.genset.alarm'].sudo()._clear(self.genset_id, code, note=self.result_note)

    def _fail_crank(self, now, facts):
        """``start``/``test`` + ``crank_failure`` → ``failed`` без повторів, тривога ``crank_failure_cmd`` (AC-26)."""
        record = facts.get('record') if facts else None
        self._set_state('failed', _('Не виконано: невдалий пуск'), confirm_reading_id=record.id if record else False,
                        next_attempt_at=False, alarm_raised_at=now)
        alarm = self.env['td.genset.alarm'].sudo()._raise(
            self.genset_id, 'crank_failure_cmd', 'crit', _('Невдалий пуск'),
            description=_('Невдалий пуск після команди «%(command)s».', command=self._label('command')),
            source=self)
        if alarm:
            self.alarm_id = alarm

    def _step_retry(self, now):
        """``retry``: у межах вікна → ``to_send``; після — політика ``window_only`` / ``until_next`` (А.5, ФВ-21)."""
        if self.cancel_requested:
            self._set_state('cancelled', _('Скасовано: новий перехід'), next_attempt_at=False)
            return
        if not self.deadline_at:
            self._start_window(now)
        within = now < self.deadline_at and self.attempt < max(self.max_attempts, 1)
        if within:
            self._set_state('to_send', None, next_attempt_at=now)
            return
        config = self._config()
        until_next = config.missed_transition_policy == 'until_next' and self.source in LATE_POLICY_SOURCES
        if not until_next:
            self._fail_unconfirmed(now)
            return
        late_every = timedelta(minutes=max(config.late_retry_every_min or 5, 1))
        if not self.alarm_raised_at:
            alarm = self._raise_unconfirmed()
            self.write({'alarm_raised_at': now, 'alarm_id': alarm.id if alarm else False})
        wait_until = (self.last_attempt_at or now) + late_every
        note = _('Не підтверджено за %(minutes)s хв — тривога; повтор кожні %(every)s хв до наступного переходу',
                 minutes=config.retry_window_min, every=config.late_retry_every_min)
        if self._due(wait_until, now):
            self._set_state('to_send', note, next_attempt_at=now)
        else:
            self._set_state('retry', note, next_attempt_at=wait_until)

    def _fail_unconfirmed(self, now):
        alarm = self._raise_unconfirmed()
        attempts = max(self.attempt + self.transport_attempt, 1)
        chatter = _('Команда «%(command)s» не виконана за %(minutes)s хв (спроб: %(attempts)s). Створено тривогу.',
                    command=self._label('command'), minutes=self._config().retry_window_min, attempts=attempts)
        self._set_state('failed', _('Не підтверджено — тривога (спроб: %(attempts)s)', attempts=attempts),
                        chatter=chatter, alarm_id=alarm.id if alarm else False, alarm_raised_at=now,
                        next_attempt_at=False)

    def _raise_unconfirmed(self):
        """Тривога «Команда «X» не підтверджена за M хв» — текст ТР 2.8.4 (``cmd_unconfirmed`` /
        ``breaker_unconfirmed``), рівень «критична», адресати — ланцюжок ескалації."""
        config = self._config()
        attempts = max(self.attempt + self.transport_attempt, 1)
        when = kyiv_hhmm(self.first_sent_at or self.create_date)
        source = self._label('source')
        link = _(", модуль не на зв'язку") if self.transport_failure else ''
        if self.command in BREAKER_COMMANDS:
            code = 'breaker_unconfirmed'
            if self.command == 'gen_close_open':
                name = _('Автомат генератора не змінив положення після команди.')
            else:
                name = _('Автомат мережі не змінив положення після команди.')
            description = _("%(origin)s, %(time)s. Спроб: %(attempts)s%(link)s. Перевірте на об'єкті: режим панелі, "
                            "блокування, зв'язок модуля з контролером.",
                            origin=source, time=when, attempts=attempts, link=link)
        else:
            code = 'cmd_unconfirmed'
            name = _('Команда «%(command)s» не підтверджена за %(minutes)s хв',
                     command=self._label('command'), minutes=config.retry_window_min)
            if self.transport_failure:
                name = '%s %s' % (name, _("(модуль не на зв'язку)"))
            description = _("%(origin)s, %(time)s. Спроб: %(attempts)s, режим контролера не змінився%(link)s. "
                            "Перевірте на об'єкті: режим панелі, блокування, зв'язок модуля з контролером.",
                            origin=source, time=when, attempts=attempts, link=link)
        return self.env['td.genset.alarm'].sudo()._raise(self.genset_id, code, 'crit', name,
                                                          description=description, source=self)

    def _step_waiting_link(self, now):
        """``waiting_link``: доки немає зв'язку — нічого; після відновлення ``deadline_at`` подовжується на час
        без зв'язку (і щонайменше нове вікно, ФВ-12) → ``awaiting`` (перший новий знімок вирішує)."""
        genset = self.genset_id.sudo()
        if genset.link_state != 'online':
            self.write({'next_attempt_at': now + STEP})
            return
        offline = now - (self.link_lost_at or now)
        deadline = max((self.deadline_at or now) + offline, now + self._retry_window())
        self._set_state('awaiting', _("Зв'язок відновлено: перевіряємо за першим знімком"),
                        deadline_at=deadline, link_restored_at=now, attempt=0, next_attempt_at=now)

    # ------------------------------------------------------------------ перевірки перед надсиланням
    def _precheck_result(self, now=None):
        """``(стан, примітка, причина)`` або ``None`` = надсилати; див. ``_precheck``."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        genset = self.genset_id.sudo()
        if not genset.commands_allowed:
            return 'disabled_odoo', _('Не надіслано: команди вимкнено в Odoo'), None
        if genset.remote_lock:
            return 'blocked', _('Не надіслано: блокування'), None
        if not genset.relay_commands_enabled:
            return 'disabled_relay', _('Керування вимкнено на ретрансляторі'), None
        if genset.link_state != 'online':
            return 'retry', _("модуль не на зв'язку"), 'link'
        if not genset.relay_commands_ready:
            return 'retry', _('ретранслятор не готовий до команд'), 'ready'
        if self.late_transition_at and self._external_control_after(self.late_transition_at):
            return 'skipped', _('Пропущено: керування не з Odoo після переходу'), None
        if self._is_manual_stop_batch():
            # «Ручний + Стоп»: мета пакета — режим Stop; уже Stop → не потрібно, інакше надсилаються обидві команди
            if genset.controller_mode == 'stop':
                return 'not_needed', _('Не потрібно: уже %(mode)s', mode=self._mode_label('stop')), None
        elif self.command in MODE_COMMANDS and genset.controller_mode == self.command:
            return 'not_needed', _('Не потрібно: уже %(mode)s', mode=self._mode_label(self.command)), None
        elif self.command == 'stop' and not genset.is_running:
            return 'not_needed', _('Не потрібно: генератор уже зупинено'), None
        elif self.command == 'start':
            status = _status_code(genset.genset_status)
            if status in START_SEQUENCE_STATUSES:
                return 'to_send', _('Очікуємо: триває пуск (стан %(status)s)', status=status), 'starting'
            if genset.is_running:
                return 'not_needed', _('Не потрібно: генератор уже працює'), None
        if self.command in BREAKER_COMMANDS:
            reading = genset.last_reading_id
            if not reading or not reading.ts or reading.ts < now - FRESH_READING:
                return 'to_send', _('Очікуємо показання: останній знімок старший за 2 хв'), 'stale'
            closed = reading.gen_on_load if self.command == 'gen_close_open' else reading.mains_on_load
            if bool(closed) == bool(self.target_breaker_closed):
                if self.command == 'gen_close_open':
                    note = _('Не потрібно: автомат генератора уже замкнено') if closed else \
                        _('Не потрібно: автомат генератора уже розімкнено')
                else:
                    note = _('Не потрібно: автомат мережі уже замкнено') if closed else \
                        _('Не потрібно: автомат мережі уже розімкнено')
                return 'not_needed', note, None
        return None

    def _precheck(self):
        """Перевірки ``to_send`` (А.5, 2.6.3): ``commands_allowed`` → ``disabled_odoo``; ``remote_lock`` →
        ``blocked``; ``relay_commands_enabled`` → ``disabled_relay``; немає зв'язку / ``commands_ready`` →
        ``retry`` (транспортний повтор); запізнілий перехід + подія ``external_control`` після нього →
        ``skipped``; «лише на переходах»: режим уже цільовий / ``stop`` для зупиненого / автомат уже в цільовому
        положенні → ``not_needed`` (пакет «Ручний + Стоп» — лише якщо контролер уже в режимі Stop, «Не потрібно:
        уже Стоп»; інакше надсилаються обидві команди); знімок для автомата старший за 2 хв → ``to_send`` (чекати);
        ``start``: двигун уже працює → ``not_needed`` «Не потрібно: генератор уже працює», триває пуск (стани 1–4) →
        ``to_send`` (чекати, без POST).

        :return: новий стан (str) або ``None`` = надсилати.
        AC-13, AC-16, AC-21, AC-23, AC-34, AC-66.
        """
        result = self._precheck_result()
        return result[0] if result else None

    def _is_manual_stop_batch(self):
        """Команда з пакета «Ручний + Стоп» (кінець вікна, кінець таймера або тесту поза вікном)."""
        self.ensure_one()
        if not self.batch_key or self.command not in MANUAL_STOP:
            return False
        siblings = self.sudo().search([('genset_id', '=', self.genset_id.id), ('batch_key', '=', self.batch_key)])
        return set(siblings.mapped('command')) == set(MANUAL_STOP)

    def _external_control_after(self, moment):
        """Чи є подія «Керування не з Odoo» після ``moment`` (ФВ-10, ФВ-21)."""
        return bool(self.env['td.genset.event'].sudo().search_count([
            ('genset_id', '=', self.genset_id.id),
            ('event_type', '=', 'external_control'),
            ('date_start', '>=', moment),
        ], limit=1))

    # ------------------------------------------------------------------ скасування, ліміт
    @api.model
    def _cancel_pending(self, genset, reason, sources=('schedule', 'timer', 'exception', 'test')):
        """Незавершені команди цих джерел → ``cancelled`` з ``result_note`` «Скасовано: <причина>» (А.5:
        ``queued_odoo``/``to_send``/``retry``/``waiting_link``). Команди, які вже на ретрансляторі
        (``sent``/``awaiting``), не скасовуються — їх підтвердження чекаємо, але повторів не буде.

        :return: скасовані команди (sudo).
        AC-28, AC-31, AC-32, AC-33.
        """
        commands = self.sudo().search([
            ('genset_id', '=', genset.id),
            ('source', 'in', list(sources)),
            ('state', 'in', OPEN_STATES),
        ])
        cancelled = commands.filtered(lambda command: command.state in CANCELLABLE_STATES)
        for command in cancelled:
            command._set_state('cancelled', _('Скасовано: %(reason)s', reason=reason), next_attempt_at=False)
        (commands - cancelled).filtered(lambda command: not command.cancel_requested).write({'cancel_requested': True})
        return cancelled

    @api.model
    def _count_inflight(self, genset):
        """Кількість команд генератора у станах ``sent/awaiting/retry`` (ліміт 2, ФВ-13)."""
        return self.sudo().search_count([('genset_id', '=', genset.id), ('state', 'in', INFLIGHT_STATES)])

    # ------------------------------------------------------------------ тривоги тех. адміністратору
    def _raise_tech(self, code, name, description=''):
        """Тривога тех. адміністратору (``tech=True``, рівень «попередження», ТР 2.8.4)."""
        return self.env['td.genset.alarm'].sudo()._raise(self.genset_id, code, 'warn', name,
                                                          description=description, source=self, tech=True)

    def _clear_tech_relay_alarms(self):
        """Успішний POST знімає тех. тривоги надсилання (403/409 формат/401), якщо вони активні."""
        Alarm = self.env['td.genset.alarm'].sudo()
        active = Alarm.search([('genset_id', '=', self.genset_id.id), ('code', 'in', list(TECH_RELAY_CODES)),
                               ('state', '!=', 'cleared')])
        for code in set(active.mapped('code')):
            Alarm._clear(self.genset_id, code, note=_('Команду прийнято ретранслятором.'))

    # ------------------------------------------------------------------ чатер
    def _subject(self):
        """«Команда Авто» (кнопка) / «Розклад: Авто» (2.8.5, AC-12)."""
        command = self._label('command')
        if self.source == 'button':
            return _('Команда %(command)s', command=command)
        return '%s: %s' % (self._label('source'), command)

    def _post_enqueue_message(self):
        """Запис у чатер про нову команду (або пакет «Ручний + Стоп») — без сповіщень (``_message_log``)."""
        if not self:
            return
        first = self[0]
        names = ' + '.join('«%s»' % command._label('command') for command in self)
        body = _('%(origin)s: %(commands)s — прийнято до надсилання (%(who)s).',
                 origin=first._label('source'), commands=names, who=first.requested_by or '')
        if first.late_transition_at:
            body = '%s (%s).' % (body.rstrip('.'), first._late_mark())
        first.genset_id.sudo()._message_log(body=body)

    def _post_final_message(self, body=None):
        """Повідомлення в чатер генератора з підтипом «Генератори: Команда» для фінальних станів (А.5, 2.8.5):
        «Команда Авто. Підтверджено контролером.», «Розклад: Ручний. Підтверджено контролером, зі спроби 2.» …"""
        self.ensure_one()
        if body is None:
            if self.state == 'done':
                suffix = _(', зі спроби %(attempt)s', attempt=self.attempt + 1) if self.attempt else ''
                body = _('%(subject)s. Підтверджено контролером%(suffix)s.', subject=self._subject(), suffix=suffix)
            elif self.state == 'done_late':
                body = _("%(subject)s. Підтверджено після відновлення зв'язку.", subject=self._subject())
            else:
                body = _('Команда «%(command)s» (%(origin)s): %(note)s.', command=self._label('command'),
                         origin=self._label('source'), note=self.result_note or self._label('state'))
        self.genset_id.sudo().message_post(body=body, subtype_xmlid='td_genset.mt_command')
