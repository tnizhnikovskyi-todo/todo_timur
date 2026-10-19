"""Крони ротації й добового скидання (R-22, R-23) та кнопка міграції (R-24)."""

import json
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..tools import params as P

_logger = logging.getLogger(__name__)

BATCH = 1000


class F3dYardVisitCron(models.Model):
    _inherit = "td.yard.visit"

    @api.model
    def _cron_gc(self):
        """R-22: ротація подій LPR, персональні дані рейсів, непризначені зважування."""
        env = self.env
        now = fields.Datetime.now()
        report = {"lpr_deleted": 0, "images_deleted": 0, "pii_cleared": 0, "weighings_deleted": 0}
        Event = env["td.yard.lpr.event"].sudo()
        cutoff = now - timedelta(days=P.get_int(env, "lpr_keep_days"))
        while True:
            events = Event.search([("received_at", "<", cutoff)], limit=BATCH)
            if not events:
                break
            images = env["ir.attachment"].sudo().search([("res_model", "=", Event._name), ("res_id", "in", events.ids)])
            report["images_deleted"] += len(images)
            images.unlink()
            report["lpr_deleted"] += len(events)
            events.unlink()
        cutoff = now - timedelta(days=P.get_int(env, "visit_pii_keep_days"))
        domain = [
            ("pii_cleared", "=", False),
            "|",
            "|",
            ("left_at", "<", cutoff),
            "&",
            ("left_at", "=", False),
            ("rejected_at", "<", cutoff),
            "&",
            "&",
            ("left_at", "=", False),
            ("rejected_at", "=", False),
            ("cancelled_at", "<", cutoff),
        ]
        while True:
            visits = self.sudo().search(domain, limit=BATCH)
            if not visits:
                break
            visits.write({"driver_phone": False, "driver_doc": False, "pii_cleared": True})
            report["pii_cleared"] += len(visits)
        cutoff = now - timedelta(days=P.get_int(env, "weighing_unassigned_keep_days"))
        Weighing = env["td.yard.weighing"].sudo()
        while True:
            old = Weighing.search([("state", "=", "unassigned"), ("ts", "<", cutoff)], limit=BATCH)
            if not old:
                break
            report["weighings_deleted"] += len(old)
            old.unlink()
        _logger.info("f3d_yard: ротація %s", json.dumps(report))
        return report

    @api.model
    def _cron_day_reset(self):
        """R-23: добові лічильники воріт."""
        gates = self.env["td.yard.gate"].sudo().search([])
        for gate in gates:
            gate.write(
                {
                    "passes_day_start": gate.counter_value,
                    "passes_today": 0,
                    "admitted_today": 0,
                    "tailgate_today": 0,
                }
            )
        gates._td_yard_notify()
        return True

    @api.model
    def f3d_yard_run_migration(self):
        """Серверна дія V-34: повторити міграцію двору (лише адміністратор «Завод 3D»)."""
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError("Повторити міграцію може лише адміністратор «Завод 3D».")
        from ..hooks import run_all

        report = run_all(self.env)
        parts = []
        for name, counters in report.items():
            if isinstance(counters, dict):
                parts.append("%s: %s" % (name, ", ".join("%s=%s" % kv for kv in counters.items())))
        if report.get("errors"):
            parts.append("Помилки: %s" % "; ".join(report["errors"]))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Міграцію двору виконано",
                "message": "\n".join(parts) or "Без змін",
                "type": "warning" if report.get("errors") else "success",
                "sticky": True,
            },
        }
