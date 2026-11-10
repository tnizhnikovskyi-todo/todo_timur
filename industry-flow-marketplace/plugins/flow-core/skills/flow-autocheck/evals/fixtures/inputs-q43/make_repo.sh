#!/usr/bin/env bash
# inputs: шлях ≠ where, вхід з незлитої гілки, умовний вхід, зовнішній вхід. Наряд — <dest>/naryad.json, база — SHA main.
set -e; D=${1:?dest}; mkdir -p "$D/repo"; cd "$D/repo"
git init -q -b main; git config user.email t@example.test; git config user.name t
mkdir -p flow package
cat > flow/ARTIFACTS.md <<'X'
| крок | where | споживачі | умова |
|---|---|---|---|
| A-10 | package/ALLOCATION.md | A-12 | |
| A-11 | package/addons/ | A-12 | лише при повторному запуску |
| A-09 | package/CONFIG.md | A-12 | |
X
echo a > package/ALLOCATION.md; echo c > package/CONFIG.md; git add -A; git commit -qm main; BASE=$(git rev-parse HEAD)
git checkout -qb side; echo d > package/CONFIG.md; git commit -qam side; SIDE=$(git rev-parse HEAD); git checkout -q main
cat > "$D/naryad.json" <<X
{"step":"A-12","scope":{"kind":"package","id":"demo-1"},"attempt":1,"repo":{"url":"x","base_branch":"main","branch":"flow/a12"},
 "inputs":[{"name":"ALLOCATION.md","from":"A-10","path":"package/allocation.md","sha":"$BASE"},
  {"name":"CONFIG.md","from":"A-09","path":"package/CONFIG.md","sha":"$SIDE"},
  {"name":"попередній ALLOCATION","from":"A-11","path":"package/addons/","sha":"$BASE","condition":"лише при повторному запуску"},
  {"name":"анкета клієнта","from":"клієнт","path":"","sha":""}],"git":{"base":"$BASE"}}
X
