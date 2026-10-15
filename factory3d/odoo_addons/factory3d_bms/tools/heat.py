"""R-14…R-16: тепловий баланс цеху (без ORM). `p` — dict полів `f3d.bms.heat.balance`."""


def _num(x, nd=2):
    """Число з комою й пробілами між тисячами: 3996 → «3 996», 0.35 → «0,35»."""
    s = ("%.*f" % (nd, x)).rstrip("0").rstrip(".") if nd else "%d" % round(x)
    sign = "-" if s.startswith("-") else ""
    s = s.lstrip("-")
    whole, _, frac = s.partition(".")
    whole = "{:,}".format(int(whole)).replace(",", " ")
    return sign + whole + ("," + frac if frac else "")


def design_balance(p, units):
    """R-14. `units` — список dict {kind, airflow_nom}. Повертає lines, total_raw, total_kw, capacity_kw, reserve,
    reserve_boilers, note."""
    L, W, H = p["length_m"], p["width_m"], p["height_m"]
    dt = p["t_in_set"] - p["t_out_design"]
    c = p["air_wh_m3k"]
    s_walls = 2 * (L + W) * H
    s_roof = s_floor = L * W
    q_trans = (s_walls * p["u_wall"] + s_roof * p["u_roof"] + s_floor * p["u_floor"]) * dt / 1000
    q_infil = L * W * H * p["infiltration_ach"] * c * dt / 1000
    air_rv = sum(u["airflow_nom"] or 0.0 for u in units if u["kind"] == "roofvent")
    air_ahu = sum(u["airflow_nom"] or 0.0 for u in units if u["kind"] == "ahu")
    oa, eta = p["winter_oa_share"], p["heat_recovery"]
    q_rv = air_rv * oa * c * dt * (1 - eta) / 1000
    dt_ahu = p["ahu_supply_c"] - p["t_out_design"]
    share_ahu = p["ahu_design_share"]
    q_ahu = air_ahu * share_ahu * c * dt_ahu / 1000
    lines = [
        {"sequence": 10, "key": "trans", "kw": q_trans,
         "name": "Тепловтрати через стіни, покрівлю й підлогу",
         "formula": "(%s·%s + %s·%s + %s·%s)·%s/1000" % (
             _num(s_walls, 0), _num(p["u_wall"], 3), _num(s_roof, 0), _num(p["u_roof"], 3),
             _num(s_floor, 0), _num(p["u_floor"], 3), _num(dt, 1))},
        {"sequence": 20, "key": "infil", "kw": q_infil,
         "name": "Інфільтрація крізь ворота (%s обміну/год)" % _num(p["infiltration_ach"], 3),
         "formula": "%s·%s·%s·%s/1000" % (
             _num(L * W * H, 0), _num(p["infiltration_ach"], 3), _num(c, 3), _num(dt, 1))},
        {"sequence": 30, "key": "vent_rv", "kw": q_rv,
         "name": "Дахові установки: %s %% зовнішнього повітря, рекуперація %s %%" % (
             _num(oa * 100, 0), _num(eta * 100, 0)),
         "formula": "%s·%s·%s·%s·(1 − %s)/1000" % (
             _num(air_rv, 0), _num(oa, 2), _num(c, 3), _num(dt, 1), _num(eta, 2))},
        {"sequence": 40, "key": "vent_ahu", "kw": q_ahu,
         "name": "Приплив дільниці фасадів (без рекуперації — витяжка з фарбування)",
         "formula": "%s·%s·%s·(%s − (%s))/1000" % (
             _num(air_ahu, 0), _num(share_ahu, 2), _num(c, 3), _num(p["ahu_supply_c"], 1),
             _num(p["t_out_design"], 1))},
    ]
    gains = p.get("internal_gains_kw") or 0.0
    if gains > 0:
        lines.append({"sequence": 50, "key": "internal", "kw": -gains,
                      "name": "Внутрішні теплонадходження (зменшують навантаження)",
                      "formula": "−%s" % _num(gains, 1)})
    total_raw = sum(line["kw"] for line in lines)
    for line in lines:
        line["kw_round"] = round(line["kw"])
    capacity = round(p["boilers"] * p["boiler_kw"])
    reserve = reserve_b = 0.0
    if total_raw > 0:
        reserve = round((capacity + p["chp_heat_kw"]) / total_raw - 1, 2)
        reserve_b = round(capacity / total_raw - 1, 2)
    gains_txt = ("внутрішні теплонадходження враховано: %s кВт" % _num(gains, 1) if gains > 0 else
                 "внутрішні теплонадходження від верстатів (сотні кВт у зміну) не враховано — це запас")
    note = "Оцінка, не проєкт: U стін %s, покрівлі %s, підлоги %s Вт/(м²·К); %s." % (
        _num(p["u_wall"], 3), _num(p["u_roof"], 3), _num(p["u_floor"], 3), gains_txt)
    return {"lines": lines, "total_raw": total_raw, "total_kw": round(total_raw), "capacity_kw": capacity,
            "reserve": reserve, "reserve_boilers": reserve_b, "note": note}


def chp_heat(el_kw, p, heat_signal=None):
    """R-15: (тепло КГУ, кВт; джерело 'signal'|'calc'|'design')."""
    if heat_signal is not None:
        return heat_signal, "signal"
    if el_kw is None:
        return p["chp_heat_50_kw"], "design"
    load = el_kw / p["chp_el_kw"] if p["chp_el_kw"] else 0.0
    h50, h75, hmax, minl = p["chp_heat_50_kw"], p["chp_heat_75_kw"], p["chp_heat_kw"], p["chp_min_load"]
    if load < 0.05:
        return 0, "calc"
    if load <= minl:
        return h50, "calc"
    if load <= 0.75:
        return h50 + (load - 0.5) / 0.25 * (h75 - h50), "calc"
    if load < 1.0:
        return h75 + (load - 0.75) / 0.25 * (hmax - h75), "calc"
    return hmax, "calc"


BOILER_STATE_COUNT = {"standby": 0, "K1": 1, "K1+K2": 2, "fault": 0}


def live_balance(need, chp, p, boiler_state=None):
    """R-16: dict boil, calc, boilers_on, boiler_state, load, available, deficit."""
    boil = max(0.0, need - chp)
    kw = p["boiler_kw"]
    if boil <= 1e-9:
        calc = 0
    elif boil <= round(p["boiler_stage_share"] * kw, 6) + 1e-9:
        calc = 1
    else:
        calc = 2
    calc = min(calc, p["boilers"])
    if boiler_state in BOILER_STATE_COUNT:
        on = BOILER_STATE_COUNT[boiler_state]
    else:
        on, boiler_state = calc, False
    available = chp + on * kw
    return {"boil": boil, "calc": calc, "boilers_on": on, "boiler_state": boiler_state,
            "load": round(boil / kw, 2) if kw else 0.0, "available": available,
            "deficit": round(max(0.0, need - available), 1)}
