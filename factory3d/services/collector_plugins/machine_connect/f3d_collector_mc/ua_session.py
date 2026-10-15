"""R-22 / §8.3 пп. 1, 2, 5: пул сесій OPC UA (одна asyncua.Client на endpoint+безпеку), нагляд і переп'єднання."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from asyncua import Client, ua
from asyncua.crypto import security_policies
from collector.core.errors import ConnectError

from .events import inc_metric

WATCHDOG_S = 5.0
BACKOFF_MAX_S = 60.0
CLOSE_TIMEOUT_S = 3.0

POLICIES = {
    "Basic256Sha256": security_policies.SecurityPolicyBasic256Sha256,
    "Aes128_Sha256_RsaOaep": security_policies.SecurityPolicyAes128Sha256RsaOaep,
    "Aes256_Sha256_RsaPss": security_policies.SecurityPolicyAes256Sha256RsaPss,
}

log = logging.getLogger("collector.plugin.opcua.session")


@dataclass
class SessionConfig:
    endpoint: str
    security_mode: str = "None"
    security_policy: str = "None"
    username: str | None = None
    timeout_s: float = 5.0
    app_uri: str = "urn:todo.ltd:f3d:collector"
    secrets: Callable[[str], str] = field(default=lambda name: "", repr=False)
    params: dict = field(default_factory=dict, repr=False)

    @property
    def key(self) -> tuple:
        return (self.endpoint, self.security_mode, self.security_policy, self.username)

    def secret(self, ref_key: str, required: bool = True) -> str | None:
        name = self.params.get(ref_key)
        if not name:
            if required:
                raise ConnectError(f"params.{ref_key} is not set")
            return None
        try:
            return self.secrets(name)
        except KeyError:
            if required:
                raise ConnectError(f"secret {name} not set") from None
            return None


class Session:
    """Одна підтримувана сесія; учасники — плагіни джерел (`UA-<C>`) того самого endpoint."""

    def __init__(self, pool: SessionPool, cfg: SessionConfig, clock: Any, ctx: Any) -> None:
        self.pool = pool
        self.cfg = cfg
        self.clock = clock
        self.ctx = ctx
        self.members: dict[str, Any] = {}
        self.client: Client | None = None
        self.ns_array: list[str] = []
        self.types_ok = False
        self.connected = False
        self.reconnects = 0
        self.last_error: str | None = None
        self._lock = asyncio.Lock()
        self._watchdog: asyncio.Task | None = None
        self._bad_reason: str | None = None
        self._closing = False
        self._types_warned = False

    # --- учасники ---
    async def join(self, plugin: Any) -> None:
        async with self._lock:
            self.members[plugin.source.code] = plugin
            if not self.connected:
                try:
                    await self._open()
                except BaseException:
                    self.members.pop(plugin.source.code, None)
                    if not self.members:
                        self.pool.drop(self)
                    raise
            if self._watchdog is None or self._watchdog.done():
                self._watchdog = asyncio.create_task(self._watch(), name=f"opcua-watchdog-{self.cfg.endpoint}")

    async def leave(self, plugin: Any) -> None:
        self.members.pop(plugin.source.code, None)
        if self.members:
            return
        self._closing = True
        self.pool.drop(self)
        task, self._watchdog = self._watchdog, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self._close_client()

    # --- з'єднання (§8.3 п. 2) ---
    async def _open(self) -> None:
        cfg = self.cfg
        client = Client(url=cfg.endpoint, timeout=cfg.timeout_s)
        client.application_uri = cfg.app_uri
        client.name = "f3d-collector"
        try:
            await self._configure_security(client)
            if cfg.username:
                client.set_user(cfg.username)
                client.set_password(cfg.secret("password_ref") or "")
            await client.connect()
        except ConnectError:
            await self._quiet_disconnect(client)
            raise
        except Exception as exc:  # noqa: BLE001 - будь-яка помилка asyncua -> ConnectError без секретів
            await self._quiet_disconnect(client)
            raise ConnectError(f"opcua connect to {cfg.endpoint} failed: {type(exc).__name__}: {exc}") from exc
        try:
            self.ns_array = list(await client.get_namespace_array())
        except Exception as exc:  # noqa: BLE001
            await self._quiet_disconnect(client)
            raise ConnectError(f"opcua namespace array of {cfg.endpoint} unavailable: {exc}") from exc
        try:
            await client.load_data_type_definitions()
            self.types_ok = True
        except Exception as exc:  # noqa: BLE001
            self.types_ok = False
            if not self._types_warned:
                self._types_warned = True
                log.warning("opcua %s: data types not loaded: %s", cfg.endpoint, exc)
        self.client = client
        self.connected = True
        self._bad_reason = None
        self.last_error = None
        log.info("opcua session %s connected", cfg.endpoint)

    async def _configure_security(self, client: Client) -> None:
        cfg = self.cfg
        if cfg.security_mode == "None":
            return
        policy = POLICIES.get(cfg.security_policy)
        if policy is None:
            raise ConnectError(f"security_policy {cfg.security_policy} is not supported")
        server_cert = cfg.secret("server_cert_ref", required=False)
        if cfg.security_mode == "SignAndEncrypt" and not server_cert:
            raise ConnectError("server certificate not pinned")
        await client.set_security(
            policy,
            certificate=cfg.secret("cert_ref"),
            private_key=cfg.secret("key_ref"),
            server_certificate=server_cert or None,
            mode=getattr(ua.MessageSecurityMode, cfg.security_mode),
        )

    async def _quiet_disconnect(self, client: Client | None) -> None:
        if client is None:
            return
        try:
            await asyncio.wait_for(client.disconnect(), CLOSE_TIMEOUT_S)
        except BaseException as exc:  # noqa: BLE001
            if isinstance(exc, asyncio.CancelledError) and not self._closing:
                raise
            log.debug("opcua disconnect (quiet): %s", exc)

    async def _close_client(self) -> None:
        client, self.client = self.client, None
        self.connected = False
        await self._quiet_disconnect(client)

    def mark_bad(self, reason: str) -> None:
        """Виклик із status_change_notification: наступний цикл нагляду запустить переп'єднання."""
        self._bad_reason = reason

    # --- нагляд і переп'єднання (§8.3 п. 5) ---
    async def _watch(self) -> None:
        while not self._closing:
            await self.clock.sleep(WATCHDOG_S)
            if self._closing:
                return
            try:
                if self._bad_reason:
                    raise ConnectionError(self._bad_reason)
                assert self.client is not None
                await self.client.check_connection()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await self._recover(f"{type(exc).__name__}: {exc}")

    async def _recover(self, reason: str) -> None:
        self.last_error = reason
        self.connected = False
        log.warning("opcua session %s lost: %s", self.cfg.endpoint, reason)
        for member in list(self.members.values()):
            member.session_down(reason)
        await self._close_client()
        backoff = 1.0
        while not self._closing:
            await self.clock.sleep(backoff)
            if self._closing:
                return
            try:
                async with self._lock:
                    await self._open()
                for member in list(self.members.values()):
                    await member.resubscribe()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                log.warning("opcua reconnect to %s failed: %s", self.cfg.endpoint, exc)
                await self._close_client()
                backoff = min(BACKOFF_MAX_S, backoff * 2)
                continue
            self.reconnects += 1
            inc_metric(self.ctx, "collector_mc_opcua_reconnects_total", endpoint=self.cfg.endpoint)
            log.info("opcua session %s reconnected", self.cfg.endpoint)
            return


class SessionPool:
    """Пул сесій процесу; ключ — (endpoint, security_mode, security_policy, username)."""

    def __init__(self) -> None:
        self._map: dict[tuple, Session] = {}

    @property
    def sessions(self) -> int:
        return len(self._map)

    def get(self, cfg: SessionConfig, clock: Any, ctx: Any) -> Session:
        session = self._map.get(cfg.key)
        if session is None:
            session = self._map[cfg.key] = Session(self, cfg, clock, ctx)
        return session

    def drop(self, session: Session) -> None:
        if self._map.get(session.cfg.key) is session:
            del self._map[session.cfg.key]


DEFAULT_POOL = SessionPool()
