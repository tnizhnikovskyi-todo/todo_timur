{
    "name": "Енергетика — Переглядач 3D",
    "summary": "Шар «Енергетика в 3D»: розфарбування вузлів за станом, маркери тривог, картка вузла, перехід з Пульта",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_energy", "td_viewer3d"],
    "data": [
        "views/td_energy_viewer3d_views.xml",  # D: V-46, V-47
    ],
    "assets": {
        "web.assets_backend": [
            "td_energy_viewer3d/static/src/layer/**/*",
        ],
        "td_viewer3d.assets_kiosk": [
            "td_energy_viewer3d/static/src/layer/**/*",
        ],
        "web.assets_unit_tests": [
            "td_energy_viewer3d/static/tests/hoot/*",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
