# flow-research

Дослідження до рішення «будуємо пакет?»: скоринг галузей, аналіз минулих проєктів, вибірка сегмента, мапа концепції, прототип і тест попиту.

## Кроки флоу

A-01, A-04, A-05, A-20, A-21, A-23 (+ список лідів B-01).

## Скіли

- `industry-scoring` — скоринг галузей за odb-catalog
- `past-projects-analyzer` — аналіз матеріалів минулих проєктів
- `segment-selector` — вибірка компаній сегмента: еталонні клієнти, ліди, розсилка
- `concept-mapper` — мапа концепції пакета
- `prototype-builder` — прототип у стилі Odoo 19
- `demand-test-runner` — тест попиту й порівняння з порогами

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Конвенції

Конвенції пакета (формат наряду, формат звіту, правила даних і `connection_id`) лежать у `flow-core/references/` (`conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`) і тут не дублюються. Потрібен встановлений `flow-core`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії.

## Установка

```
claude plugin install flow-research@industry-flow
```
