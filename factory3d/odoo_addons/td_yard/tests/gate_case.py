"""Фікстури тестів W2: ворота GATE-W/GATE-E з тестовими сигналами, збірка події LPR."""

import hashlib
from datetime import datetime

from ..tools import params as P
from .flow import YardFlowCase

ROLES = ("state", "loop", "photocell", "passes", "cmd_open", "cmd_close", "cmd_hold")
SIGNAL_FIELD = {r: r + "_signal_id" for r in ROLES}
EPOCH = datetime(1970, 1, 1)


def capture_ms(ts):
    """UTC naive -> capture_timestamp (епоха мс)."""
    return str(int((ts - EPOCH).total_seconds() * 1000))


def lpr_event(n=1, **payload):
    """Подія telemetry M-11 з тілом у форматі iot_sim §8.13.2."""
    body = {
        "sensorProviderID": "CAM-05",
        "carState": "new",
        "carID": "12891",
        "packetCounter": str(2117397 + n),
        "capture_timestamp": "1791954905507",
        "plateText": "AA4512KT",
        "plateUnicode": "АА4512КТ",
        "plateConfidence": "0.912340",
        "plateCountry": "UA",
        "plateList": "f3d_bookings",
        "plateListMode": "allow",
        "plateListDescription": "BATCH/OUT/00004 DOCK-E2 Меблі Дім (демо)",
        **payload,
    }
    body = {k: v for k, v in body.items() if v is not None}
    return {
        "event_id": hashlib.sha256(str(n).encode()).hexdigest(),
        "route": "lpr",
        "ts": datetime(2026, 10, 14, 5, 15, 5, 507000),
        "remote": "10.90.2.5",
        "headers": {},
        "payload": body,
    }


class GateCase(YardFlowCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.gate_w = env.ref("factory3d_yard.gate_w")
        cls.gate_e = env.ref("factory3d_yard.gate_e")
        cls.gate_w.responsible_id = cls.user_guard
        col = env["f3d.collector"].create({"code": "COL-YT", "name": "Колектор двору (тест)"})
        cls.src = env["f3d.source"].create(
            {
                "code": "MB-U86-YT",
                "name": "ADAM (тест)",
                "type": "modbus_tcp",
                "collector_id": col.id,
                "params": {"host": "iot-sim", "port": 502, "unit": 86},
                "module": "yard",
                "write_enabled": True,
            }
        )
        cls.sigs = {}
        for tag, gate, base in (("TW", cls.gate_w, 0), ("TE", cls.gate_e, 8)):
            vals = {"source_id": cls.src.id}
            for i, role in enumerate(ROLES):
                is_cmd = role.startswith("cmd_")
                address = {"fc": 1 if is_cmd else 2, "addr": base + i, "type": "bool"}
                if role == "passes":
                    address = {"fc": 3, "addr": base + i, "count": 2, "type": "u32", "wordorder": "little"}
                if is_cmd:
                    address["write"] = {"fc": 5, "addr": base + i}
                sig = env["f3d.signal"].create(
                    {
                        "code": "yard/gates/%s/%s" % (tag, role),
                        "name": "%s %s" % (tag, role),
                        "kind": "counter" if role == "passes" else "gauge",
                        "source_id": cls.src.id,
                        "address": address,
                        "origin": "manual",
                        "period_s": 1,
                        "store_period_s": 60,
                        "write_enabled": is_cmd,
                    }
                )
                cls.sigs[(gate.f3d_code, role)] = sig
                vals[SIGNAL_FIELD[role]] = sig.id
            gate.write(vals)
        icp = env["ir.config_parameter"].sudo()
        icp.set_param("factory3d.telemetry.write_enabled", "True")
        for name, value in (("write_enabled", "True"), ("read_enabled", "True"), ("antipassback", "True")):
            P.set_param(env, name, value)

    def sig(self, gate, role):
        return self.sigs[(gate.f3d_code, role)]

    def put(self, gate, role, value, ts, status="ok"):
        """Показання сигналу воріт (як після telemetry _f3d_ingest)."""
        self.sig(gate, role).sudo().write({"last_value": float(value), "last_ts": ts, "status": status})

    def cmds(self, gate=None):
        return self.env["f3d.command"].sudo().search([("f3d_yard_gate_id", "=", (gate or self.gate_w).id)])

    def push(self, event):
        """Подія LPR через обробник маршруту (як у telemetry M-11)."""
        return self.env["f3d.push.handler.yard"]._f3d_handle_push("lpr", event)

    def recv(self, event):
        """Те саме, але повертає запис події."""
        return self.env["f3d.yard.lpr.event"].sudo()._f3d_from_push(event)
