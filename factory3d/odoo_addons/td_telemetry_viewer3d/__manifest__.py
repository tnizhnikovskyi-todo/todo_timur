{
    "name": "Telemetry 3D Bridge",
    "summary": "Viewer provider: telemetry signal values in the 3D viewer payload",
    "description": """
Telemetry 3D Bridge
===================

Bridge between Factory 3D Telemetry and the 3D viewer, installed automatically when both are present. It adds no models, data or menus.

Key features
------------

* Adds the values of telemetry signals to the viewer payload
* Signal values become visible on the 3D objects they belong to
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    # td_viewer3d у каталозі ще немає: провайдер — duck typing за ARCHITECTURE §6.7; залежність
    # на td_viewer3d додати, коли модуль з'явиться (SPEC §0.2).
    "depends": ["td_factory3d", "td_telemetry"],
    "images": ["static/description/banner.png"],
    "data": [],
    "installable": True,
    "auto_install": True,
    "application": False,
}
