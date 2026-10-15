# td_genset
Статус: IN_PROGRESS
Тесты: td_genset 176/176 (Odoo 19, 2026-10-15), relay 20/20; ТК: ждут эмулятор
Решений без заказчика: 8 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W1 перенос td_genset 18→19 | принят | 5c2a9ef | /td_genset 176/176 |
| W0 каркас factory3d_genset | принят | 75fa1af | /factory3d_genset 3/3 |
| W1b адаптер ADP + ADAPTER_MAP | в работе | — | — |
| W2 мост: данные/телеметрия | ждёт W1b | — | — |
| W4 fake_relay D700 + REST | принят | 33cdac7 | relay/tests 20/20 |
| W3 мост: провайдер/представления | ждёт W2 | — | — |
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
