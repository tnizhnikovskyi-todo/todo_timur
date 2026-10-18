{
    "name": "Конструктор — Переглядач",
    "summary": "Провайдер переглядача `layout`: опублікована версія конструктора поверх моделі (зсув, нове, прибране)",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_constructor", "td_viewer3d"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "td_constructor_viewer3d/static/src/layout/*.js",
        ],
        "td_viewer3d.assets_kiosk": [
            "td_constructor_viewer3d/static/src/layout/*.js",
        ],
        "web.assets_unit_tests": [
            "td_constructor_viewer3d/static/tests/hoot/*",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
