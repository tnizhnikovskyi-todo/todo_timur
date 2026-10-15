from odoo import Command

G_VIEW, G_DESIGN, G_APPLY = "wh_constructor.group_wh_view", "wh_constructor.group_wh_design", "wh_constructor.group_wh_apply"


def make_user(env, login, *groups, company=None):
    """Внутренний пользователь с группами конструктора (поле групп: groups_id в Odoo 18, group_ids в 19)."""
    field = "group_ids" if "group_ids" in env["res.users"]._fields else "groups_id"
    ids = [env.ref("base.group_user").id] + [env.ref(g).id for g in groups]
    vals = {"name": f"Тест {login}", "login": login, "password": f"{login}-pass-1", field: [Command.set(ids)]}
    if company:
        vals.update(company_id=company.id, company_ids=[Command.set([company.id])])
    return env["res.users"].with_context(no_reset_password=True).create(vals)


def project_data(name="Тестовий склад", marks=0):
    """Минимальный проект v2 (как делает приложение); marks — произвольное содержимое, чтобы версии различались."""
    return {"schema": 2, "id": "p-1", "name": name, "source": {"kind": "scratch", "name": name}, "loaded_at": "2026-10-15",
            "warehouses": [{"id": "wh-1", "code": "WH", "name": "Склад", "saved": {"marks": marks}, "pending": []}]}
