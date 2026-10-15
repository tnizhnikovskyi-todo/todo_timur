# f3d_collector_mc

Пакет плагінів колектора factory3d (`services/collector`) для модуля Odoo `factory3d_machine_connect`:

- `opcua` — OPC UA (asyncua): стани верстатів HOMAG, завдання (`JobManagement`), події, виклики методів;
- `rest_vendor` — REST-адаптери `woodstore` (портал STORETEQ), `cutopt` (оптимізатор розкрою), `generic`.

Специфікація: `factory3d/docs/modules/factory3d_machine_connect/SPEC.md` §0.2, §8.
Плагіни реєструються через entry points `factory3d_collector.plugins` / `factory3d_collector.rest_vendors`.

## Установка в образ колектора

    pip install -r requirements.txt && pip install --no-deps .

Версії закріплені (asyncua 1.1.6 = емулятор). Файл `f3d_collector_mc/cmdtext.py` — побайтова копія
`odoo_addons/factory3d_machine_connect/tools/commands.py` (R-21, без імпортів Odoo).

## Стан

W0: каркас пакета (`pyproject.toml`, `requirements.txt`, `__init__.py`). Модулі плагінів — W7.

## Тести

    pytest services/collector_plugins/machine_connect -m "not stand"
