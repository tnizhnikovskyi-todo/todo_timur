# Part of td_genset (ToDo). Власник файлу: W2 «Керування». Каркас (поля, заглушки): W0.
"""Майстер підтвердження команди пульта ``td.genset.command.wizard`` — ТР 2.3.13; SPEC 5.14 (права: ``group_tech``)."""
from odoo import api, fields, models

from ..models.genset import TEST_MODES
from ..models.genset_command import COMMANDS


class TdGensetCommandWizard(models.TransientModel):
    _name = 'td.genset.command.wizard'
    _description = 'Генератори: підтвердження команди'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, ondelete='cascade',
        help='Генератор, якому буде надіслано команду.')
    command = fields.Selection(
        COMMANDS, string='Команда', required=True,
        help='Команда пульта: Авто, Ручний, Пуск, Стоп, Тест або перемикання автомата.')
    test_mode = fields.Selection(
        TEST_MODES, string='Варіант тесту',
        help='З навантаженням (режим Тест) або без навантаження (Ручний + Пуск). Обов\'язково для тесту.')
    warning_text = fields.Text(
        string='Наслідки', compute='_compute_warning_text',
        help='Що станеться після команди: попередження про людей біля генератора, скасування таймера, '
             'живлення об\'єкта.')
    target_breaker_closed = fields.Boolean(
        string='Замкнути автомат', compute='_compute_target_breaker_closed',
        help='Для перемикачів автоматів: цільове положення (замкнути / розімкнути) за поточним знімком.')
    confirm_required = fields.Boolean(
        string='Потрібне підтвердження', compute='_compute_warning_text',
        help='Команда потребує явного підтвердження (пуск, тест, автомати, стоп без мережі).')

    @api.depends('command', 'test_mode', 'genset_id')
    def _compute_warning_text(self):
        """Тексти наслідків (SPEC 5.14). TODO: W2 — AC-25, AC-67. Заглушка W0: порожньо."""
        for wizard in self:
            wizard.warning_text = False
            wizard.confirm_required = wizard.command in ('start', 'test', 'gen_close_open', 'mains_close_open')

    @api.depends('command', 'genset_id')
    def _compute_target_breaker_closed(self):
        """Цільове положення автомата — протилежне поточному. TODO: W2 — AC-21. W0: за полями генератора."""
        for wizard in self:
            if wizard.command == 'gen_close_open':
                wizard.target_breaker_closed = not wizard.genset_id.gen_on_load
            elif wizard.command == 'mains_close_open':
                wizard.target_breaker_closed = not wizard.genset_id.mains_on_load
            else:
                wizard.target_breaker_closed = False

    def action_confirm(self):
        """Підтвердити: ``td.genset.command._enqueue(genset, command, 'button', env.user,
        target_breaker_closed=…)``; тест → ``genset._test_start(mode, user)``; ``gen_close_open`` при
        ``genset_status ∉ {8, 9}`` → ``UserError`` «Генератор ще не в режимі роботи. Спочатку «Пуск».».
        Права — ``group_tech`` (``AccessError``).

        TODO: W2 — AC-12, AC-19, AC-22, AC-24, AC-25, AC-33, AC-67. Заглушка W0: перевірка групи, закриття майстра.
        """
        self.ensure_one()
        self.genset_id._td_check_group('td_genset.group_tech')
        return {'type': 'ir.actions.act_window_close'}

