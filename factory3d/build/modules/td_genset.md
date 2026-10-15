# td_genset
Статус: IN_PROGRESS
Тесты: td_genset 176/176 (Odoo 19, 2026-10-15), relay 20/20; ТК: ждут эмулятор
Решений без заказчика: 15 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W1 перенос td_genset 18→19 | принят | 5c2a9ef | /td_genset 176/176 |
| W0 каркас factory3d_genset | принят | 75fa1af | /factory3d_genset 3/3 |
| W1b адаптер ADP + ADAPTER_MAP | принят | e4b70ea | /factory3d_genset 13/13 |
| W2a мост: связка/профиль/телеметрия | принят | bd68433 | /factory3d_genset 40/40 |
| W2b мост: события/ТО | принят | 33a2ecf | /factory3d_genset 67/67 |
| W4 fake_relay D700 + REST | принят | 33cdac7 | relay/tests 20/20 |
| W3 мост: провайдер/представления | в работе | — | — |
| W5 тестировщик | ждёт W1–W4 | — | — |

## Решения без заказчика
- DEC-1: отдельного репозитория `td_genset` (ветка 19.0, тег 18.0.2.0.2) в сессии нет — перенос делается в
  `factory3d/odoo_addons/td_genset/` из ветки `claude/dreamy-ramanujan-p2wlej` (`smartgen/td_genset`, коммит 166db7e,
  версия 18.0.1.0.0, 176 UT); `fake_relay.py` → `td_genset/relay/`; `docs/MIGRATION_19.md` → `td_genset/MIGRATION_19.md`.
- DEC-2: MG-xx — не отдельный коммит на пункт, а коммиты воркера W1 + журнал MIGRATION_19.md (команда/до/после на каждый MG).
- DEC-3: MG-30 preflight-файла в модуле нет; согласование neutralize.sql с CB-10 — в W0/W5 — td_genset/data/neutralize.sql.
- DEC-4: `_notify_progress` → `_commit_progress` (Odoo 19): в кроне прогресс коммитится по пачкам — models/*, MIGRATION_19.md.
- DEC-5: `/sim/v1/*` работает только при RELAY_PROFILE=d700 (office → 404) — relay/fake_relay.py.
- DEC-6: office.json документальный, старый Genset office на константах кода (поведение не меняется) — relay/profiles/office.json.
- DEC-7: вариант B (remote_start при сети) — p_kw=0 до POST /load (иначе D.3 не сходится) — relay/genset_model.py.
- DEC-8: `clear` без сети → standby, затем AMF снова в mains_abnormal; ТК-F04 восстанавливает сеть до clear — relay/genset_model.py.
- DEC-9: `alarm_level` моста считается только по тревогам контроллера; служебные тревоги td_genset (link_lost, cmd_unconfirmed…) не учитываются — потеря связи идёт через R-12 COMM_LOST — W2a, adapters/td_genset.py snapshot()["alarms"].
- DEC-10: ADP-09 — у td_genset нет постоянной расходной нормы (только вычисляемые fuel_rate_lph_7d/30d) → set_fuel_rate() возвращает False без записи (Q-11) — adapters/td_genset.py.
- DEC-11: код R-03 2 «сеть пропала, задержка» в genset_status отсутствует → мост выводит из state=1 и mains_ok=False; ADP-07 «последний тест» — из td.genset.command source='test' — adapters/td_genset.py.
- DEC-12: при отсутствии данных last_state_json сохраняет последние state/mode/alarm_level/island, меняется online (+ offline_since, comm_lost); сигнал state публикуется 0; offline_since — ts последнего снимка (COMM_LOST сразу, если снимок старше offline_min) — models/genset_link.py.
- DEC-13: список служебных тревог td_genset (DEC-9) — константы SERVICE_ALARM_CODES/PREFIXES; `_mark_stale` не трогает сигналы в unknown (первая публикация не fresh → unknown, не stale) — models/genset_link.py, adapters/telemetry.py.
- DEC-14: td_genset сам создаёт плановые заявки ТО → мост их не создаёт (R-09 только дописывает сигнал hours в открытые превентивные заявки td); крона events/service в XML active=False, включает хук по requests_enabled — models/genset_link_events.py, data/ir_cron.xml.
- DEC-15: `maintenance_for` в Odoo 19 CE нет — пишется только если поле есть; строка мапы COMM_LOST получила td_code="COMM_LOST" (иначе уходила в DEFAULT_COMM без заявки); td_code заполнен для 32 из 48 строк, остальные — по hgm_name (Q-13 частично) — data/f3d_genset_event_map.xml.
