# Part of td_genset (ToDo). See README.md.
{
    'name': 'Генератори',
    'summary': 'Моніторинг і керування генератором SmartGen HGM6120N через ретранслятор',
    'description': """
Генератори (SmartGen HGM6120N через ретранслятор)
=================================================
Поточний стан і журнал показань, події, тривоги з ескалацією, пульт з підтвердженням
команд за знімками, розклад/таймер/тест, паливо (каністри, заправки, калібрування датчика)
і ТО за мотогодинами через стандартний модуль «Обслуговування».
""",
    'version': '18.0.1.0.0',
    'category': 'Generators',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'depends': ['base', 'mail', 'bus', 'web', 'maintenance'],
    'external_dependencies': {'python': ['requests', 'pytz']},
    'data': [
        # security
        'security/groups.xml',
        'security/ir.model.access.csv',
        # data
        'data/ir_sequence.xml',
        'data/mail_data.xml',
        'data/maintenance_data.xml',
        'data/controller_model_data.xml',
        'data/config_data.xml',
        'data/ir_cron.xml',
        'data/ir_exports.xml',
        # wizards (before the views that reference their actions)
        'wizard/command_wizard_views.xml',
        'wizard/timer_wizard_views.xml',
        'wizard/refuel_wizard_views.xml',
        'wizard/fuel_receipt_wizard_views.xml',
        # views
        'views/genset_views.xml',
        'views/genset_reading_views.xml',
        'views/genset_event_views.xml',
        'views/genset_alarm_views.xml',
        'views/genset_command_views.xml',
        'views/genset_schedule_views.xml',
        'views/genset_config_views.xml',
        'views/genset_fuel_views.xml',
        'views/maintenance_views.xml',
        'views/res_config_settings_views.xml',
        'views/analytics_actions.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'td_genset/static/src/**/*',
        ],
    },
    'application': True,
    'installable': True,
}
