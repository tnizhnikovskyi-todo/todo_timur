"""Захист від розходження data-файлів з макетом (SPEC §13.1). Запуск: pytest, поза Odoo.

Не імпортує odoo; у tests/__init__.py не підключається.
"""
import importlib.util
import os
import tempfile
import unittest

MODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GEN_PATH = os.path.join(MODULE_DIR, 'tools', 'gen_data.py')
DATA_DIR = os.path.join(MODULE_DIR, 'data')


def _load_generator():
    spec = importlib.util.spec_from_file_location('f3d_gen_data', GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDataSync(unittest.TestCase):

    def test_csv_matches_macro(self):
        gen = _load_generator()
        root = gen.DEFAULT_ROOT
        if not os.path.exists(os.path.join(root, 'dist', 'odoo_demo.json')):
            self.skipTest("немає dist/odoo_demo.json (модуль поза репозиторієм макета)")
        with tempfile.TemporaryDirectory() as out:
            gen.main(['--root', root, '--out', out])
            self.assertEqual(sorted(os.listdir(out)), sorted(gen.build(root)))
            for name in os.listdir(out):
                with open(os.path.join(out, name), 'rb') as generated, \
                        open(os.path.join(DATA_DIR, name), 'rb') as stored:
                    self.assertEqual(generated.read(), stored.read(),
                                     "%s розходиться з макетом: перегенеруйте tools/gen_data.py" % name)

    def test_expected_counts(self):
        gen = _load_generator()
        if not os.path.exists(os.path.join(gen.DEFAULT_ROOT, 'dist', 'odoo_demo.json')):
            self.skipTest("немає dist/odoo_demo.json")
        files = gen.build(gen.DEFAULT_ROOT)
        rows = {name: text.count('\n') - 1 for name, text in files.items()}
        self.assertEqual(rows['f3d.equipment.passport.csv'], 93)
        self.assertEqual(rows['f3d.equipment.spec.csv'], 999)
        self.assertEqual(rows['f3d.equipment.source.csv'], 252)
        self.assertEqual(rows['scene_equipment_codes.csv'], 210)
        self.assertEqual(rows['scene_employee_codes.csv'], 35)
        self.assertEqual(rows['scene_locations.csv'], 689)
