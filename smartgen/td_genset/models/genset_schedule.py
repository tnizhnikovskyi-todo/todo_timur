# Part of td_genset (ToDo). Власник файлу: W2 «Керування». Каркас (поля, обмеження): W0.
"""Розклад ``td.genset.schedule`` і дні-винятки ``td.genset.schedule.exception`` — ТР 2.3.6, 2.3.7, 2.7.3, А.6;
SPEC 5.6, 5.7, 9. Модульна функція ``kyiv_localize`` — межі вікон за Europe/Kyiv з обробкою DST.
"""
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

KYIV_TZ = pytz.timezone('Europe/Kyiv')
DAYS_OF_WEEK = [
    ('0', 'Понеділок'),
    ('1', 'Вівторок'),
    ('2', 'Середа'),
    ('3', 'Четвер'),
    ('4', "П'ятниця"),
    ('5', 'Субота'),
    ('6', 'Неділя'),
]
EXCEPTION_ACTIONS = [
    ('skip', 'Не запускати'),
    ('custom', 'Інший час'),
]


def kyiv_localize(date, float_time):
    """UTC naive для київського часу ``date`` + ``float_time`` (години) з обробкою DST (А.6 п. 1, AC-37).

    ``NonExistentTimeError`` (весняний перехід) → перша дійсна хвилина після переходу (04:00);
    ``AmbiguousTimeError`` (осінній) → перша година (``is_dst=True``). ``float_time`` 24.0 → 00:00 наступного дня.

    TODO: W2 — покрити тестами AC-37 (W0: базова реалізація).
    """
    minutes = int(round((float_time or 0.0) * 60))
    day = date + timedelta(days=minutes // (24 * 60))
    minutes %= 24 * 60
    naive = datetime.combine(day, time(minutes // 60, minutes % 60))
    try:
        local = KYIV_TZ.localize(naive, is_dst=None)
    except pytz.exceptions.NonExistentTimeError:
        # неіснуючий час (03:00–03:59 в останню неділю березня) → перша дійсна хвилина після переходу (04:00)
        local = KYIV_TZ.localize(naive.replace(minute=0) + timedelta(hours=1), is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        local = KYIV_TZ.localize(naive, is_dst=True)
    return local.astimezone(pytz.utc).replace(tzinfo=None)


class TdGensetSchedule(models.Model):
    _name = 'td.genset.schedule'
    _description = 'Генератори: вікно розкладу'
    _order = 'genset_id, dayofweek, time_start'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, index=True, ondelete='cascade',
        help='Генератор, для якого діє вікно.')
    dayofweek = fields.Selection(
        DAYS_OF_WEEK, string='День', required=True, default='0',
        help='День тижня вікна розкладу.')
    time_start = fields.Float(
        string='Початок → Авто', required=True,
        help='Коли перевести генератор у режим Авто (київський час).')
    time_end = fields.Float(
        string='Кінець → Ручний + Стоп', required=True,
        help='Коли перевести генератор у Ручний і зупинити (київський час).')
    enabled = fields.Boolean(
        string='Увімкнено', default=True,
        help='Вимкнений рядок не надсилає команд (поле не active — архів ховав би рядок з розкладу).')

    @api.constrains('time_start', 'time_end', 'dayofweek', 'genset_id', 'enabled')
    def _check_window(self):
        """AC-29: «Кінець має бути пізніше за початок.»; «Вікна одного дня не можуть перетинатися.»"""
        for line in self:
            if not 0 <= line.time_start < 24 or not 0 < line.time_end <= 24:
                raise ValidationError(_('Час має бути в межах доби (00:00–24:00).'))
            if line.time_end <= line.time_start:
                raise ValidationError(_('Кінець має бути пізніше за початок.'))
            if not line.enabled:
                continue
            others = self.search([
                ('id', '!=', line.id),
                ('genset_id', '=', line.genset_id.id),
                ('dayofweek', '=', line.dayofweek),
                ('enabled', '=', True),
                ('time_start', '<', line.time_end),
                ('time_end', '>', line.time_start),
            ], limit=1)
            if others:
                raise ValidationError(_('Вікна одного дня не можуть перетинатися.'))


class TdGensetScheduleException(models.Model):
    _name = 'td.genset.schedule.exception'
    _description = 'Генератори: день-виняток розкладу'
    _order = 'date desc'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, index=True, ondelete='cascade',
        help='Генератор, для якого діє виняток.')
    date = fields.Date(
        string='Дата', required=True, index=True,
        help='День, для якого розклад змінено.')
    action = fields.Selection(
        EXCEPTION_ACTIONS, string='Що робити', required=True, default='skip',
        help='Не запускати в цей день або працювати в інший час.')
    time_start = fields.Float(
        string='Початок (виняток)',
        help='Перехід у режим Авто в цей день замість звичайного вікна розкладу.')
    time_end = fields.Float(
        string='Кінець (виняток)',
        help='Перехід у Ручний + Стоп у цей день.')
    note = fields.Char(
        string='Примітка',
        help='Чому змінено розклад (свято, роботи на об\'єкті …).')
    active = fields.Boolean(
        string='Активний', default=True,
        help='Дати старші за 30 днів архівуються щоденною чисткою.')

    _sql_constraints = [
        ('date_uniq', 'unique(genset_id, date)', 'На цю дату виняток уже є.'),
    ]

    @api.constrains('action', 'time_start', 'time_end')
    def _check_custom_time(self):
        """Для «Інший час» — кінець пізніше за початок (AC-30)."""
        for exception in self:
            if exception.action == 'custom' and exception.time_end <= exception.time_start:
                raise ValidationError(_('Кінець має бути пізніше за початок.'))
