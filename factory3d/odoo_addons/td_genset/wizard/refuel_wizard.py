# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (поля): W0.
"""Майстер «Заправити генератор» ``td.genset.refuel.wizard`` — ТР 2.3.11, 2.9; SPEC 5.14 (права: ``group_admin``).

З каністр — обрані каністри розливаються часткові першими і не більше вільного об'єму бака; з іншого
джерела — назва і літри. Результат — запис заправки «Очікує показання», рухи «Заправка генератора» по
каністрах і нотатка в чатер; далі звірка з подією «Заправка» (``td.genset.refuel._reconcile_pending``).
"""
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

from ..models.genset_fuel import CTX_DEFER_STOCK, REFUEL_SOURCES, fmt_num, pour_plan


class TdGensetRefuelWizard(models.TransientModel):
    _name = 'td.genset.refuel.wizard'
    _description = 'Генератори: заправка генератора'

    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, ondelete='cascade',
        default=lambda self: self._default_genset(),
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
    fuel_liters = fields.Float(
        string='У баку, L', related='genset_id.fuel_liters',
        help='Паливо в баку за останнім знімком.')
    tank_volume_l = fields.Float(
        string="Об'єм бака, L", related='genset_id.tank_volume_l',
        help="Об'єм бака генератора.")
    free_l = fields.Float(
        string='Вільно в баку, L', compute='_compute_amounts',
        help="Об'єм бака − паливо в баку за останнім знімком.")
    will_fill_l = fields.Float(
        string='Заллється, L', compute='_compute_amounts',
        help='Скільки реально заллється з обраних каністр (не більше вільного об\'єму).')
    hint = fields.Char(
        string='Підказка', compute='_compute_amounts',
        help='«Не вміститься N L — лишиться в каністрі», «Бак повний — заливати нікуди».')
    summary = fields.Char(
        string='Підсумок', compute='_compute_amounts',
        help='«Заллється N L → у баку ≈ M L з V L».')

    @api.model
    def _default_genset(self):
        """Генератор з контексту картки (``active_id``) або єдиний генератор."""
        context = self.env.context
        if context.get('active_model') == 'td.genset' and context.get('active_id'):
            return context['active_id']
        gensets = self.env['td.genset'].search([], limit=2)
        return gensets.id if len(gensets) == 1 else False

    def _free_liters(self):
        """Вільний об'єм бака, L (0,1): ``tank_volume_l − fuel_liters``, не менше 0."""
        genset = self.genset_id
        if not genset:
            return 0.0
        free = float_round((genset.tank_volume_l or 0.0) - (genset.fuel_liters or 0.0), precision_digits=1)
        return max(free, 0.0)

    def _have_liters(self):
        """Скільки є в обраному джерелі: Σ обраних каністр або вказані літри."""
        if self.source == 'cans':
            return sum(self.canister_ids.filtered('active').mapped('liters'))
        return max(self.liters or 0.0, 0.0)

    @api.depends('genset_id', 'genset_id.fuel_liters', 'genset_id.tank_volume_l', 'source', 'canister_ids',
                 'canister_ids.liters', 'liters')
    def _compute_amounts(self):
        """Вільний об'єм, «заллється N L» і підказки (ФВ-33, AC-51)."""
        for wizard in self:
            free = wizard._free_liters()
            have = wizard._have_liters()
            fill = float_round(min(free, have), precision_digits=1)
            wizard.free_l = free
            wizard.will_fill_l = fill
            wizard.hint = wizard._hint(free, have, fill)
            if float_compare(fill, 0.0, precision_digits=1) > 0:
                wizard.summary = _('Заллється %(fill)s L → у баку ≈ %(after)s L з %(tank)s L.', fill=fmt_num(fill),
                                   after=fmt_num((wizard.genset_id.fuel_liters or 0.0) + fill),
                                   tank=fmt_num(wizard.genset_id.tank_volume_l))
            else:
                wizard.summary = False

    def _hint(self, free, have, fill):
        if not self.genset_id:
            return _('Оберіть генератор.')
        if float_compare(free, 0.0, precision_digits=1) <= 0:
            return _('Бак повний — заливати нікуди.')
        rest = float_round(have - fill, precision_digits=1)
        if self.source == 'cans':
            if not self.canister_ids:
                if not self.env['td.genset.canister'].search_count([('liters', '>', 0)], limit=1):
                    return _('Немає каністр з паливом — спочатку оформіть надходження.')
                return _('Позначте каністри, з яких заливаєте.')
            if float_compare(rest, 0.0, precision_digits=1) > 0:
                return _('Не вміститься %(rest)s L — лишиться в каністрі.', rest=fmt_num(rest))
            return False
        if float_compare(have, 0.0, precision_digits=2) <= 0:
            return _('Вкажіть, скільки літрів залито.')
        if float_compare(rest, 0.0, precision_digits=1) > 0:
            return _('Не вміститься %(rest)s L — у бак заллється лише %(fill)s L.', rest=fmt_num(rest),
                     fill=fmt_num(fill))
        return False

    def action_confirm(self):
        """Запис заправки (``waiting`` — «Очікує показання») + рухи «Заправка генератора» через
        ``fuel.move._post`` (часткові першими, не більше вільного об'єму) + чатер «Заправка: N L (джерело).»
        (ФВ-33, AC-51). Права — ``group_admin`` (інакше ``AccessError``). Бак повний — помилка
        «Бак повний — заливати нікуди.»."""
        self.ensure_one()
        genset = self.genset_id
        if not genset:
            raise UserError(_('Оберіть генератор.'))
        genset._td_check_group('td_genset.group_admin')
        free = self._free_liters()
        if float_compare(free, 0.0, precision_digits=1) <= 0:
            raise UserError(_('Бак повний — заливати нікуди.'))
        plan = []
        if self.source == 'cans':
            canisters = self.canister_ids.filtered(
                lambda canister: canister.active and float_compare(canister.liters, 0.0, precision_digits=2) > 0)
            if not canisters:
                raise UserError(_('Позначте хоча б одну каністру з паливом.'))
            plan = pour_plan(canisters, free)
            amount = float_round(sum(quantity for _canister, quantity in plan), precision_digits=2)
            names = ', '.join(canister.name for canister, _quantity in plan)
            source_note = _('Каністри %(names)s', names=names)
        else:
            if float_compare(self.liters, 0.0, precision_digits=2) <= 0:
                raise UserError(_('Вкажіть, скільки літрів залито.'))
            amount = float_round(min(self.liters, free), precision_digits=2)
            source_note = (self.source_note or '').strip() or _('Інше джерело')
        refuel = self.env['td.genset.refuel'].create({
            'genset_id': genset.id,
            'source': self.source,
            'source_note': source_note,
            'liters': amount,
            'canister_ids': [Command.set([canister.id for canister, _quantity in plan])],
        })
        moves = self.env['td.genset.fuel.move'].with_context(**{CTX_DEFER_STOCK: True})
        for canister, quantity in plan:
            moves._post('out', -quantity, canister=canister, genset=genset, refuel=refuel)
        if plan:
            self.env['td.genset']._check_fuel_stock()
        genset._message_log(body=_('Заправка: %(liters)s L (%(origin)s).', liters=fmt_num(amount),
                                   origin=source_note))
        genset._notify_bus('status')
        self.env['td.genset.refuel']._reconcile_pending()
        return {'type': 'ir.actions.act_window_close'}
