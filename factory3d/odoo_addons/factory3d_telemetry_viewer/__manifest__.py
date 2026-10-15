{
    "name": "Завод 3D: телеметрія у переглядачі",
    "summary": "Провайдер переглядача: значення сигналів телеметрії у payload (CT-07)",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    # factory3d_viewer у каталозі ще немає: провайдер — duck typing за ARCHITECTURE §6.7; залежність
    # на factory3d_viewer додати, коли модуль з'явиться (SPEC §0.2).
    "depends": ["factory3d_base", "factory3d_telemetry"],
    "data": [],
    "installable": True,
    "auto_install": True,
    "application": False,
}
