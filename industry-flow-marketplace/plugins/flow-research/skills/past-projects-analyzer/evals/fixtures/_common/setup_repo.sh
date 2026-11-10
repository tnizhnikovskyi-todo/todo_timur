#!/usr/bin/env bash
# Збирає тестовий git-репо кейсу: setup_repo.sh <case> <dest> [--track-sources]
# Якщо є <case>/setup.sh - викликає його (друга гілка, crm.csv/README.md). Копіює <case>/repo/, _common/decision.md, DATA_POLICY (allow або <case>/DATA_POLICY.md), sources.md у _input/ (поза git).
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"; c="$1"; d="$2"; mkdir -p "$d"; cd "$d"
git init -q; git config user.email t@example.invalid; git config user.name t
mkdir -p docs/industries/furniture/_input package
[ -d "$here/$c/repo" ] && cp -r "$here/$c/repo/." .
cp "$here/_common/decision.md" docs/industries/furniture/decision.md
cp "$here/${c}/DATA_POLICY.md" package/DATA_POLICY.md 2>/dev/null || cp "$here/_common/DATA_POLICY.allow.md" package/DATA_POLICY.md
cp "$here/$c/sources.md" docs/industries/furniture/_input/sources.md
[ "${3:-}" = "--track-sources" ] || echo 'docs/industries/*/_input/' > .gitignore
git add -A -f >/dev/null; [ "${3:-}" = "--track-sources" ] || git rm -q --cached -r docs/industries/furniture/_input
git commit -qm fixture
[ -f "$here/$c/setup.sh" ] && bash "$here/$c/setup.sh" "$here/$c" >&2   # опційний хук кейсу (гілки, сусідні файли _input/)
git rev-parse --short HEAD
