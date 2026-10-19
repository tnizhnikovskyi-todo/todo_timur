"""R-18, R-19: AbstractModel-обробники `report.td_energy_analytics.*` (W4-B).

* `report_management_document` — «Звіт для керівництва» (R-18): дані беруться з API-01/API-07 (`td.energy.analytics`),
  суми ₴ й блок бюджету — лише з групою вартості (їх прибирає сам API);
* `report_shift_document` — «Звіт за зміну» (R-19): енергія, пік, події, відключення, обходи (якщо встановлено
  `td_energy_mobile`), три найбільші резерви; `_td_pick_shift(date, name)` обирає зміну.

Геометрію SVG (стовпці, лінії EnPI) рахує Python: шаблони QWeb лише розкладають готові значення; без CSS-змінних, grid
і зовнішніх ресурсів — під `wkhtmltopdf`.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy_resources.tools import shifts as shift_tools

from ..tools import periods
from ..tools.fmt import fmt_dec, fmt_int, fmt_signed, spec_text

_logger = logging.getLogger(__name__)

COST = "td_energy.group_td_energy_cost"
DASH = "—"
OTHER_KEY = "OTHER"
LEVELS = {"info": "Інформація", "warn": "Увага", "bad": "Аварія"}
PART_NAMES = {
    "kpis": "Підсумки періоду", "stack": "Енергія за ділянками", "enpi": "EnPI проти бази", "budget": "Бюджет",
    "cut": "Енергія за ділянками", "opps": "Резерви економії",
}  # fmt: skip
PARTS = ("kpis", "stack", "enpi", "budget", "cut", "opps")
# геометрія SVG: стовпці (viewBox 880 × 250) і лінії EnPI (viewBox 440 × 200): left, right, top, bottom
STACK_BOX = (56.0, 870.0, 24.0, 234.0)
ENPI_BOX = (40.0, 430.0, 24.0, 174.0)


# --- спільні помічники -----------------------------------------------------------------------------------
def _error(part):
    """Текст помилки частини API-01 (`{"error": …}`) або `None`."""
    return part["error"] if isinstance(part, dict) and set(part) == {"error"} else None


def _part(part):
    """Частина відповіді API-01 або `None` (немає / `{"error": …}`)."""
    return None if part is None or _error(part) is not None else part


def _num(value, digits=1):
    """Ціле — з пробілом між розрядами, інакше `digits` знаків; `None` → «—»."""
    if value is None:
        return DASH
    return fmt_int(value) if float(value).is_integer() else fmt_dec(value, digits)


def _delta(value):
    """Відхилення в %: «+2 %», «−6 %»; `None` → «—»."""
    return DASH if value is None else "%s %%" % fmt_signed(value)


def _day(day):
    return day.strftime("%d.%m.%Y")


def _hm(utc_dt):
    return dates.to_local(utc_dt).strftime("%H:%M")


def _path(points):
    """Ламана `M x y L x y …`; `y=None` розриває лінію (немає даних)."""
    parts, pen = [], False
    for x, y in points:
        if y is None:
            pen = False
            continue
        parts.append("%s%.1f %.1f" % ("L" if pen else "M", x, y))
        pen = True
    return " ".join(parts)


def _cost_access(env):
    return env.is_superuser() or env.user.has_group(COST)


def _selection(env, model, field):
    return dict(env[model]._fields[field]._description_selection(env))


# --- геометрія графіків ------------------------------------------------------------------------------------
def _stack_chart(stack):
    """Стовпці за ділянками (UI-03): `{rects, labels, ticks, legend}`; без стовпців — `None`."""
    bars = stack.get("bars") or []
    if not bars:
        return None
    left, right, top, bottom = STACK_BOX
    y_max = float(stack.get("y_max") or 1)
    colors = {a["code"]: a["color"] for a in stack.get("areas", [])}
    slot = (right - left) / len(bars)
    width = slot * 0.7
    rects, labels = [], []
    for i, bar in enumerate(bars):
        x = left + slot * i + (slot - width) / 2
        y = bottom
        for code, color in colors.items():
            height = (bar["values"].get(code) or 0) / y_max * (bottom - top)
            if height <= 0:
                continue
            y -= height
            rects.append(
                {"x": round(x, 1), "y": round(y, 1), "w": round(width, 1), "h": round(height, 1), "fill": color}
            )
        if bar.get("label"):
            labels.append({"x": round(x + width / 2, 1), "text": bar["label"]})
    marks = [0, *(stack.get("ticks") or [])]
    ticks = [
        {"y": round(bottom - (bottom - top) * k / max(1, len(marks) - 1), 1), "text": fmt_int(v)}
        for k, v in enumerate(marks)
    ]
    return {"rects": rects, "labels": labels, "ticks": ticks, "legend": list(stack.get("areas") or [])}


def _enpi_chart(enpi):
    """Дві лінії 12 тижнів (UI-05): факт — суцільна, очікування — пунктир; без жодної точки — `None`."""
    weeks = enpi.get("weeks") or []
    if not weeks or all(w["actual_mwh"] is None and w["expected_mwh"] is None for w in weeks):
        return None
    left, right, top, bottom = ENPI_BOX
    low, high = float(enpi["y_min"]), float(enpi["y_max"])
    span = (high - low) or 1.0
    step = (right - left) / max(1, len(weeks) - 1)

    def points(key):
        return [
            (left + step * i, None if w[key] is None else bottom - (w[key] - low) / span * (bottom - top))
            for i, w in enumerate(weeks)
        ]

    ticks = [{"y": round(bottom - (bottom - top) * k / 2, 1), "text": _num(low + span * k / 2)} for k in range(3)]
    return {"actual": _path(points("actual_mwh")), "expected": _path(points("expected_mwh")), "ticks": ticks}


def _model_text(env, base):
    """Параметри моделі бази: «1 820 кВт·год/добу + 4,1 × м² плит»; період бази; R²."""
    record = env["td.energy.baseline"].sudo().browse(base["id"]).exists()
    codes = [c["driver"] for c in base["coefs"]]
    drivers = {d.code: d for d in env["td.energy.driver"].sudo().search([("code", "in", codes)])}
    terms = ["%s × %s" % (_num(c["coef"], 3), drivers[c["driver"]].name if c["driver"] in drivers else c["driver"])
             for c in base["coefs"]]  # fmt: skip
    period = "%s – %s" % (_day(record.period_from), _day(record.period_to)) if record else base.get("label", DASH)
    return {
        "formula": " + ".join(["%s кВт·год/добу" % _num(base["const_per_day"]), *terms]),
        "r2": fmt_dec(base["r2"], 2) if base.get("r2") is not None else DASH,
        "period": period,
    }


# --- R-18: звіт для керівництва ------------------------------------------------------------------------------
class ReportManagement(models.AbstractModel):
    _name = "report.td_energy_analytics.report_management_document"
    _description = "Енергетика: дані звіту для керівництва"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["td.energy.report.wizard"].browse(docids).exists()
        return {
            "doc_ids": docs.ids,
            "doc_model": "td.energy.report.wizard",
            "docs": docs,
            "reports": {doc.id: self._td_management(doc.period or "m") for doc in docs},
        }

    @api.model
    def _td_management(self, period):
        """Значення шаблону `report_management_document` для періоду `period` (R-18)."""
        api_ = self.env["td.energy.analytics"]
        dash = api_.get_dashboard(period, "area", list(PARTS))
        eq_cut = api_.get_cut("eq", period)
        meta = dash["meta"]
        cost = bool(meta["capabilities"].get("cost"))
        notes = [
            _("Розділ «%(part)s» недоступний: %(error)s", part=PART_NAMES[key], error=_error(dash.get(key)))
            for key in PARTS
            if _error(dash.get(key)) is not None
        ]
        stack = _part(dash.get("stack"))
        period_text = "%s – %s · %s" % (
            _day(fields.Date.to_date(meta["date_from"])),
            _day(fields.Date.to_date(meta["date_to"])),
            meta["period_label"],
        )
        return {
            "cost": cost,
            "title": _("Звіт для керівництва · Енергетика"),
            "company": self.env.company.name,
            "period_text": period_text,
            "generated": dates.to_local(dates.now_utc(self.env)).strftime("%d.%m.%Y %H:%M"),
            "author": self.env.user.name,
            "subtitle": meta["subtitle"],
            "kpis": self._td_kpis(_part(dash.get("kpis"))),
            "enpi": self._td_enpi(meta, _part(dash.get("enpi"))),
            "budget": self._td_budget(_part(dash.get("budget"))) if cost else None,
            "stack": _stack_chart(stack or {}),
            "stack_unit": (stack or {}).get("unit", ""),
            "areas": self._td_areas(_part(dash.get("cut")), stack, cost),
            "equipment": self._td_equipment(eq_cut, cost),
            "opps": self._td_opps(_part(dash.get("opps")), cost),
            "notes": self._td_notes(meta, dash, cost, period, notes),
        }

    @api.model
    def _td_kpis(self, kpis):
        rows = []
        for kpi in kpis or []:
            value = kpi.get("value")
            if value is None:
                text = DASH
            elif kpi["id"] == "spec":
                text = fmt_dec(value, 2)
            else:
                text = _num(value)
            rows.append(
                {
                    "id": kpi["id"], "label": kpi["label"], "value": text, "unit": kpi.get("unit") or "",
                    "note": kpi.get("note") or DASH, "tone": kpi.get("tone") or "neutral",
                }
            )  # fmt: skip
        return rows

    @api.model
    def _td_enpi(self, meta, enpi):
        base = meta.get("baseline")
        out = {"base": bool(base), "chart": None, "summary": _("База не задана"), "model": None}
        if enpi:
            out["chart"] = _enpi_chart(enpi)
            if enpi.get("enpi") is not None:
                out["summary"] = _(
                    "EnPI %(enpi)s · економія %(saving)s %% до бази",
                    enpi=fmt_dec(enpi["enpi"], 2),
                    saving=_num(enpi["saving_pct"]),
                )
                if enpi.get("saving_uah") is not None:
                    out["summary"] += _(" · ≈ %s ₴", fmt_int(enpi["saving_uah"]))
        if base:
            out["model"] = _model_text(self.env, base)
        return out

    @api.model
    def _td_budget(self, budget):
        if not budget:
            return None
        return {
            "month": budget["month_label"], "plan": fmt_int(budget["plan_uah"]), "fact": fmt_int(budget["fact_uah"]),
            "forecast": fmt_int(budget["forecast_uah"]), "fact_pct": budget["fact_pct"],
            "share_pct": budget["month_share_pct"], "delta": _delta(budget.get("delta_pct")), "text": budget["text"],
            "bar": max(0, min(100, int(budget["fact_pct"] or 0))),
            "marker": max(0, min(100, int(budget["month_share_pct"] or 0))),
        }  # fmt: skip

    @api.model
    def _td_cut_rows(self, rows, cost, colors=None, limit=None):
        out = []
        for row in rows:
            if row["key"] == OTHER_KEY and limit is not None:
                continue
            out.append(
                {
                    "name": row["name"], "kwh": fmt_int(row["kwh"]),
                    "cost": fmt_int(row["cost_uah"]) if cost and row.get("cost_uah") is not None else DASH,
                    "share": "%s %%" % row["share_pct"], "spec": row.get("spec_text") or spec_text(row.get("spec")),
                    "delta": _delta(row.get("delta_pct")), "color": (colors or {}).get(row["key"]),
                }
            )  # fmt: skip
        return out[:limit] if limit else out

    @api.model
    def _td_areas(self, cut, stack, cost):
        if not cut:
            return None
        colors = {a["code"]: a["color"] for a in (stack or {}).get("areas", [])}
        total_cost = sum(r.get("cost_uah") or 0 for r in cut["rows"])
        return {
            "col_name": cut["col_name"], "col_spec": cut["col_spec"],
            "rows": self._td_cut_rows(cut["rows"], cost, colors),
            "total_kwh": fmt_int(sum(r["kwh"] for r in cut["rows"])), "total_cost": fmt_int(total_cost),
        }  # fmt: skip

    @api.model
    def _td_equipment(self, cut, cost):
        return {"col_spec": cut["col_spec"], "rows": self._td_cut_rows(cut["rows"], cost, limit=5)}

    @api.model
    def _td_opps(self, opps, cost):
        if not opps:
            return None

        def row(item):
            labels = [a["label"] for a in item.get("actions") or [] if a.get("enabled") is not False and a.get("label")]
            return {
                "title": item["title"], "text": item.get("text") or "",
                "save": fmt_int(item["save_uah_month"]) if cost and item.get("save_uah_month") is not None else DASH,
                "actions": ", ".join(labels) or DASH,
            }  # fmt: skip

        items = opps.get("items") or []
        return {
            "plan": [row(i) for i in items if i.get("in_plan")],
            "other": [row(i) for i in items if not i.get("in_plan")],
            "plan_sum": fmt_int(opps["plan_sum"]) if cost and "plan_sum" in opps else None,
            "all_sum": fmt_int(opps["all_sum"]) if cost and "all_sum" in opps else None,
            "count": len(items),
        }

    @api.model
    def _td_notes(self, meta, dash, cost, period, notes):
        quality = meta.get("data_quality") or {}
        if quality.get("partial_days"):
            notes.append(
                _("Неповні дані за %(partial)s діб із %(days)s.", partial=quality["partial_days"], days=quality["days"])
            )
        if not meta.get("baseline"):
            notes.append(_("Модель бази не задана або не затверджена: відхилення «до бази» не розраховано."))
        if cost and "budget" in dash and dash["budget"] is None:
            notes.append(_("Бюджет енергії на поточний місяць не затверджено."))
        stack = _part(dash.get("stack"))
        if stack is not None and not stack.get("bars"):
            notes.append(_("За період немає добових даних по вузлах: стовпці за ділянками порожні."))
        gap = self.env["td.energy.analytics"]._td_stack_gap_pct(period)
        if gap is not None and abs(gap) > 3:
            notes.append(
                _(
                    "Сума ділянок відрізняється від споживання заводу на %s %% (вузли без даних або без ділянки).",
                    fmt_dec(gap, 1),
                )
            )
        return notes


# --- R-19: звіт за зміну ---------------------------------------------------------------------------------------
class ReportShift(models.AbstractModel):
    _name = "report.td_energy_analytics.report_shift_document"
    _description = "Енергетика: дані звіту за зміну"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["td.energy.report.wizard"].browse(docids).exists()
        return {
            "doc_ids": docs.ids,
            "doc_model": "td.energy.report.wizard",
            "docs": docs,
            "reports": {doc.id: self._td_shift(doc.shift_date, doc.shift_name) for doc in docs},
        }

    # --- вибір зміни -----------------------------------------------------------------------------------------
    @api.model
    def _td_shift_info(self, name, day, start, full_end, now):
        """Вікно зміни: `end` — кінець зміни або «зараз» (поточна); `current` — зміна триває."""
        current = start <= now < full_end
        return {
            "name": name, "day": day, "start": start, "full_end": full_end, "current": current,
            "end": now if current else (start if now < start else full_end),
        }  # fmt: skip

    @api.model
    def _td_pick_shift(self, date=None, name=None):
        """R-19: зміна звіту. `name` — зміна цієї назви в `date`; інакше поточна (з початку до «зараз»), або остання
        завершена сьогодні, або — коли сьогодні завершених змін ще не було — найближча попередня доба зі зміною
        (до 7 діб назад)."""
        now = dates.now_utc(self.env)
        today = dates.to_local(now).date()
        windows = shift_tools.load_windows(self.env)
        if name:
            day = fields.Date.to_date(date) or today
            for wname, start, end in windows.windows_for(day):
                if wname == name:
                    return self._td_shift_info(wname, day, start, end, now)
            raise UserError(_("Зміни «%(name)s» немає на %(day)s.", name=name, day=_day(day)))
        for wname, start, end in windows.windows_for(today):
            if start <= now < end:
                return self._td_shift_info(wname, today, start, end, now)
        for back in range(8):
            day = today - timedelta(days=back)
            done = [w for w in windows.windows_for(day) if w[2] <= now]
            if done:
                wname, start, end = max(done, key=lambda w: w[2])
                return self._td_shift_info(wname, day, start, end, now)
        raise UserError(_("У календарі змін немає жодної завершеної зміни за останній тиждень."))

    # --- дані ----------------------------------------------------------------------------------------------
    @api.model
    def _td_feeder_kwh(self, start, end):
        self.env.cr.execute(
            """SELECT COALESCE(SUM(kwh), 0) FROM td_energy_interval
                WHERE role = 'feeder' AND ts_start >= %s AND ts_start < %s""",
            (start, end),
        )
        return float(self.env.cr.fetchone()[0])

    @api.model
    def _td_typical(self, info):
        """Середнє `Σ feeder kwh` останніх 4 змін тієї ж назви за той самий відрізок від початку (≤ 28 діб назад)."""
        windows = shift_tools.load_windows(self.env)
        elapsed = info["end"] - info["start"]
        sums = []
        for back in range(1, 29):
            for wname, start, end in windows.windows_for(info["day"] - timedelta(days=back)):
                if wname == info["name"]:
                    total = self._td_feeder_kwh(start, min(start + elapsed, end))
                    if total > 0:
                        sums.append(total)
            if len(sums) >= 4:
                break
        sums = sums[:4]
        return (sum(sums) / len(sums), len(sums)) if sums else (None, 0)

    @api.model
    def _td_shift(self, shift_date, shift_name):
        """Значення шаблону `report_shift_document` (R-19)."""
        self.env["td.energy.analytics"]._td_check_access()
        info = self._td_pick_shift(shift_date, shift_name)
        cost = _cost_access(self.env)
        start, end, full_end = info["start"], info["end"], info["full_end"]
        cr = self.env.cr
        self.env.flush_all()
        cr.execute(
            """SELECT COALESCE(SUM(kwh) FILTER (WHERE role = 'feeder'), 0),
                      COALESCE(SUM(kwh) FILTER (WHERE role = 'incomer'), 0),
                      COALESCE(SUM(cost) FILTER (WHERE role = 'feeder'), 0)
                 FROM td_energy_interval
                WHERE role IN ('feeder', 'incomer') AND ts_start >= %s AND ts_start < %s""",
            (start, end),
        )
        feeder, incomer, feeder_cost = (float(v) for v in cr.fetchone())
        cr.execute(
            """SELECT ts_start, SUM(kwh) AS k FROM td_energy_interval
                WHERE role = 'feeder' AND ts_start >= %s AND ts_start < %s
                GROUP BY ts_start ORDER BY k DESC, ts_start LIMIT 1""",
            (start, end),
        )
        peak = cr.fetchone()
        typical, typical_n = self._td_typical(info)
        deviation = (feeder / typical - 1) * 100 if typical and end > start else None
        events, event_rows = self._td_events(start, end)
        return {
            "cost": cost,
            "title": _("Звіт за зміну · Енергетика"),
            "company": self.env.company.name,
            "shift": info["name"],
            "day_text": "%s %s" % (periods.WEEKDAYS[info["day"].weekday()], _day(info["day"])),
            "interval": "%s–%s" % (_hm(start), _hm(full_end)),
            "status": _("триває, дані до %s", _hm(end)) if info["current"] else _("завершена"),
            "current": info["current"],
            "generated": dates.to_local(dates.now_utc(self.env)).strftime("%d.%m.%Y %H:%M"),
            "author": self.env.user.name,
            "feeder": fmt_int(feeder),
            "incomer": fmt_int(incomer),
            "peak": fmt_int(float(peak[1]) * 4) if peak else DASH,
            "peak_at": _hm(peak[0]) if peak else "",
            "cost_text": fmt_int(feeder_cost) if cost else None,
            "deviation": _delta(deviation),
            "deviation_value": deviation,
            "typical": fmt_int(typical) if typical else DASH,
            "typical_n": typical_n,
            "events": events,
            "event_rows": event_rows,
            "outages": self._td_outages(start, full_end),
            "rounds": self._td_rounds(start, full_end),
            "opps": self._td_top_opps(cost),
        }

    @api.model
    def _td_events(self, start, end):
        """Події вікна: лічильники за рівнями й п'ять останніх (час, рівень, назва, стан)."""
        Event = self.env["td.energy.event"].sudo()
        domain = [("ts", ">=", start), ("ts", "<", end)]
        counts = dict.fromkeys(LEVELS, 0)
        for level, count in Event._read_group(domain, ["level"], ["__count"]):
            counts[level] = count
        states = _selection(self.env, "td.energy.event", "state")
        rows = [
            {
                "time": _hm(ev.ts), "level": LEVELS.get(ev.level, ev.level or ""), "title": ev.title or ev.text,
                "state": states.get(ev.state, ev.state or ""),
            }
            for ev in Event.search(domain, order="ts desc, id desc", limit=5)
        ]  # fmt: skip
        return [{"code": k, "label": LEVELS[k], "count": v} for k, v in counts.items()], rows

    @api.model
    def _td_outages(self, start, end):
        """Планові відключення, що перетинають вікно (крім скасованих): назва, статус, інтервал."""
        states = _selection(self.env, "td.energy.outage.plan", "state")
        plans = (
            self.env["td.energy.outage.plan"]
            .sudo()
            .search([("state", "!=", "cancelled"), ("start", "<", end), ("end", ">", start)], order="start, id")
        )
        return [
            {"name": p.name, "state": states.get(p.state, p.state), "from": _hm(p.start), "to": _hm(p.end)}
            for p in plans
        ]

    @api.model
    def _td_rounds(self, start, end):
        """Обходи зміни — лише з установленим `td_energy_mobile` (`None` — блок пропускається)."""
        Round = self.env.get("td.energy.round")
        if Round is None:
            return None
        states = _selection(self.env, "td.energy.round", "state")
        rounds = Round.sudo().search([("starts_at", ">=", start), ("starts_at", "<", end)], order="starts_at, id")
        return [
            {
                "name": r.name, "performer": r.performer_id.name or DASH,
                "progress": "%s/%s" % (r.done_count, r.total_count), "state": states.get(r.state, r.state),
            }
            for r in rounds
        ]  # fmt: skip

    @api.model
    def _td_top_opps(self, cost):
        """Три найбільші відкриті резерви (за ₴/міс — з групою вартості, інакше в порядку W3)."""
        items = self.env["td.energy.opportunity"].get_list(None, ("open",)).get("items", [])
        if cost:
            items = sorted(items, key=lambda i: -(i.get("save_uah_month") or 0))
        return [
            {
                "title": i["title"], "text": i.get("text") or "",
                "save": fmt_int(i["save_uah_month"]) if cost and i.get("save_uah_month") is not None else None,
            }
            for i in items[:3]
        ]  # fmt: skip
