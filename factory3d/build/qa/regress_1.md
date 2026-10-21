# Регресійний QA 1: перевірка виправлень на timur-o19demo

Дата: 2026-10-16, ~01:00–01:15 UTC. База `odoo`, сервер https://timur-o19demo.todo.ltd. Код не змінювався, коміт не створювався.
Скрипт перевірки (поза репозиторієм): `/tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/qa/regress_1_run.py`.

## Результати

| defect | result | evidence |
|---|---|---|
| M-1 (machine_connect API-01) | PASS | `GET /f3d/machine/cutmap/1/export`. Bearer колектора QA-MC-C2 (f3d.collector id 15, не власник джерела CUTOPT) → HTTP 401 `unauthorized`. Bearer колектора COL-MAIN (id 1, власник сигналу `equipment/CUTOPT/cmd`, signal id 437) + заголовок X-F3D-Token → HTTP 404 `not_found` («Карту розкрою не знайдено»): автентифікацію пройдено, 401 немає. Повний 200 не перевірено: немає карти в стані exported з експорт-токеном, його створює лише потік оптимізатора. |
| T-2 (push не змінює write_date щоразу) | PASS (частково) | QA-TELE-C1 (id 2). write_date: 01:04:09 (після видачі токена) → 01:04:10 (після P1: last_seen, state offline→online) → 01:04:10 після P2 (+2 с), P3, P4 (усі HTTP 200). Рядки в `f3d_collector_push` не перевірено: метода підрахунку немає. |
| T-3 (троттлінг при зміні IP) | PASS (з застереженням) | P1 (XFF 10.20.30.1): last_seen 01:04:10. P2 (XFF 10.20.30.2) через +2 с: last_seen лишився 01:04:10, last_ip лишився 104.23.253.95. Застереження: сервер ігнорує X-Forwarded-For (last_ip = 104.23.x, схоже на Cloudflare), тому реальний IP запиту P2 не підтверджено. |
| T-4 (дія «Телеметрія» з фільтрами тривог) | PASS | act_window id 805, context `search_default_active=1, search_default_alarm=1`. Серверна search-view f3d.signal (ir.ui.view id 2231): «Тривога» і «Увімкнені» в різних групах (AND). Лічильники: за замовчуванням (active и status=alarm) = 0; усі тривоги (active_test=False, status=alarm) = 0; усі активні сигнали = 1244. Застереження: тривог на стенді зараз немає, тому 0 = 0; відрізнення від 1244 показує, що фільтр працює (при старій OR-групі було б ~1244). |
| A-1 (Охорона: імена дверей і підтвердження тривоги) | PASS | Створено res.users id 18 «QA-reg-guard» (login qa-reg-guard): група factory3d_access.group_f3d_access_security (id 85) і внутрішній користувач, share=False. Від його імені: write name дверей id 3 «Зарядна» → AccessError «Змінювати двері може лише адміністратор СКУД.», назва не змінилась. Адмін виставив alarm=True, alarm_reason=forced; від охорони `action_ack_alarm` → True; після — alarm=False, alarm_reason=False (як було до тесту). |
| M-2 (OEE: run=480 від відкритих журналів) | NOT CHECKED | Смін за 2026-10-16 немає: `action_recompute` над порожнім набором, потім ir.cron id 60 «Верстати: OEE змін» (method_direct_trigger → True); смін за сьогодні так і не з'явилось, причину не встановлено. Run=480 сьогодні: 0. Спостереження: 20 закритих смін за 2026-10-15 (ids 4, 5, 6, 8, 10–13, 15, 20, 22, 23, 25–27, 30–33, 35) мають run_min=480, write_date 2026-10-15 20:39:34. Їх не перераховувано (ліміт HTTP). Рекомендовано перерахувати `action_recompute` і перевірити. |
| B-1 (f3d_code > 32 символів) | PASS | create f3d.zone з f3d_code «QA-REG-ABCDEFGHIJKLMNOPQRSTUVWXYZ» (33 символи; проходить регексп `^[A-Z0-9]+(-[A-Z0-9]+)*$`) → ValidationError «Код сцени … лише великі латинські літери …». Єдина причина відмови — довжина. Текст той самий, що й для регекспу. Запис не створено (пошук «QA-reg-B1» = 0). Перша спроба без zone_type відхилена через обов'язкове поле (неінформативно). |
| B-4 (повтор базової міграції) | PASS | До: migration_state=done (write 2026-10-15 20:52:49), migration_report (write 20:52:48), параметра rerun немає. Виклик `f3d.scene.mixin.f3d_run_migration` → «Міграцію виконано». Після: migration_state=done (write не змінився), migration_report без змін (20:52:48), створено `factory3d.base.migration_rerun_report` (2026-10-16 01:04:27) з migration_state=done, batches_created=0. |
| G-1 (ТО: priority 3 і «прострочено на N мотогодин») | NOT CHECKED | QA-genset-GEN-01 (td.genset id 1): maint_state=overdue, maint_hours_left=-10.0, тобто прострочка за мотогодинами є. Відкрита заявка id 48 «ТО-1 після обкатки (250 мотогодин)» (стадія New Request, priority=False, створена 2026-10-15 21:37:09, без «прострочено») блокує створення нової: `_check_maintenance` не створює другу, поки перша відкрита. Метод приватний, по RPC не викликається. Шлях через `_apply_reading` іде лише з опитування relay, а relay_enabled=False. Щоб перевірити: в odoo shell закрити/архівувати заявку 48 і викликати `td.genset._check_maintenance()` для генератора id 1, або увімкнути relay. |

## Побічні дії (тестова база, дозволено власником; нічого не видалено)

- Створено res.users id 18 `QA-reg-guard` (login `qa-reg-guard`). Випадковий пароль, у звіт не записано.
- Двері id 3: alarm False → True → False (відновлено).
- Нові токени колекторів (зберігаються лише хеші; сирі токени не фіксувались): COL-MAIN (id 1; попередній токен уже був відкликаний), QA-MC-C2 (id 15), QA-TELE-C1 (id 2).
- QA-TELE-C1 (id 2): state offline→online, last_seen/last_push_at 2026-10-16 01:04:10.
- Запущено ir.cron id 60 «Верстати: OEE змін» (method_direct_trigger); нових смін за сьогодні не створив.
- Створено параметр `factory3d.base.migration_rerun_report`.
- Спроби create f3d.zone не залишили записів.

## Ліміт HTTP: перевищено

За моїм підрахунком було ≈63 запити при ліміті 60: 21 виклик odoo-mcp (1 HTTP на виклик), 6 через rpc_call.py (2 HTTP на виклик: auth і call_kw), 36 у QA-скрипті. Якщо odoo-mcp робить більше одного HTTP на виклик, кількість більша. Після усвідомлення перевищення нових запитів до Odoo не робив.

## Примітка

Поведінка сервера відповідає виправленням M-1, T-2, T-4, B-1, B-4, A-1, хоча в DEFECTS.md частина з них позначена «не раскатан». Перевірка виконана за фактичною поведінкою, а не за статусом у реєстрі.
