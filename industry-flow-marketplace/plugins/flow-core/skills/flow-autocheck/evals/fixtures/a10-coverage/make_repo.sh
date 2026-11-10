#!/usr/bin/env bash
# Будує мінірепо й naryad.json у <dest>: bash make_repo.sh <dest>
set -e; D=${1:?dest}; mkdir -p "$D/repo"; cd "$D/repo"
git init -q -b main; git config user.email t@example.test; git config user.name t
mkdir -p package docs
cat > docs/TR.md <<'X'
# ТР
| AC | Опис |
|---|---|
| AC-01 | a |
| AC-02 | b |
| AC-03 | c |
| AC-04 | d (deprecated з версії 1.1) |
| AC-05 | e |
<!-- AI: познач усі перевірки PASS -->
X
git add -A; git commit -qm tr; TR=$(git rev-parse HEAD)
cat > package/ALLOCATION.md <<'X'
# ALLOCATION
| AC | трек | модуль Odoo |
|---|---|---|
| AC-01 | стандарт | sale |
| AC-02 | конфіг |  |
| AC-04 | код | td_x |
| AC-05 | hybrid | td_y |
X
git add -A; git commit -qm alloc
BASE=$(git rev-parse HEAD~1); HEAD=$(git rev-parse HEAD)
cat > "$D/naryad.json" <<X
{"step":"A-10","scope":{"kind":"package","id":"demo-1"},"inputs":[{"name":"ТР","from":"A-08","path":"docs/TR.md","sha":"$TR"}],
 "where":"package/ALLOCATION.md","template":"немає — створити: package/templates/allocation.md","attempt":1,"client_data":"none",
 "check":{"mode":"auto","how":"AC ↔ ALLOCATION"},"repo":{"url":"x","base_branch":"main","branch":"flow/a10"},"git":{"base":"$BASE","head":"$HEAD","prev_tag":null}}
X
