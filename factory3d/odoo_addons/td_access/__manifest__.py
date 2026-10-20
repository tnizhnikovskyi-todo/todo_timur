# ruff: noqa: B018
{
    "name": "Factory Access Control",
    "summary": "Suprema BioStar 2: attendance check-ins, cards, turnstiles, visitors, people by zone",
    "description": """
Factory Access Control
======================

Polls the REST API of a Suprema BioStar 2 access control server and brings its data into Odoo: an event journal, attendance records for perimeter passes, presence and zones of people, door status, cards and visitors.

Key features
------------

* Event journal of passes and door events
* Check-ins and check-outs in Attendances created from perimeter passes
* Presence and zone of every person, and door status
* Cards and visitors, managed under a write safety switch

Requirements and notes
----------------------

* Connects to the customer's own BioStar 2 server; the password is entered by an administrator in the settings. No data is sent to the module vendor.
* Writing to BioStar 2 is disabled by default.
""",
    "version": "19.0.1.0.1",
    "category": "Human Resources/Attendances",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "hr_attendance", "mail"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/td_access_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/td_access_server_data.xml",
        "data/td_access_device_data.xml",
        "data/ir_cron.xml",
        "views/td_access_server_views.xml",
        "views/td_access_device_views.xml",
        "views/td_access_door_views.xml",
        "views/td_access_user_link_views.xml",
        "views/td_access_event_views.xml",
        "views/td_access_presence_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_attendance_views.xml",
        "views/td_zone_views.xml",
        "views/td_access_card_views.xml",
        "views/td_access_visitor_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/event_reprocess_wizard_views.xml",
        "views/menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": ["requests"]},
    "installable": True,
    "application": False,
}
