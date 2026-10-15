# factory3d_machine_connect
Статус: IN_PROGRESS
Тесты: —, ТК: ждут W9
Решений без заказчика: 4 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 34039a1 | TestCommands 5/5 |
| W1 | в работе | | |
| W7 | в работе | | |

## Решения без заказчика
- DEC-1 (ENV-3): `mrp_workorder` (Enterprise) убран из `depends`; в CE 19.0 у `mrp.workorder`/`mrp.workcenter` нет
  `employee_ids`/`start_employee`/`stop_employee`. Ядро: собственное поле `mrp.workorder.f3d_employee_id` (оператор,
  проставляется при автостарте), старт/стоп — через `start_employee`/`stop_employee`, если метод есть (duck typing),
  иначе `button_start`/`button_finish`; разрешённые работники РЦ — `wc.employee_ids`, если поле есть, иначе пусто.
  Мост `factory3d_machine_connect_mrp_workorder` (auto_install) — минимальный, не тестирован (нет Enterprise).
  Тесты, требующие полей Enterprise, — с пропуском. — `models/mrp_workorder.py`, `models/f3d_machine_wo.py`
- DEC-2: AC-58 требует ключ запобіжника telemetry в тексте ошибки, а telemetry его не пишет — проверки module/source/signal
  продублированы в `_f3d_mc_create_command` до `create`; telemetry не менялся. — `models/f3d_command.py`
- DEC-3: Odoo 19 не принимает `target='inline'` у act_window — `action_f3d_mc_settings` без target. — `views/menus.xml`
- DEC-4: push-маршрут `mc_woodstore/status` → `f3d.gantry.job._f3d_apply_status` (SPEC не называет владельца). — `models/push_handler.py`
- Тесты гонять с `F3D_TEST_INSTALL=factory3d_machine_connect` (иначе ставится мост base_mrp_maintenance без Enterprise).
