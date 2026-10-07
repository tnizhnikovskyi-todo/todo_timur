# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (поля, заглушки): W0.
"""Майстер «Заправити генератор» ``td.genset.refuel.wizard`` — ТР 2.3.11, 2.9; SPEC 5.14 (права: ``group_admin``)."""
from odoo import api, fields, models

from ..models.genset_fuel import REFUEL_SOURCES


class TdGensetRefuelWizard(models.TransientModel):
    _name = 'td.genset.refuel.wizard'
    _description = 'Генератори: заправка генератора'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, ondelete='cascade',
        help='Який генератор заправляємо.')
    source = fields.Selection(
        REFUEL_SOURCES, string='Джерело', required=True, default='cans',
        help='З каністр (спишуться рухами запасу) або з іншого джерела.')
    canister_ids = fields.Many2many(
        'td.genset.canister', string='Каністри', domain=[('liters', '>', 0)],
        help='З яких каністр заливаємо; часткові розливаються першими.')
    source_note = fields.Char(
        string='Звідки',
        help='Звідки залили паливо, якщо не з каністр: паливовоз, АЗС тощо.')
    liters = fields.Float(
        string='Літрів',
        help="Скільки літрів залито в бак (для іншого джерела). Не більше вільного об'єму бака.")
    free_l = fields.Float(
        string='Вільно в баку, L', compute='_compute_amounts',
        help="Об'єм бака − паливо в баку за останнім знімком.")
    will_fill_l = fields.Float(
        string='Заллється, L', compute='_compute_amounts',
        help='Скільки реально заллється з обраних каністр (не більше вільного об\'єму).')
    hint = fields.Char(
        string='Підказка', compute='_compute_amounts',
        help='«Не вміститься N L — лишиться в каністрі», «Бак повний — заливати нікуди».')

    @api.depends('genset_id', 'source', 'canister_ids', 'liters')
    def _compute_amounts(self):
        """Вільний об'єм, «заллється N L», підказки. TODO: W4 — AC-51. W0: вільний об'єм, решта нейтрально."""
        for wizard in self:
            genset = wizard.genset_id
            wizard.free_l = max((genset.tank_volume_l or 0.0) - (genset.fuel_liters or 0.0), 0.0)
            wizard.will_fill_l = 0.0
            wizard.hint = False

    def action_confirm(self):
        """``td.genset.refuel`` (``waiting``) + рухи ``out`` через ``fuel.move._post`` (часткові першими, не більше
        вільного) + чатер «Заправка: N L» (AC-51). Права — ``group_admin``.

        TODO: W4 — AC-51. Заглушка W0: перевірка групи, закриття майстра.
        """
        self.ensure_one()
        self.genset_id._td_check_group('td_genset.group_admin')
        return {'type': 'ir.actions.act_window_close'}
