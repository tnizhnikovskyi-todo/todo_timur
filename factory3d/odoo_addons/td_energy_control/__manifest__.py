{
    "name": "Energy Control",
    "summary": "Automation scenarios, load-shedding priorities, manual commands with interlocks and confirmation, schedule, journal",
    "description": """
Energy Control
==============

Control of power supply and energy consumption of the plant: automation scenarios, load-shedding priorities and manual commands, each with interlocks, confirmation and a journal.

Key features
------------

* Six automation scenarios executed by the collector
* Load-shedding priorities
* Manual commands of classes A and B with interlocks, confirmation and, where required, a second confirmation
* Schedule, journal and cancellation of commands

Requirements and notes
----------------------

* Scenarios are executed by the Factory 3D collector service, which is not part of this module.
* The module does not control safety systems (fire automation, emergency lighting, protection of people).
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_energy", "td_telemetry", "td_bms"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/td_energy_control_security.xml",  # A
        "security/ir.model.access.csv",  # A
        "data/ir_config_parameter.xml",  # A
        "data/td_energy_interlock_data.xml",  # A
        "data/td_energy_command_kind_data.xml",  # A
        "data/td_energy_scenario_data.xml",  # A
        "data/td_energy_shed_item_data.xml",  # A
        "data/ir_cron.xml",  # A
        "views/td_energy_scenario_views.xml",  # B: V-37
        "views/td_energy_shed_item_views.xml",  # B: V-38
        "views/td_energy_command_kind_views.xml",  # B: V-39
        "views/td_energy_interlock_views.xml",  # B: V-40
        "views/td_energy_action_views.xml",  # B: V-41
        "views/td_energy_schedule_slot_views.xml",  # B: V-42
        "views/td_command_views.xml",  # B: V-43
        "views/res_config_settings_views.xml",  # B: V-44
        "views/td_energy_control_views.xml",  # B: V-35, V-36
        "views/menus.xml",  # B: V-45 (останнім)
    ],
    "demo": [
        "demo/ir_config_parameter_demo.xml",  # A: D-46 — на демо-даних дистанційне перемикання увімкнено
    ],
    "assets": {
        "web.assets_backend": [
            "td_energy_control/static/src/control/**/*",  # B: UI-12…UI-20
            "td_energy_control/static/src/handlers/**/*",  # B: UI-21, UI-22, UI-28
        ],
        "web.assets_unit_tests": [
            "td_energy_control/static/tests/**/*.js",  # B
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "auto_install": False,
    "application": False,
}
