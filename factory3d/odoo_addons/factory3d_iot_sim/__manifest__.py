{
    "name": "Factory3D: емулятор обладнання (пульт)",
    "version": "19.0.2.0.0",
    "summary": "Пульт емулятора обладнання factory3d: реєстр пристроїв, каталог сигналів, сценарії, рівень 0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "license": "LGPL-3",
    "website": "https://todo.ltd",
    "depends": ["factory3d_base"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        # рівень 0 — успадковані файли data-модуля, ПЕРШИМИ і без змін (інакше Odoo видалить записи)
        "data/models.xml",
        "data/actions.xml",
        "views/views.xml",
        # новий модуль
        "security/ir.model.access.csv",
        "security/security.xml",
        # W1+ додають: ir_config_parameter, ir_sequence, level0, f3d_sim_scenario, ir_cron,
        # views/sim_*_views.xml, wizard_views, maintenance_equipment_views, mrp_workcenter_views,
        # res_config_settings_views, menus (SPEC §1)
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
