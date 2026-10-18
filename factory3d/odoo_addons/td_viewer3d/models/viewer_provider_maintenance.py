from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from ..tools import dates
from ..tools import payload as payload_tools

STATIC_KEYS = ("state", "busy", "total", "boilers", "last_inspection", "leak_check")
DUE_SOON_DAYS = 7  # R-22: «ТО незабаром» — до стількох днів до планової дати
GROUP_KIOSK = "factory3d_viewer.group_f3d_kiosk"
PLAN_LOCK_NS = 7301  # advisory-lock: два швидкі кліки «Запланувати ТО» не створюють дві заявки


def plan_error(status, code, message):
    """Тіло помилки API-11: jsonrpc-маршрут не може змінити HTTP-статус, тож статус лежить у тілі (`status`)."""
    return {"ok": False, "status": status, "error": {"code": code, "message": message}}


class F3dViewerProviderMaintenance(models.AbstractModel):
    """M-01e: обладнання й заявки на обслуговування."""
    _name = "f3d.viewer.provider.maintenance"
    _inherit = "f3d.viewer.provider"
    _description = "3D: провайдер даних maintenance"

    _f3d_sequence = 50
    _f3d_sections = ("equipment", "maintenance_requests")
    _f3d_group = "base.group_user"

    @api.model
    def _f3d_viewer_bus_models(self):
        return ["maintenance.equipment", "maintenance.request"]

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        env = self.env
        if not payload_tools.access_ok(env, "maintenance.equipment"):
            return
        static_eq = (ctx.get("static") or {}).get("equipment") or {}
        equipment = payload.setdefault("equipment", {})
        since = dates.utc(ctx["today"] + " 00:00") - timedelta(days=7)

        requests = env["maintenance.request"].browse()
        open_by_eq, open_id_by_eq, open_prev, next_prev, recurring = {}, {}, set(), {}, {}
        if payload_tools.access_ok(env, "maintenance.request"):
            requests = env["maintenance.request"].search_fetch([
                ("equipment_id.f3d_code", "!=", False), ("archive", "=", False),
                "|", ("stage_id.done", "=", False), ("close_date", ">=", since.date())], order="request_date, id")
            for r in requests.filtered(lambda r: not r.stage_id.done):
                open_by_eq.setdefault(r.equipment_id.id, r.name)
                open_id_by_eq.setdefault(r.equipment_id.id, r.id)
                if r.maintenance_type == "preventive":
                    open_prev.add(r.equipment_id.id)
                # в Odoo 19 немає next_action_date: найближча планова профілактика
                if r.maintenance_type == "preventive" and (r.schedule_date or r.request_date):
                    day = r.schedule_date.date() if r.schedule_date else r.request_date
                    next_prev[r.equipment_id.id] = min(day, next_prev.get(r.equipment_id.id, day))
            recurring = self._f3d_recurring_next()
        today = fields.Date.to_date(ctx["today"])

        passport_ok = payload_tools.access_ok(env, "f3d.equipment.passport")
        tasks = {}
        if payload_tools.access_ok(env, "stock.picking.batch"):
            for b in env["stock.picking.batch"].search_fetch([("f3d_vehicle_id", "!=", False),
                                                        ("state", "in", ("in_progress", "draft"))], order="id"):
                tasks.setdefault(b.f3d_vehicle_id.id, b.name)

        for eq in env["maintenance.equipment"].search_fetch([("f3d_code", "!=", False)], order="id"):
            code = eq.f3d_code
            rec = {"name": eq.name, "category": eq.category_id.name or ""}
            if eq.serial_no and eq.serial_no != code:
                rec["serial"] = eq.serial_no
            if passport_ok and eq.f3d_manufacturer:
                rec["manufacturer"] = eq.f3d_manufacturer
            if passport_ok and eq.f3d_model:
                rec["model"] = eq.f3d_model
            nxt = eq.next_action_date if "next_action_date" in eq._fields else next_prev.get(eq.id)
            if not nxt and eq.id not in open_prev:
                nxt = recurring.get(eq.id)
            if nxt:
                rec["next_maintenance"] = str(nxt)
            if eq.id in open_by_eq:
                rec["maintenance_request"] = open_by_eq[eq.id]
                rec["maintenance_request_id"] = open_id_by_eq[eq.id]
            elif nxt and (due := self._f3d_due(nxt, today)):
                rec["maintenance_due"] = due  # планова дата настала, відкритої заявки немає → «Запланувати ТО»
            if eq.id in tasks:
                rec["current_task"] = tasks[eq.id]
            for k in STATIC_KEYS:
                if k in (static_eq.get(code) or {}):
                    rec[k] = static_eq[code][k]
            equipment.setdefault(code, {}).update(rec)

        payload["maintenance_requests"] = [self._f3d_request_rec(r, ctx["now"], ctx["today"]) for r in requests]

    @api.model
    def _f3d_request_rec(self, r, now, today):
        """Запис `maintenance_requests[]` (A.9). `res_id`, `done`, `equipment_name`, `overdue_days` — R-22:
        назва заявки не унікальна («Планове ТО» у всіх), тож клієнт знаходить заявку за `res_id`."""
        done = bool(r.stage_id.done)
        rec = {"id": r.name, "res_id": r.id, "name": r.name, "equipment": r.equipment_id.f3d_code,
               "equipment_name": r.equipment_id.name, "maintenance_type": r.maintenance_type,
               "stage": r.stage_id.name, "done": done, "priority": r.priority or "0"}
        if r.request_date:
            rec["request_date"] = dates.date_to_local(r.request_date)
        if r.schedule_date:
            rec["schedule_date"] = dates.local(r.schedule_date)
            if not done and r.schedule_date < now:
                rec["overdue_days"] = max(0, (date.fromisoformat(today)
                                              - date.fromisoformat(rec["schedule_date"][:10])).days)
        if r.user_id:
            rec["technician"] = r.user_id.name
        return rec

    @staticmethod
    def _f3d_due(day, today):
        """R-22: `overdue` — планова дата минула, `soon` — не пізніше DUE_SOON_DAYS днів, інакше None."""
        if isinstance(day, datetime):
            day = day.date()
        left = (day - today).days
        return "overdue" if left < 0 else "soon" if left <= DUE_SOON_DAYS else None

    @api.model
    def _f3d_recurring_next(self, equipment=None):
        """{equipment.id: дата} — наступна профілактика за останньою закритою повторюваною заявкою.
        В Odoo 19 у обладнання немає `next_action_date`; Odoo сама копіює повторювану заявку під час закриття,
        тож запис є лише тоді, коли копію прибрали або вона вже закрита. Без `equipment` — усе обладнання з кодом."""
        out = {}
        if not payload_tools.access_ok(self.env, "maintenance.request"):
            return out
        eq_domain = [("equipment_id", "in", equipment.ids)] if equipment else [("equipment_id.f3d_code", "!=", False)]
        done = self.env["maintenance.request"].search(eq_domain + [
            ("maintenance_type", "=", "preventive"), ("stage_id.done", "=", True),
            ("recurring_maintenance", "=", True), ("archive", "=", False)], order="schedule_date, request_date, id")
        for r in done:  # від старіших до новіших: остання закрита перекриває попередні
            base = (date.fromisoformat(dates.local(r.schedule_date)[:10]) if r.schedule_date else r.request_date)
            if not base:
                continue
            nxt = base + relativedelta(**{f"{r.repeat_unit or 'week'}s": max(1, r.repeat_interval or 1)})
            if r.repeat_type == "until" and r.repeat_until and nxt > r.repeat_until:
                out.pop(r.equipment_id.id, None)
            else:
                out[r.equipment_id.id] = nxt
        return out

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """Заявки й обладнання з кодів."""
        changes = ctx.get("changes") or {}
        sel = set(ctx.get("codes") or ())
        for model in ("maintenance.equipment", "maintenance.request"):
            sel |= set(changes.get(model) or ())
        tmp = {}
        self._f3d_viewer_collect(tmp, ctx)
        reqs = [r for r in tmp.get("maintenance_requests") or [] if r["id"] in sel or r["equipment"] in sel]
        eq_sel = sel | {r["equipment"] for r in reqs}
        part = {"maintenance_requests": reqs,
                "equipment": {c: v for c, v in (tmp.get("equipment") or {}).items() if c in eq_sel}}
        part = {k: v for k, v in part.items() if v}
        if part:
            payload_tools.deep_merge(patch, part)

    @api.model
    def _f3d_plan_maintenance(self, code=None, equipment_id=None):
        """API-11 / R-22: заявка планового ТО на обладнання. ORM — з правами користувача запиту, без sudo.
        Ідемпотентно: відкрита профілактична заявка повертається замість дубліката (`created: false`)."""
        env = self.env
        if env.context.get("kiosk") or env.user.has_group(GROUP_KIOSK):
            return plan_error(403, "kiosk", "Екран цеху не може створювати заявки на обслуговування.")
        Request = env["maintenance.request"]
        if not Request.has_access("create"):
            return plan_error(403, "forbidden", "Немає прав на створення заявок на обслуговування.")
        eq = env["maintenance.equipment"].search(
            [("id", "=", equipment_id) if equipment_id else ("f3d_code", "=", code), ("f3d_code", "!=", False)],
            limit=1)
        if not eq:
            return plan_error(404, "not_found", "Обладнання не знайдено.")
        env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (PLAN_LOCK_NS, eq.id))
        now, today = dates.now(env), dates.today(env)
        req = Request.search([("equipment_id", "=", eq.id), ("maintenance_type", "=", "preventive"),
                              ("stage_id.done", "=", False), ("archive", "=", False)], order="schedule_date, id", limit=1)
        created = not req
        if created:
            team = eq.maintenance_team_id.id or Request._get_default_team_id()
            if not team:
                return plan_error(400, "no_team", "Немає команди обслуговування: створіть її в розділі «Обслуговування».")
            nxt = eq.next_action_date if "next_action_date" in eq._fields else False
            nxt = nxt or self._f3d_recurring_next(eq).get(eq.id)
            vals = {"name": f"Планове ТО · {eq.name}", "equipment_id": eq.id, "maintenance_type": "preventive",
                    "schedule_date": dates.utc(f"{nxt} 08:00") if nxt else now.replace(second=0),
                    "request_date": fields.Date.to_date(today), "maintenance_team_id": team}
            tech = eq.technician_user_id or eq.category_id.technician_user_id
            if tech:
                vals["user_id"] = tech.id
            try:
                with env.cr.savepoint():
                    req = Request.create(vals)
            except AccessError:
                return plan_error(403, "forbidden", "Немає прав на створення заявок на обслуговування.")
            except UserError as exc:
                return plan_error(400, "bad_request", str(exc.args[0]) if exc.args else "Заявку не створено.")
        eq_patch = {"maintenance_request": req.name, "maintenance_request_id": req.id, "maintenance_due": None}
        if req.schedule_date:
            eq_patch["next_maintenance"] = dates.local(req.schedule_date)[:10]
        return {"ok": True, "created": created, "request": self._f3d_request_rec(req, now, today),
                "equipment": {eq.f3d_code: eq_patch}}
