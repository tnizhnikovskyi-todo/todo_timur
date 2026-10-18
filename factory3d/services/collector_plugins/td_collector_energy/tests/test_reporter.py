"""AC-266, AC-247: Reporter — пакети, негайна відправка, повтор із бекофом, throttle, буфер при збої (R-53 №1)."""

from helpers import FakeClock, FakeOdoo

from td_collector_energy.reporter import Reporter


def mk(odoo=None, clock=None, seen=None):
    clock = clock or FakeClock()
    odoo = odoo or FakeOdoo({"etag": "x", "config_version": 1})
    rep = Reporter(
        odoo,
        "COL-T",
        clock,
        lambda: {"config_version_applied": 1, "engine": {"mode": "auto"}, "scenarios": {}},
        on_config=(lambda etag, ver: seen.append((etag, ver))) if seen is not None else None,
    )
    return rep, odoo, clock


def action(i, state="executing", step=0):
    return {
        "id": i,
        "idem": f"i{i}",
        "state": state,
        "step": step,
        "steps_total": 4,
        "ts": "t",
        "result": None,
        "error": None,
        "checks": [],
    }


def event(i, text=None, kind="auto_step", scenario="peak"):
    return {
        "event_id": f"e{i}",
        "ts": "t",
        "scenario": scenario,
        "kind": kind,
        "text": text or f"подія {i}",
        "signal": None,
        "value": None,
        "result": "виконано",
    }


async def test_batches_respect_per_request_limits():  # AC-266
    rep, odoo, _ = mk()
    for i in range(200):
        rep.add_action(action(i, "done"))
    for i in range(450):
        rep.add_event(event(i))
    assert await rep.flush()
    sizes = [(len(b["actions"]), len(b["events"])) for b in odoo.states]
    assert sizes == [(100, 200), (100, 200), (0, 50)]  # ≤ 100 дій і ≤ 200 подій за запит
    assert rep.pending() == (0, 0) and all(b["collector"] == "COL-T" for b in odoo.states)
    assert odoo.states[0]["engine"] == {"mode": "auto"} and "sent_at" in odoo.states[0]


async def test_state_report_without_actions_is_a_heartbeat():  # SPEC 7.4
    rep, odoo, _ = mk()
    assert await rep.flush()
    assert len(odoo.states) == 1 and odoo.states[0]["actions"] == [] and odoo.states[0]["events"] == []


async def test_action_change_wakes_the_loop_and_forward_only():  # AC-266
    rep, _odoo, _ = mk()
    assert not rep.wake.is_set()
    rep.add_action(action(1, "executing", 1))
    assert rep.wake.is_set() and rep.due(10)
    rep.add_action(action(1, "done", 4))
    rep.add_action(action(1, "executing", 2))  # назад — ігнорується
    assert rep.actions[1]["state"] == "done"
    rep.add_action(
        action(1, "failed", 4)
    )  # фінальний стан, повторний звіт іншого фінального — приймається буфером (Odoo відхилить)
    assert len(rep.actions) == 1
    await rep.flush()
    assert not rep.wake.is_set() and rep.pending()[0] == 0


async def test_periodic_report_every_10_seconds():  # AC-266
    rep, _odoo, clock = mk()
    await rep.flush()
    assert not rep.due(10)
    clock.advance(10)
    assert rep.due(10)


async def test_retry_with_backoff_on_5xx_and_429():  # AC-266
    odoo = FakeOdoo({"etag": "x", "config_version": 1})
    odoo.down, odoo.status = True, 503
    rep, _o, clock = mk(odoo)
    rep.add_action(action(1, "done"))
    assert not await rep.flush()
    first = rep._next_try - clock.monotonic()
    assert first == 1.0 and rep.pending()[0] == 1 and "503" in rep.last_error
    assert not await rep.flush()  # до next_try Odoo не чіпаємо
    clock.advance(1)
    assert not await rep.flush()
    assert rep._next_try - clock.monotonic() == 2.0  # 1 → 2 → 4 … до 60 с
    for _ in range(8):
        clock.advance(rep._next_try - clock.monotonic())
        await rep.flush()
    assert rep._next_try - clock.monotonic() == 60.0
    odoo.status, odoo.retry_after = 429, 7.0
    clock.advance(60)
    await rep.flush()
    assert rep._next_try - clock.monotonic() == 7.0  # Retry-After
    odoo.down = False
    clock.advance(7)
    assert await rep.flush() and rep.pending() == (0, 0)
    assert rep._backoff == 1.0


async def test_network_error_status_none_is_retried():
    odoo = FakeOdoo({"etag": "x", "config_version": 1})
    odoo.down, odoo.status = True, None
    rep, _o, _c = mk(odoo)
    rep.add_event(event(1))
    assert not await rep.flush() and rep.pending() == (0, 1)


async def test_event_throttle_60s_for_identical_events():  # AC-266
    rep, _odoo, clock = mk()
    assert rep.add_event(event(1, "Контролер у місцевому режимі", "interlock", ""))
    clock.advance(30)
    assert not rep.add_event(event(2, "Контролер у місцевому режимі", "interlock", ""))
    assert rep.add_event(event(3, "Інша подія", "interlock", ""))
    assert rep.add_event(event(4, "Контролер у місцевому режимі", "interlock", "peak"))  # інший сценарій
    clock.advance(31)
    assert rep.add_event(event(5, "Контролер у місцевому режимі", "interlock", ""))
    assert rep.throttled == 1 and len(rep.events) == 4


async def test_buffer_caps_while_odoo_is_down_and_flush_after_recovery():  # AC-247
    odoo = FakeOdoo({"etag": "x", "config_version": 1})
    odoo.down, odoo.status = True, 503
    rep, _o, clock = mk(odoo)
    for i in range(300):
        rep.add_action(action(i, "done"))
    for i in range(1500):
        rep.add_event(event(i))
    assert rep.pending() == (200, 1000)
    assert (rep.dropped_actions, rep.dropped_events) == (100, 500)  # більш старі відкинуто зі лічильником
    assert min(rep.actions) == 100 and rep.events[0]["event_id"] == "e500"
    clock.advance(600)  # «10 хв без Odoo»
    assert not await rep.flush()
    odoo.down = False
    clock.advance(70)
    assert await rep.flush()
    assert rep.pending() == (0, 0)
    assert sum(len(b["actions"]) for b in odoo.states) == 200 and sum(len(b["events"]) for b in odoo.states) == 1000


async def test_bad_request_drops_the_poisoned_batch():  # R-53
    odoo = FakeOdoo({"etag": "x", "config_version": 1})
    odoo.down, odoo.status = True, 400
    rep, _o, _c = mk(odoo)
    rep.add_action(action(1, "done"))
    rep.add_event(event(1))
    assert not await rep.flush()
    assert rep.pending() == (0, 0)  # 400: повторювати нічого


async def test_on_config_callback_gets_etag_and_version():  # SPEC 7.4
    seen = []
    rep, _odoo, _c = mk(seen=seen)
    await rep.flush()
    assert seen == [("x", 1)]
