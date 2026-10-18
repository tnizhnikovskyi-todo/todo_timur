"""AC-71: data-файли з макета збігаються з генератором. Запуск: pytest, поза Odoo.

    cd factory3d && python -m pytest odoo_addons/td_fire_safety/tests/test_data_sync.py -q

Не імпортує odoo; у tests/__init__.py не підключається.
"""
import importlib.util
import os
import tempfile
import unittest

MODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GEN_PATH = os.path.join(MODULE_DIR, 'tools', 'gen_data.py')
DATA_DIR = os.path.join(MODULE_DIR, 'data')

# SPEC §5.2: записів у кожному згенерованому файлі
EXPECTED_ROWS = {
    'td.fire.norm.csv': 27, 'td_fire_panel.xml': 5, 'td.fire.zone.csv': 35, 'td_fire_system.xml': 3,
    'td.fire.smoke.zone.csv': 8, 'td.fire.device.csv': 353, 'td.fire.exit.csv': 12, 'td_fire_route.xml': 32,
    'td_fire_drill_template.xml': 9, 'td_source_data.xml': 2, 'td_signal_data.xml': 54,
}


def _load_generator():
    spec = importlib.util.spec_from_file_location('f3d_fire_gen_data', GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDataSync(unittest.TestCase):

    def test_generated_equals_repo(self):
        gen = _load_generator()
        root = gen.DEFAULT_ROOT
        if not os.path.exists(os.path.join(root, 'dist', 'odoo_demo.json')):
            self.skipTest("немає dist/odoo_demo.json (модуль поза репозиторієм макета)")
        with tempfile.TemporaryDirectory() as out:
            gen.main(['--root', root, '--out', out])
            self.assertEqual(sorted(os.listdir(out)), sorted(EXPECTED_ROWS))
            for name in os.listdir(out):
                with open(os.path.join(out, name), 'rb') as generated, \
                        open(os.path.join(DATA_DIR, name), 'rb') as stored:
                    self.assertEqual(generated.read(), stored.read(),
                                     "%s розходиться з макетом: перегенеруйте tools/gen_data.py" % name)

    def test_expected_counts(self):
        gen = _load_generator()
        if not os.path.exists(os.path.join(gen.DEFAULT_ROOT, 'dist', 'odoo_demo.json')):
            self.skipTest("немає dist/odoo_demo.json")
        counts = {}
        gen.build(gen.DEFAULT_ROOT, counts)
        self.assertEqual(counts, EXPECTED_ROWS)


if __name__ == '__main__':
    unittest.main()
