"""Заморожені контракти C-39 (`odoo_addons/td_energy_control/contracts/`): збирач читає й віддає рівно ці ключі."""

from helpers import INTENT_SIGNAL, boot_ready, contract, intent

from td_collector_energy.executor import _VALIDATOR


def test_contract_intent_validates_against_schema():
    assert list(_VALIDATOR.iter_errors(contract("api26_intent.json"))) == []
    bad = {**contract("api26_intent.json"), "v": 2}
    assert list(_VALIDATOR.iter_errors(bad))


async def test_result_data_shapes_equal_contract_keys():
    h = await boot_ready()
    accepted = await h.plugin.call(INTENT_SIGNAL, intent("qs_open", now=h.clock.now()))
    assert set(accepted) == set(contract("api26_result_accepted.json"))
    h2 = await boot_ready(ats_lock=0)
    blocked = await h2.plugin.call(INTENT_SIGNAL, intent("qs_close", now=h2.clock.now()))
    assert set(blocked) == set(contract("api26_result_blocked.json"))
    assert blocked["checks"][0].keys() == contract("api26_result_blocked.json")["checks"][0].keys()
    rejected = await h.plugin.call(
        INTENT_SIGNAL, intent("bess_charge", {"power_kw": 300}, now=h.clock.now(), idem="r1")
    )
    assert set(rejected) == set(contract("api26_result_rejected.json"))
    assert rejected["reason"] == contract("api26_result_rejected.json")["reason"]  # «bad params: power_kw > 200»
    await h.executor.stop()


async def test_action_report_keys_equal_contract():
    from helpers import run_intent

    h = await boot_ready()
    _res, action = await run_intent(h, "qs_close")
    ref = contract("api25_state_request.json")["actions"][0]
    assert set(action) == set(ref) and set(action["checks"][0]) == set(ref["checks"][0])


def test_event_dict_keys_equal_contract():
    from datetime import UTC, datetime

    from td_collector_energy.model import Event

    ev = Event("peak", "auto_step", "BESS · розряд 62 кВт", signal="energy_control/bess/mode", value=2).to_dict(
        datetime(2026, 10, 14, 6, tzinfo=UTC)
    )
    assert set(ev) == set(contract("api25_state_request.json")["events"][0])
    assert len(ev["event_id"]) == 32  # uuid4().hex
