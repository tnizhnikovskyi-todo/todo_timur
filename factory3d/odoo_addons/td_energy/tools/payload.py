"""R-16, R-17, R-18: розділи `energy` і `infra` payload переглядача (A.12, A.13). Працює з ORM через `env`;
`factory3d_viewer` не потрібен (провайдери викликаються лише ним)."""

import math

from . import dates, live

COST_GROUP = "factory3d_energy.group_f3d_energy_cost"
ENERGY_PREFIXES = ("energy/", "infra/pv/", "infra/bess/", "infra/chp/", "infra/ats/", "infra/totals/")
BAD_STATUS = ("stale", "unknown")
SQRT3_U = math.sqrt(3) * 380.0  # AC-64: 12,18 кВт / 0,84 → 22 А (макет рахує за 380 В)

SOURCE = (
    "Лічильники PowerLogic PM5560 на вводах, фідерах і споживачах → Modbus TCP → колектор → Odoo (factory3d_energy)"
)
NOTE_ADD = "Енергія на МО — за лічильниками; «оцінка» — за паспортом і журналом часу."
COUPLER_NOTE = (
    "Розімкнений: секції живляться кожна від свого трансформатора. "
    "АВР замкне його, якщо зникне напруга на одному з вводів."
)
PV_OK = ("on_grid", "limited")
PV_TEXT = {
    "standby": "очікування",
    "starting": "пуск",
    "fault": "аварія",
    "stopped": "зупинено",
    "no_grid": "немає мережі",
    "no_sun": "немає сонця",
}
ATS_POS = {"pos_I": "Мережа (T1/T2)", "pos_II": "Генератор", "pos_0": "0 — обидва джерела вимкнені"}
ATS_MODE = {
    "auto": "Авто",
    "remote": "Дистанційне (HGM6120N)",
    "manual": "Ручний",
    "locked": "Блоковано",
    "inhibit": "Заборонено",
}
BREAKER = {"closed": "on", "open": "off", "tripped": "tripped"}
MACHINE = {"working": "work", "setup": "work", "fault": "stop"}


# --- спільні дрібниці -----------------------------------------------------------------------------------------
def deep_merge(dst, src):
    """Рекурсивне злиття словників (списки й скаляри — заміна). Копія `factory3d_viewer.tools.payload.deep_merge`
    на випадок, коли переглядач не встановлено (X-23)."""
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            deep_merge(dst[key], value)
        else:
            dst[key] = value
    return dst


def merge_into(dst, src):
    try:
        from odoo.addons.factory3d_viewer.tools.payload import deep_merge as viewer_merge  # noqa: PLC0415
    except ImportError:
        viewer_merge = deep_merge
    viewer_merge(dst, src)
    return dst


def fmt(value, digits=1):
    """Число для рядків карток: пробіл тисяч, кома десяткова, без зайвого «,0»."""
    value = round(value, digits)
    if digits == 0 or value == int(value):
        text = "{:,}".format(int(value))
    else:
        text = "{:,.{d}f}".format(value, d=digits)
    return text.replace(",", " ").replace(".", ",")


def fmt_duration(minutes):
    total = int(round(minutes))
    hours, mins = divmod(total, 60)
    if hours and mins:
        return "%d год %d хв" % (hours, mins)
    return "%d год" % hours if hours else "%d хв" % mins


def _r(p):
    """Округлення телеметрії R-12: 2 знаки при < 20, інакше 1."""
    return round(p, 2) if abs(p) < 20 else round(p, 1)


def _now(env, ctx):
    return env.context.get("f3d_now") or (ctx or {}).get("now") or dates.now_utc(env)


def _show_cost(env, ctx):
    ctx = ctx or {}
    if ctx.get("kiosk") or not ctx.get("energy_cost", True):
        return False
    return env.user.has_group(COST_GROUP)


def _fresh(env):
    return env["f3d.energy.node"]._f3d_fresh_values()


def _val(fresh, code):
    item = fresh.get(code)
    return item[0] if item else None


def _txt(fresh, code):
    item = fresh.get(code)
    return item[1] if item else None


def wants_delta(changes, with_mrp):
    """R-18 п. 2–3: чи зачіпають зміни шини розділи `energy`/`infra`."""
    changes = changes or {}
    if "f3d.energy" in changes:
        return True
    if any(str(c).startswith(ENERGY_PREFIXES) for c in changes.get("f3d.signal", ())):
        return True
    return with_mrp and any(m in changes for m in ("mrp.production", "mrp.workorder"))


# --- energy ---------------------------------------------------------------------------------------------------
def _line_of(node, nodes):
    """Лінія-предок споживача (або None)."""
    cur, hops = node.parent_id, 0
    while cur and hops < 6:
        if cur.kind == "line":
            return cur
        cur, hops = cur.parent_id, hops + 1
    return None


def _machine_states(env):
    rows = (
        env["f3d.signal"]
        .sudo()
        .search_read(
            [("code", "=like", "workcenters/%/machine_state")],
            ["code", "last_text", "last_ts", "status", "last_quality"],
        )
    )
    return {
        r["code"].split("/")[1]: r["last_text"]
        for r in rows
        if r["last_ts"] and r["status"] not in BAD_STATUS and r["last_quality"] != "bad"
    }


def _consumer_status(node, p_now, machine, busy, wc):
    """`wc` — РЦ вузла або порожній набір (немає доступу до `mrp.workcenter`: статус лише за потужністю)."""
    if wc:
        code = wc.f3d_code or wc.code
        if code in machine:
            return MACHINE.get(machine[code], "idle")
        if wc.working_state == "blocked":
            return "stop"
        return "work" if wc.id in busy else "idle"
    if p_now is None:
        return None
    return "work" if p_now >= 0.05 * (node.p_inst_kw or 0.0) else "idle"


def build_energy(env, ctx, payload):
    """R-16: пише `payload["energy"]`, `workcenters[*].energy`, поля енергії в `productions`."""
    Node = env["f3d.energy.node"]
    if not Node.has_access("read"):
        return payload
    now = _now(env, ctx)
    show_cost = _show_cost(env, ctx)
    fresh = _fresh(env)
    snap = Node._f3d_live_snapshot(fresh)
    totals_live = snap["totals"]
    live_ok = bool(totals_live["lines"]) and snap["stale_feeders"] <= 2 and snap["stale_incomers"] < 2
    nodes = Node.search([])
    by_kind = {}
    for n in nodes:
        by_kind.setdefault(n.kind, []).append(n)
    energy = payload.setdefault("energy", {})

    # meta
    tariff = env["f3d.energy.tariff"].sudo()._f3d_tariff_at(now)
    _zone, price = env["f3d.energy.tariff"].sudo()._f3d_price_at(now)
    meta = energy.setdefault("meta", {})
    meta["source"] = SOURCE
    meta["u_kv"] = "10 / 0,4"
    if price:
        meta["tariff_uah"] = price
    note = meta.get("note") or ""
    if NOTE_ADD not in note:
        meta["note"] = (note + " " + NOTE_ADD).strip()

    # totals
    totals = energy.setdefault("totals", {})
    consumers_nodes = by_kind.get("consumer", [])
    totals["p_inst"] = int(round(sum(n.p_inst_kw for n in consumers_nodes)))
    totals["capacity_kva"] = int(sum(n.rating_kva for n in by_kind.get("transformer", [])))
    if tariff and tariff.contract_kw:
        totals["contract_kw"] = tariff.contract_kw
    if live_ok:
        totals["p_now"] = int(round(totals_live["p_now"]))
        totals["s_now"] = int(round(totals_live["s_now"]))
        totals["cos_before"] = round(totals_live["cos_before"], 2)
        totals["cos_after"] = round(totals_live["cos_after"], 2)
        totals["grid_kw"] = round(snap["grid_kw"], 1)
        totals["export_kw"] = round(snap["export_kw"], 1)
    if snap["pv_now"] or any(c.startswith("infra/pv/") for c in fresh):
        totals["pv_kw"] = round(snap["pv_now"], 1)
        totals["pv_today"] = int(round(snap["pv_today"]))
    if snap["chp_kw"] is not None:
        totals["chp_kw"] = round(snap["chp_kw"], 1)
    if snap["bess_kw"] is not None:
        totals["bess_kw"] = round(snap["bess_kw"], 1)
    day = env["f3d.energy.interval"]._f3d_day_profile(now) if env["f3d.energy.interval"].has_access("read") else None
    if day:
        totals["kwh_today"] = day["kwh_today"]
        totals["peak_kw"] = day["peak_kw"]
        if day["peak_time"]:
            totals["peak_time"] = day["peak_time"]
        if show_cost:
            totals["cost_today"] = day["cost_today"]
        energy["profile"] = day["profile"]
        if day["typical"] is not None:
            energy["typical"] = day["typical"]
    if not show_cost:
        totals.pop("cost_today", None)

    lines_live = totals_live["lines"] if live_ok else {}
    sections = totals_live["sections"] if live_ok else {}

    # transformers
    transformers = energy.setdefault("transformers", {})
    for tr in by_kind.get("transformer", []):
        incomer = tr.child_ids.filtered(lambda c: c.kind == "cell" and c.cell_type == "incomer")[:1]
        item = transformers.setdefault(tr.code, {})
        item.update({"name": tr.name, "rating_kva": tr.rating_kva, "section": incomer.section or 0})
        if incomer:
            item["incomer"] = incomer.code
        base = "energy/transformers/%s/" % tr.code
        p_kw, s_kva = _val(fresh, base + "p_kw"), _val(fresh, base + "s_kva")
        sec = sections.get(incomer.section) if incomer else None
        if s_kva is None and sec:
            s_kva = sec["s"]
        for key, v, digits in (("p_kw", p_kw, 1), ("temp_c", _val(fresh, base + "temp_c"), 1)):
            if v is not None:
                item[key] = round(v, digits)
        if s_kva is not None:
            item["s_kva"] = int(round(s_kva))
            if tr.rating_kva:
                item["load"] = round(s_kva / tr.rating_kva, 3)
        if _val(fresh, base + "i_a") is not None:
            item["i_a"] = int(round(_val(fresh, base + "i_a")))
        cos = live.pf_to_cos(_val(fresh, base + "cos_phi"))
        if cos is not None:
            item["cos_phi"] = round(cos, 2)

    # lines + consumers
    line_nodes = by_kind.get("line", [])
    line_consumers = {ln.code: [] for ln in line_nodes}
    consumer_line = {}
    for n in consumers_nodes:
        ln = _line_of(n, nodes)
        consumer_line[n.code] = ln
        if ln:
            line_consumers[ln.code].append(n)
    lines = energy.setdefault("lines", {})
    for ln in line_nodes:
        item = lines.setdefault(ln.code, {})
        members = line_consumers[ln.code]
        item.update(
            {
                "kind": ln.line_kind or "busway",
                "name": ln.name,
                "cell": ln.parent_id.code,
                "rating_a": ln.rating_a,
                "consumers": [m.code for m in members],
                "p_inst": round(sum(m.p_inst_kw for m in members), 2),
            }
        )
        vals = lines_live.get(ln.code)
        if vals:
            item["p_now"] = round(vals["p"], 1)
            item["cos_phi"] = round(vals["cos"], 2)
            if vals["i"] is not None:
                item["i_now"] = int(round(vals["i"]))
            if vals["load"] is not None:
                item["load"] = round(vals["load"], 3)

    machine = _machine_states(env)
    busy = set()
    can_wc = env["mrp.workcenter"].has_access("read")
    if can_wc and env["mrp.workorder"].has_access("read"):
        busy = set(env["mrp.workorder"].sudo().search([("state", "=", "progress")]).workcenter_id.ids)
    consumers = energy.setdefault("consumers", {})
    wc_energy = {}
    for n in consumers_nodes:
        ln = consumer_line[n.code]
        item = consumers.setdefault(n.code, {})
        item.update(
            {
                "name": n.name,
                "feeder": ln.parent_id.code if ln else None,
                "bus": ln.code if ln and ln.line_kind == "busway" else None,
                "p_inst": round(n.p_inst_kw, 2),
                "cos_phi": n.cos_phi_nominal,
                "line": ln.code if ln else None,
            }
        )
        if n.p_inst_source:
            item["source"] = n.p_inst_source
        if n.note:
            item["note"] = n.note
        if n.group:
            item["group"] = n.group
        p_now = _val(fresh, "energy/consumers/%s/p_now" % n.code)
        if p_now is not None:
            item["p_now"] = _r(p_now)
            item["i_now"] = int(round(p_now * 1000.0 / (SQRT3_U * (n.cos_phi_nominal or 0.9))))
        wc = n.workcenter_id if can_wc else n.workcenter_id.browse()
        status = _consumer_status(n, p_now, machine, busy, wc)
        if status:
            item["status"] = status
        shift = _val(fresh, "energy/consumers/%s/kwh_shift" % n.code)
        if shift is not None:
            item["kwh_shift"] = round(shift, 2)
        if wc and p_now is not None:
            wc_energy[wc.f3d_code or wc.code] = {
                "p_now": _r(p_now),
                "line": ln.code if ln else None,
            }

    # cells
    cells = energy.setdefault("cells", {})
    for cell in by_kind.get("cell", []):
        item = cells.setdefault(cell.code, {})
        ctype = cell.cell_type
        child_line = cell.child_ids.filtered(lambda c: c.kind == "line")[:1]
        item.update({"name": cell.name, "type": ctype, "section": cell.section or None, "feeds": None})
        if ctype == "incomer":
            item["feeds"] = cell.parent_id.code
            base = "energy/cells/%s/" % cell.code
            item["rating_a"] = cell.rating_a
            item["state"] = BREAKER.get(_txt(fresh, base + "state"), "on")
            if _val(fresh, base + "i_now") is not None:
                item["i_now"] = int(round(_val(fresh, base + "i_now")))
            if _val(fresh, base + "p_now") is not None:
                item["p_now"] = round(_val(fresh, base + "p_now"), 1)
        elif ctype == "coupler":
            item.update({"section": None, "rating_a": cell.rating_a, "state": "off", "note": COUPLER_NOTE})
        elif ctype == "pfc":
            sec = sections.get(cell.section)
            item.update({"rating_kvar": cell.rating_kvar, "steps": "50 + 3 × 100 квар"})
            item["q_now"] = sec["pfc_q_now"] if sec else cell.pfc_q_now
            if sec:
                item["cos_before"] = round(sec["cos_before"], 2)
                item["cos_after"] = round(sec["cos_after"], 2)
        else:
            item["rating_a"] = cell.rating_a
            if child_line:
                code = child_line.code
                item["feeds"] = item["line"] = code
                item["state"] = BREAKER.get(_txt(fresh, "energy/lines/%s/state" % code), "on")
                vals = lines_live.get(code)
                if vals:
                    item["p_now"] = round(vals["p"], 1)
                    if vals["i"] is not None:
                        item["i_now"] = int(round(vals["i"]))

    # events
    if env["f3d.energy.event"].has_access("read"):
        rows = env["f3d.energy.event"].search_read(
            [], ["ts", "level", "code", "text"], order="ts desc, id desc", limit=6
        )
        energy["events"] = [
            {
                "time": dates.to_local(r["ts"]).strftime("%Y-%m-%d %H:%M"),
                "level": r["level"],
                "code": r["code"] or "",
                "text": r["text"],
            }
            for r in rows
        ]

    # workcenters, productions
    workcenters = payload.get("workcenters")
    if isinstance(workcenters, dict):
        for code, entry in wc_energy.items():
            if isinstance(workcenters.get(code), dict):
                workcenters[code]["energy"] = entry
    fill_productions(env, ctx, payload.get("productions"))
    return payload


def fill_productions(env, ctx, productions):
    """R-16 п. 8: `energy_kwh/energy_cost/energy_quality` за назвою МО (без доступу до МО — не чіпає)."""
    if not isinstance(productions, list):
        return
    show_cost = _show_cost(env, ctx)
    if not show_cost:
        for item in productions:
            if isinstance(item, dict):
                item.pop("energy_cost", None)
    names = [p["name"] for p in productions if isinstance(p, dict) and p.get("name")]
    Production = env["mrp.production"]
    if not names or not Production.has_access("read"):
        return
    fields_ = ["name", "f3d_energy_kwh", "f3d_energy_state"] + (["f3d_energy_cost"] if show_cost else [])
    rows = {r["name"]: r for r in Production.search_read([("name", "in", names)], fields_)}
    for item in productions:
        row = rows.get(item.get("name")) if isinstance(item, dict) else None
        if not row:
            continue
        item["energy_kwh"] = round(row["f3d_energy_kwh"], 1)
        item["energy_quality"] = row["f3d_energy_state"]
        if show_cost:
            item["energy_cost"] = int(round(row["f3d_energy_cost"]))


# --- infra ----------------------------------------------------------------------------------------------------
def _node_num(env, code, key, default):
    node = env["f3d.energy.node"].search([("code", "=", code)], limit=1)
    if node and node.equipment_id:
        val = node.equipment_id.sudo().f3d_get_num(key)
        if val:
            return val
    return default


def _open_outage(env):
    Outage = env["f3d.energy.outage"]
    if not Outage.has_access("read"):
        return Outage.browse(), Outage.browse()
    last = Outage.search([], order="ts_start desc", limit=1)
    return last.filtered(lambda o: o.state == "open"), last


def build_infra(env, ctx, payload):
    """R-17: оновлює п'ять карток і ключі CE-03 `infra.totals`; решта `infra` не чіпається."""
    Node = env["f3d.energy.node"]
    if not Node.has_access("read"):
        return payload
    now = _now(env, ctx)
    fresh = _fresh(env)
    snap = Node._f3d_live_snapshot(fresh)
    infra = payload.setdefault("infra", {})
    cards = infra.setdefault("cards", {})
    totals = infra.setdefault("totals", {})
    ok_live = bool(snap["totals"]["lines"])
    load_kw = snap["totals"]["p_now"] if ok_live else None
    pv_now, pv_today = snap["pv_now"], snap["pv_today"]
    has_pv = any(c.startswith("infra/pv/") for c in fresh)
    chp_kw, bess_kw, soc = snap["chp_kw"], snap["bess_kw"], snap["bess_soc"]
    critical = snap["critical_kw"]
    outage, last_outage = _open_outage(env)

    pv_roof = Node.search([("code", "=", "PV-ROOF")], limit=1)
    chp_node = Node.search([("code", "=", "CHP")], limit=1)
    pv_kwp = pv_roof.p_inst_kw or 900.0
    wp = _node_num(env, "PV-ROOF", "wp", 580.0)
    n_modules = int(round(pv_kwp * 1000.0 / wp))
    chp_rated = chp_node.p_inst_kw or 800.0
    bess_kwh = 2 * _node_num(env, "BESS", "kwh", 193.5)
    peak_shave = dates.param_float(env, "peak_shave_kw", 600.0)

    # totals (CE-03)
    totals.update(
        {"pv_kwp": int(pv_kwp), "n_modules": n_modules, "chp_rated": int(chp_rated), "bess_kwh": int(bess_kwh)}
    )
    if has_pv:
        totals["pv_now"] = round(pv_now, 1)
        totals["pv_today"] = int(round(pv_today))
    if ok_live:
        totals["grid_kw"] = round(snap["grid_kw"], 1)
        totals["export_kw"] = round(snap["export_kw"], 1)
        totals["load_kw"] = int(round(load_kw))
    if chp_kw is not None:
        totals["chp_kw"] = round(chp_kw, 1)
        totals["chp_load"] = round(chp_kw / chp_rated, 3)
    heat = _val(fresh, "infra/chp/heat_kw")
    if heat is not None:
        totals["chp_heat"] = int(round(heat))
    if bess_kw is not None:
        totals["bess_kw"] = round(bess_kw, 1)
        totals["bess_mode"] = snap["bess_mode"]
    if soc is not None:
        totals["bess_soc"] = round(soc / 100.0, 3)
    totals["critical_kw"] = int(round(critical))
    if ok_live:
        before = outage.load_before_kw if outage else 0.0
        totals["shed_kw"] = int(round(max(0.0, before - load_kw))) if outage else 0

    # PV-ROOF, PV-INV
    if has_pv:
        share = round(pv_now / load_kw * 100) if load_kw else 0
        card = cards.setdefault("PV-ROOF", {})
        card["rows"] = [
            ["Модулів", "%s × %d Вт" % (fmt(n_modules, 0), wp)],
            ["Потужність", "%s кВт пік" % fmt(pv_kwp, 0)],
            ["Зараз", "%s кВт" % fmt(pv_now)],
            ["Сьогодні", "%s кВт·год" % fmt(pv_today, 0)],
            ["Частка СЕС зараз", "%d %% споживання" % share],
        ]
        statuses = {}
        for k in range(1, 9):
            text = _txt(fresh, "infra/pv/PV-INV-%d/status" % k)
            if text is not None:
                statuses["PV-INV-%d" % k] = text
        card = cards.setdefault("PV-INV", {})
        rows = [["Інверторів", "8 × 115 кВт"], ["Навантаження", "%d %%" % round(pv_now / 920.0 * 100)]]
        if statuses:
            bad = {c: s for c, s in statuses.items() if s not in PV_OK}
            if len(statuses) == 8 and not bad:
                rows.append(["Стан", "усі в мережі"])
            else:
                text = "в мережі %d з 8" % (len(statuses) - len(bad))
                if bad:
                    text += "; " + ", ".join("%s: %s" % (c, PV_TEXT.get(s, s)) for c, s in sorted(bad.items()))
                rows.append(["Стан", text])
        card["rows"] = rows
        if any(s == "fault" for s in statuses.values()):
            card["warn"] = "Аварія інвертора"
        else:
            card.pop("warn", None)

    # CHP
    if chp_kw is not None:
        state = _txt(fresh, "infra/chp/state")
        rows = [
            ["Потужність", "%s кВт ел. · 856 кВт тепла" % fmt(chp_rated, 0)],
            [
                "Зараз",
                "%s кВт ел. · %s кВт тепла (%d %%)" % (fmt(chp_kw), fmt(heat or 0.0), round(chp_kw / chp_rated * 100)),
            ],
        ]
        need = ((payload.get("ventilation") or {}).get("totals") or {}).get("heat_kw")
        if need is not None and heat is not None:
            rows.append(
                [
                    "Тепло",
                    "мережі потрібно %s кВт, надлишок %s кВт — у сухий охолоджувач"
                    % (fmt(need, 0), fmt(max(0.0, heat - need), 0)),
                ]
            )
        gas = _val(fresh, "infra/chp/gas_m3h")
        if gas is not None:
            rows.append(["Газ", "%s м³/год (при 100 %% — 199)" % fmt(gas)])
        rows.append(["ККД", "42,5 % ел. + 45,5 % тепл."])
        hours = _val(fresh, "infra/chp/hours")
        if hours is not None:
            rows.append(["Мотогодини", "%s · до капремонту 80 000" % fmt(hours, 0)])
        card = cards.setdefault("CHP", {})
        card["rows"] = rows
        if state == "fault":
            card["warn"] = "Аварія КГУ"
        else:
            card.pop("warn", None)

    # ATS-1
    position, mode = _txt(fresh, "infra/ats/position"), _txt(fresh, "infra/ats/mode")
    if position is not None or mode is not None:
        card = cards.setdefault("ATS-1", {})
        transfer = last_outage.transfer_s if last_outage and last_outage.transfer_s else 0
        rows = [
            ["Положення", ATS_POS.get(position, "невідомо")],
            ["Режим", ATS_MODE.get(mode, "невідомо")],
            ["Номінал", "1600 А"],
            [
                "Переключення",
                "%s с при останньому відключенні" % fmt(transfer, 0) if transfer else "після пуску генератора, 10–15 с",
            ],
        ]
        if last_outage:
            end = last_outage.ts_end or now
            minutes = (
                last_outage.duration_min if last_outage.ts_end else (end - last_outage.ts_start).total_seconds() / 60.0
            )
            rows.append(
                [
                    "Останнє спрацювання",
                    "%s — відключення мережі %s"
                    % (dates.to_local(last_outage.ts_start).strftime("%d.%m, %H:%M"), fmt_duration(minutes)),
                ]
            )
        else:
            rows.append(["Останнє спрацювання", "05.10, 18:42 — відключення мережі 2 год 11 хв"])
        card["rows"] = rows
        if last_outage and last_outage.fail_start:
            card["warn"] = "FAIL START: генератор не запустився"
        else:
            card.pop("warn", None)

    # BESS
    if bess_kw is not None or soc is not None:
        card = cards.setdefault("BESS", {})
        rows = [["Ємність", "%s кВт·год (2 шафи)" % fmt(bess_kwh, 0)], ["Потужність", "200 кВт"]]
        if soc is not None:
            rows.append(["Заряд", "%s %% · %s кВт·год" % (fmt(soc), fmt(bess_kwh * soc / 100.0))])
        mode_now = snap["bess_mode"]
        if mode_now == "charge":
            now_txt = "заряджається %s кВт (надлишок СЕС і КГУ)" % fmt(abs(bess_kw), 0)
        elif mode_now == "discharge":
            now_txt = "віддає %s кВт" % fmt(abs(bess_kw), 0)
        else:
            now_txt = "очікування"
        rows.append(["Зараз", now_txt])
        rows.append(["Режим", "зрізання піків понад %s кВт + резерв на пуск генератора" % fmt(peak_shave, 0)])
        if soc is not None and critical:
            rows.append(["Тримає критичні", "≈ %d хв" % round(bess_kwh * soc / 100.0 / critical * 60.0)])
        card["rows"] = rows
        if _txt(fresh, "infra/bess/state") == "fault":
            card["warn"] = "Аварія накопичувача"
        else:
            card.pop("warn", None)
    return payload
