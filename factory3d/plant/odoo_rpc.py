"""Тонкий клієнт XML-RPC до Odoo. Доступ — лише зі змінних середовища, у репозиторії паролів немає:
ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD (пароль або API-ключ)."""
import os
import xmlrpc.client


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
