# factory3d_energy
Статус: IN_PROGRESS
Тесты: 109/109 (и совместно с base/telemetry/viewer/iot_sim) (2026-10-15), ТК: ждут W6
Решений без заказчика: 17 (ниже)
Упирался в лимит: 0
Требует внимания человека: правки SPEC: AC-32 (DEC-8), R-16 п.6 380 В (DEC-15), R-17 ключи (DEC-16)

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 952705a | install + test_data_sync 11/11 |
| W1 | принят | 34ae1b3 | /factory3d_energy 38/38 |
| W2 | принят | 013a25f | /factory3d_energy 64/64 |
| W3 | принят | c72ce00 (+merge) | /factory3d_energy 91/91 |
| W4 | принят | 6c2b011 | /factory3d_energy 73/73 |
| W5 | принят | ce2b4df | /factory3d_energy 109/109 |
| W6 | в работе | — | — |

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
- DEC-11: положение ATyS по значению: 2 = pos_I (мережа), 3 = pos_II (генератор); АВР несвежий (>15 с) при живых вводах — отключение закрывается (R-14 п.7) с `return_s=0` — `models/f3d_energy_outage.py`
- DEC-12: сверка с мостом genset — только при `mode` auto/remote, событие не чаще раза в сутки; заявка на ATS-1 при FAIL START — штатным порогом сигнала — `models/f3d_energy_outage.py`
- DEC-13: R-08 п.1 кандидаты WO с `date_finished ≥ d0` дополнительно ограничены `date_start < end` (иначе тянутся все плановые); idle-строки — для всех прямых узлов с лічильником — `models/f3d_energy_alloc.py`
- DEC-14: без `factory3d_machine_connect` R-08 п.2 (машинные интервалы) — обёртка `_f3d_machine_intervals`, контракт CM-03 с machine_connect не проверен — `models/f3d_energy_alloc.py`
- DEC-15: `consumers.i_now` считается при 380 В (R-16 п.6 говорит 400 В; AC-64 12,18 кВт / 0,84 = 22 А сходится только при 380) — правка SPEC — `tools/payload.py`
- DEC-16: `infra.totals` всегда содержит `shed_kw` (0 без отключения) и `bess_mode` — их требует AC-59, в списке R-17 их нет — `tools/payload.py`
- DEC-17: цена тарифа и `contract_kw` в payload читаются через sudo (только чтение; group_f3d_user тарифы не читает); настройки (res.config.settings) — только base.group_system, f3d_admin без system их не открывает (по §5 ARCH admin входит в system) — `tools/payload.py`, `models/res_config_settings.py`
