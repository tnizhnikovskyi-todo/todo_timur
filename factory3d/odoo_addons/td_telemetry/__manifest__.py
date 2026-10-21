{
    "name": "Factory 3D Telemetry",
    "summary": "Data acquisition backbone: sources, signals and readings from equipment, thresholds to maintenance requests",
    "description": """
Factory 3D Telemetry
====================

Common data-collection backbone of the Factory 3D suite. Equipment signals are received through an HTTP API, stored as readings, and used for alarms and maintenance planning.

Key features
------------

* Collectors, sources, signals, readings and hourly aggregates
* HTTP push API (/f3d/telemetry/*) with rate limits and retention settings
* Thresholds that create maintenance requests
* Meter-based maintenance (preventive requests by counter value)
* Command log for writing to devices, guarded by safety switches that are off by default

Requirements and notes
----------------------

* Readings are delivered by a separate collector service (Modbus TCP, MQTT, HTTP push and BACnet/IP plugins). The collector is not part of this module and runs on the customer site.
* Reading and writing are controlled by system parameters; writing to devices is disabled by default.
""",
    "version": "19.0.1.1.2",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "maintenance", "mail", "web"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "data/td_source_data.xml",
        "data/td_actions.xml",
        "wizard/collector_token_wizard_views.xml",
        "views/td_collector_views.xml",
        "views/td_source_views.xml",
        "views/td_signal_views.xml",
        "views/td_reading_views.xml",
        "views/td_reading_hour_views.xml",
        "views/td_command_views.xml",
        "views/td_push_event_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/maintenance_request_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
