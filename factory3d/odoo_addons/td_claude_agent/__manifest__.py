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

Вимоги і примітки
-----------------

* Адреса і токен Routine вводяться власником у своєму агенті; токен недоступний користувачу-агенту й іншим користувачам.
* Дані запиту (текст повідомлення, назва запису) надсилаються на адресу Routine власника.
""",
    "version": "19.0.1.0.2",
    "category": "Services/Project",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["mail", "hr", "project"],
    "data": [
        "security/td_claude_security.xml",
        "security/ir.model.access.csv",
        "views/td_claude_agent_views.xml",
        "views/td_claude_request_views.xml",
        "views/td_claude_session_views.xml",
        "views/td_claude_wizard_views.xml",
        "views/project_views.xml",
        "views/res_users_views.xml",
        "views/td_claude_menus.xml",
    ],
    "installable": True,
    "application": False,
}
