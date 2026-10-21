{
    "name": "Fire Safety 3D Bridge",
    "summary": "Viewer providers: fire and evacuation sections; live evacuation in 3D",
    "description": """
Fire Safety 3D Bridge
=====================

Bridge between Fire Safety and the 3D viewer, installed automatically when both are present. It adds no models of its own.

Key features
------------

* Fire section in the 3D viewer
* Evacuation section in the 3D viewer
* Live evacuation in 3D: running arrows along the evacuation routes, highlighted exits, translucent smoke volumes, blocked ventilation and smoke hatches, people dots moving to the exits by access control passages, the "people in the building" plate and the stuck person highlighted
""",
    "version": "19.0.1.1.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_fire_safety", "td_viewer3d"],
    "images": ["static/description/banner.png"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "td_fire_safety_viewer3d/static/src/layer/**/*",
        ],
        "td_viewer3d.assets_kiosk": [
            "td_fire_safety_viewer3d/static/src/layer/**/*",
        ],
        "web.assets_unit_tests": [
            "td_fire_safety_viewer3d/static/tests/hoot/*",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
