#!/usr/bin/env bash
# Fetch pinned external tools listed in sources.tsv into vendor/<name>.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TSV="$DIR/sources.tsv"
declare -A seen
rc=0
want=("$@")
for n in "${want[@]}"; do
  if ! awk -F'\t' -v n="$n" '$1==n && $1!~/^#/ {f=1} END{exit !f}' "$TSV"; then
    echo "error: unknown source '$n'" >&2; exit 1
  fi
done
while IFS=$'\t' read -r name url commit license mode; do
  [[ -z "${name:-}" || "$name" == \#* || "$name" == "name" ]] && continue
  [[ "$mode" == "fetch" ]] || continue
  if ((${#want[@]})); then
    m=0; for n in "${want[@]}"; do [[ "$n" == "$name" ]] && m=1; done
    ((m)) || continue
  fi
  dest="$DIR/vendor/$name"
  short="${commit:0:7}"
  if [[ -d "$dest/.git" ]] && [[ "$(git -C "$dest" rev-parse HEAD 2>/dev/null || true)" == "$commit" ]]; then
    echo "$name: ok $short"; continue
  fi
  mkdir -p "$dest"
  [[ -d "$dest/.git" ]] || git -C "$dest" init -q
  git -C "$dest" remote remove origin 2>/dev/null || true
  git -C "$dest" remote add origin "$url"
  git -C "$dest" fetch -q --depth 1 origin "$commit"
  git -C "$dest" checkout -q --detach FETCH_HEAD
  echo "$name: fetched $short"
done < "$TSV"
