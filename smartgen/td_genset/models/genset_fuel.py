# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (моделі, поля): W0.
"""Паливо (ТР 2.3.11, 2.9; SPEC 5.12) і ТО (ТР 2.9) + ``td.genset`` (inherit): KPI палива, калібрування, ТО.

Моделі: ``td.genset.storage.location``, ``td.genset.canister``, ``td.genset.fuel.move``,
``td.genset.refuel``, ``td.genset.fuel.calibration``.

* Рух запасу створює лише ``td.genset.fuel.move._post`` — і лише він змінює каністру (літри, місце, архів).
  Зміна літрів або місця каністри через форму (``write``) записує рух «Коригування» / «Переміщення»;
  архівація каністри = списання (рух «Списання»). Запас у каністрах завжди = Σ рухів.
* Звірка заправок з подіями «Заправка» — ``td.genset.refuel._reconcile_pending`` (cron розкладу, майстер).
* Літри за калібруванням датчика — ``td.genset._liters_from_ohm``; перерахунок історії —
  ``action_recompute_liters`` (перша партія одразу, решта — cron ``cron_recompute_liters``).
* ТО за мотогодинами — ``_compute_maint``, ``_check_maintenance``; обладнання — ``_ensure_equipment``.
"""
import logging
from datetime import date, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL, float_compare, float_is_zero, float_round, split_every

_logger = logging.getLogger(__name__)

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

RECOMPUTE_BATCH = 10000                 # знімків за один крок перерахунку літрів (ТР 2.9)
RECOMPUTE_SQL_CHUNK = 1000              # рядків в одному UPDATE … FROM (VALUES …)
REFUEL_WINDOW = timedelta(hours=2)      # вікно звірки заправки з подією «Заправка» (ФВ-33)
REFUEL_RECHECK_DAYS = 7                 # «не підтверджені» ще звіряються з подіями, що прийшли із запізненням
REFUEL_TOLERANCE_SHARE = 0.02           # допуск звірки без калібрування — 2 % об'єму бака
REFUEL_TOLERANCE_CALIBRATED_L = 1.0     # допуск звірки з калібруванням датчика — 1 L
MAINT_DUE_SHARE = 0.1                   # «Скоро ТО»: лишилось ≤ 10 % інтервалу мотогодин …
MAINT_DUE_DAYS = 30                     # … або ≤ 30 днів до дати ТО
MAINT_ACTIVITY_SUMMARY = 'Термін ТО'
KYIV = pytz.timezone('Europe/Kyiv')
MINUS = '−'

# Контекст руху запасу: каністру змінює лише _post (CTX_POSTING), форма вже змінила каністру (CTX_APPLIED),
# перевірку мінімального запасу зробить викликач один раз (CTX_DEFER_STOCK).
CTX_POSTING = 'td_fuel_posting'
CTX_APPLIED = 'td_fuel_move_applied'
CTX_DEFER_STOCK = 'td_fuel_defer_stock_check'


def _config(env):
    return env.ref('td_genset.config_main', raise_if_not_found=False)


def _record_id(value):
    """Запис або id → id (``False`` для порожнього)."""
    if isinstance(value, models.BaseModel):
        return value.id
    return value or False


def fmt_num(value, digits=None):
    """Число для текстів українською: «1 098», «54,90», «7», «6,5»; від'ємне — зі знаком «−».

    :param int digits: знаків після коми; ``None`` — 0 для цілих, інакше 1.
    """
    value = float(value or 0.0)
    if digits is None:
        digits = 0 if float_is_zero(value - round(value), precision_digits=2) else 1
    value = float_round(value, precision_digits=digits)
    text = '{:,.{digits}f}'.format(abs(value), digits=digits).replace(',', ' ').replace('.', ',')
    return MINUS + text if value < 0 else text


def fmt_signed(value, digits=None):
    """«+20», «−2», «0»."""
    text = fmt_num(value, digits)
    return '+' + text if float_compare(value or 0.0, 0.0, precision_digits=2) > 0 else text


def plural(count, forms):
    """Форма слова за числом: ``forms = (одна, дві–чотири, п'ять)`` — 1 каністра, 2 каністри, 5 каністр."""
    number = abs(int(round(count or 0)))
    if number % 10 == 1 and number % 100 != 11:
        return forms[0]
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return forms[1]
    return forms[2]


def kyiv_hhmm(value):
    """UTC naive → «HH:MM» за київським часом."""
    return pytz.utc.localize(value).astimezone(KYIV).strftime('%H:%M') if value else ''


def interpolate_liters(points, ohm):
    """Лінійна інтерполяція Ом → L за відсортованими точками ``[(ohm, liters), …]`` (щонайменше 2);
    за межами таблиці — значення крайньої точки; округлення до 0,1 L (ТР 2.9)."""
    ohm = float(ohm)
    if ohm <= points[0][0]:
        liters = points[0][1]
    elif ohm >= points[-1][0]:
        liters = points[-1][1]
    else:
        liters = points[-1][1]
        for (ohm_a, liters_a), (ohm_b, liters_b) in zip(points, points[1:]):
            if ohm_a <= ohm <= ohm_b:
                liters = liters_a + (ohm - ohm_a) * (liters_b - liters_a) / (ohm_b - ohm_a)
                break
    return float_round(liters, precision_digits=1)


def liters_from_pct(fuel_level, tank_volume_l):
    """Літри за % контролера: ``round(fuel_level / 100 × об'єм бака)`` — як у compute знімка (ТР 2.9)."""
    return float(round((fuel_level or 0.0) / 100.0 * (tank_volume_l or 0.0)))


def pour_plan(canisters, need):
    """Розлив з каністр (ФВ-33): часткові першими (менше літрів — раніше), разом не більше ``need``.

    :return: ``[(каністра, літри), …]`` — лише каністри, з яких реально наливають.
    """
    plan = []
    left = float_round(need or 0.0, precision_digits=2)
    for canister in canisters.sorted(lambda can: (can.liters, can.name or '')):
        if float_compare(left, 0.0, precision_digits=2) <= 0:
            break
        quantity = float_round(min(canister.liters, left), precision_digits=2)
        if float_compare(quantity, 0.0, precision_digits=2) > 0:
            plan.append((canister, quantity))
            left = float_round(left - quantity, precision_digits=2)
    return plan


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
        """Місце з каністрами не видаляється (AC-50): з активними — «спершу перемістіть їх»; лише зі
        списаними (історія руху запасу) — архівувати замість видалення."""
        canisters = self.env['td.genset.canister'].sudo().with_context(active_test=False).search(
            [('location_id', 'in', self.ids)])
        for location in self:
            own = canisters.filtered(lambda canister: canister.location_id == location)
            if own.filtered('active'):
                raise UserError(_('У «%(name)s» є каністри — спершу перемістіть їх.', name=location.name))
            if own:
                raise UserError(_('У «%(name)s» є списані каністри з історією руху запасу — архівуйте місце '
                                  'замість видалення.', name=location.name))


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
        """Номер з послідовності; паливо, з яким каністру створено поза рухом запасу, записується рухом
        «Коригування» (запас у каністрах = Σ рухів)."""
        posting = self.env.context.get(CTX_POSTING)
        initial = []
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('td.genset.canister') or _('Нова')
            initial.append(0.0 if posting else (vals.pop('liters', 0.0) or 0.0))
        canisters = super().create(vals_list)
        moves = self.env['td.genset.fuel.move'].with_context(**{CTX_DEFER_STOCK: True})
        posted = False
        for canister, liters in zip(canisters, initial):
            if not float_is_zero(liters, precision_digits=2):
                moves._post('fix', liters, canister=canister)
                posted = True
        if posted:
            self.env['td.genset']._check_fuel_stock()
        return canisters

    def write(self, vals):
        """Зміна літрів → рух «Коригування К-04 7 → 5 L (−2 L)»; зміна місця → «Переміщення К-04 Щитова →
        Склад»; архівація → списання (рух «Списання»). Межі 0…об'єм — ``_check_volume_liters`` (AC-49)."""
        if self.env.context.get(CTX_POSTING):
            return super().write(vals)
        archive = 'active' in vals and not vals['active']
        if not ({'liters', 'location_id'} & set(vals) or archive):
            return super().write(vals)
        vals = dict(vals)
        if archive:
            del vals['active']
        before = {canister.id: (canister.liters, canister.location_id) for canister in self}
        result = super().write(vals) if vals else True
        moves = self.env['td.genset.fuel.move'].with_context(**{CTX_DEFER_STOCK: True})
        applied = moves.with_context(**{CTX_APPLIED: True})
        for canister in self:
            old_liters, old_location = before[canister.id]
            if 'liters' in vals and float_compare(canister.liters, old_liters, precision_digits=2):
                applied._post('fix', canister.liters - old_liters, canister=canister)
            if 'location_id' in vals and canister.location_id != old_location:
                applied._post('loc', 0.0, canister=canister, location_from_id=old_location.id,
                              location_to_id=canister.location_id.id)
            if archive and canister.active:
                moves._post('off', -canister.liters, canister=canister)
        self.env['td.genset']._check_fuel_stock()
        return result

    @api.depends('liters', 'volume_l')
    def _compute_state(self):
        for canister in self:
            if float_compare(canister.liters, 0.0, precision_digits=2) <= 0:
                canister.state = 'empty'
            elif float_compare(canister.liters, canister.volume_l, precision_digits=2) >= 0:
                canister.state = 'full'
            else:
                canister.state = 'part'

    @api.constrains('volume_l', 'liters')
    def _check_volume_liters(self):
        """Об'єм 5–60 L (рішення 1.9: каністри 10 і 20 L); у каністрі 0…об'єм (AC-49)."""
        for canister in self:
            if not 5 <= canister.volume_l <= 60:
                raise ValidationError(_("Об'єм каністри має бути від 5 до 60 L."))
            if float_compare(canister.liters, 0.0, precision_digits=2) < 0 \
                    or float_compare(canister.liters, canister.volume_l, precision_digits=2) > 0:
                raise ValidationError(_('У каністрі %(name)s може бути від 0 до %(volume)s L.',
                                        name=canister.name or '', volume=fmt_num(canister.volume_l)))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_has_moves(self):
        """Каністру з історією руху запасу не видаляють — її списують (рух «Списання» + архів)."""
        if self.env['td.genset.fuel.move'].sudo().search_count([('canister_id', 'in', self.ids)], limit=1):
            raise UserError(_('Каністру з історією руху запасу не видаляють — спишіть її кнопкою «Списати».'))

    def action_write_off(self):
        """«Списати» (друге підтвердження — ``confirm`` кнопки в поданні): рух «Списано К-04 (разом із 5 L)»,
        каністра архівується з 0 L (AC-49). Права — ``group_admin`` (інакше ``AccessError``)."""
        self.env['td.genset']._td_check_group('td_genset.group_admin')
        moves = self.env['td.genset.fuel.move'].with_context(**{CTX_DEFER_STOCK: True})
        for canister in self.filtered('active'):
            moves._post('off', -canister.liters, canister=canister)
        self.env['td.genset']._check_fuel_stock()
        return True


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
        help='Пояснення до руху («+20 L · АЗС … · 54,90 грн/л · 1 098 грн»).')
    balance_after = fields.Float(
        string='Залишок після, L', compute='_compute_balance_after',
        help='Запас у каністрах після цього руху (підсумок по даті).')

    @api.depends('date', 'liters_delta')
    def _compute_balance_after(self):
        """Запас у каністрах після руху: Σ ``liters_delta`` усіх рухів до цього включно (за датою, далі id)."""
        move_ids = [move_id for move_id in self.ids if move_id]
        balances = {}
        if move_ids:
            self.flush_model(['date', 'liters_delta'])
            self.env.cr.execute(SQL(
                """SELECT id, balance
                     FROM (SELECT id, SUM(liters_delta) OVER (ORDER BY date, id ROWS UNBOUNDED PRECEDING) AS balance
                             FROM td_genset_fuel_move) AS moves
                    WHERE id IN %s""",
                tuple(move_ids),
            ))
            balances = dict(self.env.cr.fetchall())
        for move in self:
            move.balance_after = float_round(balances.get(move._origin.id) or 0.0, precision_digits=2)

    @api.model
    def _post(self, kind, liters_delta, canister=None, genset=None, refuel=None, **vals):
        """Єдина точка створення руху запасу (ТР А.11) — і єдина, що змінює каністру:

        * ``in`` / ``out`` / ``fix`` — ``canister.liters += liters_delta``; ``off`` — літри 0 і архів
          (``liters_delta`` = −залишок каністри); ``loc`` — ``canister.location_id = location_to_id`` (Δ = 0);
        * контекст ``td_fuel_move_applied`` — каністру вже змінено (``write`` форми), рух лише фіксується;
        * примітка за замовчуванням: «Коригування К-04 7 → 5 L (−2 L)», «Переміщення К-04 Щитова → Склад»,
          «Списано К-04 (разом із 5 L)», «+20 L · АЗС … · 54,90 грн/л · 1 098 грн», «Заправка «…» з К-04 (ЗПР-…)»;
        * після руху — ``td.genset._check_fuel_stock()`` (контекст ``td_fuel_defer_stock_check`` — відкласти).

        :param str kind: ``in`` | ``out`` | ``fix`` | ``loc`` | ``off``.
        :param float liters_delta: зміна запасу зі знаком.
        :param canister: ``td.genset.canister`` (обов'язкова для ``fix``/``loc``/``off``).
        :param genset: ``td.genset`` — для ``out``.
        :param refuel: ``td.genset.refuel`` — для ``out``.
        :param vals: інші поля руху (``date``, ``note``, ``price_unit``, ``partner_id``, ``receipt_key``,
            ``location_from_id``, ``location_to_id``, ``user_id``).
        :return: запис ``td.genset.fuel.move``.
        """
        kinds = dict(self._fields['kind']._description_selection(self.env))
        if kind not in kinds:
            raise UserError(_('Невідомий вид руху палива: %(kind)s.', kind=kind))
        canister = canister or self.env['td.genset.canister']
        if len(canister) > 1:
            raise UserError(_('Рух запасу стосується однієї каністри.'))
        if kind in ('fix', 'loc', 'off') and not canister:
            raise UserError(_('Для руху «%(kind)s» потрібна каністра.', kind=kinds[kind]))
        applied = bool(self.env.context.get(CTX_APPLIED))
        delta = float_round(liters_delta or 0.0, precision_digits=2)
        if kind == 'off' and not applied:
            delta = -canister.liters
        elif kind == 'loc':
            delta = 0.0
        sign = float_compare(delta, 0.0, precision_digits=2)
        if (kind == 'in' and sign <= 0) or (kind == 'out' and sign >= 0) or (kind == 'off' and sign > 0):
            raise UserError(_('Зміна запасу %(delta)s L не відповідає виду руху «%(kind)s».',
                              delta=fmt_signed(delta), kind=kinds[kind]))
        Location = self.env['td.genset.storage.location']
        location_from = Location.browse(_record_id(vals.pop('location_from_id', False)))
        location_to = Location.browse(_record_id(vals.pop('location_to_id', False)))
        if kind == 'loc':
            if applied:
                location_to = location_to or canister.location_id
            else:
                location_from = location_from or canister.location_id
            if not location_to:
                raise UserError(_('Вкажіть, куди перемістити каністру.'))
        before = after = 0.0
        if canister:
            if applied:
                after = canister.liters
            else:
                after = 0.0 if kind == 'off' else float_round(canister.liters + delta, precision_digits=2)
            before = float_round(after - delta, precision_digits=2)

        values = {
            'kind': kind,
            'liters_delta': delta,
            'canister_id': canister.id,
            'genset_id': _record_id(genset),
            'refuel_id': _record_id(refuel),
            'location_from_id': location_from.id,
            'location_to_id': location_to.id,
        }
        if kind != 'in':
            values.update(price_unit=0.0, partner_id=False)
        values.update({key: _record_id(value) if key.endswith('_id') else value for key, value in vals.items()})
        if not values.get('note'):
            values['note'] = self._default_note(kind, delta, canister, genset, refuel, before, after,
                                                location_from, location_to, values)
        move = self.create(values)

        if canister and not applied:
            if kind == 'loc':
                changes = {'location_id': location_to.id}
            elif kind == 'off':
                changes = {'liters': 0.0, 'active': False}
            else:
                changes = {'liters': after}
            canister.with_context(**{CTX_POSTING: True}).write(changes)
        if not self.env.context.get(CTX_DEFER_STOCK):
            self.env['td.genset']._check_fuel_stock()
        return move

    @api.model
    def _default_note(self, kind, delta, canister, genset, refuel, before, after, location_from, location_to,
                      values):
        """Текст «Примітки» руху за видом (тексти — ТР/мокап, AC-48, AC-49)."""
        name = canister.name or ''
        if kind == 'fix':
            return _('Коригування %(canister)s %(before)s → %(after)s L (%(delta)s L)', canister=name,
                     before=fmt_num(before), after=fmt_num(after), delta=fmt_signed(delta))
        if kind == 'loc':
            return _('Переміщення %(canister)s %(origin)s → %(target)s', canister=name,
                     origin=location_from.name or '—', target=location_to.name or '—')
        if kind == 'off':
            if float_is_zero(delta, precision_digits=2):
                return _('Списано %(canister)s (порожня)', canister=name)
            return _('Списано %(canister)s (разом із %(liters)s L)', canister=name, liters=fmt_num(-delta))
        if kind == 'out':
            text = _('Заправка «%(genset)s»', genset=genset.name) if genset else _('Заправка генератора')
            if canister:
                text = _('%(text)s з %(canister)s', text=text, canister=name)
            if refuel:
                text = '%s (%s)' % (text, refuel.name)
            return text
        partner = self.env['res.partner'].browse(values.get('partner_id') or [])
        return self._receipt_note(delta, partner, values.get('price_unit'))

    @api.model
    def _receipt_note(self, liters, partner=None, price_unit=0.0, note=None):
        """Підсумок надходження: «+20 L · АЗС WOG · 54,90 грн/л · 1 098 грн» (AC-48)."""
        parts = ['+%s L' % fmt_num(liters)]
        if partner:
            parts.append(partner.display_name)
        if price_unit and float_compare(price_unit, 0.0, precision_digits=2) > 0:
            parts.append(_('%(price)s грн/л', price=fmt_num(price_unit, 2)))
            parts.append(_('%(amount)s грн', amount=fmt_num(liters * price_unit, 0)))
        if note:
            parts.append(note)
        return ' · '.join(parts)

    @api.model
    def _last_price(self):
        """Остання ціна надходження (> 0) — для вартості витрати (ФВ-34); інакше ціна з налаштувань."""
        move = self.sudo().search([('kind', '=', 'in'), ('price_unit', '>', 0)], order='date desc, id desc', limit=1)
        if move:
            return move.price_unit
        config = _config(self.env)
        return config.sudo().fuel_price_default if config else 0.0


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
        help='Звідки залили паливо: каністри або інше джерело (паливовоз, АЗС тощо).')
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
    # W4: результат звірки для списку «Заправки» («підтверджено за рівнем: +87 L» / «за рівнем: +80 L»)
    level_delta_l = fields.Float(
        string='За рівнем, L', readonly=True,
        help='Приріст рівня в баку за подією «Заправка» (зі знімків при звірці), L.')
    sensor_note = fields.Char(
        string='Звірка з датчиком', compute='_compute_sensor_note',
        help='«очікує показання», «підтверджено за рівнем: +87 L», «за рівнем: +80 L» (різниця з записаним '
             'більша за допуск — видно обидва значення), «не підтверджено».')

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

    @api.depends('sensor_state', 'level_delta_l')
    def _compute_sensor_note(self):
        for refuel in self:
            state = refuel.sensor_state
            if state == 'confirmed':
                note = _('підтверджено за рівнем: %(delta)s L', delta=fmt_signed(refuel.level_delta_l))
            elif state == 'by_level':
                note = _('за рівнем: %(delta)s L', delta=fmt_signed(refuel.level_delta_l))
            elif state == 'unconfirmed':
                note = _('не підтверджено')
            elif state == 'drain':
                note = _('падіння без роботи')
            elif state == 'waiting':
                note = _('очікує показання')
            else:
                note = False
            refuel.sensor_note = note

    @api.model
    def _reconcile_pending(self):
        """Звірка заправок з подіями «Заправка» (ФВ-33, ТР 2.9, AC-51, AC-69).

        Для записів ``waiting`` (і ``unconfirmed`` за останні 7 днів — подія могла прийти із запізненням після
        догону) шукається подія ``refuel`` генератора без іншого запису в межах ``date ± 2 год`` (найближча):
        ``|ΔL − liters| ≤ 2 % бака`` (≤ 1 L, якщо калібрування датчика заповнене) → ``confirmed``, інакше
        ``by_level``; рівні до/після — зі знімків події. Немає події 2 год → ``unconfirmed`` + попередження
        ``refuel_unconfirmed`` «Заправку N L (HH:MM) не підтверджено датчиком рівня.» (не під час догону).
        Викликається з cron розкладу, обробника подій і майстра заправки; технічний метод (``sudo``).
        """
        now = fields.Datetime.now()
        refuels = self.sudo()
        pending = refuels.search([
            '|', ('sensor_state', '=', 'waiting'),
            '&', ('sensor_state', '=', 'unconfirmed'), ('date', '>=', now - timedelta(days=REFUEL_RECHECK_DAYS)),
        ], order='date, id')
        events = self.env['td.genset.event'].sudo()
        alarms = self.env['td.genset.alarm'].sudo()
        resolved = self.env['td.genset'].sudo()
        for refuel in pending:
            genset = refuel.genset_id
            candidates = events.search([
                ('genset_id', '=', genset.id),
                ('event_type', '=', 'refuel'),
                ('refuel_id', '=', False),
                ('date_start', '>=', refuel.date - REFUEL_WINDOW),
                ('date_start', '<=', refuel.date + REFUEL_WINDOW),
            ])
            if candidates:
                event = min(candidates, key=lambda ev: (abs((ev.date_start - refuel.date).total_seconds()), ev.id))
                if refuel.sensor_state == 'unconfirmed':
                    resolved |= genset
                refuel._match_level_event(event)
            elif refuel.sensor_state == 'waiting' and now >= refuel.date + REFUEL_WINDOW and not genset.catchup_mode:
                refuel.sensor_state = 'unconfirmed'
                alarms._raise(
                    genset, 'refuel_unconfirmed', 'warn',
                    _('Заправку %(liters)s L (%(time)s) не підтверджено датчиком рівня.',
                      liters=fmt_num(refuel.liters), time=kyiv_hhmm(refuel.date)),
                    description=_('%(name)s: за 2 год після заправки рівень у баку не зріс (подію «Заправка» не '
                                  'зафіксовано). Перевірте рівень палива і запис заправки.', name=refuel.name))
        for genset in resolved:
            if not refuels.search_count([('genset_id', '=', genset.id), ('sensor_state', '=', 'unconfirmed')],
                                        limit=1):
                alarms._clear(genset, 'refuel_unconfirmed', note=_('Заправку підтверджено датчиком рівня.'))
        return None

    def _match_level_event(self, event):
        """Зв'язати запис з подією «Заправка»: рівні до/після, ΔL і стан звірки; нотатка в чатер генератора."""
        self.ensure_one()
        genset = self.genset_id
        before, after = self._level_readings(event)
        delta = event.fuel_delta_l
        if float_is_zero(delta, precision_digits=2) and before and after:
            delta = after.fuel_liters - before.fuel_liters
        if genset.fuel_calibrated:
            tolerance = REFUEL_TOLERANCE_CALIBRATED_L
        else:
            tolerance = (genset.tank_volume_l or 0.0) * REFUEL_TOLERANCE_SHARE
        difference = abs(delta - self.liters)
        state = 'confirmed' if float_compare(difference, tolerance, precision_digits=2) <= 0 else 'by_level'
        values = {'event_id': event.id, 'sensor_state': state, 'level_delta_l': float_round(delta, 1)}
        if before:
            values.update(level_before_pct=before.fuel_level, level_before_l=before.fuel_liters)
        if after:
            values.update(level_after_pct=after.fuel_level, level_after_l=after.fuel_liters)
        self.write(values)
        event.write({'refuel_id': self.id})
        levels = ' (%s → %s L)' % (fmt_num(self.level_before_l), fmt_num(self.level_after_l)) if before and after else ''
        if state == 'confirmed':
            body = _('Заправку %(name)s (%(liters)s L) підтверджено за рівнем: %(delta)s L%(levels)s.',
                     name=self.name, liters=fmt_num(self.liters), delta=fmt_signed(delta), levels=levels)
        else:
            body = _('Заправка %(name)s: записано %(liters)s L, за рівнем %(delta)s L%(levels)s — різниця '
                     '%(difference)s L більша за допуск %(tolerance)s L.', name=self.name,
                     liters=fmt_num(self.liters), delta=fmt_signed(delta), levels=levels,
                     difference=fmt_num(difference), tolerance=fmt_num(tolerance))
        genset._message_log(body=body)

    def _level_readings(self, event):
        """Знімки до і після стрибка рівня: ``reading_start_id``/``reading_end_id`` події, інакше — найближчі
        знімки генератора до початку і після кінця події."""
        readings = self.env['td.genset.reading'].sudo()
        before = event.reading_start_id
        after = event.reading_end_id
        if not before and event.date_start:
            before = readings.search([('genset_id', '=', event.genset_id.id), ('ts', '<=', event.date_start)],
                                     order='ts desc, id desc', limit=1)
        moment = event.date_end or event.date_start
        if not after and moment:
            after = readings.search([('genset_id', '=', event.genset_id.id), ('ts', '>=', moment),
                                     ('id', '!=', before.id)], order='ts, id', limit=1)
        return before, after


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
        """0 ≤ L ≤ об'єм бака, опір ≥ 0; літри за зростанням Ом строго монотонні — лише зростають або лише
        спадають (напрямок кривої датчика довільний), ФВ-31, AC-69. Використовується за ≥ 2 точок."""
        for point in self:
            if float_compare(point.ohm, 0.0, precision_digits=1) < 0:
                raise ValidationError(_("Опір датчика не може бути від'ємним."))
            tank = point.genset_id.tank_volume_l
            if float_compare(point.liters, 0.0, precision_digits=2) < 0 \
                    or float_compare(point.liters, tank, precision_digits=2) > 0:
                raise ValidationError(_("Літрів у точці калібрування має бути від 0 до об'єму бака (%(tank)s L).",
                                        tank=fmt_num(tank)))
        for genset in self.mapped('genset_id'):
            points = self.sudo().search([('genset_id', '=', genset.id)], order='ohm, id')
            steps = [float_compare(right.liters, left.liters, precision_digits=2)
                     for left, right in zip(points, points[1:])]
            if steps and not (all(step > 0 for step in steps) or all(step < 0 for step in steps)):
                raise ValidationError(_('Калібрування має бути монотонним: кожній наступній точці за Ом відповідає '
                                        'більший (або менший) об\'єм.'))


class TdGensetFuel(models.Model):
    """``td.genset`` (inherit): KPI палива, мінімальний запас, калібрування, ТО — ТР 2.9."""
    _inherit = 'td.genset'

    # ================================================================== KPI палива (ФВ-31, ФВ-34; AC-47, AC-52)
    @api.depends('fuel_liters')
    def _compute_fuel_kpi(self):
        """KPI вкладки «Паливо» і сторінки «Заправка»: «У баку» (``fuel_liters``), «У каністрах N L
        (6 повних · 1 часткова · 5 порожніх)», «Разом … · вистачить на ≈ N год» (за витратою L/год за 30 днів),
        «Мінімальний запас … · запас у нормі / бракує N L»; витрата за 7/30 днів — ``_fuel_stats``."""
        canisters = self.env['td.genset.canister'].search([])
        in_canisters = float_round(sum(canisters.mapped('liters')), precision_digits=1)
        forms = {
            'full': (_('повна'), _('повні'), _('повних')),
            'part': (_('часткова'), _('часткові'), _('часткових')),
            'empty': (_('порожня'), _('порожні'), _('порожніх')),
        }
        counts = {state: len(canisters.filtered(lambda can, state=state: can.state == state)) for state in forms}
        summary = ' · '.join('%s %s' % (counts[state], plural(counts[state], forms[state])) for state in forms)
        config = self.env['td.genset.config'].get()
        minimum = config.sudo().fuel_min_stock_l if config else 0.0
        for genset in self:
            stats = {7: genset._fuel_stats(7), 30: genset._fuel_stats(30)}
            total = float_round((genset.fuel_liters or 0.0) + in_canisters, precision_digits=1)
            rate = stats[30]['lph']
            genset.canister_liters = in_canisters
            genset.fuel_in_canisters_l = in_canisters
            genset.fuel_total_l = total
            genset.fuel_hours_left = float_round(total / rate, precision_digits=0) if rate > 0 else 0.0
            genset.fuel_min_stock_l = minimum
            genset.fuel_min_stock_ok = float_compare(in_canisters, minimum, precision_digits=1) >= 0
            genset.fuel_stock_lack_l = max(float_round(minimum - in_canisters, precision_digits=1), 0.0)
            genset.fuel_canisters_summary = summary
            for days, suffix in ((7, '7d'), (30, '30d')):
                genset['fuel_used_%s_l' % suffix] = stats[days]['used_l']
                genset['fuel_rate_lph_%s' % suffix] = stats[days]['lph']
                genset['fuel_rate_lpkwh_%s' % suffix] = stats[days]['lpkwh']
                genset['fuel_per_day_%s' % suffix] = stats[days]['per_day']
                genset['fuel_cost_%s' % suffix] = stats[days]['cost']

    def _fuel_stats(self, days):
        """KPI витрати за останні ``days`` днів (ФВ-34, ТР 2.9) — ``_read_group`` подій «Робота генератора»
        з початком у періоді: витрачено ``−Σ fuel_delta_l``, години ``Σ duration``, ``Σ energy_kwh``.

        :return: ``{'used_l' (L, 0,1), 'hours' (год, 0,01), 'kwh' (0,1), 'lph' (L/год, 0,1),
            'lpkwh' (L/kWh, 0,01), 'per_day' (L/добу, 0,1), 'cost' (грн, ціле — витрачено × остання ціна
            надходження)}``; без генератора або подій — нулі.
        """
        stats = {'used_l': 0.0, 'hours': 0.0, 'kwh': 0.0, 'lph': 0.0, 'lpkwh': 0.0, 'per_day': 0.0, 'cost': 0.0}
        genset_ids = [genset_id for genset_id in self._origin.ids if genset_id]
        if not genset_ids or not days:
            return stats
        since = fields.Datetime.now() - timedelta(days=days)
        [(delta, hours, kwh)] = self.env['td.genset.event']._read_group(
            [('genset_id', 'in', genset_ids), ('event_type', '=', 'run'), ('date_start', '>=', since)],
            aggregates=['fuel_delta_l:sum', 'duration:sum', 'energy_kwh:sum'])
        used = max(-(delta or 0.0), 0.0)
        hours = hours or 0.0
        kwh = kwh or 0.0
        stats.update(
            used_l=float_round(used, precision_digits=1),
            hours=float_round(hours, precision_digits=2),
            kwh=float_round(kwh, precision_digits=1),
            lph=float_round(used / hours, precision_digits=1) if hours > 0 else 0.0,
            lpkwh=float_round(used / kwh, precision_digits=2) if kwh > 0 else 0.0,
            per_day=float_round(used / days, precision_digits=1),
            cost=float_round(used * self.env['td.genset.fuel.move']._last_price(), precision_digits=0),
        )
        return stats

    def _check_fuel_stock(self):
        """Мінімальний запас у каністрах (ФВ-31, AC-47): запас < «Мінімальний запас» → попередження
        ``fuel_stock_low`` «Запас у каністрах N L нижчий за мінімальний M L.»; запас відновився → ``_clear``.

        Викликається після кожного руху запасу (``_post``) і з cron розкладу. Порожній recordset (виклик на
        моделі) — усі активні генератори. Поки каністр немає взагалі (облік не почато), не перевіряється.
        """
        gensets = (self or self.search([])).sudo()
        canisters = self.env['td.genset.canister'].sudo()
        if not gensets or not canisters.with_context(active_test=False).search_count([], limit=1):
            return None
        stock = float_round(sum(canisters.search([]).mapped('liters')), precision_digits=1)
        config = self.env['td.genset.config'].sudo().get()
        minimum = config.fuel_min_stock_l if config else 0.0
        low = float_compare(stock, minimum, precision_digits=1) < 0
        alarms = self.env['td.genset.alarm'].sudo()
        for genset in gensets:
            active = alarms.search_count([('genset_id', '=', genset.id), ('code', '=', 'fuel_stock_low'),
                                          ('state', '!=', 'cleared')], limit=1)
            if low and not active:
                alarms._raise(
                    genset, 'fuel_stock_low', 'warn',
                    _('Запас у каністрах %(stock)s L нижчий за мінімальний %(minimum)s L.',
                      stock=fmt_num(stock), minimum=fmt_num(minimum)),
                    description=_('Бракує %(lack)s L. Оформіть надходження палива (Генератори → Заправка).',
                                  lack=fmt_num(minimum - stock)))
            elif not low and active:
                alarms._clear(genset, 'fuel_stock_low',
                              note=_('Запас у каністрах %(stock)s L — у нормі.', stock=fmt_num(stock)))
        return None

    # ================================================================== калібрування датчика (ФВ-31, AC-69)
    def _fuel_calibration_points(self):
        """Точки калібрування ``[(ohm, liters), …]`` за зростанням Ом; ``[]`` — калібрування не заповнене
        (порожня таблиця або таблиця з 1 точки)."""
        self.ensure_one()
        points = sorted((point.ohm, point.liters) for point in self.fuel_calibration_ids)
        return points if len(points) >= 2 else []

    def _liters_from_ohm(self, ohm):
        """Літри за калібруванням датчика палива (ФВ-31, AC-69): лінійна інтерполяція між сусідніми точками
        Ом → L, за межами таблиці — значення крайньої точки; результат завжди округлено до 0,1 L
        (188,6 Ом при 100 → 60 L і 190 → 137 L дає 135,8 L).

        Таблиця з 1 точки вважається незаповненою — ``None`` (як і порожня): літри рахуються за % контролера.

        :param float ohm: опір датчика, Ом; ``None``/``False``/0 — немає даних (як у compute знімка).
        :return: літри (0,1 L) або ``None``, якщо опору немає чи калібрування не заповнене (< 2 точок).
        """
        if not ohm or len(self) != 1:
            return None
        points = self._fuel_calibration_points()
        return interpolate_liters(points, ohm) if points else None

    @api.depends('fuel_calibration_ids', 'fuel_calibration_ids.ohm', 'fuel_calibration_ids.liters')
    def _compute_fuel_calibrated(self):
        """Калібрування заповнено — щонайменше 2 точки (монотонність гарантує ``@api.constrains`` точок)."""
        for genset in self:
            genset.fuel_calibrated = len(genset.fuel_calibration_ids) >= 2

    def action_recompute_liters(self):
        """«Перерахувати літри» (``group_tech``; ФВ-31, AC-69, ТР 2.9): ``fuel_liters``/``fuel_source`` усіх
        знімків генератора — за поточним калібруванням (≥ 2 точки, є опір) або за % × об'єм бака.

        Перша партія — до 10 000 найсвіжіших знімків — перераховується синхронно у виклику кнопки (на невеликій
        базі результат видно одразу); старші — фоновим завданням ``cron_recompute_liters`` партіями по 10 000
        (``_trigger()`` + ``_notify_progress``), воркер не блокується. Події заднім числом не перераховуються.
        Одна точка калібрування → помилка «Калібрування має бути монотонним…», літри лишаються за %.

        :return: дія ``display_notification``.
        """
        self._td_check_group('td_genset.group_tech')
        done = remaining = 0
        sources = set()
        for genset in self:
            if len(genset.fuel_calibration_ids) == 1:
                raise UserError(_('Калібрування має бути монотонним: потрібно щонайменше 2 точки Ом → L (зараз 1). '
                                  'Поки точок менше двох, літри рахуються за % контролера.'))
            processed, before_id = genset._recompute_liters_batch()
            done += processed
            genset.sudo().fuel_recompute_next_id = before_id
            remaining += genset._recompute_liters_remaining()
            sources.add('ohm' if genset.fuel_calibrated else 'pct')
        if remaining:
            cron = self.env.ref('td_genset.cron_recompute_liters', raise_if_not_found=False)
            if cron:
                cron._trigger()
            else:
                while self._cron_recompute_liters():
                    pass
                done += remaining
                remaining = 0
        if sources == {'ohm'}:
            basis = _('за калібруванням датчика (Ом)')
        elif sources == {'pct'}:
            basis = _('за % контролера')
        else:
            basis = _('за калібруванням або за %')
        readings = '%s %s' % (done, plural(done, (_('знімок'), _('знімки'), _('знімків'))))
        if remaining:
            message = _('Літри перераховано %(basis)s: %(readings)s; решту (%(left)s) перерахує фонове завдання.',
                        basis=basis, readings=readings, left=remaining)
        else:
            message = _('Літри перераховано %(basis)s: %(readings)s.', basis=basis, readings=readings)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Перерахувати літри'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _recompute_liters_batch(self, before_id=0, limit=None):
        """Одна партія перерахунку літрів — від найсвіжіших знімків до старіших: знімки генератора з
        ``id < before_id`` (``0`` — від найсвіжішого) за спаданням id (id знімків зростають у порядку забору,
        тобто за часом). Значення — ``interpolate_liters`` / ``liters_from_pct`` (NULL рівня і опору → NULL),
        запис — SQL ``UPDATE … FROM (VALUES …)`` (без перерахунку ORM усього знімка); літри картки — з
        останнього знімка.

        :return: ``(оброблено знімків, межа наступної партії — найменший оброблений id, або 0 — завершено)``.
        """
        self.ensure_one()
        limit = limit or RECOMPUTE_BATCH
        readings = self.env['td.genset.reading']
        readings.flush_model(['genset_id', 'fuel_level', 'fuel_sensor_ohm', 'fuel_liters', 'fuel_source'])
        before = SQL('AND id < %s', before_id) if before_id else SQL()
        self.env.cr.execute(SQL(
            """SELECT id, fuel_level, fuel_sensor_ohm FROM td_genset_reading
                WHERE genset_id = %s %s ORDER BY id DESC LIMIT %s""",
            self.id, before, limit,
        ))
        rows = self.env.cr.fetchall()
        if not rows:
            return 0, 0
        points = self._fuel_calibration_points()
        tank = self.tank_volume_l or 0.0
        values = []
        for reading_id, level, ohm in rows:
            if points and ohm:
                liters, source = interpolate_liters(points, ohm), 'ohm'
            elif level is None:
                liters, source = None, None
            else:
                liters, source = liters_from_pct(float(level), tank), 'pct'
            values.append(SQL('(%s, %s::float8, %s::varchar)', reading_id, liters, source))
        for chunk in split_every(RECOMPUTE_SQL_CHUNK, values):
            self.env.cr.execute(SQL(
                """UPDATE td_genset_reading AS reading
                      SET fuel_liters = recomputed.liters, fuel_source = recomputed.source
                     FROM (VALUES %s) AS recomputed(id, liters, source)
                    WHERE reading.id = recomputed.id""",
                SQL(', ').join(chunk),
            ))
        readings.invalidate_model(['fuel_liters', 'fuel_source'])
        last = self.sudo().last_reading_id
        if last and last.fuel_source:
            self.sudo().write({'fuel_liters': last.fuel_liters, 'fuel_source': last.fuel_source})
        before_next = rows[-1][0] if len(rows) >= limit else 0
        return len(rows), before_next

    def _recompute_liters_remaining(self):
        """Скільки (старіших) знімків генератора ще чекає на перерахунок літрів."""
        self.ensure_one()
        if not self.fuel_recompute_next_id:
            return 0
        return self.env['td.genset.reading'].sudo().search_count(
            [('genset_id', '=', self.id), ('id', '<', self.fuel_recompute_next_id)])

    @api.model
    def _cron_recompute_liters(self):
        """Крок cron ``cron_recompute_liters``: по одній партії (10 000 знімків, від свіжіших до старіших) на
        генератор з незавершеним перерахунком літрів; ``ir.cron._notify_progress(done, remaining)`` —
        планувальник Odoo повторює крок, доки є залишок (А.7). Винятки перехоплюються (cron не падає,
        перерахунок генератора зупиняється).

        :return: скільки знімків лишилось.
        """
        gensets = self.sudo().with_context(active_test=False).search([('fuel_recompute_next_id', '>', 0)])
        done = remaining = 0
        for genset in gensets:
            try:
                with self.env.cr.savepoint():
                    processed, before_id = genset._recompute_liters_batch(genset.fuel_recompute_next_id)
                    genset.fuel_recompute_next_id = before_id
                done += processed
                remaining += genset._recompute_liters_remaining()
            except Exception as error:  # cron не кидає винятків назовні (А.7)
                _logger.warning('td_genset: перерахунок літрів генератора %s зупинено: %s', genset.id, error)
                genset.fuel_recompute_next_id = 0
        self.env['ir.cron']._notify_progress(done=done, remaining=remaining)
        return remaining

    # ================================================================== ТО (ФВ-35, ФВ-36; AC-53, AC-54)
    def _maint_team(self):
        """Команда ТО з налаштувань (data: «Генератори»), якщо вона без компанії або тієї ж компанії."""
        self.ensure_one()
        config = self.env['td.genset.config'].sudo().get()
        team = (config.maint_team_id if config else False) \
            or self.env.ref('td_genset.maintenance_team_genset', raise_if_not_found=False)
        team = team.sudo() if team else self.env['maintenance.team'].sudo()
        if team.company_id and self.company_id and team.company_id != self.company_id:
            return self.env['maintenance.team'].sudo()
        return team

    def _ensure_equipment(self):
        """Обладнання «Обслуговування» для генератора (ФВ-36, ТР 2.9): «Генератор · <назва>», категорія і
        команда «Генератори», ``technician_user_id`` = відповідальний, ``td_genset_id``; синхронізація назви,
        відповідального, компанії й архіву (архівація генератора архівує обладнання). Технічний запис — ``sudo``."""
        category = self.env.ref('td_genset.equipment_category_genset', raise_if_not_found=False)
        equipment_model = self.env['maintenance.equipment'].sudo().with_context(active_test=False)
        for genset in self.sudo().with_context(active_test=False):
            name = _('Генератор · %(name)s', name=genset.name)
            equipment = genset.equipment_id
            if not equipment:
                team = genset._maint_team()
                equipment = equipment_model.create({
                    'name': name,
                    'category_id': category.id if category else False,
                    'maintenance_team_id': team.id,
                    'technician_user_id': genset.user_id.id,
                    'company_id': (genset.company_id or self.env.company).id,
                    'td_genset_id': genset.id,
                    'active': genset.active,
                })
                genset.equipment_id = equipment
                continue
            changes = {}
            if equipment.name != name:
                changes['name'] = name
            if equipment.technician_user_id != genset.user_id:
                changes['technician_user_id'] = genset.user_id.id
            if equipment.active != genset.active:
                changes['active'] = genset.active
            if equipment.td_genset_id != genset:
                changes['td_genset_id'] = genset.id
            if genset.company_id and equipment.company_id != genset.company_id:
                changes['company_id'] = genset.company_id.id
                team = equipment.maintenance_team_id
                if team.company_id and team.company_id != genset.company_id:
                    changes['maintenance_team_id'] = genset._maint_team().id
            if changes:
                equipment.write(changes)
        return None

    @api.depends('run_hours_total', 'maint_first_hours', 'maint_interval_hours', 'maint_interval_months',
                 'commissioning_date', 'equipment_id', 'equipment_id.maintenance_ids.stage_id',
                 'equipment_id.maintenance_ids.td_run_hours_at_close',
                 'equipment_id.maintenance_ids.close_date')
    def _compute_maint(self):
        """«До ТО» (ФВ-35, ТР 2.9): ``maint_hours_left = next_due_hours − run_hours_total``, де
        ``next_due_hours`` = «Перше ТО» до першої закритої заявки, далі мотогодини закриття останньої
        (``td_run_hours_at_close``) + «Далі кожні»; ``maint_due_date`` = дата закриття (або введення в
        експлуатацію) + місяці; ``maint_state``: ``overdue`` — мотогодини ≤ 0 або дата настала, ``due`` —
        лишилось ≤ 10 % інтервалу або ≤ 30 днів, інакше ``ok``."""
        today = fields.Date.context_today(self)
        for genset in self:
            info = genset._maint_schedule(today)
            genset.maint_hours_left = info['hours_left']
            genset.maint_due_date = info['due_date']
            genset.maint_state = info['state']
            genset.maint_next_hours = info['next_hours']
            genset.maint_progress = info['progress']

    def _maint_last_done(self):
        """Остання закрита (стадія «виконано») превентивна заявка ТО обладнання генератора."""
        self.ensure_one()
        requests = self.env['maintenance.request'].sudo()
        equipment = self.sudo().equipment_id
        if not equipment:
            return requests
        done = requests.search([('equipment_id', '=', equipment.id), ('maintenance_type', '=', 'preventive'),
                                ('stage_id.done', '=', True), ('archive', '=', False)])
        if not done:
            return requests
        return max(done, key=lambda request: (request.close_date or date.min, request.id))

    def _maint_schedule(self, today=None):
        """Регламент ТО генератора на дату (ТР 2.9).

        :return: ``{'next_hours', 'hours_left', 'due_date', 'state', 'progress', 'reason', 'last'}``;
            ``reason``: ``first`` (перше ТО) | ``hours`` (кожні N мотогодин) | ``months`` (раз на N міс.).
            Інтервал ≤ 0 вимикає правило мотогодин.
        """
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        last = self._maint_last_done()
        months = self.maint_interval_months or 0
        if last:
            interval = float(self.maint_interval_hours or 0)
            base_hours = last.td_run_hours_at_close or 0.0
            base_date = last.close_date
        else:
            interval = float(self.maint_first_hours or 0)
            base_hours = 0.0
            base_date = self.commissioning_date
        run_hours = self.run_hours_total or 0.0
        by_hours = interval > 0
        next_hours = float_round(base_hours + interval, precision_digits=2) if by_hours else 0.0
        hours_left = float_round(next_hours - run_hours, precision_digits=2) if by_hours else 0.0
        due_date = base_date + relativedelta(months=months) if base_date and months > 0 else False
        hours_overdue = by_hours and float_compare(hours_left, 0.0, precision_digits=2) <= 0
        date_overdue = bool(due_date) and today >= due_date
        if hours_overdue or date_overdue:
            state = 'overdue'
        elif (by_hours and float_compare(hours_left, interval * MAINT_DUE_SHARE, precision_digits=2) <= 0) \
                or (due_date and today >= due_date - timedelta(days=MAINT_DUE_DAYS)):
            state = 'due'
        else:
            state = 'ok'
        progress = min(max((run_hours - base_hours) / interval * 100.0, 0.0), 100.0) if by_hours else 0.0
        if date_overdue and not hours_overdue:
            reason = 'months'
        else:
            reason = 'hours' if last else 'first'
        return {
            'next_hours': next_hours,
            'hours_left': hours_left,
            'due_date': due_date,
            'state': state,
            'progress': float_round(progress, precision_digits=1),
            'reason': reason,
            'last': last,
        }

    def _check_maintenance(self):
        """Авто-заявка ТО (ФВ-36, ТР 2.9, AC-53): ``maint_state == 'overdue'`` і на обладнанні немає відкритої
        заявки → превентивна заявка (команда «Генератори», виконавець — відповідальний, опис — чек-лист з
        налаштувань) + попередження ``maintenance_due`` «Термін ТО: … Створено заявку …» + активність
        «Перевірити генератор» відповідальному. Друга заявка не створюється, поки перша відкрита.

        Викликається після знімка (``_apply_reading``) і з cron розкладу; порожній recordset — усі активні
        генератори; генератор у режимі догону пропускається (тривоги — після догону). Технічний метод (``sudo``).
        """
        gensets = (self or self.search([])).sudo()
        requests = self.env['maintenance.request'].sudo()
        alarms = self.env['td.genset.alarm'].sudo()
        config = self.env['td.genset.config'].sudo().get()
        today = fields.Date.context_today(self)
        for genset in gensets:
            if not genset.active or genset.catchup_mode:
                continue
            if not genset.equipment_id:
                genset._ensure_equipment()
            info = genset._maint_schedule(today)
            if info['state'] != 'overdue' or not genset.equipment_id:
                continue
            if requests.search_count([('equipment_id', '=', genset.equipment_id.id), ('stage_id.done', '=', False),
                                      ('archive', '=', False)], limit=1):
                continue
            request = genset._create_maintenance_request(info, config, today)
            if info['reason'] == 'first':
                reason = _('перше %(hours)s год', hours=fmt_num(genset.maint_first_hours))
            elif info['reason'] == 'hours':
                reason = _('кожні %(hours)s год', hours=fmt_num(genset.maint_interval_hours))
            else:
                reason = _('%(months)s міс', months=genset.maint_interval_months)  # «Термін ТО: 12 міс. Створено…»
            alarms._raise(
                genset, 'maintenance_due', 'warn',
                _('Термін ТО: %(reason)s. Створено заявку «%(request)s».', reason=reason, request=request.name),
                description=_('Мотогодини: %(hours)s; ТО за регламентом — на %(next)s мотогодин%(date)s. Заявка — у '
                              '«Обслуговуванні» (команда «%(team)s»).', hours=fmt_num(genset.run_hours_total, 1),
                              next=fmt_num(info['next_hours']), team=request.maintenance_team_id.name or '—',
                              date=_(' або до %(date)s', date=info['due_date'].strftime('%d.%m.%Y'))
                              if info['due_date'] else ''),
                source=request)
            if genset.user_id:
                genset.activity_schedule(
                    'td_genset.activity_check', date_deadline=today, summary=MAINT_ACTIVITY_SUMMARY,
                    note=_('Створено заявку ТО «%(request)s». Узгодьте роботи з підрядником і закрийте заявку '
                           'стадією «виконано».', request=request.name),
                    user_id=genset.user_id.id)
            genset._notify_bus('status')
        return None

    def _create_maintenance_request(self, info, config, today):
        """Превентивна заявка ТО (ТР 2.3.12): обладнання генератора, команда «Генератори», виконавець —
        відповідальний, опис — чек-лист з налаштувань, ``schedule_date`` = зараз, ``request_date`` = сьогодні."""
        self.ensure_one()
        equipment = self.equipment_id
        if info['reason'] == 'first':
            name = _('ТО-1 після обкатки (%(hours)s мотогодин)', hours=fmt_num(self.maint_first_hours))
        else:
            number = self.env['maintenance.request'].sudo().search_count([
                ('equipment_id', '=', equipment.id), ('maintenance_type', '=', 'preventive'),
                ('stage_id.done', '=', True)]) + 1
            if info['reason'] == 'hours':
                name = _('ТО-%(number)s: кожні %(hours)s мотогодин', number=number,
                         hours=fmt_num(self.maint_interval_hours))
            else:
                name = _('ТО-%(number)s: раз на %(months)s міс.', number=number, months=self.maint_interval_months)
        values = {
            'name': name,
            'maintenance_type': 'preventive',
            'equipment_id': equipment.id,
            'user_id': self.user_id.id,
            'description': config.maint_checklist if config else False,
            'schedule_date': fields.Datetime.now(),
            'request_date': today,
            'company_id': (equipment.company_id or self.company_id or self.env.company).id,
        }
        team = self._maint_team() or equipment.maintenance_team_id
        if team:
            values['maintenance_team_id'] = team.id
        return self.env['maintenance.request'].sudo().create(values)
