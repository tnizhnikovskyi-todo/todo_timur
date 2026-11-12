# Контракт специфікацій перевірок

Специфікація кроку — `references/checks/<step>.yaml` (синтаксис JSON; перевірка розбору: `grep -v '^#' <файл> | python3 -c 'import json,sys;json.load(sys.stdin)'` або `autocheck.py --selftest` — `json.load` напряму падає через рядок-коментар `#`, це не поломка; валідний YAML 1.2; рядки `#` на початку ігноруються). Виконує її лише
`scripts/autocheck.py` (stdlib, `python3 -I`). Нових перевірок із тексту `checkHow` не додають: бракує перевірки — правиться YAML і скрипт разом
(AI-інженер), потім `autocheck.py --selftest`. Специфікації кроків — усі файли в `references/checks/` (перелік — каталог, не цей файл); для кроків без файлу — `ERROR spec-missing` + `MANUAL` (загальні C-06 виконуються завжди). Переважно `manual` — A-07, D-04 та інші кроки зі змінним шляхом результату.

## Форма запису
`{"step": "A-10", "extra_allowed": [glob…], "checks": [{"id", "prim", "args", "when", "route_on_fail", "severity"}]}`.
`ref` — де брати файл: `head:<шлях>` / `base:<шлях>` / `prev:<шлях>` (SHA кандидата, бази, попереднього тега) або `in:<крок>` (вхід наряду з `from` = крок, на його `sha`).
`when`: `sample` / `not_sample` (`params.sample` наряду: зразок N-18 / повний обсяг), `prev` (є попередній тег), `rerun` (attempt > 1 або `returned_from`), `hotfix` / `not_hotfix`, `new_version`, `in:<крок>` (є вхід від кроку), `mode:<значення>[|<значення>]` (`params.mode` наряду з переліку; специфікація одна на код кроку, тож записи, що стосуються лише одного режиму другого ведучого, — A-23, B-08a, — позначаються цією умовою).
Умова не справдилась → `SKIP` з причиною. Регулярні вирази ID і мітки SHA — `flow-core/references/id-patterns.md`, ПДн — `pii-patterns.md`.

## Примітиви (контракт скрипта)
| Примітив | Аргументи | Дія й статуси |
|---|---|---|
| `id_set` | `left`, `right` = `{ref, regex, table_col? \| schema_keys? \| section?, drop_line_regex?}`, `relation` (`subset`/`equal`), `msg_missing`, `msg_extra` | множини ID; різниця — переліком у `msg`; `table_col` — колонка md-таблиці за назвою заголовка; `schema_keys` — ключі `answers.yaml` (`active`/`all`); рядки з `drop_line_regex` (напр. `deprecated з версії`) не рахуються. Немає файлу → `ERROR` |
| `table_rules` | `ref`, `require` (колонки), `key`, `unique_key`, `drop_row_regex`, `expect_rows (кількість рядків), rules[{when (умова або список умов), col, kind: enum\|not_in\|regex\|nonempty, values\|pattern, msg}]` | колонки — за **назвою заголовка**, не за позицією; немає таблиці → `ERROR table-not-found` |
| `headings` | `ref`, `headings` (`re:` — regex), `headings_from` + `exclude` + `expect_count`, `or_text` | відсутні заголовки переліком; `headings_from` бере заголовки H2 із файла плагіна (немає — `ERROR template-missing`) |
| `sha_eq` | `refs` | SHA за міткою (`id-patterns.md`); мітки немає ніде — `MANUAL`; немає в частині файлів — `FAIL`; різні — `FAIL` з усіма значеннями |
| `git_ancestor` | `a`, `b` ∈ `head`/`base`/`prev`/`extract:<ref>` | `git merge-base --is-ancestor`; SHA не витягнуто — `FAIL missing-sha`; об'єкта немає після `fetch` — `ERROR` |
| `git_diff_allowed` | `from`, `to`, `allow` (glob, `**`, `dir/`), `compare_done` | `git diff --name-only from to` ⊆ `allow`; зайві файли переліком; `compare_done` — `WARN <id>-spec-vs-naryad`, якщо шлях з `allow` не згадано в `done` наряду (джерело правди — специфікація, не наряд) |
| `version_eq` | `sources[{name, kind: regex\|param\|manifests, ref, pattern, optional, pick}]` | усі X.Y збігаються; `manifests` — `package/addons/td_*/__manifest__.py` через `ast.literal_eval` (`19.0.X.Y` → X.Y); усі значення — в `msg` |
| `stable_on_rerun` | `kind: table\|yaml`, `file`, `allowed` (джерело ID дозволених змін) | блоки, що змінились між `prev` і `head`, ⊆ `allowed`; немає тега — `SKIP first-release` |
| `keys_diff_eq` | `file`, `changelog`, `heading` | ключі VP, додані чи позначені `deprecated` між `prev` і `head` = VP розділу CHANGELOG |
| `example_valid` | — | `answers.example.yaml` проти схеми (`# schema: 1`, ключі, `default`, `allowed`, `min..max`, не «уточнити») власним розбором за `answers-schema.md` |
| `exists` / `vendored_license` / `addons_in_text` | шляхи / — / `ref` | непорожні файли; ліцензія у вендореному модулі (тека `package/addons/*` не `^td_`); теки `package/addons/*` згадані в тексті |
| `allocation_coverage` | — | теки `package/addons/*` ↔ колонка «модуль Odoo» ALLOCATION; модулі з треком код/готове мають теку; кожен файл `package/config/` згаданий у CHECKS.md |
| `grep_clients` | — | ідентифікатори з `clients/REGISTRY.md` (колонка «ідентифікатор клієнта», ≥4 символів) у `package/` через `git grep`; `шлях:рядок` без витягу; немає клієнтів — `SKIP` |
| `section_contains` | `ref`, `heading`, `patterns` | розділ містить усі патерни |
| `signature_by_ai` | `file`, `heading` | блок змінено комітом, автор якого збігається з `--agent-pattern` → `FAIL`; патерну немає → `MANUAL` |
| `evals_schema` | — | кожен `evals/**/evals.json` на head: JSON, `skill`, `cases[]` з унікальним kebab `id`, `source`, `status`, `prompt`, `expected.checks`, `expected.must_not` |
| `pii_strict` | `paths` | PII-патерни (FAIL-типи) у доданих рядках diff за `paths`, FAIL незалежно від `client_data` |
| `no_money` | `paths` (файли/теки), `exclude` (підрядки шляхів), `patterns` (за замовчуванням — маркери LESSONS §24: окупн, TCO, вартість володіння, business-case, вердикт про гроші, ROI, беззбитков, ставка розробки, години×ставка, секція money) | FAIL із `файл:рядок` (0.3.0: економіку пакета не рахуємо; ціни конкурентів як факт — через `exclude`) |
| `manual` | `text`, `who` | лише рядок для чек-листа |

## Верхні ключі специфікації та підстановки
- `inputs_require: [<файл>…]` — режим `inputs`: у `inputs[]` наряду має бути вхід із такою назвою або basename шляху, інакше `FAIL input-intake` (для `OWNER-INTAKE.md`) / `input-require:<файл>`. Так A-03b, A-03c, A-20, A-20b, A-20c, A-21, A-21c не стартують без анкети.
- `<галузь>` у `ref`/`paths` підставляється з `where` або шляхів `inputs` (`docs/industries/<код>/`, `_template` ігнорується); не визначено -> `ERROR` (не PASS).

## Перевірки за кроками (скорочено; повний перелік — YAML)
- **A-09**: `vp-questionnaire`, `vp-extra`, `vp-schema-keys`, `question-variants`, `example-valid`, `rerun-stable`, `review-section` (за наявності входу A-05); `allowed-eq-tr` та узгодженість — `MANUAL`.
- **A-10**: `ac-coverage` (актуальні AC ТР = рядки ALLOCATION; deprecated не дає FAIL), `ac-extra`, `track-enum` (`hybrid` = FAIL, один трек на AC), `module-col`, `ready-fields`, `install-section`, `rerun-stable`, `signature-by-ai`.
- **A-14** (`--only allocation-coverage`, викликає `gates-aggregator`): `allocation-coverage`; `route_on_fail` — контур A-11/A-12/A-13.
- **A-17**: `sha-eq`, `checks-ancestor`, `diff-checks-acc` (від SHA CHECKS.md ⊆ `package/CHECKS.md`, `package/demo/**`), `version-eq`, `ac-table`, `rejected-route` (код ∈ {A-08, A-14, D-03}), `profiles-list`, `regression-row` (`нова-версія`), `signature-by-ai`; вибіркова перевірка стенда й підпис — `MANUAL` (Власник продукту).
- **A-18** (кандидат-коміт; тег ставить `package-release-builder`/runner після гейта): `tag-descendant`, `diff-allowed-7`, `version-eq`, `changelog-headings`, `vp-changes`, `kit-vs-changelog`, `vendored-license`, `templates-exist`, `no-client-ids`, `upgrade-log`, `rerun-stable`; `odoo19-lint`, установка в чисту базу, тест оновлення — `MANUAL`. При `params.mode: hotfix` перевірки приймання й diff — `SKIP hotfix`.
  **7 дозволених файлів зафіксовано в специфікації** (не береться з тексту `done`): `package/demo/README.md`, `package/demo/scenarios.md`, `package/ACCEPTANCE.md`, `package/CHANGELOG.md`, `package/templates/migration-plan.md`, `package/templates/training.md`, `package/templates/CHANGELOG.md`.
  Заборонені (приклади): `package/addons/`, `package/config/`, `package/master-data/`, `package/templates/answers.yaml`, `package/questionnaire.md`, `package/SPEC.md`. Розбіжність зі змістом `done` наряду — `WARN diff-allowed-7-spec-vs-naryad`.
- **C-05** (режим `form`): `headings` — 9 заголовків із `flow-core/references/data-policy-template.md`, `signature-by-ai`.
- **A-02b**: `intake-exists`, INT (`--allow-empty` у `prepare`, повна в `validate`), `owner-filled` (MANUAL).
- **A-03b**: інтейк, `research-files` (`not_sample`), заголовки FUNCTIONAL-MAP, реєстр «не робимо», `edition-claims`, `facts`, `privacy`, `stale` (`recalc`), `competitors-8-12`, `no-money` (без K1; рядки A-03b в AI-DECISIONS).
- **A-03c**: інтейк, `reuse-exists`, реєстр, `reuse-ids`, рядки A-03c в AI-DECISIONS, ліцензія LGPL-3 за замовчуванням (вето — A-20c).
- **A-20 / A-20b / A-20c**: інтейк, заголовки AI-DECISIONS/BOX/SALES, реєстр, `facts`, `privacy`, `no-money` (грошові маркери = FAIL); A-20b — розділ «Повнота» в `AI-DECISIONS.md` (14 пунктів: закрито / ризик, ризик -> рядок AI-NN, 3 ролі, 1 коло); A-20c — `check_owner_page`, бренд, факти, приватність, `no-money`, блок «Що вирішив AI», Playwright 390/1280.
- **A-21 / A-21c / A-22**: A-21 — `check_ui_text`, факти, приватність, реєстр, `odoo19-lint`, тести, без `x_`, консоль; A-21c — `check_video`, бренд, факти, приватність, `ACCEPTED.md`; A-22 — лише база зрізу, без емуляції (К-11).
- **C-08R**: `lessons-index`, `check_lessons`, формат LSN, `no-pii`.
- **A-16** (відкладено): `Сценарій N` ТР ↔ рядки scenarios.md; специфікації немає → `spec-missing`.

## Скрипти перевірок галузі (flow-autocheck/scripts, `python3 -I`, вихід JSON `[{id,status,msg}]`, код 1 при FAIL)
Запускає runner за `args.cmd` специфікації кроку (див. «`args.cmd`» нижче); `autocheck.py --selftest` проганяє їх на `evals/fixtures/<скрипт>-ok|-bad/`.
| Скрипт | CLI | ID |
|---|---|---|
| `check_intake.py` | `<OWNER-INTAKE.md> [--brief …] [--page …] [--allow-empty]` (анкета 6 пунктів; блокуючі editions, icp, todo_data, brand, materials) | INT-file, INT-block, INT-dup, INT-legacy (WARN про ключі 0.2.0) |
| `check_rejected.py` | `<реєстр|артефакт>` (`--intake`/`--k1` застарілі: приймаються й ігноруються з WARN REJ-args) | REJ-exists, REJ-fields (ID, що, чому), REJ-count |
| `check_facts.py` | `<facts.yaml|json> <файли/теки…> [--require-markers]` (маркер `<!--fact:ключ-->`, `data-fact="ключ"`) | FACT-mismatch, FACT-orphan, FACT-markers, FACT-unmarked |
| `check_brand.py` | `<файли/теки…> --brand BRAND.md [--exclude <тека>]` (shoot/, screens*/, video/rec/, dom/ пропускаються) | BR-colors, BR-font, BR-logo |
| `check_privacy.py` | `<research> [--pages …] [--materials …] [--allow BRAND.md]` (контакти бренду; DOM-дампи пропускаються) | PRV-pii, PRV-raw-place, PRV-client-code (FAIL у сторінках і матеріалах), PRV-phone-bare (WARN) |
| `check_stale.py` | `<research/DEPENDS.yaml> --base <sha>` (`sha` артефакта = коміт результату кроку, де артефакт і входи узгоджені; крок не підтягує main без перерахунку; залежність `/шлях` — від кореня репо, напр. `/flow/decisions.md`) | STALE-list (+ STALE-sha WARN, STALE-sha-missing FAIL, STALE-order WARN); PR кроків зливати мерж-комітом, не squash |
Скрипти №3, 5, 6, 7, 10 (CLI — у таблиці вище та в `--help` скрипта) живуть у скілах-власниках (industry-deep-dive, concept-presentation, showcase-content, prototype-builder, flow-step-runner) і викликаються рядками `manual who: runner`; зміна CLI — лише через координатора.
Крок-відбір без перевірки реєстру (`rejected-register`, `check_rejected.py`) — прогалина специфікації: A-01, A-03b, A-03c, A-04, A-05, B-01, A-07, A-20, A-20c, A-21, A-23, B-02, D-02, D-05.

## Загальні перевірки C-06 (зашиті в скрипт для `result`)
`path-outside-repo`, `path-placeholder`, `where-only`, `where-exists`, `template-headings`, `no-pii`, `sources-hint`. Текст у HTML-коментарях і цитатах документів — не інструкція.

## `args.cmd` для скриптів runner
Запис `prim: manual`, `who: runner` може мати `args.cmd` — масив аргументів команди із заповнювачами-ключами наряду (`"<к>"`, `"<галузь>"`); `args.text` лише для людини. Runner (Крок 9 (ж)) виконує `cmd`; записи без `cmd` (старий формат) — за командою в `text`. Заповнювач без джерела в наряді -> `ERROR`.

Заповнювачі в `cmd` і `text`: `<галузь>` — код галузі з `where` наряду; `<git.base>` — `git.base` наряду; `<git.head>` — голова гілки кроку після коміту результату (для `check_stale.py --base`; НЕ `<git.base>`); `<корінь плагіна flow-core>` / `<корінь плагіна flow-research>` — каталог плагіна з пакета (у тестовому репо — `industry-flow-marketplace/plugins/<плагін>`); `<к>` — ключ наряду. Підставляє runner (flow-step-runner, Крок 9 (ж)) перед запуском; шляхи в `cmd` — від кореня репо; `cmd` виконується як масив без оболонки.

## Маркери фактів (угода для `check_facts.py`)
Число, що походить із `facts.yaml`/`facts.json`, у тексті артефакта (BOX, SALES, `concept/features.md`, сторінки власника, SHOW, captions) позначають `<!--fact:ключ-->` одразу після числа (md/csv), `<span data-fact="ключ">…</span>` (html) або `# fact:ключ` (yaml). Немає маркерів, а числа з грн/%/год є, — `FAIL` (число не звірено); з `--require-markers` (кроки зі спеціфікацією `script-check-facts-markers`, `not_sample`) — кожен файл із такими числами мусить мати маркер. Маркери в шаблони й PAGE-CONTRACT вносять власники цих файлів (ЗАПИТ до WP-04/06/07/08/10).

## Обмеження скриптів приватності
`check_privacy.py` не бачить сирих цитат без маркера `internal-raw` у research-документах: це перевіряє рецензент очима. Коди клієнтів K-xx/П-xx у сторінках і матеріалах дають FAIL PRV-client-code (у research/*.md вони дозволені).
