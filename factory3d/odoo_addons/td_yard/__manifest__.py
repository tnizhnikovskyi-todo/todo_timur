# ruff: noqa: B018
{
    "name": "Yard Management",
    "summary": "Plant yard: third-party truck trips, gate booking, license plate recognition, barriers, truck scales",
    "description": """
Yard Management
===============

Manages the plant yard: visiting trucks, gate booking, number plate recognition, barriers and weighbridges, with a dispatcher board and a checkpoint screen.

Key features
------------

* Trips of third-party trucks and gate booking
* License plate recognition events (Axis LPV)
* Barrier commands (CAME) sent through telemetry, with safety switches
* Truck scales (SICS protocol, Mettler Toledo)
* Dispatcher board and a checkpoint (gatehouse) screen

Requirements and notes
----------------------

* Device events and commands go through the Factory 3D collector service (yard plugin), which is not part of this module.
* Processing of events and sending of barrier commands are disabled by default.
* The Gantt view of gate bookings is provided by the separate bridge Yard Gantt, which requires Odoo Enterprise.
""",
    "version": "19.0.1.0.1",
    "category": "Inventory/Inventory",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    # DEC-1: web_gantt (Enterprise) не в depends; Gantt — у мосту td_yard_gantt
    "depends": [
        "td_factory3d",
        "td_telemetry",
        "stock_picking_batch",
        "stock_fleet",
        "delivery",
        "stock_delivery",
        "mail",
        "bus",
    ],
    "images": ["static/description/banner.png"],
    "data": [
        "security/td_yard_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/td_yard_gate_data.xml",
        "data/td_yard_scale_data.xml",
        "views/td_yard_visit_views.xml",
        "views/td_yard_booking_views.xml",
        "views/stock_picking_batch_views.xml",
        "views/stock_picking_views.xml",
        "views/res_partner_views.xml",
        "wizard/td_yard_wizard_views.xml",
        "views/td_yard_menus.xml",
        "views/td_yard_gate_views.xml",
        "views/td_yard_lpr_event_views.xml",
        "views/td_command_views.xml",
        "views/td_yard_weighing_views.xml",
        "views/td_yard_scale_views.xml",
        "views/td_yard_kpp_action.xml",
        "report/td_yard_report_views.xml",
        "views/res_config_settings_views.xml",
        "data/td_yard_actions.xml",
        "data/ir_cron.xml",
    ],
    "assets": {
        "web.assets_backend": ["td_yard/static/src/kpp/*"],
        "web.assets_tests": ["td_yard/static/tests/tours/*"],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "demo": [],
    "installable": True,
    "application": False,
}
