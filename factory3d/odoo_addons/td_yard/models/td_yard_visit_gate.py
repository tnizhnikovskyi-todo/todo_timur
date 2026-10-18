"""Розширення f3d.yard.visit для КПП: ворота, події LPR, пошук за номером, хук пропуску (W2)."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..tools import params as P
from ..tools import tz

IN_STATES = ("planned", "arrived", "queued")
OUT_STATES = ("queued", "at_dock", "handling", "weighed")


class F3dYardVisit(models.Model):
    _inherit = "f3d.yard.visit"

    gate_in_id = fields.Many2one("f3d.yard.gate", string="КПП в'їзду", readonly=True, copy=False, ondelete="set null")
    gate_out_id = fields.Many2one("f3d.yard.gate", string="КПП виїзду", readonly=True, copy=False, ondelete="set null")
    lpr_event_ids = fields.One2many("f3d.yard.lpr.event", "visit_id", string="Події LPR")

    # ------------------------------------------------------------------ R-08 п. 6–7
    @api.model
    def _f3d_yard_candidates(self, direction, ts):
        """Рейси, що можуть збігатися за напрямком (без вікна за часом)."""
        if direction == "out":
            return self.search([("state", "in", OUT_STATES)])
        today = tz.local_day(ts)
        return self.search(["|", ("state", "in", IN_STATES), "&", ("state", "=", "draft"), ("day", "=", today)])

    @api.model
    def _f3d_yard_find_by_plate(self, plate_norm, direction, ts):
        """Кандидати за нормалізованим номером; порядок: |planned_start − ts|, потім id."""
        window = P.get_int(self.env, "lpr_match_window_h") * 3600
        found = self._f3d_yard_candidates(direction, ts).filtered(lambda v: v.plate_norm == plate_norm)
        if direction == "in":
            found = found.filtered(
                lambda v: (
                    v.state != "planned" or not v.planned_start or abs((v.planned_start - ts).total_seconds()) <= window
                )
            )

        def key(v):
            return (abs((v.planned_start - ts).total_seconds()) if v.planned_start else float("inf"), v.id)

        return found.sorted(key)

    @api.model
    def _f3d_yard_find_by_docs(self, tokens, direction, ts):
        tokens = set(tokens)
        return self._f3d_yard_candidates(direction, ts).filtered(
            lambda v: v.batch_id and (v.batch_id.name in tokens or tokens & set(v.batch_id.picking_ids.mapped("name")))
        )

    # ------------------------------------------------------------------ хук пропуску (W1 action_admit)
    def _f3d_yard_admit_gate(self, open_gate=True):
        self.ensure_one()
        gate = self.gate_in_id or self._f3d_yard_default_gate()
        if not gate:
            return None
        gate = gate.sudo()
        if not open_gate:
            gate._f3d_yard_count_permit(self)
            return None
        if not P.get_bool(self.env, "write_enabled"):
            gate._f3d_yard_count_permit(self)
            return ("warning", "Команди на шлагбаум вимкнено — відкрийте шлагбаум з пульта CAME.")
        try:
            # ручна команда від імені користувача: права GRP_SEC перевіряє action_admit
            self.env["f3d.yard.gate"].browse(gate.id).action_command("open", self, "manual")
        except UserError as e:
            return ("warning", str(e.args[0]))
        return ("success", "Фуру %s пропущено, команду на шлагбаум надіслано" % (self.plate or self.name))

    # ------------------------------------------------------------------ крон
    @api.model
    def _cron_queue(self):
        parent = getattr(super(), "_cron_queue", None)
        if parent:
            parent()
        self.env["f3d.yard.gate"].sudo()._cron_gates()
        self.env["f3d.yard.lpr.event"].sudo()._cron_expire()
        return True
