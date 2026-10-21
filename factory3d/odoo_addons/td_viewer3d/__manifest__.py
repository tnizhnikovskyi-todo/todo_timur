{
    "name": "Factory 3D Viewer",
    "summary": "3D viewer of the factory inside Odoo: live ORM data, Show in 3D, state journal, shop-floor kiosk",
    "description": """
Factory 3D Viewer
=================

Displays the plant, warehouse and production in an interactive 3D scene right inside Odoo 19. Objects in the scene are colored and labelled from live Odoo data, so the scene always shows the current state of stock, manufacturing, maintenance, people and logistics.

The 3D engine and the sample models are bundled with the module; no internet access or CDN is required.

Key features
------------

* Show in 3D: a button on manufacturing orders, transfers, work centers, locations, equipment, employees and zones opens the viewer on the selected object or on the document route
* Open in Odoo: click an object in the scene to open its form
* State journal with snapshots and shift replay with a time slider
* Kiosk screen for a shop-floor tablet, opened by a token URL without a login
* Briefing wall mode for a TV: a full-screen slide playlist (3D fly-around, KPI tiles, alarms and events, today's orders) on the same kiosk URL
* Cycle check that reports gaps in the receiving-to-shipping chain, and a demo-data wizard for test servers
""",
    "version": "19.0.1.1.5",
    "author": "ToDo",
    "license": "LGPL-3",
    "category": "Manufacturing/Manufacturing",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "depends": ["td_factory3d", "bus", "web"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/params.xml",
        "data/actions.xml",
        # kiosk_user.xml після actions.xml: користувач посилається на action_td_viewer
        "security/kiosk_user.xml",
        "data/cron.xml",
        "views/viewer_snapshot_views.xml",
        "views/viewer_event_views.xml",
        "views/res_config_settings_views.xml",
        "views/show_in_3d_views.xml",
        "views/templates_kiosk.xml",
        "wizard/demo_wizard_views.xml",
        "wizard/cycle_check_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_viewer3d/static/src/viewer/viewer.scss",
            "td_viewer3d/static/src/viewer/*.js",
            "td_viewer3d/static/src/action/*",
        ],
        "td_viewer3d.assets_kiosk": [
            ("include", "web._assets_helpers"),
            ("include", "web._assets_backend_helpers"),
            "web/static/src/scss/pre_variables.scss",
            "web/static/lib/bootstrap/scss/_variables.scss",
            "web/static/lib/bootstrap/scss/_variables-dark.scss",
            "web/static/lib/bootstrap/scss/_maps.scss",  # $theme-colors-rgb для utilities/_api.scss
            ("include", "web._assets_bootstrap_backend"),
            ("include", "web._assets_core"),  # module_loader.js, owl.js, odoo_module.js — уже тут
            "web/static/src/libs/fontawesome/css/font-awesome.css",
            "td_viewer3d/static/src/viewer/viewer.scss",
            "td_viewer3d/static/src/kiosk/kiosk.scss",
            "td_viewer3d/static/src/viewer/*.js",
            "td_viewer3d/static/src/kiosk/*.js",
        ],
        "web.assets_tests": [
            "td_viewer3d/static/tests/tours/*.js",
        ],
        "web.assets_unit_tests": [
            "td_viewer3d/static/tests/hoot/*",
        ],
    },
    "post_init_hook": "post_init",
    "uninstall_hook": "uninstall",
    "external_dependencies": {},
    "installable": True,
    "application": False,
}
