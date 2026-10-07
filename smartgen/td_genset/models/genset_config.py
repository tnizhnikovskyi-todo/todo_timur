# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас (поля, обмеження, get): W0.
"""Налаштування модуля ``td.genset.config`` (singleton ``td_genset.config_main``) і рівні ескалації
``td.genset.notify.level`` — ТР 2.3.8, 2.3.9; SPEC 5.8, 5.9, 9.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

NOTIFY_RULES = [
    ('always', 'Завжди'),
    ('not_quiet', 'Крім тихих годин'),
    ('chatter', 'Лише в чаті'),
]
MISSED_POLICIES = [
    ('until_next', 'Повторювати до наступного переходу'),
    ('window_only', 'Лише вікно повторів'),
]
RAW_REGS_MODES = [
    ('auto', 'Автоматично'),
    ('yes', 'Так'),
    ('no', 'Ні'),
]
JOURNAL_INTERVALS = (5, 10, 15, 30, 60)
DEFAULT_TANK_L = 145.0
MAINT_CHECKLIST = """<ul>
<li>Замінити оливу і масляний фільтр</li>
<li>Замінити паливний і повітряний фільтри (за регламентом)</li>
<li>Перевірити рівень і стан охолоджувальної рідини</li>
<li>Перевірити ремені, патрубки, витоки</li>
<li>Перевірити АКБ і зарядку (D+)</li>
<li>Тестовий пуск під навантаженням</li>
</ul>"""


class TdGensetConfig(models.Model):
    _name = 'td.genset.config'
    _description = 'Генератори: налаштування модуля'

    name = fields.Char(
        string='Назва', default='Налаштування генераторів', readonly=True,
        help='Один запис налаштувань модуля на всі генератори.')
    # ---- пульт і команди
    retry_every_min = fields.Integer(
        string='Повтор непідтвердженої команди кожні, хв', default=2,
        help='Як часто повторювати команду, яку контролер не підтвердив (≥ 1).')
    retry_window_min = fields.Integer(
        string='протягом, хв', default=10,
        help='Скільки всього повторювати, потім тривога (≥ інтервалу повтору).')
    test_minutes = fields.Integer(
        string='Тривалість тестового пуску, хв', default=3,
        help='Скільки триває тестовий пуск (1–60). Потім генератор повертається в режим за розкладом або таймером.')
    missed_transition_policy = fields.Selection(
        MISSED_POLICIES, string='Пропущений перехід', default='until_next',
        help='Що робити з командою переходу розкладу/таймера, яку не підтверджено за вікно повторів (ФВ-21).')
    late_retry_every_min = fields.Integer(
        string='Повтор після тривоги кожні, хв', default=5,
        help='Для «Повторювати до наступного переходу»: як часто повторювати після тривоги.')
    # ---- зв'язок
    link_lost_min = fields.Integer(
        string="Зв'язок втрачено через, хв", default=3,
        help="Через скільки хвилин без даних зв'язок вважається втраченим.")
    link_alarm_min = fields.Integer(
        string="Тривога про втрату зв'язку через, хв", default=10,
        help="Через скільки хвилин без зв'язку створюється тривога.")
    relay_unavailable_alarm_min = fields.Integer(
        string='Тривога «ретранслятор недоступний» через, хв', default=10,
        help='Через скільки хвилин недоступності API ретранслятора (таймаут/5xx) створюється тривога.')
    raw_regs_mode = fields.Selection(
        RAW_REGS_MODES, string='Читати сирі регістри', default='auto',
        help='Автоматично: raw=1, поки ретранслятор < 1.1.3 або в знімках немає ключів *_sensor_ohm; з образу '
             'беруться лише регістри 18/20/22 — оми датчиків (ФВ-31, AC-68).')
    # ---- журнал і зберігання
    journal_interval_min = fields.Integer(
        string='Журнал показань кожні, хв', default=15,
        help='Інтервал журналу показань: 5, 10, 15, 30 або 60 хв.')
    reading_retention_days = fields.Integer(
        string='Зберігати сирі знімки, днів', default=90,
        help='Скільки днів зберігати сирі знімки (журнальні і «зміна стану» — безстроково). 0 — не чистити.')
    catchup_summary = fields.Boolean(
        string='Підсумок догону в чатер', default=True,
        help='Після догону історії написати в чатер генератора «Догнано історію: N днів, M знімків, K подій».')
    # ---- сповіщення
    notify_crit = fields.Selection(
        NOTIFY_RULES, string='Критичні тривоги', default='always',
        help='Коли надсилати критичні тривоги.')
    notify_warn = fields.Selection(
        NOTIFY_RULES, string='Попередження', default='not_quiet',
        help='Коли надсилати попередження.')
    notify_info = fields.Selection(
        NOTIFY_RULES, string='Інформаційні події', default='chatter',
        help='Коли надсилати інформаційні події.')
    quiet_enabled = fields.Boolean(
        string='Тихі години', default=True,
        help='У тихі години правило «Крім тихих годин» відкладає сповіщення до їх кінця.')
    quiet_from = fields.Float(
        string='Тихі години з', default=22.0,
        help='Початок тихих годин (київський час).')
    quiet_to = fields.Float(
        string='Тихі години до', default=7.0,
        help='Кінець тихих годин (київський час).')
    level_ids = fields.One2many(
        'td.genset.notify.level', 'config_id', string='Ланцюжок ескалації',
        help='Загальний ланцюжок ескалації — один на всі генератори.')
    discuss_channel_id = fields.Many2one(
        'discuss.channel', string='Канал «Обговорень» для інформаційних подій', ondelete='set null',
        help='Необов\'язково: інформаційні події додатково публікуються в цей канал.')
    # ---- паливо
    fuel_min_stock_l = fields.Float(
        string='Мінімальний запас у каністрах, L', default=100.0,
        help='Нижче — тривога «Запас у каністрах нижчий за мінімальний».')
    canister_volume_default_l = fields.Float(
        string="Об'єм каністри за замовчуванням, L", default=20.0,
        help="Об'єм нової каністри за замовчуванням.")
    fuel_price_default = fields.Float(
        string='Ціна палива за замовчуванням, грн/л', default=0.0,
        help='Ціна палива за літр для нових надходжень.')
    fuel_partner_id = fields.Many2one(
        'res.partner', string='Постачальник палива', ondelete='set null',
        help='Постачальник палива за замовчуванням.')
    refuel_threshold_l = fields.Float(
        string='Поріг заправки, L', default=10.0,
        help='Приріст рівня, від якого фіксується подія «Заправка» (не менше 2 % бака).')
    drain_threshold_l = fields.Float(
        string='Поріг падіння рівня, L', default=10.0,
        help='Падіння рівня без роботи двигуна, від якого створюється тривога (не менше 2 % бака).')
    drain_window_min = fields.Integer(
        string='Вікно падіння рівня, хв', default=60,
        help='За скільки хвилин рахується падіння рівня без роботи двигуна.')
    low_fuel_pct = fields.Integer(
        string='Низький рівень палива, %', default=20,
        help='Нижче — тривога «Низький рівень палива» і активність «Долити паливо».')
    crank_battery_warn_v = fields.Float(
        string='АКБ при прокрутці нижче, V', default=21.0,
        help='Порада в аналітиці: напруга АКБ при прокрутці нижче цього значення.')
    # ---- ТО
    maint_first_hours_default = fields.Integer(
        string='Перше ТО для нових генераторів, мотогодин', default=30,
        help='Значення «Перше ТО» для нових генераторів.')
    maint_interval_hours_default = fields.Integer(
        string='Інтервал ТО для нових генераторів, мотогодин', default=250,
        help='Значення «Далі кожні, мотогодин» для нових генераторів.')
    maint_interval_months_default = fields.Integer(
        string='Інтервал ТО для нових генераторів, міс.', default=12,
        help='Значення «або раз на, міс.» для нових генераторів.')
    maint_team_id = fields.Many2one(
        'maintenance.team', string='Команда ТО', ondelete='set null',
        help='Команда «Обслуговування» для автоматичних заявок ТО.')
    maint_checklist = fields.Html(
        string='Перелік робіт ТО', default=MAINT_CHECKLIST,
        help='Копіюється в опис автоматичної заявки ТО.')
    # ---- технічне
    relay_unavailable_since = fields.Datetime(
        string='Ретранслятор недоступний з', readonly=True,
        help='Технічне: початок недоступності API для тривоги «ретранслятор недоступний» (2.6.2).')
    is_tech = fields.Boolean(
        string='Я тех. адміністратор', compute='_compute_is_tech',
        help='Поточний користувач може змінювати налаштування (інакше форма лише для перегляду).')

    # ------------------------------------------------------------------ singleton
    @api.model_create_multi
    def create(self, vals_list):
        if self.sudo().with_context(active_test=False).search_count([]) + len(vals_list) > 1:
            raise ValidationError(_('Налаштування модуля вже є — другий запис не створюється.'))
        return super().create(vals_list)

    @api.constrains('retry_every_min', 'retry_window_min', 'test_minutes', 'journal_interval_min',
                    'refuel_threshold_l', 'drain_threshold_l', 'reading_retention_days')
    def _check_values(self):
        if self.search_count([]) > 1:
            raise ValidationError(_('Налаштування модуля вже є — другий запис не створюється.'))
        tank = max(self.env['td.genset'].sudo().with_context(active_test=False).search([]).mapped('tank_volume_l')
                   or [DEFAULT_TANK_L])
        min_threshold = tank * 0.02
        for config in self:
            if config.retry_every_min < 1:
                raise ValidationError(_('Повтор команди — не рідше ніж раз на 1 хв.'))
            if config.retry_window_min < config.retry_every_min:
                raise ValidationError(_('Вікно повторів не може бути коротшим за інтервал повтору.'))
            if not 1 <= config.test_minutes <= 60:
                raise ValidationError(_('Тривалість тестового пуску — від 1 до 60 хв.'))
            if config.journal_interval_min not in JOURNAL_INTERVALS:
                raise ValidationError(_('Журнал показань — кожні 5, 10, 15, 30 або 60 хв.'))
            if config.reading_retention_days < 0:
                raise ValidationError(_('Кількість днів зберігання не може бути від\'ємною.'))
            for threshold in (config.refuel_threshold_l, config.drain_threshold_l):
                if threshold < min_threshold:
                    raise ValidationError(_('Поріг не може бути меншим за 2 %% об\'єму бака (≈ %(liters)s L для %(tank)s L).',
                                            liters=round(min_threshold), tank=round(tank)))

    @api.depends_context('uid')
    def _compute_is_tech(self):
        is_tech = self.env.user.has_group('td_genset.group_tech')
        for config in self:
            config.is_tech = is_tech

    @api.model
    def get(self):
        """Singleton налаштувань (``td_genset.config_main``); якщо запис видалено — перший наявний. Працює з W0."""
        config = self.env.ref('td_genset.config_main', raise_if_not_found=False)
        if not config:
            config = self.sudo().search([], limit=1)
        return config

    # ------------------------------------------------------------------ інтерфейси W1 (заглушки)
    def _quiet_now(self, dt=None):
        """Чи зараз (або ``dt``, UTC naive) тихі години за київським часом.

        TODO: W1 — AC-42. Заглушка W0: ``False``.
        """
        return False

    def _quiet_end(self, dt=None):
        """Кінець поточних тихих годин (UTC naive) — для відкладеної ескалації.

        TODO: W1 — AC-42. Заглушка W0: ``None``.
        """
        return None

    def action_send_test_notification(self):
        """Тестове сповіщення рівню 1 ланцюжка (AC-44).

        TODO: W1 — AC-44. Заглушка W0: нічого не надсилає.
        """
        return False


class TdGensetNotifyLevel(models.Model):
    _name = 'td.genset.notify.level'
    _description = 'Генератори: рівень ескалації'
    _order = 'sequence, id'

    config_id = fields.Many2one(
        'td.genset.config', string='Налаштування', required=True, index=True, ondelete='cascade',
        default=lambda self: self.env['td.genset.config'].get(),
        help='Налаштування модуля, до яких належить рівень.')
    sequence = fields.Integer(
        string='Порядок', default=10,
        help='Порядок рівня в ланцюжку.')
    name = fields.Char(
        string='Рівень', required=True,
        help='Назва рівня: «Черговий», «Відповідальний за об\'єкт», «Керівник».')
    user_id = fields.Many2one(
        'res.users', string='Хто', domain=[('share', '=', False)], ondelete='set null',
        help='Хто отримує тривогу на цьому рівні. Рівень без користувача ескалація пропускає (попередження в логах).')
    delay_min = fields.Integer(
        string='Через, хв', default=0,
        help='Через скільки хвилин після тривоги, якщо її досі не прийняли. Рівень 1 — 0 («одразу»).')

    @api.constrains('sequence', 'delay_min', 'config_id')
    def _check_delays(self):
        """``delay_min`` не спадає за порядком; рівень 1 — 0 («одразу»)."""
        for config in self.mapped('config_id'):
            levels = config.level_ids.sorted(lambda level: (level.sequence, level.id))
            if levels and levels[0].delay_min != 0:
                raise ValidationError(_('Перший рівень ланцюжка сповіщається одразу (0 хв).'))
            delays = levels.mapped('delay_min')
            if any(later < earlier for earlier, later in zip(delays, delays[1:])):
                raise ValidationError(_('Затримка рівнів не може зменшуватися за порядком ланцюжка.'))
