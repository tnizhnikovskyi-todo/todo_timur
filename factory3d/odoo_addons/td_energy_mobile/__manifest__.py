{
    "name": "Чергування (телефон)",
    "summary": "Мобільний екран чергового енергетика: вкладка «Обхід» (чек-лист ТП і ГРЩ), журнал обходів, події на відхилення",
    "description": "Четверта вкладка «Обхід» мобільного екрана td_energy (реєстр td_energy.mobile_tabs): шаблони обходів зі "
    "слотами за розкладом, відмітка пунктів зі значенням сигналу й нормою, завершення з журналом і подіями на "
    "відхилення, крони відкриття й закриття обходів.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    # W4 H.1: лише td_energy (транзитивно maintenance, bus, mail); td_genset — не залежність (паливо ДГУ — через get_pult)
    "depends": ["td_energy"],
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
