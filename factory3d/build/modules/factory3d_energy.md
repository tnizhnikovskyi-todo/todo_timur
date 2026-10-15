# factory3d_energy
Статус: IN_PROGRESS
Тесты: 64/64 (2026-10-15), ТК: ждут W6
Решений без заказчика: 10 (ниже)
Упирался в лимит: 0
Требует внимания человека: правка SPEC AC-32 (DEC-8)

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 952705a | install + test_data_sync 11/11 |
| W1 | принят | 34ae1b3 | /factory3d_energy 38/38 |
| W2 | принят | 013a25f | /factory3d_energy 64/64 |
| W3 | в работе | — | — |
| W4 | в работе | — | — |
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
- DEC-8: AC-32 ждёт `warn` после первого часа при `min_duration_s=3600`; логика telemetry даёт `ok` после первого, `alarm` после второго — оставлена логика telemetry, тест под неё; SPEC AC-32 поправить — `tests/test_balance.py`
- DEC-9: R-04 п.3 — после превышения `max_wait_h` все последующие слоты `missing` (как в примере AC-22), а не только первые два — `models/f3d_energy_interval.py`
- DEC-10: баланс пропускает час, если у лічильника < 4 интервалов в часе (не только `missing`) — `tools/balance.py`
