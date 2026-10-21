"""СЕС: 8 інверторів SUN2000 (R-11).

``sun``: ``SIM_SUN_MODEL=astral`` — ``max(0, sin(elev))/sin(elev_noon_today)`` для Києва;
``parabola`` (макет) — ``max(0, 1 − ((h − 13)/6)²)``. ``P_total = 765·sun·season·cf·(0,92 + 0,08·r)``,
``season`` — сезонна амплітуда (лише для ``astral``): ``√(sin(h_noon сьогодні)/sin(h_noon літнього сонцестояння))``
(жовтень ≈ 0,75, грудень ≈ 0,56, червень 1), бо ``sun`` нормований на полудень кожної доби;
``cf`` — прапор ``pv_cf`` (S-12) · погодний множник ``weather_factor`` (лише ``astral``; ``SIM_PV_WEATHER=false``
вимикає), ``P_k = min(115, P_total/8)``. Статус 32089: ніч ``0xA000``,
``P < 1 кВт`` ``0x0001``, інакше ``0x0200``; ``blackout`` — ``0x0303`` і ``P = 0``; після повернення мережі
інвертори стартують 60 с (``0x0001``).

Погода: ясне небо дає ≈ 4,6 кВт·год/кВт_п/добу наприкінці жовтня (22.10: 3 540 кВт·год), реальні 1,5…2,2. Тому доба має
детермінований множник хмарності ``0,10 + 0,70·u(дата)`` (рівномірно 0,10…0,80, середнє 0,45: за 30 діб від 22.10
≈ 1,8 кВт·год/кВт_п/добу) і повільні «хмари» впродовж доби (±20 %, інтерполяція між погодинними значеннями). Сонце
(схід/захід) — за ``astral`` для Києва, без змін: 22.10 ≈ 07:30…17:54.

W2 (SPEC §8.2): потужність кожного інвертора множиться на ``pv_limit_pct / 100`` (прапор, за замовчуванням 100;
обмеження
контролера ГРЩ із сторожовим таймером ``shed_valid_s``); статус рахується за вільною (необмеженою) потужністю.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from astral import LocationInfo
from astral.sun import elevation, noon

from iot_sim.core.rng import det
from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.meter import ctl, island

P_PEAK = 900.0 * 0.85
INV_MAX_KW = 115.0
INV_COUNT = 8
RESTART_S = 60.0
ST_NIGHT, ST_START, ST_ON, ST_BLACKOUT, ST_FAULT = 0xA000, 0x0001, 0x0200, 0x0303, 0x0300

_KYIV = LocationInfo("Kyiv", "Ukraine", "Europe/Kyiv", 50.45, 30.52)
_noon_cache: dict[date, float] = {}
_season_cache: dict[date, float] = {}
_weather_cache: dict[date, float] = {}
CF_LO, CF_SPAN = 0.10, 0.70  # добовий множник хмарності: рівномірно 0,10…0,80 (середнє 0,45)
CLOUD_WOBBLE = 0.20  # повільні хмари впродовж доби, частка добового множника
WEATHER_SALT = "pv-cloud"
_SIN_NOON_MAX = math.sin(math.radians(90.0 - 50.45 + 23.44))  # полудень літнього сонцестояння, Київ


def _astral_sun(now: datetime) -> float:
    obs = _KYIV.observer
    elev = elevation(obs, now)
    if elev <= 0:
        return 0.0
    d = now.date()
    if d not in _noon_cache:
        noon_t = noon(obs, d, tzinfo=now.tzinfo)  # type: ignore[arg-type]
        _noon_cache[d] = math.sin(math.radians(elevation(obs, noon_t)))
    return max(0.0, math.sin(math.radians(elev))) / _noon_cache[d]


def sun_factor(world: Any) -> float:
    """Частка сонця 0…1 на sim-час ``world.now()`` за моделлю ``sun_model``."""
    now = world.now()
    if getattr(world.settings, "sun_model", "astral") == "parabola":
        h = now.hour + now.minute / 60.0 + now.second / 3600.0
        return max(0.0, 1.0 - ((h - 13.0) / 6.0) ** 2)  # type: ignore[no-any-return]
    return _astral_sun(now)


def season_factor(world: Any) -> float:
    """Сезонна амплітуда СЕС 0…1: ``√(sin h_noon / sin h_noon_літо)``; для ``parabola`` (макет) — 1."""
    if getattr(world.settings, "sun_model", "astral") == "parabola":
        return 1.0
    now = world.now()
    d = now.date()
    if d not in _season_cache:
        obs = _KYIV.observer
        h = elevation(obs, noon(obs, d, tzinfo=now.tzinfo))  # type: ignore[arg-type]
        _season_cache[d] = math.sqrt(max(0.0, math.sin(math.radians(h))) / _SIN_NOON_MAX)
    return min(1.0, _season_cache[d])


def _unit(key: str) -> float:
    """Детермінована величина 0…1 за ключем (FNV-1a + перемішування бітів)."""
    n = det(key)
    n = ((n ^ (n >> 16)) * 0x7FEB352D) & 0xFFFFFFFF
    n = ((n ^ (n >> 15)) * 0x846CA68B) & 0xFFFFFFFF
    return float((n ^ (n >> 16)) / 0xFFFFFFFF)


def day_cloud_factor(d: date) -> float:
    """Добовий множник хмарності 0,10…0,80 (детермінований за датою)."""
    if d not in _weather_cache:
        _weather_cache[d] = CF_LO + CF_SPAN * _unit(f"{WEATHER_SALT}:{d.isoformat()}")
    return _weather_cache[d]


def weather_factor(world: Any) -> float:
    """Погодний множник СЕС на sim-час: добова хмарність · повільні коливання (інтерполяція погодинних значень).

    Для ``parabola`` (макет) і ``SIM_PV_WEATHER=false`` — 1 (ясне небо)."""
    st = world.settings
    if getattr(st, "sun_model", "astral") == "parabola" or not getattr(st, "pv_weather", True):
        return 1.0
    now = world.now()
    d = now.date()
    h = now.hour + now.minute / 60.0 + now.second / 3600.0
    i = int(h)
    a, b = (2.0 * _unit(f"{WEATHER_SALT}:{d.isoformat()}:{k}") - 1.0 for k in (i, i + 1))
    wobble = a + (b - a) * (h - i)
    return float(min(1.0, max(0.05, day_cloud_factor(d) * (1.0 + CLOUD_WOBBLE * wobble))))


@register_model("pv")
class Pv(Model):
    def attach(self) -> None:
        self.keys = sorted({k.split("/")[0] for k in self.device.signals if "/" in k})
        self.kwh_today = {k: 0.0 for k in self.keys}
        self.kwh_total = {k: 0.0 for k in self.keys}
        self.day: str | None = None
        self.restart_left = 0.0
        self.was_island = False

    def _cf(self) -> float:
        cf = self.world.flags.get("pv_cf", 1.0)
        return float(cf) if isinstance(cf, (int, float)) else 1.0

    def tick(self, dt_s: float) -> None:
        now = self.world.now()
        day = now.date().isoformat()
        if self.day != day:  # нова доба: лічильник «за день» скидається
            self.kwh_today = {k: 0.0 for k in self.keys}
            self.day = day
        isl = island(self.world)
        if self.was_island and not isl:
            self.restart_left = RESTART_S
        self.was_island = isl
        self.restart_left = max(0.0, self.restart_left - dt_s)
        sun = sun_factor(self.world)
        failed = self.device.fault is not None
        p_total = (
            P_PEAK
            * sun
            * season_factor(self.world)
            * self._cf()
            * weather_factor(self.world)
            * (0.92 + 0.08 * self.r("pv_now"))
        )
        if isl or failed or self.restart_left > 0:
            p_total = 0.0
        p_free = min(INV_MAX_KW, p_total / INV_COUNT)
        p_k = p_free * max(0.0, min(100.0, float(ctl(self.world, "pv_limit_pct")))) / 100.0
        if isl:
            status = ST_BLACKOUT
        elif failed:
            status = ST_FAULT
        elif sun <= 0:
            status = ST_NIGHT
        elif p_free * INV_COUNT < 1.0 or self.restart_left > 0:
            status = ST_START
        else:
            status = ST_ON
        for k in self.keys:
            self.kwh_today[k] += p_k * dt_s / 3600.0
            self.kwh_total[k] += p_k * dt_s / 3600.0
            self.set(f"{k}/p_kw", p_k)
            self.set(f"{k}/status", status)
            self.set(f"{k}/kwh_today", round(self.kwh_today[k], 4))
            self.set(f"{k}/kwh_total", round(self.kwh_total[k], 4))
        self.set("pv_now", p_k * len(self.keys))

    def get_state(self) -> dict[str, Any]:
        return {
            "kwh_today": self.kwh_today,
            "kwh_total": self.kwh_total,
            "day": self.day,
            "restart_left": self.restart_left,
            "was_island": self.was_island,
        }

    def set_state(self, d: dict[str, Any]) -> None:
        self.kwh_today = dict(d.get("kwh_today", self.kwh_today))
        self.kwh_total = dict(d.get("kwh_total", self.kwh_total))
        self.day = d.get("day")
        self.restart_left = float(d.get("restart_left", 0.0))
        self.was_island = bool(d.get("was_island", False))
