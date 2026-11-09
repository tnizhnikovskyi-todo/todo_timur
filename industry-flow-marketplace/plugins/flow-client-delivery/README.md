# flow-client-delivery

Впровадження пакета в клієнта: fit-gap, SOW, виконання ранбука, міграція даних, підтримка, оновлення пакета в клієнта.

## Кроки флоу

B-02, B-03, B-04, B-06, B-09/B-10, B-11 (+B-13).

## Скіли

- `package-fit-gap` — fit-gap пакета проти вимог клієнта
- `package-sow-builder` — SOW на впровадження пакета
- `runbook-executor` — виконання ранбука й звірка конфігурації
- `client-data-migrator` — міграція даних клієнта в тестову базу
- `support-desk` — тріаж і відповіді підтримки
- `package-upgrade-runner` — оновлення пакета в клієнта

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Конвенції

Конвенції пакета (формат наряду, формат звіту, правила даних і `connection_id`) лежать у `flow-core/references/` (`conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`) і тут не дублюються. Потрібен встановлений `flow-core`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії.

## Установка

```
claude plugin install flow-client-delivery@industry-flow
```
