"""S-24 ``fire_evacuation``: пожежна евакуація людей — рух до виходів, проходи через двері виходів, «застряглий».

Розширює каскад ``fire_drill`` (S-07: сирени, стоп вентиляції, клапани, двері, верстати) людьми, яких веде СКУД
(``models.access.AccessCtl``): кожен, хто на об'єкті (за журналом ``ACR-IN``: останній прохід — вхід), після затримки
реакції йде своїм маршрутом (``catalog/evac_routes.json``) до виходу й «проходить» через двері виходу — подія BioStar
(код 4102/4867, ``tna_key=2``, ``door_id`` виходу). Двері виходів: ``EX-IN`` — турнікет ``1`` (``TURN-1``), аварійні
``EX-*`` — ``11…21`` (їх створює міст Odoo ``td_fire_safety_access``; шлях ``door_id`` -> ``td.fire.exit`` — за збігом
кодів). Частина людей (``wrong_exit_pct``, не менше однієї) йде не своїм виходом (найближчий інший), ``stuck``
людей (з пожежної зони) не виходять взагалі: у СКУД вони лишаються «на об'єкті».

Після ``duration_s``: відкат каскаду (``fire_drill`` -> ``restoring``, 30 с), люди, що вийшли, повертаються турнікетом
(``return_people``), а на дверях з'являється 20736 «Двері зачинено на замок» — стенд не лишається розблокованим.
Зупинка (``stop``) робить те саме негайно. Логіка планування — чисті функції (``plan_evacuation``), без asyncio.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field

from iot_sim.core.rng import det
from iot_sim.core.scenarios import SCENARIOS, FireDrill, FireDrillParams, Scenario, ScenarioContext
from iot_sim.models.access import EV_UNLOCKED, READERS, ctl, verify_code

CATALOG = Path(__file__).resolve().parents[2] / "catalog" / "evac_routes.json"
EV_LOCKED = 20736
EXIT_GAP_S = 1.2  # пропускна здатність дверей виходу: одна людина за 1,2 с
REACT_MIN_S, REACT_SPAN_S = 5, 20  # затримка реакції 5…24 с від початку тривоги
RESTORE_S = 30.0  # як у models.facp: відкат каскаду
_catalog: dict[str, Any] | None = None


def catalog() -> dict[str, Any]:
    global _catalog
    if _catalog is None:
        _catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    return _catalog


class FireEvacuationParams(FireDrillParams):
    stuck: int = Field(1, ge=0, le=3)
    wrong_exit_pct: int = Field(15, ge=0, le=100)
    speed_mps: float = Field(1.3, ge=0.5, le=2.5)
    return_people: bool = True


def fire_zone_to_td(zone: str) -> str:
    """``FA-CNC`` -> ``Z-CNC`` (зона сцени за групою пожежних зон)."""
    return "Z-" + zone[3:] if zone.startswith("FA-") else zone


def _dist(a: list[float] | tuple[float, float], b: list[float] | tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def people_on_site(world: Any) -> list[dict[str, Any]]:
    """Люди, чий останній прохід ``ACR-IN`` (``tna_key`` 1/2) — вхід; порядок — за часом входу.

    Якщо людина пройшла технічними дверима (ACR-ELEC/CHG/PAINT/SRV) менше ``dwell_min`` хвилин тому, у копії запису
    ``zone_now`` — зона цих дверей (як у СКУД: access R-08/R-17), і вона йде звідти.
    """
    cat = catalog()
    c = ctl(world)
    c.step()
    now = world.now()
    last: dict[str, dict[str, Any]] = {}
    visit: dict[str, dict[str, Any]] = {}
    for ev in sorted(c.events, key=lambda e: (e["datetime"], e["id"])):
        if not ev["user_id"]:
            continue
        if ev["device"] == "ACR-IN" and ev["tna_key"] in ("1", "2"):
            last[ev["user_id"]] = ev
        elif ev["device"] in cat["readers_zone"]:
            visit[ev["user_id"]] = ev
    by_barcode = {str(p.get("barcode")): p for p in world.people}
    out = []
    for barcode, ev in last.items():
        person = by_barcode.get(barcode)
        if ev["tna_key"] != "1" or person is None:
            continue
        v = visit.get(barcode)
        if (
            v is not None
            and ev["datetime"] <= v["datetime"]
            and (now - v["datetime"]).total_seconds() < cat["dwell_min"] * 60
        ):
            person = dict(person, zone_now=cat["readers_zone"][v["device"]])
        out.append(person)
    return out


def person_key(person: dict[str, Any]) -> str:
    return str(person.get("code") or person["barcode"])


def zone_of(person: dict[str, Any], cat: dict[str, Any]) -> str | None:
    if person.get("zone_now"):
        return str(person["zone_now"])
    return cat["operators"].get(person_key(person).replace("-", "")) or cat["operators"].get(str(person["barcode"]))


def plan_evacuation(
    people: list[dict[str, Any]], params: FireEvacuationParams, cat: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """План евакуації: на кожну людину — зона, призначений і фактичний вихід, момент проходу (с) або ``None``.

    Детермінований (``det`` від коду людини): ті самі люди й параметри — той самий план.
    """
    cat = cat or catalog()
    exits, routes = cat["exits"], cat["routes"]
    fire_zone = fire_zone_to_td(params.zone)
    rows = []
    for person in people:
        key = person_key(person)
        zone = zone_of(person, cat)
        route = routes.get(zone or "")
        if route is None:  # невідома зона: найближчий до воріт вихід (EX-IN) за прямою
            route = {"exit": "EX-IN", "length": 40.0, "path": [[exits["EX-IN"]["x"], exits["EX-IN"]["y"] + 40.0]]}
        rows.append(
            {
                "code": key,
                "barcode": str(person["barcode"]),
                "zone": zone,
                "assigned": route["exit"],
                "exit": route["exit"],
                "length": float(route["length"]),
                "start": route["path"][0],
                "stuck": False,
                "wrong": False,
                "t": None,
            }
        )
    by_det = sorted(rows, key=lambda r: (det(r["code"] + "#stuck"), r["code"]))
    pool = [r for r in by_det if r["zone"] == fire_zone] or by_det  # застрягає той, хто біля вогню
    for row in pool[: params.stuck]:
        row["stuck"] = True
    movers = [r for r in rows if not r["stuck"]]
    wrong = [r for r in movers if det(r["code"] + "#wrong") % 100 < params.wrong_exit_pct]
    if params.wrong_exit_pct and movers and not wrong:  # «у частини людей»: хоча б одна
        wrong = [min(movers, key=lambda r: (det(r["code"] + "#wrong"), r["code"]))]
    for row in wrong:
        others = sorted(
            (c for c in exits if c != row["assigned"]),
            key=lambda c: (_dist(row["start"], [exits[c]["x"], exits[c]["y"]]), c),
        )
        if others:
            alt = others[0]
            row["wrong"], row["exit"] = True, alt
            row["length"] = round(_dist(row["start"], [exits[alt]["x"], exits[alt]["y"]]) * 1.3 + 3.0, 1)
    arrivals = []
    for row in movers:
        react = 3 + REACT_MIN_S + det(row["code"] + "#react") % REACT_SPAN_S
        speed = params.speed_mps * (0.85 + (det(row["code"] + "#speed") % 31) / 100.0)
        arrivals.append((react + row["length"] / speed, row["code"], row))
    free: dict[str, float] = {}
    for t_arr, _code, row in sorted(arrivals, key=lambda a: (a[0], a[1])):
        t = max(t_arr, free.get(row["exit"], 0.0) + EXIT_GAP_S)
        free[row["exit"]] = t
        row["t"] = round(t, 1)
    return rows


class FireEvacuation(Scenario):
    name, title_uk, group, Params = "fire_evacuation", "Пожежна евакуація (навчання)", "safety", FireEvacuationParams
    conflict_groups = frozenset({"safety", "bms"})
    STEPS: ClassVar[list[tuple[int, str, str]]] = FireDrill.STEPS

    def conflicts(self, p: Any) -> Any:
        return {f"zone:{p.zone}"}

    async def run(self, ctx: ScenarioContext) -> dict[str, Any]:
        p: FireEvacuationParams = ctx.params  # type: ignore[assignment]
        world, cat = ctx.world, catalog()
        people = people_on_site(world)
        by_barcode = {str(x["barcode"]): x for x in people}
        plan = plan_evacuation(people, p, cat)
        access = ctl(world)
        doors = cat["doors"]
        t0 = world.clock.epoch()
        ctx.flag(
            "fire_drill",
            {"zone": p.zone, "detector": p.detector, "real": p.real, "t0": world.now().isoformat(), "phase": "active"},
        )
        stuck = [r["code"] for r in plan if r["stuck"]]
        wrong = [r["code"] for r in plan if r["wrong"]]
        ctx.flag(
            "evacuation",
            {"zone": p.zone, "t0": world.now().isoformat(), "people": len(plan), "stuck": stuck, "wrong_exit": wrong},
        )
        movers = sorted((r for r in plan if r["t"] is not None), key=lambda r: (r["t"], r["code"]))
        actions: list[tuple[float, int, str, Any]] = [(at, 0, "step", (s, m)) for at, s, m in self.STEPS]
        actions.append((12.0, 1, "unlock_exits", None))
        actions += [(r["t"], 2, "exit", r) for r in movers]
        if movers:
            actions.append((movers[0]["t"], 3, "step", ("evac_first", "Перший вихід людей")))
            actions.append((movers[-1]["t"], 3, "step", ("evac_done", f"Вийшли {len(movers)} з {len(plan)}")))
        for code in stuck:
            row = next(r for r in plan if r["code"] == code)
            actions.append((30.0, 3, "step", ("stuck", f"Застряг: {code} у зоні {row['zone'] or '—'}")))
        actions.sort(key=lambda a: (a[0], a[1]))
        out: list[dict[str, Any]] = []
        stopped = False
        for at, _prio, kind, data in actions:
            if await ctx.sleep_until(t0 + at):
                stopped = True
                break
            if kind == "step":
                ctx.step(*data)
            elif kind == "unlock_exits":
                self._doors(access, world.now(), [d for c, d in doors.items() if c != "EX-IN"], EV_UNLOCKED)
            else:
                self._pass(access, world.now(), data, by_barcode, doors, "2")
                out.append(data)
        t_restore = max(float(p.duration_s), actions[-1][0] + 5.0)
        if not stopped:
            stopped = await ctx.sleep_until(t0 + t_restore)
        world.flags["fire_drill"]["phase"] = "restoring"
        ctx.step("restoring", "Відновлення нормального стану (30 с)")
        if p.return_people:
            back = sorted(out, key=lambda r: (det(r["code"] + "#back") % 26, r["code"]))
            for row in back:
                at = t_restore + 3 + det(row["code"] + "#back") % 26
                if not stopped and await ctx.sleep_until(t0 + at):
                    stopped = True
                self._pass(access, world.now(), row, by_barcode, doors, "1", entry=True)
        if not stopped:
            stopped = await ctx.sleep_until(t0 + t_restore + RESTORE_S)
        all_doors = [str(i + 1) for i in range(len(READERS))] + [d for c, d in doors.items() if c != "EX-IN"]
        self._doors(access, world.now(), all_doors, EV_LOCKED)
        ctx.step("doors_locked", "Двері зачинено на замок")
        last = max((r["t"] for r in out), default=0.0)
        return {
            "people": len(plan),
            "evacuated": len(out),
            "stuck": stuck,
            "wrong_exit": wrong,
            "last_exit_s": last,
            "exits": {c: sum(1 for r in out if r["exit"] == c) for c in sorted({r["exit"] for r in out})},
            "returned": len(out) if p.return_people else 0,
        }

    @staticmethod
    def _doors(access: Any, when: Any, door_ids: list[str], code: int) -> None:
        for door in door_ids:
            access.add(when, "ACR-IN", code, None, "", door=int(door))

    @staticmethod
    def _pass(
        access: Any,
        when: Any,
        row: dict[str, Any],
        by_barcode: dict[str, Any],
        doors: dict[str, str],
        tna: str,
        entry: bool = False,
    ) -> None:
        """Прохід людини: вихід — через двері вибраного виходу, повернення — турнікетом прохідної."""
        user = by_barcode[row["barcode"]]
        door = int(doors["EX-IN"] if entry else doors[row["exit"]])
        access.add(when, "ACR-IN", verify_code(person_key(user)), user, tna, door=door)


if FireEvacuation not in SCENARIOS:
    SCENARIOS.append(FireEvacuation)

__all__ = ["FireEvacuation", "FireEvacuationParams", "people_on_site", "plan_evacuation"]
