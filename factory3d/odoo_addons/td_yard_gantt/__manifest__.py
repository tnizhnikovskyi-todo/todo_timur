# ruff: noqa: B018
{
    "name": "Yard Gantt",
    "summary": "Gantt view of gate bookings (requires web_gantt, Odoo Enterprise)",
    "description": """
Yard Gantt
==========

Adds a Gantt view to the gate bookings of Yard Management. It is installed automatically when Yard Management and the Enterprise web_gantt module are present.

Key features
------------

* Gantt view of gate bookings by gate and time

Requirements and notes
----------------------

* Requires Odoo Enterprise: depends on web_gantt.
""",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_yard", "web_gantt"],
    "images": ["static/description/banner.png"],
    "data": ["views/td_yard_booking_gantt.xml"],
    "auto_install": True,
    "installable": True,
    "application": False,
}
