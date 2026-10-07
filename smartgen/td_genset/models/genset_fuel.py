# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (моделі, поля, заглушки): W0.
"""Паливо (ТР 2.3.11, 2.9; SPEC 5.12) і ТО (ТР 2.9) + ``td.genset`` (inherit): KPI палива, калібрування, ТО.

Моделі: ``td.genset.storage.location``, ``td.genset.canister``, ``td.genset.fuel.move``,
``td.genset.refuel``, ``td.genset.fuel.calibration``. Поля і ``_sql_constraints`` — за SPEC (W0);
бізнес-логіка (рухи, звірка, інтерполяція, ТО) — W4.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

FUEL_KPI_FIELDS = (
    'canister_liters', 'fuel_in_canisters_l', 'fuel_total_l', 'fuel_hours_left', 'fuel_used_7d_l',
    'fuel_used_30d_l', 'fuel_rate_lph_7d', 'fuel_rate_lph_30d', 'fuel_rate_lpkwh_7d', 'fuel_rate_lpkwh_30d',
    'fuel_per_day_7d', 'fuel_per_day_30d', 'fuel_cost_7d', 'fuel_cost_30d',
)
MOVE_KINDS = [
    ('in', 'Надходження'),
    ('out', 'Заправка генератора'),
    ('fix', 'Коригування'),
    ('loc', 'Переміщення'),
    ('off', 'Списання'),
]
REFUEL_SOURCES = [
    ('cans', 'З каністр'),
    ('other', 'Інше джерело'),
]
SENSOR_STATES = [
    ('waiting', 'Очікує показання'),
    ('confirmed', 'Підтверджено за рівнем'),
    ('by_level', 'За рівнем (різниця)'),
    ('unconfirmed', 'Не підтверджено'),
    ('drain', 'Падіння без роботи'),
]
CANISTER_STATES = [
    ('full', 'Повна'),
    ('part', 'Частково'),
    ('empty', 'Порожня'),
]


def _config(env):
    return env.ref('td_genset.config_main', raise_if_not_found=False)


class TdGensetStorageLocation(models.Model):
    _name = 'td.genset.storage.location'
    _description = 'Генератори: місце зберігання палива'
    _order = 'name'

    name = fields.Char(
        string='Назва', required=True,
        help='Назва місця зберігання каністр (склад, підвал, гараж …).')
    canister_ids = fields.One2many(
        'td.genset.canister', 'location_id', string='Каністри',
        help='Активні каністри в цьому місці.')
    canister_count = fields.Integer(
        string='Каністр', compute='_compute_totals',
        help='Скільки активних каністр тут лежить.')
    liters = fields.Float(
        string='Палива, L', compute='_compute_totals',
        help='Σ літрів активних каністр у цьому місці.')
    active = fields.Boolean(
        string='Активне', default=True,
        help='Архівоване місце не пропонується для нових каністр.')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Місце зберігання з такою назвою вже є.'),
    ]

    @api.depends('canister_ids.liters', 'canister_ids.active')
    def _compute_totals(self):
        for location in self:
            location.canister_count = len(location.canister_ids)
            location.liters = sum(location.canister_ids.mapped('liters'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_has_canisters(self):
        """«У «…» є каністри — спершу перемістіть їх.» (AC-50). TODO: W4 — уточнити (архівні каністри)."""
        for location in self:
            if location.with_context(active_test=False).canister_ids:
                raise ValidationError(_('У «%(name)s» є каністри — спершу перемістіть їх.', name=location.name))


class TdGensetCanister(models.Model):
    _name = 'td.genset.canister'
    _description = 'Генератори: каністра'
    _order = 'name'

    name = fields.Char(
        string='Номер', readonly=True, copy=False,
        help='Номер каністри з послідовності «К-01», «К-02» … (присвоюється при створенні).')
    volume_l = fields.Float(
        string="Об'єм, L", required=True,
        default=lambda self: (_config(self.env).sudo().canister_volume_default_l if _config(self.env) else 20.0),
        help="Об'єм каністри, 5–60 L (за замовчуванням — з налаштувань).")
    liters = fields.Float(
        string='У каністрі, L', default=0.0,
        help='Скільки палива зараз у каністрі. Зміна через форму записується в рух запасу як коригування.')
    location_id = fields.Many2one(
        'td.genset.storage.location', string='Місце', required=True, ondelete='restrict', index=True,
        help='Де зберігається каністра. Зміна через форму записується як переміщення.')
    state = fields.Selection(
        CANISTER_STATES, string='Стан', compute='_compute_state', store=True, index=True,
        help='Повна — літрів не менше за об\'єм; порожня — 0 L; інакше частково.')
    move_ids = fields.One2many(
        'td.genset.fuel.move', 'canister_id', string='Рухи',
        help='Рух запасу по цій каністрі.')
    active = fields.Boolean(
        string='Активна', default=True,
        help='Списання каністри = архів.')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Каністра з таким номером уже є.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('td.genset.canister') or _('Нова')
        return super().create(vals_list)

    @api.depends('liters', 'volume_l')
    def _compute_state(self):
        for canister in self:
            if canister.liters <= 0:
                canister.state = 'empty'
            elif canister.liters >= canister.volume_l:
                canister.state = 'full'
            else:
                canister.state = 'part'

    @api.constrains('volume_l', 'liters')
    def _check_volume_liters(self):
        for canister in self:
            if not 5 <= canister.volume_l <= 60:
                raise ValidationError(_("Об'єм каністри має бути від 5 до 60 L."))
            if canister.liters < 0 or canister.liters > canister.volume_l:
                raise ValidationError(_("У каністрі може бути від 0 до %(volume)s L.", volume=canister.volume_l))

    def action_write_off(self):
        """Списання (друге підтвердження — ``confirm`` у поданні): рух ``off`` «Списано К-04 (разом із 5 L)», архів.

        TODO: W4 — AC-49. Заглушка W0: перевірка групи, нічого не змінює.
        """
        self.env['td.genset']._td_check_group('td_genset.group_admin')
        return False


class TdGensetFuelMove(models.Model):
    _name = 'td.genset.fuel.move'
    _description = 'Генератори: рух запасу палива'
    _order = 'date desc, id desc'

    date = fields.Datetime(
        string='Дата', required=True, default=fields.Datetime.now, index=True,
        help='Коли відбувся рух палива.')
    kind = fields.Selection(
        MOVE_KINDS, string='Вид', required=True, index=True,
        help='Надходження, заправка генератора, коригування, переміщення або списання.')
    canister_id = fields.Many2one(
        'td.genset.canister', string='Каністра', ondelete='restrict', index=True,
        help='Каністра, якої стосується рух.')
    genset_id = fields.Many2one(
        'td.genset', string='Генератор', ondelete='set null', index=True,
        help='Генератор — для заправки (вид «Заправка генератора»).')
    refuel_id = fields.Many2one(
        'td.genset.refuel', string='Заправка', ondelete='set null', index=True,
        help='Запис заправки, до якого належить рух.')
    receipt_key = fields.Char(
        string='Надходження', index=True,
        help='Групує рухи одного надходження палива.')
    liters_delta = fields.Float(
        string='Δ, L', required=True,
        help='Зміна запасу зі знаком: + надходження, − витрата.')
    currency_id = fields.Many2one(
        'res.currency', string='Валюта', default=lambda self: self.env.company.currency_id,
        help='Валюта ціни (валюта компанії, UAH).')
    price_unit = fields.Monetary(
        string='Ціна за літр', currency_field='currency_id',
        default=lambda self: (_config(self.env).sudo().fuel_price_default if _config(self.env) else 0.0),
        help='Ціна палива за літр для надходжень; вартість витрати — за останньою ціною надходження.')
    partner_id = fields.Many2one(
        'res.partner', string='Постачальник', ondelete='set null',
        default=lambda self: (_config(self.env).sudo().fuel_partner_id if _config(self.env) else False),
        help='Постачальник палива.')
    location_from_id = fields.Many2one(
        'td.genset.storage.location', string='Звідки', ondelete='set null',
        help='Місце, звідки перемістили каністру.')
    location_to_id = fields.Many2one(
        'td.genset.storage.location', string='Куди', ondelete='set null',
        help='Місце, куди перемістили каністру.')
    user_id = fields.Many2one(
        'res.users', string='Хто', default=lambda self: self.env.user, ondelete='set null',
        help='Хто записав рух.')
    note = fields.Char(
        string='Примітка',
        help='Пояснення до руху («+20 L · АЗС … · 54,90 грн/л»).')
    balance_after = fields.Float(
        string='Залишок після, L', compute='_compute_balance_after',
        help='Запас у каністрах після цього руху (підсумок по даті).')

    @api.depends('date', 'liters_delta')
    def _compute_balance_after(self):
        """Підсумок запасу по даті. TODO: W4 — AC-48, AC-49. Заглушка W0: 0."""
        for move in self:
            move.balance_after = 0.0

    @api.model
    def _post(self, kind, liters_delta, canister=None, genset=None, refuel=None, **vals):
        """Єдина точка створення руху: оновлює ``canister.liters``, ``receipt_key``; після руху —
        ``genset._check_fuel_stock()``.

        :return: запис ``td.genset.fuel.move``.
        TODO: W4 — AC-48, AC-49, AC-51. Заглушка W0: порожній recordset.
        """
        return self.browse()


class TdGensetRefuel(models.Model):
    _name = 'td.genset.refuel'
    _description = 'Генератори: заправка'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Номер', readonly=True, copy=False,
        help='Номер заправки з послідовності «ЗПР-…» (присвоюється при створенні).')
    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, ondelete='cascade', index=True,
        help='Який генератор заправили.')
    date = fields.Datetime(
        string='Дата', required=True, default=fields.Datetime.now, index=True,
        help='Коли заправили генератор.')
    source = fields.Selection(
        REFUEL_SOURCES, string='Джерело', required=True, default='cans',
        help='З каністр (рухи запасу) або з іншого джерела (паливовоз, АЗС).')
    source_note = fields.Char(
        string='Звідки (примітка)',
        help='Звідки залили паливо, якщо не з каністр: паливовоз, АЗС тощо.')
    liters = fields.Float(
        string='Залито, L', required=True,
        help="Скільки літрів залито в бак. Більше 0 і не більше вільного об'єму бака.")
    canister_ids = fields.Many2many(
        'td.genset.canister', string='Каністри',
        help='З яких каністр залили (часткові — першими).')
    move_ids = fields.One2many(
        'td.genset.fuel.move', 'refuel_id', string='Рухи запасу',
        help='Рухи «Заправка генератора» по каністрах.')
    level_before_pct = fields.Float(
        string='Рівень до, %', readonly=True,
        help='Рівень у баку до заправки (зі знімків при звірці).')
    level_before_l = fields.Float(
        string='Рівень до, L', readonly=True,
        help='Літрів у баку до заправки (зі знімків при звірці).')
    level_after_pct = fields.Float(
        string='Рівень після, %', readonly=True,
        help='Рівень у баку після заправки (зі знімків при звірці).')
    level_after_l = fields.Float(
        string='Рівень після, L', readonly=True,
        help='Літрів у баку після заправки (зі знімків при звірці).')
    sensor_state = fields.Selection(
        SENSOR_STATES, string='Звірка', default='waiting', index=True,
        help='Підтвердження датчиком рівня: подія «Заправка» у вікні ±2 год → «Підтверджено за рівнем» '
             '(різниця ≤ 2 % бака, ≤ 1 L з калібруванням) або «За рівнем (різниця)»; 2 год без події → '
             '«Не підтверджено» + тривога.')
    event_id = fields.Many2one(
        'td.genset.event', string='Подія рівня', ondelete='set null',
        help='Подія «Заправка», з якою звірено запис.')
    user_id = fields.Many2one(
        'res.users', string='Хто записав', default=lambda self: self.env.user, ondelete='set null',
        help='Хто записав заправку.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('td.genset.refuel') or _('Нова')
        return super().create(vals_list)

    @api.constrains('liters')
    def _check_liters(self):
        for refuel in self:
            if refuel.liters <= 0:
                raise ValidationError(_('Кількість залитого палива має бути більшою за 0.'))

    @api.model
    def _reconcile_pending(self):
        """Звірка записів ``sensor_state='waiting'`` з подіями ``refuel`` у вікні ±2 год (2.9); після 2 год —
        ``unconfirmed`` + ``_raise('refuel_unconfirmed')``. Викликається з ``cron_scheduler`` і обробника подій.

        TODO: W4 — AC-51. Заглушка W0: нічого не робить.
        """
        return None


class TdGensetFuelCalibration(models.Model):
    _name = 'td.genset.fuel.calibration'
    _description = 'Генератори: точка калібрування датчика палива'
    _order = 'genset_id, ohm'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, ondelete='cascade', index=True,
        help='Генератор, датчик якого калібрується.')
    ohm = fields.Float(
        string='Опір, Ом', required=True, digits=(16, 1),
        help='Опір датчика рівня палива в цій точці, крок 0,1 Ом.')
    liters = fields.Float(
        string='Літрів у баку', required=True,
        help="Скільки літрів у баку при цьому опорі (0 … об'єм бака).")
    note = fields.Char(
        string='Примітка',
        help='Звідки точка: крива датчика в налаштуваннях контролера або реальна заправка.')

    _sql_constraints = [
        ('ohm_uniq', 'unique(genset_id, ohm)', 'Точка з таким опором уже є в калібруванні цього генератора.'),
    ]

    @api.constrains('ohm', 'liters', 'genset_id')
    def _check_calibration(self):
        """0 ≤ L ≤ об'єм бака; монотонність кривої — TODO: W4 (AC-69)."""
        for point in self:
            if point.liters < 0 or point.liters > point.genset_id.tank_volume_l:
                raise ValidationError(_("Літрів у точці калібрування має бути від 0 до об'єму бака."))


class TdGensetFuel(models.Model):
    """``td.genset`` (inherit): KPI палива, мінімальний запас, калібрування, ТО — ТР 2.9."""
    _inherit = 'td.genset'

    def _compute_fuel_kpi(self):
        """KPI вкладки «Паливо» і smart-кнопка «У каністрах» (``_fuel_stats(7/30)``, каністри).

        TODO: W4 — AC-47, AC-52. Заглушка W0: нулі; запас вважається в нормі.
        """
        for genset in self:
            for name in FUEL_KPI_FIELDS:
                genset[name] = 0.0
            genset.fuel_min_stock_ok = True

    def _fuel_stats(self, days):
        """KPI витрати за період: ``{'used_l', 'hours', 'kwh', 'lph', 'lpkwh', 'per_day', 'cost'}``
        (``_read_group`` по подіях ``run``).

        TODO: W4 — AC-47, AC-52. Заглушка W0: нулі.
        """
        return {'used_l': 0.0, 'hours': 0.0, 'kwh': 0.0, 'lph': 0.0, 'lpkwh': 0.0, 'per_day': 0.0, 'cost': 0.0}

    def _check_fuel_stock(self):
        """Мінімальний запас у каністрах: нижче ``config.fuel_min_stock_l`` → ``_raise('fuel_stock_low')``,
        інакше ``_clear``. Викликається після кожного руху і з ``cron_scheduler``.

        TODO: W4 — AC-47. Заглушка W0: нічого не робить.
        """
        return None

    def _liters_from_ohm(self, ohm):
        """Лінійна інтерполяція Ом → L за ``fuel_calibration_ids`` (за межами — крайні точки; округлення 0,1 L);
        ``None``, якщо калібрування не заповнене (< 2 точок) або ``ohm`` порожній.

        TODO: W4 — AC-69. Заглушка W0: ``None`` (літри рахуються за %).
        """
        return None

    @api.depends('fuel_calibration_ids', 'fuel_calibration_ids.ohm', 'fuel_calibration_ids.liters')
    def _compute_fuel_calibrated(self):
        """Калібрування заповнено — щонайменше 2 точки (ФВ-31). TODO: W4 — AC-69 (уточнення за потреби)."""
        for genset in self:
            genset.fuel_calibrated = len(genset.fuel_calibration_ids) >= 2

    def action_recompute_liters(self):
        """«Перерахувати літри» (``group_tech``): ``fuel_liters``/``fuel_source`` усіх знімків генератора за
        поточним калібруванням і об'ємом бака, партіями по 10 000 (``_trigger()`` + ``_notify_progress``).

        TODO: W4 — AC-69. Заглушка W0: перевірка групи, нічого не перераховує.
        """
        self._td_check_group('td_genset.group_tech')
        return False

    def _ensure_equipment(self):
        """Створення/синхронізація ``maintenance.equipment`` («Генератор · <назва>», категорія і команда
        «Генератори», ``technician_user_id = user_id``, ``td_genset_id``); архівація разом з генератором.

        TODO: W4 — AC-53. Заглушка W0: нічого не робить.
        """
        return None

    def _compute_maint(self):
        """``maint_hours_left``, ``maint_due_date``, ``maint_state`` (ТР 2.9).

        TODO: W4 — AC-53, AC-54. Заглушка W0: ТО в нормі.
        """
        for genset in self:
            genset.maint_hours_left = 0.0
            genset.maint_due_date = False
            genset.maint_state = 'ok'

    def _check_maintenance(self):
        """``maint_state == 'overdue'`` і немає відкритої заявки → заявка ТО + ``_raise('maintenance_due')`` +
        активність «Перевірити генератор» відповідальному.

        TODO: W4 — AC-53. Заглушка W0: нічого не робить.
        """
        return None
