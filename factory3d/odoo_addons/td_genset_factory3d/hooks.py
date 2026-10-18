"""SPEC §5.3, §5.4. Усі кроки ідемпотентні; звіт — параметр factory3d.genset.migration_report."""

import json
import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .adapters import td_genset as td
from .adapters import telemetry

_logger = logging.getLogger(__name__)
KYIV = ZoneInfo("Europe/Kyiv")
P = "factory3d.genset."


def _next_06_kyiv_utc(now_utc=None):
    """Найближче 06:00 Europe/Kyiv, переведене в UTC naive."""
    now_utc = now_utc or datetime.now(timezone.utc).replace(tzinfo=None)
    local = now_utc.replace(tzinfo=timezone.utc).astimezone(KYIV)
    target = datetime.combine(local.date(), time(6, 0), tzinfo=KYIV)
    if target <= local:
        target = datetime.combine(local.date() + timedelta(days=1), time(6, 0), tzinfo=KYIV)
    return target.astimezone(timezone.utc).replace(tzinfo=None)


def post_init_hook(env):
    icp = env["ir.config_parameter"].sudo()
    report = {}
    # 0. td_code рядків мапи подій: зберегти поточні, відновити збережені в порожні (ключ → код)
    if "f3d.genset.event.map" in env:
        try:
            saved = json.loads(icp.get_param(P + "migration_report") or "{}").get("td_codes", {})
        except ValueError:
            saved = {}
        rows = env["f3d.genset.event.map"].sudo().with_context(active_test=False)
        current = {row.key: row.td_code for row in rows.search([("td_code", "!=", False)])}
        report["td_codes"] = {**saved, **current}
        for key, code in saved.items():
            row = rows.search([("key", "=", key)], limit=1)
            if row and code and not row.td_code:
                row.td_code = code
    # 1. стоп-крани за CB-10
    if icp.get_param("factory3d.base.environment", "test") == "prod":
        icp.set_param(P + "read_enabled", "False")
    read_enabled = icp.get_param(P + "read_enabled", "False") in ("True", "true", "1")
    requests_enabled = icp.get_param(P + "requests_enabled", "False") in ("True", "true", "1")
    # 2. паспорт профілю
    profile = env.ref("factory3d_genset.profile_d700", raise_if_not_found=False)
    passport = env["f3d.equipment.passport"].search([("role", "=", "genset")], limit=1)
    if profile and passport:
        profile.passport_id = passport
        mismatch = {}
        for key, field in (("tank_l", "tank_l"), ("kva", "kva_prp"), ("fuel_lph_75", "fuel_lph_75")):
            value = passport.get_num(key)
            if value and abs(value - profile[field]) > 1e-6:
                mismatch[key] = {"passport": value, "profile": profile[field]}
        if mismatch:
            report["passport_mismatch"] = mismatch
    # 3–7. обладнання, джерело, сигнали, зв'язка
    eq = env["maintenance.equipment"].search([("f3d_code", "=", "GENSET")], limit=1)
    if not eq:
        report["link"] = "skipped: немає обладнання з f3d_code=GENSET"
    else:
        Link = env["f3d.genset.link"].sudo().with_context(active_test=False)
        link = Link.search([("equipment_id", "=", eq.id)], limit=1)
        pseudo = link or Link.new({"equipment_id": eq.id})
        had_source = bool(env["f3d.source"].sudo().search_count([("code", "=", telemetry.SOURCE_CODE)]))
        source = telemetry.ensure_source(env, pseudo)
        report["source"] = {"created": 0 if had_source else 1, "existing": 1 if had_source else 0}
        gens, link_msg = None, None
        try:
            gens = td.generators(env)
        except NotImplementedError:
            link_msg = "skipped: ADP-01 не звірено"
        if link:
            report["link"] = {"created": 0, "existing": 1}
            if not link.source_id:
                link.source_id = source
        elif gens is None:
            report["link"] = link_msg
        elif len(gens) == 1:
            link = Link.create(
                {
                    "equipment_id": eq.id,
                    "td_genset_ref": "%s,%d" % (td.GENSET_MODEL, gens.id),
                    "profile_id": profile.id,
                    "source_id": source.id,
                }
            )
            report["link"] = {"created": 1, "existing": 0}
        elif len(gens) > 1:
            report["link"] = "skipped: кілька генераторів — зв'яжіть вручну"
        else:
            report["link"] = "skipped: у td_genset немає генераторів"
        # сигнали (крок 5) — після зв'язки, бо ensure_signals бере код з link.equipment_id
        n_before = (
            env["f3d.signal"]
            .sudo()
            .with_context(active_test=False)
            .search_count([("code", "=like", telemetry.prefix(eq.f3d_code) + "%")])
        )
        telemetry.ensure_signals(env, link or pseudo)
        report["signals"] = {"created": len(telemetry.LEAFS) - n_before, "existing": n_before}
        report["meter"] = "skipped: A-04"
    # 8. крони
    cron_flags = {
        "cron_f3d_genset_publish": read_enabled,
        "cron_f3d_genset_events": requests_enabled,
        "cron_f3d_genset_service": requests_enabled,
    }
    for xml_id, flag in cron_flags.items():
        cron = env.ref("factory3d_genset." + xml_id, raise_if_not_found=False)
        if cron:
            cron.sudo().active = flag
            if xml_id == "cron_f3d_genset_service":
                cron.sudo().nextcall = _next_06_kyiv_utc()
    # 9. звіт
    icp.set_param(P + "migration_report", json.dumps(report, ensure_ascii=False))
    _logger.info("factory3d_genset: міграцію виконано: %s", report)


def uninstall_hook(env):
    icp = env["ir.config_parameter"].sudo()
    icp.search([("key", "=like", "factory3d.genset.%")]).unlink()
    sources = env["f3d.source"].sudo().with_context(active_test=False).search([("type", "=", "td_genset")])
    sources.write({"active": False})
