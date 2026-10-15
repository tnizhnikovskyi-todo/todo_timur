"""Базовий клас моделей пристроїв (SPEC §8.2.3, §9.1) і пасивна/шумова моделі.

Контракт для воркерів поведінки (``models/<driver>.py``):

* Клас-модель наслідує ``Model``, реєструється ``@register_model("<driver>")`` (ім'я драйвера —
  з ``devices.yaml``/``registry.DRIVER_RULES``). ``iot_sim.models.load_all()`` імпортує всі
  модулі пакета сам — правок у ``models/__init__.py`` не потрібно.
* ``tick(dt_s)`` — крок у sim-секундах (``dt_s`` ≤ 10). Інтеграли множать на ``dt_s`` (``self.dt_min``),
  шум — ``self.r(key)`` (R-00: новий на sim-хвилину). Значення пишуть ``self.set(key, v)``
  (``Signal.set`` поважає ``held_until``); читають ``self.val(key)``.
* Ключ сигналу ``key`` — лист коду (``p_now``, ``pressure_bar``); якщо в пристрої листи
  колізують (``PV-INV``: 8 інверторів) — ``"<інстанс>/<лист>"`` (``PV-INV-3/p_kw``).
* Фаза: ``phase = "source"`` (за замовчуванням) або ``"aggregate"`` (meter, transformer, ats,
  bess — рахуються після джерел; SPEC §8.2.3 п. 2–3).
* Глобальний стан сценаріїв моделі читають із ``self.world.flags`` / ``self.world.inbox``.
* ``fault(reason)`` / ``clear()`` — R-15; перевизначайте ``on_fault``/``on_clear``.
* ``get_state()/set_state()`` — доповнюють знімок (JSON-сумісні дані).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from iot_sim.core.world import Device, Signal, World

SOURCE = "source"
AGGREGATE = "aggregate"
DT_MIN_PER_S = 1.0 / 60.0


def noise_step(v: float, nominal: float, noise: float, r: float, dt_min: float) -> float:
    """R-01: ``v ← v + 0,3·(nominal − v)·dt_min + noise·r·dt_min``."""
    return v + 0.3 * (nominal - v) * dt_min + noise * r * dt_min


class Model:
    driver = "passive"
    phase = SOURCE

    def __init__(self, device: Device, world: World) -> None:
        self.device = device
        self.world = world
        self.dt_s = 0.0
        self.dt_min = 0.0

    # --- життєвий цикл ---------------------------------------------------------------
    def attach(self) -> None:
        """Викликається після створення всіх сигналів пристрою (ініціалізація станів)."""

    def tick(self, dt_s: float) -> None:
        """Один крок моделі; базовий — нічого не робить (пасивна)."""

    def _tick(self, dt_s: float) -> None:
        self.dt_s = dt_s
        self.dt_min = dt_s * DT_MIN_PER_S
        self.tick(dt_s)

    # --- доступ до сигналів ----------------------------------------------------------
    def sig(self, key: str) -> Signal:
        return self.device.signals[key]

    def has(self, key: str) -> bool:
        return key in self.device.signals

    def val(self, key: str, default: Any = None) -> Any:
        s = self.device.signals.get(key)
        return default if s is None else s.value

    def set(self, key: str, value: Any) -> bool:
        s = self.device.signals.get(key)
        return False if s is None else s.set(value, self.world.now())

    def r(self, key: str) -> float:
        """R-00: шум ``r`` ∈ [−1, 1) цього сигналу для поточної sim-хвилини."""
        return self.world.r(self.sig(key).code)

    # --- збої (R-15) -----------------------------------------------------------------
    def fault(self, reason: str = "generic", **kw: Any) -> None:
        self.device.fault = reason
        self.device.state = "offline" if reason == "comm" else "fault"
        self.on_fault(reason, **kw)
        self.world.events.emit("fault", f"Збій {self.device.code}: {reason}",
                               device=self.device.code, payload={"reason": reason, **kw})

    def clear(self) -> None:
        was = self.device.fault
        self.device.fault = None
        self.device.state = "ok"
        self.on_clear()
        if was:
            self.world.events.emit("info", f"Збій {self.device.code} усунено",
                                   device=self.device.code, payload={"reason": was})

    def on_fault(self, reason: str, **kw: Any) -> None:
        """Хук для моделей: p_now → 0, прапори тощо."""

    def on_clear(self) -> None:
        """Хук для моделей: усе назад."""

    def on_release(self, sig: Signal) -> None:
        """Утримання (force) сигналу знято — вичерпано ``hold_s`` або ``release`` (ST-4). Моделі, що рахують сигнал
        щотіку (R-01…R-25), нічого не роблять: наступний тік поверне значення. Пасивна модель — див. ``PassiveModel``."""

    # --- знімок ----------------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        return {}

    def set_state(self, d: dict[str, Any]) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.device.state, "fault": self.device.fault, "extra": self.get_state()}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.device.state = d.get("state", "ok")
        self.device.fault = d.get("fault")
        self.set_state(d.get("extra", {}))


class PassiveModel(Model):
    """Невідомий клас пристрою: тримає номінал (значення з каталогу), нічого не рахує."""

    driver = "passive"

    def on_release(self, sig: Signal) -> None:
        """Ніхто не рахує значення за моделлю, тож після ``hold_s``/``release`` воно повертається до значення каталогу
        (як ``reset``, ``Signal.spec.initial_value()``); інакше примусове значення залишалося б назавжди (ST-4)."""
        sig.value = sig.spec.initial_value()
        sig.ts = self.world.now()


class NoiseModel(Model):
    """Загальна R-01: сигнали з ``nominal`` і ``шум`` коливаються навколо номіналу."""

    driver = "noise"

    def attach(self) -> None:
        self.noisy: list[Signal] = [
            s for s in self.device.signals.values()
            if s.params.get("nominal") is not None and s.params.get("noise") is not None]

    def tick(self, dt_s: float) -> None:
        now = self.world.now()
        for s in self.noisy:
            v = noise_step(float(s.value), s.params["nominal"], s.params["noise"],
                           self.world.r(s.code), self.dt_min)
            s.set(v, now)
