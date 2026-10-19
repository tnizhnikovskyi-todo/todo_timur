# ruff: noqa: B018
{
    "name": "Factory 3D Core",
    "summary": "Base of the Factory 3D suite: scene codes, shop-floor zones, dock gates, equipment passports, access groups",
    "description": """
Factory 3D Core
===============

Foundation module of the Factory 3D suite for Odoo 19. It links standard Odoo records (locations, work centers, equipment, employees, vehicles) to objects of the 3D factory model and prepares the data that the other suite modules build on.

Key features
------------

* Scene-code mixin (td.scene.mixin): a stable code that ties an Odoo record to an object in the 3D model
* Shop-floor zones (td.zone) for grouping locations, work centers and equipment
* Warehouse gates modelled as docks, with trucks and vehicles on top of standard Fleet and Inventory
* Equipment passports on maintenance equipment
* Security groups Factory 3D User, Manager and Administrator used by all suite modules
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["stock", "stock_picking_batch", "stock_fleet", "fleet", "mrp", "maintenance", "hr", "web"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/td_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/td.equipment.passport.csv",
        "data/td.equipment.spec.csv",
        "data/td.equipment.source.csv",
        "data/td_zone_data.xml",
        "data/td_actions.xml",
        "views/stock_location_views.xml",
        "views/stock_picking_batch_views.xml",
        "views/stock_picking_views.xml",
        "views/td_zone_views.xml",
        "views/hr_employee_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/td_equipment_passport_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/td_menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": True,
}
