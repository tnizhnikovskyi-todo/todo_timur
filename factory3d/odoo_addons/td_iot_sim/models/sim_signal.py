import csv
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .sim_device import PROTOCOLS
from .sim_panel import parse_iso_utc

_logger = logging.getLogger(__name__)
CODE_RE = re.compile(r"^[a-z_]+(/[A-Za-z0-9_\-\.]+)+$")
CONSUMER_RE = re.compile(r"^energy/consumers/([^/]+)/")
PV_RE = re.compile(r"^infra/pv/(PV-INV-\d+)/")
STATE_DTYPES = ("state", "enum", "bit", "bool", "boolean", "text")


class F3dSimSignal(models.Model):
    _name = "td.sim.signal"
    _description = "Сигнал емулятора (каталог)"
    _inherit = ["td.sim.client"]
    _order = "device_id, code"
    _rec_name = "code"

    code = fields.Char(string="Код-шлях", required=True, index=True)
    name = fields.Char(string="Назва")
    device_id = fields.Many2one("td.sim.device", string="Пристрій", required=True, ondelete="cascade", index=True)
    protocol = fields.Selection(PROTOCOLS, string="Протокол", required=True)
    address = fields.Char(string="Адреса в джерелі", required=True)
    dtype = fields.Char(string="Тип")
    unit = fields.Char(string="Одиниця")
    scale = fields.Char(string="Масштаб")
    nominal = fields.Char(string="Номінал (старт)")
    thresholds = fields.Char(string="Пороги")
    model_rule = fields.Char(string="Модель поведінки")
    origin = fields.Selection([("mock", "Макет"), ("new", "Новий")], string="Походження", required=True)
    level0_code = fields.Char(string="Код сигналу рівня 0", index=True)
    level0_value = fields.Float(string="Значення рівня 0", compute="_compute_level0_value")
    last_value = fields.Float(string="Останнє значення (сервіс)", readonly=True)
    last_status = fields.Selection(
        [("ok", "ok"), ("warn", "warn"), ("alarm", "alarm"), ("stale", "stale")], string="Статус", readonly=True
    )
    last_ts = fields.Datetime(string="Час значення", readonly=True)
    kind = fields.Selection(
        [("gauge", "gauge"), ("counter", "counter"), ("state", "state"), ("event", "event")],
        string="Вид",
        required=True,
        default="gauge",
    )
    write_enabled = fields.Boolean(compute="_compute_write_enabled")

    _signal_code_uniq = models.Constraint("UNIQUE(code)", "Код сигналу має бути унікальним")

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not CODE_RE.match(rec.code or ""):
                raise ValidationError("Код сигналу «%s» не відповідає формату <група>/<об'єкт>/<сигнал>" % rec.code)

    def _compute_level0_value(self):
        values = {}
        if "x_f3d_signal" in self.env:
            codes = [c for c in self.mapped("level0_code") if c]
            if codes:
                values = {
                    s.x_code: s.x_value for s in self.env["x_f3d_signal"].sudo().search([("x_code", "in", codes)])
                }
        for rec in self:
            rec.level0_value = values.get(rec.level0_code, 0.0)

    def _compute_write_enabled(self):
        flag = self._sim_flag("write_enabled")
        for rec in self:
            rec.write_enabled = flag

    def action_read_now(self):
        self.ensure_one()
        if self.protocol == "none":
            raise UserError("Сигнал обчислює модуль-власник, емулятор його не веде")
        data = self._sim_get("/signals/%s" % self.code)
        value = data.get("value")
        self.sudo().write(
            {
                "last_value": value if isinstance(value, (int, float)) else 0.0,
                "last_status": data.get("status") if data.get("status") in ("ok", "warn", "alarm", "stale") else False,
                "last_ts": parse_iso_utc(data.get("ts")) or fields.Datetime.now(),
            }
        )

    # --- каталог ---
    @api.model
    def _guess_kind(self, row):
        dtype = (row.get("dtype") or "").strip().lower()
        rule = (row.get("model") or row.get("model_rule") or "").strip().lower()
        if dtype == "event":
            return "event"
        if rule.startswith(("counter", "energy", "hours")):
            return "counter"
        if dtype in STATE_DTYPES:
            return "state"
        return "gauge"

    @api.model
    def _catalog_device_code(self, row, known=None):
        """Пристрій сигналу: споживачі → `<X>-PM`, `infra/pv/PV-INV-n/*` → похідний `PV-INV-n` (§5.2: unit 60+n),
        решта — колонка `device` (код сцени). `known` — коди наявних пристроїв (PV без похідних лишається на батьку)."""
        match = CONSUMER_RE.match(row["code"])
        if match:
            return match.group(1) + "-PM"
        match = PV_RE.match(row["code"])
        if match and (known is None or match.group(1) in known):
            return match.group(1)
        return row["device"]

    @api.model
    def _load_catalog(self, path):
        """Upsert каталогу з CSV за `code` (SPEC §2.3, §5.1). Ідемпотентно."""
        Device = self.env["td.sim.device"].sudo()
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        devices = {d.code: d for d in Device.search([])}
        existing = {s.code: s for s in self.sudo().search([])}
        unknown = {}
        to_create = []
        for row in rows:
            code = row["code"].strip()
            row["code"] = code
            dev_code = self._catalog_device_code(row, devices)
            proto = (row.get("protocol") or "").strip()
            proto = "none" if proto in ("—", "", "-") else proto
            device = devices.get(dev_code)
            if not device:
                unknown.setdefault(dev_code, proto)
                device = devices[dev_code] = Device.create(
                    {"code": dev_code, "name": dev_code, "protocol": proto, "driver": "passive", "state": "passive"}
                )
            origin = row.get("origin") or ("mock" if (row.get("status") or "").strip() == "макет" else "new")
            last = code.rsplit("/", 1)[-1]
            vals = {
                "code": code,
                "name": (row.get("name") or "").strip() or "%s · %s" % (dev_code, last),
                "device_id": device.id,
                "protocol": proto,
                "address": row.get("address") or "—",
                "dtype": row.get("dtype"),
                "unit": row.get("unit"),
                "scale": row.get("scale"),
                "nominal": row.get("nominal"),
                "thresholds": row.get("thresholds"),
                "model_rule": row.get("model_rule") or row.get("model"),
                "origin": origin,
                "level0_code": (row.get("level0_code") or (code if origin == "mock" else "")) or False,
                "kind": row.get("kind") or self._guess_kind(row),
            }
            sig = existing.get(code)
            if sig:
                changed = {k: v for k, v in vals.items() if (sig[k].id if k == "device_id" else sig[k]) != (v or False)}
                if changed:
                    sig.write(changed)
            else:
                to_create.append(vals)
        if to_create:
            self.sudo().create(to_create)
        if unknown:
            _logger.warning(
                "Каталог сигналів: невідомі пристрої створено пасивними (%d): %s",
                len(unknown),
                ", ".join(sorted(unknown)[:50]),
            )
        return len(rows)
