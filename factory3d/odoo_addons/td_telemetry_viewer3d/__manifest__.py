{
    "name": "Телеметрія — Переглядач",
    "summary": "Провайдер переглядача: значення сигналів телеметрії у payload (CT-07)",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    # td_viewer3d у каталозі ще немає: провайдер — duck typing за ARCHITECTURE §6.7; залежність
    # на td_viewer3d додати, коли модуль з'явиться (SPEC §0.2).
    "depends": ["td_factory3d", "td_telemetry"],
    "data": [],
    "installable": True,
    "auto_install": True,
    "application": False,
}
