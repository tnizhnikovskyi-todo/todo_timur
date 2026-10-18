"""AC-255: «PFC» — рушій лише задає автоматичний режим і ціль cos φ та стежить за відмовами (R-47)."""

from helpers import T0, base_cfg, base_raw, kinds, make_env, reqs, standard_inputs, writes_of

from td_collector_energy import config as cfgmod
from td_collector_energy.scenarios import pfc


def test_enabled_sets_auto_mode_and_target_from_plant():  # AC-255
    out = pfc.step(make_env(base_cfg(), T0, **standard_inputs()))
    assert writes_of(out, "pfc") == {"pfc_mode": 1, "pfc_cos": 0.95} and out.state == "active"
    raw = base_raw()
    raw["scenarios"]["pfc"]["params"] = {}
    raw["plant"]["cos_phi_target"] = 0.97  # E-10: ціль із єдиної групи налаштувань
    cfg = cfgmod.parse(raw).config
    assert writes_of(pfc.step(make_env(cfg, T0, **standard_inputs())), "pfc")["pfc_cos"] == 0.97


def test_disabled_sets_manual_mode():  # AC-255
    cfg = base_cfg(pfc={"enabled": False})
    out = pfc.step(make_env(cfg, T0, **standard_inputs()))
    assert writes_of(out, "pfc") == {"pfc_mode": 0} and out.state == "off"
    assert not kinds(out, "interlock")


def test_fault_step_is_warn_without_ticket_events():  # AC-255
    out = pfc.step(make_env(base_cfg(), T0, **standard_inputs(pfc2_fault=3)))
    assert out.state == "warn" and out.facts["fault"] == "PFC-2 ступінь 3"
    assert {e.kind for e in out.events} <= {"auto_step"}  # заявку ТО створює W1, рушій подій-заявок не дублює
    out = pfc.step(make_env(base_cfg(), T0, **standard_inputs(pfc1_fault=2, pfc2_fault=3)))
    assert out.facts["fault"] == "PFC-1 ступінь 2"
    assert reqs(out, "pfc")  # режим і ціль підтримуються й при збої ступеня


def test_event_only_on_change():
    env = make_env(base_cfg(), T0, **standard_inputs())
    first = pfc.step(env)
    assert len(kinds(first, "auto_step")) == 1 and "ціль cos φ 0.95" in kinds(first, "auto_step")[0].text
    assert not pfc.step(env).events
