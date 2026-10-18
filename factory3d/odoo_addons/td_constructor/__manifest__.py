# ruff: noqa: B018
{
    "name": "Конструктор",
    "summary": "Конструктор розкладки заводу: площадки, шари, місця зі стелажів-шаблонів, каталог варіантів "
    "обладнання з 3D, "
    "перевірки, публікація в Odoo",
    "description": "3D-редактор розкладки (шари з відмітками, сітка, шаблони стелажів → комірки, "
    "розстановка обладнання "
    "з перевірками), каталог варіантів на паспортах обладнання з 3D-моделлю, чернетка → публікація "
    "з підтвердженням і історією версій.",
    "version": "19.0.1.3.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "td_viewer3d", "stock", "maintenance", "mrp"],
    "data": [
        "security/td_constructor_security.xml",
        "security/ir.model.access.csv",
        "data/params.xml",
        "data/td_term_data.xml",
        "data/td_generic_catalog.xml",
        "data/td_slot_type_data.xml",
        "views/td_site_views.xml",
        "views/td_layer_views.xml",
        "views/td_slot_views.xml",
        "views/td_equipment_variant_views.xml",
        "views/td_placement_views.xml",
        "views/td_check_config_views.xml",
        "views/td_layout_version_views.xml",
        "views/td_term_views.xml",
        "views/td_inherit_views.xml",
        "views/td_slot_type_views.xml",
        "views/td_putaway_views.xml",
        "views/td_collab_views.xml",
        "views/td_help.xml",
        "wizard/td_publish_wizard_views.xml",
        "data/actions.xml",
        "views/td_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_constructor/static/src/action/**/*",
            "td_constructor/static/src/editor/**/*",
            "td_constructor/static/src/model/**/*",
            "td_constructor/static/src/widgets/**/*",
        ],
        "web.assets_unit_tests": [
            "td_constructor/static/tests/editor/**/*",
            "td_constructor/static/tests/model/**/*",
            "td_constructor/static/tests/fixtures/*.json",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
