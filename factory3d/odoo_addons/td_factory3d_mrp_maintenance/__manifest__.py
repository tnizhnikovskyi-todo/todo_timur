# ruff: noqa: B018
{
    "name": "Завод 3D — mrp_maintenance",
    "summary": "Заповнює maintenance.equipment.workcenter_id за збігом td_code з робочим центром",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "mrp_maintenance"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
