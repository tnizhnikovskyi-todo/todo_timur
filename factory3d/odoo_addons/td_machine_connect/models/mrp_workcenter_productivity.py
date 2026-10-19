import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MrpWorkcenterProductivity(models.Model):
    """M-15: відмітки журналу часу. `create` — R-06 (злиття з простоєм верстата)."""

    _inherit = "mrp.workcenter.productivity"

    td_downtime_id = fields.Many2one("td.downtime", string="Простій верстата", ondelete="set null", index=True)
    td_source = fields.Selection(
        [("operator", "Оператор"), ("machine", "Верстат"), ("master", "Майстер"), ("demo", "Демо-дані")],
        default="operator",
        string="Звідки запис",
    )
    td_auto = fields.Boolean(default=False, string="Створено верстатом")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("f3d_mc_auto"):
            for rec, vals in zip(records, vals_list, strict=True):
                upd = {}
                if "td_source" not in vals:
                    upd["td_source"] = "machine"
                if "td_auto" not in vals:
                    upd["td_auto"] = True
                if upd:
                    rec.write(upd)
            return records
        for rec in records:
            if rec.loss_type in ("availability", "quality") and not rec.workorder_id:
                rec._td_merge_downtime()
        return records

    def _td_merge_downtime(self):
        """R-06 п. 1–2: запис оператора/майстра зливається з відкритим простоєм верстата РЦ."""
        self.ensure_one()
        machine = self.workcenter_id.sudo().td_machine_ids.filtered("active")[:1]
        if not machine or not machine.read_enabled:
            return
        master = self.env.user.has_group("mrp.group_mrp_manager")
        source = "master" if master else "operator"
        self.sudo().write({"td_source": source})
        dt = machine.current_downtime_id.sudo()
        if not dt or dt.date_end:
            return
        self.sudo().write({"td_downtime_id": dt.id})
        for mrec in dt.productivity_ids.filtered(lambda r: r.td_auto and not r.date_end and r.id != self.id):
            mrec.with_env(machine._td_tech_env()).write({"date_end": max(self.date_start, mrec.date_start)})
        dt._td_apply_reason(self.loss_id, source, self.env.user.employee_id)
        dt.with_context(f3d_mc_internal=True).write({"reason_state": "confirmed" if master else "to_confirm"})


class MrpWorkcenterProductivityLoss(models.Model):
    """M-16."""

    _inherit = "mrp.workcenter.productivity.loss"

    td_planned = fields.Boolean(
        default=False,
        string="Плановий простій",
        help="Не входить у плановий час виробництва при розрахунку OEE (обід, регламентна перерва)",
    )
