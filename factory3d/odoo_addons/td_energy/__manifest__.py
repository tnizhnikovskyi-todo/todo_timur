{
    "name": "Завод 3D: енергетика",
    "summary": "Схема електропостачання, лічильники PM5560, 15-хв профіль, баланс, кВт·год і вартість на завдання й МО, "
    "СЕС, накопичувач, КГУ, АВР, тарифи, ліміт потужності",
    "description": "Ієрархія ввід → трансформатор → ГРЩ → шинопровід → споживач; лічильники поверх factory3d_telemetry; "
    "розподіл енергії на робочі завдання й собівартість МО; відключення мережі й АВР; провайдери 3D.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    # ENV-2: `mrp_workorder` (Enterprise) прибрано з depends — його немає в середовищі (factory3d/build/ENV_DECISIONS.md)
    "depends": ["factory3d_telemetry", "mrp_account", "analytic", "web_hierarchy"],
    "data": [
        "security/f3d_energy_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",  # W2: live/intervals/balance/rotate; крон alloc — W3
        "data/f3d_energy_tariff_data.xml",
        "data/f3d_energy_actions.xml",
        "wizard/recompute_wizard_views.xml",  # W3
        "views/f3d_energy_node_views.xml",
        "views/f3d_energy_meter_views.xml",
        "views/f3d_energy_interval_views.xml",
        "views/f3d_energy_balance_views.xml",
        "views/f3d_energy_event_views.xml",
        "views/f3d_energy_tariff_views.xml",
        "views/f3d_energy_pool_views.xml",
        "views/f3d_energy_alloc_views.xml",  # W3
        "views/f3d_energy_outage_views.xml",  # W4
        "views/mrp_production_views.xml",  # W3
        "views/mrp_workorder_views.xml",  # W3
        "views/mrp_workcenter_views.xml",  # W3
        # "views/mrp_workorder_views.xml", "views/mrp_workcenter_views.xml";
        "views/res_config_settings_views.xml",  # W5
        "views/dashboard_views.xml",  # W5
        "views/menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
