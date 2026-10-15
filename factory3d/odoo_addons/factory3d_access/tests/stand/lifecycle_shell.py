# ruff: noqa
"""DEPLOY_TEST п.7 (деінсталяція → відмітки збережені, режими biostar → manual, параметрів немає), для ``odoo-bin shell``.

Друкує ``LIFE {json}``. Після нього повторна установка: ``update.sh <db>`` (ТК-01 зелений)."""
import json

cr = env.cr  # noqa: F821
snap = lambda: {  # noqa: E731
    "attendances": env["hr.attendance"].search_count([]),
    "in_biostar": env["hr.attendance"].search_count([("in_mode", "=", "biostar")]),
    "out_biostar": env["hr.attendance"].search_count([("out_mode", "=", "biostar")]),
    "params": env["ir.config_parameter"].search_count([("key", "like", "factory3d.access.%")]),
}
out = {"before": snap()}
module = env["ir.module.module"].search([("name", "=", "factory3d_access")])
module.button_immediate_uninstall()
cr.commit()
env.invalidate_all()
out["after"] = snap() if False else None
cr.execute("SELECT count(*) FROM hr_attendance"); total = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM hr_attendance WHERE in_mode='biostar' OR out_mode='biostar'"); bio = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM ir_config_parameter WHERE key LIKE 'factory3d.access.%'"); params = cr.fetchone()[0]
cr.execute("SELECT state FROM ir_module_module WHERE name='factory3d_access'"); state = cr.fetchone()[0]
out["after"] = {"attendances": total, "biostar_modes": bio, "params": params, "module_state": state}
print("LIFE " + json.dumps(out))
