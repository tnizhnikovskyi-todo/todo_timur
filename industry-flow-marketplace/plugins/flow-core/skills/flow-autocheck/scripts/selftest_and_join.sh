#!/usr/bin/env bash
# selftest and-join-merge (0.4.2): AND-split A-17b ∥ A-17c; flow/state.md на обох гілках = конфлікт (старий порядок),
# лише flow/runs/<наряд>.md на гілках + export state.md після merge у стику = без конфлікту.
set -eu
T=$(mktemp -d); cd "$T"; git init -q -b A17; git config user.email t@t; git config user.name t
mkdir -p flow/runs; echo base > flow/state.md; git add -A; git commit -qm base
for b in b c; do
  git checkout -q -b "A-17$b" A17
  echo "$b" > "res-$b.txt"; git add -A; git commit -qm "result $b"
  mkdir -p flow/runs; echo "run $b" > "flow/runs/A-17$b.md"; git add -A; git commit -qm "record $b (лише runs)"
done
git checkout -q -b join A-17c; git merge --no-ff -q A-17b -m join || { echo "FAIL: merge без state.md не пройшов"; exit 1; }
echo "export" > flow/state.md; git add -A; git commit -qm "export state після стику"
# негатив: state.md на обох гілках конфліктує
git checkout -q -b old-b A17; echo b > flow/state.md; git commit -qam "state b"
git checkout -q -b old-c A17; echo c > flow/state.md; git commit -qam "state c"
if git merge --no-ff -q old-b -m x 2>/dev/null; then echo "FAIL: очікувався конфлікт"; exit 1; fi
echo "selftest and-join-merge OK"
