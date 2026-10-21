{
    "name": "CHP Factory Bridge",
    "summary": "Link of the cogeneration unit console with the factory: energy nodes, one Modbus source, control through Energy",
    "description": """
CHP Factory Bridge
==================

Bridge between the Cogeneration Unit Console (td_chp) and the Factory Energy suite (td_energy, td_energy_control).

Key features
------------

* All CHP commands (start, stop, emergency stop, reset, set-points) go through Energy control: one mechanism and
  one journal with the Energy console, class A/B confirmation, interlocks of the CHP console stay in force
* The CHP signals move to the existing Modbus source of the unit (one client per device)
* Energy groups give access to the CHP console, the menu lives under Energy -> Generation and reserve
* Link of the unit with the SLD nodes of the CHP and its feeder
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_chp", "td_energy", "td_energy_control"],
    "data": [
        "security/td_chp_factory3d_security.xml",
        "data/td_energy_command_kind_data.xml",
        "data/td_chp_factory3d_menu_hide.xml",
        "views/td_chp_unit_views.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init",
    "uninstall_hook": "uninstall_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
