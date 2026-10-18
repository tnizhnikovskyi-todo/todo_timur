{
    "name": "Аналітика енергетики",
    "summary": "Добові факти, драйвери, база ISO 50001 й EnPI, бюджет, розрізи, резерви економії, екран «Аналітика», "
    "звіти для керівництва й за зміну",
    "description": "Аналітика заводу поверх td_energy і td_energy_resources: ділянки, драйвери нормалізації (м² плит, градусо-доби), "
    "добові факти, модель бази ISO 50001 (регресія) і EnPI, бюджет енергії, розрізи (ділянки, обладнання, замовлення, "
    "продукти, зміни), теплокарта, екран «Аналітика», PDF «Звіт для керівництва» й «Звіт за зміну».",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    # W4 SPEC розд. 1: td_energy_resources — жорстка залежність («усі ресурси»); mrp_account тягне mrp, stock_account, maintenance
    "depends": ["td_energy", "td_energy_resources", "mrp_account"],
    "external_dependencies": {"python": []},  # для PDF потрібен системний wkhtmltopdf (штатний для Odoo)
    "data": [
        "security/td_energy_analytics_security.xml",  # W4-A: record rules (SPEC 4.3)
        "security/ir.model.access.csv",  # W4-A: M-01…M-09
        "security/ir.model.access-report.csv",  # W4-B: M-13, M-16
        "data/td_energy_driver_data.xml",  # W4-A: plate_m2, hdd
        "data/ir_config_parameter.xml",  # W4-A
        "data/ir_cron.xml",  # W4-A: 4 крони
        "views/td_energy_analytics_views.xml",  # W4-B
        "views/td_energy_budget_views.xml",  # W4-B
        "views/product_template_views.xml",  # W4-B
        "views/res_config_settings_views.xml",  # W4-B
        "report/report_management.xml",  # W4-B
        "report/report_management_templates.xml",  # W4-B
        "report/report_shift.xml",  # W4-B
        "report/report_shift_templates.xml",  # W4-B
        "views/menus.xml",  # W4-B (останнім)
        # data/td_energy_area.csv і data/area_map.csv у data не входять: їх вантажить hooks._load_areas(env)
    ],
    "assets": {
        "web.assets_backend": [
            "td_energy_analytics/static/src/analytics/**/*",  # W4-B: UI-01…UI-10
        ],
        "web.assets_unit_tests": [
            "td_energy_analytics/static/tests/**/*.js",
        ],
    },
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
