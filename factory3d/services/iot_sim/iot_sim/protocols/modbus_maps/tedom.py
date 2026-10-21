"""P-07 TEDOM Quanto D800 NG (SPEC §8.9.5, ПРИПУЩЕННЯ): unit 72; адреси задано одразу в PDU.

Старі регістри 40000–40007, 40010–40015, 40020 і вікно u73 (230–233) — без змін. Нові (SPEC td_chp §8, D-11) — з
JSON-карти ``catalog/chp_registers.json`` (копія ``td_chp/data/chp_signals.json``: ``pdu``, ``type``, ``scale``,
``rw``); значення — ``Chp.regs[<код>]`` (інженерні одиниці; регістр = round(значення / scale)), запис ``W``/``RW`` —
``Chp.write_reg``/``Chp.post_command``; при ``ctx.write_accept = False`` — ``ModbusError(4)``, значення поза
межами — ``ModbusError(3)``. Адреси, що вже зайняті старою картою (40000–40003), пропускаються: їхні дублі в JSON
віддає старий обробник.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from iot_sim.models.meter import ctl
from iot_sim.protocols.modbus_maps import Ctx, ModbusError, encode, to_int, words_of

UNIT = 72
H = "infra/chp"
MAP_PATH = Path(__file__).resolve().parents[3] / "catalog" / "chp_registers.json"
WORDS = {"u16": 1, "i16": 1, "u32": 2, "i32": 2}


def load_map(path: Path = MAP_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "TEDOM")

    def state() -> int:
        return to_int(ctx.val(f"{H}/state", 2))

    um.add_hr(40000, lambda: [state()], 1, None, "state")
    um.add_hr(40001, lambda: [to_int(ctx.num("infra/totals/chp_kw"))], 1, None, "power")
    um.add_hr(40002, lambda: [to_int(ctx.num(f"{H}/heat_kw"))], 1, None, "heat")
    um.add_hr(40003, lambda: [to_int(ctx.num(f"{H}/gas_m3h") / 0.1)], 1, None, "gas")
    um.add_const(40004, [900, 700], "water_temps")
    um.add_hr(40006, lambda: [1500 if state() == 2 else 0], 1, None, "speed")

    def setpoint_set(_off: int, v: int) -> None:
        if not ctx.write_accept:
            raise ModbusError(4)
        ctx.world.set_flag("modbus.u72.setpoint", v)
        ctx.world.set_flag("chp_run", v > 0)  # ненульове завдання навантаження запускає КГУ, 0 — зупиняє
        ctx.command(UNIT, f"Load setpoint = {v} %")

    um.add_hr(40007, lambda: [to_int(ctx.world.flag("modbus.u72.setpoint", 50))], 1, setpoint_set, "load_setpoint")
    um.add_hr(40010, lambda: words_of(to_int(ctx.num(f"{H}/hours")), 2), 2, None, "hours")
    um.add_const(40012, words_of(211, 2), "starts")
    um.add_hr(40014, lambda: words_of(to_int(ctx.num(f"{H}/kwh_total")), 2), 2, None, "kwh_total")
    um.add_hr(40020, lambda: [101 if state() == 3 else 0], 1, None, "alarm_code")
    build_full(ctx, um)


def build_full(ctx: Ctx, um: Any) -> None:
    """Нова карта КГУ (230 регістрів) з ``catalog/chp_registers.json``; без моделі ``CHP`` у світі — нічого не додає."""
    model = ctx.model("CHP")
    if model is None or not hasattr(model, "regs"):
        return
    w = ctx.world

    def reader(code: str, scale: float, typ: str) -> Any:
        return lambda: encode(model.regs.get(code, 0.0) / scale, typ)

    def cmd_setter(_off: int, v: int) -> None:
        if not ctx.write_accept:
            raise ModbusError(4)
        if not 0 <= v <= 4:
            raise ModbusError(3)
        if v:
            model.post_command(v)
            ctx.command(UNIT, f"CHP ctl/cmd = {v}")

    def reg_setter(code: str) -> Any:
        def setter(_off: int, v: int) -> None:
            if not ctx.write_accept:
                raise ModbusError(4)
            try:
                model.write_reg(code, v)
            except ValueError as e:
                raise ModbusError(3) from e
            ctx.command(UNIT, f"{code} = {v}")

        return setter

    live = {  # прапори світу — читаються в момент запиту (результат команди видно без очікування тіку)
        "chp/ctl/cmd": lambda: [int(ctl(w, "chp_cmd"))],
        "chp/ctl/ack": lambda: [int(ctl(w, "chp_ack"))],
        "chp/ctl/ack_reason": lambda: [int(w.flags.get("chp_ack_reason", 0))],
    }
    for row in load_map():
        code, pdu, typ, scale, rw = row["code"], row["pdu"], row["type"], float(row["scale"]), row["rw"]
        getter = live.get(code) or reader(code, scale, typ)
        if code == "chp/ctl/cmd":
            setter: Any = cmd_setter
        elif "W" in rw:
            setter = reg_setter(code)
        else:
            setter = None
        um.add_hr(pdu, getter, WORDS[typ], setter, code)
