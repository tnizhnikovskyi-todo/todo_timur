# ruff: noqa: B018
{
    "name": "Завод 3D: міст base ↔ mrp_maintenance",
    "summary": "Заповнює maintenance.equipment.workcenter_id за збігом f3d_code з робочим центром",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_base", "mrp_maintenance"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
