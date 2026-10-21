{
    "name": "Energy 3D Layer",
    "summary": "Energy in 3D layer: node coloring by state, alarm markers, node card, jump from the console",
    "description": """
Energy 3D Layer
===============

Adds an Energy layer to the 3D viewer. It creates no data of its own; removing the module removes the layer.

Key features
------------

* Nodes of the power scheme colored by state
* Alarm markers in the scene
* Node card with live values
* Jump from the Energy console to the 3D scene
* Running energy counter (UAH and kWh since midnight) in the shift flow strip, 3D power coloring that follows the shift playback time, an Energy slide for the briefing wall
""",
    "version": "19.0.1.1.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_energy", "td_viewer3d"],
    "images": ["static/description/banner.png"],
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
