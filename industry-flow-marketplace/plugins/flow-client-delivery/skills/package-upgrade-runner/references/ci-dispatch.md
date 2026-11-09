# Запуск CI для B-11

Джерело контракту — `ci-contract.md` кроку C-03 (власник — `flow-core:ci-pipeline-builder`). На момент написання цього
файлу контракт не зафіксований, тому нижче — очікування скіла; звірити з `ci.yml` у репо (Відкрите питання В-2).

## Dispatch (`workflow_dispatch`, `actions_run_trigger`)
| Input | Значення |
|---|---|
| `package_tag` | тег-кандидат = тег A-18 (завжди явно) |
| `client` | ідентифікатор клієнта |
| `sha` | HEAD гілки кроку |
| `odoo_task` | id задачі Odoo |
Назви inputs і режим upgrade (попередній тег з демо-даними -> новий -> smoke) — не підтверджені.

## Пошук прогону
Через `actions_list`/`actions_get` за SHA і run-name; брати прогін, запущений цим кроком (тег і SHA збігаються).

## Критерій «зелено» для B-11
- усі модулі пакета: pass;
- кожен `td_<к>_*`: окремий job є і pass; skipped або відсутній job -> FAIL (U-05);
- логи: лише `get_job_logs` з хвостом або grep `FAIL|ERROR`.
Не завершився за таймаут -> U-05 = PENDING, run id у `upgrade-log.md`.
