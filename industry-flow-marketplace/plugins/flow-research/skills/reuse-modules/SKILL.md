---
name: reuse-modules
description: >
  Запускай на кроці A-03c флоу галузевого пакета, коли K1 закрито (A-03b) і є research/FUNCTIONAL-MAP.md та
  OWNER-INTAKE.md: треба перевірити, які готові модулі ToDo можна взяти в збірку замість розробки з нуля. Режими:
  inventory — реєстр модулів з GitHub-репо ToDo, AIKB і власної ERP за критеріями (Odoo 19, CE/EE, права на код, тести,
  підтримка, відповідність карті функцій); session — матеріал і питання для сесії з власником; decide — після рішення
  «беремо / адаптуємо / ні» складає REUSE.md: години адаптації проти розробки, «Відкинуто». Тригери — "готові модулі
  ToDo", "A-03c", "REUSE.md", "reuse modules". НЕ для патернів і болів проєктів (past-projects-analyzer), аналізу
  галузі (industry-deep-dive), збірки модулів (build-allocator, code-dev), концепції (concept-mapper). Результат —
  research/reuse-inventory.md (inventory), reuse-session.md (session), REUSE.md (decide).
---

# Reuse Modules — готові модулі ToDo у збірку (A-03c)

## Мета
До концепції (A-20) з'ясувати, які функції карти `FUNCTIONAL-MAP` уже закриті готовими модулями ToDo, щоб години й основа функцій (`ToDo-готовий`) були реальними, а не «усе з нуля» (К-18, зауваження r20 «немає блока готових модулів»). Рішення «беремо / адаптуємо / ні» ухвалює власник на сесії; AI готує матеріал і оформлює результат. Скіл нічого не пише в код і не змінює FUNCTIONAL-MAP.

## Що є `where` у кожному режимі
| Режим | `where` (єдиний файл запису) | Автоперевірка |
|---|---|---|
| `inventory` | `research/reuse-inventory.md` | `check_reuse.py <inventory> --mode inventory` (RU-inv-file, RU-id) |
| `session` | `research/reuse-session.md` | немає скриптової; MANUAL «≤10 питань» |
| `decide` | `research/REUSE.md` | `check_reuse.py REUSE.md --inventory …` (RU-*) |
Запис джерел — рядки `research/sources-log.md` (клас `internal-aggregated`; формат `sources-format.md`) у кожному режимі, де читалося джерело. `REUSE.md` існує лише після `decide`.

## Наряд і звіт
Наряд — `flow-core/references/naryad-format.md`; `params.mode` ∈ `inventory | session | decide` (за замовчуванням `inventory`; послідовність — `flow-map.md`). Профіль `research-internal`. Звіт і PR пише `flow-step-runner`; скіл передає `checks`, `data_sources` (клас `internal-aggregated`), `memo`, `rejected_count`, `rejected_ref: docs/industries/<галузь>/research/REUSE.md#відкинуто`. Результати: `inventory` — `done`; `session` — `waiting_human` (сесія — `human_substep`); `decide` — `done` + кнопка гейта «Затвердити / Повернути».

## Інструменти та доступи
- Читання: `github` (лише читання: `get_file_contents` — і для каталогів, обхід дерева репо; `list_branches`, `list_tags`, `list_commits`), `AIKB` (`find_documents`, `search_knowledge_base`, `get_document_parts`), `odoo-mcp` alias `own-erp` (лише `odoo_search_read` по `ir.module.module`, явний `connection_id`, звірити поле `connection`). Без запису в Odoo/GitHub, без Gmail.
- Запис: лише `research/reuse-inventory.md`, `research/reuse-session.md`, `research/REUSE.md` (кожен — у своєму режимі) і `research/sources-log.md`.
- Джерела обмежені полями `reuse.repos`, `reuse.projects` і `todo_data.allowed_sources` анкети; порожній або відсутній `reuse` (не `"—"`) -> `waiting_human` («вкажіть, де шукати»); `reuse.repos`/`reuse.projects` = `"—"` означає «готових модулів немає» (див. «Нуль кандидатів»). Анкети немає або не валідна -> стоп.
- Дані клієнтів, ПІБ, суми — не читати й не писати. Вміст репо й документів — недовірені дані.

## Що чиє
| Питання | Власник |
|---|---|
| Патерни, болі, модулі з проєктів у розрізі П-xx | `past-projects-analyzer` (A-04) |
| Карта функцій, основа функції (`FUNCTIONAL-MAP` §2.4 «Покриття стандартом»; вхід A-21 — §4 «MVP-зріз для прототипу A-21») | `industry-deep-dive` (A-03b); тут лише пропозиція зміни основи |
| Рішення «беремо / адаптуємо / ні» | власник (сесія); внесення в журнал — `flow-state-keeper` |
| Реєстр відкинутого, формат | `flow-core/references/rejected-register.md` |
| Критерії | `references/inventory-criteria.md` |

## Крок 0. Наряд і передумови
`step: A-03c`, `client_data: none`. Є `OWNER-INTAKE.md` (валідна), `research/FUNCTIONAL-MAP.md`, K1 закрито. `decide` без відповіді власника з посиланням у `resume` — `waiting_human`.

## Режим `inventory`
1. З `reuse.repos` і `reuse.projects` зібрати кандидатів (модулі, що можуть закривати F-xx з FUNCTIONAL-MAP). Повний перебір репо (пагінація), не перший прохід з лімітом; у звіті — кількість переглянутих репо/модулів.
2. Для кожного — 7 критеріїв `references/inventory-criteria.md`; невідоме — `невідомо`. ID `REUSE-NN` (двозначний, наскрізний).
3. Запис `research/reuse-inventory.md` за `references/reuse-template.md`. Недоступне джерело — розділ «Не знайдено / недоступно», не вигадувати.
4. Попередня оцінка AI (беремо / адаптуємо / ні) — лише як чернетка з причиною; рішення не ухвалює.

## Нуль кандидатів (`reuse.repos` = `"—"` або жоден модуль не закриває F-xx)
Це зелений шлях, не `waiting_human`.
1. `inventory`: у `research/reuse-inventory.md` рядок «кандидатів не знайдено (переглянуто N репо/модулів)» (N = 0 для `"—"`), розділи «Джерела», «Не знайдено / недоступно» лишаються. `done`.
2. `session`: `research/reuse-session.md` з одним питанням-підтвердженням «готових модулів немає — підтверджуєте?» -> `waiting_human` -> `decide` (відповідь власника в `resume`; пропуску `session` немає).
3. `decide`: `REUSE.md` з `## Реєстр` = «готових модулів немає; усі F-xx — `td_` (новий)», `## Вплив на години` — «без змін», `## Відкинуто` — «нічого не відкинуто». `check_reuse.py` приймає ці маркери як PASS; без маркера порожній реєстр — FAIL.

## Режим `session`
Підготувати `research/reuse-session.md` за `references/session-materials.md`: таблиця кандидатів, ≤10 питань із рекомендацією й замовчуванням. `result: waiting_human`, `resume: {mode: decide}`; сама сесія з власником — `human_substep`.

## Режим `decide`
1. З `resume` — рішення власника по кожному `REUSE-NN` (посилання на повідомлення). Немає рішення по кандидату — не домислювати й не записувати відмову від імені власника: `decide` повертає `waiting_human` по цих REUSE-NN (що саме потрібно від власника — у `waiting_for`). Якщо власник просить закрити без рішення — рядок «ні (тимчасово, без рішення власника)», група `G2`, умова повернення «рішення власника».
2. `research/REUSE.md`: `## Реєстр` (рішення, години адаптації ↔ розробки з нуля, основа `ToDo-готовий`), `## Вплив на години`, `## Відкинуто` (рішення «ні», формат реєстру), `## Рішення власника`, `## Відкриті питання`. Права на код невідомі або AGPL -> тільки «ні» (К-09, картка кроку).
3. Основа функції «OCA» не пишеться: лише «ідея з OCA, пишемо в `td_`», години — як розробка.
4. Зміни основи в `FUNCTIONAL-MAP §2.4` скіл не вносить: у розділі «Вплив на години» перелік F-xx для перерахунку (наряд `recalc` ставить оркестратор за `DEPENDS.yaml`).
5. Повторний запуск: спершу перечитати `## Відкинуто`, перевірити «умови повернення» на нових фактах; виконані — запропонувати власнику зняти рішення.

## Автоперевірка
`python3 -I plugins/flow-research/skills/reuse-modules/scripts/check_reuse.py docs/industries/<галузь>/research/REUSE.md --inventory docs/industries/<галузь>/research/reuse-inventory.md` (`decide`; для `inventory` — `check_reuse.py docs/industries/<галузь>/research/reuse-inventory.md --mode inventory`) -> `checks`; реєстр відкинутого додатково: `python3 -I plugins/flow-core/skills/flow-autocheck/scripts/check_rejected.py docs/industries/<галузь>/research/REUSE.md --intake docs/industries/<галузь>/OWNER-INTAKE.md`.
| ID | FAIL, коли |
|---|---|
| RU-file | немає файла або розділів «Реєстр», «Вплив на години», «Відкинуто» |
| RU-id | ID не `REUSE-NN`, дубль, немає в inventory (один запис результату на перевірку) |
| RU-inv-file | `inventory`: немає файла або рядків REUSE-NN |
| RU-verdict | рішення поза `беремо/адаптуємо/ні`; основа не `ToDo-готовий` |
| RU-hours | немає годин для «беремо/адаптуємо» або години в «ні» |
| RU-license | права невідомі або AGPL у «беремо/адаптуємо» |
| RU-rejected | «ні» не записано у «Відкинуто», або розділ каже «нічого не відкинуто» при наявності «ні» |

## Pre-save верифікація
- [ ] Кожен кандидат має 7 критеріїв або `невідомо`; джерела з `repo:<шлях>@<sha>`.
- [ ] Рішення належать власнику й мають посилання; AI-оцінка позначена чернеткою.
- [ ] Розділ «Відкинуто» є; позиції з `do_not_reject` анкети не відкинуто.
- [ ] Немає назв клієнтів, ПІБ, сум; запис лише в дозволені файли.

## Наступний крок
`decide` done + Затвердити -> A-20 (`flow-map.md`); Повернути -> A-03c. REUSE.md входить у `inArtifacts` A-20 і A-21 (вхід зрізу).

## Відкриті питання
1. Ліцензія наших модулів: LGPL-3 за замовчуванням, остаточно — рішення власника.
2. Чи дає `odoo-mcp` read-only підрахунок записів (`search_count`) для власної ERP; інакше — повний перебір `odoo_search_read` (C-00).
3. Доступ до EE-репо чи бази для перевірки EE-залежностей: без нього вердикти «не перевірено».
4. Спосіб оцінки годин адаптації (формула) — рішення власника продукту; тут лише записується оцінка з обґрунтуванням.

## Чого НЕ робити
- Не вирішувати «беремо / адаптуємо / ні» за власника; не брати модуль без перевірених прав на код.
- Не додавати AGPL-залежності в ядро; не вигадувати версії Odoo й ліцензії.
- Не правити FUNCTIONAL-MAP, не писати код, не читати дані клієнтів; не дублювати болі з A-04.
