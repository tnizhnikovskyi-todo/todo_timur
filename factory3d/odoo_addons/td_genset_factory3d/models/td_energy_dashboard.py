"""W1-C: M-10 розширення `td.energy.dashboard` — картка «ДГУ», факти вузлів АВР/ДГУ, зведення для Пульту (R-15).

Читання td_genset — лише через `adapters.td_genset` (виклик через атрибут модуля: у тестах підміняється `patch.object`).
Помилки адаптера й відсутній запис td_genset не валять Пульт: хук повертає порожньо й пише `warning` (R-15 п.3).
"""

import logging
from datetime import timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.exceptions import AccessError, MissingError

from ..adapters import td_genset as td

_logger = logging.getLogger(__name__)
KYIV = ZoneInfo("Europe/Kyiv")

# M-10: стан для Пульту за кодом зв'язки (R-03) і підписи
STATE_LABELS = {
    "offline": "немає зв'язку",
    "fault": "аварія",
    "reserve": "резерв",
    "running": "працює",
}
CARD_STATE = {"running": "gen", "fault": "alarm", "reserve": "off", "offline": "off"}  # R-26
NODE_PHRASE = {
    "reserve": "ДГУ в резерві",
    "running": "ДГУ працює",
    "fault": "ДГУ: аварія",
    "offline": "ДГУ: немає зв'язку",
}
ADAPTER_ERRORS = (NotImplementedError, MissingError, AccessError)
GENSET_NODES = ("ATS-1", "GENSET")


def _state_of(link):
    """M-10: `not online` або код 0 → offline; 10 → fault; 1 → reserve; 2…9 → running."""
    code = link.state_code
    if not link.online or code == 0:
        return "offline"
    if code == 10:
        return "fault"
    if code == 1:
        return "reserve"
    return "running"


def _kyiv(ts):
    """Datetime (UTC, naive) → «ДД.ММ ГГ:ХХ» за Києвом."""
    ts = fields.Datetime.to_datetime(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(KYIV).strftime("%d.%m %H:%M")


def _num(value, digits=1):
    return None if value is None else round(value, digits)


class TdEnergyDashboard(models.AbstractModel):
    _inherit = "td.energy.dashboard"

    # --- читання td_genset (лише через адаптер) -----------------------------------------------------------
    @api.model
    def _td_genset_link(self):
        """Перша активна зв'язка з наявним генератором td_genset; інакше порожній набір."""
        Link = self.env["td.genset3d.link"]
        link = Link.search([("active", "=", True)], order="id", limit=1)
        gen = link.td_genset_ref
        return link if link and gen and gen.exists() else Link

    @api.model
    def _td_genset_facts(self, full=True):
        """Дані ДГУ для карток і фактів: `None` (зв'язки немає або адаптер недоступний) або dict.

        `full=False` — лише стан і знімок (зведення Пульту): без тесту, розкладу й ТО.
        """
        link = self._td_genset_link()
        if not link:
            return None
        gen = link.td_genset_ref
        try:
            snap = td.snapshot(gen)
            data = {
                "link": link,
                "gen": gen,
                "state": _state_of(link),
                "fuel_pct": _num(snap.get("fuel_pct")),
                "p_kw": _num(snap.get("p_kw")),
                "hours": _num(snap.get("hours")),
            }
            if full:
                data["last_test"] = td.last_test(gen)
                data["next_event"] = td.next_event(gen)
                data["service"] = td.service_info(gen)
        except ADAPTER_ERRORS as exc:
            _logger.warning("td_genset_factory3d: ДГУ для Пульту недоступна (%s: %s)", type(exc).__name__, exc)
            return None
        return data

    # --- хуки M-27 (C-31) -----------------------------------------------------------------------------------
    @api.model
    def _td_genset_summary(self):
        super()._td_genset_summary()
        data = self._td_genset_facts(full=False)
        if not data:
            return None
        return {"state": data["state"], "label": STATE_LABELS[data["state"]], "fuel_pct": data["fuel_pct"]}

    @api.model
    def _td_generation_cards(self):
        cards = list(super()._td_generation_cards())
        data = self._td_genset_facts()
        if not data:
            return cards
        facts = []
        test = data["last_test"]
        if test and test.get("ts"):
            facts.append("Тест: %s · %s" % (_kyiv(test["ts"]), test.get("result") or "—"))
        if data["next_event"]:
            facts.append("Наступна подія: %s" % data["next_event"])
        service = data["service"]
        if service and service.get("hours_left") is not None:
            facts.append("До ТО: %g мотогод" % round(service["hours_left"], 1))
        cards.append(
            {
                "code": "GENSET",
                "title": "ДГУ",
                "kind": "genset",
                "state": CARD_STATE[data["state"]],
                "kpis": [
                    {"label": "Паливо", "value": data["fuel_pct"], "unit": "%"},
                    {"label": "Потужність", "value": data["p_kw"], "unit": "кВт"},
                    {"label": "Мотогодини", "value": data["hours"], "unit": "год"},
                ],
                "facts": facts,
                "node_code": "GENSET",
                "can_3d": True,
                "link": {"open_action": td.open_action(data["gen"])},
            }
        )
        return cards

    @api.model
    def _td_node_facts_extra(self, node):
        facts = list(super()._td_node_facts_extra(node))
        if node.code not in GENSET_NODES:
            return facts
        data = self._td_genset_facts()
        if not data:
            return facts
        line = [NODE_PHRASE[data["state"]]]
        if data["fuel_pct"] is not None:
            line.append("паливо %d %%" % round(data["fuel_pct"]))
        test = data["last_test"]
        if test and test.get("ts"):
            line.append("тест %s %s" % (_kyiv(test["ts"]), test.get("result") or ""))
        facts.append(" · ".join(line).strip())
        if data["next_event"]:
            facts.append("Наступна подія: %s" % data["next_event"])
        if node.code == "GENSET" and data["hours"] is not None:
            facts.append("Мотогодини %g" % data["hours"])
        return facts

    @api.model
    def _td_node_card_extra(self, node):
        extra = dict(super()._td_node_card_extra(node))
        if node.code != "GENSET":
            return extra
        link = self._td_genset_link()
        if link:
            extra["genset"] = {"link_id": link.id, "open_action": td.open_action(link.td_genset_ref)}
        return extra
