"""RB-05: `post_init` — одне джерело Modbus (сигнали `chp/…` → `MB-U72-CHP`) і вузли; `uninstall_hook` — назад.

Кроки ідемпотентні. Джерело `CHP-U72` архівується (не видаляється), корінь меню `td_chp.menu_td_chp_root` ховає
`data/td_chp_factory3d_menu_hide.xml`; при видаленні моста джерело, сигнали й корінь меню повертаються.
"""

import logging

from odoo import Command

_logger = logging.getLogger(__name__)
TARGET_SOURCE = "MB-U72-CHP"
OWN_SOURCE_XMLID = "td_chp.source_chp_u72"
ROOT_MENU_XMLID = "td_chp.menu_td_chp_root"
GROUP_LINKS = (
    ("td_energy.group_td_energy_user", "td_chp.group_td_chp_user"),
    ("td_energy.group_td_energy_manager", "td_chp.group_td_chp_operator"),
    ("td_energy.group_td_energy_chief", "td_chp.group_td_chp_chief"),
)


def _units(env):
    return env["td.chp.unit"].sudo().with_context(active_test=False).search([])


def _chp_signals(env):
    return env["td.signal"].sudo().with_context(active_test=False).search([("module", "=", "chp")])


def post_init(env):
    """DB-05: сигнали `module='chp'` і `unit.source_id` → `MB-U72-CHP`, `CHP-U72` → `active=False`; вузли за кодами."""
    own = env.ref(OWN_SOURCE_XMLID, raise_if_not_found=False)
    target = env["td.source"].sudo().with_context(active_test=False).search([("code", "=", TARGET_SOURCE)], limit=1)
    units = _units(env)
    if own and target and own != target:
        signals = _chp_signals(env).filtered(lambda s: s.source_id != target)
        signals.write({"source_id": target.id})
        units.filtered(lambda u: u.source_id in (own, env["td.source"])).write({"source_id": target.id})
        own.sudo().write({"active": False})
        _logger.info("td_chp_factory3d: %s сигналів КГУ перенесено на %s", len(signals), target.code)
    elif not target:
        _logger.warning(
            "td_chp_factory3d: джерело %s не знайдено, сигнали КГУ лишилися на власному джерелі", TARGET_SOURCE
        )
    nodes = env["td.energy.node"].sudo()
    node = nodes.search([("code", "=", "CHP")], limit=1)
    qf = nodes.search([("code", "=", "QF-CHP")], limit=1)
    for unit in units:
        vals = {}
        if not unit.energy_node_id and node:
            vals["energy_node_id"] = node.id
        if not unit.energy_qf_node_id and qf:
            vals["energy_qf_node_id"] = qf.id
        if vals:
            unit.write(vals)


def uninstall_hook(env):
    """RB-05: сигнали й `unit.source_id` назад на `CHP-U72` (`active=True`), корінь меню знову видно."""
    own = env.ref(OWN_SOURCE_XMLID, raise_if_not_found=False)
    if own:
        own.sudo().write({"active": True})
        _chp_signals(env).filtered(lambda s: s.source_id != own).write({"source_id": own.id})
        _units(env).write({"source_id": own.id})
    root = env.ref(ROOT_MENU_XMLID, raise_if_not_found=False)
    if root:
        root.sudo().write({"active": True})
    for parent_xmlid, child_xmlid in GROUP_LINKS:
        parent = env.ref(parent_xmlid, raise_if_not_found=False)
        child = env.ref(child_xmlid, raise_if_not_found=False)
        if parent and child:
            parent.sudo().write({"implied_ids": [Command.unlink(child.id)]})
