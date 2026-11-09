# Нічна збірка пакета скілів — звіт менеджера (2026-11-10)

## Результат
- Маркетплейс `industry-flow`: 5 плагінів, 28 скілів, 627 файлів. `claude plugin validate` — без помилок (маркетплейс і кожен плагін; є лише попередження ICON_MISSING).
- Усі 28 скілів пройшли цикл «рецензія Fable → виправлення Sonnet» до стану без blocker/major (1–4 раунди на скіл). Залишки — minor.
- Пакет у цілому: 4 раунди пакетної рецензії Fable + виправлення Sonnet, потім контрольна рецензія; останній major (доступ до проду в D-01) закрито.

| Плагін | Скіли |
|---|---|
| flow-core | flow-step-runner, flow-orchestrator, flow-state-keeper, flow-autocheck, ci-pipeline-builder, eval-builder; агенти flow-executor, flow-reviewer |
| flow-research | industry-scoring, past-projects-analyzer, segment-selector, concept-mapper, prototype-builder, demand-test-runner |
| flow-package-build | questionnaire-builder, config-as-code, master-data-template-builder, gates-aggregator, demo-base-builder, package-release-builder |
| flow-client-delivery | package-fit-gap, package-sow-builder, runbook-executor, client-data-migrator, support-desk, package-upgrade-runner |
| flow-package-evolution | package-usage-metrics, backlog-triage, product-decision-drafter, odoo-version-migrator |

## Рішення менеджера за ніч
1. Об'єднання (концепція Fable): support-first-line + support-sla-tracker → support-desk; release-planner + pilot-review → product-decision-drafter; reference-client-selector + segment-lead-builder → segment-selector; config-drift-checker → режим «звірка» runbook-executor; config-as-code-builder ≡ config-as-code.
2. Не скіли: odoo-flow-bridge і data-policy-builder → спільні references flow-core; ui-scenario-runner скасовано (q31, Odoo tours); client-help-bot відкладено (сервіс у базі клієнта, не скіл Claude Code).
3. Спільні контракти винесено в `plugins/*/references/` окремим агентом (міст Odoo, карта флоу, стан, формат наряду з `params`, звіт з `waiting_human`, формати майстер-даних тощо) — бо агенти-виправлювачі обмежені текою свого скіла.
4. Агенти flow-executor/flow-reviewer (обмежені інструменти для виконання кроку) перенесено в `plugins/flow-core/agents/`.
5. eval-builder (C-04) — лише звичайний крок під flow-step-runner; додано перевірки C-04 для flow-autocheck.
6. D-01: AI не звертається до проду клієнта взагалі; метрики — з вивантаження агрегатів від Тімліда (шаблон `package-usage-metrics/references/export-template.md`), без файлу — `waiting_human`.

## Збої вночі (вирішено)
- ~00:20 — ліміт витрат організації зупинив обидва процеси; після скидання ліміту продовжено з останньої рецензії (без повторного написання скілів).
- ~00:25 — перезапуск контейнера; стан відновлено за журналом, продовжено 5 незавершених скілів.

## Що лишилось (не блокує розробку)
- 34 відкриті питання до людини — README пакета, розділ «Відкриті питання до людини» (дані й безпека, модель виконання/C-00, продукт). Головне: технічні імена полів/стадій Odoo визначає C-00 (`flow-core/references/c00-checklist.md`); скрипти `tools/odoo/` ще не існують.
- «Відомі обмеження» в README: частина `description` > 900 символів (скоротити перед каталогом), немає іконок плагінів, частина кроків без yaml-специфікацій автоперевірки, евали не запускались (лише статична валідація).
- Minor: у фікстурах евалів package-usage-metrics лишилась колонка «alias прод-підключення» в `state.md` (без доступу до бази).

## Установка
```bash
claude plugin marketplace add ./industry-flow-marketplace
claude plugin install flow-core@industry-flow
```
(аналогічно flow-research, flow-package-build, flow-client-delivery, flow-package-evolution). Для каталогу організації — опублікувати репозиторій маркетплейсу, у нарядах фіксувати `плагін:скіл@0.1.0`.

Робочі файли: `_work/CONCEPT.md` (концепція), `_work/plans/` (плани Opus), `_work/PACKAGE_REVIEW.md` (пакетна рецензія).
