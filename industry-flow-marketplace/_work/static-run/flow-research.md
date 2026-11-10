# Статичний прогін: flow-research (T6)

Дата: 2026-11-10. Робочі копії фікстур — у scratchpad, у пакеті нічого не змінено. Виправлень не знадобилось.

| скіл | перевірка | результат | що виправлено / чому не запускалось |
|---|---|---|---|
| усі 6 | py_compile (5 скриптів + 6 допоміжних .py фікстур), bash -n (2 .sh), node --check (.mjs), json.tool (27 .json), yaml.safe_load (2 naryad.yaml) | OK | — |
| усі 6 | `claude plugin validate plugins/flow-research` | OK | — |
| усі 6 | evals_to_cli.py на evals.json (з `--out`) | OK, без помилок; WARN «фікстури не розкладено» і SKIP за `requires` — штатні | runner розкладає фікстури; кейси з odb-catalog, odoo-mcp:test, playwright, web:odoo-docs скіпаються |
| усі 6 | шляхи references/scripts/fixtures у SKILL.md і evals.json | усі існують (references резолвляться в skill/, flow-research/references/, flow-core/references/) | `flow-research/references/demand-thresholds.md` у demand-test-runner SKILL.md — свідомо відсутній (задокументований залишок, не помилка); у segment-selector fixtures a05-round2, b01-leads, a23-mailing відсутні за задумом (`fixtures_note`: готує запускач, кейси на живому odb-catalog) |
| concept-mapper | check_concept.py на reference-concept/concept + входи з happy-furniture | CM-files/src/quote/feat/signal/count/trace/pii PASS; CM-ids, CM-scope SKIP (немає --base) | Без `--input` CM-src = FAIL (очікувано: джерела поза входами) |
| concept-mapper | кейси happy-furniture, invented-feature, thin-sources, return-from-a23 | не запускались: потрібна модель (генерація концепції) | лише агентний прогін |
| industry-scoring | build_expected.py -> expected-scoring.md / expected-top10.json / metrics.json | байт-в-байт збігаються з наявними | — |
| industry-scoring | check_scoring.py на expected-scoring.md (+param, metrics, snapshot 2026-08, exclude) | усе PASS, SC-repro MANUAL (штатно) | — |
| industry-scoring | no-criterion, snapshot-date-unknown, data-traps, connection-id | не запускались: агентні, data-traps/connection-id потребують живих odb-catalog / odoo-mcp | — |
| past-projects-analyzer | check_past_projects.py --self-test | PASS | — |
| past-projects-analyzer | setup_repo.sh для 6 кейсів | OK, git-репо збираються | — |
| past-projects-analyzer | check_past_projects.py на happy-two-modes/expected/past-projects.md | усе PASS після підстановки `<sha>` з setup_repo.sh | `<sha>` в expected — плейсхолдер за задумом (README фікстури) |
| past-projects-analyzer | інші 5 кейсів | не запускались: документ створює агент; потребують AIKB/Fathom MCP | — |
| demand-test-runner | make_repo.sh clean/frozen-edit/pii-input/inject-calls/shallow-missing | OK, start_sha друкується | — |
| demand-test-runner | demand_tool.py aggregate на results-happy | збігається з expected_output кейсу results-happy (4 компанії, Р3=2/Р4=2, ≥Р3=4, out_of_period=1, поза розсилкою 99999999, featmap, F-09 поза картою, 5 гарячих) | — |
| demand-test-runner | demand_tool.py pii: clean = rc 0; pii-input = email/phone/ПІБ у calls.md:3, rc 1 | OK | — |
| demand-test-runner | demand_tool.py honesty / utm на синтетичних ok/bad файлах | ok -> rc 0, bad -> rc 1 | complexity окремо не проганявся; синтетичні файли honesty/utm не збережено; prep-фікстур у пакеті немає (prep-кейси описані лише в prompt) - залишок |
| demand-test-runner | prep-кейси, results-frozen/-pii/-start-sha-missing (агентна частина) | не запускались: потрібна модель | — |
| prototype-builder | assemble.mjs на happy-mebli-mini/expected та imitation-calc/screens.json | OK (3 екрани, 1 calc) лише з demo-data.json, підкладеним з happy-mebli-mini/expected (в imitation-calc власного data/demo-data.json немає; без нього FAIL ENOENT) | — |
| prototype-builder | check.mjs на зібраному happy-mebli-mini | VP-screens/complexity/imitation/data/size PASS; VP-files/scenarios/video/offline FAIL — очікувано: немає README.md, video/, e2e-прогону | прогін e2e і відео потребує playwright:chromium — не запускався |
| prototype-builder | record.mjs, кейси complexity-underestimate-trap (web:odoo-docs) | не запускались | потрібні Playwright/chromium, веб |
| segment-selector | скриптів і фікстур немає; evals_to_cli OK | 4 з 5 кейсів SKIP (odb-catalog) | потрібен живий odb-catalog; not-central-stop — агентний |

Підсумок: помилок скриптів, фікстур чи шляхів не знайдено; змін у файлах пакета немає.


Доповнення за зауваженнями: evals_to_cli для industry-scoring - generated=0 (три кейси happy-top10, no-criterion, snapshot-date-unknown SKIP за точним `requires: fixtures`, штатно; їх розкладає runner). У prototype-builder кейси role-gap-returned, imitation-calc-column, complexity-underestimate-trap дістали ключ `fixtures` (тепер fixtures_pending і WARN). Залишок поза задачею: додати `__pycache__/` у .gitignore маркетплейсу; перевірки py_compile запускати з PYTHONDONTWRITEBYTECODE=1 або на копії.
