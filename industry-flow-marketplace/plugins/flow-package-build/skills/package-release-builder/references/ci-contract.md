# Контракт CI (C-00 / C-03) для A-18

Єдине джерело входів workflow — `flow-core/skills/ci-pipeline-builder/references/ci-contract.md` (не копіюється). Скрипти C-00 і
workflow C-03 можуть бути ще не створені — тоді режим «вручну».

## Маппінг на inputs `ci.yml`
| Input ci.yml | Значення в A-18 |
|---|---|
| `sha` | HEAD гілки runner (`git.head`) — лише коли коміт уже запушено (запуск 2) |
| `package_tag` | тег-кандидат `$TAG` (`package/$VER`) |
| `odoo_version` | порожньо (із суфікса `-odoo<N>` тега; припущення AI, див. open-questions.md п. 8 / В-9) |
| `client` | порожньо (лише пакет) |
| `odoo_task` | id задачі Odoo з наряду |

Параметр dispatch API (не input `ci.yml`): `ref` — гілка кроку (`flow/<крок>-...`), уже на GitHub.
Режим установки — штатний прогін ci.yml. Входів `mode`/`prev_tag`/`instance` у контракті немає.

## Тест оновлення (R-11)
Підйом попереднього тега з демо-даними і `-u` до HEAD у штатному ci.yml не передбачено. Запит до `ci-pipeline-builder`: окремий job
або входи `prev_tag` + `instance`. До його появи R-11 = `NOT_RUN` (режим «вручну»), done не заявляти.

## Що вважається «однією командою»
Одна команда скрипта C-00 із тегом/ref як аргументом, що розгортає чисту базу Odoo 19, ставить усі модулі пакета, застосовує
конфіг, імпортує шаблони майстер-даних і завершується кодом 0. Кілька ручних кроків — FAIL R-09 «не одна команда».

## Smoke
Скрипт C-00 після установки; вміст визначає C-00. Скіл не придумує перевірок.

## Результат
Два запуски: у запуску 1 CI не стартує (коміту ще немає на GitHub), у запуску 2 — push/PR-прогін або dispatch з `ref`. Пошук: push/PR — check-run
на `head_sha`; dispatch — `actions_list` `event=workflow_dispatch`, `display_title` `ci <SHA>` (контракт C-03 «Статус на SHA»; `head_sha` dispatch-прогону не
дорівнює input-SHA) або commit status `context: ci`. `actions_get`: статус, conclusion; `get_job_logs` — лише `ERROR|CRITICAL|Traceback` (<= 30 рядків). У
CHANGELOG: id інстанса (для R-11), SHA прогону, витяг. Прогін не завершено до `timeoutMin` — `escalated`, run id у `memo`.

## Режим «вручну»
У `memo` — точні команди: (1) чиста база Odoo 19, (2) установка за тегом-кандидатом, (3) smoke, (4) для оновлення: підйом `PREV` з
демо-даними на окремому інстансі, `-u` до HEAD, smoke. R-09...R-11 — `NOT_RUN` до логу від людини; done не заявляти; `waiting_human` з `waiting_for` (лог від людини).
Місце логу: коментар у PR кроку (зміст лише в GitHub), позначений `ci-log A-18 <SHA>`. Resume (`params.resume.ci == pending`): прочитати цей коментар через `pull_request_read`, витяг <= 30 рядків (`ERROR|CRITICAL|Traceback`) занести в CHANGELOG окремим комітом лише `package/CHANGELOG.md`, R-09...R-11 = PASS з позначкою «вручну, лог від <роль>». Коментаря немає — знову `waiting_human`.
