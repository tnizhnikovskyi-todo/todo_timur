# Changelog — td_iot_sim

## 19.0.2.2.0 — цілі станів верстатів для демо «Живе виробництво» (контракт C-LP-01)

Оновлення: `-u` модуля. Схеми й дані не змінюються, міграційних скриптів немає.

- `td.sim.device._td_push_machine_targets(targets)` (`@api.model`): `POST <td.iot_sim.url>/api/v1/machines/targets` з токеном SIM API; `targets` — список
  `{"code": <td.machine.code>, "state": "working"|"idle"|"down", "reason", "until": <ISO UTC або datetime>}`; повертає `{"ok": n, "unknown": [коди]}`.
  Таймаут 5 с; без адреси, зі стоп-краном `write_enabled`, при помилці зв'язку, HTTP не 2xx чи не-JSON — `{"ok": 0, "unknown": []}` і `warning` у лог
  (без винятків, без токена в логу, без `td.sim.event` на кожен виклик). Викликає `td_live_production`; сервіс — `services/iot_sim` (API-50).
- Тест `tests/test_machine_targets.py` (підміна `requests.Session.request`): тіло, токен, URL, таймаут, `datetime` → ISO UTC, усі шляхи без винятків.

## 19.0.2.1.0 — сценарій S-24 «Пожежна евакуація (навчання)» (вау №8 «Евакуація в 3D»)

Оновлення: `-u` модуля. Схеми не змінюються, міграційних скриптів немає; пульт емулятора отримує 24-й сценарій.

- `data/td_sim_scenario_evac.xml` (окремий файл): `fire_evacuation`, група `safety`, 300 с; параметри `zone`, `detector`, `real`, `stuck`
  (застряглих, 0…3), `wrong_exit_pct`, `speed_mps`, `return_people`. Сервіс емулятора: `iot_sim/core/scenarios_evac.py`
  (каскад `fire_drill` + рух людей до виходів через СКУД, відкат блокувань після закінчення).
- Кнопка «Запустити тривогу з евакуацією» у навчальній тривозі `td_fire_safety` (`action_start_evac_sim`) створює запуск цього сценарію.

## 19.0.2.0.5 — меню «Емулятор» перенесено в «Дані»

Оновлення: `-u` модуля, сторінку браузера оновити. Схеми й дані не змінюються, міграційних скриптів немає.

- `menu_td_sim_root`: батько `td_factory3d.menu_td_data`, seq 40 (було: корінь, seq 90).
- `menu_iot_root` («Рівень 0 (без сервісу)») поставлено поруч у «Дані» (seq 45) і перейменовано «Емулятор: рівень 0 (без сервісу)»: під «Емулятор» він дав би 4-й рівень меню.

## 19.0.2.0.1
- S-2: `params` пристроїв за SPEC §5.2 — розкладка каналів ADAM (20 РЦ P-02 `di_run/di_fault/counter` з адрес каталогу, DUST-1,
  T1/T2 `rtd`, SPRINKLERS/AIR-RING `ai`, WATER, SPARK-1, SMOKE-CTRL/VENTS, GATE-W/E), `lsz` для 35 зон FA-*, `group/router`
  для 32 груп DALI LT-*. Було 8 з 276 (ACR, TURN-1, CAM).
- S-3: T1/T2 — unit 96 (раніше 1/2 з адреси PM5560 першого сигналу); 32 сигнали `infra/pv/PV-INV-n/*` прив'язані до
  похідних `PV-INV-n` (unit 60+n), а не до батька `PV-INV`; FL-6 і SMOKE-VENTS — пасивні (без сигналів, §5.2).
- `migrations/19.0.2.0.1/post-migrate.py` виконує `refresh_registry` (ідемпотентно, без дублікатів, ручні `params` лишаються).

## 19.0.2.0.0
- Фікс S-1: `migrations/19.0.2.0.0/post-migrate.py` виконує ті самі кроки, що й `post_init_hook` (Odoo не викликає його при `-u`),
  тож база з прототипом 19.0.1.0.0 отримує реєстр пристроїв і каталог сигналів; кроки ідемпотентні (без зайвих записів).
- Пульт емулятора (`td.sim.panel`), пристрої/сигнали (каталог 1168, з них 151 `protocol=none`), сценарії (15), запуски, події,
  майстри запуску сценарію і збою, API для сервісу (`/f3d/sim/health|devices|events`), крон рівня 0 з автоперемиканням,
  `neutralize.sql`, групи доступу `group_td_user/manager/admin`.
- Стенд (W6): перевірено ТК-01 (follow_odoo), ТК-10, ТК-15, ТБ-05/08/09/10, ТП-06 (частково) на шаблонній базі; див.
  `docs/modules/td_iot_sim/TEST_REPORT.md`, `DEPLOY_TEST.md`.
- Додано `static/description/icon.png`.
