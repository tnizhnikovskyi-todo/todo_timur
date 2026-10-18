"""Спільні засоби стенда machine_connect (SPEC §13.2–§13.4). Змінні: F3D_STAND_ODOO_URL/DB/LOGIN/PASSWORD (XML-RPC),
F3D_STAND_SIM_URL, SIM_API_TOKEN, SIM_OPCUA_USER/PASS, SIM_WOODSTORE_APIKEY, SIM_JOBS_APIKEY, F3D_STAND_COLLECTOR_METRICS,
F3D_STAND_DIR. Копії http/wait/Sim/Metrics — зі стенда телеметрії (tests/stand колектора); додано OPC UA, woodStore, оптимізатор.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parents[1]
STAND_DIR = Path(os.environ.get("F3D_STAND_DIR", "/tmp/f3dmc"))
SIM_URL = os.environ.get("F3D_STAND_SIM_URL", "http://127.0.0.1:8090/sim/v1")
SIM_TOKEN = os.environ.get("SIM_API_TOKEN", "stand-token-0123456789abcdef0123456789")
METRICS_URL = os.environ.get("F3D_STAND_COLLECTOR_METRICS", "http://127.0.0.1:9108")
OPCUA_URL = os.environ.get("F3D_STAND_OPCUA", "opc.tcp://127.0.0.1:4840/f3d/")
OPCUA_USER = os.environ.get("SIM_OPCUA_USER", "collector")
OPCUA_PASS = os.environ.get("SIM_OPCUA_PASS", "opcua-pass-stand")
WS_URL = os.environ.get("F3D_STAND_WOODSTORE", "http://127.0.0.1:8082")
WS_KEY = os.environ.get("SIM_WOODSTORE_APIKEY", "ws-key-stand-0123456789")
JOBS_URL = os.environ.get("F3D_STAND_CUTOPT", "http://127.0.0.1:8083")
JOBS_KEY = os.environ.get("SIM_JOBS_APIKEY", "jobs-key-stand-0123456789")
NS_INST = "http://todo.ltd/f3d/iot_sim/instances/"
P = "td.machine_connect."
KYIV = timezone(timedelta(hours=3))  # EEST до 25.10.2026


def http(method: str, url: str, body=None, headers=None, raw: bytes | None = None, timeout: float = 15.0):
    """(status, text, headers) без винятків на 4xx/5xx."""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    hd = dict(headers or {})
    if body is not None and "Content-Type" not in hd:
        hd["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=hd)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def wait(fn, timeout: float = 30, step: float = 1.0):
    """Опитує fn() до першого істинного значення (його й повертає) або None після timeout."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
        except Exception:  # noqa: BLE001 — Odoo/мережа можуть бути тимчасово недоступні
            v = None
        if v:
            return v
        time.sleep(step)
    return None


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)  # Odoo віддає наївні UTC


def dt(s) -> datetime | None:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None


class Sim:
    """Пульт емулятора (iot_sim §7.2)."""

    def __init__(self, base: str, token: str):
        self.base, self.token = base, token

    def req(self, method, path, body=None):
        return http(method, self.base + path, body, {"Authorization": "Bearer " + self.token})

    def _j(self, method, path, body=None):
        st, txt, _ = self.req(method, path, body)
        return st, (json.loads(txt) if txt.startswith(("{", "[")) else txt)

    def get(self, path):
        return self._j("GET", path)

    def post(self, path, body=None):
        return self._j("POST", path, body or {})

    def put(self, path, body=None):
        return self._j("PUT", path, body or {})

    def sig(self, code):
        st, d = self.get("/signals/" + code)
        assert st == 200, (code, d)
        return d

    def hold(self, code: str, value, hold_s: int = 1800):
        st, d = self.put("/signals/" + code, {"value": value, "hold_s": hold_s})
        assert st == 200, (code, st, d)
        return d

    def release(self, code: str):
        return self.put("/signals/" + code, {"release": True})

    def scenario(self, name, **params):
        st, d = self.post(f"/scenario/{name}/start", {"params": params})
        assert st == 201, (st, d)
        return d

    def stop(self, name):
        return self.post(f"/scenario/{name}/stop")

    def reset(self, keep_time=True):
        return self.post("/reset", {"keep_time": keep_time})

    def sync_time(self):
        """Правила часу §13.2: factor=1, годинник емулятора = реальний (`|sim_now − real_now| ≤ 5 с`)."""
        self.post("/time", {"factor": 1})
        self.post("/time", {"set": datetime.now(KYIV).isoformat(timespec="seconds")})

    def clock_skew_s(self) -> float:
        _, d = self.get("/status")
        return abs((datetime.fromisoformat(d["sim_now"]) - datetime.fromisoformat(d["real_now"])).total_seconds())


class Metrics:
    def __init__(self, base: str):
        self.base = base

    def text(self) -> str:
        return http("GET", self.base + "/metrics")[1]

    def get(self, name: str, **labels) -> float | None:
        total, found = 0.0, False
        for line in self.text().splitlines():
            if not line.startswith(name) or line.startswith("#"):
                continue
            head, _, val = line.rpartition(" ")
            if head[len(name) : len(name) + 1] not in ("{", ""):
                continue
            if all(f'{k}="{v}"' in head for k, v in labels.items()):
                total += float(val)
                found = True
        return total if found else None

    def health(self) -> dict:
        return json.loads(http("GET", self.base + "/health")[1])


# --- OPC UA (пульт оператора й читання черги; asyncua з користувачем SIM_OPCUA_USER) ----------------------------
def _run(coro):
    return asyncio.run(coro)


async def _ua_session(user: str | None, password: str | None):
    from asyncua import Client

    c = Client(OPCUA_URL, timeout=10)
    if user:
        c.set_user(user)
        c.set_password(password or "")
    await c.connect()
    return c


def ua_call(code: str, method: str, job_id: str = "", comment: str = "", user: str | None = OPCUA_USER) -> int:
    """Виклик `JobOrderControl.<method>(JobOrderID, Comment)` (як оператор на пульті) → ReturnStatus."""

    async def go():
        c = await _ua_session(user, OPCUA_PASS)
        try:
            ns = await c.get_namespace_index(NS_INST)
            obj = c.get_node(f"ns={ns};s={code}.JobManagement.JobOrderControl")
            return await obj.call_method(f"{ns}:{method}", job_id, comment)
        finally:
            await c.disconnect()

    return _run(go())


def ua_jobs(code: str) -> list[str]:
    """`JobOrderList` верстата (анонімне читання)."""

    async def go():
        c = await _ua_session(None, None)
        try:
            ns = await c.get_namespace_index(NS_INST)
            v = await c.get_node(f"ns={ns};s={code}.JobManagement.JobOrderControl.JobOrderList").read_value()
            return [
                getattr(x, "JobOrderID", None) or getattr(getattr(x, "JobOrder", None), "JobOrderID", None) or str(x)
                for x in v
            ]
        finally:
            await c.disconnect()

    return _run(go())


# --- woodStore / оптимізатор -----------------------------------------------------------------------------------
def ws(method: str, path: str, body=None, key: str | None = WS_KEY):
    hd = {"X-Api-Key": key} if key else {}
    st, txt, _ = http(method, WS_URL + path, body, hd)
    return st, (json.loads(txt) if txt[:1] in "{[" and txt else txt)


def cutopt(method: str, path: str, body=None, raw=None, headers=None, key: str | None = JOBS_KEY):
    hd = {"X-Api-Key": key} if key else {}
    hd.update(headers or {})
    st, txt, hh = http(method, JOBS_URL + path, body, hd, raw=raw)
    return st, (json.loads(txt) if txt[:1] in "{[" and txt else txt)


# --- керування процесами стенда ----------------------------------------------------------------------------------
def stand_sh(*args: str, env: dict | None = None, timeout: int = 300) -> str:
    r = subprocess.run(
        [str(HERE / "stand.sh"), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        timeout=timeout,
        check=False,
    )
    return (r.stdout + r.stderr).strip()


def collector_log() -> str:
    p = STAND_DIR / "collector.log"
    return p.read_text(errors="replace") if p.exists() else ""


def odoo_log() -> str:
    p = Path(os.environ.get("F3D_ODOO_LOG", "/home/user/odoo19-data/logs/serve-f3d_mc_tk.log"))
    return p.read_text(errors="replace") if p.exists() else ""


def psql(sql: str, db: str = "f3d_mc_tk") -> list[list[str]]:
    """SQL до бази стенда (знімки S0–S5, §13.5 п. 2); рядки — списки текстових полів."""
    r = subprocess.run(
        ["psql", "-h", "localhost", "-U", "odoo", "-d", db, "-X", "-q", "-At", "-F", "|", "-c", sql],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-300:]
    return [ln.split("|") for ln in r.stdout.splitlines() if ln]


def machine(o, code: str, fields=None) -> dict:
    return o.search_read(
        "td.machine", [("code", "=", code)], fields or ["code", "state", "raw_state", "raw_job", "active_workorder_id"]
    )[0]


def downtimes(o, code: str, open_only: bool = False) -> list[dict]:
    dom = [("machine_id.code", "=", code)] + ([("date_end", "=", False)] if open_only else [])
    return o.search_read(
        "td.downtime",
        dom,
        [
            "date_start",
            "date_end",
            "loss_id",
            "reason_state",
            "hint_loss_id",
            "hint_text",
            "state_kind",
            "maintenance_request_id",
        ],
        order="id",
    )


def state_log(o, code: str) -> list[dict]:
    return o.search_read(
        "td.machine.state.log", [("machine_id.code", "=", code)], ["state", "date_start", "date_end"], order="id"
    )


def enable_write(o, sources: list[str], signals: list[str]) -> None:
    """Чотири запобіжники Odoo (п'ятий — `F3D_WRITE_ENABLED=1` у середовищі колектора, див. `fresh(env=…)`)."""
    o.param(P + "write_enabled", "True")
    o.param("td.telemetry.write_enabled", "True")
    for code in sources:
        o.write(
            "td.source", o.search_read("td.source", [("code", "=", code)], ["id"])[0]["id"], {"write_enabled": True}
        )
    for code in signals:
        o.write(
            "td.signal", o.search_read("td.signal", [("code", "=", code)], ["id"])[0]["id"], {"write_enabled": True}
        )


def make_mo(o, product_code: str, qty: float) -> dict:
    """МО за специфікацією з seed_pre.py: створити, підтвердити, зарезервувати → `{"id", "name", "wo": [{id, wc, state}]}`."""
    prod = o.search_read("product.product", [("default_code", "=", product_code)], ["id", "product_tmpl_id"])[0]
    bom = o.search_read("mrp.bom", [("product_tmpl_id", "=", prod["product_tmpl_id"][0])], ["id"])[0]["id"]
    mid = o.create("mrp.production", {"product_id": prod["id"], "product_qty": qty, "bom_id": bom})
    o.call("mrp.production", "action_confirm", [mid])
    o.call("mrp.production", "action_assign", [mid])
    mo = o.read("mrp.production", mid, ["name"])[0]
    wos = o.search_read(
        "mrp.workorder", [("production_id", "=", mid)], ["workcenter_id", "state", "qty_remaining"], order="id"
    )
    return {
        "id": mid,
        "name": mo["name"],
        "wo": [{"id": w["id"], "wc": w["workcenter_id"][1], "state": w["state"]} for w in wos],
    }


def wo_of(o, mo: dict, code: str) -> int:
    wcs = o.search_read("mrp.workcenter", [("td_code", "=", code)], ["name"])
    return next(w["id"] for w in mo["wo"] if w["wc"] == wcs[0]["name"])


def commands(o, signal_code: str | None = None) -> list[dict]:
    dom = [("signal_id.module", "=", "machine_connect")]
    if signal_code:
        dom = [("signal_id.code", "=", signal_code)]
    return o.search_read(
        "td.command", dom, ["state", "text", "payload", "result_data", "signal_id", "error"], order="id"
    )


def multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes]]) -> tuple[bytes, str]:
    """multipart/form-data без зовнішніх залежностей → (тіло, Content-Type)."""
    b = "----f3dstand%d" % time.time_ns()
    out = []
    for k, v in fields.items():
        out.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (fn, data) in files.items():
        out.append(
            f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: text/csv\r\n\r\n'.encode()
        )
        out.append(data + b"\r\n")
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"


def proc_ticks(pattern: str) -> tuple[int | None, float]:
    """(pid, CPU-секунди з /proc/<pid>/stat) першого процесу, чий cmdline містить pattern."""
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid():
            continue
        try:
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            if pattern in cmd and "pytest" not in cmd:
                f = (d / "stat").read_text().rsplit(")", 1)[1].split()
                return int(d.name), (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
        except (OSError, IndexError):
            continue
    return None, 0.0


def rss_mb(pid: int) -> float:
    for ln in Path(f"/proc/{pid}/status").read_text().splitlines():
        if ln.startswith("VmRSS:"):
            return int(ln.split()[1]) / 1024
    return 0.0


def cron_run(o, name_like: str) -> float:
    """Прямий запуск крона (як кнопка «Запустити вручну») → секунди."""
    cid = o.search_read("ir.cron", [("cron_name", "ilike", name_like)], ["id"], context={"active_test": False})
    assert cid, name_like
    t = time.time()
    o.call("ir.cron", "method_direct_trigger", [cid[0]["id"]])
    return time.time() - t


def make_cert(
    der_path: Path, key_path: Path, uri: str, cn: str
) -> None:  # key_path.suffix == ".pem" → PEM, інакше DER (asyncua)
    """Самопідписаний сертифікат (DER) і ключ (PEM) з SAN URI — для ТБ-07 (SignAndEncrypt, Basic256Sha256)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri), x509.DNSName("iot-sim")]), critical=False
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(x509.KeyUsage(True, True, True, True, False, False, False, False, False), critical=True)
        .sign(key, hashes.SHA256())
    )
    der_path.write_bytes(cert.public_bytes(serialization.Encoding.DER))
    pem = key_path.suffix == ".pem"  # asyncua визначає формат ключа за розширенням файла
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM if pem else serialization.Encoding.DER,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)


FAKE_UA_PORT = 4841
FAKE_ENV = {"F3D_EXTRA_ENV": "F3D_OPCUA_PASSWORD=pw"}  # фейковий сервер пакета приймає користувача collector/pw


class FakeUa:
    """Фейковий OPC UA-сервер пакета (tests/fakes/opcua_server.py) у фоновому потоці — для сценаріїв, яких iot_sim не підтримує
    (структури ISA-95 у JobOrderList, методи Store/Start зі структурою, події WwBaseEventType/MessageId). Колектор бачить його як
    `iot-sim:4841` (allow-list)."""

    def __init__(self, machines: tuple[str, ...]):
        import asyncio
        import threading

        from ..fakes.opcua_server import FakeMachines

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.srv = FakeMachines(port=FAKE_UA_PORT, machines=machines)
        self.run(self.srv.start())
        self.endpoint = f"opc.tcp://iot-sim:{FAKE_UA_PORT}/f3d/"

    def run(self, coro):
        import asyncio

        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(30)

    def set(self, var, value, machine):
        return self.run(self.srv.set(var, value, machine))

    def set_jobs(self, items, machine):
        return self.run(self.srv.set_jobs(items, machine))

    def event(self, *a, **kw):
        return self.run(self.srv.fire_event(*a, **kw))

    @property
    def calls(self):
        return self.srv.calls

    def stop(self):
        try:
            self.run(self.srv.stop())
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)


def redirect_source(o, code: str, endpoint: str) -> None:
    """Джерело UA-<код> → інший endpoint (фейковий сервер); колектор підхопить конфігурацію за ≤ 30 с."""
    sid = o.search_read("td.source", [("code", "=", code)], ["id", "params"])[0]
    o.write("td.source", sid["id"], {"params": dict(sid["params"], endpoint=endpoint)})


def set_iot_sim_ip(ip: str) -> None:
    """`iot-sim` у /etc/hosts → ip. Для ТБ-08: на стенді `iot-sim` = 127.0.0.1 = хост Odoo, який allow-list додає автоматично,
    тож без окремої адреси відмову allow-list перевірити не можна (емулятор слухає 0.0.0.0, доступний і на 127.0.0.2)."""
    p = Path("/etc/hosts")
    lines = [ln for ln in p.read_text().splitlines() if not ln.rstrip().endswith("iot-sim")]
    p.write_text("\n".join(lines + [f"{ip} iot-sim"]) + "\n")
