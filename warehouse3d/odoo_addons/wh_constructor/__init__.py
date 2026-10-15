from . import controllers
from . import models

MENU_PARENT = "stock.menu_stock_config_settings"
GROUP_VIEW = "wh_constructor.group_wh_view"


def _menu_groups_field(env):
    # поле групп меню: groups_id в Odoo 18, group_ids в Odoo 19
    return "group_ids" if "group_ids" in env["ir.ui.menu"]._fields else "groups_id"


def post_init_hook(env):
    """Меню «Конфігурація» склада видно только менеджеру склада; даём его видеть и группе «просмотр».
    Администратор базы получает полный доступ к конструктору."""
    parent, group = env.ref(MENU_PARENT, raise_if_not_found=False), env.ref(GROUP_VIEW, raise_if_not_found=False)
    if parent and group:
        parent.write({_menu_groups_field(env): [(4, group.id)]})
    admin, apply_group = env.ref("base.user_admin", raise_if_not_found=False), env.ref("wh_constructor.group_wh_apply", raise_if_not_found=False)
    if admin and apply_group:
        field = "group_ids" if "group_ids" in env["res.users"]._fields else "groups_id"
        admin.write({field: [(4, apply_group.id)]})


def uninstall_hook(env):
    parent, group = env.ref(MENU_PARENT, raise_if_not_found=False), env.ref(GROUP_VIEW, raise_if_not_found=False)
    if parent and group:
        parent.write({_menu_groups_field(env): [(3, group.id)]})
