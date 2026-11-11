# flow-package-build

Збірка тиражованого пакета: анкета, конфігурація як код, шаблони майстер-даних, агрегація гейтів, демо-база, реліз пакета.

## Кроки флоу

A-09, A-12, A-13, A-14, A-15 (+A-22), A-18.

## Скіли

- `questionnaire-builder` — анкета для клієнта
- `config-as-code` — конфігурація Odoo як код
- `master-data-template-builder` — шаблони майстер-даних
- `gates-aggregator` — зведення результатів гейтів
- `demo-base-builder` — демо-стенд пакета (A-15) і база зрізу для гарячого ліда (A-22; без емуляції Studio/`x_`)
- `package-release-builder` — складання релізу пакета

У 0.2.0: ядро пакета — Odoo 19 CE, Enterprise — окремі мости `td_*_ee`; CI й перевірки на обох редакціях (`references/editions-and-bridges.md`); без EE-доступу EE-перевірки — WARN/«не перевірено».

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Конвенції

Конвенції пакета (формат наряду, формат звіту, правила даних і `connection_id`) лежать у `flow-core/references/` (`conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`, `odoo-bridge.md`, `flow-map.md`, `flow-step-run.md`, `flow-state.md`, `data-policy-template.md`, `pii-patterns.md`, `id-patterns.md`) і тут не дублюються. Потрібен встановлений `flow-core`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії, якщо вони є (q02: на пілоті копій немає); єдиний виняток-читання проду — `prod-ro-<клієнт>` для `client-help-bot` (q37); будь-який агент — лише B-13/B-08a на `test-<клієнт>` (q01); повністю — `flow-core/references/data-and-connections.md` §3.6.

## Установка

```
claude plugin install flow-package-build@industry-flow
```

## Спільні references
`references/`: `master-data-format.md` (контракт A-13/B-06, копія з позначкою джерела), `demo-readme-template.md` (A-15), `checks-template.md` (A-14).
