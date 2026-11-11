# flow-research

Дослідження до рішення «будуємо пакет?»: скоринг галузей, аналіз минулих проєктів, вибірка сегмента, мапа концепції, прототип і тест попиту.

## Кроки флоу

A-01, A-02b, A-03b, A-03c, A-04, A-05, A-20, A-20b, A-20c, A-21, A-21c, A-23 (+ список лідів B-01). Порядок кроків — `flow-core/references/flow-map.md`.

## Скіли

- `industry-scoring` — скоринг галузей за odb-catalog
- `past-projects-analyzer` — аналіз матеріалів минулих проєктів
- `segment-selector` — вибірка компаній сегмента: еталонні клієнти, ліди, розсилка
- `owner-questionnaire` (A-02b, нова) — анкета власника ≤20 хв: `prepare` → `validate` → `amend`
- `industry-deep-dive` (A-03b, нова) — глибокий аналіз галузі й конкурентів, контрольна точка K1 (відповіді власника, не кнопка)
- `reuse-modules` (A-03c, нова) — готові модулі ToDo у збірку: `inventory` → `session` → `decide`; гейт «беремо / адаптуємо / ні»
- `concept-mapper` — концепція пакета (A-20): функції, екрани, сценарії, OWNER-BRIEF, BOX, SALES, REJECTED
- `completeness-audit` (A-20b, нова) — аудит повноти концепції 5 ролями, прогалини `G-xx`
- `concept-presentation` (A-20c, нова) — сторінка для власника (один Artifact, 3 сторінки); єдиний гейт концепції
- `prototype-builder` — реальний зріз Odoo 19 на модулях `td_*` з живим записом і `facts.json` (А-21; HTML-оболонки `mock` немає)
- `showcase-content` (A-21c, нова) — продаючі матеріали: відео, SHOW, бренд ToDo
- `demand-test-runner` — тест попиту й порівняння з порогами

Профілі доступу виконавців: `research-internal` (A-03b, A-03c; читання внутрішніх даних ToDo за анкетою) і `content` (A-21c; виконавець — контент-менеджер, `executor: any`). Рішення людини: анкета A-02b, K1, сесія й гейт A-03c, гейт концепції A-20c, зразок і гейт A-21, гейт A-21c.

(Тексти скілів — у `skills/<скіл>/SKILL.md`.)

## Конвенції

Конвенції пакета (формат наряду, формат звіту, правила даних і `connection_id`) лежать у `flow-core/references/` (`conventions.md`, `naryad-format.md`, `report-format.md`, `data-and-connections.md`, `odoo-bridge.md`, `flow-map.md`, `flow-step-run.md`, `flow-state.md`, `data-policy-template.md`, `pii-patterns.md`, `id-patterns.md`) і тут не дублюються. Потрібен встановлений `flow-core`.

Коротко: кожен крок — наряд (задача Odoo) із YAML-блоком у `description`; результат — PR у GitHub; звіт — у задачу Odoo; рішення людини — кнопка в задачі; кожен виклик `odoo-mcp` — з явним `connection_id` з наряду; дані клієнта — лише тестові бази й знеособлені копії, якщо вони є (q02: на пілоті копій немає); єдиний виняток-читання проду — `prod-ro-<клієнт>` для `client-help-bot` (q37); будь-який агент — лише B-13/B-08a на `test-<клієнт>` (q01); повністю — `flow-core/references/data-and-connections.md` §3.6.

## Установка

```
claude plugin install flow-research@industry-flow
```

## Спільні references
`references/`: `sources-format.md`, `concept-templates.md`, `odoo19-ui-kit.md`, `PAGE-CONTRACT.md` (контракт сторінки власника), `completeness-checklist.md`, `needs-sources-catalog.md` (каталог джерел потреб), `brand-todo/` (бренд ToDo), `templates/` (шаблони FUNCTIONAL-MAP, OWNER-BRIEF, BOX, SALES, REJECTED, COMPLETENESS, K1 та ін.).
