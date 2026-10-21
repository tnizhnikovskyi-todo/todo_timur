"""DT-1: вартість простою рахується лише в плановому часі РЦ, планова причина («Перерва») — окремо (`planned_cost`).
Збережені `cost`/`planned_cost` перераховуються за календарем, чинним зараз."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Downtime = env["td.downtime"].with_context(active_test=False)
    recs = Downtime.search([])
    for name in ("cost", "planned_cost"):
        env.add_to_compute(Downtime._fields[name], recs)
    env.flush_all()
