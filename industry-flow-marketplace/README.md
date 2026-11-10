# industry-flow

Маркетплейс Claude Code зі скілами для флоу створення тиражованих галузевих пакетів на Odoo 19 («AI робить, людина вирішує й перевіряє»). Концепція — `_work/CONCEPT.md`.

## Плагіни

| Плагін | Призначення | Кроки |
|---|---|---|
| `flow-core` | Ядро флоу; таблиця кроків і скілів `references/step-skill-map.md` | Скіли: `flow-orchestrator`, `flow-state-keeper`, `ci-pipeline-builder`, `eval-builder`, `flow-step-runner`, `flow-autocheck`. Наскрізний: C-01 (оркестратор), C-02 (стан), C-03 (CI), C-04 і C-07 (евали), C-05 (політика даних), C-06 (цикл AI-кроку, автоперевірка), C-08. Агенти `plugins/flow-core/agents/`: `flow-executor` (виконавець: лише файли результату, читання odoo-mcp; запис в Odoo й команди виконує runner за рядками «ODOO:»/«КОМАНДИ:») і `flow-reviewer` (рецензент, лише читання); `flow-step-runner` і цей README посилаються саме на цю єдину копію. |
| `flow-research` | Дослідження до рішення «будуємо пакет?»; скіли: `concept-mapper`, `demand-test-runner`, `industry-scoring`, `past-projects-analyzer`, `prototype-builder`, `segment-selector`. | A-01, A-04, A-05, A-20, A-21, A-23 (+ список лідів B-01). |
| `flow-package-build` | Збірка тиражованого пакета | A-09, A-12, A-13, A-14, A-15 (+A-22), A-18; скіли: `config-as-code`, `demo-base-builder`, `gates-aggregator`, `master-data-template-builder`, `package-release-builder`, `questionnaire-builder`. |
| `flow-client-delivery` | Впровадження пакета в клієнта | B-02, B-03, B-04, B-06, B-09/B-10, B-11 (+B-13); скіли: `client-data-migrator`, `package-fit-gap`, `package-sow-builder`, `package-upgrade-runner`, `runbook-executor`, `support-desk`. |
| `flow-package-evolution` | Розвиток пакета | D-01, D-02, D-03; чернетки рішень A-07, A-17, D-04, D-05; скіли: `backlog-triage`, `odoo-version-migrator`, `package-usage-metrics`, `product-decision-drafter`. |

`flow-core` потрібен усім: у ньому цикл AI-кроку і спільні конвенції (`plugins/flow-core/references/`).

## Установка

```
claude plugin marketplace add <шлях до цієї теки або репозиторій GitHub>
claude plugin install flow-core@industry-flow
claude plugin install flow-research@industry-flow
claude plugin install flow-package-build@industry-flow
claude plugin install flow-client-delivery@industry-flow
claude plugin install flow-package-evolution@industry-flow
```

Відкладено: `client-help-bot` (B-07) — потрібен чи ні, див. питання 24.

Залежності: чотири плагіни оголошують `"dependencies": ["flow-core"]` у `plugin.json`. `claude plugin install` не закріплює версію: звірка `скіл@версія` спирається на тег каталогу. Міжплагінні посилання `flow-core/references/X.md` розв'язуються лише тому, що `flow-step-runner/scripts/build_context.py` кладе конвенції flow-core в теку контексту кроку.

Версія скіла в наряді = версія плагіна (`skill_ref: <плагін>:<скіл>@<semver>`), звірка точна.

## Евали (C-04) під runner'ом
`eval-builder` працює лише як звичайний крок під `flow-step-runner` (наряд, гілка/PR/звіт — runner); ручного шляху немає. Автоперевірки — `flow-core/skills/flow-autocheck/references/checks/C-04.yaml`, `C-07.yaml`: з десяти перевірок C-04 механічних чотири (`scope-evals-only`, `index-exists`, `json-schema`, `no-pii-evals`), решта (`source-filled`, `skills-covered`, `incident-case` та ін.) — `manual`, чек-лист runner/Тімліда, на вердикт не впливають; CLI `claude plugin eval`, `git`, `jq` виконує runner за рядком «КОМАНДИ:». Розклад оркестратора: `weekly: [C-04]` лише якщо на base є `evals/INDEX.md` (інакше позначка «евали не ініціалізовано»; `init` ставить лише AI-інженер).

## Відомі обмеження
Yaml-специфікації автоперевірки (`flow-autocheck/references/checks/`, 35 файлів) є для кроків, які виконує скіл пакета, крім C-06 і C-08. Автоматично `autocheck.py` виконує лише `exists`, `headings`, `git_diff_allowed`, `pii_strict`, `vendored_license` для кроків із фіксованими шляхами; скрипти скілів (`check_sow.py`, `check_fit_gap.py`, `check_migration.py`, `check_pii.py` та ін.) у специфікаціях — рядки `manual` з `who: runner`: їх виконує runner за `flow-step-runner`, Крок 9 (ж) (FAIL скрипта = FAIL кроку, не виконано = ERROR). До першого живого прогону PASS кроків, де всі перевірки yaml — `manual` (A-04, A-05, A-07, A-20–A-23, B-01–B-04, B-06, B-08a, B-09–B-11, B-13, D-01, D-03, D-04), не вважати підставою для зрілості 3. Без специфікації (`ERROR spec-missing`, `INCOMPLETE`; не блокує `done`): A-03, A-06, A-08, A-11, A-16, A-19, B-05, B-07, B-08b–d, B-12, C-01, C-02, C-08; C-06 — лише загальні перевірки; A-02, C-00 — людські кроки. Технічні імена полів і стадій Odoo визначає C-00 (`flow/ODOO_SCHEMA.md`); зведені вимоги до C-00 — `plugins/flow-core/references/c00-checklist.md`. Таблиця «крок → skill_ref → params.mode» — `plugins/flow-core/references/step-skill-map.md`. Наживо не запускалось: `claude plugin eval`, odoo-mcp, GitHub, Gmail, скрипти `tools/odoo/` на Odoo 19 — перший живий прогін (1 кейс eval, один крок через runner на тестовій базі) перед поданням у каталог.

## Релізи
Версія плагіна записана в `.claude-plugin/marketplace.json` і в `plugins/<плагін>/.claude-plugin/plugin.json`: при релізі міняти обидва файли; джерело для `skill_ref` — `plugin.json`.

## Правила

Наряд — задача Odoo; результат — PR; звіт — у задачу; прод клієнта заборонено; `connection_id` явно в кожному виклику `odoo-mcp`.

## Відкриті питання до людини
Коротко, подробиці — у «Відкриті питання» відповідного скіла.

**Дані й безпека (Власник продукту, Юрист)**
1. ~~Доступ до проду клієнта для D-01~~ — **закрито**: AI не працює з продом клієнта (рішення людини, без винятків). Метрики D-01 `collect` беруться з вивантаження агрегатів, яке готує Тімлід/підтримка за шаблоном `package-usage-metrics/references/export-template.md` (без файлу — `waiting_human`, «вивантаження метрик від Тімліда»). Лишається В-6 `package-usage-metrics` (договірний пункт про передачу агрегатів — Юрист).
2. Тестова база після B-06 містить персональні дані: чи B-13/B-08a лише центральному агенту — `runbook-executor`.
3. `clients/<к>/incidents/` у git проти правила «витяги зі звернень у репо не зберігаються» — `support-desk`.
4. Імена підписантів у `sow.md` чи роль + посилання на PDF; механізм підписання додатка — `package-sow-builder`.
5. Клієнт без згоди на AI: що робить флоу; джерело істини «угоду підписано» — `package-fit-gap`.
6. Email юрособи з реєстру — `commercial`? Де зберігати список розсилки — `segment-selector`, `demand-test-runner`.
7. Ознака знеособленої копії й формат таблиці «Дозволено передавати в AI» — `flow-step-runner`.

**Модель виконання й Odoo (Тімлід / C-00, AI-інженер)**
8. Запис у тестові/демо-бази: прийнято — виконує runner за рядками «ODOO:» лише для класів `test-*|test-pkg-*|demo-*|emu-*`; підтвердити або обрати окремого агента — `flow-step-runner`.
9. Технічні імена полів і стадій, `flow/ODOO_SCHEMA.md`, автоматизація «задача C-01 на зміну стадії» — визначає C-00 — `flow-orchestrator`, `flow-state-keeper`.
10. Скрипти `tools/odoo/` (чиста база за тегом, тести, імпорт, скидання): шаблони у `plugins/flow-core/references/templates/tools-odoo/`, не перевірені на реальному Odoo (опції демо-даних 19, текст підсумку тестів — відкриті питання C-00), `import.sh` — заглушка; посилання з «Відкритих питань» скілів на README шаблонів — залишок (файли скілів правлять інші); C-00 має скопіювати й адаптувати. Еталонні `apply.py`/`validate.py`/`install.sh` і доставка `package/addons` у тестову базу (AI-інженер) не існують — `ci-pipeline-builder`, `demo-base-builder`, `master-data-template-builder`, `package-release-builder`, `odoo-version-migrator`.
11. Закріплення версії плагіна при установці; де репозиторій каталогу — `flow-step-runner`, `eval-builder`.
12. Хто зливає PR автоекспорту стану; хто записує нову зрілість після кнопки; хто вписує рядок «Рішення:» після кнопки (`product-decision-drafter` В-1) — `flow-state-keeper`, `eval-builder`, `product-decision-drafter`.
13. Ліміти: `init`/`regress` евалів не вміщаються в $5/45 хв; CI довший за `timeoutMin` — `eval-builder`, `package-upgrade-runner`, `demo-base-builder`.
14. ~~Скрипт `eval-builder/scripts/evals_to_cli.py`~~ — ЗАКРИТО: створено, самотест на 5 evals.json і синтетичний; ВІДКРИТО: перший прогін реального `claude plugin eval` на 1 згенерованому кейсі (чи ігнорує CLI `manifest-<набір>.json` в eval dir, імена грейдерів); припущення — `eval-builder/references/run-eval.md`.
14а. Харнес кейсів із `requires: step-run` (повний прогін кроку) — хто й де його надає — `eval-builder`.

**Продукт і картки (Власник продукту, Керівник напряму)**
15. Усі картки (54): жодна не посилається на скіл пакета в `skillRef` (34 з `gap: true`), застарілі також `executor`; до першої диспетчеризації C-00 оновлює їх за `flow-core/references/step-skill-map.md` — `flow-orchestrator`, відповідні скіли.
16. Чи допустимий `done` A-12 без установки «однією командою» у 0.1; формат конфіг-пакета — `config-as-code`. Позначка профілю «без AI на даних» (№47, Керівник напряму) — `package-sow-builder`.
16а. Chromium для Playwright у середовищі агента; відео в git чи LFS (Власник продукту, AI-інженер) — `prototype-builder` (В-1, В-2).
17. Структура `package/pricing.md`, поріг розбіжності з вилкою B-01 — `package-sow-builder`.
18. Метрика «поза пакетом» (чи входить доналаштування) — `package-fit-gap`.
19. Шкала серйозності, строк hypercare 45 днів, календар SLA — `support-desk`.
20. Формат ID запитів D-02 з B-01/B-08c/D-05; колонка оцінки в беклозі — `backlog-triage`, `product-decision-drafter`.
21. Формулювання «зростання 2020–2025» (фактично 2021→2025); дата знімка odb-catalog у наряді; ваги балу A-05/B-01 — `industry-scoring`, `segment-selector`.
22. Формат версії `<N>.0.X.Y`, гілки й тега `-odoo<N>`; доступ до коду Enterprise — `odoo-version-migrator`, `package-upgrade-runner`.
23. Хто веде `key-models.yaml` для метрик — `package-usage-metrics`.
24. `client-help-bot` (B-07) відкладено: потрібен чи ні — CONCEPT §4.
25. Прогін CI: чи повертає MCP `github` `display_title` dispatch-прогону — `gates-aggregator`, `ci-pipeline-builder`.
26. Клас бази знеособленої копії `anon-<клієнт>` (B-11 версія 2) і крок-виробник такої копії (C-09 не існує); до рішення версія 2 не запускається — `package-upgrade-runner` (В-9), `data-and-connections.md` §3.5.
27. Список сумісних ліцензій для вендорингу (Юрист) — `config-as-code`.
28. Формулювання «на Odoo 19» і схожість з Odoo Enterprise у матеріалах для лідів (Юрист) — `prototype-builder` (В-5).
29. failureMode картки B-11 «AI звірив конфіг» проти режиму «звірка» — `package-upgrade-runner` (В-7), `runbook-executor`.
30. Хто моніторить `FLOW_STOP` і де фіксується тип агента — `flow-step-runner` (open-questions №4, №13).
31. Чи беруть D-01/B-10 непідтверджені PM прапорці — `flow-state-keeper`.
32. Річний запуск A-01 у карті флоу — `industry-scoring`.
33. Строк зберігання записів Fathom — `package-fit-gap`.
34. Файл акта звірки на Drive (формат, тека) — `client-data-migrator`.
