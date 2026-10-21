{
    "name": "Cogeneration Unit Console",
    "summary": "Operator console for a gas cogeneration unit (CHP): live state, 3D model, interlocks, commands, journal",
    "description": """
Cogeneration Unit Console
=========================

Operator console for a gas cogeneration unit (CHP, TEDOM Quanto D800 type): live readings from the Modbus controller
through the telemetry collector, a 3D model and a mimic diagram, interlocks, commands with confirmation, event journal
and maintenance by engine hours.

Key features
------------

* 230 signals of the unit as editable telemetry signals (register map is a typical assumption, adjusted per controller)
* Start, stop, emergency stop, reset and set-point commands with interlocks, two-person confirmation and a journal
* Alarm and event journal with acknowledgement, maintenance requests by engine hours
* Operator console: 3D model, mimic diagram, KPI tiles, cylinder diagnostics

Requirements and notes
----------------------

* Needs the telemetry platform (td_telemetry) and the Factory 3D base (td_factory3d).
* Write to the controller is off by default (td.chp.write_enabled); read can be stopped with td.chp.read_enabled.
* The module does not replace the controller's own protections.
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "td_telemetry", "maintenance", "mail", "bus", "web"],
    "data": [
        "security/td_chp_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/td_chp_unit.xml",
        "data/td_chp_maintenance_rule.xml",
        "data/ir_cron.xml",
        "views/td_chp_actions.xml",
        "views/td_chp_unit_views.xml",
        "views/td_chp_event_views.xml",
        "views/td_chp_command_views.xml",
        "views/td_chp_maintenance_views.xml",
        "views/td_chp_signal_views.xml",
        "views/res_config_settings_views.xml",
        "views/td_chp_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_chp/static/src/pult/**/*",
        ],
        "web.assets_unit_tests": [
            "td_chp/static/tests/hoot/**/*",
        ],
    },
    "post_init_hook": "post_init",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "auto_install": False,
    "application": True,
}
