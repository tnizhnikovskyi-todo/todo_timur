"""Executor: інтенти оператора — приймання, черга, кроки, верифікація, fail-safe, ідемпотентність (R-52)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from collector.core.errors import WriteRefused
from collector.core.types import Reading
from collector.util.timeutil import parse_iso, to_iso_z
from jsonschema import Draft202012Validator

from . import intents, limits
from .actuator import Writer
from .config import Config
from .inputs import Inputs, text_value
from .interlocks import Ctx, evaluate
from .model import Event
from .reporter import Reporter
from .store import Store
from .timeutil import local

_VALIDATOR = Draft202012Validator(
    json.loads(resources.files("td_collector_energy").joinpath("schemas", "intent.schema.json").read_text("utf-8"))
)
SKEW_WARN_S = 30.0


class Executor:
    def __init__(
        self,
        *,
        store: Store,
        reporter: Reporter,
        writer: Writer,
        live: Any,
        clock: Any,
        get_cfg: Callable[[], Config | None],
        read_signal: Callable[[str], Any] | None,
        emit: Callable[[Event], None],
        write_enabled: Callable[[], bool] | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self.store, self.reporter, self.writer, self.live, self.clock = store, reporter, writer, live, clock
        self.get_cfg, self.read_signal, self.emit = get_cfg, read_signal, emit
        self.write_enabled = write_enabled
        self.log = log or logging.getLogger("collector.plugin.energy_ctl")
        self.running: dict[str, asyncio.Task] = {}  # ресурс → задача
        self.queued = 0
        self.skew_s = 0.0  # server_time конфігу − годинник збирача (поправка `expires_at`)
        self.intents_total = self.blocked_total = 0

    # --- приймання (синхронна частина, ≤ 1 с) ----------------------------------------------------------
    def _result(self, idem: str, res: dict[str, Any], state: str, action_id: int | None = None) -> dict[str, Any]:
        self.store.intents[idem] = {
            "state": state,
            "run_id": res.get("run_id"),
            "result": res,
            "ts": self.clock.now().timestamp(),
            "action_id": action_id,
        }
        return res

    async def accept(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Перевіряє інтент і ставить його в чергу; повертає `result_data` API-26, не чекаючи кроків."""
        if not isinstance(payload, dict):
            return {"accepted": False, "state": "rejected", "reason": "bad schema: payload", "checks": []}
        errs = sorted(_VALIDATOR.iter_errors(payload), key=lambda e: list(e.path))
        if errs:
            e = errs[0]
            where = "/".join(str(x) for x in e.path) or "$"
            return {
                "accepted": False,
                "state": "rejected",
                "reason": f"bad schema: {where}: {e.message}"[:200],
                "checks": [],
            }
        idem = payload["idem"]
        known = self.store.intents.get(idem)
        if known is not None:
            return {**known["result"], "duplicate": True}
        cfg = self.get_cfg()
        now = self.clock.now()
        kind = payload["kind"]
        if kind not in intents.KINDS:
            return self._reject(idem, "unknown kind")
        if cfg is None:
            return self._reject(idem, "немає конфігурації збирача")
        try:
            expires = parse_iso(payload["expires_at"])
        except ValueError:
            return self._reject(idem, "bad schema: expires_at")
        if expires.timestamp() <= now.timestamp() + self.skew_s:
            return self._reject(idem, "expired")
        try:
            params = intents.validate_params(kind, payload["params"], cfg, payload.get("limits"))
            plan = intents.build_plan(kind, params, cfg, now, {})  # перевірка меж (until > now тощо) до черги
        except intents.ParamError as exc:
            return self._reject(idem, f"bad params: {exc}")
        if not plan.steps:  # light_*/vent_*: немає цілей BMS у конфігу (R-42 п.2 `available`)
            return self._reject(idem, "немає цілей BMS")
        refuse = self._safety(cfg, kind)
        if refuse:
            return self._block(idem, refuse, [], payload["action_id"])
        inp = Inputs(cfg, self.live, now)
        rows, blocked, reason = self._checks(kind, params, cfg, inp)
        if blocked:
            return self._block(idem, reason or "Блокування", rows, payload["action_id"])
        res = plan.resource
        if res in self.running and not self.running[res].done():
            return self._reject(idem, f"busy: {res}", rows)
        if self.queued >= limits.MAX_QUEUE:
            return self._reject(idem, "busy: queue", rows)
        run_id = "r-" + idem[:4]
        result = {"accepted": True, "run_id": run_id, "state": "executing", "checks": _brief(rows)}
        self._result(idem, result, "executing", payload["action_id"])
        self.intents_total += 1
        self.queued += 1
        self.running[res] = asyncio.create_task(
            self._run(payload, params, plan, rows, expires), name=f"intent:{run_id}"
        )
        return result

    def _reject(self, idem: str, reason: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"accepted": False, "state": "rejected", "reason": reason, "checks": _brief(rows or [])}

    def _block(self, idem: str, reason: str, rows: list[dict[str, Any]], action_id: int) -> dict[str, Any]:
        self.blocked_total += 1
        res = {"accepted": False, "state": "blocked", "reason": reason, "checks": _brief(rows)}
        self._result(idem, res, "blocked", action_id)
        return res

    def _safety(self, cfg: Config, kind: str) -> str | None:
        """Запобіжники до виконання: `write_enabled` Odoo/збирача, `remote_switching_enabled` (D-46)."""
        if not cfg.write_enabled:
            return "Запис вимкнено: td.energy_control.write_enabled"
        if self.write_enabled is not None and not self.write_enabled():
            return "Запис вимкнено в збирачі (F3D_WRITE_ENABLED)"
        if kind in intents.REMOTE_GATED and not cfg.remote_switching_enabled:
            return "Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled"
        return None

    def _checks(
        self, kind: str, params: dict[str, Any], cfg: Config, inp: Inputs, *, only: tuple[str, ...] | None = None
    ) -> tuple[list[dict[str, Any]], bool, str | None]:
        specs = [{"code": c, "soft": soft} for c, soft in intents.KIND_CHECKS[kind] if only is None or c in only]
        names = set(cfg.inputs) | set(cfg.signals)
        ctx = Ctx.from_inputs(inp, names)
        chp = self.store.data["engine"].get("shared", {}).get("chp", {})
        run_h = (inp.now.timestamp() - float(chp["started_at"])) / 3600.0 if chp.get("started_at") else None
        extra = {
            "soc_limit_pct": params.get("soc_limit_pct"),
            "power_kw": params.get("power_kw"),
            "duration_min": params.get("duration_min"),
            "reserve_pct": cfg.plant["bess_reserve_pct"],
            "setpoint_bar": params.get("setpoint_bar"),
            "fresh_names": intents.KIND_INPUTS.get(kind, ()),
            "codes": {n: inp.code(n) for n in names},
            "lux": self._aisle_lux(cfg, inp),
            "run_h": run_h,
        }
        return evaluate(specs, cfg, ctx, extra)

    def _aisle_lux(self, cfg: Config, inp: Inputs) -> list[float]:
        """Освітленість проходів: сигнал `e_now` сусідній зі `scene_signal` групи з `aisle=true` (дані конфігу)."""
        out = []
        for g in cfg.bms_targets("night", "light"):
            if g.get("aisle"):
                v = inp.v(g["scene_signal"].rsplit("/", 1)[0] + "/e_now")
                if v is not None:
                    out.append(v)
        return out

    # --- виконання ---------------------------------------------------------------------------------------
    def _report(
        self,
        payload: dict[str, Any],
        state: str,
        step: int,
        total: int,
        *,
        result: str | None = None,
        error: str | None = None,
        rows: list[dict[str, Any]] | None = None,
    ) -> None:
        now = self.clock.now()
        self.reporter.add_action(
            {
                "id": payload["action_id"],
                "idem": payload["idem"],
                "state": state,
                "step": step,
                "steps_total": total,
                "ts": to_iso_z(now),
                "result": result[:256] if result else None,
                "error": error,
                "checks": [
                    {"code": r["code"], "state": r["state"], "hard": r["hard"], "detail": r["detail"]}
                    for r in (rows or [])
                ],
            }
        )

    def _finish(
        self,
        payload: dict[str, Any],
        state: str,
        step: int,
        total: int,
        text: str | None,
        rows: list[dict[str, Any]],
        *,
        error: str | None = None,
    ) -> None:
        idem = payload["idem"]
        rec = self.store.intents.get(idem, {})
        rec.update(state=state, ts=self.clock.now().timestamp())
        self.store.intents[idem] = rec
        self.store.save(self.clock.now())
        self._report(payload, state, step, total, result=text, error=error, rows=rows)
        self.log.info("інтент %s %s → %s", payload["kind"], payload["idem"][:8], state)

    async def _write(self, w: Any) -> None:
        """Крок: запис; помилка — один повтор через 1 с; друга — виняток (R-52 п.3)."""
        try:
            await self.writer.write(w.target, w.value, w.text)
        except WriteRefused:
            raise
        except Exception:  # noqa: BLE001
            await self.clock.sleep(1.0)
            await self.writer.write(w.target, w.value, w.text)

    async def _read(self, names: list[str], cfg: Config) -> dict[str, Reading | None]:
        out: dict[str, Reading | None] = {}
        for n in names:
            code = cfg.sig(n) or cfg.inp(n) or n
            try:
                out[n] = await self.read_signal(code) if self.read_signal is not None else None
            except Exception:  # noqa: BLE001
                out[n] = None
            if out[n] is not None and self.live is not None:
                self.live.update([out[n]])
            r = out[n]
            if r is not None and r.value is None and (num := text_value(n, r)) is not None:
                out[n] = dataclasses.replace(r, value=num)  # стан-текст → індекс, щоб предикати верифікації бачили число
        return out

    async def _verify(self, v: intents.Verify, cfg: Config, deadline: float) -> tuple[bool, str | None]:
        """Розове читання раз на секунду до `timeout_s` (і не довше за загальний дедлайн)."""
        end = min(self.clock.monotonic() + v.timeout_s, deadline)
        while True:
            reads = await self._read(v.reads, cfg)
            refused = v.refuse(reads)
            if refused:
                return False, refused
            if v.ok(reads):
                return True, None
            if self.clock.monotonic() >= end:
                return False, None
            await self.clock.sleep(1.0)

    async def _run(
        self,
        payload: dict[str, Any],
        params: dict[str, Any],
        plan0: intents.Plan,
        rows0: list[dict[str, Any]],
        expires: datetime,
    ) -> None:
        kind, res = payload["kind"], plan0.resource
        cfg = self.get_cfg()
        total = len(plan0.steps)
        rows = rows0
        self.queued -= 1
        started = self.clock.monotonic()
        started_wall = self.clock.now()
        exec_to = cfg.engine.exec_timeout_s if cfg else 60.0
        deadline = started + exec_to
        plan = plan0
        failsafe_done = False
        try:
            self._report(payload, "executing", 0, total, rows=rows)
            memo = await self._collect_memo(kind, cfg)
            plan = intents.build_plan(kind, params, cfg, self.clock.now(), memo)  # type: ignore[arg-type]
            if kind in ("light_break", "vent_eco"):
                self.store.data["memo"][plan.resource] = memo.get(plan.resource, {})
            rows, blocked, reason = self._checks(kind, params, cfg, Inputs(cfg, self.live, self.clock.now()))  # type: ignore[arg-type]
            if blocked:
                self._finish(payload, "blocked", 0, total, None, rows, error=reason)
                return
            for i, step in enumerate(plan.steps, 1):
                if self.clock.monotonic() > deadline:
                    raise TimeoutError("перевищено загальний час виконання")
                if step.activating:
                    cfg_now = self.get_cfg()
                    again = self._checks(
                        kind,
                        params,
                        cfg_now,
                        Inputs(cfg_now, self.live, self.clock.now()),  # type: ignore[arg-type]
                        only=intents.RECHECK,
                    )
                    if again[1]:
                        rows = again[0] or rows
                        raise _Blocked(again[2] or "Блокування")
                    safety = self._safety(cfg_now, kind)  # type: ignore[arg-type]
                    if safety:
                        raise WriteRefused(safety)
                for w in step.writes:
                    await self._write(w)
                self._report(payload, "executing", i, total, rows=rows)
            ok, refused = await self._verify(plan.verify, cfg, deadline)  # type: ignore[arg-type]
            if not ok:
                failsafe_done = True
                note = await self._failsafe(plan)
                late = self.clock.monotonic() >= deadline
                what = refused or (
                    "Перевищено загальний час виконання" if late else f"Не підтверджено пристроєм: {plan.verify.what}"
                )
                self._finish(payload, "failed", total, total, None, rows, error=f"{what}. {note}".strip())
                return
            text = plan.summary
            if plan.soft is not None:
                soft_ok, _ = await self._verify(plan.soft, cfg, deadline)  # type: ignore[arg-type]
                if not soft_ok:
                    text += f" (попередження: {plan.soft.what})"
            self._register_override(plan, payload, started_wall)
            self._finish(payload, "done", total, total, text, rows)
        except _Blocked as exc:
            self._finish(payload, "blocked", 0, total, None, rows, error=str(exc))
        except WriteRefused as exc:
            note = await self._failsafe(plan) if not failsafe_done and plan.failsafe else ""
            self._finish(
                payload, "blocked", 0, total, None, rows, error=f"Запис вимкнено: {exc.reason}. {note}".strip()
            )
        except TimeoutError as exc:
            note = await self._failsafe(plan)
            self._finish(payload, "failed", 0, total, None, rows, error=f"{exc or 'таймаут'}. {note}".strip())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            note = await self._failsafe(plan)
            self._finish(
                payload,
                "failed",
                0,
                total,
                None,
                rows,
                error=f"Не виконано: {exc or type(exc).__name__}. {note}".strip(),
            )
        finally:
            if self.running.get(res) is asyncio.current_task():
                del self.running[res]

    async def _failsafe(self, plan: intents.Plan) -> str:
        """Fail-safe (best-effort, по одному повтору, без блокування черги); підсумок — для `result`/`error`."""
        if not plan.failsafe:
            return ""
        bad = 0
        for w in plan.failsafe:
            for attempt in range(2):
                try:
                    await self.writer.write(w.target, w.value, w.text)
                    break
                except Exception:  # noqa: BLE001
                    if attempt:
                        bad += 1
                    else:
                        await self.clock.sleep(1.0)
        if bad:
            self.emit(
                Event(None, "failsafe", f"Fail-safe {plan.kind} не виконано: стан пристрою невідомий", level="warn")
            )
            return "Стан пристрою невідомий: перевірте вручну"
        return "Повернуто безпечний стан"

    async def _collect_memo(self, kind: str, cfg: Config | None) -> dict[str, Any]:
        """Прочитати поточний стан перед записом (для fail-safe/відновлення); для restore — з Store."""
        if cfg is None:
            return {}
        memo: dict[str, Any] = {}
        if kind == "air_setpoint":
            r = (await self._read(["air_sp"], cfg)).get("air_sp")
            if r is not None and r.value is not None:
                memo["air_sp"] = float(r.value)
        elif kind == "light_break":
            codes = [g["scene_signal"] for g in cfg.bms_targets("light_break", "light") if not g.get("aisle")]
            got = await self._read(codes, cfg)
            memo["light"] = {c: float(r.value) for c, r in got.items() if r is not None and r.value is not None}
        elif kind == "vent_eco":
            codes = [u["mode_signal"] for u in cfg.bms_targets("vent_eco", "vent")]
            got = await self._read(codes, cfg)
            memo["vent"] = {c: str(r.text) for c, r in got.items() if r is not None and r.text}
        elif kind in ("light_restore", "vent_restore"):
            res = "light" if kind == "light_restore" else "vent"
            memo[res] = dict(self.store.data["memo"].get(res) or {})
        return memo

    def _register_override(self, plan: intents.Plan, payload: dict[str, Any], started: datetime) -> None:
        """Успішний інтент створює/знімає ручне перекриття ресурсу (R-52 п.8)."""
        now = self.clock.now()
        ov = self.store.data["overrides"]
        res, kind = plan.resource, plan.kind
        if plan.override_s:
            until = started.timestamp() + plan.override_s  # від початку виконання (valid_s рахується з активації)
            ov[res] = {"until": until, "action_id": payload["action_id"], "kind": kind, "idem": payload["idem"]}
            hh = local(datetime.fromtimestamp(until, UTC)).strftime("%H:%M")
            names = {"bess": "BESS", "light": "освітлення", "vent": "вентиляція"}
            self.emit(Event(None, "override", f"ручний режим {names.get(res, res)} до {hh}", level="info"))
        elif kind in ("bess_stop", "light_restore", "vent_restore"):
            ov.pop(res, None)
        shared = self.store.data["engine"].setdefault("shared", {})
        chp = shared.setdefault("chp", {"owner": None, "started_at": None, "stopped_at": None})
        if kind == "chp_start":
            chp.update(owner="manual", started_at=now.timestamp())
        elif kind == "chp_stop":
            chp.update(owner=None, stopped_at=now.timestamp(), started_at=None)

    # --- періодика (з циклу рушія) ---------------------------------------------------------------------
    async def tick(self) -> None:
        """Автовідновлення освітлення/вентиляції по завершенні `duration_min` (R-52 п.8)."""
        cfg = self.get_cfg()
        now = self.clock.now()
        if cfg is None:
            return
        for res, kind, text in (
            ("light", "light_restore", "Освітлення: перерва завершена"),
            ("vent", "vent_restore", "Вентиляція: економ-режим завершено"),
        ):
            item = self.store.data["overrides"].get(res)
            if item is None or now.timestamp() < float(item["until"]):
                continue
            if res in self.running and not self.running[res].done():
                continue
            self.running[res] = asyncio.create_task(self._auto_restore(res, kind, text), name=f"restore:{res}")

    async def _auto_restore(self, res: str, kind: str, text: str) -> None:
        cfg = self.get_cfg()
        try:
            if cfg is None or (self._safety(cfg, kind) is not None):
                return
            memo = await self._collect_memo(kind, cfg)
            plan = intents.build_plan(kind, {}, cfg, self.clock.now(), memo)
            for step in plan.steps:
                for w in step.writes:
                    await self._write(w)
            await self._verify(plan.verify, cfg, self.clock.monotonic() + cfg.engine.exec_timeout_s)
            self.store.data["overrides"].pop(res, None)
            self.emit(Event(None, "auto_release", text))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("автовідновлення %s не вдалося: %s", res, exc)
        finally:
            if self.running.get(res) is asyncio.current_task():
                del self.running[res]

    # --- рестарт (R-52 п.7, AC-248) ------------------------------------------------------------------------
    def recover(self) -> int:
        """Інтенти `executing`, що пережили рестарт, відчитуються `failed` (автопродовження немає)."""
        n = 0
        for idem, rec in self.store.intents.items():
            if rec.get("state") != "executing" or rec.get("action_id") is None:
                continue
            rec.update(state="failed", ts=self.clock.now().timestamp())
            self.reporter.add_action(
                {
                    "id": rec["action_id"],
                    "idem": idem,
                    "state": "failed",
                    "step": 0,
                    "steps_total": 0,
                    "ts": to_iso_z(self.clock.now()),
                    "result": None,
                    "checks": [],
                    "error": "рушій перезапущено під час виконання; стан пристрою невідомий — перевірте",
                }
            )
            n += 1
        return n

    async def stop(self) -> None:
        for t in list(self.running.values()):
            t.cancel()
        await asyncio.gather(*self.running.values(), return_exceptions=True)
        self.running.clear()


class _Blocked(Exception):
    """Жорстка перевірка перед активуючим кроком не пройшла."""


def _brief(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"code": r["code"], "state": r["state"], "detail": r["detail"]} for r in rows]
