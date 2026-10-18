# DEPLOY_TEST — td_iot_sim 19.0.2.0.0 (SPEC §13.5)

Чек-лист розгортання. Виконано 15.10.2026 воркером W6 у середовищі без копії демо-бази (див. «Обмеження»);
результати прогону — у `TEST_REPORT.md`. Скрипти Odoo — `factory3d/tools/odoo/`, стенд — `factory3d/services/iot_sim/tests/stand/`.

## Обмеження прогону

* Демо-бази `odoo` (timur-o19demo) немає. Замість неї — шаблонна база `f3d_template` (Odoo 19.0 CE, 86 модулів, без
  `mrp_workorder`/`mrp_maintenance`/`web_gantt`), на якій модуль ставиться командою нижче. Тому числа кроків 1–2 —
  зі шаблонної бази, а не з демо (`maintenance.equipment`=210, `x_f3d_signal`=196, рівень 0 `196/196` — **не перевірені**).
* `genset_relay` не збирається: у гілці `origin/claude/dreamy-ramanujan-p2wlej` (`git ls-tree`, без checkout) є
  `smartgen/tools/fake_relay.py` (аргументи `--port/--token/--time-scale`, без `RELAY_PROFILE=d700`, без `RELAY_SIM_TOKEN`
  і без `/sim/v1/*` API-F-01…09), але немає каталогу `relay/` з Dockerfile, який очікує compose (`build: ${TD_GENSET_PATH}/relay`).
  Контракт CI-02/X-75 у td_genset не реалізований. Compose піднято без `genset_relay` (запасний режим §8.14).

## Кроки

| № | Крок (SPEC §13.5) | Виконано | Результат |
|---|---|---|---|
| 1 | Копія демо-бази → `odoo_test_sim`; зафіксувати `x_f3d_signal`=196, `x_f3d_reading`=N, `maintenance.equipment`=210, стан крона рівня 0 | **не виконано** (немає демо-бази) | Замість копії: `new_db.sh f3d_w6` з шаблона (≈ 0,3 с). `x_f3d_signal` у шаблоні немає записів, `maintenance.equipment` порожнє |
| 2 | Встановити `td_factory3d`, потім `td_iot_sim` 19.0.2.0.0 (`-u`); лог hook: `devices=276`, `signals=1168` (none 151), `level0 matched=196/196`, `scenarios=15`, `read_enabled` | **частково** | `F3D_TEST_INSTALL=td_iot_sim tools/odoo/new_db.sh f3d_w6 && … update.sh f3d_w6` → `installed`, 11 с, код Odoo 0. Фактично: `td.sim.device`=**230** (276 — для демо з 210 одиницями обладнання; у шаблоні їх немає), `td.sim.signal`=**1168**, `protocol=none`=**151**, `td.sim.scenario`=**15**. `level0 matched` — не перевірено (немає `x_f3d_signal`) |
| 3 | AC-25 кількості; меню «Завод 3D → Емулятор» → 7 пунктів; «Рівень 0» з успадкованими (AC-59) | **частково** | Кількості (1168/151/15) — так (RPC). Меню — покриває `test_panel.py::test_menu_under_base_root` (модульні тести 40/40); візуально в UI не перевірялось |
| 4 | Піднято compose `--profile dev`, налаштування, «Перевірити зв'язок» → онлайн; крон рівня 0 вимкнувся ≤ 1 хв | **виконано** | `tests/stand/up.sh` (iot_sim + mosquitto), Odoo `serve.sh f3d_w6 18069` з `ODOO_HTTP_INTERFACE=0.0.0.0`; параметри `td.iot_sim.*` через RPC; `action_check` → `state=online`, `level0_state=auto_off`, `cron_iot_sim.active=False` (`test_odoo_e2e::test_tk15…`) |
| 5 | ТК-15 повністю; ТК-13 стоп-крани | **виконано** (ТК-15 через RPC методів кнопок, не мишею) | `test_tk15_odoo_panel_end_to_end`, `test_rest.py::test_tk13_*` |
| 6 | `neutralize.sql` на другій копії → ТБ-10 | **виконано** | `test_odoo_security.py::test_tb10_neutralize_sql_on_copy` (база `f3d_w6n`) |
| 7 | Відкат: відновлення копії; порівняння `x_value` 196 записів | **не виконано** | Нема демо-бази; відкат — `drop_db.sh` + `new_db.sh` (перевірено: тести самі перестворюють `f3d_w6n`) |
| 8 | Результати в `TEST_REPORT.md` | **виконано** | `docs/modules/td_iot_sim/TEST_REPORT.md` |

## Відтворення

```bash
T=factory3d/tools/odoo
F3D_TEST_INSTALL=td_iot_sim $T/new_db.sh f3d_w6 && F3D_TEST_INSTALL=td_iot_sim $T/update.sh f3d_w6
ODOO_HTTP_INTERFACE=0.0.0.0 $T/serve.sh f3d_w6 18069            # Odoo має бути досяжним з контейнера (шлюз odoo_default)
cd factory3d/services/iot_sim && tests/stand/up.sh              # .env, mosquitto/passwd, мережа odoo_default, compose dev
.venv/bin/pytest -m stand tests/stand                           # ТК/ТБ/ТП (≈ 30 хв)
docker compose -f docker-compose.sim.yml --profile dev down
```

Для повного прогону на демо-базі: `STAND_ODOO_DB=<копія>` і `STAND_ODOO_URL`; сідінг РЦ/працівників у `test_odoo_e2e.py` ідемпотентний
(пропускається, якщо `mrp.workcenter` із кодом `SAW-1` уже є).
