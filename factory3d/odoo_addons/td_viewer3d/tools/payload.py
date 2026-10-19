"""Збирач payload (R-01), дельта (R-14), резолвер (R-16), deep_merge (X-23, X-82), доступ (§4.4).

Жодного `sudo()` окрім читання `ir.config_parameter`: усе читається з правами користувача запиту (AC-14).
"""
import copy
import json
import logging
import re

from odoo import release

from . import dates, static_data

_logger = logging.getLogger(__name__)

PROVIDER_PREFIX = "td.viewer.provider."
DEFAULT_GROUP = "td_factory3d.group_td_user"
ENERGY_COST_GROUP = "td_energy.group_td_energy_cost"
SCHEMA = "1.1"
DELTA_MAX_BYTES = 200 * 1024

# 26 базових ключів верхнього рівня у порядку Додатка A.0 (X-24)
BASE_KEYS = (
    "meta", "products", "locations", "workcenters", "productions", "workorders", "sale_orders", "purchase_orders",
    "pickings", "quality_checks", "maintenance_requests", "equipment", "employees", "docks", "zones", "energy",
    "lighting", "ventilation", "fire", "infra", "evacuation", "sheet_chain", "ship_chain", "material_paths",
    "full_cycle_mo", "passports",
)
# статичні розділи, що потрапляють у `full=1` (R-01 п. 2)
STATIC_SECTIONS = ("energy", "lighting", "ventilation", "fire", "infra", "evacuation", "passports", "zones", "docks")
# списки записів: фільтр `codes` дивиться, чи згадується код у записі
LIST_SECTIONS = ("productions", "pickings", "sale_orders", "purchase_orders", "quality_checks", "maintenance_requests")

# opt-ключі власників (Додаток A.2–A.11): якщо в новому записі їх немає, дельта дописує null (R-14 п. 4)
OPT_KEYS = {
    "locations": ("state", "orderpoint", "production", "picking", "fronts_mo", "note", "reserved_for"),
    "workcenters": ("idle_reason", "maintenance_request", "maintenance_request_id", "current_task"),
    "equipment": ("maintenance_request", "maintenance_request_id", "maintenance_due", "next_maintenance"),
    "maintenance_requests": ("overdue_days",),
    "productions": ("child_productions", "reservation_state"),
    "workorders": ("date_start", "date_finished", "duration", "date_planned_finished", "blocked"),
    "pickings": ("dock", "truck", "location_dest", "source_locations", "vehicle", "note", "carrier"),
}
# модель події -> (розділ payload, ключ запису у списку або None для словника)
REMOVED_MAP = {
    "mrp.production": ("productions", "name"),
    "stock.picking": ("pickings", "name"),
    "stock.location": ("locations", None),
    "mrp.workorder": ("workorders", None),
}


class DeltaTooLarge(Exception):
    pass


# --- helpers ---------------------------------------------------------------

def deep_merge(dst, src):
    """Зливає src у dst на місці й повертає dst (той самий об'єкт). dict — рекурсивно, решта — заміна."""
    if not isinstance(dst, dict) or not isinstance(src, dict):
        raise TypeError("deep_merge: очікуються dict")
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            deep_merge(dst[key], value)
        else:
            dst[key] = copy.deepcopy(value)
    return dst


def read(env, model, domain, fields, order=None):
    """ORM-читання з правами користувача, без sudo."""
    return env[model].search_read(domain, fields, order=order)


def access_ok(env, model):
    """Модель є в реєстрі і користувач має право читання."""
    return model in env and env[model].has_access("read")


def group_ok(env, xmlid):
    """Група існує в базі й користувач у ній."""
    if not env["ir.model.data"]._xmlid_to_res_id(xmlid, raise_if_not_found=False):
        return False
    return env.user.has_group(xmlid)


def get_providers(env):
    """Duck-typing (X-22): усі моделі реєстру з префіксом імені, незалежно від `_inherit`."""
    names = [n for n in env.registry if n.startswith(PROVIDER_PREFIX)]
    return sorted((env[n] for n in names), key=lambda m: (getattr(m, "_td_sequence", 1000), m._name))


def default_delta(provider, patch, ctx):
    """Дельта за замовчуванням (R-14 п. 5): collect у тимчасовий dict і deep_merge розділів провайдера."""
    collect = getattr(provider, "_td_viewer_collect", None)
    if collect is None:
        return
    secs = tuple(getattr(provider, "_td_sections", ()))
    tmp = {}
    collect(tmp, ctx)
    part = {k: tmp[k] for k in secs if k in tmp}
    for key, value in part.items():
        if len(json.dumps(value, default=str)) > DELTA_MAX_BYTES:
            raise DeltaTooLarge(key)
    deep_merge(patch, part)


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _walk_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk_strings(v)


def filter_codes(payload, codes):
    """`codes` обмежує locations/workcenters/equipment кодами; документи — ті, що посилаються на коди."""
    for key in ("locations", "workcenters", "equipment", "workorders"):
        if isinstance(payload.get(key), dict):
            payload[key] = {k: v for k, v in payload[key].items()
                            if k in codes or any(s in codes for s in _walk_strings(v))}
    for key in LIST_SECTIONS:
        if isinstance(payload.get(key), list):
            payload[key] = [r for r in payload[key] if any(s in codes for s in _walk_strings(r))]
    return payload


class _Base:
    """Спільне для збирача й дельти: контекст провайдерів і безпечний виклик."""

    def __init__(self, env, lite=False, kiosk=False, codes=None):
        self.env = env
        self.lite = bool(lite)
        self.kiosk = bool(kiosk)
        self.codes = set(codes) if codes else None
        self._groups = {}  # кеш group_ok в межах одного збирання
        self._strict = False

    def build(self):
        """Оптимістичний прохід: один спільний savepoint замість двох SQL на провайдера (AC-52).
        Якщо провайдер упав — savepoint відкочується, і збирання повторюється з ізоляцією кожного."""
        self._strict = True
        try:
            with self.env.cr.savepoint():
                return self._build()
        except Exception:  # noqa: BLE001 — деталі пише повторний прохід
            pass
        finally:
            self._strict = False
        self._groups = {}
        return self._build()

    def _group_ok(self, xmlid):
        if xmlid not in self._groups:
            self._groups[xmlid] = group_ok(self.env, xmlid)
        return self._groups[xmlid]

    def _ctx(self, now, sections, **extra):
        env = self.env
        ctx = {
            "user": env.user,
            "now": now,
            "now_local": dates.local(now),
            "today": dates.local(now)[:10],
            "static": static_data.load(),
            "lite": self.lite,
            "kiosk": self.kiosk,
            "energy_cost": (not self.kiosk) and self._group_ok(ENERGY_COST_GROUP),
            "codes": None,
            "changes": {},
            "sections": sections,
        }
        ctx.update(extra)
        return ctx

    @staticmethod
    def _info(p):
        return (tuple(getattr(p, "_td_sections", ())),
                getattr(p, "_td_group", DEFAULT_GROUP))

    def _call(self, p, func, target, secs, errors):
        """Виклик у savepoint; при помилці розділи провайдера відновлюються. True — успіх."""
        if self._strict:
            func(target)
            return True
        before = {k: copy.deepcopy(target[k]) for k in secs if k in target}
        try:
            with self.env.cr.savepoint():
                func(target)
            return True
        except Exception as e:  # noqa: BLE001 — провайдер не має ламати відповідь
            if isinstance(e, DeltaTooLarge):
                _logger.warning("дельта провайдера %s завелика (розділ %s)", p._name, e)
            else:
                _logger.exception("провайдер %s впав", p._name)
            for k in secs:
                if k in before:
                    target[k] = before[k]
                else:
                    target.pop(k, None)
            errors.append({"provider": p._name, "error": type(e).__name__})
            return False


class PayloadBuilder(_Base):
    """R-01."""

    def __init__(self, env, full=False, lite=False, kiosk=False, sections=None, codes=None):
        super().__init__(env, lite=lite, kiosk=kiosk, codes=codes)
        self.full = bool(full)
        self.sections = set(sections) if sections else None

    def _meta(self, now):
        env = self.env
        params = env["ir.config_parameter"].sudo()
        host = re.sub(r"^https?://", "", params.get_param("web.base.url") or "").rstrip("/")
        warehouse = ""
        if access_ok(env, "stock.warehouse"):
            wh = env["stock.warehouse"].search_fetch([("company_id", "=", env.company.id)], limit=1)
            warehouse = wh.code or ""
        return {
            "source": f"Odoo {release.series} · {host}",
            "database": env.cr.dbname,
            "company": env.company.name,
            "warehouse": warehouse,
            "now": dates.local(now),
            "live": True,
            "pulled_at": dates.local(dates.real_now()),
            "schema": SCHEMA,
            "ts_utc": dates.iso_utc(dates.real_now()),
            "user": env.user.name,
            "lite": self.lite,
            "kiosk": self.kiosk,
            "bus": str(params.get_param("td.viewer.bus_enabled") or "True").lower() in ("true", "1"),
            "sections": {},
            "errors": [],
        }

    def _build(self):
        env = self.env
        static = static_data.load()
        now = dates.now(env)
        meta = self._meta(now)
        sections, errors = meta["sections"], meta["errors"]
        payload = {"meta": meta}
        ctx = self._ctx(now, sections, codes=self.codes)

        if self.full:
            for key in STATIC_SECTIONS:
                if key in static and (self.sections is None or key in self.sections):
                    payload[key] = copy.deepcopy(static[key])
                    sections[key] = "static"
        # порожні вузли для сигналів: провайдер сигналів має куди писати, клієнт зливає глибоко
        payload.setdefault("energy", {})
        for node in ("consumers", "transformers", "totals"):
            payload["energy"].setdefault(node, {})
        payload.setdefault("equipment", {})
        payload.setdefault("ventilation", {}).setdefault("units", {})
        payload.setdefault("fire", {}).setdefault("groups", {})
        payload.setdefault("infra", {}).setdefault("totals", {})

        for p in get_providers(env):
            collect = getattr(p, "_td_viewer_collect", None)
            if collect is None:
                _logger.warning("провайдер %s без _td_viewer_collect", p._name)
                continue
            secs, grp = self._info(p)
            if self.sections is not None and not (set(secs) & self.sections):
                continue
            if not self._group_ok(grp):
                for k in secs:
                    sections[k] = "denied"
                    if k in BASE_KEYS and k != "meta":  # §4.4: порожнє значення за типом ключа
                        payload.setdefault(k, [] if k in LIST_SECTIONS else {})
                continue
            seen = dict(sections)
            if self._call(p, lambda target, c=collect: c(target, ctx), payload, secs, errors):
                for k in secs:
                    if k in payload and sections.get(k) == seen.get(k):
                        sections[k] = "live"
            else:
                for k in secs:
                    sections[k] = "error"

        if self.codes:
            filter_codes(payload, self.codes)
        meta["note"] = self._note(payload, meta)
        # R-01 п. 6: спершу 26 базових ключів (A.0), далі ключі модулів у порядку першої появи
        ordered = {k: payload[k] for k in BASE_KEYS if k in payload}
        ordered.update({k: v for k, v in payload.items() if k not in ordered})
        return ordered

    def _note(self, payload, meta):
        quants = sum(len(loc.get("quants") or []) for loc in (payload.get("locations") or {}).values()
                     if isinstance(loc, dict))
        note = "Живі дані з бази: %d переміщень, %d виробничих замовлень, %d залишків." % (
            len(payload.get("pickings") or []), len(payload.get("productions") or []), quants)
        iot = meta.get("iot")
        if iot:
            note += " Сигналів імітації: %s." % iot.get("signals", 0)
        clock = self.env["ir.config_parameter"].sudo().get_param(dates.PARAM_CLOCK)
        if clock and dates.CLOCK_RE.match(clock):
            note += " Демо-годинник зупинено на %s — від нього рахуються таймери робочих завдань." % clock
        return note


class DeltaBuilder(_Base):
    """R-14. `changes` (для тестів) підміняє читання td.viewer.event."""

    def __init__(self, env, since, codes=None, lite=False, kiosk=False, changes=None):
        super().__init__(env, lite=lite, kiosk=kiosk, codes=codes)
        self.since = since
        self.changes = changes

    def _build(self):
        env = self.env
        now = dates.now(env)
        ts = dates.iso_utc(dates.real_now())
        if self.changes is not None:
            changes = self.changes
        elif "td.viewer.event" in env:
            changes = env["td.viewer.event"]._since(self.since)
        else:
            changes = None
        if changes is None:
            return {"full": True, "ts": ts}
        codes = set(self.codes or ())
        for value in changes.values():
            codes |= set(value)
        if not codes and not changes:
            return {"ts": ts, "patch": {}, "removed": {}, "events": 0}

        patch = {"meta": {"now": dates.local(now), "errors": []}}
        errors = patch["meta"]["errors"]
        ctx = self._ctx(now, {}, codes=codes, changes=changes, delta=True)
        failed = set()
        for p in get_providers(env):
            collect = getattr(p, "_td_viewer_collect", None)
            if collect is None:
                _logger.warning("провайдер %s без _td_viewer_collect", p._name)
                continue
            secs, grp = self._info(p)
            if not self._group_ok(grp):
                continue
            delta = getattr(p, "_td_viewer_delta", None)

            def run(target, p=p, delta=delta):
                if delta is None:
                    default_delta(p, target, ctx)
                else:
                    delta(target, ctx)
            if not self._call(p, run, patch, secs, errors):
                failed.update(secs)
        if not errors:
            patch["meta"].pop("errors")
        self._null_opt_keys(patch)
        return {"ts": ts, "full": False, "events": len(changes), "patch": patch,
                "removed": self._removed(changes, patch, failed)}

    @staticmethod
    def _null_opt_keys(patch):
        for section, keys in OPT_KEYS.items():
            value = patch.get(section)
            records = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
            for rec in records:
                if isinstance(rec, dict):
                    for k in keys:
                        rec.setdefault(k, None)

    @staticmethod
    def _removed(changes, patch, failed):
        removed = {"productions": [], "pickings": [], "locations": [], "workorders": []}
        for model, (section, key) in REMOVED_MAP.items():
            if section in failed or model not in changes:
                continue
            value = patch.get(section) or ([] if key else {})
            present = {r.get(key) for r in value if isinstance(r, dict)} if key else set(value)
            removed[section] = sorted(c for c in changes[model] if c not in present)
        return removed


# --- резолвер R-16 -----------------------------------------------------------

DOC_MODELS = ("mrp.production", "stock.picking", "sale.order", "purchase.order", "maintenance.request",
              "quality.check")
WO_RE = re.compile(r"^WO(\d{5})$")


def _found(rec, kind=None):
    if kind is None:
        kind = rec.td_kind if "td_kind" in rec._fields and rec.td_kind else "document"
    return {"model": rec._name, "res_id": rec.id, "display_name": rec.display_name, "kind": kind}


def _not_found():
    return {"model": None, "res_id": None, "reason": "not_found"}


RESOLVE_GROUP_MAX = 200


def _resolve_group(env, codes):
    """R-16 п. 5: об'єкт сцени без власного запису (стелаж, група) -> записи його дочірніх кодів (комірок): перша за
    порядком домішки модель, у якій знайшлось хоч щось. {model, res_id: None, res_ids, display_name, kind, count}."""
    codes = list(dict.fromkeys(codes))[:RESOLVE_GROUP_MAX]
    for model in env["td.scene.mixin"]._td_resolve_order:
        if not codes or model not in env or not hasattr(env[model], "search_f3d") or not access_ok(env, model):
            continue
        recs = env[model].search(["|", ("td_code", "in", codes), ("td_alias", "in", codes)],
                                 limit=RESOLVE_GROUP_MAX)
        if recs:
            return {"model": model, "res_id": None, "res_ids": recs.ids, "display_name": None, "kind": "group",
                    "count": len(recs)}
    return _not_found()


def _operator_of(env, wc_code):
    """OP-<wc> без запису -> співробітник оператора поточного завдання на центрі."""
    if not (access_ok(env, "mrp.workcenter") and access_ok(env, "mrp.workorder") and access_ok(env, "hr.employee")):
        return None
    wc = env["mrp.workcenter"].search_f3d(wc_code) if hasattr(env["mrp.workcenter"], "search_f3d") else None
    if not wc:
        return None
    wo = env["mrp.workorder"].search([("workcenter_id", "=", wc.id), ("state", "=", "progress")], limit=1)
    if not wo or "working_user_ids" not in wo._fields or not wo.working_user_ids:
        return None
    return env["hr.employee"].search([("user_id", "in", wo.working_user_ids.ids)], limit=1) or None


def resolve(env, code=None, name=None, codes=None):
    """{model, res_id, display_name, kind} або {model: None, res_id: None, reason: "not_found"}.
    `codes` (лише з `code`): коди дочірніх об'єктів — якщо власного запису немає, відповідь `_resolve_group`."""
    if code:
        m = WO_RE.match(code)
        if m and access_ok(env, "mrp.workorder"):
            wo = env["mrp.workorder"].search([("id", "=", int(m.group(1)))], limit=1)
            if wo:
                return _found(wo, "document")
        mixin = env["td.scene.mixin"]
        for model in mixin._td_resolve_order:
            if model not in env or not hasattr(env[model], "search_f3d") or not access_ok(env, model):
                continue
            rec = env[model].search_f3d(code)
            if rec:
                return _found(rec)
        if code.startswith("OP-"):
            emp = _operator_of(env, code[3:])
            if emp:
                return _found(emp)
        return _resolve_group(env, codes) if codes else _not_found()
    if name:
        for model in DOC_MODELS:
            if model in env and access_ok(env, model):
                rec = env[model].search([("name", "=", name)], limit=1)
                if rec:
                    return _found(rec, "document")
    return _not_found()


def log_scene_codes(env):
    """post_init, крок 2 (§5.4): скільки кодів статики знаходиться резолвером R-16."""
    static = static_data.load()
    codes = set()
    for key in ("locations", "workcenters", "equipment", "zones"):
        codes.update(static.get(key) or {})
    by_model = {}
    for code in sorted(codes):
        try:
            res = resolve(env, code=code)
        except Exception:  # noqa: BLE001
            continue
        if res["model"]:
            by_model[res["model"]] = by_model.get(res["model"], 0) + 1
    _logger.info("td_viewer3d: знайдено записів %d з %d кодів сцени: %s",
                 sum(by_model.values()), len(codes), by_model)
