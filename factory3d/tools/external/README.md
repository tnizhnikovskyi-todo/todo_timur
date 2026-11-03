# Внешние находки

Реестр полезного, найденного на GitHub и в других открытых источниках: что взяли, откуда, на каких условиях.
Каждая новая находка — строка в таблице ниже, а если её код нужен в работе, — ещё и строка в `sources.tsv`.

## Как забираем

Сначала смотрим лицензию (файл `LICENSE` и поле license в GitHub).

| Лицензия | Что делаем |
|---|---|
| MIT, BSD, Apache-2.0, LGPL-3, AGPL-3 (OCA) | Можно копировать в репозиторий: модули Odoo — в `factory3d/odoo_addons/`, прочее — сюда. Рядом кладём `LICENSE` и строку в реестре (источник, коммит). |
| Нет лицензии | Все права у автора: текст и код **не копируем**. Закрепляем коммит в `sources.tsv`, `fetch.sh` скачивает его в `vendor/` (в git не попадает). Идеи переписываем своими словами в наши документы. |

- `fetch.sh [имя...]` — скачать или обновить до закреплённого коммита (идемпотентно).
- Обновление находки — новый коммит в `sources.tsv` после проверки, что изменилось.
- Запуск скачанного кода в облачной сессии требует разрешения пользователя (правило в настройках Claude Code).

## Реестр

| Находка | Лицензия | Как используем | Где у нас |
|---|---|---|---|
| [ChengyanOo/odoo-lens](https://github.com/ChengyanOo/odoo-lens) — линтер и языковой сервер для модулей Odoo 16–20 | нет | `fetch`; проверка модуля перед тестами | `lens.sh`, `.claude/agents/coder.md`, `build/REVIEW_CHECKLIST.md` §0 |
| [mart337i/odoo-skills](https://github.com/mart337i/odoo-skills) — скиллы Claude Code: справочник Odoo 19, ревью, тесты | нет | `fetch`; справочник `skills/odoo-19.0/references/` читать Grep'ом по теме; идеи ревью — в наш чек-лист | `build/REVIEW_CHECKLIST.md` |
| [OCA/maintenance](https://github.com/OCA/maintenance) ветка 19.0 — 20 модулей ТО (`maintenance_plan`, `maintenance_equipment_status`, …) | AGPL-3 / LGPL-3 | кандидат для `td_genset`, `factory3d_bms`, станков; сверить с SPEC перед решением | — |
| [OCA/queue](https://github.com/OCA/queue) ветка 19.0 — `queue_job` | LGPL-3 | кандидат для фоновой обработки телеметрии | — |
| [OCA/iot](https://github.com/OCA/iot) — `iot_oca`, `iot_input_oca`, `iot_output_oca` (только ветка 18.0) | AGPL-3 | образец модели «устройство → входы/выходы» для `factory3d_telemetry`; на 19.0 не перенесён | — |
| [ivnvxd/mcp-server-odoo](https://github.com/ivnvxd/mcp-server-odoo) — MCP-сервер Odoo | MPL-2.0 | на заметку; у нас уже есть коннектор odoo-mcp | — |
| [stanleykao72/claude-code-spec-workflow-odoo](https://github.com/stanleykao72/claude-code-spec-workflow-odoo) | MIT | не берём: дублирует SPEC/ARCHITECTURE, тяжёлые агенты, не обновлялся с 09.2025 | — |
