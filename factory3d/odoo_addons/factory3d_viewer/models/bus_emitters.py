"""M-07: емітери шини — перевизначення стандартних моделей (FR-18).

Спільний міксин перехоплює create / write / _write_multi (обчислювані збережені поля пишуться через `_write`) / unlink
і публікує коди через `f3d.viewer.event._notify` (коалесценція — R-15).
"""
from odoo import models

IN_PROGRESS_NAMES = {"in progress", "в роботі"}


def _wo_code(wo):
    return "WO%05d" % wo.id if wo and wo.id else None


class F3dViewerBusMixin(models.AbstractModel):
    _name = "f3d.viewer.bus.mixin"
    _description = "3D: міксин емітера шини"

    _f3d_bus_fields = ()
    _f3d_bus_kind = "state"

    def _f3d_bus_codes(self):
        return set()

    def _f3d_bus_active(self):
        return "f3d.viewer.event" in self.env and not self.env.context.get("f3d_viewer_no_bus")

    def _f3d_bus_publish(self, codes):
        if codes:
            self.env["f3d.viewer.event"]._notify(self._name, codes, self._f3d_bus_kind)

    def _f3d_bus_hit(self, vals):
        return bool(self._f3d_bus_fields) and bool(set(self._f3d_bus_fields) & set(vals)) and self._f3d_bus_active()

    def _f3d_bus_safe_codes(self):
        try:
            return {c for c in self.sudo()._f3d_bus_codes() if c}
        except Exception:  # noqa: BLE001 — емітер ніколи не ламає бізнес-операцію
            return set()

    def create(self, vals_list):
        records = super().create(vals_list)
        if records and records._f3d_bus_active():
            records._f3d_bus_publish(records._f3d_bus_safe_codes())
        return records

    def write(self, vals):
        hit = self._f3d_bus_hit(vals)
        old = self._f3d_bus_safe_codes() if hit else set()
        res = super().write(vals)
        if hit:
            self._f3d_bus_publish(old | self._f3d_bus_safe_codes())
        return res

    def _write_multi(self, vals_list):
        # обчислювані збережені поля (state…) пишуться при flush саме через _write_multi, повз write()
        hit = any(self._f3d_bus_hit(vals) for vals in vals_list)
        old = self._f3d_bus_safe_codes() if hit else set()
        res = super()._write_multi(vals_list)
        if hit:
            self._f3d_bus_publish(old | self._f3d_bus_safe_codes())
        return res

    def unlink(self):
        if self._f3d_bus_active():
            self._f3d_bus_publish(self._f3d_bus_safe_codes())
        return super().unlink()


class StockQuant(models.Model):
    _inherit = ["stock.quant", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("quantity", "reserved_quantity", "lot_id", "package_id", "location_id")
    _f3d_bus_kind = "stock"

    def _f3d_bus_codes(self):
        return set(self.location_id.mapped("f3d_code"))


class StockMoveLine(models.Model):
    _inherit = ["stock.move.line", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("quantity", "picked", "state", "location_id", "location_dest_id")
    _f3d_bus_kind = "stock"

    def _f3d_bus_codes(self):
        return (set(self.location_id.mapped("f3d_code")) | set(self.location_dest_id.mapped("f3d_code"))
                | set(self.picking_id.mapped("name")))


class StockPicking(models.Model):
    _inherit = ["stock.picking", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("state", "scheduled_date", "date_done", "batch_id", "partner_id")
    _f3d_bus_kind = "doc"

    def _f3d_bus_codes(self):
        return set(self.mapped("name")) | set(self.batch_id.dock_id.mapped("f3d_code"))


class StockPickingBatch(models.Model):
    _inherit = ["stock.picking.batch", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("state", "dock_id", "f3d_code", "f3d_vehicle_id", "picking_ids", "scheduled_date")
    _f3d_bus_kind = "doc"

    def _f3d_bus_codes(self):
        return (set(self.picking_ids.mapped("name")) | set(self.dock_id.mapped("f3d_code"))
                | set(self.mapped("f3d_code")) | set(self.f3d_vehicle_id.mapped("f3d_code")))


class MrpWorkorder(models.Model):
    _inherit = ["mrp.workorder", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("state", "date_start", "date_finished", "working_state", "workcenter_id", "duration")
    _f3d_bus_kind = "state"

    def _f3d_bus_codes(self):
        return ({_wo_code(wo) for wo in self} | set(self.production_id.mapped("name"))
                | set(self.workcenter_id.mapped("f3d_code")))


class MrpProduction(models.Model):
    _inherit = ["mrp.production", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("state", "reservation_state", "product_qty", "date_start", "date_deadline", "move_raw_ids")
    _f3d_bus_kind = "doc"

    def _f3d_bus_codes(self):
        return set(self.mapped("name"))


class MrpWorkcenter(models.Model):
    _inherit = ["mrp.workcenter", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("working_state", "active")
    _f3d_bus_kind = "state"

    def _f3d_bus_codes(self):
        return set(self.mapped("f3d_code"))


class MrpWorkcenterProductivity(models.Model):
    _inherit = ["mrp.workcenter.productivity", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("date_start", "date_end", "loss_id", "workcenter_id")
    _f3d_bus_kind = "state"

    def _f3d_bus_codes(self):
        return set(self.workcenter_id.mapped("f3d_code")) | {_wo_code(wo) for wo in self.workorder_id}


class MaintenanceRequest(models.Model):
    _inherit = ["maintenance.request", "f3d.viewer.bus.mixin"]
    _f3d_bus_fields = ("stage_id", "equipment_id", "schedule_date", "user_id", "priority")
    _f3d_bus_kind = "maintenance"

    def _f3d_bus_codes(self):
        codes = set(self.mapped("name")) | set(self.equipment_id.mapped("f3d_code"))
        if "workcenter_id" in self.equipment_id._fields:
            codes |= set(self.equipment_id.workcenter_id.mapped("f3d_code"))
        return codes

    def write(self, vals):
        res = super().write(vals)
        if "stage_id" in vals and self._f3d_bus_active():
            self._f3d_bus_event_snapshot()
        return res

    def _f3d_bus_event_snapshot(self):
        """AC-49: перехід у стадію «В роботі» для обладнання з кодом сцени — знімок kind=event."""
        stage = self.env.ref("maintenance.stage_1", raise_if_not_found=False)
        for req in self.sudo():
            code = req.equipment_id.f3d_code
            name = (req.stage_id.name or "").strip().lower()
            if code and ((stage and req.stage_id == stage) or name in IN_PROGRESS_NAMES):
                self.env["f3d.viewer.event"]._event_snapshot("Зупинка %s · %s" % (code, req.name))
