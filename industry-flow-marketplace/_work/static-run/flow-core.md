# Статичний прогін flow-core

Дата: 2026-11-10. Без живого Odoo/GitHub/MCP. Тимчасові репо — у scratchpad, у пакеті нічого не залишено.

Загальні перевірки: `py_compile` усіх `*.py` (скрипти й фікстури), `bash -n` усіх `*.sh`, `json.tool` усіх `*.json`, `yaml.safe_load` усіх `*.yaml`/`*.yml` (PyYAML є), `evals_to_cli.py --self-test`.

| Скіл | Перевірка | Результат | Що виправлено / чому не запускалось |
|---|---|---|---|
| усі | py_compile, bash -n, json.tool | OK (усі файли) | `__pycache__` після прогону прибрано (tracked `state_export.cpython-313.pyc` не чіпали) |
| усі | yaml.safe_load | OK для 34 `checks/*.yaml` (step збігається з іменем файла, prim-и є в autocheck.py), dispatcher.yaml, answers*.yaml | `ci-pipeline-builder/references/ci-workflow-template.yml` не парситься: це шаблон з плейсхолдерами `{{...}}`, не YAML. Так задумано, не виправлялось |
| усі | `evals_to_cli.py --self-test`; генерація на evals.json кожного скіла | OK: eval-builder 7, flow-autocheck 6, flow-state-keeper 6, ci-pipeline-builder 4 (1 skip), flow-orchestrator 0/6 skip (`requires: odoo-mcp:test`), flow-step-runner 3 з 9 згенеровано, решта skip (`agents:registered` / `odoo-mcp:fixtures`) | WARN для ci-pipeline-builder: фікстури не розкладаються скриптом (за задумом) |
| flow-autocheck | `autocheck.py --selftest` | OK | |
| flow-autocheck | кейс a10-coverage (make_repo.sh + `--mode result`) | OK: FAIL, exit 1; ac-coverage AC-03, module-col AC-02, track-enum AC-05 (hybrid), AC-04 не FAIL, module-exists MANUAL, репо чисте | Додатково FAIL `install-section` (фікстура ALLOCATION.md без заголовків установки) - не суперечить expected_output, залишено |
| flow-autocheck | a18-diff-version | OK: diff-allowed-7 FAIL лише answers.yaml, route «контур A-14», version-eq FAIL з 4 значеннями, kit-vs-changelog FAIL (дозволено «можливий додатковий»), lint/clean-install MANUAL | |
| flow-autocheck | inputs-q43 (`--mode inputs`) | OK: input-path FAIL з обома шляхами, input-unmerged FAIL, conditional SKIP, external SKIP, FAIL | Додатково FAIL `input-missing` (файл відсутній на SHA) - логічний наслідок |
| flow-autocheck | spec-missing-incomplete | OK: INCOMPLETE, ERROR spec-missing, 2 MANUAL з check.how, exit 2 | |
| flow-autocheck | form-signature-by-ai (фікстури немає, зібрано ad hoc за описом) | OK: headings FAIL «Пункт про AI у договорі», signature-by-ai FAIL | Фікстури кейсу в пакеті немає - не додавалась (кейс описовий) |
| flow-autocheck | no-script-incomplete | не запускався: сценарій «скрипт видалено», поведінка моделі | |
| flow-orchestrator | setup.sh, JSON-стани, шляхи фікстур | OK; `autocheck --mode inputs` на A-12 із входами мінірепо (A-10/A-08/A-09) → PASS exit 0, `cat-file -e` для SPEC.md, answers.yaml, answers.example.yaml ok (збігається з README фікстур) | Усі 6 евалів потребують `odoo-mcp:test` (тестова база flow): не запускались |
| flow-step-runner | `build_context.py` на minirepo: нормальний збір (довірений/клієнт/anon → untrusted), `--toc`, код 4 (raw-notes без маркера), код 5 (бюджет, файли в out видаляються), код 2 (нема файла), `--sections` | OK з одним дефектом | **Баг:** `--sections` з ім'ям, якого немає серед `name` входів, мовчки ігнорувалось (код 0, без звуження). Тепер код 6 з помилкою. **Неоднозначність:** в евалі `context-over-budget-sections` ліва частина — `SPEC.md`; уточнено в evals.json, що це `name` входу з наряду |
| flow-step-runner | 9 евалів | 6 не запускались: `agents:registered` (субагент flow-executor), Odoo MCP (фікстури `odoo/*.json` — записані відповіді), PR/GitHub | Перелік: happy-path-both, stop-list-client-07, injection-and-retry, plugin-version-mismatch, maturity-3-audit-10th, cost-limit-exceeded |
| flow-state-keeper | `state_export.py`: check-ids (whitespace/ формат/ префікси), render, verify (ok; після ручної правки — exit 1), render --merge за двома частинами (cl-03 листопад + cl-04 грудень): flow/runs/2026-11.md і 2026-12.md збережено, verify ok:true; prune; stats на масиві runs (в т.ч. неповний запуск); PII у знімку → exit 2 без значення | OK | Помилка при виклику `stats` із файлом знімка замість масиву запусків (AttributeError) — некоректний ввід, формат у stats-queries.md п. 2 це визначає; лишено. Рендер без `--merge` після чого `--merge` дає втрату рядків — за задумом (SKILL: неповний знімок лише з --merge) |
| flow-state-keeper | 6 евалів | record-режими (run-incomplete-personal, gate-button-*, cursor-fallback) потребують Odoo/chatter; export-incremental і client-lifecycle-export — скрипт частина перевірена вище | Не запускались: частина «record» (живий Odoo flow) |
| ci-pipeline-builder | `check_ci.py` на шаблоні + REGISTRY.md з happy | OK: на нерозв'язаних плейсхолдерах FAIL (очікувано) | **Баг:** відсутній/неправильний шлях до ci.yml (`-h`, `--selftest`) давав traceback. Тепер `FAIL usage ...`, exit 2 |
| ci-pipeline-builder | евали happy-client-candidate, upgrade-odoo20-unsupported, no-run-tests-injection, probe-runs-live | не запускались: генерація ci.yml моделлю + тимчасовий git-репо з тегами, probe-runs-live — живий GitHub Actions | Фікстури happy/injection на місці, `run_tests.sh` синтаксично OK |
| eval-builder | `evals_to_cli.py` на всіх evals.json (див. вище) | OK | |
| eval-builder | шляхи фікстур з промптів евалів | **Відсутні** `evals/fixtures/weekly-obs/`, `init-gates/cards/A-14.json`, `incident/ai-incidents/cl-02.md`, `regress/` (4 евали: weekly-obs-to-red-case, init-gates-complete, incident-maturity, regress-regression-no-restore) | Не створювались: зміст (observations, картки, плагін-заглушки двох версій) вигадувати без узгодження; кейси описують «стан флоу-репо» як передумову. Позначено як залишок |
| усі | Шляхи references/scripts/fixtures із SKILL.md, references/*.md, evals.json | OK: `flow-core/references/*` (10 файлів), `references/*`, `scripts/*`, `evals/fixtures/*` існують | Посилання на `evals/INDEX.md`, `evals/<set>/...` — це артефакти цільового репо флоу (не плагіна), не перевірялись. `references/c03-lookup.md` у ci-contract.md — файл плагіна flow-package-build (поза задачею). У checks/*.yaml є посилання на скрипти й шаблони інших плагінів (flow-client-delivery, product-decision-drafter) — поза задачею |

## Що потребує живого Odoo/GitHub/MCP (не запускалось)
- flow-orchestrator: усі 6 евалів (`odoo-mcp:test`, тестова база flow).
- flow-step-runner: 6 з 9 евалів (`agents:registered`, `odoo-mcp:fixtures`, PR).
- flow-state-keeper: record-кейси (запис у задачі/chatter Odoo flow).
- ci-pipeline-builder: probe-runs-live (GitHub Actions), перевірка згенерованого ci.yml (потребує генерації моделлю).
- eval-builder: 4 кейси без фікстур (див. вище).

## Змінені файли
- `skills/ci-pipeline-builder/scripts/check_ci.py` - обробка нечитабельного шляху.
- `skills/flow-step-runner/scripts/build_context.py` - код 6 для невідомого name у `--sections`.
- `skills/flow-step-runner/evals/evals.json` - уточнення `SPEC.md` = name входу.
