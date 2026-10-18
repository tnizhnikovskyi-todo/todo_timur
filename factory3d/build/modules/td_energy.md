# td_energy
Статус: DONE (юнит-DoD); стенд частично — ТК-01/05/11, ТБ 6/6, ТП 5/6 зелёные; ТК-02/07/08/09 FAIL (эмулятор/сценарий), ТК-03/04/06/10/12 skip
Тесты: Odoo 111/111 (/td_energy; чистая база и совместно с base/telemetry/telemetry_viewer/iot_sim, 2026-10-15); ruff check/format OK; ТК: прогнаны частично (TEST_REPORT.md, AC_COVERAGE.md)
Решений без заказчика: 18 (ниже)
Упирался в лимит: 0
Требует внимания человека: правки SPEC AC-32 (DEC-8), R-16 п.6 380 В (DEC-15), R-17 ключи (DEC-16), ТК-02 ожидание ≥30 мин; повтор ТП-01 после D-1; демо-копия (AC-13, AC-53, AC-88, ТК-03/04, UT на копии демо); td_genset (ТК-06); viewer (ТК-12, MAN AC-63/65/76); ТК-10 (90 мин); DEPLOY_TEST этап 1; дефекты iot_sim: PM-Q2 reg 3059 ≠ REST, BESS заряжается из сети (ТК-07/08/09); мост td_energy_mrp_workorder не нужен (V-16 на CE mrp)

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 952705a | install + test_data_sync 11/11 |
| W1 | принят | 34ae1b3 | /td_energy 38/38 |
| W2 | принят | 013a25f | /td_energy 64/64 |
| W3 | принят | c72ce00 (+merge) | /td_energy 91/91 |
| W4 | принят | 6c2b011 | /td_energy 73/73 |
| W5 | принят | ce2b4df | /td_energy 109/109 |
| W6 | принят (таймбокс менеджера) | f97a7f7 | стенд: ТК 01,05,11 зел.; 02,07,08,09 FAIL; 03,04,06,10,12 skip; ТБ 6/6; ТП 5/6 (ТП-01 FAIL→D-1) |
| DoD | принят | 5fa28a9 | 111/111; D-1 перф профиля (≤40 SQL/99 слотов), O-2 OperationalError пробрасывается, README/CHANGELOG, AC_COVERAGE 92/92 |

## Решения без заказчика
- DEC-1 (ENV-2): `mrp_workorder` (Enterprise) убран из `depends`; `time_ids` и V-16 — из CE `mrp`; что нет в CE — мост `td_energy_mrp_workorder` (не тестирован — нет Enterprise) — `__manifest__.py`
- DEC-2: `imbalance_pct` min_duration — Додаток C «2 год» vs C.2 `min_duration_s=3600` — взято 3600 (явная таблица C.2) — `data/energy_signals.csv`
- DEC-3: сигналы из Додатка C с пометкой sim_data — в CSV `origin=sim_data`, хук W1 создаёт их с `origin='catalog'` (SPEC §5.2 знает лишь catalog/module) — `tools/gen_energy_data.py`, `hooks.py`
- DEC-4: `max_kw` лічильника нет в CSV — хук считает: ввід/фідер ceil(rating_a·0,4·√3), споживач max(10, ceil(2·p_inst)), SUN 125, LUNA 200, TEDOM 900 (сверено с D.1, 0 расхождений) — `hooks.py`
- DEC-5: тариф без зон допустим, цена 0; покрытие суток проверяется только при наличии зон — `models/td_energy_tariff.py`
- DEC-6: `read_enabled` хук ставит только при первой установке; повторная привязка не трогает (консервативно) — `hooks.py`
- DEC-7: AC-03 «1201,0» в SPEC = сумма p_inst всех 49 потребителей, а не поддерева QF-1 (207,5); тест проверяет оба — `tests/test_node.py`
- DEC-8: AC-32 ждёт `warn` после первого часа при `min_duration_s=3600`; логика telemetry даёт `ok` после первого, `alarm` после второго — оставлена логика telemetry, тест под неё; SPEC AC-32 поправить — `tests/test_balance.py`
- DEC-9: R-04 п.3 — после превышения `max_wait_h` все последующие слоты `missing` (как в примере AC-22), а не только первые два — `models/td_energy_interval.py`
- DEC-10: баланс пропускает час, если у лічильника < 4 интервалов в часе (не только `missing`) — `tools/balance.py`
- DEC-11: положение ATyS по значению: 2 = pos_I (мережа), 3 = pos_II (генератор); АВР несвежий (>15 с) при живых вводах — отключение закрывается (R-14 п.7) с `return_s=0` — `models/td_energy_outage.py`
- DEC-12: сверка с мостом genset — только при `mode` auto/remote, событие не чаще раза в сутки; заявка на ATS-1 при FAIL START — штатным порогом сигнала — `models/td_energy_outage.py`
- DEC-13: R-08 п.1 кандидаты WO с `date_finished ≥ d0` дополнительно ограничены `date_start < end` (иначе тянутся все плановые); idle-строки — для всех прямых узлов с лічильником — `models/td_energy_alloc.py`
- DEC-14: без `td_machine_connect` R-08 п.2 (машинные интервалы) — обёртка `_f3d_machine_intervals`, контракт CM-03 с machine_connect не проверен — `models/td_energy_alloc.py`
- DEC-15: `consumers.i_now` считается при 380 В (R-16 п.6 говорит 400 В; AC-64 12,18 кВт / 0,84 = 22 А сходится только при 380) — правка SPEC — `tools/payload.py`
- DEC-16: `infra.totals` всегда содержит `shed_kw` (0 без отключения) и `bess_mode` — их требует AC-59, в списке R-17 их нет — `tools/payload.py`
- DEC-17: цена тарифа и `contract_kw` в payload читаются через sudo (только чтение; group_td_user тарифы не читает); настройки (res.config.settings) — только base.group_system, f3d_admin без system их не открывает (по §5 ARCH admin входит в system) — `tools/payload.py`, `models/res_config_settings.py`
- DEC-18: O-4 — `data_state='reset'` держится 24 ч после последнего сброса — по SPEC R-21, не дефект; стендовый ТК-02 падает из-за собственного сброса ТК-11b — `models/td_energy_meter.py`
