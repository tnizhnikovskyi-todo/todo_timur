"""AC-54 (права на вартість МО), M-17 (підписка енергетиків на заявки). AC-52 (провайдер переглядача) — W5."""

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import TAGS, F3DEnergyCase
from .test_alloc import AllocMixin
from .test_costing import SPEC


@tagged(*TAGS)
class TestMo231(AllocMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alloc_setup()

    def make(self):
        nodes = [self.mk_direct(c, p, lf, meter=False) for c, p, lf, _m in SPEC]
        mo = self.mk_mo(self.env["mrp.workcenter"].concat(*[n.workcenter_id for n in nodes]))
        for wo, (_c, _p, _lf, minutes) in zip(mo.workorder_ids.sorted("id"), SPEC, strict=True):
            self.log(wo, self.at(1), self.at(1, minutes))
        self.run_day()
        return mo

    def test_master_rights(self):  # AC-54
        self.u_mrpm = new_test_user(self.env, login="en_mrpm", groups="base.group_user,mrp.group_mrp_manager")
        mo = self.make()
        as_master = mo.with_user(self.u_master)
        self.assertAlmostEqual(as_master.read(["f3d_energy_kwh"])[0]["f3d_energy_kwh"], 86.213, places=3)
        with self.assertRaises(AccessError):
            as_master.read(["f3d_energy_cost"])
        arch = self.env["mrp.production"].with_user(self.u_master).get_view(view_type="form")["arch"]
        self.assertIn("f3d_energy_kwh", arch)
        self.assertNotIn("f3d_energy_cost", arch)
        arch = self.env["mrp.production"].with_user(self.u_mrpm).get_view(view_type="form")["arch"]
        self.assertIn("f3d_energy_cost", arch)

    def test_request_followers(self):  # M-17, AC-34 (підписка)
        signal = self.mk_signal("energy/consumers/SAW-T/p_now")
        equipment = self.env["maintenance.equipment"].create({"name": "SWB-T"})
        req = self.env["maintenance.request"].create(
            {"name": "Перевищення потужності", "equipment_id": equipment.id, "f3d_signal_id": signal.id}
        )
        self.assertIn(self.u_energy.partner_id, req.message_partner_ids)
        other = self.env["maintenance.request"].create({"name": "Інша", "equipment_id": equipment.id})
        self.assertNotIn(self.u_energy.partner_id, other.message_partner_ids)
