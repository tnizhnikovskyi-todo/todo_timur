"""CLI: run | check-config | dump-config | test-source <code> | drain-buffer (SPEC §8.1.1)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from pydantic import ValidationError

from collector.core.app import Collector
from collector.core.buffer import Buffer
from collector.core.config import EXIT_CONFIG, Settings
from collector.core.logging_conf import setup_logging
from collector.core.odoo_client import OdooClient, OdooError, Pusher
from collector.core.registry import load_plugins, parse_config
from collector.util.timeutil import to_iso_z

_SECRET_KEYS = ("password", "token", "secret")


def _strip_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_secrets(v) for k, v in obj.items() if not any(s in k.lower() for s in _SECRET_KEYS)}
    if isinstance(obj, list):
        return [_strip_secrets(v) for v in obj]
    return obj


def _client(s: Settings) -> OdooClient:
    return OdooClient(
        s.odoo_url, s.collector_token, collector=s.collector_code, ca=s.odoo_ca, skew_warn_s=s.clock_skew_warn_s
    )


async def check_config(s: Settings) -> int:
    client = _client(s)
    try:
        await client.health()
        await client.config(None)
    except OdooError as exc:
        print(f"check-config failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()
    print("ok")
    return 0


async def dump_config(s: Settings) -> int:
    client = _client(s)
    try:
        data = await client.config(None)
    except OdooError as exc:
        print(f"dump-config failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()
    print(json.dumps(_strip_secrets(data), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


async def test_source(s: Settings, code: str) -> int:
    import logging

    from collector.core.allowlist import Allowlist
    from collector.core.config import resolve_secret
    from collector.core.metrics import Metrics
    from collector.core.scheduler import Emitter
    from collector.plugins.base import PluginContext

    client = _client(s)
    try:
        data = await client.config(None)
    except OdooError as exc:
        print(f"test-source failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()
    sources = {x.code: x for x in parse_config(data or {})}
    src = sources.get(code)
    if src is None:
        print(f"source {code} not found", file=sys.stderr)
        return 1
    cls = load_plugins().get(src.type)
    if cls is None:
        print(f"plugin {src.type} not installed", file=sys.stderr)
        return 1
    errs = cls.validate(src)
    if errs:
        print("schema: " + "; ".join(errs), file=sys.stderr)
        return 1
    metrics = Metrics()
    emitter = Emitter(Buffer(s.buffer_dir / "buffer.sqlite", s.buffer_max_mb), {}, metrics)
    ctx = PluginContext(
        settings=s,
        secrets=resolve_secret,
        allowlist=Allowlist(s.allow_hosts, s.odoo_url, metrics).check,
        emit=emitter.emit,
        emit_event=emitter.emit_event,
        metrics=metrics,
        log=logging.getLogger(f"collector.plugin.{src.type}.{src.code}"),
    )
    plugin = cls(src, ctx)
    try:
        await plugin.connect()
        readings = await plugin.poll(list(src.signals)) if not plugin.push_mode else []
    except Exception as exc:  # noqa: BLE001
        print(f"test-source failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await plugin.disconnect()
    for r in readings:
        print(
            json.dumps(
                {"code": r.code, "ts": to_iso_z(r.ts), "value": r.value, "text": r.text, "q": r.q}, ensure_ascii=False
            )
        )
    return 0


async def drain_buffer(s: Settings) -> int:
    client = _client(s)
    buffer = Buffer(s.buffer_dir / "buffer.sqlite", s.buffer_max_mb)
    pusher = Pusher(client, buffer, push_max=s.push_max, push_interval_s=s.push_interval_s)
    sent = 0
    try:
        while True:
            before = await buffer.count()
            status = await pusher.push_once()
            if status == "empty":
                break
            if status in ("wait", "retry"):
                await asyncio.sleep(1)
                continue
            if status in ("locked",):
                print("Odoo read_enabled=false: buffer not drained", file=sys.stderr)
                return 1
            sent += before - await buffer.count()
    finally:
        await buffer.close()
        await client.close()
    print(f"drained {sent} readings")
    return 0


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="f3d-collector")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("check-config")
    sub.add_parser("dump-config")
    p_ts = sub.add_parser("test-source")
    p_ts.add_argument("code")
    sub.add_parser("drain-buffer")
    args = parser.parse_args(argv)
    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"])
            print(f"configuration error: F3D_{loc.upper()}: {err['msg']}", file=sys.stderr)
        return EXIT_CONFIG
    setup_logging(settings.log_level, settings.log_json)
    if args.cmd == "run":
        return asyncio.run(Collector(settings).run())
    if args.cmd == "check-config":
        return asyncio.run(check_config(settings))
    if args.cmd == "dump-config":
        return asyncio.run(dump_config(settings))
    if args.cmd == "test-source":
        return asyncio.run(test_source(settings, args.code))
    return asyncio.run(drain_buffer(settings))


def main() -> None:
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
