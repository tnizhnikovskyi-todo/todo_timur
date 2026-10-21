{
    "name": "Demo: Live Production",
    "summary": "Demo stand only: daily orders, dispatcher of work orders, downtimes and shipping in real time",
    "description": """
Demo: Live Production
=====================

Makes the demo plant live. Not part of the product: install it only on the demo stand.

Key features
------------

* Generates a day of work from the demo templates: sales orders, manufacturing orders, a work order schedule with finite work center capacity and a deliberately overloaded section
* Dispatcher every minute: starts and finishes work orders, adds random downtimes with reasons, closes manufacturing orders and ships orders
* Catches up the past: finishes old manufacturing orders by the dates of their plans, deletes nothing
* Demo company preparation: name, currency, component costs, zonal tariff, what-if scenarios
* Sends target machine states to the emulator when the IoT emulator is installed

Requirements and notes
----------------------

* Compatible with the automatic start and stop of Machine Connect: starting and finishing are idempotent.
* Cron jobs are disabled by default; the button "Start live production" in Settings enables them.
""",
    "version": "19.0.1.0.3",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["mrp", "sale_mrp", "td_factory3d", "td_machine_connect"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/td_live_day_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
