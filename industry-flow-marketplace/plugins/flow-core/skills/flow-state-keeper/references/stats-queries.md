# Тижнева статистика для C-04

Джерело — дзеркальні поля запуску на задачах кроку (`state-model.md` §2). Технічні імена — `flow/ODOO_SCHEMA.md`. Усі виклики — `odoo_search_read` з `connection_id` бази `flow`.
**Суми й групування рахує скрипт, не модель.**

1. Домен: стадія задачі кроку ∈ {`stage.done`, `stage.escalation`, `stage.returned`, `stage.stopped`} (логічні; технічні назви й id — `ODOO_SCHEMA`) **і** `finished` у межах ISO-тижня
   **і** `run_status = повний`. Поля: `step, scope, attempt, result, skill_versions, cost_usd, tokens_in, tokens_out, returned_to, escalated_to`.
   «Неповні» (`run_status = неповний`) — окремий домен із `search_count`/кількістю, без сум.
2. Вибірку читати сторінками (`limit=200`, `offset`), кожну сторінку записати у файл `runs-pN.json` (масив об'єктів; `skill_versions` — словник).
3. Рахувати: `python3 -I scripts/state_export.py stats --runs runs-p1.json runs-p2.json …` → JSON `{incomplete_runs, rows[step, skill_version, week, attempts, escalations, returns, cost_usd, tokens_in, tokens_out]}`.
4. Відкрите питання: чи доступний `formatted_read_group` (Odoo 19; `read_group` застарів) через `odoo_execute` для `project.task` — **не перевірено** (немає джерел Odoo 19 у середовищі; перевіряє `boost:source-check` на офіційних документах). До перевірки — лише шлях зі скриптом; один робочий виклик `groupby/aggregates` додати сюди після підтвердження.
5. $ — лише статистика; порівнянь із «бюджетом» і залишків немає.
6. Результат — у `state.reconcile.stats` звіту C-02 і в `flow/state.md`; C-04 читає звідти.
