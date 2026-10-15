# ruff: noqa: B018
{
    "name": "Завод 3D: будівля (освітлення, вентиляція, опалення)",
    "summary": "Групи освітлення за нормами, DALI/HelvarNet, дахові установки й котельня (BACnet), тепловий баланс, "
    "відхилення → заявки ТО",
    "description": "factory3d_bms: норми освітленості, щити й групи освітлення LT-* (Helvar Imagine 950), установки "
    "RV-01…25, AHU-1, EF-*, котельня, тепловий баланс цеху, журнал відхилень, огляд будівлі, провайдери "
    "3D-переглядача lighting/ventilation; плагін колектора helvarnet (services/collector_plugins/f3d_collector_bms).",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_telemetry", "web"],
    # Каркас W0: решту файлів (access, дані, крон, представлення) додають W1…W5 і менеджер при злитті.
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/f3d_bms_light_norm_data.xml",
        "data/f3d_bms_light_scene_data.xml",
        "data/f3d_bms_source_data.xml",
        "data/f3d_bms_light_data.xml",
        "data/f3d_bms_hvac_data.xml",
        "views/f3d_bms_light_norm_views.xml",
        "views/f3d_bms_light_panel_views.xml",
        "views/f3d_bms_light_group_views.xml",
        "views/f3d_bms_light_scene_views.xml",
        "views/f3d_bms_hvac_unit_views.xml",
        "views/f3d_bms_heat_balance_views.xml",
        "views/menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
    "auto_install": False,
}
