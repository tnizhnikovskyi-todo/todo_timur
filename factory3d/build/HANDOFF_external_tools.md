# Передача: поиск по GitHub и забор внешних находок

Состояние на 03.11.2026. Ветка `claude/charming-goldberg-03upz1`, коммит `9ab9b0f7` (плюс этот файл).
В `claude/factory3d-build` **ещё не влито**.

## Что выяснили

- Поиск по всему публичному GitHub работает через `gh api -X GET search/{repositories,code,issues,commits,users}`.
  API `repos/...` чужих репозиториев закрыт настройками сессии, но публичные репозитории читаются через git:
  `git ls-remote`, `git clone --depth 1 --filter=blob:none`.
- Запускать скачанный чужой код в облачной сессии система не даёт без разрешения пользователя (классификатор
  авто-режима, «Code from External»).

## Найдено и оценено

| Находка | Лицензия | Решение |
|---|---|---|
| `ChengyanOo/odoo-lens`: линтер и языковой сервер для Odoo 16–20 (неизвестные поля/модели/XML id, `depends`, `_sql_constraints`, `attrs`, `<tree>`) | нет | берём через `fetch`, проверка модуля перед тестами |
| `mart337i/odoo-skills`: справочник Odoo 19 (18 руководств), скиллы ревью и тестов | нет | берём через `fetch`; идеи ревью переписаны в наш чек-лист |
| `OCA/maintenance`, ветка 19.0: 20 модулей ТО (`maintenance_plan`, `maintenance_equipment_status`, `maintenance_location` и др.) | AGPL/LGPL | кандидат для `td_genset`, `factory3d_bms`, станков, сверить со SPEC |
| `OCA/queue`, ветка 19.0: `queue_job` | LGPL | кандидат для фоновой обработки телеметрии |
| `OCA/iot`: `iot_oca`, `iot_input_oca`, `iot_output_oca` (только 18.0, ветка 19.0 пустая) | AGPL | образец модели «устройство → входы/выходы» для `factory3d_telemetry` |
| `ivnvxd/mcp-server-odoo` | MPL-2.0 | на заметку, у нас есть odoo-mcp |
| `stanleykao72/claude-code-spec-workflow-odoo` | MIT | не берём: дублирует SPEC/ARCHITECTURE, тяжёлые агенты, заброшен с 09.2025 |

Ветка 19.0 есть также в `OCA/web`, `rest-framework`, `server-tools`, `connector`. Состав модулей там не проверяли.
Готовых связок Odoo с MQTT/OPC-UA/Modbus и three.js на GitHub почти нет, есть только мелкие и старые проекты.

Сравнение с нашими агентами: оркестрация у нас сильнее (менеджер → лидер → воркеры, состояние в файлах,
DEC, QA). Не хватало знаний Odoo 19 и автоматической проверки кода до тестов. Это и закрыли.

## Что сделано (коммит `9ab9b0f7`)

| Файл | Что |
|---|---|
| `factory3d/tools/external/README.md` | реестр находок и правило по лицензиям |
| `factory3d/tools/external/sources.tsv` | закреплённые коммиты: odoo-lens `2482f92`, odoo-skills `634b2db` |
| `factory3d/tools/external/fetch.sh` | качает источники в `vendor/` (вне git), идемпотентен. Проверен |
| `factory3d/tools/external/lens.sh` | `odoo-lens check` по модулям; Odoo из `ODOO_HOME` (по умолчанию `/home/user/odoo19`). Проверена только ветка «нет исходников» (exit 2) |
| `factory3d/build/REVIEW_CHECKLIST.md` | чек-лист приёмки под Odoo 19, своими словами |
| `.claude/agents/coder.md` | линтер перед тестами; справочник Odoo 19 по Grep |
| `factory3d/build/MODULE_LEAD.md` | `fetch.sh` при старте; чек-лист в приёмке |
| `CLAUDE.md` | раздел «Внешние находки» |
| `.gitignore`, `factory3d/tools/external/.gitignore` | `vendor/`, `factory3d/odoo_addons/.odoo-lens.json` |

Правило по лицензиям: MIT/BSD/Apache/LGPL/AGPL копируем вместе с `LICENSE`. Без лицензии не копируем,
закрепляем коммит, скачиваем `fetch.sh`, идеи пишем своими словами.

## Открыто: продолжить отсюда

1. **Разрешить запуск линтера.** Без разрешения `coder` пропускает шаг. Вариант: правило в `.claude/settings.json`,
   разрешающее только `factory3d/tools/external/lens.sh`. Затем первый прогон на `factory3d_iot_sim`
   (нужны исходники Odoo 19 в `ODOO_HOME`: `factory3d/tools/odoo/setup.sh` из ветки `claude/factory3d-build`).
2. **Влить ветку в `claude/factory3d-build`** (PR или мерж), иначе лидеры модулей изменений не увидят.
3. По желанию: сверить модули `OCA/maintenance` 19.0 со SPEC `td_genset` / `factory3d_bms` и решить,
   что взять готовым.

Промпт для нового чата: «Продолжи по `factory3d/build/HANDOFF_external_tools.md`, раздел „Открыто“».
