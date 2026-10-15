# factory3d_energy
Статус: IN_PROGRESS
Тесты: —, ТК: ждут W6
Решений без заказчика: 3 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 952705a | install + test_data_sync 11/11 |
| W1 | в работе | — | — |
| W2 | ждёт | — | — |
| W3 | ждёт | — | — |
| W4 | ждёт | — | — |
| W5 | ждёт | — | — |
| W6 | ждёт | — | — |

## Решения без заказчика
- DEC-1 (ENV-2): `mrp_workorder` (Enterprise) убран из `depends`; `time_ids` и V-16 — из CE `mrp`; что нет в CE — мост `factory3d_energy_mrp_workorder` (не тестирован — нет Enterprise) — `__manifest__.py`
- DEC-2: `imbalance_pct` min_duration — Додаток C «2 год» vs C.2 `min_duration_s=3600` — взято 3600 (явная таблица C.2) — `data/energy_signals.csv`
- DEC-3: сигналы из Додатка C с пометкой sim_data — в CSV `origin=sim_data`, хук W1 создаёт их с `origin='catalog'` (SPEC §5.2 знает лишь catalog/module) — `tools/gen_energy_data.py`, `hooks.py`
