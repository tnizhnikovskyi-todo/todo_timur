# ruff: noqa: B018
{
    "name": "Завод 3D: конструктор",
    "summary": "Конструктор розкладки заводу: площадки, шари, місця зі стелажів-шаблонів, каталог варіантів обладнання з 3D, "
               "перевірки, публікація в Odoo",
    "description": "3D-редактор розкладки (шари з відмітками, сітка, шаблони стелажів → комірки, розстановка обладнання "
                   "з перевірками), каталог варіантів на паспортах обладнання з 3D-моделлю, чернетка → публікація "
                   "з підтвердженням і історією версій.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_base", "factory3d_viewer", "stock", "maintenance", "mrp"],
    "data": [
        "security/f3d_constructor_security.xml",
        "security/ir.model.access.csv",
        "data/params.xml",
        "data/f3d_term_data.xml",
        "data/f3d_generic_catalog.xml",
        "views/f3d_site_views.xml",
        "views/f3d_layer_views.xml",
        "views/f3d_slot_views.xml",
        "views/f3d_equipment_variant_views.xml",
        "views/f3d_placement_views.xml",
        "views/f3d_check_config_views.xml",
        "views/f3d_layout_version_views.xml",
        "views/f3d_term_views.xml",
        "views/f3d_inherit_views.xml",
        "wizard/f3d_publish_wizard_views.xml",
        "data/actions.xml",
        "views/f3d_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "factory3d_constructor/static/src/action/**/*",
            "factory3d_constructor/static/src/editor/**/*",
            "factory3d_constructor/static/src/model/**/*",
            "factory3d_constructor/static/src/widgets/**/*",
        ],
        "web.assets_unit_tests": [
            "factory3d_constructor/static/tests/editor/**/*",
            "factory3d_constructor/static/tests/model/**/*",
            "factory3d_constructor/static/tests/fixtures/*.json",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
