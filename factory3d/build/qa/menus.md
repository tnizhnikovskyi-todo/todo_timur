# QA: все пункты меню factory3d_* и td_genset (timur-o19demo, БД odoo)

Дата: 2026-10-16 07:20 UTC. Сервер: https://timur-o19demo.todo.ltd (Odoo 19 Enterprise), пользователь admin. Режим: только чтение; продуктовый код и данные не менялись, отчёт не закоммичен.

**Меню всего: 168 / OK: 119 / ERROR: 12 / не применимо (родительские): 30 / не выполнялось (мутирующие server-actions): 7**

Уникальных действий: 137 (window 123, server 11, client 3). Меню с общим действием получают общий результат.

## Метод

1. Меню: `ir.ui.menu` с xml id из модулей factory3d_* и td_genset (19 модулей, 168 меню), полный путь по parent_id, действие из поля `action`.
2. Сервер (123 window-действия): `get_views` для каждого вида из `views` + `search`; `web_search_read` limit 5 с контекстом действия (контекст и домен вычислены, literal-домены применены). Ошибок RPC: 0.
3. Браузер (Playwright/Chromium headless, один логин, 3 параллельных контекста): `/odoo/action-<id>`, ожидание network-idle до 25 с (long-polling `/bus/` не считается), перехват console error, pageerror, HTTP >= 400, RPC-ошибок в ответах `/web/dataset|action|view`, `/json`, диалогов (`.o_error_dialog`, `.modal`), danger-уведомлений (MutationObserver). Затем переключение на каждый другой вид (pivot, graph, calendar, kanban, list…) кнопкой переключателя; для действий с list/kanban форма первой записи открыта прямым URL `/odoo/action-<id>/<id первой записи из ответа web_search_read>` (клик по строке/карточке мог бы нажать кнопку/toggle и изменить данные); в форме дополнительно открыты все вкладки notebook (до 8). Скриншоты — только при ошибке (`scratchpad/menus/shots/`).
4. Не выполнялись (меняют данные): 7 server-actions — iot_start/stop/tick, миграции демо-данных (base, yard), повторная установка данных здания (bms), «Звіт перевірки евакуації» (на сервере `compliance_dirty=True`, действие вызовет `action_recompute_compliance()` = запись). Проверено только, что действие существует.
5. Дополнительно (сверх задания): статический разбор 404 views на выражения, ломающиеся в JS-вычислителе; серверная проверка доменов всех фильтров search-видов (`search_count`) и group_by.

Ограничения: ложные предупреждения «нет вида в переключателе» (когда видов list+form переключателя нет) отброшены; формы не проверены там, где записей нет (856, 949, 941, 942 — см. «form: нет записей»); нажатие кнопок, не-default фильтры и группировки в браузере не проверялись; бизнес-логика не проверялась.

## Таблица

| модуль | путь меню | тип действия | проверки | результат | текст ошибки (200 симв.) |
|---|---|---|---|---|---|
| factory3d_access | Відвідування / Звітність / Проходи СКУД | window | srv: get_views(list+pivot+graph+search)+web_search_read(n=2); browser: default,view:pivot,view:graph | OK |  |
| factory3d_access | Відвідування / Налаштування / Сервери BioStar | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_access | Завод 3D / Доступ | — | n/a (родительское меню) | N/A |  |
| factory3d_access | Завод 3D / Доступ / Відвідувачі | window | srv: get_views(list+calendar+form+search)+web_search_read(n=0); browser: default | ERROR | default: console: OwlError: An error occured in the owl lifecycle (see this Error's "cause" property) Error: An error occured in the owl lifecycle (see this Error's "cause" property) at handleError (h |
| factory3d_access | Завод 3D / Доступ / Двері | window | srv: get_views(kanban+list+form+search)+web_search_read(n=5); browser: default,view:list,form#3 | OK |  |
| factory3d_access | Завод 3D / Доступ / Журнал подій | window | srv: get_views(list+form+pivot+graph+search)+web_search_read(n=2); browser: default,view:pivot,view:graph,form#2 | OK |  |
| factory3d_access | Завод 3D / Доступ / Картки | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_access | Завод 3D / Доступ / Користувачі BioStar | window | srv: get_views(list+form+search)+web_search_read(n=36); browser: default | OK |  |
| factory3d_access | Завод 3D / Доступ / Люди по зонах | window | srv: get_views(kanban+list+search)+web_search_read(n=35); browser: default,view:list | OK |  |
| factory3d_access | Завод 3D / Доступ / Повторна обробка | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_access | Завод 3D / Доступ / Пристрої | window | srv: get_views(list+form+search)+web_search_read(n=5); browser: default | OK |  |
| factory3d_access | Завод 3D / Доступ / Сервери BioStar | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_access | Завод 3D / Налаштування / Налаштування СКУД | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_base | Завод 3D | — | n/a (родительское меню) | N/A |  |
| factory3d_base | Завод 3D / Завод | — | n/a (родительское меню) | N/A |  |
| factory3d_base | Завод 3D / Завод / Ворота | window | srv: get_views(list+form+search)+web_search_read(n=16); browser: default | OK |  |
| factory3d_base | Завод 3D / Завод / Зони | window | srv: get_views(kanban+list+form+search)+web_search_read(n=49); browser: default,view:list,form#47 +5 вкл. | OK |  |
| factory3d_base | Завод 3D / Завод / Обладнання зі сцени | window | srv: get_views(list+form+search)+web_search_read(n=214); browser: default | OK |  |
| factory3d_base | Завод 3D / Завод / Паспорти обладнання | window | srv: get_views(list+form+search)+web_search_read(n=93); browser: default | OK |  |
| factory3d_base | Завод 3D / Налаштування | — | n/a (родительское меню) | N/A |  |
| factory3d_base | Завод 3D / Налаштування / Джерела паспортів | window | srv: get_views(list+search)+web_search_read(n=252); browser: default | OK |  |
| factory3d_base | Завод 3D / Налаштування / Параметри паспортів | window | srv: get_views(list+search)+web_search_read(n=999); browser: default | OK |  |
| factory3d_base | Завод 3D / Налаштування / Параметри системи | window | srv: get_views(list+form+search)+web_search_read(n=206); browser: default | OK |  |
| factory3d_base | Завод 3D / Налаштування / Повторити міграцію демо-даних | server | server action найден; не выполнялось | SKIP | мутирует: повторная миграция демо-данных |
| factory3d_bms | Завод 3D / Будівля | — | n/a (родительское меню) | N/A |  |
| factory3d_bms | Завод 3D / Будівля / Вентиляція й опалення | — | n/a (родительское меню) | N/A |  |
| factory3d_bms | Завод 3D / Будівля / Вентиляція й опалення / Тепловий баланс | server | browser: default | OK |  |
| factory3d_bms | Завод 3D / Будівля / Вентиляція й опалення / Установки | window | srv: get_views(list+kanban+form+search)+web_search_read(n=29); browser: default,view:kanban,form#1 +2 вкл. | OK |  |
| factory3d_bms | Завод 3D / Будівля / Відхилення | window | srv: get_views(list+graph+pivot+form+search)+web_search_read(n=54); browser: default,view:graph,view:pivot,form#54 | OK |  |
| factory3d_bms | Завод 3D / Будівля / Огляд | client | browser: default | OK |  |
| factory3d_bms | Завод 3D / Будівля / Освітлення | — | n/a (родительское меню) | N/A |  |
| factory3d_bms | Завод 3D / Будівля / Освітлення / Групи | window | srv: get_views(kanban+list+form+search)+web_search_read(n=32); browser: default,view:list,form#1 +3 вкл. | OK |  |
| factory3d_bms | Завод 3D / Будівля / Освітлення / Норми освітленості | window | srv: get_views(list+form+search)+web_search_read(n=14); browser: default | OK |  |
| factory3d_bms | Завод 3D / Будівля / Освітлення / Щити | window | srv: get_views(list+form+search)+web_search_read(n=3); browser: default | OK |  |
| factory3d_bms | Завод 3D / Налаштування / Будівля | — | n/a (родительское меню) | N/A |  |
| factory3d_bms | Завод 3D / Налаштування / Будівля / Налаштування будівлі | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_bms | Завод 3D / Налаштування / Будівля / Повторити установку даних будівлі | server | server action найден; не выполнялось | SKIP | мутирует: повторная установка данных здания |
| factory3d_bms | Завод 3D / Налаштування / Будівля / Сцени DALI | window | srv: get_views(list+search)+web_search_read(n=6); browser: default | OK |  |
| factory3d_energy | Завод 3D / Енергетика | — | n/a (родительское меню) | N/A |  |
| factory3d_energy | Завод 3D / Енергетика / Баланс обліку | window | srv: get_views(list+search)+web_search_read(n=264); browser: default | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Відключення | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Енергія на виробництво | window | srv: get_views(pivot+graph+list+search)+web_search_read(n=45); browser: default,view:graph,view:list | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Журнал подій | window | srv: get_views(list+search)+web_search_read(n=201); browser: default | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Лічильники | window | srv: get_views(list+kanban+form+search)+web_search_read(n=67); browser: default,view:kanban,form#54 | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Налаштування | — | n/a (родительское меню) | N/A |  |
| factory3d_energy | Завод 3D / Енергетика / Налаштування / Перерахувати | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Налаштування / Пули спільних споживачів | window | srv: get_views(list+form+search)+web_search_read(n=5); browser: default | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Налаштування / Тарифи й договір | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Огляд | window | srv: get_views(kanban+list+form+search)+web_search_read(n=8); browser: default,view:list,form#5 +2 вкл. | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Профіль | window | srv: get_views(graph+pivot+list+search)+web_search_read(n=1809); browser: default,view:pivot,view:list | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Пік і вартість | window | srv: get_views(pivot+list+search)+web_search_read(n=162); browser: default,view:list | OK |  |
| factory3d_energy | Завод 3D / Енергетика / Схема мережі | window | srv: get_views(hierarchy+list+form+search)+web_search_read(n=123); browser: default,view:list,form#84 +2 вкл. | OK |  |
| factory3d_energy | Завод 3D / Налаштування / Енергетика | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_fire_safety | Завод 3D / Налаштування / Налаштування пожежної безпеки | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_fire_safety | Завод 3D / Пожежна безпека | — | n/a (родительское меню) | N/A |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Евакуація | — | n/a (родительское меню) | N/A |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Евакуація / Виходи | window | srv: get_views(list+form+search)+web_search_read(n=12); browser: default | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Евакуація / Димові зони | window | srv: get_views(list+form+search)+web_search_read(n=8); browser: default | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Евакуація / Звіт перевірки | server | server action найден; не выполнялось | SKIP | мутирует: compliance_dirty=True, действие вызовет action_recompute_compliance() (write) |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Евакуація / Маршрути | window | srv: get_views(list+form+search)+web_search_read(n=32); browser: default | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Журнал подій | window | srv: get_views(list+form+graph+search)+web_search_read(n=28); browser: default,view:graph,form#28 | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Зони сигналізації | window | srv: get_views(kanban+list+form+search)+web_search_read(n=35); browser: default,view:list,form#1 +1 вкл. | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Навчальні тривоги | window | srv: get_views(list+form+calendar+search)+web_search_read(n=1); browser: default,view:calendar,form#1 +3 вкл. | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Налаштування | — | n/a (родительское меню) | N/A |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Налаштування / Шаблони навчань | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Налаштування / Шлейфи | window | srv: get_views(list+form+search)+web_search_read(n=4); browser: default | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Норми | window | srv: get_views(list+form+search)+web_search_read(n=27); browser: default | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Огляд | window | srv: get_views(kanban+form+search)+web_search_read(n=1); browser: default | ERROR | default: console: OwlError: An error occured in the owl lifecycle (see this Error's "cause" property) Error: An error occured in the owl lifecycle (see this Error's "cause" property) at handleError (h |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Пристрої | window | srv: get_views(list+form+search)+web_search_read(n=353); browser: default | OK |  |
| factory3d_fire_safety | Завод 3D / Пожежна безпека / Системи | window | srv: get_views(list+form+search)+web_search_read(n=3); browser: default | OK |  |
| factory3d_fire_safety | Обслуговування / Обслуговування / Заявки пожежної безпеки | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_genset | Завод 3D / Генератор | — | n/a (родительское меню) | N/A |  |
| factory3d_genset | Завод 3D / Генератор / Заявки ТО генератора | window | srv: get_views(kanban+list+form+search)+web_search_read(n=1); browser: default,view:list,form#49 +1 вкл. | OK |  |
| factory3d_genset | Завод 3D / Генератор / Зв'язка | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_genset | Завод 3D / Генератор / Події → ТО | window | srv: get_views(list+form+search)+web_search_read(n=48); browser: default | OK |  |
| factory3d_genset | Завод 3D / Генератор / Профілі | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_genset | Завод 3D / Налаштування / Налаштування генератора | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_iot_sim | Завод 3D / Емулятор | — | n/a (родительское меню) | N/A |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Запуски | window | srv: get_views(list+form+search)+web_search_read(n=4); browser: default | OK |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Каталог сигналів | window | srv: get_views(list+form+search)+web_search_read(n=1168); browser: default | OK |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Події | window | srv: get_views(list+search)+web_search_read(n=2); browser: default | OK |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Пристрої | window | srv: get_views(list+form+search)+web_search_read(n=280); browser: default | OK |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Пульт | server | browser: default | OK |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Рівень 0 (без сервісу) | — | n/a (родительское меню) | N/A |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Рівень 0 (без сервісу) / Журнал показань | window | srv: get_views(graph+list+search)+web_search_read(n=57036); browser: default,view:list / НЕДОСТУПНО из UI: родитель factory3d_iot_sim.menu_iot_root неактивен | OK |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Рівень 0 (без сервісу) / Зупинити імітацію | server | server action найден; не выполнялось / НЕДОСТУПНО из UI: родитель factory3d_iot_sim.menu_iot_root неактивен | SKIP | мутирует: выключает cron имитации (write active=False) |
| factory3d_iot_sim | Завод 3D / Емулятор / Рівень 0 (без сервісу) / Оновити зараз | server | server action найден; не выполнялось / НЕДОСТУПНО из UI: родитель factory3d_iot_sim.menu_iot_root неактивен | SKIP | мутирует: запускает тик имитации (пишет сигналы/показания) |
| factory3d_iot_sim | Завод 3D / Емулятор / Рівень 0 (без сервісу) / Сигнали обладнання | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default / НЕДОСТУПНО из UI: родитель factory3d_iot_sim.menu_iot_root неактивен | OK |  |
| factory3d_iot_sim | Завод 3D / Емулятор / Рівень 0 (без сервісу) / Увімкнути імітацію | server | server action найден; не выполнялось / НЕДОСТУПНО из UI: родитель factory3d_iot_sim.menu_iot_root неактивен | SKIP | мутирует: включает cron имитации (write active=True) |
| factory3d_iot_sim | Завод 3D / Емулятор / Сценарії | window | srv: get_views(kanban+list+form+search)+web_search_read(n=15); browser: default,view:list,form#1 | OK |  |
| factory3d_iot_sim | Завод 3D / Налаштування / Налаштування емулятора | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_machine_connect | Завод 3D / Верстати | — | n/a (родительское меню) | N/A |  |
| factory3d_machine_connect | Завод 3D / Верстати / OEE | window | srv: get_views(list+pivot+graph+form+search)+web_search_read(n=70); browser: default,view:pivot,view:graph,form#65 | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Журнал станів | window | srv: get_views(list+graph+pivot+search)+web_search_read(n=175); browser: default,view:graph,view:pivot | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Налаштування | — | n/a (родительское меню) | N/A |  |
| factory3d_machine_connect | Завод 3D / Верстати / Налаштування / Верстати (підключення) | window | srv: get_views(list+form+search)+web_search_read(n=35); browser: default | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Налаштування / Повідомлення верстатів | window | srv: get_views(list+search)+web_search_read(n=10); browser: default | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Налаштування / Причини простоїв | window | srv: get_views(list+form+search)+web_search_read(n=10); browser: default | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Огляд верстатів | window | srv: get_views(kanban+list+form+search)+web_search_read(n=35); browser: default,view:list,form#30 +3 вкл. | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Події верстатів | window | srv: get_views(list+form+search)+web_search_read(n=3); browser: default | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Портал | — | n/a (родительское меню) | N/A |  |
| factory3d_machine_connect | Завод 3D / Верстати / Портал / Завдання порталу | window | srv: get_views(list+kanban+form+search)+web_search_read(n=0); browser: default,view:kanban,form | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Портал / Стоси під порталом | window | srv: get_views(kanban+list+form+search)+web_search_read(n=27); browser: default,view:list,form#1 +1 вкл. | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Простої | window | srv: get_views(list+kanban+form+graph+pivot+search)+web_search_read(n=80); browser: default,view:kanban,view:graph,view:pivot,form#116 +1 вкл. | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Простої без причини | window | srv: get_views(kanban+form+search)+web_search_read(n=80); browser: default | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Розкрій | — | n/a (родительское меню) | N/A |  |
| factory3d_machine_connect | Завод 3D / Верстати / Розкрій / Деталі виробів | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_machine_connect | Завод 3D / Верстати / Розкрій / Карти розкрою | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_machine_connect | Завод 3D / Налаштування / Налаштування верстатів | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_telemetry | Завод 3D / Налаштування / Налаштування телеметрії | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_telemetry | Завод 3D / Телеметрія | — | n/a (родительское меню) | N/A |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Годинні агрегати | window | srv: get_views(pivot+graph+list+search)+web_search_read(n=13485); browser: default,view:graph,view:list | OK |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Джерела | window | srv: get_views(list+form+kanban+search)+web_search_read(n=137); browser: default,view:kanban,form#104 +3 вкл. | OK |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Колектори | window | srv: get_views(list+form+search)+web_search_read(n=5); browser: default | OK |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Команди | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Огляд | window | srv: get_views(kanban+list+form+search)+web_search_read(n=137); browser: default,view:list,form#104 +3 вкл. | OK |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Події HTTP push | window | srv: get_views(list+form+search)+web_search_read(n=15); browser: default | OK |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Показання | window | srv: get_views(graph+list+search)+web_search_read(n=146544); browser: default,view:list | OK |  |
| factory3d_telemetry | Завод 3D / Телеметрія / Сигнали | window | srv: get_views(list+form+graph+pivot+search)+web_search_read(n=1244); browser: default,view:graph,view:pivot,form#232 +4 вкл. | OK |  |
| factory3d_telemetry | Обслуговування / Телеметрія | window | srv: get_views(list+form+graph+pivot+search)+web_search_read(n=1244); browser: default,view:graph,view:pivot,form#232 +4 вкл. | OK |  |
| factory3d_viewer | Завод 3D / Демо-дані | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_viewer | Завод 3D / Журнал станів | — | n/a (родительское меню) | N/A |  |
| factory3d_viewer | Завод 3D / Журнал станів / Знімки | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_viewer | Завод 3D / Журнал станів / Події | window | srv: get_views(list+search)+web_search_read(n=1350); browser: default | OK |  |
| factory3d_viewer | Завод 3D / Налаштування / Налаштування переглядача | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| factory3d_viewer | Завод 3D / Перевірка циклу | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_viewer | Завод 3D / Переглядач | client | browser: default; примечание: ложное срабатывание детектора «blank» (у клиентского действия нет .o_content); UI отрисован, JS-ошибок нет; 3D-сцена за 25-40 с в headless не догрузилась («Завантаження моделі…») — не проверено | OK |  |
| factory3d_yard | Завод 3D / Двір | — | n/a (родительское меню) | N/A |  |
| factory3d_yard | Завод 3D / Двір / Бронювання воріт | window | srv: get_views(gantt+calendar+list+form+search)+web_search_read(n=8); browser: default,view:calendar,view:list,form#1 | OK |  |
| factory3d_yard | Завод 3D / Двір / Диспетчеризація (стандарт) | server | browser: default,view:list | OK |  |
| factory3d_yard | Завод 3D / Двір / Диспетчерська | window | srv: get_views(kanban+list+form+pivot+graph+search)+web_search_read(n=9); browser: default,view:list,view:pivot,view:graph,form#8 +4 вкл. | OK |  |
| factory3d_yard | Завод 3D / Двір / Екран КПП | client | browser: default | OK |  |
| factory3d_yard | Завод 3D / Двір / Журнали | — | n/a (родительское меню) | N/A |  |
| factory3d_yard | Завод 3D / Двір / Журнали / Зважування | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_yard | Завод 3D / Двір / Журнали / Команди на шлагбауми | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| factory3d_yard | Завод 3D / Двір / Журнали / Розпізнавання номерів | window | srv: get_views(list+form+search)+web_search_read(n=4); browser: default | OK |  |
| factory3d_yard | Завод 3D / Двір / Звіти | — | n/a (родительское меню) | N/A |  |
| factory3d_yard | Завод 3D / Двір / Звіти / Зайнятість воріт | window | srv: get_views(pivot+graph+list+search)+web_search_read(n=1); browser: default,view:graph,view:list | OK |  |
| factory3d_yard | Завод 3D / Двір / Звіти / Рейси (аналіз) | window | srv: get_views(pivot+graph+list+search)+web_search_read(n=9); browser: default,view:graph,view:list | OK |  |
| factory3d_yard | Завод 3D / Двір / Налаштування | — | n/a (родительское меню) | N/A |  |
| factory3d_yard | Завод 3D / Двір / Налаштування / Автоваги | window | srv: get_views(list+form+search)+web_search_read(n=1); browser: default | OK |  |
| factory3d_yard | Завод 3D / Двір / Налаштування / КПП і шлагбауми | window | srv: get_views(list+form+search)+web_search_read(n=2); browser: default | OK |  |
| factory3d_yard | Завод 3D / Двір / Налаштування / Повторити міграцію двору | server | server action найден; не выполнялось | SKIP | мутирует: повторная миграция двора |
| factory3d_yard | Завод 3D / Двір / Рейси | window | srv: get_views(list+form+kanban+pivot+graph+search)+web_search_read(n=9); browser: default,view:kanban,view:pivot,view:graph,form#8 +4 вкл. | OK |  |
| factory3d_yard | Завод 3D / Налаштування / Налаштування двору | window | srv: get_views(form+search)+web_search_read(n=0); browser: default | ERROR | default: console: Failed to load resource: the server responded with a status of 404 () @ /uk/factory3d_bms/static/description/icon.png |
| td_genset | Генератори | — | n/a (родительское меню) | N/A |  |
| td_genset | Генератори / Аналітика | — | n/a (родительское меню) | N/A |  |
| td_genset | Генератори / Аналітика / Вироблено по днях | window | srv: get_views(graph+pivot+list+search)+web_search_read(n=0); browser: default,view:pivot,view:list | OK |  |
| td_genset | Генератори / Аналітика / Витрата по днях | window | srv: get_views(graph+pivot+list+search)+web_search_read(n=0); browser: default,view:pivot,view:list | OK |  |
| td_genset | Генератори / Аналітика / Навантаження під час роботи | window | srv: get_views(graph+list+pivot+search)+web_search_read(n=0); browser: default,view:list,view:pivot | OK |  |
| td_genset | Генератори / Аналітика / Напруга АКБ | window | srv: get_views(graph+pivot+list+search)+web_search_read(n=0); browser: default,view:pivot,view:list | OK |  |
| td_genset | Генератори / Аналітика / Пуски і АКБ при прокрутці | window | srv: get_views(graph+list+pivot+search)+web_search_read(n=0); browser: default,view:list,view:pivot | OK |  |
| td_genset | Генератори / Аналітика / Робота і відключення по днях | window | srv: get_views(graph+pivot+list+search)+web_search_read(n=0); browser: default,view:pivot,view:list | OK |  |
| td_genset | Генератори / Аналітика / Рівень палива | window | srv: get_views(graph+pivot+list+search)+web_search_read(n=0); browser: default,view:pivot,view:list | OK |  |
| td_genset | Генератори / Генератор | server | browser: default | OK |  |
| td_genset | Генератори / Заправка | — | n/a (родительское меню) | N/A |  |
| td_genset | Генератори / Заправка / Заправки | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| td_genset | Генератори / Заправка / Каністри | window | srv: get_views(kanban+list+form+search)+web_search_read(n=0); browser: default,view:list,form | OK |  |
| td_genset | Генератори / Заправка / Рух запасу | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| td_genset | Генератори / Налаштування | — | n/a (родительское меню) | N/A |  |
| td_genset | Генератори / Налаштування / Генератори | window | srv: get_views(list+kanban+form+search)+web_search_read(n=1); browser: default,view:kanban,form#1 +7 вкл. | OK |  |
| td_genset | Генератори / Налаштування / Ланцюжок ескалації | window | srv: get_views(list+search)+web_search_read(n=3); browser: default | OK |  |
| td_genset | Генератори / Налаштування / Моделі контролерів | window | srv: get_views(list+form+search)+web_search_read(n=2); browser: default | OK |  |
| td_genset | Генератори / Налаштування / Місця зберігання | window | srv: get_views(list+form+search)+web_search_read(n=0); browser: default | OK |  |
| td_genset | Генератори / Налаштування / Налаштування | window | srv: get_views(form+search)+web_search_read(n=1); browser: default | OK |  |
| td_genset | Генератори / Налаштування / Ролі доступу | window | srv: get_views(list+form+kanban+search)+web_search_read(n=14); browser: default,view:kanban,form#2 +3 вкл. | OK |  |
| td_genset | Генератори / Події | window | srv: get_views(list+calendar+graph+pivot+form+search)+web_search_read(n=0); browser: default,view:calendar,view:graph,view:pivot,form | OK |  |
| td_genset | Генератори / Показання | window | srv: get_views(list+graph+pivot+form+search)+web_search_read(n=0); browser: default,view:graph,view:pivot,form | OK |  |

## Ошибки и воспроизведение


**E-1. Завод 3D / Доступ / Відвідувачі** (`factory3d_access.menu_f3d_access_visitor`, action 825, `f3d.access.visitor`) — ERROR, P1 (меню не открывается).
Диалог «От халепа!» (OwlError), `TypeError: Cannot read properties of undefined (reading 'hour')` в `PyDateTime.combine`.
Причина: действие применяет `search_default_today`, а фильтр `today` в `factory3d_access.view_f3d_access_visitor_search` использует `datetime.time.max` / `datetime.time.min`; JS-вычислитель домена Odoo (py.js) их не поддерживает.
Воспроизведение: войти admin, открыть `/odoo/action-825` (или меню «Відвідувачі»). Исправление: `datetime.time(23, 59, 59)` и `datetime.time(0, 0, 0)` (как в td_genset). Виды list/calendar после падения не проверялись.

**E-2. Завод 3D / Пожежна безпека / Огляд пожежної сигналізації** (`factory3d_fire_safety.menu_f3d_fire_overview`, action 914, `f3d.fire.panel`) — ERROR, P1 (меню не открывается).
Диалог «От халепа!» (OwlError), `TypeError: Cannot use 'in' operator to search for 'normal' in prealarm`.
Причина: в kanban `factory3d_fire_safety.view_f3d_fire_panel_kanban` шаблон `t-attf-class` содержит Python-синтаксис `record.state.raw_value in ('alarm','prealarm') ? … : record.state.raw_value in ('fault','disabled') ? …` внутри JS-выражения; в JS это `x in 'prealarm'` -> TypeError.
Воспроизведение: открыть `/odoo/action-914` (в данных есть панель 1). Исправление: `['alarm','prealarm'].includes(record.state.raw_value)` и `['fault','disabled'].includes(...)`. Форма панели после падения не проверялась.

**E-3. 10 меню «Налаштування» модулей** — ERROR, P3 (косметика, меню открываются).
Меню: access (826), bms (906), energy (879), fire_safety (927), genset (968), iot_sim (795), machine_connect (862), telemetry (810), viewer (836), yard (893) (`*.menu_*settings*`/`*config*`, `res.config.settings`).
Ошибка консоли: `Failed to load resource: 404` для `/uk/factory3d_bms/static/description/icon.png`. Единая причина: у модуля `factory3d_bms` нет `static/description/icon.png` (ссылка из блока настроек/иконки приложения). Прочие страницы настроек тоже загружают этот блок; 404 попал в лог не на всех из-за кеша браузера.
Воспроизведение: открыть любую страницу «Налаштування» (`/odoo/action-826`), в консоли браузера 404 на icon.png. Связано с T-5 («нет icon.png») из DEFECTS.md.

**Не ошибки меню, но найдено попутно (серверная проверка доменов фильтров):**
- **F-1.** `f3d.gantry.stack`, фильтр «Нижче мінімуму» (`f_below_min`, поиск-вид действия 855, меню «Завод 3D / Верстати / Портал / Стоси під порталом», `factory3d_machine_connect.menu_f3d_mc_gantry_stack`): домен `[('ws_qty', '<', 'min_qty')]` сравнивает поле со строкой `'min_qty'`; при нажатии фильтра `search_count` падает: `ValueError: invalid literal for int() with base 10: 'min_qty'`. Odoo не умеет сравнивать поле с полем в домене; нужен stored-compute булево поле или `filtered`-метод. Воспроизведение RPC: `f3d.gantry.stack.search_count([('ws_qty','<','min_qty')])`. P2.
- **N-1.** Меню под неактивным корнем `factory3d_iot_sim.menu_iot_root` («Завод 3D / Емулятор / Рівень 0 (без сервісу)», 5 пунктов: журнал показаний, сигнали обладнання, увімкнути/зупинити/оновити) не видны в UI (active=False); по URL действия открываются. Скорее всего намеренно (уровень 0 выключен, T-1); просто отметка.

- **Оговорка по серверной проверке фильтров:** первый прогон показал только 825 и 855 (+ пропуски вычисления `datetime`/`time` в моём упрощённом eval, это ограничение проверки, не дефекты td_genset/machine_connect); начало вывода (действия с id < 825) было обрезано, повторный прогон не завершился в рамках таймбокса. Полнота проверки фильтров действий 777–822 не подтверждена.

## Итог
Из 168 меню: 30 родительских (n/a), 7 мутирующих не выполнялись, 131 проверено: 119 OK, 12 ERROR (2 функциональные P1 + 10 косметических 404 иконки). Остальные 118 уникальных действий (включая клиентское «Завод 3D» с примечанием) открываются без ошибок в консоли, RPC и UI; виды pivot/graph/calendar/kanban/list переключаются, формы первых записей и их вкладки открываются без ошибок.
