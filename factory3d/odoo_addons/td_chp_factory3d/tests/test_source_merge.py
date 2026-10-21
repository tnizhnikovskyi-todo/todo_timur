"""AC-B02: одне джерело Modbus на пристрій — сигнали `chp/…` на `MB-U72-CHP`, `CHP-U72` архівовано."""

from odoo.tests import tagged

from .. import hooks
from .common import TAGS, BridgeCase


@tagged(*TAGS)
class TestSourceMerge(BridgeCase):
    def signals(self):
        return self.Signal.with_context(active_test=False).search([("module", "=", "chp")])

    def test_signals_on_energy_source(self):
        target = self.env["td.source"].search([("code", "=", "MB-U72-CHP")])
        self.assertTrue(target)
        signals = self.signals()
        self.assertEqual(len(signals), 230)
        self.assertEqual(signals.mapped("source_id"), target)
        self.assertEqual(self.unit.source_id, target)
        own = self.env.ref("td_chp.source_chp_u72")
        self.assertFalse(own.active)

    def test_post_init_is_idempotent(self):
        before = self.signals().mapped("source_id").ids
        hooks.post_init(self.env)
        hooks.post_init(self.env)
        self.assertEqual(self.signals().mapped("source_id").ids, before)
        self.assertFalse(self.env.ref("td_chp.source_chp_u72").active)

    def test_uninstall_returns_signals_to_own_source(self):
        hooks.uninstall_hook(self.env)
        own = self.env.ref("td_chp.source_chp_u72")
        self.assertTrue(own.active)
        self.assertEqual(self.signals().mapped("source_id"), own)
        self.assertEqual(self.unit.source_id, own)

    def test_energy_signals_keep_their_source(self):
        energy = self.Signal.search([("code", "like", "infra/chp/%")])
        self.assertTrue(energy)
        self.assertEqual(energy.mapped("source_id.code"), ["MB-U72-CHP"])
