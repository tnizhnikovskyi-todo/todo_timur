from odoo.tests import TransactionCase, tagged

from ..services import registry
from ..services.registry import CHECKS, PLAN_BUILDERS, RENDERERS, SNAPSHOT_SECTIONS, Registry, RegistryError

ALL = {'CHECKS': CHECKS, 'PLAN_BUILDERS': PLAN_BUILDERS, 'SNAPSHOT_SECTIONS': SNAPSHOT_SECTIONS, 'RENDERERS': RENDERERS}


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestRegistries(TransactionCase):
    """W0-B: Python-реєстри (MERGE.md §5.0) існують, окремі й розширювані без змін спільного коду."""

    def test_four_registries_are_separate(self):
        self.assertEqual(set(ALL), {'CHECKS', 'PLAN_BUILDERS', 'SNAPSHOT_SECTIONS', 'RENDERERS'})
        self.assertEqual(len({id(reg) for reg in ALL.values()}), 4)
        for name, reg in ALL.items():
            self.assertIsInstance(reg, Registry)
            self.assertEqual(reg.name, name)
            self.assertIs(getattr(registry, name), reg)

    def test_register_get_unregister_restore_state(self):
        for reg in ALL.values():
            before = (len(reg), reg.keys())
            reg.register('w0b_probe', len, sequence=5)
            self.assertIn('w0b_probe', reg)
            self.assertIs(reg.get('w0b_probe'), len)
            self.assertEqual(reg.items()[0], ('w0b_probe', len))  # sequence 5 — раніше за типові 100
            reg.unregister('w0b_probe')
            self.assertNotIn('w0b_probe', reg)
            self.assertIsNone(reg.get('w0b_probe'))
            self.assertEqual((len(reg), reg.keys()), before)

    def test_duplicate_replace_unknown(self):
        reg = Registry('probe')
        reg.register('a', 1)
        with self.assertRaises(RegistryError):
            reg.register('a', 2)
        reg.register('a', 2, replace=True)
        self.assertEqual(reg.get('a'), 2)
        with self.assertRaises(RegistryError):
            reg.unregister('b')
        with self.assertRaises(RegistryError):
            reg.register('', 1)

    def test_order_and_decorator(self):
        reg = Registry('probe')

        @reg.register('late', sequence=200)
        def late():
            return 'late'

        reg.register('first', 'x', sequence=10)
        reg.register('second', 'y', sequence=10)  # той самий sequence — за порядком реєстрації
        reg.register('mid', 'z')
        self.assertEqual(reg.keys(), ['first', 'second', 'mid', 'late'])
        self.assertEqual(list(reg), reg.keys())
        self.assertEqual(reg.values(), ['x', 'y', 'z', late])
        self.assertEqual(late(), 'late')  # декоратор повертає функцію без змін
        self.assertEqual(len(reg), 4)

    def test_snapshot_section_contract(self):
        section = registry.SnapshotSection(build=lambda site: {'n': 1}, apply=lambda site, data: None)
        SNAPSHOT_SECTIONS.register('w0b_probe', section)
        try:
            self.assertEqual(SNAPSHOT_SECTIONS.get('w0b_probe').build(None), {'n': 1})
        finally:
            SNAPSHOT_SECTIONS.unregister('w0b_probe')
