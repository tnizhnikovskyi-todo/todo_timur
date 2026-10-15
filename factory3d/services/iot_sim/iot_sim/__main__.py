"""CLI: python -m iot_sim run|check-config|dump-catalog (SPEC §8.1.1)."""
from __future__ import annotations

import argparse
import asyncio
import csv
import importlib
import inspect
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from iot_sim import __version__
from iot_sim.config import Settings

log = logging.getLogger("iot_sim")

# Протоколи W3: підключаються, якщо модуль є (ImportError -> пропуск). (модуль, імена класів, порт-поле)
OPTIONAL_SERVERS = (
    ("iot_sim.protocols.modbus_server", ("ModbusServer", "ModbusTcpServer"), "port_modbus"),
    ("iot_sim.protocols.bacnet_server", ("BacnetServer", "BACnetServer"), "port_bacnet"),
    ("iot_sim.protocols.helvarnet_server", ("HelvarNetServer", "HelvarnetServer"), "port_helvar_tcp"),
)


def cmd_check_config(settings: Settings) -> int:
    errors = settings.validate_required()
    catalog = Path(settings.catalog_dir) / "signals.csv"
    if not catalog.is_file():
        errors.append(f"немає каталогу {catalog}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if errors:
        return 2 if any("SIM_API_TOKEN" in e for e in errors) else 1
    print("config OK")
    return 0


def cmd_dump_catalog(settings: Settings) -> int:
    path = Path(settings.catalog_dir) / "signals.csv"
    with path.open(encoding="utf-8", newline="") as f:
        csv.writer(sys.stdout, lineterminator="\n").writerows(csv.reader(f))
    return 0


def _optional_server(world: Any, settings: Settings, module: str, names: tuple[str, ...], port_attr: str) -> Any:
    try:
        mod = importlib.import_module(module)
    except ImportError:
        log.info("протокол %s ще не доступний (немає модуля), пропускаю", module)
        return None
    cls = next((getattr(mod, n) for n in names if hasattr(mod, n)), None)
    if cls is None:
        log.warning("у %s немає жодного з класів %s", module, names)
        return None
    params = inspect.signature(cls).parameters
    kw: dict[str, Any] = {}
    if "port" in params:
        kw["port"] = getattr(settings, port_attr)
    if "udp_port" in params:
        kw["udp_port"] = settings.port_helvar_udp
    if "version" in params:
        kw["version"] = settings.helvar_version
    if "settings" in params:
        kw["settings"] = settings
    try:
        return cls(world, **kw)
    except Exception:
        log.exception("не вдалося створити сервер %s", cls.__name__)
        return None


class Service:
    """Збирає World, ScenarioRunner і всі протокольні сервери; цикл ``world.tick_real``."""

    def __init__(self, settings: Settings, registry: Any = None) -> None:
        from iot_sim.core.clock import SimClock
        from iot_sim.core.outbound import OutboundGuard
        from iot_sim.core.registry import Registry
        from iot_sim.core.scenarios import ScenarioRunner
        from iot_sim.core.world import World
        from iot_sim.odoo.devices_client import DevicesClient, EventForwarder
        from iot_sim.odoo.follow import FollowOdoo, OdooReadOnly
        from iot_sim.protocols.biostar_api import BioStarApi
        from iot_sim.protocols.control_api import create_app
        from iot_sim.protocols.jobs_api import JobsApi
        from iot_sim.protocols.lpr_push import LprPusher
        from iot_sim.protocols.mqtt_publisher import MqttPublisher
        from iot_sim.protocols.opcua_server import OpcUaServer
        from iot_sim.protocols.sics_server import SicsServer
        from iot_sim.protocols.woodstore_api import UvicornRunner, WoodStoreApi

        s = self.settings = settings
        self.guard = OutboundGuard(s.allow_outbound_hosts())
        odoo_host = urlsplit(s.odoo_url).hostname
        configured = bool(s.odoo_url and s.odoo_db and s.odoo_user and s.odoo_apikey)
        mode = s.mode
        if mode == "follow_odoo" and not configured:
            log.warning("SIM_MODE=follow_odoo, але Odoo не налаштовано: стартую в режимі scenario")
            mode = "scenario"
        factor = 1.0 if mode == "follow_odoo" else s.factor
        sim_t0 = datetime.fromisoformat(s.start_at) if s.start_at else None
        clock = SimClock(s.tz, factor, sim_t0)
        self.registry = registry or Registry.load(s.catalog_dir)
        self.world = World(self.registry, seed=s.seed, clock=clock, settings=s, mode=mode)
        self.runner = ScenarioRunner(self.world)
        self.servers: dict[str, Any] = {}

        def add(srv: Any) -> None:
            if srv is not None:
                self.servers[srv.name] = srv

        w = self.world
        add(OpcUaServer(w, port=s.port_opcua, user=s.opcua_user, password=s.opcua_pass,
                        cert_dir=s.opcua_cert_dir))
        add(WoodStoreApi(w, port=s.port_woodstore, apikey=s.woodstore_apikey))
        add(JobsApi(w, port=s.port_jobs, apikey=s.jobs_apikey))
        add(MqttPublisher(w, url=s.mqtt_url, prefix=s.mqtt_prefix, guard=self.guard))
        add(BioStarApi(w, port_http=s.port_biostar_http, port_https=s.port_biostar_https,
                       user=s.biostar_user, password=s.biostar_pass, cert_dir=s.opcua_cert_dir))
        add(SicsServer(w, port=s.port_sics))
        add(LprPusher(w, url=s.lpr_push_url, guard=self.guard))
        for module, names, port_attr in OPTIONAL_SERVERS:
            add(_optional_server(w, s, module, names, port_attr))

        self.odoo = OdooReadOnly(s.odoo_url, s.odoo_db, s.odoo_user, s.odoo_apikey, guard=self.guard)
        self.follow = FollowOdoo(w, self.odoo, follow_s=s.odoo_follow_s, slow_s=s.odoo_follow_slow_s,
                                 stale_s=s.odoo_stale_s, level0_sync=s.level0_sync)
        self.devices_client = DevicesClient(s.odoo_url, s.odoo_export_token, guard=self.guard)
        self.forwarder = EventForwarder(w, self.devices_client)
        self.app = create_app(s, world=w, runner=self.runner, servers=self.servers, follow=self.follow,
                              guard=self.guard)
        self.ctl = self.app.state.ctl
        self.control = UvicornRunner(self.app, "0.0.0.0", s.port_control)
        self._odoo_host = odoo_host
        self._stop = asyncio.Event()
        self._started: list[Any] = []

    # --- життєвий цикл ---------------------------------------------------------------------
    async def start(self) -> None:
        from iot_sim.core import snapshot

        s, w = self.settings, self.world
        self.guard.install()
        data = snapshot.load(s.state_dir) if s.restore_snapshot and s.snapshot_s != 0 else None
        if data is not None:
            try:
                w.restore(data)
                self.runner.restore_runs(data.get("runs", {}))
            except Exception:
                log.exception("не вдалося відновити знімок, старт від каталогу")
        else:
            log.info("fresh start from catalog")
        if w.mode == "follow_odoo":
            w.clock.set_factor(1.0)
        if self.devices_client.configured:
            await self.forwarder.start()
        for name, srv in self.servers.items():
            try:
                await srv.start()
                self._started.append(srv)
            except Exception:
                log.exception("сервер %s не стартував", name)
        await self.follow.start()
        await self.control.start()
        log.info("iot_sim %s запущено: mode=%s, factor=%s, servers=%s", __version__, w.mode,
                 w.clock.factor, sorted(self.servers))

    async def tick_loop(self) -> None:
        from iot_sim.core import snapshot

        s, w = self.settings, self.world
        period = max(s.tick_ms, 10) / 1000.0
        last = time.monotonic()
        last_snap = last
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=period)
            except TimeoutError:
                pass
            now = time.monotonic()
            dt = now - last
            last = now
            if not self.ctl.locked:  # стоп-кран: значення заморожені
                try:
                    w.tick_real(dt)
                    self.ctl.tick_hist.observe(time.monotonic() - now)
                except Exception:
                    log.exception("помилка тіку")
            w.last_tick_real = time.monotonic()
            if s.snapshot_s > 0 and now - last_snap >= s.snapshot_s:
                last_snap = now
                try:
                    snapshot.save(w, s.state_dir)
                except Exception:
                    log.exception("не вдалося зберегти знімок")

    async def stop(self) -> None:
        from iot_sim.core import snapshot

        self._stop.set()
        try:
            await self.runner.stop_all()
        except Exception:
            log.exception("stop_all")
        if self.settings.snapshot_s > 0:
            try:
                snapshot.save(self.world, self.settings.state_dir)
            except Exception:
                log.exception("знімок при зупинці")
        await self.follow.stop()
        await self.forwarder.stop()
        for srv in reversed(self._started):
            try:
                await srv.stop()
            except Exception:
                log.exception("зупинка %s", srv.name)
        await self.control.stop()
        await self.devices_client.aclose()
        self.guard.uninstall()

    async def run_forever(self) -> int:
        from iot_sim.logging_conf import setup_logging

        setup_logging(self.settings)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:  # pragma: no cover - Windows
                pass
        await self.start()
        try:
            await self.tick_loop()
        finally:
            await self.stop()
        return 0


def cmd_run(settings: Settings) -> int:
    errors = settings.validate_required()
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    async def main_async() -> int:
        return await Service(settings).run_forever()

    return asyncio.run(main_async())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="iot_sim")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("command", choices=["run", "check-config", "dump-catalog"])
    args = p.parse_args(argv)
    settings = Settings()
    handlers = {"run": cmd_run, "check-config": cmd_check_config, "dump-catalog": cmd_dump_catalog}
    return handlers[args.command](settings)


if __name__ == "__main__":
    sys.exit(main())
