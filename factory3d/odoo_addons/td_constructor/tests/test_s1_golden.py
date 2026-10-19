import json

from odoo.tests import TransactionCase, tagged

from . import golden_s1


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestS1Golden(TransactionCase):
    """Золоті фікстури S1 (Python ↔ JS) не розійшлися з кодом: перегенерація — `python3 tests/golden_s1.py --write`."""

    def test_fixtures_match_code(self):
        for name, data in golden_s1.build().items():
            path = golden_s1.FIXTURES / (name + '.json')
            self.assertTrue(path.is_file(), "немає фікстури %s" % path)
            self.assertEqual(
                json.loads(path.read_text(encoding='utf-8')),
                json.loads(golden_s1.dump(data)),
                "%s.json застарів: python3 odoo_addons/td_constructor/tests/golden_s1.py --write" % name,
            )
