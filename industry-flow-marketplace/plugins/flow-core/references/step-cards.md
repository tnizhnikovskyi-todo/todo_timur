# Картки кроків: чернетки нових і змінених кроків (A-02b … C-08R)

Чернетки для оновлення карток у Odoo після позначки C-00 «картки оновлено» (`c00-checklist.md`); джерело правди для порядку — `flow-map.md`, для `skill_ref`/`access_profile` — `step-skill-map.md`. Поля: `raciR` (виконавець), `executor`, `skillRef`, `access_profile`, `inArtifacts`, `outArtifacts`, гейт, `review.checklists` (`review-checklists/`), `params.sample` (N-18), ліміти (модель/ефорт; години; $) — стартові оцінки до першого прогону, стартова зрілість — 1 для всіх, ескалація. Шляхи — відносно `docs/industries/<галузь>/`, якщо не вказано інше.

## Ролі
- **Контент-менеджер (маркетинг)** — людина зі своїм Claude, `executor: any`. Кроки: A-21c, A-23 `prep` (тексти), D-05 (кейси), A-18 (матеріали релізу). Працює лише з контентом у репо (клас даних `commercial`), без баз Odoo (читає лише наряд), без `internal-raw`; профіль `content` (`flow-executor-content`).
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
- `outArtifacts`: research/{REUSE.md (розділ `## Інвентар` + реєстр; REUSE-xx), sources-log.md; дописує рядки A-03c в `research/AI-DECISIONS.md`}
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
- `outArtifacts`: concept/{features.md, screens.md, scenarios.md}; research/{BOX.md (склад коробок без годин і грошей), SALES.md, facts.yaml (доповнює)}; розділ «Повнота» в `research/AI-DECISIONS.md` (самоперевірка в кінці кроку: `flow-research:completeness-audit` як під-скіл, 3 ролі, 14 пунктів, 1 коло; кабінетні прогалини закриваються правкою тут, незакрите — рядки AI-NN «ризик, перевірити на пілоті»); дописує в `research/REJECTED.md` і `research/AI-DECISIONS.md` (A-03b, A-03c) свої рядки, не перезаписуючи чужі
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
Картки посилаються на файли: `research.md`, `edition-claims.md` (A-03b, A-20, A-20c), `concept.md` (A-20), `completeness.md` (A-20, самоперевірка повноти), `owner-page.md` (A-20c), `prototype.md` (A-21), `video-materials.md` (A-21c). Назви — контракт: файли створюються з цими іменами; при зміні назви правляться картки тут. Для кроків із `[]` чек-лист не потрібен.

## Відкриті питання
- Немає відкритих питань (відкриті питання пакета — у плані §5).
