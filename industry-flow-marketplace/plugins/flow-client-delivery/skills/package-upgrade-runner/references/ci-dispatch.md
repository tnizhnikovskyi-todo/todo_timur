# Запуск CI для B-11

Власник контракту — `flow-core:ci-pipeline-builder`, файл `flow-core/skills/ci-pipeline-builder/references/ci-contract.md`
(читати його, не копіювати). Витяг нижче; розбіжність із ним — перевага ci-contract.md.

## Dispatch (`workflow_dispatch`, `actions_run_trigger`)
| Input | Значення |
|---|---|
| `package_tag` | тег-кандидат = тег A-18 (завжди явно; порожньо CI візьме тег з REGISTRY) |
| `client` | ідентифікатор клієнта за DATA_POLICY |
| `odoo_version` | 19 або N із суфікса `-odoo<N>` тега |
| `sha` | `git.head` наряду (HEAD гілки кроку) |
| `odoo_task` | id задачі Odoo |
Режим upgrade (попередній тег -> новий -> smoke) і розбіжність із `package-release-builder/references/ci-contract.md`
(`tag_candidate`, `mode`, `prev_tag`) — В-2.

## Пошук прогону
dispatch-прогін шукати за SHA у `run-name`/`display_title` (`actions_list`, `event=workflow_dispatch`), не за `head_sha`
(правило — ci-contract.md). Брати прогін, запущений цим кроком (тег і SHA збігаються).

## Критерій «зелено» для B-11
- усі модулі пакета: pass;
- кожен `td_<к>_*`: окремий job є і pass; skipped або відсутній job -> FAIL (U-05);
- логи: лише `get_job_logs` з хвостом або grep `FAIL|ERROR`.
Не завершився за таймаут -> U-05 = PENDING, run id у `upgrade-log.md`, результат `waiting_human` (role Тімлід), `attempt`
не витрачається; «Передача в B-12» не заповнюється.
