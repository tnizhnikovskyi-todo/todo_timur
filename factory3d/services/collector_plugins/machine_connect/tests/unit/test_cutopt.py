"""AC-78, AC-79: адаптер `cutopt` (команди CMD-03: upload / status / release / mpr)."""

from __future__ import annotations

import logging

import pytest
from collector.core.errors import NotSupported, WriteError
from f3d_collector_mc.cutopt import CutOptAdapter

TOKEN = "9f2c41aa07b3e5d1"
UPLOAD = {"op": "upload", "map": 12, "token": TOKEN}


async def connect(rest_plugin, app):
    plugin = rest_plugin(app, "cutopt")
    await plugin.connect()
    return plugin


def cmd(plugin):
    return next(s for s in plugin.source.signals if s.code.endswith("/cmd"))


def events(ctx, kind: str) -> list[dict]:
    return [e.payload for e in ctx.events if e.route == "mc_cutopt" and e.payload["kind"] == kind]


async def test_upload_flow(ctx, cutopt_app, fake_odoo_export, rest_plugin, caplog):
    caplog.set_level(logging.DEBUG)
    plugin = await connect(rest_plugin, cutopt_app)
    assert isinstance(plugin.adapter, CutOptAdapter)
    result = await plugin.call(cmd(plugin), UPLOAD)
    assert result == {"job_id": "cj-1", "state": "optimizing", "eta_s": 5}
    path, query, auth = fake_odoo_export.calls[0]
    assert path == "/f3d/machine/cutmap/12/export" and query == {"t": TOKEN}
    assert auth == f"Bearer {ctx.settings.collector_token}"
    up = cutopt_app.uploads[0]
    assert up["parts"].decode("utf-8") == fake_odoo_export.body["parts_csv"]  # побайтово
    assert up["parts_filename"] == "parts.csv" and up["parts_content_type"] == "text/csv; charset=utf-8"
    assert (up["material"], up["sheet"], up["external_ref"], up["machine"]) == (
        "DSP16-ANT",
        "2800x2070x16",
        "WH/MO/00233",
        "SAW-1",
    )
    jobs = events(ctx, "job")
    assert len(jobs) == 1 and jobs[0]["map"] == "КР/00012" and jobs[0]["job"]["job_id"] == "cj-1"
    assert jobs[0]["source"] == "REST-CUTOPT-T"
    assert ctx.settings.collector_token not in caplog.text
    assert fake_odoo_export.body["parts_csv"] not in caplog.text
    await plugin.disconnect()


async def test_upload_export_gone(ctx, cutopt_app, fake_odoo_export, rest_plugin):
    plugin = await connect(rest_plugin, cutopt_app)
    for status in (410, 403):
        fake_odoo_export.status = status
        with pytest.raises(WriteError, match=f"export {status}"):
            await plugin.call(cmd(plugin), UPLOAD)
    fake_odoo_export.status = 200
    cutopt_app.reject_next = True
    with pytest.raises(WriteError, match="422: parts: empty list"):
        await plugin.call(cmd(plugin), UPLOAD)
    assert events(ctx, "job") == []
    await plugin.disconnect()


async def test_status_planned(ctx, cutopt_app, fake_odoo_export, rest_plugin):
    plugin = await connect(rest_plugin, cutopt_app)
    await plugin.call(cmd(plugin), UPLOAD)
    status = {"op": "status", "job": "cj-1"}
    result = await plugin.call(cmd(plugin), status)
    assert result == {"job_id": "cj-1", "state": "optimizing", "sheets": None, "waste_pct": None}
    assert events(ctx, "plan") == []
    cutopt_app.advance("cj-1", "planned", plan={"sheets": 7, "waste_pct": 11.4})
    before = len(events(ctx, "job"))
    result = await plugin.call(cmd(plugin), status)
    assert result == {"job_id": "cj-1", "state": "planned", "sheets": 7, "waste_pct": 11.4}
    assert len(events(ctx, "job")) == before + 1
    plans = events(ctx, "plan")
    assert len(plans) == 1 and plans[0]["job_id"] == "cj-1" and plans[0]["map"] == "КР/00012"
    assert plans[0]["plan"]["total_sheets"] == 7
    assert await plugin.write(cmd(plugin), None, "status;cj-1") == "planned 7 11.4"
    await plugin.disconnect()


async def test_release(ctx, cutopt_app, fake_odoo_export, rest_plugin):
    plugin = await connect(rest_plugin, cutopt_app)
    await plugin.call(cmd(plugin), UPLOAD)
    release = {"op": "release", "job": "cj-1", "machine": "SAW-1", "priority": 5}
    result = await plugin.call(cmd(plugin), release)
    assert result == {"job_id": "cj-1", "state": "released", "job_order_id": "cj-1"}
    assert events(ctx, "job")[-1]["job"]["state"] == "released"
    post = next(c for c in cutopt_app.calls if c[1] == "/jobs/cj-1/release")
    assert post[3] == {"machine": "SAW-1", "priority": 5}
    assert await plugin.write(cmd(plugin), None, "release;cj-1;SAW-1;5") == "released cj-1"
    await plugin.disconnect()


async def test_mpr(ctx, cutopt_app, fake_odoo_export, rest_plugin):
    plugin = await connect(rest_plugin, cutopt_app)
    await plugin.call(cmd(plugin), UPLOAD)
    cutopt_app.advance("cj-1", "released", mpr={"P001": "A" * 4096, "BIG": "B" * (200 * 1024 + 1)})
    result = await plugin.call(cmd(plugin), {"op": "mpr", "job": "cj-1", "part": "P001"})
    assert result == {"part": "P001", "size_kb": 4}
    mpr = events(ctx, "mpr")
    assert len(mpr) == 1 and mpr[0]["part"] == "P001" and mpr[0]["job_id"] == "cj-1" and len(mpr[0]["text"]) == 4096
    assert await plugin.call(cmd(plugin), {"op": "mpr", "job": "cj-1", "part": "P002"}) == {
        "part": "P002",
        "size_kb": None,
    }
    assert await plugin.write(cmd(plugin), None, "mpr;cj-1;P002") == "no mpr"
    with pytest.raises(WriteError, match="mpr too large"):
        await plugin.call(cmd(plugin), {"op": "mpr", "job": "cj-1", "part": "BIG"})
    assert len(events(ctx, "mpr")) == 1
    await plugin.disconnect()


async def test_bad_command_and_not_supported(ctx, cutopt_app, rest_plugin):
    plugin = await connect(rest_plugin, cutopt_app)
    n = len(cutopt_app.calls)
    with pytest.raises(WriteError, match="bad_command"):
        await plugin.call(cmd(plugin), {"op": "upload", "map": 12})
    with pytest.raises(WriteError, match="bad_command"):
        await plugin.call(cmd(plugin), {"op": "upload", "map": 12, "token": "XYZ"})
    assert len(cutopt_app.calls) == n
    other = type(cmd(plugin))(**{**cmd(plugin).__dict__, "address": {"path": "/x"}})
    with pytest.raises(NotSupported):
        await plugin.call(other, UPLOAD)
    assert await plugin.poll([]) == []
    await plugin.disconnect()
