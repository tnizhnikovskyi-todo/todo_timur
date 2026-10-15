"""Спільні фікстури тестів W1: ворота, типи операцій, товари, пакети."""

from datetime import datetime
from unittest.mock import patch

from odoo import Command

from ..tools import params as P
from .common import YardCase

T0 = datetime(2026, 10, 12, 10, 0)  # 13:00 Київ, понеділок


def at(hour, minute=0, day=12):
    """UTC naive за київським часом (жовтень 2026, UTC+3)."""
    return datetime(2026, 10, day, hour - 3, minute)


def freeze(ts):
    return patch("odoo.fields.Datetime.now", return_value=ts)


class YardFlowCase(YardCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.wh = env["stock.warehouse"].search([("company_id", "=", env.company.id)], limit=1)
        PType = env["stock.picking.type"]
        cls.ptype_in = PType.create(
            {
                "name": "T приймання",
                "code": "incoming",
                "sequence_code": "TYI",
                "warehouse_id": cls.wh.id,
                "default_location_src_id": env.ref("stock.stock_location_suppliers").id,
                "default_location_dest_id": cls.wh.lot_stock_id.id,
            }
        )
        cls.ptype_out = PType.create(
            {
                "name": "T відвантаження",
                "code": "outgoing",
                "sequence_code": "TYO",
                "warehouse_id": cls.wh.id,
                "default_location_src_id": cls.wh.lot_stock_id.id,
                "default_location_dest_id": env.ref("stock.stock_location_customers").id,
            }
        )
        cls.ptype_int = PType.create(
            {
                "name": "T внутрішнє",
                "code": "internal",
                "sequence_code": "TYX",
                "warehouse_id": cls.wh.id,
                "default_location_src_id": cls.wh.lot_stock_id.id,
                "default_location_dest_id": cls.wh.lot_stock_id.id,
            }
        )
        cls.dock_t1 = cls._dock("DOCK-T1", "west", 91)
        cls.dock_t2 = cls._dock("DOCK-T2", "west", 92)
        cls.dock_t3 = cls._dock("DOCK-T3", "east", 93)
        cls.dock_t4 = cls._dock("DOCK-T4", "west", 94)
        cls.dock_t5 = cls._dock("DOCK-T5", "west", 95)
        cls.ptype_in.dock_ids = [Command.set((cls.dock_t1 | cls.dock_t2 | cls.dock_t4).ids)]
        cls.ptype_out.dock_ids = [Command.set(cls.dock_t3.ids)]
        Categ = env["product.category"]
        cls.categ_plates = Categ.create({"name": "Плитні матеріали"})
        cls.categ_hdf = Categ.create({"name": "ХДФ", "parent_id": cls.categ_plates.id})
        cls.categ_edge = Categ.create({"name": "Крайка"})
        cls.product = cls._product("T Плита", 56.0, cls.categ_hdf)
        cls.product2 = cls._product("T Плита 2", 56.0, cls.categ_hdf)
        cls.product_nw = cls._product("T Фурнітура", 0.0, cls.categ_edge)
        P.set_param(env, "calendar_id", "")
        P.set_param(env, "enforce_calendar", "False")
        P.set_param(env, "auto_call_next", "False")

    @classmethod
    def _dock(cls, code, side, no):
        return cls.env["stock.location"].create(
            {
                "name": code,
                "usage": "internal",
                "location_id": cls.wh.view_location_id.id,
                "f3d_kind": "dock",
                "f3d_code": code,
                "f3d_side": side,
                "f3d_dock_no": no,
                "f3d_x": 10.0,
                "f3d_y": 10.0,
            }
        )

    @classmethod
    def _product(cls, name, weight, categ):
        return cls.env["product.product"].create(
            {"name": name, "type": "consu", "weight": weight, "categ_id": categ.id}
        )

    @classmethod
    def _batch(
        cls,
        code="incoming",
        lines=((120, None), (80, "p2")),
        partner=None,
        dock=None,
        start=None,
        end=None,
        product=None,
    ):
        """Пакет з одним документом; lines — (qty, product|None)."""
        ptype = {"incoming": cls.ptype_in, "outgoing": cls.ptype_out, "internal": cls.ptype_int}[code]
        picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": ptype.id,
                "location_id": ptype.default_location_src_id.id,
                "location_dest_id": ptype.default_location_dest_id.id,
                "partner_id": partner.id if partner else False,
                "move_ids": [
                    Command.create(
                        {
                            "description_picking": "t",
                            "product_id": (cls.product2 if prod == "p2" else prod or product or cls.product).id,
                            "product_uom_qty": qty,
                            "location_id": ptype.default_location_src_id.id,
                            "location_dest_id": ptype.default_location_dest_id.id,
                        }
                    )
                    for qty, prod in lines
                ],
            }
        )
        picking.action_confirm()
        vals = {"picking_type_id": ptype.id, "picking_ids": [Command.set(picking.ids)]}
        if dock:
            vals.update(dock_id=dock.id, scheduled_date=start, end_date=end)
        return cls.env["stock.picking.batch"].create(vals)

    def _visit(self, **vals):
        vals.setdefault("visit_type", "incoming")
        return self.env["f3d.yard.visit"].create(vals)

    def _booking(self, visit, dock, start, end, confirm=False, **vals):
        booking = self.env["f3d.yard.booking"].create(
            dict(visit_id=visit.id if visit else False, dock_id=dock.id, slot_start=start, slot_end=end, **vals)
        )
        if confirm:
            booking.action_confirm()
        return booking

    def _force(self, visit, state, **vals):
        """Тестове форсування стану (без перевірки переходів)."""
        visit.write(dict(vals, state=state))
        return visit
