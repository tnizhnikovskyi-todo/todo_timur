# QA telemetry
Статус: PARTIAL (API, токены, сигналы, заявки, крони — PASS; миграция прототипа iot_sim на этой базе — FAIL)
Проверено: 39, провалено: 9, не проверено: 11 (2026-10-15, коммит 29a088e)
Дефекты: 8 (критичных: 1)
Мусор в базе: см. раздел «Мусор в базе» ниже (QA-записи, ничего не удалялось)

Объект: `factory3d_telemetry` (19.0.1.1.0) и мосты `factory3d_telemetry_viewer`, `factory3d_access_telemetry` (только стык) на базе `odoo`
(https://timur-o19demo.todo.ltd, Odoo 19.0 Enterprise). Коннектор odoo-mcp `AxI--dg8QCmJAxW_`, `connection.db == "odoo"`.
Время работы: 20:46–21:15 UTC. Код — только чтение, `/home/user/f3d-build/factory3d/odoo_addons/factory3d_telemetry/`.
Глобальные параметры не менялись: попытка временно поставить `push_rate_per_min=3` (AC-41) была отклонена классификатором прав
(«Modify Shared Resources»), обхода я не искал. Значения `push_rate_per_min=60`, `read_enabled=True`, `write_enabled=False` проверены в конце.

QA-фикстуры: колектор `QA-TELE-C1` (id 2, имя «QA-telemetry-collector»), источник `QA-TELE-S1` (id 137, modbus_tcp, 127.0.0.1:502, службы нет),
сигналы `equipment/QA-TELE/{pressure_bar,state,hours,temp_c,free}` (id 1214–1218), оборудование `QA-telemetry-equipment` (id 211),
пользователи `qa-telemetry-user` (id 7) и `qa-telemetry-manager` (id 8). Токен колектора отозван, пароли пользователей перезаписаны
случайными значениями, нигде не сохранёнными.

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка: telemetry 19.0.1.1.0, viewer 19.0.1.0.0, access_telemetry 19.0.1.0.0 = манифест | ir.module.module | PASS | все `installed` |
| 2 | 10 действий меню (сигналы, тревоги, колекторы, источники, обзор, показания, агрегаты, команды, события, настройки) и формы колектора/сигнала/источника/оборудования/заявки открываются | Playwright | PASS | без диалога ошибки и JS-ошибок; показания открываются графиком, агрегаты — pivot (так в action) |
| 3 | `get_views` list/form/search для 7 моделей, form для equipment/request/settings | JSON-RPC | PASS | без ошибок |
| 4 | Действие «Телеметрия» (`action_f3d_signal_alarm`, фильтр «Тривога») | Playwright | FAIL | D4: фасет «Тривога или Увімкнені», пагинация 1–80 / 1218 вместо тревог |
| 5 | Миграция, шаги 2/3/3а: 196 `sim_data`, by_module energy 87 / telemetry 27 / bms 81 / fire_safety 1, 196 xml-id `sig_*`, catalog created 29 / bound 55 / bind_missing 0, meters 9 | `level0_migrated` + ORM | PASS | как в AC-58 |
| 6 | Миграция, шаги 5/7: `f3d.reading(sim_data)` 56840 = `x_f3d_reading` на момент установки, `received_at` = `create_date`, 196 × 48 ч = 9408 агрегатов | ORM | PASS | `skipped_null_ts=0`; выборка RV-05: агрегат часа совпадает с сырыми показаниями |
| 7 | Миграция, шаг 8 и итог (AC-58): `mismatches=[]`, `state='done'` | `level0_migrated` | FAIL | D1: `state='partial'`, `mismatches=["equipment/FL-5/battery: status warn != x_state норма"]` |
| 8 | Миграция, шаг 6 `requests_level0` (AC-58 `requests_linked`) | ORM | FAIL | D1: шаг не выполнен; у 28 сигналов уровня 0 есть `x_request_id`, но у `f3d.signal` `maintenance_request_id` пуст (RV-05: заявка 6 открыта, связи нет); `f3d_origin='threshold'` — 0 заявок |
| 9 | Миграция, шаг 9 `level0_off` (AC-58 `cron_iot_sim.active=False`, `x_active=False` у 196) | ORM | FAIL | D1: крон 42 «Емулятор IoT: рівень 0» активен, `x_active=False` — 0 записей, `factory3d.iot_sim.level0_enabled=True` |
| 10 | Повторный запуск миграции (AC-54) кнопкой/`f3d_run_migration` | ORM, 21:02 | FAIL | D1: `created=0`, `meters=0` (идемпотентно), но `partial` и около 350 расхождений; не сходится |
| 11 | Агрегаты R-09: крон `hour` + QA-сигнал | method_direct_trigger | PASS | pressure_bar за 20:00: min 1, avg 6.875, max 11, count 4, first 6.5, last 1.0 = сырые данные |
| 12 | AC-02: коды колектора `qa-bad`, `-QA`, 33 символа, дубль, `push_interval_s=0`, `status_interval_s=5`, `push_max=2001` | JSON-RPC create | PASS | ValidationError с текстом SPEC; значения по умолчанию 5/1000/60/60, `state=never` |
| 13 | AC-01: выдача, замена, отзыв токена | JSON-RPC + HTTP | PASS | действие `act_window` на мастер, токен 43 символа, `token_hint`=хвост; старый токен → 401 после замены; отозванный → 401; в чаттере только `…hint` |
| 14 | AC-60/права: user и manager | вход под QA-пользователями | PASS | `token_hash`/`token_hint` недоступны обеим ролям и отсутствуют в `fields_get`; `action_generate_token` и запись колектора — AccessError; signal/source пишет только manager; команду user — AccessError, manager — UserError «вимкнено»; `f3d_run_migration` — только admin; показания не редактируются |
| 15 | Валидаторы: код сигнала, пороги (AC-10), `state` + числовые пороги, адрес `fc=99`, код источника, дубль, обязательные `params` mqtt, `params_text` не JSON | JSON-RPC create/write | PASS | ValidationError с текстами SPEC |
| 16 | API-04 `GET /health`: без токена, с плохим, с валидным | curl | PASS | 200; ключи `ok,module,version,server_time`; с токеном `collector{}` и `counts{}` |
| 17 | Авторизация API-01/02/03/05/06/07: нет токена, плохой, схема `Token`, `GET` на `/push` | curl | PASS | 401 `unauthorized`; 405 на неверный метод |
| 18 | API-01 `GET /config`: 200, ETag, `If-None-Match` → 304, заголовки | curl | PASS | `Cache-Control: private, max-age=0`, 304 без тела; в 200 только QA-источник и 4 сигнала, `read_enabled=true` |
| 19 | AC-38 API-02 валидный push (4 показания) | curl | PASS | `accepted=4, stored=4`, `changed` 4 кода, `config_etag` 64 hex, `server_time` с `Z`, `state=online`, `last_push_at` |
| 20 | API-02: причины отклонения — `unknown_code`, `foreign_signal` (чужой и без источника), `ts_no_tz`, `ts_invalid` (×3), `ts_future`, `ts_too_old`, `value_invalid` (строка, bool, Infinity, NaN), `text_too_long`, `missing_value`, `bad_code_format`, `unknown_state` | curl | PASS | индексы `i` верны, прочие показания пакета приняты |
| 21 | API-02: идемпотентность — тот же `(signal, ts)` | curl | PASS | `duplicates=1`, `stored=0`; в пакете из 2000 одинаковых — `duplicates=1999` |
| 22 | API-02/03/05 ошибки: невалидный JSON, пустое тело, тело-список, `readings` не список/нет, 2001 → 413 `too_many_readings`, тело > 1 МБ → 413, `collector` ≠ токен → 403 | curl | PASS | коды и `error.code` как в SPEC §7 |
| 23 | AC-41: лимит частоты `429` + `Retry-After: 10` | — | НЕ ПРОВЕРЕНО | `push_rate_per_min=3` не разрешено, 61 запрос превышает лимит. Косвенно: `rate_count` растёт 1→2→3→5 в окне, `rate_window_start` ставится |
| 24 | AC-41: `423 read_disabled` для push и event | — | НЕ ПРОВЕРЕНО | нужно менять глобальный `read_enabled` |
| 25 | `403 forbidden` для неактивного колектора | — | НЕ ПРОВЕРЕНО | архивация записи требует подтверждения |
| 26 | AC-42 API-03 `/status`: версия, uptime, буфер, плагины, состояние источника, чужие/неизвестные коды в `rejected`, `sources` не список → 400, 501 источник → 413 | curl | PASS | `version`, `uptime_s`, `buffer_rows`, `plugins` сохранены; `last_error` маскирует `password=`/`token=`/`Bearer` и обрезается до 512 |
| 27 | API-03: неизвестный `state`, поле `error` | curl | FAIL | D5 (мелкий): `state:"bogus"` → 200, состояние не меняется, но `last_error` стирается |
| 28 | AC API-05 `/event`: маршрут без обработчика, дубль `event_id` → `rejected: duplicate`, плохие `event_id`/`route`/`payload`/`ts` → 400, 101 событие → 413, `collector` ≠ → 403 | curl | PASS | `f3d.push.event` 2 записи, `headers` не хранятся |
| 29 | API-05 с реальными обработчиками (`lpr`, `mc_*`, `bacnet_event`) | — | НЕ ПРОВЕРЕНО | это модули yard/machine_connect/fire_safety, на стыке не нужны, QA-мусор в чужих модулях не создавался |
| 30 | API-06/07 при выключенной записи: `GET /commands` → `commands=[]`; `/commands/result` с неизвестным id → `not_found`; нет `results`/плохой `id`/`data` не объект → 400 | curl | PASS | `command create` при `write_enabled=False` — UserError «Запис у пристрій вимкнено: параметр модуля» |
| 31 | API-06/07: очередь команд, `sent` → `done/failed` | — | НЕ ПРОВЕРЕНО | нужно включать глобальный `write_enabled` |
| 32 | Статусы R-04: warn/alarm, гистерезис, возврат в `ok`, `min_duration_s=30` (`breach_since`), `state` + `alarm_states`, смена порога | HTTP + ORM | PASS | pressure 9→warn, 11→alarm, 5.0→ok; temp 95 держится до 30 с, затем alarm; state `fault` → alarm |
| 33 | AC-03 крон stale + офлайн колектора | method_direct_trigger + ожидание | PASS | сигналы без данных → `stale`; колектор `online` → `offline` через 180 с, его источник `offline` |
| 34 | R-05 заявка из тревоги | HTTP + ORM | PASS | «QA-telemetry- тиск 11 бар при нормі до 10», corrective, приоритет 2, команда 2, `f3d_origin=threshold`, `f3d_value=11`, `f3d_threshold=10`; повторный push — без второй заявки; `create_request=False` — без заявки |
| 35 | R-06 закрытие заявки | ORM | PASS | `maintenance_request_id` сброшен, `request_closed_at`, чаттер «…Тривога триває, нова заявка не раніше 16.10.2026 00:54» (3600 с по Киеву) |
| 36 | A-22 ТО по счётчику | HTTP + ORM | PASS | интервал 1000, `hours=960` → preventive «ТО за лічильником: … 1 000 год (зараз 960)», приоритет 1; закрытие → `last_value=960`, `next=1960` |
| 37 | Четыре крона telemetry через `method_direct_trigger` (stale, hour, rotate, commands_gc) | ORM | PASS | `failure_count=0`, `lastcall` обновлены |
| 38 | R-10 ротация удаляет старое | — | НЕ ПРОВЕРЕНО | в базе нет данных старше 30 суток, а удалять мне нельзя: проверен только запуск без ошибки |
| 39 | DEC-19: `_touch` не пишет чаще 30 с при стабильном IP | HTTP keep-alive, 5 запросов за 12 с | PASS | `last_seen` не менялся 21:07:31 → 21:07:43; обновился на запрос после 31 с |
| 40 | DEC-19: окно = min(30, `status_interval_s`) | `status_interval_s=10` на QA-колекторе | PASS | +5 с — без записи, +13 с — запись; значение возвращено на 60 |
| 41 | DEC-19 на этом сервере (Cloudflare перед Odoo) | HTTP без keep-alive | FAIL | D3: `last_ip` каждый запрос другой (162.158.x, 172.69.x, 172.70.x, 172.71.x, 104.23.x), 7 из 7 запросов подряд пишут `last_seen` |
| 42 | DEC-19: не писать общую строку колектора на каждый запрос | HTTP keep-alive | FAIL | D2: после 2 push за 3 с `last_seen` не изменился, но `write_date` 21:09:27 → 21:09:30 и `rate_count` 1 → 2 |
| 43 | Мост viewer: `meta.iot` в `/f3d/viewer/data` | ORM + HTTP | PASS | `source`=«телеметрія (factory3d_telemetry)», `signals=200`, `alarms=1`, `stale=158` = подсчёт по ORM |
| 44 | Мост access_telemetry: 7 сигналов СКУД | ORM | PASS | 5 `access/readers/*/last_event`, `access/turnstiles/TURNSTILES/on_site`, `access/events`; `origin=module`, без источника |
| 45 | API-02: показание с `value` и `text` одновременно | curl | FAIL | D6 (мелкий): принято, у gauge появился `last_text="x"` |
| 46 | Нагрузка ТП-01 (35 push/с, deadlock/serialization) | — | НЕ ПРОВЕРЕНО | нельзя флудить сервер |
| 47 | 3D-просмотр в браузере, событие шины `f3d.viewer.event` (AC-70) | — | НЕ ПРОВЕРЕНО | открыт только JSON `/f3d/viewer/data` |
| 48 | `neutralize.sql`, `uninstall_hook`, `drop_level0`, повторная установка | — | НЕ ПРОВЕРЕНО | требует удаления/переустановки |
| 49 | Сервис колектора (`services/collector`: modbus, mqtt, bacnet, http_push) | — | НЕ ПРОВЕРЕНО | на тестовой базе колектор не запущен |
| 50 | ТП-04: размеры таблиц `f3d_reading` и `f3d_reading_hour` (DEC-16) | — | НЕ ПРОВЕРЕНО | прямого доступа к SQL нет |

Итог по строкам: PASS 30 (№1–3, 5, 6, 11–22, 26, 28, 30, 32–37, 39, 40, 43, 44), FAIL 9 (№4, 7–10, 27, 41, 42, 45),
НЕ ПРОВЕРЕНО 11 (№23–25, 29, 31, 38, 46–50). Строки 7–10 — один дефект D1.

## Дефекты

**D1 (критичный). Миграция прототипа iot_sim завершается `partial` и после этого не может завершиться.**
Шаги воспроизведения:
1. На базе с живым уровнем 0 (`x_f3d_signal` 196, `x_f3d_reading` ≈ 56 тыс., крон iot_sim активен) установить factory3d_telemetry. Это уже сделано, отчёт хука лежит в `ir.config_parameter` `factory3d.telemetry.level0_migrated` (20:36:54).
2. Открыть отчёт.

Ожидание (AC-58, §5.3): `mismatches=[]`, `state='done'`, шаги 6 и 9 выполнены.
Факт:
- `state='partial'`, `mismatches=["equipment/FL-5/battery: status warn != x_state норма"]`. Причина: каталог (C.2, `data/signal_catalog.csv`, `equipment/FL-*/battery`: `warn_low=25`, `alarm_low=15`) при шаге 3 пересчитывает статус по новым порогам. FL-5 имел 22,9 %, поэтому `warn`. На уровне 0 порога у батареи нет (`x_alarm` пусто, `x_state='норма'`). Проверка шага 8 сравнивает статус только с `тривога`/`ok` (`hooks.py:567`), поэтому любая батарея ниже 25 % ломает миграцию. На копии демо от 14.10 все батареи были выше 25 %, потому тесты прошли.
- Из-за `partial` шаги 6 и 9 пропущены (`hooks.py:656–662`): 28 заявок уровня 0 не привязаны к `f3d.signal` (`maintenance_request_id` пуст, RV-05 filter_dp_pa — заявка 6 открыта), крон `cron_iot_sim`, меню и `x_active` не выключены. Когда сигнал снова уйдёт в тревогу, телеметрия может завести вторую заявку вместо привязки к существующей (в этой базе без колектора не воспроизводилось).
- База оказалась в гибридном состоянии: уровень 0 продолжает писать `x_f3d_signal`, а у 154 из 196 мигрированных сигналов статус `stale` (источники BACnet/Modbus/MQTT без колектора), 3D показывает замороженные значения (FL-5/battery 22,9 % при живых 21,6 %).
- Повторный запуск не лечит: `f3d_run_migration` в 21:02:31 вернул `partial`, около 350 расхождений. Шаг 2 для уже существующих `sim_data` не обновляет `last_value`/`status` (`hooks.py:76,258`), а проверка требует `last_value == x_value` (`hooks.py:564`), хотя уровень 0 продолжает меняться (190 из 196 значений различаются). Счётчик показаний тоже расходится: `f3d.reading(sim_data)` 57 232 против `x_f3d_reading` 56 056 (iot_sim чистит свои строки, телеметрия — нет).
Последствие для пользователя: «Запустить миграцию» в настройках на живой базе не работает, выйти можно только вручную остановив iot_sim. Нужно решение менеджера: проверять статус без новых порогов, сверять только на момент транзакции установки, обновлять `last_*` при повторном запуске.
Я перезапустил миграцию один раз (21:02:31) как проверку AC-54: параметр `level0_migrated` перезаписан отчётом повторного запуска. Исходный отчёт установки (20:36:54): `partial`, `signals_migrated=196`, `created=196`, `alarm=28`, `with_request=28`, `signals_catalog{created 29, bound 55, bind_missing 0, no_equipment 0}`, `meters=9`, `meter_requests_linked=9`, `sim_catalog{updated 182, unparsed 43}`, `readings_migrated=56840`, `hours=9408`. Эти числа можно сравнить с AC-58: `alarm=28` и `with_request=28` вместо 1 и 2 — состояние живого прототипа, не дефект кода.

**D2 (серьёзный). DEC-19 не доведён до конца: `_rate_check` пишет строку колектора на каждый push.**
`models/f3d_collector.py:230–241`: `rec.write({"rate_count": rec.rate_count + 1})` вызывается в каждом `POST /push`. Это тот же общий UPDATE строки `f3d_collector`, который DEC-19 убирает из `_touch`. Проверено с keep-alive (один IP): два push за 3 с — `last_seen` и `last_push_at` не менялись, `write_date` изменился, `rate_count` 1 → 2.
Увеличение не атомарно (прочитать, прибавить, записать), под параллельной нагрузкой счёт теряется, лимит можно обойти. Под нагрузкой ТП-01 (35 push/с, DEC-19) конкуренция за строку остаётся. Не проверено под нагрузкой.

**D3 (средний). Троттлинг `_touch` зависит от неизменного IP и не работает за CDN/прокси.**
`models/f3d_collector.py:143–150`: запись пропускается только при `rec.last_ip == ip`. На этом сервере перед Odoo стоит Cloudflare, `remote_addr` — адрес края CDN (подсети 162.158, 172.69–71, 104.23). Без keep-alive IP меняется каждый запрос, и все 7 подряд запросов `/config` писали `last_seen` (см. строку 41). С keep-alive троттлинг работает (строки 39–40). Нужно либо не включать IP в условие (писать `last_ip` вместе с периодической записью), либо включить `proxy_mode` на сервере. Заодно `last_ip` в карточке показывает адрес края CDN, а не колектора.

**D4 (средний). Фильтры сигналов объединены по ИЛИ, действие «Телеметрия» показывает все сигналы.**
`views/f3d_signal_views.xml:183–187`: фильтры `alarm`, `warn`, `stale`, `no_source`, `active` — одна группа без `<separator/>`. Действие `action_f3d_signal_alarm` (там же, строка 210, `search_default_active` + `search_default_alarm`) открывается с фасетом «Тривога або Увімкнені»: 1218 сигналов, а не тревоги (1 тревога). Нужно отделить «Увімкнені» разделителем.

**D5 (мелкий). `_apply_status` стирает `last_error` при неизвестном `state`.**
`models/f3d_source.py:205–213`: `last_error` всегда перезаписывается из `item["error"]`, даже если `state` не распознан или не передан. Источник остаётся `error` без текста ошибки. Маска ошибок (`password=`, `token=`, `Bearer`) не закрывает `secret=`, `api_key=` и запись `password: x`.

**D6 (мелкий). Показание с `value` и `text` одновременно принимается.**
Для gauge записывается `last_text="x"` (SPEC §7 API-02: «один з `value` або `text`»). Показание с неверным `q` отклоняется как `value_invalid`, чего в SPEC нет (допустимо).

**D7 (мелкий). Ответ 405 — HTML Odoo, а не JSON-конверт ошибки.** `GET /f3d/telemetry/push` → 405 с HTML-страницей. SPEC §7: «усі помилки — JSON».

**D8 (мелкий). У модуля нет иконки `static/description/icon.png`.** В настройках 404 для `/factory3d_telemetry/static/description/icon.png`. 404 есть и у genset, energy, yard, fire_safety (не проверял, чьё это).

## Что не проверено и почему

- 429 (AC-41), 423, API-06/07 happy path: требуют менять глобальные `ir.config_parameter`; запрос на `push_rate_per_min=3` отклонён, 61 запрос недопустим.
- 403 для неактивного колектора: архивирование записей без разрешения пользователя нельзя.
- Реальное удаление старых данных кроном ротации (нет данных старше 30 суток; не удалял).
- Нагрузка, ТП-04 (размер таблиц, DEC-16): нет доступа к SQL и нельзя флудить.
- Сервис колектора, обработчики событий lpr/mc/bacnet (чужие модули), 3D в браузере, шина viewer.
- `uninstall_hook`, `neutralize.sql`, `drop_level0`, повторная установка: не разрешены правилами QA.

## Мусор в базе (ничего не удалялось)

- `f3d.collector` id 2 `QA-TELE-C1` (токен отозван, `state=online/offline` по времени); `f3d.source` id 137 `QA-TELE-S1`.
- `f3d.signal` id 1214–1218 `equipment/QA-TELE/*`; `maintenance.equipment` id 211 `QA-telemetry-equipment` (настроен счётчик на сигнал 1216).
- `maintenance.request` id 44 (закрыта), 45 (открыта, «QA-telemetry- стан 2»), 46 (закрыта, ТО по счётчику).
- `f3d.reading` около 20 строк `src=collector` по QA-сигналам, `f3d.reading.hour` несколько строк, `f3d.push.event` 2 записи (`route=qa_none`), сообщения в чаттере QA-записей.
- `res.users` id 7 `qa-telemetry-user`, id 8 `qa-telemetry-manager` (пароли затёрты, пользователей лучше заархивировать).
- `ir.config_parameter` `factory3d.telemetry.level0_migrated` перезаписан повторным запуском миграции (21:02:31); `ir.cron` 45–48 имеют обновлённый `lastcall`.
- Примечания «QA-telemetry- by manager» в `f3d.signal` 1218 и `f3d.source` 137.

## Расход запросов

Запросов к HTTP API телеметрии — 81 (curl/requests, счётчик в скрипте). Кроме них около 70 вызовов JSON-RPC (проверки полей, создание фикстур, вход QA-пользователей) и одна сессия браузера (два прогона по 12–14 страниц): общий объём превысил «около 100». Всплесков по одному эндпоинту не было, самый плотный — 7 запросов за 14 с. Скрипты и скриншоты: `/tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/qa_telemetry/`.
