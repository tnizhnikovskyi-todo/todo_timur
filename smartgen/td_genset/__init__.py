# Part of td_genset (ToDo). See README.md.
from . import models
from . import wizard

# Системні параметри модуля (ir.config_parameter, без xml id): адреса API, токен і таймаут ретранслятора
CONFIG_PARAM_PREFIX = 'td_genset.'


def uninstall_hook(env):
    """Деінсталяція модуля: системні параметри ``td_genset.*`` (адреса API, **токен** ретранслятора, таймаут) створює
    ``res.config.settings`` без xml id, тож Odoo сам їх не видаляє — прибираємо явно, щоб токен не лишився в базі.

    Решту прибирає Odoo за xml id модуля: заплановані дії (cron), дії, меню, групи, підтипи повідомлень, налаштування
    і таблиці ``td_genset_*`` (разом із чатером, підписками й активностями генераторів). Обладнання й заявки ТО
    лишаються в «Обслуговуванні» (ТР 2.15), поля ``td_*`` на них видаляються. Щоб Odoo не пробував видаляти записи,
    на які ще є посилання (рядки ERROR ``bad query … violates foreign key constraint`` у лозі деінсталяції):
    активності генераторів видаляються одразу, моделі контролерів — разом зі своєю таблицею, а команда ТО і категорія
    обладнання «Генератори», якщо на них посилаються заявки й обладнання, лишаються звичайними записами.
    """
    env = env(su=True)
    params = env['ir.config_parameter'].search([('key', '=like', 'td%genset.%')])
    params.filtered(lambda param: param.key.startswith(CONFIG_PARAM_PREFIX)).unlink()
    env['mail.activity'].search([('res_model', '=', 'td.genset')]).unlink()
    keep = env['ir.model.data'].search([('module', '=', 'td_genset'), ('model', '=', 'td.genset.controller.model')])
    team = env.ref('td_genset.maintenance_team_genset', raise_if_not_found=False)
    if team and env['maintenance.request'].with_context(active_test=False).search_count(
            [('maintenance_team_id', '=', team.id)], limit=1):
        keep |= env['ir.model.data'].search([('module', '=', 'td_genset'), ('name', '=', 'maintenance_team_genset')])
    category = env.ref('td_genset.equipment_category_genset', raise_if_not_found=False)
    if category and env['maintenance.equipment'].with_context(active_test=False).search_count(
            [('category_id', '=', category.id)], limit=1):
        keep |= env['ir.model.data'].search([('module', '=', 'td_genset'), '|',
                                             ('name', '=', 'equipment_category_genset'),
                                             '&', ('model', '=', 'mail.alias'), ('res_id', '=', category.alias_id.id)])
    keep.unlink()
