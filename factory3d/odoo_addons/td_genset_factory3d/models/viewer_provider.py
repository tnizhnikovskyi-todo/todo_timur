"""M-08, A-18, X-20: провайдер переглядача — `AbstractModel` без `_inherit` (duck typing, ARCHITECTURE §6.7).
Без `td_viewer3d` модель просто ніхто не викликає; імпортів viewer на рівні модуля немає."""

import logging
from datetime import timezone

from odoo import fields, models

from ..adapters import td_genset as td
from ..adapters import telemetry
from .genset_link import ALARM_LABELS, KYIV, STATE_LABELS

_logger = logging.getLogger(__name__)

MODE_LABELS = {0: "стоп", 1: "ручний", 2: "авто", 3: "тест"}
BREAKER_LABELS = {0: "немає", 1: "мережа", 2: "генератор"}
INT_LEAFS = frozenset({"state", "mode", "breaker", "mains_ok", "alarm_level", "alarm_count", "online", "starts"})
UNITS = {row[0]: row[2] for row in telemetry.SIGNALS}
NOTE = (
    "Під час відключення генератор тримає пожежну сигналізацію, освітлення, аспірацію, компресори, "
    "котельню, офіс із серверною і лінії A–B. Для довгих відключень потрібен додатковий паливний бак."
)


def _fmt(value, digits=0):
    """Як plant/infra.py:_fmt: тисячі пробілом, десятковий роздільник — кома."""
    text = ("{:,.%df}" % digits).format(value)
    return text.replace(",", "\0").replace(".", ",").replace("\0", " ")


def _round(leaf, value):
    """R-11."""
    if value is None:
        return None
    if leaf in INT_LEAFS:
        return int(value)
    if UNITS.get(leaf) == "%":
        return round(value / 100.0, 3)
    return round(value, 2) if abs(value) < 20 else round(value, 1)


def _local(ts):
    return ts.replace(tzinfo=timezone.utc).astimezone(KYIV) if ts else None


class F3dViewerProviderGenset(models.AbstractModel):
    _name = "td.viewer.provider.genset"
    _description = "3D: постачальник даних генератора"
    _f3d_sequence = 155
    _f3d_sections = ("infra",)
    _f3d_group = "td_factory3d.group_td_user"

    def _f3d_viewer_collect(self, payload, ctx):
        for link in self.env["td.genset3d.link"].sudo().search([("active", "=", True)]):
            self._collect_link(link, payload)

    def _collect_link(self, link, payload):
        code, profile = link.td_code, link.profile_id
        pfx = telemetry.prefix(code)
        rows = telemetry.read_values(self.env, [pfx + leaf for leaf in telemetry.LEAFS])
        raw = {leaf: rows[pfx + leaf][0] for leaf in telemetry.LEAFS if pfx + leaf in rows}
        node = payload.setdefault("infra", {}).setdefault("genset", {}).setdefault(code, {})
        for leaf, value in raw.items():
            node[leaf] = _round(leaf, value)
        stamps = [r[1] for r in rows.values() if r[1]]
        updated = _local(max(stamps)) if stamps else None
        node["updated"] = updated.strftime("%H:%M") if updated else None
        state = int(raw.get("state") or 0)
        node["state_label"] = STATE_LABELS.get(state, STATE_LABELS[0])
        node["mode_label"] = MODE_LABELS.get(int(raw.get("mode") or 0), "—")
        node["breaker_label"] = BREAKER_LABELS.get(int(raw.get("breaker") or 0), "—")
        node["alarm_label"] = ALARM_LABELS.get(int(raw.get("alarm_level") or 0), "—")
        crit_kw, missing, names = link._critical_kw()
        node["critical_missing"] = missing
        isl = link._island_state_from_signals(raw)
        totals = payload["infra"].setdefault("totals", {})
        totals.update(
            {
                "genset_kw": node.get("p_kw", 0.0),
                "genset_state": node["state_label"],
                "genset_fuel_pct": node.get("fuel_pct"),
                "genset_autonomy_h": node.get("autonomy_h"),
                "island": isl["island"],
                "grid_ok": isl["grid_ok"],
                "genset_kva": int(round(profile.kva_prp)),
            }
        )
        payload["infra"].setdefault("cards", {})[code] = self._card(link, raw, node, isl, crit_kw, names, updated)

    def _card(self, link, raw, node, isl, crit_kw, names, updated):
        """R-10."""
        profile = link.profile_id
        state, island = int(raw.get("state") or 0), bool(isl["island"])
        p_kw, load_pct = raw.get("p_kw"), raw.get("load_pct")
        online = int(raw.get("online") or 0)
        row_state = node["state_label"]
        if state == 7 and p_kw is not None:
            row_state += " · %s кВт (%s %%)" % (_fmt(p_kw), _fmt(load_pct or 0.0, 1))
        elif state == 0:
            row_state = "немає даних"
        autonomy = raw.get("autonomy_h")
        ref_pct = load_pct if state == 7 and (p_kw or 0) > 0 and load_pct else 75.0
        grid = {True: "є", False: "відсутня"}.get(isl["grid_ok"], "—")
        if island:
            grid += " · острів: генератор живить критичних"
        volt = "—"
        if state in (6, 7) and raw.get("u_v") is not None:
            volt = "%s В · %s Гц" % (_fmt(raw["u_v"]), _fmt(raw.get("f_hz") or 0.0, 1))
        hours = "—"
        if raw.get("hours") is not None:
            hours = _fmt(raw["hours"])
            if raw.get("service_h_left") is not None:
                hours += " · до ТО %s" % _fmt(raw["service_h_left"])
        alarm_n = int(raw.get("alarm_count") or 0)
        alarms = "немає" if not alarm_n else "%d: %s" % (alarm_n, node["alarm_label"])
        state_json = link.last_state_json or {}
        if online:
            conn = "оновлено %s" % (updated.strftime("%H:%M") if updated else "—")
        else:
            since = (
                _local(fields.Datetime.to_datetime(state_json.get("offline_since")))
                if state_json.get("offline_since")
                else updated
            )
            conn = "втрачено з %s" % (since.strftime("%H:%M") if since else "—")
        card = {
            "rows": [
                ["Потужність", "%s кВА / %s кВт (основна)" % (_fmt(profile.kva_prp), _fmt(profile.kw_prp))],
                ["Стан", row_state],
                ["Режим", node["mode_label"]],
                ["Логіка AMF", "ATyS p (головний)" if link.amf_master == "ats" else "HGM6120N (AMF)"],
                ["Контролер", "SmartGen HGM6120N · CMM366B-4G → Odoo (td_genset)"],
                [
                    "Паливо",
                    "%s %% · %s л" % (_fmt(raw["fuel_pct"]), _fmt(raw.get("fuel_l") or 0.0))
                    if raw.get("fuel_pct") is not None
                    else "—",
                ],
                [
                    "Автономність",
                    "≈ %s год при %s %%" % (_fmt(autonomy, 1), _fmt(ref_pct)) if autonomy is not None else "—",
                ],
                ["Критичні споживачі зараз", "%s кВт з %s кВт" % (_fmt(crit_kw), _fmt(profile.kw_prp))],
                ["Мережа", grid],
                ["Напруга · частота", volt],
                ["Мотогодини", hours],
                ["Тривоги", alarms],
                ["Остання перевірка", self._last_test(link)],
                ["Зв'язок", conn],
            ],
            "items": list(names),
            "note": NOTE,
        }
        warn = None
        if int(raw.get("alarm_level") or 0) == 2:
            warn = "Аварійна зупинка: %s" % (alarm_n or 1)
        elif not online:
            since = state_json.get("offline_since")
            mins = int((telemetry.now() - fields.Datetime.to_datetime(since)).total_seconds() // 60) if since else 0
            warn = "Зв'язок із контролером втрачено (%d хв)" % mins
        elif int(raw.get("alarm_level") or 0) == 1:
            warn = "Попередження: %s" % (alarm_n or 1)
        elif island and autonomy is not None and autonomy < profile.autonomy_warn_h:
            warn = "Палива на ≈ %s год — підготувати заправку" % _fmt(autonomy, 1)
        if warn:
            card["warn"] = warn
        return card

    def _last_test(self, link):
        """ADP-07; адаптер може бути не звірений — тоді «—»."""
        try:
            info = td.last_test(link.td_genset_ref)
        except Exception:
            _logger.debug("td_genset_factory3d: last_test недоступний", exc_info=True)
            return "—"
        if not info or not info.get("ts"):
            return "—"
        local = _local(info["ts"].replace(tzinfo=None) if info["ts"].tzinfo else info["ts"])
        text = local.strftime("%d.%m %H:%M")
        if info.get("duration_min") is not None:
            text += " — тест %s хв, %s" % (_fmt(info["duration_min"]), info.get("result") or "—")
        return text

    def _f3d_viewer_delta(self, patch, ctx):
        """R-13: власна дельта з глибоким злиттям; `patch["infra"]` не присвоюється."""
        changes = (ctx or {}).get("changes") or {}
        if not self._wants_delta(changes):
            return
        from odoo.addons.td_viewer3d.tools.payload import deep_merge

        tmp = {}
        self._f3d_viewer_collect(tmp, ctx)
        deep_merge(patch.setdefault("infra", {}), tmp.get("infra", {}))

    def _wants_delta(self, changes):
        Link = self.env["td.genset3d.link"].sudo()
        if changes.get("maintenance.equipment"):
            codes = set(Link.search([("active", "=", True)]).mapped("td_code"))
            if codes & set(changes["maintenance.equipment"]):
                return True
        signals = [str(c) for c in changes.get("td.signal") or ()]
        if any(c.startswith(("infra/genset/", "infra/ats/")) for c in signals):
            return True
        return bool(signals) and bool(set(signals) & set(Link._critical_signal_codes()))

    def _f3d_viewer_bus_models(self):
        return ["maintenance.equipment", "td.signal"]
