# Пошук прогону C-03

C-03 тестує пакет і модулі; A-14 тести не запускає, лише читає статус.

## Алгоритм
1. `BASE = git log -n1 --format=%H SHA_GATES -- package/addons/ package/config/` (останній коміт, що змінював код/конфіг).
2. Кандидати: `git rev-list BASE^..SHA_GATES`, від найновішого. Якщо `BASE` кореневий — лише `BASE..SHA_GATES` і `BASE`.
3. MCP `github` `actions_list method=list_workflow_runs resource_id=ci.yml workflow_runs_filter={branch: <repo.branch або repo.base_branch>, status: completed}`
   (`perPage` ≤ 30). Прогін знаходити так (контракт `flow-core/skills/ci-pipeline-builder/references/ci-contract.md`, «Статус на SHA»):
   push/PR — `head_sha` == кандидат; dispatch (`event=workflow_dispatch`) — SHA кандидата в `display_title` (`run-name` = `ci <SHA> …`), **не** `head_sha`
   (у dispatch-прогону він дорівнює HEAD гілки, а не `inputs.sha`). Спершу перевірити, що відповідь MCP містить `display_title`; немає — запасний шлях:
   commit status `context: ci` на SHA (якщо MCP читає статуси), інакше «збій виконання: прогін не знайдено», не вгадувати. Деталі — `actions_get`.
   Логи падіння — лише помилки/`tail`.
4. Результат:
   - завершений `success` -> `SHA_C03`, run id, статус. `SHA_C03` ≠ `SHA_GATES` -> «предок без змін у addons/config: так».
   - `failure`/`cancelled` -> C-03 червоний, вердикт не APPROVE; правка (код за шляхом тесту), посилання на прогін.
   - немає прогону або `in_progress` -> `actions_run_trigger method=run_workflow workflow_id=ci.yml ref=<repo.branch> inputs={sha: SHA_GATES}`;
     прогін шукати за `event=workflow_dispatch` і SHA у `display_title`. Очікування — Monitor/until-loop на статус у межах `timeout_min`; середовище не дозволяє —
     «збій виконання: C-03 in_progress, run id …», повтор у межах `maxAttempts`.
5. workflow_dispatch лише якщо жодного прогону для кандидатів немає (захист від зависання на комітах лише з master-data/CHECKS).

## Що писати в CHECKS.md
`SHA_C03`, run id, статус (success / failure / cancelled), посилання на прогін, «предок без змін у
addons/config: так/ні». Окремим полем від `SHA_GATES`.

## Контракт з ci-pipeline-builder і відкриті питання
- Очікується input `sha` у workflow_dispatch `ci.yml` (В-2). Без нього запуск можливий лише на гілку; тоді
  записати це в `memo` і не вважати прогін гілки прогоном для `SHA_GATES`, якщо head_sha інший.
- Чи має C-03 job тест-імпорту `package/master-data/` — визначає C-03 (В-1); якщо job є, його результат
  береться звідси, інакше тест-імпорт робить A-14 через `odoo-mcp` у `test-pkg-<пакет>`.
- Назву workflow C-03 брати з наряду/`ci.yml`; не вгадувати.
