from odoo import api, fields, models
from odoo.exceptions import UserError


class F3dFireDrillRollcallWizard(models.TransientModel):
    _name = "f3d.fire.drill.rollcall.wizard"
    _description = "Навчальна тривога: перекличка"

    drill_id = fields.Many2one("f3d.fire.drill", required=True, ondelete="cascade")
    line_ids = fields.One2many("f3d.fire.drill.rollcall.line", "wizard_id", string="Люди")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        drill = self.env["f3d.fire.drill"].browse(res.get("drill_id") or self.env.context.get("default_drill_id"))
        if drill and "line_ids" in fields_list:
            persons = drill.sudo().person_ids.filtered(lambda p: p.status in ("missing", "present"))
            res["line_ids"] = [(0, 0, {"person_id": p.id, "present": p.rollcall == "present"}) for p in persons]
        return res

    def action_apply(self):
        self.ensure_one()
        drill = self.drill_id
        if drill.state != "evaluating":
            raise UserError("Перекличка — після завершення навчання.")
        present = absent = 0
        for line in self.line_ids:
            line.person_id.sudo().rollcall = "present" if line.present else "absent"
            if line.present:
                present += 1
            else:
                absent += 1
        drill.message_post(body="Перекличка: присутні %d, відсутні %d" % (present, absent))
        return {"type": "ir.actions.act_window_close"}


class F3dFireDrillRollcallLine(models.TransientModel):
    _name = "f3d.fire.drill.rollcall.line"
    _description = "Навчальна тривога: рядок переклички"

    wizard_id = fields.Many2one("f3d.fire.drill.rollcall.wizard", required=True, ondelete="cascade")
    person_id = fields.Many2one("f3d.fire.drill.person", required=True, ondelete="cascade")
    seq = fields.Integer(related="person_id.seq", string="№")
    employee_name = fields.Char(related="person_id.employee_id.name", string="Працівник")
    present = fields.Boolean(string="Присутній")
