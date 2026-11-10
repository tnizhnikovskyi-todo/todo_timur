# Крок → skill_ref → params.mode

Таблиця для `flow-orchestrator` (Крок 3): `skill_ref` у наряді береться з картки, але картки можуть містити застарілі або порожні `skillRef` (gap). До позначки C-00 «картки оновлено» (`c00-checklist.md`) діє таблиця, без порівняння з карткою. Після позначки розбіжність картки й таблиці → `skipped_precondition`, активність AI-інженеру.
Формат елемента: `<плагін>:<скіл>@<версія з plugin.json>`. **Перший елемент — скіл, що веде крок** (його виконує runner; скіл, що чужий наряду, відхиляє наряд); у `skill_ref[1:]` лишаються лише скіли-гейти (`flow-step-runner`, Крок 9д). Крок з кількома ведучими скілами — окремі рядки «крок / режим» (кожен наряд має одного ведучого). Режим — `params.mode`; «—» = ключа немає (режим із `params`/`naryad-format.md`).

| Крок | skill_ref (перший — ведучий) | params.mode / ключі |
|---|---|---|
| A-01 | flow-research:industry-scoring | — |
| A-04 | flow-research:past-projects-analyzer | — |
| A-05 | flow-research:segment-selector | `phase` 1\|2 (режим «еталонні клієнти») |
| A-07 | flow-package-evolution:product-decision-drafter | `mode: перша` (AI-частина: чернетка; людська задача рішення — без `skill_ref`) |
| A-09 | flow-package-build:questionnaire-builder | `first`\|`review` |
| A-12 | flow-package-build:config-as-code | `build`\|`fix`\|`new-version`\|`validate` |
| A-13 | flow-package-build:master-data-template-builder | — |
| A-14 | flow-package-build:gates-aggregator | `перевірка`\|`повернення`\|`нова-версія`\|`hotfix` |
| A-15 | flow-package-build:demo-base-builder | `перша`\|`нова-версія` (стенд пакета) |
| A-17 | flow-package-evolution:product-decision-drafter | `перша`\|`нова-версія`\|`hotfix` (AI-частина: чернетка; людська задача рішення — без `skill_ref`) |
| A-18 | flow-package-build:package-release-builder | `перша`\|`нова-версія`\|`hotfix`; `phase` `release`\|`tag` |
| A-20 | flow-research:concept-mapper | — |
| A-21 | flow-research:prototype-builder | — |
| A-22 | flow-package-build:demo-base-builder | режим «емуляція» (`перша`\|`нова-версія`) |
| A-23 / `prep`\|`results` | flow-research:demand-test-runner | — |
| A-23 / `список`\|`адреси` | flow-research:segment-selector | список розсилки — окремий наряд |
| B-01 | flow-research:segment-selector | режим «ліди» |
| B-02 | flow-client-delivery:package-fit-gap | — |
| B-03 | flow-client-delivery:package-sow-builder | `main`\|`addendum` |
| B-04 | flow-client-delivery:runbook-executor | застосувати |
| B-06 | flow-client-delivery:client-data-migrator | `main`\|`reconcile`\|`return` (`returned_from` — з наряду) |
| B-08a / звірка | flow-client-delivery:runbook-executor | звірка (перший наряд) |
| B-08a / збіжність | odoo19-mvp-build:track-convergence | другий наряд після звірки (`convergence.md`; вхід `config-drift.md`) |
| B-09 | flow-client-delivery:support-desk | `intake`\|`hypercare-close` |
| B-10 | flow-client-delivery:support-desk | `intake`\|`sla-month` |
| B-11 / `phase: 0`\|`1`, `pilot` | flow-client-delivery:package-upgrade-runner | — |
| B-11 / `reconcile` | flow-client-delivery:runbook-executor | звірка |
| B-11 / `addendum` | flow-client-delivery:package-sow-builder | додаток SOW (фаза 0) |
| B-13 | flow-client-delivery:runbook-executor | виправлення (б) |
| C-03 | flow-core:ci-pipeline-builder | — |
| C-04 | flow-core:eval-builder | `weekly`\|`init`\|`regress` |
| C-07 | flow-core:eval-builder | `incident` |
| D-01 | flow-package-evolution:package-usage-metrics | `collect`\|`report` |
| D-02 | flow-package-evolution:backlog-triage | `a`\|`b`\|`c`\|`d` |
| D-03 | flow-package-evolution:odoo-version-migrator | `prepare`\|`verify` |
| D-04 | flow-package-evolution:product-decision-drafter | `нова-версія` (AI-частина: чернетка; людська задача рішення — без `skill_ref`) |
| D-05 | flow-package-evolution:product-decision-drafter | — (`pilot/decision.md`; AI-частина: чернетка; людська задача рішення — без `skill_ref`) |

Не через цю таблицю: C-01 (`flow-orchestrator`) і C-02 (`flow-state-keeper`) працюють за розкладом/подіями без наряду; C-06 — це сам runner; людські кроки (A-02, A-06, B-08b, B-08d, B-12, C-00, C-08) скіла не мають. Кроки, закриті скілами організації (A-03, A-08, A-10, A-11, A-16, A-19, B-05, B-07, B-08c) — `skillRef` з картки.
