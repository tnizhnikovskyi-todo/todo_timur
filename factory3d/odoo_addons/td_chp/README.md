# td_chp — Когенерація: пульт КГУ

Модуль Odoo 19 (`depends`: `td_factory3d`, `td_telemetry`, `maintenance`, `mail`, `bus`, `web`; LGPL-3, `application=True`).
Пульт газової когенераційної установки (TEDOM Quanto D800 NG, V16): живі показання з Modbus-контролера через колектор
телеметрії, 3D-модель і мнемосхема, блокування, команди з підтвердженням, журнал подій і аварій, ТО за наробітком.

Документація: `factory3d/docs/modules/td_chp/` (`SPEC.md` — вимоги, `ARCHITECTURE.md` — технічне рішення і план збирання).
Міст до пульта енергетики — модуль `td_chp_factory3d`.

## Що всередині

| Частина | Де |
|---|---|
| Агрегат (паспорт, пороги) · журнал подій · команди · правила ТО | `models/td_chp_{unit,event,command,maintenance_rule}.py` |
| API пульта (`td.chp.pult`, AbstractModel) і хуки для мосту | `models/td_chp_pult.py` |
| Маршрути `/td_chp/{state,trend,journal,ack,cmd,maintenance,sim}` (`jsonrpc`, `auth="user"`) | `controllers/main.py` |
| Карта 230 сигналів `chp/…` (типова, налаштовується в Odoo) | `data/chp_signals.json`, `tools/gen_chp_signals.py` |
| Розрахунки: KPI, циліндри, блокування, аварії, тренд, шина | `tools/` |
| Клієнт «Пульт КГУ» (`td_chp.pult`) | `static/` (окремий воркер) |

## Налаштування

Параметри `ir.config_parameter` (Налаштування → Когенерація, лише адміністратор):

* `td.chp.read_enabled` — стоп-кран читання (`True` на тесті; на проді `False` до звірки). `False`: API-01 віддає
  `{"read_disabled": true}`, події, ТО й крони не працюють.
* `td.chp.write_enabled` (за замовчуванням `False`) — запис команд у контролер.
* `td.chp.remote_switching_enabled` (за замовчуванням `False`) — дистанційний пуск (зупинка від нього не залежить).
* `td.chp.confirm_ttl_s`=60, `second_ttl_s`=600, `verify_timeout_s`=30, `command_ttl_s`=60, `stale_s`=30,
  `event_keep_days`=365, `bus_throttle_s`=1.

Запис у контролер потребує ще й `td.telemetry.write_enabled`, `write_enabled` джерела `CHP-U72` і сигналу цілі
(`chp/ctl/cmd`, `ctl/mode`, `ctl/sp_pct`, `ctl/cos_set`, `ctl/heat_dir`, `ctl/bypass_mode`; усі вимкнені після встановлення).
`neutralize.sql` (`data/`) вимикає крони, запис, дистанційний пуск і скасовує команди в черзі.

### Права

`КГУ: перегляд` (⊂ `td_factory3d.group_td_user`) → `КГУ: енергетик` (квитування, команди, «ТО виконано») →
`КГУ: головний енергетик` (клас Б одноосібно; може бути другою особою). Адміністратор без цих груп команд не підтверджує.
«Імітація» (API-07) — лише `td_factory3d.group_td_manager` і лише з `td_iot_sim`.

### Карта регістрів

Типова карта (припущення) створюється при встановленні (`post_init`, ідемпотентно). «Когенерація → Карта регістрів»:
правка адреси, типу, множника, одиниці, періоду й порогів сигналу; код сигналу незмінний. «Паспорт → Джерело й карта →
Відновити типову карту» повертає заводські значення з `chp_signals.json`. Адреса й порт контролера — у джерелі `CHP-U72`.

## Команди й міст (D-15)

Без мосту команди живуть у `td.chp.command` (клас Б — `start`, `stop`: головний енергетик одноосібно або енергетик +
2/2 **іншої** особи; решта — клас А). З мостом `td_chp_factory3d` усі 9 видів (start, stop, estop, reset, set_*) йдуть у
`td_energy_control`, а `td.chp.command` не створюється. Хуки `td.chp.pult`, які перевизначає міст цілком:
`_td_route(kind)`, `_td_dispatch(op, unit, kind, params, ref, token)`, `_td_command_rows(unit, limit, before)`,
`_td_pending_rows(unit)`, `_td_flags(unit)`.

## Тести

```bash
F3D_TEST_INSTALL=td_chp factory3d/tools/odoo/run_tests.sh <db> /td_chp     # усе, окрім Hoot-набору пульта
F3D_TEST_INSTALL=td_chp,td_iot_sim factory3d/tools/odoo/run_tests.sh <db> /td_chp:TestSim
```
