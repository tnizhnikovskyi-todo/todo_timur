"""Адаптер OrmProxy (A-08): та сама сигнатура `o(model, method, *args, **kw)`, що в plant/odoo_rpc.Odoo,
але виклики йдуть у ORM поточного env. Так кроки заливки з plant/odoo_push.py працюють без змін."""

import hashlib
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.models import BaseModel

CTX = {"lang": "uk_UA", "tz": "Europe/Kyiv", "tracking_disable": True, "mail_create_nolog": True, "mail_notrack": True}
TZ = ZoneInfo("Europe/Kyiv")
MODEL_METHODS = {
    "search_read",
    "search",
    "search_count",
    "fields_get",
    "name_search",
    "create",
    "default_get",
    "read_group",
    "name_create",
}


def key(*parts):
    """Зовнішній ID: латиниця як є, а для кирилиці — ще й короткий хеш, щоб назви не злипалися."""
    raw = "_".join(str(p) for p in parts)
    k = re.sub(r"[^0-9A-Za-z]+", "_", raw).strip("_").lower()
    if not raw.isascii():
        k += "_" + hashlib.md5(raw.encode()).hexdigest()[:8]
    return k


def utc(s):
    """'2026-10-12 10:30' за Києвом → рядок UTC для полів Odoo."""
    if not s:
        return False
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _plain(v):
    """Те, що віддав би XML-RPC: id замість записів, рядки замість дат, списки замість кортежів."""
    if isinstance(v, BaseModel):
        return v.ids
    if isinstance(v, datetime):
        return fields.Datetime.to_string(v)
    if isinstance(v, date):
        return fields.Date.to_string(v)
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


class OrmProxy:
    version = {"server_serie": "19.0", "server_version": "19.0"}

    def __init__(self, env):
        self.env = env
        self.uid = env.uid
        self.ctx = dict(CTX)
        self.lang_ok = None

    def refresh_lang(self):
        """Мова з контексту діє, лише коли вона встановлена (інакше Odoo кидає «Invalid language code»)."""
        self.lang_ok = bool(
            self.env["res.lang"].sudo().search_count([("code", "=", self.ctx.get("lang")), ("active", "=", True)])
        )

    def __call__(self, model, method, *args, **kw):
        if self.lang_ok is None:
            self.refresh_lang()
        ctx = dict(self.ctx, **(kw.pop("context", None) or {}))
        if not self.lang_ok and ctx.get("lang") == self.ctx.get("lang"):
            ctx.pop("lang", None)
        recs = self.env[model].with_context(**ctx)
        fn = getattr(recs, method)
        if method in MODEL_METHODS or getattr(fn, "_api_model", False):  # без id першим аргументом
            res = fn(*args, **kw)
            if method == "create" and isinstance(res, BaseModel) and not isinstance(args[0], (list, tuple)):
                return res.id
            return _plain(res)
        # методи записів: перший аргумент — id або список id (як у execute_kw)
        res = getattr(recs.browse(args[0] if args else []), method)(*args[1:], **kw)
        return _plain(res)

    def has(self, model):
        return model in self.env

    def installed(self, *names):
        rows = self.env["ir.module.module"].sudo().search_read([("name", "in", list(names))], ["name", "state"])
        return {r["name"]: r["state"] for r in rows}

    def install(self, *names):
        for name in names:
            if self.installed(name).get(name) != "installed":
                self.env["ir.module.module"].sudo().search([("name", "=", name)]).button_immediate_install()
