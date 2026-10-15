"""XML-RPC-клієнт Odoo для стенда machine_connect (SPEC §13.2: env F3D_STAND_ODOO_URL/DB/LOGIN/PASSWORD).
Копія помічника стенда телеметрії (DEC-15) з іншою базою за замовчуванням і додатковими методами (`create`, `execute`).

CLI: ``python odoo_rpc.py token`` — згенерувати токен колектора COL-MAIN і надрукувати (як кнопка «Згенерувати токен»).
"""

from __future__ import annotations

import os
import sys
import xmlrpc.client as xc

URL = os.environ.get("F3D_STAND_ODOO_URL", "http://127.0.0.1:18070")
DB = os.environ.get("F3D_STAND_ODOO_DB", "f3d_mc_tk")
LOGIN = os.environ.get("F3D_STAND_ODOO_LOGIN", "admin")
PASSWORD = os.environ.get("F3D_STAND_ODOO_PASSWORD", "admin")


class Odoo:
    def __init__(self, url: str = URL, db: str = DB, login: str = LOGIN, password: str = PASSWORD):
        self.url, self.db, self.password = url, db, password
        self.uid = xc.ServerProxy(url + "/xmlrpc/2/common", allow_none=True).authenticate(db, login, password, {})
        if not self.uid:
            raise RuntimeError(f"Odoo: вхід {login} у {db} не вдався")
        self._m = xc.ServerProxy(url + "/xmlrpc/2/object", allow_none=True)

    def call(self, model: str, method: str, *args, **kw):
        try:
            return self._m.execute_kw(self.db, self.uid, self.password, model, method, list(args), kw)
        except xc.Fault as e:  # короткий текст замість повного трейсбека Odoo
            tail = [ln for ln in str(e.faultString).strip().splitlines() if ln.strip()][-1]
            if "cannot marshal None" in tail:  # метод виконано й закомічено, лише відповідь None XML-RPC не серіалізує
                return None
            raise RuntimeError(f"{model}.{method}: {tail}") from None

    def create(self, model: str, vals: dict) -> int:
        return self.call(model, "create", vals)

    def read(self, model: str, ids, fields=None) -> list[dict]:
        return self.call(model, "read", ids if isinstance(ids, list) else [ids], fields=fields or [])

    def search_read(self, model: str, domain=None, fields=None, **kw):
        return self.call(model, "search_read", domain or [], fields=fields or [], **kw)

    def count(self, model: str, domain=None) -> int:
        return self.call(model, "search_count", domain or [])

    def write(self, model: str, ids, vals) -> bool:
        return self.call(model, "write", ids if isinstance(ids, list) else [ids], vals)

    def param(self, key: str, value=None):
        """Читання/запис параметра. Читання — напряму з таблиці (get_param кешується ormcache); запис — завжди `write`
        (set_param пропускає запис, якщо значення збігається з БД, і кеш лишається застарілим)."""
        rows = self.search_read("ir.config_parameter", [("key", "=", key)], ["value"])
        if value is None:
            return rows[0]["value"] if rows else False
        if rows:
            self.write("ir.config_parameter", rows[0]["id"], {"value": str(value)})
            return rows[0]["value"]
        self.call("ir.config_parameter", "set_param", key, str(value))
        return False

    def signal(self, code: str, fields=None) -> dict:
        rows = self.search_read(
            "f3d.signal",
            [("code", "=", code)],
            fields or ["code", "status", "last_value", "last_text", "last_ts", "last_quality"],
            limit=1,
        )
        return rows[0] if rows else {}

    def requests(self, code: str, only_open: bool = False) -> list[dict]:
        """Заявки maintenance.request, створені сигналом `code` (f3d_signal_id)."""
        dom = [("f3d_signal_id.code", "=", code)]
        if only_open:
            dom.append(("stage_id.done", "=", False))
        return self.search_read(
            "maintenance.request",
            dom,
            [
                "name",
                "stage_id",
                "maintenance_team_id",
                "maintenance_type",
                "priority",
                "f3d_value",
                "f3d_threshold",
                "f3d_origin",
                "equipment_id",
            ],
            order="id",
        )

    def close_request(self, rid: int) -> None:
        """Стадія «Repaired» (done=True) — як закриття менеджером."""
        stage = self.search_read("maintenance.stage", [("done", "=", True)], ["id"], limit=1)[0]["id"]
        self.write("maintenance.request", rid, {"stage_id": stage})

    def chatter(self, model: str, res_id: int) -> list[str]:
        msgs = self.search_read("mail.message", [("model", "=", model), ("res_id", "=", res_id)], ["body"], order="id")
        return [m["body"] or "" for m in msgs]

    def signal_id(self, code: str) -> int:
        return self.search_read("f3d.signal", [("code", "=", code)], ["id"], limit=1)[0]["id"]

    def new_token(self, collector: str = "COL-MAIN") -> str:
        cid = self.search_read("f3d.collector", [("code", "=", collector)], ["id"], limit=1)[0]["id"]
        act = self.call("f3d.collector", "action_generate_token", [cid])
        return act["context"]["default_token"]


def main(argv: list[str]) -> int:
    if argv[:1] == ["token"]:
        print(Odoo().new_token(argv[1] if len(argv) > 1 else "COL-MAIN"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
