# ruff: noqa: E501
"""ТП-04 (SPEC §13.4): часи крону перевірок і огляду на базі стенда. Запуск: stand.sh shell < perf_odoo.py (odoo shell)."""

import time

Check = env["td.bms.check"]  # noqa: F821
n_chk = env["td.signal"].search_count([("code", "like", "%/check"), ("module", "=", "bms")])  # noqa: F821
n_sig = env["td.signal"].search_count([("module", "=", "bms")])  # noqa: F821
n_ep = env["td.bms.deviation"].search_count([])  # noqa: F821
runs = []
for _ in range(5):
    t = time.perf_counter()
    Check._cron_check()
    runs.append(time.perf_counter() - t)
    env.cr.commit()  # noqa: F821
ov = []
for _ in range(5):
    t = time.perf_counter()
    env["td.bms.overview"].get_overview_data()  # noqa: F821
    ov.append(time.perf_counter() - t)
print("STAND perf: check_signals=%d bms_signals=%d episodes=%d" % (n_chk, n_sig, n_ep))
print("STAND perf: cron_check_s=%s max=%.3f" % (["%.3f" % x for x in runs], max(runs)))
print("STAND perf: overview_s=%s max=%.3f" % (["%.3f" % x for x in ov], max(ov)))
