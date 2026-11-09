# Тижнева статистика для C-04

Джерело — дзеркальні поля запуску на задачах кроку (`state-model.md` §2). Технічні імена — з `flow/ODOO_SCHEMA.md` (C-00).
Усі виклики — `odoo_search_read` з `connection_id` бази `flow`.

1. Домен: стадія задачі кроку ∈ {Готово, Ескалація, Повернено, Зупинено} **і** `finished` у межах тижня (ISO) **і** `run_status = повний`.
   Поля: `step, scope, attempt, result, skill_versions, cost_usd, tokens_in, tokens_out, returned_to, escalated_to`.
2. Групування — на боці скіла за `step × skill_version × тиждень`: кількість спроб, ескалацій, повернень (за `returned_to`),
   сума `cost_usd`, `tokens_in/out`. Відкрите питання: чи підтримує `odoo_execute` `read_group` у Odoo 19 (у 19 перейменовано на
   `_read_group`/`formatted_read_group`) — перевірити `boost:source-check`; до цього групувати вручну порціями ≤200 записів.
3. «Неповні» запуски рахувати окремо (кількість, без сум); їх не доповнювати.
4. $ — лише статистика; порівнянь із «бюджетом» і залишків немає.
5. Результат — у `state.reconcile.stats` звіту C-02 і в `flow/state.md`; C-04 читає звідти.
