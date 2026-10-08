# Part of td_genset (ToDo). Власник файлу: W2 «Керування». Каркас (поля): W0.
"""Майстер підтвердження команди пульта ``td.genset.command.wizard`` — ТР 2.3.13; SPEC 5.14 (права: ``group_tech``).

Діалог показує наслідки команди (тексти мокапа / ФВ-17): пуск і тест — «Переконайтеся, що біля генератора немає
людей…»; Ручний/Пуск/Стоп під час таймера — «Запущений таймер роботи поза графіком буде скасовано.»; Стоп без
мережі — «Мережі немає: після зупинки офіс залишиться без живлення.» (AC-67); автомати — повне або миттєве
знеструмлення об'єкта (AC-21). Без натискання «Підтвердити» команда не створюється.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.genset import TEST_MODES
from ..models.genset_command import BREAKER_COMMANDS, COMMANDS


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
        string='Замкнути автомат', compute='_compute_target_breaker_closed', store=True, readonly=False,
        help='Для перемикачів автоматів: цільове положення (замкнути / розімкнути) за станом на момент відкриття '
             'діалогу; якщо автомат уже в цьому положенні, команда не надсилається («Не потрібно»).')
    confirm_required = fields.Boolean(
        string='Потрібне підтвердження', compute='_compute_warning_text',
        help='Команда з ризиком для людей або живлення об\'єкта (пуск, тест, автомати, стоп без мережі) — кнопка '
             'підтвердження червона.')

    @api.depends('command', 'test_mode', 'genset_id')
    def _compute_warning_text(self):
        """Тексти наслідків (SPEC 5.14, ФВ-17; AC-12, AC-21, AC-25, AC-67)."""
        for wizard in self:
            lines = wizard._warning_lines()
            wizard.warning_text = '\n'.join(lines) if lines else False
            genset = wizard.genset_id.sudo()
            wizard.confirm_required = bool(
                wizard.command in ('start', 'test') + BREAKER_COMMANDS
                or (wizard.command == 'stop' and not genset.mains_ok))

    def _warning_lines(self):
        self.ensure_one()
        genset = self.genset_id.sudo()
        command = self.command
        if not command or not genset:
            return []
        people = _('Переконайтеся, що біля генератора немає людей і роботи з ним не ведуться.')
        timer_cancel = _('Запущений таймер роботи поза графіком буде скасовано.')
        timer_active = bool(genset.timer_end or genset.test_timer_paused_left)
        test_active = bool(genset.test_end)
        lines = []
        if command == 'auto':
            lines = [_('Перевести в режим Авто?'), _('Генератор запуститься сам, якщо зникне мережа.')]
            if test_active:
                lines.append(_('Тест буде завершено раніше.'))
        elif command == 'manual':
            lines = [_('Перевести в ручний режим?'), _('Автоматичний пуск при зникненні мережі буде вимкнено.')]
            if timer_active:
                lines.append(timer_cancel)
        elif command == 'start':
            if genset._pult_start_commands() == ['manual', 'start']:
                lines = [_('Запустити генератор?'), _('Генератор буде переведено в Ручний і запущено.'), people]
            else:
                lines = [_('Запустити генератор?'), _("Команда «Пуск» запустить двигун на об'єкті."), people]
            if timer_active:
                lines.append(timer_cancel)
        elif command == 'stop':
            lines = [_('Зупинити генератор?'), _('Генератор зніме навантаження, перейде в охолодження і зупиниться.')]
            if genset.mains_ok:
                lines.append(_('Навантаження повернеться на мережу.'))
            else:
                lines.append(_('Мережі немає: після зупинки офіс залишиться без живлення.'))
            if timer_active:
                lines.append(timer_cancel)
            if test_active:
                lines.append(_('Тест буде завершено раніше.'))
        elif command == 'test':
            minutes = self.env['td.genset.config'].sudo().get().test_minutes or 3
            lines = [_('Тестовий пуск'), people]
            if self.test_mode == 'load':
                lines.append(_('З навантаженням: режим «Тест» (05H 0002) — після прогріву навантаження перейде на '
                               'генератор.'))
            elif self.test_mode == 'idle':
                lines.append(_("Без навантаження: Ручний + Пуск (05H 0004, 0000) — двигун працює, об'єкт лишається "
                               "на мережі."))
            else:
                lines.append(_('Оберіть варіант: з навантаженням або без навантаження.'))
            lines.append(_('Через %(minutes)s хв генератор сам повернеться в режим за розкладом або таймером. '
                           'Завершити раніше — Авто або Стоп.', minutes=minutes))
            if timer_active:
                lines.append(_('Таймер не скасовується: після тесту — знову Авто за таймером.'))
        elif command == 'gen_close_open':
            if genset.gen_on_load:
                lines = [_('Розімкнути автомат генератора?'), _('Навантаження буде переведено на мережу.')]
                if not genset.mains_ok:
                    lines.append(_("Мережі немає: об'єкт залишиться без живлення."))
            else:
                lines = [_('Перевести навантаження на генератор?'),
                         _('Автомат мережі розімкнеться, автомат генератора замкнеться.'),
                         _("Під час перемикання об'єкт на мить залишиться без живлення.")]
                if genset.genset_status not in ('8', '9'):
                    lines.append(_('Генератор ще не в режимі роботи. Спочатку «Пуск».'))
        elif command == 'mains_close_open':
            if genset.mains_on_load:
                lines = [_("Відключити об'єкт від мережі?"), _('Автомат мережі розімкнеться.')]
                if not genset.gen_on_load:
                    lines.append(_("Генератор не живить об'єкт: живлення зникне повністю."))
            else:
                lines = [_('Перевести навантаження на мережу?'),
                         _('Автомат генератора розімкнеться, автомат мережі замкнеться.'),
                         _("Під час перемикання об'єкт на мить залишиться без живлення.")]
        return lines

    @api.depends('command', 'genset_id')
    def _compute_target_breaker_closed(self):
        """Цільове положення автомата — протилежне поточному на момент відкриття діалогу (ФВ-14, AC-21)."""
        for wizard in self:
            genset = wizard.genset_id.sudo()
            if wizard.command == 'gen_close_open':
                wizard.target_breaker_closed = not genset.gen_on_load
            elif wizard.command == 'mains_close_open':
                wizard.target_breaker_closed = not genset.mains_on_load
            else:
                wizard.target_breaker_closed = False

    def action_confirm(self):
        """Підтвердити: ``td.genset.command._enqueue(genset, command, 'button', env.user,
        target_breaker_closed=…)``; «Пуск», коли контролер не в Ручному і двигун стоїть, — пакет «Ручний» + «Пуск»
        (``_pult_start_commands``, D-02); тест → ``genset._test_start(mode, user)``; ``gen_close_open`` (замкнути) при
        ``genset_status ∉ {8, 9}`` → ``UserError`` «Генератор ще не в режимі роботи. Спочатку «Пуск».»; без
        зв'язку пульт недоступний. Права — ``group_tech`` (``AccessError``).

        AC-12, AC-19, AC-22, AC-24, AC-25, AC-33, AC-67.
        """
        self.ensure_one()
        genset = self.genset_id
        genset._td_check_group('td_genset.group_tech')
        state = genset.sudo()
        if state.link_state != 'online':
            raise UserError(_("Немає зв'язку з модулем — команди неможливо доставити."))
        user = self.env.user
        command = self.command
        if command == 'test':
            if not self.test_mode:
                raise UserError(_('Оберіть варіант тесту: з навантаженням або без навантаження.'))
            genset._test_start(self.test_mode, user)
            label = dict(self._fields['test_mode']._description_selection(self.env)).get(self.test_mode)
            return self._notification(_('Тест «%(mode)s» запущено, очікуємо підтвердження.', mode=label))
        target = None
        if command in BREAKER_COMMANDS:
            target = bool(self.target_breaker_closed)
            if command == 'gen_close_open' and target and state.genset_status not in ('8', '9'):
                raise UserError(_('Генератор ще не в режимі роботи. Спочатку «Пуск».'))
        batch = state._pult_start_commands() if command == 'start' else [command]
        genset._pult_prepare(command, user)
        if len(batch) > 1:
            # «Пуск» не в режимі Ручний: пакет «Ручний» + «Пуск» (D-02, relay_api.md 7.1)
            records = self.env['td.genset.command']._enqueue_batch(genset, batch, 'button', user)
            label = ' + '.join(record._label('command') for record in records)
            return self._notification(_('Команду «%(command)s» прийнято, очікуємо підтвердження.', command=label))
        record = self.env['td.genset.command']._enqueue(genset, command, 'button', user, target_breaker_closed=target)
        label = record._label('command')
        if command in BREAKER_COMMANDS and record.state == 'to_send' and not self._fresh_reading(state):
            return self._notification(_('Команду «%(command)s» прийнято: очікуємо показання (останній знімок старший '
                                        'за 2 хв).', command=label), 'warning')
        return self._notification(_('Команду «%(command)s» прийнято, очікуємо підтвердження.', command=label))

    @api.model
    def _fresh_reading(self, genset):
        reading = genset.last_reading_id
        return bool(reading and reading.ts and reading.ts >= fields.Datetime.subtract(fields.Datetime.now(), minutes=2))

    @api.model
    def _notification(self, message, notif_type='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Пульт'),
                'message': message,
                'type': notif_type,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
