#!/usr/bin/env bash
# A-14 allocation-coverage: у package/addons лежить файл AC-COVERAGE.md і спільні/демо модулі (td_home_menu, td_support, td_knowledge, td_x_demo, td_x_elearning, td_x_knowledge), яких немає в ALLOCATION; package/config має CONFIG.md, manifest.yaml, vp-map.yaml, install-log.md. Очікується PASS.
set -e; D=${1:?dest}; mkdir -p "$D/repo"; cd "$D/repo"
git init -q -b main; git config user.email t@example.test; git config user.name t
mkdir -p package/addons/td_x package/addons/td_home_menu package/addons/td_support package/addons/td_knowledge package/addons/td_x_demo package/addons/td_x_elearning package/addons/td_x_knowledge package/config
for m in td_x td_home_menu td_support td_knowledge td_x_demo td_x_elearning td_x_knowledge; do echo "{'name':'$m','version':'19.0.1.0.0'}" > package/addons/$m/__manifest__.py; done
echo "# покриття" > package/addons/AC-COVERAGE.md
for f in CONFIG.md manifest.yaml vp-map.yaml install-log.md; do echo x > package/config/$f; done
printf '# ALLOCATION\n\n| AC | трек | модуль Odoo |\n|---|---|---|\n| AC-01 | код | td_x |\n' > package/ALLOCATION.md
printf '# CHECKS\n\nconfig: CONFIG, manifest, vp-map, install-log\n' > package/CHECKS.md
git add -A; git commit -qm base; B=$(git rev-parse HEAD)
cat > "$D/naryad.json" <<X
{"step":"A-14","scope":{"kind":"package","id":"demo-1"},"inputs":[],"where":"package/CHECKS.md","template":"package/CHECKS.md","done":"x","attempt":1,"client_data":"none",
 "check":{"mode":"result"},"repo":{"url":"x","base_branch":"main","branch":"flow/a14"},"git":{"base":"$B","head":"$B"}}
X
