# ruff: noqa
"""DEPLOY_TEST п.6 (деінсталяція на копії): сигнали без джерел, параметри/крони модуля прибрані; для ``odoo-bin shell``.

Друкує ``LIFE {json}``. Після нього повторна установка: ``update.sh <db>`` і ТК-01 (зелений)."""

import json

cr = env.cr  # noqa: F821


def snap():
    cr.execute("SELECT count(*) FROM f3d_signal WHERE code LIKE 'energy/%' OR code LIKE 'infra/%'")
    sigs = cr.fetchone()[0]
    cr.execute("""SELECT count(*), count(*) FILTER (WHERE active) FROM f3d_signal
                  WHERE (code LIKE 'energy/%' OR code LIKE 'infra/%') AND source_id IS NULL""")
    nosrc, nosrc_active = cr.fetchone()
    cr.execute("SELECT count(*) FROM ir_config_parameter WHERE key LIKE 'factory3d.energy.%'")
    params = cr.fetchone()[0]
    cr.execute("SELECT count(*) FROM f3d_source WHERE code LIKE 'MB-U%'")
    srcs = cr.fetchone()[0]
    cr.execute("SELECT state FROM ir_module_module WHERE name='factory3d_energy'")
    return {
        "signals": sigs,
        "signals_without_source": nosrc,
        "signals_without_source_active": nosrc_active,
        "params": params,
        "mb_sources": srcs,
        "module_state": cr.fetchone()[0],
    }


out = {"before": snap()}
env["ir.module.module"].search([("name", "=", "factory3d_energy")]).button_immediate_uninstall()  # noqa: F821
cr.commit()
out["after"] = snap()
print("LIFE " + json.dumps(out))
