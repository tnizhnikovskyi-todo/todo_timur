#!/usr/bin/env bash
# Самоперевірка check_edition (_common.sh): ce з EE-шляхом поза addons-path -> 0; ce з EE у addons-path -> 2; ee без шляху -> 3.
# Використання: bash selftest_edition.sh  (код 0 = усе гаразд). Нічого не змінює.
d="$(cd "$(dirname "$0")" && pwd)"; bad=0
t() { # назва очікуваний_rc  env...
  local name="$1" want="$2"; shift 2
  env -i PATH="$PATH" "$@" bash -c 'source "$1/_common.sh"; check_edition' _ "$d" >/dev/null 2>&1
  local rc=$?
  if [[ $rc -eq $want ]]; then echo "PASS $name (rc=$rc)"; else echo "FAIL $name: rc=$rc, очікувалось $want"; bad=1; fi
}
t ce-ee-поза-addons-path 0 ODOO_EDITION=ce ODOO_EE_ADDONS_PATH=/ee ODOO_ADDONS_PATH=/a,/b
t ce-без-ODOO_ADDONS_PATH 0 ODOO_EDITION=ce ODOO_EE_ADDONS_PATH=/ee
t ce-без-ee-шляху 0 ODOO_EDITION=ce
t ce-ee-в-addons-path 2 ODOO_EDITION=ce ODOO_EE_ADDONS_PATH=/ee ODOO_ADDONS_PATH=/a,/ee/
t ee-без-шляху 3 ODOO_EDITION=ee
exit $bad
