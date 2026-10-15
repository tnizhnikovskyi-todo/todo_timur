# factory3d_machine_connect_mrp_workorder

Міст між `factory3d_machine_connect` і Enterprise `mrp_workorder` (DEC-1). Установлюється автоматично
(`auto_install`), коли в базі є обидва модулі.

Коду в мосту немає: ядро (`models/f3d_machine_wo.py`) уже використовує `mrp.workcenter.employee_ids`,
`mrp.workorder.employee_ids`, `start_employee(employee_id)` і `stop_employee(employee_ids)` через duck typing
(за наявності поля/методу). У CE 19.0 цих полів немає: ядро працює через `button_start()` та
`mrp.workorder.f3d_employee_id`.

Не тестується в середовищі без Enterprise.
