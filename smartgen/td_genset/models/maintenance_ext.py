# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (поля, хук write): W0.
"""Розширення стандартних моделей ТО — ТР 2.3.12, 2.9; SPEC 5.13.

Закриття заявки (перехід у стадію з ознакою «виконано») фіксує мотогодини генератора
(``td_run_hours_at_close``) — від них і дати закриття рахується наступне ТО (``td.genset._compute_maint``).
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .genset_fuel import MAINT_ACTIVITY_SUMMARY, fmt_num


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    td_genset_id = fields.Many2one(
        'td.genset', string='Генератор', readonly=True, index='btree_not_null', ondelete='set null',
        help='Генератор, для якого створено це обладнання (модуль «Генератори»).')


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    td_partner_id = fields.Many2one(
        'res.partner', string='Підрядник', ondelete='set null',
        help='Підрядник, який виконує роботи. Лише контакт — у систему він не заходить.')
    td_genset_id = fields.Many2one(
        'td.genset', string='Генератор (ТО)', related='equipment_id.td_genset_id', store=True, index='btree_not_null',
        help='Генератор обладнання заявки.')
    td_run_hours_at_close = fields.Float(
        string='Мотогодини при закритті', readonly=True,
        help='Мотогодини генератора на момент переведення заявки у стадію «виконано» — від них новий відлік ТО.')

    @api.model_create_multi
    def create(self, vals_list):
        """Заявку ТО генератора одразу в стадії «виконано» створює лише тех. адміністратор (див. ``write``)."""
        requests = super().create(vals_list)
        if requests.filtered(lambda request: request.td_genset_id and request.stage_id.done):
            requests._td_check_close_rights()
        return requests

    def write(self, vals):
        """Перехід заявки генератора в стадію «виконано» (з іншої стадії) → ``_td_on_done`` (AC-54). Закрити заявку
        ТО генератора може лише тех. адміністратор: закриття скидає відлік ТО і знімає тривогу «Термін ТО» (матриця
        прав «ТО — Т», AC-56; security-review WARNING-2). Заявки іншого обладнання — стандартні права."""
        was_done = {request.id: request.stage_id.done for request in self} if 'stage_id' in vals else {}
        if vals.get('stage_id') and self.env['maintenance.stage'].browse(vals['stage_id']).done \
                and self.filtered(lambda request: request.td_genset_id and not was_done.get(request.id)):
            self._td_check_close_rights()
        result = super().write(vals)
        if 'stage_id' in vals:
            self.filtered(
                lambda request: request.td_genset_id and request.stage_id.done and not was_done.get(request.id)
            )._td_on_done()
        return result

    def _td_check_close_rights(self):
        """Закриття заявки ТО генератора — лише ``td_genset.group_tech`` (cron/суперкористувач проходить)."""
        if self.env.su or self.env.user.has_group('td_genset.group_tech'):
            return
        raise AccessError(_('Закрити заявку ТО генератора (стадія «виконано») може лише тех. адміністратор — група '
                            '«Генератори: Тех. адміністратор». Закриття фіксує мотогодини і починає новий відлік ТО.'))

    def _td_on_done(self):
        """Хук закриття заявки ТО (ФВ-35, ФВ-36, AC-54): ``td_run_hours_at_close`` = мотогодини генератора →
        новий відлік («До ТО: 250 год», дата наступного ТО = дата закриття + місяці); якщо ТО більше не
        прострочене — ``_clear('maintenance_due')``; активність «Термін ТО» позначається виконаною; нотатка в
        чатер генератора. Технічні записи — ``sudo`` (права на закриття перевірив ``write`` —
        ``_td_check_close_rights``)."""
        alarms = self.env['td.genset.alarm'].sudo()
        activity_type = self.env.ref('td_genset.activity_check', raise_if_not_found=False)
        for request in self:
            genset = request.td_genset_id.sudo()
            if not genset or not request.stage_id.done:
                continue
            request.sudo().write({'td_run_hours_at_close': genset.run_hours_total})
            info = genset._maint_schedule()
            if info['state'] != 'overdue':
                alarms._clear(genset, 'maintenance_due', note=_('ТО виконано: заявка «%(name)s».', name=request.name))
            if activity_type:
                genset.activity_ids.filtered(
                    lambda activity: activity.activity_type_id == activity_type
                    and activity.summary == MAINT_ACTIVITY_SUMMARY
                ).action_feedback(feedback=_('Заявку ТО «%(name)s» закрито.', name=request.name))
            due = _(' або до %(date)s', date=info['due_date'].strftime('%d.%m.%Y')) if info['due_date'] else ''
            genset._message_log(body=_(
                'ТО виконано: заявку «%(name)s» закрито на %(hours)s мотогодин. Наступне ТО — на %(next)s '
                'мотогодин%(due)s.', name=request.name, hours=fmt_num(genset.run_hours_total, 1),
                next=fmt_num(info['next_hours']), due=due))
            genset._notify_bus('status')
        return None
