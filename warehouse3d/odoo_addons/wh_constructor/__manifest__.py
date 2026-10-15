{
    "name": "Конструктор складу",
    "summary": "Проєкти, версії та блокування зон для застосунку «Конструктор складу» (warehouse3d)",
    "version": "1.0.0",
    "category": "Inventory/Inventory",
    "author": "todo.ltd",
    "license": "LGPL-3",
    "depends": ["stock", "web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/menu.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
