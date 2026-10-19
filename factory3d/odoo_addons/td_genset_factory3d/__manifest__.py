{
    "name": "Generator Factory Bridge",
    "summary": "Link of Generators with the factory model: telemetry, maintenance requests, 3D card, blackout balance",
    "description": """
Generator Factory Bridge
========================

Bridge between Generators and the Factory 3D suite: telemetry, energy, maintenance and a 3D card for every generator.

Key features
------------

* Generator signals in telemetry
* Maintenance requests for generators
* Generator card in the 3D viewer (optional)
* Power balance during a blackout in Factory Energy
""",
    "version": "19.0.1.1.0",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "category": "Manufacturing/Maintenance",
    "depends": ["td_genset", "td_factory3d", "td_telemetry", "td_energy"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/ir.model.access.csv",
        "security/td_genset_factory3d_security.xml",  # W1 (C): implied_ids «Енергетик» → td_genset.group_user
        "data/ir_config_parameter.xml",
        "data/td_genset_profile.xml",
        "data/td_genset_event_map.xml",
        "data/ir_cron.xml",
        "views/td_genset_link_views.xml",
        "views/td_genset_profile_views.xml",
        "views/td_genset_event_map_views.xml",
        "views/maintenance_views.xml",
        "views/res_config_settings_views.xml",
        "data/menu_hide.xml",  # W1 (C): приховання td_genset.menu_root
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "external_dependencies": {"python": []},
}
