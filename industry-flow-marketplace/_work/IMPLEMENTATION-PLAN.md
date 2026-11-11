# IMPLEMENTATION-PLAN: внесення уроків «меблі» в пакет industry-flow

Дата: 2026-11-11. Статус: **план, у плагінах нічого не змінено, нічого не закомічено.**
Входи: `_work/LESSONS-A21-real.md` (L§1–22), `_work/FIRST-TIME-RIGHT.md` (FTR: N-01…N-18, С-01…С-16, §4, §5), `_work/SELF-LEARNING.md` (SL),
`_work/templates/PAGE-CONTRACT.md`. Пакет: 5 плагінів, 29 скілів, усі `0.1.0`; після плану — 36 скілів.
Еталони (тестове репо `/home/user/industry-flow-test-mebli`, читати лише оглавленням `grep -nE '^#{2,3} '` і потрібними розділами — файли 40–380 KB):
- гілка `flow/A-03b-deep` @ `008541fb4d4ced7adfa7061c1edf5576eaa9bf36` — `docs/industries/mebli/research/` (OWNER-BRIEF, FUNCTIONAL-MAP, BOX, SALES,
  REJECTED, COMPLETENESS, odoo-ecosystem, competitors-registry, competitor-features, competitors/*.md, industry-model, subsegments-deep,
  `owner-page/{index,competitors,rejected}.html`);
- гілка `flow/A-21-real` @ `74c90ca81993f871d46316bee87a2a33dac0d9f3` — `docs/industries/mebli/prototype-real/` (`PLAN.md`, `README.md`, `SHOW.tpl.md`,
  `brand-todo/`, `shoot/*.mjs|*.sh|*.html|brand.css`, `video/rec/*.json`); читати `git -C /home/user/industry-flow-test-mebli show flow/A-21-real:<шлях>`.

Скорочення: **WP** — пакет робіт; **F** — фінальна інтеграція; **К-xx** — канонічне рішення (розділ 1); `<FR>` = `plugins/flow-research`,
`<FC>` = `plugins/flow-core`, `<FB>` = `plugins/flow-package-build`, `<FE>` = `plugins/flow-package-evolution`, `<FD>` = `plugins/flow-client-delivery`.

---

## 0. Загальні правила для всіх виконавців (Sonnet, одна сесія на WP)

1. Міняти **лише** файли зі списку «Файли» свого WP. Потрібна правка чужого файла → рядок у відповіді «ЗАПИТ до WP-xx: …», файл не чіпати.
2. Не бампати `version`, не правити `README.md` плагінів і кореня, `marketplace.json` — це робить F. Не комітити.
3. Мова файлів — українська. Дані клієнтів — лише коди (K-xx, П-xx); з еталона «меблі» в плагіни копіювати **структуру** (заголовки, колонки,
   позначки, CSS/JS), не меблевий зміст; бінарники зі зрізу (png, mp4) не копіювати, крім `brand-todo/` (WP-04).
4. `description` скіла ≤900 символів (зараз деякі 880–897: правити опис лише разом із перевіркою довжини). Перевірка — команда §2.0.3.
5. Новий скіл — повна структура: `SKILL.md` (frontmatter `name`, `description` з тригерами й «НЕ для …»; розділи як у сусідніх скілах:
   Мета · Наряд і звіт · Інструменти та доступи · Що чиє · Кроки · Автоперевірка · Pre-save верифікація · Наступний крок · Відкриті питання ·
   Чого НЕ робити), `references/`, `scripts/` (за потреби), `evals/evals.json` (формат `{"skill_name", "evals":[{"id","prompt",
   "expected_output","assertions","input"}]}`, ≥5 кейсів, з них ≥2 з хронології «меблі» за таблицею §2.0.2).
6. Скрипти перевірок — `python3 -I`, лише stdlib, вихід — JSON-список `[{"id","status","msg"}]` (`PASS|FAIL|WARN|SKIP|MANUAL`), код 1 при FAIL
   (як `concept-mapper/scripts/check_concept.py`). Кожен скрипт має фікстури `evals/fixtures/<скрипт>-ok|-bad/` і рядок у `evals.json`.
7. Готовність WP: `claude plugin validate plugins/<плагін>` для кожного зміненого плагіна — без помилок; скрипти зелені на `-ok`, червоні на `-bad`;
   відповідь координатору ≤15 рядків: що зроблено, `git diff --stat` (без коміту — `git status --short`), відкриті питання, «ЗАПИТИ до WP».
8. Відкриті питання до людини не вирішувати: рядок у розділі «Відкриті питання» скіла (і в §5 цього плану, якщо їх ще немає).

### 0.1 Файлова власність (без перетину)

| WP | Виключно свої файли / теки |
|---|---|
| WP-01 | `<FC>/references/{flow-map,step-skill-map,naryad-format,report-format,id-patterns,flow-state,odoo-bridge,conventions,flow-step-run}.md`, нові `<FC>/references/{step-cards,rejected-register}.md`; `<FC>/skills/flow-orchestrator/**` |
| WP-02 | `<FC>/references/{data-policy-template,data-and-connections,pii-patterns,c00-checklist}.md`, `<FC>/references/templates/tools-odoo/**`; `<FC>/agents/{flow-executor,flow-executor-research}.md`, нові `<FC>/agents/{flow-executor-research-internal,flow-executor-content}.md`; `<FC>/skills/ci-pipeline-builder/**` |
| WP-03 | `<FC>/skills/flow-autocheck/**` (усі `references/checks/*.yaml`, нові скрипти); нова `<FC>/references/review-checklists/**`; `<FC>/agents/flow-reviewer.md` |
| WP-04 | `<FR>/references/**` крім `concept-templates.md` і `odoo19-ui-kit.md` (нові: `templates/**`, `needs-sources-catalog.md`, `completeness-checklist.md`, `brand-todo/**`, `PAGE-CONTRACT.md`; правка `sources-format.md`) |
| WP-05 | нові `<FR>/skills/owner-questionnaire/**`, `<FR>/skills/reuse-modules/**`; `<FR>/skills/{past-projects-analyzer,industry-scoring,segment-selector}/**` |
| WP-06 | новий `<FR>/skills/industry-deep-dive/**` |
| WP-07 | `<FR>/skills/concept-mapper/**`, новий `<FR>/skills/completeness-audit/**`, `<FR>/references/concept-templates.md` |
| WP-08 | новий `<FR>/skills/concept-presentation/**` |
| WP-09 | `<FR>/skills/prototype-builder/**`, `<FR>/references/odoo19-ui-kit.md` |
| WP-10 | новий `<FR>/skills/showcase-content/**`; `<FR>/skills/demand-test-runner/**` |
| WP-11 | `<FC>/skills/{flow-step-runner,flow-state-keeper,eval-builder}/**`, новий `<FC>/skills/skill-retro/**`; `<FD>/skills/support-desk/**` |
| WP-12 | `<FB>/skills/**`, `<FB>/references/**`; `<FE>/skills/{backlog-triage,odoo-version-migrator,product-decision-drafter}/**`; `<FD>/skills/{package-fit-gap,package-sow-builder,client-data-migrator,package-upgrade-runner,runbook-executor}/**`, `<FD>/references/**` |
| F | `plugins/*/.claude-plugin/plugin.json`, `plugins/*/README.md`, `README.md`, `.claude-plugin/marketplace.json`, `_work/LESSONS-A21-real.md` (лише заміна кодів і «Заст.») |

Без змін: `<FE>/skills/package-usage-metrics`, `<FD>/skills/client-help-bot` (FTR §4.2).

---

## 1. Канон: узгоджені рішення (для всіх виконавців)

### 1.1 Порядок кроків (FTR 2.1, §5; С-03, С-04, С-15) — єдина нумерація

`A-01 → A-02 (гейт) → A-02b → A-03 ∥ A-04 → [шлюз сесій → A-05 → A-06] → A-03b (K1) → A-03c (гейт) → A-20 → A-20b → A-20c (єдиний гейт концепції)
→ A-21 (зразок → повний обсяг → гейт) → A-21c (гейт) → A-23 список/prep/results → A-07 …`; наскрізний **C-08R** «Ретро скілів» (щодня + за подією).

| Код | Крок | Ведучий скіл | Профіль | Людина |
|---|---|---|---|---|
| A-02b | Анкета власника | `flow-research:owner-questionnaire` (`prepare` → `validate` → `amend`) | `base` | заповнює власник ≤20 хв (`waiting_human`) |
| A-03b | Глибокий аналіз галузі й конкурентів, K1 усередині | `flow-research:industry-deep-dive` | `research-internal` | K1 — відповіді власника (не кнопка) |
| A-03c | Готові модулі ToDo у збірку | `flow-research:reuse-modules` (`inventory` → `session` → `decide`) | `research-internal` | гейт: сесія з власником |
| A-20 | Концепція + OWNER-BRIEF + BOX + SALES + REJECTED | `flow-research:concept-mapper` | `research` | гейта немає (перенесено в A-20c) |
| A-20b | Аудит повноти (5 ролей) | `flow-research:completeness-audit` | `base` | ні |
| A-20c | Сторінка для власника (1 Artifact, 3 сторінки) | `flow-research:concept-presentation` | `base` | **гейт концепції** |
| A-21 | Реальний зріз Odoo 19 `td_*` + живий запис + `facts.json` | `flow-research:prototype-builder` | `repo` | зразок (N-18), потім гейт |
| A-21c | Продаючі матеріали | `flow-research:showcase-content` | `content` | гейт; виконавець — контент-менеджер (`executor: any`) |
| A-22 | База зрізу для гарячого ліда (без емуляції `x_`) | `flow-package-build:demo-base-builder` | `base` | — |
| C-08R | Ретро скілів | `flow-core:skill-retro` | `repo` | щоденний пакет — кнопка Власника продукту |

### 1.2 Узгодження суперечностей FTR §3

| К | С | Канон |
|---|---|---|
| К-01 | С-01 | Поріг доказів — параметр анкети `ambition.scope: full\|mvp`, `ambition.evidence_gate: risk\|block`; за замовчуванням `full`/`risk`. Брак болів/розмітки/тріалів **не зупиняє** A-20: ризик іде в план перевірки A-23. L§9 «stop» переписати. |
| К-02 | С-02, С-12 | «≥2 незалежні типи джерел» — **позначка ризику, не фільтр складу**. Новий тип доказу `owner-decision` («рішення власника / досвід ринку»), доказовість не підвищується. Кандидати на відкидання показуються в K1 **до синтезу**; дашборд покупця — у замовчуванні «не відкидати». |
| К-03 | С-03 | Нумерація — лише таблиця 1.1; «A-03b концепція для власника», «новий крок перед A-21», «A-20c аудит» у тексті скілів заборонені. F замінює в LESSONS. |
| К-04 | С-04 | Аудит A-20b — над документами **до** сторінки; сторінка A-20c — остання; один гейт власника. |
| К-05 | С-05, L§21 №19 | Вхід A-21 — `FUNCTIONAL-MAP §4`, `BOX`, `SALES §2/§6`, `REUSE.md`, а не попередній зріз. Блок «порівняння з поточним зрізом» на сторінці — лише якщо зріз уже існує. |
| К-06 | С-06 | Ядро — Odoo 19 CE; EE — підсилення через окремі `td_*_ee` (auto_install). Зріз A-21 — на `demo_edition` з анкети (типово CE), EE — позначкою. Каркас `td_*_ee` і CI на обох редакціях — з A-10/A-11. Формулу «td_ лише для CE» вилучити. |
| К-07 | С-07, §5 | Дані ToDo дозволено (лише читання) за полем анкети `todo_data`; до валідної анкети — лише `internal-aggregated`. Сирі спостереження — `internal-raw` **у репо галузі** `docs/industries/<галузь>/research/sources/`; знеособлені висновки — `research/*.md` і сторінки. Пуш `sources/` — лише якщо preflight C-00 підтвердив дозвіл середовища. `internal-raw` ніколи не йде в продаючі матеріали й публічні артефакти. |
| К-08 | С-08, §5 | Журнал рішень: AI вносить рядки в `flow/decisions.md` **за повідомленням власника** з позначкою «внесено AI від імені власника» і посиланням на повідомлення/задачу (режим `decisions-batch` у `flow-state-keeper`); без посилання — FAIL. У бойовому флоу — кнопка в задачі Odoo. Рішень гейтів AI не вигадує. |
| К-09 | С-09, L§21 №14 | Основа функції: `Стд CE` · `Стд EE` · `td_` (новий) · `ToDo-готовий` (A-03c) · `Інтегр`. «OCA» — лише «ідея з OCA, пишемо в `td_`»; години — як розробка; стан гілки OCA 19.0 — довідково. Ядро без AGPL-залежностей; ліцензія наших модулів — LGPL-3 (або OPL за рішенням власника). |
| К-10 | С-10 | Контент — окремий скіл `showcase-content` і крок A-21c; A-21 віддає безперервний запис, сцени, `facts.json`. Перемонтаж — без перезйомки й без доступу до Odoo. |
| К-11 | С-11 | A-22 = «база зрізу для гарячого ліда» в `demo-base-builder`; режим «емуляція» (Studio/`x_`) вилучити. |
| К-12 | С-13 | Переліки «чого немає в CE» і «EE-підсилення» — лише рядками `edition-claims.md` з вердиктом `повністю/частково/ні/не перевірено` + доказ (CE — файл:рядок коду 19.0; EE — URL документації 19.0 + цитата або база EE); з тексту скілів як факт — прибрати. Години мостів — від вердиктів. |
| К-13 | С-14 | «Новий» у кадрі — поле анкети `prototype.new_record_in_frame`; типово `false` (зберігати запис до кадру). |
| К-14 | С-15 | Шлюз «Потрібні сесії?» читає `ambition.sessions_a05_a06` з анкети; A-05/A-06 — необов'язкова гілка з AND-join в A-20. |
| К-15 | С-16 | Профілі конкурентів — **8–12** скрізь. |
| К-16 | Заст. | Конкретні дефекти зрізу «меблі» (L§6–8: мобільний конфігуратор, ціна від розміру) — у беклог A-11 «меблів», у скілах — лише правила. Шапку LESSONS «очікує підтвердження» F замінює на «внесено в пакет 0.2.0, план IMPLEMENTATION-PLAN». |

### 1.3 Рішення людини FTR §5 (обов'язкові) і рішення плану

| К | Канон |
|---|---|
| К-17 | Порядок кроків і анкета A-02b (14 блоків, замовчування — рішення «меблів») — прийнято (§5). |
| К-18 | A-03c = AI-інвентаризація (GitHub-репо ToDo, AIKB, проєкти) з критеріями: Odoo 19, CE/EE, права на код, тести, підтримка, відповідність карті функцій → сесія з власником → рішення «беремо / адаптуємо / ні» → `research/REUSE.md` + перерахунок годин (§5). |
| К-19 | Сирі внутрішні дані — у репо галузі `research/sources/`, клас `internal-raw`; передумова — пункт C-00/preflight «дозвіл середовища на push» (§5). FTR N-06 №9 «поза git» замінюється на «лише в `research/sources/`». |
| К-20 | **Рішення плану** (людина може змінити до старту): шаблон анкети живе в скілі `owner-questionnaire/references/owner-intake-template.md` (а не в `<FC>/references/templates/`); `check_intake.py` читає його звідти. |
| К-21 | **Рішення плану**: OWNER-BRIEF пише A-20 (`concept-mapper`); A-03b пише лише `FUNCTIONAL-MAP §5 «Резюме для власника»`. |
| К-22 | **Рішення плану**: профілі доступу — нові `research-internal` (агент `flow-executor-research-internal`) і `content` (`flow-executor-content`); `research` лишається без власної ERP/Gmail/Unitalk. A-21 — профіль `repo` (GitHub-читання модулів REUSE + WebFetch документації Odoo 19). Bash/Odoo/Playwright/ffmpeg для A-21, A-21c виконує runner за рядками «КОМАНДИ:» (як зараз). |
| К-23 | **Рішення плану**: `prototype.fidelity: mock` у 0.2.0 не підтримується (HTML-оболонку вилучити); значення `mock` → `waiting_human` з поясненням. |
| К-24 | **Рішення плану**: реєстр уроків — `flow/lessons/LSN-xxx.md` + `flow/lessons/INDEX.md` у репо флоу (експорт `flow-state-keeper`); прогалини повноти — `G-xx` у `COMPLETENESS.md`. |
| К-25 | **Рішення плану**: версії — усі 5 плагінів `0.1.0 → 0.2.0` (нові скіли й кроки), синхронно в `marketplace.json` (F). |

### 1.4 Спільні формати (фіксує план; власник файла — у дужках)

- **Класи даних** (`data-policy-template.md`, WP-02; `report-format.md`, WP-01): `none | commercial | personal | internal-aggregated | internal-raw`.
- **Поля звіту** (WP-01): `rejected_count`, `rejected_ref`, `completeness: {closed, partial, open}` (A-20b/A-20c), `review_rounds`, `human_rounds`,
  `sample: true|false`, `accepted_ref` (N-11), `stale: []` (N-07), `data_sources[].class`.
- **Ключі наряду** (WP-01): `review.checklists: [<файл>]`, `review.max_rounds: 2` (+1 контрольний), `params.sample: true`, `params.mode: recalc`
  (перерахунок N-07), `resume` для K1 і зразка, `inputs` з `OWNER-INTAKE.md` для A-03b…A-21c, `odoo_connections` з alias `own-erp` (лише читання).
- **Реєстр відкинутого** (`<FC>/references/rejected-register.md`, WP-01): колонки `ID · назва · група · причина · доказ · умова повернення · де живе зараз · рішення (K1/гейт, дата)`;
  групи `G1 поза пакетом | G2 не в першій версії | G3 інший підсегмент/профіль | G4 понижено в попередньому артефакті | G4а повернуто рішенням власника`;
  місце — `<артефакт>-rejected.md` або розділ `## Відкинуто`; журнал знятих рішень із датою. Великий шаблон A-03b/A-20 — `REJECTED.tpl.md` (WP-04) поверх цього формату.
- **ID** (`id-patterns.md`, WP-01): `G-\d{2}`, `LSN-\d{3}`, `K1-Q\d+`, `EC-\d{3}` (рядок edition-claims), `REUSE-\d{2}`, тип доказу `owner-decision`.
- **Анкета** `docs/industries/<галузь>/OWNER-INTAKE.md` (WP-05; читають WP-03, -06, -07, -08, -09, -10, -12). YAML-блок, `*` — блокуючі:
  `editions*` (`ce|ee|both`), `ee_bridges*` (`now|later`), `demo_edition*`, `market*` {country, language, localization, accounting_system, accounting_mode},
  `icp*` {min_employees, revenue_min, legal_forms, light_tariff_fop}, `ambition*` {scope, evidence_gate, company_marking, trials, sessions_a05_a06},
  `pricing*` {ce_entry, ee_upgrade, box_fixed_price, pilot}, `todo_data*` {allowed_sources, mode: read, internal_raw_storage: repo-sources, push_deidentified},
  `do_not_reject*` {items, class_rule, n}, `licenses` {own_modules, oca: idea|dependency}, `reuse` {repos, projects}, `brand` {materials, demo_client, white_label},
  `materials` {formats: [video_16x9, reels_9x16, mobile, one_pager], languages}, `prototype` {fidelity, new_record_in_frame},
  `legal_ambiguous` {to_answers_yaml}, `rounds` {review_max, review_control, human_target}.
- **Файли галузі**: `research/{sources-log.md, sources/, facts.yaml, DEPENDS.yaml, K1.md, REUSE.md, COMPLETENESS.md, owner-page/{index,competitors,rejected}.html, owner-page/PUBLISHED.md}`;
  зріз — `package/addons/td_<галузь>_*` + `docs/industries/<галузь>/prototype-real/{PLAN.md, README.md, screens/, screens-mobile/, shoot/, video/rec/, facts.json, ACCEPTED.md}`;
  матеріали A-21c — `prototype-real/{video/*-16x9.mp4, video/*-9x16.mp4, SHOW.md|html|pdf, captions.yaml, ACCEPTED.md}`.

---

## 2. Пакети робіт

### 2.0 Спільні таблиці

#### 2.0.1 Контракт 11 автоперевірок (N-06): назва, місце, CLI — фіксовані

| № | Скрипт | Місце (хто пише) | CLI (з кореня репо галузі) | ID перевірок |
|---|---|---|---|---|
| 1 | `check_intake.py` | `<FC>/skills/flow-autocheck/scripts/` (WP-03) | `<OWNER-INTAKE.md> [--brief OWNER-BRIEF.md] [--page owner-page/index.html]` | INT-file, INT-block, INT-dup |
| 2 | `check_rejected.py` | там само (WP-03) | `<реєстр або артефакт> [--intake OWNER-INTAKE.md] [--k1 research/K1.md]` | REJ-exists, REJ-fields, REJ-dnr, REJ-count |
| 3 | `check_edition_claims.py` | `<FR>/skills/industry-deep-dive/scripts/` (WP-06) | `<research/edition-claims.md>` | EC-verdict, EC-evidence, EC-partial |
| 4 | `check_facts.py` | `<FC>/skills/flow-autocheck/scripts/` (WP-03) | `<facts.yaml\|facts.json> <файли/теки…>` | FACT-mismatch, FACT-orphan |
| 5 | `check_owner_page.py` | `<FR>/skills/concept-presentation/scripts/` (WP-08) | `<research/owner-page> [--research research]` | OP-pages, OP-nav, OP-anchors, OP-contract, OP-target |
| 6 | `check_video.py` | `<FR>/skills/showcase-content/scripts/` (WP-10) | `<prototype-real/video> --intake OWNER-INTAKE.md` | VID-format, VID-freeze, VID-frames |
| 7 | `check_ui_text.py` | `<FR>/skills/prototype-builder/scripts/` (WP-09) | `<prototype-real/shoot/dom> [--lang uk]` | UI-english, UI-new, UI-empty |
| 8 | `check_brand.py` | `<FC>/skills/flow-autocheck/scripts/` (WP-03) | `<файли/теки…> --brand <BRAND.md>` | BR-colors, BR-font, BR-logo |
| 9 | `check_privacy.py` | там само (WP-03) | `<research> [--pages research/owner-page] [--materials prototype-real]` | PRV-pii, PRV-raw-place |
| 10 | `check_lessons.py` | `<FC>/skills/flow-step-runner/scripts/` (WP-11) | `--remarks <файл зауважень сесії> --observations observations/` | LSN-coverage |
| 11 | `check_stale.py` | `<FC>/skills/flow-autocheck/scripts/` (WP-03) | `<research/DEPENDS.yaml> --base <sha>` | STALE-list |

Специфікації `checks/*.yaml` (WP-03) посилаються на ці шляхи рядками `prim: manual, who: runner`; зміна CLI після WP-03 — лише через координатора.

#### 2.0.2 Евал-кейси з хронології «меблі» (N-17): зауваження FTR §1 → кейс → WP

| FTR §1 № | Кейс (id) | Скіл | WP |
|---|---|---|---|
| 1 | `mebli-r01-html-mock-instead-of-slice` | prototype-builder | 09 |
| 2, 7 | `mebli-r02-not-selling`, `mebli-r07-regress-approved-dynamics` | showcase-content | 10 |
| 3 | `mebli-r03-no-brand` | showcase-content (+ check_brand) | 10 |
| 4, 6 | `mebli-r04-formats-mobile`, `mebli-r06-static-frames` | showcase-content | 10 |
| 5 | `mebli-r05-buyer-without-dashboard` | concept-mapper | 07 |
| 8 | `mebli-r08-content-role-missing` | showcase-content | 10 |
| 9, 17 | `mebli-r09-no-lesson`, `mebli-r17-remark-not-recorded` | skill-retro, flow-step-runner | 11 |
| 10, 18 | `mebli-r10-shallow-industry`, `mebli-r18-sources-coverage` | industry-deep-dive | 06 |
| 11, 15 | `mebli-r11-md-not-page`, `mebli-r15-three-pages` | concept-presentation | 08 |
| 13 | `mebli-r13-no-rejected-register` | industry-deep-dive, concept-presentation | 06, 08 |
| 14 | `mebli-r14-competitor-names-only` | industry-deep-dive | 06 |
| 16, 24 | `mebli-r16-editions-asked-late`, `mebli-r24-owner-questions-after-synthesis` | owner-questionnaire | 05 |
| 19 | `mebli-r19-internal-raw-push` | past-projects-analyzer (+ preflight) | 05 |
| 20 | `mebli-r20-no-reuse-block` | reuse-modules | 05 |
| 21 | `mebli-r21-incomplete-concept` | completeness-audit | 07 |
| 22 | `mebli-r22-ee-claim-unverified` | industry-deep-dive | 06 |
| 23 | `mebli-r23-owner-returned-rejected` | industry-deep-dive (K1), concept-mapper | 06, 07 |
| С-01 | `mebli-c01-ai-recommends-against-intake` | concept-mapper | 07 |

Кейс посилається на еталон шляхом і SHA (§заголовок), а не копією даних. Індекс — `eval-builder/references/gold/mebli.md` (WP-11).

#### 2.0.3 Команди перевірки
```bash
claude plugin validate plugins/<плагін>        # кожен змінений плагін
claude plugin validate .                         # маркетплейс (F)
python3 - <<'EOF'                               # довжина description (≤900)
import glob,re
for f in glob.glob('plugins/*/skills/*/SKILL.md'):
    fm=open(f).read().split('---')[1]; m=re.search(r'description:\s*>?\s*\n?(.*?)(\n[a-z_-]+:|\Z)',fm,re.S)
    n=len(' '.join(m.group(1).split())); print(('FAIL ' if n>900 else '')+str(n), f) if n>860 else None
EOF
```

---

### WP-01. Карта флоу, картки кроків, контракти наряду й звіту, оркестратор
- **Файли:** див. 0.1 (WP-01).
- **Закриває:** L§2 (карта, A-22), §4 (роль), §9, §11 (формат), §12, §14 (перерахунок), §17, §18, §21 №19; FTR N-03, N-07 (наряд), N-10, N-12 (тип доказу), N-16 (колонки), N-18 (ключ); С-03, С-04, С-11, С-15; SL §6 (крок C-08R, межі C-04/C-07).
- **Зробити:**
  1. `flow-map.md`: пул A — рядки за 1.1 (A-02 → A-02b → A-03∥A-04 → шлюз «Потрібні сесії?» за `ambition.sessions_a05_a06` → A-03b (K1: `waiting_human` з `resume`) → A-03c (гейт) → A-20 → A-20b → A-20c (гейт, `gate.return_to` ∈ {A-20, A-03b, A-03c}) → A-21 (зразок `waiting_human` → повний → гейт; Повернути → A-21 або A-20) → A-21c (гейт; Повернути → A-21c або A-21) → A-23 `список`); прибрати гейт A-20; A-22 — «база зрізу для гарячого ліда»; рядок «зміна рішення власника / `facts.yaml` → наряд `params.mode: recalc` за списком `check_stale`». Пул C — C-08R (щодня + події «Повернути», `escalated`, червоний CI), межа з C-04/C-07.
  2. `step-skill-map.md`: рядки A-02b, A-03b, A-03c, A-20b, A-20c, A-21c, C-08R, A-22 (без «емуляції»); `access_profile`: додати `research-internal` (industry-deep-dive, past-projects-analyzer, reuse-modules, industry-scoring, segment-selector) і `content` (showcase-content); prototype-builder → `repo`; concept-mapper лишити `research`.
  3. Новий `step-cards.md`: чернетки карток для A-02b, A-03b, A-03c, A-20, A-20b, A-20c, A-21, A-21c, A-22, A-23, C-04, C-07, C-08R (код, назва, `raciR`, `executor`, `skillRef`, `access_profile`, `inArtifacts`, `outArtifacts`, гейт, `review.checklists`, `params.sample`, ліміти моделі/годин/$, стартова зрілість 1, ескалація); розділ «Ролі» з новою роллю **Контент-менеджер (маркетинг)** (людина зі своїм Claude, `executor: any`; A-21c, A-23 `prep` тексти, D-05 кейси, A-18 матеріали релізу; лише контент у репо, клас `commercial`, без баз Odoo, крім читання наряду) і **AI-інженер / агент Ретро**.
  4. `naryad-format.md`: ключі з 1.4; режими A-02b (`prepare|validate|amend`), A-03c (`inventory|session|decide`), C-08R (`daily|event`), `recalc`; K1 і зразок — `waiting_human` + `resume`.
  5. `report-format.md`: поля з 1.4, класи даних; `human_rounds > 2` → сигнал C-08R.
  6. `id-patterns.md`: ID з 1.4. `flow-state.md` §3: колонка/позначка «внесено AI від імені власника» + посилання на повідомлення; §1 — облік уроків LSN і метрик якості. `odoo-bridge.md`: K1 і зразок як `human_substep`; кнопка «пакет рішень».
  7. Новий `rejected-register.md` (формат 1.4) з переліком кроків, що зобов'язані його писати: A-01, A-03b, A-03c, A-04, A-05/B-01, A-20, A-20c, A-21, A-23, B-02, D-02, D-05, A-07.
  8. `flow-orchestrator` (SKILL.md, `references/dispatch-rules.md`, `sweep-rules.md`): постановка в новому порядку; шлюз сесій з анкети; K1/зразок як `human_substep`; наряд `recalc`; C-08R за розкладом; описи ≤900.
- **Еталони:** FTR 2.1, 2.7 (N-07, N-10, N-16, N-18); SL §2, §6; L§4.
- **Готово:** у `flow-map.md` є всі 7 нових кодів і немає гейта A-20; `grep -n "емуляц" step-skill-map.md flow-map.md` — 0; кожен код з 1.1 є в `step-cards.md`; `rejected-register.md` має 8 колонок і 5 груп; `validate plugins/flow-core` PASS; евал оркестратора `+2` кейси (K1 не ставить A-03c до відповіді; `recalc` ставить усі застарілі).
- **Залежності:** немає (перший).

### WP-02. Дані, середовище C-00, агенти-виконавці, CI на CE і EE
- **Файли:** див. 0.1 (WP-02).
- **Закриває:** L§1.1 (локальне Odoo 19), §2 (tools-odoo), §13 (C-00 CE/EE, CI), §16, §17 (доп.: сховище, push), §21 №12; FTR N-08, С-07, К-19, К-22; 4.3 (data-policy, агенти).
- **Зробити:**
  1. `data-policy-template.md`: класи `internal-aggregated` / `internal-raw`; дозвіл внутрішніх даних ToDo (лише читання: власна ERP `own-erp`, Fathom, Unitalk — лише наявні транскрипти, без `transcribe_calls`/`analyze_call` без окремого прохання людини, AIKB, Drive, Gmail read, репо минулих проєктів); межі (прод клієнта заборонено, крім q37; коди K-xx/П-xx; без ПІБ, телефонів, e-mail, сум угод, дослівних цитат клієнтів у висновках); правило «`internal-raw` — лише `research/sources/`, не в продаючих і публічних артефактах»; новий заголовок → F перевіряє, що `C-05.yaml` (WP-03) знає кількість заголовків (ЗАПИТ до WP-03, якщо змінюється з 9).
  2. `data-and-connections.md`: alias `own-erp` (лише читання, `connection_id` явно); вибірки з ERP — повний перебір із пагінацією, розмір вибірки й критерій у звіті, ID вибірки — лише в `sources/`. `pii-patterns.md`: патерни для `check_privacy` (коди K-xx дозволені, суми угод і цитати з `internal-raw` — FAIL поза `sources/`).
  3. `c00-checklist.md`: Odoo 19 CE (скрипти `tools/odoo`), доступ до EE або запис «EE недоступна → твердження лише з документації»; Playwright + Chromium; ffmpeg/ffprobe; шрифт Open Sans; бренд-кіт; дозвіл середовища на push `research/sources/` (К-19); alias `own-erp`, Fathom, Unitalk read у профілі `research-internal`; публікація Artifact; оновлення карток за `step-cards.md`.
  4. `templates/tools-odoo/`: `ODOO_EDITION=ce|ee` і `ODOO_EE_ADDONS_PATH` у `_common.sh`, `install.sh`, `reset.sh`, `run_tests.sh`, README; новий `preflight.sh` (JSON-вихід як 0.6; FAIL → runner ставить `waiting_human` до витрати бюджету); оновлення перекладів мови показу з перезаписом (L§7).
  5. Агенти: новий `flow-executor-research-internal.md` (інструменти `research` + odoo-mcp `odoo_search_read`/`odoo_get_fields`/`list_odoo_connections` лише на `own-erp` з брифу; Fathom read; Unitalk: `list_transcriptions`, `get_transcription`, `get_call_history`, `get_call_stats`, `get_operator_stats`, `list_users`, `list_departments`; Gmail: `search_threads`, `get_thread`, `get_message`, `list_labels`; GitHub read: `get_file_contents`, `list_branches`, `list_commits`, `list_tags`; без `get_company`, без запису); новий `flow-executor-content.md` (Read/Write/Edit/Grep/Glob/Skill, без конекторів даних; команди монтажу — «КОМАНДИ:»). `flow-executor-research.md`, `flow-executor.md` — лише посилання на нові профілі.
  6. `ci-pipeline-builder`: матриця CE і EE; `workflow_dispatch` вхід `edition`; EE-job без доступу до EE → `WARN ee-unavailable`, не PASS; заборона AGPL-залежностей у ядрі (перевірка `__manifest__` `depends` проти переліку вендорованих з ліцензією); `references/ci-workflow-template.yml`, `ci-contract.md`, `check_ci.py`, евали +2.
- **Еталони:** `factory3d/tools/odoo/` (якщо є в `/home/user/todo_timur/factory3d/tools/odoo`), `prototype-real/shoot/build_db.sh`, L§16–17.
- **Готово:** `bash -n` для всіх `.sh`; `preflight.sh` без середовища дає JSON із FAIL/WARN, а не падіння; у `flow-executor-research-internal.md` немає жодного інструмента запису (`grep -E "create|write|execute|send|draft|transcribe|analyze"` — 0); `check_ci.py` зелений на фікстурі з двома редакціями; `validate plugins/flow-core` PASS.
- **Залежності:** WP-01 (назви профілів у `step-skill-map.md`).

### WP-03. Перевірки: flow-autocheck (11 перевірок), yaml-специфікації, чек-листи рецензента
- **Файли:** див. 0.1 (WP-03).
- **Закриває:** L§1.9–1.10, §2 (бриф рецензента), §10 (критерій рецензента), §11 (FAIL без реєстру), §12, §18 (spec A-20c→A-20b), §19; FTR N-05, N-06 (усі 11), N-07, N-01 (критерій `inputs`).
- **Зробити:**
  1. Скрипти №1, 2, 4, 8, 9, 11 за 2.0.1 з фікстурами `-ok/-bad`; `check_rejected` читає колонки з `<FC>/references/rejected-register.md`; `check_brand` — токени з `BRAND.md`; `check_privacy` — `pii-patterns.md`.
  2. Нові yaml: `A-02b`, `A-03b`, `A-03c`, `A-20b`, `A-20c`, `A-21c`, `C-08R`; оновити `A-01`, `A-04`, `A-05`, `A-07`, `A-20`, `A-21`, `A-22`, `A-23`, `B-02`, `D-02`, `D-05` (реєстр «Відкинуто» — `check_rejected`; `exists` на `OWNER-INTAKE.md` для A-03b/A-20/A-21/A-21c у режимі `inputs` → FAIL без анкети; скрипти №3, 5, 6, 7, 10 — рядки `manual who: runner` з CLI 2.0.1; A-20b — `COMPLETENESS.md` є, кожен пункт чек-листа має статус і відповідального, немає critical desk-прогалин; A-20c — №5, 8, 4, 9; A-21 — №7, 4, odoo19-lint, тести модулів, без `x_`, консоль без помилок; A-21c — №6, 8, 4, 9).
  3. `references/checks.md`: розділ «Перевірки за кроками» для нових кодів; `SKILL.md` — режими й опис ≤900.
  4. Нові `<FC>/references/review-checklists/{research,edition-claims,concept,completeness,owner-page,prototype,video-materials}.md` — пункти FTR 2.5 дослівно за змістом, кожен пункт «ні» = major, minor що впливає на рішення власника = major; шапка «відкрий результат: сторінку, кадри, PDF».
  5. `agents/flow-reviewer.md`: завантажує чек-листи з ключа наряду `review.checklists`; обов'язково відкриває результат (зображення, кадри, сторінку) — інструменти лишаються Read/Grep/Glob.
- **Еталони:** FTR 2.5, 2.6; наявні `checks/A-20.yaml`, `checks.md` §«Примітиви»; `check_concept.py` (формат виходу).
- **Готово:** 6 скриптів зелені/червоні на своїх фікстурах; усі yaml — валідний JSON (`python3 -c json.load` по всіх); у yaml 12 кроків-відбору є перевірка реєстру; `autocheck.py --self-test` (або наявні евали) зелені; 7 чек-листів; `validate plugins/flow-core` PASS.
- **Залежності:** WP-01 (коди, формат реєстру, поля звіту); WP-04 бажано раніше (заголовки шаблонів для `headings_from`) — інакше `headings` додає F.

### WP-04. Шаблони з еталона, каталог джерел, чек-лист повноти, бренд ToDo, контракт сторінки (flow-research/references)
- **Файли:** див. 0.1 (WP-04).
- **Закриває:** L§1.4, §10, §11 (подача), §12, §15, §18 (чек-лист), §19 (шаблон); FTR N-04, N-15, 2.4 (усі 10 шаблонів).
- **Зробити:**
  1. `templates/`: `FUNCTIONAL-MAP.tpl.md`, `odoo-ecosystem.tpl.md`, `edition-claims.tpl.md`, `competitors.tpl.md` (реєстр за типами, матриця з рядками «Odoo 19 Community», «Odoo 19 Enterprise», «наш пакет ◎», профілі 8–12), `OWNER-BRIEF.tpl.md` (§1–10), `BOX.tpl.md` (§1–13 + 1а), `SALES.tpl.md` (§1–7), `REJECTED.tpl.md` (групи 1–4, 4а, 5 поверх `rejected-register.md`), `COMPLETENESS.tpl.md` (§1–3), `facts.yaml`, `DEPENDS.yaml`, `K1.tpl.md` (≤10 питань з рекомендацією й замовчуванням: підсегмент, кандидати на відкидання, прогалини джерел) — заголовки й колонки з еталона, без меблевого змісту, з коментарем «звідки» (файл еталона + §).
  2. `templates/owner-page/{index,competitors,rejected}.html`: каркас з еталона (навігація 3 сторінок, токени бренду, світла/темна тема, блок рішень із «Скопіювати мої відповіді» у формат рядків `decisions.md`, `localStorage` у try/catch, 390/1280 px); `index.html` — без doctype за `PAGE-CONTRACT.md`, `competitors.html`/`rejected.html` — з власним doctype/meta (багатофайловий Artifact); плейсхолдери `{{…}}`; кожен ≤60 KB, без `img/` еталона.
  3. `PAGE-CONTRACT.md` — з `_work/templates/` + розділ «багатофайловий Artifact, той самий URL, копія в `research/owner-page/`, `PUBLISHED.md` з URL».
  4. `needs-sources-catalog.md`: 8 груп L§15 з позначкою «AI сам / потрібна людина / потрібне рішення про дані», мінімум: внутрішні сигнали ToDo обов'язково + ≥4 групи з 8; правила: цитата в лапках лише після звірки на сторінці; переказ WebFetch — таблиця «не звірено»; «пропозиція нашого продавця» ≠ попит; ERP — повний перебір.
  5. `completeness-checklist.md` — 22 пункти L§18 + 5 ролей рецензентів; `sources-format.md` — формат `research/sources-log.md` (що, звідки, дата, клас даних).
  6. `brand-todo/`: `BRAND.md`, `todo-logo.png`, `todo-mark.png`, `fonts/OpenSans-*.ttf` + ліцензія Apache 2.0 — з `flow/A-21-real:…/prototype-real/brand-todo/`.
- **Еталони:** `research/*.md` і `owner-page/*.html` (A-03b-deep), `prototype-real/brand-todo/` (A-21-real), `_work/templates/PAGE-CONTRACT.md`.
- **Готово:** 13 шаблонів + 3 HTML; `grep -ciE "мебл|кухн|ДСП|фасад"` у `templates/` — 0 (крім коментарів «звідки»); HTML-каркаси відкриваються Playwright на 390 і 1280 без горизонтальної прокрутки (`scrollWidth ≤ clientWidth`); `validate plugins/flow-research` PASS.
- **Залежності:** WP-01 (формат реєстру й колонки `decisions.md`). Паралельно з WP-01 можна, якщо `REJECTED.tpl.md` і блок рішень роблять останніми.

### WP-05. Старт галузі й відбір: owner-questionnaire (A-02b), reuse-modules (A-03c), правки A-01/A-04/A-05
- **Файли:** див. 0.1 (WP-05).
- **Закриває:** L§11 (A-01, A-04, A-05), §13–14 (анкета), §16, §17 (A-03c, межа з A-04, `search_count`), §20–21 (рішення до синтезу); FTR N-01, N-15 (внутрішні дані), К-07, К-17, К-18, К-20; зауваження №16, 19, 20, 24.
- **Зробити:**
  1. **owner-questionnaire** (новий): `prepare` — чернетка `OWNER-INTAKE.md` із замовчуваннями «меблів» (14 блоків 1.4) і попередніх рішень `flow/decisions.md`; `waiting_human` (власник ≤20 хв); `validate` — `check_intake.py`; `amend` — зміна умови → список застарілих (`check_stale`) і наряд `recalc`. `references/owner-intake-template.md` (поля, пояснення простою мовою, замовчування), `references/questions-routing.md` (питання «з анкети / K1 / лише після результату»). Евали ≥5 (r16, r24).
  2. **reuse-modules** (новий): `inventory` — реєстр модулів ToDo (GitHub-репо з `reuse.repos`, AIKB, проєкти власної ERP) з критеріями К-18 → `research/reuse-inventory.md`; `session` — матеріал і питання для сесії з власником; `decide` — `research/REUSE.md` (беремо / адаптуємо / ні, години адаптації ↔ розробки, вплив на основу «ToDo-готовий»), розділ «Відкинуто». Межа з A-04 (A-04 — патерни проєктів, A-03c — код і модулі). Евали ≥5 (r20).
  3. **past-projects-analyzer**: джерела за К-07 (власна ERP, Fathom, Unitalk наявні транскрипти, AIKB, Gmail read); повний перебір із пагінацією, розмір вибірки й критерій у звіті; сирі — `research/sources/` (`internal-raw`), висновки знеособлено; знято вимогу «рішення про підставу обробки» для власних даних ToDo за умови поля анкети `todo_data` (С-07); реєстр «Відкинуто» (проєкти/патерни, що не взяли); межа з A-03c; евал r19.
  4. **industry-scoring**: реєстр «Відкинуто» (галузі поза топом з причиною й умовою повернення); внутрішні агрегати (виграні/програні угоди за КВЕД) як додатковий сигнал з класом `internal-aggregated`.
  5. **segment-selector**: ICP з анкети (`icp.*`, легкий тариф ФОП), розмітку не робити, якщо `company_marking: false`; реєстр відсіяних сегментів/компаній; внутрішні агрегати CRM.
- **Еталони:** FTR 2.2; L§16–17; `research/sources/`-правила; `segment-selector/references/selection-criteria.md`.
- **Готово:** два нові скіли з повною структурою; описи ≤900 (усі 5); `check_past_projects.py` і `check_scoring.py` доповнено перевіркою реєстру або викликом `check_rejected.py` (CLI 2.0.1); евали всіх 5 скілів зелені на фікстурах; `validate plugins/flow-research` PASS.
- **Залежності:** WP-01, WP-02 (профіль `research-internal`), WP-03 (`check_intake`, `check_rejected`), WP-04 (`sources-format`).

### WP-06. industry-deep-dive (A-03b) з контрольною точкою K1
- **Файли:** див. 0.1 (WP-06).
- **Закриває:** L§9, §10 (A-03b), §11, §13 (CE/EE), §14, §15, §16, §17 (колонка готових модулів, знахідки рецензії), §19, §20, §21 №14; FTR N-02, N-04, N-12, N-14, N-15, N-18; К-02, К-09, К-12, К-15, К-21; зауваження №10, 13, 14, 18, 22, 23.
- **Зробити:**
  1. `SKILL.md`: вхід — `OWNER-INTAKE.md` (блокуючий), `briefing.md` (A-03), `past-projects.md` (A-04); склад запуску R1 реєстр конкурентів 25–40 (Sonnet) ∥ R2 галузева модель по підсегментах (Opus) ∥ R3 екосистема Odoo CE/EE (Sonnet) → **K1** (`research/K1.md`, ≤10 питань, кандидати на відкидання = є у ≥`do_not_reject.n` конкурентів, у попередній концепції або в `do_not_reject.items`; `waiting_human`) → R4 матриця 60–100 рядків + профілі 8–12 (Opus) → синтез `FUNCTIONAL-MAP.md` (§0–8, §5 «Резюме для власника») → рецензія Fable 5.2 за `research.md` і `edition-claims.md` до відсутності major (2 + 1 контрольний).
  2. Обов'язкові розділи (L§10): ринок за смугами з odb-catalog з датою знімка; рамка окупності з чутливістю до N; ціни в одній валюті з курсом і датою (пастка geoip odoo.com/pricing); матриця без порожніх стовпців; реальні замінники; кожен підсегмент — глибина або «неможливо»; ◎ «ціль» для нашого пакета; два рядки Odoo CE/EE; основа кожної функції за К-09 з колонкою «ToDo-готовий» (після A-03c — заповнює A-20).
  3. Джерела — `needs-sources-catalog.md`; `research/sources-log.md`; внутрішні — `sources/`; правило К-02 (позначка ризику, тип `owner-decision`); рекомендація AI, що суперечить анкеті, — лише як альтернатива з причиною.
  4. `edition-claims.md` за шаблоном + `scripts/check_edition_claims.py` (CLI 2.0.1); `REJECTED.md` (чернетка груп) з посиланнями на відповіді K1; `facts.yaml`, `DEPENDS.yaml`.
  5. Зразок (N-18, `params.sample`): профіль одного конкурента + 10 рядків матриці → `waiting_human`.
  6. `references/`: `run-plan.md` (R1–R4, моделі, формати JSON R1), `pitfalls.md` (пастки L§10, §17), `review-criteria.md` (рівень галузевого експерта; не перевірене кабінетно — не major, якщо позначено й винесено в план перевірки); межі з `industry-briefing`, `competitor-mapper` (організація).
  7. Евали ≥7: r10, r13, r14, r18, r22, r23 + K1 не пропущено.
- **Еталони:** `research/{FUNCTIONAL-MAP,odoo-ecosystem,competitors-registry,competitor-features,industry-model,subsegments-deep,REJECTED}.md`, `competitors/*.md`; шаблони WP-04.
- **Готово:** повна структура; опис ≤900 з тригерами й межами; `check_edition_claims.py` червоний на рядку «EE дає X» без URL/цитати і на «частково» без переліку; евали зелені; `validate plugins/flow-research` PASS.
- **Залежності:** WP-03 (yaml A-03b, `check_rejected`), WP-04 (шаблони, каталог), WP-05 (формат анкети фактично — з 1.4, тож можна паралельно з WP-05).

### WP-07. Концепція: concept-mapper (A-20) і completeness-audit (A-20b)
- **Файли:** див. 0.1 (WP-07).
- **Закриває:** L§2 (покриття ролей/F/екранів), §9 (поріг → К-01), §11, §13, §16, §17 (вхід REUSE), §18, §19, §20, §21 (№0, №2, №17, №19); FTR N-01, N-04 (OWNER-BRIEF, BOX, SALES), N-05 (`completeness.md`), N-12, К-01, К-02, К-04, К-12, К-21; зауваження №5, 21, 23, С-01.
- **Зробити:**
  1. **concept-mapper**: входи `OWNER-INTAKE.md`, `FUNCTIONAL-MAP.md`, `K1.md`, `REUSE.md` (без нього — `waiting_human`), `briefing.md`, `past-projects.md`, протоколи A-06 (необов'язково); виходи `concept/{features,screens,scenarios}.md` + `research/{OWNER-BRIEF,BOX,SALES,REJECTED}.md` за шаблонами WP-04, `facts.yaml` — єдине джерело чисел; правила: роль-покупець має екран і сценарій (дашборд); кожна роль має сценарій, кожна F — крок, роль на екрані = роль у `screens.md`; основа екрана CE/EE/`ToDo-готовий`; юридично неоднозначне → параметр `answers.yaml`; повернення з A-20c/A-23 перечитує умови повернення в REJECTED; Крок 8 «Недостатньо джерел» переписати за К-01; питання сортувати (анкета / K1 / ≤5 на гейт). `check_concept.py`: нові ID CM-buyer, CM-roles-scenarios, CM-base-edition, CM-dnr (через `check_rejected`), CM-facts (через `check_facts`). `references/concept-templates.md` — під нові виходи.
  2. **completeness-audit** (новий): 5 рецензентів-ролей Fable 5.2 паралельно (власник продукту, галузевий експерт, архітектор Odoo 19 CE/EE, продавець ToDo, аудитор узгодженості) → тріаж (Opus) у `research/COMPLETENESS.md` (чек-лист → статус → де → чого бракує → хто закриває: кабінетно / людина / рішення власника; G-xx) → виправлення desk-прогалин у `research/*.md`, `concept/` → фінальний критик ≤2 кіл; minor, що впливає на рішення власника, = major; поле звіту `completeness`. `references/`: `roles-briefs.md`, `triage-rules.md`; без гейта.
  3. Евали: concept-mapper r05, r23, c01 (+ наявні 5 оновити під нові виходи); completeness-audit ≥5 (r21).
- **Еталони:** `research/{OWNER-BRIEF,BOX,SALES,REJECTED,COMPLETENESS}.md`; `completeness-checklist.md` (WP-04); `flow/decisions.md` тестового репо (рядки 4–27) — для кейсів.
- **Готово:** `check_concept.py` червоний на фікстурі «покупець без екрана» і «позиція з do_not_reject у відкинутому без K1»; евали зелені; описи ≤900; `validate plugins/flow-research` PASS.
- **Залежності:** WP-04, WP-05 (анкета, REUSE), WP-06 (формати FUNCTIONAL-MAP/K1 — фіксовані шаблонами, тому може йти паралельно з WP-06 в останню чергу).

### WP-08. concept-presentation (A-20c): один Artifact з 3 сторінок
- **Файли:** див. 0.1 (WP-08).
- **Закриває:** L§10 (подача), §11 (сторінка відкинутого), §12, §14, §17 (той самий URL), §19, §20, §21 (механіка рішень); FTR N-02 (≤5 питань), N-16 (формат рядків), N-18; К-04, К-05, К-08; зауваження №11, 13, 15.
- **Зробити:**
  1. `SKILL.md`: входи OWNER-BRIEF, FUNCTIONAL-MAP, BOX, SALES, REJECTED, COMPLETENESS, competitors-*, `facts.yaml`, `OWNER-INTAKE.md` (бренд, мова), `prototype-real/PLAN.md` (лише якщо існує — блок «що вже є в зрізі» з реального переліку екранів); зразок — перший екран (`params.sample`); повний обсяг — `index` (висновок і чесний вердикт про гроші → біль → наскрізний сценарій → «день з життя» → екрани MVP з основою CE/EE/ToDo-готовий → [зріз] → конкуренти коротко → що не робимо → гроші → ризики → «Повнота концепції» → рішення власника → обмеження → джерела), `competitors`, `rejected` за шаблонами WP-04.
  2. Публікація: багатофайловий Artifact рядком «КОМАНДИ: artifact-publish …» (runner); повторно — той самий URL з `owner-page/PUBLISHED.md`; копія в `research/owner-page/`.
  3. Блок рішень: варіанти + рекомендація + замовчування; «Скопіювати мої відповіді» → готові рядки `flow/decisions.md` (колонки `flow-state.md` §3, «не вирішено» теж); далі `flow-state-keeper decisions-batch` (WP-11).
  4. `scripts/check_owner_page.py` (CLI 2.0.1): 3 сторінки, навігація туди-назад, якорі на рядки дослідження, контракт сторінки (без зовнішніх ресурсів, крім Google Fonts; токени; 390 px), ◎ не позначено як факт.
  5. `references/`: `page-structure.md`, `copy-rules.md` (мова власника, «концепція, а не таблиця рішень»), `publish.md`. Евали ≥6: r11, r13, r15 + ◎ як ● + питання дублюють анкету.
- **Еталони:** `owner-page/{index,competitors,rejected}.html` (A-03b-deep), шаблони WP-04, `PAGE-CONTRACT.md`.
- **Готово:** `check_owner_page.py` зелений на каркасі WP-04 із заповненими плейсхолдерами й червоний на фікстурі з 2 сторінками; евали зелені; опис ≤900; `validate plugins/flow-research` PASS.
- **Залежності:** WP-04, WP-07 (виходи A-20/A-20b), WP-03 (yaml A-20c).

### WP-09. prototype-builder (A-21): реальний зріз Odoo 19 `td_*`, а не HTML
- **Файли:** див. 0.1 (WP-09).
- **Закриває:** L§1.1–1.3, §1.6–1.7 (запис, дашборд як екран зрізу), §1.9, §2, §6–8 (правила, не дефекти), §11, §13, §21 №19; FTR N-11, N-13, N-18, К-05, К-06, К-13, К-16, К-22, К-23; зауваження №1.
- **Зробити:**
  1. Переписати «Мета» і кроки: 0 preflight (`preflight.sh`) → 1 план зрізу (Opus) `prototype-real/PLAN.md` з перевіркою кожного припущення про стандарт по вихідниках Odoo 19 (файл:рядок; немає `mrp_workorder`, `web_gantt` у CE тощо) з входів К-05 → 2 зразок (1 екран + 15 с запису + 1 кадр) → `waiting_human` → 3 модулі `package/addons/td_<галузь>_*` (Python-моделі, подання, дані; без Studio/`x_`; без EE-залежностей; тести; `boost:odoo19-lint`) — заготовка A-11 → 4 демо-дані з калібруванням (маржа 12–40 % з розкидом, години, масштаб, 8–17, правдоподібні адреси, без «0,0», планова собівартість у чернетці) і переклади з перезаписом → 5 `build_db.sh` (перестворення бази перед зйомкою) → 6 живий запис десктоп 1920×1080 і мобільний 390×844 (isMobile, hasTouch, DPR 3), сценарій = `SALES §6`, `facts.json` з DOM по сцені → 7 перевірки: консоль без помилок, `check_ui_text.py`, картка дашборда = звіт drill-down, `<separator/>` у фільтрах → 8 `complexity.md` (стандарт/конфіг/код окремо CE і EE) → 9 README, розділ «Відкинуто» (екрани, що не ввійшли), `ACCEPTED.md` (N-11).
  2. Скрипти з `shoot/` (A-21-real), узагальнені параметрами галузі: `rec_lib.mjs`, `scenario.mjs` (шаблон), `scenario-mobile.mjs`, `rec_clips.mjs`, `scenes.mjs`, `build_db.sh`, `fix_dates.sh`; `check_english.sh` → `check_ui_text.py` (CLI 2.0.1). Вилучити `prototype-shell.html`, `assemble.mjs`, старі `check.mjs`/`record.mjs` (замінити), `odoo19-ui-kit.md` — вилучити або звести до правил UI-тексту.
  3. Межі: A-21c (монтаж, титри, бренд, SHOW) — `showcase-content`; A-11 (повна збірка) — збірка; A-22 — база зрізу. Профіль `repo` (К-22), команди — «КОМАНДИ:».
  4. `references/`: `slice-plan-template.md` (з `PLAN.md` еталона, без меблевого змісту), `demo-data-rules.md` (калібрування), `recording.md` (формати, мобільний, кадрування), `handoff-a21c.md` (що віддає: `video/rec/*.mp4|json`, `scenes`, `facts.json`, скріни). Евали ≥5: r01 + «Новий» у кадрі + англійські підписи + маржа 100 % до підтвердження + зріз зі старого зрізу замість FUNCTIONAL-MAP.
- **Еталони:** `git show flow/A-21-real:docs/industries/mebli/prototype-real/{PLAN.md,README.md,shoot/*}`.
- **Готово:** `grep -rn "клікабельн\|prototype-shell\|x_" plugins/flow-research/skills/prototype-builder` — лише в «Чого НЕ робити»; `node --check` для всіх `.mjs`, `bash -n` для `.sh`; `check_ui_text.py` зелений/червоний на фікстурах DOM; опис ≤900; `validate plugins/flow-research` PASS.
- **Залежності:** WP-02 (`preflight.sh`, CE/EE tools-odoo), WP-03 (yaml A-21), WP-04, WP-07 (BOX/SALES як вхід).

### WP-10. showcase-content (A-21c) + роль контент-менеджера; demand-test-runner (A-23)
- **Файли:** див. 0.1 (WP-10).
- **Закриває:** L§1.4–1.8, §2 (A-23), §4, §6–8 (відео/SHOW-правила), §11 (A-23), §15 п. 8, §16, §20–21 (ризики в A-23); FTR N-09, N-11, N-12 (план перевірки ризиків), N-13 (титри з SALES §2), N-18, К-10; зауваження №2, 3, 4, 6, 7, 8.
- **Зробити:**
  1. **showcase-content** (новий): входи — передача A-21 (`video/rec`, сцени, `facts.json`), `SALES §2` (заперечення → титри), `§6`, анкета (`materials`, `brand`), `brand-todo/`, попередній `ACCEPTED.md`; виходи — повне відео 16:9 1920×1080 3–4 хв, Reels 9:16 1080×1920 55–60 с, мобільний блок (живий запис, телефон ≥85 % ширини, маска рамки), `SHOW.md/html/pdf` (числа з `facts.json`, збірка падає при розбіжності), `captions.yaml`, `ACCEPTED.md`. Правила: основа — безперервний живий запис; бренд лише в заставках/титрах/плашці; гачок 0–3 с; жодного статичного кадру >2 с; титр ≥1,5 с, синхронний зі сценою, не закриває доказ, без накладання; бічна цифра — з поточної сцени; блок керівника ~10 с; zoom не обрізає цифри й осі; наближення до ключових цифр на 1920; SHOW щільний, відмінювання чисел, без формулювань «як дефект». Схвалене не міняти без «було / стало» (A/B). Перемонтаж без перезйомки й без Odoo. Зразок — 15 с + 1 кадр титра.
  2. Скрипти з `shoot/` (A-21-real), узагальнені: `rec_cards.mjs`, `_card_*.html` → `references/cards/`, `brand.css`, `montage.mjs`, `build_video.mjs`, `make_show.mjs`, `make_images.mjs`, `SHOW.tpl.md`; `verify_video.sh` → `check_video.py` (CLI 2.0.1, `ffprobe` + `freezedetect` + кадри перших/останніх 5 с; фікстура генерується `ffmpeg -f lavfi` у `evals/smoke.sh`, бінарники >1 MB не комітити).
  3. Роль: виконавець — Контент-менеджер (`executor: any`, профіль `content`), рішення — кнопка в задачі; розділ «Ролі й доступ» у SKILL.md. Евали ≥7: r02, r03, r04, r06, r07, r08 + число в кадрі ≠ facts.json.
  4. **demand-test-runner**: входи A-21c (Reels, повне відео, SHOW.pdf) у лендингу, листах, плані розсилки; план перевірки ризиків N-12 (позиції з доказом `owner-decision` → пункти тесту); група джерел 8 (fake-door голосування за функції, «збери свій пакет», тест ціни CE/EE); варіанти цінності, що не пройшли поріг → реєстр «Відкинуто»; внутрішні агрегати (причини програшів) з класом `internal-aggregated`; тексти `prep` може вести контент-менеджер. Евали +2.
- **Еталони:** `git show flow/A-21-real:…/prototype-real/{shoot/*,SHOW.tpl.md,SHOW.md,brand-todo/BRAND.md}`; `review-checklists/video-materials.md` (WP-03).
- **Готово:** `check_video.py` червоний на згенерованому статичному відео 5 с і зелений на динамічному; `node --check` усіх `.mjs`; описи ≤900; евали зелені; `validate plugins/flow-research` PASS.
- **Залежності:** WP-09 (контракт передачі `handoff-a21c.md`), WP-03, WP-04 (бренд).

### WP-11. Цикл кроку, стан і самонавчання: flow-step-runner, flow-state-keeper, skill-retro (C-08R), eval-builder
- **Файли:** див. 0.1 (WP-11).
- **Закриває:** L§1.10, §2 (бриф рецензента), §3, §5, §14 (урок одразу, звірка перед «готово», перерахунок), §21 (пакет рішень); SL §1–6; FTR N-08 (крок 0), N-10, N-11, N-16, N-17, К-08, К-24; зауваження №7, 9, 17.
- **Зробити:**
  1. **flow-step-runner**: Крок 0 — preflight за ключем картки (FAIL → `waiting_human` до витрати бюджету); observation **за подією** («Повернути», `escalated`, червоний CI) з посиланням на задачу/PR; зауваження людини під час кроку → observation у тому ж ході; перед «done» — `scripts/check_lessons.py` (CLI 2.0.1); `review.max_rounds` 2 + 1; `human_rounds` у звіті; `ACCEPTED.md` (N-11) — зміна схваленого лише з «було / стало»; зразок `params.sample` → `waiting_human` + `resume`; бриф рецензента — `review.checklists`, обов'язковий перегляд візуального результату; вимоги людини посеред циклу — у пізніші раунди без зміни ранніх промптів. `references/executor-brief.md`, `pr-checklist.md`.
  2. **flow-state-keeper**: режим `decisions-batch` (рядки з «Скопіювати мої відповіді» → PR у `flow/decisions.md` з позначкою «внесено AI від імені власника» + посилання; без посилання — відмова); облік уроків LSN і метрик (% повернень на скіл@версію, раунди, частка правок людини, вартість); експорт `flow/lessons/`.
  3. **skill-retro** (новий, C-08R): `daily` — обхід реєстру репо (GitHub read) і журналу запусків Odoo flow; сигнали SL §1; кластеризація в `LSN-xxx` (`repeat_of` → серйозність вгору); класифікація SL §2.4; для **кожного** уроку — чернетка правки (PR у каталог плагінів або схему) + евал-кейс через `eval-builder`; щоденний пакет Власнику продукту (одна кнопка, окремі «Повернути/Відкласти»); закриття — правка внесена, евал зелений, 2 тижні без повтору; незакриті >3 робочих днів → ескалація AI-інженеру; звірка «сигнали ↔ уроки» (жодного сигналу без уроку чи «не помилка» з причиною); п'ятничний підсумок. `event` — миттєвий запис. Профіль `repo`. Евали ≥5 (r09, r17, повтор закритого уроку, сигнал без уроку, дані клієнта в уроці).
  4. **eval-builder**: режим `init` з джерелом «хронологія галузі» (зауваження людини → кейс «поганий артефакт → рецензент має повернути»); `references/gold/mebli.md` — SHA еталонів, таблиця 2.0.2, правило «посилання, не копія»; візуальні кейси (фікстура — шлях до кадру/скріна + SHA); вхід — `LSN-xxx` від C-08R; межа C-04/C-07 ↔ C-08R.
  5. **support-desk**: одне речення — звернення-дефект пакета є сигналом для C-08R (без зміни маршрутизації).
- **Еталони:** SL; FTR 2.7; `flow/decisions.md` тестового репо (формат рядків).
- **Готово:** `check_lessons.py` червоний, якщо зауваження без observation; евал runner «зауваження не записано» червоний на 0.1.0 і зелений після правки; описи ≤900 (runner зараз 882 — не розширювати); `validate plugins/flow-core`, `plugins/flow-client-delivery` PASS.
- **Залежності:** WP-01 (ключі наряду, поля звіту, `flow-state.md`), WP-03 (yaml C-08R), WP-02 (`preflight.sh`).

### WP-12. Збірка, впровадження й розвиток: CE + EE, мости, режим договору, без AGPL, реєстр відкинутого
- **Файли:** див. 0.1 (WP-12).
- **Закриває:** L§11 (B-02, D-02, D-05), §13 (збірка, B-02/B-03, D-03), §16 (D-02, B-02), §20 (D-10 міграція), §21 (№3б, №4, №12, №14, №17); К-06, К-09, К-11; FTR 4.2 (рядки flow-package-build, evolution, delivery).
- **Зробити** (у кожному скілі — абзац у «Мета»/кроках, `references/` за потреби, опис ≤900, евал +1):

| Скіл | Правка |
|---|---|
| config-as-code | профілі модулів `ce`/`ee` у `manifest.yaml`; параметри `edition` і `contract_mode` у `vp-map.yaml`/`answers.yaml`; застосування на CE і EE тестовій базі; ядро `td_*` без EE-залежностей; `td_*_ee` — auto_install мости |
| gates-aggregator | вердикт для кожної редакції в `CHECKS.md`; APPROVE лише якщо обидві (при `editions: both`); EE недоступна → `WARN`, не APPROVE мовчки; AGPL у ядрі → BLOCK |
| demo-base-builder | стенд CE і EE; A-22 = база зрізу для гарячого ліда (з `prototype-real/shoot/build_db.sh`); вилучити режим «емуляція», `references/emulation-*.md`, переписати евал `emulation-prod-trap` |
| package-release-builder | CHANGELOG і перевірка установки/оновлення для обох редакцій; матеріали релізу — контент-менеджер (посилання на картку) |
| questionnaire-builder | параметр редакції клієнта; «юридично неоднозначне → параметр `answers.yaml`» (режим договору, §21 №17) |
| master-data-template-builder | вхід `BOX §3–4` (довідники, дані на старті) |
| odoo-version-migrator | інвентар і перевірка для обох редакцій; заборона AGPL-залежностей у ядрі |
| backlog-triage | «відхилити» — рядок реєстру `rejected-register.md` з причиною й умовою повернення; внутрішні дані (`internal-aggregated`); `backlog_check.py` → виклик `check_rejected.py` |
| product-decision-drafter | реєстр альтернатив, що не обрали (A-07, D-04, D-05); входи `BOX §1`, `SALES §3`; тарифи CE-вхід / EE-апгрейд / легкий ФОП |
| package-fit-gap | редакція клієнта як вхід; вимоги поза пакетом — реєстр «Відкинуто»; внутрішні дані; `check_fit_gap.py` + `check_rejected.py` |
| package-sow-builder | входи `BOX §1–2` (коробки, тарифи, план запуску); редакція |
| client-data-migrator | входи `BOX §4`, `§6` (міграція BAS/BAF, контракт обміну); редакція |
| package-upgrade-runner | оновлення для CE і EE клієнта |
| runbook-executor | EE-модулі й мости — лише на EE-базі клієнта; редакція з `answers.yaml` |

- **Еталони:** L§13; `research/BOX.md` §1–6, §12 (A-03b-deep); `<FC>/references/rejected-register.md`.
- **Готово:** `grep -rn "емуляц" plugins/flow-package-build` — лише «вилучено»/історія; `grep -rln "edition\|редакц" ` охоплює всі 14 скілів; наявні скрипти й евали зелені; описи ≤900; `validate` трьох плагінів PASS.
- **Залежності:** WP-01 (формат реєстру, A-22), WP-02 (tools-odoo CE/EE), WP-03 (yaml B-02, D-02, D-05, A-07, A-22).

---

## 3. Порядок виконання й паралельність (≤2 одночасно)

| Етап | Паралельно | Чому так |
|---|---|---|
| 1 | **WP-01 ∥ WP-04** | основа: коди й контракти flow-core ∥ шаблони flow-research; файли не перетинаються |
| 2 | **WP-02 ∥ WP-03** | обидва читають WP-01; WP-03 бере заголовки шаблонів WP-04 |
| 3 | **WP-05 ∥ WP-06** | старт галузі й глибокий аналіз; формат анкети зафіксовано в 1.4 |
| 4 | **WP-07 ∥ WP-11** | концепція (читає WP-05/06) ∥ цикл і самонавчання (незалежні файли flow-core) |
| 5 | **WP-08 ∥ WP-09** | сторінка (читає WP-07) ∥ зріз (читає WP-07 BOX/SALES, WP-02 preflight) |
| 6 | **WP-10 ∥ WP-12** | матеріали (читають передачу WP-09) ∥ збірка/впровадження CE+EE |
| 7 | **F** (послідовно), потім рецензія §4 | версії, README, маркетплейс, наскрізні перевірки |

Після кожного етапу координатор: `git status --short` (лише файли WP), `validate` змінених плагінів, «ЗАПИТИ до WP» — уточненням тому самому виконавцю. Невдалий WP — повтор тим самим виконавцем, не новий.

**F. Фінальна інтеграція** (координатор або один Sonnet; файли — 0.1 рядок F):
1. `version` `0.1.0 → 0.2.0` у 5 `plugin.json` і синхронно в `.claude-plugin/marketplace.json` (К-25).
2. README 5 плагінів (перелік скілів: +7 нових; кроки; профілі `research-internal`, `content`; роль контент-менеджера) і кореневий `README.md` (таблиця плагінів, кроки A-02b…C-08R, «Евали», «Відомі обмеження», нові відкриті питання §5; кількість yaml-специфікацій).
3. `_work/LESSONS-A21-real.md`: шапка за К-16, коди за таблицею 1.1 (К-03), конкретні дефекти §6–8 позначити «→ беклог A-11 меблі».
4. Наскрізно: `claude plugin validate` для 5 плагінів і `.`; команда довжини описів (§2.0.3) — без FAIL; `python3 -c` по всіх `evals.json` (JSON валідний, унікальні id); `grep -rnE "A-03b концепц|td_ лише для CE|емуляц.*A-22|клікабельн.*прототип|OCA 19\.0 \| td_" plugins` — 0 (крім «Чого НЕ робити»/історії); кожен код із 1.1 є в `flow-map.md`, `step-skill-map.md`, `step-cards.md`, `checks/*.yaml` і в розділі «Наступний крок» сусідніх скілів.

---

## 4. Чек-лист фінальної пакетної рецензії Fable 5.2

Рецензент відкриває файли, а не лише звіти WP. Вердикт: **APPROVE / REQUEST CHANGES / BLOCK**; зауваження {серйозність, файл:рядок, що не так, що зробити};
будь-який пункт «ні» = major; minor, що змінює рішення власника або поведінку кроку, = major.

**A. Структура й публікація**
- [ ] 5 плагінів `0.2.0` у `plugin.json` і `marketplace.json`; `claude plugin validate` — PASS для кожного й для `.`.
- [ ] 7 нових скілів (`owner-questionnaire`, `industry-deep-dive`, `reuse-modules`, `completeness-audit`, `concept-presentation`, `showcase-content`, `skill-retro`) мають повну структуру; `evals.json` ≥5 кейсів, ≥2 з «меблів».
- [ ] Усі `description` ≤900, з тригерами (uk/ru) і «НЕ для …»; межі сусідніх скілів не перетинаються (deep-dive ↔ industry-briefing/competitor-mapper; reuse-modules ↔ past-projects; prototype ↔ showcase ↔ demo-base-builder; completeness-audit ↔ concept-presentation; skill-retro ↔ eval-builder C-04/C-07).

**B. Канон (розділ 1) відображено**
- [ ] Порядок 1.1 однаковий у `flow-map`, `step-skill-map`, `step-cards`, оркестраторі, `checks/*.yaml`, «Наступний крок» кожного скіла; гейт концепції лише в A-20c; A-22 без емуляції.
- [ ] К-01/К-02: жоден скіл не зупиняє A-20 через брак доказів при `evidence_gate: risk`; правило ≥2 джерел — позначка ризику; тип `owner-decision` є в `id-patterns.md` і шаблонах.
- [ ] K1 у A-03b до синтезу; кандидати на відкидання включають `do_not_reject`; `check_rejected` FAIL на позиції з `do_not_reject` без посилання на K1.
- [ ] К-06/К-09/К-12: ядро CE, `td_*_ee` мости, без AGPL; кожне «CE/EE дає» — рядок `edition-claims` з вердиктом і доказом; у текстах скілів немає переліків «EE дає» як факту.
- [ ] К-07/К-19: класи `internal-aggregated`/`internal-raw` однакові в `data-policy-template`, `report-format`, `pii-patterns`, скілах; `internal-raw` лише в `research/sources/`; профіль `research-internal` без інструментів запису й платних дій Unitalk.
- [ ] К-08: `decisions-batch` не пише рядок без посилання на повідомлення власника.

**C. Ланцюжок артефактів (сусіди)**
- [ ] Хто пише → хто читає звірено для: `OWNER-INTAKE.md` (A-02b → A-03b, A-20, A-20c, A-21, A-21c, A-23, B-02, A-09), `K1.md`, `FUNCTIONAL-MAP.md`, `REUSE.md`, `OWNER-BRIEF/BOX/SALES/REJECTED.md`, `COMPLETENESS.md`, `owner-page/*`, `facts.yaml`, `DEPENDS.yaml`, `PLAN.md` + `video/rec` + `facts.json` (A-21 → A-21c → A-23), `ACCEPTED.md`, `flow/decisions.md`, `LSN-xxx`.
- [ ] Імена розділів, на які посилаються сусіди (`BOX §1–6`, `SALES §2/§3/§6`, `FUNCTIONAL-MAP §4/§5`), існують у шаблонах WP-04.
- [ ] Поля звіту (`rejected_count`, `completeness`, `human_rounds`, `sample`, `accepted_ref`, `stale`) пишуть скіли й читають `flow-state-keeper`/`skill-retro`.

**D. Перевірки й евали**
- [ ] 11 скриптів 2.0.1 існують за вказаними шляхами з тим самим CLI; кожен червоний на `-bad`, зелений на `-ok`; yaml посилаються на них правильно.
- [ ] 7 чек-листів рецензента є й підключені через `review.checklists` у картках; `flow-reviewer` вимагає відкрити візуальний результат.
- [ ] 24 зауваження FTR §1 покриті кейсами за 2.0.2; кейси посилаються на SHA еталона, не копіюють даних.
- [ ] `check_lessons` + observation за подією + C-08R утворюють замкнений цикл «зауваження → урок → правка → евал».

**E. Контент і візуальні правила**
- [ ] `showcase-content`: формати з анкети, живий запис як основа, >2 с статики — FAIL, телефон ≥85 %, бренд лише поверх, числа з `facts.json`, A/B зі схваленим.
- [ ] `prototype-builder`: реальні `td_*`, без `x_`/Studio, без HTML-оболонки, план із файл:рядок, калібровані дані, переклади, зразок до повного обсягу.
- [ ] `concept-presentation`: 3 сторінки одного Artifact, той самий URL, контракт сторінки, ◎ не як факт, ≤5 нових питань, «Скопіювати відповіді» = рядки журналу.

**F. Дані й безпека**
- [ ] У `plugins/` немає назв компаній-клієнтів, ПІБ, контактів, сум угод, вмісту `research/sources/` еталона; меблевий зміст лише як посилання на еталон.
- [ ] Недовірені входи (сторінки, транскрипти, CRM) у нових скілах позначено як дані, не інструкції; публікація й push — лише runner за «КОМАНДИ:».

**G. Відкриті питання**
- [ ] Питання §5 не вирішено мовчки: є в «Відкриті питання» скілів і в кореневому README.

---

## 5. Поза пакетом і відкриті питання

**Правки поза цим репо (не входять у WP; передати власникам):**
- `odoo19-mvp-build:build-allocator`, `code-dev` (монорепо «Методологія»): профілі `ce`/`ee`, мости `td_*_ee` у ALLOCATION з першого релізу, трек «готові модулі ToDo» (адаптація, не розробка), ядро без AGPL (L§13, §17, §21 №12, №14).
- `odoo19-discovery-initiation:industry-briefing`, `competitor-mapper`: опис меж з `industry-deep-dive`.
- `boost:skill-feedback`: поле «репо/задача» (SL §6).
- Тестове репо / `industry-flow-test-kit/bootstrap.sh`: оновити копії скілів, агентів і `tests/` під 0.2.0 після F.
- Беклог A-11 «меблі»: дефекти L§6–8 (мобільний конфігуратор, ціна від розміру).

**Відкриті питання (до людини; виконавці не вирішують):**
1. Ліцензія наших модулів: LGPL-3 чи OPL (К-09 — «за рішенням власника»).
2. `search_count` власної ERP: чи дає odoo-mcp read-only спосіб підрахунку (інакше — повний перебір `odoo_search_read`); C-00.
3. Доступ до EE (ліцензія/база) для CI й перевірки тверджень; без нього EE-вердикти — «не перевірено», EE-job — WARN.
4. Дозвіл середовища на push `research/sources/` (`internal-raw`) — хто й де фіксує (C-00).
5. Хто публікує Artifact у бойовому флоу (runner від імені технічного користувача чи людина) і де зберігається URL поза репо.
6. Рішення плану К-20…К-25 — підтвердити або змінити до старту етапу 1.
