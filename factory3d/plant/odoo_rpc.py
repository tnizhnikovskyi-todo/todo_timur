"""Тонкий клієнт XML-RPC до Odoo. Доступ — лише зі змінних середовища, у репозиторії паролів немає:
ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD (пароль або API-ключ)."""
import hashlib
import os
import re
import time
import xmlrpc.client
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Kyiv")


def utc(s):
    """'2026-10-12 10:30' за Києвом → рядок UTC для полів Odoo."""
    if not s:
        return False
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")


def key(*parts):
    """Зовнішній ID: латиниця як є, а для кирилиці — ще й короткий хеш, щоб назви не злипалися."""
    raw = "_".join(str(p) for p in parts)
    k = re.sub(r"[^0-9A-Za-z]+", "_", raw).strip("_").lower()
    if not raw.isascii():
        k += "_" + hashlib.md5(raw.encode()).hexdigest()[:8]
    return k


class Odoo:
    def __init__(self, url=None, db=None, user=None, password=None):
        self.url = (url or os.environ["ODOO_URL"]).rstrip("/")
        self.db = db or os.environ["ODOO_DB"]
        self.user = user or os.environ.get("ODOO_USER", "admin")
        self.pw = password or os.environ["ODOO_PASSWORD"]
        common = xmlrpc.client.ServerProxy(self.url + "/xmlrpc/2/common", allow_none=True)
        self.version = common.version()
        self.uid = common.authenticate(self.db, self.user, self.pw, {})
        if not self.uid:
            raise SystemExit("Odoo: невірний логін або пароль")
        self.obj = xmlrpc.client.ServerProxy(self.url + "/xmlrpc/2/object", allow_none=True)
        self.ctx = {}

    def __call__(self, model, method, *args, **kw):
        if self.ctx and "context" not in kw:
            kw["context"] = self.ctx
        try:
            return self.obj.execute_kw(self.db, self.uid, self.pw, model, method, list(args), kw)
        except xmlrpc.client.Fault as e:
            # метод виконано й закомічено, але повернув None, якого XML-RPC не передає
            if "cannot marshal None" in str(e.faultString):
                return None
            raise

    def has(self, model):
        return bool(self("ir.model", "search_count", [["model", "=", model]]))

    def installed(self, *names):
        rows = self("ir.module.module", "search_read", [["name", "in", list(names)]], fields=["name", "state"])
        return {r["name"]: r["state"] for r in rows}

    def install(self, *names):
        """Встановити модулі по одному; поки сервер зайнятий іншою операцією чи cron — чекати."""
        for name in names:
            for _ in range(40):
                if self.installed(name).get(name) == "installed":
                    break
                mid = self("ir.module.module", "search", [["name", "=", name]])
                try:
                    self("ir.module.module", "button_immediate_install", mid)
                except xmlrpc.client.Fault as e:
                    if "processing" not in e.faultString:
                        raise
                    time.sleep(20)
            else:
                raise SystemExit(f"Odoo: модуль {name} не встановився")
