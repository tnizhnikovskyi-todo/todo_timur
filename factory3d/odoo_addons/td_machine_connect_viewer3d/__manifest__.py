{
    "name": "Machine Connect 3D",
    "summary": "Machine Connect in 3D: downtime cost coloring and the plant bottleneck (queue stack and card block)",
    "description": """
Machine Connect 3D
==================

Adds a color mode to the 3D viewer that paints machines by the cost of their downtime for the current month. It creates no data of its own; removing the module removes the mode.

Key features
------------

* "Downtime, cost" color mode next to the OEE mode
* Legend with the largest monthly loss
* Visible only to Factory 3D managers and hidden on shop-floor kiosk screens
* Plant bottleneck: a red stack of waiting orders in front of the constraining section (height by queue length) and a metrics block in the machine card
""",
    "version": "19.0.1.1.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_machine_connect", "td_viewer3d"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "td_machine_connect_viewer3d/static/src/layer/**/*",
        ],
        "td_viewer3d.assets_kiosk": [
            "td_machine_connect_viewer3d/static/src/layer/**/*",
        ],
        "web.assets_unit_tests": [
            "td_machine_connect_viewer3d/static/tests/hoot/*",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
