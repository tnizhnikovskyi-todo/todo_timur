# Картки кроків: чернетки нових і змінених кроків (A-02b … C-08R, 0.4.0: A-16b, A-17b, A-17c)

Чернетки для оновлення карток у Odoo після позначки C-00 «картки оновлено» (`c00-checklist.md`); джерело правди для порядку — `flow-map.md`, для `skill_ref`/`access_profile` — `step-skill-map.md`. Поля: `raciR` (виконавець), `executor`, `skillRef`, `access_profile`, `inArtifacts`, `outArtifacts`, гейт, `review.checklists` (`review-checklists/`), `params.sample` (N-18), ліміти (модель/ефорт; години; $) — стартові оцінки до першого прогону, стартова зрілість — 1 для всіх, ескалація. Шляхи — відносно `docs/industries/<галузь>/`, якщо не вказано інше.

## Ролі
- **Контент-менеджер (маркетинг)** — людина зі своїм Claude, `executor: any`. Кроки: A-21c, A-23 `prep` (тексти), D-05 (кейси), A-18 (матеріали релізу); рецензент A-16b (чек-лист `user-guide.md`). Працює лише з контентом у репо (клас даних `commercial`), без баз Odoo (читає лише наряд), без `internal-raw`; профіль `content` (`flow-executor-content`).
- **AI-інженер / агент Ретро** — веде C-04, C-07, C-08R: регрес евалів, розбір помилки AI, зведення уроків `LSN-xxx`; правки скілів — PR, рішення про зрілість кроку — людина.

- **власник** — власник бізнесу ToDo / замовник пакета (людина, не AI): заповнює анкету A-02b, приймає зразок і має вето на гейті концепції (A-20c) разом із Власником продукту. У ростері Odoo (`ODOO_SCHEMA`) відповідає ролі «Власник продукту» (A); `waiting_for.role` для його підкроків = ця роль, інша — лише за ростером.

## Картки

### A-02b. Анкета власника
- `raciR`: власник (R); BA (A)
- `executor`: any (prepare/validate); human (заповнення)
- `skillRef`: flow-research:owner-questionnaire
- `access_profile`: base
- `inArtifacts`: docs/industries/scoring.md; A-02 рішення (flow/decisions.md)
- `outArtifacts`: docs/industries/<галузь>/OWNER-INTAKE.md
- гейт: ні (валідація check_intake.py); заповнення — `waiting_human` ≤5 хв
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/low; 1 год; $3; стартова зрілість: 1
- примітки: Анкета: 6 пунктів (`editions`, `icp`, `todo_data`, `brand`, `materials` — блокуючі `*`; `do_not_do`), решта — `defaults:` (AI-замовчування); режими `prepare → validate`
- ескалація: власник не відповів за `human_sla` -> активність Тімліду; блокуюче поле порожнє -> `waiting_human`

### A-03b. Глибокий аналіз галузі й конкурентів
- `raciR`: BA (R)
- `executor`: any
- `skillRef`: flow-research:industry-deep-dive
- `access_profile`: research-internal
- `inArtifacts`: OWNER-INTAKE.md; briefing.md (A-03); past-projects.md (A-04); sessions (якщо A-05/A-06)
- `outArtifacts`: research/{FUNCTIONAL-MAP.md, edition-claims.md, competitors-registry.md, competitors/*.md (8–12), sources-log.md, facts.yaml, DEPENDS.yaml, REJECTED.md (короткий формат «не робимо й чому»), AI-DECISIONS.md (створює A-03b; рядки A-03b: підсегмент, кандидати на «не робимо»)}
- гейт: ні; контрольної точки K1 і питань власнику немає — рішення AI в `AI-DECISIONS.md`
- `review.checklists`: [research.md, edition-claims.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false (true лише на явний запит або для першої галузі: профіль одного конкурента + 10 рядків матриці)
- ліміти: opus/high для синтезу, sonnet для профілів; 6 год; $25; стартова зрілість: 1
- примітки: Профілі конкурентів 8–12 (К-15); підсегмент і кандидати на «не робимо» вирішує AI (рядки AI-DECISIONS); слабкий довід = «ризик, перевірити на пілоті»; EE-твердження — лише через `edition-claims.md` (К-12)
- примітки (join): AND-join сесій — у A-03b (читає протоколи A-06)
- ескалація: немає доступу до EE -> «не перевірено» (WARN), не стоп; брак доказів -> «ризик, перевірити на пілоті» (план A-23), не стоп

### A-03c. Готові модулі ToDo у збірку
- `raciR`: Архітектор (R)
- `executor`: any (один наряд, без режимів)
- `skillRef`: flow-research:reuse-modules
- `access_profile`: research-internal
- `inArtifacts`: OWNER-INTAKE.md (`reuse`); research/FUNCTIONAL-MAP.md
- `outArtifacts`: research/{REUSE.md (розділ `## Інвентар` + реєстр; REUSE-xx), sources-log.md; дописує рядки A-03c в `research/AI-DECISIONS.md`} (§27: в інвентарі завжди `td_home_menu` (лише CE) і `td_support` (CE і EE), рішення «беремо»; перевірка RU-core)
- гейт: ні; «беремо / адаптуємо / ні» вирішує AI (рядки AI-DECISIONS), вето — на A-20c
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 3 год; $10; стартова зрілість: 1
- примітки: Критерії: Odoo 19, CE/EE, права на код, тести, підтримка, відповідність карті функцій; ліцензія наших модулів — LGPL-3 за замовчуванням (рядок AI-DECISIONS, вето — на A-20c)
- ескалація: репо/проєкт недоступні -> `waiting_human`; права на код невідомі -> «ні» до уточнення

### A-20. Концепція + BOX + SALES + REJECTED + AI-DECISIONS
- `raciR`: BA (R); Власник продукту (A)
- `executor`: any
- `skillRef`: flow-research:concept-mapper
- `access_profile`: research
- `inArtifacts`: OWNER-INTAKE.md; research/{FUNCTIONAL-MAP.md, REJECTED.md, AI-DECISIONS.md, facts.yaml, REUSE.md, edition-claims.md}; flow/decisions.md (вето власника — режим `recalc`); briefing.md; past-projects.md; протоколи сесій A-05/A-06 (якщо були)
- `outArtifacts`: concept/{features.md, screens.md, scenarios.md}; research/{BOX.md (склад коробок без годин і грошей), SALES.md, facts.yaml (доповнює)}; розділ «Повнота» в `research/AI-DECISIONS.md` (самоперевірка в кінці кроку: `flow-research:completeness-audit` як під-скіл, 3 ролі, 14 пунктів, 1 коло; кабінетні прогалини закриваються правкою тут, незакрите — рядки AI-NN «ризик, перевірити на пілоті»); дописує в `research/REJECTED.md` і `research/AI-DECISIONS.md` (A-03b, A-03c) свої рядки, не перезаписуючи чужі (§27: у кожній коробці `td_home_menu` (лише CE) і `td_support`; перевірка CM-box-core; мітки `Коробка входу`, `Показників дашборда`)
- гейт: ні (єдиний гейт — A-20c)
- `review.checklists`: [concept.md, edition-claims.md, completeness.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: opus/high; 8 год; $32 (концепція + самоперевірка повноти: 3 рецензенти, критик; до 0.3.1 A-20 5 год/$20 + A-20b 3 год/$12); стартова зрілість: 1
- примітки: `where` завжди містить `research/AI-DECISIONS.md`; самоперевірку повноти запускає runner (виконавець без Agent/Bash), `check_completeness.py` — рядком «КОМАНДИ»; Роль-покупець має екран-дашборд; вето власника з `flow/decisions.md` не відкидається знову; OWNER-BRIEF не пишеться; брак болів не зупиняє крок (слабкий довід = «ризик, перевірити на пілоті»); економіку (окупність, години, ціни коробок) не рахувати
- ескалація: рекомендація AI проти анкети -> показати розбіжність, не перемагати анкету (С-01)

### A-20c. Сторінка для власника (1 Artifact, 3 сторінки) — єдиний гейт концепції
- `raciR`: Власник продукту (A, гейт); BA (R)
- `executor`: any
- `skillRef`: flow-research:concept-presentation
- `access_profile`: base
- `inArtifacts`: research/*; concept/*; research/AI-DECISIONS.md
- `outArtifacts`: research/owner-page/{index,competitors,rejected}.html; owner-page/PUBLISHED.md; research/owner-page/screens-390/**, research/owner-page/screens-1280/** (знімки 390/1280 px)
- гейт: так: єдиний гейт дослідження (вето-цикл); Затвердити = немає заперечень; Повернути (рядки `AI-NN: не згоден — <що замість>`) -> A-20 `recalc` / A-03b / A-03c (`gate.return_to`)
- `review.checklists`: [owner-page.md, edition-claims.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false (true лише на явний запит або для першої галузі: перший екран сторінки)
- ліміти: sonnet/high; 3 год; $12; стартова зрілість: 1
- примітки: Висновок без грошового блоку на першому екрані; кожна теза веде на рядок дослідження; блок «Що вирішив AI і з яким ризиком» — відповідь лише за незгоди (кнопка «Скопіювати мої заперечення»)
- ескалація: контракт сторінки не виконано -> `returned` на себе (до 2 кругів + 1)

### A-21. Реальний зріз Odoo 19 `td_*` + живий запис + `facts.json`
- `raciR`: BA (R: сценарії й приймання); Архітектор або AI (код `td_*`); власник (приймання зразка)
- `executor`: any
- `skillRef`: flow-research:prototype-builder
- `access_profile`: repo
- `inArtifacts`: research/FUNCTIONAL-MAP.md §4; BOX.md; SALES.md §2/§6; REUSE.md; OWNER-INTAKE.md (`demo_edition`, `prototype`)
- `outArtifacts`: package/addons/td_<галузь>_*; prototype-real/{PLAN.md, README.md, screens/, screens-mobile/, shoot/, video/rec/, facts.json, ACCEPTED.md}
- гейт: зразок: `waiting_human`; після приймання — повний обсяг; потім гейт зрізу; Повернути -> A-21 або A-20
- `review.checklists`: [prototype.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: true спочатку (1 екран + 15 с + 1 кадр титра), далі false
- ліміти: sonnet/high; 8 год; $40; стартова зрілість: 1
- примітки: Справжні моделі `td_`, без `x_`/Studio; `defaults.prototype.fidelity: mock` -> `waiting_human` (К-23); EE — позначкою (К-06)
- ескалація: preflight середовища не пройдено -> `waiting_human` до витрат бюджету

### A-21d. Огляд покриття зрізу (slice-coverage, E3)
- `raciR`: AI (R); власник — вето через `veto-batch`
- `executor`: ai; `skillRef`: flow-research:completeness-audit (`params.mode: slice-coverage`)
- `access_profile`: research; `client_data: none`
- `inArtifacts`: prototype-real/{PLAN,complexity,ACCEPTED,README}.md; package/addons/td_* (імена моделей, `__manifest__.py`); concept/*; research/{BOX,SALES,REJECTED,AI-DECISIONS,FUNCTIONAL-MAP,REUSE}.md, facts.yaml; OWNER-INTAKE.md
- `outArtifacts`: research/COVERAGE-SLICE.md; рядки в research/AI-DECISIONS.md (разом <=15 рядків «Рішення»)
- гейт: ні (`done` -> A-21c, а при `skip_market_check` -> A-07)
- перевірки: `check_slice_coverage.py` (CS-*) — `flow-autocheck/references/checks/A-21d.yaml`
- ліміти: opus/medium; 2 год; стартова зрілість: 1
- примітки: зріз, REJECTED і код не правити; пропозиції "в A" входять у `from-slice` SPEC A-08
- ескалація: немає зрізу A-21 (`ACCEPTED.md`) -> `returned` на A-21

### A-21c. Продаючі матеріали
- `raciR`: Контент-менеджер (R); Власник продукту (A, гейт)
- `executor`: any (Контент-менеджер)
- `skillRef`: flow-research:showcase-content
- `access_profile`: content
- `inArtifacts`: prototype-real/{video/rec/, facts.json, PLAN.md}; research/SALES.md; OWNER-INTAKE.md (`materials`, `brand`)
- `outArtifacts`: prototype-real/{video/*-16x9.mp4, video/*-9x16.mp4, SHOW.md|html|pdf, captions.yaml, ACCEPTED.md}
- гейт: так: гейт; Повернути -> A-21c або A-21
- `review.checklists`: [video-materials.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: true (15 с + 1 кадр титра)
- ліміти: sonnet/medium; 4 год; $15; стартова зрілість: 1
- примітки: Перемонтаж без перезйомки й без доступу до Odoo (К-10); числа = `facts.json`; бренд лише в заставках/титрах
- ескалація: потрібна перезйомка -> повернути в A-21 з причиною

### A-22. База зрізу для гарячого ліда
- `raciR`: BA (R)
- `executor`: any
- `skillRef`: flow-package-build:demo-base-builder
- `access_profile`: base
- `inArtifacts`: package/addons/td_<галузь>_*; prototype-real/facts.json; запит гарячого ліда з A-23
- `outArtifacts`: окрема демо-база зі зрізу `td_*` (без `x_`, К-11); опис бази — `docs/industries/<галузь>/prototype-real/lead-base/…` (за `base-description` в `A-22.yaml`)
- гейт: ні
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 2 год; $8; стартова зрілість: 1
- примітки: Лише allow-list демо-баз; нічне скидання — за описом бази
- ескалація: немає зрізу A-21 -> `escalated` до BA

### A-23. Тест попиту: список / адреси / prep / results
- `raciR`: Контент-менеджер (R, prep: тексти); BA (A)
- `executor`: any; central (адреси)
- `skillRef`: flow-research:demand-test-runner (prep/results); flow-research:segment-selector (список/адреси)
- `access_profile`: outreach (prep/results); research-internal (список/адреси)
- `inArtifacts`: OWNER-INTAKE.md; prototype-real/ (ACCEPTED); матеріали A-21c: video/*-16x9.mp4, video/*-9x16.mp4, SHOW.*, captions.yaml; research/{AI-DECISIONS.md, BOX.md, SALES.md}, concept/features.md; mailing-list
- `outArtifacts`: demand/{risk-plan.md, emails.md, mailing-plan.md, thresholds.md, landing.md} (`prep`), demand/results.md (`results`; склад — за «Запис» скіла demand-test-runner); mailing-list.csv (+ парний .md)
- гейт: ні; результати нижче порогів 2–3 тижні -> рішення Власника продукту
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 3 год; $10; стартова зрілість: 1
- примітки: Нічого не надсилає й не публікує; ризики з A-20 (брак болів/тріалів) — у план перевірки (К-01)
- ескалація: сигнали нижче порогів -> ескалація без автопереходу

### A-08. SPEC пакета (режим `from-slice`, E2)
- `raciR`: BA / Архітектор (R); Власник продукту (A, гейт)
- `executor`: any; `skillRef`: скіл організації (зовнішній, `odoo19-mvp-build:spec-writer` / `odoo19-tr-authoring:*`; `skill_ref` з картки)
- `inArtifacts`: режим `from-slice` — `prototype-real/{PLAN.md, complexity.md, facts.json}`, `research/{BOX,SALES,REJECTED,AI-DECISIONS}.md`, `concept/*`; режим `перша` (лише без зрізу) — повний ТР
- `outArtifacts`: `package/SPEC.md` (при `from-slice` — короткий SPEC: concept + complexity + PLAN зрізу, без повного ТР; сценарії за ролями, AC-NN)
- гейт: так: Затвердити; Повернути -> A-08
- `params.mode`: `from-slice` (за замовчуванням, коли є зріз A-21) | `перша` | `нова-версія`
- примітки: скіли A-08 зовнішні — режим задається лише ключем наряду й переліком входів; повторювати детальну роботу зрізу повним ТР не можна (E2: «ми вже це проходили»)
- ескалація: у PLAN/complexity немає даних для AC -> `escalated` до BA з переліком прогалин

### A-16b. Інструкції користувача
- `raciR`: AI (R, виконавець); Контент-менеджер / власник (рецензія, A)
- `executor`: any; `skillRef`: flow-package-build:user-guide-builder
- `access_profile`: repo
- `inArtifacts`: package/SPEC.md (сценарії за ролями, AC); package/demo/ (стенд, ролі, скрипти, README із SHA); тури A-16 (`package/demo/scenarios.md`); `package/templates/answers.yaml` і профілі
- `outArtifacts`: package/docs/user-guide/{INDEX.md, admin.md, <роль>.md, cards/<роль>.md, reference/messages.md, img/<роль>/*.png}; `package/demo/defects.md` — лише запис дефекту UI (повернення на A-14); INDEX — три таблиці покриття («заявлене»: сценарій SPEC -> розділ; «розроблене»: меню/дії/звіти td_* -> розділ; «налаштування й експлуатація»: ключі answers.yaml/VP-NN -> розділ) і SHA стенда; `package/docs/user-guide/img/SHOOT-LOG.md`, `shoot-plan.json`; рядок(и) AI-NN в `docs/industries/<галузь>/research/AI-DECISIONS.md` (запасний засіб зйомки, рішення AI)
- гейт: ні (рецензія — чек-лист; крок закривається `done`, гейт — A-17)
- `review.checklists`: [user-guide.md]; `review.max_rounds: 5` (без контрольного; цикл до нуля зауважень, ліміт 5 кругів на день, далі `waiting_human`); **незалежний аудит покриття (0.4.1) — обов'язковий після самоперевірки: 3 рецензенти `flow-reviewer` з різних кутів (адмін наскрізно / ролі: цикл замовлення, права, кадри / переліки з коду + F/AC + ACCEPTANCE), кожен із власним переліком із джерел; цикл до нуля зауважень; у тестовому наряді A-16b `review.max_rounds: 5` на день, зауваження лишились -> `waiting_human` і чекати рішення людини**
- перевірки (повний перелік — таблиця «Автоперевірка» SKILL.md скіла): `check_guides.py` (UG-files, UG-card, UG-roles, UG-admin, UG-admin-ops, UG-cover, UG-cover-dev, UG-cover-admin (§26а: заявлене / розроблене / налаштування й експлуатація; 0.4.1 — розділи `admin.md` з командами, `get_param`, меню лише для групи), UG-cover-buttons, UG-access (права ролей; джерело груп — `img/ROLE-GROUPS.json` зі стенда, обов'язковий артефакт, plan.md — запасне: FAIL за plan.md має дві причини, спершу зняти ROLE-GROUPS.json зі стенда (shoot.mjs) і повторити, на A-11/A-12 повертати лише коли FAIL підтверджено групами зі стенда; перевизначення меню записами `ir.ui.menu` без name враховуються; заперечення діє на фрагмент-речення клітинки, не на весь крок), UG-shots (кадри під логіном ролі), UG-messages (`reference/messages.md`), UG-std-label (назви за uk.po 19.0), UG-img, UG-sha, UG-lang) — `flow-autocheck/references/checks/A-16b.yaml`
- ліміти: sonnet/medium; 4 год; $12; стартова зрілість: 1
- примітки: скриншоти зі стенда на поточному SHA; текст кроків українською без англійських підписів
- ескалація: дефект UI під час зйомки -> повернути в A-14 (не правити модулі тут); **права ролей / код** (меню чи кнопка, названі в кроці, недоступні групам ролі; UG-access, код 3 `shoot.mjs`) -> дефект у `defects.md` і повернення в `returned_to: A-11` (конфіг — A-12), далі контур A-11 -> A-12 -> A-14 -> A-15-full -> A-16 -> A-16b, **конфіг** (ролі, «Модулі до установки») -> A-12, не обхід текстом (пунктир A-16b -> A-11 / A-12 у `flow-map.md`); стенд недоступний -> A-15; стенд застарів: код пакета змінено після SHA гейтів (зокрема злито модулі §27: td_home_menu, td_support) -> контур коду 1: A-11-fix -> A-12-fix -> A-14 -> A-15-full -> A-16 -> A-16b; A-15 refresh окремим нарядом (AI сам, без людини) — лише коли `git diff --quiet <SHA_CHECKS>..HEAD` дає код 0 (SHA гейтів змінився лише міткою)

### A-17. Приймання пакета (змінена картка 0.4.0)
- `raciR`: Власник продукту (R, A); AI — чернетка `product-decision-drafter`
- `skillRef`: flow-package-evolution:product-decision-drafter (AI-частина)
- `inArtifacts`: package/{ACCEPTANCE.md, CHECKS.md, demo/, docs/user-guide/INDEX.md}
- гейт: так: Затвердити -> A-17b ∥ A-17c; Повернути -> A-08 / A-14 (з повтором A-15 -> A-16 -> A-16b -> A-17) / D-03
- **рядок картки й чек-листа: «власник тестує стенд за інструкціями A-16b»** — власник проходить сценарії своєї ролі за `package/docs/user-guide/<роль>.md`, фіксує зауваження в `package/demo/defects.md`, у `ACCEPTANCE.md` — «власник тестував: дата, SHA». Стенд локальний (`package/demo/up.sh`); рішення про сервер відкрите; окремого наряду немає
- примітки: сам стенд у карту не входить (відкрите рішення), лише точка «власник тестує»

### A-17b. Електронне навчання
- `raciR`: AI (R); Контент-менеджер / Власник продукту (рецензія, A)
- `executor`: any; `skillRef`: flow-package-build:elearning-builder; `access_profile`: repo
- `inArtifacts`: package/docs/user-guide/ (INDEX, розділи ролей, img); package/SPEC.md; `package/templates/answers.yaml` (ключі `elearning.mode: "on"|"off"`, `elearning.pass_score`; за замовчуванням 80); вихідники Odoo 19 (`website_slides`, `website_slides_survey`) — «перевірити файл:рядок»
- `outArtifacts`: модуль package/addons/td_<галузь>_elearning (залежність `website_slides`; data XML: курс на роль, уроки з розділів A-16b, тест після кожного курсу з оцінкою й порогом; сертифікація — лише якщо підтверджено у вихідниках 19.0, інакше «не перевірено» в `AI-DECISIONS.md`); тести модуля; блок `elearning:` у `package/templates/answers.yaml` (додає A-17b, якщо його немає); рядки AI-NN в `AI-DECISIONS.md` (сертифікація, рішення AI); `package/config/{manifest.yaml,CONFIG.md}` (лише рядки `website_slides` і `td_<галузь>_elearning`)
- гейт: ні; AND-split з A-17c, AND-join в A-18
- перелік установки: при `elearning.mode: "on"` крок сам дописує `website_slides` і `td_<галузь>_elearning` у `package/config/{manifest.yaml,CONFIG.md}` (обидва профілі)
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- перевірки (повний перелік — таблиця «Автоперевірка» SKILL.md): `check_elearning.py` (EL-deps, EL-tests, EL-blocked, EL-courses, EL-quiz, EL-source, EL-lang, EL-score, EL-access, EL-content, EL-pass, EL-mode), тести на чистій CE (курсів = ролей, >=5 питань у курсі), lint, CI C-03, security-review (недоступний гейт = рішення AI + MANUAL), `A-17b.yaml`
- ліміти: sonnet/medium; 4 год; $12; стартова зрілість: 1
- ескалація: `website_slides` не встановлюється на CE -> `escalated` з логом; дефект тексту уроку -> A-16b

### A-17c. Інструкції для AI-підтримки
- `raciR`: AI (R); Власник продукту (A)
- `executor`: any; `skillRef`: flow-package-build:support-kb-builder; `access_profile`: repo
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний); рецензент — Власник продукту (Архітектор — KB-facts)
- `inArtifacts`: package/addons/td_*; package/docs/user-guide (FAQ); `research/AI-DECISIONS.md` (ризики); package/SPEC.md; `package/demo/defects.md`
- `outArtifacts`: package/support/{AI-INSTRUCTIONS.md, kb/KB-NNN-*.md, INDEX.md} — **лишається в ToDo, клієнту не передається**; споживачі: flow-client-delivery:support-desk, client-help-bot, odoo19-implementation:hypercare-tracker (зовнішній — лише згадка)
- гейт: ні; AND-split з A-17b, AND-join в A-18
- перевірки (повний перелік — таблиця «Автоперевірка» SKILL.md): `check_kb.py` (KB-ai, KB-kinds, KB-merge, KB-module, KB-ids, KB-route, KB-support (§27: розділ «звернення з td_support»), KB-privacy), `no-client-ids`, `A-17c.yaml`
- ліміти: sonnet/medium; 3 год; $10; стартова зрілість: 1
- примітки: режим `params.mode: reconcile` — AI сам після злиття A-17b і A-17c звіряє сторінку `td_<галузь>_elearning` (при незлитих PR — з гілки-стику: локальний `git merge --no-ff flow/A-17b-test` від `flow/A-17c-test`, база reconcile = merge-коміт; A-18 стартує від HEAD гілки reconcile, git.base = цей HEAD), знімає позначку «звірити після злиття A-17b» (до A-18, без наряду від людини); читання проду лише через `prod-ro-<клієнт>`; маршрути діагностики B-13 / A-19 / D-02; даних клієнтів у KB немає
- ескалація: модуль td_* без опису поведінки в SPEC -> `escalated` до Архітектора; виняток — спільні модулі §27/§27а (`td_home_menu`, `td_support`, `td_knowledge` та будь-який спільний модуль із README): їх немає в SPEC галузевого пакета, джерело — код і README модуля та сторінка 5а support-kb-builder; ескалація лише якщо немає ні SPEC, ні README

### A-18. Реліз (змінена картка 0.4.0)
- `inArtifacts` додатково: package/docs/user-guide, package/addons/td_<галузь>_elearning, package/support
- реліз включає A-16b (package/docs/user-guide) і модуль td_<галузь>_elearning; `package/support/` — у репо пакета, з клієнтської передачі виключено (перелік у release-нотатці). B-07 (`user-training-builder`, зовнішній) і client-help-bot беруть пакетні матеріали й лише адаптують під конфіг клієнта

### C-04. Регрес евалів
- `raciR`: AI-інженер (R)
- `executor`: any
- `skillRef`: flow-core:eval-builder
- `access_profile`: base
- `inArtifacts`: evals/ кожного скіла; поточні версії плагінів
- `outArtifacts`: evals/INDEX.md; блок `evals:` у звіті
- гейт: ні
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 2 год; $8; стартова зрілість: 1
- примітки: Режими `weekly|init|regress`; старт — набір «меблі» (N-17)
- ескалація: падіння регресу -> пропозиція пониження зрілості кроку (`maturity_proposals`)

### C-07. Розбір помилки AI
- `raciR`: AI-інженер (R)
- `executor`: any
- `skillRef`: flow-core:eval-builder (`incident`)
- `access_profile`: base
- `inArtifacts`: flow/ai-incidents/<id>.md; звіт кроку
- `outArtifacts`: evals/ новий кейс; блок `evals:`
- гейт: ні
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 2 год; $8; стартова зрілість: 1
- примітки: Причина конкретної помилки; зведення уроків — C-08R
- ескалація: причину не знайдено -> активність AI-інженеру

### C-08R. Ретро скілів
- `raciR`: AI-інженер / агент Ретро (R); Власник продукту (A, щоденний пакет — кнопка)
- `executor`: any
- `skillRef`: flow-core:skill-retro
- `access_profile`: repo
- `inArtifacts`: звіти `run` з `human_rounds`, `review_rounds`; observations/; зауваження людей
- `outArtifacts`: flow/lessons/LSN-xxx.md; flow/lessons/INDEX.md; пропозиції правок скілів (PR)
- гейт: щоденний пакет — кнопка Власника продукту
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 2 год; $8; стартова зрілість: 1
- примітки: Щодня (`mode: daily`) + події (`mode: event`: «Повернути», `escalated`, червоний CI, `human_rounds > 2`); межі з C-04/C-07 — `flow-map.md`
- ескалація: зауваження без урока -> `LSN-coverage` FAIL (`check_lessons.py`)

## Назви чек-листів рецензента (`review-checklists/`)
Картки посилаються на файли: `research.md`, `edition-claims.md` (A-03b, A-20, A-20c), `concept.md` (A-20), `completeness.md` (A-20, самоперевірка повноти), `owner-page.md` (A-20c), `prototype.md` (A-21), `video-materials.md` (A-21c), `user-guide.md` (A-16b). Назви — контракт: файли створюються з цими іменами; при зміні назви правляться картки тут. Для кроків із `[]` чек-лист не потрібен.

## Відкриті питання
- Немає відкритих питань (відкриті питання пакета — у плані §5).
