"""AC-246, AC-264: Actuator (запис за зміни, інтервал, сторожовий таймер, повтор, запобіжник) і Writer (allowlist)."""

import pytest
from collector.core.errors import WriteError, WriteRefused
from collector.core.live import LiveCache
from helpers import FakeClock, FakeDevice, base_cfg, base_raw

from td_collector_energy import config as cfgmod
from td_collector_energy.actuator import Actuator, Writer
from td_collector_energy.inputs import Inputs
from td_collector_energy.model import Request, W
from td_collector_energy.scenarios import common as c


class Rig:
    def __init__(self, cfg=None):
        self.cfg = cfg or base_cfg()
        self.clock = FakeClock()
        self.live = LiveCache(self.clock)
        self.device = FakeDevice(lambda: self.cfg, self.live, self.clock)
        self.events = []
        self.writer = Writer(
            self.device.write,
            lambda: self.cfg,
            self.live,
            self.clock.now,
            lambda kind, text, level, signal: self.events.append((kind, text, signal)),
        )
        self.act = Actuator(self.writer, lambda: self.cfg, self.live)

    def inp(self):
        return Inputs(self.cfg, self.live, self.clock.now())

    async def apply(self, req):
        return await self.act.apply(req, self.inp())

    def codes(self):
        return [c for c, _v, _t in self.device.writes]


PFC = lambda cos=0.95: Request("pfc", [W("pfc_mode", 1), W("pfc_cos", cos)], "pfc")  # noqa: E731


async def test_writes_only_on_change_and_in_order():  # AC-246
    rig = Rig()
    res = await rig.apply(PFC())
    assert res.written == 2 and rig.codes() == ["energy_control/pfc/mode", "energy_control/pfc/cos_target"]
    rig.clock.advance(20)
    res = await rig.apply(PFC())  # читання назад збігається з бажаним: без записів
    assert res.written == 0 and len(rig.device.writes) == 2
    rig.clock.advance(20)
    res = await rig.apply(PFC(0.97))
    assert res.written == 1 and rig.device.writes[-1][:2] == ("energy_control/pfc/cos_target", 0.97)


async def test_min_write_interval_per_signal():  # AC-246
    rig = Rig()
    await rig.apply(PFC())
    rig.clock.advance(4)
    assert (await rig.apply(PFC(0.97))).written == 0  # < min_write_interval_s 10 с
    rig.clock.advance(7)
    assert (await rig.apply(PFC(0.97))).written == 1


async def test_without_readback_compares_with_last_write():  # AC-246
    rig = Rig()
    await rig.apply(PFC())
    rig.live._last.clear()  # читання назад недоступне
    rig.clock.advance(20)
    assert (await rig.apply(PFC())).written == 0  # однаковий останній запис — не пишемо
    assert (await rig.apply(PFC(0.96))).written == 1


async def test_stale_readback_older_than_own_write_is_not_trusted():  # AC-246
    rig = Rig()
    rig.device.set("pfc_cos", 0.90)
    rig.clock.advance(30)
    await rig.apply(Request("pfc", [W("pfc_cos", 0.95)], "pfc"))
    assert len(rig.device.writes) == 1
    rig.clock.advance(11)
    # читання назад (0,90) старіше за наш запис: не вважаємо, що запис не дійшов
    old = rig.live.get("energy_control/pfc/cos_target")
    rig.live.update([type(old)(old.code, rig.clock.now() - __import__("datetime").timedelta(seconds=12), value=0.90)])
    assert (await rig.apply(Request("pfc", [W("pfc_cos", 0.95)], "pfc"))).written == 0


def bess_req(valid=30):
    return Request(
        "bess",
        [W("bess_sp", 60), W("bess_until", 30), W("bess_valid", valid), W("bess_mode", 2)],
        "peak",
        watchdog="bess_valid",
        refresh_s=10,
    )


async def test_forced_mode_rewritten_every_valid_s_over_3():  # AC-246
    rig = Rig()
    res = await rig.apply(bess_req())
    assert res.written == 4 and rig.codes() == [
        "energy_control/bess/setpoint_kw",
        "energy_control/bess/until_soc",
        "energy_control/bess/valid_s",
        "energy_control/bess/mode",
    ]  # режим — останнім (R-42)
    rig.clock.advance(5)
    assert (await rig.apply(bess_req())).written == 0
    rig.clock.advance(5)  # 10 с: лише сторожовий таймер, решта збігається з читанням назад
    res = await rig.apply(bess_req())
    assert res.written == 1 and rig.codes()[-1] == "energy_control/bess/valid_s"
    rig.clock.advance(10)
    assert (await rig.apply(bess_req())).written == 1
    rig.clock.advance(1)
    assert (await rig.apply(bess_req())).written == 0


async def test_failed_write_retried_third_failure_in_a_row_releases_resource():  # AC-246
    rig = Rig()
    rig.device.fail["energy_control/bess/setpoint_kw"] = 3
    res = await rig.apply(bess_req())
    assert res.written == 0 and not res.failed and rig.device.writes == []  # перша невдача: решту не пишемо (порядок)
    rig.clock.advance(5)
    assert (await rig.apply(bess_req())).written == 0  # повтор не раніше min_write_interval_s
    rig.clock.advance(6)
    assert not (await rig.apply(bess_req())).failed
    rig.clock.advance(11)
    res = await rig.apply(bess_req())
    assert res.failed == ["bess"]  # третя невдача поспіль
    rig.clock.advance(11)
    res = await rig.apply(bess_req())  # лічильник скинуто, пристрій відповідає
    assert res.written == 4 and not res.failed


async def test_success_resets_failure_counter():  # AC-246
    rig = Rig()
    rig.device.fail["energy_control/pfc/mode"] = 2
    for _ in range(2):
        await rig.apply(PFC())
        rig.clock.advance(11)
    assert rig.act.fails["pfc"] == 2
    await rig.apply(PFC())
    assert rig.act.fails["pfc"] == 0


async def test_rate_fuse_stops_automatic_writes():  # AC-246
    cfg = base_cfg(engine={**base_raw()["engine"], "max_writes_per_min": 3})
    rig = Rig(cfg)
    res = await rig.apply(bess_req())
    assert res.rate_exceeded and res.written == 3 and rig.writer.writes_last_min() == 3
    rig.clock.advance(61)
    assert rig.writer.writes_last_min() == 0  # ковзна хвилина


async def test_executor_writes_count_but_do_not_hit_manual_fuse():  # R-52 п.10
    rig = Rig(base_cfg(engine={**base_raw()["engine"], "max_writes_per_min": 3}))
    for _ in range(5):
        await rig.writer.write("qs_cmd", 2)
    assert rig.writer.writes_last_min() == 5  # лічильник рахує все, але `Writer.write` не блокує оператора


async def test_writer_allows_only_configured_codes_and_denies_prefixes():  # AC-264
    rig = Rig()
    assert await rig.writer.write("qs_cmd", 2) == "ok"  # логічне ім'я
    assert await rig.writer.write("energy_control/shed/LP-1/limit_pct", 50) == "ok"  # shed[].signal
    assert await rig.writer.write("ventilation/units/RV-01/mode", None, "VEL") == "ok"  # bms.*
    for code in (
        "fire/panel/reset",
        "evacuation/x",
        "sprinklers/y",
        "smoke/z",
        "lightning/a",
        "access/b",
        "workcenters/CNC-1/cmd",
        "security/c",
        "yard/gate/open",
    ):
        with pytest.raises(WriteRefused, match="заборонено"):
            await rig.writer.write(code, 1)
    with pytest.raises(WriteRefused, match="поза конфігом"):
        await rig.writer.write("infra/totals/grid_kw", 1)  # вхід, а не сигнал керування
    kinds = [k for k, _t, _s in rig.events]
    assert kinds.count("interlock") == 10
    assert not any(c_ == "fire/panel/reset" for c_, _v, _t in rig.device.writes)


async def test_denied_prefix_wins_even_if_config_lists_it():  # R-60 п.2 в
    raw = base_raw()
    raw["signals"]["evil"] = "fire/panel/reset"
    rig = Rig(cfgmod.parse(raw).config)
    with pytest.raises(WriteRefused, match="fire/"):
        await rig.writer.write("evil", 1)
    res = await rig.apply(Request("bess", [W("fire/panel/reset", 1)], "peak"))
    assert res.refused and "заборонено" in res.refused


async def test_write_refused_by_core_is_reported_not_counted_as_failure():  # R-53 №18
    rig = Rig()

    async def refuse(*a, **k):
        raise WriteRefused("source write disabled: MB-U73-SWB-CMD")

    rig.writer._write = refuse
    res = await rig.apply(PFC())
    assert (
        res.refused == "source write disabled: MB-U73-SWB-CMD" and not res.failed and rig.act.fails.get("pfc", 0) == 0
    )


async def test_write_timeout_is_a_failure():  # R-52 п.3
    rig = Rig(base_cfg(engine={**base_raw()["engine"], "step_timeout_s": 0.01}))

    async def hang(*a, **k):
        import asyncio

        await asyncio.sleep(5)

    rig.writer._write = hang
    with pytest.raises(TimeoutError):
        await rig.writer.write("qs_cmd", 2)
    assert (await rig.apply(PFC())).written == 0 and rig.act.fails["pfc"] == 1


async def test_housekeeping_helpers_use_last_write():
    from helpers import make_env

    rig = Rig()
    await rig.writer.write("pv_limit", 100)
    env = make_env(rig.cfg, rig.clock.now())
    env.inp.live.note_write("energy_control/pv/limit_pct", 100.0, rig.clock.now())
    assert c.written(env, "pv_limit", 100.0)
    assert isinstance(WriteError("x"), Exception)
