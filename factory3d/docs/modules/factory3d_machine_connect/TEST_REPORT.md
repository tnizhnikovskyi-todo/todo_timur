# TEST_REPORT factory3d_machine_connect (W9)

Дата: **2026-10-15**. Стенд — процесний режим без Docker (див. DEPLOY_TEST.md): iot_sim 0.1.0, колектор + пакет `f3d_collector_mc`,
Odoo 19 CE (один процес), посів `tests/stand/seed_pre.py` (демо-копії `odoo` немає). Прогін: `pytest <пакет> -m stand`
(фінальний прогін 11 тестів — 7 PASS / 4 FAIL; решта прогнана групами по мірі виправлення тестів, у таблицях — останній результат).
Режими: **iot_sim** — проти емулятора; **фейк** — проти фейкового OPC UA-сервера пакета (`tests/fakes`), де iot_sim не підтримує сценарій.

## Підсумок

| Набір | Результат |
|---|---|
| Odoo `/factory3d_machine_connect` (F3D_TEST_INSTALL) | 0 failed of 127 |
| Пакет `pytest -m "not stand"` | 53 passed |
| ТК (16) | PASS 12 (04, 09, 11, 12 — частково на фейку); FAIL 2 (03, 15); НЕ ПРОГНАН 1 (14) ; ТК-04 Store з Odoo на iot_sim — xfail |
| ТБ (10) | PASS 9 (ТБ-03 — крім критерію логу); FAIL-частина ТБ-03 |
| ТП (4) | PASS 2 (02, 03); FAIL 2 (01 — дедлоки; 04 — HTTP 500 EV-02) |

## Дефекти коду, знайдені стендом і виправлені (з регресс-тестами)

| Файл | Суть |
|---|---|
| `f3d_collector_mc/ua_values.py`, `models/f3d_machine_downtime.py` | Подія без ActiveState (BaseEventType) йшла з `active=false` → запис «Події верстатів» архівувався й зникав зі списку. Тепер `active=true` для не-тривог (тести `test_plain_event_without_activestate_is_active`, `test_plain_event_is_not_archived`) |
| `models/maintenance_request.py` | Заявка з тривоги створюється до переходу в `fault` і чіплялась до відкритого простою «Очікування»; простій `fault` лишався без заявки (R-08). Тепер лише до простою `fault` (`test_request_before_fault_goes_to_fault_downtime`) |
| `f3d_collector_mc/ua_session.py` | При SignAndEncrypt і чужому сертифікаті asyncua дає лише TimeoutError — додано підказку «server certificate» (ТБ-07; `test_secure_connect_failure_names_server_certificate`) |

## Не виправлено — потребує рішення

* **ТП-01 дедлоки**: 72 `deadlock detected` і 278 `could not serialize` при 35 верстатах/с + крон `_cron_tick`/`_cron_oee`/оновлення `f3d_collector` (одночасні UPDATE рядків `f3d_machine`/`f3d_collector`); API-02: 281×200, p95 451 мс, p99 1819 мс, max 10,6 с, 0×5xx, перекриттів 0. Критерій «0 дедлоків» не виконано.
* **ТБ-03**: одноразовий токен `t` потрапляє в access-log werkzeug (URL з query); SPEC вимагає 0 збігів. Решта ТБ-03 PASS (100×403, одноразовість, `no-store`, 401).
* **ТП-04**: POST `/f3d/telemetry/event` з 27 стосами (EV-02) → HTTP 500 (аналіз не завершено; можливо формат payload тесту).
* **ТК-03**: крок «події I0001/I0002» — подій у «Подіях верстатів» за прогін немає (див. обмеження iot_sim); решта перевірок (журнал без розривів, 0 записів `write_uid`=бот, 0 команд) пройшла до цього кроку.
* **ТК-15**: крок 2 — автостарт I/O-верстата (SLIDE-1) після вмикання `auto_start_enabled` не спрацював за 120 с (не розібрано); п'ять запобіжників — не досягнуто у прогоні. Раніше ТК-05 (автостарт I/O) — PASS.

## Обмеження iot_sim (власник емулятора; не правилось)

1. `SourceTimestamp` OPC UA пишеться наївним київським часом → плагін бачить «в майбутньому» й підставляє час приймання.
2. Події: BaseEventType без MessageId/EventCategory/PathParts (немає WwBaseEventType) → підказка «E0421 …» (AC-94) на ньому не відтворюється.
3. `JobOrderList` — `String[]`, а не структури ISA-95; методи `JobOrderControl` мають BrowseName в просторі екземплярів і вхід (String, String) → `Store` з Odoo = BadNoMatch, `job` у плагіні завжди `-`.
4. Виклики Store/Start з пульта не впливають на модель верстата в `scenario` (немає споживача `opc_joborder`).
5. `machine_fault comm`: `CurrentState=OFFLINE` зі статусом Good → верстат `off`, а не `nodata`.
6. SignAndEncrypt вмикається лише за наявності `server.der`/`server.key` (DER) у `SIM_OPCUA_CERT_DIR`.
7. `iot-sim`=127.0.0.1 збігається з хостом Odoo → allow-list не відмовляє; у ТБ-08 `iot-sim` тимчасово 127.0.0.2.
Спостереження ядра колектора: на старті попередження «reading for unknown signal … scale not applied»; одноразова `push failed (HTTP 500)`; `address already in use` при швидкому рестарті (стенд чекає звільнення порту).

## ТК (§13.2)

| ТК | Режим | Статус | Факт / причина |
|---|---|---|---|
| 01 | iot_sim (`shift`) | PASS | S0–S5 без змін, `migration_report=done`, 35 верстатів, усі 22+1 джерела online ≤ 3 хв. Без демо-копії (29 working/74 простої — людина) |
| 02 | iot_sim + фейк | PASS | fault ≤ 10 с, події, простій, заявка пов'язана, РЦ blocked; підказка E0421 — на фейку |
| 03 | iot_sim | FAIL | див. вище (події I0001/I0002; тривалість 12 хв замість 60) |
| 04 | фейк | PASS | Store (ReturnStatus 0) → Start → автостарт ≤ 15 с, `OP-SAW-1`, автозавершення, qty 2. На iot_sim — xfail (п. 3–4) |
| 05 | iot_sim | PASS | автостарт «одне в черзі», лічильник через межу слова, done, fault + одна заявка |
| 06 | iot_sim | PASS | feed `done`, `ws_id=wj-…`, 4 листи, стос −4, `fed_unconsumed=4` (закриття МО — MAN) |
| 07 | iot_sim | PASS | pending→diff→діяльність→accept; `stack` fix; `stack_diff_confirm_min=2` замість 10; кроки 6–8 (поповнення) НЕ ПРОГНАНО |
| 08 | iot_sim | PASS | `origin='machine'`, done=2, стос −2, тривога GANTRY-1 → одна заявка, команд 0 |
| 09 | iot_sim | PASS | CSV за R-19, план → planned, release без команд |
| 10 | iot_sim + фейк | PASS | upload→planned→released, `cj-…` у JobOrderList, автостарт на фейку; `done` карти НЕ ПРОГНАНО (емулятор) |
| 11 | iot_sim | PASS | кроки 1–3, 5, 6; крок 4 (злиття, Shop Floor) — MAN |
| 12 | фейк | PASS | nodata ≤ 180 с, автодій 0, відновлення; на iot_sim — xfail (п. 5) |
| 13 | iot_sim | PASS | інтервал idle [T1,T2) ±6 с, без дублікатів, буфер спорожнів |
| 14 | — | НЕ ПРОГНАН | `factory3d_viewer` не встановлено (середовище) |
| 15 | iot_sim | FAIL | див. вище |
| 16 | iot_sim | PASS | простій закрито на межі зміни (календар «до now+9 хв»), OEE `closed`, повтор крону без змін, формули ±1e-4/±0,5 |

## ТБ (§13.3)

| ТБ | Статус | Факт |
|---|---|---|
| 01 | PASS | матриця прав `has_access` для 6 користувачів; UI-меню — MAN |
| 02 | PASS | grep write_value/set_value/… = 0; запобіжники запису — частково (ТК-15 FAIL) |
| 03 | PASS* | *крім логу (див. вище) |
| 04 | PASS | автентифікація бота → False, неактивний, без пароля |
| 05 | PASS | секрети відсутні в логах колектора (DEBUG 5 хв), Odoo, config; у params лише `*_ref` |
| 06 | PASS | SQL-текст у job, XSS екрановано, `;` у ref → job `error`, grep SQL = 0 |
| 07 | PASS | pin → online; чужий сертифікат → error (підказка); без pin → «not pinned»; без користувача → BadUserAccessDenied |
| 08 | PASS | `not set`, 401, verify_tls=false, allow-list (iot-sim=127.0.0.2), колектор healthy |
| 09 | PASS | користувач C2 бачить лише M2; стоси порталу не обмежені правилами |
| 10 | PASS | neutralize.sql: прапори False, крони неактивні, токени NULL, надсилання не створює команд |

## ТП (§13.4)

| ТП | Статус | Факт (скорочено: 5 хв замість 30) |
|---|---|---|
| 01 | FAIL | p95 451 мс (≤1200), p99 1819 (≤2000), 0×5xx, CPU 21 %, `_cron_tick` до 9,1 с; **72 дедлоки** |
| 02 | PASS | 16 переходів, p95 5,5 с, буфер ≤ 20, CPU 1 %, RSS 102 МБ (8 хв замість 30) |
| 03 | PASS | 837 900 інтервалів/140 000 простоїв: `_cron_oee` 0,6 с, ротація 73 500 за 2 с (keep_log_days=365), Index Scan; WO 20 000 і OEE-звіт — не виміряно коректно |
| 04 | FAIL | EV-02 HTTP 500; `_cron_gantry`/API-01 5 000 деталей не досягнуто |

## AC-93…AC-100

AC-93 — НЕ ПРОГНАН (демо-копія, follow_odoo); AC-94 — ТК-02 (фейк); AC-95 — ТК-04 (фейк); AC-96 — ТК-06; AC-97 — ТК-10 (частково);
AC-98 — ТК-12 (фейк); AC-99 — FAIL (ТП-01 дедлоки); AC-100 — ТК-03 (частково, FAIL).
