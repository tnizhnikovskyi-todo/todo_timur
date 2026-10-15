"""ST-1: `store_period_s = 300` для сигналів стану (CSV) і міграція 19.0.1.0.1 для сигналів зі значенням 0."""

import importlib.util
import re

from odoo.modules import get_module_path
from odoo.tests import tagged

from .. import hooks
from .common import F3DMachineCase

STATE_RE = re.compile(r"workcenters/[^/]+/(state|mode|alarm|job)$|equipment/GANTRY-1/(state|job)$")


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestStorePeriodMigration(F3DMachineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Sig = cls.env["f3d.signal"].with_context(active_test=False)

    def _targets(self):
        sigs = self.Sig.search([("module", "=", "machine_connect")])
        return sigs.filtered(lambda s: STATE_RE.match(s.code))

    def test_csv_values(self):
        """Сигнали, створені хуком установки, вже мають 300; решта шаблонів — як у CSV."""
        targets = self._targets()
        self.assertTrue(targets)
        self.assertEqual(set(targets.mapped("store_period_s")), {300})
        by_template = {r["template"]: r["store_period_s"] for r in hooks._csv_rows(self.env, "mc_signals")}
        for template in hooks.STORE_PERIOD_TEMPLATES:
            self.assertEqual(by_template[template], "300", template)
        pieces = self.Sig.search([("module", "=", "machine_connect"), ("code", "=like", "workcenters/%/pieces_out")])
        self.assertEqual(set(pieces.mapped("store_period_s")), {300})

    def test_migrate_only_zero(self):
        """Міграція ставить 300 лише там, де 0; ручне значення, `pieces_out` і шаблони «команд» не чіпає."""
        targets = self._targets()
        manual = self.Sig.search([("code", "=", "workcenters/SAW-1/mode")])
        pieces = self.Sig.search([("module", "=", "machine_connect"), ("code", "=like", "workcenters/%/pieces_out")])
        cmd = self.Sig.search([("code", "=", "equipment/GANTRY-1/cmd")])
        stacks = self.Sig.search([("code", "=", "equipment/GANTRY-1/stacks")])
        self.assertTrue(manual and pieces and cmd and stacks)
        self.env.cr.execute(
            "UPDATE f3d_signal SET store_period_s = 0 WHERE id IN %s", (tuple(targets.ids + pieces.ids),)
        )
        manual.store_period_s = 120
        self.env.invalidate_all()
        self.assertEqual(set((targets - manual).mapped("store_period_s")), {0})

        fixed = hooks.migrate_store_period(self.env)
        self.assertEqual(fixed, len(targets) - 1)
        self.assertEqual(set((targets - manual).mapped("store_period_s")), {300})
        self.assertEqual(manual.store_period_s, 120)
        self.assertEqual(set(pieces.mapped("store_period_s")), {0})  # не в списку ST-1
        self.assertEqual((cmd.store_period_s, stacks.store_period_s), (0, 0))
        self.assertEqual(hooks.migrate_store_period(self.env), 0)  # ідемпотентність

    def test_post_migrate_script(self):
        """Скрипт `migrations/19.0.1.0.1/post-migrate.py` викликає міграцію на поточній базі."""
        targets = self._targets()
        self.env.cr.execute("UPDATE f3d_signal SET store_period_s = 0 WHERE id IN %s", (tuple(targets.ids),))
        self.env.invalidate_all()
        path = get_module_path("factory3d_machine_connect") + "/migrations/19.0.1.0.1/post-migrate.py"
        spec = importlib.util.spec_from_file_location("f3d_mc_post_migrate_1_0_1", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.1.0.0")
        self.env.invalidate_all()
        self.assertEqual(set(targets.mapped("store_period_s")), {300})
