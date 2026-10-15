# QA iot_sim
Статус: PARTIAL
Проверено: 26, провалено: 4, не проверено: 10 (2026-10-15, коммит 29a088e)
Дефекты: 5 (критичных: 1)
Мусор в базе: f3d.sim.run: id 1–4 (RUN/2026/0001 running, 0002 done, 0003 и 0004 failed; у 0001–0002 sim_run_id `QA-iot_sim-run-1`, у 0003–0004 параметры device=NOPE-1 / RV-05, создал run-wizard); f3d.sim.event: id 1–2 (сообщения `QA-iot_sim-ev1`, `QA-iot_sim-ev2 done`). Пользователей qa-iot_sim-* не создавал (см. «Не проверено»). Run №1 в состоянии `running` виден на пульте в «Активные запуски», удалить вручную.
Временно менял и вернул: `factory3d.iot_sim.export_token` (дважды на ≈1 мин, значение `QA-iot_sim-<hex>`, возвращено в пустое), `factory3d.iot_sim.write_enabled` (True на несколько секунд, возвращено в `False`), `f3d.sim.panel.state` (после проверки кнопки «Перевірити зв'язок» стало `offline`, возвращено в `unconfigured`, `last_error` очищен).

Контекст: БД `odoo` (timur-o19demo), модуль `factory3d_iot_sim` 19.0.2.0.0, `ir_module_module.state=installed`. Код модуля в `/home/user/f3d-build` на HEAD 6328313 не отличается от 29a088e (`git diff --stat` по каталогу пуст). Эталона «до миграции» нет (копии базы до апгрейда нет), поэтому проверялась согласованность данных между собой, с каталогом `data/f3d_sim_signal.csv`, с XML сценариев и со SPEC. Анализ делал скриптом по JSON-RPC (логин из cred-файла, пароль нигде не выводился) плюс коннектор odoo-mcp (connection.db == "odoo"), браузер Playwright для UI. Эмулятор-сервис не запущен, сценарии, которым он нужен, помечены ниже.

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка: модуль installed, версия = манифест | search_read ir.module.module | PASS | state=installed, latest_version=installed_version=19.0.2.0.0 |
| 2 | AC-25, количества | search_count | PASS | f3d.sim.panel=1, device=276 (210 + ACR×5 + TURN-1 + CAM×2 + PV-INV×8 + 49 `-PM` + CUTOPT, passive=100), signal=1168 (protocol=none 151: energy 55, machine_connect 37, bms 59), origin=mock 196, scenario=15 |
| 3 | AC-25, рівень 0 пережив апгрейд | search_count, read_group | PASS | x_f3d_signal=196 (create_date 2026-10-13, т.е. данные прототипа), x_f3d_reading=56840 (=196×290, без записей без сигнала/времени/оборудования), `cron_iot_sim` существует и активен (переименован в «Емулятор IoT: рівень 0 (без сервісу)»), чтения идут без разрыва на момент апгрейда (20:20 → 20:30) |
| 4 | Шаг 4 хука: mock ↔ x_f3d_signal | скрипт | PASS | 196 mock-сигналов, у всех `level0_code`, все есть в x_f3d_signal.x_code; обратно: x_f3d_signal без mock-сигнала 0; дублей x_code 0; не-mock с level0_code 0; оборудование x_f3d_signal совпадает с оборудованием устройства (0 расхождений) |
| 5 | Устройства ↔ оборудование/РЦ, сирот нет | скрипт | PASS | 210/210 оборудования с f3d_code имеют устройство; все equipment_id указывают на f3d-оборудование; 35/35 РЦ связаны корректно; лишних устройств вне (оборудование, производные, -PM) нет; дублей code нет |
| 6 | Каталог сигналов = CSV | скрипт, построчно | PASS | 1168/1168 кодов равны, расхождений по device/protocol/address/dtype/unit/scale/nominal/thresholds/model/origin/level0_code = 0; сигналов без устройства 0; `fire/groups/FA-SOC|FA-OFFICE/state` (LSZ:34/35), `equipment/CUTOPT/cmd` и `GANTRY-1/stacks` = protocol none (AC-62) |
| 7 | Сценарии S-01…S-15 | скрипт vs XML и SPEC §9.3 | PASS | 15 кодов, name/group/duration_s/sequence/params_schema/params_default равны данным XML, все active |
| 8 | Пульт, параметры, крони | search_read | PASS | device_count 276, signal_count 1168, level0_signal_count 196, scenario_ids 15; 10 параметров `factory3d.iot_sim.*` (токены пусты, read_enabled=True при `factory3d.base.environment=test`, write_enabled=False); крони C-01, C-02, рівень 0 активны, failure_count 0 |
| 9 | Рівень 0: данные | скрипт | PASS | x_value без пустых; 28 сигналов в «тривога» и все 28 ссылаются на существующие заявки ТО (2 из них — исходные MR из сидинга, 26 созданы кроном), висячих x_request_id/x_source_id нет |
| 10 | Висячие xml-id модуля | скрипт | PASS | 467 записей ir.model.data (кроме ir.model.constraint/inherit, недоступны для чтения, ir.cron проверен отдельно) — все res_id существуют |
| 11 | AC-59 меню (+ §13.5 п.3) | read ir.ui.menu | PASS | `menu_f3d_sim_root`→`factory3d_base.menu_f3d_root` seq 90, `menu_iot_root`→`menu_f3d_sim_root` seq 9, `menu_f3d_sim_settings`→`menu_f3d_config` seq 90, в `maintenance.menu_maintenance_title` пунктов модуля нет; 6 пунктов + «Рівень 0» = 7 |
| 12 | Действия и представления | get_views, чтение полей | PASS | 8 act_window (список/форма/канбан/граф), серверное действие «Пульт», 2 мастера, формы maintenance.equipment, mrp.workcenter, res.config.settings открываются; поля всех представлений читаются без ошибок |
| 13 | UI в браузере | Playwright, admin | PASS | пульт, пристрої (группировка по протоколу, 12 групп), сценарії (канбан, 15), запуски, каталог, події, налаштування, рівень 0 (сигнали, журнал), форма пристрою CNC-2 (8 сигналов), форма обладнання CNC-2 (вкладки «Емулятор» и «Сигнали»): без диалогов ошибок, без 5xx, без pageerror |
| 14 | AC-32 права (статически) | read ir.model.access | PASS (статика) | user: только R на panel/device/signal/scenario/run/event; manager RW на device/signal/panel, RWC на scenario/run; admin RWCU; совпадает со SPEC §4.1; x_f3d_* с `base.group_user` RWCU по SPEC (A-09) |
| 15 | AC-28 стоп-кран записи | execute | PASS | при write_enabled=False `action_apply_factor/mode/reset/stop_all`, `action_f3d_sim_clear`, мастер сценария и мастер сбоя дают UserError «Команди на емулятор вимкнено стоп-краном factory3d.iot_sim.write_enabled», запросов нет, run не создан |
| 16 | AC-27 автовключение рівня 0 | наблюдение, чаттер | PASS | панель создана 20:25:34, в 20:31:21 запись в чаттере «стан рівня 0: Авто: увімкнено (сервіс офлайн)», cron_iot_sim active=True, level0_state=auto_on |
| 17 | AC-31, API-01/02 | curl-аналог (requests) | PASS | `/f3d/sim/health` 200 без токена (276/1168, panel_state); `/f3d/sim/devices` при пустом export_token 503; с токеном: без заголовка/неверный/Basic 401, верный 200 (511 КБ, 0,7 с), 276 устройств, 1168 сигналов, SAW-1 с 8 сигналами `workcenters/SAW-1/*`, дублей кодов нет; ETag + If-None-Match 304; `?protocol=P-01` 15 устройств; POST на health 405 |
| 18 | AC-30, API-03 | requests | PASS | 2 события → 200 `accepted=2`, run по `run_ref` стал `done` со `stop_ts`; повтор тех же event_id → `duplicate`×2; невалидные kind/message/ts/не объект → отклонены с причинами; битый JSON 400; `events` не список 400; 101 событие 413; неверный токен 401; GET 405 |
| 19 | AC-58 read_enabled по среде | чтение параметров | PASS (частично) | environment=test → read_enabled=True, write_enabled не менялся; повторный запуск хука не проверен (см. «Не проверено») |
| 20 | Ограничения моделей | execute (откат) | PASS | дубль кода устройства/сигнала/сценария, код устройства в нижнем регистре, код сигнала «BAD CODE», второй пульт, factor вне диапазона — все отклонены ValidationError |
| 21 | Крони через `method_direct_trigger` | execute | PASS | `cron_f3d_sim_gc`, `cron_f3d_sim_status` отработали без ошибки (true), failure_count 0, состояние панели не ломается |
| 22 | Мастера: валидация и отказ сервиса | execute, write_enabled=True кратко | PASS | мастер сбоя с причиной `loop` для CNC-2 → ValidationError; run-wizard: невалидный JSON → UserError, нет обязательного `device` → ValidationError; валидные параметры при пустом url → run `failed` с message «Адресу сервісу…не налаштовано», пристрій не получил ложного состояния fault |
| 23 | §5.3 / AC-25: заполнение реестра при штатном `-u` | чтение кода Odoo + метки времени БД | **FAIL** | см. дефект D1 |
| 24 | §5.3 п.7, state machine: `unconfigured` при пустом url | execute | **FAIL** | см. дефект D4 |
| 25 | §5.2 / §5.3 п.2: `params` устройств | скрипт по 276 устройствам | **FAIL** | см. дефект D2 |
| 26 | §5.2: unit_id и привязка сигналов у производных/особых устройств | скрипт | **FAIL** | см. дефект D3 |

## Дефекты

**D1 (критичный). `post_init_hook` не вызывается при обновлении модуля `-u`, поэтому на реальной миграции 19.0.1.0.0 → 19.0.2.0.0 реестр не наполняется.**
- Шаги: обновить базу с прототипом 19.0.1.0.0 командой `-u factory3d_iot_sim`.
- Ожидание (SPEC §5.3, AC-25, §13.5 п.2): после обновления панель=1, устройств 276, сигналов 1168, mock 196.
- Факт по коду: `/home/user/odoo19/odoo/modules/loading.py:240-243` вызывает `post_init_hook` только при `update_operation == 'install'`; при `upgrade` — нет. В `migrations/19.0.2.0.0/pre-migrate.py` только логирование и проверка `x_f3d_signal`, post-migrate нет. Наполнение (шаги 1–7) живёт целиком в `hooks.py:post_init_hook` (стр. 163-174), `__manifest__.py:36`.
- Косвенно по БД: сценарии (данные модуля) созданы 20:23:40, пульт 20:25:34, все 276 устройств и 1168 сигналов 20:25:58 — через 2 мин после загрузки модуля, т.е. хук, вероятно, был вызван вручную. В этой базе данные корректны, но на другой копии (прод) штатный `-u` даст пустые пристрої и каталог, при этом `x_f3d_*` останутся.
- Почему тесты зелёные: `tests/test_migration.py` вызывает `post_init_hook(self.env)` напрямую и фикстуры 1.0.0 нет (DEC-9), реальный путь `-u` не покрыт.
- Предложение (решает менеджер): добавить `migrations/19.0.2.0.0/post-migrate.py` с вызовом `post_init_hook(env)` и тест, который проверяет это.

**D2 (средний). Хук не заполняет `params` устройств (SPEC §5.2).** Из 276 устройств `params` есть только у 8 (ACR-×5, TURN-1 — `biostar_device_id`; CAM-05/06 — `gate`). Нет раскладки каналов ADAM у 31 устройства (`di_run/di_fault/counter` у 20 РЦ P-02, `ai/rtd` у T1/T2/DUST-1/SPRINKLERS/AIR-RING, `di_open/di_spark…` у SPARK-1/SMOKE-CTRL/SMOKE-VENTS/GATE-E и др.), нет `{"lsz": n}` у извещателей FA-*, `{"group","router"}` у групп DALI. `hooks.py:_ensure_devices` (стр. 71-116) задаёт params только для ACCESS/TURNSTILES/CCTV. API-01 (`/f3d/sim/devices`) отдаёт `params: {}`. Влияние на сервис при `SIM_CATALOG_SOURCE=odoo` (AC-22) не проверено, нужен сервис; в локальном режиме (DEC-14) не критично.

**D3 (средний/низкий). Расхождения реестра со SPEC §5.2.**
- T1/T2 (`transformer`): unit_id=1 и 2 вместо unit 96; `_fill_addresses` (hooks.py:119-141) берёт unit из адреса первого сигнала (`Modbus u1 … PM5560`), в итоге unit_id совпадает с Q1/Q2 (`modbus_pm5560`), ограничение уникальности это пропускает, т.к. `modbus_adam6015` в `SHARED_UNIT_DRIVERS`. Восемь сигналов `energy/transformers/T*/…` имеют protocol P-05 на устройстве с protocol P-07.
- PV-INV: все 32 сигнала `infra/pv/PV-INV-n/*` привязаны к родителю `PV-INV` (unit_id=0), а 8 производных PV-INV-1..8 (unit 61–68) не имеют ни одного сигнала. Причина: колонка `device` CSV = `PV-INV`.
- FL-6 по SPEC пассивный (без сигналов), в базе `mqtt_mobile` / `unknown`.
- Ещё `modbus`-устройства без unit_id: EMS-1, QS, SWB-1, PV-INV, SMOKE-VENTS (последние три без сигналов). Всего 14 непассивных устройств без сигналов: QS, SWB-1, FL-6, PV-INV-1..8, SMOKE-VENTS, TURN-1, CCTV.

**D4 (низкий). Кнопка «Перевірити зв'язок» при пустом url переводит пульт в `offline` навсегда.** Шаги: `f3d.sim.panel.action_check()` при `factory3d.iot_sim.url=''`. Ожидание: остаётся `unconfigured` (SPEC §5.3 п.7, §10). Факт: `_poll` (`models/sim_panel.py:115-124`) ловит UserError «Адресу…не налаштовано» и пишет `state='offline'`, `last_error`; `_cron_poll_status` (стр. 263-269) возвращает в `offline` только из online/degraded/locked и никогда не возвращает в `unconfigured`. Побочно это меняет подсчёт «offline_long» для рівня 0 (не критично).

**D5 (низкий). В `params_schema` сценариев поле `device` объявлено как `{"type": "string"}` без enum (SPEC §9.3 S-02/S-04/S-10 требуют enum).** Run-wizard принимает `device="NOPE-1"` для `filter_clogged`: запуск RUN/2026/0003 создан, упал только из-за пустого url. Проверка допустимых кодов целиком отложена сервису. `data/f3d_sim_scenario.xml`, `models/sim_run.py:validate_params` (jsonschema-lite).

Наблюдение, не дефект: журнал показаний рівня 0 (унаследованный `action_iot_tick`) пишется только при `now.minute % 10 == 0`, и из-за разброса запуска крона в данных есть 6 пропусков по 20 минут за 2 суток (в т.ч. 20:40 сегодня). Код рівня 0 по SPEC «без изменений».

## Не проверено и почему

1. Сравнение `x_value` 196 сигналов и числа `x_f3d_reading` с исходной копией (AC-25, §13.5 п.7): эталона «до миграции» нет. Проверена только внутренняя согласованность и непрерывность данных.
2. AC-32 динамически (права `group_f3d_user` / `manager` на запись, невидимость кнопок сценариев): создание пользователей `qa-iot_sim-user/manager` с группами отклонено классификатором (Permission Grant). Права проверены статически по `ir.model.access`.
3. Повторный запуск `post_init_hook` (идемпотентность, AC-58 вторая часть) и `uninstall_hook`: через API не вызываются, деинсталляция запрещена.
4. Реальный прогон `-u` и лог миграции (в т.ч. сообщение `pre-migrate`): обновлять модули нельзя, журнал сервера недоступен (`ir.logging` пуст).
5. `neutralize.sql` (AC-34, ТБ-10): на этой базе не выполнялся. Статически SQL согласован со схемой (таблица `f3d_sim_panel`, значения `state='unconfigured'`, `level0_state='forced_off'` существуют в selection).
6. Не проверено — нужен сервис: AC-26 (онлайн-ветка `_apply_status`: `version/mode/factor/sim_time`, выключение крона рівня 0), AC-29 (успешный запуск мастера, `sim_run_id`, событие `command` без токена), AC-33 полностью («Збій» → «Скинути» с ответом сервиса), AC-22 (`catalog_source=odoo`, `devices=276`), AC-49 (`catalog_hash`), ТК-13 и ТК-15 п.1–5, AC-47 (запуск S-01…S-15), синхронизация `_sync_runs` / `_sync_device_faults`, заявка ТО от рівня 0 для RV-05 при запуске `filter_clogged`.
7. Все AC сервиса (AC-01…24, 35–57, 60–68, ТК-01…18, ТП): вне Odoo-модуля, закрывает стендовый этап.
8. Интерфейс под ролями (менеджер, обычный пользователь): см. п. 2.
9. Хук/каталог под `environment=prod` (`read_enabled='False'`): среда базы `test`, менять `factory3d.base.environment` не требовалось.
10. Работа `f3d.sim.event._gc` с реальными старыми событиями (батчи по 5000, `keep_days`): событий нет, проверен только запуск крона.
