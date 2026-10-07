# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (поля): W0.
"""Майстер «Надходження палива» ``td.genset.fuel.receipt.wizard`` — ТР 2.3.11; SPEC 5.14 (права: ``group_admin``).

Нові каністри (кількість 1–50, об'єм 5–60 L — каністри 10 і 20 L, рішення 1.9) або наповнення наявних;
рухи «Надходження» з одним ``receipt_key`` і підсумком «+20 L · АЗС … · 54,90 грн/л · 1 098 грн» (AC-48).
"""
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

from ..models.genset_fuel import CTX_DEFER_STOCK, fmt_num, plural

RECEIPT_MODES = [
    ('new', 'Нові каністри'),
    ('fill', 'Наповнити наявні'),
]


def _config(env):
    return env.ref('td_genset.config_main', raise_if_not_found=False)


class TdGensetFuelReceiptWizard(models.TransientModel):
    _name = 'td.genset.fuel.receipt.wizard'
    _description = 'Генератори: надходження палива'

    mode = fields.Selection(
        RECEIPT_MODES, string='Що надійшло', required=True, default=lambda self: self._default_mode(),
        help='Нові каністри з паливом або наповнення наявних каністр.')
    canister_qty = fields.Integer(
        string='Кількість каністр', default=1,
        help='Кількість нових каністр, що надійшли (1–50).')
    canister_volume_l = fields.Float(
        string="Об'єм каністри, L",
        default=lambda self: (_config(self.env).sudo().canister_volume_default_l if _config(self.env) else 20.0),
        help="Об'єм однієї нової каністри, L (5–60; зазвичай 10 або 20 L).")
    canister_ids = fields.Many2many(
        'td.genset.canister', string='Каністри для наповнення', domain=[('state', '!=', 'full')],
        default=lambda self: self._default_canisters(),
        help='Наявні каністри, які наповнюємо доповна (режим «Наповнити наявні»).')
    location_id = fields.Many2one(
        'td.genset.storage.location', string='Місце зберігання', ondelete='cascade',
        default=lambda self: self._default_location(),
        help='Де зберігатимуться нові каністри.')
    currency_id = fields.Many2one(
        'res.currency', string='Валюта', default=lambda self: self.env.company.currency_id,
        help='Валюта ціни (валюта компанії).')
    price_unit = fields.Monetary(
        string='Ціна за літр', currency_field='currency_id',
        default=lambda self: (_config(self.env).sudo().fuel_price_default if _config(self.env) else 0.0),
        help='Ціна палива за літр — для вартості витрати на «Заправці» і в «Аналітиці».')
    partner_id = fields.Many2one(
        'res.partner', string='Постачальник', ondelete='set null',
        default=lambda self: (_config(self.env).sudo().fuel_partner_id if _config(self.env) else False),
        help='Постачальник палива.')
    note = fields.Char(
        string='Примітка',
        help='Пояснення до надходження (АЗС, номер накладної …).')
    summary = fields.Char(
        string='Підсумок', compute='_compute_summary',
        help='«+20 L · 2 каністри · 1 098 грн. У каністрах стане N L.»')

    @api.model
    def _fillable(self):
        return self.env['td.genset.canister'].search([('state', '!=', 'full')])

    @api.model
    def _default_mode(self):
        """Як у мокапі: є неповні каністри — «Наповнити наявні», інакше «Нові каністри»."""
        return 'fill' if self._fillable() else 'new'

    @api.model
    def _default_canisters(self):
        return self._fillable().ids

    @api.model
    def _default_location(self):
        locations = self.env['td.genset.storage.location'].search([], limit=2)
        return locations.id if len(locations) == 1 else False

    def _amounts(self):
        """``[(каністра або None, літри), …]``: нові каністри (об'єм кожної) або доливи до повної."""
        if self.mode == 'new':
            return [(None, self.canister_volume_l)] * max(self.canister_qty, 0)
        return [(canister, float_round(canister.volume_l - canister.liters, precision_digits=2))
                for canister in self.canister_ids.filtered('active')
                if float_compare(canister.volume_l, canister.liters, precision_digits=2) > 0]

    @api.depends('mode', 'canister_qty', 'canister_volume_l', 'canister_ids', 'price_unit')
    def _compute_summary(self):
        stock = sum(self.env['td.genset.canister'].search([]).mapped('liters'))
        forms = (_('каністра'), _('каністри'), _('каністр'))
        for wizard in self:
            amounts = wizard._amounts()
            added = sum(liters for _canister, liters in amounts)
            if float_compare(added, 0.0, precision_digits=2) <= 0:
                wizard.summary = _('Нічого не обрано.')
                continue
            parts = ['+%s L' % fmt_num(added), '%s %s' % (len(amounts), plural(len(amounts), forms))]
            if float_compare(wizard.price_unit, 0.0, precision_digits=2) > 0:
                parts.append(_('%(amount)s грн', amount=fmt_num(added * wizard.price_unit, 0)))
            wizard.summary = _('%(summary)s. У каністрах стане %(stock)s L.', summary=' · '.join(parts),
                               stock=fmt_num(stock + added))

    def action_confirm(self):
        """Каністри (``ir.sequence`` «К-NN») + рухи «Надходження» з одним ``receipt_key`` і приміткою
        «+20 L · АЗС … · 54,90 грн/л · 1 098 грн»; помилка «Кількість 1–50, об'єм 5–60 L.» (AC-48).
        Права — ``group_admin`` (інакше ``AccessError``)."""
        self.ensure_one()
        self.env['td.genset']._td_check_group('td_genset.group_admin')
        if self.mode == 'new':
            if not 1 <= self.canister_qty <= 50 or not 5 <= self.canister_volume_l <= 60:
                raise UserError(_("Кількість 1–50, об'єм 5–60 L."))
            if not self.location_id:
                raise UserError(_('Вкажіть місце зберігання нових каністр.'))
            canisters = self.env['td.genset.canister'].create([
                {'volume_l': self.canister_volume_l, 'location_id': self.location_id.id}
                for _index in range(self.canister_qty)])
            amounts = [(canister, canister.volume_l) for canister in canisters]
        else:
            amounts = self._amounts()
            if not amounts:
                raise UserError(_('Позначте каністри для наповнення.'))
        total = float_round(sum(liters for _canister, liters in amounts), precision_digits=2)
        moves = self.env['td.genset.fuel.move'].with_context(**{CTX_DEFER_STOCK: True})
        note = moves._receipt_note(total, self.partner_id, self.price_unit, (self.note or '').strip() or None)
        receipt_key = '%s-%s' % (fields.Datetime.now().strftime('%Y%m%d-%H%M%S'), uuid4().hex[:6])
        for canister, liters in amounts:
            moves._post('in', liters, canister=canister, receipt_key=receipt_key, price_unit=self.price_unit,
                        partner_id=self.partner_id.id, note=note)
        self.env['td.genset']._check_fuel_stock()
        if self.env.context.get('active_model') == 'td.genset' and self.env.context.get('active_id'):
            genset = self.env['td.genset'].browse(self.env.context['active_id']).exists()
            if genset:
                genset._message_log(body=_('Надходження палива: %(note)s.', note=note))
        return {'type': 'ir.actions.act_window_close'}
