# QA viewer
Статус: PARTIAL
Проверено: 26, провалено: 0, не проверено: 8 (2026-10-15, коммит 29a088e; фикс 7415e55 проверен поведением)
Дефекты: 0 (критичных: 0)
Мусор в базе: res.users id 15 `qa-viewer-mrp`, id 16 `qa-viewer-nomrp`, id 17 `qa-viewer-none` (имена `QA-viewer-…`). Записей f3d.* не создавал. Удалить пользователей вручную, если не нужны.

Сервер: timur-o19demo.todo.ltd, база `odoo`, коннектор `AxI--dg8QCmJAxW_` (connection.db = odoo). Модули `factory3d_viewer` и `factory3d_viewer_sale` installed, версия 19.0.1.0.0 (совпадает с манифестом).

Входные документы: в задании указаны `build/modules/viewer.md` и `docs/modules/viewer/SPEC.md`, таких файлов нет. Использованы `build/modules/factory3d_viewer.md` и `docs/modules/factory3d_viewer/SPEC.md` (66 строк AC).

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка (AC-55, часть) | RPC `ir.module.module` | OK: оба модуля installed, 19.0.1.0.0; sale-мост `auto_install=True` | RPC-вывод |
| 2 | Меню «Завод 3D» (AC-64, AC-01, часть) | RPC `ir.ui.menu`, `ir.actions.client` + браузер | OK: меню id 481, группа `group_f3d_user`, действие `f3d_viewer.action` id 828; открывается `/odoo/action-828` | `scratchpad/qa/viewer/viewer_admin.png` |
| 3 | Провайдер stock (фикс 7415e55) | `GET /f3d/viewer/data?full=1` | OK: products 57, locations 701 с квантами, `meta.errors` пустой | HTTP |
| 4 | Провайдер quality (фикс 7415e55) | то же | OK: quality_checks 5, поле `lot` заполнено (напр. `DSP16-ANT-2608-77`) | HTTP |
| 5 | Провайдер logistics (фикс 7415e55) | то же | OK: pickings 44, docks 15, sale_orders 8, purchase_orders 13 | HTTP |
| 6 | Провайдер production | то же | OK: workcenters 38, productions 32, workorders 199 | HTTP |
| 7 | Провайдер maintenance | то же | OK: equipment 213, maintenance_requests 44 | HTTP |
| 8 | Провайдер people | то же | OK: employees 37 | HTTP |
| 9 | Провайдер chains | то же | OK: sheet_chain, ship_chain, material_paths 6, full_cycle_mo `WH/MO/00237` | HTTP |
| 10 | Провайдер signals | то же | OK: energy, lighting, ventilation, fire, infra, evacuation в статусе live | HTTP |
| 11 | Изоляция сбоев провайдеров (AC-13, часть) | `meta.errors` и `meta.sections` | OK: ошибок нет, все разделы live/static | HTTP |
| 12 | `/f3d/viewer/static` (AC-10, часть) | HTTP с сессией | 200 с ETag; повтор с If-None-Match → 304 | HTTP |
| 13 | `/f3d/viewer/delta` | HTTP | `since` в ISO с `Z` → 200 (events, patch, removed, ts); неверный формат → 400 `bad_request` (ожидаемо) | HTTP |
| 14 | `/f3d/viewer/resolve` (AC-40, часть) | HTTP | `PLT-04C` → 200, stock.location; `PLT-04C'; DROP` → 400 `bad_request` | HTTP |
| 15 | `/parts/manifest.json`, `/snapshots`, `/cycle_check` | HTTP | 200; 200 (1 снимок, kind=install); 200 (ok=false, 2 замечания по складу QAB, это данные) | HTTP |
| 16 | Доступ без входа | HTTP без сессии | 303 на `/web/login` | HTTP |
| 17 | AC-14: пользователь без mrp | `qa-viewer-nomrp`: `/data` | productions, workorders, workcenters пустые; sections denied; остальные live | HTTP |
| 18 | Пользователь без групп factory3d | `qa-viewer-none`: `/data` | 403 `forbidden`, «Немає доступу до переглядача «Завод 3D»» | HTTP |
| 19 | Полный доступ MRP | `qa-viewer-mrp`: `/data` | 200, productions 32, все разделы live, errors пусто | HTTP |
| 20 | AC-54: пункты меню по группам | браузер: admin и `qa-viewer-nomrp` | «Журнал станів», «Перевірка циклу», «Демо-дані» видны admin, у nomrp отсутствуют | текст страницы |
| 21 | 3D-вид, админ (AC-03, AC-05, часть) | Playwright, headless, `/opt/pw-browsers/chromium` | вход, сцена загружена за 33 с, canvas=1, console errors 0, pageerror 0, ответов 4xx/5xx 0 | `viewer_admin.png` |
| 22 | 3D-вид, nomrp | Playwright | вход, canvas=1, console errors 0, pageerror 0 | текст страницы |
| 23 | Шина live (AC-19, AC-20, часть) | RPC `f3d.viewer.event`, `ir.config_parameter`; браузер | `factory3d.viewer.bus_enabled=True`; 107 событий, последнее signal 2026-10-15 21:34:42; клиент получил `/delta` 200 за 15 с | RPC + браузер |
| 24 | Sale-мост: действие (AC-23, часть) | RPC `sale.order.action_f3d_show` на S00087 (только чтение) | возвращает `ir.actions.client` `f3d_viewer.action`, params `{mo: WH/MO/00239, so: S00087}` | RPC-вывод |
| 25 | Sale-мост: вид формы (AC-22, часть) | RPC `ir.ui.view` | `factory3d_viewer_sale.view_order_form_f3d_show` наследует `sale.order.form` | RPC-вывод |
| 26 | Фикс 7415e55 в коде | git | 29a088e является предком 7415e55 (фикс новее ревизии установки). Версия по коду на сервере не сверена, подтверждено поведением: quality/stock/logistics без ошибок | git log |

## Дефекты

Нет. Ошибок сервера (500, трейсбеков) на проверенных сценариях не найдено. Ошибки 400/403 получены только там, где они ожидаются по SPEC.

## Наблюдения (не дефекты, решить менеджеру)

1. Тестовая база работает на демо-часах: `meta.now = 2026-10-12 10:30`, в `meta.note` написано «Демо-годинник зупинено». Сегодня 2026-10-15. DEC-18 исходит из пустого `demo_clock` на проде. Проверить, задано ли это сознательно на тест-базе.
2. В `/snapshots` один снимок `kind=install` за 2026-10-12. Периодических снимков (крон `_cron_snapshot`, окно 06:30–16:00) не видно. Крон не проверял, возможная причина связана с п. 1.
3. `/cycle_check` видит 2 замечания по складу QAB (`QAB/IN/00001`, `QAB/IN/00002`: «приймання без західних воріт»). Это данные тестового склада, не код модуля.
4. В коннекторе odoo-mcp `odoo_search_read` на `ir.module.module` вернул общую ошибку. Через RPC-хелпер тот же запрос прошёл. Проблема коннектора, не модуля.
5. Индикатор шины в тексте страницы показывает «Odoo підключення…». Визуально на скриншоте не сверял. Сам канал работает (`/delta` 200).

## Не проверено и почему

1. Периодические снимки и ротация (AC-25, AC-26, AC-27): нужен разбор крона, не делал, лимит HTTP.
2. Киоск (AC-28, AC-29, AC-32, AC-48, AC-50): нужен токен киоска, не запрашивал.
3. AC-16, AC-18 (дельта после изменения остатка, пакетные события): требуют записи в базу, по заданию не делал.
4. Майстер демо (AC-33, AC-35, AC-36): запускает заливку данных, не запускал.
5. AC-38 (пересборка dist через Blender), ТК-07 (планшет): вне среды, как указано в отчёте лидера.
6. ТК-09 (повторный ▶ не останавливает проигрывание): не проверял.
7. Кнопка «Показати в 3D» на формах SO и МО визуально (AC-22, AC-23): проверены RPC-действие и наследование вида, не UI.
8. Тесты модуля (`test_*`, hoot): не запускались, задача QA — смоук на живой базе.

## Лимиты и среда

- Прямых HTTP-запросов (скрипты, RPC-хелпер, без браузера): 50 из 50.
- Вызовов odoo-mcp: 3 (один ошибочный на `ir.module.module`, остальные в RPC-хелпере).
- Браузер: Playwright (Node) с `/opt/pw-browsers/chromium`, headless, `--enable-unsafe-swiftshader`.
- Пароли тестовых пользователей записаны в `scratchpad/qa/viewer/users.cred` (права 600). В отчёт не выводились.
- Ничего не удалялось. Модули не устанавливались и не обновлялись. Код не менялся. Отчёт не коммитился.
