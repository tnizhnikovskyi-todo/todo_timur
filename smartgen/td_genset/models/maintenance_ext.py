# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (поля, хук write): W0.
"""Розширення стандартних моделей ТО — ТР 2.3.12, 2.9; SPEC 5.13."""
from odoo import fields, models


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

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals:
            self.filtered(lambda request: request.td_genset_id and request.stage_id.done)._td_on_done()
        return res

    def _td_on_done(self):
        """Хук закриття заявки ТО: ``td_run_hours_at_close = genset.run_hours_total``, ``_clear('maintenance_due')``.

        TODO: W4 — AC-54. Заглушка W0: нічого не робить.
        """
        return None
