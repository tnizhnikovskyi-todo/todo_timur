#!/usr/bin/env bash
# Run odoo-lens check on Odoo module dirs (default: all in factory3d/odoo_addons).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
ADDONS="$ROOT/factory3d/odoo_addons"
ODOO_HOME="${ODOO_HOME:-/home/user/odoo19}"
if [[ ! -f "$ODOO_HOME/odoo/__init__.py" ]]; then
  echo "Odoo 19 sources not found at $ODOO_HOME — run factory3d/tools/odoo/setup.sh or set ODOO_HOME" >&2
  exit 2
fi
[[ -d "$DIR/vendor/odoo-lens" ]] || "$DIR/fetch.sh" odoo-lens
mods=("$@")
if ((${#mods[@]} == 0)); then
  for d in "$ADDONS"/*/; do
    [[ -f "$d/__manifest__.py" ]] && mods+=("${d%/}")
  done
fi
cat > "$ADDONS/.odoo-lens.json" <<JSON
{"odoo": "$ODOO_HOME", "addons": ["$ODOO_HOME/addons", "."], "version": "19.0", "diagnostics": true}
JSON
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
rc=0
"$DIR/vendor/odoo-lens/bin/odoo-lens" check "${mods[@]}" > "$tmp" 2>&1 || rc=$?
sed "s#$ROOT/##g" "$tmp" | head -60
echo "odoo-lens: $(grep -cE ':[0-9]+:[0-9]+:' "$tmp" || true) problems"
exit "$rc"
