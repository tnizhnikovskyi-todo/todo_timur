"""Фікстури моста 3D: макет 14:20 W1 (`TestW1Common.fixture_grid`) + відкриті тривоги для шару `energy.layer`."""

from odoo.addons.td_energy.tests.common import TestW1Common
from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder, PayloadBuilder

TAGS = ("post_install", "-at_install", "f3d", "f3d_energy_viewer3d")
SECOND_TS = "2026-10-17 10:50:00"  # 13:50 Київ


class LayerCase(TestW1Common):
    """Макет 14:20: C2 — лічильник не на зв'язку (+ подія `bad`), PFC-2 — `warn`, ШР-2 — норма."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.u_viewer_only = cls._mk_user("l3d_viewer", [])
        cls.env.cr.execute("UPDATE td_signal SET last_value=NULL, last_text=NULL, last_ts=NULL, status='unknown'")
        cls.env["td.signal"].invalidate_model()

    def setUp(self):
        super().setUp()
        self.fixture_grid()
        self.Meter.search([("code", "=", "PM-QF-C2")]).write({"data_state": "stale"})
        self.c2 = self.Node.search([("code", "=", "C2")])
        self.c2_event = self.event(
            self.c2,
            "bad",
            "meter",
            "Лічильник PM-QF-C2 не на зв'язку",
            ts="2026-10-17 10:47:00",
            detail="modbus: timeout",
        )

    def event(self, node, level, kind="threshold", title="Тривога", state="active", ts=None, detail=None, text=None):
        return self.Event.create(
            {
                "node_id": node.id, "level": level, "kind": kind, "title": title, "text": text or title,
                "state": state, "ts": ts or SECOND_TS, "detail": detail or False,
            }
        )  # fmt: skip

    def provider(self, user=None):
        env = self.env(user=user.id) if user else self.env
        return env["td.viewer.provider.energy_layer"]

    def layer(self, user=None, **ctx):
        payload = {}
        self.provider(user)._f3d_viewer_collect(payload, dict({"kiosk": False, "changes": {}}, **ctx))
        return payload["energy"]["layer"]

    def node(self, layer, code):
        return next(n for n in layer["nodes"] if n["code"] == code)

    def payload(self, user, **kw):
        return PayloadBuilder(self.env(user=user.id), **kw).build()

    def delta(self, user, changes, **kw):
        return DeltaBuilder(self.env(user=user.id), None, changes=changes, **kw).build()
