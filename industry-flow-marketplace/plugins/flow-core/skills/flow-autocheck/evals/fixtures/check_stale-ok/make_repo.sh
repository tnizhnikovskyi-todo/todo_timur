#!/usr/bin/env bash
# Фікстура check_stale (ok): залежності не змінювались після sha артефактів. Використання: make_repo.sh <тека>; друкує BASE=<sha>.
set -e; D=${1:?dest}; mkdir -p "$D/docs/industries/test/research"; cd "$D"
git init -q -b main; git config user.email t@example.test; git config user.name t
R=docs/industries/test
echo "анкета" > $R/OWNER-INTAKE.md; echo "факти" > $R/research/facts.yaml; echo "карта" > $R/research/FUNCTIONAL-MAP.md
git add -A; git commit -qm base; S=$(git rev-parse HEAD)
cat > $R/research/DEPENDS.yaml <<Y
artifacts:
  research/FUNCTIONAL-MAP.md:
    depends_on: [OWNER-INTAKE.md, research/facts.yaml]
    sha: $S
  research/BOX.md:
    depends_on: [research/FUNCTIONAL-MAP.md, research/facts.yaml]
    sha: $S
Y
echo "BOX" > $R/research/BOX.md; git add -A; git commit -qm box
echo "BASE=$(git rev-parse HEAD)"
