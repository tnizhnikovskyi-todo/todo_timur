"""AC-258: «КГУ за графіком і ціною» + слоти BESS (R-50, R-54 п.5)."""

from datetime import UTC, datetime

from helpers import T0, advance, base_cfg, base_raw, kinds, make_env, reqs, standard_inputs, writes_of

from td_collector_energy import config as cfgmod
from td_collector_energy.scenarios import chp, slots
from td_collector_energy.scenarios import common as c

NIGHT_TARIFF = datetime(2026, 10, 14, 1, 0, tzinfo=UTC)  # 04:00 Київ: зона 0…7, ціна 3,4 ₴
SLOT = {
    "id": 9,
    "resource": "chp",
    "date": None,
    "weekdays": "1111111",
    "from": 8.0,
    "to": 12.0,
    "mode": "run",
    "setpoint_kw": None,
}


def mk(now=T0, cfg=None, **over):
    return make_env(cfg or base_cfg(), now, **standard_inputs(**over))


def test_start_by_price_when_all_checks_ok():  # AC-258
    env = mk()  # 09:00 Київ: тариф 8,4; собівартість КГУ 19,80·0,25 = 4,95; 8,4 − 4,95 ≥ 0,5
    out = chp.step(env)
    assert writes_of(out, "chp") == {"chp_cmd": 1} and env.shared["chp"]["owner"] == "chp"
    assert kinds(out, "auto_step")[0].text == "КГУ: пуск за ціною (8.4 ₴ проти 4.95 ₴)"


def test_no_start_when_price_not_attractive_or_checks_fail_or_min_off():  # AC-258
    assert not reqs(chp.step(mk(NIGHT_TARIFF)), "chp")  # 3,4 − 4,95 < 0,5
    for bad in ({"chp_permit": 0}, {"chp_gas": 0.8}, {"chp_state": 1}):
        out = chp.step(mk(**bad))
        assert not reqs(out, "chp"), bad
    env = mk()
    env.shared["chp"] = {"owner": None, "started_at": None, "stopped_at": env.epoch - 20 * 60}  # пауза 30 хв не минула
    assert not reqs(chp.step(env), "chp")
    env.shared["chp"]["stopped_at"] = env.epoch - 31 * 60
    assert reqs(chp.step(env), "chp")


def test_start_by_slot_even_when_price_is_low():  # AC-258
    raw = base_raw()
    raw["slots"] = [SLOT]
    cfg = cfgmod.parse(raw).config
    out = chp.step(mk(datetime(2026, 10, 14, 6, 0, tzinfo=UTC), cfg))  # 09:00 у слоті 8…12, тариф 8,4 теж вигідний
    assert reqs(out, "chp")
    low = {**SLOT, "from": 3.0, "to": 6.0}
    raw["slots"] = [low]
    cfg = cfgmod.parse(raw).config
    out = chp.step(mk(NIGHT_TARIFF, cfg))
    assert reqs(out, "chp") and kinds(out, "auto_step")[0].text == "КГУ: пуск за графіком"
    cfg_noslots = base_cfg(chp={"params": {"use_slots": False}})
    cfg2 = cfgmod.parse({**base_raw(), "slots": [low]}).config
    assert cfg2 and not reqs(chp.step(mk(NIGHT_TARIFF, cfg_noslots)), "chp")


def test_stop_only_after_min_run_and_only_own():  # AC-258
    env = mk(NIGHT_TARIFF, chp_state=2)
    env.shared["chp"] = {"owner": "chp", "started_at": env.epoch - 1.2 * 3600, "stopped_at": None}
    assert not reqs(chp.step(env), "chp")  # відпрацьовано 1,2 год < min_run_h 2
    env.shared["chp"]["started_at"] = env.epoch - 2.3 * 3600
    out = chp.step(env)
    assert writes_of(out, "chp") == {"chp_cmd": 2} and env.shared["chp"]["owner"] is None
    for owner in ("peak", "manual"):
        env = mk(NIGHT_TARIFF, chp_state=2)
        env.shared["chp"] = {"owner": owner, "started_at": env.epoch - 5 * 3600, "stopped_at": None}
        assert not reqs(chp.step(env), "chp"), owner  # КГУ піку/оператора цим сценарієм не зупиняється


def test_fault_state_is_warn_and_disabled_is_off():  # AC-258
    out = chp.step(mk(chp_state=3))
    assert out.state == "warn" and out.facts["reason"] == "КГУ в аварії" and not out.requests
    off = chp.step(mk(cfg=base_cfg(chp={"enabled": False})))
    assert off.state == "off" and not off.requests
    assert chp.step(mk()).state == "armed"
    running = chp.step(mk(chp_state=2, chp_kw=640))
    assert running.state == "active" and running.facts["chp_kw"] == 640


def test_manual_override_of_chp_blocks_start():
    env = mk()
    env.overrides["chp"] = {"until": env.epoch + 100}
    assert not reqs(chp.step(env), "chp")


def test_owner_sync_clears_when_chp_stopped():
    env = mk(chp_state=2)
    env.shared["chp"] = {"owner": "chp", "started_at": env.epoch - 7200, "stopped_at": None}
    chp.sync_owner(env)
    assert env.shared["chp"]["running_seen"] is True
    env = advance(env, 2, chp_state=0)
    chp.sync_owner(env)
    ch = env.shared["chp"]
    assert ch["owner"] is None and ch["stopped_at"] == env.epoch and not ch["running_seen"]
    env2 = mk(chp_state=0)  # пуск не відбувся за 90 с
    env2.shared["chp"] = {"owner": "peak", "started_at": env2.epoch - 100, "stopped_at": None}
    chp.sync_owner(env2)
    assert env2.shared["chp"]["owner"] is None
    assert c.chp_run_h(env) is None


# --- слоти BESS (R-54 п.5) ----------------------------------------------------------------------------------
def slot_cfg(**kw):
    raw = base_raw()
    raw["slots"] = [
        {
            "id": 1,
            "resource": "bess",
            "date": None,
            "weekdays": "1111111",
            "from": 8.0,
            "to": 12.0,
            "mode": "charge",
            "setpoint_kw": 80.0,
            **kw,
        }
    ]
    return cfgmod.parse(raw).config


def test_bess_slot_charge_and_discharge_requests():
    out = slots.step(mk(cfg=slot_cfg(), bess_soc=50))
    assert writes_of(out, "bess") == {"bess_sp": 80, "bess_until": 95, "bess_valid": 30, "bess_mode": 1}
    out = slots.step(mk(cfg=slot_cfg(mode="discharge", setpoint_kw=None), bess_soc=70))
    assert writes_of(out, "bess") == {"bess_sp": 100, "bess_until": 30, "bess_valid": 30, "bess_mode": 2}
    assert not reqs(slots.step(mk(cfg=slot_cfg(), bess_soc=96)), "bess")  # SOC ≥ ціль
    assert not reqs(slots.step(mk(cfg=slot_cfg(mode="discharge"), bess_soc=31)), "bess")  # SOC ≤ пол + 2


def test_slot_date_weekday_and_window():
    env_out = mk(NIGHT_TARIFF, slot_cfg(), bess_soc=50)  # 04:00 — поза 8…12
    assert not reqs(slots.step(env_out), "bess")
    assert reqs(slots.step(mk(cfg=slot_cfg(date="2026-10-14"), bess_soc=50)), "bess")
    assert not reqs(slots.step(mk(cfg=slot_cfg(date="2026-10-15"), bess_soc=50)), "bess")
    assert not reqs(slots.step(mk(cfg=slot_cfg(weekdays="1000000"), bess_soc=50)), "bess")  # 14.10 — середа
    assert reqs(slots.step(mk(cfg=slot_cfg(weekdays="0010000"), bess_soc=50)), "bess")


def test_slot_end_releases_bess_once_and_blocked_by_override():
    env = mk(cfg=slot_cfg(), bess_soc=50)
    slots.step(env)
    assert env.shared["bess_by"] == "slots"
    late = advance(env, 5 * 3600, bess_soc=60)  # 14:00 — слот скінчився
    out = slots.step(late)
    assert writes_of(out, "bess") == {"bess_mode": 0, "bess_valid": 0} and kinds(out, "auto_release")
    assert not slots.step(advance(late, 2)).requests
    ov = mk(cfg=slot_cfg(), bess_soc=50)
    ov.overrides["bess"] = {"until": ov.epoch + 60}
    assert not reqs(slots.step(ov), "bess")
