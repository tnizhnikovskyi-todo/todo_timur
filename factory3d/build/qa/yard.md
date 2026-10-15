# QA yard

Статус: PARTIAL
Проверено: 21, провалено: 1, не проверено: 12 (дата 2026-10-15, коммит 29a088e; мост `factory3d_yard_gantt` сверен по arch в базе и в браузере)
Дефекты: 1 (критичных: 0)
Мусор в базе: f3d.yard.visit id 7 «YV/2026/00007» (note «QA-yard-visit-1», state left); f3d.yard.visit id 8 (note «QA-yard-visit-2», state draft); f3d.yard.booking id 7 («QA-yard-booking-1», confirmed, DOCK-W2, 2026-10-20 10:00–11:00 UTC, visit 7); f3d.yard.booking id 8 («QA-yard-booking-overlap», requested, DOCK-W2, 2026-10-20 10:30–11:30 UTC). Побочный эффект: крон `day_reset` сбросил дневные счётчики ворот (штатно, не удаление). Удалений не было, пользователей не создавалось, LPR-событий не создавалось.

Окружение: connection `AxI--dg8QCmJAxW_`, db `odoo` (проверено в каждом ответе). Пользователь `admin` (uid 2) имеет группы охраны и диспетчера. Команды на ворота не отправлялись: `factory3d.yard.write_enabled = False`.

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка: `factory3d_yard`, `factory3d_yard_gantt` | `ir.module.module` | PASS: installed, версии 19.0.1.0.0 совпадают с манифестами; `web_gantt` и `stock_fleet_enterprise` installed | odoo_search_read ir.module.module |
| 2 | Меню и действия (FR-22, AC-66 частично) | `ir.model.data` модуля | PASS: 17 меню (root + 16), 12 `act_window`, 3 `ir.actions.server`. Факт открытия проверен для gantt-действия | odoo_search_read ir.model.data |
| 3 | Представления бронирования (AC-53 частично) | `get_views` `f3d.yard.booking` | PASS: gantt, list, form, calendar, search отдаются без ошибок | odoo_execute get_views |
| 4 | Мост gantt: `decoration-secondary` вместо `decoration-muted` (DEC-1, фикс 6328313) | arch в базе | PASS: в gantt-view `decoration-secondary="state == 'cancelled'"`, `decoration-muted` только в list-view (допустимо) | arch view id 2574 |
| 5 | Gantt бронирований открывается в браузере | Playwright (Node), действие `action_f3d_yard_booking`, `view_type=gantt` | PASS: `.o_gantt_renderer` есть, переключатель видов gantt/calendar/list; ошибок консоли, 5xx и диалогов нет. Полосок нет (открыт день 15.10, брони на 20.10), цвета decoration не проверены визуально | /tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/qa_yard_gantt.png |
| 6 | Серверное действие «Диспетчеризация (стандарт)» (AC-55) | `ir.actions.server.run` id 895 | PASS: `views` = gantt, list, form; `domain` = `dock_id != False`; gantt view id 2162 | odoo_execute run |
| 7 | Создание рейса (AC-01 частично) | `create` `f3d.yard.visit` | PASS: name `YV/2026/00007`, номер `' аа 1001 те '` → `АА 1001 ТЕ`, `plate_norm` `AA1001TE`, side west, policy in_out, state draft | visit id 7 |
| 8 | Подтверждение брони → рейс `planned` (FR-02, AC-04 частично) | `action_confirm` брони 7 | PASS: бронь confirmed, рейс planned, `planned_at` заполнен | booking 7, visit 7 |
| 9 | Конфликт слотов (FR-03, AC-07) | `create` брони 8 13:30–14:30 на DOCK-W2, `action_confirm` | PASS: `ValidationError` «Ворота DOCK-W2 уже заброньовані: …»; бронь 8 осталась requested. Текст ошибки получен через XML-RPC | XML-RPC fault, см. замечание R1 |
| 10 | Отрицательный переход `planned → planned` (§10.1) | `action_plan` рейса 7 | PASS: `UserError` «Перехід … неможливий» | odoo_execute (ошибка) |
| 11 | Полный путь рейса `planned → arrived → queued → at_dock → left` (AC-02 частично) | `action_arrive`, `action_admit(open_gate=False)`, `action_call_to_dock`, `action_leave` | PASS: каждый шаг ок; `arrived_at` и `at_dock_at` заполнены. Команд на ворота не было | visit 7 read: state at_dock, arrived_at |
| 12 | Запрет перехода из `left` (§10.1) | `action_arrive` рейса 7 после leave | PASS: отказ (`left` без переходов) | odoo_execute (ошибка) |
| 13 | Отмена и возврат брони (AC-06 частично) | `action_cancel`, `action_reset` брони 8 | PASS: requested → cancelled → requested | odoo_execute true |
| 14 | Отмена и возврат рейса (§10.1) | `action_cancel`, `action_draft` рейса 8 | PASS: draft → cancelled → draft | odoo_execute true |
| 15 | Миграция (AC-75 частично) | `ir.config_parameter` `factory3d.yard.migration_*` | PASS: `migration_state=done`; отчёт: visits 6, bookings 6, conflicts 0, weighings 1, products_weighted 7, carriers_linked 2, unmatched 1 (совпадает с §5.4). Не перезапускалась (нельзя) | config_parameter id 196, 197 |
| 16 | Кроны (FR-25, §6): `method_direct_trigger` для 69 (очередь), 70 (GC), 71 (day reset) | `ir.cron.method_direct_trigger` | PASS: все три вернули `true`; `ir.logging` ERROR/CRITICAL/WARNING с 2026-10-15 пустой. Кроны активны, `lastcall` свежий (очередь каждую минуту) | odoo_execute, odoo_search_read ir.logging |
| 17 | Безопасность крона GC перед запуском | `search_count` LPR-событий, взвешиваний и рейсов старше порога | PASS: 0 / 0 / 0, значит GC ничего не удалит | odoo_execute search_count |
| 18 | HTTP: `POST /f3d/telemetry/event` без токена (AC-82 частично) | curl | PASS: 401 | curl, код ответа |
| 19 | HTTP: `POST /f3d/telemetry/push` без токена | curl | PASS: 401 | curl, код ответа |
| 20 | HTTP: `GET /f3d/viewer/data` без входа (AC-86 частично) | curl | PASS: 303 на логин (auth=user) | curl, код ответа |
| 21 | HTTP: путь LPR из AC-82 `POST /f3d/lpr` | curl | FAIL: 404. Маршрута `/f3d/lpr` нет (см. дефект D1) | curl, код ответа |

Дополнительно: `GET /f3d/telemetry/health` вернул 200. Всего прямых HTTP-запросов (curl и XML-RPC): 7. Браузерная сессия (вход, открытие gantt, ресурсы страницы и JSON-RPC) по запросам не считалась поштучно, поэтому лимит 50 мог быть превышен только ресурсами страницы. Это нужно проверить по сетевому журналу браузера.

## Дефекты

### D1 (низкий): путь LPR из AC-82 / ТК-02 не существует
- Шаги: `POST https://timur-o19demo.todo.ltd/f3d/lpr` (любое тело, без токена).
- Ожидание (AC-82): ответ 401 без токена; с токеном событие в Odoo за 10 с.
- Факт: 404. Реальный путь: `POST /f3d/telemetry/event` с `events[].route = "lpr"`. Без токена даёт 401.
- Код: `factory3d_telemetry/controllers/telemetry.py:225` (маршрут `/f3d/telemetry/event`); `factory3d_yard/models/f3d_push_handler.py:10-12` (`_f3d_push_routes = ("lpr",)`).
- Вывод: в SPEC модуля (AC-82, ТК-02) и в плане стенда путь неверный. Код не менять, исправить текст SPEC/ТК.

## Замечания (не дефекты)

- R1: текст ошибки пересечения повторяет время слота: «…: DOCK-W2 · 20.10 13:00–14:00 (13:00–14:00).». Это буквальное следование R-03 п.1 (`name` брони плюс локальные часы), но читается как дубль. `factory3d_yard/models/f3d_yard_booking.py:185-199`. Решение за менеджером.
- R2: бронь в `requested`, которая перетинает `confirmed`, не получает `warning`; предупреждение видно только у подтверждённой брони («Перетин із запитом»). Это соответствует R-03 п.2.
- R3: коннектор скрывает текст `ValidationError`/`UserError` («Error executing tool»). Тексты проверены через XML-RPC.
- R4: в задании указаны состояния requested → confirmed → arrived → done. В коде у брони: requested, confirmed, cancelled. У рейса: draft, planned, arrived, queued, at_dock, handling, weighed, left, rejected, cancelled. Состояния `done` нет, финальное состояние рейса — `left`.
- R5: слоты хранятся в UTC, в названиях и предупреждениях время локальное (Europe/Kyiv, UTC+3).
- R6: на тестовом сервере `read_enabled = True`, `write_enabled = False`. Команды ворот не отправлялись.

## Не проверено и почему

1. RBAC (AC-21, AC-35, AC-59, AC-67–AC-69): пользователей `qa-yard-<роль>` не создавал, время ограничено. Проверено только, что `admin` имеет группы охраны и диспетчера.
2. Буфер и календарь (AC-08, AC-09) и категории (AC-10): не проверялись, предупреждения не сверял.
3. Весы и зважування (AC-17–AC-19, AC-41–AC-45), SICS (AC-49–AC-52): нет оборудования; `write_enabled = False`.
4. Ворота и команды (AC-34–AC-40, AC-47, AC-88): команды запрещены конфигурацией, проверка заблокирована.
5. LPR-логика (AC-23–AC-31): проверено только 401; положительный путь требует токена, которого нет в переданных данных.
6. Авто-диспетчеризация (AC-12, AC-13, AC-37): не проверялась.
7. Отчёты, КПП-API и туры интерфейса (AC-54, AC-56–AC-58, AC-61–AC-63): не проверялись.
8. Очистка ПДн и ротация (AC-70, AC-71): GC запущен, но данных для проверки не было (кандидатов 0), поведение не проверено.
9. Миграция синтетическая (AC-76, AC-77): не запускалась, это не разрешено.
10. Удаление (AC-22, unlink): не вызывалось по правилу «не удалять».
11. Стендовые ТК-01…ТК-08 и DEPLOY_TEST (AC-81–AC-86): требуют железа и стенда, не выполнялись.
12. Визуальные цвета gantt-полосок (decoration-secondary) и отображение бронирований на 20.10: не видны в открытом по умолчанию дне.
