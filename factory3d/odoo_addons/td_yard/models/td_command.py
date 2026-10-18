"""M-18 f3d.command: розширення командами шлагбаумів двору."""

from odoo import fields, models


class F3dCommand(models.Model):
    _inherit = "f3d.command"

    f3d_yard_gate_id = fields.Many2one("f3d.yard.gate", string="КПП", index=True, readonly=True, ondelete="set null")
    f3d_yard_visit_id = fields.Many2one("f3d.yard.visit", string="Рейс", index=True, readonly=True, ondelete="set null")
    f3d_yard_kind = fields.Selection(
        [
            ("open", "Відкрити"),
            ("close", "Закрити"),
            ("hold", "Тримати відкритим"),
            ("release", "Зняти утримання"),
        ],
        string="Команда шлагбаума",
        readonly=True,
    )
    f3d_yard_reason = fields.Selection(
        [
            ("manual", "Вручну"),
            ("auto_booking", "Авто: бронювання"),
            ("auto_exit", "Авто: виїзд"),
            ("auto_hold_max", "Авто: ліміт утримання"),
        ],
        readonly=True,
    )

    def write(self, vals):
        old = {cmd.id: cmd.state for cmd in self} if "state" in vals else {}
        res = super().write(vals)
        if old:
            gates = self.filtered(lambda c: c.f3d_yard_gate_id and c.state != old[c.id]).mapped("f3d_yard_gate_id")
            if gates:
                gates.sudo()._f3d_yard_refresh_state()
        return res
