{
    "name": "Energy Resources",
    "summary": "Gas, heat, compressed air and water: meters of any resource, 15-minute series, cost, savings reserves",
    "description": """
Energy Resources
================

Extends Factory Energy to non-electric resources: gas, heat, compressed air and water, with prices, metering points, meters and savings reserves.

Key features
------------

* Resource catalog, prices, metering points and meters
* 15-minute intervals: meter value, flow integral and estimate
* Reactive energy
* Usage summary, savings reserves and detectors
* Energy Resources screen and Excel export
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    # D-18: td_bms, td_yard, td_genset — не залежності (тепло з BMS — міст td_energy_resources_bms)
    "depends": ["td_energy"],
    "images": ["static/description/banner.png"],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "data": [
        "security/td_energy_resources_security.xml",  # W3-A: record rules (SPEC 4.3)
        "security/ir.model.access.csv",  # W3-A: M-01…M-08
        "security/ir.model.access-opportunity.csv",  # W3-B: M-09, M-10
        "data/ir_config_parameter.xml",  # W3-A
        "data/td_energy_resource.xml",  # W3-A
        "data/td_energy_price_data.xml",  # W3-A
        "data/opportunity_rules.xml",  # W3-B
        "data/ir_cron.xml",  # W3-A: res_build, res_rotate
        "data/ir_cron_opportunity.xml",  # W3-B: opportunity, opportunity_links
        "views/td_energy_resources_views.xml",  # W3-C
        "views/td_energy_opportunity_views.xml",  # W3-C
        "views/res_config_settings_views.xml",  # W3-C
        "views/menus.xml",  # W3-C (останнім)
    ],
    "assets": {
        "web.assets_backend": [
            "td_energy_resources/static/src/resources/**/*",  # W3-C: UI-01…UI-08
        ],
        "web.assets_unit_tests": [
            "td_energy_resources/static/tests/**/*.js",
        ],
    },
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
