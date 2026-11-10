#!/usr/bin/env python3
"""Еталон C-00: перевірка стану ТЕСТОВОЇ бази проти очікуваного (лише читання, XML-RPC /xmlrpc/2, stdlib).
Використання: validate.py --db DB --expect expect.json
expect.json: {"modules": ["stock","mrp"],                       # ir.module.module.state == installed
              "params": {"td_x.vp_01": "10"},                   # ir.config_parameter: key -> value (рядок)
              "records": [{"xmlid": "td_config.a", "model": "res.partner", "values": {"name": "X"}}]}
Середовище: ODOO_URL, ODOO_LOGIN, ODOO_API_KEY, ODOO_ALLOWED_HOSTS (обов'язково; без нього FLOW_STOP).
Вихід: рядки PASS/FAIL, останній -- JSON {"checked","failed"}. Коди: 0 усе збіглося, 1 є розбіжності, 2 запуск/захист.
Відкрите для C-00: модель/поле стану модуля (ir.module.module.state) і ir.config_parameter у Odoo 19 звірити з реальною базою.
"""
import argparse, json, sys
import apply as A  # той самий каталог: guard_db, guard_host, rpc_conn, norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--expect", required=True)
    a = ap.parse_args()
    A.guard_db(a.db)
    exp = A.load_json(a.expect)
    if not isinstance(exp, dict):
        A.stop("expect.json має бути об'єктом")
    call = A.rpc_conn(a.db)
    checked = failed = 0

    def rep(ok, msg):
        nonlocal checked, failed
        checked += 1
        failed += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + msg)

    def guarded(label, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 -- помилка формату/RPC = FAIL, підсумок друкується завжди
            rep(False, "%s: помилка %s" % (label, str(e)[:200]))

    def chk_module(m):
        r = call("ir.module.module", "search_read", [["name", "=", m]], fields=["state"], limit=1)
        st = r[0]["state"] if r else "немає в базі"
        rep(st == "installed", "module %s: %s" % (m, st))

    def chk_param(k, v):
        r = call("ir.config_parameter", "search_read", [["key", "=", k]], fields=["value"], limit=1)
        got = r[0]["value"] if r else None
        rep(got == v, "param %s: %r (очікується %r)" % (k, got, v))

    def chk_record(it):
        mod, name = it["xmlid"].split(".", 1)
        imd = call("ir.model.data", "search_read", [["module", "=", mod], ["name", "=", name]], fields=["res_id"], limit=1)
        if not imd:
            rep(False, "record %s: немає xml-id" % it["xmlid"])
            return
        cur = call(it["model"], "read", [imd[0]["res_id"]], fields=list(it["values"]))[0]
        bad = {k: cur.get(k) for k, v in it["values"].items() if not A.same(cur.get(k), v)}
        rep(not bad, "record %s: %s" % (it["xmlid"], bad or "ok"))

    for m in exp.get("modules", []):
        guarded("module %s" % m, lambda m=m: chk_module(m))
    for k, v in exp.get("params", {}).items():
        guarded("param %s" % k, lambda k=k, v=v: chk_param(k, v))
    for it in exp.get("records", []):
        guarded("record %s" % (it.get("xmlid") if isinstance(it, dict) else it), lambda it=it: chk_record(it))
    print(json.dumps({"checked": checked, "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
