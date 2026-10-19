import importlib.util
import os

from odoo.tests import TransactionCase, tagged

MIGRATION = os.path.join(os.path.dirname(__file__), '..', 'migrations', '19.0.1.2.0', 'post-migrate.py')


def _load_migration():
    spec = importlib.util.spec_from_file_location('td_constructor_post_migrate_1_2_0', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestMigrationFloorSpot(TransactionCase):
    """S1: post-migrate 19.0.1.2.0 додає `floor_spot` у дозволені типи шарів «Склади» наявних площадок."""

    def setUp(self):
        super().setUp()
        self.term = self.env['td.term'].search([('term_type', '=', 'slot_type'), ('key', '=', 'floor_spot')])
        site_model = self.env['td.site'].with_context(f3d_blank=True)
        self.site = site_model.create({'name': "Стара площадка", 'code': 'OLDMIG'})
        self.layers = {layer.kind: layer for layer in self.site.layer_ids}

    def _migrate(self):
        _load_migration().migrate(self.env.cr, '19.0.1.1.0')
        self.env.invalidate_all()

    def _keys(self, kind):
        return set(self.layers[kind].allowed_slot_type_ids.mapped('key'))

    def _make_old(self):
        """Шар «Склади» зі старим списком (без floor_spot), як у базах до S1."""
        self.layers['storage'].allowed_slot_type_ids -= self.term
        self.assertEqual(self._keys('storage'), {'pallet_rack', 'cantilever', 'shelf', 'floor_stack'})

    def test_old_storage_layer_gets_floor_spot_idempotently(self):
        self.assertTrue(self.term)
        self._make_old()
        production = self._keys('production')
        self._migrate()
        self.assertEqual(self._keys('storage'), {'pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'floor_spot'})
        self.assertEqual(self._keys('production'), production)  # інші види шарів не чіпаємо
        self._migrate()  # повторний запуск нічого не змінює й не дублює
        self.assertEqual(len(self.layers['storage'].allowed_slot_type_ids), 5)

    def test_empty_list_stays_empty(self):
        self.layers['storage'].allowed_slot_type_ids = [(5, 0, 0)]  # порожньо = дозволено все
        self._migrate()
        self.assertEqual(self._keys('storage'), set())

    def test_inactive_layer_and_draft_not_touched(self):
        self._make_old()
        self.layers['storage'].active = False
        before = self.site.draft_changes
        self._migrate()
        self.assertIn('floor_spot', self._keys('storage'))  # архівні шари теж
        self.assertEqual(self.site.draft_changes, before)
