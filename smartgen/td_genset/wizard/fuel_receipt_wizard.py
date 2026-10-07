# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО». Каркас (поля, заглушки): W0.
"""Майстер «Надходження палива» ``td.genset.fuel.receipt.wizard`` — ТР 2.3.11; SPEC 5.14 (права: ``group_admin``)."""
from odoo import fields, models

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
        RECEIPT_MODES, string='Що надійшло', required=True, default='new',
        help='Нові каністри з паливом або наповнення наявних каністр.')
    canister_qty = fields.Integer(
        string='Кількість каністр', default=1,
        help='Кількість нових каністр, що надійшли (1–50).')
    canister_volume_l = fields.Float(
        string="Об'єм каністри, L",
        default=lambda self: (_config(self.env).sudo().canister_volume_default_l if _config(self.env) else 20.0),
        help="Об'єм однієї нової каністри, L (5–60).")
    canister_ids = fields.Many2many(
        'td.genset.canister', string='Каністри для наповнення',
        help='Наявні каністри, які наповнюємо (режим «Наповнити наявні»).')
    location_id = fields.Many2one(
        'td.genset.storage.location', string='Місце зберігання', ondelete='cascade',
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

    def action_confirm(self):
        """Каністри (``ir.sequence``) + рухи ``in`` з одним ``receipt_key`` («+20 L · АЗС … · 54,90 грн/л · 1 098 грн»);
        помилка «Кількість 1–50, об'єм 5–60 L» (AC-48). Права — ``group_admin``.

        TODO: W4 — AC-48. Заглушка W0: перевірка групи, закриття майстра.
        """
        self.ensure_one()
        self.env['td.genset']._td_check_group('td_genset.group_admin')
        return {'type': 'ir.actions.act_window_close'}
