from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """v2: наявний агент стає Менеджером, агенти отримують право на табель, стадії — ролі за мітками."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    manager = env["td.claude.role"].search([("code", "=", "manager")], limit=1)
    agents = env["td.claude.agent"].with_context(active_test=False).search([("role_id", "=", False)])
    if manager and agents:
        agents.write({"role_id": manager.id})
    group = env.ref("hr_timesheet.group_hr_timesheet_user", raise_if_not_found=False)
    if group:
        all_agents = env["td.claude.agent"].with_context(active_test=False).search([])
        all_agents.agent_user_id.write({"group_ids": [(4, group.id)]})
    env["td.claude.role"]._td_map_stages()
