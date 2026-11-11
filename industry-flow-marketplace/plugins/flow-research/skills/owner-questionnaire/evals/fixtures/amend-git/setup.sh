#!/bin/sh
# Міні-git-фікстура режиму amend: bash setup.sh <тека>; далі запустити check_stale.py (шлях до скрипта — аргумент $2, за замовчуванням plugins/flow-core/...)
set -e
T="${1:?тека}"; S="${2:-plugins/flow-core/skills/flow-autocheck/scripts/check_stale.py}"
mkdir -p "$T/docs/industries/x/research" && cd "$T" && git init -q . && git config user.email t@t && git config user.name t
printf 'editions: ce\n' > docs/industries/x/OWNER-INTAKE.md
printf 'концепція\n' > docs/industries/x/concept.md
git add -A && git commit -qm base && B=$(git rev-parse HEAD)
printf 'artifacts:\n  concept.md:\n    depends_on: [OWNER-INTAKE.md]\n    sha: %s\n' "$B" > docs/industries/x/research/DEPENDS.yaml
git add -A && git commit -qm depends
printf 'editions: both\n' > docs/industries/x/OWNER-INTAKE.md      # незакомічена зміна
echo "--- до коміту (очікуємо PASS: зміна невидима, WARN у memo)"; python3 -I "$S" docs/industries/x/research/DEPENDS.yaml --base HEAD || true
git add -A && git commit -qm amend
echo "--- після коміту (очікуємо FAIL зі списком: concept.md)"; python3 -I "$S" docs/industries/x/research/DEPENDS.yaml --base HEAD || true
