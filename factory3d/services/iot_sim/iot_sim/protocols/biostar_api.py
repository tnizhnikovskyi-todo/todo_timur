"""P-10: Suprema BioStar 2 REST (СКУД), API-40…API-46 (SPEC §8.12).

HTTPS (самопідписаний, ``SIM_PORT_BIOSTAR_HTTPS``) і HTTP (``SIM_PORT_BIOSTAR_HTTP``, тести). Усі значення
в JSON — рядки, як у BioStar 2. Події СКУД веде модель ``access`` через ``world.events``:
``emit("access", msg, device="ACR-IN", payload={"user_id": "OPSAW1", "event_code": 4102,
"door": "1", "tna_key": "1"})`` (``door`` і ``tna_key`` необов'язкові; ``event_code`` — коди §8.12);
``BioStarStore.add_event`` — той самий вхід для тестів. Користувачі — ``world.people`` (``barcode``,
``name``, необов'язково ``group``). POST/PUT/DELETE на незмінні ресурси -> 405.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import ipaddress
import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from iot_sim.core.events import Event
from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer
from iot_sim.protocols.woodstore_api import UvicornRunner

log = logging.getLogger("iot_sim.biostar")

SESSION_TTL_S = 30 * 60
MAX_SESSIONS = 10
MAX_LIMIT = 2000
DEFAULT_GROUP = {"id": "1", "name": "Виробництво"}
DEVICES = [
    ("5390001", "ACR-IN", "ACR-IN BioEntry W3 (прохідна)", "10.90.1.11", "1"),
    ("5390002", "ACR-ELEC", "ACR-ELEC BioEntry W3 (електрощитова)", "10.90.1.12", "2"),
    ("5390003", "ACR-CHG", "ACR-CHG BioEntry W3 (зарядна)", "10.90.1.13", "3"),
    ("5390004", "ACR-PAINT", "ACR-PAINT BioEntry W3 (склад ЛФМ)", "10.90.1.14", "4"),
    ("5390005", "ACR-SRV", "ACR-SRV BioEntry W3 (серверна)", "10.90.1.15", "5")]
DOORS = {"1": "Турнікет TURN-1 (вхід персоналу)", "2": "Електрощитова", "3": "Зарядна",
         "4": "Склад ЛФМ", "5": "Серверна"}
DOOR_SHORT = {"1": "Турнікет TURN-1"}
EVENT_TYPES = {
    4102: "Verify Success (Card)", 4100: "Verify Success (ID+Face)", 4867: "Identify Success (Face)",
    4865: "Identify Success (Fingerprint)", 5120: "Identify Fail", 4352: "Verify Fail",
    6400: "Access Denied", 6401: "Access Denied (not in access group)",
    6402: "Access Denied (user inactive)", 6403: "Access Denied (expired)",
    6405: "Access Denied (anti-passback)", 20480: "Door Unlocked", 20736: "Door Locked",
    20992: "Door Opened", 21248: "Door Closed", 21504: "Door Forced Open", 21760: "Door Held Open",
    26368: "Zone Fire Alarm", 12544: "Device System Started", 15104: "TCP Connected"}
_COLUMN_SYNONYMS = {"device_id.id": "device", "door_id.id": "door", "event_type_id.code": "code",
                    "user_group_id.id": "group", "user_id.user_id": "user", "datetime": "datetime",
                    "server_datetime": "server_datetime", "id": "id"}


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 10000:02d}Z"


def _parse(v: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(v)).astimezone(dt.UTC)


def ok(body: dict | None = None, status: int = 200, headers: dict | None = None) -> JSONResponse:
    data = dict(body or {})
    data.setdefault("Response", {"code": "0", "message": "Success"})
    return JSONResponse(data, status_code=status, headers=headers)


def fail(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"Response": {"code": code, "message": message}}, status_code=status)


class BioStarStore:
    def __init__(self, world: World, *, login: str = "admin", password: str = "",
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.world, self.login, self.password, self._clock = world, login, password, clock
        self.sessions: dict[str, float] = {}
        self.events: list[dict[str, Any]] = []
        self._next_id = 1
        self.requests = 0
        self._by_code = {d[1]: d for d in DEVICES}
        world.events.subscribe(self._on_event)

    # --- події --------------------------------------------------------------------------
    def _on_event(self, ev: Event) -> None:
        p = ev.payload if isinstance(ev.payload, dict) else {}
        if ev.kind != "access" or "event_code" not in p:
            return
        self.add_event(p.get("user_id"), p.get("device") or ev.device or "ACR-IN", int(p["event_code"]),
                       door=p.get("door"), tna_key=p.get("tna_key", ""), ts=ev.ts)

    def _user(self, user_id: str | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        for p in self.world.people:
            if str(p.get("barcode")) == str(user_id):
                return p
        return {"barcode": user_id, "name": str(user_id)}

    def add_event(self, user_id: str | None, device: str, code: int, *, door: str | None = None,
                  tna_key: str = "", ts: dt.datetime | None = None) -> dict[str, Any]:
        ts = ts or self.world.now()
        dev = self._by_code.get(device) or DEVICES[0]
        row = {"id": self._next_id, "ts": ts.astimezone(dt.UTC), "user_id": user_id,
               "device": dev[0], "device_name": dev[2], "door": str(door or dev[4]),
               "code": int(code), "tna_key": str(tna_key or "")}
        self._next_id += 1
        self.events.append(row)
        if len(self.events) > 100_000:
            del self.events[:10_000]
        return row

    def _row(self, e: dict[str, Any]) -> dict[str, Any]:
        tz = self.world.clock.tz
        off = e["ts"].astimezone(tz).utcoffset() or dt.timedelta()
        hours = int(abs(off.total_seconds()) // 3600)
        person = self._user(e["user_id"])
        door_name = DOOR_SHORT.get(e["door"], DOORS.get(e["door"], ""))
        return {
            "id": str(e["id"]), "server_datetime": _iso(e["ts"] + dt.timedelta(seconds=1)),
            "datetime": _iso(e["ts"]), "index": str(e["id"] * 2 + 344),
            "user_id": ({"user_id": str(e["user_id"]), "name": person["name"], "photo_exists": "false"}
                        if person else {"user_id": "", "name": "", "photo_exists": "false"}),
            "user_group_id": (person or {}).get("group") or DEFAULT_GROUP,
            "device_id": {"id": e["device"], "name": e["device_name"]},
            "door_id": [{"id": e["door"], "name": door_name}],
            "event_type_id": {"code": str(e["code"])}, "tna_key": e["tna_key"], "is_dst": "0",
            "timezone": {"half": "0", "hour": str(hours), "negative": "1" if off.total_seconds() < 0 else "0"},
            "user_update_by_device": "false", "hint": f"h{e['id']}"}

    # --- пошук (API-45) -------------------------------------------------------------------
    @staticmethod
    def _value(e: dict[str, Any], key: str) -> Any:
        if key == "datetime":
            return e["ts"]
        if key == "server_datetime":
            return e["ts"] + dt.timedelta(seconds=1)
        if key == "user":
            return str(e["user_id"] or "")
        if key == "group":
            return "1"
        return e[key]

    def _match(self, e: dict[str, Any], cond: dict[str, Any]) -> bool:
        key = _COLUMN_SYNONYMS.get(cond.get("column", ""))
        if key is None:
            raise ValueError(f"unknown column {cond.get('column')!r}")
        op, vals = int(cond.get("operator", 0)), [str(v) for v in cond.get("values", [])]
        v = self._value(e, key)
        if key in ("datetime", "server_datetime"):
            vals_c: list[Any] = [_parse(x) for x in vals]
        elif key in ("id", "code"):
            vals_c = [int(x) for x in vals]
        else:
            vals_c, v = vals, str(v)
        if not vals_c:
            return True
        if op == 0:
            return v == vals_c[0]
        if op == 1:
            return v != vals_c[0]
        if op in (2, 4):
            return str(vals_c[0]).lower() in str(v).lower()
        if op == 3:
            return vals_c[0] <= v <= vals_c[-1]
        if op == 5:
            return v > vals_c[0]
        if op == 6:
            return v < vals_c[0]
        raise ValueError(f"unknown operator {op}")

    def search(self, query: dict[str, Any]) -> dict[str, Any]:
        conds = query.get("conditions") or []
        for c in conds:
            if c.get("column") not in _COLUMN_SYNONYMS:
                raise ValueError(f"unknown column {c.get('column')!r}")
        rows = [e for e in self.events if all(self._match(e, c) for c in conds)]
        orders = query.get("orders") or [{"column": "datetime", "descending": False}]
        for o in reversed(orders):
            col = o.get("column", "datetime")
            if col not in ("datetime", "id"):
                raise ValueError(f"unsupported order column {col!r}")
            desc = str(o.get("descending", False)).lower() == "true"
            rows.sort(key=lambda e, c=col: (e["ts"], e["id"]) if c == "datetime" else e["id"],
                      reverse=desc)
        total = len(rows)
        limit = min(int(query.get("limit", 100)), MAX_LIMIT)
        hint, offset = query.get("hint"), int(query.get("offset", 0))
        if hint:
            for i, e in enumerate(rows):
                if f"h{e['id']}" == hint:
                    offset = i + 1
                    break
            else:
                raise ValueError("invalid hint")
        page = rows[offset:offset + limit]
        return {"EventCollection": {"total": str(total), "rows": [self._row(e) for e in page]}}

    # --- сесії --------------------------------------------------------------------------
    def new_session(self) -> str | None:
        self._expire()
        if len(self.sessions) >= MAX_SESSIONS:
            return None
        sid = str(uuid.uuid4())
        self.sessions[sid] = self._clock()
        return sid

    def _expire(self) -> None:
        now = self._clock()
        for sid in [s for s, t in self.sessions.items() if now - t > SESSION_TTL_S]:
            del self.sessions[sid]

    def touch(self, sid: str | None) -> bool:
        self._expire()
        if sid and sid in self.sessions:
            self.sessions[sid] = self._clock()
            return True
        return False

    def users(self) -> list[dict[str, Any]]:
        rows = [{"user_id": "1", "name": "Administrator", "user_group_id": {"id": "1", "name": "All Users"},
                 "start_datetime": "2001-01-01T00:00:00.00Z", "expiry_datetime": "2030-12-31T23:59:00.00Z",
                 "disabled": "false", "card_count": "0", "face_count": "0", "login_id": self.login}]
        for p in self.world.people:
            if not p.get("barcode"):
                continue
            rows.append({"user_id": str(p["barcode"]), "name": p.get("name", ""),
                         "user_group_id": p.get("group") or DEFAULT_GROUP,
                         "start_datetime": "2001-01-01T00:00:00.00Z",
                         "expiry_datetime": "2030-12-31T23:59:00.00Z", "disabled": "false",
                         "card_count": "1", "face_count": "1", "login_id": ""})
        return rows


def create_app(store: BioStarStore) -> FastAPI:
    app = FastAPI(title="BioStar 2 emulator", docs_url=None, redoc_url=None, openapi_url=None)

    def session_error(request: Request) -> JSONResponse | None:
        store.requests += 1
        if store.touch(request.headers.get("bs-session-id")):
            return None
        log.warning("BioStar 401 invalid session", extra={"proto": "biostar"})
        return fail(401, "1", "Invalid session")

    @app.post("/api/login")
    async def login(request: Request):
        store.requests += 1
        try:
            u = (await request.json())["User"]
            good = (u.get("login_id") == store.login and bool(store.password)
                    and u.get("password") == store.password)
        except (ValueError, KeyError, TypeError, AttributeError):
            good = False
        if not good:
            log.warning("BioStar login failed", extra={"proto": "biostar"})
            return fail(401, "101", "Failed to login for invalid username or password")
        sid = store.new_session()
        if sid is None:
            return fail(429, "102", "Too many sessions")
        return ok({"User": {"user_id": "1", "name": "Administrator", "login_id": store.login}},
                  headers={"bs-session-id": sid})

    @app.post("/api/logout")
    async def logout(request: Request):
        if (err := session_error(request)):
            return err
        store.sessions.pop(request.headers["bs-session-id"], None)
        return ok()

    @app.get("/api/users")
    async def users(request: Request, limit: int = 100, offset: int = 0):
        if (err := session_error(request)):
            return err
        rows = store.users()
        return ok({"UserCollection": {"total": str(len(rows)), "rows": rows[offset:offset + limit]}})

    @app.get("/api/devices")
    async def devices(request: Request):
        if (err := session_error(request)):
            return err
        rows = [{"id": d[0], "name": d[2], "device_type_id": {"id": "62", "name": "BioEntry W3"},
                 "status": "1", "ip": d[3], "port": "51211", "door": d[4]} for d in DEVICES]
        return ok({"DeviceCollection": {"rows": rows}})

    @app.get("/api/doors")
    async def doors(request: Request):
        if (err := session_error(request)):
            return err
        rows = [{"id": k, "name": v, "status": "1", "open_duration": "5",
                 **({"entry_device_id": {"id": "5390001"}} if k == "1" else {})}
                for k, v in DOORS.items()]
        return ok({"DoorCollection": {"rows": rows}})

    @app.post("/api/events/search")
    async def events_search(request: Request):
        if (err := session_error(request)):
            return err
        try:
            query = (await request.json())["Query"]
            return ok(store.search(query))
        except (KeyError, TypeError, ValueError) as exc:
            return fail(400, "2", f"Invalid query: {exc}")

    @app.get("/api/event_types")
    async def event_types(request: Request):
        if (err := session_error(request)):
            return err
        rows = [{"code": str(c), "name": n, "description": n} for c, n in EVENT_TYPES.items()]
        return ok({"EventTypeCollection": {"rows": rows}})

    return app


def ensure_cert(cert_dir: Path) -> tuple[Path, Path]:
    """Самопідписаний сертифікат ``biostar.crt/.key`` (створюється, якщо немає)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    cert_dir.mkdir(parents=True, exist_ok=True)
    crt, key = cert_dir / "biostar.crt", cert_dir / "biostar.key"
    if crt.exists() and key.exists():
        return crt, key
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "iot-sim")])
    now = dt.datetime.now(dt.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName("iot-sim"), x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(k, hashes.SHA256()))
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()))
    key.chmod(0o600)
    return crt, key


class BioStarApi(ProtocolServer):
    name = "biostar"

    def __init__(self, world: World, *, port_http: int = 8081, port_https: int | None = 8443,
                 host: str = "0.0.0.0", user: str = "admin", password: str = "",
                 cert_dir: str | Path = "./certs") -> None:
        self.world, self.host = world, host
        self.port_http, self.port_https = port_http, port_https
        self.store = BioStarStore(world, login=user, password=password)
        self.app = create_app(self.store)
        self.cert_dir = Path(cert_dir)
        self._http = UvicornRunner(self.app, host, port_http)
        self._https: UvicornRunner | None = None

    async def start(self) -> None:
        await self._http.start()
        if self.port_https:
            crt, key = ensure_cert(self.cert_dir)
            runner = UvicornRunner(self.app, self.host, self.port_https)
            runner.server = uvicorn.Server(uvicorn.Config(
                self.app, host=self.host, port=self.port_https, log_level="warning", lifespan="off",
                ssl_certfile=str(crt), ssl_keyfile=str(key)))
            runner.server.capture_signals = contextlib.nullcontext  # type: ignore[method-assign]
            self._https = runner
            await runner.start()

    async def stop(self) -> None:
        await self._http.stop()
        if self._https is not None:
            await self._https.stop()

    def health(self) -> dict:
        up = self._http.up and (self._https is None or self._https.up)
        return {"proto": self.name, "up": up, "port": self.port_http, "port_https": self.port_https,
                "sessions": len(self.store.sessions), "events": len(self.store.events)}
