# factory3d_viewer
Статус: IN_PROGRESS
Тесты: — , ТК: —
Решений без заказчика: 9 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| D (демо-шаблон) | принят | 1bdb774 | f3d_demo_tpl: 35 РЦ, 731 лок., WH/MO/00231, base+iot_sim |
| W0 | принят | e59553e | TestInstall 6/6 (1 skip без демо) |
| W1a | принят | e3fcaea | /factory3d_viewer+/test_factory3d_viewer 60/60 (демо-тесты skip) |
| W1b-1 | принят (на демо 9 FAIL → W1c) | 3c285ed | 111/111 пусто; демо 132/141 |
| W1c (демо-фиксы) | в работе | — | — |
| W3 | в работе | — | — |
| W1b-2 | принят (дельта chains ждёт W1b-1) | 4a7da35 | 84/84 (демо skip) |
| W2 | в работе | — | — |
| W4 | — | — | — |
| W5 | — | — | — |
| W6 | — | — | — |

## Решения без заказчика
- DEC-1: §13.0 требует копию демо-базы `odoo`, её в среде нет — шаблон `f3d_demo_tpl` собирается из `f3d_template`
  установкой `factory3d_base,factory3d_iot_sim` и заливкой `plant/odoo_push.py` по XML-RPC (скрипт
  `factory3d/tools/odoo/make_demo_tpl.sh`); прогоны с демо — `F3D_TEMPLATE_DB=f3d_demo_tpl run_tests.sh …`.
- DEC-2: порядок data в manifest — `security/kiosk_user.xml` после `data/actions.xml` (user_kiosk ссылается на action_f3d_viewer); строки access/правила/меню/кроны добавляются вместе с моделями воркеров. — `__manifest__.py`
- DEC-3: W1 разбит на W1a (M-01, tools, API, test_factory3d_viewer) и W1b (провайдеры M-01a…h) — объём не помещается в один контекст воркера; порядок слияния W1a → W1b → W3.
- DEC-4: `zz_fail` бросает ValueError только при context `zz_fail` или параметре `factory3d.test.zz_fail` — иначе ERROR в логе валит каждый прогон (run_tests strict). — `test_factory3d_viewer/models/providers.py`
- DEC-5: встроенные провайдеры — по файлу на провайдер `models/viewer_provider_<key>.py` (а не все в `viewer_provider.py`) — параллельная сборка W1b-1/W1b-2 без конфликтов.
- DEC-6: провайдеры chains/signals сами пишут свой статус в `meta.sections` (live/partial/missing/denied); `docks` пишет logistics, не chains. — `models/viewer_provider_chains.py`, `viewer_provider_signals.py`
- DEC-7: в шаблоне f3d_demo_tpl шаги push `modules,iot_module,signals` пропущены (Enterprise iot, zip-импорт); `x_f3d_signal` пуст, сигналы есть в `f3d_sim_signal` (1168) — AC-17 на демо проверяется моками; `plant/odoo_push.py` получил CE-правки (поля Enterprise через fields_get, lot_name при приёмке). — `factory3d/tools/odoo/make_demo_tpl.sh`
- DEC-8: ir.rule только чтение для group_f3d_user на maintenance.equipment/request с f3d_code (в Odoo 19 обычный пользователь видит лишь «свои» — противоречит §4.4). — `security/security.xml`
- DEC-9: `energy.profile_k` нет в model_static.json — запасная таблица PROFILE_KF из plant/energy.py; `next_maintenance` — ближайшая открытая preventive-заявка (в 19 нет next_action_date). — `models/viewer_provider_production.py`, `viewer_provider_maintenance.py`
