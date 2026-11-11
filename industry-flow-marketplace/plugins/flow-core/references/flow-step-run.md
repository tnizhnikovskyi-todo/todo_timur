# Шаблони задач флоу: наряд кроку, задача гейта, задача ролі

Спільний шаблон для `flow-orchestrator` (створює) і `flow-step-runner` (читає). Поля й ключі наряду — `naryad-format.md`; запис `description` — `odoo-bridge.md` §3.

## 1. Наряд AI-кроку (`task.kind = step`)
- Назва задачі: `<код кроку> · <scope.id> · спроба <N>`.
- Проєкт: проєкт пакета (`scope.kind = package`) або клієнта; стадія при створенні — `stage.queue`.
- `description`: YAML-блок за `naryad-format.md` у `<pre><code class="language-yaml">`; поверх YAML — нічого.
- `skill_ref`, `model`, `effort`, `limits`, `check`, `done`, `data_rule`, `odoo_connections` — з картки кроку; `inputs[].sha` — фіксує оркестратор на момент створення.
- Для кроків із паралельними запусками (A-11/A-12/A-13; B-01..B-13 на клієнта): окремий наряд на кожну одиницю, ключ злиття записується в `params.group`.

## 2. Задача гейта (`task.kind = gate`, батько — задача кроку)
Створюється оркестратором, коли крок має `check.mode: human|both` або сам є людським. Містить:
- назва `Гейт <код> · <scope.id>`; `parent_id` = наряд кроку; `human_sla` з картки; відповідальний — роль R з RACI (A — затверджує);
- `description` — чек-лист з `checkHow` картки (по одному пункту, з посиланнями `path@sha` на результат), PR-посилання, `memo` зі звіту;
- поля: `gate.decision` (порожнє; кнопки «Затвердити» / «Повернути»), `gate.return_to` (код кроку, з переліку допустимих у `flow-map.md`), `gate.comment`, `gate.fixed_in_ai_result`, `gate.skill_feedback` (так/ні);
- AI не має прав на кнопки й поля `gate.*`.
Рішення розпізнається за `odoo-bridge.md` §5 і є входом для переходу за `flow-map.md`.

## 3. Підкрок людини (`task.kind = human_substep`) для `result: waiting_human`
Створюється оркестратором у відповідь на `waiting_human` (`report-format.md`): `parent_id` = наряд, назва `Дія людини <код> · <що>`, `description` = `waiting_for.what` + інструкція, `user_id` = роль з `waiting_for.role`. Закриття (стадія `stage.done`) -> оркестратор створює наряд того самого кроку з `attempt` без збільшення, `params.resume` = `waiting_for.resume`.

Приклади: A-02b (власник заповнює `OWNER-INTAKE.md`, ≤20 хв), A-03b K1 (відповіді на `K1-Q*`, кандидати на відкидання показані до синтезу), A-03c `session` (сесія з власником; матеріал готує AI-наряд `session`), зразок кроків із `params.sample: true` за карткою (A-03b, A-20c, A-21, A-21c). Для A-21c виконавець кроку — Контент-менеджер (`executor: any`, `step-cards.md`, «Ролі»).

## 4. Задача ролі (`task.kind = role_task`)
Для кроків, де `executor: human` без AI (A-02, A-07, A-17, D-05, C-05, C-08, B-08b, B-08d, B-12): наряд з YAML (`executor: human`, `inputs`, `done`, `human_sla`), без `skill_ref`; виконавець — людина за RACI. Задача сама є гейтом (кнопки з §2). Підготовку матеріалів (напр. чернетку рішення) створює окремий наряд AI-кроку, який є входом.

## 5. Повернення
Повторна задача кроку при `returned`/«Повернути»: новий наряд з `attempt+1` (не перевідкривати стару), `returned_from: {step: <код гейта/кроку>, comment: <текст>}`; перед створенням оркестратор перевіряє `attempt ≤ limits.max_attempts`, інакше `stage.escalation` за `escalation` картки.
