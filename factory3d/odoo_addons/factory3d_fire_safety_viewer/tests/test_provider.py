"""AC-58 (M-17): провайдери 130/140 у PayloadBuilder і DeltaBuilder переглядача."""
import json
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.factory3d_fire_safety.tests.common import FireCase
from odoo.addons.factory3d_viewer.tools.payload import DeltaBuilder, PayloadBuilder, get_providers


@tagged("post_install", "-at_install", "f3d", "f3d_fire_viewer")
class TestProvider(FireCase):

    def test_registered_and_live(self):
        names = {p._name: p for p in get_providers(self.env)}
        fire, evac = names["f3d.viewer.provider.fire"], names["f3d.viewer.provider.evacuation"]
        self.assertEqual((fire._f3d_sequence, fire._f3d_sections), (130, ("fire",)))
        self.assertEqual((evac._f3d_sequence, evac._f3d_sections), (140, ("evacuation",)))
        self.assertEqual(fire._f3d_group, "factory3d_base.group_f3d_user")
        self.assertEqual(fire._f3d_viewer_bus_models(), [
            "f3d.fire.panel", "f3d.fire.zone", "f3d.fire.system", "f3d.fire.event", "f3d.fire.device"])
        self.assertEqual(evac._f3d_viewer_bus_models(), ["f3d.fire.drill", "f3d.fire.route", "f3d.fire.exit"])
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
        Event = self.env["f3d.viewer.event"].sudo()
        before = Event.search([("model", "=", "f3d.fire.zone")]).ids
        since = fields.Datetime.now() - timedelta(seconds=1)
        self.push_text("fire/groups/FA-CUT/state", "alarm", self.at(0))
        self.env.flush_all()
        self.env.cr.precommit.run()
        events = Event.search([("model", "=", "f3d.fire.zone"), ("id", "not in", before)])
        self.assertEqual([e.codes for e in events], [["FA-CUT"]])
        delta = DeltaBuilder(self.env(user=self.u), since=since, changes={"f3d.fire.zone": {"FA-CUT"}}).build()
        self.assertEqual(delta["patch"]["fire"]["groups"]["FA-CUT"]["state"], "alarm")
        self.assertNotIn("evacuation", delta["patch"])
        other = DeltaBuilder(self.env(user=self.u), since=since, changes={"stock.quant": {"LOC-1"}}).build()
        self.assertNotIn("fire", other["patch"])
        drill = DeltaBuilder(self.env(user=self.u), since=since, changes={"f3d.fire.drill": {"DRILL/1"}}).build()
        self.assertIn("evacuation", drill["patch"])
