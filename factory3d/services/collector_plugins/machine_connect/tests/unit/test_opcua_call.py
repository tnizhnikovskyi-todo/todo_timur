"""AC-74, AC-103: команди CMD-01 (`call`) і запасна текстова граматика (`write`) на `JobOrderControl`."""

from __future__ import annotations

import pytest
from collector.core.errors import NotSupported, WriteError

STORE = {"method": "StoreAndStart", "job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5}


def signal(plugin, suffix: str):
    return next(s for s in plugin.source.signals if s.code.endswith(suffix))


async def test_store_and_start(ctx, ua_server, opcua_plugin):
    ctx.settings.write_enabled = True
    result = await opcua_plugin.call(signal(opcua_plugin, "/job_cmd"), STORE)
    assert result == {"ReturnStatus": 0}
    method, args = ua_server.calls[-1]
    assert method == "StoreAndStart"
    order = args[0]
    assert order.JobOrderID == "WO00013" and order.Priority == 5
    assert order.Description[0].Text == "WH/MO/00233 WO00013"
    params = {p.ID: p.Value for p in order.JobOrderParameters}
    assert params["PlannedOrderQuantity"].Value == 14.0
    assert params["OrderNumbers"].Value == ["WH/MO/00233"]


async def test_stop(ctx, ua_server, opcua_plugin):
    ctx.settings.write_enabled = True
    result = await opcua_plugin.call(signal(opcua_plugin, "/job_cmd"), {"method": "Stop", "job": "WO00013"})
    assert result == {"ReturnStatus": 0}
    assert ua_server.calls[-1] == ("Stop", ("WO00013", []))


async def test_return_status_error(ctx, ua_server, opcua_plugin):
    ctx.settings.write_enabled = True
    ua_server.ret_status = 3
    with pytest.raises(WriteError, match="ReturnStatus=3"):
        await opcua_plugin.call(signal(opcua_plugin, "/job_cmd"), STORE)


async def test_write_disabled(ctx, ua_server, opcua_plugin):
    with pytest.raises(WriteError, match="write disabled"):
        await opcua_plugin.call(signal(opcua_plugin, "/job_cmd"), STORE)
    with pytest.raises(WriteError, match="write disabled"):
        await opcua_plugin.write(signal(opcua_plugin, "/job_cmd"), None, "Stop;WO00013")
    assert ua_server.calls == []


async def test_bad_command(ctx, ua_server, opcua_plugin):
    ctx.settings.write_enabled = True
    sig = signal(opcua_plugin, "/job_cmd")
    with pytest.raises(WriteError, match=r"bad_command: job: відсутнє"):
        await opcua_plugin.call(sig, {"method": "Store"})
    with pytest.raises(WriteError, match="bad_command"):
        await opcua_plugin.call(sig, {"method": "Explode", "job": "WO1"})
    with pytest.raises(WriteError, match="bad_command"):
        await opcua_plugin.write(sig, None, "Stop")
    assert ua_server.calls == []


async def test_not_job_signal(ctx, ua_server, opcua_plugin):
    ctx.settings.write_enabled = True
    with pytest.raises(NotSupported):
        await opcua_plugin.call(signal(opcua_plugin, "/state"), {"method": "Stop", "job": "WO1"})
    with pytest.raises(NotSupported):
        await opcua_plugin.write(signal(opcua_plugin, "/state"), None, "Stop;WO1")


async def test_write_text_fallback(ctx, ua_server, opcua_plugin):
    ctx.settings.write_enabled = True
    sig = signal(opcua_plugin, "/job_cmd")
    result = await opcua_plugin.write(sig, None, "Stop;WO00013")
    assert result == "ok ReturnStatus=0"
    text_call = ua_server.calls[-1]
    await opcua_plugin.call(sig, {"method": "Stop", "job": "WO00013"})
    assert ua_server.calls[-1] == text_call == ("Stop", ("WO00013", []))
    await opcua_plugin.write(sig, None, "StoreAndStart;WO00013;14;WH/MO/00233;5")
    assert ua_server.calls[-1][1][0].JobOrderID == "WO00013"
