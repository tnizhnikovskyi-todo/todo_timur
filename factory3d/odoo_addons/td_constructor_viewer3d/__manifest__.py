{
    "name": "Завод 3D: розкладка конструктора у переглядачі",
    "summary": "Провайдер переглядача `layout`: опублікована версія конструктора поверх моделі (зсув, нове, прибране)",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_constructor", "factory3d_viewer"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "factory3d_constructor_viewer/static/src/layout/*.js",
        ],
        "factory3d_viewer.assets_kiosk": [
            "factory3d_constructor_viewer/static/src/layout/*.js",
        ],
        "web.assets_unit_tests": [
            "factory3d_constructor_viewer/static/tests/hoot/*",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
