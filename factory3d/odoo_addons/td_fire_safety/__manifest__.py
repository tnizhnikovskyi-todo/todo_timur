{
    "name": "Пожежна безпека",
    "summary": "Пожежна сигналізація (лише читання), іскрогасіння, димовидалення, евакуація за нормами, навчальні тривоги",
    "version": "19.0.1.0.0",
    "author": "ToDo",
    "license": "LGPL-3",
    "category": "Manufacturing/Maintenance",
    "website": "https://todo.ltd",
    "depends": ["td_telemetry", "hr_attendance"],
    # W0-скелет (DEC-1): моделей модуля ще немає, тому активні лише файли без залежності від моделей.
    # Повний порядок SPEC §1 — у закоментованих рядках; лідер розкоментовує їх по мірі появи моделей W1…W4
    # (порядок істотний: норми → прилад/шлейфи → зони → системи → димові зони → пристрої → виходи → маршрути →
    # шаблон → джерела → сигнали → крони → представлення → звіти → меню).
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/mail_activity_type.xml",
        "data/td.fire.norm.csv",               # M-08
        "data/td_fire_panel.xml",              # M-01, M-02
        "data/td.fire.zone.csv",               # M-03
        "data/td_fire_system.xml",             # M-06
        "data/td.fire.smoke.zone.csv",         # M-07
        "data/td.fire.device.csv",             # M-04
        "data/td.fire.exit.csv",                 # M-09
        "data/td_fire_route.xml",               # M-10
        "data/td_fire_drill_template.xml",     # M-11c, M-11e
        "data/td_source_data.xml",              # поле td_fire_readonly на td.source (M-15)
        "data/td_signal_data.xml",              # M-01…M-06 (signal_*), M-15
        "data/ir_cron.xml",                      # panel, drill
        "views/td_fire_norm_views.xml",
        "views/td_fire_panel_views.xml",
        "views/td_fire_zone_views.xml",
        "views/td_fire_device_views.xml",
        "views/td_fire_event_views.xml",
        "views/td_fire_system_views.xml",
        "views/td_fire_exit_views.xml",
        "views/td_fire_route_views.xml",
        "views/td_fire_smoke_zone_views.xml",
        "views/td_fire_drill_views.xml",
        "wizard/drill_rollcall_views.xml",
        "wizard/bacnet_device_views.xml",
        "views/td_zone_views.xml",
        "views/td_source_views.xml",
        "views/maintenance_request_views.xml",
        "views/res_config_settings_views.xml",
        "report/report_evac_compliance.xml",
        "report/report_evac_compliance_templates.xml",
        "report/report_drill.xml",
        "report/report_drill_templates.xml",
        # "report/report_events.xml",
        # "report/report_events_templates.xml",
        "views/menus.xml",  # у W0 — лише кореневе меню й контейнери; листки з діями — закоментовані в menus.xml
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {"python": []},
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
