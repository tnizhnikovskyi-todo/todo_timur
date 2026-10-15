from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .wh_project import iso

LOCK_TTL = 300  # секунд; переопределяется параметром wh_constructor.lock_ttl. Клиент продлевает блокировку раз в минуту.
GROUP_DESIGN = "wh_constructor.group_wh_design"


class WhZoneLock(models.Model):
    _name = "wh.zone.lock"
    _description = "Блокування зони конструктора складу"
    _order = "project_id, warehouse_key, zone_key"

    project_id = fields.Many2one("wh.project", required=True, ondelete="cascade", index=True)
    warehouse_key = fields.Char(string="Склад у застосунку", required=True, help="Поле id складу в проєкті v2.")
    warehouse_id = fields.Many2one("stock.warehouse", string="Склад Odoo", ondelete="set null")
    zone_key = fields.Char(string="Ключ зони", required=True)
    user_id = fields.Many2one("res.users", string="Користувач", required=True, default=lambda self: self.env.user, ondelete="cascade")
    expires = fields.Datetime(string="Спливає", required=True)

    def init(self):
        # одна запись на зону: гонка двух захватов упирается в уникальный индекс
        self.env.cr.execute("CREATE UNIQUE INDEX IF NOT EXISTS wh_zone_lock_zone_uniq ON wh_zone_lock (project_id, warehouse_key, zone_key)")

    @api.model
    def _ttl(self):
        try:
            return max(int(self.env["ir.config_parameter"].sudo().get_param("wh_constructor.lock_ttl", LOCK_TTL)), 1)
        except (TypeError, ValueError):
            return LOCK_TTL

    @api.model
    def _require_design(self):
        if not self.env.user.has_group(GROUP_DESIGN):
            raise AccessError(_("Блокувати зони можуть лише користувачі з правом «Конструктор: проєктування»."))

    def _info(self, ok):
        self.ensure_one()
        return {"ok": ok, "zone": self.zone_key, "warehouse": self.warehouse_key, "owner": self.user_id.name,
                "owner_id": self.user_id.id, "expires": iso(self.expires), "mine": self.user_id == self.env.user}

    @api.model
    def api_acquire(self, key, warehouse_key, zone_key, warehouse_code=None):
        """Захват или продление блокировки зоны. Занята другим (и не истекла) — {"ok": False, "owner", "expires"}."""
        self._require_design()
        project = self.env["wh.project"]._find(key)
        if not project:
            return {"ok": False, "error": "no_project"}
        project._lock_row()
        now = fields.Datetime.now()
        expires = now + timedelta(seconds=self._ttl())
        lock = self.sudo().search([("project_id", "=", project.id), ("warehouse_key", "=", warehouse_key), ("zone_key", "=", zone_key)], limit=1)
        if lock and lock.user_id != self.env.user and lock.expires > now:
            return lock._info(False)
        wh = self.env["stock.warehouse"].search([("code", "=", warehouse_code)], limit=1) if warehouse_code else self.env["stock.warehouse"]
        vals = {"user_id": self.env.user.id, "expires": expires, "warehouse_id": wh.id or False}
        if lock:
            lock.write(vals)
        else:
            lock = self.sudo().create({**vals, "project_id": project.id, "warehouse_key": warehouse_key, "zone_key": zone_key})
        return lock._info(True)

    @api.model
    def api_release(self, key, warehouse_key=None, zone_key=None):
        """Освободить свою блокировку зоны (без zone_key — все свои блокировки проекта)."""
        self._require_design()
        project = self.env["wh.project"]._find(key)
        if not project:
            return {"ok": True, "released": 0}
        domain = [("project_id", "=", project.id), ("user_id", "=", self.env.user.id)]
        if warehouse_key:
            domain.append(("warehouse_key", "=", warehouse_key))
        if zone_key:
            domain.append(("zone_key", "=", zone_key))
        locks = self.sudo().search(domain)
        n = len(locks)
        locks.unlink()
        return {"ok": True, "released": n}

    @api.model
    def api_list(self, key):
        """Действующие (не истекшие) блокировки проекта."""
        project = self.env["wh.project"]._find(key)
        if not project:
            return []
        now = fields.Datetime.now()
        return [lk._info(True) for lk in self.sudo().search([("project_id", "=", project.id), ("expires", ">", now)])]

    @api.model
    def _gc(self):
        """Удалить истёкшие блокировки (вызывается при захвате/списке при желании; безопасно в любой момент)."""
        self.sudo().search([("expires", "<=", fields.Datetime.now())]).unlink()
