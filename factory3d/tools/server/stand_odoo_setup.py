#!/usr/bin/env python3
"""Odoo-сторона постоянного стенда (E-11): токен сборщика, параметры, backfill истории. Только stdlib, XML-RPC.

Запускает менеджер снаружи, после установки новой БД с модулями td_*:

    export ODOO_URL=https://timur-o19demo.todo.ltd ODOO_DB=odoo ODOO_USER=admin ODOO_PASSWORD=...   # пароль или
    API-ключ
    python3 stand_odoo_setup.py setup > td-stand.secrets   # токены ОДИН раз в stdout, остальное в stderr
    python3 stand_odoo_setup.py status                     # состояние без секретов
    python3 stand_odoo_setup.py backfill                   # через >= 5 мин после запуска стенда

Команды:
  setup     коллектор COL-MAIN (создать/включить), токен сборщика (если ещё не выдан или --rotate), токен API эмулятора,
            параметры ir.config_parameter, params источника HTTP-PUSH. В stdout печатает строки KEY=VALUE:
            TD_COLLECTOR_TOKEN (виден только сейчас: в Odoo хранится хэш) и TD_SIM_API_TOKEN (лежит в td.iot_sim.token).
            Файл с этими строками клиент передаёт install_stand.sh как TD_SECRETS_FILE.
  params    только параметры (без токенов).
  backfill  td.energy.interval._td_backfill(days=90) (R-36). Метод приватный, по RPC его вызвать нельзя, поэтому
            скрипт создаёт временное серверное действие, запускает и удаляет его. Опции --days, --seed, --purge,
            --force.
  status    состояние коллектора, источников, свежих показаний и истории.

Переменные: ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD (обязательны); TD_COLLECTOR_CODE (COL-MAIN), TD_SIM_URL
(http://127.0.0.1:8090: адрес эмулятора, как его видит Odoo), TD_SIM_API_TOKEN (задать свой вместо генерации),
TD_SIM_WRITE_ENABLED (1/0, по умолчанию 1: сценарии и сбои из пульта Odoo), TD_RPC_TIMEOUT (с, 1800).
Пароль и токены в аргументах командной строки не передаются и в stderr не печатаются.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import secrets
import sys
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
res = env['td.energy.interval']._td_backfill(days=%(days)d, seed=%(seed)d, purge=%(purge)s)
action = {'type': 'ir.actions.act_window_close', 'td_result': str(res)}
"""


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
    model_id = odoo.call("ir.model", "search", [("model", "=", "td.energy.interval")], limit=1)[0]
    code = BACKFILL_CODE % {"days": args.days, "seed": args.seed, "purge": bool(args.purge)}
    act = odoo.call(
        "ir.actions.server",
        "create",
        {
            "name": "td-stand: backfill истории (временное, удаляется)",
            "model_id": model_id,
            "state": "code",
            "code": code,
        },
    )
    try:
        info(
            f"запускаю _td_backfill(days={args.days}, seed={args.seed}, purge={bool(args.purge)}): до нескольких минут"
        )
        result = odoo.call("ir.actions.server", "run", [act])
    finally:
        odoo.call("ir.actions.server", "unlink", [act])
    stats = (result or {}).get("td_result") if isinstance(result, dict) else result
    print(stats if stats else "(метод вернул пустой результат)")
    n = odoo.call("td.energy.interval", "search_count", [("is_backfill", "=", True)])
    info(f"строк td.energy.interval с is_backfill=True: {n}")


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
    p.set_defaults(fn=cmd_backfill)
    sub.add_parser("status", help="состояние без секретов").set_defaults(fn=cmd_status)
    args = ap.parse_args()
    if not 1 <= getattr(args, "days", 1) <= 400:
        die("--days: 1..400", 2)
    args.fn(Odoo(), args)


if __name__ == "__main__":
    main()
