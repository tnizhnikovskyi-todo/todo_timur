"""R-11: СЕС (AC-11)."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from iot_sim.models.pv import (
    P_PEAK,
    ST_BLACKOUT,
    ST_NIGHT,
    ST_ON,
    ST_START,
    day_cloud_factor,
    season_factor,
    sun_factor,
    weather_factor,
)


def _total(world) -> float:
    return sum(world.signals[f"infra/pv/PV-INV-{k}/p_kw"].value for k in range(1, 9))


def _status(world, k: int = 1) -> int:
    return world.signals[f"infra/pv/PV-INV-{k}/status"].value


def test_parabola_matches_mock(world):
    world.settings = SimpleNamespace(sun_model="parabola")
    assert sun_factor(world) == pytest.approx(0.826, abs=1e-3)
    world.step(10)
    expected = 765 * 0.826
    assert expected * 0.84 * 0.99 <= _total(world) <= expected * 1.0 * 1.01
    assert world.signals["infra/totals/pv_now"].value == pytest.approx(_total(world))
    assert _status(world) == ST_ON
    assert world.signals["infra/pv/PV-INV-1/p_kw"].value <= 115


def test_astral_zero_at_night(world):
    world.clock.set(datetime(2026, 10, 12, 23, 0))
    assert sun_factor(world) == 0.0
    world.step(10)
    assert _total(world) == 0.0
    assert _status(world) == ST_NIGHT
    world.clock.set(datetime(2026, 10, 12, 10, 30))
    assert 0.6 < sun_factor(world) < 1.0
    assert sun_factor(world) == sun_factor(world)  # кеш полудня


def test_inverter_status_enum(world):
    world.settings = SimpleNamespace(sun_model="parabola")
    world.clock.set(datetime(2026, 10, 12, 7, 0, 5))  # sun ≈ 0,001 → P < 1 кВт
    world.step(1)
    assert 0 < _total(world) < 1.0
    assert _status(world) == ST_START
    world.clock.set(datetime(2026, 10, 12, 6, 59, 0))  # sun = 0
    world.step(1)
    assert _status(world) == ST_NIGHT
    world.clock.set(datetime(2026, 10, 12, 8, 0))
    world.step(1)
    assert _status(world) == ST_ON


def test_cloudy_scales_power(world):
    world.settings = SimpleNamespace(sun_model="parabola")
    world.step(10)
    clear = _total(world)
    world.set_flag("pv_cf", 0.3)
    world.step(10)
    assert _total(world) == pytest.approx(0.3 * clear, rel=0.1)


def test_blackout_status_and_restart(world):
    world.settings = SimpleNamespace(sun_model="parabola")
    world.set_flag("blackout", {"phase": "outage"})
    world.step(10)
    assert _total(world) == 0.0
    assert _status(world, 3) == ST_BLACKOUT
    world.clear_flag("blackout")
    world.step(10)
    assert _status(world) == ST_START and _total(world) == 0.0
    world.advance(70)
    assert _status(world) == ST_ON and _total(world) > 0


def test_energy_counters_and_state(world):
    world.settings = SimpleNamespace(sun_model="parabola")
    world.advance(600)
    today = world.signals["infra/pv/PV-INV-2/kwh_today"].value
    assert today == pytest.approx(world.signals["infra/pv/PV-INV-2/p_kw"].value * 600 / 3600, rel=0.1)
    model = world.devices["PV-INV"].model
    state = model.get_state()
    model.set_state(state)
    assert model.kwh_today["PV-INV-2"] == pytest.approx(today, rel=0.01)
    world.clock.set(datetime(2026, 10, 13, 10, 30))
    world.step(10)
    assert world.signals["infra/pv/PV-INV-2/kwh_today"].value < today
    world.fault("PV-INV")
    world.step(10)
    assert _total(world) == 0.0


def test_season_october_profile(world):
    """Жовтень: пік СЕС ≈ 0,75 від літнього (не 100 % щодоби); літо ≈ 1, грудень ≈ 0,56; parabola (макет) — 1."""
    world.clock.set(datetime(2026, 10, 16, 12, 0))
    assert season_factor(world) == pytest.approx(0.75, abs=0.03)
    world.clock.set(datetime(2026, 6, 21, 12, 0))
    assert season_factor(world) == pytest.approx(1.0, abs=0.01)
    world.clock.set(datetime(2026, 12, 21, 12, 0))
    assert season_factor(world) == pytest.approx(0.56, abs=0.04)
    world.settings = SimpleNamespace(sun_model="parabola")
    assert season_factor(world) == 1.0


def test_october_day_peak_below_summer(world):
    world.settings = SimpleNamespace(pv_weather=False)  # ясне небо
    peak = {}
    for day in (datetime(2026, 10, 16), datetime(2026, 6, 19)):
        best = 0.0
        for minute in range(12 * 60, 15 * 60, 15):  # навколо сонячного полудня
            world.clock.set(day.replace(hour=minute // 60, minute=minute % 60))
            world.step(10)
            best = max(best, _total(world))
        peak[day.month] = best
    assert 400 <= peak[10] <= 640  # жовтень: ≈ 0,75·765 ± шум
    assert peak[6] > 650  # літо: майже повна потужність
    assert peak[10] < 0.85 * peak[6]


# --- погода: хмарність і реальна добова вироблена енергія ----------------------------------------------------------
def _clear_kw(world) -> float:
    return min(920.0, P_PEAK * sun_factor(world) * season_factor(world) * 0.96)


def test_sun_times_kyiv_22_oct(world):
    """Схід ≈ 07:30, захід ≈ 17:54 (EEST) 22.10.2026; о 15:40 сонце ≈ 0,63 від полудня."""
    lit = []
    for minute in range(24 * 60):
        world.clock.set(datetime(2026, 10, 22, minute // 60, minute % 60))
        if sun_factor(world) > 0:
            lit.append(minute)
    assert 7 * 60 + 25 <= lit[0] <= 7 * 60 + 36 and 17 * 60 + 48 <= lit[-1] <= 17 * 60 + 58
    world.clock.set(datetime(2026, 10, 22, 15, 40))
    assert sun_factor(world) == pytest.approx(0.63, abs=0.03)


def test_weather_factor_deterministic_and_bounded(world):
    world.clock.set(datetime(2026, 10, 22, 12, 0))
    a = weather_factor(world)
    assert a == weather_factor(world) and 0.05 <= a <= 1.0
    days = {day_cloud_factor(datetime(2026, 10, d).date()) for d in range(1, 29)}
    assert len(days) > 20 and 0.1 <= min(days) and max(days) <= 0.8  # доби різні, але ряд відтворюваний
    world.clock.set(datetime(2026, 10, 22, 12, 30))
    assert abs(weather_factor(world) - a) < 0.1  # хмари змінюються повільно (інтерполяція погодинних значень)
    world.settings = SimpleNamespace(pv_weather=False)
    assert weather_factor(world) == 1.0
    world.settings = SimpleNamespace(sun_model="parabola")
    assert weather_factor(world) == 1.0  # макет: без погоди


def test_daily_energy_is_realistic_for_late_october(world):
    """З 22.10 на 30 діб: 1,5…2,2 кВт·год/кВт_п/добу в середньому (ясне небо дало б ≈ 3,9); окремі доби — від майже 0
    до майже ясних, але не вище за ясне небо."""
    from datetime import timedelta

    per_day, clear_day = [], []
    for i in range(30):
        d = datetime(2026, 10, 22) + timedelta(days=i)
        kwh = clear = 0.0
        for minute in range(0, 24 * 60, 5):
            world.clock.set(d.replace(hour=minute // 60, minute=minute % 60))
            kwh += _clear_kw(world) * weather_factor(world) * 5 / 60
            clear += _clear_kw(world) * 5 / 60
        per_day.append(kwh / P_PEAK)
        clear_day.append(clear / P_PEAK)
    mean = sum(per_day) / len(per_day)
    assert 1.5 <= mean <= 2.2, mean
    assert 3.3 <= sum(clear_day) / len(clear_day) <= 4.2  # ясне небо — для порівняння
    assert all(c <= k + 1e-9 for c, k in zip(per_day, clear_day, strict=True)) and max(per_day) - min(per_day) > 1.0


def test_pv_model_follows_weather(world):
    """15:40 22.10: потужність моделі = ясне небо · погода (шум до −16 %); ``pv_cf`` лишається окремим множником."""
    world.clock.set(datetime(2026, 10, 22, 15, 40))
    world.step(10)
    expected = _clear_kw(world) / 0.96 * weather_factor(world)
    assert expected * 0.83 <= _total(world) <= expected * 1.02  # шум 0,92 + 0,08·r ∈ [0,84; 1,0)
    assert _total(world) < _clear_kw(world)  # хмарно: нижче за ясне небо
    before = _total(world)
    world.set_flag("pv_cf", 0.5)
    world.step(10)
    assert _total(world) == pytest.approx(0.5 * before, rel=0.1)
