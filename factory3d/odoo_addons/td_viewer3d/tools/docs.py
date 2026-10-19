"""R-23: назви й стани документів для карток (стани-бейджі, посилання на форму Odoo).

Стан документа — нормалізований так само, як у payload: `stock.picking` (`PICK_STATE`), `mrp.production`
(`MO_STATE`), `quality.check` (`quality_state` без змін). Клієнт перекладає стан у українську мітку за видом
документа (`picking | scrap | production | quality`, `format.js`).
"""

import re

from . import payload as payload_tools

# назва документа: `WH/IN/00128`, `WH/INT/00061`, `QC/00413` (сегменти-префікси, потім число); клієнтський DOC_RE — той
# самий
NAME_RE = re.compile(r"\b(?:[A-Z][A-Z0-9]{0,5}/){1,3}\d{3,}\b")
PICK_STATE = {
    "confirmed": "waiting",
    "waiting": "waiting",
    "assigned": "assigned",
    "done": "done",
    "draft": "draft",
    "cancel": "cancel",
}
MO_STATE = {
    "to_close": "progress",
    "draft": "draft",
    "confirmed": "confirmed",
    "progress": "progress",
    "done": "done",
    "cancel": "cancel",
}
NAMES_LIMIT = 200


def names_in(*texts):
    """Усі назви документів у рядках (None пропускається)."""
    found = set()
    for text in texts:
        if text:
            found.update(NAME_RE.findall(text))
    return found


def picking_state(raw):
    return PICK_STATE.get(raw, raw)


def production_state(raw):
    return MO_STATE.get(raw, raw)


def lookup_states(env, names):
    """Пакетно (по одному запиту на модель): {назва: {"kind", "state"}} для назв, знайдених у моделях
    `stock.picking` / `mrp.production` / `quality.check` (з правами користувача; відсутня модель пропускається)."""
    left = sorted(names)[:NAMES_LIMIT]
    out = {}
    for model, kind, field, norm in (
        ("stock.picking", "picking", "state", picking_state),
        ("mrp.production", "production", "state", production_state),
        ("quality.check", "quality", "quality_state", lambda s: s),
    ):
        if not left or not payload_tools.access_ok(env, model):
            continue
        for rec in env[model].search_fetch([("name", "in", left)], ["name", field], limit=NAMES_LIMIT):
            out.setdefault(rec.name, {"kind": kind, "state": norm(rec[field])})
        left = [n for n in left if n not in out]
    return out
