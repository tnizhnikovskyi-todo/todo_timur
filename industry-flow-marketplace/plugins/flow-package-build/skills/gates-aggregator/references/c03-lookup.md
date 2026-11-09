# Пошук прогону C-03

C-03 тестує пакет і модулі; A-14 тести не запускає, лише читає статус.

## Алгоритм
1. `BASE = git log -n1 --format=%H SHA_GATES -- package/addons/ package/config/` (останній коміт, що змінював код/конфіг).
2. Кандидати: `git rev-list BASE^..SHA_GATES`, від найновішого. Якщо `BASE` кореневий — лише `BASE..SHA_GATES` і `BASE`.
3. MCP `github` `actions_list` (workflow C-03, фільтр `head_sha`) для кандидатів; деталі — `actions_get`.
   Логи падіння — лише помилки/`tail`.
4. Результат:
   - завершений `success` -> `SHA_C03`, run id, статус. `SHA_C03` ≠ `SHA_GATES` -> «предок без змін у addons/config: так».
   - `failure`/`cancelled` -> C-03 червоний, вердикт не APPROVE; правка (код за шляхом тесту), посилання на прогін.
   - немає прогону або `in_progress` -> `actions_run_trigger` (workflow_dispatch C-03 з input `sha=SHA_GATES`),
     потім опитування ~кожні 2 хв у межах `timeout_min`. Не дочекались -> «збій виконання: C-03 не завершився».
5. workflow_dispatch лише якщо жодного прогону для кандидатів немає (захист від зависання на комітах лише з master-data/CHECKS).

## Що писати в CHECKS.md
`SHA_C03`, run id, статус (success / failure / cancelled), посилання на прогін, «предок без змін у
addons/config: так/ні». Окремим полем від `SHA_GATES`.

## Контракт з ci-pipeline-builder і відкриті питання
- Очікується input `sha` у workflow_dispatch `ci.yml` (В-2). Без нього запуск можливий лише на гілку; тоді
  записати це в `memo` і не вважати прогін гілки прогоном для `SHA_GATES`, якщо head_sha інший.
- Чи має C-03 job тест-імпорту `package/master-data/` — визначає C-03 (В-1); якщо job є, його результат
  береться звідси, інакше тест-імпорт робить A-14 через `odoo-mcp` у `test-pkg-<id>`.
- Назву workflow C-03 брати з наряду/`ci.yml`; не вгадувати.
