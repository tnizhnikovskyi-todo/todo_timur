{
    "name": "Constructor 3D Bridge",
    "summary": "Viewer provider layout: shows the layout published in the Constructor on top of the 3D model",
    "description": """
Constructor 3D Bridge
=====================

Bridge between Factory 3D Constructor and Factory 3D Viewer, installed automatically when both are present.

Key features
------------

* The viewer shows the layout published in the Constructor
* Moved, added and removed objects are highlighted relative to the model
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_constructor", "td_viewer3d"],
    "images": ["static/description/banner.png"],
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
