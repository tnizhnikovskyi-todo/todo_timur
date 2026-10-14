"""R-23 вентустановки, R-24 освітлення, R-21 вода (AC-64)."""
from datetime import datetime

import pytest

from iot_sim.core.rng import det
from iot_sim.models.lighting import BY_CODE, GROUPS, c110_state
from iot_sim.models.roofvent import AQ, REC, ST, VE, VEL

BIG = 1e9


def val(world, code: str):
    return world.signals[code].value


def unit(code: str, leaf: str) -> str:
    return f"ventilation/units/{code}/{leaf}"


def hold_outdoor(world, t: float = 9.0) -> None:
    world.force("ventilation/totals/outdoor_c", t, BIG)


# --- R-23 --------------------------------------------------------------------------------------------
def test_heat_formula_bms_r13(world):
    hold_outdoor(world)
    world.devices["RV-05"].params["k"] = 0.72
    assert val(world, unit("RV-05", "mode")) == AQ
    world.step(10)
    assert val(world, unit("RV-05", "heat_kw")) == pytest.approx(6.88, abs=0.05)  # макет 6,9
    world.devices["RV-01"].params["k"] = 0.68
    assert val(world, unit("RV-01", "mode")) == VE
    world.step(10)
    assert val(world, unit("RV-01", "heat_kw")) == pytest.approx(17.3, abs=0.1)
    # AHU-1: 17 000 м³/год, outdoor = 9 → 68 кВт
    heat_ahu = 17000 * 1.2 / 3600 * (21 - 9)
    assert val(world, unit("AHU-1", "heat_kw")) == pytest.approx(heat_ahu, abs=0.1)
    assert val(world, unit("AHU-1", "heat_kw")) == pytest.approx(68.0, abs=0.1)


def test_valve_percent(world):
    hold_outdoor(world)
    world.devices["RV-05"].params["k"] = 0.72
    world.devices["RV-01"].params["k"] = 0.68
    world.step(10)
    assert val(world, unit("RV-05", "heating_valve")) == 6  # %, не частка
    assert val(world, unit("RV-01", "heating_valve")) == 15
    # витрата, потужність вентилятора, шум
    world.devices["RV-05"].params["k"] = 0.74
    world.advance(1800)
    assert val(world, unit("RV-05", "airflow_m3h")) == pytest.approx(8000 * 0.74, rel=0.03)
    assert val(world, unit("RV-05", "p_now")) == pytest.approx(8.6 * 0.74 ** 3 + 0.1)
    assert val(world, unit("RV-05", "state")) == "running"
    assert val(world, unit("RV-05", "supply_c")) == pytest.approx(19.5 + (det("RV-05") % 10) / 10,
                                                                  abs=0.5)
    assert val(world, "energy/consumers/AHU-1/p_now") == pytest.approx(9.3)


def test_default_k_and_modes_by_schedule(world):
    hold_outdoor(world)
    world.step(10)
    expected = 8000 * (0.55 + (det("RV-07") % 30) / 100)
    world.advance(1800)
    assert val(world, unit("RV-07", "airflow_m3h")) == pytest.approx(expected, rel=0.03)
    assert val(world, unit("RV-21", "mode")) == REC
    assert val(world, unit("RV-05", "mode")) == AQ
    world.clock.set(datetime(2026, 10, 12, 16, 0))  # поза зміною
    world.step(10)
    assert val(world, unit("RV-05", "mode")) == VEL
    world.clock.set(datetime(2026, 10, 12, 23, 30))
    world.step(10)
    assert val(world, unit("RV-05", "mode")) == ST
    assert val(world, unit("RV-05", "state")) == "stopped"
    assert val(world, unit("RV-05", "heat_kw")) == 0.0 and val(world, unit("RV-05", "heating_valve")) == 0
    world.clock.set(datetime(2026, 10, 13, 11, 45))  # обід: без змін
    world.step(10)
    assert val(world, unit("RV-05", "mode")) == ST
    world.clock.set(datetime(2026, 10, 13, 9, 0))
    world.step(10)
    assert val(world, unit("RV-05", "mode")) == AQ


def test_external_mode_write_persists_until_period_change(world):
    world.force(unit("RV-05", "mode"), 4, 600)
    world.advance(30)
    assert val(world, unit("RV-05", "mode")) == 4
    world.clock.set(datetime(2026, 10, 12, 16, 0))
    world.step(10)
    assert val(world, unit("RV-05", "mode")) == VEL


def test_blackout_stops_noncritical_fans(world):
    world.set_flag("blackout", {"phase": "outage"})
    world.step(10)
    assert val(world, unit("RV-05", "state")) == "stopped"
    assert val(world, unit("RV-05", "airflow_m3h")) == 0.0
    assert val(world, unit("AHU-1", "state")) == "stopped"
    assert val(world, "ventilation/units/EF-ELEC/state") == "running"  # критична
    world.clear_flag("blackout")
    world.step(10)
    assert val(world, unit("RV-05", "mode")) == AQ
    assert val(world, unit("RV-05", "state")) == "running"
    assert val(world, "energy/consumers/RV-ALL/p_now") > 0  # Σ вентиляторів RV (після BESS-тіку)


def test_outdoor_curve_and_fault(world):
    world.step(10)
    assert val(world, "ventilation/totals/outdoor_c") == pytest.approx(9.0, abs=0.1)
    world.fault("RV-05")
    world.step(10)
    assert val(world, unit("RV-05", "state")) == "fault"
    world.clear("RV-05")
    world.step(10)
    assert val(world, unit("RV-05", "state")) == "running"
    model = world.devices["RV-05"].model
    state = model.get_state()
    model.set_state(state)
    assert model.get_state() == state
    fan = world.devices["EF-CMP"].model
    fan.set_state({"enabled": False, "stopped_s": 3.0})
    assert fan.get_state()["enabled"] is False and fan.drift is None
    world.step(10)
    assert val(world, "ventilation/units/EF-CMP/airflow_m3h") == 0.0


def test_ef_chg_alarm(world):
    ef = world.devices["EF-CHG"].model
    assert val(world, "ventilation/units/EF-CHG/state") in ("running", 0)
    world.step(10)
    assert val(world, "ventilation/units/EF-CHG/state") == "running"
    assert val(world, "ventilation/units/EF-CHG/airflow_m3h") > 100
    ef.enabled = False
    world.set_flag("ef_chg_charging", True)
    for _ in range(60):
        world.step(1)
    assert val(world, "ventilation/units/EF-CHG/state") == "stopped"
    world.step(1)  # 61 с
    assert val(world, "ventilation/units/EF-CHG/state") == "stopped_charging"
    events, _ = world.events.since(0, kind="alarm")
    assert [e.message for e in events if "EF-CHG" in e.message] == [
        "EF-CHG: не працює під час заряджання — водень!"]
    world.step(10)
    assert len([e for e in world.events.since(0, kind="alarm")[0] if "EF-CHG" in e.message]) == 1
    ef.enabled = True
    world.step(10)
    assert val(world, "ventilation/units/EF-CHG/state") == "running"
    # без заряджання і без прапора: за потужністю CHARGING
    world.clear_flag("ef_chg_charging")
    ef.enabled = False
    world.force("energy/consumers/CHARGING/p_now", 0.0, BIG)
    world.advance(120)
    assert val(world, "ventilation/units/EF-CHG/state") == "stopped"
    world.force("energy/consumers/CHARGING/p_now", 5.0, BIG)
    world.advance(80)
    assert val(world, "ventilation/units/EF-CHG/state") == "stopped_charging"


# --- R-24 --------------------------------------------------------------------------------------------
def test_lighting_level_percent(world):
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 100  # %, не частка
    assert val(world, "lighting/groups/LT-CUT/p_now") == 27 * 126  # 3,4 кВт
    assert val(world, "lighting/groups/LT-FG/level") == 60
    assert val(world, "lighting/groups/LT-FG/p_now") == round(12 * 126 * 0.6)  # ≈ 0,9 кВт
    assert val(world, "lighting/groups/LT-RCV-1/level") == 80  # денне світло −20 %
    world.step(10)
    panel = sum(val(world, f"lighting/groups/{c}/p_now") for c, p, *_ in GROUPS if p == "LP-2")
    assert val(world, "energy/consumers/LP-2/p_now") == pytest.approx(panel / 1000.0)
    assert val(world, "lighting/panels/LP-2/state") == "ok"
    assert val(world, "lighting/groups/LT-CUT/faulty") == "—"


def test_lighting_schedule_periods(world):
    world.clock.set(datetime(2026, 10, 12, 6, 30))
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 50
    assert val(world, "lighting/groups/LT-FG/level") == 50
    world.clock.set(datetime(2026, 10, 12, 16, 0))
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 50
    world.clock.set(datetime(2026, 10, 12, 23, 0))
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 10  # ніч
    assert val(world, "lighting/groups/LT-FG/level") == 0  # присутність відсутня
    world.set_flag("presence", {"LT-FG": True})
    world.step(10)
    assert val(world, "lighting/groups/LT-FG/level") == 100
    world.clock.set(datetime(2026, 10, 17, 10, 0))  # субота
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 10


def test_lighting_helvarnet_command_and_scene(world):
    world.step(10)
    world.post("lighting", {"group": "LT-CUT", "level": 60})
    world.post("lighting", {"group": 13, "scene": 3})  # G:13 = LT-EB
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 60
    assert val(world, "lighting/groups/LT-EB/level") == 50
    assert val(world, "lighting/groups/LT-EB/scene") == 3
    assert val(world, "lighting/groups/LT-CNC/level") == 100  # чужі команди не зачіпають
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 60  # тримається до зміни розкладу
    world.clock.set(datetime(2026, 10, 12, 16, 0))
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 50
    world.set_flag("lighting_scene", {"all": {"scene": 4, "level": None, "fault_device": None}})
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 25
    world.set_flag("lighting_scene", {"LT-CUT": {"level": 70, "scene": None, "fault_device": None},
                                      "all": {"scene": 1}})
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 70
    assert val(world, "lighting/groups/LT-FG/level") == 100
    world.set_flag("lighting_scene", {"LT-CUT": {"note": 1}})
    world.step(10)
    assert val(world, "lighting/groups/LT-CUT/level") == 50
    lt = world.devices["LT-CUT"].model
    lt.set_state(lt.get_state())
    assert lt.get_state()["scene"] == 4  # остання викликана сцена
    assert world.devices["LP-1"].model.panel and not world.devices["LT-CUT"].model.panel


def test_c110_bits(world):
    assert c110_state(world, "@1.2.1.5") == 0  # норма
    world.set_flag("lighting_scene", {"LT-CUT": {"fault_device": "@1.2.1.5"}})
    world.step(10)
    assert c110_state(world, "@1.2.1.5") == 2  # NSLampFailure (S-15)
    assert c110_state(world, "@1.2.1.6") == 0
    assert val(world, "lighting/groups/LT-CUT/faults") == 1
    assert val(world, "lighting/groups/LT-CUT/faulty") == "@1.2.1.5"
    assert c110_state(world, "@1.9.9.9") is None  # поза складом → !…=11#
    world.clear_flag("lighting_scene")
    world.step(10)
    assert c110_state(world, "@1.2.1.5") == 0 and val(world, "lighting/groups/LT-CUT/faults") == 0
    # blackout до переключення: аварійний світильник = 0x400 (1024), решта — рівень 0
    world.set_flag("blackout", {"phase": "outage"})
    world.step(10)
    assert c110_state(world, "@1.2.1.1") == 1024
    assert c110_state(world, "@1.2.1.5") == 0
    assert val(world, "lighting/groups/LT-CUT/level") == 0
    # після переключення в II — за розкладом
    world.force("infra/ats/position", 3, BIG)
    world.step(10)
    assert c110_state(world, "@1.2.1.1") == 0
    assert val(world, "lighting/groups/LT-CUT/level") == 100
    assert BY_CODE["LT-CUT"][2] == 27


# --- R-21 --------------------------------------------------------------------------------------------
def _water_world(world, *, paint: bool):
    for code in ("SPRAY-1", "AUTOSPRAY-1"):
        world.workcenters[code] = {"state": "WORKING" if paint else "READY"}


def test_water_pulses_in_shift(world):
    _water_world(world, paint=False)
    start = val(world, "infra/water/m3_total")
    for _ in range(360):  # 1 год зміни, крок 10 с
        world.step(10)
    assert val(world, "infra/water/m3_total") - start == pytest.approx(2.1, abs=0.02)  # 210 імп.
    assert val(world, "infra/water/flow_m3h") == pytest.approx(2.1)


def test_water_off_shift_and_paint(world):
    _water_world(world, paint=True)
    world.advance(600)
    assert val(world, "infra/water/flow_m3h") == pytest.approx(3.6)
    _water_world(world, paint=False)
    world.clock.set(datetime(2026, 10, 12, 20, 0))
    world.advance(600)
    assert val(world, "infra/water/flow_m3h") == pytest.approx(0.3)
    world.workcenters.clear()
    world.step(10)  # без станів РЦ — за потужністю passive-номіналу (> 50 %) = «працює»
    wm = world.devices["WATER"].model
    wm.set_state(wm.get_state())
    assert wm.pulses > 0
    world.force("energy/consumers/SPRAY-1/p_now", 0.0, BIG)
    world.force("energy/consumers/AUTOSPRAY-1/p_now", 0.0, BIG)
    world.advance(600)
    assert val(world, "infra/water/flow_m3h") == pytest.approx(0.3)
    world.signals.pop("energy/consumers/SPRAY-1/p_now")
    world.signals.pop("energy/consumers/AUTOSPRAY-1/p_now")
    world.advance(10)
    assert val(world, "infra/water/flow_m3h") == pytest.approx(0.3)
