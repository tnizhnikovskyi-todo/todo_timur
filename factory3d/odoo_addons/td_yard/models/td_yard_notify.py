"""R-21: сповіщення шини `f3d_yard` (API-05) і viewer для воріт, ваг, подій LPR (W4)."""

from odoo import fields, models

BUS_KEY = "f3d_yard.bus"


def f3d_yard_bus_add(env, model, ids):
    """Збирає (модель, id) у precommit; один `_sendone` на модель при завершенні транзакції (R-21 п. 4)."""
    ids = [i for i in ids if i]
    if not ids:
        return
    data = env.cr.precommit.data
    pending = data.setdefault(BUS_KEY, {})
    if not data.get(BUS_KEY + ".scheduled"):
        data[BUS_KEY + ".scheduled"] = True

        def flush():
            batch = data.pop(BUS_KEY, {})
            data.pop(BUS_KEY + ".scheduled", None)
            for name, model_ids in batch.items():
                env["bus.bus"]._sendone(
                    "f3d_yard",
                    "f3d_yard/update",
                    {"model": name, "ids": sorted(model_ids), "ts": fields.Datetime.now().isoformat()},
                )

        env.cr.precommit.add(flush)
    pending.setdefault(model, set()).update(ids)


class F3dYardGateNotify(models.Model):
    _inherit = "td.yard.gate"

    def _td_yard_notify(self):
        res = super()._td_yard_notify()
        gates = self.sudo()
        f3d_yard_bus_add(self.env, "td.yard.gate", gates.ids)
        ev = self.env["td.yard.visit"]._td_yard_viewer_event()
        if ev:
            for gate in gates:
                ev._notify("td.yard.gate", [gate.td_code], "state")
        return res


class F3dYardScaleNotify(models.Model):
    _inherit = "td.yard.scale"

    def _td_yard_notify(self):
        res = super()._td_yard_notify()
        scales = self.sudo()
        f3d_yard_bus_add(self.env, "td.yard.scale", scales.ids)
        ev = self.env["td.yard.visit"]._td_yard_viewer_event()
        if ev:
            for scale in scales:
                ev._notify("td.yard.scale", [scale.td_code], "state")
        return res


class F3dYardLprEventNotify(models.Model):
    _inherit = "td.yard.lpr.event"

    def _td_yard_notify(self):
        res = super()._td_yard_notify()
        f3d_yard_bus_add(self.env, "td.yard.lpr.event", self.ids)
        return res
