#!/usr/bin/env bash
# Крок без специфікації (A-99): очікується ERROR spec-missing і вердикт INCOMPLETE, не PASS.
set -e; D=${1:?dest}; mkdir -p "$D/repo"; cd "$D/repo"
git init -q -b main; git config user.email t@example.test; git config user.name t
mkdir -p package; echo base > README.md; git add -A; git commit -qm base; BASE=$(git rev-parse HEAD)
echo "# Результат" > package/X.md; git add -A; git commit -qm x; HEAD=$(git rev-parse HEAD)
cat > "$D/naryad.json" <<X
{"step":"A-99","scope":{"kind":"package","id":"demo-1"},"inputs":[],"where":"package/X.md","template":"немає","attempt":1,"client_data":"none",
 "check":{"mode":"auto","how":"Автоперевірка: усе гаразд. Людина: оцінює зміст."},"repo":{"url":"x","base_branch":"main","branch":"flow/a99"},"git":{"base":"$BASE","head":"$HEAD"}}
X
