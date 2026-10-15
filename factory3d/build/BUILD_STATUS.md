# Состояние сборки factory3d

Правит только менеджер (`factory3d/build/MANAGER.md`). Лидеры модулей пишут в `factory3d/build/modules/<m>.md`.

Шаг 0: готов
Ветка интеграции: `claude/factory3d-build`
Документация заморожена на коммите: `9b5cbb5`
BUILD_STATUS ведётся в ветке менеджера `claude/funny-knuth-8tq7jy`; интеграция — в отдельном worktree `claude/factory3d-build`.

## Сводка для продолжения (обновлено 2026-10-15 20:15 UTC)

Сборка завершена: 11 из 11 модулей DONE и смержены в `claude/factory3d-build` @ `29a088e` (Odoo 1633/1633, 18 модулей
вместе с iot_sim, td_genset и factory3d_genset; демо viewer 211/211; фикс machine_connect DEC-19/20 включён).
Итоговое сообщение отправлено, send_later не ставится.

Дальше — QA на тестовой базе `timur-o19demo` (см. журнал 20:05 и 20:07 UTC): ждём от пользователя «готово» после
установки модулей из `29a088e`; затем проверить установку через коннектор, агенты по модулям (≤3 одновременно),
этап 2 — стенд в контейнере (таймбокс 1 ч). Отчёты — `factory3d/build/qa/<m>.md`.

Процедура мержа (работает агент coder в worktree /home/user/f3d-build, БД f3d_int): `git merge --no-ff`; проверить,
что чужие модули не откатываются (ветки старые); прогон A — все DONE-модули вместе с iot_sim на пустом шаблоне;
прогон B — демо-набор viewer на f3d_demo_tpl, только если менялся viewer; плагины коллектора — в отдельных venv
(test_load_real_plugins_exactly_four падает, если плагины в одном venv). Кросс-модульные падения тестов, где неверны
именно ожидания теста, чинить отдельным коммитом; дефект кода — откат и `send_message` лидеру. Среда: Postgres
после перезапуска контейнера — `pg.sh start`; у f3d_demo_tpl могут сбиться сиквенсы (setval или make_demo_tpl.sh --force).

Указания пользователя: лимиты «Темп» сняты (запускать сразу, как зависимости DONE); отчёты в чат — по-русски, таблица
модулей с колонкой «Время в работе»; время для пользователя — по Киеву (UTC+3) в ответах на его вопросы о времени;
стенд лидерам ограничивать по времени (30–45 мин), закрывать DONE (юнит-DoD).

Требует внимания человека (сводно, подробности — в `factory3d/build/modules/<m>.md`):
- Прогоны на копии демо-базы `odoo` (все модули); стендовые ТК/ТБ/ТП на сервере с Docker (telemetry ТК-03/09/10/12,
  ТП-06; energy ТК-02/07/08/09; machine_connect ТК-03/15, ТП-01/04; iot_sim ТП-06 24 ч; fire_safety весь стенд).
- Подписи security-review (iot_sim, access, viewer, yard, bms, fire_safety) и pr-review (access).
- iot_sim: ТП-04 p95 1,39 с > 1 с; эмулятор D-1…D-3, O-1/O-2 (bms TEST_REPORT); td_genset relay для ТК-18 (CI-02).
- Расхождения SPEC: base §4.2 group_f3d_admin ⊄ base.group_system (bms DEC-5); fire_safety AC-77 45 vs 46;
  machine_connect AC-13 vs R-05 (DEC-8); yard AC-58 1 с vs 50 мс, AC-76 частично, sudo шире §4.4; telemetry ТП-04 объём
  таблиц (DEC-16); viewer ARCHITECTURE.md строки 337/483 — старый состав файлов.
- Enterprise-мосты не тестированы: base_mrp_maintenance, yard_gantt, machine_connect_mrp_workorder.
- viewer: ТК-07 планшет, AC-38 пересборка dist (Blender), eslint+prettier; повторный ▶ не останавливает проигрывание.
- Правки SPEC по DEC уже внесены: base, iot_sim, telemetry, access, viewer, energy.

## Модули

Статусы: `TODO` → `IN_PROGRESS` → `DONE`; `BLOCKED` (причина в отчёте модуля); `BLOCKED-ENV` (зависимость не ставится в среде).

| # | Модуль | Фаза | Зависит от (factory3d) | Статус | Сессия | Старт | Готов | Тесты | DEC |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `factory3d_base` | 1 | — | DONE | session_01QHzZ3cNyHZ2W6eBd43JJwn | 2026-10-14 22:04 UTC | 2026-10-14 23:17 UTC | 150/150 | 15 |
| 2 | `factory3d_iot_sim` | 1 | base | DONE | session_019MFyhB78Wd7hgrNLzgRGkP | 2026-10-14 23:18 UTC | 2026-10-15 04:30 UTC | Odoo 140/140, svc 451/451 | 18 |
| 3 | `factory3d_telemetry` | 2 | base | DONE | session_01NF5Tuhsrpzgd1SMkYaMG8N | 2026-10-15 06:47 UTC | 2026-10-15 11:43 UTC | Odoo 541/541 (6 модулей), collector 174+2 skip | 16 |
| 4 | `factory3d_viewer` | 1 | base | DONE | session_01HJS765EQsGKtWkA6ocokUP | 2026-10-15 08:33 UTC | 2026-10-15 13:27 UTC | Odoo 711/711 (9 модулей), демо f3d_demo_tpl 211/211 | 20 |
| 5 | `factory3d_access` | 4 | base | DONE | session_01VWzBg1ho7GaJgftY7d5EgN | 2026-10-15 08:55 UTC | 2026-10-15 10:59 UTC | 156/156 (вместе с base+iot_sim 296/296) | 13 |
| 6 | `factory3d_machine_connect` | 2 | telemetry | DONE | session_015rKvjaStE6jPJzyWqGrcwf | 2026-10-15 11:44 UTC | 2026-10-15 18:13 UTC | Odoo 1205/1205 (15 модулей), плагины 53/53, collector 174+2 skip | 18 |
| 7 | `factory3d_energy` | 3 | telemetry | DONE | session_018rtyAE7NdpmjQDfBdoewi1 | 2026-10-15 11:54 UTC | 2026-10-15 17:42 UTC | Odoo 1076/1076 (14 модулей), демо viewer 211/211 | 18 |
| 8 | `factory3d_yard` | 4 | base, telemetry | DONE | session_01D3xkbVgCSWZFh4E4Agha1H | 2026-10-15 12:20 UTC | 2026-10-15 13:53 UTC | Odoo 831/831 (10 модулей), collector 174+2 skip, плагин sics 34/34 | 8 |
| 9 | `factory3d_bms` | 5 | telemetry | DONE | session_01L43oC1FugyPdK6kpcRc1ij | 2026-10-15 13:54 UTC | 2026-10-15 19:02 UTC | Odoo 1344/1344 (16 модулей), helvarnet 28/28, collector 174+2 skip | 7 |
| 10 | `factory3d_fire_safety` | 5 | telemetry | DONE | session_01KJcdAJpD2ninHpqxDQv2FC | 2026-10-15 13:58 UTC | 2026-10-15 16:12 UTC | Odoo 965/965 (13 модулей), демо viewer 211/211 | 13 |
| 11 | `td_genset` + мост `factory3d_genset` | 3 | base, telemetry, energy | DONE | session_013Ue8H7Af5WRGUBWdWKM5e4 | 2026-10-15 17:43 UTC | 2026-10-15 19:00 UTC | Odoo 1620/1620 (18 модулей), демо viewer 211/211, relay 20/20 | 16 |

Порядок строк — приоритет запуска. Эмулятор (`iot_sim`) и телеметрия идут раньше: от них зависят стендовые тесты.
Мостики auto_install (`factory3d_viewer_sale`, `factory3d_telemetry_viewer`, `factory3d_fire_safety_viewer`,
`factory3d_access_telemetry`) делают лидеры модулей, в чьих §6 они описаны.

## Среда

Зависимости Odoo по модулям (из `docs/ARCHITECTURE.md` §3). Odoo 19.0 CE `bc77fac7`; скрипты `factory3d/tools/odoo/` (`setup.sh` с нуля ≈3 мин).
Нет в среде: `mrp_maintenance`, `mrp_workorder`, `web_gantt` → решения ENV-1..4 в `factory3d/build/ENV_DECISIONS.md` (ветка интеграции).

| Модуль | Зависимости Odoo | Ставится |
|---|---|---|
| base | stock, mrp, maintenance, mrp_maintenance, hr, stock_picking_batch, stock_fleet, fleet, web | кроме mrp_maintenance → ENV-1 |
| viewer | bus, web | да |
| iot_sim | — | да |
| telemetry | maintenance, mail, web | да |
| machine_connect | mrp_workorder | нет → ENV-3 |
| energy | mrp_account, mrp_workorder, analytic, web_hierarchy | кроме mrp_workorder → ENV-2 |
| genset (мост) | td_genset | свой модуль, переносит лидер |
| yard | stock_picking_batch, stock_fleet, delivery, stock_delivery, web_gantt, mail, bus | кроме web_gantt → ENV-4 |
| access | hr_attendance, mail | да |
| bms | web | да |
| fire_safety | hr_attendance | да |

## Журнал менеджера

Коротко, одна строка на событие: дата, модуль, что произошло.

- 2026-10-14 менеджер: шаг 0.1 — создана `claude/factory3d-build` от `9b5cbb5`; решение: BUILD_STATUS живёт в ветке менеджера, чтобы продолжение после очистки контекста видело актуальное состояние.
- 2026-10-14 менеджер: шаг 0.2–0.3 — скрипты Odoo 19 в `claude/factory3d-build` (`49decab`), смоук зелёный; нет mrp_maintenance, mrp_workorder, web_gantt.
- 2026-10-14 менеджер: решение ENV-1..4 (`f0fbe9f`) — ядро на CE, Enterprise-часть в мосты auto_install; вместо BLOCKED-ENV для base/energy/machine_connect/yard.
- 2026-10-14 22:04 UTC factory3d_base: запущена сессия session_01QHzZ3cNyHZ2W6eBd43JJwn (1/2 за 24 ч).
- 2026-10-14 23:17 UTC factory3d_base: DONE — смержен в `claude/factory3d-build` (`298871a`), тесты 150/150, DEC 15. Не проверено: ТК-01…05 (нужна копия базы `odoo`), мост `factory3d_base_mrp_maintenance` (нет Enterprise, ENV-1).
- 2026-10-14 23:18 UTC factory3d_iot_sim: запущена сессия session_019MFyhB78Wd7hgrNLzgRGkP (2/2 за 24 ч; следующий слот — 2026-10-15 22:04 UTC).
- 2026-10-15 04:30 UTC factory3d_iot_sim: DONE — смержен в `claude/factory3d-build` (`609a247`), Odoo 140/140 (base+iot_sim), сервис 451/451, DEC 18. Не проверено: ТК-01/15 на копии базы `odoo`, ТК-18 (нет genset_relay в td_genset, CI-02), ТП-06 24 ч; ТП-04 p95 1,39 с > 1 с (медиана в норме); подпись security-review — за человеком.
- 2026-10-15 04:30 UTC менеджер: лимит запусков 2/24 ч исчерпан; следующий запуск (`factory3d_telemetry`) — 2026-10-15 22:05 UTC.
- 2026-10-15 06:47 UTC factory3d_telemetry: запущена сессия session_01NF5Tuhsrpzgd1SMkYaMG8N по прямому указанию пользователя сверх лимита (3/2 за 24 ч). Пауза до 22:05 отменена. Дальше лимит «2 за 24 ч» снова действует: следующий запуск — когда в окне 24 ч останется меньше 2 сессий (после 2026-10-15 23:19 UTC).
- 2026-10-15 08:33 UTC factory3d_viewer: запущена сессия session_01HJS765EQsGKtWkA6ocokUP по прямому указанию пользователя сверх лимита (4 за 24 ч); одновременно 2 (telemetry, viewer).
- 2026-10-15 08:55 UTC factory3d_access: запущена сессия session_01VWzBg1ho7GaJgftY7d5EgN по прямому указанию пользователя сверх лимитов (5 за 24 ч; одновременно 3: telemetry, viewer, access).
- 2026-10-15 09:58 UTC менеджер: правки SPEC по DEC (base DEC-5/11/15, iot_sim DEC-4/11, telemetry DEC-10, access AC-69) — `fa69787` в `claude/factory3d-build`; отчёт base (ТК-01 частично на timur-o19demo) смержен — `c3c845b`.
- 2026-10-15 10:59 UTC factory3d_access: DONE — смержен в `claude/factory3d-build` (`9ab374a`), Odoo 296/296 (base+iot_sim+access), DEC 13. Не проверено: мост `factory3d_access_telemetry` (нет telemetry), ТК-09 (viewer), ТК-10 drill (fire_safety), копия базы `odoo`. Найдено: эмулятор iot_sim отдаёт 404 вместо 405 (D-2); ERROR FK `card.server_id` при деинсталляции (O-1); подпись security/pr-review — за человеком.
- 2026-10-15 11:36 UTC менеджер: исправлены D-2 (эмулятор iot_sim: 405 вместо 404, `d79c297`, svc 463/463) и O-1 (uninstall factory3d_access без FK ERROR, `e6ebb47`, Odoo 297/297) в `claude/factory3d-build`.
- 2026-10-15 11:43 UTC factory3d_telemetry: DONE — смержен в `claude/factory3d-build` (`d10cd6e`), Odoo 541/541 (base, iot_sim, access, telemetry + мосты access_telemetry, telemetry_viewer), collector unit 174 + 2 skip (MQTT без docker), DEC 16. Не проверено: стенд ТК-03/09/10 (красные в полном прогоне), ТК-12, ТП-06 — на сервере с Docker; ТП-04 объём таблиц выше оценки (DEC-16).
- 2026-10-15 11:44 UTC factory3d_machine_connect: запущена сессия session_015rKvjaStE6jPJzyWqGrcwf по указанию пользователя; одновременно 2 (viewer, machine_connect).
- 2026-10-15 11:54 UTC factory3d_energy: запущена сессия session_018rtyAE7NdpmjQDfBdoewi1 по указанию пользователя сверх лимита одновременных (3: viewer, machine_connect, energy).
- 2026-10-15 12:20 UTC factory3d_yard: запущена сессия session_01D3xkbVgCSWZFh4E4Agha1H по указанию пользователя сверх лимита одновременных (3: machine_connect, energy, yard); viewer DONE по отчёту (12:06), идёт мерж.
- 2026-10-15 12:36 UTC factory3d_viewer: мерж откатан (интеграция красная): 4 failed/671 из-за совместной установки с access (провайдер access в тестах viewer; тест access ждёт отсутствия viewer) и 24 failed+10 errors при установленном iot_sim (is_demo_db() истинно без демо-данных). Лидеру отправлено send_message с задачей; статус IN_PROGRESS.
- 2026-10-15 13:03 UTC пользователь: с 14:30 UTC (17:30 Киев, после сброса 5-часового лимита в 14:20 UTC) запустить все модули с готовыми зависимостями и дальше запускать без ограничений по числу (раздел «Темп» MANAGER.md отменён пользователем с 14:30 UTC). Будильник на 14:30 UTC поставлен.
- 2026-10-15 13:27 UTC factory3d_viewer: DONE — со второй попытки смержен в `claude/factory3d-build` (`848580c`), Odoo 711/711 (все модули с iot_sim), демо 211/211, DEC 20 (DEC-20 — демо-детект по наличию демо-данных). Правки SPEC DEC-5/12/15 — `be809aa`. Не проверено: копия базы `odoo`, ТК-07 планшет, AC-38 dist (Blender), access/telemetry на демо-шаблоне.
- 2026-10-15 13:53 UTC factory3d_yard: DONE — смержен в `claude/factory3d-build` (`f7b0a84`), Odoo 831/831, collector 174+2 skip, плагин sics 34/34, DEC 8. Мост factory3d_yard_gantt не ставился (нет web_gantt). Замечание: тест коллектора test_load_real_plugins_exactly_four падает, если плагин yard стоит в том же venv (5 плагинов) — ставить в разные venv или поправить тест. Не проверено: ТК-01…08 на копии демо-базы.
- 2026-10-15 13:54 UTC factory3d_bms: запущена сессия session_01L43oC1FugyPdK6kpcRc1ij по указанию пользователя (раньше 14:30); одновременно 3 (machine_connect, energy, bms). В 14:30 UTC — fire_safety (и td_genset, если energy DONE).
- 2026-10-15 13:58 UTC factory3d_fire_safety: запущена сессия session_01KJcdAJpD2ninHpqxDQv2FC по указанию пользователя; одновременно 4 (machine_connect, energy, bms, fire_safety). Будильник 14:30 UTC отменён пользователем. Лимиты «Темп» сняты: td_genset запускать сразу, как energy DONE.
- 2026-10-15 16:12 UTC factory3d_fire_safety: DONE — смержен в `claude/factory3d-build` (`a2407fb`) со 2-й попытки; первая — 3 failed в тестах провайдеров viewer (ожидали static для fire/evacuation). Фикс тестов viewer в интеграции, независимый от установленных провайдеров — `d8e3b22`. Odoo 965/965, демо 211/211. Не проверено: стенд ТК/ТБ/ТП, DEPLOY_TEST, копия демо (AC-02), security-review.
- 2026-10-15 17:07 UTC менеджер: стендовые этапы затянулись (machine_connect W9 ~4 ч, energy W6 ~4 ч, bms W7 ~2 ч) — лидерам отправлено: ограничить стенд 30–45 мин, затем закрываться DONE (юнит-DoD), непрогнанные стендовые тесты — в «Требует внимания человека», найденные дефекты кода исправить.
- 2026-10-15 17:42 UTC factory3d_energy: DONE — смержен в `claude/factory3d-build` (`c3056fb`), фикс кросс-модульных ожиданий тестов telemetry/viewer — `0c7a736`; Odoo 1076/1076, демо 211/211. Стенд частично (ТК-01/05/11, ТБ 6/6, ТП 5/6; ТК-02/07/08/09 красные — эмулятор/сценарий). Правки SPEC: AC-32, R-16 п.6, R-17.
- 2026-10-15 17:43 UTC td_genset: запущена сессия session_013Ue8H7Af5WRGUBWdWKM5e4 (зависимости DONE). machine_connect DONE по отчёту (d29e2f3), идёт мерж.
- 2026-10-15 18:13 UTC factory3d_machine_connect: DONE — смержен в `claude/factory3d-build` (`9e6004f`), фикс ожиданий тестов telemetry/energy — `0859a61`; Odoo 1205/1205. Правка telemetry DEC-7 (push_handler: в Odoo 19 registry.descendants отдаёт имена моделей) — после неё стал обнаруживаться push-обработчик lpr из yard, раньше не вызывался. Мост machine_connect_mrp_workorder не ставился (Enterprise). Открыто: ТБ-03 токен в логе, ТП-01 deadlock — разобрать.
- 2026-10-15 18:32 UTC factory3d_bms: мерж откатан — 3 failed + 1 error в telemetry test_migration: post_init_hook bms создаёт 81 сигнал origin=sim_data, verify() миграции telemetry считает их (88 != 7) → partial. Лидеру отправлено: как energy DEC-3 (sim_data как catalog без level 0) + обновить test_hooks; статус IN_PROGRESS.
- 2026-10-15 19:02 UTC factory3d_bms: DONE — со 2-й попытки смержен в `claude/factory3d-build` (`29e4340`), Odoo 1344/1344. Правка SPEC energy (AC-32, R-16, R-17) — `37182a6`. Фикс machine_connect DEC-19/DEC-20 (решение менеджера по поручению пользователя) — в работе в ветке claude/f3d-fix-machine-connect.
- 2026-10-15 19:10 UTC td_genset: лидер DONE в 19:00 UTC (юнит-DoD, `ecd794a`): 276/276 (td_genset 176 + factory3d_genset 100), мост без viewer 90/90, relay 20/20, DEC 16. Мерж поручен агенту a5bedb35ea3301f92 (прогон всех модулей + td_genset + factory3d_genset). Фикс machine_connect DEC-19/20 — агент a3790e56e2dacc752 гоняет полный прогон в /home/user/f3d-mc-fix, ветка ещё не запушена.
- 2026-10-15 19:15 UTC machine_connect фикс DEC-19/20: ветка `claude/f3d-fix-machine-connect` запушена (ba25258 DEC-20 токен в заголовок `X-F3D-Token`, query `t` → 400; 4198a49 DEC-19 крон по id батчами по 10 + FOR UPDATE SKIP LOCKED, троттлинг raw_ts/pieces_ts и telemetry `_touch` 30 с). Odoo mc+telemetry+energy 482/482, pytest плагина 54 passed. Ждёт мержа после td_genset. Не проверено: ТП-01/ТБ-03 на стенде; на стенде нужен ручной `-u`; query-токен больше не принимается (без обратной совместимости).
- 2026-10-15 19:45 UTC td_genset: DONE — смержен в `claude/factory3d-build` (`9f4934d`), фикс ожиданий viewer test_group_denied (провайдер infra моста genset) — `44d71c4`; Odoo 1620/1620 (18 модулей), демо viewer 211/211, relay 20/20, DEC 16. Мерж фикса machine_connect DEC-19/20 поручен тому же агенту.
- 2026-10-15 20:05 UTC QA на тестовой базе (по просьбе пользователя): коннектор odoo-mcp, подключение `timur-o19demo` (id AxI--dg8QCmJAxW_, db `odoo`, https://timur-o19demo.todo.ltd, Odoo 19.0+e Enterprise, без демо). Пользователь ставит модули из `claude/factory3d-build` после мержа фикса machine_connect (включая Enterprise-мосты base_mrp_maintenance, machine_connect_mrp_workorder, yard_gantt; без test_*). Разрешено: агентам создавать/менять записи; удалять — только по подтверждению пользователя списком. Логин для браузера — у менеджера в scratchpad (в репо не хранить). Эмулятор/коллектор на стенде — ответа нет, считаем, что их нет. План: после «готово» проверить установку, затем агенты по модулям (≤3 одновременно), отчёты `factory3d/build/qa/<m>.md`.
- 2026-10-15 20:07 UTC QA, стенд (пользователь: «сам реши»). Решение менеджера: этап 1 — проверки через Odoo/коннектор, HTTP API и браузер, без стенда. Этап 2 — один агент поднимает эмулятор iot_sim и коллектор процессами в контейнере, без Docker. Коллектор шлёт данные на timur-o19demo по HTTPS. Таймбокс 1 ч: если стенд поднялся, прогоняем стендовые ТК; если нет — фиксируем и пропускаем.
- 2026-10-15 20:15 UTC machine_connect фикс DEC-19/20: смержен в `claude/factory3d-build` (`29a088e`), Odoo 1633/1633 (18 модулей, +13 новых тестов), pytest плагина 54 passed. Все 11 модулей DONE — итоговое сообщение пользователю.
- 2026-10-15 20:35 UTC QA: пользователь поручил установку и тестирование менеджеру. Проверка timur-o19demo: все 19 модулей в списке. Версии совпадают с `29a088e`, кроме iot_sim: на диске сервера старый прототип 19.0.1.0.0 (коммит e7fb9a6 от 13.10, нет static/description/icon.png), а нужен 19.0.2.0.0 (есть migrations/19.0.2.0.0). Старая папка в addons_path перекрывает новую; заменить её может только пользователь (доступа к диску нет). static viewer совпадает с репо. Порядок установки: update_list → -u base, iot_sim, base_mrp_maintenance → -i 16 модулей (миграция telemetry опирается на новый iot_sim). Процедура QA-агентов — `factory3d/build/QA.md`. Волны по 3: (base+mrp_maintenance, iot_sim, telemetry), (viewer+sale, access, machine_connect+workorder), (energy, yard+gantt, bms), (fire_safety, td_genset+genset, стенд).
- 2026-10-15 20:50 UTC QA, установка на timur-o19demo (пользователь разрешил ставить менеджеру): 18 из 19 модулей installed, версии = `29a088e`. Enterprise-мосты base_mrp_maintenance и machine_connect_mrp_workorder встали. Дефект: factory3d_yard_gantt не ставится — ParseError «Invalid attributes (decoration-muted) in gantt view» (Odoo 19.0+e). Исправлено в интеграции `6328313` (decoration-secondary). На сервере нужно обновить код (/mnt/f3d-addons), затем поставить yard_gantt. Пакетная установка 16 модулей откатывалась из-за этого моста (auto_install вместе с yard). Установка через коннектор иногда падает по таймауту — ставим через JSON-RPC (scratchpad/qa/odoo_rpc.py), повтор, если работает крон. QA волна 1 запущена: base+mrp_maintenance, iot_sim, telemetry.
- 2026-10-15 20:55 UTC QA: на сервере настроен таймер `f3d-update` (раз в 2 мин). Он забирает `claude/factory3d-build` в `/mnt/f3d-addons`. Для изменённых установленных модулей он сам делает `-u` и перезапуск, перед этим снимает дамп; при падении откатывает базу и код. Новые модули ставим через Odoo (JSON-RPC). yard_gantt установлен — 19/19. Дефект viewer (сообщил пользователь): `quality.check.lot_id` → в Odoo 19 `lot_ids` (m2m), падают провайдеры logistics/quality. Исправление и аудит Enterprise-полей по живому серверу поручены агенту a5bedb35ea3301f92. Пушить только зелёное: таймер раскатывает на сервер. SSH из контейнера закрыт (порт 22), доступы — в scratchpad.
- 2026-10-15 20:58 UTC Указание пользователя: беречь лимиты, QA-агенты — простые (model haiku), работы много, но она несложная. Волна 1 уже на sonnet; волны 2+ на haiku, таймбокс 40 мин, отчёты короче.
- 2026-10-15 21:10 UTC Указание пользователя (уходит спать): «разрешаю делать всё, что нужно, это тестовая база; решения принимаешь сам; утром всё должно работать». Разрешено создавать тестовых пользователей `qa-<m>-<роль>` и менять что угодно в тестовой базе. Ночной план менеджера: 1) QA остальных модулей агентами на haiku (≤3 агента одновременно). 2) Исправления пакетами через coder (sonnet): сначала критичные (iot_sim D1 — нет загрузки реестра при `-u`; viewer lot_ids), затем средние. Пушить только зелёное, на сервер раскатывает таймер. 3) Этап стенда (эмулятор и коллектор в контейнере) — таймбокс. 4) Утром сводка: таблица QA, исправленное, остатки. Будильник 00:30 UTC.
- 2026-10-15 22:05 UTC QA волна по всем 11 модулям завершена (отчёты `factory3d/build/qa/*.md`, реестр `qa/DEFECTS.md`). Итог: все PARTIAL, FAIL нет. base 51/4/13, iot_sim 26/4/10, telemetry 39/9/11, machine_connect 23/2/6, access 12/0/9, energy 15/1/11, yard 21/1/12, bms 15/2/8 (D-1 не подтверждён), fire_safety 18/0/8, viewer 26/0/8, td_genset 24/2/7. V-1 (viewer lot_ids) исправлен `7415e55` и подтверждён. Решение менеджера: демо-часы viewer (2026-10-12 10:30) оставить — база демонстрационная (данные загружены odoo_push.py), DEC-18 по дизайну. QA-ссылка genset id 3 архивирована (публиковала каждую минуту). В работе: coder batch 1 (S-1, T-1, Y-2), стенд в контейнере (таймбокс 1 ч). Дальше: coder batch 2 (P2: M-1, T-2, T-3, T-4, M-2, B-1, B-2, A-1, G-1, S-2, S-3) после batch 1, затем P3.
- 2026-10-15 22:20 UTC Batch 1 (S-1 `376fc5e`, T-1 `26e1b49`, Y-2 `7602a37`) запушен в 22:01 UTC, Run A зелёный у coder. За 20 мин таймер f3d-update его НЕ раскатал. На сервере старый код: поиск yard ещё с context_today, поля is_today нет. Проверка: `button_immediate_upgrade` yard через RPC прошёл, данные взяты с диска, а там старые XML. Предыдущий деплой (viewer `7415e55`) прошёл в 21:31. Причина на сервере неизвестна: доступа к логам нет, SSH закрыт. Нужно утром: `journalctl -u f3d-update`. Миграцию telemetry (`f3d.signal.f3d_run_migration`) запускать только после деплоя T-1.
- 2026-10-15 22:58 UTC Batch 2a запушен (6d10452, Run A 1649/1649). Сервер по-прежнему не раскатывает (поля is_today нет, rate_count на месте; yard write_date 22:14 — это мой ручной RPC-апгрейд). Запущены batch 2b (M-2, B-1, B-2, G-1, context_today в 4 модулях, readonly-форма двери для охраны, drop f3d_collector_push) и фиксы стенда ST-1…ST-4 в отдельном worktree /home/user/f3d-stand, ветка claude/f3d-fix-stand (мерж — менеджер).
