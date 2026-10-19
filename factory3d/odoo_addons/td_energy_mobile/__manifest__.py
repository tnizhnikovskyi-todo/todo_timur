{
    "name": "Energy Rounds Mobile",
    "summary": "Mobile screen of the energy duty officer: Rounds tab with checklists, round journal, deviation events",
    "description": """
Energy Rounds Mobile
====================

Adds a Rounds tab to the mobile screen of the duty energy engineer: checklists for substations and switchboards, a round journal and events for deviations.

Key features
------------

* Round templates with slots by schedule
* Checking items with the signal value shown next to the norm
* Finishing a round writes a journal entry and events for deviations
* Scheduled actions that open and close rounds
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    # W4 H.1: лише td_energy (транзитивно maintenance, bus, mail); td_genset — не залежність (паливо ДГУ — через get_pult)
    "depends": ["td_energy"],
    "images": ["static/description/banner.png"],
    "external_dependencies": {"python": []},
    "data": [
        "security/td_energy_mobile_security.xml",  # W4-C: record rules (H.4.2)
        "security/ir.model.access.csv",  # W4-C: M-H1…M-H5
        "data/ir_config_parameter.xml",  # W4-C
        "data/round_template_data.xml",  # W4-C: шаблон «Обхід ТП і ГРЩ»
        "data/ir_cron.xml",  # W4-C: 3 крони
        "views/td_energy_round_views.xml",  # W4-C
        "views/menus.xml",  # W4-C (останнім)
    ],
    "assets": {
        # Реєстр `td_energy.mobile_tabs` створює td_energy: ассет вантажиться після нього (залежність модуля)
        "web.assets_backend": [
            "td_energy_mobile/static/src/mobile_round/**/*",  # W4-C: UI-H1…UI-H4
        ],
        "web.assets_unit_tests": [
            "td_energy_mobile/static/tests/**/*.js",
        ],
    },
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
