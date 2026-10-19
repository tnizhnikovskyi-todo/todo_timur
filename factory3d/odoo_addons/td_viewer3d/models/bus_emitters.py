"""M-07: емітери шини — перевизначення стандартних моделей (FR-18).

Спільний міксин перехоплює create / write / _write_multi (обчислювані збережені поля пишуться через `_write`) / unlink
і публікує коди через `td.viewer.event._notify` (коалесценція — R-15).
"""

from odoo import api, models

IN_PROGRESS_NAMES = {"in progress", "в роботі"}


def _wo_code(wo):
    return "WO%05d" % wo.id if wo and wo.id else None


class F3dViewerBusMixin(models.AbstractModel):
    _name = "td.viewer.bus.mixin"
    _description = "3D: міксин емітера шини"

    _td_bus_fields = ()
    _td_bus_kind = "state"

    def _td_bus_codes(self):
        return set()

    def _td_bus_active(self):
        return "td.viewer.event" in self.env and not self.env.context.get("f3d_viewer_no_bus")

    def _td_bus_publish(self, codes):
        if codes:
            self.env["td.viewer.event"]._notify(self._name, codes, self._td_bus_kind)

    def _td_bus_hit(self, vals):
        return bool(self._td_bus_fields) and bool(set(self._td_bus_fields) & set(vals)) and self._td_bus_active()

    def _td_bus_safe_codes(self):
        try:
            return {c for c in self.sudo()._td_bus_codes() if c}
        except Exception:  # noqa: BLE001 — емітер ніколи не ламає бізнес-операцію
            return set()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records and records._td_bus_active():
            records._td_bus_publish(records._td_bus_safe_codes())
        return records

    def write(self, vals):
        hit = self._td_bus_hit(vals)
        old = self._td_bus_safe_codes() if hit else set()
        res = super().write(vals)
        if hit:
            self._td_bus_publish(old | self._td_bus_safe_codes())
        return res

    def _write_multi(self, vals_list):
        # обчислювані збережені поля (state…) пишуться при flush саме через _write_multi, повз write()
        hit = any(self._td_bus_hit(vals) for vals in vals_list)
        old = self._td_bus_safe_codes() if hit else set()
        res = super()._write_multi(vals_list)
        if hit:
            self._td_bus_publish(old | self._td_bus_safe_codes())
        return res

    def unlink(self):
        if self._td_bus_active():
            self._td_bus_publish(self._td_bus_safe_codes())
        return super().unlink()


class StockQuant(models.Model):
    _inherit = ["stock.quant", "td.viewer.bus.mixin"]
    _td_bus_fields = ("quantity", "reserved_quantity", "lot_id", "package_id", "location_id")
    _td_bus_kind = "stock"

    def _td_bus_codes(self):
        return set(self.location_id.mapped("td_code"))


class StockMoveLine(models.Model):
    _inherit = ["stock.move.line", "td.viewer.bus.mixin"]
    _td_bus_fields = ("quantity", "picked", "state", "location_id", "location_dest_id")
    _td_bus_kind = "stock"

    def _td_bus_codes(self):
        return (
            set(self.location_id.mapped("td_code"))
            | set(self.location_dest_id.mapped("td_code"))
            | set(self.picking_id.mapped("name"))
        )


class StockPicking(models.Model):
    _inherit = ["stock.picking", "td.viewer.bus.mixin"]
    _td_bus_fields = ("state", "scheduled_date", "date_done", "batch_id", "partner_id")
    _td_bus_kind = "doc"

    def _td_bus_codes(self):
        return set(self.mapped("name")) | set(self.batch_id.dock_id.mapped("td_code"))


class StockPickingBatch(models.Model):
    _inherit = ["stock.picking.batch", "td.viewer.bus.mixin"]
    _td_bus_fields = ("state", "dock_id", "td_code", "td_vehicle_id", "picking_ids", "scheduled_date")
    _td_bus_kind = "doc"

    def _td_bus_codes(self):
        return (
            set(self.picking_ids.mapped("name"))
            | set(self.dock_id.mapped("td_code"))
            | set(self.mapped("td_code"))
            | set(self.td_vehicle_id.mapped("td_code"))
        )


class MrpWorkorder(models.Model):
    _inherit = ["mrp.workorder", "td.viewer.bus.mixin"]
    _td_bus_fields = ("state", "date_start", "date_finished", "working_state", "workcenter_id", "duration")
    _td_bus_kind = "state"

    def _td_bus_codes(self):
        return (
            {_wo_code(wo) for wo in self}
            | set(self.production_id.mapped("name"))
            | set(self.workcenter_id.mapped("td_code"))
        )


class MrpProduction(models.Model):
    _inherit = ["mrp.production", "td.viewer.bus.mixin"]
    _td_bus_fields = ("state", "reservation_state", "product_qty", "date_start", "date_deadline", "move_raw_ids")
    _td_bus_kind = "doc"

    def _td_bus_codes(self):
        return set(self.mapped("name"))


class MrpWorkcenter(models.Model):
    _inherit = ["mrp.workcenter", "td.viewer.bus.mixin"]
    _td_bus_fields = ("working_state", "active")
    _td_bus_kind = "state"

    def _td_bus_codes(self):
        return set(self.mapped("td_code"))


class MrpWorkcenterProductivity(models.Model):
    _inherit = ["mrp.workcenter.productivity", "td.viewer.bus.mixin"]
    _td_bus_fields = ("date_start", "date_end", "loss_id", "workcenter_id")
    _td_bus_kind = "state"

    def _td_bus_codes(self):
        return set(self.workcenter_id.mapped("td_code")) | {_wo_code(wo) for wo in self.workorder_id}


class MaintenanceRequest(models.Model):
    _inherit = ["maintenance.request", "td.viewer.bus.mixin"]
    _td_bus_fields = ("stage_id", "equipment_id", "schedule_date", "user_id", "priority")
    _td_bus_kind = "maintenance"

    def _td_bus_codes(self):
        codes = set(self.mapped("name")) | set(self.equipment_id.mapped("td_code"))
        if "workcenter_id" in self.equipment_id._fields:
            codes |= set(self.equipment_id.workcenter_id.mapped("td_code"))
        return codes

    def write(self, vals):
        res = super().write(vals)
        if "stage_id" in vals and self._td_bus_active():
            self._td_bus_event_snapshot()
        return res

    def _td_bus_event_snapshot(self):
        """AC-49: перехід у стадію «В роботі» для обладнання з кодом сцени — знімок kind=event."""
        stage = self.env.ref("maintenance.stage_1", raise_if_not_found=False)
        for req in self.sudo():
            code = req.equipment_id.td_code
            name = (req.stage_id.name or "").strip().lower()
            if code and ((stage and req.stage_id == stage) or name in IN_PROGRESS_NAMES):
                self.env["td.viewer.event"]._event_snapshot("Зупинка %s · %s" % (code, req.name))
