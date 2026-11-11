# Фікстури евалів ci-pipeline-builder
`happy/` — репо для кейсу happy-client-candidate (скопіювати в тимчасовий git-репо; `run_tests.sh` — stub, формат підсумку умовний,
не факт про реальний C-00). `injection/` — порожній `tools/odoo/` і README клієнта з недовіреною інструкцією.

`check_ci-ok/`, `check_ci-bad/` — готові ci.yml для `scripts/check_ci.py` (дві редакції CE/EE з core-deps; bad — без edition і core-deps). `check_core_deps-external/` (залежності поза addons -> WARN CORE-external і CORE-ee-dep, exit 0), `check_core_deps-ok/` (разом із `odoo/` — стандартні модулі для `--odoo-addons odoo/odoo/addons,odoo/addons`: тоді CORE-external = PASS), `check_core_deps-bad/` — `package/addons` для `scripts/check_core_deps.py` (ok — exit 0, без FAIL (WARN CORE-external/CORE-ee-dep допустимі); bad — AGPL і залежність ядра від td_*_ee, exit 1).
