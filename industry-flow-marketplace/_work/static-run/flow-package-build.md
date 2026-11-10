# Статичний прогін: flow-package-build (T6)

Дата: 2026-11-10. Файли скілів не змінювались: розбіжностей не знайдено. Згенеровані `__pycache__` прибрано.

| Скіл | Перевірка | Результат | Що виправлено / чому не запускалось |
|---|---|---|---|
| усі (6) | `python3 -m py_compile scripts/*.py` | OK: єдиний скрипт `master-data-template-builder/scripts/check_master_data.py` | — |
| усі (6) | `bash -n` усіх `*.sh` (12 у фікстурах demo-base-builder) | OK | — |
| усі (6) | `python -m json.tool` усіх `*.json` | OK (6 evals.json, fields.json x3, installed.json) | — |
| усі (6) | `yaml.safe_load` усіх `*.yaml` (PyYAML є) | OK (answers.yaml, answers.example.yaml) | — |
| master-data-template-builder | `check_master_data.py --dir evals/fixtures/script-td-root/master-data` | OK: MD-td = FAIL (файл у корені), rc=1, решта PASS, MD-cols/req SKIPPED, як у asserts кейсу `td-and-code-allocation` | — |
| master-data-template-builder | синтетичний набір у scratchpad + `--fields happy-furniture/fields.json` | Скрипт ловить: MD-readme (відсутні заголовки), MD-td, MD-pii (email, vat), MD-ref (висячі td_md.*), MD-cols (невідома колонка/модель) | — |
| master-data-template-builder | кейси `happy-furniture`, `config-priority-and-pii` (повний прогін агента) | НЕ запускалось: потрібен агент і `odoo-mcp:test` (test-pkg-furniture-01) для MD-import/MD-modules; фікстури (ТР, ALLOCATION, CONFIG, fields.json, installed.json) на місці й валідні | — |
| demo-base-builder | кейси без Odoo (`stand-happy-profiles` тощо) | НЕ запускалось: скриптів скіла немає; перевіряє агент + `tools/odoo/*.sh` проти живого стенду Odoo. Фікстури на місці (манифести, шаблони, 6 stand-скриптів) | — |
| config-as-code | скрипти | Скриптів у скілі немає (`apply.py`/`validate.py` у SKILL.md — планові артефакти пакета, не скіла). Кейси `mode-validate`, `no-test-base`, `settings-related-readback` вимагають `odoo-mcp:test` | не запускалось |
| gates-aggregator | скрипти/кейси | Скриптів немає; фікстури — лише README-описи (runner/агент розкладає git-репо за описом). Потрібні GitHub MCP (`actions_list`) і живі гейти | не запускалось |
| package-release-builder | скрипти/кейси | Скриптів немає; кейс `release-second-version` вимагає github + `odoo-mcp:test` | не запускалось |
| questionnaire-builder | скрипти | Скриптів немає (автоперевірка — `flow-core:flow-autocheck`, `checks/A-09.yaml`); кейси без Odoo виконує агент | не запускалось окремо |
| усі (6) | `eval-builder/scripts/evals_to_cli.py <evals.json> --out <tmp>` | rc=0 для всіх: config-as-code (9 evals), demo-base-builder (7), gates-aggregator (10), master-data-template-builder (3), package-release-builder (generated 5, skip 1), questionnaire-builder (6/0). SKIP за `requires: odoo-mcp:test`; WARN «фікстури не розкладено» — штатна поведінка конвертера (фікстури розкладає runner) | — |
| усі (6) | шляхи `references/`, `scripts/`, `evals/fixtures/`, `files[]` з SKILL.md, references/*.md, evals.json | Усі існують (references скілів, `../../references/*` плагіна, `flow-core/references/*`, `flow-core/skills/ci-pipeline-builder/references/ci-contract.md`, flow-autocheck). Не існують лише свідомо «планові»: `flow-package-build/references/module-skeleton.md`, `flow-package-build/references/changelog-template.md` (у SKILL.md прямо сказано, що спільного немає), `apply.py`/`validate.py` | — |
| усі (6) | `claude plugin validate` (маркетплейс і кожен plugins/*) | Passed | — |

## Потребує живого Odoo/GitHub/MCP (не запускалось)
- master-data-template-builder: MD-import, MD-modules (`odoo-mcp:test`, test-pkg-furniture-01).
- demo-base-builder: `tools/odoo/{install,import,snapshot,restore,clean,smoke}.sh` на реальному стенді; емуляція.
- config-as-code: усі кейси з `odoo-mcp:test`.
- gates-aggregator: `actions_list`/`actions_get` (C-03), вердикти гейтів.
- package-release-builder: workflow dispatch C-03, `get_tag`, Odoo test.
