# Статичний прогін flow-package-evolution (T6)

Дата: 2026-11-10. Рецензія раунд 1, виправлено: (1) hypercare.md фікстур monthly-happy і new-cycle: INC-011 «навчання» перенесено в «Запити в D-02» (rows=3, relevant=1), евал 1 тепер виконуваний; (2) new-cycle: попередній backlog.md доповнено до 4 REQ + SAL-D02-02 у «Без ID джерела», рішення внесено в джерела, входи в шапці виправлено, нова чернетка (+MIG-D02-01) прогнана `--phase draft --base`: усі BT PASS; (3) `extract_d02.py` не падає на відсутньому файлі/без аргументу (`file_found`); (4) `files` додано в кейси package-usage-metrics і product-decision-drafter.

| Скіл | Перевірка | Результат | Що виправлено / чому не запускалось |
|---|---|---|---|
| backlog-triage | py_compile `scripts/backlog_check.py`, `extract_d02.py` | OK | — |
| backlog-triage | `evals.json` json.tool | OK | — |
| backlog-triage | `backlog_check.py --selftest` | PASS | — |
| backlog-triage | `extract_d02.py` на monthly-happy | OK: INC-012 у hypercare і support-log (relevant), INC-013 «баг конфіг» relevant=false, INC-011 «навчання» (тепер у розділі D-02, relevant=false); воронка: SAL-D02-01/02 + рядок «ціна» без ID; fit-gap FG-D02-02/03 | — |
| backlog-triage | `extract_d02.py` на new-cycle, mode-b-no-d01, wrong-metrics, post-sign-violations | OK (MIG-D02-01 є в new-cycle; у mode-b один рядок FG-D02-03) | — |
| backlog-triage | `extract_d02.py` на no-metrics-injection | OK: обидва рядки без ID (no_id=1 у config-log і acceptance-act) -> «Без ID джерела» | — |
| backlog-triage | `backlog_check.py --phase post-sign` на post-sign-violations | збігається з евалом: BT-signed FAIL (INC-012 без версії), BT-lead FAIL (ld03 «у кастом»), BT-pii MANUAL | — |
| backlog-triage | `--phase draft --base` на еталонній новій чернетці new-cycle (base + MIG-D02-01, зібрана вручну, не в репо) | усі BT PASS (rerun, coverage, refusals, lead, draft-only) | Фікстуру виправлено (розбіжність була в ній, не «очікуваний FAIL»); повне складання беклога моделлю не запускалось |
| backlog-triage | evals_to_cli.py | generated=6; WARN «фікстури не розкладено» (штатно: розкладає runner) | — |
| backlog-triage | шляхи SKILL.md/evals.json | усі існують (references/* локальні; flow-core/references/*, flow-client-delivery/references/triage-routes.md — наявні у сусідніх плагінах) | — |
| odoo-version-migrator | json.tool evals.json; скриптів/фікстур немає | OK | — |
| odoo-version-migrator | evals_to_cli.py | generated=6, skipped=1 (stale-results: requires odoo-mcp:test) | кейс потребує живого Odoo MCP — не запускався. ВІДКРИТЕ: у prompt згадано фікстури odoo-src/odoo-src-19, їх у каталозі скіла немає (описані лише текстом) — кейси не відтворювані без них; питання до власника скіла/людини |
| odoo-version-migrator | шляхи | усі існують (changelog-template у flow-package-build, решта у flow-core) | — |
| package-usage-metrics | json.tool evals.json; yaml.safe_load для 11 yaml-фікстур (PyYAML 6.0.3) | OK | — |
| package-usage-metrics | evals_to_cli.py | generated=5; WARN «фікстури не розкладено» (штатно: розкладає runner) | — |
| package-usage-metrics | шляхи/фікстури | усі існують; скриптів у скіла немає | Збір метрик потребує Odoo MCP/живих баз — не запускався |
| product-decision-drafter | json.tool evals.json та `odoo-flow-aggregate.json` | OK | — |
| product-decision-drafter | evals_to_cli.py | generated=5; WARN «фікстури не розкладено» (штатно: розкладає runner) | — |
| product-decision-drafter | шляхи | усі існують (`flow-autocheck/scripts/autocheck.py`, `references/checks/{A-07,A-17,D-04,D-05}.yaml` у flow-core) | Скриптів у скіла немає; autocheck запускає runner |
| усі | `bash -n` | `*.sh` у плагіні немає | — |
| плагін | `claude plugin validate` (корінь і всі plugins/*) | passed | — |

Не запускалось (потрібні живий Odoo/GitHub/MCP/модель): повне складання backlog.md за кейсами 1, 3-6 backlog-triage; усі кейси odoo-version-migrator, package-usage-metrics (збір з Odoo), product-decision-drafter (генерація документів моделлю); runner-кроки наряду (гілка, PR).


Примітка: еталонна чернетка new-cycle збиралася вручну (не в репо): base + рядок REQ-B06-kl09-MIG-D02-01, порожній підпис, підпис 2026-11-12 у журналі запусків; `backlog_check.py --phase draft --mode a --base` без `--rerun` дає 10 BT PASS.
ВІДКРИТЕ питання до людини: фікстури odoo-src / odoo-src-19 для odoo-version-migrator відсутні.
