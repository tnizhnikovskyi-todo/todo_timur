"""P-02/P-07/P-09 Advantech ADAM-6050 (SPEC §8.4.2, §8.9.6, §8.11.3): unit 80–85; 12 DI, 6 DO.

Спільний код цифрового модуля (``digital_module``) використовує й ``adam6060``. Адреси — PDU
(coil/DI ``0000N`` -> ``N-1``; HR ``4NNNN`` -> ``N-40001``); лічильники — 32 біт, **молодше слово першим**.
DI/лічильники беруться з каталогу (``SignalSpec.modbus``); решта каналів — 0 (резерв).
"""
from __future__ import annotations

from iot_sim.protocols.modbus_maps import (
    Ctx,
    ModbusError,
    UnitMap,
    coil_cmd,
    parse_scale,
    to_bool,
    to_float,
    to_int,
    words_of,
)

MACHINE_UNITS = (80, 81, 82, 83)
SMOKE_CMDS = {16: "open", 17: "close"}  # u85 DO0/DO1 (SPEC §8.11.3)


def build(ctx: Ctx) -> None:
    for unit in (*MACHINE_UNITS, 84, 85):
        digital_module(ctx, unit, n_di=12, n_do=6, module=0x6050, name="ADAM-6050")


def digital_module(ctx: Ctx, unit: int, n_di: int, n_do: int, module: int, name: str) -> UnitMap:
    um = ctx.unit(unit, name)
    world = ctx.world

    # --- дискретні входи (fc02, дзеркало fc01) ---
    def di_getter(i: int):
        sig = ctx.sig_at(unit, i, fc=2)
        if unit == 84 and i in (0, 1):  # DUST-1: складений стан (DI0 в роботі, DI1 аварія)
            comp = ctx.world.signals.get("equipment/DUST-1/state")
            return lambda: _dust_bit(comp.value if comp else 1, i)
        if sig is None:
            return lambda: False
        return lambda: to_bool(sig.value)

    getters = [di_getter(i) for i in range(n_di)]
    for i in range(n_di):
        um.add_bit("d", i, getters[i], None, f"DI{i}")

    # --- дискретні виходи (fc01/05) ---
    for j in range(n_do):
        addr = 16 + j
        sig = ctx.sig_at(unit, addr, fc=1)
        if sig is not None:  # командний сигнал каталогу (шлагбауми)
            um.add_bit("c", addr, lambda s=sig: to_bool(s.value), coil_cmd(ctx, unit, sig.spec),
                       sig.code)
            continue
        key = f"modbus.u{unit}.do{j}"

        def do_set(_off: int, v: int, a=addr, k=key, jj=j) -> None:
            if not ctx.write_accept:
                raise ModbusError(4)
            world.set_flag(k, int(bool(v)))
            cmd = SMOKE_CMDS.get(a) if unit == 85 else None
            if cmd and v:
                world.post("smoke", {"cmd": cmd, "unit": unit})
            ctx.command(unit, f"DO{jj} = {int(bool(v))}" + ("" if cmd else " (резерв, без ефекту)"),
                        {"channel": jj, "cmd": cmd})

        um.add_bit("c", addr, lambda k=key: bool(world.flag(k, 0)), do_set, f"DO{j}")

    # --- лічильники на DI: 40001+2k -> pdu 2k, u32 little ---
    def counter(k: int):
        sig = ctx.sig_at(unit, 2 * k, fc=3)
        scale = parse_scale(sig.spec.scale) if sig else 1.0
        okey = f"modbus.u{unit}.cnt_off{k}"

        def raw() -> int:
            return to_int(to_float(sig.value) / scale) if sig else 0

        def get() -> list[int]:
            return words_of(max(0, raw() - int(world.flag(okey, 0))), 2, little=True)

        return raw, get, okey

    for k in range(n_di):
        raw, get, okey = counter(k)
        um.add_hr(2 * k, get, 2, None, f"cnt{k}")
        base = 32 + 4 * k
        for off, label in enumerate(("start", "clear", "clear_ovf", "latch")):
            ck = f"modbus.u{unit}.cnt{k}.{label}"

            def cset(_o: int, v: int, lab=label, okey=okey, raw=raw, ck=ck) -> None:
                if lab == "clear":
                    if v:
                        world.set_flag(okey, raw())
                    return
                world.set_flag(ck, int(bool(v)))

            def cget(lab=label, ck=ck):
                return False if lab == "clear" else bool(world.flag(ck, 1 if lab == "start" else 0))

            um.add_bit("c", base + off, cget, cset, f"cnt{k}_{label}")

    # --- агрегати ---
    um.add_hr(300, lambda: [sum(1 << i for i, g in enumerate(getters) if g())], 1, None, "di_all")

    def do_all() -> list[int]:
        return [sum(1 << j for j in range(n_do) if um.read("c", 16 + j, 1)[0])]

    def do_all_set(_off: int, v: int) -> None:
        for j in range(n_do):
            um.write("c", 16 + j, [(v >> j) & 1])

    um.add_hr(302, do_all, 1, do_all_set, "do_all")
    um.add_const(210, [module, 0], "module_name")
    return um


def _dust_bit(v: object, i: int) -> bool:
    s = str(v).strip().lower()
    fault = s in ("2", "3", "fault", "error", "alarm", "true_fault")
    run = s in ("1", "1.0", "on", "running", "run", "true")
    return fault if i == 1 else run
