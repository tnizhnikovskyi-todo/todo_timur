# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас (поля, заглушки): W0.
"""Тривога ``td.genset.alarm`` — ТР 2.3.4, 2.8.2–2.8.5; SPEC 5.4, 9."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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

    # ------------------------------------------------------------------ інтерфейси W1 (заглушки)
    @api.model
    def _raise(self, genset, code, level, name, description='', source=None, tech=False):
        """Підняти тривогу: без дубля активної на ``(genset, code)``; ``state='active'``,
        ``next_escalation_at=now``; чатер ``mt_alarm``; ``tech=True`` → адресати — ``group_tech``;
        ``_notify_bus('alarm')``.

        :return: запис ``td.genset.alarm`` (наявний або новий).
        TODO: W1 — AC-41, AC-42, AC-45. Заглушка W0: порожній recordset.
        """
        return self.browse()

    @api.model
    def _clear(self, genset, code, note=''):
        """Зняти тривогу: ``state='cleared'``, ``date_cleared``, ``next_escalation_at=NULL``, чатер «… — знято»,
        ``_notify_bus('alarm')``.

        TODO: W1 — AC-41. Заглушка W0: нічого не робить.
        """
        return None

    def _can_ack(self, user):
        """Учасник ланцюжка (``config.level_ids.user_id``) або ``group_tech``.

        TODO: W1 — AC-43. Заглушка W0: лише ``group_tech``.
        """
        return bool(user) and user.has_group('td_genset.group_tech')

    def action_ack(self):
        """Кнопка «Прийняв»: перевірка ``_can_ack`` (інакше ``AccessError`` «Прийняти тривогу може учасник
        ланцюжка ескалації або тех. адміністратор.»); ``state='acked'``, зупинка ескалації, чатер.

        TODO: W1 — AC-43. Заглушка W0: нічого не змінює.
        """
        return False

    @api.model
    def _cron_escalate(self):
        """Ескалація 2.8.2: наступний рівень, правила ``notify_*``, тихі години, ``message_notify``.

        TODO: W1 — AC-42. Заглушка W0: нічого не робить.
        """
        return None

    @api.model
    def _evaluate_current(self, genset):
        """Одноразова оцінка всіх правил тривог за останнім знімком після догону (А.7).

        TODO: W1 — AC-45. Заглушка W0: нічого не робить.
        """
        return None
