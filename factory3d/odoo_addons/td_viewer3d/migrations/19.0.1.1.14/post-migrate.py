"""Події шини потрібні лише дельті: умовчання `event_keep_hours` 48 → 24 год. Змінене адміністратором значення не
чіпаємо (`noupdate`-параметр без міграції лишився б 48 на всіх наявних базах, а таблиця росла б на тисячі рядків
за годину)."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env["ir.config_parameter"].sudo()
    if params.get_param("td.viewer.event_keep_hours") == "48":
        params.set_param("td.viewer.event_keep_hours", "24")
