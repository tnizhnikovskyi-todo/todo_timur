"""СКУД Suprema BioStar 2 (R-28; SPEC §8.12): ACCESS, ACR-*, TURNSTILES, TURN-1; драйвер ``access``.

Спільний контролер ``AccessCtl`` (на ``world._access``) веде журнал подій і розклад доби; його крокує
кожна модель СКУД (ідемпотентно за sim-епохою). Дані для протоколу P-10 — ``AccessCtl.search()``
(``datetime``/``device_id``/``user_id``/``code``, сортування, ``offset`` і ``hint`` — X-50) та ``events``.

* Працівники — ``world.people`` (API-01 ``employees``): ``{"barcode": "OPSAW1", "code": "OP-SAW-1",
  "name", "group"}``; ``det`` береться від ``code`` (``plant/odoo_demo.py:det``; за відсутності — ``barcode``).
* Вхід ``06:40 + det mod 20`` хв: код 4102 (card), якщо ``det % 2 == 0``, інакше 4867 (face), ACR-IN,
  ``tna_key=1``, далі 20480/20992/21248 дверей TURN-1; вихід ``15:30 + det mod 20`` — ``tna_key=2``.
  Події до поточного sim-часу «доганяються» одразу (журнал доби).
* Бригади за змінами ``world.shift.shifts`` (Odoo: календар із кількома змінами; одна зміна — одна бригада A):
  вхід ``початок зміни − 20 хв + det mod 20``, вихід ``кінець зміни + det mod 20``. Для 07:00–15:30 і 15:30–23:00:
  A — 06:40…15:30, B — 15:10…23:00 (+ det mod 20); у будівлі о 15:40 — бригада B і ті з A, хто ще не вийшов.
  До бригади B потрапляє ``N // k`` працівників з найменшим ``det`` (без чергових ролей, вони завжди в A).
* Чергові ролі (ASSUMPTION): OP-W1 -> ACR-ELEC 09:51, OP-W2 -> ACR-PAINT 10:20, OP-W3/OP-W5 -> ACR-CHG,
  OP-W7 -> ACR-SRV (раз на день), бригада A.
* ``world.post("access", {...})`` (S-09) — довільна подія; ``fire_drill`` (крок ``doors``) — 20480 на всіх
  дверях і 26368.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from iot_sim.core.rng import det
from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.facp import drill_view

READERS = ("ACR-IN", "ACR-ELEC", "ACR-CHG", "ACR-PAINT", "ACR-SRV")
DOOR_ID = {c: i + 1 for i, c in enumerate(READERS)}
DEVICE_ID = {c: str(5390001 + i) for i, c in enumerate(READERS)}
EV_CARD, EV_FACE, EV_DENIED = 4102, 4867, 6400
EV_UNLOCKED, EV_OPENED, EV_CLOSED, EV_FIRE = 20480, 20992, 21248, 26368
NO_DEVICE_CODES = frozenset({EV_UNLOCKED, 20736, EV_OPENED, EV_CLOSED, 21504, 21760, EV_FIRE})  # двері/зона
ROLE_ROUTES = (
    ("OP-W1", "ACR-ELEC", (9, 51)),
    ("OP-W2", "ACR-PAINT", (10, 20)),
    ("OP-W3", "ACR-CHG", (11, 15)),
    ("OP-W5", "ACR-CHG", (14, 40)),
    ("OP-W7", "ACR-SRV", (13, 10)),
)
MAX_EVENTS = 20000
DUTY_CODES = frozenset(who for who, _reader, _at in ROLE_ROUTES)  # чергові ролі лишаються в бригаді A
ENTRY_LEAD_MIN = 20  # вхід раніше початку зміни
DEFAULT_WINDOW = (7 * 60, 15 * 60 + 30)  # одна зміна за замовчуванням, хв доби


def verify_code(key: str) -> int:
    """4102 (card) якщо ``det(key) % 2 == 0``, інакше 4867 (face)."""
    return EV_CARD if det(key) % 2 == 0 else EV_FACE


def shift_windows(world: Any) -> list[tuple[int, int]]:
    """Вікна змін у хвилинах доби: ``world.shift.shifts`` (кілька змін) або одна зміна ``start``–``end`` календаря."""
    cal = world.shift
    wins = [(a.hour * 60 + a.minute, b.hour * 60 + b.minute) for a, b in cal.shifts] or [
        (cal.start.hour * 60 + cal.start.minute, cal.end.hour * 60 + cal.end.minute)
    ]
    return [(a, b) for a, b in wins if b > a] or [DEFAULT_WINDOW]


def assign_crews(keys: list[str], n: int) -> dict[str, int]:
    """Бригада кожного працівника: 0 — A (усі при ``n = 1``, чергові ролі), 1…n−1 — по ``len(keys) // n`` людей з
    найменшим ``det`` серед решти (детермінований «жереб», склад не залежить від порядку списку)."""
    crew = dict.fromkeys(keys, 0)
    if n <= 1:
        return crew
    free = sorted((k for k in keys if k not in DUTY_CODES), key=lambda k: (det(k), k))
    size = len(keys) // n
    for j in range(1, n):
        for k in free[(j - 1) * size : j * size]:
            crew[k] = j
    return crew


class AccessCtl:
    def __init__(self, world: Any) -> None:
        self.world = world
        self.events: list[dict[str, Any]] = []
        self.seq = 0
        self.day: Any = None
        self.schedule: list[tuple[float, dict[str, Any]]] = []
        self.ptr = 0
        self.on_site = 0
        self.people_key: tuple[Any, ...] | None = None  # (склад людей, вікна змін), з яких побудовано розклад
        self.inside: set[str] = set()  # user_id (barcode) тих, хто за журналом зараз у будівлі
        self.last_ts: float | None = None  # мітка останньої виданої події розкладу (для догону без дублів)
        self.epoch_key: tuple[float, int] | None = None
        self.drill_id: float | None = None

    # --- події --------------------------------------------------------------------------
    def add(
        self,
        when: datetime,
        device: str,
        code: int,
        user: dict[str, Any] | None = None,
        tna: str = "",
        door: int | None = None,
    ) -> dict[str, Any]:
        self.seq += 1
        no_dev = code in NO_DEVICE_CODES  # події дверей/зони не належать зчитувачу (AC-16: 35 подій ACR-IN)
        ev = {
            "id": self.seq,
            "datetime": when,
            "device": None if no_dev else device,
            "device_id": None if no_dev else DEVICE_ID.get(device),
            "reader": device,
            "user_id": user.get("barcode") if user else None,
            "name": user.get("name") if user else None,
            "group": user.get("group") if user else None,
            "code": code,
            "tna_key": tna,
            "door_id": door if door is not None else DOOR_ID.get(device),
            "hint": f"h{self.seq}",
        }
        self.events.append(ev)
        if len(self.events) > MAX_EVENTS:
            del self.events[: len(self.events) - MAX_EVENTS]
        uid = ev["user_id"]
        if device == "ACR-IN" and tna == "1" and not no_dev:
            if uid is None or uid not in self.inside:  # повторний вхід того, хто вже всередині, не рахуємо вдруге
                self.on_site += 1
            if uid is not None:
                self.inside.add(uid)
        elif device == "ACR-IN" and tna == "2" and not no_dev:
            if uid is None or uid in self.inside:
                self.on_site = max(0, self.on_site - 1)
            self.inside.discard(uid)
        # контракт з BioStar (protocols/biostar_api): payload {user_id,event_code,door,tna_key}
        self.world.events.emit(
            "access",
            f"Доступ {code}: {device}",
            device=device,
            payload={
                "user_id": ev["user_id"],
                "event_code": code,
                "door": str(ev["door_id"] or ""),
                "tna_key": tna,
                "ts": when.isoformat(),
                "code": code,
                "user": ev["user_id"],
            },
        )
        return ev

    def _doors(self, when: datetime, device: str) -> None:
        for off, code in ((1, EV_UNLOCKED), (2, EV_OPENED), (6, EV_CLOSED)):
            self.add(when + timedelta(seconds=off), device, code)

    # --- розклад доби -------------------------------------------------------------------
    def _people_key(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted((p.get("code") or p.get("barcode") or "", p.get("barcode") or "") for p in self.world.people)
        )

    def _rebuild_key(self) -> tuple[Any, ...]:
        """Від чого залежить розклад: склад людей і вікна змін (бригади)."""
        return (self._people_key(), tuple(shift_windows(self.world)))

    def _redundant(self, it: dict[str, Any]) -> bool:
        """Вхід того, хто вже всередині, і вихід того, кого всередині немає (після перебудови розкладу): не видаємо."""
        u = it["user"]
        if not u or it["device"] != "ACR-IN" or it["tna"] not in ("1", "2"):
            return False
        return (u.get("barcode") in self.inside) == (it["tna"] == "1")

    def _build_day(self, now: datetime) -> None:
        w = self.world
        self.schedule, self.ptr, self.people_key = [], 0, self._rebuild_key()
        if now.weekday() not in w.shift.workdays:
            return
        base = datetime.combine(now.date(), datetime.min.time(), tzinfo=now.tzinfo)
        people = list(w.people)
        by_code = {p.get("code") or p.get("barcode"): p for p in people}
        items: list[tuple[datetime, dict[str, Any]]] = []
        windows = shift_windows(w)
        crews = assign_crews([p.get("code") or p["barcode"] for p in people], len(windows))
        for p in people:
            key = p.get("code") or p["barcode"]
            m = det(key) % 20
            code = verify_code(key)
            start, end = windows[crews[key]]
            t_in = max(0, start - ENTRY_LEAD_MIN) + m
            t_out = min(end + m, 24 * 60 - 1)  # вихід не переходить у наступну добу
            items.append((base + timedelta(minutes=t_in), {"device": "ACR-IN", "user": p, "code": code, "tna": "1"}))
            items.append((base + timedelta(minutes=t_out), {"device": "ACR-IN", "user": p, "code": code, "tna": "2"}))
        for who, reader, (hh, mm) in ROLE_ROUTES:
            p = by_code.get(who)
            if p is not None:
                items.append(
                    (
                        base + timedelta(hours=hh, minutes=mm),
                        {"device": reader, "user": p, "code": verify_code(who), "tna": ""},
                    )
                )
        for t, it in list(items):  # двері після кожної події зчитувача: розклад лишається впорядкованим
            for off, code in ((1, EV_UNLOCKED), (2, EV_OPENED), (6, EV_CLOSED)):
                items.append(
                    (t + timedelta(seconds=off), {"device": it["device"], "user": None, "code": code, "tna": ""})
                )
        items.sort(key=lambda t: t[0])
        self.schedule = [(t.timestamp(), dict(it, when=t)) for t, it in items]

    def step(self) -> None:
        w = self.world
        epoch = w.clock.epoch()
        key = (epoch, w.tick_count)
        if self.epoch_key == key:
            return
        self.epoch_key = key
        now = w.now()
        if self.day != now.date() or self.people_key != self._rebuild_key():  # нова доба, склад людей або вікна змін
            if self.day != now.date():
                self.last_ts, self.on_site = None, 0
                self.inside.clear()
            self.day = now.date()
            self._build_day(now)
            # уже видані події не дублюємо; нічого не видано — ptr 0 (минулі входи доганяються одразу)
            self.ptr = sum(1 for t, _ in self.schedule if self.last_ts is not None and t <= self.last_ts)
        while self.ptr < len(self.schedule) and self.schedule[self.ptr][0] <= epoch:
            self.last_ts, it = self.schedule[self.ptr]
            self.ptr += 1
            if not self._redundant(it):
                self.add(it["when"], it["device"], it["code"], it["user"], it["tna"])
        for cmd in w.drain("access"):
            self._manual(cmd, now)
        view = drill_view(w)
        did = view["id"] if view and view["steps"]["doors"] else None
        if did is not None and did != self.drill_id:
            for r in READERS:
                self.add(now, r, EV_UNLOCKED)
            self.add(now, "ACR-IN", EV_FIRE)
        self.drill_id = did

    def _manual(self, cmd: dict[str, Any], now: datetime) -> None:
        device = cmd.get("device") or "ACR-IN"
        people = self.world.people
        user = next((p for p in people if p.get("barcode") == cmd.get("user")), None)
        if user is None and people and not cmd.get("user"):
            user = people[self.world.minute % len(people)]
        code = int(cmd.get("code") or EV_CARD)
        tna = str(cmd.get("tna_key") if cmd.get("tna_key") is not None else "1")
        ev = self.add(now, device, code, user, tna)
        if cmd.get("door_open", True) and code != EV_DENIED:
            self._doors(ev["datetime"], device)

    # --- пошук (API-45) -----------------------------------------------------------------
    def search(
        self,
        device_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        user_id: str | None = None,
        code: int | None = None,
        descending: bool = False,
        limit: int = 100,
        offset: int = 0,
        hint: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [
            e
            for e in self.events
            if (device_id is None or device_id in (e["device"], e["device_id"]))
            and (start is None or e["datetime"] >= start)
            and (end is None or e["datetime"] <= end)
            and (user_id is None or e["user_id"] == user_id)
            and (code is None or e["code"] == code)
        ]
        rows.sort(key=lambda e: (e["datetime"], e["id"]), reverse=descending)
        total = len(rows)
        if hint is not None:
            idx = next((i for i, e in enumerate(rows) if e["hint"] == hint), -1)
            rows = rows[idx + 1 :]
        else:
            rows = rows[offset:]
        return rows[:limit], total


def ctl(world: Any) -> AccessCtl:
    c = getattr(world, "_access", None)
    if c is None:
        c = world._access = AccessCtl(world)
    return c


@register_model("access")
class Access(Model):
    @property
    def ctl(self) -> AccessCtl:
        return ctl(self.world)

    def tick(self, dt_s: float) -> None:
        c = self.ctl
        c.step()
        code = self.device.code
        if code == "ACCESS":
            self.set("events", len(c.events))
        elif code == "TURNSTILES":
            self.set("on_site", c.on_site)
        elif code in READERS:
            last = next((e for e in reversed(c.events) if e["device"] == code), None)
            if last is not None:
                self.set("last_event", last["code"])

    def get_state(self) -> dict[str, Any]:
        if self.device.code != "ACCESS":
            return {}
        c = self.ctl
        return {
            "seq": c.seq,
            "on_site": c.on_site,
            "ptr": c.ptr,
            "last_ts": c.last_ts,
            "day": c.day.isoformat() if c.day else None,
            "events": [dict(e, datetime=e["datetime"].isoformat()) for e in c.events],
        }

    def set_state(self, d: dict[str, Any]) -> None:
        if self.device.code != "ACCESS" or not d:
            return
        c = self.ctl
        c.seq = d.get("seq", 0)
        c.events = [dict(e, datetime=datetime.fromisoformat(e["datetime"])) for e in d.get("events", [])]
        c.day = datetime.fromisoformat(d["day"]).date() if d.get("day") else None
        if c.day:
            c._build_day(self.world.now())
            c.ptr = d.get("ptr", 0)
            c.last_ts = d.get("last_ts", c.schedule[c.ptr - 1][0] if 0 < c.ptr <= len(c.schedule) else None)
        c.on_site = d.get("on_site", 0)
        last: dict[str, str] = {}  # хто всередині — за останнім проходом ACR-IN у журналі
        for e in sorted((e for e in c.events if e["device"] == "ACR-IN" and e["user_id"]), key=lambda e: e["id"]):
            if e["tna_key"] in ("1", "2"):
                last[e["user_id"]] = e["tna_key"]
        c.inside = {u for u, k in last.items() if k == "1"}
