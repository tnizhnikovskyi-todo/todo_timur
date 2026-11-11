# Картки кроків: чернетки нових і змінених кроків (A-02b … C-08R)

Чернетки для оновлення карток у Odoo після позначки C-00 «картки оновлено» (`c00-checklist.md`); джерело правди для порядку — `flow-map.md`, для `skill_ref`/`access_profile` — `step-skill-map.md`. Поля: `raciR` (виконавець), `executor`, `skillRef`, `access_profile`, `inArtifacts`, `outArtifacts`, гейт, `review.checklists` (`review-checklists/`), `params.sample` (N-18), ліміти (модель/ефорт; години; $) — стартові оцінки до першого прогону, стартова зрілість — 1 для всіх, ескалація. Шляхи — відносно `docs/industries/<галузь>/`, якщо не вказано інше.

## Ролі
- **Контент-менеджер (маркетинг)** — людина зі своїм Claude, `executor: any`. Кроки: A-21c, A-23 `prep` (тексти), D-05 (кейси), A-18 (матеріали релізу). Працює лише з контентом у репо (клас даних `commercial`), без баз Odoo (читає лише наряд), без `internal-raw`; профіль `content` (`flow-executor-content`).
- **AI-інженер / агент Ретро** — веде C-04, C-07, C-08R: регрес евалів, розбір помилки AI, зведення уроків `LSN-xxx`; правки скілів — PR, рішення про зрілість кроку — людина.

- **власник** — власник бізнесу ToDo / замовник пакета (людина, не AI): заповнює анкету A-02b, відповідає на K1 (A-03b), приймає зразок і гейт концепції разом із Власником продукту. У ростері Odoo (`ODOO_SCHEMA`) відповідає ролі «Власник продукту» (A); `waiting_for.role` для його підкроків = ця роль, інша — лише за ростером.

## Картки

### A-02b. Анкета власника
- `raciR`: власник (R); BA (A)
- `executor`: any (prepare/validate); human (заповнення)
- `skillRef`: flow-research:owner-questionnaire
- `access_profile`: base
- `inArtifacts`: docs/industries/scoring.md; A-02 рішення (flow/decisions.md)
- `outArtifacts`: docs/industries/<галузь>/OWNER-INTAKE.md
- гейт: ні (валідація check_intake.py); заповнення — `waiting_human` ≤20 хв
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/low; 1 год; $3; стартова зрілість: 1
- примітки: Анкета: 14 блоків, блокуючі `*`; питання власнику — ДО синтезу (К-02, N-02)
- ескалація: власник не відповів за `human_sla` -> активність Тімліду; блокуюче поле порожнє -> `waiting_human`

### A-03b. Глибокий аналіз галузі й конкурентів (K1 усередині)
- `raciR`: BA (R); власник (K1)
- `executor`: any
- `skillRef`: flow-research:industry-deep-dive
- `access_profile`: research-internal
- `inArtifacts`: OWNER-INTAKE.md; briefing.md (A-03); past-projects.md (A-04); sessions (якщо A-05/A-06)
- `outArtifacts`: research/{FUNCTIONAL-MAP.md, edition-claims.md, competitors-registry.md, competitors/*.md (8–12), K1.md, sources-log.md, facts.yaml, DEPENDS.yaml, REJECTED.md (створює A-03b; рядки G1–G3)}
- гейт: ні; K1 — `waiting_human` + `resume` (відповіді власника `K1-Q*`); не кнопка
- `review.checklists`: [research.md, edition-claims.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: true (профіль одного конкурента + 10 рядків матриці)
- ліміти: opus/high для синтезу, sonnet для профілів; 6 год; $25; стартова зрілість: 1
- примітки: Профілі конкурентів 8–12 (К-15); кандидати на відкидання показано в K1 до синтезу (К-02); EE-твердження — лише через `edition-claims.md` (К-12)
- примітки (join): AND-join сесій — у A-03b (читає протоколи A-06)
- ескалація: немає доступу до EE -> «не перевірено» (WARN), не стоп; брак груп джерел -> ризик у план A-23, не стоп (К-01)

### A-03c. Готові модулі ToDo у збірку
- `raciR`: Архітектор (R); власник (гейт)
- `executor`: any (inventory/session/decide); сесія з власником — `human_substep` (AI-наряд `session` готує матеріал і питання)
- `skillRef`: flow-research:reuse-modules
- `access_profile`: research-internal
- `inArtifacts`: OWNER-INTAKE.md (`reuse`); research/FUNCTIONAL-MAP.md
- `outArtifacts`: research/REUSE.md (REUSE-xx, години перераховано)
- гейт: так: гейт «беремо / адаптуємо / ні» після сесії з власником (К-18)
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 3 год; $10; стартова зрілість: 1
- примітки: Критерії: Odoo 19, CE/EE, права на код, тести, підтримка, відповідність карті функцій; ліцензія наших модулів — LGPL-3 за замовчуванням, остаточно — рішення власника
- ескалація: репо/проєкт недоступні -> `waiting_human`; права на код невідомі -> «ні» до уточнення

### A-20. Концепція + OWNER-BRIEF + BOX + SALES (+ рядки G4/G4а в REJECTED)
- `raciR`: BA (R); Власник продукту (A)
- `executor`: any
- `skillRef`: flow-research:concept-mapper
- `access_profile`: research
- `inArtifacts`: OWNER-INTAKE.md; research/FUNCTIONAL-MAP.md; REUSE.md; briefing.md; past-projects.md; протоколи сесій A-05/A-06 (якщо були)
- `outArtifacts`: concept/{features.md, screens.md, scenarios.md}; research/{OWNER-BRIEF.md, BOX.md, SALES.md}; дописує в існуючий `research/REJECTED.md` (A-03b) лише рядки G4/G4а, не перезаписуючи чужі
- гейт: ні (гейт перенесено в A-20c, К-04)
- `review.checklists`: [concept.md, edition-claims.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: opus/high; 5 год; $20; стартова зрілість: 1
- примітки: Роль-покупець має екран-дашборд; позиції з `do_not_reject` не відкидати; OWNER-BRIEF пише A-20 (К-21); брак болів не зупиняє крок (К-01)
- ескалація: рекомендація AI проти анкети -> показати розбіжність, не перемагати анкету (С-01)

### A-20b. Аудит повноти (5 ролей)
- `raciR`: BA (R); Архітектор (C)
- `executor`: any
- `skillRef`: flow-research:completeness-audit
- `access_profile`: base
- `inArtifacts`: concept/*; research/*.md; OWNER-INTAKE.md
- `outArtifacts`: research/COMPLETENESS.md (G-xx)
- гейт: ні
- `review.checklists`: [completeness.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: opus/high; 3 год; $12; стартова зрілість: 1
- примітки: Аудит над документами ДО сторінки (К-04); кожна прогалина G-xx: «кабінетно / людина / рішення власника»
- ескалація: прогалина «рішення власника» -> у пакет питань A-20c

### A-20c. Сторінка для власника (1 Artifact, 3 сторінки) — єдиний гейт концепції
- `raciR`: Власник продукту (A, гейт); BA (R)
- `executor`: any
- `skillRef`: flow-research:concept-presentation
- `access_profile`: base
- `inArtifacts`: research/*; concept/*; COMPLETENESS.md
- `outArtifacts`: research/owner-page/{index,competitors,rejected}.html; owner-page/PUBLISHED.md
- гейт: так: гейт концепції; Повернути -> A-20 / A-03b / A-03c (`gate.return_to`)
- `review.checklists`: [owner-page.md, edition-claims.md]; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: true (перший екран сторінки)
- ліміти: sonnet/high; 3 год; $12; стартова зрілість: 1
- примітки: Висновок і чесний вердикт про гроші на першому екрані; кожна теза веде на рядок дослідження; питання з рекомендацією й замовчуванням
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
- примітки: Справжні моделі `td_`, без `x_`/Studio; `prototype.fidelity: mock` -> `waiting_human` (К-23); EE — позначкою (К-06)
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
- `outArtifacts`: окрема демо-база зі зрізу `td_*` (без `x_`, К-11); опис бази — відкрите питання: шлях не визначено (див. «Відкриті питання»; чинний скіл пише `prototype/emulation.md`)
- гейт: ні
- `review.checklists`: []; `review.max_rounds: 2` (+1 контрольний)
- `params.sample`: false
- ліміти: sonnet/medium; 2 год; $8; стартова зрілість: 1
- примітки: Лише allow-list демо-баз; нічне скидання — лише за описом бази (відкрите питання про шлях)
- ескалація: немає зрізу A-21 -> `escalated` до BA

### A-23. Тест попиту: список / адреси / prep / results
- `raciR`: Контент-менеджер (R, prep: тексти); BA (A)
- `executor`: any; central (адреси)
- `skillRef`: flow-research:demand-test-runner (prep/results); flow-research:segment-selector (список/адреси)
- `access_profile`: outreach (prep/results); research-internal (список/адреси)
- `inArtifacts`: prototype-real/ (ACCEPTED); матеріали A-21c: video/*-16x9.mp4, video/*-9x16.mp4, SHOW.*, captions.yaml; research/OWNER-BRIEF.md, concept/features.md; mailing-list
- `outArtifacts`: demand-test/{plan.md, thresholds.md, landing.md, results.md}; mailing-list.csv (+ парний .md)
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
Картки посилаються на файли: `research.md`, `edition-claims.md` (A-03b, A-20, A-20c), `concept.md` (A-20), `completeness.md` (A-20b), `owner-page.md` (A-20c), `prototype.md` (A-21), `video-materials.md` (A-21c). Назви — контракт: файли створюються з цими іменами; при зміні назви правляться картки тут. Для кроків із `[]` чек-лист не потрібен.

## Відкриті питання
- A-22: шлях опису демо-бази зрізу (`outArtifacts`) не визначено; чинний скіл `demo-base-builder` пише `prototype/emulation.md`. Рішення — власник скіла; до того не вгадувати.
