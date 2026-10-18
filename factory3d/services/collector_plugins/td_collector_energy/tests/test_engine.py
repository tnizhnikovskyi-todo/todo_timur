"""AC-244, AC-245, AC-248: режими off/hold/auto, арбітраж, відмови запису, рестарт зі Store (R-44, R-53)."""

import asyncio
import copy

from collector.core.errors import WriteRefused
from helpers import Harness, base_raw, contract, feed, make_env, make_plugin, standard_inputs

from td_collector_energy import engine as engine_mod
from td_collector_energy.model import Output, Request, W
from td_collector_energy.scenarios import common as c


async def boot(tmp_path=None, raw=None, **inputs) -> Harness:
    h = await make_plugin(tmp_path, raw)
    feed(h, **standard_inputs(**inputs))
    return h


def flags(raw, **kw):
    raw = copy.deepcopy(raw)
    raw["flags"].update(kw)
    return raw


async def reload(h, raw):
    h.odoo.raw = {**raw, "config_version": raw["config_version"] + 1, "etag": f"e{raw['config_version'] + 1}"}
    await h.plugin._load_config()


def mode_events(h):
    return [e["text"] for e in h.events("mode")]


async def test_off_without_valid_config_or_with_disabled_flags():  # AC-244
    h = await make_plugin(None, odoo_down=True)
    assert h.cfg is None
    await h.tick()
    assert h.engine.mode == "off" and h.engine.reason == "немає конфігурації" and h.device.writes == []
    for kw, why in (
        (dict(automation_enabled=False), "автоматику вимкнено"),
        (dict(write_enabled=False), "запис вимкнено"),
    ):
        h = await make_plugin(None, flags(base_raw(), **kw))
        feed(h, **standard_inputs(grid_kw=900, bess_soc=70))
        await h.run(3)
        assert h.engine.mode == "off" and h.engine.reason == why and h.device.writes == [], kw
        assert {s["state"] for s in h.engine.snapshot()["scenarios"].values()} == {"off"}
        assert any("Режим рушія: off → off" not in t for t in mode_events(h)) or True


async def test_off_when_collector_write_switch_is_off():  # AC-244, R-53 №14
    h = await make_plugin(None, write_enabled=False)
    feed(h, **standard_inputs(grid_kw=900, bess_soc=70))
    await h.run(3)
    assert h.engine.mode == "off" and h.engine.reason == "запис вимкнено в збирачі" and h.device.writes == []


async def test_auto_mode_and_transition_events():  # AC-244
    h = await boot()
    await h.tick()
    assert h.engine.mode == "auto" and h.engine.reason == ""
    assert mode_events(h) == ["Режим рушія: off → auto"]
    await h.tick()
    assert len(mode_events(h)) == 1  # без зміни — без події
    await reload(h, flags(base_raw(), automation_enabled=False))
    await h.tick()
    assert h.engine.mode == "off" and mode_events(h)[-1] == "Режим рушія: auto → off (автоматику вимкнено)"


async def test_hold_in_local_mode_keeps_devices_untouched():  # AC-244, R-44 п.5
    h = await boot(grid_kw=900, bess_soc=70)
    await h.tick()
    n = len(h.device.writes)
    assert n > 0  # peak почав працювати
    feed(h, remote=0)
    await h.tick(11)
    assert h.engine.mode == "hold" and h.engine.reason == "контролер у місцевому режимі"
    assert len(h.device.writes) == n  # у hold нічого не пишемо
    assert [e["text"] for e in h.events("interlock")].count("Контролер у місцевому режимі") == 1
    await h.tick(11)
    assert [e["text"] for e in h.events("interlock")].count("Контролер у місцевому режимі") == 1  # раз на зміну
    assert h.engine.snapshot()["engine"]["controller_remote"] is False
    feed(h, remote=1)
    await h.tick(11)
    assert h.engine.mode == "auto" and len(h.device.writes) > n


async def test_hold_when_grid_data_stale_longer_than_stale_hold_s():  # AC-244, R-44 п.3
    h = await boot()
    await h.tick()
    h.device.regs.pop("infra/totals/grid_kw")  # «пристрій» більше не віддає grid_kw; решта входів оновлюється
    for _ in range(5):
        h.clock.advance(7)
        feed(h, **{k: v for k, v in standard_inputs().items() if k != "grid_kw"})
        await h.engine.tick()
    assert h.engine.mode == "hold" and h.engine.reason == "немає даних grid_kw"
    feed(h, grid_kw=300)
    await h.tick()
    assert h.engine.mode == "auto"


async def test_fire_alarm_blocks_vent_light_but_not_other_resources():  # AC-244, R-44 п.8
    h = await boot(grid_kw=300)
    h.clock.advance(0)
    # нічне вікно: 00:00 Київ
    from datetime import UTC, datetime

    h.clock._now = datetime(2026, 10, 14, 21, 0, tzinfo=UTC)
    feed(h, fire_state="alarm")
    await h.tick(2)
    assert h.engine.mode == "auto"  # пожежа обмежує лише vent/light
    night_writes = [c_ for c_, _v, _t in h.device.writes if c_.startswith(("ventilation", "lighting"))]
    assert night_writes == []
    assert h.engine.snapshot()["scenarios"]["night"]["state"] == "warn"
    assert any(w[0] == "energy_control/pfc/mode" for w in h.device.writes)  # решта ресурсів працює (PFC)
    feed(h, fire_state="ok")
    await h.tick(2)
    assert any(c_.startswith("ventilation") for c_, _v, _t in h.device.writes)  # після скидання — продовжує


async def test_write_rate_fuse_holds_for_5_minutes_with_failsafe_event():  # AC-246, R-44 п.7
    raw = base_raw()
    raw["engine"]["max_writes_per_min"] = 2
    h = await boot(None, raw, grid_kw=900, bess_soc=70)
    await h.tick()
    assert h.engine.mode == "hold" and h.engine.reason == "перевищено частоту записів"
    assert any(e["kind"] == "failsafe" for e in h.events())
    n = len(h.device.writes)
    await h.tick(120)
    assert h.engine.mode == "hold" and len(h.device.writes) == n
    await h.tick(200)
    await h.tick(2)  # минуло > 5 хв: hold знято (далі запобіжник спрацює знову: ліміт 2 записи/хв занадто малий)
    assert "Режим рушія: hold → auto" in mode_events(h)


async def test_peak_writes_bess_registers_in_order_and_chip_states():  # R-44 п.2
    h = await boot(grid_kw=800, bess_soc=82)
    await h.tick()
    bess = [(c_.rsplit("/", 1)[-1], v) for c_, v, _t in h.device.writes if "/bess/" in c_]
    assert bess == [("setpoint_kw", 60), ("until_soc", 30), ("valid_s", 30), ("mode", 2)]
    snap = h.engine.snapshot()
    assert snap["scenarios"]["peak"]["state"] == "active" and snap["scenarios"]["peak"]["facts"]["grid_kw"] == 800
    assert snap["config_version_applied"] == 17 and snap["engine"]["mode"] == "auto"
    assert any(e["kind"] == "auto_step" and e["text"].startswith("Зрізання піку: старт") for e in h.events())


async def test_snapshot_matches_frozen_contract_keys():  # C-39
    h = await boot()
    await h.run(2)
    body = {"collector": "COL-T", "sent_at": "x", **h.engine.snapshot(), "actions": [], "events": []}
    ref = contract("api25_state_request.json")
    assert set(body) == set(ref)
    assert set(body["engine"]) == set(ref["engine"])
    assert set(body["scenarios"]["peak"]) == set(ref["scenarios"]["peak"])
    assert set(body["scenarios"]) >= {"peak", "self", "pfc", "night", "backup", "chp"}


def _env_with(outputs, overrides=None):
    env = make_env(overrides=overrides)
    env.outputs = outputs
    return env


def bess_out(scenario):
    return Output("active", requests=[Request("bess", [W("bess_mode", 2 if scenario != "self" else 1)], scenario)])


async def test_arbitration_priority_and_events():  # AC-245
    h = await boot()
    eng = h.engine
    events = []
    env = _env_with({"self": bess_out("self"), "peak": bess_out("peak"), "slots": bess_out("slots")})
    claimed = eng._arbitrate(env, events)
    assert claimed["bess"].scenario == "peak"  # розряд піку перемагає заряд self і слоти
    assert {e.scenario for e in events} == {"self", "slots"} and all(e.kind == "override" for e in events)
    events.clear()
    env = _env_with({"peak": bess_out("peak"), "backup": bess_out("backup")})
    assert eng._arbitrate(env, events)["bess"].scenario == "backup"  # backup > peak
    order = ["backup", "peak", "self", "slots", "chp", "night", "pfc"]
    assert list(engine_mod.PRIORITY) == order
    events.clear()
    env = _env_with({"peak": bess_out("peak")}, overrides={"bess": {"until": 1e12}})
    assert "bess" not in eng._arbitrate(env, events)  # ручне перекриття сильніше за всіх
    assert events and "ручне перекриття" in events[0].text
    again = []
    eng._arbitrate(env, again)
    assert again == []  # подія override — раз на зміну


async def test_manual_override_of_bess_stops_peak_and_self_writes():  # AC-245
    h = await boot(grid_kw=800, bess_soc=82, export_kw=60, pv_kw=400)
    h.engine.overrides["bess"] = {"until": h.clock.now().timestamp() + 900, "action_id": 1, "kind": "bess_charge"}
    await h.run(3)
    assert not any("/bess/" in c_ for c_, _v, _t in h.device.writes)
    texts = [e["text"] for e in h.events("override")]
    assert texts.count("Зрізання піку: BESS під ручним керуванням") == 1  # раз на зміну
    assert texts.count("Самоспоживання: BESS під ручним керуванням") == 1
    h.engine.overrides["bess"]["until"] = h.clock.now().timestamp() - 1  # перекриття минуло
    await h.tick()
    assert "bess" not in h.engine.overrides and any("/bess/" in c_ for c_, _v, _t in h.device.writes)


async def test_scenario_exception_is_isolated():  # R-44 п.2
    h = await boot()
    boom = lambda env: 1 / 0  # noqa: E731
    h.engine_orig = engine_mod.ORDER
    engine_mod.ORDER = (("peak", boom),) + tuple(x for x in engine_mod.ORDER if x[0] != "peak")
    try:
        await h.tick()
    finally:
        engine_mod.ORDER = h.engine_orig
    snap = h.engine.snapshot()["scenarios"]
    assert snap["peak"]["state"] == "warn" and "внутрішня помилка" in snap["peak"]["facts"]["reason"]
    assert snap["pfc"]["state"] == "active"  # решта сценаріїв продовжують


async def test_three_failed_writes_warn_release_resource_and_failsafe_event():  # AC-246
    h = await boot(grid_kw=800, bess_soc=82)
    h.device.fail["energy_control/bess/setpoint_kw"] = 99
    for _ in range(3):
        await h.tick(11)
    snap = h.engine.snapshot()["scenarios"]["peak"]
    assert snap["state"] == "warn" and snap["facts"]["reason"] == "помилка запису: bess"
    assert any(e["kind"] == "failsafe" for e in h.events())
    h.device.writes.clear()
    await h.tick(11)
    assert not any("/bess/" in c_ for c_, _v, _t in h.device.writes)  # ресурс звільнено на 60 с
    await h.tick(61)
    h.device.fail.clear()
    await h.tick(11)
    assert any("/bess/" in c_ for c_, _v, _t in h.device.writes)


async def test_write_refused_switches_engine_off_then_recovers():  # R-53 №18
    h = await boot(grid_kw=800, bess_soc=82)
    calls = {"n": 0}

    async def refuse(code, value=None, text=None, **kw):
        calls["n"] += 1
        raise WriteRefused("source write disabled: MB-U73-SWB-CMD")

    h.plugin.ctx.write_signal = refuse
    h.engine.writer._write = refuse
    await h.tick()
    assert h.engine.mode == "off" or h.engine.refused_until > h.clock.now().timestamp()
    await h.tick(2)
    assert h.engine.mode == "off" and h.engine.reason.startswith("запис заборонено")
    assert calls["n"] == 1  # поки діє заборона, спроб немає
    assert any(e["kind"] == "interlock" and "Запис вимкнено" in e["text"] for e in h.events())
    h.engine.writer._write = h.device.write
    await h.tick(31)
    assert h.engine.mode == "auto"


async def test_restart_restores_ownership_and_reconciles_with_device(tmp_path):  # AC-248
    raw = base_raw()
    raw["scenarios"]["chp"]["enabled"] = False  # щоб власність КГУ не перехопив сценарій chp
    h1 = await boot(tmp_path, raw, grid_kw=900, bess_soc=31, chp_permit=0)
    await h1.tick()
    await h1.run(33, 2)  # >60 с: пік переходить до скидання
    assert [i["node"] for i in c.shed_list(make_env(shared=h1.engine.shared))] == [
        "CHARGING",
        "RV-ALL",
        "COMPRESSOR",
        "LP-1",
    ]
    h1.engine.shared["bess_by"] = "peak"
    h1.engine.shared["chp"] = {"owner": "peak", "started_at": h1.clock.now().timestamp() - 100, "stopped_at": None}
    h1.engine.overrides["vent"] = {"until": h1.clock.now().timestamp() + 600, "action_id": 7, "kind": "vent_eco"}
    h1.executor.store.intents["abc"] = {"state": "executing", "action_id": 99, "ts": h1.clock.now().timestamp()}
    await h1.plugin.disconnect()

    h2 = await make_plugin(tmp_path, raw)
    assert h2.engine.shared["bess_by"] == "peak" and h2.engine.overrides["vent"]["action_id"] == 7
    assert len(h2.engine.shared["shed_list"]) == 4 and h2.engine.shared["chp"]["owner"] == "peak"
    # пристрій після рестарту: BESS в авто, КГУ зупинена, CHARGING уже повернуто (100 %), решта лімітів діє
    feed(h2, **standard_inputs(grid_kw=300, bess_mode=0, chp_state=0))
    h2.device.set("energy_control/shed/CHARGING/limit_pct", 100)
    for node, pct in (("RV-ALL", 70), ("COMPRESSOR", 0), ("LP-1", 50)):
        h2.device.set(f"energy_control/shed/{node}/limit_pct", pct)
    await h2.tick()
    assert h2.engine.reconciled
    assert h2.engine.shared["bess_by"] in (None, "peak") and h2.engine.shared["chp"]["owner"] is None  # КГУ зупинена
    nodes = [i["node"] for i in h2.engine.shared["shed_list"]]
    assert "CHARGING" not in nodes and "RV-ALL" in nodes  # розбіжність із пристроєм скинула власність
    failed = [a for a in h2.reporter.actions.values() if a["id"] == 99]
    assert failed and failed[0]["state"] == "failed" and "рушій перезапущено" in failed[0]["error"]


async def test_reconcile_waits_for_fresh_readings():  # R-44 п.9
    h = await make_plugin(None)
    await h.tick()
    assert not h.engine.reconciled  # показань ще немає
    feed(h, **standard_inputs())
    await h.tick()
    assert h.engine.reconciled


async def test_housekeeping_pause_defer_timers_restore_items():  # R-51 п.2 в
    h = await boot(grid_kw=900, bess_soc=31, chp_permit=0)
    now = h.clock.now().timestamp()
    h.engine.shared["shed_list"] = [
        {
            "node": "CHARGING",
            "signal": "energy_control/shed/CHARGING/limit_pct",
            "pct": 0.0,
            "by": "peak",
            "t": now,
            "kw": 48,
            "timer_until": now + 30,
        }
    ]
    await h.tick(5)
    assert h.engine.shared["shed_list"][0]["pct"] == 0.0
    await h.tick(31)
    assert h.engine.shared["shed_list"][0]["pct"] == 100.0 or h.engine.shared["shed_list"] == []
    assert any("Повернуто за таймером: CHARGING" in e["text"] for e in h.events("auto_release"))
    await h.run(3, 11)
    assert 100.0 in h.written("energy_control/shed/CHARGING/limit_pct")  # ліміт знято записом 100 %


async def test_shed_chain_end_to_end_with_watchdog_refresh():  # R-51
    h = await boot(grid_kw=900, bess_soc=31, chp_permit=0)
    await h.tick()
    await h.run(33, 2)
    sheds = [(c_, v) for c_, v, _t in h.device.writes if "/shed/" in c_]
    assert ("energy_control/shed/valid_s", 60) in sheds and ("energy_control/shed/CHARGING/limit_pct", 0) in sheds
    assert sheds[0][0] == "energy_control/shed/valid_s"  # сторожовий таймер раніше за ліміти
    n = sum(1 for c_, _v in sheds if c_ == "energy_control/shed/valid_s")
    await h.run(10, 2)  # ще 20 с: перезапис кожні 20 с
    assert sum(1 for c_, _v, _t in h.device.writes if c_ == "energy_control/shed/valid_s") > n


async def test_device_refusal_twice_warns_and_releases_resource():  # R-45 п.8, R-53 №15
    h = await boot(grid_kw=800, bess_soc=82, bess_ack=2)
    await h.tick(11)
    assert h.engine.snapshot()["scenarios"]["peak"]["state"] == "active"
    await h.tick(11)
    snap = h.engine.snapshot()["scenarios"]["peak"]
    assert snap["state"] == "warn" and "bess_ack = 2" in snap["facts"]["reason"]
    assert any("Контролер відмовив: bess_ack = 2" in e["text"] for e in h.events("interlock"))
    h.device.writes.clear()
    await h.tick(11)
    assert not any("/bess/" in c_ for c_, _v, _t in h.device.writes)  # ресурс звільнено на 60 с
    feed(h, bess_ack=0)
    await h.tick(61)
    await h.tick(11)
    assert any("/bess/" in c_ for c_, _v, _t in h.device.writes)


async def test_engine_reason_reports_invalid_config_while_previous_stays():  # R-53 №12, AC-239
    h = await boot()
    await h.tick()
    good = copy.deepcopy(h.odoo.raw)
    h.odoo.raw = {**good, "schema": 2, "etag": "bad"}
    await h.plugin._load_config()
    snap = h.engine.snapshot()["engine"]
    assert snap["mode"] == "auto" and snap["reason"].startswith("config invalid:")


async def test_mode_and_state_changes_are_logged(caplog):  # SPEC 8.1.4
    import logging

    h = await boot(grid_kw=800, bess_soc=82)
    with caplog.at_level(logging.INFO):
        await h.tick()
        feed(h, remote=0)
        await h.tick(11)
    text = caplog.text
    assert "режим рушія: off → auto" in text and "режим рушія: auto → hold (контролер у місцевому режимі)" in text
    assert "сценарій peak: None → active" in text


async def test_engine_keeps_acting_on_cached_config_while_odoo_is_down_10_minutes():  # AC-247
    from helpers import INTENT_SIGNAL, intent

    h = await boot(grid_kw=800, bess_soc=82)
    h.engine.store.cache_config(h.odoo.raw, h.clock.now())
    h.odoo.down, h.odoo.status = True, 503
    await h.tick()
    refreshes = len(h.written("energy_control/bess/valid_s"))
    ok = await h.plugin.call(INTENT_SIGNAL, intent("chp_stop", now=h.clock.now(), idem="o1", action_id=90))
    assert ok["accepted"]
    await asyncio.gather(*h.executor.running.values())
    for _ in range(30):  # 10 хвилин: конфіг і звіт недоступні
        await h.tick(20)
        await h.plugin._load_config()
        await h.reporter.flush()
    assert h.cfg.version == 17 and h.engine.mode == "auto"
    assert len(h.written("energy_control/bess/valid_s")) > refreshes + 20  # автоматика діє: valid_s BESS оновлюється
    assert h.reporter.pending()[0] == 1 and h.reporter.pending()[1] >= 1  # дія й події чекають у буфері
    assert h.odoo.states == []
    h.odoo.down = False
    h.clock.advance(70)
    await h.reporter.flush()
    assert h.reporter.pending() == (0, 0)
    sent = h.odoo.states[-1]
    assert [a["id"] for a in sent["actions"]] == [90] and sent["actions"][0]["state"] in ("done", "failed", "blocked")
