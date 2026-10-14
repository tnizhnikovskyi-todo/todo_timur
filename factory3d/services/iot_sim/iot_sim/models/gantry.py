"""Портал STORETEQ P-500 (GANTRY-1; R-18, R-07; SPEC §8.5 «woodStore API v1»).

Цикл подачі одного листа: idle -> moving (10 с) -> picking (4 с) -> moving (10 с) -> placing (3 с) -> idle;
``stack.qty -= 1``, ``cycles_today += 1``. Авто-``feed``: для кожного з РЦ ``SAW-*``/``NEST-1`` у
стані WORKING раз на ``per_unit`` хв цього РЦ ставиться цикл (R-18; у ``follow_odoo`` — те саме, бо
WORKING = завдання в роботі). API-завдання (``add_job``, API-25) виконуються по листу за цикл.

Публічні дані для протоколу P-03: ``stacks`` (dict за ``id``), ``jobs`` (список), ``events`` (кільце 2000),
``aisles`` ({№: gate_open}; ``set_aisle(n, True)`` -> ``blocked``), ``cycles_total``, ``status()``.
Початкові стоси — ``params["stacks"]`` з ``devices.yaml`` (з ``locations["PLT-*"]`` демо).
"""
from __future__ import annotations

from collections import deque
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model, noise_step
from iot_sim.models.machine import WORKING

FEED_TARGETS = ("SAW-1", "SAW-2", "SAW-3", "NEST-1")
PHASES = (("moving", 10.0), ("picking", 4.0), ("moving", 10.0), ("placing", 3.0))
CYCLE_S = sum(d for _, d in PHASES)


@register_model("gantry")
class Gantry(Model):
    def attach(self) -> None:
        p = self.device.params
        self.stacks: dict[str, dict[str, Any]] = {s["id"]: dict(s) for s in p.get("stacks", [])}
        self.aisles: dict[int, bool] = {n: False for n in range(1, int(p.get("aisles", 9)) + 1)}
        self.jobs: list[dict[str, Any]] = []
        self.events: deque[dict[str, Any]] = deque(maxlen=2000)
        self.state = "idle"
        self.cycles_total = 0
        self.cycles_today = 0
        self.day: Any = None
        self.phase_i = -1
        self.phase_left = 0.0
        self.cur: dict[str, Any] | None = None  # поточний цикл: {"job", "stack"}
        self.demand: dict[str, float] = dict.fromkeys(FEED_TARGETS, 0.0)
        self.queue: list[str] = []
        self.seq = 0
        self.ev_seq = 0
        self.energy_wh = 0.0
        self.energy_shift_wh = 0.0
        self.p_now = 0.0

    # --- API ----------------------------------------------------------------------------
    def event(self, typ: str, message: str, job: str | None = None, stack: str | None = None,
              target: str | None = None) -> None:
        self.ev_seq += 1
        self.events.append({"id": self.ev_seq, "ts": self.world.now().isoformat(), "type": typ, "job": job,
                            "stack": stack, "target": target, "message": message})

    def add_job(self, target: str, sheets: int, product: str, source: str | None = None, lot: str | None = None,
                typ: str = "feed", priority: int = 5, external_ref: str | None = None) -> dict[str, Any]:
        avail = sum(s["qty"] for s in self.stacks.values() if s["product"] == product) if source is None \
            else self.stacks[source]["qty"]
        if sheets > avail:
            raise ValueError("CONFLICT")
        self.seq += 1
        job = {"id": f"wj-{self.seq:05d}", "type": typ, "source": source, "target": target, "sheets": sheets,
               "done": 0, "product": product, "lot": lot, "priority": priority, "external_ref": external_ref,
               "state": "queued", "created": self.world.now().isoformat(), "started": None, "finished": None}
        self.jobs.append(job)
        return job

    def cancel_job(self, job_id: str) -> bool:
        j = next((x for x in self.jobs if x["id"] == job_id), None)
        if j is None:
            return False
        if j["state"] != "active":
            j["state"], j["finished"] = "cancelled", self.world.now().isoformat()
        else:
            j["cancel"] = True  # завершити поточний лист і скасувати
        return True

    def set_aisle(self, n: int, gate_open: bool) -> None:
        if self.aisles.get(n) != gate_open:
            self.aisles[n] = gate_open
            self.event("aisle_opened" if gate_open else "aisle_closed", f"Прохід {n}: ворота "
                       f"{'відкрито' if gate_open else 'закрито'}")

    def status(self) -> dict[str, Any]:
        return {"state": self.state, "vacuum_kpa": self.val("vacuum_kpa"), "cycles_today": self.cycles_today,
                "cycles_total": self.cycles_total,
                "current_job": self.cur["job"]["id"] if self.cur and self.cur["job"] else None,
                "aisles": [{"no": n, "gate_open": o} for n, o in self.aisles.items()]}

    # --- вибір стосу --------------------------------------------------------------------
    @staticmethod
    def aisle_of(stack: dict[str, Any]) -> int:
        return int(stack.get("row", 1))

    def pick_stack(self, job: dict[str, Any]) -> dict[str, Any] | None:
        if job.get("source") and self.stacks[job["source"]]["qty"] > 0:
            return self.stacks[job["source"]]
        cands = [s for s in self.stacks.values() if s["qty"] > 0 and (
            job.get("product") is None or s["product"] == job["product"])]
        return min(cands, key=lambda s: s["id"]) if cands else None

    def _default_product(self) -> str | None:
        st = [s for s in self.stacks.values() if s["qty"] > 0]
        return max(st, key=lambda s: s["qty"])["product"] if st else None

    # --- цикл ---------------------------------------------------------------------------
    def _next_cycle(self) -> bool:
        job = next((j for j in sorted(self.jobs, key=lambda x: -x["priority"])
                    if j["state"] in ("queued", "active")), None)
        if job is None and self.queue:
            tgt = self.queue.pop(0)
            self.seq += 1
            job = {"id": f"wj-{self.seq:05d}", "type": "feed", "source": None, "target": tgt, "sheets": 1,
                   "done": 0, "product": self._default_product(), "lot": None, "priority": 1, "auto": True,
                   "external_ref": None, "state": "queued", "created": self.world.now().isoformat(),
                   "started": None, "finished": None}
            self.jobs.append(job)
        if job is None:
            return False
        stack = self.pick_stack(job)
        if stack is None:
            job["state"], job["finished"] = "error", self.world.now().isoformat()
            self.event("stack_empty", f"Немає листів {job['product']} для {job['target']}", job["id"],
                       None, job["target"])
            return True
        if self.aisles.get(self.aisle_of(stack)):
            self.state = "blocked"
            return True
        if job["state"] == "queued":
            job["state"], job["started"] = "active", self.world.now().isoformat()
            self.event("job_started", f"Завдання {job['id']} розпочато", job["id"], stack["id"], job["target"])
        self.cur = {"job": job, "stack": stack}
        self.phase_i, self.phase_left = 0, PHASES[0][1]
        return True

    def _finish_cycle(self) -> None:
        assert self.cur is not None
        job, stack = self.cur["job"], self.cur["stack"]
        stack["qty"] -= 1
        job["done"] += 1
        self.cycles_today += 1
        self.cycles_total += 1
        self.event("sheet_placed", f"Лист покладено на {job['target']}", job["id"], stack["id"], job["target"])
        if stack["qty"] <= 0:
            self.event("stack_empty", f"Стос {stack['id']} порожній", job["id"], stack["id"], job["target"])
            self.world.events.emit("info", f"Стос {stack['id']} порожній", device=self.device.code,
                                   payload={"type": "stack_empty", "stack": stack["id"]})
        if job.get("cancel") or job["done"] >= job["sheets"]:
            job["state"] = "cancelled" if job.get("cancel") else "done"
            job["finished"] = self.world.now().isoformat()
            self.event("job_finished", f"Завдання {job['id']} завершено", job["id"], stack["id"], job["target"])
        self.cur = None
        self.phase_i = -1

    def tick(self, dt_s: float) -> None:
        w = self.world
        now = w.now()
        if self.day != now.date():
            if self.day is not None:
                self.cycles_today = 0
                self.energy_shift_wh = 0.0
            self.day = now.date()
        in_shift = w.shift.in_shift(now)
        # попит авто-feed: 1 лист за per_unit хв цільового РЦ
        for tgt in FEED_TARGETS:
            dev = w.devices.get(tgt)
            m = dev.model if dev else None
            if m is not None and getattr(m, "current_state", None) == WORKING:
                self.demand[tgt] += dt_s / (60 * getattr(m, "per_unit", 2.2))
                if self.demand[tgt] >= 1:
                    self.demand[tgt] -= 1
                    if tgt not in self.queue:
                        self.queue.append(tgt)
        remaining = dt_s
        if self.device.fault in (None, "comm") and in_shift:
            while remaining > 1e-9:
                if self.cur is None:
                    self.state = "idle"
                    if not self._next_cycle() or self.cur is None:
                        break
                step = min(remaining, self.phase_left)
                self.state = PHASES[self.phase_i][0]
                self.phase_left -= step
                remaining -= step
                if self.phase_left <= 1e-9:
                    self.phase_i += 1
                    if self.phase_i >= len(PHASES):
                        self._finish_cycle()
                    else:
                        self.phase_left = PHASES[self.phase_i][1]
            if self.cur is None and self.state != "blocked":
                self.state = "idle"
        elif self.device.fault not in (None, "comm"):
            self.state = "error"
        else:
            self.state = "idle"
        self._publish(in_shift)

    def _publish(self, in_shift: bool) -> None:
        active = self.state in ("moving", "picking", "placing")
        nom = self.sig("p_now").params["nominal"] if self.has("p_now") else 0.0
        noise = (self.sig("p_now").params["noise"] if self.has("p_now") else 0.0) or 0.0
        if self.state == "error" or not in_shift:
            self.p_now = 0.0
        else:
            target = nom if active else 0.25 * nom
            self.p_now = max(0.0, noise_step(self.p_now or target, target, noise, self.r("p_now"), self.dt_min))
        self.set("p_now", self.p_now)
        wh = self.p_now * 1000 * self.dt_s / 3600
        self.energy_wh += wh
        self.energy_shift_wh += wh
        self.set("kwh_total", self.energy_wh / 1000)
        self.set("kwh_shift", self.energy_shift_wh / 1000)
        self.set("state", self.state)
        self.set("cycles_today", self.cycles_today)
        self.set("job", self.cur["job"]["id"] if self.cur else "")
        if self.has("vacuum_kpa"):
            s = self.sig("vacuum_kpa")
            self.set("vacuum_kpa", noise_step(float(s.value), s.params["nominal"], s.params["noise"],
                                              self.r("vacuum_kpa"), self.dt_min))

    def get_state(self) -> dict[str, Any]:
        return {"stacks": self.stacks, "jobs": self.jobs, "cycles_total": self.cycles_total,
                "cycles_today": self.cycles_today, "seq": self.seq, "energy_wh": self.energy_wh}

    def set_state(self, d: dict[str, Any]) -> None:
        self.stacks = d.get("stacks", self.stacks)
        self.jobs = d.get("jobs", [])
        self.cycles_total = d.get("cycles_total", 0)
        self.cycles_today = d.get("cycles_today", 0)
        self.seq = d.get("seq", 0)
        self.energy_wh = d.get("energy_wh", 0.0)
