# QA: стенд «эмулятор + коллектор → Odoo 19 test server»

Дата: 2026-10-15, окно 21:50–22:23 UTC. Сервер: https://timur-o19demo.todo.ltd, БД `odoo`.
Среда: этот контейнер, Python 3.13, без Docker, только исходящий HTTPS. Продуктовый код не менялся
(репозиторий `/home/user/f3d-build`, ветка `claude/factory3d-build`, `git status` чист; рабочая копия
`services/{collector,collector_plugins,iot_sim}` без tests скопирована в `.../scratchpad/stand/src`).
Итог: стенд работает, данные текут (коллектор `COL-MAIN` online, 131 из 132 источников online, +79 тыс. показаний
за 31 мин). Всё, что идёт от сервера к эмулятору, не проверялось (см. «Не проверено»).

## 1. Что запущено и как

Каталог стенда: `/tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/stand/` (далее `$S`).

Коллектор: использована существующая запись `COL-MAIN` (id 1, 132 источника, 1009 сигналов, `state=never`, токена не было).
Токен выдан так же, как в модуле: `f3d.collector.action_generate_token` (RPC от admin), токен записан в `$S/run/token`
(chmod 600, в отчёт не попадает). В конце токен отозван (`action_revoke_token`), файл удалён.

venv (создавались в `$S`):

    python3 -m venv $S/venv_sim  && $S/venv_sim/bin/pip install -r services/iot_sim/requirements.txt
    python3 -m venv $S/venv_core && $S/venv_core/bin/pip install -r services/collector/requirements.txt
    $S/venv_core/bin/pip install --no-deps $S/src/collector $S/src/collector_plugins/f3d_collector_bms \
                                           $S/src/collector_plugins/f3d_collector_yard
    $S/venv_core/bin/pip install $S/src/collector_plugins/machine_connect     # asyncua 1.1.6, cryptography 44.0.3

Заявленный конфликт плагинов при совместной установке НЕ воспроизвёлся: `pip check` чист, все entry points
(`modbus_tcp, mqtt, bacnet_ip, http_push, helvarnet, sics, opcua, rest_vendor` и rest_vendors `woodstore, cutopt, generic`)
загружаются в одном venv. Поэтому запущен ОДИН процесс коллектора с одним venv (несколько процессов с одним токеном
конфликтовали бы по статусам источников). Условие: плагины bms/yard ставить с `--no-deps`
(yard требует `f3d_collector>=0.1.0`, а `requirements-extra.txt` ссылается на `file:///opt/plugins/...`).

Имена из данных модуля (`iot-sim`, `mosquitto`, `collector`) разрешены через `/etc/hosts` (127.0.0.1), в конце файл восстановлен.

Эмулятор (`cwd=$S/src/iot_sim`, `SIM_CATALOG_SOURCE=local`, `SIM_MODE=scenario`):

    SIM_API_TOKEN=<>=32 симв.> SIM_BIOSTAR_PASS=... SIM_WOODSTORE_APIKEY=... SIM_JOBS_APIKEY=... SIM_OPCUA_PASS=... \
    SIM_OPCUA_CERT_DIR=$S/run/certs SIM_STATE_DIR=$S/run/sim_state \
    SIM_LPR_PUSH_URL=http://collector:8080/f3d/lpr/<секрет> SIM_MQTT_URL=mqtt://sim:...@mosquitto:1883 \
    $S/venv_sim/bin/python -m iot_sim check-config     # config OK
    $S/venv_sim/bin/python -m iot_sim run              # health: 11 протоколов ok за 4 с, 278 устройств, 1168 сигналов

Коллектор (`cwd=$S/src/collector`, обёртка `$S/run_collector.sh`, `env -i`):

    F3D_ODOO_URL=https://timur-o19demo.todo.ltd F3D_COLLECTOR_CODE=COL-MAIN F3D_COLLECTOR_TOKEN=<token> \
    F3D_ALLOW_HOSTS=iot-sim,mosquitto,127.0.0.1 F3D_BUFFER_DIR=$S/run/state F3D_WRITE_ENABLED=0 \
    F3D_BACNET_BIND=127.0.0.2:47808 F3D_CONFIG_POLL_S=30 F3D_PUSH_INTERVAL_S=5 \
    F3D_OPCUA_PASSWORD=<=SIM_OPCUA_PASS> F3D_WOODSTORE_KEY=<=SIM_WOODSTORE_APIKEY> F3D_CUTOPT_KEY=<=SIM_JOBS_APIKEY> \
    F3D_MQTT_PASSWORD=... F3D_HTTP_PUSH_SECRET_LPR=<секрет> F3D_HTTP_PUSH_TOKEN_LPR=... \
    $S/venv_core/bin/f3d-collector check-config     # ok (Odoo достижим напрямую по HTTPS, CA не нужен)
    $S/venv_core/bin/f3d-collector run

BACnet: эмулятор слушает 127.0.0.1:47808, коллектор 127.0.0.2:47808 (иначе два UDP-сокета на одном порту).
Старт: эмулятор 21:50:52, коллектор 21:51:00 (`collector COL-MAIN started` 21:51:21), остановка 22:22:45 (SIGTERM, чисто).

Инъекции через API эмулятора (`/sim/v1`, Bearer SIM_API_TOKEN): принудительные значения `equipment/DUST-1/filter_dp_kpa=2.6`
и `equipment/AIR-RING/pressure_bar=4.5` (21:54:08); сценарии `shift`, `machine_fault` (CNC-2, 21:56:48, авто-сброс 150 с),
`truck_no_booking` (LPR); сдвиг времени эмулятора на 2026-10-16 10:30 Kyiv (22:03:06 UTC), чтобы станки перешли в работу.

## 2. Какие данные пришли (до / через 10 мин / в конце, ~31 мин)

Снимки: `$S/snap_before.json` (21:50:31), `snap_after10.json` (22:01:34), `snap_final.json` (22:21:57).

| Показатель | до | через 10 мин | в конце |
|---|---|---|---|
| `f3d.collector` COL-MAIN: state / last_seen | never / нет | online / 22:01:33 | online / 22:22:29 |
| источники COL-MAIN | 132 unknown | 131 online, 1 offline | то же (offline = MQTT-MOBILE) |
| `f3d.reading` всего | 57 404 | 84 589 (+27 185) | 136 630 (+79 226) |
| сигналов с `last_ts` (всего 1244) | 263 | 1107 | 1114 |
| сигналов COL-MAIN с данными (из 1009) | 156 | 953 | 954 |
| статусы сигналов ok / stale / unknown | 103 / 160 / 981 | 1083 / 20 / 137 (+alarm 3, warn 1) | 1092 / 20 / 130 (+alarm 1, warn 1) |
| счётчики energy (`kind=counter`) с данными (из 108) | 40 | 99 | 99 |
| сигналы с `kwh` в коде с данными (из 129) | 40 | 118 | 118 |
| 67 счётчиков `f3d.energy.meter` (import kWh): с показаниями | 0 | 67 | 67 (65 с ненулевым значением) |
| `f3d.energy.interval` | 0 | 0 | 67 (первый слот построен кроном ~22:20) |
| сигналы в `alarm` | 0 | 3 | 1 (LT-FAC/faults, штатное состояние эмулятора) |
| `maintenance.request` всего / с `f3d_signal_id` | 49 / 14 | 53 / 18 | 53 / 18 |
| `f3d.machine` (35): состояния | fault 1, nodata 34 | idle 20, off 15 | working 30, idle 5 |
| `f3d.machine.state.log` / `f3d.machine.event` | 0 / 0 | 38 / 3 | 70 / 3 |
| `f3d.yard.lpr.event` | 0 | 0 | 4 (после снятия `token_ref`, см. п. 3) |

Новые показания по модулям (итого 79 811 по id>113068): machine_connect 75 013 (174 сигнала), energy 2 795 (239),
bms 1 524 (549), yard 308 (18), telemetry 104 (16), fire_safety 67 (55). Метрики коллектора: `collector_push_total{ok}`=297,
`push_rejected`=0.

Пороги и заявки (сигнал → alarm → заявка, все `f3d_origin=threshold`, стадия New Request):
- #50 «Пневмомагістраль: тиск 4,5 бар при нормі від 6» (AIR-RING, принудительно 4.5), создана через ~10 с;
- #51 «Заміна фільтрів: перепад тиску 2,6 кПа при нормі до 1,8» (DUST-1, принудительно 2.6), через ~10 с;
- #52 «Аварія світильників LT-FAC: несправних 2 шт.» (Helvar, естественное состояние эмулятора, 21:56:19);
- #53 «CNC-2: аварія верстата» (сценарий machine_fault, 21:56:56).
FA-FAC/dust = 82 дал статус `warn` (порог 80) без заявки. После возврата значений к норме статусы вернулись в `ok`,
заявки остались открытыми.

Машины (machine_connect): ночью (по времени эмулятора 00:55 Kyiv) все станки off/idle; после сдвига времени 30 из 35 стали
`working`. Цепочка CNC-2: off → fault (21:56:49) → off (21:59:21) → working (22:03:07). `raw_ts` заполнен у 35 из 35.

Счётчики energy: 67 счётчиков из находки QA «без показаний» теперь все с показаниями; интервалы построены (67).
Не получили данных 9 производных `energy/consumers/{AHU-1,EF-CHG,EF-CMP,EF-ELEC,LP-1,LP-2,LP-3,OFFICE,RV-ALL}/kwh_shift`
(источник «Енергетика: обчислені показники», считает Odoo-крон из `kwh_total`; на момент остановки не появились,
причину не выяснял). У COL-MAIN без данных остаются 55 сигналов: 29 OPC UA (`workcenters/*/event`, `job_cmd` — события и
команды), 24 MQTT (нет брокера), по 1 REST-CUTOPT (`equipment/CUTOPT/cmd`) и woodStore.

## 3. Что не получилось / замечания (по убыванию важности)

1. Вес данных: сигналы `workcenters/*/state` и `workcenters/*/alarm` (Modbus-станки, `period_s=1`, `store_period_s=0`)
   пишутся при каждом опросе: ~74 тыс. из 79 тыс. новых показаний, по 1 825 строк на сигнал за 30 мин, около 40 сигналов →
   порядка 3,5 млн строк/сутки. Нужна запись «по изменению» или `store_period_s>0` (связано с telemetry DEC-16/ТП-04).
2. LPR: эмулятор шлёт push без токена, а у источника HTTP-PUSH на сервере задан `token_ref` → HTTP 401 (4 попытки, лог
   `iot_sim.lpr`). Это известный DEC-15 telemetry. Для проверки я временно убрал `token_ref` у источника HTTP-PUSH:
   6 запросов 200, в Odoo 4 `f3d.yard.lpr.event`. После теста `token_ref` восстановлен.
3. OPC UA SourceTimestamp эмулятора = локальное время Kyiv без зоны (`protocols/opcua_server.py:321`,
   `w.now().replace(tzinfo=None)`), коллектор читает его как UTC: ts оказывается на +3 ч в будущем, срабатывает защита
   `ua_values.value_ts` (подмена на `now`), в логе 232 WARNING «timestamp is in the future». Данные не теряются.
4. Эмулятор: принудительное значение (`PUT /sim/v1/signals/...`) не возвращается к модели после `hold_s` и после
   `release`: AIR-RING остался 4.5 (из-за этого сигнал был в alarm до 22:14), DUST-1 продолжал расти. Вернул значения
   вручную (форсом 6.4 и 1.0). Требует проверки: баг модели или так задумано.
5. MQTT-MOBILE offline: брокера нет (mosquitto не установлен, Docker запрещён). 24 сигнала `equipment/FL-*`, `TUGGER-1`
   без данных. Эмулятор при этом показывает `mqtt: ok` (DEC-15).
6. Кратковременный отказ сервера: HTTP 502 с 22:04:14 до ~22:04:50 (причина неизвестна; совпало по времени с моим
   сдвигом часов эмулятора, но связь не установлена). Коллектор буферизовал (6 «push failed», 1 «config refresh failed») и
   доотправил без потерь (`buffer_rows` 196 → 65).
7. Шум при старте: 45 WARNING «reading for unknown signal workcenters/…: scale not applied» и 2 для `equipment/BOILER/*`
   в первые 3 с после запуска (первые уведомления OPC UA раньше, чем карта сигналов). 15 WARNING «Woodworking event types
   not found (BadNoMatch)» (все UA-источники, откат на BaseEventType — DEC-10 iot_sim); события получены (3), `message_name`
   пуст. Единичный сбой опроса MB-U69-BESS «database table is locked» (SQLite-буфер, 22:13:22).
8. Побочный эффект теста: сдвиг времени эмулятора на +9,5 ч увеличил счётчики kWh на сервере (65 из 67 ненулевые);
   на тестовой БД допустимо. На сервере остаются 4 тестовые заявки #50–#53 и записи LPR.

## 4. Не проверено

- Всё направление Odoo → эмулятор: `factory3d.iot_sim.url` пуст, сервер до контейнера не достаёт («проверить соединение»,
  опрос состояния сервиса, запуск сценариев и команд из панели). Команды записи не проверялись (`F3D_WRITE_ENABLED=0`,
  `f3d.command` = 0).
- Крон Odoo «СКУД: опитування подій BioStar» (BioStar-эмулятор недоступен серверу), модуль access: сигналов 7, без данных.
- genset (relay `td_genset` отсутствует), MQTT/мобильная техника, cutopt и задания woodStore (только опрос REST-WOODSTORE:
  52 показания), нагрузка и длительный прогон (>30 мин).
- Встроенный Odoo-эмулятор «Емулятор IoT: рівень 0» (`level0_enabled=True`) активен и пишет в те же сигналы; его
  взаимодействие с сервисом не проверялось.

## 5. Рецепт постоянного стенда на сервере

Вариант А (Docker, по `DEPLOY_TEST` telemetry): на сервере с доступом контейнеров к PyPI/реестру.
1. `services/iot_sim`: `cp .env.example .env`, задать `SIM_API_TOKEN` (>=32), `SIM_BIOSTAR_PASS`, `SIM_WOODSTORE_APIKEY`,
   `SIM_JOBS_APIKEY`, `SIM_OPCUA_PASS`, `SIM_MQTT_URL`, `SIM_CATALOG_SOURCE=local`; создать `mosquitto/passwd` (`sim`, `collector`);
   `docker compose -f docker-compose.sim.yml --profile demo up -d`.
2. `services/collector`: `.env` с `F3D_ODOO_URL=https://timur-o19demo.todo.ltd`, `F3D_COLLECTOR_CODE=COL-MAIN`,
   `F3D_COLLECTOR_TOKEN` (Odoo → Телеметрия → Колектори → «Згенерувати токен», показывается один раз),
   `F3D_ALLOW_HOSTS=iot-sim,mosquitto`, `F3D_OPCUA_PASSWORD=$SIM_OPCUA_PASS`, `F3D_WOODSTORE_KEY=$SIM_WOODSTORE_APIKEY`,
   `F3D_CUTOPT_KEY=$SIM_JOBS_APIKEY`, `F3D_MQTT_PASSWORD`, `F3D_HTTP_PUSH_SECRET_LPR`, `F3D_HTTP_PUSH_TOKEN_LPR`;
   `docker compose -f docker-compose.collector.yml up -d`. Оба compose в одной docker-сети, имена сервисов `iot-sim`,
   `mosquitto`, `collector` должны совпасть с адресами в данных источников.

Вариант Б (без Docker, как этот стенд): два venv (эмулятор; коллектор + bms + yard + machine_connect, bms/yard с `--no-deps`),
два systemd-юнита с `EnvironmentFile` (chmod 600) и `Restart=always`: `python -m iot_sim run` (WorkingDirectory=`services/iot_sim`)
и `f3d-collector run`; записи `127.0.0.1 iot-sim mosquitto collector` в `/etc/hosts`; mosquitto пакетом ОС с пользователями
`sim` и `collector`; BACnet: коллектор `F3D_BACNET_BIND=127.0.0.2:47808`, эмулятор 127.0.0.1.

Настройка в Odoo (для обоих вариантов):
- `factory3d.iot_sim.url` = адрес эмулятора, достижимый с сервера Odoo (`http://iot-sim:8090`) и его токен, иначе панель
  «проверить соединение» и команды не работают;
- источник HTTP-PUSH: либо снять `token_ref`, либо научить эмулятор слать токен (п. 3.2);
- отключить встроенный крон «Емулятор IoT: рівень 0 (без сервісу)» (`level0_enabled=False`), чтобы он не писал в те же сигналы;
- решить п. 3.1 (объём состояний станков) до включения на постоянной основе; мониторинг: `/metrics` и `/health` коллектора
  на :9108, `f3d.collector.state`, размер `f3d_reading`;
- токен коллектора хранить как секрет, при утечке — `action_revoke_token` и выдать заново.

## 6. Состояние на конец теста

Процессов нет (эмулятор и коллектор остановлены, порты свободны, `/etc/hosts` восстановлен). Токен COL-MAIN отозван, `token_ref`
источника HTTP-PUSH восстановлен. На диске остались venv и копия исходников в `$S` (не в репозитории) и логи
`$S/run/collector.log`, `$S/run/sim.log`. Сервер: COL-MAIN останется `online` до срабатывания проверки `last_seen`,
затем станет `offline`. Данные теста (показания, заявки #50–#53, LPR-события) на сервере сохранены.
