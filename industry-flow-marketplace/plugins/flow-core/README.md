# flow-core

Ядро флоу: цикл AI-кроку (черга Odoo, наряд, звіт, PR), оркестратор, стан і журнал, автоперевірка артефактів, CI та евали. Містить спільні конвенції пакета.

## Кроки флоу

Наскрізний: C-06 (цикл AI-кроку), C-05, C-07, C-08; вхід для всіх кроків флоу.

## Скіли

- `flow-step-runner` — цикл AI-кроку: взяти наряд із черги, виконати скіл, перевірити, PR і звіт у задачу
- `flow-orchestrator` — видає наряди за картками кроків, фіксує SHA входів, керує повторами й шлюзами
- `flow-state-keeper` — стан флоу й журнал у репозиторії та Odoo
- `flow-autocheck` — автоперевірка артефактів за checkHow картки
- `ci-pipeline-builder` — збирає CI для репозиторіїв пакета
- `eval-builder` — будує евали скілів і статистику за версіями

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Агенти плагіна
- Профільні виконавці `flow-executor-mail|-research|-outreach|-drive|-repo` (`agents/`): той самий виконавець + мінімальний набір конекторів за `access_profile` наряду (`step-skill-map.md`); без запису в Gmail/Drive/GitHub, окрім чернеток Gmail.
- `flow-core:flow-executor` (`agents/flow-executor.md`) — субагент-виконавець кроку: лише файли результату, читання odoo-mcp; без Bash, git, gh, запису в Odoo.
- `flow-core:flow-reviewer` (`agents/flow-reviewer.md`) — субагент-рецензент кроку: лише читання.
Їх використовує `flow-step-runner` (крок 0 перевіряє наявність).

## Конвенції

Цей плагін і є джерелом спільних конвенцій: `conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`, `odoo-bridge.md`, `flow-map.md`, `flow-step-run.md`, `flow-state.md`, `data-policy-template.md`, `pii-patterns.md`, `id-patterns.md`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії, якщо вони є (q02: на пілоті копій немає); єдиний виняток-читання проду — `prod-ro-<клієнт>` для `client-help-bot` (q37); будь-який агент — лише B-13/B-08a на `test-<клієнт>` (q01); повністю — `flow-core/references/data-and-connections.md` §3.6.

## Установка

```
claude plugin install flow-core@industry-flow
```

## Спільні references
`references/`: `conventions.md` (конвенції), `naryad-format.md` і `report-format.md` (наряд і звіт, `params`, `waiting_human`), `odoo-bridge.md` (читання/запис задач, рішення vs коментар, активності), `flow-map.md` (карта переходів), `flow-step-run.md` (шаблони задач), `flow-state.md` (стан і автоекспорт), `data-policy-template.md`, `pii-patterns.md`, `id-patterns.md`, `data-and-connections.md`. Технічні імена кастомних полів Odoo визначає C-00 (`flow/ODOO_SCHEMA.md`); до того — стоп і питання Тімліду.
