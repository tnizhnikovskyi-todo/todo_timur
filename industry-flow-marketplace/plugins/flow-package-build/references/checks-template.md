# Шаблон `package/templates/CHECKS.md` (крок A-14)

Копіюється в `package/templates/CHECKS.md` на першому запуску A-14 (`gates-aggregator`); результат — `package/CHECKS.md`. Заголовки — grep-контракт для A-15 (SHA), A-17, A-18.

## Ревізія package/ (commit SHA)
`SHA: <40 hex>` — на якому виконано гейти (мітка — `flow-core/references/id-patterns.md`).

## Прогін C-03
`SHA прогону: <sha>` · статус: `success|failure|pending` · посилання на прогін. Для SHA гейтів або найближчого предка без змін у `package/addons/` і `package/config/`.

## Гейти
| гейт | команда або скіл | вердикт | примітка |
|---|---|---|---|
| pr-review | `odoo19-mvp-build:pr-review` | APPROVE / правки / не виконано | |
| config-review | `odoo19-mvp-build:config-review` | APPROVE / правки / не виконано | |
| security-review | `odoo19-mvp-build:security-review` | APPROVE / правки / не виконано | |
| odoo19-lint | `boost:odoo19-lint` | APPROVE / правки / не виконано | |
| track-convergence | `odoo19-mvp-build:track-convergence` | APPROVE / правки / не виконано: гейти pr-review/config-review не APPROVE | виконується лише після APPROVE pr-review і config-review |

## Правки
| № | опис | код кроку повернення (A-11 / A-12 / A-13) | джерело |
|---|---|---|---|
Порожньо — «немає». Кожна правка має код A-11, A-12 або A-13; джерело — гейт або дефект з A-15/A-16/A-17/A-18 (`defects.md`, `release-defects.md`).

## Зведений вердикт
`APPROVE` (усі п'ять APPROVE, правок немає) або `правки` (крок завершується переходом за кодами правок, гейти на незмінених входах не повторюються). Лічильник циклів A-11/12/13 -> A-14 веде оркестратор.
