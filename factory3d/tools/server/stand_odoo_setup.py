#!/usr/bin/env python3
"""Odoo-сторона постоянного стенда (E-11): токен сборщика, параметры, backfill истории. Только stdlib, XML-RPC.

Запускает менеджер снаружи, после установки новой БД с модулями td_*:

    export ODOO_URL=https://timur-o19demo.todo.ltd ODOO_DB=odoo ODOO_USER=admin ODOO_PASSWORD=...   # пароль или
    API-ключ
    python3 stand_odoo_setup.py setup > td-stand.secrets   # токены ОДИН раз в stdout, остальное в stderr
    python3 stand_odoo_setup.py status                     # состояние без секретов
    python3 stand_odoo_setup.py backfill                   # через >= 5 мин после запуска стенда (электрика + ресурсы)
    python3 stand_odoo_setup.py seed                       # затем демо-данные аналитики W4
    python3 stand_odoo_setup.py genset --token-file td-stand.secrets   # «живой» генератор td_genset (имитатор)

Команды:
  setup     коллектор COL-MAIN (создать/включить), токен сборщика (если ещё не выдан или --rotate), токен API эмулятора,
            параметры ir.config_parameter, params источника HTTP-PUSH. В stdout печатает строки KEY=VALUE:
            TD_COLLECTOR_TOKEN (виден только сейчас: в Odoo хранится хэш) и TD_SIM_API_TOKEN (лежит в td.iot_sim.token).
            Файл с этими строками клиент передаёт install_stand.sh как TD_SECRETS_FILE.
  params    только параметры (без токенов).
  backfill  td.energy.interval._td_backfill(days=90) (R-36). Метод приватный, по RPC его вызвать нельзя, поэтому
            скрипт создаёт временное серверное действие, запускает и удаляет его. Опции --days, --seed, --purge,
            --force.
  genset    генератор td_genset + имитатор ретранслятора SmartGen (fake_relay, профиль D700; ставит install_stand.sh):
            td.genset с профилем D700 и адресом имитатора (--relay-url, по умолчанию шлюз сети compose :8087), токен API
            из файла --token-file (нет в файле: генерируется и дописывается; в вывод не печатается), связка
            td.genset3d.link с 3D-объектом и узлом энергосети GENSET, крони td_genset включены. Идемпотентно, ничего не
            удаляет; на адрес настоящего ретранслятора SmartGen (порт 8081, *.todo.ltd) не подключает.
            Опции --relay-url, --token-file, --hostid, --wait, --force.
  status    состояние коллектора, источников, свежих показаний и истории.

Переменные: ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD (обязательны); TD_COLLECTOR_CODE (COL-MAIN), TD_SIM_URL
(http://127.0.0.1:8090: адрес эмулятора, как его видит Odoo), TD_SIM_API_TOKEN (задать свой вместо генерации),
TD_SIM_WRITE_ENABLED (1/0, по умолчанию 1: сценарии и сбои из пульта Odoo), TD_RPC_TIMEOUT (с, 1800); для genset ещё
TD_RELAY_URL, TD_RELAY_TOKEN_FILE, TD_SIM_PORT_GENSET_RELAY (8087), TD_GENSET_RELAY_HOSTID.
Пароль и токены в аргументах командной строки не передаются и в stderr не печатаются.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import secrets
import sys
import time
import urllib.parse
import xmlrpc.client

COLLECTOR_NAME = "Основной коллектор (стенд)"
HTTP_PUSH_CODE = "HTTP-PUSH"
# Имена переменных окружения сборщика, на которые ссылается params источника (сами значения — в
# /etc/td-stand/collector.env)
HTTP_PUSH_PARAMS = {
    "routes": ["lpr"],
    "allow_ips": ["iot-sim", "127.0.0.1"],
    "token_ref": "F3D_HTTP_PUSH_TOKEN_LPR",
    "secret_ref": "F3D_HTTP_PUSH_SECRET_LPR",
}
# Модули с флагами read/write в ir.config_parameter: на стенде читаем (True), пишем в устройства — нет (False).
FLAG_MODULES = ("telemetry", "energy", "bms", "yard", "fire_safety", "genset", "machine_connect", "access")


def info(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def die(msg: str, code: int = 1) -> None:
    info(f"ОШИБКА: {msg}")
    sys.exit(code)


def _with_timeout(base: type[xmlrpc.client.Transport], timeout: float) -> xmlrpc.client.Transport:
    """Транспорт XML-RPC с таймаутом сокета (backfill может идти минуты)."""

    class _T(base):  # type: ignore[valid-type, misc]
        def make_connection(self, host):  # type: ignore[no-untyped-def]
            conn = super().make_connection(host)
            conn.timeout = timeout
            return conn

    return _T()


class Odoo:
    """Минимальный клиент XML-RPC (execute_kw)."""

    def __init__(self) -> None:
        try:
            self.url = os.environ["ODOO_URL"].rstrip("/")
            self.db = os.environ["ODOO_DB"]
            self.user = os.environ["ODOO_USER"]
            self._password = os.environ["ODOO_PASSWORD"]
        except KeyError as e:
            die(f"не задана переменная окружения {e.args[0]} (нужны ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)", 2)
        timeout = float(os.environ.get("TD_RPC_TIMEOUT", "1800"))
        https = self.url.startswith("https://")

        def proxy(path: str) -> xmlrpc.client.ServerProxy:
            transport = _with_timeout(xmlrpc.client.SafeTransport if https else xmlrpc.client.Transport, timeout)
            return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/{path}", transport=transport, allow_none=True)

        self._common, self._object = proxy("common"), proxy("object")
        try:
            self.uid = self._common.authenticate(self.db, self.user, self._password, {})
        except (OSError, xmlrpc.client.ProtocolError) as e:
            die(f"Odoo {self.url} недоступен: {e}")
        if not self.uid:
            die(f"Odoo отклонил вход {self.user!r} в базу {self.db!r}")

    def call(self, model: str, method: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return self._object.execute_kw(self.db, self.uid, self._password, model, method, list(args), kwargs)
        except xmlrpc.client.Fault as e:
            msg = (e.faultString or "").strip().splitlines()
            die(f"{model}.{method}: {msg[-1] if msg else e.faultCode}")

    def soft(self, model: str, method: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Как call, но без завершения скрипта: (True, результат) или (False, последняя строка ошибки)."""
        try:
            return True, self._object.execute_kw(self.db, self.uid, self._password, model, method, list(args), kwargs)
        except xmlrpc.client.Fault as e:
            msg = (e.faultString or "").strip().splitlines()
            return False, msg[-1] if msg else str(e.faultCode)

    def search_read(self, model, domain, fields, **kw):  # type: ignore[no-untyped-def]
        return self.call(model, "search_read", domain, fields, **kw)

    def param(self, key: str) -> str:
        return self.call("ir.config_parameter", "get_param", key) or ""

    def set_param(self, key: str, value: str) -> None:
        self.call("ir.config_parameter", "set_param", key, value)

    def model_exists(self, name: str) -> bool:
        return bool(self.call("ir.model", "search_count", [("model", "=", name)]))


# --------------------------------------------------------------------------------------------- setup
def ensure_collector(odoo: Odoo, code: str, rotate: bool) -> str | None:
    """Коллектор + токен. Токен возвращается только если выдан сейчас (в Odoo хранится sha256)."""
    if not odoo.model_exists("td.collector"):
        die("в базе нет модели td.collector: установите модуль td_telemetry")
    rows = odoo.search_read(
        "td.collector",
        [("code", "=", code)],
        ["id", "active", "token_set_at", "token_hint"],
        context={"active_test": False},
    )
    if rows:
        rec = rows[0]
        cid = rec["id"]
        if not rec["active"]:
            odoo.call("td.collector", "write", [cid], {"active": True})
            info(f"коллектор {code}: был архивным, включён")
    else:
        cid = odoo.call("td.collector", "create", {"code": code, "name": COLLECTOR_NAME})
        rec = {"token_set_at": False, "token_hint": False}
        info(f"коллектор {code}: создан (id {cid})")
    if rec.get("token_set_at") and not rotate:
        info(
            f"токен коллектора {code} уже выдан (последние символы …{rec.get('token_hint') or '?'}): "
            "новый не выпускаю. "
            "Потеряли значение, а сборщик ещё не подключён — повторите с --rotate (прежний токен перестанет работать)."
        )
        return None
    action = odoo.call("td.collector", "action_generate_token", [cid])
    token = ((action or {}).get("context") or {}).get("default_token")
    if not token:
        die("td.collector.action_generate_token не вернул токен (нужна группа td_factory3d.group_td_admin)")
    info(f"токен коллектора {code} выдан (…{token[-4:]}); печатаю один раз в stdout")
    return token


def ensure_params(odoo: Odoo, sim_token: str | None) -> str:
    """Параметры стенда. Возвращает токен API эмулятора (из Odoo или новый)."""
    sim_url = os.environ.get("TD_SIM_URL", "http://127.0.0.1:8090").rstrip("/")
    write_sim = "True" if os.environ.get("TD_SIM_WRITE_ENABLED", "1").lower() in ("1", "true", "yes") else "False"
    token = sim_token or os.environ.get("TD_SIM_API_TOKEN") or odoo.param("td.iot_sim.token")
    if not token:
        token = secrets.token_hex(24)
        info("токен API эмулятора сгенерирован")
    want = {
        "td.iot_sim.url": sim_url,
        "td.iot_sim.token": token,
        "td.iot_sim.read_enabled": "True",
        "td.iot_sim.write_enabled": write_sim,
    }
    for mod in FLAG_MODULES:  # только уже существующие ключи: не плодим параметры модулей, которых нет в базе
        for flag, value in (("read_enabled", "True"), ("write_enabled", "False")):
            key = f"td.{mod}.{flag}"
            if odoo.call("ir.config_parameter", "search_count", [("key", "=", key)]):
                want.setdefault(key, value)
    changed = []
    for key, value in want.items():
        if odoo.param(key) != value:
            odoo.set_param(key, value)
            changed.append(key)
    info("параметры: " + (", ".join(changed) if changed else "уже в нужном состоянии"))
    env = odoo.param("td.base.environment")
    if env != "test":
        info(
            f"ВНИМАНИЕ: td.base.environment = {env!r} (на тестовом сервере ожидается 'test'; хук td_telemetry включает "
            "чтение только в нём). Скрипт это не меняет."
        )
    ensure_http_push(odoo)
    return token


def ensure_http_push(odoo: Odoo) -> None:
    """params источника HTTP-PUSH (приёмник LPR): маршрут, разрешённые отправители, имена секретов (не значения)."""
    rows = odoo.search_read(
        "td.source", [("code", "=", HTTP_PUSH_CODE)], ["id", "params"], context={"active_test": False}
    )
    if not rows:
        info(f"источник {HTTP_PUSH_CODE} не найден (td_telemetry не загрузил данные стенда?): params пропущены")
        return
    cur = dict(rows[0].get("params") or {})
    new = {**cur, **HTTP_PUSH_PARAMS}
    allow = list(dict.fromkeys(list(cur.get("allow_ips") or []) + HTTP_PUSH_PARAMS["allow_ips"]))
    new["allow_ips"] = allow
    new["routes"] = list(dict.fromkeys(list(cur.get("routes") or []) + HTTP_PUSH_PARAMS["routes"]))
    if new != cur:
        odoo.call("td.source", "write", [rows[0]["id"]], {"params": new})
        info(f"источник {HTTP_PUSH_CODE}: params обновлены (routes, allow_ips, token_ref, secret_ref)")
    else:
        info(f"источник {HTTP_PUSH_CODE}: params уже в нужном состоянии")


def cmd_setup(odoo: Odoo, args: argparse.Namespace) -> None:
    code = os.environ.get("TD_COLLECTOR_CODE", "COL-MAIN")
    col_token = ensure_collector(odoo, code, args.rotate)
    sim_token = ensure_params(odoo, None)
    if col_token:
        print(f"TD_COLLECTOR_TOKEN={col_token}")
    print(f"TD_SIM_API_TOKEN={sim_token}")
    info(
        "готово. Дальше: клиент запускает install_stand.sh с этими строками (TD_SECRETS_FILE), "
        "через >= 5 минут — команда backfill."
    )


def cmd_params(odoo: Odoo, args: argparse.Namespace) -> None:
    ensure_params(odoo, None)


# --------------------------------------------------------------------------------------------- backfill
BACKFILL_CODE = """\
res = env[%(model)r]._td_backfill(days=%(days)d, until=%(until)r, seed=%(seed)d, purge=%(purge)s)
action = {'type': 'ir.actions.act_window_close', 'td_result': str(res)}
"""
SEED_CODE = """\
res = env['td.energy.analytics']._td_seed_demo(days=%(days)d, seed=%(seed)d)
action = {'type': 'ir.actions.act_window_close', 'td_result': str(res)}
"""
# Прокси перед Odoo (Cloudflare) рве запит ~100 с, а Odoo знімає воркер за limit_time_real: історію пишемо шматками
# по --chunk-days діб — кожен шматок окремим коротким викликом; запис ідемпотентний (ON CONFLICT DO NOTHING).
TARGETS = {"energy": "td.energy.interval", "resources": "td.energy.res.interval"}


def _run_code(odoo: Odoo, act: int, code: str, retries: int = 1):
    """Записати код у тимчасову серверну дію й виконати; 502/504 (обрив проксі) — один повтор."""
    odoo.call("ir.actions.server", "write", [act], {"code": code})
    for attempt in range(retries + 1):
        try:
            result = odoo.call("ir.actions.server", "run", [act])
            return (result or {}).get("td_result") if isinstance(result, dict) else result
        except xmlrpc.client.ProtocolError as e:
            if e.errcode not in (502, 504) or attempt == retries:
                raise
            info(f"обрив {e.errcode}, повторюю шматок (запис ідемпотентний)")
    return None


def cmd_backfill(odoo: Odoo, args: argparse.Namespace) -> None:
    if not odoo.model_exists("td.energy.interval"):
        die("в базе нет td.energy.interval: установите модуль td_energy")
    if not args.force and not args.purge:
        n = odoo.call("td.reading", "search_count", [("src", "=", "collector")])
        if not n:
            die(
                "в базе ещё нет показаний от сборщика: R-36 требует, чтобы стенд проработал >= 5 минут "
                "(повторите позже или добавьте --force)",
                3,
            )
        first = odoo.search_read("td.reading", [("src", "=", "collector")], ["ts"], order="ts asc", limit=1)[0]["ts"]
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.strptime(first, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=dt.timezone.utc
        )
        if age < dt.timedelta(minutes=5):
            die(
                f"первое показание сборщика пришло {int(age.total_seconds())} с назад, нужно >= 300 с "
                "(иначе на стыке истории и живых данных будут пропуски; --force обходит проверку)",
                3,
            )
    first_rows = odoo.search_read("td.reading", [("src", "=", "collector")], ["ts"], order="ts asc", limit=1)
    anchor = (
        dt.datetime.strptime(first_rows[0]["ts"], "%Y-%m-%d %H:%M:%S")
        if first_rows
        else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    )
    anchor = anchor.replace(second=0, microsecond=0) + dt.timedelta(minutes=(15 - anchor.minute % 15) % 15)
    targets = ["energy", "resources"] if args.target == "all" else [args.target]
    for target in targets:
        model = TARGETS[target]
        if not odoo.model_exists(model):
            info(f"{model}: моделі немає (модуль не встановлено) — пропускаю")
            continue
        act = odoo.call(
            "ir.actions.server",
            "create",
            {
                "name": "td-stand: backfill історії (тимчасова, видаляється)",
                "model_id": odoo.call("ir.model", "search", [("model", "=", model)], limit=1)[0],
                "state": "code",
                "code": "action = False",
            },
        )
        try:
            if args.purge:
                windows = [(args.days, anchor)]
            else:
                step = max(1, args.chunk_days)
                windows = []
                left = args.days
                while left > 0:
                    d = min(step, left)
                    windows.append((d, anchor - dt.timedelta(days=left - d)))
                    left -= d
            for i, (days, until) in enumerate(windows, 1):
                info(f"{model}: шматок {i}/{len(windows)} — {days} діб до {until:%Y-%m-%d %H:%M} UTC")
                code = BACKFILL_CODE % {
                    "model": model, "days": days, "until": until.strftime("%Y-%m-%d %H:%M:%S"),
                    "seed": args.seed, "purge": bool(args.purge),
                }  # fmt: skip
                res = _run_code(odoo, act, code)
                if res:
                    info(f"    {str(res)[:200]}")
        finally:
            odoo.call("ir.actions.server", "unlink", [act])
        n = odoo.call(model, "search_count", [("is_backfill", "=", True)])
        info(f"{model}: рядків із is_backfill=True: {n}")
    print("backfill: готово")


def cmd_seed(odoo: Odoo, args: argparse.Namespace) -> None:
    """W4 R-20: демо-дані аналітики за `--days` діб (після backfill електрики й ресурсів); повтор замінює попередній."""
    if not odoo.model_exists("td.energy.analytics"):
        die("у базі немає td.energy.analytics: встановіть модуль td_energy_analytics")
    act = odoo.call(
        "ir.actions.server",
        "create",
        {
            "name": "td-stand: демо аналітики (тимчасова, видаляється)",
            # td.energy.analytics — абстрактна модель без ACL: run() відмовляє; дія вішається на td.energy.daily
            "model_id": odoo.call("ir.model", "search", [("model", "=", "td.energy.daily")], limit=1)[0],
            "state": "code",
            "code": "action = False",
        },
    )
    try:
        info(f"запускаю _td_seed_demo(days={args.days}): до кількох хвилин")
        res = _run_code(odoo, act, SEED_CODE % {"days": args.days, "seed": args.seed}, retries=0)
    finally:
        odoo.call("ir.actions.server", "unlink", [act])
    print(f"seed: {str(res)[:300] if res else 'готово'}")


# --------------------------------------------------------------------------------------------- status
def cmd_status(odoo: Odoo, args: argparse.Namespace) -> None:
    code = os.environ.get("TD_COLLECTOR_CODE", "COL-MAIN")
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    five = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Odoo {odoo.url} db={odoo.db} uid={odoo.uid}, UTC сейчас {now}")
    col = odoo.search_read(
        "td.collector",
        [("code", "=", code)],
        ["state", "last_seen", "last_push_at", "version", "buffer_rows", "token_hint", "token_set_at"],
        context={"active_test": False},
    )
    print("коллектор:", col[0] if col else "НЕТ записи " + code)
    for state in ("online", "offline", "error", "disabled", "unknown"):
        n = odoo.call("td.source", "search_count", [("state", "=", state)])
        if n:
            print(f"источников {state}: {n}")
    print(
        "сигналов всего:",
        odoo.call("td.signal", "search_count", []),
        "| обновлено за 5 мин:",
        odoo.call("td.signal", "search_count", [("last_ts", ">=", five)]),
    )
    print(
        "показаний от сборщика за 5 мин:",
        odoo.call("td.reading", "search_count", [("src", "=", "collector"), ("received_at", ">=", five)]),
    )
    last = odoo.search_read(
        "td.signal", [("last_ts", "!=", False)], ["code", "last_value", "last_ts"], order="last_ts desc", limit=3
    )
    for s in last:
        print("  последний:", s["code"], s["last_value"], s["last_ts"])
    if odoo.model_exists("td.energy.interval"):
        print(
            "энергетика: интервалов",
            odoo.call("td.energy.interval", "search_count", []),
            "| из них backfill",
            odoo.call("td.energy.interval", "search_count", [("is_backfill", "=", True)]),
        )
    for key in (
        "td.base.environment",
        "td.iot_sim.url",
        "td.iot_sim.read_enabled",
        "td.iot_sim.write_enabled",
        "td.telemetry.read_enabled",
        "td.telemetry.write_enabled",
        "td.energy.read_enabled",
    ):
        print(f"  {key} = {odoo.param(key) or '(пусто)'}")
    print("  td.iot_sim.token:", "задан" if odoo.param("td.iot_sim.token") else "НЕ задан")


# --------------------------------------------------------------------------------------------- genset
# Живой генератор: td_genset опрашивает ИМИТАТОР ретранслятора SmartGen (td_genset/relay/fake_relay.py, профиль D700),
# его ставит install_stand.sh (служба td-genset-relay, порт TD_SIM_PORT_GENSET_RELAY, по умолчанию 8087). Настоящий
# ретранслятор SmartGen (127.0.0.1:8081 на хосте, gen-relay.todo.ltd) этой командой не используется и не настраивается.
RELAY_API_PREFIX = "/api/v1"
REAL_RELAY_PORT = 8081  # на timur-o19demo занят настоящим ретранслятором чужой системы
DEFAULT_RELAY_HOST = "172.18.0.1"  # шлюз compose-сети timur-o19demo: так контейнер Odoo видит хост (как td.iot_sim.url)
DEFAULT_RELAY_HOSTID = "53494D47454E534554443730"  # как в install_stand.sh (TD_GENSET_RELAY_HOSTID), не hostid модуля
GENSET_NAME = "ДГУ D700 (стенд, имитатор ретранслятора)"
GENSET_CRONS = (
    ("td_genset", "cron_pull_readings"),
    ("td_genset", "cron_commands"),
    ("td_genset", "cron_scheduler"),
    ("td_genset", "cron_cleanup"),
    ("td_genset_factory3d", "cron_td_genset_publish"),
    ("td_genset_factory3d", "cron_td_genset_events"),
    ("td_genset_factory3d", "cron_td_genset_service"),
)
SECRET_RE = re.compile(r"^[A-Za-z0-9._~+/=-]{32,256}$")  # как valid_secret в install_stand.sh
TOKEN_KEYS = {"api": ("TD_RELAY_API_TOKEN", "RELAY_API_TOKEN"), "sim": ("TD_RELAY_SIM_TOKEN", "RELAY_SIM_TOKEN")}
GENSET_FIELDS = [
    "link_state",
    "last_reading_at",
    "genset_status",
    "controller_mode",
    "active_power",
    "fuel_level",
    "fuel_liters",
    "readings_cursor",
    "relay_last_reading_id",
]
LINK_FIELDS = ["td_genset_ref", "profile_id", "source_id", "publish_enabled", "active"]
PROFILE_FIELDS = ["id", "kw_prp", "tank_l"]
FRESH_S = 150  # показание считается свежим, если не старше (снимок раз в 60 с + крон раз в 60 с)


def default_relay_url() -> str:
    port = os.environ.get("TD_SIM_PORT_GENSET_RELAY", "8087")
    sim = urllib.parse.urlsplit(os.environ["TD_SIM_URL"]) if os.environ.get("TD_SIM_URL") else None
    host = (sim.hostname if sim else None) or DEFAULT_RELAY_HOST
    return f"http://{host}:{port}"


def normalize_relay_url(raw: str) -> str:
    """Базовый адрес API (…/api/v1) и защита от адреса настоящего ретранслятора SmartGen."""
    url = raw.strip().rstrip("/")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        die(f"--relay-url {raw!r}: нужен адрес вида http://172.18.0.1:8087", 2)
    host = parts.hostname.lower()
    if parts.port == REAL_RELAY_PORT or host == "todo.ltd" or host.endswith(".todo.ltd"):
        die(
            f"--relay-url {raw!r}: это адрес настоящего ретранслятора SmartGen "
            f"(порт {REAL_RELAY_PORT} или *.todo.ltd). "
            "Odoo к нему не подключаем: укажите адрес имитатора (install_stand.sh, по умолчанию порт 8087)",
            2,
        )
    if not parts.path.rstrip("/").endswith(RELAY_API_PREFIX):
        url += RELAY_API_PREFIX
    return url


def _read_kv(text: str) -> dict[str, str]:
    """Файл секретов: строки KEY=VALUE (кавычки и «export » срезаются) или одно голое значение (токен API)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    out: dict[str, str] = {}
    for ln in lines:
        if "=" in ln:
            key, _, val = ln.removeprefix("export ").partition("=")
            out[key.strip()] = val.strip().strip("'\"")
    if len(lines) == 1 and "=" not in lines[0]:
        out["TD_RELAY_API_TOKEN"] = lines[0]
    return out


def load_relay_tokens(path: str) -> str:
    """Токен API ретранслятора (его же Odoo шлёт Bearer-ом) из файла.

    Если токенов в файле нет, выдаёт API и SIM и дописывает их в файл (0600): тот же файл уходит на хост как
    TD_SECRETS_FILE для install_stand.sh. Значения нигде не печатаются.
    """
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    kv = _read_kv(text)
    found = {kind: next((kv[k] for k in keys if kv.get(k)), "") for kind, keys in TOKEN_KEYS.items()}
    for kind, val in found.items():
        if val and not SECRET_RE.match(val):
            die(f"токен {TOKEN_KEYS[kind][0]} в {path} некорректен (32-256 символов A-Za-z0-9 . _ ~ + / = -)")
    missing = [kind for kind, val in found.items() if not val]
    if missing:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            for kind in missing:
                found[kind] = secrets.token_urlsafe(32)
                f.write(f"{TOKEN_KEYS[kind][0]}={found[kind]}\n")
        names = ", ".join(TOKEN_KEYS[kind][0] for kind in missing)
        info(
            f"токены имитатора ретранслятора ({names}) выданы и дописаны в {path} (значения не печатаю). "
            "Передайте этот файл на хост как TD_SECRETS_FILE для install_stand.sh."
        )
    if os.stat(path).st_mode & 0o077:
        info(f"ВНИМАНИЕ: {path} доступен группе и остальным (chmod 600)")
    return found["api"]


def _first(odoo: Odoo, model: str, domain: list, fields: list[str]) -> dict | None:
    rows = odoo.search_read(model, domain, fields, limit=1, context={"active_test": False})
    return rows[0] if rows else None


def _label(odoo: Odoo, field: str, value: str) -> str:
    """Подпись значения поля-выбора td.genset («0» -> «Очікування»)."""
    sel = odoo.call("td.genset", "fields_get", [field], attributes=["selection"]).get(field, {}).get("selection") or []
    return dict(sel).get(value) or str(value)


def _msg(res: object) -> str:
    """Текст display_notification из ответа кнопки."""
    params = res.get("params") if isinstance(res, dict) else None
    return str((params or {}).get("message", ""))[:300]


def ensure_genset_params(odoo: Odoo, url: str, token: str, force: bool) -> None:
    cur = odoo.param("td_genset.relay_url")
    if cur and cur.rstrip("/") != url and not force:
        die(
            f"td_genset.relay_url уже задан ({cur}), а запрошен {url}. Не перезаписываю без --force "
            "(убедитесь, что прежний адрес не нужен)"
        )
    want = {
        "td_genset.relay_url": url,
        "td_genset.relay_token": token,
        "td.genset.read_enabled": "True",
        "td.genset.requests_enabled": "True",
    }
    if not odoo.call("ir.config_parameter", "search_count", [("key", "=", "td.genset.write_enabled")]):
        want["td.genset.write_enabled"] = "False"  # запись в устройства не включаем
    changed = [key for key, value in want.items() if odoo.param(key) != value]
    for key in changed:
        odoo.set_param(key, want[key])
    shown = ", ".join(key if "token" not in key else "relay_token (значение не печатаю)" for key in changed)
    info("параметры td_genset: " + (shown or "уже в нужном состоянии"))
    env = odoo.param("td.base.environment")
    if env != "test":
        info(f"ВНИМАНИЕ: td.base.environment = {env!r} (ожидается 'test'); скрипт это не меняет.")


def ensure_genset(odoo: Odoo, hostid: str, name: str, profile: dict | None) -> int:
    """td.genset (ДГУ D700) с hostid имитатора: создать или привести к профилю. Ключ поиска — relay_hostid."""
    ctrl = _first(odoo, "td.genset.controller.model", [("code", "=", "hgm6120n")], ["id"])
    if not ctrl:
        die("в td_genset нет модели контроллера HGM6120N (td.genset.controller.model, code=hgm6120n)")
    vals = {
        "relay_hostid": hostid,
        "relay_enabled": True,
        "controller_model_id": ctrl["id"],
        "power_kw": profile["kw_prp"] if profile else 507.0,
        "tank_volume_l": profile["tank_l"] if profile else 610.0,
        "active": True,
    }
    rec = _first(odoo, "td.genset", [("relay_hostid", "=", hostid)], list(vals))
    if rec:
        rec["controller_model_id"] = (rec["controller_model_id"] or [False])[0]
        diff = {key: value for key, value in vals.items() if rec[key] != value}
        if diff:
            odoo.call("td.genset", "write", [rec["id"]], diff)
        info(f"td.genset id={rec['id']}: " + (f"обновлено {', '.join(diff)}" if diff else "уже в нужном состоянии"))
        return rec["id"]
    vals.update(
        name=name,
        address="Производственная площадка (стенд)",
        relay_note="ИМИТАТОР ретранслятора SmartGen HGM6120N (td_genset/relay/fake_relay.py, D700), не настоящий.",
    )
    gid = odoo.call("td.genset", "create", vals)
    info(f"td.genset создан (id {gid}): {name}")
    return gid


def ensure_link(odoo: Odoo, gid: int, eq: dict, profile: dict | None) -> str:
    """td.genset3d.link: генератор td_genset <-> 3D-объект eq (maintenance.equipment, td_code GENSET) + профиль D700."""
    ref = f"td.genset,{gid}"
    link = _first(odoo, "td.genset3d.link", [("equipment_id", "=", eq["id"])], LINK_FIELDS)
    other = _first(odoo, "td.genset3d.link", [("td_genset_ref", "=", ref)], ["equipment_id"])
    if other and (not link or other["id"] != link["id"]):
        info(f"ВНИМАНИЕ: генератор уже связан с другим 3D-объектом ({other['equipment_id'][1]}); связку не трогаю")
        return f"id {other['id']} (другой объект)"
    source = _first(odoo, "td.source", [("code", "=", "GENSET-RELAY")], ["id"])
    vals = {"td_genset_ref": ref, "publish_enabled": True, "active": True}
    if profile:
        vals["profile_id"] = profile["id"]
    if source:
        vals["source_id"] = source["id"]
    if not link:
        link_id = odoo.call("td.genset3d.link", "create", {"equipment_id": eq["id"], **vals})
        info(f"связка td.genset3d.link создана (id {link_id}): {eq['name']}")
        return f"id {link_id} ({eq['name']})"
    cur = {key: (value[0] if isinstance(value, list) else value) for key, value in link.items()}
    diff = {key: value for key, value in vals.items() if cur[key] != value and not (key == "source_id" and cur[key])}
    if diff:
        odoo.call("td.genset3d.link", "write", [link["id"]], diff)
    info(f"связка id={link['id']}: " + (f"обновлено {', '.join(diff)}" if diff else "уже в нужном состоянии"))
    return f"id {link['id']} ({eq['name']})"


def ensure_genset3d(odoo: Odoo, gid: int, profile: dict | None) -> tuple[str, str]:
    """Профиль D700, связка с 3D-объектом и узлом энергосети GENSET. Возвращает описания связки и узла для вывода."""
    if not odoo.model_exists("td.genset3d.link"):
        info("модуля td_genset_factory3d нет: связка с 3D и узлом энергосети пропущена")
        return "нет (нет td_genset_factory3d)", "нет"
    if profile:
        ok, res = odoo.soft("td.genset3d.profile", "action_apply_to_td", [profile["id"]])
        info("профиль D700 применён к td_genset" if ok else f"профиль D700: action_apply_to_td не выполнен ({res})")
    node = None
    if odoo.model_exists("td.energy.node"):
        node = _first(odoo, "td.energy.node", [("code", "=", "GENSET")], ["equipment_id", "kind", "gen_kind"])
    eq = _first(odoo, "maintenance.equipment", [("td_code", "=", "GENSET")], ["name"])
    if not eq and node and node["equipment_id"]:
        eq = {"id": node["equipment_id"][0], "name": node["equipment_id"][1]}
    if not eq:
        info("ВНИМАНИЕ: нет 3D-объекта (maintenance.equipment с td_code=GENSET): связка не создана")
        return "нет (нет 3D-объекта GENSET)", "нет"
    link = ensure_link(odoo, gid, eq, profile)
    if not node:
        info("ВНИМАНИЕ: в энергосети нет узла GENSET (td_energy)")
        return link, "нет"
    if not node["equipment_id"]:
        odoo.call("td.energy.node", "write", [node["id"]], {"equipment_id": eq["id"]})
        info("узел энергосети GENSET связан с 3D-объектом")
    elif node["equipment_id"][0] != eq["id"]:
        info(f"ВНИМАНИЕ: узел GENSET уже связан с {node['equipment_id'][1]}; не меняю")
    return link, f"GENSET ({node['gen_kind'] or node['kind']}) -> {eq['name']}"


def enable_genset_crons(odoo: Odoo) -> int:
    """Включает крони td_genset и td_genset_factory3d (только active=True, ничего не создаёт и не удаляет)."""
    ids = []
    for module, name in GENSET_CRONS:
        domain = [("module", "=", module), ("name", "=", name), ("model", "=", "ir.cron")]
        row = _first(odoo, "ir.model.data", domain, ["res_id"])
        if row:
            ids.append(row["res_id"])
    crons = []
    if ids:
        crons = odoo.search_read("ir.cron", [("id", "in", ids)], ["active"], context={"active_test": False})
    off = [cron["id"] for cron in crons if not cron["active"]]
    if off:
        odoo.call("ir.cron", "write", off, {"active": True})
    info(f"крони генератора: найдено {len(crons)} из {len(GENSET_CRONS)}, включено сейчас {len(off)}")
    return len(crons)


def _age_s(stamp: str | bool) -> float | None:
    """Возраст UTC-метки Odoo («ГГГГ-ММ-ДД ЧЧ:ММ:СС») в секундах."""
    if not stamp:
        return None
    then = dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - then).total_seconds()


def wait_genset_readings(odoo: Odoo, gid: int, wait_s: int) -> dict:
    """Просит Odoo опросить имитатор сейчас (кнопки «Проверить связь», «Обновить данные») и ждёт свежее показание
    (не старше FRESH_S: имитатор снимает показания раз в минуту, крон Odoo читает раз в минуту)."""
    ok, res = odoo.soft("td.genset", "action_check_relay", [gid])
    info("проверка связи: " + (_msg(res) if ok else f"не выполнена ({res})"))
    odoo.soft("td.genset", "action_refresh", [gid])
    deadline = time.monotonic() + wait_s
    while True:
        rec = odoo.search_read("td.genset", [("id", "=", gid)], GENSET_FIELDS, context={"active_test": False})[0]
        age = _age_s(rec["last_reading_at"])
        if (age is not None and age <= FRESH_S) or time.monotonic() >= deadline:
            return rec
        time.sleep(5)


def cmd_genset(odoo: Odoo, args: argparse.Namespace) -> None:
    if not odoo.model_exists("td.genset"):
        die("в базе нет td.genset: установите модуль td_genset")
    if not args.token_file:
        die(
            "не задан файл токена: --token-file ФАЙЛ (или TD_RELAY_TOKEN_FILE). Если токенов в нём нет, они будут "
            "выданы и дописаны; тот же файл передают на хост как TD_SECRETS_FILE (install_stand.sh)",
            2,
        )
    url = normalize_relay_url(args.relay_url or os.environ.get("TD_RELAY_URL") or default_relay_url())
    token = load_relay_tokens(args.token_file)
    ensure_genset_params(odoo, url, token, args.force)
    profile = None
    if odoo.model_exists("td.genset3d.profile"):
        profile = _first(odoo, "td.genset3d.profile", [("code", "=", "D700")], PROFILE_FIELDS)
    gid = ensure_genset(odoo, args.hostid, args.name, profile)
    link, node = ensure_genset3d(odoo, gid, profile)
    n_cron = enable_genset_crons(odoo)
    rec = wait_genset_readings(odoo, gid, args.wait)
    if rec["last_reading_at"] and link.startswith("id "):
        link_id = int(link.split()[1])
        ok, res = odoo.soft("td.genset3d.link", "action_check", [link_id])
        info("публикация в телеметрию: " + (_msg(res) if ok else f"не выполнена ({res})"))
    print(f"genset: td.genset id={gid}, имитатор {url} (hostid {args.hostid}), профиль D700, крони {n_cron}")
    print(f"genset: связка 3D: {link}; узел энергосети: {node}")
    if not rec["last_reading_at"]:
        print(
            f"genset: показаний пока нет (связь {rec['link_state']}): Odoo не достучался до имитатора. Если "
            "install_stand.sh на хосте ещё не запускали с этими токенами, это нормально: повторите команду после "
            "установки (она идемпотентна)."
        )
        return
    age = _age_s(rec["last_reading_at"])
    stale = f" [СТАРОЕ: {int(age // 60)} мин назад, новых нет]" if age is not None and age > FRESH_S else ""
    print(
        f"genset: показание {rec['last_reading_at']} UTC{stale}: связь {rec['link_state']}, "
        f"режим {rec['controller_mode']}, "
        f"состояние {_label(odoo, 'genset_status', rec['genset_status'])}, {rec['active_power']:.1f} кВт, "
        f"топливо {rec['fuel_level']:.1f} % ({rec['fuel_liters']:.0f} л)"
    )
    if rec["relay_last_reading_id"] and rec["readings_cursor"] > rec["relay_last_reading_id"]:
        info(
            f"ВНИМАНИЕ: курсор Odoo ({rec['readings_cursor']}) опережает журнал имитатора "
            f"({rec['relay_last_reading_id']}): имитатор перезапускался (журнал в памяти), см. STAND.md."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Odoo-сторона постоянного стенда (токен, параметры, backfill)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("setup", help="коллектор, токены, параметры; токены в stdout")
    p.add_argument("--rotate", action="store_true", help="выпустить новый токен сборщика, даже если он уже выдан")
    p.set_defaults(fn=cmd_setup)
    sub.add_parser("params", help="только параметры").set_defaults(fn=cmd_params)
    p = sub.add_parser("backfill", help="_td_backfill(days=90) через временное серверное действие")
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--seed", type=int, default=20261018)
    p.add_argument("--purge", action="store_true", help="удалить сгенерированные интервалы (is_backfill) и выйти")
    p.add_argument("--force", action="store_true", help="не ждать 5 минут работы стенда")
    p.add_argument("--chunk-days", type=int, default=5, help="діб на один виклик (проксі рве довгі запити), 5")
    p.add_argument("--target", choices=("energy", "resources", "all"), default="all",
                   help="електрика (td_energy), ресурси (td_energy_resources) чи обидва")  # fmt: skip
    p.set_defaults(fn=cmd_backfill)
    p = sub.add_parser("seed", help="демо-дані аналітики W4 (_td_seed_demo) після backfill")
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--seed", type=int, default=20261018)
    p.set_defaults(fn=cmd_seed)
    sub.add_parser("status", help="состояние без секретов").set_defaults(fn=cmd_status)
    p = sub.add_parser("genset", help="живой генератор td_genset + имитатор ретранслятора (fake_relay D700)")
    p.add_argument("--relay-url", help="адрес имитатора для контейнера Odoo (по умолчанию http://172.18.0.1:8087)")
    p.add_argument(
        "--token-file",
        default=os.environ.get("TD_RELAY_TOKEN_FILE"),
        help="файл с токеном API (KEY=VALUE или одно значение); токенов нет: выдать и дописать",
    )
    p.add_argument(
        "--hostid",
        default=os.environ.get("TD_GENSET_RELAY_HOSTID", DEFAULT_RELAY_HOSTID),
        help="hostid имитатора (как в install_stand.sh)",
    )
    p.add_argument("--name", default=GENSET_NAME, help="название нового td.genset")
    p.add_argument("--force", action="store_true", help="перезаписать уже заданный td_genset.relay_url")
    p.add_argument("--wait", type=int, default=90, help="сколько секунд ждать первое показание (90)")
    p.set_defaults(fn=cmd_genset)
    args = ap.parse_args()
    if not 1 <= getattr(args, "days", 1) <= 400:
        die("--days: 1..400", 2)
    args.fn(Odoo(), args)


if __name__ == "__main__":
    main()
