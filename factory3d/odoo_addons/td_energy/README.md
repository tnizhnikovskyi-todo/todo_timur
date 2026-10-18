# td_energy — Завод 3D: енергетика

Схема електропостачання, лічильники PM5560, 15-хв профіль, баланс, кВт·год і вартість на завдання й МО, СЕС,
накопичувач, КГУ, АВР, тарифи. Специфікація — `docs/modules/td_energy/SPEC.md`, архітектура — `ARCHITECTURE.md`
там само, покриття AC — `AC_COVERAGE.md`, результати стенда — `TEST_REPORT.md`.

## Встановлення
- Залежності (`__manifest__.py`): `td_telemetry`, `mrp_account`, `analytic`, `web_hierarchy`.
  `mrp_workorder` (Enterprise) не вимагається — ENV-2 (`factory3d/build/ENV_DECISIONS.md`); поля й дії на робочих
  операціях додаються лише якщо модель `mrp.workorder` доступна.
- Хук після встановлення прив'язує вузли до обладнання/РЦ демо-бази і пише звіт у `td.energy.install_report`.
- Дані `data/energy_*.csv` генеруються з макета (`python3 odoo_addons/td_energy/tools/gen_energy_data.py --root .`
  з каталогу `factory3d/`), Odoo їх напряму не вантажить — читає хук.
- На проді одразу після встановлення `td.energy.read_enabled = False`; вмикати після перевірки адрес джерел.

## Параметри `td.energy.*` (`data/ir_config_parameter.xml`; Налаштування → Завод 3D → Енергетика)
| Параметр | Значення | Призначення |
|---|---|---|
| `read_enabled` | True (тест) / False (прод) | стоп-кран: опитування джерел і крони |
| `write_enabled` | False | запис у пристрої — у v1 недоступний (A-15) |
| `costing_enabled` | True | енергія в `extra_cost` при закритті МО (потрібні AVCO/FIFO у категорії) |
| `analytic_enabled` | True | аналітичні рядки за аналітикою РЦ |
| `balance_tol_pct` / `balance_tol_kwh` | 3 / 2.0 | допуск балансу за годину |
| `gap_alarm_min` / `gap_max_s` | 60 / — | подія про відсутність даних лічильника; максимальний розрив показань |
| `max_wait_h` / `settle_s` | 6 / 120 | коли інтервал без даних стає `missing`; затримка побудови слота |
| `reset_tol_kwh` | — | правдоподібність показника після скидання лічильника |
| `keep_interval_days` / `keep_event_days` | 400 / 90 | ротація інтервалів і подій |
| `shift_calendar_id` | id календаря зміни | початок зміни для `kwh_shift` |
| `typical_days` | 20 | типовий день — середнє за N робочих днів |
| `ats_fail_start_s` / `ats_fresh_factor` | 35 / — | FAIL START (варіант B); свіжість сигналів АВР |
| `peak_shave_kw` | 600 | текст картки BESS |
| `alloc_close_h` | — | вікно закриття розподілу |
| `install_report` | службовий | звіт хука встановлення |

## Коротка інструкція
1. Лічильники: Енергетика → Лічильники, колонка «Стан» (`ok`/`gap`/`stale`/`reset`); «немає даних 60 хв» — у Подіях.
2. МО: вкладка «Енергія» (кВт·год прямі й спільні, якість, вартість — лише бухгалтер/керівник); кнопка «Розподіл».
3. Тариф: Енергетика → Налаштування → Тарифи; попередній закрити датою «по»; майстер «Перерахувати» — для
   незафіксованих МО.
4. Баланс: Енергетика → Баланс; відхилення довше двох годин → заявка ТО «Небаланс обліку».
5. Відключення мережі: Енергетика → Відключення (час переключення АВР, скинуте навантаження, FAIL START).
Докладно — `docs/modules/td_energy/ARCHITECTURE.md` §4.

## Стоп-крани і neutralize
- `read_enabled = False` — джерела енергетики не опитуються, крони нічого не роблять.
- `costing_enabled = False` — енергія не потрапляє в `extra_cost`.
- `write_enabled` у v1 увімкнути неможливо.
- `data/neutralize.sql` (копія проду): `read_enabled`/`write_enabled`/`costing_enabled` → False, крони модуля вимкнені,
  джерела енергетики неактивні; застосовується разом із neutralize `td_telemetry`.

## Тести
- Юніт: `F3D_TEST_INSTALL=td_energy factory3d/tools/odoo/run_tests.sh <db> /td_energy`.
- Стенд (емулятор `td_iot_sim` + колектор): `tests/stand/` (pytest, `pytest.ini`, `reset_stand.sh`),
  сценарії ТК/ТБ/ТП — `docs/modules/td_energy/DEPLOY_TEST.md`.
- Перф (ТП-01): `tests/stand/test_tp.py`; юніт-захист від N+1 — `test_interval.py::test_build_query_count`.
