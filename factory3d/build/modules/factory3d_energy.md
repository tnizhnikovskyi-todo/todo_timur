# factory3d_energy
Статус: IN_PROGRESS
Тесты: 38/38 (2026-10-15), ТК: ждут W6
Решений без заказчика: 7 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 952705a | install + test_data_sync 11/11 |
| W1 | принят | 34ae1b3 | /factory3d_energy 38/38 |
| W2 | в работе | — | — |
| W3 | ждёт | — | — |
| W4 | ждёт | — | — |
| W5 | ждёт | — | — |
| W6 | ждёт | — | — |

## Решения без заказчика
- DEC-1 (ENV-2): `mrp_workorder` (Enterprise) убран из `depends`; `time_ids` и V-16 — из CE `mrp`; что нет в CE — мост `factory3d_energy_mrp_workorder` (не тестирован — нет Enterprise) — `__manifest__.py`
- DEC-2: `imbalance_pct` min_duration — Додаток C «2 год» vs C.2 `min_duration_s=3600` — взято 3600 (явная таблица C.2) — `data/energy_signals.csv`
- DEC-3: сигналы из Додатка C с пометкой sim_data — в CSV `origin=sim_data`, хук W1 создаёт их с `origin='catalog'` (SPEC §5.2 знает лишь catalog/module) — `tools/gen_energy_data.py`, `hooks.py`
- DEC-4: `max_kw` лічильника нет в CSV — хук считает: ввід/фідер ceil(rating_a·0,4·√3), споживач max(10, ceil(2·p_inst)), SUN 125, LUNA 200, TEDOM 900 (сверено с D.1, 0 расхождений) — `hooks.py`
- DEC-5: тариф без зон допустим, цена 0; покрытие суток проверяется только при наличии зон — `models/f3d_energy_tariff.py`
- DEC-6: `read_enabled` хук ставит только при первой установке; повторная привязка не трогает (консервативно) — `hooks.py`
- DEC-7: AC-03 «1201,0» в SPEC = сумма p_inst всех 49 потребителей, а не поддерева QF-1 (207,5); тест проверяет оба — `tests/test_node.py`
