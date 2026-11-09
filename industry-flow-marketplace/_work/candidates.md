# Кандидати в скіли (з карток флоу; gap = скіла немає в каталозі)

Опис кроків і контекст флоу: /tmp/claude-0/-home-user-todo-timur/5a7cf5c8-af6a-5a14-b383-5c1efcffbc70/scratchpad/cards/context.md; картки: …/scratchpad/apply/final/<id>.json (поле code).

- `backlog-triage` — кроки D-02: запити B-02/B-09/B-10 + метрики D-01 → чернетка backlog
- `ci-pipeline-builder` — кроки C-03: перелік модулів пакета й клієнтів + правила C-05 →
- `client-data-migrator` — кроки B-06: план + вивантаження + шаблони A-13 → завантажені довідники й звіт звірки)
- `client-help-bot` — кроки B-07: відповідає на питання користувачів за конфігом і матеріалами клієнта
- `concept-mapper` — кроки A-20: з briefing, past-projects і протоколів генерує карту функцій, екрани й сценарії «день з життя»
- `config-as-code` — кроки A-12, C-03: 
- `config-as-code-builder` — кроки A-12: 
- `data-policy-builder` — кроки C-05: типи даних клієнтів і минулих проєктів, договір/SOW → package/DATA_POLICY
- `demo-base-builder` — кроки A-15, A-22: модулі, конфіг, майстер-дані, анкета, план → працюючий стенд, answers
- `eval-builder` — кроки C-04: зауваження з observations/ або failureMode картки + статистика кроків → евал у evals/<скіл>/
- `flow-orchestrator` — кроки C-01: стан в Odoo + картки + карта флоу → постановка задач у чергу Odoo, передача шляхів, активності на гейті й людському кроці, облік спроб/лімітів/ескалацій (build-
- `flow-state-keeper` — кроки C-02: результати кроків + рішення людини → Odoo (стан флоу
- `gates-aggregator` — кроки A-14: вердикти п'яти гейтів + статус C-03 → CHECKS
- `odoo-version-migrator` — кроки D-03: пакет версії N + release notes N+1 → пакет N+1 + скрипти міграції
- `package-sow-builder` — кроки B-03: fit-gap (B-02) + пакет (A-18) → sow
- `package-upgrade-runner` — кроки B-11: git-тег + доробки + тестова база/копія → upgrade-log
- `package-usage-metrics` — кроки D-01: агрегати з баз клієнтів + перелік моделей і меню → package/metrics/<YYYY-MM>
- `past-projects-analyzer` — кроки A-04: ТР, транскрипти, код + sources
- `pilot-review` — кроки D-05: факти пілота → чернетка рішення
- `prototype-builder` — кроки A-21: генерує клікабельний HTML у стилі Odoo 19 і записує відео Playwright
- `questionnaire-builder` — кроки A-09: ТР з VP-xx → questionnaire
- `reference-client-selector` — кроки A-05: сегмент (A-02), параметри (A-03), odb-catalog, CRM → reference-clients
- `release-planner` — кроки D-04: беклог + бюджет → чернетка плану версії
- `segment-lead-builder` — кроки B-01: сегмент (A-02) + odb-catalog → список лідів у CRM
- `support-first-line` — кроки B-09, B-10: читає мітку Gmail, заводить звернення з часом, чернетки відповідей)
- `support-sla-tracker` — кроки B-10: звернення + SLA з договору супроводу + support-log
- `runbook-executor` — крок B-04: виконує runbook налаштувань у тестовій базі клієнта через odoo-mcp, пише config-log (додано менеджером з рішень сесії)
- `config-drift-checker` — крок B-11: порівнює config-log з фактичною тестовою базою через odoo-mcp (дрейф, втрачений конфіг) (додано менеджером з рішень сесії)
- `master-data-template-builder` — крок A-13: шаблони майстер-даних з прикладами + перевірка тест-імпортом (додано менеджером з рішень сесії)
- `industry-scoring` — крок A-01: скоринг галузей за odb-catalog (додано менеджером з рішень сесії)
- `flow-step-runner` — крок C-06: цикл AI-кроку: бере наряд із задачі Odoo, звіряє скіл@версію, виконує, автоперевірка, PR, звіт у задачу Odoo (додано менеджером з рішень сесії)
- `odoo-flow-bridge` — крок C-01/C-02: читання/запис нарядів, звітів, табеля й журналу в задачах Odoo через odoo-mcp (спільна основа для агентів) (додано менеджером з рішень сесії)
- `demand-test-runner` — крок A-23: лендинг, розсилка за сегментом, аналіз відповідей і сигналів попиту (додано менеджером з рішень сесії)

Примітки менеджера: `config-as-code` і `config-as-code-builder` — один скіл. `ui-scenario-runner` скасовано (рішення q31: Odoo tours у CI через скіл testing). Наявні скіли каталогу (tr-*, odoo19-mvp-build, odoo19-implementation, discovery-*, sales-prep, boost) НЕ переписуємо — лише посилаємось на них.