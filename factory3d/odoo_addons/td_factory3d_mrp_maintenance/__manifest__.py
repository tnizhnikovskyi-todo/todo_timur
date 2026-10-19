# ruff: noqa: B018
{
    "name": "MRP Maintenance Bridge",
    "summary": "Fills maintenance.equipment.workcenter_id by matching td_code with the work center",
    "description": """
MRP Maintenance Bridge
======================

Bridge between Factory 3D Core and the Odoo Enterprise mrp_maintenance module, installed automatically when both are present.

On installation it fills empty work center links of maintenance equipment by matching the td_code of the equipment with the td_code of the work center.

Key features
------------

* Fills maintenance.equipment.workcenter_id by matching td_code

Requirements and notes
----------------------

* Requires Odoo Enterprise: depends on mrp_maintenance.
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "mrp_maintenance"],
    "images": ["static/description/banner.png"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
