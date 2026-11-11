#!/usr/bin/env bash
# inputs для A-03b: у наряді немає OWNER-INTAKE.md -> FAIL input-intake; briefing.md є. Наряд — <dest>/naryad.json.
set -e; D=${1:?dest}; mkdir -p "$D/repo"; cd "$D/repo"
git init -q -b main; git config user.email t@example.test; git config user.name t
mkdir -p flow docs/industries/test
cat > flow/ARTIFACTS.md <<'X'
| крок | where | споживачі | умова |
|---|---|---|---|
| A-03 | docs/industries/test/briefing.md | A-03b | |
X
echo b > docs/industries/test/briefing.md; git add -A; git commit -qm main; BASE=$(git rev-parse HEAD)
cat > "$D/naryad.json" <<X
{"step":"A-03b","scope":{"kind":"package","id":"test"},"attempt":1,"repo":{"url":"x","base_branch":"main","branch":"flow/a03b"},
 "inputs":[{"name":"briefing.md","from":"A-03","path":"docs/industries/test/briefing.md","sha":"$BASE"}],"git":{"base":"$BASE"}}
X
