# ruff: noqa: B018
{
    "name": "Claude-агент",
    "summary": "Особистий ШІ-агент Claude для користувача Odoo: згадка в чаттері або призначення задачі запускає Claude Code Routine",
    "description": """
Claude-агент
============

Кожен користувач Odoo («власник») може мати особистого агента — внутрішнього користувача «Claude · <ім'я>».
Коли власник згадує агента в чаттері або призначає йому задачу, Odoo викликає API «fire» Claude Code Routine власника.
Хмарна сесія далі працює в Odoo через XML-RPC від імені агента. Один запис Odoo = одна постійна сесія Claude.

Версія 2: команда ролей (Менеджер, Архітектор, Кодер, Тестувальник, Методолог), інструкції ролей і скіли зберігаються
в Odoo (пропозиції покращень агентів затверджує власник), стадія задачі запускає агента своєї ролі, запобіжники
(ліміт запусків за добу, пауза, склеювання), табель агентів зі стандартом опису.

Вимоги і примітки
-----------------

* Адреса і токен Routine вводяться власником у своєму агенті; токен недоступний користувачу-агенту й іншим користувачам.
* Дані запиту (текст повідомлення, назва запису) надсилаються на адресу Routine власника.
""",
    "version": "19.0.2.0.2",
    "category": "Services/Project",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["mail", "hr", "project", "hr_timesheet"],
    "data": [
        "security/td_claude_security.xml",
        "security/ir.model.access.csv",
        "data/td_claude_role_data.xml",
        "data/td_claude_skill_data.xml",
        "views/td_claude_role_views.xml",
        "views/td_claude_skill_views.xml",
        "views/td_claude_agent_views.xml",
        "views/td_claude_request_views.xml",
        "views/td_claude_session_views.xml",
        "views/td_claude_wizard_views.xml",
        "views/td_claude_team_wizard_views.xml",
        "views/project_views.xml",
        "views/res_users_views.xml",
        "views/td_claude_menus.xml",
    ],
    "post_init_hook": "_post_init_hook",
    "installable": True,
    "application": False,
}
