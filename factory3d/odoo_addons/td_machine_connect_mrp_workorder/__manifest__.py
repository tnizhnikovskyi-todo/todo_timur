{
    "name": "Machine Connect Workorder",
    "summary": "Auto start/stop with the employees of Enterprise mrp_workorder (start_employee/stop_employee)",
    "description": """
Machine Connect Workorder
=========================

Bridge between Machine Connect and the Odoo Enterprise Manufacturing Work Orders app (mrp_workorder). It is installed automatically when both are present.

The module contains no code of its own: the Machine Connect core already uses the work center employees through duck typing, so the bridge only declares the dependency.

Key features
------------

* Machine auto start and stop work with the employees of mrp_workorder
* Uses start_employee and stop_employee of Enterprise work orders

Requirements and notes
----------------------

* Requires Odoo Enterprise: depends on mrp_workorder.
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_machine_connect", "mrp_workorder"],
    "images": ["static/description/banner.png"],
    "data": [],
    "auto_install": True,
    "installable": True,
    "application": False,
}
