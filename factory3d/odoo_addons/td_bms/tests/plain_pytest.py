"""Плагін pytest для тестів без Odoo (`test_data_sync.py`): файл завантажується як окремий модуль, без імпорту
пакета `factory3d_bms` (його `__init__` потребує `odoo`). Підключається через `pytest.ini` (`-p plain_pytest`)."""

import importlib.util

import pytest


class PlainModule(pytest.Module):
    def _getobj(self):
        name = "f3d_bms_plain_" + self.path.stem
        spec = importlib.util.spec_from_file_location(name, self.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def pytest_pycollect_makemodule(module_path, parent):
    if module_path.name == "test_data_sync.py":
        return PlainModule.from_parent(parent, path=module_path)
    return None


def pytest_collect_directory(path, parent):
    """Каталоги з `__init__.py` — звичайні `Dir`, а не `Package` (інакше pytest імпортує `__init__.py` пакета)."""
    if (path / "__init__.py").exists():
        return pytest.Dir.from_parent(parent, path=path)
    return None
