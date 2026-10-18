from odoo.tests import TransactionCase, tagged

from ..services import checks, state as state_svc
from .golden_scenes import _configs, _pl, _slot, _state

RACK = {
    'bays': 2,
    'levels': 2,
    'bay_width': 2.7,
    'depth': 1.1,
    'level_height': 1.5,
    'positions_per_bay': 3,
    'max_load_kg': 1000,
}
SITE_ADDR = {'tpl': '{row} {bay} {level}', 'sep': '.'}  # коди комірок: 01.01.1, 01.01.2, 01.02.1, 01.02.2


def _scene(cell_code, site_addr=None, slot_addr=None, **site_extra):
    slot = _slot(1, 2, 'pallet_rack', 'RK-1', 30, 15, params=RACK)
    if slot_addr is not None:
        slot['addr'] = slot_addr
    state = _state(slots=[slot], placements=[_pl(1, 'PAL-1', 4, 28.65, 15, 0, 2, 1, cell_code)])
    if site_addr is not None:
        state['site']['addr'] = site_addr
    state['site'].update(site_extra)
    return state


def _run(state):
    configs = _configs(only=('fits', 'load'))
    return sorted((i['check'], tuple(i['codes'])) for i in checks.run_checks(state, configs, 0.001))


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestChecksWithAddressing(TransactionCase):
    """F01: перевірки за `cell_code` рахують комірки з контекстом адресації; без адресації — як раніше."""

    def test_legacy_without_addressing_is_unchanged(self):
        # PAL-1 (1200 кг) у комірці з ліміту 1000 кг: «load»; коду адресації в legacy-місці немає: «fits»
        self.assertEqual(_run(_scene('RK-1-B01-L1')), [('load', ('PAL-1',))])
        self.assertEqual(_run(_scene('01.01.1')), [('fits', ('PAL-1',))])
        self.assertEqual(_run(_scene('RK-1-B01-L1', site_addr={})), [('load', ('PAL-1',))])

    def test_addressed_code_is_found_without_false_positive(self):
        self.assertEqual(_run(_scene('01.01.1', SITE_ADDR)), [('load', ('PAL-1',))])
        self.assertEqual(_run(_scene('01.01.2', SITE_ADDR)), [('load', ('PAL-1',))])

    def test_stale_or_wrong_code_is_caught(self):
        # старий код у місці з адресацією й код-дубль, якого в місці немає: «fits»
        self.assertEqual(_run(_scene('RK-1-B01-L1', SITE_ADDR)), [('fits', ('PAL-1',))])
        self.assertEqual(_run(_scene('01.03.1', SITE_ADDR)), [('fits', ('PAL-1',))])

    def test_slot_addr_and_depth_mode_cell(self):
        slot_addr = {'tpl': '{prefix}/{bay}{level}', 'sep': ''}
        self.assertEqual(_run(_scene('RK-1/011', slot_addr=slot_addr)), [('load', ('PAL-1',))])
        self.assertEqual(_run(_scene('RK-1-B01-L1', slot_addr=slot_addr)), [('fits', ('PAL-1',))])
        # глибина «комірка»: у ярусі з'являються позиції (cells_per_level), код ярусу без позиції вже не існує;
        # напівкомірка: код знайдено (є і «виходить за межі комірки», і ліміт 500 кг), а не «комірки немає»
        with_pos = {'tpl': '{row} {bay} {level} {pos}', 'sep': '.'}
        deep = dict(RACK, cells_per_level=2)
        both = [('fits', ('PAL-1',)), ('load', ('PAL-1',))]
        for cell_code, expected in (('01.01.1.2', both), ('01.01.1', [('fits', ('PAL-1',))])):
            state = _scene(cell_code, with_pos, depth_mode='cell')
            state['slots'][0]['params'] = deep
            self.assertEqual(_run(state), expected, cell_code)

    def test_scene_state_has_site_addr(self):
        """`checks_state` передає в перевірки адресацію площадки (інакше контексти порожні)."""
        site = self.env['td.site'].create({'name': "Адреса", 'code': 'ADRCHK'})
        data = state_svc.checks_state(site)
        self.assertEqual(data['site']['depth_mode'], 'level')
        self.assertIn('addr', data['site'])
        site.write({'addr': SITE_ADDR})
        self.assertEqual(state_svc.checks_state(site)['site']['addr']['tpl'], SITE_ADDR['tpl'])
