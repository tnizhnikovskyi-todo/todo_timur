# Part of td_genset (ToDo). See README.md.
{
    "name": "Generators",
    "summary": "Monitoring and control of SmartGen HGM6120N generators through a relay",
    "description": """
Generators
==========

Monitoring and control of generator sets with the SmartGen HGM6120N controller through a relay service. Current state, event and alarm journals, a control console with command confirmation, fuel accounting and maintenance by engine hours.

Key features
------------

* Current state and a journal of readings
* Events and alarms with escalation
* Control console with confirmation of commands by snapshots, schedule, timer and test
* Fuel: canisters, refuelling, sensor calibration
* Maintenance by engine hours through the standard Maintenance app

Requirements and notes
----------------------

* Requires a SmartGen relay service reachable over HTTP. The relay is operated separately and is not part of this module.
* The relay address and token are entered by an administrator and removed when the module is uninstalled.
""",
    "version": "19.0.1.0.1",
    "category": "Generators",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "OPL-1",
    "depends": ["base", "mail", "bus", "web", "maintenance"],
    "images": ["static/description/banner.png"],
    "external_dependencies": {"python": ["requests", "pytz"]},
    "data": [
        # security
        "security/groups.xml",
        "security/ir.model.access.csv",
        # data
        "data/ir_sequence.xml",
        "data/mail_data.xml",
        "data/maintenance_data.xml",
        "data/controller_model_data.xml",
        "data/config_data.xml",
        "data/ir_cron.xml",
        "data/ir_exports.xml",
        # wizards (before the views that reference their actions)
        "wizard/command_wizard_views.xml",
        "wizard/timer_wizard_views.xml",
        "wizard/refuel_wizard_views.xml",
        "wizard/fuel_receipt_wizard_views.xml",
        # views
        "views/genset_views.xml",
        "views/genset_reading_views.xml",
        "views/genset_event_views.xml",
        "views/genset_alarm_views.xml",
        "views/genset_command_views.xml",
        "views/genset_schedule_views.xml",
        "views/genset_config_views.xml",
        "views/genset_fuel_views.xml",
        "views/maintenance_views.xml",
        "views/res_config_settings_views.xml",
        "views/analytics_actions.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_genset/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
    # токен і адреса ретранслятора (ir.config_parameter без xml id) видаляються при деінсталяції;
    # копія бази (odoo-bin neutralize / --neutralize) — data/neutralize.sql: стоп-крани, без токена, cron вимкнено
    "uninstall_hook": "uninstall_hook",
}
