"""Хук джерел проходів людей (SPEC M-12, M-12a): джерело — будь-яка модель з префіксом f3d.fire.passage.source."""
from datetime import timedelta

from odoo import api, models


class F3dFirePassageSource(models.AbstractModel):
    _name = "f3d.fire.passage.source"
    _description = "Пожежна безпека: джерело даних про людей на об'єкті"

    _f3d_priority = 1000  # менше — пріоритетніше
    PREFIX = "f3d.fire.passage.source."

    @api.model
    def _f3d_source_names(self):
        return sorted(n for n in self.env.registry if n.startswith(self.PREFIX))

    @api.model
    def _f3d_get_source(self):
        candidates = []
        for name in self._f3d_source_names():
            model = self.env[name].sudo()
            if not hasattr(model, "_f3d_passages"):
                continue
            if hasattr(model, "_f3d_available") and not model._f3d_available():
                continue
            candidates.append((getattr(model, "_f3d_priority", 1000), name, model))
        if candidates:
            return min(candidates, key=lambda c: (c[0], c[1]))[2]
        return self.env["f3d.fire.passage.source.hr_attendance"].sudo()

    @api.model
    def _f3d_source_key(self, model):
        return getattr(model, "_f3d_key", None) or model._name[len(self.PREFIX):]

    @api.model
    def _f3d_people_at(self, model, at):
        if hasattr(model, "_f3d_on_site"):
            return model._f3d_on_site(at)
        last = {}
        for passage in sorted(model._f3d_passages(at - timedelta(hours=24), at), key=lambda p: p["ts"]):
            if passage["direction"] == "in":
                last[passage["employee_id"]] = {
                    "employee_id": passage["employee_id"], "since": passage["ts"], "point": passage["point"]}
            else:
                last.pop(passage["employee_id"], None)
        return list(last.values())


class F3dFirePassageSourceHrAttendance(models.AbstractModel):
    _name = "f3d.fire.passage.source.hr_attendance"
    _inherit = "f3d.fire.passage.source"
    _description = "Пожежна безпека: джерело проходів — відмітки hr.attendance"

    _f3d_priority = 100
    _f3d_key = "hr_attendance"

    def _f3d_available(self):
        return True

    def _f3d_on_site(self, at):
        attendances = self.env["hr.attendance"].sudo().search(
            [("check_in", "<=", at), "|", ("check_out", "=", False), ("check_out", ">", at)],
            order="check_in, id")
        people = {}
        for att in attendances:
            people.setdefault(att.employee_id.id, {
                "employee_id": att.employee_id.id, "since": att.check_in, "point": "Відмітка входу"})
        return list(people.values())

    def _f3d_passages(self, start, end):
        attendances = self.env["hr.attendance"].sudo().search(
            [("check_out", ">=", start), ("check_out", "<=", end)], order="check_out")
        return [{"employee_id": att.employee_id.id, "ts": att.check_out, "point": "Відмітка виходу",
                 "direction": "out"} for att in attendances]
