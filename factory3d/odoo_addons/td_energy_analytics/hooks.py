"""post_init_hook / uninstall_hook (W4_SPEC 5.4, 5.5). Каркас: тіло пише воркер A.

Контракт для воркерів (імена функцій фіксовані; ті самі функції викликає міграція `19.0.1.0.0`):
`_load_areas(env)` (читає `data/td_energy_area.csv`, ідемпотентно), `_assign_areas(env)` (читає `data/area_map.csv`;
`area_id` лише там, де порожній), `_fill_alloc_product(env)` (SQL-пакети 5 000).
Драйвери, параметри й крони — XML; базу й бюджет установка не створює.
"""


def post_init_hook(env):
    """5.4: `_load_areas` → `_assign_areas` → `_fill_alloc_product` (ідемпотентні)."""


def uninstall_hook(env):
    """5.5: видаляє власні крон-записи й параметри `td.energy_analytics.*`."""
