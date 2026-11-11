# flow-client-delivery

Впровадження пакета в клієнта: fit-gap, SOW, виконання ранбука, міграція даних, підтримка, оновлення пакета в клієнта.

## Кроки флоу

B-02, B-03, B-04, B-06, B-07 (бот-помічник), B-09/B-10, B-11 (+B-13).

## Скіли

- `package-fit-gap` — fit-gap пакета проти вимог клієнта
- `package-sow-builder` — SOW на впровадження пакета
- `runbook-executor` — виконання ранбука й звірка конфігурації
- `client-data-migrator` — міграція даних клієнта в тестову базу

У 0.2.0: редакція клієнта (CE/EE) і реєстр відкинутого враховуються в fit-gap і SOW (`references/client-edition-and-rejected.md`).
- `client-help-bot` — бот-помічник користувачів клієнта (B-07; після go-live — відповіді-чернетки за config-log, матеріалами й read-only читанням проду `prod-ro-<клієнт>`; виняток q37, лише цей скіл)
- `support-desk` — тріаж і відповіді підтримки
- `package-upgrade-runner` — оновлення пакета в клієнта

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Конвенції

Конвенції пакета (формат наряду, формат звіту, правила даних і `connection_id`) лежать у `flow-core/references/` (`conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`, `odoo-bridge.md`, `flow-map.md`, `flow-step-run.md`, `flow-state.md`, `data-policy-template.md`, `pii-patterns.md`, `id-patterns.md`) і тут не дублюються. Потрібен встановлений `flow-core`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії, якщо вони є (q02: на пілоті копій немає); єдиний виняток-читання проду — `prod-ro-<клієнт>` для `client-help-bot` (q37); будь-який агент — лише B-13/B-08a на `test-<клієнт>` (q01); повністю — `flow-core/references/data-and-connections.md` §3.6.

## Установка

```
claude plugin install flow-client-delivery@industry-flow
```

## Спільні references
`references/`: `triage-routes.md` (тип -> маршрут для B-09/B-10/B-13), `support-report-template.md` (звіт SLA B-10).

