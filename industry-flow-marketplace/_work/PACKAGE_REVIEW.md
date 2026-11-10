# PACKAGE_REVIEW — підсумкова рецензія після рішень людини (q01–q44), раунд 2 (2026-11-10)

Вердикт: **major** (2 major, 6 minor, blocker немає). Лише рекомендації; файли пакета не змінювались.

## 1. Що перевірено

- `claude plugin validate` для маркетплейсу і всіх 5 плагінів — пройшло. JSON, Python, bash — без синтаксичних помилок; yaml парситься (крім `ci-workflow-template.yml` — це шаблон із `{{…}}`, очікувано).
- 29 скілів у 5 плагінах: теки = README = `step-skill-map.md`; `name` у frontmatter збігається з текою; у кожного є «НЕ використовуй» і «Відкриті питання»; однакових тригерних фраз між скілами немає.
- Усі посилання `плагін:скіл` існують (пакет + каталог організації); старих назв кандидатів немає; версії — лише `@0.1.0` і приклад `@1.4.0`.
- Попередні major: M-2 (q09/q30) закрито — згадок профілю «без AI» як варіанту немає. M-4 закрито — `support-desk` знає бота, `params.handoff`, `HB-NNN` в `id-patterns.md`, рядок B-07 у `naryad-format.md`, `triage-routes.md` виправлено. M-5 закрито в межах можливого — `answer` заблоковано до підтвердження Тімліда в `kb-index.md`; виконавець бота структурно без інструментів запису. M-1 і M-3 закрито частково (нижче).
- q01: виняток лише для B-13/B-08a на `test-<клієнт>` — у 12 місцях однаково, на прод і інші кроки не поширено.
- q37: `prod-ro-<клієнт>` дозволено лише наряду з `skill_ref[0]` = `client-help-bot` — однаково в оркестраторі, sweep, runner, `naryad-format.md`, `data-and-connections.md`, шаблоні DATA_POLICY, SOW; рядки «ODOO:» на `prod-ro-*` відхиляються; `executor: central`.
- q17: еталони `apply.py`, `validate.py`, `install.sh` і решта скриптів є в `flow-core/references/templates/tools-odoo/`; захист: allow-list імен баз + відмова на «prod» в імені, для RPC — обов'язковий `ODOO_ALLOWED_HOSTS`.
- Вибірково без суперечностей: q03, q05, q06, q33, q34, q38, q42.

## 2. Зауваження

### Major

**M-1. Профілі доступу не покривають конектори шести скілів.** За `step-skill-map.md` скіл, якому потрібен конектор поза профілем, зупиняється `escalated`:
- `gates-aggregator` (A-14) і `package-release-builder` (A-18): потрібен MCP `github` (`actions_list`, `actions_get`, `get_commit`, `get_job_logs`, `get_tag`, `actions_run_trigger`), а профіль — `base`. У профілі `repo` немає `actions_run_trigger` і `get_tag`. Кожен A-14 зупиниться на статусі C-03.
- `support-desk` (B-09/B-10): читання договору супроводу з Drive, профіль `mail` Drive не має.
- `segment-selector`, режим `адреси` (A-23): Drive `create_file`; жоден профіль не має запису в Drive.
- `industry-scoring`, `segment-selector` (A-05), `prototype-builder`, `odoo-version-migrator`: `WebSearch`/`WebFetch` — немає в жодного виконавця.
Рекомендація: додати `gates-aggregator` і `package-release-builder` у профіль `repo` (запуск workflow — рядком «КОМАНДИ:» через runner); Drive-читання в `mail` або окремий профіль для `support-desk`; для `адреси` — запис файлу runner'ом або окремий профіль; `WebFetch`/`WebSearch` — у `research` (або прибрати зі скілів).

**M-2. q10: ядро і скіли-споживачі описують різний канал.** `naryad-format.md` р. 25 вводить ключ `preconditions_confirmed: {crm_deal_stage: signed, …}`. А `package-fit-gap` (`agreement-check.md` р. 7, `open-questions.md`), `runbook-executor` (р. 65–66, 190), `client-data-migrator` (р. 67–68, 179), `package-upgrade-runner` (р. 95) досі пишуть «у форматі наряду такого поля немає», «ключ наряду — відкрите питання» і чекають дослівний текст «стадія угоди в CRM: підписано». Крім того, для B-02 угода — це `discovery-agreement.md` (до SOW), а ключ один: значення `signed` не розрізняє угоду про обробку даних і SOW. В `odoo-bridge.md` ключа немає, хоча `c00-checklist.md` на нього посилається.
Рекомендація: у чотирьох скілах замінити очікування тексту на ключ `preconditions_confirmed.crm_deal_stage`; розділити значення (наприклад `discovery_signed` / `sow_signed`) або два ключі; дописати `odoo-bridge.md`.

### Minor

- m-1. `client-help-bot/references/open-questions.md`, останній рядок («Зміни поза цим скілом: рядок B-07…, `params.handoff`…») — уже зроблено, прибрати; лишити лише тригер `answer` «на період» і поле db.
- m-2. Там само питання «`groups_id` чи `group_ids`»: у Odoo 19 поле `groups_id` перейменовано (ловушка `boost:odoo19-lint`) — закрити через `boost:source-check`.
- m-3. `config-package-format.md` р. 15: «у 0.1 НЕ постачається: install.sh, bin/apply.py, bin/validate.py» — після q17 еталони є; сигнатури еталонів і контракту різні (питання в `c00-checklist.md`), але в README «Лишається відкритим» його немає.
- m-4. У багатьох скілах в «Інструменти» стоїть `Bash (git)`, а виконавець Bash не має (команди — рядком «КОМАНДИ:» через runner). Додати одне речення в `executor-brief.md` або вирівняти формулювання.
- m-5. `guard_db` у bash-скриптах перевіряє лише ім'я бази; перевірку хоста додає C-00 (є в чек-листі). До неї скрипти не запускати на сервері, де є прод.
- m-6. Мітка Gmail допомоги — окрема чи спільна з `support-desk` — відкрита (у README є); до рішення діє «мітки різні, спільна = `escalated`».

## 3. Покриття флоу

Без змін відносно раунду 1. Кандидати з `candidates.md` закриті скілами або злиттям: `support-first-line` + `support-sla-tracker` → `support-desk`; `reference-client-selector` + `segment-lead-builder` → `segment-selector`; `release-planner` + `pilot-review` → `product-decision-drafter`; `config-drift-checker` → `runbook-executor` (режим `звірка`); `odoo-flow-bridge` → `flow-core/references/odoo-bridge.md`; `data-policy-builder` — скіла немає: C-05 людський крок із шаблоном `data-policy-template.md` і `checks/C-05.yaml`. Без скіла пакета (скіли організації або люди): A-02, A-03, A-06, A-08, A-10, A-11, A-16, A-19, B-05, B-07 (навчання), B-08b–d, B-12, C-00, C-08. Кроку-виробника знеособленої копії (C-09) немає — відкладено q03.

---

# PACKAGE_REVIEW — підсумкова рецензія після рішень людини (q01–q44), раунд 1 (2026-11-10)

Перевірка пакета на коміті `7e0f831` (робоче дерево чисте) після внесення рішень `DECISIONS_2026-11-10.md`. Лише рекомендації, файли пакета не змінювались. Рішення людини не переглядались; технічні імена полів Odoo — C-00.
Вердикт: **major** (blocker — 0, major — 5, minor — 10).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6 |
| marketplace.json ↔ plugin.json ↔ теки | 5/5 плагінів, версії 0.1.0, іконки є; 29 `SKILL.md` (README: 29), 29 `evals/evals.json` (усі парсяться), 36 `checks/*.yaml` |
| 29 `SKILL.md` | `name` = тека; frontmatter лише `name`/`description`; розділи «Наряд і звіт», «Pre-save», «Відкриті питання», «Чого НЕ робити» є в усіх |
| Посилання `плагін:скіл` | усі існують (пакет, агенти `flow-core`, скіли організації) |
| Самотести | `autocheck.py --selftest` OK; `evals_to_cli.py --self-test` OK |
| q17: `flow-core/references/templates/tools-odoo/` | є `apply.py`, `validate.py`, `install.sh` + 6 скриптів; усі викликають `guard_db`; `prod`, `prod-acme`, `test-prod`, `prod-ro-k01`, `client-x`, `anon-k1` — відмова; `apply.py rpc`/`validate.py` додатково вимагають `ODOO_ALLOWED_HOSTS` і https |
| q37: клас `prod-ro-<клієнт>` | дозволений лише `flow-client-delivery:client-help-bot`: `data-and-connections.md` §3.5–3.6, `naryad-format.md`, оркестратор (Крок 3, евал `prod-ro-only-help-bot`), runner (Крок 2, евал `prod-ro-write-refused`, рядки «ODOO:» на `prod-ro-*` — відмова), `eval-builder`, `flow-state.md`, `package-usage-metrics` (прод не читає). В інших скілах дозволу немає |
| q01: виняток B-13/B-08a | є в `data-and-connections.md`, `naryad-format.md`, оркестраторі, runner, `runbook-executor` (евал: B-04 з `executor: any` → `stopped`). `client-data-migrator`, `package-upgrade-runner`, `package-fit-gap`, `support-desk`, `client-help-bot`, `past-projects-analyzer` лишились `central` — виняток не поширився |
| q09/q30: профіль «без AI» | прибрано з `package-fit-gap`, `package-sow-builder`; **лишився** в `product-decision-drafter` (M-2) |
| Решта рішень | q02–q08, q11–q16, q18–q29, q31–q36, q38–q44 внесені у відповідні скіли й references; суперечностей не знайдено, крім зазначених нижче |

## 2. Зауваження

### Major

**M-1. Виконавець `flow-core:flow-executor` не має інструментів конекторів, яких потребують скіли.**
`plugins/flow-core/agents/flow-executor.md`, `tools:` — лише `Read, Write, Edit, Grep, Glob, Skill` і три читальні інструменти `odoo-mcp`. Runner (`flow-step-runner/SKILL.md` р. 32) забороняє інший агент. Отже під runner не виконаються: `client-help-bot` і `support-desk` (Gmail: `search_threads`, `get_thread`, `create_draft`), `industry-scoring` і `segment-selector` (`odb-catalog`), `past-projects-analyzer` (AIKB), `package-fit-gap` (Fathom), `segment-selector` `адреси` (запис на Drive), `ci-pipeline-builder` (MCP `github`). У `naryad-format.md`, `executor-brief.md` і runner про ці конектори немає жодного слова.
Виправити: окремі визначення агентів із мінімальним `tools:` за профілем кроку (наприклад `flow-executor-mail`: Gmail лише читання й `create_draft`, без `send_message`/`label_*`; `flow-executor-research`: `odb-catalog`, AIKB, Fathom — лише читання), ключ наряду `access_profile`, який ставить оркестратор за `step-skill-map.md`, і правило runner «агент = профіль наряду». Не розширювати єдиний `flow-executor` усіма інструментами: бот із `prod-ro` не повинен отримати запис у Gmail чи Drive.

**M-2. q09/q30 не внесено в `product-decision-drafter`.**
`plugins/flow-package-evolution/skills/product-decision-drafter/references/business-case.md` р. 49–54: розділ «Політика клієнтів без згоди на AI» з варіантом «Б — профіль „без AI на даних“: кроки B-06, B-09, B-10, D-01 ручні» і «вибір — людина»; `SKILL.md` р. 145 вимагає в чернетці A-07 цей розділ «(А/Б)». Суперечить рішенню «таких клієнтів не беремо, профілю немає» і скілам `package-fit-gap`, `package-sow-builder`.
Виправити: замінити розділ на один рядок-факт «клієнтів без згоди на AI не беремо (q09); відмова = причина „умови AI“ у воронці B-01», прибрати «(А/Б)» з р. 145 і вплив профілю на ціну SOW.

**M-3. q10 (підпис = стадія угоди в CRM) є в чотирьох скілах, але не в `flow-core`.**
`package-fit-gap` (р. 69–70), `runbook-executor` (р. 65–66), `client-data-migrator` (р. 67–68), `package-upgrade-runner` (р. 95) чекають у тексті наряду рядок «стадія угоди в CRM: підписано». У `naryad-format.md`, `flow-map.md` (р. 63: «B-03 done + Затвердити (SOW підписано) → B-04» — тригер досі кнопка), оркестраторі, `odoo-bridge.md` і `c00-checklist.md` слова «CRM» немає: ніхто не визначений вписувати цю ознаку. Наслідок — B-02, B-04, B-06, B-11 зупиняться або ескалюють на першому клієнті.
Виправити: логічний ключ у `naryad-format.md` (наприклад `preconditions_confirmed: {crm_deal_stage: signed, by: <роль>, at: <дата>}`), правило оркестратора «B-04 ставити лише за стадії угоди CRM „підписано“; ознаку в наряд вписує C-01 з дзеркального поля проєкту», рядок у `flow-map.md` р. 63 і пункт у `c00-checklist.md` (назва стадії CRM і поле-дзеркало — C-00). У README це питання в «Лишається відкритим» додати.

**M-4. Межа `client-help-bot` ↔ `support-desk` описана лише з боку бота.**
`support-desk/SKILL.md` бота не знає: у `description` і таблиці «Що чиє» його немає, обидва скіли читають листи клієнта з мітки Gmail і створюють чернетки відповідей; маршрут «консультація» (питання «як») у `flow-client-delivery/references/triage-routes.md` р. 15 лишився за Підтримкою. Питання «окрема мітка допомоги чи спільна» відкрите (`client-help-bot/references/open-questions.md`); за спільної мітки на один тред буде дві чернетки. Вхід `params.handoff` у `support-desk` `intake` не реалізовано; `HB-NNN` немає в `flow-core/references/id-patterns.md`; рядка B-07 (`prepare`/`answer`, `period`) немає в таблиці `params.mode` `naryad-format.md` (є лише в `step-skill-map.md`).
Виправити: 1) у `support-desk` — рядок у «Що чиє» і «НЕ використовуй для питань „як зробити“ за наявності розділу бота в SOW (client-help-bot)», крок `intake`: тред із мітки допомоги не брати, передачу приймати за `params.handoff`; 2) до рішення про мітку зафіксувати в обох скілах «мітки різні, спільна мітка → `escalated`»; 3) рядок B-07 у `naryad-format.md`, `HB-NNN` в `id-patterns.md`, примітка в `triage-routes.md`.

**M-5. q37: «лише читання» на проді гарантоване тільки на боці скіла; режим `answer` не залежить від підтвердження прав технічного користувача.**
`client-help-bot/references/tech-user-checklist.md` і «Відкриті питання»: штатної read-only ролі немає, гарантія — інструменти скіла й allow-list. Runner сам має `odoo_write`/`odoo_execute` (для бази `flow`), підключення `prod-ro-<клієнт>` у конекторі центрального агента доступне всім його сесіям. Умова менеджера «окремий технічний користувач з мінімальними групами, жодних записів» перевіряється лише читанням груп (`prepare`, крок 5).
Виправити (рішення не переглядається, лише його дотримання): у `prepare` зробити обов'язковим пункт чек-листа «Тімлід підтвердив: користувач не має прав запису/створення/видалення в жодній моделі; дата, роль» (рядок у `kb-index.md`, перевірка `HB-prepare`); без нього `answer` → `escalated`, прод не читати. У `c00-checklist.md` — пункт «`prod-ro-*`: права лише на читання перевірено на базі клієнта». Питання лишити в README як блокувальне для першого запуску `answer`.

### Minor

1. `config-as-code`: `SKILL.md` р. 20 і `references/apply-semantics.md` р. 3 кажуть «скриптів `apply.py`/`validate.py`/`install.sh` немає», а р. 243 того ж скіла й q17 — «еталони є в `flow-core/references/templates/tools-odoo/`, у `tools/odoo/` їх ставить C-00». Уточнити формулювання в р. 20 і р. 3: «у `tools/odoo/` репозиторію ще немає (еталони — у flow-core, q17)». Р. 96 «рядка A-12 у таблиці `params.mode` немає» застарів: рядок є (`naryad-format.md` р. 65).
2. Хибні номери рішень (лишились зі старої нумерації README): `client-help-bot/SKILL.md` р. 138 і `references/open-questions.md` р. 4 — «q21: чернетки» (q21 — каталог плагінів); `segment-selector/SKILL.md` р. 76 — «q12: CRM вручну» (q12 — додаткова угода); `flow-autocheck/SKILL.md` р. 32 і 68 — «(q43)» біля режиму `inputs` (q43 — формулювання «на базі Odoo 19»). Прибрати номер або замінити на правильне джерело.
3. Рядок «Коротко» у п'яти `plugins/*/README.md`: «дані клієнта — лише тестові бази й знеособлені копії» — без q02 (копій на пілоті немає), q37 і q01. Звести до посилання на `data-and-connections.md` §3.6 або дописати винятки.
4. Закриті пункти досі названі відкритими: README «`config-as-code`: клас `test-pkg-<пакет>` у `data-and-connections.md`» (клас уже визначено в §3.5); `segment-selector/SKILL.md` р. 46–48 «`naryad-format.md`, `flow-map.md` не знають наряду `адреси`» (знають: `flow-map.md` р. 24, `naryad-format.md` р. 66); `demand-test-runner/SKILL.md` р. 204 (рядок A-23 у таблиці режимів уже є). У `naryad-format.md` рядок A-08 продубльовано (р. 60–61).
5. `_work/CONCEPT.md` не оновлено після рішень: «28 скілів» (р. 9, 40), `client-help-bot` — «відкласти» (р. 235), немає винятків q01 і q37. README називає його концепцією пакета. Оновити §2, §3.5–3.6, §4 або дописати на початку «після 2026-11-10 чинні `DECISIONS_2026-11-10.md` і `flow-core/references/`».
6. `flow-orchestrator/SKILL.md` р. 80 (Крок 2 п. 4): клієнт з «AI-обробка: відкликано» → кроки ставляться людині; посилання на розділ DATA_POLICY «Відкликання згоди на AI-обробку», якого немає в переліку обов'язкових заголовків (`data-and-connections.md` §3.6, `data-policy-template.md`). Дописати, що це лише аварійний випадок C-08 під час чинного договору, а не профіль продажу (q09), і додати заголовок у шаблон або прибрати посилання.
7. `description` у `package-release-builder` — 915 символів (у пакеті прийнято ≤ 900); у `client-help-bot` — 897, запасу немає.
8. У робочому дереві 10 файлів `__pycache__/*.pyc` (git їх ігнорує, але установка з локальної теки їх забере; еталон `install.sh` сам зупиняється на `__pycache__`). Видалити. Клас `o19demo` названо демо-класом у `data-and-connections.md` §3.5, а `guard_db` приймає лише `demo-<суфікс>`: дописати в §3.5, що скрипти `tools/odoo` з `o19demo` не працюють.
9. `client-help-bot`: 3 евал-кейси без фікстур (README плагіна це визнає); немає кейсів «немає розділу бота в SOW → `prepare` без читання проду», «`executor` не `central`», «тригерна фраза без наряду». `checks/B-07.yaml` — усі три перевірки `manual`; перевірок частини «навчання» кроку B-07 немає.
10. Наживо не запускалось: `claude plugin eval`, odoo-mcp, GitHub, Gmail, `tools-odoo` на Odoo 19 (README це вказує; q17 і q26 — до пілоту).

## 3. Покриття флоу

29 скілів: 28 за CONCEPT §2 і `client-help-bot` (q37). Кандидати з `candidates.md` реалізовані або злиті/відкинуті за CONCEPT §4.
Без скіла пакета: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; на скілах організації — A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07 (навчання), B-08c, B-08a `збіжність`; C-05 — шаблон `data-policy-template.md` + `C-05.yaml`; C-07 — режим `incident` у `eval-builder`.
Немає виробника: знеособлена копія `anon-<клієнт>` (відкладено, q02/q03); тригер наряду `client-help-bot` `answer` «на період» (до рішення — вручну PM/Підтримка); канал ознаки «стадія угоди в CRM» (M-3).

---

# PACKAGE_REVIEW — підсумкова рецензія після дозбирання, раунд 4 (2026-11-10)

Перевірка після виправлень M-1 раунду 3 (15 файлів у робочому дереві поверх `65373ab`, ще не закомічено). Лише рекомендації, файли пакета не змінювались. Прийняті рішення (D-01, `eval-builder` лише під runner, агенти у `flow-core/agents/`, імена полів Odoo — C-00) не переглядались; відкриті питання README не вирішувались.
Вердикт: **major** (blocker — 0, major — 1, minor — 5).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6 |
| marketplace.json ↔ plugin.json ↔ теки | 5/5 плагінів (версії 0.1.0, іконки є), 28 `SKILL.md`, 28 `evals/evals.json`, `*.pyc` — 0 |
| 28 `SKILL.md` | `name` = тека; frontmatter лише `name`/`description`; `description` після розбору YAML — максимум 888 (усі ≤ 900) |
| Посилання `плагін:скіл` | усі існують (пакет, агенти `flow-core`, `boost`, `odoo19-mvp-build`, `odoo19-implementation`, `odoo19-tr-authoring`, `odoo19-sales-prep`) |
| `checks/*.yaml` (35) | усі парсяться; усі `<корінь плагіна X>/…` скрипти існують; усі значення `when` — з переліку `checks.md` |
| Самотести | `autocheck.py --selftest` OK; `evals_to_cli.py --self-test` OK |
| Шаблони `tools-odoo` | 6 скриптів викликають `guard_db`; `prod`, `prod-acme`, `test-prod`, `Test-PROD2`, `client-x`, `anon-k1`, порожнє, `test-`, `test-x;id` — відмова (код 2); `test-x`, `demo-1`, `emu-a`, `test-pkg-a` — дозволено |
| Попередній M-1 (а) | закрито: умова `when: mode:<значення>` у `checks.md` і `autocheck.py`; `A-23.yaml` (7 записів `mode:prep\|results`), `B-08a.yaml` (`mode:звірка`); runner (ж) виконує записи лише за справдженої `when` і бере плагін з тексту команди, не зі `skill_ref[0]` |
| Попередній M-1 (в) | закрито: рядки `A-23 список → prep` і `B-08a звірка → збіжність` у `flow-map.md`, посилання з оркестратора (ключ ідемпотентності з `mode`), `segment-selector` р. 53 виправлено |
| Попередній M-1 (б) | закрито в таблиці й README (один наряд B-11, звірку й додаток викликає ведучий), але позначка `called` не доведена до формату наряду й runner — M-1 нижче |
| Minor 1 і 3 раунду 3 | закрито: `guard_db` відхиляє імена з `prod`, пункт у `c00-checklist.md`; `pii_strict` у `B-11.yaml` і `D-01.yaml` |

## 2. Зауваження

### Major

**M-1. Позначка `called` для B-11 існує лише в `step-skill-map.md` р. 33 і README р. 39; формат наряду, runner, оркестратор і `package-upgrade-runner` її не знають.**
(а) `flow-step-runner/SKILL.md` р. 34 і Крок 9 (д) трактують `skill_ref[1:]` як «скіли-гейти» й запускають їх після виконавця. Для наряду B-11 зі `skill_ref: [package-upgrade-runner, runbook-executor, package-sow-builder]` runner запустить `runbook-executor` («звірка», читання тестової бази клієнта) і `package-sow-builder` як гейти — незалежно від `params.reconcile`, який `package-upgrade-runner` (Крок 8, В-7) за замовчуванням тримає вимкненим до рішення людини.
(б) `naryad-format.md` р. 11 задає `skill_ref` як список рядків `плагін:скіл@semver`; синтаксису позначки немає, а Крок 3 runner порівнює semver точною рівністю — суфікс у рядку зламає звірку версії.
(в) `package-upgrade-runner/SKILL.md` (р. 92, 141) викликає обидва скіли, але про `skill_ref[1:]` і звірку їхніх версій не каже; `flow-orchestrator` не має правила додавати викликані скіли в наряд B-11.
Виправити: 1) у `naryad-format.md` додати окремий ключ `called_skills: ["плагін:скіл@semver", …]` (скіли, які ведучий викликає у своєму запуску; runner звіряє версії на Кроці 3 і не запускає їх на Кроці 9 (д)) — це простіше за позначку в `skill_ref`; 2) у runner: Крок 3 — звірка semver і для `called_skills`; (д) — «лише `skill_ref[1:]`»; 3) у `step-skill-map.md` р. 33 і README р. 39 замінити «`skill_ref[1:]` з позначкою `called`» на `called_skills`; 4) у `package-upgrade-runner` Кроки 2 і 8 — «викликаний скіл має бути в `called_skills` наряду, інакше `escalated`»; 5) в оркестраторі (блок `skill_ref`, р. 101) — «`called_skills` — з примітки `step-skill-map.md`».

### Minor

1. `flow-map.md`: рядки-сусіди не уточнені за режимом. Р. 23 «A-21 done → A-23» (має бути A-23 `список`), р. 68 «B-07 done → B-08a» (B-08a `звірка`), р. 70 «B-08a APPROVE → B-08b» (APPROVE наряду `збіжність`), р. 26 «A-23 done (сигнали…)» (наряд `results`). Тригер наряду A-23 `адреси` не названо (р. 24 каже лише «окремий наряд для центрального агента»), хоча `segment-selector` р. 53 посилається на `flow-map.md`. Додати режими в ці рядки й рядок «A-23 `список` waiting_human (потрібні адреси) → A-23 `адреси`».
2. `naryad-format.md`: у таблиці режимів немає рядків A-23 (`список\|адреси\|prep\|results`) і B-08a (`звірка\|збіжність`) — вони лише в `step-skill-map.md`; коментар р. 46 `reconcile: … # B-06 фаза 1` стосується B-11 (у B-06 це `mode: reconcile`). `package-upgrade-runner` В-1 (р. 205) застаріло: `phase` і `reconcile` у `naryad-format.md` вже описані.
3. Наряд A-23 `список\|адреси` і B-08a `збіжність` тепер має лише загальні перевірки C-06 (усі записи кроку — `SKIP` або `manual`). Для A-23 `список` додати `exists` на `mailing-list.csv` і перевірку SS-mode; для `збіжність` — `exists` на `convergence.md`. Наряд A-23 без `params.mode` дає `SKIP` усіх семи записів і `PASS`: додати в `A-23.yaml` перевірку «`params.mode` задано».
4. Крок 9 (ж) і далі розпізнає команду з прози `args.text` (необов'язкові частини, заповнювачі `<complexity.md>`); надійніше поле `args.cmd` (масив) — повтор з раундів 2–3. Кроки з усіма перевірками `manual` без команди: A-05, A-07, A-22, B-01, D-03, D-04.
5. Виправлення раунду 3 не закомічені (15 змінених файлів). Наживо не запускалось (за `_work/static-run/*.md`): `claude plugin eval`, odoo-mcp, GitHub, Gmail, `tools-odoo` на Odoo 19 — перший живий прогін перед поданням у каталог.

## 3. Покриття флоу

Без змін: 28 скілів за CONCEPT §2 на місці, кандидати з `candidates.md` реалізовані або злиті/відкинуті за CONCEPT §4.
Без власного скіла пакета: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; на скілах організації — A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07, B-08c і другий наряд B-08a; C-05 — шаблон `data-policy-template.md` + `C-05.yaml`; C-07 — режим `incident` у `eval-builder`. Відкладено `client-help-bot` (B-07, питання 24). Виробника знеособленої копії `anon-<клієнт>` немає (питання 26).

# PACKAGE_REVIEW — раунд 1 (2026-11-09)

Рецензія всього пакета `industry-flow-marketplace`. Лише рекомендації, файли пакета не змінювались.
Вердикт: **major** (blocker — 0, major — 12, minor — 10).

## 1. Що перевірено і результат

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` (маркетплейс) | PASS |
| `claude plugin validate plugins/<p>` × 5 | PASS; одне попередження на кожен плагін — `ICON_MISSING` (не впливає на установку) |
| marketplace.json ↔ теки плагінів ↔ plugin.json | 5/5, імена, описи, версії `0.1.0` збігаються |
| Скіли: 28 за CONCEPT §2 ↔ 28 `SKILL.md` | всі на місці (core 6, research 6, build 6, delivery 6, evolution 4); `name` = тека; frontmatter лише `name`/`description`; YAML валідний |
| `evals/evals.json` | є в усіх 28, JSON валідний, 3–10 кейсів |
| Посилання `плагін:скіл` (усі `.md/.json/.yaml/.py`) | усі існують у пакеті або каталозі організації; `flow-core:flow-executor|flow-reviewer` — агенти, є в `plugins/flow-core/agents/` |
| Дублі тригерних фраз між `description` | точних дублів немає; кожен код кроку як «власний» має одного власника (режими B-09/B-10, A-15/A-22, A-07/A-17/D-04/D-05 — в одному скілі) |
| `connection_id` у скілах з `odoo-mcp` | є в усіх; `demand-test-runner` odoo-mcp забороняє (коректно) |
| Агенти (рішення 2) | `flow-step-runner` (SKILL.md, executor-brief, model-ladder, evals) і `plugins/flow-core/README.md` посилаються на `agents/` flow-core, одна копія. Кореневий README агентів не згадує (minor) |
| Довжина SKILL.md ≤ 250 | 27/28; `package-release-builder` — 256 |

## 2. Зауваження

### Major

**M-1. Рішення менеджера 1 (eval-builder лише під runner) не внесено.**
`plugins/flow-core/skills/eval-builder/SKILL.md` р. 75–86 («Шлях 2 — ручний запуск», `params.manual`, `by: self`), р. 177; `references/index-checks.md` р. 5; `references/open-questions.md` р. 6, 20; `evals/evals.json` р. 100–106 (кейс шляху 2). Файлу `flow-core/skills/flow-autocheck/references/checks/C-04.yaml` (і `C-07.yaml`) немає, тоді як `dispatcher-config.md` (`weekly: [C-04]`), `sweep-rules.md` р. 21 і `flow-map.md` р. 103 ставлять C-04 щотижня → щотижнева ескалація «немає специфікації кроку».
Виправити: прибрати шлях 2, `params.manual`, `by: self` і кейс евала; Крок 0 — лише перевірки шляху 1; додати `checks/C-04.yaml` (+`C-07.yaml`) з шістьма механічними перевірками з `index-checks.md` (`scope-evals-only` за `git.base/head`, `json-schema`, `no-pii` за `flow-core/references/pii-patterns.md`, `source-filled`, `skills-covered`, `incident-case`), решта — MANUAL; у `naryad-format.md` додати рядки `params.mode` C-04 (`weekly|init|regress`) і C-07 (`incident`); розклад оркестратора лишити.

**M-2. eval-builder під runner не має Bash.** Виконавець `flow-core:flow-executor` без Bash, а скіл потребує `claude plugin eval`, `git`, `jq` (open-questions eval-builder №2 — не закрито). Після M-1 це єдиний шлях, тож крок не виконається.
Виправити в `flow-step-runner`: або явне правило «команди з рядка `КОМАНДИ:` для C-04/C-07 виконує runner (дозволений перелік: `claude plugin eval`, `git`, `jq`) і повертає вивід виконавцю», або два проходи (кейси → runner запускає регрес → статуси й INDEX). Дзеркально описати в eval-builder.

**M-3. Системне: виконавець не має `odoo_write/create/execute`, а скіли їх вимагають.**
`agents/flow-executor.md` дає лише `odoo_search_read`, `odoo_get_fields`, `list_odoo_connections`. Запис/execute потрібні: `runbook-executor` (B-04, `odoo_write/execute/create`), `client-data-migrator` (`odoo_execute load`), `master-data-template-builder` (`default_get`, `load`), `config-as-code` (`ir.module.module.update_list`), `demo-base-builder` (A-22, `x_`-моделі), `package-usage-metrics` і `flow-step-runner` для лічильників (`odoo_execute search_count`). Жоден зі скілів і runner цього розриву не описують — під циклом C-06 ці кроки не виконаються.
Виправити (рішення власника flow-core, одне на пакет): (а) другий агент `flow-core:flow-executor-odoo` з `odoo_write/create/execute`, який runner обирає лише коли в наряді `odoo_connections` містить клас `test-*`/`demo`/`emu-*`/`test-pkg-*` з `purpose` запису; (б) або протокол «ODOO: …» — виконавець перелічує виклики, виконує runner (аналог «КОМАНДИ:»). Для `search_count` — окремо: або (а), або перелік лічильників виконує runner. Зафіксувати в `executor-brief.md`, `naryad-format.md` і в розділі «Інструменти та доступи» кожного з шести скілів.

**M-4. Прод-читання в `package-usage-metrics` суперечить правилу «прод заборонено» без зафіксованого рішення людини.**
Скіл і `naryad-format.md` (рядок D-01: `prod-metrics-<код>`) читають прод лічильниками; CONCEPT §3.5 називає це єдиним винятком, але кореневий README і модель виконання кажуть «прод заборонено» без винятку; картка D-01 має `executor: any` (скіл вимагає `central`). Обмеження скіла коректні (лише `search_count`, без вмісту, центральний агент), тому не blocker, але виняток має бути рішенням людини.
Виправити: винести в «Відкриті питання до людини» (нижче, №1); до рішення — у `sweep-rules`/`dispatcher-config` не ставити `collect` автоматично; у README і `conventions.md` правило сформулювати однаково («прод заборонено; виняток D-01 — лише після рішення …»); картку D-01 → `executor: central`.

**M-5. Оренда: дві формули.** `flow-core/references/odoo-bridge.md` р. 68: `lease_until = now + limits.timeout_min`; `flow-orchestrator` (`dispatch-rules.md` р. 12, `dispatcher-config.md` `lease_factor: 1.5`, `sweep-rules.md` р. 11): `timeoutMin × 1,5`. Runner запише коротшу оренду, sweep забере задачу до кінця роботи.
Виправити: одна формула в `odoo-bridge.md` §7 (рекомендую `timeout_min × lease_factor`, фактор — у наряді `limits.lease_factor` або в `dispatcher.yaml`, який runner не читає → класти в наряд); sweep порівнює лише `lease_until < now`.

**M-6. Пошук dispatch-прогону CI: `head_sha` проти `run-name`.** `flow-package-build/skills/gates-aggregator/references/c03-lookup.md` р. 9, 15, 25 шукає за `head_sha`; `ci-pipeline-builder` (`ci-contract.md` р. 22–27, SKILL.md р. 121, 145) і `package-upgrade-runner/references/ci-dispatch.md` р. 18 — за SHA в `run-name`/`display_title`. Для `inputs.sha` ≠ HEAD гілки A-14 прогін не знайде.
Виправити `c03-lookup.md` за контрактом `ci-pipeline-builder`; перевірити, чи MCP `github` повертає `display_title` (В-7).

**M-7. Два `ci-contract.md` з різними входами dispatch.** `flow-core/skills/ci-pipeline-builder/references/ci-contract.md` (фактичний: тег, клієнт, версія Odoo, sha) і `flow-package-build/skills/package-release-builder/references/ci-contract.md` (`tag_candidate`, `mode`, `prev_tag`). Власник контракту — `ci-pipeline-builder`.
Виправити: у release-builder лишити лише посилання на контракт flow-core і список запитів до нього (вхід `prev_tag`/`instance` для тесту оновлення R-11); узгодити з `package-upgrade-runner` (В-2).

**M-8. `naryad-format.md` не знає режимів більшості скілів.** Таблиця `params.mode` має A-08, A-14, A-17/A-18, B-03, B-09, B-10, D-01. Скіли очікують, але рядків немає: A-09 (`review`, `new-version`, `return`), A-12 (`build|fix|new-version|validate`), A-15/A-22, B-04/B-13/B-08a (`mode`, `phase`), B-06 (основний/звірка/повернення), B-11 (`phase: 0|1`, `reconcile`, `pilot`), D-02 (`a|b|c|d`, `phase`, `trigger_ref`), D-03 (`prepare|verify`, `resume`), A-05/B-01/A-23 (режими `segment-selector`), C-04/C-07; також ключі `maturity`, `check.risk_paths`, `repo.base_sha`. Оркестратор не зможе поставити ці наряди однозначно (backlog-triage сам називає це «блокер для C-01»).
Виправити: один прохід власника flow-core по розділах «Відкриті питання» всіх скілів — внести рядки в `naryad-format.md`, блоки звіту (`project_fields`, `evals`, `upgrade_odoo`, список у `returned_to`) у `report-format.md`, переходи (A-04→A-02, A-13→A-10/A-08, D-03 prepare→verify) у `flow-map.md`.

**M-9. Немає специфікацій `flow-autocheck` для кроків, які на них спираються.** Є `checks/` A-09, A-10, A-14, A-17, A-18, C-05. Немає: C-04, C-07 (M-1), A-07, D-04, D-05 (`product-decision-drafter` В-5: «до того завершуються `escalated`»); `A-09.yaml` неповний (`questionnaire-builder`: `extra_allowed`, `variants-1to1`, `schema-format` тощо), `A-17.yaml` без коду `D-03` у `rejected-route`.
Виправити: додати відсутні yaml; до того README має чесно перелічити кроки, що ескалюють.

**M-10. Клас «чиста тестова база пакета» не визначений у конвенціях, імена розходяться.** `conventions.md`/`data-and-connections.md` §3.5 мають `flow`, `test-<клієнт>`, `demo`/`o19demo`, `emu-<галузь>`. Скіли вживають `test-pkg-<id>` (6), `test-pkg-<пакет>` (3), `ci-<пакет>` (release-builder), `demo-<пакет>[-<instance>]`, `prod-metrics-<код>` (naryad-format). Allow-list — правило безпеки; невизначений клас = або зупинка runner, або розширення «на око».
Виправити: додати класи `test-pkg-<пакет>` і (за рішенням M-4) `prod-metrics-<код>` у `data-and-connections.md`, `conventions.md`, `data-policy-template.md` («Класи доступу до баз Odoo»); замінити `ci-<пакет>` на `test-pkg-<пакет>`; `<к>` vs `<клієнт>` — одне написання.

**M-11. `description` довші за 1024 символи.** `backlog-triage` (1509), `questionnaire-builder` (1504), `runbook-executor` (1143), `demo-base-builder` (1095), `package-release-builder` (1050). CONCEPT §3.9 — ≤ ~900; найдовший опис у каталозі організації — 920; ліміт поля `description` скіла на claude.ai — 1024 (каталог організації синхронізується звідти) — завантаження може бути відхилене або хвіст «НЕ для…» обрізаний.
Виправити: скоротити до ≤ 900–1000, зберігши тригери і блок «НЕ для».

**M-12. У кореневому README немає розділу «Відкриті питання до людини» (рішення 4).** Чернетка — розділ 4 цього файла. Також немає розділів «Відкриті питання» у `client-data-migrator`, `gates-aggregator`, `demand-test-runner` (у migrator питання розкидані по тексту, р. 175; у demand-test-runner — р. 208–214 під іншим заголовком), у `prototype-builder` і `past-projects-analyzer` заголовок є, у prototype — порожньо.

### Minor

- m-1. Зламані/застарілі шляхи: `package-fit-gap/references/open-questions.md` р. 10 → `flow-client-delivery/references/fit-gap-template.md` (файл у теці скіла); `flow-package-build/references/master-data-format.md` р. 24 → `references/fictional-examples.md` (файл у теці скіла `master-data-template-builder`); `package-release-builder/SKILL.md` р. 256 → `flow-core/references/pr-checklist.md` (фактично `flow-core/skills/flow-step-runner/references/pr-checklist.md`).
- m-2. Спільні references з CONCEPT §3.10, яких немає: flow-core `artifacts-registry.md`, `pr-checklist.md` (лежить у скілі); build `allocation-template.md`, `module-skeleton.md`, `changelog-template.md` (покриття A-10/A-11 у §2.6 спирається саме на них); delivery `fit-gap-template.md`, `sow-template.md`, `config-log-format.md` (у скілах — прийнятно); evolution — теки `references/` немає; research `scoring-formula.md`, `demand-thresholds.md`. Або створити, або оновити CONCEPT §3.10/§2.6.
- m-3. Дублі, що розійдуться: `flow-core/references/conventions.md` р. 55–80 = `data-and-connections.md` (дослівно); `master-data-format.md` у двох місцях; `concept-templates.md` розходиться зі скриптом `concept-mapper` (його ж В-4). Лишити одне джерело, друге — посилання.
- m-4. Заголовки розділів не за §3.8: `product-decision-drafter` — «Наряд, звіт, межі запису» (замість «Наряд і звіт»); `questionnaire-builder` — «Перевірки» (замість «Автоперевірка»). Зміст є.
- m-5. `package-release-builder/SKILL.md` — 256 рядків (ліміт ~250).
- m-6. Кореневий README: у рядку `flow-core` кроки «C-06, C-05, C-07, C-08» — немає C-01, C-02, C-03, C-04; немає згадки агентів `flow-core/agents/` і залежності «спершу flow-core». Додати `"dependencies": ["flow-core"]` у `plugin.json` чотирьох плагінів (якщо версія CLI підтримує — перевірити `claude plugin validate`).
- m-7. Міжплагінні шляхи `flow-core/references/X.md` (118 згадок) не розв'язуються з іншого плагіна (`${CLAUDE_PLUGIN_ROOT}` — свій корінь). Працює лише тому, що конвенції читає runner і кладе в бриф. Записати це одним реченням у README кожного плагіна («файли flow-core дає runner у теці контексту») і перевірити, що `build_context.py` їх справді копіює.
- m-8. Скрипти, оголошені «ще не створено»: eval-builder `scripts/evals_to_cli.py`, `index_check.py`, `pii_scan.py`; еталонні `apply.py/validate.py/install.sh` (config-as-code). Після M-1 `index_check`/`pii_scan` замінює `flow-autocheck` — прибрати згадки.
- m-9. `ICON_MISSING` у всіх 5 плагінах — потрібне лише для каталогу-директорії; ікону можна задати один раз при першому поданні.
- m-10. `flow-step-runner` open-questions №3: `claude plugin install` не закріплює версію — звірка `скіл@версія` (CONCEPT §3.3) спирається на тег каталогу; описати в README «Установка» (каталог на тегу = версія в наряді).

## 3. Покриття кроків флоу

Усі кандидати з `candidates.md` або реалізовані, або злиті/відкинуті за CONCEPT §4 (розбіжностей зі списком §2 немає).
Без власного скіла лишились (свідомо, CONCEPT §2.6): A-02, A-06, B-08b, B-08d, B-12, C-00, C-08 (людські); A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07, B-08a, B-08c, B-13 (наявні скіли організації); C-05 (шаблон), C-07 (режим `incident` eval-builder).

Прогалини покриття:
- **A-10, A-11** — §2.6 обіцяє `allocation-template.md` і `module-skeleton.md` у `flow-package-build/references/`; файлів немає (m-2).
- **C-00** — людський крок, але від нього залежать майже всі скіли (`tools/odoo/*`, `flow/ODOO_SCHEMA.md`, класи баз, автоматизація `on-complete`); жодного шаблону/чек-листа C-00 у пакеті немає. Рекомендую `flow-core/references/c00-checklist.md` — зведення всіх вимог скілів до C-00.
- **B-07 `client-help-bot`** — відкладено (§4), у README не згадано.
- **B-01** — лише режим «ліди» `segment-selector`; шлях файла лідів не визначений (open-questions).
- **Імена полів/стадій Odoo** (рішення 3) — скіли вживають логічні імена з `odoo-bridge.md` §2 і посилаються на `flow/ODOO_SCHEMA.md` (C-00); вигаданих технічних імен не знайдено. Не зауваження.

## 4. Чернетка розділу README «Відкриті питання до людини»

Вставити в кореневий `README.md` (зібрано з розділів «Відкриті питання» скілів; подробиці — у скілі).

**Дані й безпека (Власник продукту, Юрист)**
1. Чи дозволено читати прод клієнта лічильниками (`search_count`, без вмісту) для D-01 — виняток із «прод заборонено»; підключення `prod-metrics-<код>`, лише центральний агент — `package-usage-metrics`.
2. Тестова база після B-06 містить персональні дані: кроки B-13/B-08a мають іти лише центральному агенту? — `runbook-executor`.
3. `clients/<к>/incidents/` у git проти правила «витяги зі звернень у репо не зберігаються» — `support-desk`.
4. Імена підписантів у `sow.md` чи лише роль + посилання на PDF; механізм підписання додатка — `package-sow-builder`.
5. Клієнт без згоди на AI: що робить флоу; джерело істини «угоду підписано» — `package-fit-gap`.
6. Чи email юрособи з реєстру — `commercial`, де зберігати список розсилки — `segment-selector`, `demand-test-runner`.
7. Ознака знеособленої копії й формат таблиці «Дозволено передавати в AI» — `flow-step-runner`.

**Модель виконання й Odoo (Тімлід / C-00, AI-інженер)**
8. Хто і чим виконує запис у тестові/демо-бази, якщо виконавець кроку не має `odoo_write/execute` (окремий агент чи runner) — `flow-step-runner` (зауваження M-3).
9. Технічні імена полів і стадій, `flow/ODOO_SCHEMA.md`, автоматизація «задача C-01 на зміну стадії» — `flow-orchestrator`, `flow-state-keeper`.
10. Скрипти `tools/odoo/` (чиста база за тегом, тести, імпорт шаблонів, скидання) ще не існують — `ci-pipeline-builder`, `demo-base-builder`, `master-data-template-builder`, `package-release-builder`, `odoo-version-migrator`.
11. Клас і назва «чистої тестової бази пакета» в allow-list — `config-as-code`, `master-data-template-builder`, `package-release-builder`.
12. Формула оренди задачі (`timeout` чи `timeout × 1,5`) — `flow-step-runner`, `flow-orchestrator`.
13. Як закріпити версію плагіна при установці (CLI не має прапорця версії); де репозиторій каталогу плагінів — `flow-step-runner`, `eval-builder`.
14. Хто зливає PR автоекспорту стану; хто записує нову зрілість після кнопки — `flow-state-keeper`, `eval-builder`.
15. Ліміти: `init`/`regress` евалів не вміщаються в $5/45 хв; CI довший за `timeoutMin` — `eval-builder`, `package-upgrade-runner`, `demo-base-builder`.

**Продукт і картки (Власник продукту, Керівник напряму)**
16. Картки з застарілими `skillRef`/`executor`: A-04, A-20, A-15/A-22, C-04/C-07, D-01, D-02 — відповідні скіли.
17. Чи допустимий `done` A-12 без установки «однією командою» у версії 0.1; формат конфіг-пакета — `config-as-code`.
18. Структура `package/pricing.md`, поріг розбіжності з вилкою B-01 — `package-sow-builder`.
19. Метрика «поза пакетом» (чи входить доналаштування) — `package-fit-gap`.
20. Шкала серйозності, строк hypercare 45 днів, календар SLA — `support-desk`.
21. Формат ID запитів у D-02 з B-01/B-08c/D-05; колонка оцінки в беклозі — `backlog-triage`, `product-decision-drafter`.
22. Формулювання «зростання 2020–2025» (фактично 2021→2025); дата знімка odb-catalog у наряді; ваги балу A-05/B-01 — `industry-scoring`, `segment-selector`.
23. Формат версії `<N>.0.X.Y`, гілки й тега `-odoo<N>`; доступ до коду Enterprise — `odoo-version-migrator`, `package-upgrade-runner`.
24. Хто веде `key-models.yaml` для метрик — `package-usage-metrics`.
25. `client-help-bot` (B-07) відкладено: потрібен чи ні — CONCEPT §4.

---

# PACKAGE_REVIEW — раунд 2 (2026-11-09)

Повторна рецензія після виправлень. Лише рекомендації, файли пакета не змінювались.
Вердикт: **major** (blocker — 0, major — 3, minor — 8). З 12 попередніх major закрито 9, частково — 3.

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6 (лишилось попередження про іконки, на установку не впливає) |
| marketplace.json ↔ plugin.json ↔ теки | 5/5; 28 `SKILL.md`, `name` = тека, frontmatter лише `name`/`description` |
| `description` ≤ 1024 | усі 28 (макс. 1003 — backlog-triage); 11 скілів у межах 900–1003 (CONCEPT §3.9 радить ~900) |
| SKILL.md ≤ 250 рядків | усі 28 (макс. 248) |
| Розділ «Відкриті питання» | є в усіх 28, непорожній |
| Посилання `плагін:скіл` | усі існують (пакет, каталог організації, агенти flow-core) |
| Рішення 1 (eval-builder лише під runner) | внесено: шляху 2, `params.manual`, `by: self` немає; `checks/C-04.yaml` і `C-07.yaml` є; команди — рядок «КОМАНДИ:», виконує runner; MANUAL вердикт не змінює, тож щотижневої ескалації немає |
| Рішення 2 (агенти) | одна копія в `plugins/flow-core/agents/`; `flow-step-runner` (р. 31, 38, 98, 118), README плагіна й кореневий README посилаються туди |
| Рішення 3 (імена полів Odoo) | не вигадуються, посилання на C-00 / `flow/ODOO_SCHEMA.md` |
| Рішення 4 (README «Відкриті питання до людини») | розділ є, 25 питань із посиланням на скіл |
| Запис в Odoo під C-06 | закрито: рядки «ODOO:» виконує runner лише для `test-*`, `test-pkg-*`, `demo-*`, `emu-*` (naryad-format.md р. 84) |
| Пошук dispatch-прогону CI | закрито: gates-aggregator, package-release-builder, package-upgrade-runner — за `display_title` |
| Класи баз | `test-pkg-<пакет>` визначено, `ci-<пакет>` скасовано |

## 2. Зауваження

### Major

**M-1. Формула оренди в runner лишилась стара.** `flow-core/skills/flow-step-runner/SKILL.md` р. 46 — `now + limits.timeout_min` (без `lease_factor`), тоді як `odoo-bridge.md` р. 68, `naryad-format.md` р. 19, `sweep-rules.md` р. 11, `dispatcher-config.md` р. 25 — `timeout_min x lease_factor`. Runner — єдиний, хто пише `lease_until`. `flow-step-runner/references/open-questions.md` п. 2 і п. 6 описують уже закриті розбіжності.
Виправити: р. 46 — «за формулою odoo-bridge.md §7» без власної формули; п. 2 і 6 open-questions позначити закритими.

**M-2. D-01 `collect` (читання прод) ставиться за розкладом, хоча рішення людини ще немає.** README (питання 1), `naryad-format.md` р. 84 і `package-usage-metrics/SKILL.md` р. 50 кажуть: до рішення `collect` автоматично не ставити. Але `sweep-rules.md` р. 20, `flow-map.md` р. 88, таблиця `params.mode` D-01 (naryad-format.md р. 72) і `flow-orchestrator/SKILL.md` р. 106, 139, 164 ставлять `collect` щомісяця без умови «рішення зафіксовано». `data-and-connections.md` §3.5 і `conventions.md` р. 72 подають виняток як чинний («Прод клієнта — лише package-usage-metrics»), а §3.6 і README «Правила» — «прод заборонено». Наслідок не витік (runner відмовить), а щомісячна ескалація N нарядів і суперечливе правило даних.
Виправити: в оркестраторі умова «D-01 collect — лише якщо в `flow/decisions.md` є рішення за питанням 1; інакше маркер „метрики не зібрано“ і D-02(а) йде далі»; у §3.5 — «за рішенням людини (README, питання 1), до нього заборонено».

**M-3. Таблиця `params.mode` досі неповна.** У `naryad-format.md` додано A-09, A-12, A-15/A-22, B-06, C-04, C-07, D-03, але немає: D-02 (`mode a|b|c|d`, `phase draft|post-sign`, `trigger_ref`, `markers`), B-11 (`phase 0|1`, `pilot`, `reconcile` — ключ `reconcile` підписано лише B-06), B-04/B-13/B-08a (`runbook-executor`), A-05/B-01 (`segment-selector`: `mode`, `phase`, `size`, `seed`, `regions`, `extra_kved`), A-23 (`demand-test-runner`: `mode results`, `round`, `final`, `start_sha`), A-01, A-04, A-13, A-20/A-21, B-02, A-07/D-04/D-05 (`product-decision-drafter`). Оркестратор не має звідки вивести ці значення.
Виправити: дописати рядки таблиці або явне правило «режими цих кроків — у SKILL.md скіла, оркестратор бере з картки».

### Minor

1. `checks/C-04.yaml`, `C-07.yaml`: `json-schema`, `no-pii-evals`, `source-filled`, `skills-covered` — примітив `manual` (`who: runner`), тобто механічно не виконуються; `eval-builder/SKILL.md` р. 170 називає їх «механічні шість, виконує лише flow-autocheck». Фактично механічні лише `scope-evals-only` та `index-exists`. Додати примітиви в `autocheck.py` (json-схема, строгий `no-pii` для `evals/`) або виправити формулювання.
2. Специфікацій перевірок немає для A-07, D-04, D-05 (і решти кроків): `product-decision-drafter` завершується `INCOMPLETE`/`escalated`. Зафіксовано в README «Відомі обмеження», але лишається робочою перешкодою. У `A-17.yaml` `rejected-route` — перевірити, чи додано D-03 (у `checks.md` р. 38 перелік досі {A-08, A-14}).
3. Застарілі примітки: `ci-pipeline-builder/references/ci-contract.md` р. 27 і `SKILL.md` р. 145–146 (В-7) кажуть, що `c03-lookup.md` шукає за `head_sha` — вже виправлено.
4. `package-release-builder/references/ci-contract.md`: у таблиці «Input ci.yml» є `ref`, якого немає серед inputs контракту (це параметр dispatch API, не input) — підписати окремо.
5. Клас `anon-<к>` (`package-upgrade-runner`, В-9) відсутній у `data-and-connections.md` і в allow-list runner для «ODOO:» — рішення за В-9 винести в README «Відкриті питання».
6. Імена класів: `test-pkg-<id>` (gates-aggregator, config-as-code, master-data-template-builder) проти `test-pkg-<пакет>`; `test-<к>` проти `test-<клієнт>` — уніфікувати.
7. README р. 28: «див. питання 25» — `client-help-bot` це питання 24. `data-and-connections.md` починається з «### 3.3» під H1 (обрізаний фрагмент CONCEPT).
8. 11 `description` довші за ~900 символів (до 1003); іконок плагінів немає.

## 3. Покриття флоу

28 скілів за CONCEPT §2 — усі на місці. Без власного скіла: B-07 (`client-help-bot`, відкладено, CONCEPT р. 235); кроки на скілах організації (A-03, A-06, A-08, A-10, A-11, A-16, B-01, B-05, B-07, B-08) — нових скілів не потребують. Кроки без специфікації автоперевірки — див. minor 2.

---

# PACKAGE_REVIEW — раунд 3 (2026-11-09)

Третя рецензія після виправлень. Лише рекомендації, файли пакета не змінювались.
Вердикт: **major** (blocker — 0, major — 1, minor — 9). З трьох major раунду 2 закрито два повністю (оренда, таблиця `params.mode`), один — частково (D-01 `collect`: розклад виправлено, лишився хвіст у runner і двох довідниках).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6; попередження `ICON_MISSING` у 5 плагінах (на установку не впливає) |
| marketplace.json ↔ plugin.json ↔ теки | 5/5; чотири плагіни мають `"dependencies": ["flow-core"]` |
| 28 `SKILL.md` | `name` = тека; frontmatter лише `name`/`description`; `description` ≤ 1024 (макс. 978); ≤ 250 рядків (макс. 248); `evals/evals.json` валідний у всіх (3–10 кейсів); розділ «Відкриті питання» в усіх |
| Посилання `плагін:скіл` у всіх `.md/.json/.yaml/.py` | усі існують: пакет, каталог організації (`boost`, `odoo19-*`, зокрема `odoo19-sales-prep`), агенти `flow-core:flow-executor`, `flow-core:flow-reviewer` |
| Тригери `description` | один збіг фрази «нова версія» (`master-data-template-builder`, `questionnaire-builder`) — це назва режиму, не тригер; межі з наявними скілами організації («НЕ для …») прописані |
| Рішення 1 (eval-builder лише під runner) | виконано: шляху 2, `params.manual`, `by: self` немає; `checks/C-04.yaml` і `C-07.yaml` є; `json-schema` і `no-pii-evals` тепер механічні (`evals_schema`, `pii_strict` у `autocheck.py`); `weekly: [C-04]` у `dispatcher-config.md`, `sweep-rules.md`, `flow-map.md` узгоджено. Пробний прогін `autocheck.py --mode result` для C-04 у тимчасовому репо: 4 механічні PASS, 6 MANUAL у чек-лист гейта; `--selftest` OK |
| Рішення 2 (агенти) | одна копія в `plugins/flow-core/agents/`; `flow-step-runner/SKILL.md` р. 38 (`${CLAUDE_PLUGIN_ROOT}/agents/…`), README flow-core і кореневий README посилаються туди; інструменти агентів відповідають конвенції (виконавець без Bash і запису в Odoo, рецензент лише читання) |
| Рішення 3 (імена полів Odoo) | не вигадуються; `flow/ODOO_SCHEMA.md` / C-00 |
| Рішення 4 (README «Відкриті питання до людини») | розділ є, 26 питань із посиланням на скіл; бракує кількох — див. minor 2 |
| Оренда (M-1 раунду 2) | закрито: runner р. 46 посилається на `odoo-bridge.md` §7, власної формули немає; open-questions п. 2, 6 позначені закритими |
| `params.mode` (M-3 раунду 2) | закрито: додано D-02, B-11 і правило «решта кроків — режими в SKILL.md скіла, оркестратор бере з картки» |
| D-01 `collect` за розкладом (M-2 раунду 2) | розклад закрито: `sweep-rules.md` р. 20, 22, `flow-map.md` р. 88, `naryad-format.md` р. 72, `flow-orchestrator/SKILL.md` р. 106, 139, 164, `data-and-connections.md` §3.5 — «лише за рішенням людини». Хвіст — major нижче |

## 2. Зауваження

### Major

**M-1. Виняток «прод для D-01» у runner і двох довідниках записано без умови «рішення людини».**
- `flow-core/skills/flow-step-runner/SKILL.md` р. 58: «…з базою класу „прод“ в allow-list (крім D-01 `package-usage-metrics`, центральний агент) → стоп» — умови рішення немає. Runner — останній, хто перевіряє наряд перед викликом до проду; `package-usage-metrics/SKILL.md` р. 50 стверджує, що runner виконує `search_count` «лише за зафіксованим рішенням людини», але в runner цієї перевірки немає. Наряд `collect`, поставлений вручну або до появи умови в оркестраторі, пройде.
- `flow-core/references/data-policy-template.md` р. 30: «прод клієнта — лише `package-usage-metrics` (лічильники)» — подано як чинне правило.
- `data-and-connections.md` §3.6 і `conventions.md` р. 77: «прод заборонено» без посилання на виняток §3.5 (у тому ж файлі §3.5 каже інакше).
- `naryad-format.md` р. 88: в одному реченні «`prod-metrics-*` — відмова» і «`search_count` на `prod-metrics-<код>` — за рішенням» — не сказано, хто перевіряє рішення.

Виправити: runner р. 58 — «крім D-01 `collect`: `executor: central`, alias `prod-metrics-<код>` і запис рішення за питанням 1 README у `flow/decisions.md` на SHA бази; запису немає → стоп „підключення не те“»; так само в `naryad-format.md` р. 88 («перевіряє runner»); `data-policy-template.md` р. 30 — додати «лише після рішення людини (README, питання 1), до нього заборонено»; §3.6 — «прод заборонено (єдиний можливий виняток — §3.5)».

### Minor

1. C-04 `weekly` до першого `init`: `index-exists` і `json-schema` дають FAIL (перевірено прогоном: «Немає жодного evals/**/evals.json»), тобто до `init` щотижневий наряд повертається. `init` ставить лише AI-інженер і він не вміщається в ліміти (README, питання 13). Додати в `sweep-rules.md` умову «C-04 weekly — лише якщо на base є `evals/INDEX.md`».
2. README «Відкриті питання до людини» — бракує питань, адресованих людям у скілах: список сумісних ліцензій для вендорингу — Юрист (`config-as-code`); пункт договору про агрегати з проду — Юрист (`package-usage-metrics` В-6; доповнити питання 1); формулювання «на Odoo 19» і схожість з Odoo Enterprise у матеріалах для лідів — Юрист (`prototype-builder` В-5); failureMode картки B-11 проти режиму «звірка» (`package-upgrade-runner` В-7, `runbook-executor`); хто моніторить `FLOW_STOP` і тип агента (`flow-step-runner` №4, №13); чи беруть D-01/B-10 непідтверджені PM прапорці (`flow-state-keeper`); річний запуск A-01 у карті флоу (`industry-scoring`); строк зберігання записів Fathom і файл акта звірки на Drive (`package-fit-gap`, `client-data-migrator`).
3. `eval-builder/SKILL.md` р. 173: `source-filled`, `skills-covered`, `incident-case` — `manual`; у README «Евали (C-04)» написано «Механічні перевірки — C-04.yaml» без уточнення, що механічних чотири з десяти. Уточнити одним реченням.
4. `flow-step-runner/SKILL.md` р. 174 досі згадує «формула оренди» серед відкритих питань (закрито). `open-questions.md` п. 7: доповнення звіту runner (`attempts_in_run`, `models_used`, `routing`, `lease` …) ще не внесені в `report-format.md`.
5. CONCEPT §3.10 і §2.6 (р. 92, 219) обіцяють `flow-package-build/references/allocation-template.md` і `module-skeleton.md` (опора покриття A-10/A-11), `flow-research/references/demand-thresholds.md` — файлів немає. Створити або виправити CONCEPT.
6. Немає зведеного чек-листа C-00 (`tools/odoo/*`, `flow/ODOO_SCHEMA.md`, класи баз, автоматизація стадій, `FLOW_AGENT_KIND`) — вимоги розкидані по скілах; рекомендую `flow-core/references/c00-checklist.md`.
7. Специфікацій `flow-autocheck` немає для більшості кроків (є 11: A-07, A-09, A-10, A-14, A-17, A-18, C-04, C-05, C-07, D-04, D-05) — решта завершуються `escalated`; у README зафіксовано, але це робоча перешкода першого прогону.
8. Написання класів: `anon-<к>` (4) проти `anon-<клієнт>` (1); `conventions.md` р. 55–80 дублює `data-and-connections.md` дослівно — лишити одне джерело.
9. 12 `description` довші за ~900 символів (CONCEPT §3.9), до 978; іконок плагінів немає (потрібні лише для подання в каталог).

## 3. Покриття флоу

28 скілів за CONCEPT §2 — усі на місці; розбіжностей з `candidates.md` (злито/відкинуто за §4) немає.
Без власного скіла: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; кроки на скілах організації A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-08a, B-08c, B-13; C-05 — шаблон `data-policy-template.md`; C-07 — режим `incident` у `eval-builder`; B-07 (`client-help-bot`) — відкладено (README, питання 24).

---

# PACKAGE_REVIEW — раунд 4 (2026-11-09)

Четверта рецензія після виправлень. Лише рекомендації, файли пакета не змінювались.
Вердикт: **major** (blocker — 0, major — 1, minor — 8). Major раунду 3 (умова «рішення людини» для проду D-01) закрито в усіх п'яти місцях; під час перевірки шляху D-01 `collect` наскрізь знайдено нову суперечність у тому самому місці (нижче).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6; лише попередження `ICON_MISSING` у 5 плагінах |
| marketplace.json ↔ plugin.json ↔ теки | 5/5; 28 `SKILL.md` на місці; 4 плагіни мають `"dependencies": ["flow-core"]` |
| 28 `SKILL.md` (скрипт) | `name` = тека; frontmatter лише `name`/`description`; `description` 672–978 (≤ 1024); рядків 140–248 (≤ 250); `evals/evals.json` валідний у всіх (3–10 кейсів); «Наряд і звіт» і «Відкриті питання» в усіх; «НЕ використовуй» у всіх |
| Посилання `плагін:скіл` (усі `.md/.json/.yaml/.py`) | усі існують (пакет, каталог організації, агенти `flow-core:flow-executor|flow-reviewer`) |
| Посилання на файли `references/…`, `scripts/…` | неіснуючі згадано лише як «немає / не створено» (`evals_to_cli.py`, `demand-thresholds.md`, `module-skeleton.md`, спільний `changelog-template.md`) — зламаних немає |
| Тригери `description` | збіги фраз лише як назви режиму/межі («нова версія», «у продукт чи в кастом», «будуємо пакет?») — конфліктів немає; сусідні скіли організації названі в «НЕ для…» |
| Рішення 1 (eval-builder лише під runner) | виконано: «шляху 2», `params.manual`, `by: self` немає; `checks/C-04.yaml` (4 механічні + 6 `manual`) і `C-07.yaml` є; `autocheck.py --selftest` OK; `weekly: [C-04]` лише за наявності `evals/INDEX.md` — узгоджено в `dispatcher-config.md`, `sweep-rules.md`, `flow-map.md`, README |
| Рішення 2 (агенти) | одна копія `plugins/flow-core/agents/`; runner р. 31, 38 (`${CLAUDE_PLUGIN_ROOT}/agents/…`), `flow-core/README.md` р. 21–22 і кореневий README посилаються туди |
| Рішення 3 (імена полів Odoo) | не вигадуються; `flow/ODOO_SCHEMA.md` / C-00; зведення — `c00-checklist.md` |
| Рішення 4 (README «Відкриті питання до людини») | розділ є, 34 питання з посиланням на скіл; бракує кількох — minor 2 |
| Major раунду 3 | закрито: runner р. 58 (умова `executor: central` + alias + запис рішення на SHA бази, інакше стоп), `naryad-format.md` р. 88 («перевіряє runner»), `data-policy-template.md` р. 30, `data-and-connections.md` §3.5–3.6; `conventions.md` §3.3–3.6 тепер лише посилається на `data-and-connections.md` (дубль прибрано) |
| Minor раунду 3 | закрито 1, 2 (частково), 3, 4, 5 (CONCEPT виправлено), 6, 8; лишаються 7 і 9 |

## 2. Зауваження

### Major

**M-1. Шлях D-01 `collect` суперечить сам собі: хто і чим виконує `search_count` на `prod-metrics-<код>`.**
- `package-usage-metrics/SKILL.md` р. 50: виконавець повертає `odoo_execute search_count` рядками «ODOO: …», runner виконує їх на `prod-metrics-<код>`.
- `flow-step-runner/SKILL.md` р. 99 і `references/executor-brief.md` р. 5: runner виконує рядки «ODOO:» **лише** для `test-*|test-pkg-*|demo-*|emu-*`, «решту відхиляє»; `naryad-format.md` р. 88: «`prod-metrics-*` — відмова, `escalated`», і одразу наступним реченням — «читання `search_count` на `prod-metrics` — за рішенням». Тобто після рішення людини крок або завжди `escalated`, або агент сам обирає, яке з двох правил чинне, — на єдиному шляху до проду.
- У `flow-executor` (`agents/flow-executor.md`, `tools:`) є `odoo_search_read`; для `collect` alias проду є в `odoo_connections` наряду → виконавець технічно може прочитати вміст записів проду. Заборона (`package-usage-metrics` р. 56, перевірка M-02 «за журналом викликів») — лише текстом і постфактум.
- Умова runner «запис рішення за питанням 1 README у `flow/decisions.md`» не має стабільної ознаки: номер питання в README маркетплейса зміниться, сам README не встановлюється разом із плагіном, формат запису рішення не задано. Евала на цю перевірку в `flow-step-runner/evals` і `flow-orchestrator/evals` немає.

Виправити (до того, як людина відповість на питання 1; зараз прод закрито, правило даних не порушено):
1. Один виняток у трьох місцях (runner р. 99, `executor-brief.md`, `naryad-format.md` р. 88): «для `prod-metrics-<код>` runner виконує рядок „ODOO:" лише якщо `step: D-01`, `params.mode: collect`, `executor: central`, є рішення, `tool: odoo_execute` і `method: search_count`; будь-що інше — відмова, стоп, інцидент C-05».
2. Для `collect` не передавати alias проду виконавцю: у брифі лише `flow`; усі виклики до проду робить runner за білим списком методів.
3. Стабільний ідентифікатор рішення (наприклад ключ `prod_metrics_allowed` у `params-registry.md` / код запису в журналі рішень) замість «питання 1 README»; однаково в runner, оркестраторі, `sweep-rules.md`, `flow-map.md`, `data-and-connections.md`, `data-policy-template.md`, `package-usage-metrics`.
4. Евали: runner — наряд `collect` без запису рішення → стоп; з рішенням, але метод не `search_count` → відмова.

### Minor

1. README, питання 1: дві дужки поспіль з одним змістом («runner теж перевіряє…» і «оркестратор перевіряє…») — звести в одне речення.
2. README «Відкриті питання до людини» — не внесено: позначка профілю «без AI на даних» (№47) у `answers.yaml`/`pricing.md` — Керівник напряму (`package-sow-builder`); еталонні скрипти `apply.py`/`validate.py`/`install.sh` і доставка `package/addons` у тестову базу — AI-інженер (`config-as-code`; доповнити питання 10 або 16); Chromium для Playwright в агента і відео в git/LFS — AI-інженер, Тімлід (`prototype-builder` В-1, В-2); харнес кейсів `requires: step-run` — AI-інженер (`eval-builder`); хто вписує рядок `Рішення:` після кнопки (`product-decision-drafter` В-1; близьке до питання 12).
3. `product-decision-drafter/SKILL.md`, В-5 застаріло: `checks/A-07.yaml`, `D-04.yaml`, `D-05.yaml` уже є, `D-03` у `A-17.yaml` є, а текст каже «до того A-07/D-04/D-05 завершуються `escalated`». Позначити закритим.
4. `eval-builder/SKILL.md`, «Наряд і звіт»: «PR і звіт в Odoo пише той, хто веде крок» — написати прямо «`flow-core:flow-step-runner`» (ручного шляху немає). `open-questions.md`: блок `evals:` у `report-format.md` досі не внесено (носій — `evals/INDEX.md`).
5. `eval-builder`: скрипта `scripts/evals_to_cli.py` немає, формат CLI генерує runner за `run-eval.md` — ручна ділянка в щотижневому кроці; створити скрипт або зафіксувати як обмеження в README (зараз лише питання 14).
6. Специфікацій `flow-autocheck` — 11 з ~45 кроків; решта завершується `escalated` (у README зазначено). Перед першим прогоном додати yaml хоча б для кроків із власними скриптами перевірки (`check_sow.py`, `check_fit_gap.py`, `check_config_log.py`, `check_migration.py`, `check_ci.py`, `check_support.py`).
7. Міжплагінні посилання `flow-core/references/X.md` працюють лише через `build_context.py`; при запуску скіла поза runner файл не знайдеться. У README зазначено; додати рядок у «Наряд і звіт» шаблону скіла: «поза runner не запускати».
8. 12 `description` довші за 900 символів (CONCEPT §3.9); іконок плагінів немає (потрібні лише для каталогу).

## 3. Покриття флоу

28 скілів за CONCEPT §2 — усі на місці; кандидати з `candidates.md` або реалізовані, або злиті/відкинуті за CONCEPT §4 (розбіжностей немає).
Без власного скіла: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; на скілах організації — A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07 (`user-training-builder`), B-08a, B-08c, B-13; C-05 — шаблон `data-policy-template.md`; C-07 — режим `incident` у `eval-builder`; `client-help-bot` (B-07) відкладено (README, питання 24). Не вирішено, хто виробляє знеособлену копію (`anon-<клієнт>`, питання 26) — B-11 версія 2 не запускається.

---

# PACKAGE_REVIEW — підсумкова рецензія після дозбирання, раунд 1 (2026-11-10)

Лише рекомендації, файли пакета не змінювались. Прийняті рішення (D-01 без проду, eval-builder лише під runner, агенти у `flow-core/agents/`, імена полів Odoo — C-00) не переглядались; відкриті питання README не вирішувались.
Вердикт: **major** (blocker — 0, major — 2, minor — 6).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6, без попереджень (іконки є) |
| marketplace.json ↔ plugin.json ↔ теки | 5/5 плагінів, 28 `SKILL.md`; версія 0.1.0 всюди; 4 плагіни з `dependencies: ["flow-core"]`; README плагінів перелічують свої скіли повністю |
| 28 `SKILL.md` | `name` = тека; frontmatter лише `name`/`description`; `description` 672–887 (усі ≤ 900); рядків 140–248; `evals.json` валідний (3–10 кейсів); «Наряд і звіт», «Відкриті питання» — в усіх |
| Посилання `плагін:скіл` у всіх `.md/.json/.yaml/.py` | усі існують (пакет, каталог організації, агенти `flow-core:flow-executor|flow-reviewer`); назв відкинутих кандидатів (`odoo-flow-bridge`, `pilot-review` тощо) у плагінах немає |
| `checks/*.yaml` (34) | усі парсяться, `step` = ім'я файлу; усі 14 згаданих скриптів скілів існують (`up.sh`, `*-migrate.py` — артефакти репо пакета, не скрипти скілів) |
| Самотести | `autocheck.py --selftest` OK; `evals_to_cli.py --self-test` OK |
| Шаблони `tools-odoo` | усі 6 скриптів викликають `guard_db` до будь-якої дії; прогін: `prod`, `client-acme`, `anon-k1`, порожнє, `test-`, `test-x;id` — відмова `FLOW_STOP`; `test-x`, `test-pkg-1`, `demo-1`, `emu-a` — дозволено |
| Прод клієнта | залишків `prod-metrics`/`prod_alias` як дозволеного шляху немає (лише заборона в `package-usage-metrics`, `flow-state.md` р. 30 і негативні евали) |
| Конвенції (наряд, звіт, `connection_id`, класи баз, `skill_ref` з точним semver) | узгоджені; `demand-test-runner` без `connection_id` — коректно (odoo-mcp йому заборонено) |
| Тригери `description` | усі прив'язані до коду кроку; збіг фраз один («нова версія» в `questionnaire-builder` і `master-data-template-builder` — різні кроки); конфліктів немає |

## 2. Зауваження

### Major

**M-1. Жодна з 54 карток не має скіла пакета в `skillRef`, а оркестратор бере `skill_ref` саме з картки.**
`flow-orchestrator/SKILL.md` р. 100–103: `skill_ref` наряду — з картки; runner виконує перший елемент; `demand-test-runner` (Крок 0.1) відхиляє наряд без себе в `skill_ref`. У картках `…/scratchpad/apply/final/*.json` `skillRef` — лише скіли організації або порожньо (A-09, A-22, D-01 та ін.), `gap: true` у 34 картках. README, питання 15, називає лише A-04, A-20, A-15/A-22, C-04/C-07, D-02. Таблиця «крок → скіл» є тільки в `_work/CONCEPT.md` §2, яка з плагіном не встановлюється.
Виправити: (1) у `flow-core/references/` (окремий файл або колонка в `flow-map.md`) — таблиця «код кроку → `skill_ref` (перший — скіл, що веде крок) → `params.mode`» для всіх ~33 кроків пакета, зокрема кроків із двома скілами (A-23: `demand-test-runner` перший, `segment-selector` — режим списку розсилки; B-11: `package-upgrade-runner` перший, `runbook-executor` — «звірка»; B-13 → `runbook-executor`); (2) пункт у `c00-checklist.md`: «оновити `skills`, `skillRef`, `gap`, `raciR` карток за цією таблицею до першої диспетчеризації»; (3) питання 15 README розширити на всі картки.

**M-2. Перевірки-скрипти скілів (`manual`, `who: runner`) ніхто не виконує; 19 кроків дають autocheck `PASS` без жодної механічної перевірки, окрім загальних C-06.**
Усі перевірки `manual` у yaml: A-04, A-05, A-07, A-20–A-23, B-01–B-04, B-06, B-09–B-11, B-13, D-01, D-03, D-04. У `flow-step-runner/SKILL.md` слова `manual`/`who` не зустрічаються — інструкції запускати ці команди немає; `MANUAL` вердикт не змінює. Сюди входять і перевірки даних клієнта (`check_pii.py` для B-06, `sow-pii`); загальний `no-pii` скрипта виконується завжди, тож правило даних не порушено, але перевірка слабша за задуману. README це визнає («Відомі обмеження»), проте виправлення немає.
Виправити (одне з двох, власник — AI-інженер): примітив `run_script` в `autocheck.py` (шлях відносно кореня плагіна, JSON у `checks[]`, FAIL скрипта = FAIL кроку) — або крок у `flow-step-runner/SKILL.md`: «для кожного `manual` з `who: runner` виконати команду, результат вставити в `checks[]`; не виконано → `ERROR`, не `PASS`». Разом із цим вирішити, як runner знаходить корінь чужого плагіна (`<корінь плагіна flow-…>` у командах). До виправлення `PASS` цих кроків не вважати підставою для зрілості 3.

### Minor

1. README «Відомі обмеження» містить застаріле: «частина `description` довша за 900» (зараз максимум 887) і «іконки — додати» (є в усіх 5 плагінах, validate без попереджень). Прибрати.
2. `flow-autocheck/SKILL.md` р. 64 називає 6 специфікацій, `references/checks.md` р. 5 — 11; фактично 34. Оновити перелік або замінити на «див. `references/checks/`».
3. У git 7 файлів `__pycache__/*.pyc` (`flow-state-keeper/scripts`, `master-data-template-builder/scripts`, 5 у фікстурах `demo-base-builder`); кореневого `.gitignore` немає. Видалити з індексу, додати `.gitignore`.
4. `guard_db` перевіряє лише ім'я бази, не сервер (це записано в `_common.sh`). У `c00-checklist.md` додати явний пункт: «`PGHOST`/`ODOO_CONF` скриптів `tools/odoo/` — лише непродовий сервер; C-00 додає перевірку хоста». Шаблон `test-pkg-?*` поглинається `test-?*` — зайвий, але нешкідливий.
5. Версія плагіна записана двічі (`marketplace.json` і `plugin.json`). Джерело для `skill_ref` — `plugin.json` (оркестратор р. 100); у README додати рядок «при релізі міняти обидва».
6. Наживо не запускалось (за протоколами `_work/static-run/*.md`): `claude plugin eval` на згенерованих кейсах, odoo-mcp, GitHub, Gmail, скрипти `tools-odoo` на реальному Odoo 19. Перший живий прогін — окремий крок перед поданням у каталог.

## 3. Покриття флоу

28 скілів за CONCEPT §2 на місці; кандидати з `candidates.md` або реалізовані, або злиті/відкинуті за CONCEPT §4 — розбіжностей немає.
Без власного скіла пакета: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; на скілах організації — A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07 (`user-training-builder`), B-08a, B-08c; C-05 — шаблон `data-policy-template.md` (перевірка форми — `flow-autocheck`, режим `form`); C-07 — режим `incident` у `eval-builder`. Відкладено `client-help-bot` (B-07, питання 24). Немає кроку-виробника знеособленої копії `anon-<клієнт>` (питання 26) — B-11 версія 2 не запускається; клас `anon-*` шаблони `tools-odoo` теж відхиляють, що узгоджено.

# PACKAGE_REVIEW — підсумкова рецензія після дозбирання, раунд 2 (2026-11-10)

Перевірка після виправлень M-1 і M-2 попереднього раунду. Лише рекомендації, файли пакета не змінювались. Прийняті рішення (D-01 — вивантаження людини, `eval-builder` лише під runner, агенти у `flow-core/agents/`, імена полів Odoo — C-00) не переглядались; відкриті питання README не вирішувались.
Вердикт: **major** (blocker — 0, major — 2, minor — 5).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6, без попереджень |
| marketplace.json ↔ plugin.json ↔ теки | 5/5 плагінів, 28 `SKILL.md`, версія 0.1.0, `dependencies: ["flow-core"]` у чотирьох; усі 28 скілів названі в кореневому README, README плагінів і CONCEPT |
| 28 `SKILL.md` | `name` = тека; frontmatter лише `name`/`description`; `description` 672–887 (усі ≤ 900); 140–248 рядків; `evals/evals.json` є в усіх |
| Посилання `плагін:скіл` у `.md/.json/.yaml/.py/.sh` | усі існують (пакет, каталог організації, агенти `flow-core:flow-executor|flow-reviewer`) |
| `checks/*.yaml` (34) | парсяться; усі 15 згаданих скриптів скілів існують і лежать у плагіні ведучого скіла кроку (`up.sh`, `*-migrate.py` — артефакти репо пакета) |
| Самотести | `autocheck.py --selftest` OK; `evals_to_cli.py --self-test` OK |
| Шаблони `tools-odoo` | усі 6 скриптів викликають `guard_db` до будь-якої дії з базою; `prod`, `client-acme`, `anon-k1`, `production_test`, порожнє, `test-`, `test-x;id` — відмова `FLOW_STOP`; `test-x`, `demo-1`, `emu-a` — дозволено |
| Прод клієнта | дозволених шляхів до `prod-*` немає (лише заборони й негативні евали) |
| Конвенції (наряд, звіт, `connection_id`, класи баз, `скіл@версія`) | є в усіх 28; `demand-test-runner` без `connection_id` — коректно (odoo-mcp йому заборонено) |
| Тригери `description` | кожен скіл прив'язаний до свого коду кроку й має блок «НЕ»; чужі коди — лише як входи/межі; конфліктів немає |
| Попередній M-1 (картки без скілів пакета) | закрито по суті: `flow-core/references/step-skill-map.md` (33 кроки), посилання з оркестратора (Крок 3), пункт у `c00-checklist.md`, питання 15 README на всі 54 картки. Дефекти самої таблиці — M-1 нижче |
| Попередній M-2 (скрипти `manual`/`who: runner`) | закрито по суті: `flow-step-runner`, Крок 9 (ж) — runner виконує команди, FAIL скрипта = FAIL кроку, не виконано = `ERROR`; yaml і README оновлено. Залишок — M-2 нижче |
| Попередні minor 1–5 | виправлено (README без застарілого, перелік специфікацій = каталог, `.gitignore`, пункт про `PGHOST` у C-00, розділ «Релізи») |

## 2. Зауваження

### Major

**M-1. `step-skill-map.md` у чотирьох місцях суперечить скілам і runner'у.**
(а) Перший абзац сам собі суперечить: «поки C-00 не оновив картки, джерело — ця таблиця» і одразу «розбіжність картки й таблиці → `skipped_precondition`». Зараз розходяться всі 54 картки; оркестратор (Крок 3) каже «діє таблиця». Лишити одне правило: до позначки C-00 «картки оновлено» — таблиця без порівняння; після — розбіжність → `skipped_precondition`.
(б) Рядки з двома скілами (A-23: `demand-test-runner, segment-selector`; B-11: `package-upgrade-runner, runbook-executor`): runner на Кроці 9 (д) запускає `skill_ref[1:]` як скіли-гейти, а це не гейти. Окремий наряд A-23 для `segment-selector` (`список`/`адреси`) за таблицею отримає першим `demand-test-runner`, який на такому `mode` зупиняється (його Крок 0.2). Те саме для звірки B-11 (`runbook-executor`) і додатка SOW на кроці B-11 (`package-sow-builder`, `addendum`). Виправити: окремі рядки «A-23 / список|адреси → segment-selector», «B-11 / reconcile → runbook-executor», «B-11 / addendum → package-sow-builder», у кожному рядку один ведучий; у `skill_ref[1:]` лишати тільки гейти.
(в) Рядок B-06 (`phase: 0|1`, `pilot`, `reconcile`) скопійовано з B-11; так само в `naryad-format.md` р. 64. `client-data-migrator` (Крок 1) читає `params.mode == reconcile` і `returned_from`, ключів `phase`/`pilot` не має; `B-06.yaml` — `--mode main|reconcile|return`. Замінити в обох файлах на `main|reconcile|return` (скіл сам просить про це власника flow-core).
(г) B-08a: ведучий — `runbook-executor` («звірка»), але `convergence.md` на цьому кроці веде `odoo19-mvp-build:track-convergence` (`runbook-executor/SKILL.md` р. 37), якого в рядку немає; останній абзац таблиці B-08a не згадує. Вказати, що B-08a — два наряди (звірка → `track-convergence`), або додати другий скіл з приміткою.

**M-2. Runner не визначає, що робити з вердиктом `INCOMPLETE` і статусом `ERROR`.**
`flow-step-runner/SKILL.md`, Крок 10 описує лише `FAIL` (повтор); слів `INCOMPLETE` у файлі немає, `ERROR` — лише в новому (ж). Через це не визначено: (1) чи «не виконано → ERROR» з (ж) справді блокує `done`; (2) чим завершується крок без специфікації — `ERROR spec-missing` → `INCOMPLETE` дають 16 кроків за README плюс B-08a, який за таблицею веде скіл пакета, а `B-08a.yaml` немає (README р. 38 каже, що специфікації є для всіх кроків зі скілом пакета). Виправити: рядок у Кроці 10 — «`INCOMPLETE`: `spec-missing` → не блокує, у звіт і чек-лист гейта; будь-який інший `ERROR` (зокрема з (ж)) → без `done`, один повтор перевірки, далі ескалація AI-інженеру, спроба виконавця не рахується»; додати `B-08a.yaml` (скрипт `check_config_log.py`, режим звірки) або прибрати B-08a з твердження README.

### Minor

1. Крок 9 (ж) розпізнає команду за текстом (`python3 -I …`/`node …`) у полі `args.text`, де після команди йде проза, є необов'язкові частини (`[--base --head]`, «перед цим --self-test») і заповнювачі без джерела (`<галузь>`, `<complexity.md>`, період). Runner сказано лише про `<к>` і `<тег>`. Надійніше — окреме поле `args.cmd` (масив аргументів, заповнювачі з назвами ключів наряду) і `text` тільки для людини. У (ж) написано `who: runner`, у yaml це `args.who` — уточнити.
2. Вісім кроків, де всі перевірки `manual`, не мають жодної команди для (ж): A-05, A-07, A-22, B-01, B-11, D-01, D-03, D-04. Для них autocheck і далі дає `PASS` лише за загальними перевірками C-06. README це обмежує («не підстава для зрілості 3»); для B-11 і D-01 (дані клієнта) варто додати хоча б `pii_strict` і `exists` на їхні фіксовані шляхи.
3. `flow-step-run.md` р. 24 називає A-07, A-17, D-05 людськими кроками «без `skill_ref`», а таблиця дає їм `product-decision-drafter`. Це узгоджується лише через «окремий наряд AI-кроку»; додати в таблицю примітку «AI-частина; людська задача — без `skill_ref`».
4. На диску лишились 7 файлів `*.pyc` (з індексу git вони прибрані, `.gitignore` є, але ще не закомічено разом зі `step-skill-map.md`). Видалити файли й закомітити.
5. Наживо не запускалось (за `_work/static-run/*.md`): `claude plugin eval`, odoo-mcp, GitHub, Gmail, `tools-odoo` на Odoo 19. Перший живий прогін — перед поданням у каталог (README це вже каже).

## 3. Покриття флоу

Без змін проти попереднього раунду: 28 скілів за CONCEPT §2 на місці, кандидати з `candidates.md` реалізовані або злиті/відкинуті за CONCEPT §4.
Без власного скіла пакета: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; на скілах організації — A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07, B-08c (і друга половина B-08a); C-05 — шаблон `data-policy-template.md` + `C-05.yaml`; C-07 — режим `incident` у `eval-builder`. Відкладено `client-help-bot` (B-07, питання 24). Виробника знеособленої копії `anon-<клієнт>` немає (питання 26).

# PACKAGE_REVIEW — підсумкова рецензія після дозбирання, раунд 3 (2026-11-10)

Перевірка після коміту `65373ab` (виправлення M-1 і M-2 раунду 2). Лише рекомендації, файли пакета не змінювались. Прийняті рішення (D-01, `eval-builder` лише під runner, агенти у `flow-core/agents/`, імена полів Odoo — C-00) не переглядались; відкриті питання README не вирішувались.
Вердикт: **major** (blocker — 0, major — 1, minor — 4).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6 |
| marketplace.json ↔ plugin.json ↔ теки | 5/5 плагінів, 28 `SKILL.md`, 28 `evals/evals.json`, робоче дерево чисте, `*.pyc` на диску — 0 |
| 28 `SKILL.md` | `name` = тека; frontmatter лише `name`/`description`; `description` після розбору YAML — максимум 887 (усі ≤ 900) |
| Посилання `плагін:скіл` | усі існують (пакет, агенти `flow-core`, `boost`, `odoo19-mvp-build`, `odoo19-implementation`, `odoo19-tr-authoring`, `odoo19-sales-prep`) |
| `checks/*.yaml` (35, додано `B-08a.yaml`) | усі парсяться; усі названі скрипти скілів існують (`up.sh`, `*-migrate.py` — артефакти репо пакета, не скіла) |
| Самотести | `autocheck.py --selftest` OK; `evals_to_cli.py --self-test` OK |
| Шаблони `tools-odoo` | 6 скриптів викликають `guard_db` до дії з базою; `prod`, `prod-acme`, `PROD-x`, `client-acme`, `anon-k1`, `production_test`, порожнє, `test-`, `test-x;id` — `FLOW_STOP`; `test-x`, `demo-1`, `emu-a`, `test-pkg-a` — дозволено |
| Попередній M-1 (а) | закрито: одне правило «до позначки C-00 — таблиця без порівняння», узгоджено з оркестратором р. 100 |
| Попередній M-1 (в) | закрито: B-06 — `main\|reconcile\|return` у таблиці й `naryad-format.md` |
| Попередній M-1 (б), (г) | закрито в таблиці (окремі рядки «крок / режим», один ведучий; B-08a — два наряди). Наслідки для оркестратора, yaml і `package-upgrade-runner` — M-1 нижче |
| Попередній M-2 | закрито: runner, Крок 10 — `spec-missing` не блокує `done`, інший `ERROR`/`INCOMPLETE` — без `done`, один повтор, ескалація AI-інженеру; `B-08a.yaml` є; README р. 38 — 35 файлів |

## 2. Зауваження

### Major

**M-1. Рядки «крок / режим» таблиці `step-skill-map.md` не доведені до оркестратора, yaml-специфікацій і `package-upgrade-runner`.**
(а) Специфікація автоперевірки одна на код кроку, умови за режимом у `when` немає (`checks.md` р. 10). Наряд другого ведучого отримує перевірки першого: A-23 `список|адреси` (`segment-selector`) — чотири команди `demand_tool.py … landing.md emails.md` з `A-23.yaml`; цих файлів у наряді списку немає, скрипт падає (`FileNotFoundError`), за Кроком 9 (ж) це FAIL кроку. Те саме: B-08a «збіжність» (`track-convergence`) і B-11 `reconcile`/`addendum` проти `B-08a.yaml`/`B-11.yaml`. Крім того, (ж) бере корінь плагіна зі `skill_ref[0]` — для наряду `odoo19-mvp-build:track-convergence` це не `flow-client-delivery`, скрипт `check_config_log.py` не знайдеться → `ERROR` → без `done`.
(б) B-11: таблиця дає окремі наряди `reconcile` → `runbook-executor` і `addendum` → `package-sow-builder`, а `package-upgrade-runner` викликає обидва скіли «у цьому ж запуску й гілці» (р. 92, 141) і вмикає звірку ключем `params.reconcile: true`, не `mode: reconcile`. Два механізми для однієї дії; при виклику в запуску версія викликаного скіла не зафіксована в `skill_ref`.
(в) Ні `flow-orchestrator`, ні `flow-map.md` не кажуть, коли створювати другий наряд того самого кроку (A-23 `список` перед `prep`; B-08a «збіжність» після «звірки»; B-11). `segment-selector` р. 53 досі каже «до оновлення flow-core створює Тімлід вручну».
Виправити: 1) у `checks.md` додати умову `when: mode:<значення>` (або файли `A-23.список.yaml`, `B-08a.збіжність.yaml`, `B-11.reconcile.yaml`, `B-11.addendum.yaml`) і розмітити записи `A-23.yaml`, `B-08a.yaml`, `B-11.yaml`; у (ж) брати плагін з тексту команди, не зі `skill_ref[0]`; 2) для B-11 лишити один механізм: або прибрати рядки `B-11 / reconcile|addendum` з таблиці й записати «викликає ведучий у своєму запуску; версії викликаних скілів — у `skill_ref[1:]` з позначкою `called`», або переписати Кроки 2 і 8 `package-upgrade-runner` на `waiting_human`/окремий наряд і замінити `params.reconcile` на `mode: reconcile`; 3) у `flow-map.md` додати рядки «A-23 список done → A-23 prep», «B-08a звірка done → B-08a збіжність» і послатися на них з оркестратора (Крок 3).

### Minor

1. `guard_db` пропускає `test-prod` (і будь-яке `test-*prod*`): відповідає класу `test-*`, але назва двозначна. Додати відмову для імен, що містять `prod` після префікса, або пункт у `c00-checklist.md` «тестові бази не називати з `prod`».
2. Крок 9 (ж) і далі розпізнає команду з прози `args.text` (необов'язкові частини, заповнювачі `<complexity.md>`, `main|addendum`). Надійніше окреме поле `args.cmd` (масив) — повтор minor 1 раунду 2.
3. Вісім кроків, де всі перевірки `manual` без команди (A-05, A-07, A-22, B-01, B-11, D-01, D-03, D-04): autocheck дає `PASS` лише за загальними перевірками C-06. Для B-11 і D-01 додати `pii_strict` і `exists` — повтор minor 2 раунду 2.
4. Наживо не запускалось (за `_work/static-run/*.md`): `claude plugin eval`, odoo-mcp, GitHub, Gmail, `tools-odoo` на Odoo 19. Перший живий прогін — перед поданням у каталог.

## 3. Покриття флоу

Без змін: 28 скілів за CONCEPT §2 на місці, кандидати з `candidates.md` реалізовані або злиті/відкинуті за CONCEPT §4.
Без власного скіла пакета: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; на скілах організації — A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07, B-08c і другий наряд B-08a; C-05 — шаблон `data-policy-template.md` + `C-05.yaml`; C-07 — режим `incident` у `eval-builder`. Відкладено `client-help-bot` (B-07, питання 24). Виробника знеособленої копії `anon-<клієнт>` немає (питання 26).

# PACKAGE_REVIEW — рецензія після внесення рішень людини (q01–q44), перевірка №3 (2026-11-10)

Стан: робоче дерево поверх коміту `7e0f831` (44 змінені файли, 6 невідстежуваних шляхів). Лише рекомендації, файли пакета не змінювались. Рішення людини (`DECISIONS_2026-11-10.md`) не переглядались; технічні імена полів Odoo — C-00.
Вердикт: **major** (blocker — 0, major — 2, minor — 7).

## 1. Що перевірено

| Перевірка | Результат |
|---|---|
| `claude plugin validate .` і `plugins/<p>` × 5 | PASS × 6 |
| marketplace.json ↔ plugin.json ↔ теки | 5/5 плагінів, версії 0.1.0 збігаються, `dependencies: [flow-core]` у чотирьох; 29 `SKILL.md`, 29 `evals/evals.json` (JSON валідний); README каже 29 — збігається |
| 29 `SKILL.md` | `name` = тека; frontmatter лише `name`/`description`; `description` ≤ 897 символів; дублів тригерних фраз між скілами немає |
| Посилання `плагін:скіл` (73 різні) | усі існують: пакет, 7 агентів `flow-core`, `boost`, `odoo19-mvp-build`, `odoo19-implementation`, `odoo19-tr-authoring`, `odoo19-sales-prep`, `odoo19-discovery-initiation`, `odoo19-discovery-closeout` |
| `checks/*.yaml` | 36 файлів (додано `B-07.yaml`), усі парсяться; `autocheck.py --selftest` OK; `evals_to_cli.py --self-test` OK |
| q01 | узгоджено: виняток лише B-13/B-08a на `test-<клієнт>` у `naryad-format.md`, `conventions.md`, `data-and-connections.md`, оркестраторі, `sweep-rules.md`, runner, `runbook-executor`; `client-data-migrator`, `package-fit-gap`, `package-upgrade-runner`, `support-desk`, `client-help-bot` вимагають `central`; є евали «B-04 — виняток не діє» |
| q37 | узгоджено: `prod-ro-<клієнт>` дозволено лише при `skill_ref[0]` = `client-help-bot` і `purpose: читання (client-help-bot)` (оркестратор, runner, `sweep-rules.md`, `naryad-format.md`, `executor-brief.md`); рядки «ODOO:» на `prod-ro-*` відхиляються; `eval-builder`, `flow-state.md` (D-01) і `guard_db` його забороняють; агент `mail` не має запису в Odoo/Drive/GitHub. В інших скілах дозволу на прод немає |
| q09/q30 | профілю «без AI» немає ніде; відсутній пункт про AI → `escalated` (`package-fit-gap`, `package-sow-builder`, `business-case.md`) |
| q17 | еталони є; `guard_db` (bash і python): `prod`, `test-prod`, `prod-ro-acme`, `client-acme`, `anon-k1`, порожнє, `test-`, `test-x;id` → `FLOW_STOP`; `test-x`, `demo-1` → дозволено; без `ODOO_ALLOWED_HOSTS` — відмова |
| Попередній M-1 (профілі доступу) | закрито: профіль `repo` покриває gates-aggregator, package-release-builder, package-upgrade-runner, odoo-version-migrator (+`get_tag`, `list_tags`, WebFetch); `mail` має читання Drive; `research` має WebSearch/WebFetch. Лишок — M-1 і minor 1 нижче |
| Попередній M-2 (q10) | закрито: ключ `preconditions_confirmed.crm_deal_stage` зі значеннями `discovery_signed` (B-02) і `sow_signed` (B-04/B-06/B-11) у `naryad-format.md`, `odoo-bridge.md`, `c00-checklist.md`, `flow-map.md`, оркестраторі й чотирьох скілах-споживачах. Лишок — minor 2 |
| Решта рішень (q02–q08, q11–q16, q18–q29, q31–q36, q38–q44) | вибіркова перевірка за ключовими словами: суперечностей не знайдено (ліцензії q42, «на базі Odoo 19» q43, 2021→2025 q38, календарні дні q34, `anon-*` відкладено q02/q03, Fathom безстроково q05) |

## 2. Зауваження

### Major

**M-1. Запис файлу адрес у Drive (A-23 `адреси`, q08) не має виконавця: команду `drive-create` runner не знає, а скіл і агент суперечать один одному.**
`step-skill-map.md` (р. 60), `flow-executor-research.md` і `segment-selector/SKILL.md` (р. 70) віддають створення файлу runner'у рядком «КОМАНДИ: drive-create …». У `flow-step-runner/SKILL.md` такої команди немає, Drive серед інструментів runner не названо, дозволеного переліку команд для цього кроку немає. Крім того, агент каже «файл виконавець кладе в тимчасовий шлях із `where`», а скіл — «жодного проміжного файлу в робочому дереві репо чи scratchpad». Як адреси потрапляють від виконавця до runner, не визначено; наряд `адреси` закінчиться `escalated`.
Виправити: у `flow-step-runner` (Інструменти + Крок 8–9) описати `drive-create`: інструмент (`Google_Drive create_file`), дозволена тека лише з DATA_POLICY «Місця зберігання», лише для A-23 `адреси`, звідки береться вміст і де він видаляється; у скілі й агенті лишити одне формулювання про проміжний файл. Те саме одним рядком для `gh workflow run` (зараз є лише в `executor-brief.md`).

**M-2. Частину пакета не закомічено: 5 профільних агентів і фікстури `client-help-bot` — невідстежувані, 44 файли змінено.**
`plugins/flow-core/agents/flow-executor-{drive,mail,outreach,repo,research}.md` і `client-help-bot/evals/fixtures/` відсутні в git. Якщо каталог зібрати з `HEAD`, runner на Кроці 0 зупинить кожен наряд з `access_profile` ≠ `base` («немає агента»), тобто 18 з 29 ведучих скілів. Виправити: закомітити робоче дерево до тега релізу каталогу (q21) і перевірити `git status` порожній.

### Minor

1. `gates-aggregator` (р. 33), `package-release-builder` (р. 55), `package-upgrade-runner` (р. 42), `ci-pipeline-builder` (р. 34) називають `actions_run_trigger` своїм інструментом MCP, а в профілі `repo` його немає (це рядок «КОМАНДИ: gh workflow run»). Міст є лише в `executor-brief.md` і агенті; додати в кожен скіл три слова «через runner, рядок КОМАНДИ».
2. q10, залишки старого формулювання: `runbook-executor/evals/evals.json` р. 168 («назва стадії й ключ наряду — відкрите питання»; ключ уже визначено); `package-fit-gap/evals/evals.json` р. 66, 103 подають підтвердження прозою «Стадія угоди в CRM: підписано (вказано в наряді)», а не ключем `preconditions_confirmed.crm_deal_stage: discovery_signed`.
3. `ODOO_ALLOWED_HOSTS`: `_common.sh` читає список через пробіл, `apply.py`/`validate.py` — через кому. Значення з двох хостів пройде лише в одному з них (другий відмовить; безпечно, але зламає прогін). Узгодити роздільник і записати в `tools-odoo/README.md`.
4. `flow-client-delivery/README.md` р. 36 застарів: «фікстур для evals немає» (є три) і «`params.handoff`/`params.mode` для B-07 ще не внесено» (внесено в `naryad-format.md` і `support-desk`).
5. Закриті питання лишились у «Відкритих»: `config-as-code` («додати клас `test-pkg-<пакет>` у `data-and-connections.md`») і `master-data-template-builder` («у конвенціях flow-core немає `test-pkg-*`») — клас уже є в `data-and-connections.md` р. 21 і `c00-checklist.md`.
6. `client-help-bot/SKILL.md` р. 46: «odoo-mcp за замовчуванням може дивитися в іншу базу» — в усіх інших скілах «за замовчуванням дивиться в прод»; вирівняти формулювання.
7. Повтори з попередніх раундів, не змінились: розпізнавання команди з прози `args.text` у Кроці 9 (ж); кроки, де всі перевірки `manual`; наживо не запускались `claude plugin eval`, odoo-mcp, GitHub, Gmail, `tools-odoo` на Odoo 19 (q26 — AI-інженер до подання).

## 3. Покриття флоу

29 скілів; проти `CONCEPT.md` §2 (28, історична) додано `client-help-bot` (B-07, друга частина, q37). Кандидати з `candidates.md` реалізовані або злиті/відкинуті за CONCEPT §4.
Без власного скіла пакета: людські кроки A-02, A-06, B-08b, B-08d, B-12, C-00, C-08; на скілах організації — A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07 (навчання), B-08c і другий наряд B-08a; C-05 — шаблон `data-policy-template.md` + `C-05.yaml`; C-07 — режим `incident` у `eval-builder`.
Свідомо відкладено рішеннями: виробник знеособленої копії `anon-<клієнт>` (C-09) і B-11 версія 2 (q02/q03); щорічний перерахунок A-01 (q40, ручне завдання); евали `requires: step-run` (q27); код Enterprise для D-03 (q20). Не визначено: що створює наряд `client-help-bot` `answer` «на період» (до рішення — вручну PM/Підтримка).
