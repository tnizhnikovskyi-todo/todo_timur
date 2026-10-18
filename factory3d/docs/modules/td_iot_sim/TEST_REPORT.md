# TEST_REPORT — factory3d_iot_sim (стенд, ТК/ТБ/ТП, SPEC §13.2–13.5)

Воркер W6, 15.10.2026. Гілка `claude/f3d-factory3d_iot_sim`. Сервіс `factory3d/services/iot_sim/`, модуль Odoo
`factory3d/odoo_addons/factory3d_iot_sim/` 19.0.2.0.0. Код стенда — `factory3d/services/iot_sim/tests/stand/` (`pytest -m stand`),
підняти — `tests/stand/up.sh`. Чек-лист розгортання — `DEPLOY_TEST.md`.

## Середовище і обмеження

| Параметр | Значення |
|---|---|
| Docker | 29.8.2; образи: `python:3.12-slim` (з вшитим CA проксі, лише для збірки), `eclipse-mosquitto:2.0.20`, `f3d_iot_sim` (збірка з `Dockerfile`) |
| Бібліотеки клієнтів | pymodbus 3.9.2, asyncua 1.1.6, bacpypes3 0.0.102, paho-mqtt 2.1.0, httpx 0.28.1, pytest 9.1.1 |
| Хеш каталогу | `sha256:e14fc2041e68a0e667307150f8ae4d561f9229dafffc998f635199fa08f13533` (`catalog/signals.csv` = `data/f3d_sim_signal.csv` = `GET /catalog/signals.csv`) |
| Стенд | `docker compose -f docker-compose.sim.yml --profile dev` (iot_sim + mosquitto). **Без `genset_relay`**: у `td_genset` (`origin/claude/dreamy-ramanujan-p2wlej`) немає каталогу `relay/` і `/sim/v1` API-F (є лише `smartgen/tools/fake_relay.py` зі старим інтерфейсом) → запасний режим §8.14 |
| Odoo | Odoo 19.0 CE зі шаблонної бази `f3d_template` + `factory3d_iot_sim` (**копії демо-бази немає**): `f3d.sim.device`=230, `f3d.sim.signal`=1168 (151 `protocol=none`), сценаріїв 15; дані РЦ/працівників сідуються `test_odoo_e2e.py` через XML-RPC (2 РЦ, 35 працівників) |
| Доступ клієнтів | Порти §8.1.3 не публікуються на хост (ТБ-01); тести ходять на IP контейнера в мережі `f3d_sim` (маршрутизується з хоста), REST/OPC UA — на `127.0.0.1:8090/4840` |
| Скорочення | 15 хв → 45–110 с (на `factor=10`), 10 хв → 120 с, 30 хв → 60–75 с, 24 год (ТП-06) — не прогнано; кожне скорочення позначено «скорочено» |

Підсумок останнього повного прогону `pytest -m stand tests/stand`: **46 тестів (stand): 43 пройшли в повному прогоні, 2 пропущено (ТК-18 кроки 2–5, ТК-10 без Odoo), 1 нестабільний; після виправлень перепрогнано вибірково (misc+modbus 11 passed, perf+ТП-04 5 passed)**
(ТК-02 після `fire_drill` — виправлено `reset` двору, перепрогнано: зелений). Юніт/інтеграція (`pytest tests -q`, без stand): **451 passed**.
`ruff check .` — чисто. Модульні тести Odoo (`run_tests.sh`) — 40/40 (модуль не змінювався).

## ТК — стендові сценарії (§13.2)

Підсумок: **прогнано 16**, **частково 1 (ТК-07)**, **не прогнано 1 (ТК-18)**. «Прогнан» — з позначками нижче; усі ТК виконувалися з `POST /reset` до/після.

| ТК | Що перевірено | Підсумок | Тест |
|---|---|---|---|
| ТК-01 | OPC UA: 16 об'єктів `Machines`, `SAW-1` HOMAG, 26 булевих `Flags`, `RelativePiecesOut` UInt64, DataChange росте, write у `CurrentState` → відхилено. Варіант `follow_odoo` (AC-07) на шаблонній базі: `SAW-1`=3 (workorder `progress`), `CNC-2`=4 + `Error=True` (`working_state=blocked`), `factor≠1` → 409. Не перевірено: лічильник «+6/15 хв», PM5560 `u22` | **прогнан** (follow_odoo — на шаблоні, не на копії демо) | `test_opcua_portal.py::test_tk01…`, `test_odoo_e2e.py::test_tk01_follow_odoo_states` |
| ТК-02 | PM5560 `u11 pdu3059+2` = `/signals` і ∈ [10,9; 13,5]; INT64 `3203` росте; `Σu3…u8 ≈ u1+u2` (±1 % + 1 кВт); ADAM `u80 fc2 0+12`, `fc3 0+24`, `pdu210=0x6050`, unit 200 → 0x0B, `pdu9998` → 0x02, лічильник `[1,1]` = 65 537 (молодше слово першим); FC05 `u86 pdu16` → DI0; FC06 `u11` → 0x02; `u51…u59` | **прогнан** | `test_modbus.py::test_tk02…` |
| ТК-03 | Who-Is (101–125, 130–133, 140, 200; 99 — опційно), RP 25 RV ≤ 2,5 с, COV на AI:4, write AO:1=80 (пріоритет 8) → утримується, MSV:1=7 → AI:3 ≈ 0, BI:1=0. Утримання 10 хв — **скорочено** до перевірки відразу після запису | **прогнан** | `test_mqtt_bacnet.py::test_tk03…` |
| ТК-04 | `f3d/mobile/#`: ≥ 8 кодів, JSON валідний, `status` retained `online=true`, `battery_low FL-2 level_pct=18` → `to_charge`/`charging`, `fault comm FL-3` → `status online=false`; брокер відхиляє хибний пароль. **Скорочено**: 45 с на `factor=10` замість 3 хв | **прогнан** | `test_mqtt_bacnet.py::test_tk04…` |
| ТК-05 | woodStore: 23 стоси `qty>0`, `POST /jobs feed 3` → `PLT-04C qty −3`, стани `/status`, OPC UA `GANTRY-1…CurrentState`, `signals/equipment/GANTRY-1/stacks` → 404, хибний `X-Api-Key` → 401 | **прогнан** | `test_opcua_portal.py::test_tk05…` |
| ТК-06 | `compressor_fault`: тиск < 6,0 ≤ 15 хв sim, подія; `u70 pdu3001` = тиск·1000; `pdu3009` = `load`; `u90`, `u96`, `u84` читаються, лічильник води не спадає. Читання по регістрах (суцільне `3000+30` дає 0x02 — розріджена карта). `load ≥ 80` (AC-12) — лише коли всі 35 РЦ WORKING; на стенді 13/35 → перевірено `load = сигнал` і `≥ 25`. Лічильник води «+350 імп» — **не** перевірено кількісно | **прогнан** (частково по AC-12 / воді) | `test_modbus.py::test_tk06…` |
| ТК-07 | `pv_cloudy` → `blackout` (варіант A, `hgm`, **запасний режим без relay**, 15 с): `u71 pdu20483` 3→2, `20486`=0/2, `20487`=2, `20482`=32, `u1/u2`=0, `u61 pdu32089`=0x0303, повернення. **Не прогнано**: варіант `amf_master=ats`, `chp_island=true`, `fake_relay` API-F-09, `load.kw`=348 (немає relay), `u72`/`u69` за межами одиничних читань | **частково** | `test_modbus.py::test_tk07…` |
| ТК-08 | `fire_drill FA-CNC`: LSZ:14/LSP:21405 = `test-alarm`, BV:10=1, `u85 DI4`=1, `u86 fc1 pdu20+2`=`[1,1]`, BioStar 20480 на дверях 1–5; write LSZ/BV/PIV/MSV → `write-access-denied`, ReinitializeDevice/DCC відхилені; `filter_clogged FA-FAC` → PIV:21607 ≥ 90; `FA-CUT` `sensor`→`clear`→`loop`, `spindle`/`PV-ROOF` → 422; 302 LSP, `1.MCP.01`/`2.SND.13`/`2.FLM.01`. `object-list` читається поелементно (див. «Спостереження») | **прогнан** | `test_mqtt_bacnet.py::test_tk08…`, `test_misc.py::test_tk08_fire_drill_side_effects` |
| ТК-09 | `spark count=2`: 2 імпульси DI0, `count_today += 2`, DO0 (FC05 `u85 pdu16`) → DI4 через 60 с sim | **прогнан** | `test_modbus.py::test_tk09…` |
| ТК-10 | Сесія `bs-session-id`, помилки входу (`code=101`, без сесії `10`), `access_event ACR-ELEC 6400` (двері 2), `DELETE` відхилено, logout → 401. 35 працівників з Odoo (шаблон) о 06:30 sim: події 4102/4867, ≥ 20 користувачів, пагінація `offset` = `hint`, сортування. **Скорочено** 5 хв → 110 с на `factor=10` | **прогнан** (працівники сідуються в Odoo, не з демо) | `test_misc.py::test_tk10_biostar_session_and_6400`, `test_odoo_e2e.py::test_tk10…` |
| ТК-11 | `truck_arrival BATCH/IN/00001`: DI0/DI1, SICS `S S 25200 kg` ± 20, LPR `plateList=f3d_bookings`/`allow`/`GATE-W`; `BATCH/OUT/00004` (`AA4512KT`, `plateListDescription`); `truck_no_booking` (`plateList=""`, `none`, DI0=0). Виїзне зважування 14 000 кг — **не** перевірено; `factor=3` | **прогнан** | `test_misc.py::test_tk11…`, `test_ac42_sics_basic` |
| ТК-12 | `u82/u83` DI/лічильники, 10 хв sim (≈10 с на `factor=60`), `machine_fault ASM-3 emergency` → fault=1, run=0 | **прогнан** | `test_modbus.py::test_tk12…` |
| ТК-13 | Усі ендпоінти з/без токена, `stop-all` → 423, `resume`, `SIM_ENABLED=0` (рестарт), `PUT /signals … hold`, `hold_s` > ліміт → 422 | **прогнан** | `test_rest.py::test_tk13_*` |
| ТК-14 | `factor=10`: 10 с реального = 100 ± 15 с sim, `factor=500` → 422. Порівняння лічильників із `factor=1` на 100 хв — **замінено** ТП-07 (30 хв sim) | **прогнан** (скорочено) | `test_rest.py::test_tk14…`, `test_perf.py::test_tp07…` |
| ТК-15 | Пульт Odoo через RPC методів кнопок: «Перевірити зв'язок» → `online`, крон рівня 0 вимкнено (`auto_off`); режим `scenario` + прискорення 5; сценарій `filter_clogged` (`RV-05`, 285) → `RUN/…`, подія `command`, сигнал > 250; збій `CNC-2` → `fault`, «Скинути»; зупинка сервісу (поріг 1 хв) → крон рівня 0 увімкнено; запуск → вимкнено. Не перевірено: UI мишею, чаттер, заявка ТО від рівня 0 | **прогнан** (на шаблоні; без UI і заявки ТО) | `test_odoo_e2e.py::test_tk15…` |
| ТК-16 | `shift` + `machine_fault`, `docker restart`: лог «restored snapshot», лічильники не скинуті, CNC-3 у fault (дефект виправлено, див. нижче) | **прогнан** | `test_rest.py::test_tk16…` |
| ТК-17 | Два TCP-клієнти: `C:152` (`V:1`/`V:2`), `C:13` з/без `A:1` (відповідь лише відправнику, push усім), `C:164 G:16` (два кадри `$`/`#`), `C:110` після `fault_device`, `C:191`; `SIM_HELVAR_VERSION=1` (рестарт) → `V:2` = 18, `C:191`=1. Дефект env виправлено | **прогнан** | `test_misc.py::test_tk17_*` |
| ТК-18 | Крок 1 (`compose config`, env/мережі `genset_relay`, спільний токен) — так. Кроки 2–5 — **немає relay** (`td_genset` не містить `relay/` і `/sim/v1`) | **не прогнан** (крок 1 — так) | `test_compose.py` (кроки 2–5 `skip` з причиною) |

## ТБ — безпека (§13.3)

Підсумок: **прогнано 10 з 10** (ТБ-04, ТБ-06 — з приміткою).

| ТБ | Що перевірено | Підсумок | Тест |
|---|---|---|---|
| ТБ-01 | `compose --profile demo config`: жодного `ports`; `dev`: лише `127.0.0.1:8090`/`4840`; `f3d_sim` internal; `cap_drop=ALL`, `read_only`, user 10001, не privileged; `docker ps`/`inspect` — порти 502/47808/50000/… не на хості. (Дефект compose виправлено) | **прогнан** | `test_security.py::test_tb01…` |
| ТБ-02 | Без токена / хибний / довжиною 200 → 401; 6 хибних за хвилину → 429 (навіть із вірним токеном із того ж IP), через 60 с знімається | **прогнан** | `test_rest.py::test_tb02…` |
| ТБ-03 | `../etc/passwd`, `CNC-2; DROP`, `note` 10 КБ, `params` вкладеністю 100, ім'я сценарію з `;` → 404/422, сервіс живий, у логу без трасувань | **прогнан** | `test_rest.py::test_tb03…` |
| ТБ-04 | BACnet dev 200: write LSZ/BV/PIV/MSV → `write-access-denied`, `ReinitializeDevice`/`DeviceCommunicationControl` відхилено; OPC UA write у `State.*` — анонімом **і** користувачем `collector` → відхилено (дефект виправлено); Modbus FC06 у PM5560 → 0x02; BioStar `DELETE /api/users/1` → 403/404/405. Modbus write у Huawei RO — не перевірено окремо | **прогнан** (частково по Huawei) | `test_mqtt_bacnet.py::test_tk08…`, `test_opcua_portal.py::test_tb04…`, `test_modbus.py::test_tk02…`, `test_misc.py::test_tk10_biostar_session_and_6400` |
| ТБ-05 | Чотири множини `code+address` (1168) збігаються: `catalog/signals.csv`, `data/f3d_sim_signal.csv`, `GET /catalog/signals.csv`, `GET /f3d/sim/devices` (Odoo); sha256 перших трьох однаковий; `GET /signals` ⊂ каталогу | **прогнан** | `test_security.py::test_tb05…`, `test_odoo_security.py::test_tb05…` |
| ТБ-06 | Лог контейнера (`SIM_LOG_LEVEL=DEBUG`, весь прогін ≈ 27 хв, включно з ТК-10/13) не містить значень `SIM_API_TOKEN`, `SIM_BIOSTAR_PASS`, `SIM_WOODSTORE_APIKEY`, `SIM_JOBS_APIKEY`, `SIM_OPCUA_PASS`, `bs-session-id`. `SIM_ODOO_APIKEY` — на стенді без Odoo-змінної (e2e-прогін окремо, лог не перевірявся) | **прогнан** (частково по `SIM_ODOO_APIKEY`) | `test_rest.py::test_tb06…` |
| ТБ-07 | `SIM_LPR_PUSH_URL` = хост поза allow-list: `iot_sim_outbound_denied_total` ≥ 1, у логу «outbound denied»; tcpdump-спостерігача не використано (метрика + лог) | **прогнан** (без tcpdump) | `test_security.py::test_tb07…` |
| ТБ-08 | `group_f3d_user`: `create/write/unlink` на `f3d.sim.{panel,device,signal,scenario,run,event}` → `AccessError`; менеджер: полів токенів у `res.config.settings` немає (адмін — є) | **прогнан** | `test_odoo_security.py::test_tb08…` (+ модульні `test_security.py`) |
| ТБ-09 | `token` замість `export_token` на `/f3d/sim/devices` і `/f3d/sim/events` → 401; `export_token` як токен REST керування → 401 | **прогнан** | `test_odoo_security.py::test_tb09…` |
| ТБ-10 | `neutralize.sql` на копії бази: крони `cron_iot_sim`/`cron_f3d_sim_status` неактивні, `state=unconfigured`; «Перевірити зв'язок» → повідомлення «вимкнено/не налаштовано», `stop-all`/`reset`/`apply_factor` → `UserError` | **прогнан** | `test_odoo_security.py::test_tb10…` |

## ТП — продуктивність (§13.4)

Підсумок: **прогнано 6 (усі скорочено), частково 1 (ТП-06)**. Хост: 4 vCPU, 16 ГБ; генератор навантаження на тому ж хості.

| ТП | Навантаження (скорочено) | Результат | Підсумок | Тест |
|---|---|---|---|---|
| ТП-01 | `factor=10`, 120 с (замість 10 хв), 3 клієнти (Modbus 20 зап/с, REST `/signals`, shift) | tick lag p95 = 0,000 с (запізнення понад період 1 с; 104 вибірки), CPU контейнера ≤ 0,06 ядра, RSS ≤ 161 МіБ (критерій: < 0,5 с / < 1 ядра / < 400 МіБ) | **прогнан** (скорочено) | `test_perf.py::test_tp01…` |
| ТП-02 | 20 клієнтів × 50 зап/с, 30 с | 1 000 зап/с, 0 помилок, p50 = 1,1 мс, p99 = 24,3 мс (критерій p99 < 50 мс); генератор — asyncio на тому ж хості | **прогнан** (скорочено) | `test_perf.py::test_tp02…` |
| ТП-03 | RPM `present-value` усіх об'єктів RV-01…25 щосекунди + COV 120 об'єктів, 60 с | 525 об'єктів RV-01…25, 120 COV; цикл RPM: середній 0,14 с, максимум 0,21 с (критерій < 2 с); CPU контейнера 0,03 ядра | **прогнан** (скорочено; CPU — контейнера, не окремо BACnet-таска) | `test_perf.py::test_tp03…` |
| ТП-04 | 10 клієнтів × підписка на всі CurrentState/RelativePiecesOut (32 вузли, не 720), publishing 500 мс, 75 с (замість 30 хв) | 90 вимірів: p50 = 0,69 с, p95 = 1,39 с, максимум 1,39 с (критерій < 1 с для медіани виконується, для p95 — ні: див. «Спостереження») | **прогнан частково**: затримка виміряна від `PUT /signals`; стабільність пам'яті 30 хв — не перевірялась | `test_opcua_portal.py::test_tp04…` |
| ТП-05 | `GET /signals` (1017) 10 раз/с, 20 с | p95 < 100 мс (є в тесті), `count ≥ 900` | **прогнан** | `test_rest.py::test_tp05…` |
| ТП-06 | Odoo: `refresh_signals` ≤ 5 с (≥ 1000 `f3d.sim.signal` без `none`), 2 000 подій через API-03 (по 100) ≤ 60 с, дедуплікація. **24 год крона — не прогнано** | див. тест | **частково** | `test_odoo_e2e.py::test_tp06…` |
| ТП-07 | 30 хв sim: `factor=60` (30 с) проти `factor=10` (3 хв), той самий seed після `reset`; лічильники РЦ і кількість подій | 84 лічильники `pieces_out`: розбіжностей 0 (допуск ± 0,5 % / ± 1 шт); подій 58 (`factor=10`) проти 60 (`factor=60`) | **прогнан** (скорочено: 30 хв замість 8 год; еталон `factor=10`, не `factor=1`) | `test_perf.py::test_tp07…` |

## Знайдені й виправлені дефекти

Кожен має тест (юніт/протокольний у `tests/`, або стендовий). Після правок `pytest tests -q` — зелений, `ruff check .` — чисто.

1. **Образ не збирав BACnet** (`IndexError` у `load_layout`): `dist/odoo_demo.json` не потрапляв у контекст збірки → додано `catalog/odoo_demo.json` (лише `fire`+`lighting`, ≈ 40 КБ), `load_layout` шукає його першим (`test_layout_catalog.py`).
2. **`read_only` ФС**: BioStar/OPC UA створювали `./certs` → `SIM_OPCUA_CERT_DIR=/app/state/certs` у compose.
3. **compose**: шляхи `./services/iot_sim/...` не збігалися з розташуванням файлу; порти 8090/4840 публікувались і в профілі `demo` (ТБ-01) → `iot_sim` (dev, з `ports` на 127.0.0.1) і `iot_sim_demo` (без `ports`, аліас `iot_sim`).
4. **BACnet слухав не ту мережу** (інтерфейс `odoo_default` замість `f3d_sim`; префікс завжди `/24`) → `_local_bip(peer)` обирає інтерфейс за маршрутом до брокера MQTT, префікс — з ioctl.
5. **OPC UA**: `Flags` мав 11 булевих замість 26 (AC-36), `ExternalEmergency` не публікувався (AC-15); клієнтський Write дозволявся автентифікованому `collector` (ТБ-04).
6. **ТК-16 / AC-48**: `shift_key` РЦ не потрапляв у знімок → після рестарту «нова зміна» обнуляла `Relative*`.
7. **ТК-04 / AC-08, AC-40**: сценарій `battery_low` не діяв на модель (модель тримала власний заряд); MQTT `telemetry.state` не віддавав `to_charge`; `status` публікувався лише при з'єднанні, не при зміні (`fault comm` → `online=false`).
8. **Хибні тривоги `QF-*/i_now`** (`> 0,9·номінал` читалось як абсолютні 0,9 А) — постійні події `alarm` при нормальному струмі.
9. **BioStar**: відповідь без сесії мала `Response.code="1"` замість `"10"` (AC-41).
10. **BACnet dev 200**: 222 LSP замість 302 (не було ручних, оповіщувачів, полум'я; AC-66).
11. **`POST /reset` не скидав стан моделей** (лічильники РЦ, АКБ, ГПВЧ, ворота/фури двору) → повторні прогони не відтворювалися (ТП-07: +9 шт на кожен прогін); тепер `World.reset_models()`.
12. **Метрика `iot_sim_tick_lag_seconds`** була часом від останнього тіку (0…1 с випадково), тепер — запізнення понад період тіку.
13. **`SIM_HELVAR_VERSION=1` з env** відхилявся (`Literal[1, 2]` проти рядка) → сервіс не стартував (ТК-17).
14. `tools/gen_catalog.py` — прапор виконання (ruff EXE001).

## Рішення лідера після стенду (виконано)

* `fire_drill` без `detector` для `FA-CNC` → `2.CNC.05` (LSP:21405), AC-15 (`test_fire_drill_default_detector_ac15`).
* `u69 fc3 pdu37000+51` блоком → 0x02 **залишено** як поведінку (розріджена карта BESS, X-51, як у реального приладу); читання по адресах працює.
* `object-list` цілком: сервер сегментує коректно; помилка була в тестовому клієнті bacpypes3 (клієнтський `Application` не оголошує
  сегментацію — потрібно `client.asap.device_object = client.device_object`). Стендовий тест читає список цілком (571 об'єкт dev 200),
  юніт — `test_object_list_full_read_segmented`.
* Modbus 2020 (Reset All Energies) обнуляє кВт·год лічильника і його споживачів (`Meter._commands`, `test_reset_all_energies_zeroes_counters`).

## DoD (SPEC §14), фінальний круг

| Пункт | Результат |
|---|---|
| `pytest tests -q` | 451 passed; покриття `iot_sim/core`+`models` — 99 % |
| `ruff` / `mypy --strict` | чисто (`mypy` у `pyproject.toml`; 84 точкових `# type: ignore[код]`, переважно «Cannot infer type of lambda» і Any від bacpypes3/asyncua без заглушок) |
| `pre-commit run --all-files` (корінь, `.pre-commit-config.yaml`: ruff+isort(I), xml lint, end-of-file, mypy) | Passed |
| `tools/gen_catalog.py --check` | OK, 1168 сигналів; sha256 `signals.csv` = `f3d_sim_signal.csv` |
| ТБ-05 | зелений (прогін стенду; після правок типів файли каталогу не змінювались) |
| Odoo `run_tests.sh f3d_iot_sim_dod /factory3d_iot_sim` (`factory3d_base,factory3d_iot_sim`) | OK, 0 failed of 40 tests |
| `CHANGELOG.md` сервісу 0.1.0 і модуля 19.0.2.0.0, `static/description/icon.png` | додано (іконка — з `factory3d_base`) |
| Не виконано | перегляд безпеки менеджером, звірка §4 ARCHITECTURE з UI, `compose --profile demo up ≤ 60 с` (demo-профіль лише `config`) |

## Спостереження без змін коду (потребують рішення)

* **ТП-04**: затримка DataChange фізично ≥ період тіку (1 с) + publishing (0,5 с): p50 = 0,69 с, p95 = 1,39 с.
* **AC-12**: `load ≥ 80` вимагає WORKING усіх 35 РЦ; `shift` на стенді дає 13/35.
* Демо-бази немає: `devices=276`, `level0 matched=196/196`, `x_f3d_signal`, `maintenance.equipment`=210 — не перевірені.
* `td_genset` не містить контракту CI-02 (`relay/`, `RELAY_PROFILE=d700`, `RELAY_SIM_TOKEN`, `/sim/v1/*`): ТК-18, ТК-07 (variant relay) і §8.14 «штатний режим» не перевіряються.
