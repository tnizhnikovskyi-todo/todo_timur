# factory3d_viewer
Статус: IN_PROGRESS
Тесты: — , ТК: —
Решений без заказчика: 2 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| D (демо-шаблон) | в работе | — | — |
| W0 | принят | e59553e | TestInstall 6/6 (1 skip без демо) |
| W1 | — | — | — |
| W2 | — | — | — |
| W3 | — | — | — |
| W4 | — | — | — |
| W5 | — | — | — |
| W6 | — | — | — |

## Решения без заказчика
- DEC-1: §13.0 требует копию демо-базы `odoo`, её в среде нет — шаблон `f3d_demo_tpl` собирается из `f3d_template`
  установкой `factory3d_base,factory3d_iot_sim` и заливкой `plant/odoo_push.py` по XML-RPC (скрипт
  `factory3d/tools/odoo/make_demo_tpl.sh`); прогоны с демо — `F3D_TEMPLATE_DB=f3d_demo_tpl run_tests.sh …`.
- DEC-2: порядок data в manifest — `security/kiosk_user.xml` после `data/actions.xml` (user_kiosk ссылается на action_f3d_viewer); строки access/правила/меню/кроны добавляются вместе с моделями воркеров. — `__manifest__.py`
