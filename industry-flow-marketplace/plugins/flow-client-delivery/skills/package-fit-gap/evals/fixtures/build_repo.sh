#!/bin/sh
# Збирає тимчасовий git-репо: package-tag/ (тег package/v0.1.0), business-case, угода, потім clients/k01 з check_fit_gap-ok/.
# Використання: sh evals/fixtures/build_repo.sh <нова тека> [ok|bad|bad-edition]  (друкує base=<SHA>)
# Далі в <теці>: python3 -I <скіл>/scripts/check_fit_gap.py --client k01 --tag package/v0.1.0 --base <SHA> \
#   --business-case docs/industries/furniture/business-case.md      ok -> код 0 (MANUAL лишаються); bad -> FG-rejected FAIL.
set -e
D="$1"; V="${2:-ok}"; HERE="$(cd "$(dirname "$0")" && pwd)"; K="$HERE/check_fit_gap-ok/clients/k01"
mkdir -p "$D"; cd "$D"; git init -q .; git config user.email t@t; git config user.name t
cp -r "$HERE/package-tag/package" .; mkdir -p docs/industries/furniture clients/k01
cp "$HERE/package-tag/docs/business-case.md" docs/industries/furniture/
printf 'clients/*/_input/\n' > .gitignore; cp "$K/discovery-agreement.md" clients/k01/
git add -A; git commit -qm pkg; git tag package/v0.1.0; BASE=$(git rev-parse HEAD)
BC=$(git log -1 --format=%H -- docs/industries/furniture/business-case.md | cut -c1-12)
for f in fit-gap.md questionnaire.md answers.yaml; do cp "$K/$f" clients/k01/; done
sed -i "s#business-case)#business-case, SHA $BC)#" clients/k01/fit-gap.md
if [ "$V" = bad-edition ]; then sed -i '/^edition:/d' clients/k01/answers.yaml; fi
if [ "$V" = bad ]; then sed -i 's# (див. REJ-001)##' clients/k01/fit-gap.md; fi
git add -A; git commit -qm fg
echo "base=$BASE"
