"""Статус сигналу за порогами (R-04) і допоміжні функції R-07. Чисті функції без ORM."""

RANK = {"unknown": 0, "stale": 0, "ok": 0, "warn": 1, "alarm": 2}
LEVELS = ("ok", "warn", "alarm")

CFG_FIELDS = (
    "kind",
    "warn_low_on",
    "warn_low",
    "warn_high_on",
    "warn_high",
    "alarm_low_on",
    "alarm_low",
    "alarm_high_on",
    "alarm_high",
    "hysteresis",
    "min_duration_s",
    "alarm_states",
)


def cov_check_s(period_s):
    """Інтервал контрольного читання COV-сигналу колектором (R-07, X-06)."""
    return max(int(period_s or 0) * 10, 300)


def _breach(cfg, level, v, sticky, h):
    """Чи порушено поріг рівня `level` ('warn'|'alarm'); `sticky` — діє гістерезис (поточний статус не нижчий)."""
    lo_on, hi_on = cfg.get(level + "_low_on"), cfg.get(level + "_high_on")
    lo, hi = cfg.get(level + "_low") or 0.0, cfg.get(level + "_high") or 0.0
    if lo_on and (v < lo or (sticky and v < lo + h)):
        return True
    if hi_on and (v > hi or (sticky and v > hi - h)):
        return True
    return False


def eval_status(state, value, text, ts, cfg, quality=None, ignore_min_duration=False):
    """R-04. `state = {"status", "breach_since"}`, `cfg` — поля порогів сигналу (CFG_FIELDS).

    Повертає `(status, breach_since)`. `q='bad'` статус не змінює; `kind='event'` — завжди `ok`;
    `kind='state'` — `text ∈ alarm_states` → `alarm`; `gauge/counter` — пороги з гістерезисом і мін. тривалістю.
    """
    cur = state.get("status") or "unknown"
    since = state.get("breach_since")
    if quality == "bad":
        return cur, since
    kind = cfg.get("kind") or "gauge"
    if kind == "event":
        return "ok", None
    if kind == "state":
        return ("alarm" if text in (cfg.get("alarm_states") or []) else "ok"), None
    if value is None:
        return cur, since
    base = cur if cur in LEVELS else "ok"
    h = cfg.get("hysteresis") or 0.0
    target = "ok"
    if _breach(cfg, "warn", value, RANK[base] >= RANK["warn"], h):
        target = "warn"
    if _breach(cfg, "alarm", value, RANK[base] >= RANK["alarm"], h):
        target = "alarm"
    if RANK[target] <= RANK[base]:
        return target, None
    # перехід угору: утримання min_duration_s
    min_d = 0 if ignore_min_duration else (cfg.get("min_duration_s") or 0)
    if min_d <= 0:
        return target, None
    if since is None:
        since = ts
    if (ts - since).total_seconds() >= min_d:
        return target, None
    return base, since


def breach_info(cfg, value):
    """Поріг, що спрацював для `value`, і напрям: `(threshold, rel)`; rel — «від» (нижній) або «до» (верхній)."""
    h = cfg.get("hysteresis") or 0.0
    if value is None:
        return None, ""
    for level in ("alarm", "warn"):
        if cfg.get(level + "_low_on") and value < (cfg.get(level + "_low") or 0.0):
            return cfg.get(level + "_low"), "від"
        if cfg.get(level + "_high_on") and value > (cfg.get(level + "_high") or 0.0):
            return cfg.get(level + "_high"), "до"
    # утримання за гістерезисом
    for level in ("alarm", "warn"):
        if cfg.get(level + "_low_on") and value < (cfg.get(level + "_low") or 0.0) + h:
            return cfg.get(level + "_low"), "від"
        if cfg.get(level + "_high_on") and value > (cfg.get(level + "_high") or 0.0) - h:
            return cfg.get(level + "_high"), "до"
    return None, ""
