#!/usr/bin/env python3
"""Еталон C-00: застосування конфіг-пакета у ТЕСТОВУ базу. Лише stdlib. Не перевірявся на реальному Odoo 19.

Режими (підкоманди):
  modules  --db DB --modules a,b                       odoo-bin -u <модулі>: підхоплює data-файли з manifest (XML/CSV); потім перевірка state=installed
                                                       (psql, як require_installed в install.sh), інакше rc=1. Доставку модулів робить install.sh --addons-src.
  shell    --db DB --script FILE.py                    odoo-bin shell -d DB < FILE.py (змінна `env` у скрипті).
                                                       Скрипт сам викликає env.cr.commit(): інакше зміни відкочуються (припущення, звірити).
  rpc      --db DB --plan plan.json [--dry-run]        upsert за xml-id через XML-RPC /xmlrpc/2 (execute_kw).
Формат plan.json: [{"xmlid": "td_config.vp_01", "model": "res.partner", "values": {"name": "X"}}, ...]
  Скалярні значення; many2one -- числовий id (xml-id у id розв'язує викликач). Порядок записів = порядок застосування.
Середовище: ODOO_BIN, ODOO_CONF, ODOO_ADDONS_PATH (режими modules/shell); ODOO_URL, ODOO_LOGIN, ODOO_API_KEY,
  ODOO_ALLOWED_HOSTS=host1,host2 (режим rpc; без allowlist -- FLOW_STOP). Секрети лише зі змінних, не з аргументів.
Лічильники created/updated/unchanged у режимах modules/shell завжди 0: ідемпотентність за ними не перевіряється (лише rpc їх рахує).
Обмеження rpc: створення запису і ir.model.data -- два виклики, не атомарно; збій між ними лишає запис без xml-id і повтор створить дубль (відкрите питання C-00: чи є в Odoo 19 підтримуваний одновикликовий upsert за xml-id -- не вигадано). Значення в plan.json лише скалярні; ODOO_URL -- https (http лише для localhost/127.0.0.1).
Вихід: JSON-підсумок {"created","updated","unchanged","manual","errors"} в останньому рядку stdout. Коди: 0 ок, 1 помилки даних, 2 запуск/захист.
Відкрите для C-00: рядок підсумку тестів/поведінка shell-коміту в Odoo 19; JSON-2 API (/json/2) -- не використано, доки не підтверджено.
"""
import argparse, json, os, re, subprocess, sys, xmlrpc.client
from urllib.parse import urlparse

DB_OK = re.compile(r"(test-|test-pkg-|demo-|emu-).+")
DB_CHARS = re.compile(r"[A-Za-z0-9_-]+")
MOD_OK = re.compile(r"[a-z0-9_]+")
SCALAR = (str, int, float, bool, type(None))


def stop(msg):
    print("FLOW_STOP: " + msg, file=sys.stderr)
    sys.exit(2)


def guard_db(db):
    if not db:
        stop("не задано ім'я бази")
    if re.search("prod", db, re.I):
        stop("ім'я бази '%s' містить prod; відмова" % db)
    if not DB_OK.fullmatch(db) or not DB_CHARS.fullmatch(db):
        stop("база '%s' не відповідає test-*|test-pkg-*|demo-*|emu-*; відмова (прод не чіпаємо)" % db)


def guard_host(url):
    allowed = [h.strip() for h in os.environ.get("ODOO_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if not allowed:
        stop("задайте ODOO_ALLOWED_HOSTS (allowlist непродових серверів); ім'я бази сервер не гарантує")
    host = urlparse(url).hostname
    if host not in allowed:
        stop("хост '%s' не в ODOO_ALLOWED_HOSTS" % host)


def odoo_base():
    args = [os.environ.get("ODOO_BIN", "odoo-bin")]
    if os.environ.get("ODOO_CONF"):
        args += ["-c", os.environ["ODOO_CONF"]]
    if os.environ.get("ODOO_ADDONS_PATH"):
        args += ["--addons-path=" + os.environ["ODOO_ADDONS_PATH"]]
    return args


def run_logged(cmd, db, stdin=None, mods=None):
    try:
        p = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    except OSError as e:
        stop("не вдалося запустити %s: %s" % (cmd[0], e))
    bad = [l for l in (p.stdout + p.stderr).splitlines() if re.search(r" (ERROR|CRITICAL) |Traceback", l)]
    for l in bad[:40]:
        print(l, file=sys.stderr)
    errors = [] if p.returncode == 0 and not bad else ["odoo-bin: код %d, ERROR-рядків %d" % (p.returncode, len(bad))]
    if not errors and mods:  # -u невстановленого/невідомого модуля -- тихий no-op (WARNING, код 0)
        for m in mods:
            try:
                q = subprocess.run(["psql", "-d", db, "-Atc", "select state from ir_module_module where name='%s'" % m],
                                   capture_output=True, text=True)
            except OSError as e:
                stop("не вдалося запустити psql: %s" % e)
            st = q.stdout.strip()
            if st != "installed":
                errors.append("module %s: стан '%s', очікується installed" % (m, st or "немає в базі"))
    print(json.dumps({"created": 0, "updated": 0, "unchanged": 0, "manual": 0, "errors": errors}))
    return 0 if not errors else 1


def rpc_conn(db):
    url = os.environ.get("ODOO_URL", "")
    login, key = os.environ.get("ODOO_LOGIN"), os.environ.get("ODOO_API_KEY")
    if not (url and login and key):
        stop("задайте ODOO_URL, ODOO_LOGIN, ODOO_API_KEY")
    pu = urlparse(url)
    if pu.scheme != "https" and not (pu.scheme == "http" and pu.hostname in ("localhost", "127.0.0.1")):
        stop("ODOO_URL має бути https (http лише для localhost/127.0.0.1): API-ключ не передаємо відкрито")
    guard_host(url)
    try:
        uid = xmlrpc.client.ServerProxy(url.rstrip("/") + "/xmlrpc/2/common").authenticate(db, login, key, {})
    except (OSError, xmlrpc.client.Error) as e:
        stop("автентифікація не вдалася: %s" % str(e)[:200])
    if not uid:
        stop("автентифікація в базі '%s' не вдалася" % db)
    obj = xmlrpc.client.ServerProxy(url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)
    return lambda model, method, *a, **kw: obj.execute_kw(db, uid, key, model, method, list(a), kw)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        stop("не вдалося прочитати JSON '%s': %s" % (path, e))


def norm(v):
    return v[0] if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int) else v  # many2one -> id


def same(cur, v):
    """Порівняння значення з бази (read) з планом: False з бази == null/"" з плану (для небулевого очікуваного)."""
    cur = norm(cur)
    if cur is False and (v is None or v == ""):
        return True
    return cur == v


def cmd_rpc(a):
    call = rpc_conn(a.db)
    plan = load_json(a.plan)
    if not isinstance(plan, list):
        stop("plan.json має бути списком")
    res = {"created": 0, "updated": 0, "unchanged": 0, "manual": 0, "errors": []}
    for it in plan:
        try:
            mod, name = it["xmlid"].split(".", 1)
            imd = call("ir.model.data", "search_read", [["module", "=", mod], ["name", "=", name]],
                       fields=["res_id", "model"], limit=1)
            vals = it["values"]
            if not all(isinstance(v, SCALAR) for v in vals.values()):
                raise ValueError("нескалярне значення в values (many2one -- числовий id; x2many не підтримано)")
            if not imd:
                if not a.dry_run:
                    rid = call(it["model"], "create", vals)
                    call("ir.model.data", "create", {"module": mod, "name": name, "model": it["model"], "res_id": rid})
                res["created"] += 1
                continue
            cur = call(it["model"], "read", [imd[0]["res_id"]], fields=list(vals))[0]
            diff = {k: v for k, v in vals.items() if not same(cur.get(k), v)}
            if diff:
                if not a.dry_run:
                    call(it["model"], "write", [imd[0]["res_id"]], diff)
                res["updated"] += 1
            else:
                res["unchanged"] += 1
        except Exception as e:  # noqa: BLE001
            res["errors"].append("%s: %s" % (it.get("xmlid"), str(e)[:200]))
    print(json.dumps(res))
    return 1 if res["errors"] else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    m = sub.add_parser("modules"); m.add_argument("--db", required=True); m.add_argument("--modules", required=True)
    s = sub.add_parser("shell"); s.add_argument("--db", required=True); s.add_argument("--script", required=True)
    r = sub.add_parser("rpc"); r.add_argument("--db", required=True); r.add_argument("--plan", required=True)
    r.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    guard_db(a.db)
    if a.mode == "modules":
        for x in a.modules.split(","):
            if not MOD_OK.fullmatch(x):
                stop("недопустиме ім'я модуля '%s'" % x)
        return run_logged(odoo_base() + ["-d", a.db, "-u", a.modules, "--stop-after-init", "--log-level=warn"], a.db, mods=a.modules.split(","))
    if a.mode == "shell":
        try:
            src = open(a.script, encoding="utf-8").read()
        except OSError as e:
            stop("не вдалося прочитати --script: %s" % e)
        return run_logged(odoo_base() + ["shell", "-d", a.db, "--log-level=warn"], a.db, stdin=src)
    return cmd_rpc(a)


if __name__ == "__main__":
    sys.exit(main())
