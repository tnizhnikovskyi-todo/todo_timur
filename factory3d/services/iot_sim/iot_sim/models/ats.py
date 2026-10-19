"""АВР Socomec ATyS p (R-22; регістри Annexe III — SPEC §8.9.4, X-41, X-59, X-67).

Модельна частина blackout: ``position`` (20483: 2 = I мережа, 1 = 0 мертва зона ODT, 3 = II генератор),
``src1_state`` (20486), ``src2_state`` (20487), ``gen_start`` (20484), ``mode`` (20482: 32 при
``amf_master=hgm``, 16 при ``ats``), ``fail_start``; виведені ``src1_ok``/``src2_ok``.

Зв'язок з ретранслятором генератора (API-F, робить окремий воркер) — через хуки:

* ``relay_cb(endpoint, payload)`` — модель кличе його для API-F-02 (``"mains"``), API-F-03
  (``"remote_start"``), API-F-04 (``"load"``); усі виклики пишуться ще й у ``relay_log``;
* ``set_relay_state({"gen_ok": bool, "breaker": "mains"|"gen", "state": str, "p_kw": float})`` — відповідь
  API-F-01 (щосекунди). Поки її не було (``relay_state is None``) діє запасний режим §8.14: генератор готовий
  і переключення — через 15 с після t0, повернення — через 60 с після ``blackout(off)``.

Навантаження генератора в острові (post-хук, після всіх моделей тіку):
``P_genset = min(SIM_GENSET_KW_MAX, max(0, P_crit − chp_kw − pv_now + bess_kw))``; ``genset_load_kw`` з
прапора ``blackout`` замінює формулу; API-F-04 — при зміні ≥ 1 кВт. Таймери (мануал 542 001 D):
1FT 3 с, 2AT 5 с, ODT 3 с, 1RT 180 с, 2CT 180 с, 2ST 30 с.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model
from iot_sim.models.meter import blackout, get, island, p_crit

FT1, AT2, ODT, RT1, CT2, ST2 = 3.0, 5.0, 3.0, 180.0, 180.0, 30.0
FALLBACK_START_S, FALLBACK_RETURN_S, STABILISE_S = 15.0, 60.0, 2.0
POS_0, POS_I, POS_II = 1, 2, 3
IDLE_STATES = (None, "standby", "stop", "stopped", "idle")


@register_model("ats")
class Ats(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        self.clk = 0.0
        self.timers: list[tuple[float, Callable[[], None]]] = []
        self.pos = POS_I
        self.src1 = 2
        self.src2 = 0
        self.gen_start = 0
        self.fail = 0
        self.counter = 17
        self.cur_amf = self._default_amf()
        self.busy = False
        self.outage = False
        self.test = False
        self.cmd_t: float | None = None
        self.b_sched = False
        self.last_sent: float | None = None
        self.genset_kw = 0.0
        self.relay_state: dict[str, Any] | None = None
        self.relay_cb: Callable[[str, dict[str, Any]], None] | None = None
        self.relay_log: list[tuple[str, dict[str, Any]]] = []
        self.world.add_hook("post", self._post)

    # --- ретранслятор ---------------------------------------------------------------
    def set_relay_state(self, state: dict[str, Any] | None) -> None:
        self.relay_state = state

    def _relay(self, endpoint: str, payload: dict[str, Any]) -> None:
        self.relay_log.append((endpoint, payload))
        del self.relay_log[:-200]
        if self.relay_cb is not None:
            self.relay_cb(endpoint, payload)

    # --- параметри ------------------------------------------------------------------
    def _default_amf(self) -> str:
        return str(getattr(self.world.settings, "genset_amf_master", "hgm"))

    def amf(self) -> str:
        """Чинний варіант АВР: ``blackout.amf_master``; після зняття прапора тримається до кінця повернення."""
        return self.cur_amf

    def _refresh_amf(self) -> None:
        b = blackout(self.world)
        if b and b.get("amf_master"):
            self.cur_amf = str(b["amf_master"])
        elif not self.outage and self.pos == POS_I and not self.timers:
            self.cur_amf = self._default_amf()

    def _after(self, delay: float, fn: Callable[[], None]) -> None:
        self.timers.append((self.clk + delay, fn))

    def _info(self, msg: str, kind: str = "info", **payload: Any) -> None:
        self.world.events.emit(kind, msg, device=self.device.code, payload=payload)

    # --- переключення ---------------------------------------------------------------
    def transfer(self, to: int) -> None:
        if self.busy or self.pos == to:
            return
        self.busy = True
        self.pos = POS_0

        def done() -> None:
            self.pos = to
            self.busy = False
            if to == POS_II:
                self.counter += 1
                self._info("АВР: критична шина переключена на генератор (II)", position=to)
            else:
                self._info("АВР: критична шина повернена на мережу (I)", position=to)

        self._after(ODT, done)

    def _gen_ready_fallback(self) -> None:
        self.src2 = 2
        if self.outage or self.test and (self.world.flags.get("genset_test") or {}).get("on_load"):
            self.transfer(POS_II)

    def _order_start(self) -> None:  # варіант B: 1FT після втрати мережі
        if self.outage:
            self.gen_start = 1
            self.cmd_t = self.clk
            self._relay("remote_start", {"on": True})

    def _stop_cmd(self) -> None:  # варіант B: 2CT після повернення
        if self.outage:
            return
        self.gen_start = 0
        self.cmd_t = None
        self._relay("remote_start", {"on": False})
        if self.relay_state is None:
            self.src2 = 0

    def _return_to_mains(self) -> None:
        if not self.outage:
            self.transfer(POS_I)
            if self.relay_state is None:
                self.src2 = 0

    # --- події blackout / тесту -----------------------------------------------------
    def _begin_outage(self) -> None:
        b = blackout(self.world) or {}
        self.outage = True
        self.src1 = 0
        self.fail = 0
        self.b_sched = False
        self.cmd_t = None
        if not b.get("genset", True):
            return
        if self.amf() == "hgm":
            self._relay("mains", {"available": False})
        else:
            self._after(FT1, self._order_start)
        if self.relay_state is None:
            self._after(FALLBACK_START_S, self._gen_ready_fallback)

    def _begin_restore(self) -> None:
        self.outage = False
        self.src1 = 1
        self._after(STABILISE_S, lambda: setattr(self, "src1", 2))
        if self.amf() == "hgm":
            self._relay("mains", {"available": True, "u_v": 400, "f_hz": 50.0})
            if self.relay_state is None:
                self._after(FALLBACK_RETURN_S, self._return_to_mains)
        else:
            self._after(RT1, self._return_to_mains)
            self._after(RT1 + CT2, self._stop_cmd)

    def _begin_test(self) -> None:
        self.test = True
        self._relay("remote_start", {"on": True})
        if self.relay_state is None:
            self._after(FALLBACK_START_S, self._gen_ready_fallback)

    def _end_test(self) -> None:
        self.test = False
        self._relay("remote_start", {"on": False})
        if self.pos == POS_II and not self.outage:
            self.transfer(POS_I)
        if self.relay_state is None and not self.outage:
            self.src2 = 0

    def _poll_relay(self) -> None:
        rs = self.relay_state
        if rs is None:
            return
        gen_ok = bool(rs.get("gen_ok"))
        engine = rs.get("state") not in IDLE_STATES
        self.src2 = 2 if gen_ok else (1 if engine else 0)
        breaker = rs.get("breaker")
        on_load = bool((self.world.flags.get("genset_test") or {}).get("on_load")) and self.test
        hgm = self.amf() == "hgm"
        if self.outage:
            if hgm:
                if breaker == "gen":
                    self.transfer(POS_II)
            elif gen_ok and not self.b_sched:
                self.b_sched = True
                self._after(AT2, lambda: self.transfer(POS_II) if self.outage else None)
            elif not gen_ok and self.cmd_t is not None and not self.fail and self.clk - self.cmd_t >= ST2:
                self.fail = 1
                self._info("АВР: генератор не запустився (FAIL START)", "alarm")
        elif self.test and on_load and gen_ok:
            self.transfer(POS_II)
        elif self.pos == POS_II and hgm and breaker == "mains" and not self.test:
            self.transfer(POS_I)

    # --- тік --------------------------------------------------------------------------
    def tick(self, dt_s: float) -> None:
        self.clk += dt_s
        self._refresh_amf()
        due = sorted((t for t in self.timers if t[0] <= self.clk), key=lambda t: t[0])
        self.timers = [t for t in self.timers if t[0] > self.clk]
        for _, fn in due:
            fn()
        isl = island(self.world)
        if isl and not self.outage:
            self._begin_outage()
        elif not isl and self.outage:
            self._begin_restore()
        test = bool(self.world.flags.get("genset_test")) and not isl
        if test and not self.test:
            self._begin_test()
        elif not test and self.test:
            self._end_test()
        self._poll_relay()
        self.set("position", self.pos)
        self.set("src1_state", self.src1)
        self.set("src2_state", self.src2)
        self.set("src1_ok", 1 if self.src1 > 0 else 0)
        self.set("src2_ok", 1 if self.src2 > 0 else 0)
        self.set("mode", 32 if self.amf() == "hgm" else 16)
        self.set("gen_start", self.gen_start)
        self.set("fail_start", self.fail)

    def _post(self, world: Any, dt_s: float) -> None:
        """R-22: навантаження генератора після того, як усі моделі тіку порахували свої значення."""
        if self.pos != POS_II:
            if self.last_sent is not None:
                self._relay("load", {"kw": 0})
                self.last_sent = None
            self.genset_kw = 0.0
            return
        b = blackout(world) or {}
        override = b.get("genset_load_kw")
        if override is not None:
            want = float(override)
        else:
            kw_max = float(getattr(world.settings, "genset_kw_max", 558.0))
            want = min(
                kw_max,
                max(
                    0.0,
                    p_crit(world)
                    - float(get(world, "infra/totals/chp_kw"))
                    - float(get(world, "infra/totals/pv_now"))
                    + float(get(world, "infra/totals/bess_kw")),
                ),
            )
        self.genset_kw = want
        if self.last_sent is None or abs(want - self.last_sent) >= 1.0:
            self._relay("load", {"kw": round(want, 1)})
            self.last_sent = want

    def get_state(self) -> dict[str, Any]:
        return {
            "pos": self.pos,
            "src1": self.src1,
            "src2": self.src2,
            "counter": self.counter,
            "gen_start": self.gen_start,
            "fail": self.fail,
        }

    def set_state(self, d: dict[str, Any]) -> None:
        self.pos = int(d.get("pos", POS_I))
        self.src1 = int(d.get("src1", 2))
        self.src2 = int(d.get("src2", 0))
        self.counter = int(d.get("counter", 17))
        self.gen_start = int(d.get("gen_start", 0))
        self.fail = int(d.get("fail", 0))
