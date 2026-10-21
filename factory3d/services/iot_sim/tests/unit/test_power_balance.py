"""Баланс потужності й енергії: КГУ (модель ``chp``) — єдине джерело електричної потужності КГУ для мережі ГРЩ.

``grid_import − export = load − PV − CHP − genset ± BESS`` на кожному тіку; головний лічильник (Q1 + Q2) = Σ фідерів −
генерація + заряд BESS; енергія лічильників = ∫P dt; паливний баланс КГУ (η_ел, η_тепл, контури HT/LT).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from iot_sim.models.chp import LHV, P_NOM_KW
from iot_sim.models.meter import ALL_CONSUMERS, LINE_CONSUMERS

pytestmark = pytest.mark.unit

BIG = 3600.0 * 24
LINES = tuple(LINE_CONSUMERS)


def val(world, code: str) -> float:
    return float(world.signals[code].value)


def hold(world, code: str, value: float) -> None:
    world.force(code, value, BIG)


def chp(world):
    return world.devices["CHP"].model


def setup_loads(world, s1: float, s2: float, pv: float = 0.0, bess_idle: bool = True) -> None:
    """Навантаження: ``GANTRY-1`` у секції 1 (Q1), ``SAW-1`` у секції 2 (Q2); СЕС — задана; BESS у простої."""
    for c in ALL_CONSUMERS:
        hold(world, f"energy/consumers/{c}/p_now", 0.0)
    hold(world, "energy/consumers/GANTRY-1/p_now", s1)
    hold(world, "energy/consumers/SAW-1/p_now", s2)
    hold(world, "infra/totals/pv_now", pv)
    world.set_flag("bess_auto_idle", bess_idle)


def start_chp(world, sp_pct: int | None = None, secs: int = 120) -> float:
    """Пуск КГУ командою (``chp_run``); ``sp_pct`` — ручний режим з уставкою. Повертає P ел. після виходу на режим."""
    if sp_pct is not None:
        chp(world).s.update(mode=3, sp_pct=sp_pct)
    world.set_flag("chp_run", True)
    for _ in range(secs):
        world.step(1)
    assert val(world, "infra/chp/state") == 2
    return val(world, "infra/totals/chp_kw")


def import_export(world) -> tuple[float, float]:
    return val(world, "infra/totals/grid_kw"), val(world, "infra/totals/export_kw")


# --- імпорт з мережі: КГУ вимкнено / працює / надлишок ------
def test_chp_off_grid_import_is_load_minus_pv(world):
    setup_loads(world, 300.0, 326.0, pv=100.0)
    world.step(10)
    assert val(world, "infra/totals/chp_kw") == 0.0
    grid, export = import_export(world)
    assert grid == pytest.approx(626.0 - 100.0) and export == 0.0
    assert val(world, "energy/cells/Q1/p_now") + val(world, "energy/cells/Q2/p_now") == pytest.approx(grid)


def test_chp_running_cuts_grid_import_by_its_power(world):
    setup_loads(world, 300.0, 326.0, pv=100.0)
    world.step(10)
    grid_off, _ = import_export(world)
    p = start_chp(world, sp_pct=50)
    assert p == pytest.approx(0.5 * P_NOM_KW, abs=5.0)
    grid_on, export = import_export(world)
    assert export == 0.0
    assert grid_off - grid_on == pytest.approx(p)  # імпорт впав рівно на потужність КГУ
    assert grid_on == pytest.approx(626.0 - 100.0 - p)
    q1, q2 = val(world, "energy/cells/Q1/p_now"), val(world, "energy/cells/Q2/p_now")
    assert q1 == pytest.approx(300.0) and q2 == pytest.approx(326.0 - 100.0 - p)  # СЕС і КГУ приєднані до секції 2
    assert q1 + q2 == pytest.approx(grid_on)
    # ... і зупинка повертає імпорт
    world.set_flag("chp_run", False)
    for _ in range(80):
        world.step(1)
    assert val(world, "infra/totals/chp_kw") == 0.0
    assert import_export(world)[0] == pytest.approx(grid_off)


def test_chp_surplus_is_exported_import_never_negative(world):
    setup_loads(world, 0.0, 200.0, pv=100.0)
    p = start_chp(world, sp_pct=75)
    surplus = p + 100.0 - 200.0
    grid, export = import_export(world)
    assert grid == 0.0 and export == pytest.approx(surplus) and surplus > 400.0
    assert val(world, "energy/cells/Q1/p_now") + val(world, "energy/cells/Q2/p_now") == pytest.approx(-export)
    for _ in range(30):
        world.step(1)
        assert val(world, "infra/totals/grid_kw") >= 0.0 and val(world, "infra/totals/export_kw") >= 0.0
    assert val(world, "energy/cells/Q2/kwh_export") > 0.0  # лічильник віддачі росте


def test_surplus_charges_bess_first_when_auto(world):
    """Штатний BESS заряджається від надлишку до 200 кВт; решта — експорт (існуюча семантика R-13)."""
    setup_loads(world, 0.0, 200.0, pv=100.0, bess_idle=False)
    p = start_chp(world, sp_pct=75)
    bess = val(world, "infra/totals/bess_kw")
    grid, export = import_export(world)
    assert bess == pytest.approx(200.0)
    assert grid == 0.0 and export == pytest.approx(p + 100.0 - 200.0 - 200.0)


# --- тотожність балансу на кожному тіку: СЕС + КГУ + навантаження ------
def test_identity_pv_chp_load_over_one_hour(world):
    """15:40 22.10: СЕС (астрономічна модель), КГУ (старий профіль режиму 4), навантаження верстатів — 1 год із кроком
    10 с. На кожному тіку ``grid − export = Σ фідерів − PV − CHP + BESS``, ``Q1 + Q2`` те саме, ``T1 + T2`` =
    ``Q1 + Q2``; за годину енергія лічильників = ∫P dt."""
    world.clock.set(datetime(2026, 10, 22, 15, 40))
    world.set_flag("chp_run", True)
    for _ in range(12):
        world.step(10)  # КГУ виходить на режим
    assert val(world, "infra/chp/state") == 2

    pv_codes = [c for c in world.signals if c.startswith("infra/pv/PV-INV-") and c.endswith("/kwh_total")]
    q_codes = [f"energy/cells/Q{i}/{k}" for i in (1, 2) for k in ("kwh_total", "kwh_export")]

    def counters() -> dict[str, float]:
        out = {c: val(world, c) for c in q_codes + pv_codes}
        out.update({f"line:{ln}": val(world, f"energy/lines/{ln}/kwh_total") for ln in LINES})
        out["chp"] = val(world, "infra/chp/kwh_total")
        out["bess+"] = val(world, "infra/bess/kwh_charge_total")
        out["bess-"] = val(world, "infra/bess/kwh_discharge_total")
        return out

    c0 = counters()
    dt, n = 10, 360
    acc = dict.fromkeys(("load", "pv", "chp", "bess", "q"), 0.0)
    seen = {"chp_on": 0, "import": 0, "export": 0}
    for _ in range(n):
        world.step(dt)
        load = sum(val(world, f"energy/lines/{ln}/p_now") for ln in LINES)  # Σ фідерів
        pv, gen, bess = (
            val(world, "infra/totals/pv_now"),
            val(world, "infra/totals/chp_kw"),
            val(world, "infra/totals/bess_kw"),
        )
        grid, export = import_export(world)
        q = val(world, "energy/cells/Q1/p_now") + val(world, "energy/cells/Q2/p_now")
        net = load - pv - gen + bess
        assert grid - export == pytest.approx(net, abs=1e-6)
        assert q == pytest.approx(net, abs=1e-6)
        assert grid >= 0.0 and export >= 0.0 and (grid == 0.0 or export == 0.0)
        t = val(world, "energy/transformers/T1/p_kw") + val(world, "energy/transformers/T2/p_kw")
        assert t == pytest.approx(q, abs=1e-6)
        for k, v in zip(acc, (load, pv, gen, bess, q), strict=True):
            acc[k] += v * dt / 3600.0
        seen["chp_on"] += gen > 300.0
        seen["import"] += grid > 0.0
        seen["export"] += export > 0.0
    assert seen["chp_on"] == n and (seen["import"] or seen["export"])  # КГУ працює всю годину

    c1 = counters()
    d = {k: c1[k] - c0[k] for k in c0}
    tol = 0.02  # кВт·год (округлення лічильників 4–6 знаків)
    assert sum(d[f"line:{ln}"] for ln in LINES) == pytest.approx(acc["load"], abs=tol)
    assert sum(d[c] for c in pv_codes) == pytest.approx(acc["pv"], abs=tol)
    assert d["chp"] == pytest.approx(acc["chp"], abs=tol)
    assert d["bess+"] - d["bess-"] == pytest.approx(acc["bess"], abs=tol)
    main = sum(d[f"energy/cells/Q{i}/kwh_total"] - d[f"energy/cells/Q{i}/kwh_export"] for i in (1, 2))
    assert main == pytest.approx(acc["q"], abs=tol)  # головний лічильник (імпорт − віддача)
    assert main == pytest.approx(acc["load"] - acc["pv"] - acc["chp"] + acc["bess"], abs=3 * tol)


def test_island_genset_covers_load_minus_chp_pv_bess(world):
    """Острів: ``load(критичне) = genset + CHP + PV − BESS`` (мережі немає: імпорт = експорт = 0) до і після
    переключення ATyS; надлишку немає: BESS віддає лише те, чого не покриває КГУ."""
    from types import SimpleNamespace

    for c in ALL_CONSUMERS:
        hold(world, f"energy/consumers/{c}/p_now", 0.0)
    hold(world, "energy/consumers/COMPRESSOR/p_now", 500.0)  # критичний споживач
    world.settings = SimpleNamespace(genset_amf_master="hgm", genset_kw_max=558.0)
    world.set_flag("chp_run", True)
    chp(world).s.update(mode=3, sp_pct=50)
    for _ in range(100):
        world.step(1)
    assert val(world, "infra/chp/state") == 2
    ats = world.devices["ATS-1"].model
    ats.set_relay_state({"gen_ok": False, "breaker": "mains", "state": "standby"})
    world.set_flag(
        "blackout",
        {
            "t0": "x",
            "phase": "outage",
            "genset": True,
            "amf_master": "hgm",
            "restore_delay_s": 600,
            "genset_load_kw": None,
            "chp_island": True,
        },
    )
    world.step(10)

    def check(stage: str) -> None:
        p_chp, pv, bess = (
            val(world, "infra/totals/chp_kw"),
            val(world, "infra/totals/pv_now"),
            val(world, "infra/totals/bess_kw"),
        )
        assert import_export(world) == (0.0, 0.0), stage
        assert 0.0 < p_chp <= 500.0, stage
        assert ats.genset_kw + p_chp + pv - bess == pytest.approx(500.0, abs=1.0), stage

    check("до переключення")  # BESS закриває дефіцит після КГУ (100 кВт), генератор ще не потрібен
    assert val(world, "infra/totals/bess_kw") == pytest.approx(-(500.0 - val(world, "infra/totals/chp_kw")))
    ats.set_relay_state({"gen_ok": True, "breaker": "gen", "state": "running"})
    world.step(10)
    world.step(10)
    assert val(world, "infra/ats/position") == 3
    check("після переключення")  # BESS 0, генератор бере решту
    assert ats.genset_kw == pytest.approx(500.0 - val(world, "infra/totals/chp_kw"), abs=1.0)


# --- паливний баланс КГУ ------
@pytest.mark.parametrize("sp_pct", [50, 75, 100])
def test_chp_fuel_balance_and_heat_circuits(world, sp_pct):
    """Паливо = 9,5 кВт·год/м³ · витрата газу: η_ел 38…44 %, η_тепл 43…50 %, разом 80…92 %; решта (випускний
    тракт, випромінювання) 3…12 %; контури HT/LT сходяться з тепловою потужністю (Q = 1,163·V·ΔT)."""
    setup_loads(world, 300.0, 326.0)
    start_chp(world, sp_pct=sp_pct, secs=240)
    el, heat, gas = val(world, "infra/totals/chp_kw"), val(world, "infra/chp/heat_kw"), val(world, "infra/chp/gas_m3h")
    fuel = gas * LHV
    assert el == pytest.approx(P_NOM_KW * sp_pct / 100.0, abs=5.0)
    assert 0.38 <= el / fuel <= 0.44 and 0.43 <= heat / fuel <= 0.50 and 0.80 <= (el + heat) / fuel <= 0.92
    r = chp(world).regs
    lt = r["chp/lt/q_kw"]
    assert el + heat + lt <= fuel and 0.03 <= (fuel - el - heat - lt) / fuel <= 0.12
    assert r["chp/gen/p_kw"] == pytest.approx(el) and r["chp/ht/q_total"] == pytest.approx(heat)
    assert r["chp/gas/flow"] == pytest.approx(gas)
    assert r["chp/ht/q_phe"] + r["chp/ht/q_exh"] == pytest.approx(heat, abs=1.0)
    assert r["chp/ht/q_boiler"] + r["chp/ht/q_cooler"] == pytest.approx(heat, abs=1.0)
    dt_ht = r["chp/ht/t_sup"] - r["chp/ht/t_ret"]
    assert 1.163 * r["chp/ht/flow"] * dt_ht == pytest.approx(heat, rel=0.01)
    dt_lt = r["chp/lt/t_out"] - r["chp/lt/t_in"]
    assert 1.163 * r["chp/lt/flow"] * dt_lt == pytest.approx(lt, rel=0.01)
    assert r["chp/eng/shaft_kw"] == pytest.approx(el / 0.96)  # вал = ел. / η генератора
    if sp_pct == 100:
        assert gas == pytest.approx(199.0, abs=2.0)  # паспорт: 199 м³/год при 100 % (td_factory3d)


def test_chp_fuel_energy_counters(world):
    """Лічильники КГУ: кВт·год ел. = ∫P dt, газ (м³) і тепло (ГДж) інтегруються тими ж значеннями, що публікуються."""
    setup_loads(world, 300.0, 326.0)
    start_chp(world, sp_pct=75, secs=120)
    s = chp(world).s
    e0, g0, q0, k0 = s["e_kwh"], s["gas_total"], s["heat_tot"], val(world, "infra/chp/kwh_total")
    acc_e = acc_g = acc_q = 0.0
    for _ in range(600):
        world.step(1)
        h = 1.0 / 3600.0
        acc_e += val(world, "infra/totals/chp_kw") * h
        acc_g += val(world, "infra/chp/gas_m3h") * h
        acc_q += val(world, "infra/chp/heat_kw") * h / 1163.0
    assert s["e_kwh"] - e0 == pytest.approx(acc_e, rel=1e-6)
    assert val(world, "infra/chp/kwh_total") - k0 == pytest.approx(acc_e, abs=1e-3)
    assert s["gas_total"] - g0 == pytest.approx(acc_g, rel=1e-6)
    assert s["heat_tot"] - q0 == pytest.approx(acc_q, rel=1e-6)
