# ruff: noqa: B018
{
    "name": "Factory 3D Constructor",
    "summary": "Factory layout constructor: sites, layers, rack templates, equipment variants with 3D, checks, publishing",
    "description": """
Factory 3D Constructor
======================

A 3D layout editor for the factory floor. Plan the plant layer by layer, place racks and equipment, run layout checks, and publish a confirmed version to Odoo.

Key features
------------

* Sites and layers with elevation marks and a grid
* Rack templates that generate storage cells (locations) automatically
* Catalog of equipment variants kept on equipment passports, each with a 3D model
* Placement checks while arranging equipment
* Draft, then publication with confirmation and a version history

Requirements and notes
----------------------

* The editor bundle is included in the module; no external build step or CDN is needed.
""",
    "version": "19.0.1.4.1",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "td_viewer3d", "stock", "maintenance", "mrp"],
    "images": ["static/description/banner.png"],
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
        "web.assets_tests": [
            "td_constructor/static/src/tours/*.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
