{
    "name": "Завод 3D: верстати — міст mrp_workorder (Enterprise)",
    "summary": "Автостарт/зупинка з працівниками Enterprise mrp_workorder (start_employee/stop_employee)",
    "description": "Міст установлюється автоматично, коли в базі є Enterprise `mrp_workorder`. Ядро "
    "factory3d_machine_connect уже використовує employee_ids/start_employee/stop_employee через duck typing, "
    "тому міст мінімальний: лише залежності.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_machine_connect", "mrp_workorder"],
    "data": [],
    "auto_install": True,
    "installable": True,
    "application": False,
}
