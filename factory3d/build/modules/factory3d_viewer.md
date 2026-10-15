# factory3d_viewer
Статус: IN_PROGRESS
Тесты: — , ТК: —
Решений без заказчика: 5 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| D (демо-шаблон) | в работе | — | — |
| W0 | принят | e59553e | TestInstall 6/6 (1 skip без демо) |
| W1a | принят | e3fcaea | /factory3d_viewer+/test_factory3d_viewer 60/60 (демо-тесты skip) |
| W1b-1 | в работе (M-01a…f) | — | — |
| W1b-2 | в работе (M-01g, h) | — | — |
| W2 | в работе | — | — |
| W3 | — | — | — |
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
