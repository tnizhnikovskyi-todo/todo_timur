# industry-flow

Маркетплейс Claude Code зі скілами для флоу створення тиражованих галузевих пакетів на Odoo 19 («AI робить, людина вирішує й перевіряє»). Концепція — `_work/CONCEPT.md` (історична, до 2026-11-10; чинні — `_work/DECISIONS_2026-11-10.md` і `plugins/flow-core/references/`). Версія 0.2.0: 36 скілів у 5 плагінах (7 нових: `owner-questionnaire`, `industry-deep-dive`, `reuse-modules`, `completeness-audit`, `concept-presentation`, `showcase-content`, `skill-retro`). Основа змін — уроки реального зрізу «меблі» (`_work/LESSONS-A21-real.md`, план — `_work/IMPLEMENTATION-PLAN.md`).

## Плагіни

| Плагін | Призначення | Кроки |
|---|---|---|
| `flow-core` | Ядро флоу; таблиця кроків і скілів `references/step-skill-map.md` | Скіли: `flow-orchestrator`, `flow-state-keeper`, `ci-pipeline-builder`, `eval-builder`, `flow-step-runner`, `flow-autocheck`, `skill-retro`. Наскрізний: C-01 (оркестратор), C-02 (стан), C-03 (CI), C-04 і C-07 (евали), C-05 (політика даних), C-06 (цикл AI-кроку, автоперевірка), C-08, C-08R (ретро скілів: щодня й за подією). Агенти `plugins/flow-core/agents/`: `flow-executor` (виконавець `base`: лише файли результату, читання odoo-mcp; запис в Odoo й команди виконує runner за рядками «ODOO:»/«КОМАНДИ:»), профільні виконавці `flow-executor-mail|-research|-research-internal|-content|-outreach|-drive|-repo` (мінімальні конектори за ключем наряду `access_profile`; таблиця — `step-skill-map.md`; `repo` — також gates-aggregator, package-release-builder, package-upgrade-runner, odoo-version-migrator; `research` — WebSearch/WebFetch; `research-internal` — + читання внутрішніх даних ToDo (A-03b, A-03c); `content` — A-21c (контент-менеджер); `mail` — читання договору в Drive; запуск workflow і запис у Drive — рядком «КОМАНДИ:» для runner) і `flow-reviewer` (рецензент, лише читання); `flow-step-runner` і цей README посилаються саме на цю єдину копію. |
| `flow-research` | Дослідження до рішення «будуємо пакет?»; скіли: `owner-questionnaire`, `industry-deep-dive`, `reuse-modules`, `concept-mapper`, `completeness-audit`, `concept-presentation`, `prototype-builder` (реальний зріз Odoo 19 `td_*`), `showcase-content`, `demand-test-runner`, `industry-scoring`, `past-projects-analyzer`, `segment-selector`. | A-01, A-02b, A-03b, A-03c, A-04, A-05, A-20, A-20b, A-20c, A-21, A-21c, A-23 (+ список лідів B-01). |
| `flow-package-build` | Збірка тиражованого пакета | A-09, A-12, A-13, A-14, A-15 (+A-22), A-18; скіли: `config-as-code`, `demo-base-builder`, `gates-aggregator`, `master-data-template-builder`, `package-release-builder`, `questionnaire-builder`. |
| `flow-client-delivery` | Впровадження пакета в клієнта | B-02, B-03, B-04, B-06, B-07 (бот), B-09/B-10, B-11 (+B-13); скіли: `client-data-migrator`, `client-help-bot` (B-07; читає прод клієнта лише через підключення `prod-ro-<клієнт>`, лише читання — рішення q37), `package-fit-gap`, `package-sow-builder`, `package-upgrade-runner`, `runbook-executor`, `support-desk`. |
| `flow-package-evolution` | Розвиток пакета | D-01, D-02, D-03; чернетки рішень A-07, A-17, D-04, D-05; скіли: `backlog-triage`, `odoo-version-migrator`, `package-usage-metrics`, `product-decision-drafter`. |

`flow-core` потрібен усім: у ньому цикл AI-кроку і спільні конвенції (`plugins/flow-core/references/`).

## Порядок кроків дослідження (0.2.0)

`A-01 → A-02 (гейт) → A-02b (анкета власника) → A-03 ∥ A-04 → [шлюз сесій → A-05 → A-06] → A-03b (K1) → A-03c (гейт) → A-20 → A-20b → A-20c (єдиний гейт концепції) → A-21 (зразок → повний обсяг → гейт) → A-21c (гейт) → A-23 → A-07`; наскрізний C-08R. Джерело — `plugins/flow-core/references/flow-map.md`.

**Рішення людини в новому порядку:** гейт A-02 (галузь); заповнення анкети A-02b (≤20 хв); відповіді на K1 в A-03b (не кнопка); сесія з власником і гейт A-03c («беремо / адаптуємо / ні»); гейт концепції A-20c; зразок і гейт A-21; гейт A-21c; A-07. Роль **контент-менеджера** — виконавець A-21c (`executor: any`, профіль `content`). Рядки в `flow/decisions.md` від імені власника вносить AI лише за його повідомленням, з позначкою й посиланням (`flow-state-keeper`, режим `decisions-batch`).

**Редакції:** ядро — Odoo 19 CE; Enterprise — окремі мости `td_*_ee`; CI й перевірки на CE і EE (`ODOO_EDITION=ce|ee`). Без доступу до EE EE-перевірки — WARN/«не перевірено».

## Установка

```
claude plugin marketplace add <шлях до цієї теки або репозиторій GitHub>
claude plugin install flow-core@industry-flow
claude plugin install flow-research@industry-flow
claude plugin install flow-package-build@industry-flow
claude plugin install flow-client-delivery@industry-flow
claude plugin install flow-package-evolution@industry-flow
```

Залежності: чотири плагіни оголошують `"dependencies": ["flow-core"]` у `plugin.json`. `claude plugin install` не закріплює версію: звірка `скіл@версія` спирається на тег каталогу. Міжплагінні посилання `flow-core/references/X.md` розв'язуються лише тому, що `flow-step-runner/scripts/build_context.py` кладе конвенції flow-core в теку контексту кроку.

Версія скіла в наряді = версія плагіна (`skill_ref: <плагін>:<скіл>@<semver>`), звірка точна.

## Евали (C-04) під runner'ом
`eval-builder` працює лише як звичайний крок під `flow-step-runner` (наряд, гілка/PR/звіт — runner); ручного шляху немає. Автоперевірки — `flow-core/skills/flow-autocheck/references/checks/C-04.yaml`, `C-07.yaml`: з десяти перевірок C-04 механічних чотири (`scope-evals-only`, `index-exists`, `json-schema`, `no-pii-evals`), решта (`source-filled`, `skills-covered`, `incident-case` та ін.) — `manual`, чек-лист runner/Тімліда, на вердикт не впливають; CLI `claude plugin eval`, `git`, `jq` виконує runner за рядком «КОМАНДИ:». Розклад оркестратора: `weekly: [C-04]` лише якщо на base є `evals/INDEX.md` (інакше позначка «евали не ініціалізовано»; `init` ставить лише AI-інженер).

## Відомі обмеження

- Конкретні дефекти зрізу «меблі» (L§6–8: мобільний конфігуратор, ціна від розміру) — у беклозі A-11 «меблів», не в скілах.

- Другий наряд того самого кроку (A-23 `список`->`prep`, B-08a `звірка`->`збіжність`) створює `flow-orchestrator` за `flow-core/references/flow-map.md`; перевірки в `checks/*.yaml` розрізняються умовою `when: mode:<значення>`. B-11: звірку й додаток SOW виконує `package-upgrade-runner` сам (ключ наряду `called_skills`, не гейти). Тестові бази з «prod» в імені відхиляє `tools-odoo/_common.sh`.
Yaml-специфікації автоперевірки (`flow-autocheck/references/checks/`, 43 файли) є для кроків, які виконує скіл пакета, крім C-06 і C-08. Автоматично `autocheck.py` виконує лише `exists`, `headings`, `git_diff_allowed`, `pii_strict`, `vendored_license` для кроків із фіксованими шляхами; скрипти скілів (`check_sow.py`, `check_fit_gap.py`, `check_migration.py`, `check_pii.py` та ін.) у специфікаціях — рядки `manual` з `who: runner`: їх виконує runner за `flow-step-runner`, Крок 9 (ж) (FAIL скрипта = FAIL кроку, не виконано = ERROR). До першого живого прогону PASS кроків, де всі перевірки yaml — `manual` (A-04, A-05, A-07, A-20–A-23, B-01–B-04, B-06, B-08a, B-09–B-11, B-13, D-01, D-03, D-04), не вважати підставою для зрілості 3. Без специфікації (`ERROR spec-missing`, `INCOMPLETE`; не блокує `done`): A-03, A-06, A-08, A-11, A-16, A-19, B-05, B-08b–d, B-12, C-01, C-02, C-08; C-06 — лише загальні перевірки; A-02, C-00 — людські кроки. Технічні імена полів і стадій Odoo визначає C-00 (`flow/ODOO_SCHEMA.md`); зведені вимоги до C-00 — `plugins/flow-core/references/c00-checklist.md`. Таблиця «крок → skill_ref → params.mode» — `plugins/flow-core/references/step-skill-map.md`. Іконки плагінів є (`.claude-plugin/icon.png`); `eval-builder/scripts/evals_to_cli.py` створено (самотест на 5 evals.json); еталони `apply.py`/`validate.py`/`install.sh` і скрипти `tools/odoo/` є як шаблони в `flow-core/references/templates/tools-odoo/` — C-00 копіює й адаптує, на Odoo 19 не перевірені. Наживо не запускалось: `claude plugin eval`, odoo-mcp, GitHub, Gmail, скрипти `tools/odoo/` на Odoo 19 — перший живий прогін (1 кейс eval, один крок через runner на тестовій базі) перед поданням у каталог.

## Агенти flow-core
`flow-executor` (профіль `base`) і профільні `flow-executor-drive|mail|outreach|repo|research` лежать у `plugins/flow-core/agents/`; runner зупиняє наряд, якщо потрібного агента немає. Дії поза профілем (`gh workflow run`, `drive-create` для A-23) виконує runner за рядком «КОМАНДИ:». `ODOO_ALLOWED_HOSTS` у tools-odoo — через кому або пробіл.

## Релізи
Версія плагіна записана в `.claude-plugin/marketplace.json` і в `plugins/<плагін>/.claude-plugin/plugin.json`: при релізі міняти обидва файли; джерело для `skill_ref` — `plugin.json`.

## Правила

Наряд — задача Odoo; результат — PR; звіт — у задачу; прод клієнта заборонено — єдиний виняток (q37): скіл `client-help-bot`, лише читання, лише через підключення `prod-ro-<клієнт>`, окремий технічний користувач з мінімальними групами, пункт у SOW і згода клієнта, журнал запитів; `connection_id` явно в кожному виклику `odoo-mcp`.

Дані: ПДн (`client_data: personal`) обробляє лише центральний агент; виняток (q01) — кроки B-13 і B-08a на тестовій базі клієнта: дозволено будь-якого агента.

## Рішення людини (2026-11-10) і відкриті питання

Повна таблиця (q01–q44: питання, рішення, рекомендація, хто) — `_work/DECISIONS_2026-11-10.md`. Нумерація q — з того файлу; колишні номери README 1–34 розбито на q01–q44.

**Закрито** (рішення одним рядком)
- Дані: q01 B-13/B-08a — будь-який агент; q02 знеособлені копії — пілот без них; q03 B-11 версія 2 — після пілоту; q04 `incidents/` — у git метадані й переказ; q05 записи Fathom — безстроково; q06 акт звірки — лише в PR; q07 загальні email юросіб — commercial; q08 список розсилки — Drive з доступом ролей; q09 клієнтів без згоди на AI не беремо (профілю «без AI» немає, q30 знято).
- SOW: q10 «підписано» — стадія угоди в CRM; q11 підписанти — роль, дата, посилання; q12 зміни — додаткова угода; q31 поріг розбіжності з вилкою B-01 — 20%; q41 пункт про агрегати — у шаблоні SOW.
- Виконання й Odoo: q13 запис у тест/демо-бази — runner за allow-list; q14 `ODOO_SCHEMA.md` — AI-чернетка, Тімлід затверджує; q15 картки — AI-чернетка одним PR; q16 зрілість і «Рішення:» — AI у PR автоекспорту; q17 `tools/odoo`, apply/validate/install — усе до пілоту; q21 каталог — окремий репо, тег релізу; q22 PR автоекспорту — auto-merge за перевіркою; q23 `FLOW_STOP` — активність у задачі Odoo; q24 `display_title` — перевірити, запас — SHA; q25 ліміти — порції, CI поза таймаутом; q26 перший `claude plugin eval` — AI-інженер до подання; q27 евали `requires: step-run` — пропускати до після пілоту.
- Пакет і продукт: q18 Chromium, лише останнє відео; q19 версії 19.0.X.Y, тег релізу `package/vX.Y`, суфікс `-odoo<N>` лише для переходу на нову мажорну Odoo (гілка `upgrade/vX.Y-odoo<N>`, тег `package/vX.Y-odoo<N>`); q16 -- рядок «Рішення:» про зрілість скіла, а рядки рішень у документах D-04/D-05/A-07/A-17 вписує людина (В-1 `product-decision-drafter`); q20 код Enterprise — відкласти до міграції; q28 B-11 звірка лише за метаданими; q29 A-12 у 0.1 — інструкція; q32 «поза пакетом» — лише доробки; q33 шкала серйозності й hypercare 45 днів — як є; q34 SLA — календарні дні; q35 ID запитів SAL/UAT/PIL, оцінка з джерел; q36 `key-models.yaml` — AI-чернетка при релізі; q38 «2021→2025»; q39 ваги балу — після першого запуску; q40 A-01 — ручне завдання; q42 ліцензії — пермісивні та LGPL-3; q43 формулювання «на базі Odoo 19»; q44 непідтверджені ознаки PM — з позначкою.
- q37: `client-help-bot` (B-07) робимо зараз; читання проду клієнта — єдиний виняток (див. «Правила»).

**Лишається відкритим** (за «Відкриті питання» скілів; подробиці — там і в `references/open-questions.md`)
- Блокує перший `client-help-bot` `answer`: підтвердження Тімліда в `kb-index.md`, що користувач `prod-ro-<клієнт>` без прав запису/створення/видалення (штатної read-only ролі немає); пункт у `c00-checklist.md`.
- `flow-core`: назви стадій угоди CRM для `preconditions_confirmed.crm_deal_stage` (`discovery_signed` — B-02, `sow_signed` — B-04/B-06/B-11) і поле-дзеркало (q10; C-00); мітка Gmail допомоги — окрема чи спільна з `support-desk` (до рішення мітки різні, спільна = `escalated`; PM, Підтримка).
- `client-help-bot`: як гарантувати «лише читання» на боці Odoo (Тімлід, Архітектор); allow-list моделей і заборонені групи в Odoo 19 (`group_ids`; Тімлід, C-00); журнал запитів і читання `res.users` (Юрист); що створює наряд `answer` «на період» (`flow-orchestrator`).
- `support-desk`: середня серйозність дефекту пакета — беклог чи обхід.
- `package-sow-builder`: структура `package/pricing.md`.
- `package-upgrade-runner`: сценарій міграції клієнта на нову мажорну Odoo; де PM фіксує «зняті відхилення».
- `demo-base-builder`: ліміт установки всіх профілів; паролі демо-ролей і хостинг (Тімлід, C-05).
- `package-usage-metrics`: як рахувати «активні внутрішні користувачі»; де лежить вивантаження за замовчуванням (Тімлід).
- `config-as-code`: дозвіл агенту встановлювати модулі в тестовій базі пакета (C-05).
- `ci-pipeline-builder`: хто й коли доперевіряє довгий CI за run id.
- `product-decision-drafter`: чи є модель табеля пілота в `ODOO_SCHEMA.md`.
- `industry-scoring`: дата знімка odb-catalog у наряді A-01.
- `flow-package-build`/`flow-core`: сигнатури еталонів `install.sh`/`validate.py` (`templates/tools-odoo/`) відрізняються від «CLI-контракту» в `config-package-format.md` — рішення людини: перейменувати еталони чи змінити контракт (q17; пункт у `c00-checklist.md`). Bash-скрипти `tools-odoo` не запускати на сервері, де є прод, поки C-00 не задасть `ODOO_ALLOWED_HOSTS`.
- Наживо не перевірено: перший прогін `claude plugin eval`, скриптів `tools/odoo/`, MCP (q26).

**Відкриті питання плану 0.2.0 (рішення людини; не вирішено мовчки, див. `_work/IMPLEMENTATION-PLAN.md` §5)**
- Ліцензія наших модулів: LGPL-3 за замовчуванням, остаточно — рішення власника (OPL — альтернатива).
- `search_count` власної ERP: чи дає `odoo-mcp` read-only спосіб підрахунку (інакше повний перебір `odoo_search_read`); C-00.
- Доступ до EE (ліцензія/база) для CI й перевірки тверджень; без нього EE-вердикти «не перевірено», EE-job — WARN.
- Дозвіл середовища на push `research/sources/` (`internal-raw`) — хто й де фіксує (C-00).
- Хто публікує Artifact (A-20c) у бойовому флоу: runner від технічного користувача чи людина; де зберігається URL поза репо.
- Рішення плану К-20…К-25 (місце шаблону анкети, автор OWNER-BRIEF, профілі `research-internal`/`content`, без `fidelity: mock`, реєстр уроків `flow/lessons/`, версії 0.2.0) — підтвердити або змінити.
