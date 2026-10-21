"""AC-02, AC-03, AC-26: карта сигналів `chp/…` (C-chp-01)."""

import json
from pathlib import Path

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import file_open

from .. import hooks
from ..tools import gen_chp_signals
from .common import TAGS, ChpCase

REPO = Path(__file__).resolve().parents[4]  # …/factory3d


def _rows():
    with file_open("td_chp/data/chp_signals.json", "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


@tagged(*TAGS)
class TestSignalMap(ChpCase):
    def test_map_matches_json(self):  # AC-02
        rows = _rows()
        self.assertEqual(len(rows), 230)
        codes = [r["code"] for r in rows]
        self.assertEqual(len(set(codes)), 230)
        self.enable_write(False)
        sigs = {s.code: s for s in self.Signal.with_context(active_test=False).search([("module", "=", "chp")])}
        self.assertEqual(set(sigs), set(codes))
        for row in rows:
            sig = sigs[row["code"]]
            addr = sig.address
            self.assertEqual(
                (addr["fc"], addr["addr"], addr["type"], addr["scale"]), (3, row["pdu"], row["type"], row["scale"])
            )
            self.assertEqual(sig.period_s, row["period_s"], row["code"])
            self.assertEqual(sig.kind, "gauge")
            self.assertEqual(bool(sig.create_request), row["create_request"], row["code"])
        writable = [s for s in sigs.values() if "write" in (s.address or {})]
        self.assertEqual(
            sorted(s.code for s in writable),
            sorted(f"chp/ctl/{k}" for k in ("cmd", "mode", "sp_pct", "cos_set", "heat_dir", "bypass_mode")),
        )
        self.assertFalse(any(s.write_enabled for s in sigs.values()))
        # характерні рядки карти
        self.assertEqual(sigs["chp/gas/p_in"].address["addr"], 40200)
        self.assertEqual((sigs["chp/gas/p_in"].warn_low, sigs["chp/gas/p_in"].alarm_low), (1.7, 1.5))
        self.assertEqual(sigs["chp/eng/hours"].address["type"], "u32")
        self.assertEqual(sigs["chp/cyl/B8/plug_h"].address["addr"], 40864 + 15)
        self.assertEqual(sigs["chp/gen/p_kw"].store_period_s, 30)
        self.assertEqual(sigs["chp/eng/rpm"].store_period_s, 300)
        with self.assertRaises(ValidationError):  # код незмінний
            sigs["chp/gas/p_in"].write({"code": "chp/gas/p_in2"})
        sigs["chp/gas/p_in"].write({"code": "chp/gas/p_in"})  # той самий код — дозволено

    def test_json_is_generated_from_spec_map(self):  # C-chp-01: JSON відтворюється генератором
        with file_open("td_chp/data/chp_signals.json", "rb") as fh:
            self.assertEqual(fh.read().decode("utf-8"), gen_chp_signals.build())

    def test_engineer_edits_survive(self):  # AC-03
        sig = self.Signal.search([("code", "=", "chp/gas/p_in")])
        sig.write({"address": {"fc": 3, "addr": 41000, "type": "i16", "scale": 0.1}, "unit": "psi", "scale": 2.0})
        hooks.post_init(self.env)  # повторне -u: правки інженера зберігаються
        self.assertEqual((sig.address["addr"], sig.unit, sig.scale), (41000, "psi", 2.0))
        self.unit.with_user(self.u_mgr).action_reset_map()
        self.assertEqual((sig.address["addr"], sig.address["type"], sig.address["scale"]), (40200, "u16", 0.01))
        self.assertEqual((sig.unit, sig.scale), ("бар", 1.0))
        with self.assertRaises(AccessError):
            self.unit.with_user(self.u_op1).action_reset_map()  # лише менеджер

    def test_registers_json_identity(self):  # AC-26
        rows = _rows()
        taken = {}
        for row in rows:
            width = 2 if row["type"] == "u32" else 1
            for reg in range(row["pdu"], row["pdu"] + width):
                self.assertNotIn(reg, taken, f"{row['code']} перетинається з {taken.get(reg)}")
                taken[reg] = row["code"]
                self.assertFalse(40004 <= reg <= 40020, row["code"])
        emulator = REPO / "services" / "iot_sim" / "catalog" / "chp_registers.json"
        if emulator.exists():  # копію кладе W3
            own = file_open("td_chp/data/chp_signals.json", "rb").read()
            self.assertEqual(emulator.read_bytes(), own)
