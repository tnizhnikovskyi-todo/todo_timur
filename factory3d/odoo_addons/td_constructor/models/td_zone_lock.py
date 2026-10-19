import math
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..services import geometry as geo


class TdZoneLock(models.Model):
    """Оренда зони на 5 хвилин (F14, Q6) поверх `etag` (R-21); строк — параметри `lock_ttl_s`, `lock_heartbeat_s`.

    «Зона» об'єкта — найменша зона (місце-зона), що містить його центр; поза зонами — сам об'єкт (його uid).
    Оренда необов'язкова: правку відхиляє лише чужа діюча оренда (`f3d_assert_write/create`, їх викликає
    `td.draft.mixin`)."""

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

    # --- параметри ---------------------------------------------------------------------------------------
    @api.model
    def f3d_ttl(self):
        return self._param('lock_ttl_s', 300)

    @api.model
    def f3d_heartbeat(self):
        return self._param('lock_heartbeat_s', 60)

    @api.model
    def _param(self, key, default):
        try:
            return max(1, int(self.env['ir.config_parameter'].sudo().get_param('td.constructor.' + key, default)))
        except (TypeError, ValueError):
            return default

    # --- оренда -----------------------------------------------------------------------------------------------
    @api.model
    def f3d_purge(self, site=None):
        """Прибирає прострочені оренди (від імені сервера)."""
        domain = [('expires_at', '<=', fields.Datetime.now())]
        if site:
            domain.append(('site_id', '=', site.id))
        self.sudo().search(domain).unlink()

    @api.model
    def f3d_active(self, site):
        """Діючі оренди площадки."""
        return self.sudo().search([('site_id', '=', site.id), ('expires_at', '>', fields.Datetime.now())])

    @api.model
    def f3d_acquire(self, site, zone_uid):
        """Орендувати зону (або продовжити свою) на `lock_ttl_s`: `(ok, lock)`; чужа діюча оренда — `(False, lock)`."""
        if not (self.env.su or self.env.user.has_group('td_factory3d.group_td_user')):
            raise AccessError("Немає доступу до конструктора.")
        Lock = self.sudo()
        now = fields.Datetime.now()
        expires = now + timedelta(seconds=self.f3d_ttl())
        for _attempt in range(2):
            lock = Lock.search([('site_id', '=', site.id), ('zone_uid', '=', zone_uid)], limit=1)
            if lock and lock.expires_at > now and lock.user_id != self.env.user:
                return False, lock
            try:
                with self.env.cr.savepoint():
                    if lock:
                        lock.write({'user_id': self.env.user.id, 'expires_at': expires})
                    else:
                        lock = Lock.create(
                            {
                                'site_id': site.id,
                                'zone_uid': zone_uid,
                                'user_id': self.env.user.id,
                                'expires_at': expires,
                            }
                        )
                return True, lock
            except IntegrityError:
                self.env.invalidate_all()
        return False, Lock.search([('site_id', '=', site.id), ('zone_uid', '=', zone_uid)], limit=1)

    @api.model
    def f3d_release(self, site, zone_uid=None):
        """Зняти свої оренди площадки (одну зону або всі); повертає кількість знятих."""
        domain = [('site_id', '=', site.id), ('user_id', '=', self.env.user.id)]
        if zone_uid:
            domain.append(('zone_uid', '=', zone_uid))
        locks = self.sudo().search(domain)
        count = len(locks)
        locks.unlink()
        return count

    def f3d_dict(self):
        self.ensure_one()
        return {
            'zone_uid': self.zone_uid,
            'user_id': self.user_id.id,
            'user': self.user_id.name or '',
            'mine': self.user_id == self.env.user,
            'expires_at': fields.Datetime.to_string(self.expires_at),
        }

    # --- зона об'єкта ----------------------------------------------------------------------------------------
    @api.model
    def _td_zone_polys(self, site):
        """Зони площадки `[(uid, назва, многокутник, площа)]`: свій многокутник або прямокутник `length × width`."""
        out = []
        slots = (
            self.env['td.slot']
            .sudo()
            .search([('site_id', '=', site.id), ('template', '=', 'zone'), ('layer_id.active', '=', True)])
        )
        for zone in slots:
            params = zone.params or {}
            poly = params.get('polygon')
            if not poly:
                length, width = params.get('length') or 1, params.get('width') or 1
                angle = math.radians(zone.rotation or 0)
                c, s = math.cos(angle), math.sin(angle)
                poly = [
                    [zone.x_m + x * c - y * s, zone.y_m + x * s + y * c]
                    for x, y in (
                        (-length / 2, -width / 2),
                        (length / 2, -width / 2),
                        (length / 2, width / 2),
                        (-length / 2, width / 2),
                    )
                ]
            area = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True))) / 2
            out.append((zone.uid, params.get('title') or zone.code_prefix or zone.uid, poly, area))
        return out

    @api.model
    def _td_zone_at(self, zones, x, y):
        """uid найменшої зони, що містить точку, або None."""
        hit = [(area, uid) for uid, _name, poly, area in zones if geo.polygon_contains(poly, (x, y))]
        return min(hit)[1] if hit else None

    @api.model
    def f3d_assert_write(self, records, vals=None):
        """Зміна/видалення місць і розміщень: нова позиція з `vals` перевіряється поруч зі старою."""
        if self.env.su or self.env.context.get('f3d_no_lock_check'):
            return
        spots = []
        for rec in records:
            is_zone = rec._name == 'td.slot' and rec.template == 'zone'
            points = [(rec.x_m, rec.y_m)]
            if vals and ('x_m' in vals or 'y_m' in vals):
                points.append((vals.get('x_m', rec.x_m), vals.get('y_m', rec.y_m)))
            spots += [(rec.site_id.id, x, y, rec.uid or None, is_zone) for x, y in points]
        self._td_assert_spots(spots)

    @api.model
    def f3d_assert_create(self, model, vals_list):
        """Створення місць і розміщень у чужій орендованій зоні."""
        if self.env.su or self.env.context.get('f3d_no_lock_check'):
            return
        Layer = self.env['td.layer'].sudo()
        spots = [
            (
                vals.get('site_id') or Layer.browse(vals.get('layer_id')).site_id.id,
                vals.get('x_m') or 0.0,
                vals.get('y_m') or 0.0,
                vals.get('uid') or None,
                model == 'td.slot' and vals.get('template') == 'zone',
            )
            for vals in vals_list
        ]
        self._td_assert_spots(spots)

    @api.model
    def _td_assert_spots(self, spots):
        """`spots`: `[(site_id, x, y, uid|None, is_zone)]`; AccessError «Зону … редагує … до …»."""
        by_site = {}
        for site_id, x, y, uid, is_zone in spots:
            if site_id:
                by_site.setdefault(site_id, []).append((x, y, uid, is_zone))
        for site_id, items in by_site.items():
            foreign = self.sudo().search(
                [
                    ('site_id', '=', site_id),
                    ('expires_at', '>', fields.Datetime.now()),
                    ('user_id', '!=', self.env.user.id),
                ]
            )
            if not foreign:
                continue
            by_zone = {lock.zone_uid: lock for lock in foreign}
            zones = self._td_zone_polys(self.env['td.site'].sudo().browse(site_id))
            names = {uid: name for uid, name, _poly, _area in zones}
            for x, y, uid, is_zone in items:
                for key in [uid] if is_zone else [self._td_zone_at(zones, x, y), uid]:
                    if key and key in by_zone:
                        raise AccessError(self._td_busy_message(by_zone[key], names.get(key)))

    @api.model
    def f3d_label(self, site, uid):
        """Підпис зони/об'єкта за uid: назва зони, префікс місця чи код розміщення."""
        slot = self.env['td.slot'].sudo().search([('site_id', '=', site.id), ('uid', '=', uid)], limit=1)
        if slot:
            return (slot.params or {}).get('title') or slot.code_prefix or uid
        placement = self.env['td.placement'].sudo().search([('site_id', '=', site.id), ('uid', '=', uid)], limit=1)
        return placement.code or uid

    @api.model
    def _td_busy_message(self, lock, name=None):
        until = fields.Datetime.context_timestamp(self, lock.expires_at).strftime('%H:%M')
        return "Зону «%s» редагує %s до %s." % (name or lock.zone_uid, lock.user_id.name, until)
