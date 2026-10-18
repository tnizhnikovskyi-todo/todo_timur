"""M-07 `td.energy.usage` — SQL-view (W3-A). Каркас: поля й повне тіло `init()` (CREATE VIEW) — воркер A."""

from odoo import models, tools


class TdEnergyUsage(models.Model):
    _name = "td.energy.usage"
    _description = "Енергетика: зведення використання"
    _auto = False

    def init(self):
        # Каркас: порожнє представлення, щоб реєстр не лаявся на відсутню таблицю; воркер A замінює його.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("CREATE VIEW %s AS SELECT 0::int AS id WHERE false" % self._table)
