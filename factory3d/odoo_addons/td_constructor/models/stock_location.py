from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services import addr as addr_mod


class StockLocation(models.Model):
    _inherit = 'stock.location'

    td_site_id = fields.Many2one(
        'td.site',
        string="Площадка конструктора",
        index=True,
        copy=False,
        readonly=True,
        ondelete='set null',
        help="Запис керується конструктором розкладки (CC-01)",
    )
    td_slot_uid = fields.Char(string="UID місця", size=32, copy=False, readonly=True)
    # MERGE.md §3.3: номери сегментів адреси (заміна posx/posy/posz) — для сортування й пошуку; 0 — не задано
    td_row = fields.Integer(string="Ряд", copy=False, readonly=True, index=True)
    td_bay = fields.Integer(string="Секція", copy=False, readonly=True)
    td_level = fields.Integer(string="Ярус", copy=False, readonly=True)
    td_pos = fields.Integer(string="Позиція", copy=False, readonly=True)

    @api.constrains('td_row', 'td_bay', 'td_level', 'td_pos')
    def _check_td_address_numbers(self):
        for location in self:
            if min(location.td_row, location.td_bay, location.td_level, location.td_pos) < 0:
                raise ValidationError("Номери адреси локації (ряд, секція, ярус, позиція) не можуть бути від'ємними.")

    @api.model
    def _f3d_address_vals(self, code, parts, addr=None, loc_tree='flat'):
        """Поля локації за кодом комірки й значеннями сегментів (F01-05, F01-11).

        Повертає {name, barcode, td_row, td_bay, td_level, td_pos}.

        Лише розрахунок: записує їх публікація (план змін). `addr` — повні налаштування адресації (для короткого імені
        при `loc_tree` row/section); `parts` — {row, bay, level, pos} (логічні номери)."""
        return addr_mod.location_vals(code, parts, addr, loc_tree)
