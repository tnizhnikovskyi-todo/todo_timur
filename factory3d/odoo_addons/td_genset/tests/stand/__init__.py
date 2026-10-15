# Part of td_genset (ToDo). Власник: W0. Стендові тести W5 — файли tests/stand/test_w5_stand_*.py
# імпортуються автоматично (будь-яка кількість файлів, без правок цього __init__); tests/__init__.py
# робить «from .stand import *», щоб завантажувач тестів Odoo бачив модулі test_* на рівні tests.
import importlib
import pkgutil

__all__ = []
for _module_info in pkgutil.iter_modules(__path__):
    if _module_info.name.startswith('test_w5_stand_'):
        globals()[_module_info.name] = importlib.import_module('%s.%s' % (__name__, _module_info.name))
        __all__.append(_module_info.name)
