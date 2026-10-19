{
    "name": "Energy Resources BMS",
    "summary": "Bridge of Energy Resources and Building Management: heat points and meters from BMS, KPIs, three detectors",
    "description": """
Energy Resources BMS
====================

Bridge between Energy Resources and Building Management, installed automatically when both are present.

Key features
------------

* Heat points and meters created from the building management system
* Temperature and heat-recovery KPIs
* Three savings-reserve detectors
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_energy_resources", "td_bms"],
    "images": ["static/description/banner.png"],
    "data": [
        "data/opportunity_rules.xml",  # W3-B: preheat_early, ahu_recuperation, dock_gates
    ],
    "assets": {
        "web.assets_backend": [
            "td_energy_resources_bms/static/src/**/*",  # W3-B: UI-B1 (heat_note.xml)
        ],
    },
    "post_init_hook": "post_init_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
