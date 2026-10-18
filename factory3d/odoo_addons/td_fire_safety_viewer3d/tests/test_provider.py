"""AC-58 (M-17): провайдери 130/140 у PayloadBuilder і DeltaBuilder переглядача."""
import json
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.td_fire_safety.tests.common import FireCase
from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder, PayloadBuilder, get_providers


@tagged("post_install", "-at_install", "f3d", "f3d_fire_viewer")
class TestProvider(FireCase):

    def test_registered_and_live(self):
        names = {p._name: p for p in get_providers(self.env)}
        fire, evac = names["td.viewer.provider.fire"], names["td.viewer.provider.evacuation"]
        self.assertEqual((fire._f3d_sequence, fire._f3d_sections), (130, ("fire",)))
        self.assertEqual((evac._f3d_sequence, evac._f3d_sections), (140, ("evacuation",)))
        self.assertEqual(fire._f3d_group, "td_factory3d.group_td_user")
        self.assertEqual(fire._f3d_viewer_bus_models(), [
            "td.fire.panel", "td.fire.zone", "td.fire.system", "td.fire.event", "td.fire.device"])
        self.assertEqual(evac._f3d_viewer_bus_models(), ["td.fire.drill", "td.fire.route", "td.fire.exit"])
        data = PayloadBuilder(self.env(user=self.u), sections=["fire", "evacuation"]).build()
        self.assertEqual(data["meta"]["sections"]["fire"], "live")
        self.assertEqual(data["meta"]["sections"]["evacuation"], "live")
        self.assertEqual(len(data["fire"]["groups"]), 35)
        self.assertEqual(len(data["evacuation"]["exits"]), 12)
        json.dumps(data["fire"])
        json.dumps(data["evacuation"])

    def test_bus_and_delta(self):
        # накопичення шини з setUpClass (клас-рівневий курсор) не має блокувати реєстрацію precommit-колбека
        self.env.cr.precommit.data.pop("f3d_viewer.notify", None)
        Event = self.env["td.viewer.event"].sudo()
        before = Event.search([("model", "=", "td.fire.zone")]).ids
        since = fields.Datetime.now() - timedelta(seconds=1)
        self.push_text("fire/groups/FA-CUT/state", "alarm", self.at(0))
        self.env.flush_all()
        self.env.cr.precommit.run()
        events = Event.search([("model", "=", "td.fire.zone"), ("id", "not in", before)])
        self.assertEqual([e.codes for e in events], [["FA-CUT"]])
        delta = DeltaBuilder(self.env(user=self.u), since=since, changes={"td.fire.zone": {"FA-CUT"}}).build()
        self.assertEqual(delta["patch"]["fire"]["groups"]["FA-CUT"]["state"], "alarm")
        self.assertNotIn("evacuation", delta["patch"])
        other = DeltaBuilder(self.env(user=self.u), since=since, changes={"stock.quant": {"LOC-1"}}).build()
        self.assertNotIn("fire", other["patch"])
        drill = DeltaBuilder(self.env(user=self.u), since=since, changes={"td.fire.drill": {"DRILL/1"}}).build()
        self.assertIn("evacuation", drill["patch"])

    def test_group_request_id_resolves_in_requests(self):
        """Viewer R-22: `maintenance_request_id` групи == `res_id` заявки в `maintenance_requests` (не за назвою)."""
        self.push_value("fire/groups/FA-FAC/dust", 90.1, self.at(0))
        request = self.env["maintenance.request"].search([("td_fire_zone_id", "=", self.z_fac.id)])
        self.assertEqual(len(request), 1)
        twin = self.env["maintenance.request"].create({
            "name": request.name, "equipment_id": request.equipment_id.id,
            "stage_id": self.env["maintenance.stage"].search([("done", "=", False)], limit=1).id})
        self.assertNotEqual(twin.id, request.id)
        self.env.invalidate_all()
        data = PayloadBuilder(self.env(user=self.u), sections=["fire", "maintenance_requests", "equipment"]).build()
        group = data["fire"]["groups"]["FA-FAC"]
        by_res_id = {r["res_id"]: r for r in data["maintenance_requests"]}
        self.assertEqual(group["maintenance_request_id"], request.id)
        self.assertEqual(by_res_id[group["maintenance_request_id"]]["name"], group["maintenance_request"])
        self.assertIn(twin.id, by_res_id)
