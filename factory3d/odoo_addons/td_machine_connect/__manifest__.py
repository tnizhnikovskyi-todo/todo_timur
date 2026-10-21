{
    "name": "Machine Connect",
    "summary": "Machine states to time log: auto start, downtime reasons, OEE, STORETEQ portal, cutting maps",
    "description": """
Machine Connect
===============

Connects woodworking machines to Manufacturing. Machine states become a state and downtime journal, work orders start, pause and finish automatically, and OEE is calculated from actual data.

Key features
------------

* States of HOMAG machines (OPC UA, OPC 40550-1) and of machines without an interface (I/O modules)
* State and downtime journal with downtime reasons
* Automatic start, pause and finish of work orders, with the operator stored on the work order
* OEE from actual data
* Plant bottleneck analytics: utilisation, queue, waiting time and output per section, the constraining section and a what-if hint
* HOMAG STORETEQ P-500 portal warehouse: stacks versus stock, portal jobs from manufacturing orders
* Cutting maps and CNC programs attached to manufacturing orders

Requirements and notes
----------------------

* Machine data comes from a separate collector service with the opcua and rest_vendor plugins. The collector is not part of this module.
* Automatic start and writing to machines are disabled by default and enabled by system parameters.
* Works with Odoo Community; the Enterprise mrp_workorder module is not required.
""",
    "version": "19.0.1.3.1",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    # DEC-1/ENV-3: mrp_workorder (Enterprise) у середовищі немає; mrp, hr, stock, maintenance — явно (CE).
    "depends": ["td_telemetry", "mrp", "hr", "stock", "maintenance"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/res_users.xml",
        "data/mrp_loss_data.xml",
        "data/mc_sources.xml",
        "data/mc_machine_messages.xml",
        "data/ir_cron.xml",
        "data/td_actions.xml",
        "wizard/downtime_reason_wizard_views.xml",
        "views/td_machine_views.xml",
        "views/td_machine_state_log_views.xml",
        "views/td_downtime_views.xml",
        "views/td_bottleneck_views.xml",
        "views/td_machine_event_views.xml",
        "views/td_gantry_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/td_oee_views.xml",
        "wizard/cut_wizard_views.xml",
        "views/td_cut_views.xml",
        "views/mrp_production_views.xml",
        "views/product_views.xml",
        "views/mrp_workorder_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_machine_connect/static/src/views/**/*",
            "td_machine_connect/static/src/bottleneck/**/*",
        ],
        "web.assets_tests": [
            "td_machine_connect/static/tests/tours/*.js",
        ],
    },
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
