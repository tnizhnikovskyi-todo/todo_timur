#!/usr/bin/env bash
# Друкує start_sha. Викликається перед запуском евала; потребує git.
set -euo pipefail
dst="$1"; mode="$2"; here="$(cd "$(dirname "$0")" && pwd)"
rm -rf "$dst"; mkdir -p "$dst/docs/industries/furniture"; cp -r "$here/results-happy/demand" "$here/results-happy/concept" "$dst/docs/industries/furniture/"
cd "$dst"; git init -q -b main; git config user.email t@example.com; git config user.name tester
git add -A; git commit -qm "prep: thresholds merged"; start=$(git rev-parse HEAD)
t=docs/industries/furniture/demand/thresholds.md
case "$mode" in
  clean) ;;
  frozen-edit) sed -i 's/| Р3 | заявка | 3 |/| Р3 | заявка | 1 |/' "$t"; git commit -qam "tweak thresholds" ;;
  shallow-missing) start=0123456789abcdef0123456789abcdef01234567 ;;
esac
echo "$start"
