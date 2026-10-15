import logging

from odoo.addons.factory3d_base.hooks import zones

_logger = logging.getLogger('odoo.addons.factory3d_base_mrp_maintenance')


def post_init_hook(env):
    """A-15: maintenance.equipment.workcenter_id = РЦ з тим самим f3d_code (лише порожнім полям).

    Потім — `zones.bind` (B-2, крок 7 міграції base): міст ставиться поверх уже встановленого base, коли його
    `post_init_hook` пройшов без поля `workcenter_id` (CE), тож зони обладнання треба прив'язати знову (ідемпотентно)."""
    workcenters = env['mrp.workcenter'].search([('f3d_code', '!=', False)])
    by_code = {wc.f3d_code: wc for wc in workcenters}
    equipment = env['maintenance.equipment'].search([('f3d_code', 'in', list(by_code)),
                                                     ('workcenter_id', '=', False)])
    for eq in equipment:
        eq.workcenter_id = by_code[eq.f3d_code]
    _logger.info("Міст mrp_maintenance: workcenter_id заповнено для %d одиниць обладнання", len(equipment))
    zones.bind(env)
