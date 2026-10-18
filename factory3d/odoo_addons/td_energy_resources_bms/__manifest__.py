{
    "name": "Енергоресурси — Будівля",
    "summary": "Міст td_energy_resources і td_bms: теплові точки й лічильники з BMS, KPI температури й рекуперації, "
    "три детектори резервів",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_energy_resources", "td_bms"],
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
