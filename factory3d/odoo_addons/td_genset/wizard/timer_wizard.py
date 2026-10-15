# Part of td_genset (ToDo). Власник файлу: W2 «Керування». Каркас (поля): W0.
"""Майстер таймера «Робота поза графіком» ``td.genset.timer.wizard`` — ТР 2.3.13; SPEC 5.14 (права: ``group_user``)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.genset_schedule import kyiv_hhmm


class TdGensetTimerWizard(models.TransientModel):
    _name = 'td.genset.timer.wizard'
    _description = 'Генератори: робота поза графіком'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, ondelete='cascade',
        help='Генератор, який працюватиме поза графіком.')
    hours = fields.Integer(
        string='Годин', default=1,
        help='Скільки годин генератор працює в режимі Авто поза графіком (0–24).')
    minutes = fields.Integer(
        string='Хвилин', default=0,
        help='Додаткові хвилини (0–59, крок 5).')
    confirm_text = fields.Char(
        string='Що станеться', compute='_compute_confirm_text',
        help='Підсумок дії перед підтвердженням.')

    @api.depends('hours', 'minutes')
    def _compute_confirm_text(self):
        for wizard in self:
            wizard.confirm_text = _('Генератор перейде в режим Авто на %(hours)s год %(minutes)02d хв, потім у Ручний '
                                    'і Стоп.', hours=wizard.hours or 0, minutes=wizard.minutes or 0)

    def _duration_minutes(self):
        """Тривалість у хвилинах; поза межами 1 хв…24 год — «Вкажіть тривалість від 1 хв до 24 год.» (AC-31)."""
        self.ensure_one()
        hours, minutes = self.hours or 0, self.minutes or 0
        total = hours * 60 + minutes
        if hours < 0 or minutes < 0 or minutes > 59 or not 1 <= total <= 24 * 60:
            raise UserError(_('Вкажіть тривалість від 1 хв до 24 год.'))
        return total

    def action_confirm(self):
        """Валідація 1 хв…24 год («Вкажіть тривалість від 1 хв до 24 год.») → ``genset._timer_start(duration_min, user)``.

        AC-31.
        """
        self.ensure_one()
        self.genset_id._td_check_group('td_genset.group_user')
        self.genset_id._timer_start(self._duration_minutes(), self.env.user)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Робота поза графіком'),
                'message': _('Таймер запущено до %(end)s.', end=kyiv_hhmm(self.genset_id.sudo().timer_end)),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
