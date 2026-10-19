"""Вікно керування контролера ГРЩ SWB-CTRL (SPEC §8.2, R-59, C-47): unit 73, HR 200…291, u16, FC3/FC6.

Карта регістрів — ПРИПУЩЕННЯ для емулятора (A-45, Q-26): на об'єкті діє документ контролера, змінюються лише
``address`` сигналів (дані), код плагіна ``energy_ctl`` не змінюється. Таблиця — W2 SPEC §5.6 /
``contracts/c47_registers.json``.

Читання — з прапорів світу (``ctl(world, …)``) і сигналів; запис — ``set``-колбеки, які змінюють прапори (HR 100…123 W1
лишаються за ``bind_catalog``). Модель (``swb``, ``bess``, ``chp``, ``meter``, ``pv``, ``compressor``) споживає прапори
в
тіку; регістри ``qs/cmd`` і ``chp/cmd`` самоочищаються в наступному тіку.

* ``write_accept == False`` → ``ModbusError(4)``; значення поза межами → ``ModbusError(3)``;
* ``ctl_remote = 0`` (місцевий режим) — записи ігноруються, командні регістри дають ``ack = 2``;
* команди QS і КГУ додають подію світу ``command`` (``ctx.command(UNIT, "QS cmd = 2")``).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from iot_sim.models.bess import try_set_mode
from iot_sim.models.compressor import MIN_CONSUMER_BAR
from iot_sim.models.meter import SHED_NODES, bess_temp_c, ctl, remote
from iot_sim.protocols.modbus_maps import Ctx, ModbusError, to_int

UNIT = 73
CTL = "energy_control/"
U16_MAX = 65535
AIR_RAW = (500, 850)  # 5,00…8,50 бар
COS_RAW = (80, 100)  # cos φ 0,80…1,00
SHED_ADDRS = {node: 260 + i for i, node in enumerate(SHED_NODES)}


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "SWB-CTRL")
    w = ctx.world

    def guard() -> None:
        if not ctx.write_accept:
            raise ModbusError(4)

    def bounded(v: int, lo: int, hi: int) -> int:
        if not lo <= v <= hi:
            raise ModbusError(3)
        return v

    def ro(addr: int, get: Callable[[], int], name: str) -> None:
        um.add_hr(addr, lambda: [max(0, min(U16_MAX, int(get())))], 1, None, name)

    def rw(
        addr: int,
        get: Callable[[], int],
        put_: Callable[[int], None],
        lo: int,
        hi: int,
        name: str,
        on_local: Callable[[], None] | None = None,
    ) -> None:
        def setter(_off: int, v: int) -> None:
            guard()
            bounded(v, lo, hi)
            if remote(w):
                put_(v)
            elif on_local is not None:  # місцевий режим: запис приймається протоколом, але ігнорується контролером
                on_local()

        um.add_hr(addr, lambda: [max(0, min(U16_MAX, int(get())))], 1, setter, name)

    def flag_setter(name: str, scale: float = 1.0) -> Callable[[int], None]:
        return lambda v: w.set_flag(name, v * scale)

    def cmd_reg(addr: int, flag: str, ack: str, label: str, values: tuple[int, ...]) -> None:
        def setter(_off: int, v: int) -> None:
            guard()
            bounded(v, 0, max(values))
            if not v:
                return
            if remote(w):
                w.set_flag(flag, v)
            else:
                w.set_flag(ack, 2)
            ctx.command(UNIT, f"{label} = {v}")

        um.add_hr(addr, lambda: [int(ctl(w, flag))], 1, setter, flag)

    # --- службові (R) ------------------------------------------------------------------
    ro(290, lambda: ctx.num(CTL + "ctl/heartbeat"), "ctl_heartbeat")
    ro(291, lambda: int(remote(w)), "ctl_remote")

    # --- QS (200…202) ------------------------------------------------------------------
    cmd_reg(200, "qs_cmd", "qs_ack", "QS cmd", (1, 2))
    ro(201, lambda: int(ctl(w, "qs_ack")), "qs_ack")
    ro(202, lambda: to_int(ctx.num(CTL + "ats/parallel_lock", 1.0)), "ats_parallel_lock")

    # --- PFC (210, 211) ----------------------------------------------------------------
    rw(210, lambda: int(ctl(w, "pfc_mode")), flag_setter("pfc_mode"), 0, 1, "pfc_mode")

    def cos_raw() -> int:
        flag = ctl(w, "pfc_cos_target")
        if flag is None:
            flag = getattr(w.settings, "pfc_cos_target", 0.95)
        return round(float(flag) * 100)

    rw(211, cos_raw, flag_setter("pfc_cos_target", 0.01), *COS_RAW, "pfc_cos_target")

    # --- BESS (220…227) ----------------------------------------------------------------
    def set_bess_mode(v: int) -> None:
        try_set_mode(w, v)

    rw(
        220,
        lambda: int(ctl(w, "bess_mode")),
        set_bess_mode,
        0,
        3,
        "bess_mode",
        on_local=lambda: w.set_flag("bess_ack", 2),
    )
    rw(221, lambda: round(float(ctl(w, "bess_setpoint_kw"))), flag_setter("bess_setpoint_kw"), 0, 200, "bess_sp")
    rw(222, lambda: round(float(ctl(w, "bess_until_soc"))), flag_setter("bess_until_soc"), 0, 100, "bess_until")

    def set_valid(v: int) -> None:
        w.set_flag("bess_valid_s", float(v))
        w.set_flag("bess_valid_left", float(v))

    rw(223, lambda: round(float(ctl(w, "bess_valid_s"))), set_valid, 0, U16_MAX, "bess_valid_s")
    ro(224, lambda: math.ceil(float(ctl(w, "bess_valid_left"))) if int(ctl(w, "bess_mode")) else 0, "bess_remaining")
    ro(225, lambda: round(float(ctl(w, "bess_reserve_pct"))), "bess_reserve")
    ro(226, lambda: int(ctl(w, "bess_ack")), "bess_ack")
    ro(227, lambda: round(bess_temp_c(w) * 10), "bess_temp")

    # --- КГУ (230…233) -----------------------------------------------------------------
    cmd_reg(230, "chp_cmd", "chp_ack", "CHP cmd", (1, 2))
    ro(231, lambda: int(ctl(w, "chp_ack")), "chp_ack")
    ro(232, lambda: int(ctl(w, "chp_permit")), "chp_permit")
    ro(233, lambda: round(float(ctl(w, "gas_bar")) * 100), "chp_gas")

    # --- повітря (240, 241) ------------------------------------------------------------
    def set_air(v: int) -> None:
        w.set_flag("air_setpoint_bar", v / 100.0)

    rw(240, lambda: round(float(ctl(w, "air_setpoint_bar")) * 100), set_air, *AIR_RAW, "air_setpoint")
    ro(241, lambda: round(MIN_CONSUMER_BAR * 100), "air_min_consumer")

    # --- СЕС і скидання навантажень (250, 260…264, 270) --------------------------------
    rw(250, lambda: round(float(ctl(w, "pv_limit_pct"))), flag_setter("pv_limit_pct"), 0, 100, "pv_limit")

    def shed_get(node: str) -> Callable[[], int]:
        def get() -> int:
            limits = w.flags.get("shed_limit")
            return round(float(limits.get(node, 100.0))) if isinstance(limits, dict) else 100

        return get

    def shed_set(node: str) -> Callable[[int], None]:
        def put_(v: int) -> None:
            limits: Any = w.flags.setdefault("shed_limit", {})
            limits[node] = float(v)

        return put_

    for node, addr in SHED_ADDRS.items():
        rw(addr, shed_get(node), shed_set(node), 0, 100, f"shed_{node}")

    def set_shed_valid(v: int) -> None:
        w.set_flag("shed_valid_s", float(v))
        w.set_flag("shed_valid_left", float(v))

    rw(270, lambda: round(float(ctl(w, "shed_valid_s"))), set_shed_valid, 0, U16_MAX, "shed_valid_s")
