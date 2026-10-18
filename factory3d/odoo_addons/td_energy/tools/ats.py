"""R-14: АВР, відключення, острів. Чисті функції без ORM."""

MODE_MASTER = {"remote": "hgm", "auto": "ats"}
MODE_LABEL = {
    "manual": "Ручний",
    "locked": "Заблокований",
    "auto": "Авто",
    "remote": "Remote control",
    "inhibit": "Заборонений",
}
POS_GRID, POS_GEN = 2, 3  # position: pos_I (мережа), pos_II (генератор) — last_value


def is_fresh(status, age_s, period_s, factor=3.0):
    """Свіжість сигналу АВР: `status ≠ stale` і вік ≤ factor × period_s (3 × 5 = 15 с)."""
    if age_s is None or status == "stale":
        return False
    return age_s <= factor * (period_s or 0)


def amf_master(mode):
    """Режим АВР → ведучий пристрій пуску генератора (п. 4)."""
    return MODE_MASTER.get(mode, "unknown")


def mode_label(mode):
    return MODE_LABEL.get(mode, "невідомо")


def grid_state(src1, position, incomers):
    """П. 2: (grid_ok, source). `src1` — текст, `position` — число; обидва лише свіжі (інакше None).
    `incomers` — [(P, I), …] обох вводів зі свіжих показань (None — немає)."""
    if src1 is not None:
        return src1 == "available", "ats"
    if position is not None:
        return position == POS_GRID, "ats"
    if incomers and all(p is not None and i is not None for p, i in incomers):
        if all(abs(p) < 1.0 and i < 1.0 for p, i in incomers):
            return False, "incomers"
    return True, "incomers"


def fail_start_due(mode, gen_start_age_s, src2_text, limit_s):
    """П. 5 (варіант B, лише mode='auto'): генератор не запустився довше за `limit_s`."""
    return mode == "auto" and gen_start_age_s is not None and gen_start_age_s >= limit_s and src2_text != "available"


def shed(load_before, load_island, current=0.0):
    """П. 8: max(shed, load_before − load_island)."""
    return max(current or 0.0, (load_before or 0.0) - (load_island or 0.0))
