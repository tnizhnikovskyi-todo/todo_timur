from odoo import fields, models


class TdZoneLock(models.Model):
    """Оренда зони на 5 хвилин (F14, Q6) поверх `etag` (R-21); строк — параметри `lock_ttl_s`, `lock_heartbeat_s`."""

    _name = 'td.zone.lock'
    _description = "Блокування зони"
    _order = 'site_id, zone_uid'

    site_id = fields.Many2one('td.site', string="Площадка", required=True, ondelete='cascade', index=True)
    zone_uid = fields.Char(string="UID зони", size=32, required=True, index=True)
    user_id = fields.Many2one(
        'res.users', string="Хто редагує", required=True, default=lambda self: self.env.user, ondelete='cascade'
    )
    expires_at = fields.Datetime(string="Діє до", required=True, index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)

    _td_zone_lock_uniq = models.Constraint('UNIQUE(site_id, zone_uid)', "Зона вже заблокована.")
