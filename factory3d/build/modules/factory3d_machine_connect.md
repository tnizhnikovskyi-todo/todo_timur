# factory3d_machine_connect
Статус: IN_PROGRESS
Тесты: —, ТК: ждут W9
Решений без заказчика: 1 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | в работе | | |

## Решения без заказчика
- DEC-1 (ENV-3): `mrp_workorder` (Enterprise) убран из `depends`; в CE 19.0 у `mrp.workorder`/`mrp.workcenter` нет
  `employee_ids`/`start_employee`/`stop_employee`. Ядро: собственное поле `mrp.workorder.f3d_employee_id` (оператор,
  проставляется при автостарте), старт/стоп — через `start_employee`/`stop_employee`, если метод есть (duck typing),
  иначе `button_start`/`button_finish`; разрешённые работники РЦ — `wc.employee_ids`, если поле есть, иначе пусто.
  Мост `factory3d_machine_connect_mrp_workorder` (auto_install) — минимальный, не тестирован (нет Enterprise).
  Тесты, требующие полей Enterprise, — с пропуском. — `models/mrp_workorder.py`, `models/f3d_machine_wo.py`
