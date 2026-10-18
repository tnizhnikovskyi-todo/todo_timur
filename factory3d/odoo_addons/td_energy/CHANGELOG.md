# Changelog

## 19.0.1.1.0 — W1 «Енергетика»: Пульт, картка вузла, тривоги, планові відключення (W1-A, бекенд)
- `td.energy.event`: `title/detail/state` (R-24), життєвий цикл `active → acked → resolved` (`action_ack|take|release|resolve`,
  `_td_auto_resolve`: лічильник, поріг, PFC, баланс, trip), події `pfc` (ступінь не вмикається, cos φ секції) і `trip`.
- `td.energy.node`: геометрія схеми `sld_*` (+ `data/sld_layout.csv`, 21 вузол), `sld_state` (R-26), захист, ступені PFC (35 × 10, D-09),
  `action_open_card`; `td.energy.meter`: повірка (`next_verification`, `_cron_verification`); `td.energy.interval`: `is_backfill`,
  `_td_backfill` (R-36: 90 діб ≈ 66 с, 578 880 рядків).
- Нові моделі: `td.energy.outage.plan` (R-31), `td.energy.advice` (слот, реєстр `_td_advice_rule_*`), `td.energy.ticket.wizard`,
  `td.energy.dashboard` (API-05…07, 12, 13; хуки для моста), `tools/bus.py` (канал `td_energy`, без даних, throttle 5 с).
- Сигнали: +15 (QS, PFC, секційні cos φ/P/Q) і джерело `MB-U73-SWB-CTRL`; пороги cos φ 0,92/0,90 (E-10); група «головний енергетик».
- Міграція `19.0.1.1.0`: сигнали, пороги, схема, R-24 для наявних подій (ідемпотентна). 3 нові крони; `neutralize.sql` без змін по суті.
- Існуючі `_f3d_*`-методи не перейменовано (RENAME.md §6); SPEC-імена `_td_log`, `action_td_show` — аліаси.

## Unreleased
- W4 (C-02): хук `td.energy.dashboard._td_report_action()` (у базі `None`; значення задає `td_energy_analytics`); `get_pult`:
  `meta.report_action` і `capabilities.report = bool(хук)`; кнопка «Звіт за зміну» Пульту відкриває `meta.report_action`
  (раніше — `capabilities.report=False` і жорсткий xml-id `td_energy.action_td_energy_report`). Без модуля аналітики кнопки немає.
- E-4: `kwh_shift` (R-11) для лічильника, що звітує менше за зміну (новий вузол, свіжа установка, стенд): раніше без показання
  на `shift_start` `delta` повертав `missing` і сигнал лишався порожнім до наступної зміни. Тепер — енергія від першого показання
  зміни з якістю `uncertain`; з показанням на початок зміни — як і раніше (`good`, AC-83).

## 19.0.1.0.0
- W0: каркас модуля — маніфест (без `mrp_workorder`, ENV-2), групи й імплікації (SPEC §4.2), параметри `td.energy.*`
  (§5.1), меню «Енергетика», `neutralize.sql`, генератор і CSV-дані `data/energy_*.csv` (вузли 123, джерела 68,
  сигнали 297, лічильники 67, пули 5), тести узгодженості CSV ↔ макет.
- Моделі, представлення, крони, хуки — додаються наступними воркерами (див. коментарі в `__manifest__.py`).
- Можливості: вузли/лічильники/джерела/пули; безперервний лічильник Ec(t) зі скиданнями; 15-хв профіль і
  тарифні зони; живі тотали, похідні, баланс; події (пороги, PFC, пік, аварія верстата); розподіл кВт·год на МО/завдання
  і собівартість (`extra_cost`, аналітика); АВР, відключення, острівний режим; payload переглядача; групи доступу;
  ротація; стоп-крани `read_enabled`/`costing_enabled`; neutralize; хук встановлення.
- Fix D-1: побудова 15-хв профілю — тариф і зони шукаються один раз на місцеву добу, а не на кожен слот
  (було ≈ 26 000 SQL на прогін); тест `test_build_query_count`.
- Fix O-2: `_f3d_on_ingest` — помилки БД рівня транзакції (`OperationalError`, serialization failure) не ковтаються,
  а пробрасуються для ретраю приймання; інші помилки журналу подій — лише лог у savepoint. Тест
  `test_on_ingest_db_error_propagates`.
- O-4: `data_state='reset'` тримається 24 год після скидання за R-21 (SPEC) — поведінка за специфікацією.
