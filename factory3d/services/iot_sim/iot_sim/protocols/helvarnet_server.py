"""P-08 HelvarNet (SPEC §8.10.4): роутери LP-1…LP-3 (cluster 1, router 1…3), TCP 50000 і UDP 50001.

ASCII-кадри ``>V:<v>,C:<cmd>[,G:|B:|S:|L:|P:|F:|A:|@c.r.s.d…]#``; відповідь на запит — ``?V:<v>,C:<cmd>[,…]=<знач>#``
(версія запиту, X-64), помилка — ``!V:<v>,C:<cmd>[,…]=<код>#``; довга відповідь C:164 ділиться на часткові кадри (``$``,
≤ 64 адрес). Команди (C:11…18) виконуються, розсилаються push усім TCP-клієнтам; при ``A:1`` відправник
додатково отримує ``!…=0#``. Рівень/сцена групи ставляться у ``World`` (``world.force`` сигналів
``lighting/groups/<LT>/{level,scene}`` із утриманням, ``world.post("lighting", …)``, подія ``command``).

Склад груп (``@c.r.s.d``) — за правилом bms R-06 (SPEC §8.10.4) з ``dist/odoo_demo.json`` (``lighting.groups[*].n``,
``lighting.panels[*].groups``); шлях — параметр ``layout`` / ``SIM_LAYOUT_PATH``. Без макета — ПРИПУЩЕННЯ: групи з каталогу
сигналів по 4 світильники, усі на LP-1. Стан світильника (C:110) — з прапорів ``World``: ``blackout`` (фаза ``outage``) ->
EMERGENCY ``0x400``; ``lighting_scene[*].fault_device`` і ``lighting.fault_devices`` -> ``0x2``.
EMERGENCY (G:40) — ПРИПУЩЕННЯ: по 2 світильники ``@1.r.1.63/64`` на роутер.

Реєстрація у ``__main__ run``: ``HelvarServer(world, tcp_port=s.port_helvar_tcp, udp_port=s.port_helvar_udp,
version=s.helvar_version)``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from iot_sim.core.world import World
from iot_sim.protocols.bacnet_server import load_layout
from iot_sim.protocols.base import ProtocolServer

log = logging.getLogger("iot_sim.helvarnet")

LINE_SIZE = 64
MAX_PARTIAL = 64
EMERGENCY_G = 40
SCENE_LEVELS = [100, 75, 50, 25, 10, 0] + [
    100
] * 10  # R-24: S1=100, S2=75, S3=50, S4=25, S5=10, S6=0, S7…S16 — ПРИПУЩЕННЯ
SCENE_NAMES = ["Зміна", "Прибирання", "Ніч", "Чергове", "10 %", "Вимкнено"] + [f"Сцена {i}" for i in range(7, 17)]
HOLD_S = 1800.0  # утримання ручного рівня проти розкладу DALI (sim-секунди)
NS_LAMP_FAILURE, NS_EM_INEMERGENCY = 0x2, 0x400
DEVICE_TYPE_DALI = 1537
ERR_OK, ERR_GROUP, ERR_CLUSTER, ERR_ROUTER, ERR_SUBNET, ERR_DEVICE = 0, 1, 2, 3, 4, 5
ERR_BLOCK, ERR_SCENE, ERR_NOCLUSTER, ERR_NOROUTER, ERR_NODEVICE = 7, 8, 9, 10, 11
ERR_PROP, ERR_CMD, ERR_PARAM, ERR_VERSION = 12, 15, 17, 18
_ADDR = re.compile(r"^@(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?$")


class HelvarError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Group:
    g: int
    code: str
    panel: str
    n: int
    name: str
    devices: list[str] = field(default_factory=list)


@dataclass
class Request:
    version: int
    cmd: int
    items: list[tuple[str, str]]  # у порядку запиту, без V і C

    def get(self, key: str) -> str | None:
        for k, v in self.items:
            if k == key:
                return v
        return None

    def header(self, drop: tuple[str, ...] = ()) -> str:
        parts = [f"V:{self.version}", f"C:{self.cmd}"]
        for k, v in self.items:
            if k in drop:
                continue
            parts.append(f"@{v}" if k == "@" else f"{k}:{v}")
        return ",".join(parts)


def parse_frame(frame: str) -> tuple[int | None, int | None, list[tuple[str, str]]]:
    """``>V:2,C:13,G:12,L:60#`` -> (версія, команда, [(ключ, значення)…])."""
    body = frame[1:-1]
    ver = cmd = None
    items: list[tuple[str, str]] = []
    for part in filter(None, body.split(",")):
        if part.startswith("@"):
            items.append(("@", part[1:]))
            continue
        k, _, v = part.partition(":")
        if k == "V":
            ver = int(v) if v.lstrip("-").isdigit() else -1
        elif k == "C":
            cmd = int(v) if v.isdigit() else -1
        else:
            items.append((k, v))
    return ver, cmd, items


class Layout:
    """Групи, склад ліній DALI (bms R-06) і адреси; ``G`` = порядковий номер LT-* у каталозі."""

    def __init__(self, world: World, layout: dict[str, Any]) -> None:
        lt = [c.split("/")[2] for c in world.signals if c.startswith("lighting/groups/") and c.endswith("/level")]
        lay = layout.get("lighting") or {}
        lgroups = lay.get("groups") or {}
        panels = lay.get("panels") or {}
        panel_of = {g: p for p, info in panels.items() for g in info.get("groups", [])}
        self.groups: list[Group] = []
        for i, code in enumerate(lt, 1):
            info = lgroups.get(code, {})
            self.groups.append(
                Group(
                    i,
                    code,
                    panel_of.get(code, info.get("panel", "LP-1")),
                    int(info.get("n", 4)),
                    info.get("zone_name", code),
                )
            )
        self.by_g = {g.g: g for g in self.groups}
        self.by_code = {g.code: g for g in self.groups}
        self.devices: dict[str, Group | None] = {}
        self._place()

    def _place(self) -> None:
        for r, panel in enumerate(sorted({g.panel for g in self.groups}), 1):
            line, used = 1, 0
            for g in [x for x in self.groups if x.panel == panel]:
                if used > 0 and g.n > LINE_SIZE - used:
                    line, used = line + 1, 0
                for _ in range(g.n):
                    if used == LINE_SIZE:
                        line, used = line + 1, 0
                    used += 1
                    addr = f"@1.{r}.{line}.{used}"
                    g.devices.append(addr)
                    self.devices[addr] = g
            self.routers = r
        self.emergency: list[str] = []
        for r in range(1, getattr(self, "routers", 3) + 1):
            for d in (63, 64):
                a = f"@1.{r}.1.{d}"
                if a not in self.devices:
                    self.emergency.append(a)
                    self.devices[a] = None  # EMERGENCY: не належить LT-групі
        self.sensors = {
            f"@1.{r}.{s}.{d}"
            for r in range(1, getattr(self, "routers", 3) + 1)
            for s in range(1, 5)
            for d in range(65, 71)
        }


class HelvarServer(ProtocolServer):
    name = "helvarnet"

    def __init__(
        self,
        world: World,
        *,
        tcp_port: int = 50000,
        udp_port: int | None = 50001,
        host: str = "0.0.0.0",
        version: int | None = None,
        layout: dict[str, Any] | str | None = None,
    ) -> None:
        self.world = world
        self.tcp_port, self.udp_port, self.host = tcp_port, udp_port, host
        self.version = version or int(getattr(world.settings, "helvar_version", 2) or 2)
        lay = layout if isinstance(layout, dict) else load_layout(layout)
        self.layout = Layout(world, lay)
        self.up = False
        self.clients: set[asyncio.StreamWriter] = set()
        self._server: asyncio.AbstractServer | None = None
        self._udp: asyncio.DatagramTransport | None = None
        self._last: dict[int, int] = {}
        self.overrides: dict[str, int] = {}  # рівні окремих світильників
        self.em: dict[str, int] = {"ft_time": 0, "ft_state": 0, "dt_time": 0, "dt_state": 0}

    # --- життєвий цикл ---------------------------------------------------------------
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._server = await asyncio.start_server(self._on_client, self.host, self.tcp_port)
        if self.tcp_port == 0:
            self.tcp_port = self._server.sockets[0].getsockname()[1]
        if self.udp_port is not None:
            outer = self

            class Udp(asyncio.DatagramProtocol):
                def datagram_received(self, data: bytes, addr: Any) -> None:
                    for frame in outer._frames(data.decode("utf-8", "replace")):
                        resp, _ = outer.handle(frame)
                        if resp and outer._udp is not None:
                            outer._udp.sendto("".join(resp).encode("utf-8"), addr)

            transport, _ = await loop.create_datagram_endpoint(Udp, local_addr=(self.host, self.udp_port))
            self._udp = transport
            if self.udp_port == 0:
                self.udp_port = transport.get_extra_info("sockname")[1]
        self._last = {g.g: self._level(g) for g in self.layout.groups}
        self.world.on_tick(self._on_tick)
        self.up = True
        log.info(
            "HelvarNet TCP %d UDP %s v%d, груп %d", self.tcp_port, self.udp_port, self.version, len(self.layout.groups)
        )

    async def stop(self) -> None:
        self.up = False
        for w in list(self.clients):
            w.close()
        self.clients.clear()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._udp is not None:
            self._udp.close()
            self._udp = None

    def health(self) -> dict[str, Any]:
        return {
            "proto": self.name,
            "up": self.up,
            "tcp": self.tcp_port,
            "udp": self.udp_port,
            "clients": len(self.clients),
            "groups": len(self.layout.groups),
        }

    # --- TCP -------------------------------------------------------------------------
    @staticmethod
    def _frames(text: str) -> list[str]:
        return re.findall(r">[^>#]*#", text)

    async def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.clients.add(writer)
        buf = ""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buf += data.decode("utf-8", "replace")
                frames = self._frames(buf)
                if frames:
                    buf = buf[buf.rfind("#") + 1 :]
                for frame in frames:
                    resp, push = self.handle(frame)
                    if push:
                        self._push(push)
                    if resp:
                        writer.write("".join(resp).encode("utf-8"))
                        await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self.clients.discard(writer)
            writer.close()

    def _push(self, frame: str) -> None:
        for w in list(self.clients):
            try:
                w.write(frame.encode("utf-8"))
            except (OSError, RuntimeError):  # pragma: no cover
                self.clients.discard(w)

    def _on_tick(self, _w: World) -> None:
        """Рівень групи змінився моделлю/сценарієм -> push ``C:13`` усім клієнтам."""
        if not self.up:
            return
        for g in self.layout.groups:
            lvl = self._level(g)
            if lvl != self._last.get(g.g):
                self._last[g.g] = lvl
                self._push(f">V:{self.version},C:13,G:{g.g},L:{lvl},F:100#")

    # --- стан світу ------------------------------------------------------------------
    def _level(self, g: Group) -> int:
        s = self.world.signals.get(f"lighting/groups/{g.code}/level")
        try:
            return round(float(s.value)) if s is not None else 0
        except (TypeError, ValueError):
            return 0

    def _scene(self, g: Group) -> int:
        s = self.world.signals.get(f"lighting/groups/{g.code}/scene")
        try:
            return int(float(s.value)) if s is not None else 1
        except (TypeError, ValueError):
            return 1

    def _blackout(self) -> bool:
        b = self.world.flag("blackout")
        return isinstance(b, dict) and b.get("phase") == "outage"

    def _faulty(self) -> set[str]:
        out = set(self.world.flag("lighting.fault_devices") or [])
        for v in (self.world.flag("lighting_scene") or {}).values():
            if isinstance(v, dict) and v.get("fault_device"):
                out.add(v["fault_device"])
        for g in self.layout.groups:  # лічильник faults моделі без явних адрес — перші k світильників групи
            s = self.world.signals.get(f"lighting/groups/{g.code}/faults")
            try:
                k = int(float(s.value)) if s is not None else 0
            except (TypeError, ValueError):
                k = 0
            if k and not (set(g.devices) & out):
                out.update(g.devices[:k])
        return out

    def _dev_state(self, addr: str, faulty: set[str] | None = None) -> int:
        if addr in self.layout.emergency:
            return NS_EM_INEMERGENCY if self._blackout() else 0
        if self._blackout():
            return 0
        return NS_LAMP_FAILURE if addr in (faulty if faulty is not None else self._faulty()) else 0

    def _dev_level(self, addr: str) -> int:
        if addr in self.overrides:
            return self.overrides[addr]
        g = self.layout.devices.get(addr)
        if self._blackout() and addr not in self.layout.emergency:
            return 0
        return self._level(g) if g else (100 if addr in self.layout.emergency else 0)

    # --- розбір параметрів -----------------------------------------------------------
    def _group(self, req: Request, allow_emergency: bool = False) -> Group | int:
        raw = req.get("G")
        if raw is None or not raw.lstrip("-").isdigit():
            raise HelvarError(ERR_PARAM)
        g = int(raw)
        if allow_emergency and g == EMERGENCY_G:
            return g
        grp = self.layout.by_g.get(g)
        if grp is None:
            raise HelvarError(ERR_GROUP)
        return grp

    def _addr(self, req: Request, sensors: bool = False) -> str:
        raw = req.get("@")
        if raw is None:
            raise HelvarError(ERR_PARAM)
        m = _ADDR.match("@" + raw)
        if not m:
            raise HelvarError(ERR_DEVICE)
        parts = [int(x) if x else None for x in m.groups()]
        cl, r, s, d = parts
        if cl != 1:
            raise HelvarError(ERR_NOCLUSTER)
        if r is None or not 1 <= r <= self.layout.routers:
            raise HelvarError(ERR_NOROUTER)
        if s is None or d is None:
            raise HelvarError(ERR_PARAM)
        if not 1 <= s <= 4:
            raise HelvarError(ERR_SUBNET)
        addr = f"@{cl}.{r}.{s}.{d}"
        if addr in self.layout.devices or (sensors and addr in self.layout.sensors):
            return addr
        raise HelvarError(ERR_NODEVICE)

    @staticmethod
    def _int(req: Request, key: str, lo: int, hi: int, err: int, default: int | None = None) -> int:
        raw = req.get(key)
        if raw is None:
            if default is None:
                raise HelvarError(ERR_PARAM)
            return default
        try:
            v = int(raw)
        except ValueError as e:
            raise HelvarError(ERR_PARAM) from e
        if not lo <= v <= hi:
            raise HelvarError(err)
        return v

    # --- обробка кадру ---------------------------------------------------------------
    def handle(self, frame: str) -> tuple[list[str], str | None]:
        """(відповідні кадри відправнику, push-кадр усім клієнтам)."""
        ver, cmd, items = parse_frame(frame)
        v = ver if ver in (1, 2) else self.version
        if ver is None or cmd is None or cmd < 0:
            return [
                f"!V:{v},C:{cmd if cmd and cmd > 0 else 0}={ERR_PARAM if ver is None or cmd is None else ERR_CMD}#"
            ], None
        req = Request(v, cmd, items)
        if ver not in (1, 2) or (self.version == 1 and ver == 2):
            return [f"!{req.header()}={ERR_VERSION}#"], None
        try:
            return self._dispatch(req)
        except HelvarError as e:
            return [f"!{req.header()}={e.code}#"], None

    def _ok(self, req: Request, value: Any) -> tuple[list[str], None]:
        return [f"?{req.header()}={value}#"], None

    def _dispatch(self, req: Request) -> tuple[list[str], str | None]:
        c = req.cmd
        if 11 <= c <= 18:
            return self._command(req)
        if 19 <= c <= 24:
            return self._emergency_cmd(req)
        fn = getattr(self, f"_q{c}", None)
        if fn is None:
            raise HelvarError(ERR_CMD)
        return fn(req)  # type: ignore[no-any-return]

    # --- команди C:11…18 -------------------------------------------------------------
    def _targets(self, req: Request) -> tuple[Group | None, str | None]:
        if req.cmd % 2 == 1:  # 11, 13, 15, 17 — група
            g = self._group(req)
            return g, None  # type: ignore[return-value]
        return None, self._addr(req)

    def _command(self, req: Request) -> tuple[list[str], str | None]:
        grp, addr = self._targets(req)
        c = req.cmd
        fade = self._int(req, "F", 0, 10**6, ERR_PARAM, default=0)
        old = self._level(grp) if grp else self._dev_level(addr or "")
        if c in (11, 12):
            self._int(req, "B", 1, 8, ERR_BLOCK)
            scene = self._int(req, "S", 1, 16, ERR_SCENE)
            level, extra = SCENE_LEVELS[scene - 1], {"scene": scene}
        elif c in (13, 14):
            level, extra = self._int(req, "L", 0, 100, ERR_PARAM), {}
        elif c in (15, 16):
            p = self._int(req, "P", -100, 100, ERR_PARAM)
            level, extra = max(0, min(100, round(old * (100 + p) / 100))), {"proportion": p}
        else:  # 17, 18 — Modify Proportion
            p = self._int(req, "P", -100, 100, ERR_PARAM)
            level, extra = max(0, min(100, round(old + old * p / 100))), {"proportion": p}
        self._apply(grp, addr, level, extra, fade)
        push = f">{req.header(drop=('A',))}#"
        resp = [f"!{req.header()}={ERR_OK}#"] if req.get("A") == "1" else []
        return resp, push

    def _apply(self, grp: Group | None, addr: str | None, level: int, extra: dict[str, Any], fade: int) -> None:
        w = self.world
        if grp is not None:
            for d in grp.devices:
                self.overrides.pop(d, None)
            w.force(f"lighting/groups/{grp.code}/level", level, HOLD_S)
            if "scene" in extra and f"lighting/groups/{grp.code}/scene" in w.signals:
                w.force(f"lighting/groups/{grp.code}/scene", extra["scene"], HOLD_S)
            self._last[grp.g] = level  # ця зміна вже розіслана самою командою
            target = grp.code
        else:
            self.overrides[addr or ""] = level
            target = addr or ""
        w.post("lighting", {"target": target, "level": level, "fade_cs": fade, **extra})
        w.events.emit(
            "command",
            f"HelvarNet: {target} -> {level} %",
            device=grp.panel if grp else None,
            payload={"target": target, "level": level, **extra},
        )

    # --- аварійні тести C:19…24 ------------------------------------------------------
    def _emergency_cmd(self, req: Request) -> tuple[list[str], str | None]:
        if req.cmd % 2 == 1:
            g = self._group(req, allow_emergency=True)
            if g != EMERGENCY_G:
                raise HelvarError(ERR_GROUP)
        else:
            a = self._addr(req)
            if a not in self.layout.emergency:
                raise HelvarError(ERR_NODEVICE)
        now = int(self.world.now().timestamp())
        if req.cmd in (19, 20):
            self.em.update(ft_time=now, ft_state=2)
            self.world.call_later(60, lambda: self.em.update(ft_state=1))
        elif req.cmd in (21, 22):
            self.em.update(dt_time=now, dt_state=2)
            self.world.call_later(3600, lambda: self.em.update(dt_state=1))
        else:
            for k in ("ft_state", "dt_state"):
                if self.em[k] == 2:
                    self.em[k] = 0
        self.world.events.emit("command", f"HelvarNet: аварійний тест C:{req.cmd}", payload={"cmd": req.cmd})
        resp = [f"!{req.header()}={ERR_OK}#"] if req.get("A") == "1" else []
        return resp, f">{req.header(drop=('A',))}#"

    # --- запити ----------------------------------------------------------------------
    def _q101(self, req: Any) -> Any:  # Query Clusters
        return self._ok(req, 1)

    def _q102(self, req: Any) -> Any:  # Query Routers
        return self._ok(req, ",".join(str(i) for i in range(1, self.layout.routers + 1)))

    def _q103(self, req: Any) -> Any:  # LSIB
        g = self._group(req)
        self._int(req, "B", 1, 8, ERR_BLOCK)
        return self._ok(req, self._scene(g))  # type: ignore[arg-type]

    def _q104(self, req: Any) -> Any:  # Query Device Type
        self._addr(req, sensors=True)
        return self._ok(req, DEVICE_TYPE_DALI)

    def _q105(self, req: Any) -> Any:  # Description (Group)
        g = self._group(req, allow_emergency=True)
        return self._ok(req, "EMERGENCY" if g == EMERGENCY_G else g.name)  # type: ignore[union-attr]

    def _q106(self, req: Any) -> Any:  # Description (Device)
        a = self._addr(req, sensors=True)
        grp = self.layout.devices.get(a)
        return self._ok(req, f"{grp.name} {a}" if grp else f"Датчик/EMERGENCY {a}")

    def _q107(self, req: Any) -> Any:
        return self._ok(req, "F3D")

    def _q108(self, req: Any) -> Any:  # Workgroup membership
        a = self._addr(req)
        grp = self.layout.devices.get(a)
        return self._ok(req, grp.g if grp else EMERGENCY_G)

    def _q109(self, req: Any) -> Any:  # LSIG
        g = self._group(req)
        return self._ok(req, self._scene(g))  # type: ignore[arg-type]

    def _q110(self, req: Any) -> Any:  # Query Device State
        a = self._addr(req)
        return self._ok(req, self._dev_state(a))

    def _flag_q(self, req: Request, mask: int) -> Any:
        a = self._addr(req)
        return self._ok(req, 1 if self._dev_state(a) & mask else 0)

    def _q111(self, req: Any) -> Any:
        return self._flag_q(req, 0x1)

    def _q112(self, req: Any) -> Any:
        return self._flag_q(req, 0x2)

    def _q113(self, req: Any) -> Any:
        return self._flag_q(req, 0x4)

    def _q114(self, req: Any) -> Any:
        return self._flag_q(req, 0x8)

    def _q150(self, req: Any) -> Any:  # Measurement (датчик 322): лк
        self._addr(req, sensors=True)
        lux = self.world.flag("lighting.lux")
        return self._ok(req, int(lux) if isinstance(lux, (int, float)) else 300)

    def _q151(self, req: Any) -> Any:  # Inputs: присутність
        self._addr(req, sensors=True)
        return self._ok(req, 1 if self.world.shift.in_shift(self.world.now()) else 0)

    def _q152(self, req: Any) -> Any:  # Load level
        a = self._addr(req)
        return self._ok(req, self._dev_level(a))

    def _q160(self, req: Any) -> Any:  # Power (device)
        a = self._addr(req)
        return self._ok(req, round(126 * self._dev_level(a) / 100))

    def _q161(self, req: Any) -> Any:  # Power (group)
        g = self._group(req)
        return self._ok(req, round(len(g.devices) * 126 * self._level(g) / 100))  # type: ignore[arg-type,union-attr]

    def _q164(self, req: Any) -> Any:  # Query Group: склад, ≤ 64 адрес у кадрі, часткові кадри `$`
        g = self._group(req, allow_emergency=True)
        devs = self.layout.emergency if g == EMERGENCY_G else g.devices  # type: ignore[union-attr]
        if not devs:
            raise HelvarError(ERR_GROUP)
        head = req.header()
        chunks = [devs[i : i + MAX_PARTIAL] for i in range(0, len(devs), MAX_PARTIAL)]
        frames = [f"?{head}={','.join(ch)}{'#' if i == len(chunks) - 1 else '$'}" for i, ch in enumerate(chunks)]
        return frames, None

    def _q165(self, req: Any) -> Any:  # Query Groups
        return self._ok(req, ",".join([str(g.g) for g in self.layout.groups] + [str(EMERGENCY_G)]))

    def _q166(self, req: Any) -> Any:  # Query Scene Names
        self._group(req, allow_emergency=True)
        return self._ok(req, ",".join(SCENE_NAMES))

    def _q167(self, req: Any) -> Any:  # Query Scene Info
        self._group(req, allow_emergency=True)
        s = self._int(req, "S", 1, 16, ERR_SCENE)
        return self._ok(req, f"{SCENE_NAMES[s - 1]},{SCENE_LEVELS[s - 1]}")

    def _em_query(self, req: Request, value: int) -> Any:
        if req.get("G") is not None:
            if self._group(req, allow_emergency=True) != EMERGENCY_G:
                raise HelvarError(ERR_GROUP)
        elif self._addr(req) not in self.layout.emergency:
            raise HelvarError(ERR_NODEVICE)
        return self._ok(req, value)

    def _q170(self, req: Any) -> Any:
        return self._em_query(req, self.em["ft_time"])

    def _q171(self, req: Any) -> Any:
        return self._em_query(req, self.em["ft_state"])

    def _q172(self, req: Any) -> Any:
        return self._em_query(req, self.em["dt_time"])

    def _q173(self, req: Any) -> Any:
        return self._em_query(req, self.em["dt_state"])

    def _q174(self, req: Any) -> Any:  # заряд АКБ, %
        return self._em_query(req, 40 if self._blackout() else 100)

    def _q175(self, req: Any) -> Any:  # час роботи від АКБ, хв
        return self._em_query(req, 180)

    def _q176(self, req: Any) -> Any:  # напрацювання лампи, год
        return self._em_query(req, 1200)

    def _q185(self, req: Any) -> Any:
        return self._ok(req, int(self.world.now().timestamp()))

    def _q186(self, req: Any) -> Any:
        return self._ok(req, 30.52)

    def _q187(self, req: Any) -> Any:
        return self._ok(req, 50.45)

    def _q188(self, req: Any) -> Any:
        return self._ok(req, "+120")

    def _q189(self, req: Any) -> Any:
        return self._ok(req, 1)

    def _q190(self, req: Any) -> Any:
        return self._ok(req, "5.4.0")

    def _q191(self, req: Any) -> Any:
        return self._ok(req, self.version)
