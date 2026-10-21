"""R-03, R-04, R-12, R-13, R-22: баланс, лічильники, трансформатор, АВР, острів (AC-14, AC-51, AC-60)."""

import math
from datetime import datetime
from types import SimpleNamespace

import pytest
from iot_sim.models.meter import ALL_CONSUMERS, CRITICAL, p_crit, total_load

BIG = 1e9


def hold(world, code: str, value: float) -> None:
    world.force(code, value, BIG)


def zero_loads(world) -> None:
    for c in ALL_CONSUMERS:
        hold(world, f"energy/consumers/{c}/p_now", 0.0)


def val(world, code: str) -> float:
    return world.signals[code].value


def run(world, seconds: int, dt: int = 1) -> None:
    for _ in range(seconds // dt):
        world.step(dt)


def set_blackout(world, amf: str = "hgm", **kw) -> None:
    world.set_flag(
        "blackout",
        {
            "t0": "x",
            "phase": "outage",
            "genset": True,
            "amf_master": amf,
            "restore_delay_s": 60,
            "genset_load_kw": None,
            "chp_island": False,
            **kw,
        },
    )


def ats(world):
    return world.devices["ATS-1"].model


def loads(world, crit: float | None = None, other: float = 0.0) -> None:
    zero_loads(world)
    if crit is not None:
        hold(world, "energy/consumers/COMPRESSOR/p_now", crit)
    if other:
        hold(world, "energy/consumers/CNC-3/p_now", other)  # BW-2, некритична лінія


# --- R-13 баланс -------------------------------------------------------------------------
def test_balance(world):
    zero_loads(world)
    hold(world, "energy/consumers/GANTRY-1/p_now", 300.0)  # секція 1 (BW-2)
    hold(world, "energy/consumers/SAW-1/p_now", 326.0)  # секція 2 (BW-1)
    hold(world, "infra/totals/pv_now", 468.0)
    hold(world, "infra/totals/chp_kw", 397.0)
    world.signals["infra/totals/bess_soc"].value = 76.0
    world.step(10)
    assert total_load(world) == pytest.approx(626.0)
    assert val(world, "infra/totals/bess_kw") == 200.0
    assert val(world, "infra/totals/export_kw") == pytest.approx(39.0)
    assert val(world, "infra/totals/grid_kw") == 0.0
    assert val(world, "energy/cells/Q2/p_now") == pytest.approx(326 - 865 + 200)  # < 0 → експорт
    assert val(world, "energy/cells/Q2/p_now") < 0
    assert val(world, "infra/ats/position") == 2
    assert val(world, "infra/totals/bess_soc") == pytest.approx(76 + 200 * 10 / 3600 / 387 * 100)
    world.step(10)
    assert val(world, "energy/cells/Q2/kwh_export") > 0
    assert val(world, "infra/bess/kwh_charge_total") > 0
    assert val(world, "infra/bess/state") == 2


def test_balance_deficit_and_soc_limits(world):
    world.set_flag("bess_shave_kw", 0)  # розряд на будь-який дефіцит (R-13 макета)
    zero_loads(world)
    hold(world, "energy/consumers/GANTRY-1/p_now", 300.0)
    hold(world, "energy/consumers/SAW-1/p_now", 326.0)
    hold(world, "infra/totals/pv_now", 0.0)
    hold(world, "infra/totals/chp_kw", 397.0)
    world.step(10)
    assert val(world, "infra/totals/bess_kw") == -200.0
    assert val(world, "infra/totals/grid_kw") == pytest.approx(29.0)  # макет R-13
    assert val(world, "infra/bess/kwh_discharge_total") > 0
    world.signals["infra/totals/bess_soc"].value = 10.0
    world.step(10)
    assert val(world, "infra/totals/bess_kw") == 0.0
    assert val(world, "infra/totals/grid_kw") == pytest.approx(229.0)
    hold(world, "infra/totals/pv_now", 900.0)
    world.signals["infra/totals/bess_soc"].value = 100.0
    world.step(10)
    assert val(world, "infra/totals/bess_kw") == 0.0
    assert val(world, "infra/totals/export_kw") == pytest.approx(900 + 397 - 626)
    world.fault("BESS")
    world.step(10)
    assert val(world, "infra/bess/state") == 3
    world.devices["BESS"].model.set_state({"charge_kwh": 1.0, "discharge_kwh": 2.0})
    assert world.devices["BESS"].model.get_state() == {"charge_kwh": 1.0, "discharge_kwh": 2.0}


# --- R-03 / R-13 лічильники --------------------------------------------------------------------
def test_meter_aggregation(world):
    zero_loads(world)
    hold(world, "energy/consumers/SAW-1/p_now", 12.18)
    hold(world, "energy/consumers/CNC-1/p_now", 5.0)  # BW-1 — секція 2
    hold(world, "energy/consumers/SAW-3/p_now", 7.0)  # BW-2 — секція 1
    hold(world, "energy/consumers/COMPRESSOR/p_now", 40.0)  # C1 — секція 1
    hold(world, "infra/totals/pv_now", 0.0)
    hold(world, "infra/totals/chp_kw", 0.0)
    shift0 = val(world, "energy/consumers/SAW-1/kwh_shift")
    run(world, 60, 10)
    assert val(world, "energy/lines/BW-1/p_now") == pytest.approx(17.18)
    assert val(world, "energy/lines/BW-2/p_now") == pytest.approx(7.0)
    assert val(world, "energy/lines/C1/p_now") == pytest.approx(40.0)
    q1 = val(world, "energy/cells/Q1/p_now")
    assert (
        q1
        == pytest.approx(47.0)
        == pytest.approx(
            val(world, "energy/lines/BW-2/p_now")
            + val(world, "energy/lines/BW-3/p_now")
            + val(world, "energy/lines/C1/p_now")
        )
    )
    q2_expected = (
        val(world, "energy/lines/BW-1/p_now")
        + val(world, "energy/lines/BW-4/p_now")
        + val(world, "energy/lines/C2/p_now")
        + val(world, "infra/totals/bess_kw")
    )
    assert val(world, "energy/cells/Q2/p_now") == pytest.approx(q2_expected)
    # R-03: P=12,18 кВт, dt=60 с → +203 Вт·год
    assert val(world, "energy/consumers/SAW-1/kwh_shift") - shift0 == pytest.approx(0.203, abs=0.002)
    i_now = val(world, "energy/lines/BW-1/i_now")
    s_kva = 17.18 / val(world, "energy/lines/BW-1/cos_phi")
    assert i_now == pytest.approx(s_kva * 1000 / (math.sqrt(3) * 400), rel=0.01)
    for ph in "abc":
        assert val(world, f"energy/lines/BW-1/i_{ph}") == pytest.approx(i_now, rel=0.04)
    assert val(world, "energy/lines/BW-1/kwh_total") > 0
    assert val(world, "energy/lines/BW-1/state") == 1
    assert val(world, "energy/cells/Q1/q_kvar") > 0


def test_shift_counter_resets_at_shift_start(world):
    zero_loads(world)
    hold(world, "energy/consumers/SAW-1/p_now", 36.0)
    world.clock.set(datetime(2026, 10, 12, 6, 59, 30))
    run(world, 20, 10)
    before = val(world, "energy/consumers/SAW-1/kwh_shift")
    run(world, 30, 10)  # перетин 07:00
    after = val(world, "energy/consumers/SAW-1/kwh_shift")
    assert after < before
    assert after == pytest.approx(36 * 10 / 3600 * 2, abs=0.05)


def test_meter_fault_and_state_roundtrip(world):
    meter = world.devices["QF-1"].model
    world.fault("QF-1", "generic")
    world.step(10)
    assert val(world, "energy/lines/BW-1/state") == 2
    assert val(world, "energy/lines/BW-1/p_now") == 0.0
    world.fault("Q2", "generic")
    world.step(10)
    assert val(world, "energy/cells/Q2/p_now") == 0.0
    world.clear("QF-1")
    world.step(10)
    state = meter.get_state()
    meter.set_state(state)
    assert meter.get_state() == state


def test_blackout_zeroes_inputs_and_noncritical(world):
    loads(world, crit=100.0, other=50.0)
    set_blackout(world)
    world.step(10)
    assert val(world, "energy/cells/Q1/p_now") == 0.0
    assert val(world, "energy/cells/Q2/p_now") == 0.0
    assert val(world, "energy/lines/BW-2/p_now") == 0.0  # некритична лінія
    assert val(world, "energy/lines/C1/p_now") == pytest.approx(100.0)  # COMPRESSOR критичний
    assert val(world, "energy/transformers/T1/p_kw") == 0.0
    assert val(world, "infra/totals/grid_kw") == 0.0 and val(world, "infra/totals/export_kw") == 0.0
    assert val(world, "infra/ats/src1_state") == 0 and val(world, "infra/ats/src1_ok") == 0
    assert "COMPRESSOR" in CRITICAL and p_crit(world) == pytest.approx(100.0)


# --- R-04 трансформатор -----------------------------------------------------------------------------
def test_transformer_temp(world):
    t1 = world.devices["T1"].model
    t1.update(345 * 0.97)
    assert val(world, "energy/transformers/T1/s_kva") == pytest.approx(345.0)
    assert val(world, "energy/transformers/T1/temp_c") == pytest.approx(38 + 60 * 345 / 1000, abs=0.31)
    assert val(world, "energy/transformers/T1/i_a") == pytest.approx(498.0, abs=0.5)  # макет 498
    assert val(world, "energy/transformers/T1/cos_phi") == 0.97
    zero_loads(world)
    hold(world, "infra/totals/pv_now", 0.0)  # T2 = ввід Q2: без СЕС/КГУ/BESS це рівно навантаження секції
    hold(world, "infra/totals/chp_kw", 0.0)
    world.set_flag("bess_auto_idle", True)
    hold(world, "energy/consumers/SAW-1/p_now", 970.0)  # секція 2 → T2
    world.step(10)
    assert val(world, "energy/transformers/T2/p_kw") == pytest.approx(970.0)
    assert val(world, "energy/transformers/T2/p_kw") == pytest.approx(val(world, "energy/cells/Q2/p_now"))
    assert val(world, "energy/transformers/T2/temp_c") == pytest.approx(38 + 60 * 1000 / 1000, abs=0.31)
    t1.update(2400 * 0.97)
    assert world.signals["energy/transformers/T1/temp_c"].evaluate() == "alarm"  # > 140 °C


# --- R-22 АВР, регістри Annexe III ---------------------------------------------------------------------
@pytest.mark.parametrize(("amf", "mode"), [("hgm", 32), ("ats", 16)])
def test_ats_annexe3_registers(world, amf, mode):
    world.settings = SimpleNamespace(genset_amf_master=amf)
    world.step(10)
    assert val(world, "infra/ats/mode") == mode
    assert val(world, "infra/ats/position") == 2
    assert val(world, "infra/ats/gen_start") == 0
    assert val(world, "infra/ats/src1_state") == 2
    assert val(world, "infra/ats/src2_state") == 0
    assert val(world, "infra/ats/src1_ok") == 1 and val(world, "infra/ats/src2_ok") == 0
    assert val(world, "infra/ats/fail_start") == 0


def _hgm_island(world, *, crit: float, chp_island: bool = False, genset_load_kw=None):
    loads(world, crit=crit)
    a = ats(world)
    a.set_relay_state({"gen_ok": False, "breaker": "mains", "state": "standby"})
    set_blackout(world, "hgm", chp_island=chp_island, genset_load_kw=genset_load_kw)
    world.step(10)
    deficit = max(0.0, crit - val(world, "infra/totals/chp_kw"))  # КГУ в острові покриває своє, BESS — лише решту
    assert val(world, "infra/totals/bess_kw") == -min(200.0, deficit)  # до переключення (X-67)
    assert val(world, "infra/ats/position") == 2 and val(world, "infra/ats/src1_state") == 0
    a.set_relay_state({"gen_ok": True, "breaker": "gen", "state": "running"})
    world.step(10)
    assert val(world, "infra/ats/position") == 1  # ODT: мертва зона
    world.step(10)
    assert val(world, "infra/ats/position") == 3
    assert val(world, "infra/totals/bess_kw") == 0.0  # після переключення
    assert val(world, "infra/ats/src2_state") == 2
    return a


def _loads_sent(a):
    return [p["kw"] for e, p in a.relay_log if e == "load"]


@pytest.mark.parametrize(
    ("crit", "chp_island", "override", "expected"),
    [
        (348.0, False, None, 348.0),  # AC-60: острів без КГУ
        (348.0, True, None, 0.0),  # КГУ в острові покриває критичне навантаження вдень
        (600.0, False, None, 558.0),  # обмеження SIM_GENSET_KW_MAX
        (348.0, False, 200.0, 200.0),  # явний genset_load_kw
    ],
)
def test_island_genset_load(world, crit, chp_island, override, expected):
    world.set_flag("chp_run", True)  # КГУ запущено командою (штатно — резерв)
    a = _hgm_island(world, crit=crit, chp_island=chp_island, genset_load_kw=override)
    assert _loads_sent(a)[-1] == pytest.approx(expected, abs=1.0)
    assert [p for e, p in a.relay_log if e == "mains"] == [{"available": False}]  # рівно раз
    assert a.counter == 18
    assert a.genset_kw == pytest.approx(expected, abs=1.0)
    n = len(_loads_sent(a))
    world.step(10)
    assert len(_loads_sent(a)) == n  # без зміни ≥ 1 кВт нічого не шле


def test_island_chp_variants(world):
    world.set_flag("chp_run", True)
    loads(world, crit=348.0)
    set_blackout(world, chp_island=False)
    world.step(10)
    assert val(world, "infra/chp/state") == 4
    assert val(world, "infra/totals/chp_kw") == 0.0 and val(world, "infra/chp/heat_kw") == 0.0
    run(world, 70, 10)
    assert val(world, "infra/chp/state") == 0
    world.clear_flag("blackout")
    world.step(10)
    assert val(world, "infra/chp/state") == 1
    run(world, 70, 10)
    assert val(world, "infra/chp/state") == 2
    assert val(world, "infra/totals/chp_kw") == pytest.approx(400, abs=4.1)
    assert val(world, "infra/chp/heat_kw") == 497 and val(world, "infra/chp/gas_m3h") == 109
    set_blackout(world, chp_island=True)
    world.step(10)
    assert val(world, "infra/chp/state") == 2
    assert val(world, "infra/totals/chp_kw") == pytest.approx(348.0)  # min(400, P_crit − pv)


def test_chp_night_cold_hours_fault(world):
    world.set_flag("chp_run", True)
    world.clock.set(datetime(2026, 10, 12, 23, 0))
    world.step(10)
    assert val(world, "infra/chp/heat_kw") == 856 and val(world, "infra/chp/gas_m3h") == 199
    assert val(world, "infra/totals/chp_kw") == pytest.approx(800, abs=4.1)
    world.clock.set(datetime(2026, 10, 12, 12, 0))
    hold(world, "ventilation/totals/outdoor_c", -5.0)
    world.step(10)
    assert val(world, "infra/chp/heat_kw") == 856  # outdoor < 0 → 100 %
    hours = val(world, "infra/chp/hours")
    world.step(10)
    assert val(world, "infra/chp/hours") > hours
    assert val(world, "infra/chp/kwh_total") > 0
    world.fault("CHP")
    world.step(10)
    assert val(world, "infra/chp/state") == 3 and val(world, "infra/totals/chp_kw") == 0.0
    world.clear("CHP")
    world.step(10)
    assert val(world, "infra/chp/state") == 2
    chp = world.devices["CHP"].model
    state = chp.get_state()
    chp.set_state(state)
    assert chp.get_state() == state


def test_ats_variant_b_fallback_full_cycle(world):
    """``ats`` без ретранслятора: 1FT → пуск → запасний режим (15 с) → II → 1RT → I → 2CT → стоп."""
    loads(world, crit=348.0)
    set_blackout(world, "ats")
    run(world, 2)
    assert val(world, "infra/ats/gen_start") == 0
    run(world, 3)  # 1FT = 3 с
    assert val(world, "infra/ats/gen_start") == 1
    assert ("remote_start", {"on": True}) in ats(world).relay_log
    assert not any(e == "mains" for e, _ in ats(world).relay_log)  # варіант B не кличе API-F-02
    run(world, 20)
    assert val(world, "infra/ats/position") == 3 and val(world, "infra/ats/src2_state") == 2
    assert _loads_sent(ats(world))[-1] == pytest.approx(348.0, abs=1.0)
    world.clear_flag("blackout")
    run(world, 1)
    assert val(world, "infra/ats/src1_state") == 1  # стабілізація 2 с
    run(world, 4)
    assert val(world, "infra/ats/src1_state") == 2
    assert val(world, "infra/ats/position") == 3  # 1RT ще не минув
    run(world, 185)
    assert val(world, "infra/ats/position") == 2
    assert _loads_sent(ats(world))[-1] == 0
    assert val(world, "infra/ats/gen_start") == 1
    run(world, 185)
    assert val(world, "infra/ats/gen_start") == 0 and val(world, "infra/ats/src2_state") == 0
    assert ("remote_start", {"on": False}) in ats(world).relay_log


def test_ats_variant_b_relay_fail_start_then_ok(world):
    loads(world, crit=100.0)
    a = ats(world)
    a.set_relay_state({"gen_ok": False, "breaker": "mains", "state": "standby"})
    set_blackout(world, "ats")
    run(world, 40)
    assert val(world, "infra/ats/fail_start") == 1  # 2ST = 30 с
    assert val(world, "infra/ats/position") == 2
    assert any(e.message.startswith("АВР: генератор не запустився") for e in world.events.since(0)[0])
    a.set_relay_state({"gen_ok": True, "breaker": "mains", "state": "running"})
    run(world, 4)
    assert val(world, "infra/ats/src2_state") == 2 and val(world, "infra/ats/position") == 2
    run(world, 12)  # 2AT 5 с + ODT 3 с
    assert val(world, "infra/ats/position") == 3


def test_ats_variant_a_fallback_and_relay_return(world):
    loads(world, crit=100.0)
    set_blackout(world, "hgm")
    run(world, 12)
    assert val(world, "infra/ats/position") == 2
    run(world, 12)  # запасний режим: 15 с + ODT
    assert val(world, "infra/ats/position") == 3 and val(world, "infra/ats/src2_state") == 2
    world.clear_flag("blackout")
    run(world, 5)
    assert ("mains", {"available": True, "u_v": 400, "f_hz": 50.0}) in ats(world).relay_log
    run(world, 70)  # 60 с запасного повернення
    assert val(world, "infra/ats/position") == 2 and val(world, "infra/ats/src2_state") == 0
    # з ретранслятором: повернення за breaker == "mains"
    set_blackout(world, "hgm")
    a = ats(world)
    a.set_relay_state({"gen_ok": True, "breaker": "gen", "state": "running"})
    run(world, 15)
    assert val(world, "infra/ats/position") == 3
    world.clear_flag("blackout")
    run(world, 5)
    assert val(world, "infra/ats/position") == 3
    a.set_relay_state({"gen_ok": True, "breaker": "mains", "state": "cooling"})
    run(world, 10)
    assert val(world, "infra/ats/position") == 2
    a.set_relay_state({"gen_ok": False, "breaker": "mains", "state": "standby"})
    run(world, 2)
    assert val(world, "infra/ats/src2_state") == 0


def test_genset_test_on_load(world):
    loads(world, crit=200.0)
    hold(world, "infra/totals/pv_now", 250.0)  # СЕС (250 кВт) покриває критичні 200 кВт
    a = ats(world)
    world.set_flag("genset_test", {"on_load": False, "phase": "running"})
    run(world, 20)
    assert ("remote_start", {"on": True}) in a.relay_log
    assert val(world, "infra/ats/position") == 2 and val(world, "infra/ats/src2_state") == 2
    world.clear_flag("genset_test")
    run(world, 3)
    assert ("remote_start", {"on": False}) in a.relay_log
    assert val(world, "infra/ats/src2_state") == 0
    world.set_flag("genset_test", {"on_load": True, "phase": "running"})
    run(world, 25)
    assert val(world, "infra/ats/position") == 3
    assert _loads_sent(a)[-1] == 0.0  # генерація (СЕС) покриває критичні 200 кВт
    world.clear_flag("genset_test")
    run(world, 12)
    assert val(world, "infra/ats/position") == 2
    assert _loads_sent(a)[-1] == 0
    # з ретранслятором
    a.set_relay_state({"gen_ok": True, "breaker": "mains", "state": "running"})
    world.set_flag("genset_test", {"on_load": True, "phase": "running"})
    run(world, 6)
    assert val(world, "infra/ats/position") == 3
    world.clear_flag("genset_test")
    run(world, 6)
    assert val(world, "infra/ats/position") == 2


def test_blackout_without_genset_and_ats_state(world):
    loads(world, crit=100.0)
    set_blackout(world, "hgm", genset=False)
    run(world, 30)
    assert val(world, "infra/ats/position") == 2
    assert not a_relay_calls(world)
    a = ats(world)
    a.set_state({"pos": 3, "src1": 0, "src2": 2, "counter": 20, "gen_start": 1, "fail": 1})
    assert a.get_state()["counter"] == 20 and a.pos == 3
    calls = []
    a.relay_cb = lambda ep, payload: calls.append(ep)
    a._relay("load", {"kw": 1})
    assert calls == ["load"]


def a_relay_calls(world):
    return [c for c in ats(world).relay_log if c[0] != "load"]


def test_reset_all_energies_zeroes_counters(world):
    """Modbus 2020 (Reset All Energies): накопичені кВт·год лічильника (споживачі лінії і власний) обнуляються."""
    meters = [d for d in world.devices.values() if d.driver == "meter" and d.model.consumers]
    m = meters[0].model
    world.advance(60)
    c = m.consumers[0]
    m.e_wh[c] = 500_000.0
    world.advance(1)
    assert world.signals[f"energy/consumers/{c}/kwh_total"].value > 100
    world.post("meter", {"unit": meters[0].unit_id, "cmd": "reset_energy"})
    world.advance(1)
    assert world.signals[f"energy/consumers/{c}/kwh_total"].value < 0.1
    assert not world.inbox["meter"]


# --- КГУ: штатно резерв (R-12), запуск командою ----------------------------------------------
def test_chp_reserve_by_default(world):
    assert val(world, "infra/chp/state") == 2  # номінал каталогу до першого тіку
    run(world, 120, 10)
    assert val(world, "infra/chp/state") == 0  # без охолодження: одразу резерв
    for code in ("infra/totals/chp_kw", "infra/chp/heat_kw", "infra/chp/gas_m3h"):
        assert val(world, code) == 0.0
    hours = val(world, "infra/chp/hours")
    run(world, 60, 10)
    assert val(world, "infra/chp/hours") == hours


def test_chp_start_and_stop_commands(world):
    run(world, 10, 10)
    assert val(world, "infra/chp/state") == 0
    world.set_flag("chp_run", True)
    world.step(10)
    assert val(world, "infra/chp/state") == 1 and val(world, "infra/totals/chp_kw") == 0.0
    run(world, 70, 10)
    assert val(world, "infra/chp/state") == 2
    assert val(world, "infra/totals/chp_kw") > 300
    world.set_flag("chp_run", False)
    world.step(10)
    assert val(world, "infra/chp/state") == 4 and val(world, "infra/totals/chp_kw") == 0.0
    run(world, 70, 10)
    assert val(world, "infra/chp/state") == 0


@pytest.mark.parametrize("weather", [False, True])
def test_normal_working_day_imports_from_grid(world, weather):
    """Робоча доба в штатному стані (КГУ в резерві, СЕС за жовтневим профілем): Q1 + Q2 > 0 щогодини,
    а Q2 може бути від'ємним (невеликий експорт через T2) лише вдень, коли СЕС перекриває секцію 2."""
    world.settings = SimpleNamespace(pv_weather=weather)  # False — ясне небо (жовтневий профіль), True — з хмарами
    world.clock.set(datetime(2026, 10, 16, 0, 5))  # п'ятниця
    hold(world, "infra/totals/bess_soc", 10.0)  # BESS розряджений: дефіцит покриває мережа (R-13)
    negative_q2 = []
    for hour in range(24):
        world.clock.set(datetime(2026, 10, 16, hour, 5))
        run(world, 30, 10)
        q1, q2 = val(world, "energy/cells/Q1/p_now"), val(world, "energy/cells/Q2/p_now")
        assert q1 + q2 > 0, (hour, q1, q2)  # імпорт додатний (конвенція: імпорт +)
        assert val(world, "infra/totals/export_kw") == 0.0
        assert val(world, "infra/totals/chp_kw") == 0.0
        if q2 < 0:
            negative_q2.append(hour)
        assert val(world, "infra/totals/grid_kw") == pytest.approx(q1 + q2, abs=1.0)
    assert all(9 <= h <= 17 for h in negative_q2), negative_q2
    assert negative_q2 or weather  # ясного дня СЕС таки перекриває секцію 2


def test_bess_peak_shaving_only_above_threshold(world):
    """Штатно BESS в очікуванні: розряд лише на частину дефіциту понад ``bess_shave_kw`` (600 кВт), не більш як 200."""
    zero_loads(world)
    hold(world, "infra/totals/pv_now", 0.0)
    hold(world, "infra/totals/chp_kw", 0.0)
    hold(world, "energy/consumers/GANTRY-1/p_now", 300.0)  # секція 1
    for load, bess, grid in ((326.0, 0.0, 326.0), (626.0, -26.0, 600.0), (826.0, -200.0, 626.0)):
        hold(world, "energy/consumers/SAW-1/p_now", load - 300.0 if load > 326 else 26.0)
        world.step(10)
        assert val(world, "infra/totals/bess_kw") == pytest.approx(bess)
        assert val(world, "infra/totals/grid_kw") == pytest.approx(grid)
    hold(world, "energy/consumers/SAW-1/p_now", 26.0)
    world.step(10)
    assert val(world, "infra/bess/state") == 1  # очікування
