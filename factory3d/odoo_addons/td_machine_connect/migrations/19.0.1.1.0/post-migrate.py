"""DT-4: ставки `costs_hour` демо-РЦ верстатів (лише порожні, лише в демо-базі); вартість простоїв перераховується
стандартним обчисленням збереженого поля `td.downtime.cost` під час оновлення модуля."""

from odoo import SUPERUSER_ID, api

from odoo.addons.td_machine_connect.hooks import demo_rates


def migrate(cr, version):
    demo_rates(api.Environment(cr, SUPERUSER_ID, {}))
