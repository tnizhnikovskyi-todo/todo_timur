# Шаблон package/templates/ci-workflow.md (перший запуск C-03)

Файл-опис CI для людей (Тімлід, PM). Створюється при першому запуску, у режимі `update` — оновлюється разом із `ci.yml`.
Розділи (заголовки обов'язкові):

## Тригери
Які зміни що запускають (таблиця: шлях -> job). Гілки `main`, `upgrade/**`. Ручний `workflow_dispatch` і його inputs
(`references/ci-contract.md`).

## Вибір версії Odoo
Порядок джерел і поведінка при непідтримці (`references/odoo-version-resolve.md`). Поточний стан підтримки N — з C-00.

## Jobs
Перелік job'ів, команди з `tools/odoo/` (дослівно), що вважається червоним (`references/test-verdict-rules.md`), зразок рядка підсумку
`run_tests.sh`.

## Версія 2 (знеособлена копія)
Є/немає вхід C-09; якщо немає — «не генерується».

## Умови зеленого
Перелік умов, за яких `ci` зелений; N/A-job'и з причинами (`config-matrix`, `tours`, `self-test`).

## Дії людини
Required status check `ci` для `main` (дата), секрети `ODOO_FLOW_*`, видалення пробних гілок `flow/C-03-probe-*`.

## Відкриті питання
Формат підсумку run_tests.sh, параметр версії Odoo, формат REGISTRY.md, місце фікстур self-test.
