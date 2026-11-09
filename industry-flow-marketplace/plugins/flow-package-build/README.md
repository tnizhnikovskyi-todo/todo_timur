# flow-package-build

Збірка тиражованого пакета: анкета, конфігурація як код, шаблони майстер-даних, агрегація гейтів, демо-база, реліз пакета.

## Кроки флоу

A-09, A-12, A-13, A-14, A-15 (+A-22), A-18.

## Скіли

- `questionnaire-builder` — анкета для клієнта
- `config-as-code` — конфігурація Odoo як код
- `master-data-template-builder` — шаблони майстер-даних
- `gates-aggregator` — зведення результатів гейтів
- `demo-base-builder` — збірка демо-бази
- `package-release-builder` — складання релізу пакета

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Конвенції

Конвенції пакета (формат наряду, формат звіту, правила даних і `connection_id`) лежать у `flow-core/references/` (`conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`) і тут не дублюються. Потрібен встановлений `flow-core`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії.

## Установка

```
claude plugin install flow-package-build@industry-flow
```
