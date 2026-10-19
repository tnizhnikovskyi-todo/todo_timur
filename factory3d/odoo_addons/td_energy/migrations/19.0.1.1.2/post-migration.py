"""Міграція 19.0.1.1.2: шафа вводу КГУ `QF-CHP` на секції 2 (тип `generator`), `CHP` живиться від неї, схема Пульту.

Увесь код — у `hooks._migrate_chp_cell` (ідемпотентний; правки користувача не перезаписуються).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.td_energy import hooks


def migrate(cr, version):
    hooks._migrate_chp_cell(api.Environment(cr, SUPERUSER_ID, {}))
