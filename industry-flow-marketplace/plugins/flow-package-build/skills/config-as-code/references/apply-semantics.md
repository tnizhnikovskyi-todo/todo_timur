# Семантика застосування (режим `mcp-fallback`; у 0.1 -- єдиний)

Скриптів `apply.py`/`install.sh` немає: агент виконує кроки сам. Загальні правила викликів `odoo-mcp` (явний `connection_id`,
перевірка `connection`, технічні користувачі) -- `flow-core/references/odoo-bridge.md` §1; тут лише виклики для `ir.module.module`,
`ir.model.data`, `res.config.settings`, яких у ньому немає.

## Передумова: чиста база
Базу створює/скидає людина або C-00 **до** запуску; агент через odoo-mcp це зробити не може. Є `ir.model.data` з
`module = td_config` або встановлені модулі поза базовим набором з M -> `build`: `waiting_human` (SKILL, Крок 0);
`fix`: upsert дозволений, у лозі «база не чиста (fix)». Те саме для 2-ї спроби `build`: стан бази не скидається сам.

## Загальні правила
- **Upsert за xml-id**: є запис -> порівняти й оновити лише змінені поля (`updated`/`unchanged`), немає -> створити з xml-id
  (`created`). Числових id немає. Запис, створений установкою, видаляє лише людина; `unlink` не викликається.
- Порядок: модулі (`manifest`) -> файли `data_files` за `NN_` -> `res.config.settings`.
- `ir.config_parameter`: перевірити/записати за `key`.
- Значення VP: `transform` з `vp-map.yaml`; значення поза схемою відхиляє `CFG-schema` до запису.

## Кроки й приклади викликів (`connection_id` -- з наряду, тут `<id>`)
1. Модулі: `odoo_search_read` model `ir.module.module`, domain `[["name","in",["stock","mrp"]]]`, fields `["name","state","dependencies_id"]`,
   `connection_id: <id>`. Перед цим список модулів оновлено (`button_immediate_install` для не встановлених вимагає запису в списку).
2. Установка: `odoo_execute` model `ir.module.module`, method `button_immediate_install`, ids знайдених із `state = "uninstalled"`
   (за одним модулем у порядку `manifest`), `connection_id: <id>`. Дозволено явно для тестової бази пакета (не прод, даних клієнта
   немає). Після виклику (можливе перезавантаження реєстру/тайм-аут) перечитати `state`; не `installed` -> `waiting_human`
   з текстом «встановити модуль <name> у базі <alias> вручну», або `escalated`, якщо помилка в `ERROR|Traceback`.
3. Дані: `odoo_search_read` model `ir.model.data`, domain `[["module","=","td_config"],["name","=","<slug>"]]`, fields `["res_id","model"]`.
   Немає -> `odoo_create` цільова модель зі значеннями, потім `odoo_create` `ir.model.data` `{module: "td_config", name: "<slug>", model, res_id}`;
   є -> `odoo_search_read` за `res_id`, порівняти, `odoo_write` лише змінені поля.
4. Settings: `odoo_create` `res.config.settings` зі значеннями -> `odoo_execute` method `execute` на створеному id.
   Settings, що через `group_*`/`module_*` ставлять модулі, застосовувати **окремим першим пунктом** (реєстр перезавантажиться),
   а ці модулі вносити в `manifest` явно; побічні дії `execute()` вручну не відтворювати -- позначити в CONFIG.md.
5. Read-back: для кожного VP -- `odoo_search_read` за якорем з `vp-map.yaml` (`config-package-format.md`, «Формат якоря»), порівняти
   з `transform(answers.example.yaml)`.

## Ідемпотентність у fallback
`CFG-idempotent` = **другий прохід порівняння** за xml-id (кроки 3-5 без запису): розбіжностей і відсутніх записів немає -> PASS;
є -> FAIL; повторний `execute()` не викликається. `CFG-readback` обов'язковий. Лічильники `{created, updated, unchanged, manual,
errors}` веде агент у `install-log.md`.
