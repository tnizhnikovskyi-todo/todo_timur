#!/usr/bin/env bash
# Export td_* addons as a flat directory for apps.odoo.com: one module per top-level folder, repository branch 19.0.
#
# Usage: export_apps.sh <out_dir> [--force] [--with-docs] [--skip-ee] [--modules td_a,td_b] [--no-check]
#   --force       out_dir may be non-empty: everything except .git is removed first (a clone of the Apps repo)
#   --with-docs   keep module-level *.md (README, CHANGELOG, ...); by default they are internal build notes -> dropped
#   --skip-ee     do not export the Enterprise bridges (edition "ee" in apps_catalog.json)
#   --modules     export only these modules plus their td_* dependencies (default: all td_* modules)
#   --no-check    skip check_apps.py on the result
# Never exported: test_td_* modules, python tests/ (incl. tests/stand), ruff/pytest configs, *.pyc, caches,
# editor leftovers, td_genset/relay (fake relay for tests). static/tests (JS, referenced by manifest assets) stays.
# The editor bundle of td_constructor and three.js of td_viewer3d already live inside the modules, so no core files
# are copied; check_apps.py verifies that every file named in `data`/`demo`/`assets` exists in the result.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/../../odoo_addons" && pwd)"
CATALOG="$HERE/apps_catalog.json"

OUT=""; FORCE=0; DOCS=0; SKIP_EE=0; CHECK=1; ONLY=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE=1 ;;
        --with-docs) DOCS=1 ;;
        --skip-ee) SKIP_EE=1 ;;
        --no-check) CHECK=0 ;;
        --modules) ONLY="${2:?--modules needs a value}"; shift ;;
        -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}"; exit 0 ;;
        -*) echo "unknown option: $1" >&2; exit 2 ;;
        *) [[ -z "$OUT" ]] && OUT="$1" || { echo "extra argument: $1" >&2; exit 2; } ;;
    esac
    shift
done
[[ -n "$OUT" ]] || { echo "usage: export_apps.sh <out_dir> [options]" >&2; exit 2; }

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
case "$SRC/" in "$OUT"/*) echo "refusing: out_dir contains the source addons" >&2; exit 2 ;; esac
case "$OUT" in "/"|"$HOME"|"$SRC"|"$SRC"/*) echo "refusing unsafe out_dir: $OUT" >&2; exit 2 ;; esac
if [[ -n "$(find "$OUT" -mindepth 1 -maxdepth 1 ! -name .git -print -quit)" ]]; then
    [[ $FORCE -eq 1 ]] || { echo "out_dir is not empty: $OUT (use --force)" >&2; exit 2; }
    find "$OUT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
fi

# module list: td_* with a manifest, optional subset + dependency closure, optional EE filter
mapfile -t MODS < <(python3 - "$SRC" "$CATALOG" "$ONLY" "$SKIP_EE" <<'PY'
import ast, json, sys
from pathlib import Path
src, catalog, only, skip_ee = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4] == "1"
cat = json.loads(catalog.read_text(encoding="utf8"))["modules"] if catalog.is_file() else {}
deps = {}
for d in sorted(src.iterdir()):
    if d.name.startswith("td_") and (d / "__manifest__.py").is_file():
        tree = ast.parse((d / "__manifest__.py").read_text(encoding="utf8"))
        node = next(n.value for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Dict))
        deps[d.name] = [x for x in ast.literal_eval(node).get("depends", []) if x.startswith("td_")]
want = [m for m in only.split(",") if m] or list(deps)
missing = [m for m in want if m not in deps]
if missing:
    sys.exit("unknown module(s): " + ", ".join(missing))
out, stack = set(), list(want)
while stack:
    m = stack.pop()
    if m not in out:
        out.add(m)
        stack += [d for d in deps[m] if d in deps]
if skip_ee:
    out = {m for m in out if cat.get(m, {}).get("edition") != "ee"}
print("\n".join(sorted(out)))
PY
)
[[ ${#MODS[@]} -gt 0 ]] || { echo "no modules selected" >&2; exit 2; }

# tar exclusion patterns are position-sensitive: first the module-level ones (anchored, '*' does not cross '/'),
# then caches and leftovers at any depth
TAR_OPTS=(--anchored --no-wildcards-match-slash
          --exclude='*/tests' --exclude='*/ruff.toml' --exclude='*/pytest.ini' --exclude='td_genset/relay'
          --exclude='td_genset/DEPLOY_TEST.md' --exclude='td_genset/MIGRATION_19.md')
[[ $DOCS -eq 1 ]] || TAR_OPTS+=(--exclude='*/*.md')
TAR_OPTS+=(--no-anchored --wildcards-match-slash
           --exclude=__pycache__ --exclude='*.pyc' --exclude='*.pyo' --exclude=.pytest_cache
           --exclude=.ruff_cache --exclude=.mypy_cache --exclude=node_modules --exclude=.DS_Store
           --exclude='*.orig' --exclude='*.rej' --exclude='*.swp' --exclude='*~' --exclude='*.log')
tar -C "$SRC" -cf - "${TAR_OPTS[@]}" "${MODS[@]}" | tar -C "$OUT" -xf -

# repository README for the Apps repo root
python3 - "$OUT" "$CATALOG" "${MODS[@]}" <<'PY'
import ast, json, sys
from pathlib import Path
out, catalog, mods = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
cat = json.loads(catalog.read_text(encoding="utf8"))["modules"] if catalog.is_file() else {}
rows = []
for m in mods:
    tree = ast.parse((out / m / "__manifest__.py").read_text(encoding="utf8"))
    node = next(n.value for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Dict))
    man = ast.literal_eval(node)
    ed = "Enterprise" if cat.get(m, {}).get("edition") == "ee" else "Community"
    rows.append(f"| `{m}` | {man['name']} | {man['version']} | {man['license']} | {ed} | {man['summary']} |")
(out / "README.md").write_text(
    "# Factory 3D suite for Odoo 19\n\nBranch `19.0`; every top-level folder is an Odoo module.\n\n"
    "| Module | Name | Version | License | Edition | Summary |\n|---|---|---|---|---|---|\n"
    + "\n".join(rows) + "\n", encoding="utf8")
PY

echo "exported ${#MODS[@]} modules to $OUT ($(du -sh "$OUT" --exclude=.git | cut -f1), $(find "$OUT" -path "$OUT/.git" -prune -o -type f -print | wc -l) files)"
if [[ $CHECK -eq 1 ]]; then
    python3 "$HERE/check_apps.py" "$OUT" --catalog "$CATALOG" -q
fi
