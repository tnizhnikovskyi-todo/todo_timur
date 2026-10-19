import json
import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .td_fire_smoke_zone import COMPLIANCE, plant_size


class F3dFireRoute(models.Model):
    _name = "td.fire.route"
    _description = "Евакуація: маршрут"
    _order = "zone_code"
    _rec_name = "name"

    code = fields.Char(string="Код у 3D", size=32, required=True, index=True)
    name = fields.Char(string="Назва", size=128, required=True)
    zone_id = fields.Many2one("td.zone", string="Зона", required=True, ondelete="cascade", index=True)
    zone_code = fields.Char(related="zone_id.td_code", store=True)
    exit_id = fields.Many2one("td.fire.exit", string="Вихід", required=True, ondelete="restrict")
    length_m = fields.Float(string="Довжина шляху, м", digits=(8, 1), required=True)
    path = fields.Json(string="Шлях", required=True)
    path_text = fields.Text(string="Шлях (JSON)", compute="_compute_path_text", inverse="_inverse_path_text")
    point_count = fields.Integer(string="Точок", compute="_compute_point_count")
    width_min_m = fields.Float(string="Найвужче місце, м", digits=(4, 2))
    norm_m = fields.Float(string="Норма, м", compute="_compute_norm_m")
    length_ok = fields.Boolean(readonly=True)
    width_ok = fields.Boolean(readonly=True)
    compliance = fields.Selection(COMPLIANCE, default="na", readonly=True, index=True)
    compliance_note = fields.Text(readonly=True)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint("UNIQUE(code)", "Код маршруту має бути унікальним.")
    _zone_uniq = models.Constraint("UNIQUE(zone_id)", "Для зони вже є маршрут.")

    @api.depends("path")
    def _compute_path_text(self):
        for rec in self:
            rec.path_text = json.dumps(rec.path) if rec.path else False

    def _inverse_path_text(self):
        for rec in self:
            text = (rec.path_text or "").strip()
            if not text:
                rec.path = False
                continue
            try:
                rec.path = json.loads(text)
            except ValueError:
                raise ValidationError("Шлях: очікується JSON-список точок [[x, y], …]") from None

    @api.depends("path")
    def _compute_point_count(self):
        for rec in self:
            rec.point_count = len(rec.path) if isinstance(rec.path, list) else 0

    def _norm_key(self):
        icp = self.env["ir.config_parameter"].sudo()
        poly = (icp.get_param("td.fire_safety.polymer_panels", "False") or "").lower() in ("true", "1")
        return "evac_distance_polymer" if poly else "evac_distance_prod_B"

    def _compute_norm_m(self):
        value = self.env["td.fire.norm"].get(self._norm_key()) or 0.0
        for rec in self:
            rec.norm_m = value

    @api.constrains("path", "exit_id", "length_m")
    def _check_path(self):
        length, width = plant_size(self.env)
        for rec in self:

            def fail(reason, rec=rec):
                raise ValidationError("Шлях маршруту %s: %s" % (rec.code, reason))

            pts = rec.path
            if not isinstance(pts, list) or len(pts) < 2:
                fail("потрібно щонайменше 2 точки")
            for pt in pts:
                if (
                    not isinstance(pt, (list, tuple))
                    or len(pt) != 2
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in pt)
                ):
                    fail("точка має бути парою чисел")
                if not (0 <= pt[0] <= length and 0 <= pt[1] <= width):
                    fail("точка %s поза будівлею" % (list(pt),))
            ex = rec.exit_id
            dist = math.hypot(pts[-1][0] - ex.x, pts[-1][1] - ex.y)
            if dist > ex.width_m / 2 + 0.5:
                fail("кінець шляху за %.1f м від виходу %s" % (dist, ex.code))
            if rec.length_m <= 0:
                fail("довжина має бути більшою за 0")

    def _recompute(self):
        """R-05, R-07."""
        norm = self.env["td.fire.norm"]
        key = self._norm_key()
        limit = norm.get(key)
        ref = norm.get_ref(key)
        width_min = norm.get("exit_width_min")
        for rec in self:
            if not rec.active:
                rec.write({"compliance": "na", "length_ok": False, "width_ok": False, "compliance_note": False})
                continue
            if limit is None or width_min is None:
                rec.write({"compliance": "na", "compliance_note": "Норма не задана"})
                continue
            widths = [w for w in (rec.width_min_m, rec.exit_id.width_m) if w]
            width_ok = bool(widths) and min(widths) >= width_min
            length_ok = rec.length_m <= limit
            rec.write(
                {
                    "length_ok": length_ok,
                    "width_ok": width_ok,
                    "compliance": "ok" if length_ok and width_ok else "fail",
                    "compliance_note": "%s м до %s при нормі ≤ %s м (%s)%s"
                    % (
                        rec.length_m,
                        rec.exit_id.code,
                        limit,
                        ref,
                        "" if width_ok else "; ширина менша за %s м" % width_min,
                    ),
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._recompute()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if {"length_m", "exit_id", "width_min_m", "active"} & set(vals):
            self._recompute()
        return res

    def action_f3d_show(self):
        self.ensure_one()
        act = self.zone_id.action_f3d_show()
        if act.get("tag") == "f3d_viewer.action":
            act["params"]["code"] = self.code
        return act
