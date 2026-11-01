from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.td_viewer3d.tools.payload import PayloadBuilder, DeltaBuilder

from .common import F3dViewerBase, F3dViewerCase

SIGNAL = "energy/consumers/SAW-1/p_now"
CORE = ("stock", "production", "logistics", "maintenance", "people")


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDeltaSignalOnly(F3dViewerBase):
    """Тік сигналів (коди — шляхи, а не коди записів сцени) не змушує основних провайдерів збирати розділи цілком."""

    def _spy(self, name, attr):
        cls = type(self.env["td.viewer.provider." + name])
        original = getattr(cls, attr)
        calls = []

        def spy(this, patch, ctx, original=original):
            calls.append(ctx)
            return original(this, patch, ctx)

        self.patch(cls, attr, spy)
        return calls

    def _delta(self, changes, codes=None):
        env = self.env(user=self.user_f3d)
        return DeltaBuilder(env, None, changes=changes, codes=codes).build()

    def test_signal_only_skips_core_collects(self):
        collects = {key: self._spy(key, "_td_viewer_collect") for key in CORE}
        res = self._delta({"x_f3d_signal": {SIGNAL}}, codes={SIGNAL})
        self.assertFalse(res["full"])
        self.assertEqual(res["events"], 1)
        self.assertEqual({k: len(v) for k, v in collects.items()}, dict.fromkeys(CORE, 0))
        for key in ("locations", "pickings", "docks", "productions", "workorders", "employees", "maintenance_requests"):
            self.assertNotIn(key, res["patch"], key)

    def test_signal_codes_not_in_ctx_codes(self):
        seen = self._spy("stock", "_td_viewer_delta")
        self._delta({"x_f3d_signal": {SIGNAL}, "stock.quant": {"TST-LOC-A"}}, codes={SIGNAL, "TST-LOC-B"})
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["codes"], {"TST-LOC-A", "TST-LOC-B"})

    def test_unrelated_codes_skip_other_providers(self):
        """Коди, яких немає серед записів провайдера (ескорт складської події), не змушують його збирати розділи."""
        collects = {key: self._spy(key, "_td_viewer_collect") for key in CORE if key != "stock"}
        res = self._delta({"stock.quant": {"NO-SUCH-CODE"}})
        self.assertFalse(res["full"])
        self.assertEqual({k: len(v) for k, v in collects.items()}, dict.fromkeys(collects, 0))
        for key in ("pickings", "docks", "productions", "workorders", "employees", "maintenance_requests"):
            self.assertNotIn(key, res["patch"], key)

    def test_other_models_codes_still_selected(self):
        """Клієнтські коди, яких немає серед сигналів, лишаються (повтор після збою, ескорт подій)."""
        collects = self._spy("stock", "_td_viewer_collect")
        self._delta({}, codes={"TST-LOC-B"})
        self.assertEqual(len(collects), 1)
        self.assertEqual(collects[0]["only_locs"], {"TST-LOC-B"})


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDeltaStockScope(F3dViewerCase):
    """Дельта stock збирає лише вибрані локації й віддає рівно те, що дала б повна збірка після фільтра за кодами."""

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.env.ref("base.user_admin"))

    def _locations(self, codes):
        env = self.env
        full = PayloadBuilder(env, sections={"locations"}).build()["locations"]
        delta = DeltaBuilder(env, fields.Datetime.now() - timedelta(minutes=5), changes={}, codes=codes).build()
        return full, delta["patch"].get("locations") or {}

    def test_scoped_equals_filtered_full(self):
        quants = self.env["stock.quant"].search([("quantity", ">", 0), ("location_id.td_code", "!=", False)], limit=40)
        codes = set(quants.location_id.mapped("td_code")[:12])
        if not codes:
            self.skipTest("немає залишків у локаціях із кодом")
        full, got = self._locations(codes | {"NO-SUCH-LOC"})
        self.assertTrue(got)
        want = {"locations": {c: v for c, v in full.items() if c in codes}}
        DeltaBuilder._null_opt_keys(want)  # дельта дописує null для відсутніх opt-ключів (R-14 п. 4)
        self.assertEqual(got, want["locations"])

    def test_unknown_code_is_cheap(self):
        """Код без локації: ні залишків, ні товарів, ні складських вибірок — лише пошук локації й перевірки доступу."""
        prov = self.env["td.viewer.provider.stock"]
        ctx = {"codes": {"NO-SUCH-LOC"}, "changes": {}, "static": {}, "today": "2026-10-12", "delta": True}
        patch = {}
        prov._td_viewer_delta(patch, ctx)  # прогрів кешів доступу
        self.env.invalidate_all()
        n0 = self.env.cr.sql_log_count
        prov._td_viewer_delta(patch, ctx)
        self.assertEqual(patch, {})
        self.assertLessEqual(self.env.cr.sql_log_count - n0, 6)

    def test_empty_codes_collects_nothing(self):
        collects = []
        cls = type(self.env["td.viewer.provider.stock"])
        original = cls._td_viewer_collect

        def spy(this, payload, ctx):
            collects.append(1)
            return original(this, payload, ctx)

        self.patch(cls, "_td_viewer_collect", spy)
        res = DeltaBuilder(self.env, fields.Datetime.now(), changes={"x_f3d_signal": {SIGNAL}}).build()
        self.assertFalse(collects)
        self.assertNotIn("locations", res["patch"])

    def test_related_codes_still_collect(self):
        """Коди, що збігаються із записами провайдера, збираються як раніше (гейт не ковтає зміни)."""
        env = self.env
        picking = env["stock.picking"].search([], limit=1)
        equipment = env["maintenance.equipment"].search([("td_code", "!=", False)], limit=1)
        wc = env["mrp.workcenter"].search([("td_code", "!=", False)], limit=1)
        if not (picking and equipment and wc):
            self.skipTest("у демо-базі немає переміщення, обладнання чи центру з кодом")
        cases = {
            "logistics": {picking.name},
            "maintenance": {equipment.td_code},
            "people": {wc.td_code},
            "production": {wc.td_code},
        }
        for key, codes in cases.items():
            calls = []
            cls = type(env["td.viewer.provider." + key])
            original = cls._td_viewer_collect

            def spy(this, payload, ctx, original=original, calls=calls):
                calls.append(1)
                return original(this, payload, ctx)

            with patch.object(cls, "_td_viewer_collect", spy):
                DeltaBuilder(env, fields.Datetime.now(), changes={}, codes=codes).build()
            self.assertTrue(calls, key)

    def test_dock_code_selects_logistics(self):
        calls = []
        cls = type(self.env["td.viewer.provider.logistics"])
        original = cls._td_viewer_collect

        def spy(this, payload, ctx):
            calls.append(1)
            return original(this, payload, ctx)

        with patch.object(cls, "_td_viewer_collect", spy):
            res = DeltaBuilder(self.env, fields.Datetime.now(), changes={}, codes={"DOCK-W1"}).build()
        self.assertTrue(calls)
        self.assertIn("docks", res["patch"])

    def test_collect_shared_with_chains(self):
        """production/logistics збирають розділи один раз на дельту: `chains` бере готові, а не збирає вдруге."""
        env = self.env
        mo = env["mrp.production"].search([], limit=1)
        picking = env["stock.picking"].search([], limit=1)
        if not (mo and picking):
            self.skipTest("у демо-базі немає МО чи переміщення")
        calls = {"production": 0, "logistics": 0, "stock": 0}
        for key in calls:
            cls = type(env["td.viewer.provider." + key])
            original = cls._td_viewer_collect

            def spy(this, payload, ctx, original=original, key=key):
                calls[key] += 1
                return original(this, payload, ctx)

            self.patch(cls, "_td_viewer_collect", spy)
        res = DeltaBuilder(
            env, fields.Datetime.now(), changes={"mrp.production": {mo.name}, "stock.picking": {picking.name}}
        ).build()
        self.assertIn("sheet_chain", res["patch"])  # chains відпрацював
        self.assertEqual(calls["production"], 1)
        self.assertEqual(calls["logistics"], 1)
        self.assertEqual(calls["stock"], 2)  # власна дельта (вибрані локації) + повна збірка для chains

    def test_chains_patch_unchanged_by_sharing(self):
        """Спільні дані не псують патч: productions/pickings у дельті збігаються з тим, що дала б окрема збірка."""
        env = self.env
        mo = env["mrp.production"].search([], limit=1)
        if not mo:
            self.skipTest("у демо-базі немає МО")
        res = DeltaBuilder(env, fields.Datetime.now(), changes={"mrp.production": {mo.name}}).build()
        full = PayloadBuilder(env).build()
        want = next(m for m in full["productions"] if m["name"] == mo.name)
        got = next(m for m in res["patch"]["productions"] if m["name"] == mo.name)
        for key in ("state", "supply", "delivery", "components"):
            self.assertEqual(got.get(key), want.get(key), key)
