"""Чисті Python-сервіси конструктора (без ORM; їх тестують без бази).

Реєстри точок розширення — `registry.py` (`CHECKS`, `PLAN_BUILDERS`, `SNAPSHOT_SECTIONS`, `RENDERERS`). Файли слайсів
хвиль 1–2 підключені тут заздалегідь (W0-B): слайс править лише свій файл, а його реєстрації виконуються при імпорті.
"""

from . import registry

# S1 Структура місця
from . import addr

# S2 Зв'язок з Odoo
from . import capacity, putaway

# S3 Робота зі складом
from . import labels, metrics

# S4 Структура з Odoo, файли
from . import odoo_sync, tabular

# S5 Будівля, майстер, документи
from . import building, checks_building, rack_spec, render_docs
