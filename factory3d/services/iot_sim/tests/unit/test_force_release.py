"""ST-4: примусове значення (force) повертається до моделі — після ``hold_s`` і після ``release`` (SPEC API-16,
AC-50)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from iot_sim.config import Settings
from iot_sim.core.scenarios import ScenarioRunner
from iot_sim.protocols.control_api import create_app

AIR = "equipment/AIR-RING/pressure_bar"  # пасивний пристрій: моделі, що веде значення, немає; номінал 6,37
COMPRESSOR = "equipment/COMPRESSOR/pressure_bar"  # модель compressor рахує тиск щотіку (R-01 навколо nominal)
TOKEN = "t" * 40


def test_passive_forced_value_returns_to_nominal_after_hold(world):
    sig = world.signals[AIR]
    assert world.devices["AIR-RING"].driver == "passive"
    nominal = sig.spec.initial_value()
    assert nominal == pytest.approx(6.37)
    t0 = world.now()
    world.force(AIR, 4.5, hold_s=60)
    world.advance(30)
    assert sig.value == 4.5 and sig.held_until is not None  # утримання діє
    world.advance(31)
    assert sig.held_until is None
    assert sig.value == pytest.approx(nominal)
    assert sig.ts >= t0 + timedelta(seconds=60)  # ts оновлено, щоб споживач бачив нове значення


def test_passive_status_leaves_alarm_after_expiry(world):
    """Стенд: AIR-RING 4,5 < порога 6,0 тримав сигнал в alarm до ручного повернення."""
    sig = world.signals[AIR]
    world.force(AIR, 4.5, hold_s=20)
    world.advance(5)
    assert sig.status == "alarm"
    world.advance(30)
    assert sig.status == "warn"  # 6,37 бар — у межах 10 % до порога 6,0 (warn), але не alarm


def test_hold_zero_is_not_expired_by_anything_else(world):
    """Без ``hold_s`` значення пасивного сигналу лишається (запис клієнта протоколу), поки не буде ``release``."""
    sig = world.signals[AIR]
    world.force(AIR, 4.5)
    world.advance(300)
    assert sig.value == 4.5
    world.release(AIR)
    assert sig.value == pytest.approx(6.37) and sig.held_until is None


def test_model_driven_signal_is_led_by_model_after_expiry(world):
    sig = world.signals[COMPRESSOR]
    world.force(COMPRESSOR, 4.5, hold_s=60)
    world.advance(30)
    assert sig.value == 4.5
    world.advance(300)
    assert sig.held_until is None
    assert sig.value > 5.5  # модель компресора веде тиск назад до ~6,8 бар
    assert sig.value != 4.5


def test_expiry_uses_sim_clock_and_each_signal_separately(world):
    a, b = world.signals[AIR], world.signals["equipment/SPRINKLERS/pressure_bar"]
    world.force(AIR, 4.5, hold_s=30)
    world.force(b.code, 3.0, hold_s=120)
    world.advance(60)
    assert a.held_until is None and a.value == pytest.approx(6.37)
    assert b.held_until is not None and b.value == 3.0
    assert b.held_until - world.now() < timedelta(seconds=61)
    world.advance(61)
    assert b.held_until is None and b.value == pytest.approx(b.spec.initial_value())


def test_api_release_returns_value_to_model(world):
    app = create_app(Settings(_env_file=None, api_token=TOKEN), world=world, runner=ScenarioRunner(world), follow=None)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as api:
        r = api.put(f"/sim/v1/signals/{AIR}", json={"value": 4.5, "hold_s": 600})
        assert r.json()["value"] == 4.5 and r.json()["held_until"] is not None
        r = api.put(f"/sim/v1/signals/{AIR}", json={"release": True})
        assert r.status_code == 200
        assert r.json()["held_until"] is None and r.json()["value"] == pytest.approx(6.37)
        assert api.get(f"/sim/v1/signals/{AIR}").json()["value"] == pytest.approx(6.37)
