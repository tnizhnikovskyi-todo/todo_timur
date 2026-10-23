from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Менеджер — адміністратор проєктів: роль отримує групу, наявні агенти-менеджери теж."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    manager = env["td.claude.role"].search([("code", "=", "manager")], limit=1)
    group = env.ref("project.group_project_manager", raise_if_not_found=False)
    if manager and group and not manager.group_ids:
        manager.group_ids = [(4, group.id)]
    manager._td_sync_agent_groups()
