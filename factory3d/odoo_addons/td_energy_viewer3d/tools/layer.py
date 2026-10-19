"""R-57 (SPEC 8.4.2): збирання payload `energy.layer` — стан вузлів мережі й тривоги для 3D.

Стани, номінали й пороги беруться зі знімка `td_energy.tools.sld.Snap` (той самий, що в Пульті: AC-284),
струм/потужність/номінал — з `NodeCard` (картка вузла W1). Модуль не пише в БД; читання — `sudo()` лише на читання
конкретних полів. Ключів вартості й імен користувачів у шарі немає.
"""

import json
import logging

from odoo.addons.td_energy.tools import dates, node_card, sld

_logger = logging.getLogger(__name__)

P = "td.energy_viewer3d."
SCHEMA = 1
LAYER_KINDS = ("line", "transformer", "cell", "generator", "storage", "ats", "section")
CARD_KINDS = ("line", "transformer", "cell")  # для них є `NodeCard` (струм, потужність, номінал)
# «гірший» стан об'єкта сцени: тривога > увага > генерує > норма > вимкнено
RANK = {"alarm": 4, "warn": 3, "gen": 2, "ok": 1, "off": 0}
CABLES = "CABLES"  # єдиний об'єкт сцени для кабельних ліній C1, C2
DEFAULT_LAYERS = ["building", "zones", "line", "facade", "energy", "backup", "roofdeck"]
DEFAULT_MARKER_LIMIT = 40
MAX_MARKER_LIMIT = 200
TITLE_MAX = 80
EVENT_LIMIT = 500
CARD_GROUP = "td_energy.group_td_energy_user"
# у киоску тривога без технічних деталей діагностики: лише загальна назва за видом події
KIOSK_TITLES = {
    "threshold": "Перевищення порогу",
    "peak": "Пік потужності",
    "balance": "Розбіжність обліку",
    "meter": "Немає зв'язку з лічильником",
    "ats": "АВР",
    "outage": "Відключення живлення",
    "pfc": "Компенсація реактивної потужності",
    "trip": "Спрацювання захисту",
}
_MANIFEST_CODES = {}  # sha1 маніфесту частин моделі → множина кодів об'єктів сцени


# --- параметри (M-42) ---------------------------------------------------------------------------------------
def parse_layers(raw):
    """JSON-список ключів шарів; порожнє, не JSON чи не список рядків — типовий список."""
    try:
        value = json.loads(raw) if raw else None
    except ValueError:
        value = None
    if isinstance(value, list) and value and all(isinstance(k, str) and k for k in value):
        return value
    return list(DEFAULT_LAYERS)


def params(env):
    """`{layers, marker_limit, show_markers}` з `td.energy_viewer3d.*` (типові значення, якщо параметра немає)."""
    icp = env["ir.config_parameter"].sudo()
    try:
        limit = int(icp.get_param(P + "marker_limit") or DEFAULT_MARKER_LIMIT)
    except ValueError:
        limit = DEFAULT_MARKER_LIMIT
    return {
        "layers": parse_layers(icp.get_param(P + "layers")),
        "marker_limit": max(1, min(limit, MAX_MARKER_LIMIT)),
        "show_markers": icp.get_param(P + "show_markers", "True") not in ("False", "false", "0"),
    }


# --- об'єкт сцени ---------------------------------------------------------------------------------------------
def _manifest_codes():
    """Коди об'єктів з маніфесту частин моделі `td_viewer3d` (кеш за sha1)."""
    from odoo.addons.td_viewer3d.tools import static_data  # noqa: PLC0415 — місток не ламає ядро без переглядача

    body, sha1 = static_data.parts_manifest()
    if sha1 not in _MANIFEST_CODES:
        parts = json.loads(body).get("parts") or []
        _MANIFEST_CODES.clear()
        _MANIFEST_CODES[sha1] = {c for part in parts for c in part.get("codes") or []}
    return _MANIFEST_CODES[sha1]


def scene_codes(ctx=None):
    """Відомі коди сцени: `energy.lines|transformers|cells`, `equipment`, `zones` зі статики `td_viewer3d`
    (`ctx["static"]` чи `static_data.load()`) плюс коди об'єктів GLB. Отримати неможливо — `None` (A-53)."""
    try:
        static = (ctx or {}).get("static")
        if static is None:
            from odoo.addons.td_viewer3d.tools import static_data  # noqa: PLC0415

            static = static_data.load()
        known = set()
        energy = static.get("energy") or {}
        for key in ("lines", "transformers", "cells"):
            known.update(energy.get(key) or {})
        known.update(static.get("equipment") or {})
        known.update(static.get("zones") or {})
        known.update(_manifest_codes())
    except Exception:  # noqa: BLE001 — шар має працювати й без статики
        _logger.warning("energy.layer: коди сцени недоступні, scene без перевірки", exc_info=True)
        return None
    return known or None


def scene_of(code, kind, line_kind, equipment_code, known):
    """`scene`: кабельна лінія → `CABLES`; інакше `equipment.td_code` або `code` вузла; немає серед відомих → `None`."""
    if kind == "line" and line_kind == "cable":
        return CABLES
    scene = equipment_code or code
    if known is not None and scene not in known:
        return None
    return scene


def node_scene(node, ctx=None):
    """`scene` запису `td.energy.node` (для `action_td_open_3d`)."""
    node = node.sudo()
    return scene_of(node.code, node.kind, node.line_kind, node.equipment_id.td_code or None, scene_codes(ctx))


def worst_state(states):
    """Найгірший стан із набору (порожній набір — `ok`)."""
    return max(states, key=lambda s: RANK.get(s, 0), default="ok")


def scene_states(layer):
    """`{scene: стан}` — найгірший серед вузлів шару з тим самим `scene` (вузли без `scene` пропускаються)."""
    by_scene = {}
    for node in (layer or {}).get("nodes") or []:
        if node.get("scene"):
            by_scene.setdefault(node["scene"], []).append(node["state"])
    return {scene: worst_state(states) for scene, states in by_scene.items()}


# --- збирання ---------------------------------------------------------------------------------------------------
def _num(value):
    return int(value) if value == int(value) else value


def _equipment_codes(env, ids):
    if not ids:
        return {}
    rows = env["maintenance.equipment"].sudo().search_read([("id", "in", sorted(ids))], ["td_code"])
    return {r["id"]: r["td_code"] for r in rows if r["td_code"]}


def _power_kw(snap, row, card):
    """Потужність вузла, кВт: картка (лінії, шафи, трансформатори) чи інфра-сигнали; `None` — немає даних."""
    kind = row["kind"]
    if card is not None:
        p = card.power_kw()
        if p is None and kind == "line":
            meter = snap.meter_of(row)
            if meter and meter["data_state"] in ("stale", "no_data"):
                p = snap.section_estimate(row)  # «Оцінка за балансом секції» (W1 R-30)
        return p
    if kind == "generator":
        if row["gen_kind"] == "pv_inverters":
            return snap.v("infra/totals/pv_now")
        if row["gen_kind"] == "chp":
            return snap.v("infra/totals/chp_kw")
    if kind == "storage":
        return snap.v("infra/totals/bess_kw")
    if kind == "section" and row["section"]:
        return snap.v("energy/sections/S%d/p_kw" % row["section"])
    return None


def _events(env, snap):
    """Відкриті події `warn|bad` вузлів: спершу `bad`, далі за часом (нові першими); ≤ `EVENT_LIMIT`."""
    rows = (
        env["td.energy.event"]
        .sudo()
        .search_read(
            [("state", "in", sld.OPEN_STATES), ("level", "in", ("warn", "bad")), ("node_id", "!=", False)],
            ["node_id", "level", "kind", "title", "text", "ts", "state"],
            order="ts desc, id desc",
            limit=EVENT_LIMIT,
        )
    )
    rows = [r for r in rows if r["node_id"][0] in snap.nodes]
    return sorted(rows, key=lambda r: r["level"] != "bad")  # сортування стабільне: у межах рівня порядок за часом


def _title(event, kiosk):
    if kiosk:
        return KIOSK_TITLES.get(event["kind"]) or ("Тривога" if event["level"] == "bad" else "Увага")
    return (event["title"] or event["text"] or "")[:TITLE_MAX]


def build(env, ctx=None):
    """Розділ `energy.layer` (SPEC 8.4.2)."""
    ctx = ctx or {}
    kiosk = bool(ctx.get("kiosk"))
    prm = params(env)
    now = env.context.get("f3d_now") or ctx.get("now") or dates.now_utc(env)
    snap = sld.Snap(env(su=True), now)
    known = scene_codes(ctx)
    events = _events(env, snap)
    rows = [r for r in snap.nodes.values() if r["sld_show"] and r["kind"] in LAYER_KINDS]
    equipment = _equipment_codes(env, {r["equipment"] for r in snap.nodes.values() if r["equipment"]})

    def scene(row):
        return scene_of(row["code"], row["kind"], row["line_kind"], equipment.get(row["equipment"]), known)

    by_node = {}
    for event in events:
        by_node.setdefault(event["node_id"][0], []).append(event)
    card_ok = (not kiosk) and env.user.has_group(CARD_GROUP)
    nodes = []
    for row in rows:
        card = node_card.NodeCard(env, snap, row["code"]) if row["kind"] in CARD_KINDS else None
        load = snap.load_pct(row)
        i_a = card.current_a() if card is not None else None
        rating = card.rating_a() if card is not None else None
        p_kw = _power_kw(snap, row, card)
        own = by_node.get(row["id"], [])
        nodes.append(
            {
                "code": row["code"],
                "scene": scene(row),
                "kind": row["kind"],
                "name": row["sld_label"] or row["name"],
                "state": snap.state(row),
                "load": round(load / 100.0, 3) if load is not None else None,
                "i_a": int(round(i_a)) if i_a is not None else None,
                "p_kw": round(p_kw, 1) if p_kw is not None else None,
                "rating_a": int(rating) if rating else None,
                "card": card_ok,
                "alarms": len(own),
                "worst": own[0]["level"] if own else None,
                "title": _title(own[0], kiosk) if own else None,
            }
        )
    alarms = []
    for event in events[: prm["marker_limit"]]:
        node = snap.nodes[event["node_id"][0]]
        alarms.append(
            {
                "id": event["id"],
                "node": node["code"],
                "scene": scene(node),
                "level": event["level"],
                "title": _title(event, kiosk),
                "time": dates.to_local(event["ts"]).strftime("%H:%M"),
                "state": event["state"],
            }
        )
    summary = {key: sum(1 for n in nodes if n["state"] == key) for key in ("alarm", "warn", "gen", "off")}
    return {
        "schema": SCHEMA,
        "thresholds": {"warn_pct": _num(snap.warn_pct), "alarm_pct": _num(snap.alarm_pct)},
        "show_markers": prm["show_markers"],
        "can_pult": card_ok,  # «Відкрити пульт»: не киоск і група td_energy.group_td_energy_user (або вища)
        "nodes": nodes,
        "alarms": alarms,
        "summary": summary,
    }
