import json
import logging
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..adapters import td_genset as td
from ..adapters import telemetry

_logger = logging.getLogger(__name__)
KYIV = ZoneInfo("Europe/Kyiv")

STATE_LABELS = {
    0: "немає даних",
    1: "очікування",
    2: "мережа втрачена, затримка",
    3: "пуск",
    4: "захисна затримка",
    5: "прогрів",
    6: "працює без навантаження",
    7: "під навантаженням",
    8: "охолодження",
    9: "зупинка",
    10: "аварійна зупинка",
}
ALARM_LABELS = {0: "немає", 1: "попередження", 2: "аварійна зупинка"}
# DEC-9: службові тривоги td_genset (не з контролера) не входять в alarm_level/alarm_count; зв'язок — R-12
SERVICE_ALARM_CODES = frozenset(
    {
        "link_lost",
        "cmd_unconfirmed",
        "breaker_unconfirmed",
        "external_control",
        "drain",
        "maintenance_due",
    }
)
SERVICE_ALARM_PREFIXES = ("relay_", "sensor_")
STATE_KEYS = ("state", "mode", "alarm_level", "island", "grid_ok", "online")
CLOCK_AHEAD_S = 120


def _is_service_alarm(code):
    code = code or ""
    return code in SERVICE_ALARM_CODES or code.startswith(SERVICE_ALARM_PREFIXES)


def _to_utc_naive(ts):
    if ts and getattr(ts, "tzinfo", None):
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts or None


class F3dGensetLink(models.Model):
    _name = "td.genset3d.link"
    _description = "Генератор: зв'язка з моделлю заводу"
    _inherit = ["mail.thread"]
    _order = "equipment_id"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Обладнання",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('td_passport_id.role', '=', 'genset')]",
        tracking=True,
    )
    td_code = fields.Char(related="equipment_id.td_code", string="Код сцени")
    td_genset_ref = fields.Reference(selection="_td_models", string="Генератор td_genset", required=True)
    profile_id = fields.Many2one(
        "td.genset3d.profile",
        string="Профіль",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.ref("td_genset_factory3d.profile_d700", raise_if_not_found=False),
    )
    source_id = fields.Many2one("td.source", string="Джерело телеметрії", readonly=True, ondelete="set null")
    publish_enabled = fields.Boolean(string="Публікувати в телеметрію", default=True, tracking=True)
    amf_master = fields.Selection(
        [("hgm", "HGM6120N веде AMF"), ("ats", "ATyS p головний")], compute="_compute_amf_master", string="Логіка AMF"
    )
    last_publish_ts = fields.Datetime(string="Остання публікація", readonly=True)
    last_publish_error = fields.Char(string="Помилка публікації", readonly=True)
    last_event_ts = fields.Datetime(string="Остання оброблена подія", readonly=True)
    last_event_id = fields.Integer(readonly=True, default=0)
    last_state_json = fields.Json(string="Останній знімок", readonly=True)
    last_state_text = fields.Char(compute="_compute_last_state_text", string="Знімок (JSON)")
    online = fields.Boolean(compute="_compute_live", string="На зв'язку")
    state_code = fields.Integer(compute="_compute_live", string="Код стану")
    state_label = fields.Char(compute="_compute_live", string="Стан")
    island = fields.Boolean(compute="_compute_live", string="Острів (від генератора)")
    signal_count = fields.Integer(compute="_compute_counts", string="Сигналів")
    request_open_count = fields.Integer(compute="_compute_counts", string="Відкритих заявок")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    _equipment_uniq = models.Constraint("UNIQUE(equipment_id)", "Для цього обладнання зв'язка вже існує.")
    _td_ref_uniq = models.Constraint("UNIQUE(td_genset_ref)", "Цей генератор td_genset уже зв'язано.")

    # --- довідники / computes ---------------------------------------------------------------------------
    @api.model
    def _td_models(self):
        model = td.GENSET_MODEL
        if model and model in self.env:
            return [(model, "Генератор td_genset")]
        return []

    @api.depends("equipment_id.name", "equipment_id.td_code")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s (%s)" % (rec.equipment_id.name or "", rec.equipment_id.td_code or "—")

    def _compute_amf_master(self):
        value = self._param("amf_master", "hgm")
        for rec in self:
            rec.amf_master = value if value in ("hgm", "ats") else "hgm"

    @api.depends("last_state_json")
    def _compute_last_state_text(self):
        for rec in self:
            rec.last_state_text = json.dumps(rec.last_state_json or {}, ensure_ascii=False, indent=1)

    @api.depends("last_state_json")
    def _compute_live(self):
        for rec in self:
            st = rec.last_state_json or {}
            rec.online = bool(st.get("online"))
            rec.state_code = int(st.get("state") or 0)
            rec.state_label = STATE_LABELS.get(rec.state_code, STATE_LABELS[0])
            rec.island = bool(st.get("island"))

    def _compute_counts(self):
        Request = self.env["maintenance.request"]
        has_key = "td_genset_event_key" in Request._fields
        for rec in self:
            rec.signal_count = (
                self.env["td.signal"].search_count(
                    [
                        ("equipment_id", "=", rec.equipment_id.id),
                        ("code", "=like", telemetry.prefix(rec.td_code or "") + "%"),
                    ]
                )
                if rec.td_code
                else 0
            )
            rec.request_open_count = (
                Request.search_count(
                    [
                        ("equipment_id", "=", rec.equipment_id.id),
                        ("td_genset_event_key", "!=", False),
                        ("stage_id.done", "=", False),
                    ]
                )
                if has_key
                else 0
            )

    @api.constrains("equipment_id")
    def _check_equipment(self):
        for rec in self:
            eq = rec.equipment_id
            if not eq.td_code:
                raise ValidationError(
                    _("Обладнання не має коду сцени (td_code). Заповніть «3D Завод → Код сцени» в base.")
                )
            role = eq.td_passport_id.role
            if role != "genset":
                raise ValidationError(_("Паспорт обладнання має роль «%s», потрібна «genset».", role or "—"))

    # --- параметри ---------------------------------------------------------------------------------------
    @api.model
    def _param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param("td.genset." + key, default)

    @api.model
    def _flag(self, key, default):
        return str(self._param(key, default)) in ("True", "true", "1")

    @api.model
    def _read_enabled(self):
        environment = self.env["ir.config_parameter"].sudo().get_param("td.base.environment", "test")
        return self._flag("read_enabled", "True" if environment == "test" else "False")

    @api.model
    def _offline_min(self):
        try:
            return max(1, int(self._param("offline_min", "5")))
        except (TypeError, ValueError):
            return 5

    # --- публікація ---------------------------------------------------------------------------------------
    @api.model
    def _cron_publish(self):
        if not self._read_enabled():
            return
        for link in self.search([("publish_enabled", "=", True)]):
            try:
                with self.env.cr.savepoint():
                    link._publish_one()
            except Exception as e:  # MG-11: збій однієї зв'язки не валить крон
                link.last_publish_error = ("%s: %s" % (type(e).__name__, e))[:250]
                _logger.exception("td_genset_factory3d: публікація зв'язки %s не вдалася", link.id)

    def _state_codes(self, snap):
        """R-03: коди state/mode/breaker/alarm_level + службові; повертає (codes, error|None)."""
        self.ensure_one()
        error = None
        raw = snap.get("state_raw")
        state = td.STATE_MAP.get(str(raw).lower()) if raw is not None else None
        if raw is not None and state is None:
            error = "невідомий стан контролера: %s" % raw
        state = state or 0
        p_kw = snap.get("p_kw")
        kw_prp = self.profile_id.kw_prp
        mode_raw, breaker_raw = snap.get("mode_raw"), snap.get("breaker_raw")
        mode = td.MODE_MAP.get(str(mode_raw).lower(), 0) if mode_raw is not None else 0
        breaker = td.BREAKER_MAP.get(str(breaker_raw).lower(), 0) if breaker_raw is not None else 0
        if state == 1 and snap.get("mains_ok") is False:  # DEC-11: код 2 виводить міст
            state = 2
        elif state == 6 and (breaker == 2 or (p_kw is not None and p_kw >= 0.05 * kw_prp)):
            state = 7
        alarms = [a for a in snap.get("alarms") or [] if not _is_service_alarm(a.get("code"))]  # DEC-9
        severities = {a.get("severity") for a in alarms}
        alarm_level = 2 if "shutdown" in severities else 1 if "warning" in severities else 0
        return {
            "state": state,
            "mode": mode,
            "breaker": breaker,
            "alarm_level": alarm_level,
            "alarm_count": len(alarms),
        }, error

    def _compute_values(self, snap, errors=None):
        """R-03, R-01, R-02: dict leaf -> float|None для свіжого знімка."""
        self.ensure_one()
        profile = self.profile_id
        codes, error = self._state_codes(snap)
        if error and errors is not None:
            errors.append(error)
        state, p_kw = codes["state"], snap.get("p_kw")
        load_pct = round(p_kw / profile.kw_prp * 100.0, 1) if p_kw is not None else None
        fuel_l = snap.get("fuel_l")
        if fuel_l is None and snap.get("fuel_pct") is not None:
            fuel_l = round(snap["fuel_pct"] / 100.0 * profile.tank_l, 1)
        running = state in (6, 7) and (p_kw or 0) > 0
        fuel_lph = profile.fuel_lph(load_pct) if running else 0.0
        ref_pct = load_pct if state == 7 and (p_kw or 0) > 0 else 75.0
        autonomy = profile.autonomy_h(fuel_l, ref_pct) if fuel_l is not None else None
        try:
            service_left = td.service_info(self.td_genset_ref).get("hours_left")
        except Exception:  # ТО не критичне для публікації
            _logger.debug("td_genset_factory3d: service_info недоступний", exc_info=True)
            service_left = None
        mains_ok = snap.get("mains_ok")
        vals = {
            "state": codes["state"],
            "mode": codes["mode"],
            "breaker": codes["breaker"],
            "mains_ok": None if mains_ok is None else int(bool(mains_ok)),
            "alarm_level": codes["alarm_level"],
            "alarm_count": codes["alarm_count"],
            "online": 1,
            "p_kw": p_kw,
            "load_pct": load_pct,
            "fuel_l": fuel_l,
            "fuel_lph": fuel_lph,
            "autonomy_h": autonomy,
            "service_h_left": service_left,
        }
        for leaf in (
            "u_v",
            "f_hz",
            "i_a",
            "pf",
            "kwh",
            "fuel_pct",
            "hours",
            "starts",
            "coolant_c",
            "oil_bar",
            "batt_v",
            "charger_v",
            "rpm",
        ):
            vals[leaf] = snap.get(leaf)
        return vals

    def _island_state(self, snap):
        """R-05: {"island", "grid_ok", "source"}."""
        self.ensure_one()
        now = fields.Datetime.now()
        pos_code = (self._param("ats_position_code", "") or "").strip()
        s1_code = (self._param("ats_src1_code", "") or "").strip()
        codes = [c for c in (pos_code, s1_code) if c]
        if codes:
            values = telemetry.read_values(self.env, codes)
            periods = telemetry.signal_periods(self.env, codes)
            pos = self._fresh_value(values, periods, pos_code, now)
            s1 = self._fresh_value(values, periods, s1_code, now)
            if pos is not None:
                return self._island_from_ats(pos, s1)
        if snap.get("online"):
            codes_, _err = self._state_codes(snap)
            return {
                "island": codes_["breaker"] == 2 and codes_["state"] in (6, 7),
                "grid_ok": None if snap.get("mains_ok") is None else bool(snap["mains_ok"]),
                "source": "hgm",
            }
        last = self.last_state_json or {}
        return {"island": last.get("island"), "grid_ok": None, "source": "stale"}

    @api.model
    def _fresh_value(self, values, periods, code, now):
        """Значення сигналу ATS, якщо він свіжий: status != stale і now − last_ts ≤ 3·period_s."""
        if not code or code not in values:
            return None
        value, ts, status = values[code]
        if status == "stale" or not ts:
            return None
        if (now - ts).total_seconds() > 3 * (periods.get(code) or 30):
            return None
        return value

    def _island_from_ats(self, pos, s1):
        """R-05 пріоритет 1: положення ATS свіже."""
        pos_i = int(self._param("ats_position_i_value", "2"))
        pos_ii = int(self._param("ats_position_ii_value", "3"))
        island = int(pos) == pos_ii
        if s1 is not None:
            grid_ok = int(s1) == 1
        elif int(pos) == pos_i:
            grid_ok = True
        elif island:
            grid_ok = False
        else:
            grid_ok = None
        return {"island": island, "grid_ok": grid_ok, "source": "ats"}

    def _critical_kw(self):
        """R-04: (сума кВт, відсутні коди, назви наявних). У infra.totals не пише."""
        self.ensure_one()
        Equipment = self.env["maintenance.equipment"].sudo()
        entries = []  # (code сигналу, назва)
        if "td.energy.node" in self.env:
            nodes = (
                self.env["td.energy.node"]
                .sudo()
                .search_read([("is_critical", "=", True)], ["code", "kind", "name", "equipment_id"], order="code")
            )
            for node in nodes:
                folder = {"consumer": "consumers", "line": "lines"}.get(node["kind"])
                if not folder:
                    _logger.debug("td_genset_factory3d: вузол %s (%s) пропущено", node["code"], node["kind"])
                    continue
                name = node["equipment_id"][1] if node["equipment_id"] else node["name"]
                entries.append(("energy/%s/%s/p_now" % (folder, node["code"]), name))
        if not entries:
            codes = [c.strip() for c in (self._param("critical_codes", "") or "").split(",") if c.strip()]
            seg = {c: (c.split("/")[-2] if c.count("/") >= 2 else c) for c in codes}
            eq_names = {
                r["td_code"]: r["name"]
                for r in Equipment.search_read([("td_code", "in", list(seg.values()))], ["td_code", "name"])
            }
            entries = [(c, eq_names.get(seg[c], seg[c])) for c in codes]
        values = telemetry.read_values(self.env, [c for c, _n in entries])
        missing = [c for c, _n in entries if c not in values]
        names = [n for c, n in entries if c in values]
        return round(sum(values[c][0] or 0.0 for c, _n in entries if c in values), 1), missing, names

    def _publish_one(self):
        """R-12/R-03/R-05: один прогін публікації; повертає dict із знімком, значеннями й результатом TEL-03."""
        self.ensure_one()
        now = fields.Datetime.now()
        snap = td.snapshot(self.td_genset_ref)  # атрибут модуля: §2.0.3
        telemetry.ensure_signals(self.env, self)
        prev = dict(self.last_state_json or {})
        offline_min = self._offline_min()
        errors = []
        ts = _to_utc_naive(snap.get("ts"))
        if ts and (ts - now).total_seconds() > CLOCK_AHEAD_S:
            errors.append("годинник ретранслятора попереду на %d с" % (ts - now).total_seconds())
            ts = now
        fresh = bool(snap.get("online")) and bool(ts) and (now - ts) <= timedelta(minutes=offline_min)
        pfx = telemetry.prefix(self.td_code)
        island = self._island_state(snap)
        if fresh:
            vals = self._compute_values(snap, errors)
            batch_ts = ts
            codes, _err = self._state_codes(snap)
            new_state = {
                "state": codes["state"],
                "mode": codes["mode"],
                "breaker": codes["breaker"],
                "alarm_level": codes["alarm_level"],
                "online": 1,
            }
        else:
            last_fuel = telemetry.read_values(self.env, [pfx + "fuel_l"]).get(pfx + "fuel_l")
            autonomy = None
            if last_fuel and last_fuel[1]:
                autonomy = self.profile_id.autonomy_h(last_fuel[0], 75.0)
            vals = {"online": 0, "state": 0, "fuel_lph": 0.0, "autonomy_h": autonomy}
            batch_ts = now
            new_state = {
                "state": prev.get("state", 0),
                "mode": prev.get("mode", 0),
                "breaker": prev.get("breaker", 0),
                "alarm_level": prev.get("alarm_level", 0),
                "online": 0,
            }
        new_state.update(island=island["island"], grid_ok=island["grid_ok"])
        batch = [
            {"code": pfx + leaf, "ts": batch_ts, "value": float(v), "q": "good"}
            for leaf, v in vals.items()
            if v is not None
        ]
        result = telemetry.ingest(self.env, batch)
        if not fresh:
            telemetry.mark_stale(
                self.env, [pfx + leaf for leaf in telemetry.STALE_LEAFS], "td_genset: немає свіжих даних"
            )
            since = prev.get("offline_since") if prev.get("online") == 0 and prev.get("offline_since") else None
            since = since or fields.Datetime.to_string(min(ts, now) if ts else now)
            comm_lost = bool(prev.get("comm_lost")) if prev.get("online") == 0 else False
            new_state.update(offline_since=since, comm_lost=comm_lost)
            if not comm_lost and now - fields.Datetime.from_string(since) >= timedelta(minutes=offline_min):
                self._on_comm_lost()
                new_state["comm_lost"] = True
        elif prev.get("online") == 0:
            self._on_comm_restored()
        if any(new_state.get(k) != prev.get(k) for k in STATE_KEYS):
            self._notify_state_change(new_state, prev)
        self.write(
            {
                "last_publish_ts": now,
                "last_publish_error": "; ".join(errors)[:250] or False,
                "last_state_json": new_state,
            }
        )
        return {"snap": snap, "values": vals, "result": result, "fresh": fresh}

    def _notify_state_change(self, new_state, prev=None):
        """Подія шини (якщо є viewer) і запис у чаттер при зміні state/alarm_level/island."""
        self.ensure_one()
        prev = prev if prev is not None else (self.last_state_json or {})
        if "td.viewer.event" in self.env:
            self.env["td.viewer.event"]._notify("maintenance.equipment", [self.td_code], "state")
        if any(new_state.get(k) != prev.get(k) for k in ("state", "alarm_level", "island")):
            self.message_post(
                body=_(
                    "Стан: %(state)s, режим: %(mode)s, тривога: %(alarm)s, острів: %(island)s",
                    state=STATE_LABELS.get(new_state.get("state"), "—"),
                    mode={0: "стоп", 1: "ручний", 2: "авто", 3: "тест"}.get(new_state.get("mode"), "—"),
                    alarm=ALARM_LABELS.get(new_state.get("alarm_level"), "—"),
                    island=_("так") if new_state.get("island") else _("ні"),
                )
            )

    # --- R-12: зв'язок -----------------------------------------------------------------------------------
    def _on_comm_lost(self):
        """Одна подія COMM_LOST через R-07 (мапа подій і _apply_event — W2b)."""
        self.ensure_one()
        if (
            not self._flag("requests_enabled", "True")
            or not hasattr(self, "_apply_event")
            or "td.genset3d.event.map" not in self.env
        ):
            return
        ev = {
            "id": 0,
            "ts": fields.Datetime.now(),
            "code": "COMM_LOST",
            "severity": "comm",
            "name": "втрачено зв'язок з контролером",
            "value": None,
            "unit": None,
            "threshold": None,
            "text": "",
        }
        row = self.env["td.genset3d.event.map"]._match(ev)
        self._apply_event(ev, row)

    def _on_comm_restored(self):
        self.ensure_one()
        Request = self.env["maintenance.request"]
        if "td_genset_event_key" not in Request._fields:
            return
        req = Request.sudo().search(
            [
                ("equipment_id", "=", self.equipment_id.id),
                ("td_genset_event_key", "=", "GENSET:COMM_LOST"),
                ("stage_id.done", "=", False),
            ],
            limit=1,
        )
        if req:
            local = fields.Datetime.now().replace(tzinfo=timezone.utc).astimezone(KYIV)
            req.message_post(body=_("Зв'язок відновлено о %s", local.strftime("%H:%M")))

    # --- дії -----------------------------------------------------------------------------------------------
    def action_check(self):
        self.ensure_one()
        if not self.env.user.has_group("td_factory3d.group_td_manager"):
            raise AccessError(_("Перевірку зв'язки може виконати лише менеджер «3D Завод»."))
        if not self._read_enabled():
            raise UserError(_("Публікацію вимкнено стоп-краном td.genset.read_enabled"))
        # виняток із ACL: менеджер вже перевірений вище, запис показань — права telemetry (SPEC §4.1)
        res = self.sudo()._publish_one()
        snap, vals = res["snap"], res["values"]
        message = _(
            "Знімок: стан %(state)s, %(p)s кВт, паливо %(pct)s %% (%(l)s л), мотогодини %(h)s; записано %(n)s показань",
            state=STATE_LABELS.get(vals.get("state"), "—"),
            p=snap.get("p_kw"),
            pct=snap.get("fuel_pct"),
            l=vals.get("fuel_l"),
            h=snap.get("hours"),
            n=res["result"]["accepted"],
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": "info", "sticky": False},
        }

    def action_open_td(self):
        self.ensure_one()
        return td.open_action(self.td_genset_ref)

    def action_open_signals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Сигнали генератора"),
            "res_model": "td.signal",
            "view_mode": "list,form",
            "domain": [("code", "=like", telemetry.prefix(self.td_code) + "%")],
        }

    def action_open_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Заявки генератора"),
            "res_model": "maintenance.request",
            "view_mode": "list,form",
            "domain": [("equipment_id", "=", self.equipment_id.id), ("td_genset_event_key", "!=", False)],
        }

    def action_show_3d(self):
        self.ensure_one()
        return self.equipment_id.action_f3d_show()
