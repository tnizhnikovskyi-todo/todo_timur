# PLAN-0.3.0: «не рахуємо взагалі» й мінімум рішень (LESSONS §24)

Джерело: `_work/LESSONS-A21-real.md` §24 (людина 2026-11-12: «не считаем вообще»). Попередній канон — `IMPLEMENTATION-PLAN.md` §1;
де він суперечить §24, діє цей план (перелік скасованого — §2.10). Корінь шляхів: `plugins/` = `industry-flow-marketplace/plugins/`;
`<FC>` flow-core, `<FR>` flow-research, `<FE>` flow-package-evolution, `<FD>` flow-client-delivery, `<FB>` flow-package-build.

**Не чіпати** (рамка задачі): ціни й години для конкретного клієнта на впровадженні — логіку цін і годин у `package-fit-gap`,
`package-sow-builder`, ціни SOW, `pricing-rules.md`; оцінки трудомісткості збірки (A-08/A-10, `build-allocator`); урок §23
(двобічна перевірка стандарту, `prototype-builder`, `check_data_model.py`). `<FB>/**` і `prototype-builder` у 0.3.0 не змінюються
(нумерація BOX/SALES, яку вони читають, лишається стабільною — §2.6). Описи SKILL.md ≤ 900 символів. Не комітити.

---

## 1. Інвентар (grep по `plugins/`, 2026-11-12)

Шаблон пошуку: `окупн|TCO|business-case|вердикт про гроші|грош|K1|поріг доказ|правило доказ|≥2 тип|OWNER-BRIEF|BOX|SALES|COMPLETENESS|
рішення власника|питання власник|REJ-returned|REJ-dnr|G4а|evidence_gate|pricing|box_fixed_price|do_not_reject|human_target`.
Хибні збіги, які **не** правимо: `BOX` у `boundingBox`/`box-shadow` (`*.mjs`, `brand.css`), `SALES`/`Sales` як роль продавця
(`segment-selector`, `demand-test-runner`), «рішення власника» про ліцензії/AGPL/юриста (`editions-and-bridges.md`, `ci-pipeline-builder`,
`questionnaire-builder`, `c00-checklist.md`, `odoo-ecosystem.tpl.md`, `slice-plan-template.md`), «гроші/рахунки/податки» як зона
ризику коду (`routing-and-tag.md`, `cards/A-11.json`, `upgrade-template.md`), читачі `BOX §3–4/§4,§6` (`<FB>/master-data-template-builder`,
`<FD>/client-data-migrator`, `demo-base-builder`), `prototype-builder` (вже «годин і грошей немає»), шрифти `*.ttf`, `todo-logo.png`.

### 1.1 flow-core (WP-A)
| Файл | Що зробити |
|---|---|
| `references/flow-map.md` | Прибрати K1 (рядки A-03b `waiting_human` K1, «A-03c не ставити до K1», п.7 правил), гейт A-03c і режим `session`; A-03c `inventory → decide` без гейта; A-20c — єдиний гейт із вето (§2.7); A-07 — за §2.8; рядок A-20: «пише BOX, SALES, REJECTED, AI-DECISIONS» замість OWNER-BRIEF. |
| `references/step-cards.md` | Картки A-02b (≤5 хв, 6 пунктів), A-03b (без K1, `raciR` без власника, outArtifacts без K1.md, + рядки AI-DECISIONS), A-03c (без сесії/гейта/годин), A-20 (заголовок «Концепція + BOX + SALES + REJECTED + AI-DECISIONS», без G4/G4а, без `do_not_reject`), A-20b (out: розділ «Повнота» в AI-DECISIONS, без COMPLETENESS/OWNER-BRIEF), A-20c (in без COMPLETENESS; «без грошового блоку; список рішень AI, відповідь лише за незгоди»), A-07 (без business-case). |
| `references/step-skill-map.md` | A-03b без «K1 усередині»; A-20 без OWNER-BRIEF; A-02b режими `prepare → validate` (без `amend`); A-07 — за §2.8. |
| `references/naryad-format.md` | `resume` лише для зразка й `waiting_human` анкети (K1 прибрати); режими A-02b; `human_rounds` лишити як метрику. |
| `references/report-format.md` | `completeness` — лічильники з розділу «Повнота» AI-DECISIONS (не G-xx); нові поля `ai_decisions: <n>`, `vetoed: [AI-NN]`; прибрати згадки COMPLETENESS. |
| `references/id-patterns.md` | Прибрати `K1-Q\d+`, `G-\d{2}`, групи `G1…G4а`, тип доказу `owner-decision`; додати `AI-\d{2}` (AI-DECISIONS). `REJ-\d{3}` лишається. |
| `references/rejected-register.md` | Переписати на короткий формат «не робимо й чому» (§2.4): без груп, кругів, K1-повернень, журналу знятих рішень; правило сумісності для старих 8-колонкових таблиць. |
| `references/flow-state.md` | Без `COMPLETENESS.md`/G-xx; журнал `flow/decisions.md` — лише гейти й вето (§2.7). |
| `references/odoo-bridge.md` §4.1 | `human_substep` лише для анкети й зразка; K1 і сесію A-03c прибрати; `decisions-batch` → `veto-batch`. |
| `references/flow-step-run.md` | Рядок про «A-03b K1 (відповіді на K1-Q*)» прибрати; анкета ≤5 хв. |
| `references/review-checklists/*.md` (7) | Спільний рядок «minor, що впливає на рішення власника (гроші, обсяг, відкинуте, редакції)» → «(обсяг, відкинуте, редакції)». `research.md` п.2 «рамка окупності» — вилучити; п. про K1 — вилучити. `owner-page.md` — «вердикт про гроші» → «висновок без грошей; блок «Що вирішив AI і з яким ризиком»». `concept.md` — K1/G4а → «вето власника не відкидається знову»; п. про `do_not_reject` → `do_not_do`. `completeness.md` — під 14 пунктів і 3 ролі (§2.9). `edition-claims.md`, `prototype.md`, `video-materials.md` — лише спільний рядок. |
| `agents/flow-reviewer.md` | Той самий спільний рядок без «гроші». |
| `skills/flow-autocheck/scripts/check_rejected.py` | Переписати за §2.4: `REJ-exists`, `REJ-fields` (ID, що, чому), `REJ-count`; вилучити `REJ-dnr`, `REJ-returned`, `REJ-class-rule`, валідацію груп; `--intake`/`--k1` приймати й ігнорувати з WARN «застарілий аргумент 0.2.0». |
| `skills/flow-autocheck/scripts/check_intake.py` | Нова схема анкети (§2.1): блокуючі 6 ключів; `ambition.scope/evidence_gate`, `pricing.*`, `do_not_reject.*`, `rounds.human_target` — не вимагати; їх наявність = WARN «вилучено в 0.3.0». |
| `skills/flow-autocheck/scripts/autocheck.py` | Перевірки, що читають K1/OWNER-BRIEF/COMPLETENESS (inputs A-03b…A-21c, stale) — під новий набір файлів (§2.2). |
| `skills/flow-autocheck/scripts/check_facts.py` | Логіку не міняти (маркери чисел потрібні й без економіки); оновити лише docstring-приклади з OWNER-BRIEF. |
| `skills/flow-autocheck/references/checks/A-02b.yaml` | 6 блокуючих пунктів; ≤5 хв. |
| `…/checks/A-03b.yaml` | Без K1.md, без `--k1`; заголовки FUNCTIONAL-MAP без §3.2/§3.3/§4.3 (§2.6); новий пункт «AI-DECISIONS має рядки A-03b»; грошові маркери (§2.8) = FAIL. |
| `…/checks/A-03c.yaml` | Без гейта/сесії/`RU-hours`; рядки AI-DECISIONS від A-03c. |
| `…/checks/A-20.yaml` (24 збіги) | Без OWNER-BRIEF, K1, G4/G4а, `do_not_reject`, `re:гроші`; BOX §1 «склад», SALES §3 «ризики продажу»; новий FAIL на грошові маркери. |
| `…/checks/A-20b.yaml` (14) | Замість COMPLETENESS.md — розділ «Повнота» в AI-DECISIONS; 14 пунктів, 3 ролі, 1 коло. |
| `…/checks/A-20c.yaml` | Без «вердикту про гроші», без секції `money`; блок рішень AI; `check_rejected` без `--k1`. |
| `…/checks/A-21.yaml` | `check_rejected` без `--k1`; входи без OWNER-BRIEF. |
| `…/checks/A-07.yaml` | Без `business-case.md` (за §2.8). |
| `…/checks/{A-01,A-04,A-05,A-23,B-01,B-02,D-02,D-05}.yaml` | Прибрати `--intake`/`REJ-dnr` з команди `check_rejected`; B-02 — без `--business-case` і `FG-threshold`. |
| `…/checks/B-03.yaml` | `--business-case` лише «якщо файл є» (узгоджено з WP-B, §3). |
| `skills/flow-autocheck/references/checks.md`, `SKILL.md`, `evals/evals.json` | Таблиця перевірок без REJ-dnr/REJ-returned/K1; евал-кейси K1 вилучити, rejected/intake — під новий формат. |
| `skills/flow-orchestrator/SKILL.md`, `references/dispatch-rules.md`, `evals/evals.json` | Без K1-очікування і гейта A-03c; A-20c — вето-цикл (§2.7). |
| `skills/flow-state-keeper/SKILL.md`, `references/decisions-batch-and-lessons.md`, `references/params-registry.md`, `evals/evals.json` | Режим `decisions-batch` → `veto-batch` (лише рядки незгоди + рядок гейта); економічні параметри («ціна пакета», ключі business-case) з реєстру параметрів вилучити. Опис ≤900. |
| `skills/flow-step-runner/references/lessons-and-rounds.md` | Без K1-resume; `human_rounds` лишити. |
| `skills/skill-retro/references/open-questions.md`, `skills/eval-builder/references/gold/mebli.md` | Прибрати K1/«правило доказів» як актуальні; у gold — позначка «застаріло в 0.3.0». |

### 1.2 flow-research, ранні кроки й нижче за течією; flow-package-evolution; flow-client-delivery (WP-B)
| Файл | Що зробити |
|---|---|
| `<FR>/skills/owner-questionnaire/SKILL.md` | Анкета 6 пунктів (§2.1), ≤5 хв; режими `prepare → validate` (`amend` вилучити: правка анкети = новий `validate`); опис без «амбіція, поріг доказів, тарифи». |
| `…/references/owner-intake-template.md` | Новий YAML (§2.1): 6 питань + блок `defaults:` (AI-замовчування, власника не питаємо) + необов'язкове `tariffs`. |
| `…/references/questions-routing.md` | Лише 6 пунктів; усе інше — AI-замовчування, суттєві — рядок AI-DECISIONS. |
| `…/evals/evals.json`, fixtures `intake-ok/`, `intake-bad/` | Під нову схему; `OWNER-BRIEF.md` у фікстурах — видалити; `amend-git/` — видалити. |
| `<FR>/skills/industry-deep-dive/SKILL.md` | Прибрати K1 (контрольна точка, `waiting_human`, `K1.md`, G4а-рядки, REJ-returned), «рамку окупності з чутливістю до N», ≥2 типи як фільтр; підсегмент і кандидати на «не робимо» вирішує AI → рядки AI-DECISIONS; слабкий довід → «ризик, перевірити на пілоті». Опис ≤900 без «K1». |
| `…/references/run-plan.md` | Видалити крок K1 і перерахунок «години й окупність»; новий крок «рішення AI → AI-DECISIONS». |
| `…/references/pitfalls.md` | Розділ «Ціни й гроші» → «Ціни конкурентів — лише факт з URL, без розрахунків»; п. про `do_not_reject`/G4а — вилучити. |
| `…/references/review-criteria.md` | «немає рамки окупності» — вилучити. |
| `…/references/boundaries.md` | Без OWNER-BRIEF/G4а; A-03b пише FUNCTIONAL-MAP, REJECTED (короткий), рядки AI-DECISIONS. |
| `…/evals/evals.json`, fixture `k1-owner-returned/` | Кейси K1 і «≥2 типи відсікли» → кейс «слабкий довід = ризик, не відсів»; фікстуру видалити. |
| `…/scripts/check_depth.py` | Звірити з новими заголовками FUNCTIONAL-MAP (§2.6); правити лише якщо перевіряє §3.2/§3.3/§4.3. |
| `<FR>/skills/reuse-modules/SKILL.md` | Режими `inventory → decide` (AI), без сесії й гейта, без «годин адаптації проти розробки»; вердикти → рядки AI-DECISIONS; тригер «K1 закрито» → «A-03b завершено». |
| `…/references/reuse-template.md`, `…/references/session-materials.md` | Шаблон без `## Вплив на години`; `session-materials.md` — видалити. |
| `…/scripts/check_reuse.py`, `…/evals/evals.json`, fixtures `check_reuse-ok/`, `check_reuse-empty/` | Вилучити `RU-hours` і розділ «Вплив на години»; фікстури й евали — відповідно. |
| `<FR>/skills/past-projects-analyzer/SKILL.md`, fixture `mebli-r19-internal-raw-push/OWNER-INTAKE.md` | K1 → AI-DECISIONS; анкета — нова схема (ключі `todo_data` не змінюються). |
| `<FR>/skills/segment-selector/**` (лише збіги K1/`do_not_reject`; `references/open-questions.md`, `reference-clients-template.md`), fixture `icp-no-marking/OWNER-INTAKE.md` | Анкета — нова схема (`ambition.company_marking` лишається в `defaults`). Роль «Sales» не чіпати. |
| `<FR>/skills/industry-scoring/references/scoring-template.md` | Розділ відкинутого — короткий формат (§2.4). Фікстури не чіпати (сумісність). |
| `<FR>/skills/demand-test-runner/SKILL.md` | Ризик-план: статус `ризик:` і `вето власника` замість `owner-decision`/G4а/«1 тип джерел»; експеримент `price` — лише з `tariffs` власника, без `box_fixed_price` і без діапазонів AI; results — розділ «Рекомендація AI для A-07» (§2.8). Опис ≤900. |
| `…/references/{experiments-format,risk-plan-template,results-template,materials-a21c}.md` | Те саме; `forbidden-claims.md` і regex у `demand_tool.py` (заборона «окупність/ROI» у листах клієнтам) — **лишити**. |
| `…/scripts/demand_tool.py`, `…/evals/evals.json`, fixtures `risks-*/`, `rejected-*/` (`risk-plan.md` ×4) | `price` без `box_fixed_price`; фікстури — нові статуси. |
| `<FR>/skills/showcase-content/SKILL.md` | Рядок «Заперечення, TCO, демо-сценарій» → «Заперечення, демо-сценарій». |
| `<FE>/skills/product-decision-drafter/SKILL.md` | Режим A-07 `business-case.md` вилучити (§2.8); D-04 реліз-план — без «бюджету в грошах» (години як план робіт лишаються); D-05 — оцінка з SOW/fit-gap, не з business-case; тарифи з BOX §1 — лише цитата власника; відкинуте — короткий формат без `do_not_reject`/G4а/REJ-dnr. Опис ≤900. |
| `…/references/business-case.md` | Видалити. |
| `…/references/{release-plan,pilot-decision}.md`, `…/evals/evals.json`, fixture `decision-alternatives-tariffs/` | Без business-case; фікстуру видалити, кейси A-07 business-case — вилучити. |
| `<FE>/skills/backlog-triage/SKILL.md`, `…/references/backlog-format.md`, `…/evals/evals.json` | Відкинуте — короткий формат; без `do_not_reject`, G4а, REJ-dnr, `--intake`. `extract_d02.py`, `backlog_check.py` — лише docstring, якщо згадують G4а/`do_not_reject`. |
| `<FE>/skills/odoo-version-migrator/SKILL.md`, `…/references/db-migration-paths.md` | Редакція й хостинг — з `OWNER-INTAKE.editions` і `answers.yaml`, не з business-case. |
| `<FD>/references/client-edition-and-rejected.md` | Короткий формат відкинутого; без `do_not_reject`/G4а. |
| `<FD>/skills/package-fit-gap/SKILL.md`, `scripts/check_fit_gap.py`, `references/{fit-gap-template,autocheck-commands,agreement-check,open-questions}.md`, `evals/evals.json`, `evals/fixtures/build_repo.sh` | **Лише** §24 п.1: вилучити поріг «Відповідність пакету проти business-case» (`FG-threshold`, `--business-case` — приймати й ігнорувати), `--intake`/REJ-dnr, 8 колонок/G4а → короткий формат. Частку відповідності рахувати й показувати (без порогу). Години, ціни, класи fit/gap — **не чіпати**. |
| `<FD>/skills/package-sow-builder/SKILL.md`, `scripts/check_sow.py`, `references/pricing-rules.md` | **Лише входи**: `business-case.md` стає необов'язковим (A-07 його більше не пише); редакція/хостинг — з наряду й `answers.yaml`; умови пілоту еталонних — з `SALES §5`, якщо business-case немає. Правила цін і розбивку не змінювати. |

### 1.3 flow-research, концепція й шаблони (WP-C)
| Файл | Що зробити |
|---|---|
| `<FR>/skills/concept-mapper/SKILL.md` (53 збіги) | Виходи: `concept/*` + `research/{BOX,SALES,REJECTED,AI-DECISIONS}.md` + `facts.yaml`; OWNER-BRIEF не писати; без K1, G4/G4а, `do_not_reject`, `evidence_gate`, `pricing`, `hours.*`; BOX — лише склад коробок, тарифи — дослівно `tariffs` власника або «не задано»; брак доказів → `ризик: перевірити на пілоті`; вето власника з `flow/decisions.md` (режим `recalc`). Опис ≤900 без «K1/OWNER-BRIEF». |
| `…/scripts/check_concept.py` | `CM-research`: BOX §1–13, SALES §1–7, REJECTED (короткий), AI-DECISIONS — без OWNER-BRIEF; `CM-dnr` вилучити; новий `CM-money` (FAIL на маркери §2.8); `CM-facts` і `CM-scope` — без OWNER-BRIEF; `--k1` приймати й ігнорувати. |
| `…/references/{source-anchors.md,template/features.md}`, `…/evals/evals.json` | Статуси функцій (§2.5); кейси про K1/do_not_reject/G4а → «вето власника» і «слабкий довід = ризик». |
| `…/evals/fixtures/*` (9 тек) | У кожній: видалити `research/K1.md`, `research/OWNER-BRIEF.md`; `REJECTED.md` — короткий формат; `OWNER-INTAKE.md` — нова схема; для `check_concept-*` додати `research/AI-DECISIONS.md`; `check_concept-bad-dnr/` — видалити; новий `check_concept-bad-money/` (BOX із ціною/окупністю → FAIL). |
| `<FR>/skills/completeness-audit/SKILL.md` | Спростити (§2.9): 3 ролі, 14 пунктів без грошей і рішень власника, без тріажу human/decision і P1–P3, 1 коло критика; вихід — розділ «Повнота» в AI-DECISIONS, незакрите → рядки AI-NN «ризик, перевірити на пілоті»; COMPLETENESS.md не писати. Опис ≤900. |
| `…/references/roles-briefs.md`, `…/references/triage-rules.md` | 3 ролі без «власника продукту» й окупності; тріаж: `desk` (закрити зараз) / `ризик` (AI-NN). |
| `…/scripts/check_completeness.py`, `…/evals/evals.json`, fixtures `check_completeness-ok/`, `-bad/`, `incomplete-concept/` | Перевірки `CA-checklist` (1..14), `CA-gaps` (незакрите → AI-NN), `CA-money`, `CA-rounds` (≤1); `CA-owner`, `CA-p1` вилучити; фікстури COMPLETENESS.md → AI-DECISIONS.md; K1/OWNER-BRIEF у фікстурах — видалити. |
| `<FR>/skills/concept-presentation/SKILL.md` | Перший екран — висновок без грошей; секцію `money` вилучити; замість «≤5 питань з рекомендацією й замовчуванням» — блок «Що вирішив AI і з яким ризиком» (рядки AI-DECISIONS) і кнопка «Скопіювати мої заперечення» (лише відмічені рядки); 3 сторінки лишаються (L§12); rejected — короткий список. Опис ≤900 без «вердикт про гроші». |
| `…/references/{page-structure,copy-rules}.md`; `decisions-block.md` → перейменувати на `veto-block.md` | Секції `verdict`→`summary`, без `money`; копіювання = готові рядки вето для `veto-batch`. |
| `…/scripts/check_owner_page.py` | `CORE = [summary, pain, screens, ai-decisions, risks]`; `REJ_IDS` без груп (`not-doing`, без `g1…g4a`, `log`); новий `OP-money` (FAIL: id `money`, «окупн», «TCO», «вердикт про гроші»). |
| `…/evals/evals.json`, fixtures 7 тек (`index.html` ×6, `rejected.html` ×4, `competitors.html`, `BOX.md` ×6, `inputs-mebli/{OWNER-INTAKE,REJECTED}.md`) | Перебудувати з нового шаблону; `check_owner_page-bad` — додати грошовий блок як причину FAIL. |
| `<FR>/references/templates/OWNER-BRIEF.tpl.md`, `COMPLETENESS.tpl.md`, `K1.tpl.md` | Видалити. |
| `<FR>/references/templates/AI-DECISIONS.tpl.md` | Новий (§2.3). |
| `…/templates/BOX.tpl.md` | §1 «Коробки: склад функцій (що входить); тарифи — дослівно `tariffs` власника або «не задано»»; §1а лише якщо власник дав тариф ФОП; нумерація §2–§13 без змін. |
| `…/templates/SALES.tpl.md` | §3 «Вартість володіння» → «Ризики продажу (перевірити на пілоті)»; §5 без «знижка за кейс» (умови й критерій успіху); нумерація без змін. |
| `…/templates/FUNCTIONAL-MAP.tpl.md` | Вилучити §3.2 (вартість володіння), §3.3 (рамка окупності), §4.3 (owner-decision); §2.5 — «довід або `ризик: перевірити на пілоті`»; §5 — без «вердикт, гроші»; §7 → «Рішення AI — `AI-DECISIONS.md`». Решта номерів не змінюється. |
| `…/templates/REJECTED.tpl.md` | Короткий формат (§2.4), без груп і журналу. |
| `…/templates/DEPENDS.yaml` | Без OWNER-BRIEF, K1, COMPLETENESS; + AI-DECISIONS (§2.2). |
| `…/templates/facts.yaml` | Вилучити `pricing:`, ставку й години розробки. |
| `…/templates/README.md` | Таблиця шаблонів 0.3.0. |
| `…/templates/owner-page/index.html`, `rejected.html` | index: без «Вердикт і гроші» і «Гроші: коробка, TCO, окупність»; + секція `ai-decisions`; rejected — один список «не робимо й чому» без G1–G4а. |
| `<FR>/references/completeness-checklist.md` | 14 пунктів і 3 ролі (§2.9). |
| `<FR>/references/concept-templates.md` | Набір `research/{BOX,SALES,REJECTED,AI-DECISIONS}.md`; мітки відкритих питань без K1. |
| `<FR>/references/needs-sources-catalog.md` | «винесено у K1» → «рядок AI-DECISIONS (ризик)»; поріг джерел — орієнтир, не фільтр. |
| `<FR>/references/PAGE-CONTRACT.md` | «Скопіювати мої відповіді» → «Скопіювати мої заперечення»; без грошового блоку. |

### 1.4 Поза WP (координатор F, після злиття)
`plugins/*/.claude-plugin/plugin.json` (5 × `0.2.0 → 0.3.0`), `.claude-plugin/marketplace.json`, `README.md`,
`plugins/flow-research/README.md` (5 збігів), `plugins/flow-package-evolution/README.md` (1), примітка в `_work/LESSONS-A21-real.md` §24
«внесено в 0.3.0, PLAN-0.3.0».

---

## 2. Нова форма (спільний контракт — фіксує план; WP його не змінюють)

### 2.1 Анкета A-02b (`docs/industries/<галузь>/OWNER-INTAKE.md`, ≤5 хв)
Шість питань (`*` — блокуючі):
1. `editions*`: `ce|ee|both` (+ `demo_edition`, `ee_bridges` — AI-замовчування `ce`, `now`).
2. `icp*`: `{min_employees, legal_forms, light_tariff_fop}` (без `revenue_min`, якщо власник не дав).
3. `todo_data*`: `{allowed_sources, mode: read, internal_raw_storage: repo-sources, push_deidentified}`.
4. `brand*`: `{materials: todo|white_label, demo_client}`.
5. `materials*`: `{formats: [video_16x9, reels_9x16, mobile, one_pager], languages}`.
6. `do_not_do`: список «що точно не робимо» (може бути порожнім) → рядки REJECTED з причиною «рішення власника».
Необов'язково: `tariffs` (вільний текст; AI не рахує й не обґрунтовує — лише цитує в BOX §1).
Блок `defaults:` заповнює AI, власника не питає; **ключові шляхи для читачів не змінюються**: `market.*`, `ambition.{company_marking,
trials, sessions_a05_a06}`, `licenses.*`, `reuse.*`, `prototype.{fidelity, new_record_in_frame}`, `legal_ambiguous.*`, `rounds.{review_max,
review_control}`. Вилучено: `ambition.scope`, `ambition.evidence_gate`, `pricing.*` (у т.ч. `box_fixed_price`), `do_not_reject.*`,
`rounds.human_target`. Суттєве замовчування (редакція, ринок, облікова система) — рядок AI-DECISIONS.

### 2.2 Набір файлів галузі 0.3.0
- Видалено: `research/K1.md`, `research/OWNER-BRIEF.md`, `research/COMPLETENESS.md`, `docs/industries/<галузь>/business-case.md`.
- Лишаються: `research/{FUNCTIONAL-MAP, edition-claims, competitors-registry, competitors/*, REUSE, BOX, SALES, REJECTED, facts.yaml,
  DEPENDS.yaml, sources-log}`, `concept/{features,screens,scenarios}.md`, `research/owner-page/{index,competitors,rejected}.html`.
- Новий: `research/AI-DECISIONS.md` (пишуть A-03b, A-03c, A-20 — дописують свої рядки; A-20b — розділ «Повнота»; читає A-20c).
- `DEPENDS.yaml`: `AI-DECISIONS ← [OWNER-INTAKE, FUNCTIONAL-MAP, REUSE, concept/*]`; `BOX ← [concept/features, OWNER-INTAKE]`;
  `SALES ← [concept/*, facts.yaml]`; сторінка ← `[AI-DECISIONS, BOX, SALES, REJECTED, concept/*, facts.yaml]`; `prototype-real/*` ← `concept/*`.

### 2.3 `AI-DECISIONS.md` — «що вирішив AI і з яким ризиком»
```
# <галузь>: рішення AI (власник — вето)
## Рішення
| ID | Що вирішено | Рішення AI | Альтернатива | Ризик | Перевірка (пілот / A-23) | Крок | Статус |
| AI-01 | Підсегмент | … | … | … | … | A-03b | прийнято / вето <дата, посилання> |
## Повнота (A-20b)
| № | Пункт (1–14) | Статус: закрито / ризик | Де / AI-NN |
```
Правила: ≤15 рядків «Рішення»; лише рішення, де альтернатива міняє обсяг, редакцію, підсегмент, «не робимо», готові модулі, коробки;
дрібниці — ні. Без грошей. Відповіді власника не чекаємо: рядок має статус `прийнято` до вето.

### 2.4 Реєстр «не робимо й чому» (`<FC>/references/rejected-register.md`)
Мінімум колонок: `ID (REJ-NNN) · що не робимо · чому`; необов'язкова — `коли повернутись`. Без груп G1–G4а, кругів, K1-повернень,
журналу знятих рішень, `do_not_reject`. Місце — `REJECTED.md` або розділ `## Не робимо`. Сумісність: `check_rejected.py` знаходить
колонки за назвами (`ID`; `назва|що`; `причина|чому`), додаткові колонки ігнорує — тож старі 8-колонкові таблиці (fit-gap, scoring,
backlog) проходять без змін. Вето власника на позицію → рядок видаляється з реєстру й функція повертається в концепцію.

### 2.5 Доказовість
Правило «≥2 незалежні типи джерел» і поріг доказів скасовано. У MVP — усе, що галузі потрібно за досвідом ToDo, конкурентами й
джерелами болю. Статус функції в `features.md` / FUNCTIONAL-MAP: `довід: <типи>` або `ризик: перевірити на пілоті`; `вето власника <дата>`.
Тип `owner-decision` і групу `G4а` вилучено. `demand-test-runner` будує план перевірки з рядків `ризик:` і `вето власника`.

### 2.6 Стабільна нумерація (читачі поза WP)
- BOX §1–13 (+1а) — номери ті самі; §1 змінює зміст на «склад + тарифи власника дослівно» (читачі: `package-sow-builder` §1–2,
  `master-data-template-builder` §3–4, `client-data-migrator` §4/§6).
- SALES §1–7 — номери ті самі; §3 = «Ризики продажу» (читачі: `prototype-builder`, `showcase-content` §2/§6; `demand-test-runner` §4/§7).
- FUNCTIONAL-MAP: §3.2, §3.3, §4.3 вилучено без перенумерації; §3.4, §3.5, §4, §4.1, §4.2, §5 — ті самі.

### 2.7 Гейт A-20c і вето
Сторінка: висновок (що будуємо, для кого) → біль → сценарій → екрани з основою CE/EE → «Що вирішив AI і з яким ризиком» (AI-DECISIONS)
→ ризики → «не робимо». Власник: «Затвердити» (немає заперечень) або «Повернути» з рядками незгоди (кнопка «Скопіювати мої заперечення»
дає готові рядки `AI-NN: не згоден — <що замість>`). `flow-state-keeper` режим `veto-batch` пише в `flow/decisions.md` один рядок на
заперечення + рядок гейта. Далі A-20 `recalc` → A-20b → A-20c показує лише змінене. Окремих чернеток рішень, K1, сесій A-03c,
повторних кіл «питання власнику» немає. Інші гейти дослідження прибрано (A-03c); A-21 «зразок» і A-21/A-21c — приймання роботи
(якість кадру/матеріалів), а не рішення.

### 2.8 Гроші: що заборонено й що лишається
FAIL у `research/*`, `concept/*`, `owner-page/*`, `AI-DECISIONS.md`: `окупн`, `TCO`, `вартість володіння`, `business-case|бізнес-кейс`,
`вердикт про гроші`, `ROI`, `беззбитков`, `ставка розробки`, `годин.{0,20}(×|x|\*).{0,10}ставк`, секція `money`.
Дозволено: ціни конкурентів у `competitors-registry`/`competitors/*` як факт з URL (без розрахунків); цитата `tariffs` власника в BOX §1
з позначкою «вхід власника». A-07: `business-case.md` не пишеться; рішення «будуємо / ні / змінити концепцію» — розділ
«Рекомендація AI для A-07» у `demand/results.md` (A-23 results) за сигналами й порогами; власник — кнопка A-07 (вето). Ціни й години
клієнта на B-02/B-03 — без змін (рамка).

### 2.9 completeness-audit (A-20b), спрощений
Ролі (3, паралельно): галузевий експерт; архітектор Odoo 19 CE/EE; продавець ToDo + аудитор узгодженості.
14 пунктів: 1 сегмент/ICP; 2 болі з цитатами (слабкий довід → ризик); 3 ролі й день з життя; 4 наскрізний сценарій + варіанти;
5 функціональна карта з основою; 6 екрани MVP; 7 дані: довідники, старт, міграція; 8 інтеграції й формати; 9 звіти/KPI/дашборд;
10 права й нефункціональні; 11 склад коробок і план запуску (без цін); 12 заперечення й демо-сценарій; 13 ризики й план перевірки
(пілот/A-23); 14 «не робимо» + готові модулі ToDo. Вилучено: економіка (№17), тарифи (№13), рішення власника (№20), роль «власник
продукту», тріаж human/decision, P1–P3, друге коло. Desk-прогалини закриваються правкою документів у тому ж кроці; решта → AI-NN.

### 2.10 Скасовані або змінені канони IMPLEMENTATION-PLAN §1
К-01, К-02 — скасовано (§2.5). К-08 — замість журналу рішень лише вето (§2.7). К-17 — анкета 6 пунктів (§2.1). К-18 — A-03c без
сесії, гейта й годин. К-21 — OWNER-BRIEF не пишеться. К-24 — `G-xx`/COMPLETENESS прибрано (LSN лишається). 1.4: формат відкинутого
(§2.4), ID `K1-Q`/`G-xx`/`owner-decision` вилучено, анкета (§2.1), файли галузі (§2.2). Решта К-03…К-07, К-09…К-16, К-19, К-20,
К-22…К-23 — діють; К-25 → версії `0.3.0`.

---

## 3. Пакети робіт (власність файлів не перетинається)

| WP | Виключно свої файли | Файлів (оцінка) |
|---|---|---|
| **WP-A** flow-core: карта, картки, наряд, звіт, autocheck, чек-листи, оркестратор, стан | `<FC>/references/{flow-map,step-cards,step-skill-map,naryad-format,report-format,id-patterns,rejected-register,flow-state,odoo-bridge,flow-step-run}.md`, `<FC>/references/review-checklists/*.md` (7), `<FC>/agents/flow-reviewer.md`, `<FC>/skills/flow-autocheck/**`, `<FC>/skills/flow-orchestrator/**`, `<FC>/skills/flow-state-keeper/**`, `<FC>/skills/flow-step-runner/references/lessons-and-rounds.md`, `<FC>/skills/skill-retro/references/open-questions.md`, `<FC>/skills/eval-builder/references/gold/mebli.md` | ≈51 робочих + ≈41 фікстура (видалити `check_rejected-k1-*` ×6 тек, `k1-no-a03c/`; переписати `check_rejected-ok/bad`, `check_intake-*` ×3, `check_facts-*`/`check_privacy-ok` (OWNER-BRIEF → `concept/features.md`), `check_stale-*/make_repo.sh`, `minirepo/flow/{flow-map.md,ARTIFACTS.md,cards/A-03b,A-03c,A-20,A-20b,A-20c}.json`, `recalc-stale/state.json`, `chatter-gate.json`) ≈ **92** |
| **WP-B** flow-research ранні кроки й нижче за течією; flow-package-evolution; flow-client-delivery (лише §24 п.1 і формат відкинутого) | `<FR>/skills/{owner-questionnaire,industry-deep-dive,reuse-modules,past-projects-analyzer,segment-selector,demand-test-runner}/**`, `<FR>/skills/industry-scoring/references/scoring-template.md`, `<FR>/skills/showcase-content/SKILL.md`; `<FE>/skills/{product-decision-drafter,backlog-triage,odoo-version-migrator}/**`; `<FD>/references/client-edition-and-rejected.md`, `<FD>/skills/package-fit-gap/**`, `<FD>/skills/package-sow-builder/{SKILL.md,scripts/check_sow.py,references/pricing-rules.md}` | ≈50 робочих + ≈17 фікстур ≈ **67** |
| **WP-C** flow-research концепція й шаблони | `<FR>/skills/{concept-mapper,completeness-audit,concept-presentation}/**`, `<FR>/references/**` (у т.ч. `templates/**`, `completeness-checklist.md`, `concept-templates.md`, `needs-sources-catalog.md`, `PAGE-CONTRACT.md`) | ≈33 робочих + ≈60 фікстур ≈ **93** |
| **F** координатор (після злиття WP) | §1.4 | 9 |

Без змін у 0.3.0: `<FB>/**`, `<FR>/skills/prototype-builder/**` (урок §23 — окремо), `<FD>/skills/{client-data-migrator,client-help-bot,
package-upgrade-runner,runbook-executor,support-desk}/**`, `<FE>/skills/package-usage-metrics/**`, `<FC>/skills/{ci-pipeline-builder,flow-step-runner/SKILL.md}`.

**Порядок.** WP-A, WP-B, WP-C — паралельно (≤3), бо контракт §2 зафіксовано. Залежності лише через контракт: WP-C `check_concept.py`
викликає `check_rejected.py` (WP-A) — до злиття WP-A працює режим сумісності; WP-B `check_fit_gap.py` викликає `check_rejected.py` з
`--intake` — після WP-A аргумент ігнорується з WARN. B-03 (`check_sow --business-case`): WP-B робить аргумент необов'язковим, WP-A
пише його в YAML як «лише якщо файл є». Після злиття — інтеграційний прогін (§4.4), потім F.

---

## 4. Критерії готовності

### 4.0 Спільні для кожного WP
1. Змінено лише свої файли: `git -C /home/user/todo_timur status --short -- industry-flow-marketplace/plugins` — усі шляхи в межах WP.
2. Описи SKILL.md ≤900 символів:
   `python3 -I -c "import sys,re,pathlib;[print(len(m.group(1)),p) for p in pathlib.Path('plugins').rglob('SKILL.md') for m in [re.search(r'^description:\s*(.+?)\n[a-z_-]+:',p.read_text(),re.S|re.M)] if m and len(m.group(1))>900]"` — порожньо.
3. Усі `evals/evals.json` у своїх скілах — валідний JSON; жоден кейс не посилається на видалену фікстуру.
4. Свої скрипти `check_*.py` на своїх фікстурах дають очікувані PASS/FAIL з `evals.json`.
5. Грошовий grep по своїх файлах (крім рамки «не чіпати» й хибних збігів §1):
   `grep -rnE 'окупн|TCO|вартість володіння|business-case|бізнес-кейс|вердикт про гроші|K1|G4а|REJ-dnr|REJ-returned|evidence_gate|box_fixed_price|do_not_reject|OWNER-BRIEF|COMPLETENESS' <свої шляхи>` — лише рядки «застаріло в 0.3.0 / ігнорується» і заборонні regex.
6. Звіт ≤15 рядків: файли (кількість), що вилучено, що лишено свідомо, відкриті питання.

### 4.1 WP-A
- `flow-map.md`: немає K1, гейта A-03c, режиму `session`; A-20c — єдиний гейт дослідження з вето-циклом; A-07 за §2.8.
- `step-cards.md`/`step-skill-map.md`: A-02b (6 пунктів, ≤5 хв), A-03b, A-03c, A-20, A-20b, A-20c, A-07 — входи/виходи за §2.2.
- `check_rejected.py`: короткий формат PASS; таблиця без «чому» FAIL; старий 8-колонковий формат PASS; `--intake/--k1` → WARN, не FAIL.
- `check_intake.py`: анкета з 6 пунктами PASS; без `editions`/`icp`/`todo_data`/`brand`/`materials` — FAIL; старі ключі `pricing`/`evidence_gate` — WARN.
- `checks/*.yaml`: жодна команда не передає `--k1`; A-20/A-20c/A-03b мають перевірку грошових маркерів; A-20b — 14 пунктів.
- Оркестратор: евали без кейсу `k1-no-a03c`; є кейс «A-20c Повернути з вето → A-20 recalc».
- `flow-state-keeper`: режим `veto-batch`; у реєстрі параметрів немає економічних ключів.
- Чек-листи: жодного «гроші» в спільному рядку; `completeness.md` = 14 пунктів, 3 ролі.

### 4.2 WP-B
- Анкета: шаблон із 6 питаннями + `defaults:` + `tariffs`; `check_intake.py` (WP-A, після злиття) на `intake-ok` — PASS.
- `industry-deep-dive`: немає `waiting_human` для K1, `K1.md`, рамки окупності; рядки AI-DECISIONS від A-03b описано.
- `reuse-modules`: режими `inventory → decide`; `check_reuse.py` без `RU-hours`; евали проходять.
- `demand-test-runner`: ризик-план з `ризик:`/`вето власника`; `price` лише з `tariffs`; розділ «Рекомендація AI для A-07»; `forbidden-claims` збережено.
- `product-decision-drafter`: немає режиму A-07 business-case і файла `references/business-case.md`; D-04 без бюджету в грошах.
- `package-fit-gap`: немає `FG-threshold`; години/ціни/класи — диф лише в рядках порогу й формату відкинутого (`git diff` перевіряє координатор).
- `package-sow-builder`: `check_sow.py` без `--business-case` не падає; правила цін незмінні (диф `pricing-rules.md` — лише рядок джерела).

### 4.3 WP-C
- Видалено `OWNER-BRIEF.tpl.md`, `COMPLETENESS.tpl.md`, `K1.tpl.md`; є `AI-DECISIONS.tpl.md` за §2.3.
- BOX/SALES/FUNCTIONAL-MAP — нумерація за §2.6; у шаблонах немає TCO/окупності/ставки.
- `check_concept.py`: `check_concept-ok` PASS; `check_concept-bad-money` FAIL `CM-money`; немає `CM-dnr`.
- `check_completeness.py`: 14 пунктів, `CA-money`, ≤1 коло; фікстури без COMPLETENESS.md.
- `check_owner_page.py`: `-ok` PASS (секції `summary, pain, screens, ai-decisions, risks`); `-bad` FAIL `OP-money`; 3 сторінки.
- Шаблон `owner-page/index.html` без «Вердикт і гроші», «Гроші: коробка, TCO, окупність»; кнопка «Скопіювати мої заперечення».

### 4.4 Інтеграція (координатор, після злиття)
- Прогін усіх `check_*.py` на фікстурах усіх евалів п'яти плагінів — без FAIL, окрім очікуваних `*-bad`.
- Наскрізний grep §4.0 п.5 по `plugins/` — лише дозволені місця (рамка, хибні збіги §1, заборонні regex).
- `claude plugin validate plugins/<p>` для 5 плагінів; версії `0.3.0`; `marketplace.json` синхронно.

---

## 5. Відкриті питання до людини (не вирішувати в WP)
1. A-07: лишити кнопку «будуємо» (вето за рекомендацією AI в `demand/results.md`) чи переходити на A-08 автоматично? План: кнопка лишається.
2. A-21 «зразок», A-21/A-21c — приймання роботи кнопкою лишається (не «рішення»). Підтвердити.
3. `package-sow-builder`: вхід `business-case.md` стає необов'язковим, умови пілоту — з `SALES §5`. Підтвердити, що це не «ціноутворення».
4. BOX.md (13 розділів) і SALES.md (7 розділів) лишаються окремими файлами заради стабільної нумерації для читачів (`package-sow-builder`, `master-data-template-builder`, `client-data-migrator`, `showcase-content`, `demand-test-runner`). План: лишити (читачі не ламаються) чи звести в розділи `concept/features.md` у 0.4.0 з правкою читачів? Рішення людини.
5. A-20b (opus/high, 3 год, $12; 3 рецензенти + внутрішній критик + `flow-reviewer` з `completeness.md`) — три шари перевірки одного розділу «Повнота». Злити A-20b у приймання A-20 (`flow-reviewer` з чек-листом на 14 пунктів) чи лишити A-20b із `review.checklists: []` без внутрішнього критика? Рішення людини.
