#!/usr/bin/env bash
# Хук кейсу: викликається з setup_repo.sh у теці тестового репо після базового коміту ($1 = тека кейсу).
# Гілка build/x з модулем td_edge (на гілці за замовчуванням його немає); crm.csv і README.md у _input/ (сусідні вхідні файли, поза git).
set -euo pipefail
git checkout -q -b build/x
cp -r "$1/branch-build-x/." .
git add -A; git commit -qm "build/x: td_edge"
git checkout -q -
printf 'edrpou\n' > docs/industries/furniture/_input/crm.csv
printf '# Вхід A-05 (вигаданий)\n' > docs/industries/furniture/_input/README.md
