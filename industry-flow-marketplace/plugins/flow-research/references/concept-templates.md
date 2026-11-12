# Шаблони концепції пакета (A-20): `concept/*` і `research/{BOX,SALES,REJECTED,AI-DECISIONS}.md`

Спільні для `concept-mapper` (A-20), `completeness-audit` (A-20b), `concept-presentation` (A-20c), `prototype-builder` (A-21), `demand-test-runner` (A-23) і ТР (A-08).
**Еталон колонок і скрипт — `skills/concept-mapper/references/template/` і `check_concept.py`**; при розбіжності діють вони. Копіюються в `docs/industries/<галузь>/concept/` (або `_template/concept/`).
Каркаси `research/*.md` — `templates/{BOX,SALES,REJECTED,AI-DECISIONS}.tpl.md` (поруч). **Заголовки `##` — контракт скрипта (CM-files, CM-research), не змінювати.**

## ID і джерела
- ID: `ROLE-NN`, `PAIN-NN`, `F-NN`, `S-NN`, `SC-NN`; двозначний мінімум, наскрізні, не перевикористовуються; зникнення ID між версіями — FAIL `CM-ids`. Не `R-/B-/P-`.
- Джерело болю — `<файл>§<заголовок>` (`skills/concept-mapper/references/source-anchors.md`): `briefing.md`, `past-projects.md`, `sessions/protocol-<ід>-<дата>.md`, `OWNER-INTAKE.md` (слова власника з анкети). Цитата — дослівна, ≤25 слів, знеособлена; у джерелі без назв клієнтів, ПІБ, контактів, сум.
- Числа в `research/*.md` і `concept/*` — лише з `research/facts.yaml` з маркером `<!--fact:ключ-->`.

## concept/features.md — обов'язкові `##`
`## Ролі` · `## Болі` · `## Функції` · `## Поза концепцією` · `## Відкриті питання`
- Ролі: `ID | Роль | Що робить | Джерело`; роль-покупець — позначка `[покупець]` у колонці «Роль».
- Болі: `ID | Роль | Біль | Джерело | Цитата` (5 колонок).
- Функції: `ID | Функція | Роль | Біль | Джерел N | Екран | Статус` (≥6 колонок; «Джерел N» = різних записів джерел по болях функції; статус: `довід: <типи джерел>` | `ризик: перевірити на пілоті` | `інтерес: є/немає/не тестувалась` | `знято: причина` | `вето власника <дата>`).
- Поза концепцією: `Що | Причина` (біль без функції; відкинуте — посилання на `research/REJECTED.md`).
- Відкриті питання: `№ | Мітка [анкета/ризик] | Питання | Рекомендація AI | Замовчування`; відкрите питання без відповіді — рядок `ризик: перевірити на пілоті` й рядок AI-NN; порожньо — «Немає».
- (лише при Кроці 9) `## Чого бракує`.

## concept/screens.md — обов'язковий `##`
`## Екрани`: `ID | Назва | Ролі | Тип | Призначення | Поля | Дії | Функції | Сценарії | Основа` — Ролі як `ROLE-NN`; Тип — список/форма/канбан/календар/зведення/майстер; Основа — одне з `Стд CE · Стд EE · td_ · ToDo-готовий · Інтегр` («OCA» — не основа).

## concept/scenarios.md — обов'язковий `##`
`## Сценарії`: по одному блоку `### SC-NN ROLE-NN <назва>` на **кожну** роль; кроки `№ | Час | Дія | Екран | Функція`; кожна F — щонайменше в одному кроці; екран у кроці має містити роль сценарію.

## research/BOX.md · SALES.md · REJECTED.md · AI-DECISIONS.md
Нумеровані розділи шаблонів: BOX §1–13 (+1а; §1 — склад коробок, тарифи — дослівно `tariffs` власника або «не задано»), SALES §1–7 (§3 — «Ризики продажу»); REJECTED — короткий список `ID · що не робимо · чому` (`flow-core/references/rejected-register.md`); `AI-DECISIONS.md` — розділи «Рішення» й «Повнота» (`templates/AI-DECISIONS.tpl.md`). OWNER-BRIEF не пишеться. Грошей у цих файлах немає (`CM-money`).

## Перевірки CM-*
`CM-files`, `CM-src`, `CM-quote`, `CM-feat`, `CM-signal`, `CM-count`, `CM-trace`, `CM-ids`, `CM-pii`, `CM-scope` + з `--research`: `CM-research`, `CM-buyer`, `CM-roles-scenarios`, `CM-base-edition`, `CM-money`, `CM-facts` (через `check_facts.py`).
