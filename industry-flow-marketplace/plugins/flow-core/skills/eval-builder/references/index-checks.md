# Автоперевірки eval-builder

Скриптів `scripts/index_check.py` і `scripts/pii_scan.py` ще немає. Хто що виконує (`SKILL.md`, «Автоперевірка»):
- шість механічних (`skills-covered`, `source-filled`, `incident-case`, `no-pii`, `json-schema`, `scope-evals-only`) — під runner'ом лише `flow-autocheck`
  за `checks/<крок>.yaml`; на ручному запуску AI-інженера — скіл сам (`by: self`);
- п'ять власних (`gates-covered`, `obs-closed`, `escalations-covered`, `init-complete`, `regress-recorded`) — завжди скіл, окремими рядками `checks[]`.
Інструменти: grep, `jq`, `python3 -I`.
Статуси: PASS / FAIL / SKIP (перевірка не для цього режиму) / MANUAL.

| id | Режими | Перевірка |
|---|---|---|
| `skills-covered` | усі | множина скілів флоу (крок 1) входить у рядки INDEX; кожен зі статусом з `index-format.md` |
| `source-filled` | усі | «Джерело евала» непорожнє, формат `failureMode картки <код>` / `observation <файл>` / `incident <id>`; код `^[ABCD]-\d{2}[a-z]?$` |
| `gates-covered` | init і далі | 5 гейтових скілів мають >=1 кейс із `source` failureMode A-14/B-05/B-04 |
| `obs-closed` | weekly | кожне `open` спостереження тижня має кейс або причину в таблиці 3 |
| `escalations-covered` | weekly | кожен крок зі статистики C-02 за порогом має рядок у таблиці 4; статистики немає — SKIP з причиною («статистика відсутня») |
| `init-complete` | init | для оброблених скілів кількість кейсів = кількість failureModes їхніх карток |
| `regress-recorded` | regress, weekly | для кожної нової версії/моделі з наряду є рядок прогону (дата, модель, версія, pass/fail) |
| `incident-case` | incident | у `evals/<крок>/evals.json` є кейс `source: incident <id>`; `maturity_proposals` є, якщо умова пониження виконана (це й є `done` C-07) |
| `no-pii` | усі | у diff `evals/` немає: e-mail, телефону, IBAN `UA\d{27}`, ЄДРПОУ (8 цифр у контексті «код/ЄДРПОУ»), «Прізвище І. І.», токенів/паролів, ідентифікаторів з `clients/REGISTRY.md` |
| `json-schema` | усі | кожен `evals/**/evals.json` валідний за `evals-format.md` (`python3 -I -c 'import json,sys; json.load(open(sys.argv[1]))'` + обов'язкові поля) |
| `scope-evals-only` | усі | `git diff --name-only <base>...HEAD` — лише `evals/` |

Регекси `no-pii` — єдине джерело `flow-core/references/pii-patterns.md` (режим `strict`; той самий файл у `flow-core:flow-autocheck`). Для `evals/` збіг — FAIL
незалежно від `client_data` наряду (у autocheck при `client_data: none` це може бути WARN). Скрипт `pii_scan.py` не створено — виконувати вручну за таблицею.
`maturity` не змінено: `git diff` по `flow/cards/` порожній.
