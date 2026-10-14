"""Освітлення: групи DALI LT-* і щити LP-1…LP-3 (R-24; SPEC §8.10.4).

Група: рівень за розкладом — зміна → ``level_design`` макета, 06:00–07:00 і 15:30–17:00 → 0,5, ніч → 0,1
(групи «присутність» — 0 без присутності); денне світло (``sun > 0,5``) знижує групи приймання/відвантаження на
20 %. Сигнал ``level`` — у % (0…100), ``p_now = n·126·level`` Вт. Команди HelvarNet (C:11/12/13/14) приходять у
``world.post("lighting", {"group": "LT-CUT"|G, "level": %, "scene": n})`` і перекривають розклад до наступної зміни
періоду. Сценарій S-15 (``lighting_scene[group|"all"]``: ``scene``/``level``/``fault_device``) — явна сцена.
``blackout`` до переключення ATyS у II — аварійний режим (рівні 0, у C:110 аварійні світильники ``0x400``).

``dali_layout()`` — розкладка пристроїв по лініях за правилом bms R-06 (X-65); ``c110_state()`` — відповідь
``C:110`` для адреси ``@c.r.s.d``.

ASSUMPTIONS: присутність — ``world.flags["presence"][<група>]``; аварійний світильник кожної групи — перший за
адресою; сцени 7…16 дають 100 %.
"""
from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.meter import get, island
from iot_sim.models.pv import sun_factor

WATT = 126.0
LINE_CAPACITY = 64
NS_FAULT_LAMP = 0x02
NS_EM_IN_EMERGENCY = 0x400
SCENE_LEVEL = {1: 100, 2: 75, 3: 50, 4: 25, 5: 10, 6: 0}
# (код, щит, n світильників, level_design, control) — bms Додаток A.1, порядок каталогу (G = 1…32)
GROUPS: tuple[tuple[str, str, int, float, str], ...] = (
    ("LT-RCV-1", "LP-1", 4, 1.0, "shift"),
    ("LT-RCV-2", "LP-1", 4, 1.0, "shift"),
    ("LT-RCV-3", "LP-1", 4, 1.0, "shift"),
    ("LT-RCV-4", "LP-1", 4, 1.0, "shift"),
    ("LT-RCV-5", "LP-1", 4, 1.0, "shift"),
    ("LT-RCV-6", "LP-1", 4, 1.0, "shift"),
    ("LT-RCV-7", "LP-1", 4, 1.0, "shift"),
    ("LT-SHEETS", "LP-1", 12, 0.8, "presence"),
    ("LT-HW", "LP-1", 5, 0.7, "presence"),
    ("LT-EDGE", "LP-1", 3, 0.7, "presence"),
    ("LT-PKS", "LP-1", 2, 0.6, "presence"),
    ("LT-CUT", "LP-2", 27, 1.0, "shift"),
    ("LT-EB", "LP-2", 27, 1.0, "shift"),
    ("LT-CNC", "LP-2", 27, 1.0, "shift"),
    ("LT-SORT", "LP-2", 12, 1.0, "shift"),
    ("LT-FAC", "LP-2", 91, 1.0, "shift"),
    ("LT-ASM", "LP-3", 15, 1.0, "shift"),
    ("LT-PRE", "LP-3", 4, 0.8, "presence"),
    ("LT-MAINT", "LP-3", 4, 1.0, "shift"),
    ("LT-PACK", "LP-3", 12, 1.0, "shift"),
    ("LT-POST", "LP-3", 3, 0.8, "presence"),
    ("LT-CMP", "LP-3", 2, 0.5, "presence"),
    ("LT-CHG", "LP-3", 2, 0.5, "presence"),
    ("LT-FG", "LP-3", 12, 0.6, "presence"),
    ("LT-ELEC", "LP-3", 4, 0.5, "presence"),
    ("LT-OUT-1", "LP-3", 4, 1.0, "shift"),
    ("LT-OUT-2", "LP-3", 4, 1.0, "shift"),
    ("LT-OUT-3", "LP-3", 4, 1.0, "shift"),
    ("LT-OUT-4", "LP-3", 4, 1.0, "shift"),
    ("LT-OUT-5", "LP-3", 4, 1.0, "shift"),
    ("LT-OUT-6", "LP-3", 4, 1.0, "shift"),
    ("LT-OUT-7", "LP-3", 4, 1.0, "shift"),
)
BY_CODE = {g[0]: g for g in GROUPS}


def dali_layout(groups: tuple[tuple[str, str, int, float, str], ...] = GROUPS
                ) -> dict[str, list[tuple[int, int, int, int]]]:
    """Склад груп: ``{код: [(router, line, d_from, d_to), …]}`` за правилом bms R-06."""
    out: dict[str, list[tuple[int, int, int, int]]] = {}
    state: dict[str, list[int]] = {}  # щит -> [лінія, використано]
    for code, panel, n, _, _ in groups:
        router = int(panel.rsplit("-", 1)[1])
        line, used = state.setdefault(panel, [1, 0])
        if used > 0 and n > LINE_CAPACITY - used:
            line, used = line + 1, 0
        segs: list[tuple[int, int, int, int]] = []
        left = n
        while left > 0:
            take = min(left, LINE_CAPACITY - used)
            segs.append((router, line, used + 1, used + take))
            used += take
            left -= take
            if used == LINE_CAPACITY and left > 0:
                line, used = line + 1, 0
        state[panel] = [line, used]
        out[code] = segs
    return out


def format_dali(segs: list[tuple[int, int, int, int]]) -> str:
    """``@1.2.3.1-64;@1.2.4.1-27``; один пристрій — ``@1.3.2.7``."""
    return ";".join(f"@1.{r}.{s}.{a}" if a == b else f"@1.{r}.{s}.{a}-{b}" for r, s, a, b in segs)


def addresses(code: str) -> list[str]:
    """Адреси пристроїв групи (відповідь C:164)."""
    return [f"@1.{r}.{s}.{d}" for r, s, a, b in dali_layout()[code] for d in range(a, b + 1)]


def group_of(address: str) -> str | None:
    for code in BY_CODE:
        if address in addresses(code):
            return code
    return None


def c110_state(world, address: str) -> int | None:
    """``C:110``: 0 — норма, ``0x02`` — збій світильника (S-15), ``0x400`` — аварійний (blackout до II);
    ``None`` — пристрій поза складом (``!…=11#``)."""
    code = group_of(address)
    if code is None:
        return None
    model = world.devices[code].model if code in world.devices else None
    mask = 0
    if model is not None and address in getattr(model, "faulty", ()):
        mask |= NS_FAULT_LAMP
    if emergency(world) and address == addresses(code)[0]:
        mask |= NS_EM_IN_EMERGENCY
    return mask


def emergency(world) -> bool:
    """Мережі немає і ATyS ще не в II → аварійне освітлення від АКБ."""
    return island(world) and get(world, "infra/ats/position", 2) != 3


@register_model("lighting")
class Lighting(Model):
    def attach(self) -> None:
        self.code = self.device.code
        self.group = BY_CODE.get(self.code)
        self.panel = self.group is None
        self.period: str | None = None
        self.override: float | None = None  # частка (HelvarNet)
        self.scene = 0
        self.faulty: list[str] = []
        self.flag_faults = False
        if self.group is not None:
            self.n = int(self.device.params.get("n", self.group[2]))

    # --- розклад ---------------------------------------------------------------------
    def _period(self) -> str:
        now, shift = self.world.now(), self.world.shift
        t, workday = now.time(), now.weekday() in shift.workdays
        if workday and shift.in_shift(now):
            return "shift"
        if workday and (6 <= now.hour < 7 or (t >= shift.end and now.hour < 17)):
            return "edge"
        return "night"

    def _scheduled(self, period: str) -> float:
        assert self.group is not None
        _, _, _, design, control = self.group
        if period == "shift":
            level = design
        elif period == "edge":
            level = 0.5
        else:
            presence = (self.world.flags.get("presence") or {}).get(self.code)
            level = 0.0 if control == "presence" and not presence else (1.0 if presence else 0.1)
        if level > 0 and self.code.startswith(("LT-RCV", "LT-OUT")) and sun_factor(self.world) > 0.5:
            level *= 0.8
        return level

    def _scene_flag(self) -> dict[str, Any] | None:
        flags = self.world.flags.get("lighting_scene")
        if not isinstance(flags, dict):
            return None
        return flags.get(self.code) or flags.get("all")

    def _commands(self) -> None:
        stash = self.world.__dict__.setdefault("_lt_stash", {})
        for cmd in self.world.drain("lighting"):
            g = cmd.get("group")
            if isinstance(g, int) and 1 <= g <= len(GROUPS):
                g = GROUPS[g - 1][0]
            stash.setdefault(g, []).append(cmd)
        for cmd in stash.pop(self.code, []):
            if cmd.get("level") is not None:
                self.override = max(0.0, min(100.0, float(cmd["level"]))) / 100.0
            elif cmd.get("scene") is not None:
                self.scene = int(cmd["scene"])
                self.override = SCENE_LEVEL.get(self.scene, 100) / 100.0

    def _apply_scene(self, sc: dict[str, Any] | None) -> float | None:
        if sc is None:
            if self.flag_faults:
                self.faulty, self.flag_faults = [], False
            return None
        fd = sc.get("fault_device")
        if fd and fd not in self.faulty:
            self.faulty.append(fd)
            self.flag_faults = True
        if sc.get("level") is not None:
            return float(sc["level"]) / 100.0
        if sc.get("scene") is not None:
            self.scene = int(sc["scene"])
            return SCENE_LEVEL.get(self.scene, 100) / 100.0
        return None

    # --- тік --------------------------------------------------------------------------
    def tick(self, dt_s: float) -> None:
        if self.panel:
            self._tick_panel()
            return
        self._commands()
        period = self._period()
        if period != self.period:  # зміна розкладу скидає команди HelvarNet
            self.period = period
            self.override = None
        level = self._scheduled(period)
        explicit = self._apply_scene(self._scene_flag())
        if explicit is not None:
            level = explicit
        elif self.override is not None:
            level = self.override
        if emergency(self.world):
            level = 0.0
        pct = round(100.0 * level)
        self.set("level", pct)
        self.set("p_now", round(self.n * WATT * pct / 100.0))
        self.set("scene", self.scene)
        self.set("faults", len(self.faulty))
        self.set("faulty", "; ".join(self.faulty) if self.faulty else "—")

    def _tick_panel(self) -> None:
        total = sum(float(get(self.world, f"lighting/groups/{c}/p_now"))
                    for c, p, *_ in GROUPS if p == self.code)
        self.set("p_now", round(total / 1000.0, 3))
        self.set("state", "fault" if self.device.fault else "ok")

    def get_state(self) -> dict[str, Any]:
        return {"period": self.period, "override": self.override, "scene": self.scene,
                "faulty": self.faulty, "flag_faults": self.flag_faults}

    def set_state(self, d: dict[str, Any]) -> None:
        self.period = d.get("period")
        self.override = d.get("override")
        self.scene = int(d.get("scene", 0))
        self.faulty = list(d.get("faulty", []))
        self.flag_faults = bool(d.get("flag_faults", False))
