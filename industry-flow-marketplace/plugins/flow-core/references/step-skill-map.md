# Крок → skill_ref → params.mode

Таблиця для `flow-orchestrator` (Крок 3): `skill_ref` у наряді береться з картки, але картки можуть містити застарілі або порожні `skillRef` (gap). До позначки C-00 «картки оновлено» (`c00-checklist.md`) діє таблиця, без порівняння з карткою. Після позначки розбіжність картки й таблиці → `skipped_precondition`, активність AI-інженеру.
Формат елемента: `<плагін>:<скіл>@<версія з plugin.json>`. **Перший елемент — скіл, що веде крок** (його виконує runner; скіл, що чужий наряду, відхиляє наряд); у `skill_ref[1:]` лишаються лише скіли-гейти (`flow-step-runner`, Крок 9д). Крок з кількома ведучими скілами — окремі рядки «крок / режим» (кожен наряд має одного ведучого). Режим — `params.mode`; «—» = ключа немає (режим із `params`/`naryad-format.md`).

| Крок | skill_ref (перший — ведучий) | params.mode / ключі |
|---|---|---|
| A-01 | flow-research:industry-scoring | — |
| A-02b | flow-research:owner-questionnaire | `mode: prepare`\|`validate` (анкета власника 6 пунктів, `waiting_human` між `prepare` і `validate`; правка анкети = новий `validate`) |
| A-03b | flow-research:industry-deep-dive | — (без K1; рішення AI -> рядки AI-DECISIONS) | `recalc` (`params.mode`) |
| A-03c | flow-research:reuse-modules | один наряд без режимів (`## Інвентар` у `REUSE.md`; без сесії й гейта; рішення AI — рядки AI-DECISIONS) |
| A-04 | flow-research:past-projects-analyzer | — |
| A-05 | flow-research:segment-selector | `phase` 1\|2 (режим «еталонні клієнти») |
| A-07 | — (людська задача, без `skill_ref`) | Кнопка-вето за розділом «Рекомендація AI для A-07» у `demand/results.md` (його пише A-23 results) |
| A-09 | flow-package-build:questionnaire-builder | `first`\|`review` |
| A-12 | flow-package-build:config-as-code | `build`\|`fix`\|`new-version`\|`validate` |
| A-13 | flow-package-build:master-data-template-builder | — |
| A-14 | flow-package-build:gates-aggregator | `перевірка`\|`повернення`\|`нова-версія`\|`hotfix` |
| A-15 | flow-package-build:demo-base-builder | `перша`\|`нова-версія` (стенд пакета) |
| A-17 | flow-package-evolution:product-decision-drafter | `перша`\|`нова-версія`\|`hotfix` (AI-частина: чернетка; людська задача рішення — без `skill_ref`) |
| A-18 | flow-package-build:package-release-builder | `перша`\|`нова-версія`\|`hotfix`; `phase` `release`\|`tag` |
| A-20 | flow-research:concept-mapper (+ під-скіл flow-research:completeness-audit у кінці кроку, не окремий крок) | — (BOX, SALES, REJECTED, AI-DECISIONS; `params.mode: recalc` — за вето власника з `flow/decisions.md`) |
| A-20c | flow-research:concept-presentation | — (гейт концепції; `params.mode: recalc`) |
| A-21 | flow-research:prototype-builder | `params.sample: true` (зразок) \| повний обсяг; `defaults.prototype.fidelity: mock` не підтримується (К-23) |
| A-21c | flow-research:showcase-content | — (виконавець — Контент-менеджер, `executor: any`) |
| A-22 | flow-package-build:demo-base-builder | база зрізу для гарячого ліда (`перша`\|`нова-версія`) |
| A-23 / `prep`\|`results` | flow-research:demand-test-runner | `mode: prep`\|`results` |
| A-23 / `список`\|`адреси` | flow-research:segment-selector | `mode: список`\|`адреси`; список розсилки — окремий наряд, створюється раніше за `prep` (див. `flow-map.md`) |
| B-01 | flow-research:segment-selector | режим «ліди» |
| B-02 | flow-client-delivery:package-fit-gap | — |
| B-03 | flow-client-delivery:package-sow-builder | `main`\|`addendum` |
| B-04 | flow-client-delivery:runbook-executor | застосувати |
| B-06 | flow-client-delivery:client-data-migrator | `main`\|`reconcile`\|`return` (`returned_from` — з наряду) |
| B-07 / бот `prepare` | flow-client-delivery:client-help-bot | `mode: prepare`; лише якщо в SOW є розділ бота; другий наряд кроку B-07 після матеріалів навчання (`user-training-builder` — перша частина, скіл організації, `skillRef` з картки) |
| B-07 / бот `answer` | flow-client-delivery:client-help-bot | `mode: answer`, `period`; лише якщо в SOW є розділ бота й `prepare` = done; `odoo_connections` додатково `prod-ro-<клієнт>` (q37, лише читання). Відкрито: що створює наряд `answer` «на період» (розклад чи рішення PM) — скіл не визначає, до рішення наряд створює вручну PM/Підтримка |
| B-08a / звірка | flow-client-delivery:runbook-executor | `mode: звірка` (перший наряд) |
| B-08a / збіжність | odoo19-mvp-build:track-convergence | `mode: збіжність`; другий наряд після звірки (`convergence.md`; вхід `config-drift.md`) |
| B-09 | flow-client-delivery:support-desk | `intake`\|`hypercare-close` |
| B-10 | flow-client-delivery:support-desk | `intake`\|`sla-month` |
| B-11 | flow-client-delivery:package-upgrade-runner | `phase` 0\|1, `pilot`; звірка (`params.reconcile: true`) і додаток SOW виконує сам ведучий у своєму запуску й гілці: `runbook-executor` і `package-sow-builder` — у ключі `called_skills` наряду (версії з `plugin.json`), не в `skill_ref[1:]`, окремих нарядів немає |
| B-13 | flow-client-delivery:runbook-executor | виправлення (б) |
| C-03 | flow-core:ci-pipeline-builder | — |
| C-04 | flow-core:eval-builder | `weekly`\|`init`\|`regress` |
| C-07 | flow-core:eval-builder | `incident` |
| C-08R | flow-core:skill-retro | `mode: daily`\|`event` |
| D-01 | flow-package-evolution:package-usage-metrics | `collect`\|`report` |
| D-02 | flow-package-evolution:backlog-triage | `a`\|`b`\|`c`\|`d` |
| D-03 | flow-package-evolution:odoo-version-migrator | `prepare`\|`verify` |
| D-04 | flow-package-evolution:product-decision-drafter | `нова-версія` (AI-частина: чернетка; людська задача рішення — без `skill_ref`) |
| D-05 | flow-package-evolution:product-decision-drafter | — (`pilot/decision.md`; AI-частина: чернетка; людська задача рішення — без `skill_ref`) |

Не через цю таблицю: C-01 (`flow-orchestrator`) і C-02 (`flow-state-keeper`) працюють за розкладом/подіями без наряду; C-06 — це сам runner; людські кроки (A-02, A-06, B-08b, B-08d, B-12, C-00, C-08) скіла не мають. Кроки, закриті скілами організації (A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07 (навчання; бот — рядки вище), B-08c) — `skillRef` з картки.

## Профіль доступу наряду (`access_profile`)
Оркестратор ставить у наряд ключ `access_profile` за **ведучим скілом** (`skill_ref[0]`); runner запускає виконавця з однойменним агентом (`naryad-format.md`). Ключа немає = `base`. Профілі не складаються: одному наряду — один агент з мінімальним `tools:`.

| access_profile | агент | додаткові інструменти (до читання odoo-mcp) | ведучі скіли |
|---|---|---|---|
| `base` | `flow-core:flow-executor` | немає | усі, не названі нижче |
| `mail` | `flow-core:flow-executor-mail` | Gmail: читання й `create_draft`; Drive: читання файлу за id з наряду (договір для support-desk) | client-help-bot, support-desk |
| `research` | `flow-core:flow-executor-research` | odb-catalog, AIKB, Fathom, Drive — лише читання; WebSearch/WebFetch; без власної ERP/Gmail/Unitalk (К-22) | concept-mapper, questionnaire-builder, package-fit-gap |
| `research-internal` | `flow-core:flow-executor-research-internal` | як `research` + читання внутрішніх даних ToDo за `todo_data` анкети (alias `own-erp`, лише читання; Unitalk/Fathom/Gmail — лише читання); сирі спостереження — лише в `research/sources/` (К-07, К-19) | industry-deep-dive, past-projects-analyzer, reuse-modules, industry-scoring, segment-selector |
| `content` | `flow-core:flow-executor-content` | лише файли репо галузі й наряд (контент; клас `commercial`, без баз Odoo, без `internal-raw`) | showcase-content |
| `outreach` | `flow-core:flow-executor-outreach` | odb-catalog, Drive (читання) + Gmail `create_draft` | demand-test-runner |
| `drive` | `flow-core:flow-executor-drive` | Drive: лише читання файлів з наряду | package-sow-builder, package-usage-metrics, client-data-migrator |
| `repo` | `flow-core:flow-executor-repo` | GitHub MCP — лише читання (+ `get_tag`, `list_tags`); WebFetch (лише документація Odoo 19) | ci-pipeline-builder, gates-aggregator, package-release-builder, package-upgrade-runner, odoo-version-migrator, prototype-builder (GitHub-читання модулів REUSE + WebFetch документації Odoo 19; Bash/Odoo/Playwright/ffmpeg виконує runner за «КОМАНДИ:», К-22), skill-retro |

Наряд із `prod-ro-<клієнт>` (лише client-help-bot, q37) має профіль `mail` і не отримує запису в Gmail/Drive/GitHub — таких інструментів у цього агента немає. Дії, яких виконавець не має (`actions_run_trigger`, запис файлу в Drive, `Bash (git)` у скілі), він віддає runner'у рядком «КОМАНДИ:» (`executor-brief.md`). Скіл, чия інструкція потребує конектора поза профілем наряду, зупиняється `escalated` (не шукає обхідних шляхів). Якщо ведучий скіл не в таблиці — `base`; помилку профілю виправляє AI-інженер у цій таблиці.
