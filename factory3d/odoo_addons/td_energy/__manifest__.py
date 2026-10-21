{
    "name": "Factory Energy",
    "summary": "Power supply scheme, PM5560 meters, 15-minute profile, kWh and cost per work order, tariffs, demand limit",
    "description": """
Factory Energy
==============

Electric energy management for a manufacturing plant. Models the power supply hierarchy, collects meter readings through telemetry, and allocates energy and cost to work orders and manufacturing orders.

Key features
------------

* Hierarchy: infeed, transformer, main switchboard, busway, consumer
* Power meters (PM5560) on top of Factory 3D Telemetry, 15-minute profile and balance
* Energy allocation to work orders and manufacturing order costing (kWh and cost)
* Solar plant, battery storage, cogeneration unit and automatic transfer switch (ATS), grid outage handling
* Tariffs and a demand (power) limit

Requirements and notes
----------------------

* Meter data comes from the Factory 3D collector service, which is not part of this module.
""",
    "version": "19.0.1.1.3",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    # ENV-2: `mrp_workorder` (Enterprise) прибрано з depends — його немає в середовищі (factory3d/build/ENV_DECISIONS.md)
    "depends": ["td_telemetry", "mrp_account", "analytic", "web_hierarchy"],
    "images": ["static/description/banner.png"],
    "data": [
        "security/td_energy_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",  # W2: live/intervals/balance/rotate; крон alloc — W3; W1: advice, outage_plan, verification
        "data/td_energy_tariff_data.xml",
        "data/td_energy_actions.xml",
        "wizard/recompute_wizard_views.xml",  # W3
        "views/td_energy_ticket_wizard_views.xml",  # W1 (B): до node_views — кнопка вузла посилається на дію
        "views/td_energy_node_views.xml",
        "views/td_energy_meter_views.xml",
        "views/td_energy_interval_views.xml",
        "views/td_energy_balance_views.xml",
        "views/td_energy_event_views.xml",
        "views/td_energy_tariff_views.xml",
        "views/td_energy_pool_views.xml",
        "views/td_energy_alloc_views.xml",  # W3
        "views/td_energy_outage_views.xml",  # W4
        "views/td_energy_outage_plan_views.xml",  # W1 (B)
        "views/td_energy_advice_views.xml",  # W1 (B)
        "views/mrp_production_views.xml",  # W3
        "views/mrp_workorder_views.xml",  # W3
        "views/mrp_workcenter_views.xml",  # W3
        "views/td_energy_pult_views.xml",  # W1 (B): клієнтські дії Пульт, Картка вузла, Мобільний, Генерація
        "views/res_config_settings_views.xml",  # W5
        "views/dashboard_views.xml",  # W5
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_energy/static/src/common/**/*",  # W1 (B): UI-10, UI-11
            "td_energy/static/src/pult/**/*",
            "td_energy/static/src/node_card/**/*",
            "td_energy/static/src/generation/**/*",
            "td_energy/static/src/mobile/**/*",
        ],
        "web.assets_unit_tests": [
            "td_energy/static/tests/**/*.js",
        ],
    },
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
