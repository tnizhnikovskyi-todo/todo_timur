# Part of td_genset (ToDo). Власник файлу: W2 «Керування». Каркас (поля, заглушки): W0.
"""Команда ``td.genset.command`` — стан-машина ТР 2.6.3, А.5; SPEC 5.5, 9.

Створення команди — лише через ``_enqueue`` / ``_enqueue_batch`` (майстер, таймер, тест, планувальник).
"""
from odoo import _, api, fields, models

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
        help='Звідки прийшла команда; у ретранслятор передається як «odoo:<джерело>».')
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
        help='Номер повтору підтвердження.')
    transport_attempt = fields.Integer(
        string='Транспортна спроба', default=0,
        help='Повтори надсилання після 409 / 5xx / таймауту.')
    max_attempts = fields.Integer(
        string='Макс. спроб',
        help='retry_window_min / retry_every_min на момент створення — «Спроба N з M».')
    first_sent_at = fields.Datetime(
        string='Перша спроба',
        help='Перша спроба POST, навіть невдала — від неї відлічується вікно повторів (А.5).')
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

    # ------------------------------------------------------------------ інтерфейси W2 (заглушки)
    @api.model
    def _enqueue(self, genset, command, source, requested_by, batch_key=None, late_transition_at=None,
                 target_breaker_closed=None):
        """Єдина точка створення команди: ``requested_by`` — ``res.users`` або рядок («Odoo: розклад»);
        стан ``to_send``/``queued_odoo`` (ліміт 2), ``next_attempt_at=now``, ``max_attempts``, запис у чатер;
        ``env.ref('td_genset.cron_commands')._trigger()``. Права перевіряє викликач; метод працює через ``sudo()``.

        :return: запис ``td.genset.command``.
        TODO: W2 — AC-12, AC-19, AC-20, AC-21. Заглушка W0: порожній recordset (нічого не створює).
        """
        return self.browse()

    @api.model
    def _enqueue_batch(self, genset, commands, source, requested_by, late_transition_at=None):
        """Пакет (``batch_key = f"{genset.id}-{uuid4().hex[:8]}"``, ``sequence`` 1..n), ``_enqueue`` для кожної.

        :return: recordset команд.
        TODO: W2 — AC-19. Заглушка W0: порожній recordset.
        """
        return self.browse()

    @api.model
    def _cron_process_commands(self):
        """Точка входу cron ``cron_commands`` (1 хв, priority 1, + ``_trigger()``): вибірка
        ``FOR NO KEY UPDATE SKIP LOCKED`` (А.7), ``_step()`` для кожної, ``_trigger(at=min(next_attempt_at))``.

        TODO: W2 — AC-12…AC-23, AC-26, AC-66, AC-67. Заглушка W0: нічого не робить (успішно).
        """
        return None

    def _step(self):
        """Один крок стан-машини А.5 для ``self`` (``ensure_one``); ``result_note``, ``_notify_bus('command')``.

        TODO: W2 — AC-12…AC-18. Заглушка W0: нічого не робить.
        """
        return None

    def _precheck(self):
        """Перевірки ``to_send`` (``commands_allowed``, ``remote_lock``, ``relay_commands_enabled``, зв'язок,
        «лише на переходах», запізнілий перехід).

        :return: новий стан (str) або ``None`` = надсилати.
        TODO: W2 — AC-13, AC-16, AC-21, AC-23, AC-66. Заглушка W0: ``None``.
        """
        return None

    def _check_confirmation(self, reading):
        """Умова ФВ-9 для ``self.command`` за знімком (``reading.ts ≥ done_at``).

        :rtype: bool
        TODO: W2 — AC-12, AC-21, AC-26. Заглушка W0: ``False``.
        """
        return False

    @api.model
    def _cancel_pending(self, genset, reason, sources=('schedule', 'timer', 'exception', 'test')):
        """Незавершені команди цих джерел → ``cancelled`` з ``result_note``.

        TODO: W2 — AC-28, AC-31, AC-32. Заглушка W0: нічого не робить.
        """
        return None

    @api.model
    def _count_inflight(self, genset):
        """Кількість команд генератора у станах ``sent/awaiting/retry`` (ліміт 2, ФВ-13). Працює з W0."""
        return self.sudo().search_count([('genset_id', '=', genset.id), ('state', 'in', INFLIGHT_STATES)])
