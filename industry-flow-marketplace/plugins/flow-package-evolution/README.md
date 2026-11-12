# flow-package-evolution

Розвиток пакета: метрики використання, тріаж беклогу, чернетки рішень Власника продукту, міграція на нову версію Odoo.

## Кроки флоу

D-01, D-02, D-03; чернетки рішень A-17, D-04, D-05 (A-07 — кнопка-вето власника без чернетки, за рекомендацією AI в `demand/results.md`).

## Скіли

- `package-usage-metrics` — лічильники використання пакета
- `backlog-triage` — тріаж беклогу
- `product-decision-drafter` — чернетки рішень Власника продукту
- `odoo-version-migrator` — міграція пакета на нову версію Odoo

У 0.2.0: реєстр відкинутого (`flow-core/references/rejected-register.md`) у тріажі беклогу (D-02); ліцензія модулів — LGPL-3 за замовчуванням, остаточно — рішення власника.

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Конвенції

Конвенції пакета (формат наряду, формат звіту, правила даних і `connection_id`) лежать у `flow-core/references/` (`conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`, `odoo-bridge.md`, `flow-map.md`, `flow-step-run.md`, `flow-state.md`, `data-policy-template.md`, `pii-patterns.md`, `id-patterns.md`) і тут не дублюються. Потрібен встановлений `flow-core`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії, якщо вони є (q02: на пілоті копій немає); єдиний виняток-читання проду — `prod-ro-<клієнт>` для `client-help-bot` (q37); будь-який агент — лише B-13/B-08a на `test-<клієнт>` (q01); повністю — `flow-core/references/data-and-connections.md` §3.6.

## Установка

```
claude plugin install flow-package-evolution@industry-flow
```
