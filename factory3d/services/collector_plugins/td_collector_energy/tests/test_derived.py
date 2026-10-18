"""D-47: похідні входи `derived` плагін рахує сам із LiveCache (E-03); fail-closed за відсутнім/несвіжим термом."""

import logging
from datetime import timedelta

import pytest
from collector.core.live import LiveCache
from collector.core.types import Reading
from helpers import (
    INTENT_SIGNAL,
    T0,
    base_raw,
    derived_block,
    feed_raw_plant,
    intent,
    make_plugin,
    raw_plant,
    run_intent,
    wire_device,
)

from td_collector_energy import config as cfgmod
from td_collector_energy import derived as drv
from td_collector_energy.inputs import Inputs
from td_collector_energy.interlocks import Ctx

CODES = {k: k for k in derived_block()}


def cfg_with(derived=None):
    raw = base_raw()
    raw["derived"] = derived if derived is not None else derived_block()
    return cfgmod.parse(raw).config


def live_of(**vals):
    live = LiveCache()
    for code, val in {**raw_plant(), **vals}.items():
        if val is None:
            continue
        v, t = (None, val) if isinstance(val, str) else (val, None)
        live.update([Reading(code, T0, value=v, text=t)])
    return live


def inp(live=None, now=T0, cfg=None):
    return Inputs(cfg or cfg_with(), live or live_of(), now)


def test_sums_of_lines_and_sections():
    i = inp()
    assert i.v("p_total") == 350.0 and i.v("s1_p") == 200.0 and i.v("s2_p") == 150.0
    assert i.reading("p_total").ts == T0 and i.age("p_total") == 0.0


def test_src1_ok_is_ge_over_src1_state_numbers_and_text():
    for state, want in ((0, 0.0), (1, 1.0), (2, 1.0), ("under", 0.0), ("present", 1.0), ("available", 1.0)):
        assert inp(live_of(**{"infra/ats/src1_state": state})).v("src1_ok") == want, state


def test_grid_and_export_from_q1_q2_clamped():
    assert (inp().v("grid_kw"), inp().v("export_kw")) == (200.0, 0.0)  # 120 + 80
    i = inp(live_of(**{"energy/cells/Q1/p_now": -200.0, "energy/cells/Q2/p_now": 50.0}))
    assert (i.v("grid_kw"), i.v("export_kw")) == (0.0, 150.0)  # clamp_min 0, експорт = −(Q1+Q2)


@pytest.mark.parametrize("position", ["pos_II", 3])
def test_island_zeroes_grid_and_export(position):
    i = inp(live_of(**{"infra/ats/position": position, "energy/cells/Q1/p_now": 90.0}))
    assert (i.v("grid_kw"), i.v("export_kw")) == (0.0, 0.0) and i.v("ats_pos") == 3.0


def test_zero_if_signal_absent_or_stale_is_ignored():
    i = inp(live_of(**{"infra/ats/position": None}))
    assert i.v("grid_kw") == 200.0  # сигналу положення немає — умова ігнорується
    live = live_of(**{"infra/ats/position": "pos_II"})
    assert Inputs(cfg_with(), live, T0 + timedelta(seconds=30)).v("grid_kw") == 0.0
    live.update(
        [
            Reading("energy/cells/Q1/p_now", T0 + timedelta(seconds=100), value=120.0),
            Reading("energy/cells/Q2/p_now", T0 + timedelta(seconds=100), value=80.0),
        ]
    )
    assert Inputs(cfg_with(), live, T0 + timedelta(seconds=110)).v("grid_kw") == 200.0  # положення старше max_age_s


def test_pv_sum_with_term_lower_bound_zero():
    i = inp(live_of(**{"infra/pv/PV-INV-1/p_kw": 10.0, "infra/pv/PV-INV-2/p_kw": -2.5}))
    assert i.v("pv_kw") == 10.0  # терм −2,5 (ніч) обмежено знизу нулем
    assert inp(live_of(**{"infra/pv/PV-INV-1/p_kw": 40.5, "infra/pv/PV-INV-2/p_kw": 3.0})).v("pv_kw") == 43.5


def test_missing_term_means_input_absent_fail_closed():
    live = live_of(**{"energy/cells/Q2/p_now": None})
    i = inp(live)
    assert i.v("grid_kw") is None and i.v("export_kw") is None and not i.known("grid_kw")
    assert i.absent("grid_kw") and i.v("p_total") == 350.0  # решта входів не страждає
    ctx = Ctx.from_inputs(i, ["grid_kw"])
    assert ctx.v("grid_kw") is None


def test_stale_term_means_input_absent_and_age_is_the_oldest_term():
    live = live_of()
    live.update(
        [
            Reading("energy/lines/C1/p_now", T0 + timedelta(seconds=40), value=200.0),
            Reading("energy/lines/C2/p_now", T0 + timedelta(seconds=10), value=150.0),
        ]
    )
    fresh = Inputs(cfg_with(), live, T0 + timedelta(seconds=59))
    assert (
        fresh.v("p_total") == 350.0
        and fresh.age("p_total") == 49.0
        and fresh.reading("p_total").ts == T0 + timedelta(seconds=10)
    )  # свіжість = найстаріший терм
    stale = Inputs(cfg_with(), live, T0 + timedelta(seconds=71))
    assert stale.v("p_total") is None and not stale.absent("p_total")  # несвіже ≠ «не підключено»
    assert stale.age("p_total") == 61.0
    assert Inputs(cfg_with(), live, T0 + timedelta(seconds=71)).v("s1_p") == 200.0  # секція 1 — лише свіжий терм C1


def test_bad_quality_term_is_missing():
    live = live_of()
    live.update([Reading("energy/lines/C1/p_now", T0, value=200.0, q="bad")])
    assert inp(live).v("p_total") is None and inp(live).v("s2_p") == 150.0


def test_period_extends_freshness_of_terms():
    live = live_of()
    late = Inputs(
        cfg_with(), live, T0 + timedelta(seconds=80), periods={"energy/lines/C1/p_now": 30, "energy/lines/C2/p_now": 30}
    )
    assert late.v("p_total") == 350.0  # max(3·30, 60) = 90 с


def test_derived_overrides_raw_reading_of_the_same_code():
    live = live_of(**{"infra/totals/grid_kw": 999.0})
    assert inp(live).v("grid_kw") == 200.0
    live = live_of(**{"energy/cells/Q2/p_now": None, "infra/totals/grid_kw": 999.0})
    assert inp(live).v("grid_kw") is None  # без fallback на сирий сигнал (fail-closed)


def test_empty_terms_input_is_absent_without_warning(caplog):
    cfg = cfg_with({"energy/sections/S1/p_kw": {"op": "sum", "terms": []}})
    with caplog.at_level(logging.WARNING):
        i = inp(cfg=cfg)
        assert i.v("s1_p") is None and i.absent("s1_p")
    assert "derived" not in caplog.text


@pytest.mark.parametrize(
    "formula",
    [
        {"op": "avg", "terms": []},
        {"op": "sum", "terms": [{"code": "x", "k": "1"}]},
        {"op": "sum", "terms": "x"},
        {"op": "ge", "code": "infra/ats/src1_state"},
        {"op": "sum", "terms": [{"code": "energy/lines/C1/p_now", "k": 1.0}], "zero_if": {"code": "a"}},
    ],
)
def test_unknown_op_or_malformed_formula_input_absent_with_one_warning(formula, caplog):
    drv._warned.clear()
    raw = base_raw()
    raw["derived"] = {"energy/totals/p_now": formula}
    parsed = cfgmod.parse(raw)
    assert any(w.startswith("derived.energy/totals/p_now") for w in parsed.warnings)
    with caplog.at_level(logging.WARNING, logger="collector.plugin.energy_ctl"):
        i = inp(cfg=parsed.config)
        assert i.v("p_total") is None and i.v("p_total") is None
        assert Inputs(parsed.config, live_of(), T0).v("p_total") is None
    assert caplog.text.count("вхід вважається відсутнім") == 1  # попередження — раз


def test_config_keeps_derived_block_and_schema_rejects_non_objects():
    cfg = cfg_with()
    assert set(cfg.derived) == set(derived_block()) and cfg.derived["infra/ats/src1_ok"]["op"] == "ge"
    raw = base_raw()
    raw["derived"] = {"x": 5}
    assert cfgmod.parse(raw).errors
    assert cfgmod.parse({"schema": 1, "config_version": 1}).config.derived == {}


# --- інтеграція: з сирими сигналами (без жодного похідного) автоматика й інтенти більше не блокуються ---------------
def derived_raw():
    raw = base_raw()
    raw["derived"] = derived_block()
    raw["scenarios"]["chp"]["enabled"] = False  # щоб сценарій chp не запускав КГУ раніше за інтент chp_start
    return raw


async def boot_raw():
    """Плагін із `derived` у конфігу й лише сирими показаннями на «пристрої» (похідних кодів у LiveCache немає)."""
    h = await make_plugin(None, derived_raw())
    wire_device(h)
    feed_raw_plant(h)
    return h


async def test_backup_and_intents_work_on_raw_signals_only():
    h = await boot_raw()
    for code in (
        "infra/totals/grid_kw",
        "infra/totals/export_kw",
        "infra/totals/pv_now",
        "energy/totals/p_now",
        "energy/sections/S1/p_kw",
        "energy/sections/S2/p_kw",
        "infra/ats/src1_ok",
    ):
        assert code not in h.device.regs  # збирач їх не опитує
    await h.tick()
    snap = h.engine.snapshot()
    assert snap["engine"]["mode"] == "auto" and snap["scenarios"]["backup"]["state"] == "armed"
    assert snap["scenarios"]["peak"]["facts"]["grid_kw"] == 200 and snap["scenarios"]["self"]["state"] != "warn"
    for i, (kind, params) in enumerate(
        (("qs_close", {}), ("bess_charge", {"power_kw": 40, "until": "16:00", "soc_limit_pct": 95}), ("chp_start", {}))
    ):
        h.device.hooks["energy_control/qs/cmd"] = lambda v, t: h.device.regs.__setitem__(
            "energy/cells/QS/state", (None, "closed")
        )
        h.device.hooks["energy_control/chp/cmd"] = lambda v, t: h.device.regs.__setitem__(
            "infra/chp/state", (None, "starting")
        )
        res, action = await run_intent(h, kind, params, idem=f"dv{i}", action_id=100 + i)
        assert res["accepted"] is True, (kind, res)
        assert action["state"] == "done", (kind, action)


async def test_backup_activates_from_derived_src1_ok_and_island_zeroes_grid():
    h = await boot_raw()
    await h.tick()
    h.device.regs["infra/ats/src1_state"] = (None, "under")  # мережа зникла: src1_ok = ge(0, 1) = 0
    h.device.sync()
    await h.run(3)
    assert h.engine.snapshot()["scenarios"]["backup"]["state"] == "active"
    assert h.engine.shared["backup_active"] is True
    h.device.regs["infra/ats/position"] = (None, "pos_II")
    h.device.sync()
    await h.tick()
    assert h.engine.snapshot()["scenarios"]["peak"]["facts"].get("reason") == "резервне живлення"


async def test_intent_blocked_when_a_derived_term_is_missing():  # fail-closed
    h = await boot_raw()
    del h.device.regs["infra/ats/src1_state"]
    h.live._last.pop("infra/ats/src1_state")
    res = await h.plugin.call(INTENT_SIGNAL, intent("bess_charge", {"power_kw": 40}, now=h.clock.now()))
    assert res["state"] == "blocked" and "infra/ats/src1_ok" in res["reason"]  # data_fresh: немає терма src1_state


async def test_hold_when_derived_grid_is_stale_longer_than_stale_hold_s():
    h = await make_plugin(None, derived_raw())
    feed_raw_plant(h)
    await h.tick()
    assert h.engine.mode == "auto"
    for code in ("energy/cells/Q1/p_now", "energy/cells/Q2/p_now"):  # вводи більше не оновлюються
        h.device.regs.pop(code)
    for _ in range(3):
        h.clock.advance(12)
        h.device.sync()
        await h.engine.tick()
    assert h.engine.mode == "hold" and h.engine.reason == "немає даних grid_kw"
