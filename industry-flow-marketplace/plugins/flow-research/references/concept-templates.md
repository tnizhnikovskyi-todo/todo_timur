# Шаблони концепції пакета (A-20): `concept/*` і `research/{OWNER-BRIEF,BOX,SALES,REJECTED}.md`

Спільні для `concept-mapper` (A-20), `completeness-audit` (A-20b), `concept-presentation` (A-20c), `prototype-builder` (A-21), `demand-test-runner` (A-23) і ТР (A-08).
**Еталон колонок і скрипт — `skills/concept-mapper/references/template/` і `check_concept.py`**; при розбіжності діють вони. Копіюються в `docs/industries/<галузь>/concept/` (або `_template/concept/`).
Каркаси `research/*.md` — `templates/{OWNER-BRIEF,BOX,SALES,REJECTED}.tpl.md` (поруч). **Заголовки `##` — контракт скрипта (CM-files, CM-research), не змінювати.**

## ID і джерела
- ID: `ROLE-NN`, `PAIN-NN`, `F-NN`, `S-NN`, `SC-NN`; двозначний мінімум, наскрізні, не перевикористовуються; зникнення ID між версіями — FAIL `CM-ids`. Не `R-/B-/P-`.
- Джерело болю — `<файл>§<заголовок>` (`skills/concept-mapper/references/source-anchors.md`): `briefing.md`, `past-projects.md`, `sessions/protocol-<ід>-<дата>.md`, `K1.md` / `OWNER-INTAKE.md` (тип `owner-decision`, доказовість не підвищується). Цитата — дослівна, ≤25 слів, знеособлена; у джерелі без назв клієнтів, ПІБ, контактів, сум.
- Числа в `research/*.md` і `concept/*` — лише з `research/facts.yaml` з маркером `<!--fact:ключ-->`.

## concept/features.md — обов'язкові `##`
`## Ролі` · `## Болі` · `## Функції` · `## Поза концепцією` · `## Відкриті питання`
- Ролі: `ID | Роль | Що робить | Джерело`; роль-покупець — позначка `[покупець]` у колонці «Роль».
- Болі: `ID | Роль | Біль | Джерело | Цитата` (5 колонок).
- Функції: `ID | Функція | Роль | Біль | Джерел N | Екран | Статус` (≥6 колонок; «Джерел N» = різних записів джерел по болях функції; статус: порожньо | `інтерес: є/немає/не тестувалась` | `знято: причина` | `owner-decision`).
- Поза концепцією: `Що | Причина` (біль без функції; відкинуте — посилання на `research/REJECTED.md`).
- Відкриті питання: `№ | Мітка [анкета/K1/гейт] | Питання | Рекомендація AI | Замовчування`; на гейт ≤5; порожньо — «Немає».
- (лише при Кроці 9) `## Чого бракує`.

## concept/screens.md — обов'язковий `##`
`## Екрани`: `ID | Назва | Ролі | Тип | Призначення | Поля | Дії | Функції | Сценарії | Основа` — Ролі як `ROLE-NN`; Тип — список/форма/канбан/календар/зведення/майстер; Основа — одне з `Стд CE · Стд EE · td_ · ToDo-готовий · Інтегр` («OCA» — не основа).

## concept/scenarios.md — обов'язковий `##`
`## Сценарії`: по одному блоку `### SC-NN ROLE-NN <назва>` на **кожну** роль; кроки `№ | Час | Дія | Екран | Функція`; кожна F — щонайменше в одному кроці; екран у кроці має містити роль сценарію.

## research/OWNER-BRIEF.md · BOX.md · SALES.md · REJECTED.md
Нумеровані розділи шаблонів: OWNER-BRIEF §1–10, BOX §1–13 (+1а), SALES §1–7; REJECTED — 8 канонічних колонок (`flow-core/references/rejected-register.md`) і розділ `## Журнал знятих рішень`.

## Перевірки CM-*
`CM-files`, `CM-src`, `CM-quote`, `CM-feat`, `CM-signal`, `CM-count`, `CM-trace`, `CM-ids`, `CM-pii`, `CM-scope` + з `--research`: `CM-research`, `CM-buyer`, `CM-roles-scenarios`, `CM-base-edition`, `CM-dnr` (через `check_rejected.py`), `CM-facts` (через `check_facts.py`).
