"""R-43 п.5, D-27: текст і чипи карток сценаріїв за числами рушія. Чисті функції."""

from .kinds import fmt

STATE_KIND = {"armed": "arm", "active": "act", "warn": "warn", "off": "off", "unknown": "off"}


def chips(code, params, plant=None):
    """Чипи параметрів картки (макет Control.dc.html): список рядків."""
    p, plant = params or {}, plant or {}
    if code == "peak":
        contract = plant.get("contract_kw") or 0
        pct = round(p.get("limit_kw", 0) / contract * 100) if contract else None
        head = "уставка %s кВт" % fmt(p.get("limit_kw"))
        return [head + (" · %s %%" % pct if pct is not None else ""), "прогноз 15 хв"]
    if code == "self":
        return ["експорт ≤ %s кВт" % fmt(p.get("export_max_kw")), "BESS до %s %%" % fmt(p.get("bess_target_soc_pct"))]
    if code == "pfc":
        cos = plant.get("cos_target")
        step = plant.get("pfc_step_kvar")
        return ["ціль cos φ %s" % (fmt(cos, 2) if cos is not None else "—"), "крок %s квар" % fmt(step)]
    if code == "night":
        return [
            "%s–%s" % (p.get("from", "—"), p.get("to", "—")),
            "RoofVent %s %%" % fmt(p.get("vent_pct")),
            "%s °C" % fmt(p.get("heat_setpoint_c")),
        ]
    if code == "backup":
        return ["АВР → ДГУ", "критичні %s кВт" % fmt(p.get("critical_kw"))]
    if code == "chp":
        return [
            "мін. робота %s год" % fmt(p.get("min_run_h")),
            "ціна газу %s ₴/м³" % fmt(p.get("gas_price_uah_m3"), 2),
        ]
    return []


def _peak_active(facts):
    stage = facts.get("stage")
    parts = ["BESS %s кВт" % fmt(facts.get("bess_kw"))] if stage in (None, "bess") else ["BESS"]
    if stage in ("chp", "shed"):
        parts.append("КГУ")
    if stage == "shed":
        parts.append("скинуто %s" % fmt(facts.get("shed_n")))
    return "Зрізання піку · " + " + ".join(parts)


def state_text(code, enabled, state, facts, fresh=True, params=None):
    """(текст чипа, вид `act|arm|warn|off`). `fresh=False` — немає звіту рушія за `2·heartbeat_stale_s`."""
    facts, params = facts or {}, params or {}
    if not enabled:
        return "Вимкнено", "off"
    if not fresh or state == "unknown":
        return "Немає даних від рушія", "off"
    kind = STATE_KIND.get(state, "off")
    if state == "off":
        return "Вимкнено", kind
    if state == "warn":
        return "Збій: %s" % (facts.get("reason") or facts.get("fault") or "—"), kind
    if code == "peak":
        return (
            ("Чергування · запас %s кВт" % fmt(facts.get("margin_kw"))) if state == "armed" else _peak_active(facts),
            kind,
        )
    if code == "self":
        if state == "armed":
            return "Очікування · експорт %s кВт" % fmt(facts.get("export_kw")), kind
        if facts.get("pv_limit_pct") is not None and facts["pv_limit_pct"] < 100:
            return "Обмеження СЕС %s %%" % fmt(facts["pv_limit_pct"]), kind
        return "Активний · заряд BESS %s кВт" % fmt(facts.get("bess_kw")), kind
    if code == "pfc":
        if state == "armed":
            return "Чергування", kind
        return "Активний · cos φ %s / %s" % (fmt(facts.get("cos1"), 2), fmt(facts.get("cos2"), 2)), kind
    if code == "night":
        if state == "armed":
            return "Наступний запуск о %s" % (facts.get("next_run") or params.get("from") or "—"), kind
        return "Активний до %s" % (params.get("to") or facts.get("until") or "—"), kind
    if code == "backup":
        if state == "armed":
            fuel = facts.get("fuel_pct")
            return ("Готовий · паливо %s %%" % fmt(fuel)) if fuel is not None else "Готовий", kind
        return "Мережі немає · скинуто %s" % fmt(facts.get("shed_n") or 0), kind
    if code == "chp":
        if state == "armed":
            return "Очікує вигідної ціни", kind
        return "Працює · %s кВт" % fmt(facts.get("chp_kw")), kind
    return "—", kind
