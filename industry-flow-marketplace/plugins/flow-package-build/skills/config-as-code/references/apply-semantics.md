# Семантика застосування (`apply.py` і режим `mcp-fallback`)

## Загальні правила
- **Upsert за xml-id**: є запис з таким xml-id -> порівняти й оновити лише змінені поля (`updated`/`unchanged`), немає -> створити
  з xml-id (`created`). Числових id немає.
- Порядок: модулі (`manifest`) -> файли `data_files` за номером `NN_` -> `res.config.settings`.
- `res.config.settings`: створити запис зі значеннями і викликати `execute()`. Побічні дії `execute()` (установка модулів за
  прапорцями, зміна груп) **не відтворюються** вручну; такі пункти позначають у CONFIG.md. Відкрите питання: чи `execute()`
  ідемпотентний для кожного налаштування -- перевіряє `CFG-idempotent`.
- `ir.config_parameter`: `set_param` за ключем.
- Запис, створений установкою, у режимі `new-version` видаляється лише рішенням людини; скіл `unlink` не викликає.
- Значення VP: `transform` з `vp-map.yaml` (мапа або identity); значення поза схемою відхиляє `validate` до запису.
- Read-back: кожний VP читається за якорем і порівнюється з `transform(answers)`.

## Режим `mcp-fallback` (немає локального Odoo)
Лише тестова база пакета з `odoo_connections`; `connection_id` у кожному виклику; після кожного виклику звірити `connection.db`.
Орієнтовна послідовність (параметри вказують: db -- з наряду, моделі/поля -- з `odoo_get_fields`):
1. `odoo_search_read` `ir.module.module` [name in M] -> `state`, `dependencies_id`.
2. Установка модулів -- `odoo_execute` метод `button_immediate_install` на знайдених записах (виконує людина або дозволено нарядом).
3. Пункти даних -- `odoo_search_read` за xml-id (`ir.model.data`), далі `odoo_create`/`odoo_write`; xml-id -- запис `ir.model.data`.
4. Налаштування -- `odoo_create` `res.config.settings` -> `odoo_execute` `execute`.
У звіті: `install-one-command: N/A (немає середовища)`; `CFG-install` -- `N/A`, не PASS. Точні сигнатури викликів `odoo-mcp`
не вигадувати -- взяти з `flow-core/references/odoo-bridge.md`, якщо його немає -- запитати AI-інженера.
