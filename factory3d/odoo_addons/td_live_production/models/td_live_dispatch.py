"""Диспетчер живого виробництва (LP-03, LP-04): такт, застосування подій, закриття МО, відвантаження, цілі верстатам.

Такт не пам'ятає стану: він збирає його з бази, `tools.dispatch.simulate` дає хронологічні події до «зараз», а тут вони
застосовуються. Кожен крок ідемпотентний: наряд, який уже запущено (у т. ч. автостартом `td_machine_connect`, з
Enterprise `mrp_workorder` чи без нього), не стартує вдруге, завершений не завершується вдруге, відкритий верстатом
простій лише класифікується. Помилка кроку відкочується його savepoint і не зупиняє решту.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.td_machine_connect.tools import ppt

from ..tools import clock, dispatch, planner

_logger = logging.getLogger(__name__)

SHIP_STATES = ("done", "cancel")
WARN_EVERY = timedelta(hours=1)
_LAST_WARN = {}  # база → коли востаннє писали про недоступний емулятор (одне попередження на годину)


class TdLiveEngine(models.AbstractModel):
    _inherit = "td.live.engine"

    # --- стан із бази ---------------------------------------------------------------------------------
    @api.model
    def _td_scope(self):
        """Керовані МО: відкриті й ті, чиє замовлення ще не відвантажено. `(МО, замовлення до відвантаження)`."""
        env = self.env
        Picking = env["stock.picking"]
        pending = Picking.search([("sale_id.td_live_day_id", "!=", False), ("state", "not in", SHIP_STATES)]).sale_id
        MO = env["mrp.production"]
        mos = MO.search([("td_live_day_id", "!=", False), ("state", "not in", ("done", "cancel"))])
        if pending:
            mos |= MO.search([("origin", "in", pending.mapped("name")), ("td_live_day_id", "!=", False)])
        return mos, pending

    @api.model
    def _td_open_timers(self, wo):
        return wo.sudo().time_ids.filtered(lambda t: not t.date_end)

    @api.model
    def _td_wo_started_at(self, wo):
        starts = wo.time_ids.filtered("date_start").mapped("date_start")
        return min(starts) if starts else (wo.date_start or None)

    @api.model
    def _td_snapshot(self, mos, live_dts):
        """Вхід `tools.dispatch.simulate` з ORM."""
        env = self.env
        names = {so.name: so for so in env["sale.order"].search([("name", "in", mos.mapped("origin"))])}
        state = {"wos": {}, "mos": {}, "sos": {}, "dts": {}}
        for mo in mos:
            wos = mo.workorder_ids.filtered(lambda w: w.state != "cancel").sorted("id")
            so = names.get(mo.origin)
            done_at = None
            if mo.state == "done":
                done_at = mo.date_finished or max(wos.mapped("date_finished") or [fields.Datetime.now()])
            state["mos"][mo.id] = {"wos": wos.ids, "so": so.id if so else None, "done_at": done_at}
            if so:
                state["sos"].setdefault(so.id, {"mos": [], "shipped": False})["mos"].append(mo.id)
            for wo in wos:
                started = wo.state == "progress"
                state["wos"][wo.id] = {
                    "mo": mo.id,
                    "wc": wo.workcenter_id.id,
                    "state": wo.state if wo.state in ("progress", "done") else "ready",
                    "plan_start": None if wo.state in ("progress", "done") else (wo.date_start or None),
                    "minutes": wo.duration_expected or 1.0,
                    "start": self._td_wo_started_at(wo) if started or wo.state == "done" else None,
                    "end": (wo.date_finished or None) if wo.state == "done" else None,
                }
        for sid, item in state["sos"].items():
            so = env["sale.order"].browse(sid)
            item["shipped"] = all(p.state in SHIP_STATES for p in so.picking_ids)
        for live in live_dts:
            state["dts"][live.id] = {
                "wc": live.workcenter_id.id,
                "plan_start": live.plan_start,
                "minutes": live.minutes,
                "kind": live.kind,
                "reason": planner.REASON_LABELS.get(live.reason, live.reason),
                "state": live.state,
                "start": live.date_start or None,
                "end": live.date_end or None,
            }
        return state

    # --- такт -----------------------------------------------------------------------------------------
    @api.model
    def td_dispatch(self, now=None, force=False, limit=None):
        """Такт диспетчера: події до `now`, цілі верстатам. Повертає лічильники й цілі.

        `limit` — не більше стільки подій за виклик (крон після довгої паузи доганяє частинами, не вичерпуючи ліміт
        часу); решту подасть наступний такт, бо стан береться з бази. Тоді цілі верстатам не надсилаються.
        """
        self = self.sudo()
        res = {"started": 0, "finished": 0, "closed": 0, "shipped": 0, "downtimes": 0, "targets": [], "pushed": {}}
        if not (force or self._td_params()["enabled"]):
            return res
        now = now or self._td_now()
        params = self._td_params()
        mos, _pending = self._td_scope()
        Live = self.env["td.live.downtime"]
        live_dts = Live.search(
            ["|", ("state", "=", "active"), "&", ("state", "=", "planned"), ("plan_start", "<=", now)]
        )
        if not mos and not live_dts:
            return res
        state = self._td_snapshot(mos, live_dts)
        events, after = dispatch.simulate(state, now, params["shift"], params["workdays"])
        failed = set()
        for ev in events[:limit]:
            self._td_apply_event(ev, state, failed, res)
        if limit and len(events) > limit:
            _logger.info("td_live_production: у черзі ще %s подій, продовжить наступний такт", len(events) - limit)
            return res
        targets = dispatch.machine_targets(after, now)
        res["targets"] = targets
        res["pushed"] = self._td_push_targets(targets)
        return res

    @api.model
    def _td_apply_event(self, ev, state, failed, res):
        """Один крок у savepoint. `failed` — ключі, чиї залежні кроки цього такту пропускаються."""
        env = self.env
        kind, ident, t = ev["kind"], ev["id"], ev["t"]
        mo_id = state["wos"][ident]["mo"] if kind in ("wo_start", "wo_finish") else None
        if kind == "mo_done":
            mo_id = ident
        key = {"wo_start": ("mo", mo_id), "wo_finish": ("mo", mo_id), "mo_done": ("mo", mo_id)}.get(kind)
        if kind == "ship":
            if any(("mo", m) in failed for m in state["sos"][ident]["mos"]):
                return False
        elif key and key in failed:
            return False
        try:
            with env.cr.savepoint():
                if kind == "wo_start":
                    res["started"] += bool(self._td_wo_start(env["mrp.workorder"].browse(ident), t))
                elif kind == "wo_finish":
                    res["finished"] += bool(self._td_wo_finish(env["mrp.workorder"].browse(ident), t))
                elif kind == "mo_done":
                    res["closed"] += bool(self._td_mo_close(env["mrp.production"].browse(ident), t))
                elif kind == "ship":
                    res["shipped"] += bool(self._td_ship(env["sale.order"].browse(ident), t))
                elif kind == "dt_start":
                    res["downtimes"] += bool(self._td_downtime_start(env["td.live.downtime"].browse(ident), t))
                elif kind == "dt_end":
                    self._td_downtime_end(env["td.live.downtime"].browse(ident), t)
        except Exception as exc:  # noqa: BLE001 — крок не повинен зупиняти такт; причина в логу, повтор на наступному тику
            _logger.warning("td_live_production: %s #%s о %s не виконано: %s", kind, ident, t, exc)
            if key:
                failed.add(key)
            return False
        return True

    # --- наряди ---------------------------------------------------------------------------------------
    @api.model
    def _td_machine_of(self, wo):
        return wo.workcenter_id.sudo().td_machine_ids.filtered("active")[:1]

    @api.model
    def _td_unblock(self, wo, t):
        """Верстат «заблоковано» відкритими записами втрат (старі простої демо, залишки): закрити їх о `t`, як це
        робить автостарт верстата (`_td_unblock_wc`) — інакше Odoo не дає запустити наряд."""
        timers = (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .search(
                [
                    ("workcenter_id", "=", wo.workcenter_id.id),
                    ("date_end", "=", False),
                    ("loss_id.loss_type", "in", ("availability", "quality")),
                    ("date_start", "<=", t),
                ]
            )
        )
        if timers:
            timers.write({"date_end": t})
            wo.workcenter_id.invalidate_recordset(["working_state"])

    @api.model
    def _td_wo_dates(self, wo, start, end):
        """Дати наряду дослівно: без `bypass_duration_calculation` Odoo перераховує кінець за календарем РЦ."""
        wo.sudo().with_context(bypass_duration_calculation=True).write({"date_start": start, "date_finished": end})

    @api.model
    def _td_wo_start(self, wo, t):
        """Старт наряду з датою `t`. Ідемпотентно: уже в роботі або з відкритим таймером — нічого не робить."""
        wo = wo.sudo()
        if wo.state in ("done", "cancel", "progress") or self._td_open_timers(wo):
            return False
        machine = self._td_machine_of(wo)
        before = wo.time_ids
        # `button_start` першого наряду МО скидає плановані дати решти нарядів (`button_unplan`): запам'ятаємо
        plan = {
            o.id: (o.date_start, o.date_finished)
            for o in wo.production_id.workorder_ids - wo
            if o.state not in ("done", "cancel") and o.date_start and o.date_finished
        }
        self._td_unblock(wo, t)
        if machine:
            emp = machine._td_pick_employee(wo)
            machine._td_start_at(wo, emp, t)
            machine._td_set_active(wo, emp)
        else:
            wo.button_start()
        wo.invalidate_recordset(["state", "time_ids"])
        if wo.state != "progress":
            raise UserError(_("Наряд %s не запустився.", wo.display_name))
        for timer in self._td_open_timers(wo) | (wo.time_ids - before):
            timer.sudo().write({"date_start": t})
        self._td_wo_dates(wo, t, t + timedelta(minutes=wo.duration_expected or 1.0))
        for other in wo.production_id.workorder_ids - wo:
            if other.id in plan and not other.date_start:
                self._td_wo_dates(other, *plan[other.id])
        mo = wo.production_id
        others = mo.workorder_ids - wo
        if all(o.state not in ("progress", "done") for o in others) and mo.date_start != t:
            mo.sudo().with_context(force_date=True).write({"date_start": t})
        return True

    @api.model
    def _td_wo_finish(self, wo, t):
        """Завершення наряду о `t`. Ідемпотентно: завершений (у т. ч. автостопом верстата) пропускається."""
        wo = wo.sudo()
        if wo.state in ("done", "cancel"):
            return False
        if wo.state != "progress" and not self._td_open_timers(wo):
            self._td_wo_start(wo, min(t, wo.date_start or t))
        timers = self._td_open_timers(wo)
        wo.write({"qty_produced": wo.qty_production})
        if "employee_ids" in wo._fields and wo.employee_ids and hasattr(wo, "stop_employee"):
            wo.stop_employee(wo.employee_ids.ids)  # Enterprise: працівники наряду
        wo.button_finish()
        wo.invalidate_recordset(["state", "time_ids"])
        for timer in timers | wo.time_ids.filtered(lambda r: not r.date_end or r.date_end > t):
            timer.sudo().write({"date_end": max(t, timer.date_start)})
        self._td_wo_dates(wo, wo.date_start, t)
        machine = self._td_machine_of(wo)
        if machine and machine.active_workorder_id == wo:
            machine.with_context(tracking_disable=True).write({"active_workorder_id": False, "wo_paused": False})
        return True

    # --- МО, склад, відвантаження ------------------------------------------------------------------------
    @api.model
    def _td_stock_location(self, location):
        """Внутрішня локація для приходу: сама, якщо внутрішня, інакше перша внутрішня всередині."""
        if location.usage == "internal":
            return location
        child = self.env["stock.location"].search(
            [("location_id", "child_of", location.id), ("usage", "=", "internal")], limit=1
        )
        return child or location

    @api.model
    def _td_restock(self, product, location, qty, label):
        """Віртуальне «приймання» того, чого бракує (демо без закупівель): коригування залишку, партія `LIVE-…`."""
        lot = False
        if product.tracking != "none":
            name = "LIVE-%s" % label
            Lot = self.env["stock.lot"].sudo()
            lot = Lot.search([("product_id", "=", product.id), ("name", "=", name)], limit=1) or Lot.create(
                {"name": name, "product_id": product.id, "company_id": self.env.company.id}
            )
        self.env["stock.quant"].sudo()._update_available_quantity(
            product, self._td_stock_location(location), qty, lot_id=lot or None
        )

    @api.model
    def _td_cover_moves(self, moves, t):
        """Зарезервувати рухи; чого бракує на складі — оприбуткувати й зарезервувати знову."""
        label = clock.local_date(t).strftime("%Y%m%d")
        for move in moves.filtered(lambda m: m.state not in ("done", "cancel")):
            product = move.product_id
            if product.is_storable:
                if (
                    product.tracking != "none"
                ):  # стандартне завершення наряду «бере» кількість без партії — партія потрібна
                    move.move_line_ids.filtered(lambda line: not line.lot_id).unlink()
                    move._recompute_state()
                short = move.product_uom_qty - sum(move.move_line_ids.mapped("quantity"))
                if short > 1e-6:
                    qty = move.product_uom._compute_quantity(short, product.uom_id)
                    self._td_restock(product, move.location_id, qty, label)
                    move._action_assign()
            if move.quantity < move.product_uom_qty:
                move.quantity = move.product_uom_qty

    @api.model
    def _td_mo_close(self, mo, t):
        """Закрити МО о `t`: списання компонентів (бракуюче оприбутковується), випуск виробів."""
        mo = mo.sudo()
        if mo.state in ("done", "cancel") or any(w.state not in ("done", "cancel") for w in mo.workorder_ids):
            return False
        if mo.state == "draft":
            mo.action_confirm()
        self._td_cover_moves(mo.move_raw_ids, t)
        mo.move_raw_ids.filtered(lambda m: m.state not in ("done", "cancel")).picked = True
        mo.qty_producing = mo.product_qty
        res = mo.with_context(skip_backorder=True, skip_immediate=True, skip_consumption=True).button_mark_done()
        if isinstance(res, dict):
            raise UserError(_("МО %s потребує підтвердження вручну: %s", mo.name, res.get("res_model")))
        mo.invalidate_recordset(["state"])
        if mo.state != "done":
            raise UserError(_("МО %s не закрилось (стан %s).", mo.name, mo.state))
        mo.with_context(force_date=True).write({"date_finished": t})
        moves = mo.move_raw_ids | mo.move_finished_ids
        moves.write({"date": t})
        moves.move_line_ids.write({"date": t})
        return True

    @api.model
    def _td_ship(self, so, t):
        """Відвантажити замовлення о `t`: усі незавершені переміщення замовлення (відбір, відправлення)."""
        so = so.sudo()
        done = False
        label = clock.local_date(t).strftime("%Y%m%d")
        for _i in range(3):  # відбір → відправлення: наступне переміщення з'являється після попереднього
            pickings = so.picking_ids.filtered(lambda p: p.state not in SHIP_STATES).sorted("id")
            if not pickings:
                break
            for picking in pickings:
                if picking.state == "draft":
                    picking.action_confirm()
                picking.action_assign()
                self._td_cover_moves(picking.move_ids, t)
                picking.move_ids.filtered(lambda m: m.state not in SHIP_STATES).picked = True
                res = picking.with_context(skip_backorder=True, skip_sms=True, skip_immediate=True).button_validate()
                if isinstance(res, dict):
                    raise UserError(_("Переміщення %s потребує підтвердження вручну.", picking.name))
                if picking.state == "done":
                    picking.write({"date_done": t})
                    picking.move_ids.write({"date": t})
                    picking.move_ids.move_line_ids.write({"date": t})
                    done = True
        if not done:
            _logger.info("td_live_production: відвантаження %s: нічого не залишалось (мітка %s)", so.name, label)
        return done

    # --- простої -------------------------------------------------------------------------------------
    @api.model
    def _td_downtime_start(self, live, t):
        """Відкрити простій верстата. Верстат уже в простої (стан із емулятора) — лише проставити причину."""
        live = live.sudo()
        if live.state != "planned":
            return False
        machine = live.workcenter_id.td_machine_ids.filtered("active")[:1]
        if not machine:
            live.write({"state": "skipped"})
            return False
        Downtime = self.env["td.downtime"].sudo().with_context(tracking_disable=True, f3d_mc_internal=True)
        loss = live.loss_id
        opened = Downtime.search([("machine_id", "=", machine.id), ("date_end", "=", False)], limit=1)
        if opened:
            if loss and opened.reason_state == "to_classify":
                opened._td_apply_reason(loss, "master")
                opened.write({"reason_state": "confirmed"})
            live.write({"state": "active", "date_start": t, "downtime_id": opened.id, "owned": False})
            return True
        dt = Downtime.create(
            {
                "machine_id": machine.id,
                "date_start": t,
                "state_kind": live.kind,
                "loss_id": loss.id if loss else self.env.ref("td_machine_connect.loss_unknown").id,
                "reason_source": "demo",
                "reason_state": "confirmed",
                "workorder_id": False,
            }
        )
        machine.with_context(tracking_disable=True).write({"current_downtime_id": dt.id})
        live.write({"state": "active", "date_start": t, "downtime_id": dt.id, "owned": True})
        return True

    @api.model
    def _td_downtime_end(self, live, t):
        """Закрити простій, який відкрив диспетчер; чужий (стан верстата) закриє сам верстат."""
        live = live.sudo()
        dt = live.downtime_id.sudo()
        if live.owned and dt and not dt.date_end:
            end = max(t, dt.date_start)
            machine = dt.machine_id
            ppt_min = ppt.total_min(ppt.ppt_intervals(self.env, dt.workcenter_id, dt.date_start, end))
            dt.with_context(tracking_disable=True, f3d_mc_internal=True).write({"date_end": end, "ppt_min": ppt_min})
            if machine.current_downtime_id == dt:
                machine.with_context(tracking_disable=True).write({"current_downtime_id": False})
            machine._td_create_machine_record(dt, dt.date_start, live.loss_id.name or live.reason, date_end=end)
        live.write({"state": "done", "date_end": t})

    # --- емулятор (C-LP-01) ---------------------------------------------------------------------------
    @api.model
    def _td_sim_device(self):
        """Модель емулятора, якщо `td_iot_sim` стоїть і вміє приймати цілі; інакше `None`."""
        if "td.sim.device" not in self.env:
            return None
        device = self.env["td.sim.device"]
        return device if hasattr(device, "_td_push_machine_targets") else None

    @api.model
    def _td_push_targets(self, targets):
        """Цілі станів верстатів → емулятор: `{"ok": n, "unknown": [коди]}`; без емулятора чи зв'язку `{"ok": 0}`."""
        device = self._td_sim_device()
        if device is None or not targets:
            return {"ok": 0, "unknown": [], "skipped": "no_emulator" if device is None else "no_targets"}
        codes = {wc.id: wc.td_code for wc in self.env["mrp.workcenter"].browse({tg["wc"] for tg in targets})}
        payload = [
            {
                "code": codes[tg["wc"]],
                "state": tg["state"],
                "reason": tg["reason"],
                "until": tg["until"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            for tg in targets
            if codes.get(tg["wc"])
        ]
        try:
            res = device._td_push_machine_targets(payload) or {"ok": 0, "unknown": []}
        except Exception as exc:  # noqa: BLE001 — емулятор не повинен ламати такт
            res = {"ok": 0, "unknown": [], "error": str(exc)}
        if payload and not res.get("ok"):
            self._td_warn_hourly("цілі верстатам не прийнято емулятором: %s" % (res.get("error") or res))
        return res

    @api.model
    def _td_warn_hourly(self, text):
        """Попередження в журнал не частіше за раз на годину (на базу), щоб не засмічувати лог щохвилини."""
        now = fields.Datetime.now()
        db = self.env.cr.dbname
        if db not in _LAST_WARN or now - _LAST_WARN[db] >= WARN_EVERY:
            _LAST_WARN[db] = now
            _logger.warning("td_live_production: %s", text)

    # --- догнати минуле (LP-04) -------------------------------------------------------------------------
    @api.model
    def td_catch_up(self):
        """Завершити датами планів МО й наряди минулих діб, що досі «в роботі»; відвантажити їхні замовлення.

        Нічого не видаляє. Керовані МО (згенеровані модулем) доганяє диспетчер симуляцією, решту — цей прохід.
        """
        self = self.sudo()
        env = self.env
        now = self._td_now()
        managed = self.td_dispatch(now=now, force=True)
        today_start = clock.shift_window(clock.local_date(now), (0.0, 24.0))[0]
        MO = env["mrp.production"]
        old = MO.search([("td_live_day_id", "=", False), ("state", "in", ("confirmed", "progress", "to_close"))])
        closed = failed = skipped = 0
        for mo in old:
            wos = mo.workorder_ids.filtered(lambda w: w.state != "cancel").sorted("id")
            ends = [w.date_finished or w.date_start for w in wos if (w.date_finished or w.date_start)]
            last = max(ends) if ends else (mo.date_finished or mo.date_start)
            if not last or last >= today_start:
                skipped += 1
                continue
            try:
                with env.cr.savepoint():
                    end = self._td_catch_up_mo(mo, wos)
                    if end:
                        self._td_ship_ready(mo, end)
                        closed += 1
                    else:
                        skipped += 1
            except Exception as exc:  # noqa: BLE001 — одна МО не зупиняє решту
                failed += 1
                _logger.warning("td_live_production: догнати %s: %s", mo.name, exc)
        return _(
            "Догнати минуле: закрито МО %(closed)s (не вдалось %(failed)s, пропущено %(skipped)s). Згенеровані МО: "
            "стартувало нарядів %(started)s, завершено %(finished)s, закрито МО %(mos)s, відвантажено %(ship)s.",
            closed=closed,
            failed=failed,
            skipped=skipped,
            started=managed["started"],
            finished=managed["finished"],
            mos=managed["closed"],
            ship=managed["shipped"],
        )

    @api.model
    def _td_catch_up_mo(self, mo, wos):
        """Наряди МО за датами планів, потім закриття МО. Повертає момент закриття (або `None`)."""
        open_wos = wos.filtered(lambda w: w.state != "done")
        done_ends = [w.date_finished for w in wos if w.state == "done" and w.date_finished]
        items = [
            {
                "id": w.id,
                "state": w.state,
                "start": self._td_wo_started_at(w) if w.state == "progress" else None,
                "plan_start": w.date_start or None,
                "plan_end": w.date_finished or None,
                "minutes": w.duration_expected,
            }
            for w in open_wos
        ]
        chain = dispatch.catchup_chain(items, max(done_ends) if done_ends else mo.date_start or None)
        if len(chain) != len(open_wos):
            return None
        end = max(done_ends) if done_ends else None
        for wo_id, start, finish in chain:
            wo = self.env["mrp.workorder"].browse(wo_id)
            self._td_wo_start(wo, start)
            self._td_wo_finish(wo, finish)
            end = finish
        if end and self._td_mo_close(mo, end):
            return end
        return end if mo.state == "done" else None

    @api.model
    def _td_ship_ready(self, mo, t):
        """Відвантажити замовлення МО, якщо всі його МО (з цим `origin`) закрито."""
        so = self.env["sale.order"].search([("name", "=", mo.origin)], limit=1) if mo.origin else self.env["sale.order"]
        if not so:
            return False
        roots = self.env["mrp.production"].search([("origin", "=", so.name), ("state", "!=", "cancel")])
        if roots and all(m.state == "done" for m in roots):
            return self._td_ship(so, t + timedelta(minutes=dispatch.SHIP_DELAY_MIN))
        return False
