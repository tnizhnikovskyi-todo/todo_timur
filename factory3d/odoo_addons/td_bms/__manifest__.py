# ruff: noqa: B018
{
    "name": "Building Management",
    "summary": "Lighting groups by norms, DALI/HelvarNet, rooftop units and boiler room (BACnet), heat balance, deviations",
    "description": """
Building Management
===================

Building management for the plant: lighting, ventilation and heating, with a heat balance and a deviation journal that creates maintenance requests.

Key features
------------

* Lighting norms, panels and lighting groups (DALI, HelvarNet)
* Ventilation and heating units and the boiler room (BACnet)
* Heat balance of the workshop
* Deviation journal; deviations create maintenance requests
* Building overview and 3D viewer providers for lighting and ventilation

Requirements and notes
----------------------

* Device data comes from the Factory 3D collector service (HelvarNet and BACnet plugins), which is not part of this module.
* Writing to building systems is disabled by default.
""",
    "version": "19.0.1.0.4",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_telemetry", "web"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/td_bms_light_norm_data.xml",
        "data/td_bms_light_scene_data.xml",
        "data/td_bms_source_data.xml",
        "data/td_bms_light_data.xml",
        "data/td_bms_hvac_data.xml",
        "views/td_bms_light_norm_views.xml",
        "views/td_bms_light_panel_views.xml",
        "views/td_bms_light_group_views.xml",
        "views/td_bms_light_scene_views.xml",
        "views/td_bms_hvac_unit_views.xml",
        "views/td_bms_heat_balance_views.xml",
        "views/td_bms_deviation_views.xml",
        "views/td_zone_views.xml",
        "views/maintenance_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/command_wizard_views.xml",
        "data/td_bms_actions.xml",
        "data/ir_cron.xml",
        "views/td_bms_overview_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_bms/static/src/overview/overview.js",
            "td_bms/static/src/overview/overview.xml",
            "td_bms/static/src/overview/overview.scss",
        ],
        "web.assets_unit_tests": ["td_bms/static/tests/overview.test.js"],
    },
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
    "auto_install": False,
}
