# Статичний прогін flow-client-delivery

| Скіл | Перевірка | Результат | Що виправлено / чому не запускалось |
|---|---|---|---|
| усі | py_compile scripts/*.py (8 файлів), bash -n smoke.sh, json.tool (усі *.json), yaml.safe_load (6 *.yaml) | OK | - |
| усі | `python3 -I plugins/flow-core/skills/eval-builder/scripts/evals_to_cli.py <evals.json> [--self-test]` на evals.json кожного скіла, плюс --self-test | OK (самотест OK; кейси з odoo-mcp/mock: SKIP, кейси з фікстурами: WARN «не розкладено» - за дизайном) | - |
| client-data-migrator | evals/smoke.sh (check_pii, check_migration) | 18/18 ok | - |
| support-desk | test_check_support.py (unittest) | 6 tests OK | - |
| support-desk | `python3 -I skills/support-desk/scripts/check_support.py <support-log.md фікстури> --mode intake\|sla-month [--routes references/triage-routes.md] [--other <2-й реєстр>]` на intake-happy, sla-month, injection | збігається з expected_checks: SD-close FAIL INC-103, SD-report FAIL INC-102, SD-dup FAIL t-dup, SD-route-table PASS | - |
| support-desk | фікстури з evals.json | дві теки не існували | створено evals/fixtures/no-contract/ (порожній support-log client-demo-04 + ТР без AC; SD-sla-source FAIL одразу, SD-ac з'явиться після рядка від AI); з кейсу stop-executor прибрано ключ fixtures (файлів не потребує) |
| runbook-executor | `python3 -I skills/runbook-executor/scripts/check_config_log.py --client-dir <фікстура> --package <пакет> --mode apply` на valid-log / no-readback | valid-log: без FAIL, rc 0; no-readback: readback FAIL CL-003, rc 1 - як в евалі | у evals.json шляхи `skills/runbook-executor/evals/fixtures/...` (в prompt і fixtures) замінено на `evals/fixtures/...` (відносно теки скіла, як у `scripts/`) |
| package-sow-builder | `python3 -I skills/package-sow-builder/scripts/check_sow.py fixtures/sow.md --mode main [--tag package/v1.2]` | усе PASS, SOW-sign MANUAL; SOW-tag PASS у тимчасовому репо з тегом package/v1.2 (у робочому репо тега нема - очікувано) | - |
| package-fit-gap | `python3 -I skills/package-fit-gap/scripts/check_fit_gap.py --client <к> --tag <тег> --base <sha> --repo <тимчасове репо з тегом>` | скрипт працює, JSON валідний; фікстури fit-gap.md (виходу AI) нема, тож перевірки FG-* по чужому/відсутньому fit-gap дають FAIL/SKIP - очікувано; точний перелік id зі статусами не зафіксовано (відкрито: повторити прогін і записати) | - |
| package-upgrade-runner | скриптів нема; evals.json валідний, evals_to_cli ок | 6 згенеровано, 2 SKIP (odoo-mcp) | - |
| усі | шляхи references/scripts/fixtures у SKILL.md, references/*.md, evals.json | усі існують (посилання на сусідні скіли/плагіни перевірено) | `config-runbook/references/config-log-template.md` - зовнішній плагін поза пакетом, не перевірялось |
| усі | `claude plugin validate .` (корінь пакета) і `claude plugin validate plugins/flow-client-delivery` | Validation passed (обидва) | - |

## Не запускалось (потрібен живий Odoo/MCP/GitHub)
- Кейси з `requires: odoo-mcp:*`: package-upgrade-runner (phase1-addons-skipped, phase1-code-deployed-not-updated, reconcile-b08a), package-sow-builder (main-happy, main-traps, addendum-*), runbook-executor (кейси apply/fix/reconcile), client-data-migrator (return-from-hypercare, odoo-trial-load, reconcile-resume).
- Кейси з mock Gmail/Fathom/Odoo (support-desk, package-fit-gap): потрібен runner із заглушками; для fit-gap немає еталонного fit-gap.md-виходу.


