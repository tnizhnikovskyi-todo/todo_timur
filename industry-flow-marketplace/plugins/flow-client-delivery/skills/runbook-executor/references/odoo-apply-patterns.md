# ORM-патерни застосування через odoo-mcp (Odoo 19)

Статус: ЧЕРНЕТКА, не звірено з документацією Odoo 19. Перед першим використанням — `boost:source-check`;
непідтверджене -> «очікує: виконує людина». Кожен виклик — з явним `connection_id`; після кожного перевірити
`connection.db`.

## Загальний цикл
1. Знайти ціль: `odoo_search_read` (модель, домен за якорем, `fields`, `limit`).
2. Записати: `odoo_write` (ids, vals) або `odoo_execute` (метод).
3. Прочитати назад: той самий `odoo_search_read`; порівняти зі значенням з `answers.yaml` (типи: bool, число,
   many2one -> id/xml_id, selection -> ключ).
4. Записати рядок `CL-NNN` (див. `config-log-format.md`).

## Патерни
- **Запис за xml_id:** `ir.model.data` (`module`, `name`) -> `res_id` -> `odoo_write` на цільовій моделі.
- **`res.config.settings`:** створення wizard-запису (`odoo_create`) із потрібними полями, далі `odoo_execute`
  методу `execute`; read-back — з цільових моделей/параметрів, а не з wizard (його значення тимчасові).
- **`ir.config_parameter`:** пошук за `key`, запис `value` (рядок); секретні ключі — «очікує: виконує людина».
- **Установка модуля:** `odoo_execute` `button_immediate_install` на запису `ir.module.module` (лише `uninstalled`,
  по одному); read-back `state`, `latest_version` (версія в БД; `installed_version` — лише маніфест на диску).
- **Групи:** `odoo_search_read` на `res.groups` (xml_id через `ir.model.data`). Ім'я поля груп на `res.users` у Odoo 19 перейменовано: ПЕРЕД першим викликом `odoo_get_fields` на `res.users` і підтвердити його (не вгадувати `groups_id`); далі `search_count([('<поле груп>','in',[gid]),('share','=',False)])`. Не підтвердилось — «очікує: виконує людина».

## НЕ через ORM
Секрети й ключі інтеграцій; майстри з побічними діями (імпорт, розсилки, закриття періодів); створення/зміна
користувачів; видалення й архівування; будь-що в прод-базі.
