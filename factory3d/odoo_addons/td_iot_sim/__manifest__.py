{
    "name": "Equipment Simulator",
    "version": "19.0.2.3.0",
    "summary": "Console of the factory equipment simulator: device registry, signal catalog, scenarios, level 0",
    "description": """
Equipment Simulator
===================

Control panel for the Factory 3D equipment simulator. It lets you demonstrate and test the suite without real hardware: simulated devices produce signals, and scenarios replay typical situations.

Key features
------------

* Registry of simulated devices and a catalog of signals
* Scenarios and runs with an event journal
* Simulator panel
* Level 0: simulated signals on work centers and maintenance equipment

Requirements and notes
----------------------

* The simulator service itself runs outside Odoo and is not part of this module.
* Intended for demos, training and testing, not for production data.
""",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "license": "LGPL-3",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "depends": ["td_factory3d"],
    "images": ["static/description/banner.png"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        # рівень 0 — успадковані файли data-модуля, ПЕРШИМИ і без змін (інакше Odoo видалить записи)
        "data/models.xml",
        "data/actions.xml",
        "views/views.xml",
        # новий модуль
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/level0.xml",
        "data/td_sim_scenario.xml",
        "data/td_sim_scenario_resources.xml",
        "data/td_sim_scenario_evac.xml",
        "data/ir_cron.xml",
        "views/sim_panel_views.xml",
        "views/sim_device_views.xml",
        "views/sim_signal_views.xml",
        "views/sim_scenario_views.xml",
        "views/sim_run_views.xml",
        "views/sim_event_views.xml",
        "views/wizard_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
