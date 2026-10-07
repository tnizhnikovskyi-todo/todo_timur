# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас (поля, заглушки): W0.
"""Подія ``td.genset.event`` — ТР 2.3.3, 2.8.1; SPEC 5.3, 9."""
from odoo import _, api, fields, models

from .genset import CONTROLLER_MODES

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

    @api.depends('event_type')
    def _compute_display_name(self):
        labels = dict(EVENT_TYPES)
        for event in self:
            event.display_name = labels.get(event.event_type) or _('Подія')

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
        у ``catchup_mode`` не кличе ``_raise``.

        TODO: W1 — AC-27, AC-38, AC-39, AC-40, AC-41, AC-45, AC-46. Заглушка W0: нічого не робить.
        """
        return None

    @api.model
    def _open(self, genset, event_type, date_start, **vals):
        """Створює відкриту подію (``date_end = NULL``) і повертає її.

        TODO: W1 — AC-38, AC-39. Заглушка W0: порожній recordset.
        """
        return self.browse()

    @api.model
    def _close(self, event, date_end, **vals):
        """Закриває подію: ``date_end``, атрибути (``energy_kwh``, ``peak_kw``, ``fuel_delta_l``, ``summary`` …).

        TODO: W1 — AC-38, AC-39. Заглушка W0: нічого не робить.
        """
        return None

    @api.model
    def _detect_external_control(self, genset, prev=None, cur=None, cloud=None):
        """Правило ``external_control`` 2.8.1 (зі знімків ``prev``/``cur`` або з ``cloud_commands_seen``):
        подія, ``control_source='external'``, ``_raise('external_control')`` поза догоном.

        TODO: W1 — AC-27. Заглушка W0: нічого не робить.
        """
        return None
