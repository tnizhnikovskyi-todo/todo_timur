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
    "data": [],
    "assets": {
        "web.assets_backend": [
            "td_chp/static/src/pult/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
}
