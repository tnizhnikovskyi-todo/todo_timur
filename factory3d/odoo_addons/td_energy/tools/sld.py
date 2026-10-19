"""W1-A: стани вузлів схеми, ребра, факти й рядки блоків (R-26, R-29). Знімок `Snap` — один на виклик API.

`Snap` читає за 6 запитів: сигнали `energy/%` й `infra/%`, вузли, лічильники, відкриті події, відкрите відключення АВР,
відкриті заявки ТО. Далі всі правила — чисті обчислення над знімком (без N+1).
"""

import math
import re

from . import dates
from .dates import local_slot_index, param_float

BAD_STATUS = ("stale", "unknown")
OPEN_STATES = ("active", "acked")
SHOWN_SHAPES = ("box", "bar")
CARD_KINDS = ("line", "transformer", "cell")
CHP_STATES = {"stop": "стоп", "starting": "запуск", "running": "працює", "fault": "аварія", "cooling": "охолодження"}
PV_P_RE = re.compile(r"^infra/pv/PV-INV-\d+/p_kw$")
PV_TODAY_RE = re.compile(r"^infra/pv/PV-INV-\d+/kwh_today$")
PV_STATUS_RE = re.compile(r"^infra/pv/PV-INV-\d+/status$")
GEN_POWER = {"chp": "infra/totals/chp_kw", "pv_inverters": "infra/totals/pv_now"}  # сигнал P генератора за `gen_kind`
SQRT3 = math.sqrt(3)
NODE_FIELDS = [
    "code", "name", "kind", "cell_type", "line_kind", "gen_kind", "parent_id", "parent_path", "section", "rating_a",
    "rating_kva", "rating_kvar", "p_inst_kw", "equipment_id", "workcenter_id", "note", "sld_show", "sld_shape", "sld_x",
    "sld_y", "sld_w", "sld_h", "sld_label", "sld_anchor_id", "pfc_step_kvar", "pfc_steps_total", "cos_phi_nominal",
    "sequence", "is_critical", "cabinet_id", "protection_trip_unit", "protection_ir_ratio",
]  # fmt: skip


def rnd(x):
    """Округлення «від нуля» до цілого (як у макеті): 44,75 → 45; 0,5 → 1."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def fmt(x, digits=0):
    if x is None:
        return "—"
    if digits:
        return ("%.*f" % (digits, x)).replace(".", ",")
    return str(rnd(x))


class Snap:
    """Знімок даних для схеми, Пульту й картки вузла."""

    def __init__(self, env, now=None):
        self.env = env
        self.now = now or dates.now_utc(env)
        self.warn_pct = param_float(env, "load_warn_pct", 80.0)
        self.alarm_pct = param_float(env, "load_alarm_pct", 100.0)
        self.cos_warn = param_float(env, "cos_phi_warn", 0.92)
        self.cos_alarm = param_float(env, "cos_phi_alarm", 0.90)
        self.pv_kwp = param_float(env, "pv_kwp", 920.0)
        self.bess_reserve = param_float(env, "bess_reserve_pct", 30.0)
        self._load_signals()
        self._load_nodes()
        self._load_meters()
        self._load_events()
        self._load_outage()
        self._load_requests()
        self._states = {}

    # --- читання -----------------------------------------------------------------------------------------
    def _load_signals(self):
        rows = (
            self.env["td.signal"]
            .sudo()
            .search_read(
                ["|", ("code", "=like", "energy/%"), ("code", "=like", "infra/%")],
                ["code", "last_value", "last_text", "last_ts", "last_quality", "status"],
            )
        )
        self.rows = {r["code"]: r for r in rows}
        self.fresh = {
            r["code"]: (r["last_value"], r["last_text"])
            for r in rows
            if r["last_ts"] and r["status"] not in BAD_STATUS and r["last_quality"] != "bad"
        }

    def _load_nodes(self):
        rows = self.env["td.energy.node"].sudo().search_read([], NODE_FIELDS, order="sequence, code")
        self.nodes = {}
        for r in rows:
            r["parent"] = r["parent_id"][0] if r["parent_id"] else False
            r["anchor"] = r["sld_anchor_id"][0] if r["sld_anchor_id"] else False
            r["equipment"] = r["equipment_id"][0] if r["equipment_id"] else False
            r["workcenter"] = r["workcenter_id"][0] if r["workcenter_id"] else False
            r["cabinet"] = r["cabinet_id"][0] if r["cabinet_id"] else False
            self.nodes[r["id"]] = r
        self.by_code = {r["code"]: r for r in rows}
        self.children = {}
        for r in rows:
            self.children.setdefault(r["parent"], []).append(r)

    def _load_meters(self):
        rows = (
            self.env["td.energy.meter"]
            .sudo()
            .search_read(
                [("active", "=", True), ("node_id", "!=", False)],  # td_energy_resources: лічильники ресурсів без вузла
                ["code", "node_id", "role", "data_state", "source_id", "model"],
            )
        )
        self.meters = {}
        for r in sorted(rows, key=lambda r: r["code"]):
            self.meters.setdefault(r["node_id"][0], r)  # як `node.meter_id`: перший за кодом
        self.meter_rows = rows

    def _load_events(self):
        rows = (
            self.env["td.energy.event"]
            .sudo()
            .search_read([("state", "in", OPEN_STATES), ("node_id", "!=", False)], ["node_id", "level"])
        )
        self.node_events = {}
        for r in rows:
            self.node_events.setdefault(r["node_id"][0], set()).add(r["level"])

    def _load_outage(self):
        outage = self.env["td.energy.outage"].sudo().search([("state", "=", "open")], limit=1)
        self.outage_open = bool(outage)
        self.outage_no_gen = bool(outage) and not outage.gen_started

    def _load_requests(self):
        """Відкриті заявки ТО: `mnt` у таблиці відгалужень, «Наступне ТО», термографія."""
        rows = (
            self.env["maintenance.request"]
            .sudo()
            .search_read(
                [("stage_id.done", "=", False), ("equipment_id", "!=", False)],
                ["equipment_id", "maintenance_type", "schedule_date", "name"],
            )  # fmt: skip
        )
        self.corrective_eq, self.corrective_name, self.planned = set(), {}, {}
        for r in rows:
            eq = r["equipment_id"][0]
            if r["maintenance_type"] == "corrective":
                self.corrective_eq.add(eq)
                self.corrective_name.setdefault(eq, r["name"])
            elif r["schedule_date"] and r["schedule_date"] >= self.now:
                if eq not in self.planned or r["schedule_date"] < self.planned[eq]["schedule_date"]:
                    self.planned[eq] = r

    # --- доступ ------------------------------------------------------------------------------------------
    def v(self, code):
        item = self.fresh.get(code)
        return item[0] if item else None

    def t(self, code):
        item = self.fresh.get(code)
        return item[1] if item else None

    def ts(self, code):
        row = self.rows.get(code)
        return row["last_ts"] if row else None

    def descendants(self, row, kinds=None):
        prefix = row["parent_path"] or ""
        out = [n for n in self.nodes.values() if n["id"] != row["id"] and (n["parent_path"] or "").startswith(prefix)]
        return [n for n in out if not kinds or n["kind"] in kinds]

    def ancestors(self, row):
        out, seen = [], set()
        parent = self.nodes.get(row["parent"])
        while parent and parent["id"] not in seen:
            out.append(parent)
            seen.add(parent["id"])
            parent = self.nodes.get(parent["parent"])
        return out

    def meter_of(self, row):
        """Лічильник вузла; для лінії — лічильник її шафи-фідера (батько-`cell`)."""
        meter = self.meters.get(row["id"])
        if meter is None and row["kind"] == "line":
            meter = self.meters.get(row["parent"])
        return meter

    def meter_state(self, row):
        meter = self.meter_of(row)
        return meter["data_state"] if meter else "none"

    def generator_of(self, row):
        """Генератор, що живиться через шафу вводу генератора (`cell_type='generator'`): перший дочірній `generator`."""
        return next((c for c in self.children.get(row["id"], []) if c["kind"] == "generator"), None)

    def generator_power(self, row):
        """P шафи вводу генератора, кВт: вимірювання генератора (КГУ — `infra/totals/chp_kw`); `None` — немає даних."""
        gen = self.generator_of(row)
        code = GEN_POWER.get(gen["gen_kind"]) if gen else None
        return self.v(code) if code else None

    def generator_current(self, row):
        """Струм шафи вводу генератора, А: `P·1000/(√3·380·cos φ)` (R-16 п. 6, DEC-15); `None` — немає P."""
        p = self.generator_power(row)
        if p is None:
            return None
        return abs(p) * 1000.0 / (SQRT3 * 380.0 * (row["cos_phi_nominal"] or 0.9))

    # --- R-26: стан вузла --------------------------------------------------------------------------------
    def load_pct(self, row):
        """Завантаження вузла, %: `None` — немає даних або номіналу."""
        kind = row["kind"]
        code = row["code"]
        if kind == "transformer":
            s, rating = self.v("energy/transformers/%s/s_kva" % code), row["rating_kva"]
            return s / rating * 100 if s is not None and rating else None
        if kind == "line":
            i, rating = self.v("energy/lines/%s/i_now" % code), row["rating_a"]
            return i / rating * 100 if i is not None and rating else None
        if kind == "cell":
            if row["cell_type"] == "incomer":
                i, rating = self.v("energy/cells/%s/i_now" % code), row["rating_a"]
            elif row["cell_type"] == "generator":
                i, rating = self.generator_current(row), row["rating_a"]
            else:
                line = next((c for c in self.children.get(row["id"], []) if c["kind"] == "line"), None)
                i = self.v("energy/lines/%s/i_now" % line["code"]) if line else None
                rating = row["rating_a"]
            return i / rating * 100 if i is not None and rating else None
        if kind == "consumer":
            p, rating = self.v("energy/consumers/%s/p_now" % code), row["p_inst_kw"]
            return p / rating * 100 if p is not None and rating else None
        return None

    def state(self, row):
        sid = row["id"]
        if sid not in self._states:
            self._states[sid] = self._state(row)
        return self._states[sid]

    def _state(self, row):
        levels = self.node_events.get(row["id"], ())
        if "bad" in levels:
            return "alarm"
        if "warn" in levels:
            return "warn"
        kind, code = row["kind"], row["code"]
        if kind == "generator":
            gen = row["gen_kind"]
            if gen in ("pv_inverters", "pv_inverter", "pv_field"):
                return "gen" if (self.v("infra/totals/pv_now") or 0) >= 1 else "off"
            if gen == "chp":
                chp = self.t("infra/chp/state")
                return "gen" if chp in ("running", "starting") else "alarm" if chp == "fault" else "off"
            if gen == "genset":
                return "gen" if self.v("infra/ats/position") == 3 else "off"
            return "off"
        if kind == "storage":
            if self.t("infra/bess/state") in ("offline", "fault"):
                return "alarm"
            return "gen" if abs(self.v("infra/totals/bess_kw") or 0) >= 1 else "ok"
        if kind == "ats":
            if self.outage_no_gen:
                return "alarm"
            return "gen" if self.v("infra/ats/position") == 3 else "off"
        if kind == "cell" and row["cell_type"] == "coupler":
            return "ok" if self.t("energy/cells/%s/state" % code) == "closed" else "off"
        if kind == "cell" and row["cell_type"] == "pfc":
            return self._pfc_state(row)
        if kind == "cell" and row["cell_type"] == "generator":
            gen = self.generator_of(row)  # шафа вводу генератора — за станом її генератора
            return self.state(gen) if gen else "off"
        if kind in ("transformer", "line", "cell", "consumer"):
            return self._load_state(row)
        if kind in ("input", "substation", "section", "switchboard"):
            return "alarm" if self.outage_no_gen else "ok"
        return "ok"

    def _pfc_state(self, row):
        fault = self.v("energy/cells/%s/fault_step" % row["code"])
        if fault and fault > 0:
            return "warn"
        cos = self.v("energy/sections/S%d/cos_phi" % (row["section"] or 1))
        if cos is not None and cos < self.cos_alarm:
            return "alarm"
        if cos is not None and cos < self.cos_warn:
            return "warn"
        return "ok"

    def _load_state(self, row):
        has_meter = self.meter_of(row) is not None
        status = self.meter_state(row)
        if has_meter and status in ("stale", "no_data"):
            return "alarm"
        load = self.load_pct(row)
        if load is not None:
            if load >= self.alarm_pct:
                return "alarm"
            if load >= self.warn_pct:
                return "warn"
        if has_meter and status == "gap":
            return "warn"
        if not has_meter and load is None:
            return "off"
        return "ok"

    # --- ребра (R-26) ------------------------------------------------------------------------------------
    def visible_parent(self, row):
        if row["anchor"] and row["anchor"] in self.nodes:
            return self.nodes[row["anchor"]]
        for anc in self.ancestors(row):
            if anc["sld_show"] and anc["sld_shape"] in SHOWN_SHAPES:
                return anc
        return None

    def edges(self):
        out = []
        for row in self.sld_rows():
            if row["sld_shape"] not in SHOWN_SHAPES:
                continue
            parent = self.visible_parent(row)
            if parent is None:
                continue
            st = self.state(row)
            out.append({"from": parent["code"], "to": row["code"], "state": st if st in ("gen", "off") else "ok"})
        return out

    def sld_rows(self):
        return [r for r in self.nodes.values() if r["sld_show"]]

    # --- тексти ------------------------------------------------------------------------------------------
    def consumers_state(self, row):
        """R-30 п. 10: стан споживачів піддерева `{code: run|idle|mnt}` і `p_now` по них."""
        out = {}
        for n in self.descendants(row, ("consumer",)) or ([row] if row["kind"] == "consumer" else []):
            p = self.v("energy/consumers/%s/p_now" % n["code"])
            if n["equipment"] and n["equipment"] in self.corrective_eq:
                st = "mnt"
            elif p is not None and n["p_inst_kw"] and p < 0.05 * n["p_inst_kw"]:
                st = "idle"
            elif p is None:
                st = "idle"
            else:
                st = "run"
            out[n["code"]] = (st, p or 0.0, n)
        return out

    def section_estimate(self, row):
        """«Оцінка за балансом секції»: Σ секції − Σ інших фідерів секції (кВт)."""
        section = row["section"] or self.nodes.get(row["parent"], {}).get("section")
        total = self.v("energy/sections/S%d/p_kw" % section) if section else None
        if total is None:
            return None
        others = 0.0
        for n in self.nodes.values():
            if n["kind"] == "line" and n["id"] != row["id"] and (n["section"] or 0) == section:
                others += self.v("energy/lines/%s/p_now" % n["code"]) or 0.0
        return max(0.0, total - others)

    def lines(self, row):
        """Рядки блока на схемі: підпис, головний показник, (необов'язково) уточнення."""
        label = row["sld_label"] or row["name"]
        kind, code = row["kind"], row["code"]
        out = [label]
        if kind == "input":
            out.append("%s кВт з мережі" % fmt(self.v("infra/totals/grid_kw")))
        elif kind == "substation":
            out.append("%d відгалужень" % len(self.children.get(row["id"], [])))
        elif kind == "transformer":
            p, load = self.v("energy/transformers/%s/p_kw" % code), self.load_pct(row)
            if p is None:
                out.append("немає даних")
            elif p < 0:
                out.append("експорт %s кВт" % fmt(-p))
            else:
                out.append("%s кВт · %s %%" % (fmt(p), fmt(load)))
        elif kind == "generator" and row["gen_kind"] in ("pv_inverters", "pv_inverter", "pv_field"):
            out.append("%s кВт" % fmt(self.v("infra/totals/pv_now")))
        elif kind == "generator" and row["gen_kind"] == "chp":
            out.append(CHP_STATES.get(self.t("infra/chp/state"), "немає даних"))
        elif kind == "cell" and row["cell_type"] == "generator":
            p = self.generator_power(row)
            out.append("немає даних" if p is None else "%s кВт" % fmt(p))
        elif kind == "cell" and row["cell_type"] == "pfc":
            q = self.v("energy/cells/%s/q_kvar" % code)
            on, total = self.v("energy/cells/%s/steps_on" % code), self.v("energy/cells/%s/steps_total" % code)
            out.append("%s квар" % fmt(q if q is not None else row.get("pfc_q_now")))
            if on is not None:
                out.append("%s з %s ступенів" % (fmt(on), fmt(total if total is not None else row["pfc_steps_total"])))
        elif kind == "storage":
            soc, kw = self.v("infra/totals/bess_soc"), self.v("infra/totals/bess_kw") or 0.0
            out.append("%s %%" % fmt(soc))
            out.append("заряд" if kw > 1 else "розряд" if kw < -1 else "очікування")
        elif kind == "ats":
            out.append("ДГУ" if self.v("infra/ats/position") == 3 else "мережа")
        elif kind in ("line", "cell") and row["cell_type"] != "coupler":
            i, load = self.v("energy/lines/%s/i_now" % code), self.load_pct(row)
            if kind == "line" and i is None:
                out.append("немає даних")
            else:
                out.append("%s А · %s %%" % (fmt(i), fmt(load)))
            if " · " in (row["name"] or ""):
                out.append(row["name"].split(" · ", 1)[1].split(",")[0])
        return out

    def facts(self, row, extra=None):
        """R-29: лише факти з даних; відсутні — пропускаються."""
        kind, code = row["kind"], row["code"]
        out = []
        if kind == "input":
            contract = self.contract_kw
            if self.v("infra/totals/grid_kw") is not None:
                out.append("З мережі %s кВт · договірна %s кВт" % (fmt(self.v("infra/totals/grid_kw")), fmt(contract)))
            incomers = [m["code"] for m in self.meter_rows if m["role"] == "incomer"]
            if incomers:
                out.append("Лічильники вводу: %s" % ", ".join(sorted(incomers)))
        elif kind == "substation":
            if row["note"]:
                out.append(row["note"])
            out.append("%d відгалужень" % len(self.children.get(row["id"], [])))
        elif kind == "transformer":
            out += self._transformer_facts(row)
        elif kind == "generator" and row["gen_kind"] in ("pv_inverters", "pv_inverter", "pv_field"):
            out += self._pv_facts(row)
        elif kind == "generator" and row["gen_kind"] == "chp":
            out.append(CHP_STATES.get(self.t("infra/chp/state"), "немає даних").capitalize())
            if self.v("infra/chp/hours") is not None:
                out.append("Мотогодини %s" % fmt(self.v("infra/chp/hours")))
        elif kind == "cell" and row["cell_type"] == "coupler":
            if self.t("energy/cells/%s/state" % code) == "closed":
                out.append("Увімкнено: секції 1 і 2 працюють разом")
            else:
                out.append("Вимкнено: секції живляться окремо від T1 і T2")
        elif kind == "cell" and row["cell_type"] == "generator":
            out += self._generator_cell_facts(row)
        elif kind == "cell" and row["cell_type"] == "pfc":
            out += self._pfc_facts(row)
        elif kind in ("line", "cell") and row["cell_type"] != "coupler":
            out += self._line_facts(row)
        elif kind == "storage":
            out += self._bess_facts(row)
        elif kind == "ats":
            out.append("Положення: %s" % ("ДГУ" if self.v("infra/ats/position") == 3 else "мережа"))
        return out + list(extra or [])

    def _generator_cell_facts(self, row):
        """Шафа вводу генератора (QF-CHP): куди підключена, номінал, що видає зараз — лише з даних."""
        gen = self.generator_of(row)
        out = []
        if gen:
            out.append("Ввід %s на секцію шин %s" % (gen["name"], row["section"] or "—"))
        if row["rating_a"]:
            out.append("Номінал %s А" % fmt(row["rating_a"]))
        p, i = self.generator_power(row), self.generator_current(row)
        if p is not None:
            out.append("Видає %s кВт · ≈ %s А" % (fmt(p), fmt(i)))
        return out

    def _transformer_facts(self, row):
        code = row["code"]
        out = []
        p, load = self.v("energy/transformers/%s/p_kw" % code), self.load_pct(row)
        if p is not None:
            out.append("експорт %s кВт" % fmt(-p) if p < 0 else "%s кВт · %s %%" % (fmt(p), fmt(load)))
        cos = self.v("energy/transformers/%s/cos_phi" % code)
        if cos is not None:
            out.append("cos φ %s" % fmt(cos, 2))
        temp = self.v("energy/transformers/%s/temp_c" % code)
        if temp is not None:
            out.append("Температура масла %s °C" % fmt(temp))
        plan = self.planned.get(row["equipment"]) if row["equipment"] else None
        if plan:
            out.append("Наступне ТО: %s" % dates.to_local(plan["schedule_date"]).strftime("%d.%m.%Y"))
        return out

    def _pv_facts(self, row):
        out = []
        pv = self.v("infra/totals/pv_now")
        if pv is not None:
            out.append("%s кВт зараз · %s %% піку" % (fmt(pv), fmt(pv / self.pv_kwp * 100 if self.pv_kwp else 0)))
        today = [v[0] for c, v in self.fresh.items() if PV_TODAY_RE.match(c) and v[0] is not None]
        if today:
            out.append("Виробіток сьогодні %s кВт·год" % fmt(sum(today)))
        total = sum(1 for c in self.rows if PV_STATUS_RE.match(c)) or 8
        alive = sum(1 for c in self.fresh if PV_STATUS_RE.match(c))
        out.append("Інверторів на зв'язку: %d з %d" % (alive, total))
        return out

    def _pfc_facts(self, row):
        code = row["code"]
        out = []
        q = self.v("energy/cells/%s/q_kvar" % code)
        on = self.v("energy/cells/%s/steps_on" % code)
        total = self.v("energy/cells/%s/steps_total" % code)
        if q is not None:
            out.append("Увімкнено %s квар (%s з %s ступенів)" % (fmt(q), fmt(on), fmt(total or row["pfc_steps_total"])))
        cos = self.v("energy/sections/S%d/cos_phi" % (row["section"] or 1))
        if cos is not None:
            out.append("cos φ секції %s" % fmt(cos, 2))
        fault = self.v("energy/cells/%s/fault_step" % code)
        if fault and fault > 0:
            out.append("Ступінь %s не вмикається" % fmt(fault))
        return out

    def _line_facts(self, row):
        out = []
        i, load = self.v("energy/lines/%s/i_now" % row["code"]), self.load_pct(row)
        if row["kind"] == "line":
            if i is not None:
                out.append("%s А з %s А · %s %%" % (fmt(i), fmt(row["rating_a"]), fmt(load)))
            p = self.v("energy/lines/%s/p_now" % row["code"])
            cons = self.consumers_state(row)
            taps = [n for n in self.descendants(row, ("tapoff",))] or [c[2] for c in cons.values()]
            not_working = sum(1 for st, _p, _n in cons.values() if st in ("idle", "mnt"))
            if p is not None:
                line = "%s кВт · %d відгалужень" % (fmt(p), len(taps))
                if not_working:
                    line += ", %d не працюють" % not_working
                out.append(line)
            if row["code"].startswith("C") and cons:
                top = sorted(cons.values(), key=lambda c: -c[1])[:3]
                out.append("Найбільші: " + ", ".join("%s %s кВт" % (n["code"], fmt(p_)) for _st, p_, n in top))
            meter = self.meter_of(row)
            if meter and meter["data_state"] in ("stale", "no_data"):
                ts = self.ts("energy/lines/%s/p_now" % row["code"])
                since = " з %s" % dates.to_local(ts).strftime("%H:%M") if ts else ""
                out.append("Лічильник %s не на зв'язку%s" % (meter["code"], since))
                est = self.section_estimate(row)
                if est is not None:
                    out.append("Оцінка за балансом секції: ≈ %s кВт" % fmt(est))
        else:
            if i is not None:
                out.append("%s А з %s А · %s %%" % (fmt(i), fmt(row["rating_a"]), fmt(load)))
        return out

    def _bess_facts(self, row):
        out = []
        soc, kw = self.v("infra/totals/bess_soc"), self.v("infra/totals/bess_kw")
        if soc is not None:
            out.append("Заряд %s %%" % fmt(soc))
        if kw is not None:
            if kw > 1:
                out.append("Заряджається %s кВт" % fmt(kw))
            elif kw < -1:
                out.append("Розряджається %s кВт" % fmt(-kw))
            else:
                out.append("Очікування, 0 кВт")
        out.append("Резерв на відключення мережі: %s %%" % fmt(self.bess_reserve))
        return out

    # заповнюється Пультом (потрібне фактам вузла `input`)
    contract_kw = 0.0


def states(env, nodes):
    """R-26: `{id вузла: стан}` для набору вузлів (один знімок на виклик)."""
    if not nodes:
        return {}
    snap = Snap(env(su=True))
    return {n.id: snap.state(snap.nodes[n.id]) for n in nodes if n.id in snap.nodes}


def minutes_ago_text(now, ts):
    if not ts:
        return ""
    return "%d хв" % int(max(0, (now - ts).total_seconds()) // 60)


__all__ = ["Snap", "states", "local_slot_index", "rnd", "fmt"]
