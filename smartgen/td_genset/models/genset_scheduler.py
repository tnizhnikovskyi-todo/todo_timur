# Part of td_genset (ToDo). Власник файлу: W2 «Керування». Каркас: W0.
"""``td.genset`` (inherit): планувальник, таймер, тест, кнопки пульта — ТР 2.7, А.6; SPEC 9.

Розклад працює «лише на переходах»: команди створюються, коли змінюється стан «у вікні» (``sched_in_window``);
між переходами режим не контролюється. Межі вікон — UTC-моменти ``kyiv_localize`` (DST: неіснуючий час → 04:00,
повторна година → перша), тож кожна межа спрацьовує один раз (AC-37). Пропущений під час простою перехід
виконується з ``late_transition_at`` (AC-34). Таймер пріоритетніший за кінець вікна, тест — за обидва.
"""
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from .genset_schedule import kyiv_hhmm, kyiv_localize, to_kyiv, to_utc

_logger = logging.getLogger(__name__)

TIMER_MIN_MINUTES = 1
TIMER_MAX_MINUTES = 24 * 60
SCHEDULER_GAP = timedelta(minutes=2)   # простій планувальника довше — перехід «із запізненням» (А.6 п. 3)
LATE_AFTER = timedelta(minutes=1)      # перехід, що минув більш ніж на крок cron
HORIZON_DAYS = 7                       # «Наступна подія» — найближчий перехід за 7 днів (ФВ-23)
PULT_MODE_COMMANDS = ('auto', 'manual', 'start', 'stop')


class TdGensetScheduler(models.Model):
    _inherit = 'td.genset'

    # ------------------------------------------------------------------ cron «Генератори: розклад, таймер, тест, ескалація»
    @api.model
    def _cron_scheduler(self):
        """Точка входу cron ``cron_scheduler`` (1 хв, priority 3) — А.6, кроки 1–8: для кожного генератора з
        ``relay_enabled`` (рядок — ``FOR NO KEY UPDATE SKIP LOCKED``) вікно, перший запуск, пропущений перехід,
        перехід (тест/таймер/команди), таймер, тест; потім супутні перевірки ``td.genset.alarm._cron_escalate()``,
        ``td.genset.refuel._reconcile_pending()``, ``_check_maintenance()``, ``_check_fuel_stock()``.
        Винятки перехоплені (cron не падає).

        AC-28, AC-30, AC-31, AC-32, AC-33, AC-34, AC-35, AC-37.
        """
        now = fields.Datetime.now()
        gensets = self.sudo().search([('relay_enabled', '=', True)])
        for genset in gensets:
            try:
                with self.env.cr.savepoint():
                    if genset._td_lock_row():
                        genset._scheduler_step(now)
            except Exception:  # noqa: BLE001 — cron не має падати (А.7)
                _logger.warning('td_genset: scheduler step failed for genset %s', genset.id, exc_info=True)
        side_checks = (
            ('escalation', lambda: self.env['td.genset.alarm'].sudo()._cron_escalate()),
            ('refuel reconciliation', lambda: self.env['td.genset.refuel'].sudo()._reconcile_pending()),
            ('maintenance', lambda: gensets._check_maintenance()),
            ('fuel stock', lambda: gensets._check_fuel_stock()),
        )
        for label, check in side_checks:
            try:
                with self.env.cr.savepoint():
                    check()
            except Exception:  # noqa: BLE001
                _logger.warning('td_genset: scheduler side check failed: %s', label, exc_info=True)
        return None

    def _td_lock_row(self):
        """``SELECT … FOR NO KEY UPDATE SKIP LOCKED`` рядка генератора: зайнятий іншим воркером — пропустити."""
        self.ensure_one()
        self.env.cr.execute(SQL('SELECT id FROM td_genset WHERE id = %s FOR NO KEY UPDATE SKIP LOCKED', self.id))
        return bool(self.env.cr.fetchone())

    def _scheduler_step(self, now):
        """Кроки 1–7 А.6 для одного генератора: спершу перехід розкладу, потім кінець таймера і тесту."""
        self.ensure_one()
        genset = self.sudo()
        genset._scheduler_transition(now)
        if genset.timer_end and genset.timer_end <= now:
            genset._timer_expire()
        if genset.test_end and genset.test_end <= now:
            genset._test_finish()

    def _scheduler_transition(self, now):
        """Кроки 1–4 А.6: стан «у вікні» на ``now``; перший запуск лише запам'ятовує стан; зміна →
        ``_schedule_transition`` (із запізненням, якщо cron простоював). Викликається і перед зупинкою таймера
        (D-04): перехід, що вже настав, обробляється, поки таймер діє, — «Пропущено: діє таймер до HH:MM», а не
        другий пакет «Ручний + Стоп» після таймера."""
        self.ensure_one()
        genset = self.sudo()
        in_window = genset._in_window(to_kyiv(now))
        if not genset.sched_last_eval_at:
            # перший запуск не «зрушує» генератор — лише запам'ятати стан (А.6 п. 2)
            genset.write({'sched_in_window': in_window, 'sched_last_eval_at': now})
            return
        if in_window != genset.sched_in_window:
            late = False
            if now - genset.sched_last_eval_at > SCHEDULER_GAP:
                boundary = genset._next_transition(to_kyiv(genset.sched_last_eval_at))
                if boundary and boundary[0] <= now - LATE_AFTER:
                    late = boundary[0]
            genset._schedule_transition(in_window, now, late)
        genset.write({'sched_in_window': in_window, 'sched_last_eval_at': now})

    def _schedule_transition(self, entering, now, late=False):
        """Перехід розкладу (А.6 п. 4): тест → «Пропущено: іде тест»; таймер → вхід «Не потрібно: уже Авто за
        таймером» / вихід «Пропущено: діє таймер до HH:MM»; інакше скасувати незавершені команди попереднього
        переходу і надіслати ``auto`` або «Ручний + Стоп» (якщо така сама команда вже в роботі — «Вже надіслано»,
        D-04); ``control_source = 'schedule'``."""
        self.ensure_one()
        genset = self.sudo()
        commands = self.env['td.genset.command'].sudo()
        moment = late or now
        source = 'exception' if genset._exception_for(to_kyiv(moment).date()) else 'schedule'
        command = 'auto' if entering else 'manual'
        if genset.test_end:
            commands._log_final(genset, command, source, None, 'skipped', _('Пропущено: іде тест'),
                                late_transition_at=late)
        elif genset.timer_end:
            if entering:
                commands._log_final(genset, 'auto', source, None, 'not_needed', _('Не потрібно: уже Авто за таймером'),
                                    late_transition_at=late,
                                    body=_('Початок вікна: команда не потрібна — генератор уже в Авто за таймером.'))
            else:
                until = kyiv_hhmm(genset.timer_end)
                commands._log_final(genset, 'manual', source, None, 'skipped',
                                    _('Пропущено: діє таймер до %(time)s', time=until), late_transition_at=late,
                                    body=_('Кінець вікна: команду пропущено — діє таймер до %(time)s. Після таймера — '
                                           'Ручний + Стоп.', time=until))
        else:
            commands._enqueue_target(genset, ['auto'] if entering else ['manual', 'stop'], source, None,
                                     _('новий перехід'), late_transition_at=late)
            genset.control_source = 'schedule'
        genset._notify_bus('schedule', {'in_window': entering})

    # ------------------------------------------------------------------ вікна розкладу
    def _exception_for(self, day):
        """Активний день-виняток генератора на дату (або порожній recordset)."""
        self.ensure_one()
        return self.env['td.genset.schedule.exception'].sudo().search(
            [('genset_id', '=', self.id), ('date', '=', day)], limit=1)

    def _in_window(self, dt_kyiv):
        """Чи ``dt_kyiv`` (aware; naive — як UTC) у вікні розкладу з урахуванням винятку на дату.

        Вікна дня порівнюються як UTC-моменти ``kyiv_localize`` (DST, AC-37).

        :rtype: bool
        AC-28, AC-30, AC-37.
        """
        self.ensure_one()
        moment = to_utc(dt_kyiv)
        day = to_kyiv(moment).date()
        return any(start <= moment < end for start, end in self._window_moments(day))

    def _window_bounds(self, date_kyiv):
        """Вікна дня після застосування винятку (``skip`` → ``[]``; ``custom`` → одне вікно), увімкнені рядки дня
        тижня, відсортовані, вікна, що торкаються, об'єднано.

        :param date_kyiv: ``date`` або ``datetime`` (береться дата).
        :rtype: list[tuple[float, float]]
        AC-28, AC-30.
        """
        self.ensure_one()
        day = date_kyiv.date() if isinstance(date_kyiv, datetime) else date_kyiv
        exception = self._exception_for(day)
        if exception:
            if exception.action == 'custom' and exception.time_end > exception.time_start:
                return [(exception.time_start, exception.time_end)]
            return []
        weekday = str(day.weekday())
        bounds = sorted((line.time_start, line.time_end) for line in self.sudo().schedule_line_ids
                        if line.enabled and line.dayofweek == weekday and line.time_end > line.time_start)
        merged = []
        for start, end in bounds:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def _window_moments(self, day):
        """Вікна дня як UTC-моменти ``[(початок, кінець)]`` (порожні після DST-зсуву відкинуто)."""
        moments = []
        for start, end in self._window_bounds(day):
            start_at, end_at = kyiv_localize(day, start), kyiv_localize(day, end)
            if start_at < end_at:
                moments.append((start_at, end_at))
        return moments

    def _next_transition(self, after_kyiv):
        """Найближча межа за 7 днів після ``after_kyiv``: ``(момент UTC naive, 'start' | 'end')`` або ``None``.

        Вікна, що торкаються (у тому числі через північ), — одне вікно: межа між ними не перехід.

        AC-34, AC-36.
        """
        self.ensure_one()
        after = to_utc(after_kyiv)
        first_day = to_kyiv(after).date()
        intervals = []
        for offset in range(-1, HORIZON_DAYS + 1):
            intervals.extend(self._window_moments(first_day + timedelta(days=offset)))
        intervals.sort()
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        limit = after + timedelta(days=HORIZON_DAYS)
        for start, end in merged:
            if start > after:
                return (start, 'start') if start <= limit else None
            if end > after:
                return (end, 'end') if end <= limit else None
        return None

    def _follow_schedule(self, source, requested_by=None):
        """Стан за розкладом після таймера/тесту (А.6 п. 6): у вікні → ``auto`` (лише якщо режим не ``auto``),
        поза вікном → пакет ``manual`` + ``stop``; незавершені команди попереднього стану скасовуються; така сама
        команда вже в роботі (перехід розкладу щойно надіслав) — «Вже надіслано», без дубля (D-04);
        ``control_source = 'schedule'``.

        :param str source: ``timer`` | ``test``.
        AC-31, AC-32, AC-33.
        """
        self.ensure_one()
        genset = self.sudo()
        commands = self.env['td.genset.command'].sudo()
        now = fields.Datetime.now()
        reason = _('повернення до розкладу')
        if genset._in_window(to_kyiv(now)):
            if genset.controller_mode != 'auto':
                commands._enqueue_target(genset, ['auto'], source, requested_by, reason)
            else:
                commands._cancel_pending(genset, reason)
        else:
            commands._enqueue_target(genset, ['manual', 'stop'], source, requested_by, reason)
        genset.control_source = 'schedule'
        genset._notify_bus('schedule')
        return None

    # ------------------------------------------------------------------ таймер «Робота поза графіком»
    def _timer_check_allowed(self):
        """Умови кнопок таймера (А.6, 2.5): зв'язок, немає блокування на контролері, команди дозволено."""
        genset = self.sudo()
        if genset.link_state != 'online':
            raise UserError(_("Немає зв'язку з модулем — команди неможливо доставити."))
        if genset.remote_lock:
            raise UserError(_('Дистанційне керування заблоковано на контролері.'))
        if not genset.commands_allowed:
            raise UserError(_('Команди вимкнено в Odoo: увімкніть «Дозволити команди» на картці генератора.'))

    def _timer_start(self, duration_min, user):
        """Запуск таймера (ФВ-20): перевірки ``group_user``, зв'язок, ``remote_lock``, ``commands_allowed``;
        валідація 1 хв…24 год («Вкажіть тривалість від 1 хв до 24 год.»); ``_cancel_pending('таймер')``,
        ``_enqueue(genset, 'auto', 'timer', user)``, ``control_source = 'timer'``, чатер.

        AC-25, AC-31, AC-32.
        """
        self.ensure_one()
        self._td_check_group('td_genset.group_user')
        duration = int(duration_min or 0)
        if not TIMER_MIN_MINUTES <= duration <= TIMER_MAX_MINUTES:
            raise UserError(_('Вкажіть тривалість від 1 хв до 24 год.'))
        genset = self.sudo()
        genset._timer_check_allowed()
        if genset.timer_end or genset.test_timer_paused_left:
            raise UserError(_('Таймер уже запущено: подовжте або зупиніть його.'))
        if genset.test_end:
            raise UserError(_('Іде тестовий пуск: запустіть таймер після його завершення.'))
        now = fields.Datetime.now()
        end = now + timedelta(minutes=duration)
        commands = self.env['td.genset.command'].sudo()
        commands._cancel_pending(genset, _('таймер'))
        genset.write({'timer_end': end, 'timer_started_at': now, 'timer_user_id': user.id,
                      'control_source': 'timer'})
        commands._enqueue(genset, 'auto', 'timer', user)
        genset.message_post(
            body=_('Таймер роботи поза графіком: %(hours)s год %(minutes)02d хв, до %(end)s, потім за розкладом '
                   '(запустив %(user)s).', hours=duration // 60, minutes=duration % 60, end=kyiv_hhmm(end),
                   user=user.name),
            subtype_xmlid='td_genset.mt_command')
        genset._notify_bus('timer', {'timer_end': fields.Datetime.to_string(end)})
        return None

    def _timer_extend(self, minutes, user):
        """Подовження таймера на ``minutes`` без зупинки — не далі ``now + 24 год`` (інакше ``UserError``
        «Таймер уже на максимумі — 24 год.»); під час тесту подовжується залишок на паузі.

        AC-31.
        """
        self.ensure_one()
        self._td_check_group('td_genset.group_user')
        genset = self.sudo()
        genset._timer_check_allowed()
        now = fields.Datetime.now()
        limit = now + timedelta(minutes=TIMER_MAX_MINUTES)
        if genset.timer_end:
            current = genset.timer_end
        elif genset.test_end and genset.test_timer_paused_left:
            current = genset.test_end + timedelta(seconds=genset.test_timer_paused_left)
        else:
            raise UserError(_('Таймер не запущено.'))
        if current >= limit - timedelta(minutes=1):
            raise UserError(_('Таймер уже на максимумі — 24 год.'))
        added = min(int(minutes), int((limit - current).total_seconds() // 60))
        new_end = current + timedelta(minutes=added)
        if genset.timer_end:
            genset.timer_end = new_end
        else:
            genset.test_timer_paused_left += added * 60
        genset.message_post(body=_('Таймер подовжено на %(minutes)s хв, до %(end)s.', minutes=added,
                                   end=kyiv_hhmm(new_end)),
                            subtype_xmlid='td_genset.mt_command')
        genset._notify_bus('timer', {'timer_end': fields.Datetime.to_string(new_end)})
        return None

    def _timer_stop(self, user):
        """Зупинка таймера: ``timer_end = NULL``, ``_follow_schedule('timer')`` (у вікні — нічого, якщо вже Авто;
        поза вікном — «Ручний + Стоп»), чатер. Під час тесту — скасовується таймер на паузі.

        AC-31.
        """
        self.ensure_one()
        self._td_check_group('td_genset.group_user')
        genset = self.sudo()
        genset._timer_check_allowed()
        if not genset.timer_end and not genset.test_timer_paused_left:
            raise UserError(_('Таймер не запущено.'))
        if genset.relay_enabled:
            # перехід розкладу, що вже настав, — поки таймер діє (D-04): «Пропущено: діє таймер до HH:MM»
            genset._scheduler_transition(fields.Datetime.now())
        genset.write({'timer_end': False, 'timer_started_at': False, 'timer_user_id': False,
                      'test_timer_paused_left': 0})
        genset.message_post(body=_('Зупинив таймер роботи поза графіком.'), subtype_xmlid='td_genset.mt_command')
        if not genset.test_end:
            genset._follow_schedule('timer', requested_by=user)
        genset._notify_bus('timer', {'timer_end': False})
        return None

    def _timer_expire(self):
        """Кінець таймера (А.6 п. 6): ``timer_end = NULL``, чатер «Таймер завершився.», ``_follow_schedule``."""
        self.ensure_one()
        genset = self.sudo()
        genset.write({'timer_end': False, 'timer_started_at': False, 'timer_user_id': False})
        genset.message_post(body=_('Таймер завершився.'), subtype_xmlid='td_genset.mt_command')
        genset._follow_schedule('timer')
        genset._notify_bus('timer', {'timer_end': False})

    def _timer_cancel_by_command(self, command):
        """Ручний / Пуск / Стоп з пульта скасовують таймер (ФВ-20): чатер «Таймер скасовано командою Пуск.»."""
        self.ensure_one()
        genset = self.sudo()
        if not genset.timer_end and not genset.test_timer_paused_left:
            return
        label = self.env['td.genset.command']._label('command', command)
        genset.write({'timer_end': False, 'timer_started_at': False, 'timer_user_id': False,
                      'test_timer_paused_left': 0})
        self.env['td.genset.command'].sudo()._cancel_pending(genset, _('таймер скасовано'), sources=('timer',))
        genset.message_post(body=_('Таймер скасовано командою %(command)s.', command=label),
                            subtype_xmlid='td_genset.mt_command')
        genset._notify_bus('timer', {'timer_end': False})

    # ------------------------------------------------------------------ тест
    def _test_start(self, mode, user):
        """Тест (ФВ-22): ``load`` → ``_enqueue(genset, 'test', 'test', user)``; ``idle`` → пакет ``manual`` +
        ``start``; ``test_end = now + config.test_minutes``, ``control_source = 'test'``; таймер на паузу
        (``test_timer_paused_left``), а якщо він закінчився б під час тесту — його кінець переноситься на кінець
        тесту (після тесту — за розкладом).

        AC-33.
        """
        self.ensure_one()
        self._td_check_group('td_genset.group_tech')
        if mode not in ('load', 'idle'):
            raise UserError(_('Оберіть варіант тесту: з навантаженням або без навантаження.'))
        genset = self.sudo()
        if genset.test_end:
            raise UserError(_('Тест уже йде.'))
        now = fields.Datetime.now()
        minutes = self.env['td.genset.config'].sudo().get().test_minutes or 3
        test_end = now + timedelta(minutes=minutes)
        commands = self.env['td.genset.command'].sudo()
        commands._cancel_pending(genset, _('тест'))
        vals = {'test_end': test_end, 'test_mode': mode, 'control_source': 'test'}
        timer_note = ''
        if genset.timer_end:
            paused = int((genset.timer_end - now).total_seconds()) if genset.timer_end > test_end else 0
            vals.update(test_timer_paused_left=paused, timer_end=False)
            if paused:
                timer_note = _('Таймер на паузі до кінця тесту.')
            else:
                vals.update(timer_started_at=False, timer_user_id=False)
                timer_note = _('Таймер закінчиться разом із тестом.')
        genset.write(vals)
        if mode == 'load':
            commands._enqueue(genset, 'test', 'test', user)
            text = _('Тестовий пуск з навантаженням на %(minutes)s хв, потім повернення в режим за розкладом або '
                     'таймером.', minutes=minutes)
        else:
            commands._enqueue_batch(genset, ['manual', 'start'], 'test', user)
            text = _('Тестовий пуск без навантаження (Ручний + Пуск) на %(minutes)s хв, потім повернення в режим '
                     'за розкладом або таймером.', minutes=minutes)
        if timer_note:
            text = '%s %s' % (text, timer_note)
        genset.message_post(body=text, subtype_xmlid='td_genset.mt_command')
        genset._notify_bus('test', {'test_end': fields.Datetime.to_string(test_end), 'test_mode': mode})
        return None

    def _test_finish(self):
        """Кінець тесту (А.6 п. 7): таймер на паузі → ``timer_end = now + paused_left``, ``control_source='timer'``,
        ``auto`` (якщо режим не ``auto``); інакше ``_follow_schedule('test')``; чатер «Тест завершено через N хв:
        повернення в режим …».

        AC-33.
        """
        self.ensure_one()
        genset = self.sudo()
        if not genset.test_end:
            return None
        now = fields.Datetime.now()
        minutes = self.env['td.genset.config'].sudo().get().test_minutes or 3
        paused = genset.test_timer_paused_left
        commands = self.env['td.genset.command'].sudo()
        genset.write({'test_end': False, 'test_mode': False, 'test_timer_paused_left': 0})
        if paused:
            commands._cancel_pending(genset, _('кінець тесту'))
            genset.write({'timer_end': now + timedelta(seconds=paused), 'control_source': 'timer'})
            if genset.controller_mode != 'auto':
                commands._enqueue(genset, 'auto', 'test', None)
            label = _('Авто за таймером')
        else:
            label = _('Авто за розкладом') if genset._in_window(to_kyiv(now)) else _('Ручний + Стоп')
            genset._follow_schedule('test')
        genset.message_post(body=_('Тест завершено через %(minutes)s хв: повернення в режим %(label)s.',
                                   minutes=minutes, label=label),
                            subtype_xmlid='td_genset.mt_command')
        genset._notify_bus('test', {'test_end': False})
        return None

    def _test_end_early(self, command):
        """«Авто» або «Стоп» з пульта під час тесту завершують тест раніше; таймер з паузи повертається."""
        self.ensure_one()
        genset = self.sudo()
        if not genset.test_end:
            return
        paused = genset.test_timer_paused_left
        now = fields.Datetime.now()
        vals = {'test_end': False, 'test_mode': False, 'test_timer_paused_left': 0}
        if paused:
            vals.update(timer_end=now + timedelta(seconds=paused), control_source='timer')
        genset.write(vals)
        label = self.env['td.genset.command']._label('command', command)
        genset.message_post(body=_('Тест завершено раніше командою %(command)s.', command=label),
                            subtype_xmlid='td_genset.mt_command')
        genset._notify_bus('test', {'test_end': False})

    def _pult_start_commands(self):
        """Команди для «Пуск» з пульта (D-02): контролер виконує «Пуск» лише в режимі Ручний (``relay_api.md`` 7.1),
        тож коли режим не Ручний (Авто, Стоп, Тест…) і двигун стоїть — пакет ``manual`` + ``start``, як «Тест без
        навантаження»; у Ручному — лише ``start``. Двигун уже працює або триває пуск (``is_running``) — теж лише
        ``start`` («Не потрібно: генератор уже працює» / очікування кінця пуску), без зміни режиму.

        :rtype: list[str]
        """
        self.ensure_one()
        genset = self.sudo()
        if genset.controller_mode != 'manual' and not genset.is_running:
            return ['manual', 'start']
        return ['start']

    def _pult_prepare(self, command, user):
        """Перед командою пульта (А.6 «Пульт», ФВ-20, ФВ-22): Авто/Стоп під час тесту завершують тест; Ручний/Пуск/
        Стоп скасовують таймер; незавершені автоматичні команди (розклад/таймер/тест) скасовуються — керує людина;
        ``control_source`` — ``manual`` (або ``timer``, якщо таймер триває)."""
        self.ensure_one()
        genset = self.sudo()
        if command in ('auto', 'stop') and genset.test_end:
            genset._test_end_early(command)
        if command in ('manual', 'start', 'stop'):
            genset._timer_cancel_by_command(command)
        if command in PULT_MODE_COMMANDS:
            self.env['td.genset.command'].sudo()._cancel_pending(genset, _('команда з пульта'))
            genset.control_source = 'timer' if genset.timer_end else 'manual'

    # ------------------------------------------------------------------ «Наступна подія»
    @api.depends('timer_end', 'test_end', 'test_mode', 'controller_mode',
                 'schedule_line_ids.dayofweek', 'schedule_line_ids.time_start', 'schedule_line_ids.time_end',
                 'schedule_line_ids.enabled', 'exception_ids.date', 'exception_ids.action',
                 'exception_ids.time_start', 'exception_ids.time_end')
    def _compute_next_event_text(self):
        """«Наступна подія» (ФВ-23, А.6): тест → «HH:MM → кінець тесту · далі <Авто за таймером | Авто за
        розкладом | Ручний + Стоп>»; таймер → «HH:MM → кінець таймера · далі за розкладом»; інакше найближчий
        перехід за 7 днів («сьогодні/завтра/<день>, HH:MM → Авто | Ручний + Стоп») або «Розклад вимкнено».

        AC-36.
        """
        now = fields.Datetime.now()
        today = to_kyiv(now).date()
        for genset in self:
            if not genset.id:
                genset.next_event_text = False
                continue
            if genset.test_end:
                if genset.test_timer_paused_left:
                    after = _('Авто за таймером')
                elif genset._in_window(to_kyiv(genset.test_end)):
                    after = _('Авто за розкладом')
                else:
                    after = _('Ручний + Стоп')
                text = _('%(time)s → кінець тесту · далі %(after)s', time=kyiv_hhmm(genset.test_end), after=after)
            elif genset.timer_end:
                text = _('%(time)s → кінець таймера · далі за розкладом', time=kyiv_hhmm(genset.timer_end))
            else:
                transition = genset._next_transition(to_kyiv(now))
                if not transition:
                    text = _('Розклад вимкнено')
                else:
                    moment, kind = transition
                    local = to_kyiv(moment)
                    text = _('%(day)s, %(time)s → %(action)s', day=genset._day_word(local.date(), today),
                             time=local.strftime('%H:%M'),
                             action=_('Авто') if kind == 'start' else _('Ручний + Стоп'))
            genset.next_event_text = text

    @api.model
    def _day_word(self, day, today):
        """«сьогодні» / «завтра» / назва дня тижня."""
        if day == today:
            return _('сьогодні')
        if day == today + timedelta(days=1):
            return _('завтра')
        weekdays = [_('понеділок'), _('вівторок'), _('середа'), _('четвер'), _("п'ятниця"), _('субота'),
                    _('неділя')]
        return weekdays[day.weekday()]

    # ------------------------------------------------------------------ кнопки пульта / таймера
    def action_open_command_wizard(self):
        """Майстер підтвердження команди пульта (``group_tech``); команда — з контексту ``default_command``.

        AC-12, AC-24, AC-25, AC-67.
        """
        self.ensure_one()
        self._td_check_group('td_genset.group_tech')
        action = self.env['ir.actions.act_window']._for_xml_id('td_genset.action_td_genset_command_wizard')
        context = {'default_genset_id': self.id}
        if self.env.context.get('default_command'):
            context['default_command'] = self.env.context['default_command']
        action['context'] = context
        return action

    def action_open_timer_wizard(self):
        """Майстер таймера «Робота поза графіком» (``group_user``).

        AC-31.
        """
        self.ensure_one()
        self._td_check_group('td_genset.group_user')
        action = self.env['ir.actions.act_window']._for_xml_id('td_genset.action_td_genset_timer_wizard')
        action['context'] = {'default_genset_id': self.id}
        return action

    def action_timer_extend_15(self):
        """Кнопка «+15 хв» (AC-31)."""
        self._td_check_group('td_genset.group_user')
        for genset in self:
            genset._timer_extend(15, self.env.user)
        return False

    def action_timer_extend_30(self):
        """Кнопка «+30 хв» (AC-31)."""
        self._td_check_group('td_genset.group_user')
        for genset in self:
            genset._timer_extend(30, self.env.user)
        return False

    def action_timer_extend_60(self):
        """Кнопка «+60 хв» (AC-31)."""
        self._td_check_group('td_genset.group_user')
        for genset in self:
            genset._timer_extend(60, self.env.user)
        return False

    def action_timer_stop(self):
        """Кнопка «Зупинити таймер» (``confirm`` у поданні, AC-31)."""
        self._td_check_group('td_genset.group_user')
        for genset in self:
            genset._timer_stop(self.env.user)
        return False
