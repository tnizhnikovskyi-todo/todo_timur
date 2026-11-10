#!/usr/bin/env bash
# Відновлює робочі вхідні файли кроків (docs/industries/*/_input/ поза git) з шаблонів tests/input-templates/.
# Наявні файли не перезаписує. Запускати на початку кожної нової сесії.
set -euo pipefail
cd "$(dirname "$0")/.."
for src in tests/input-templates/*/; do
  ind=$(basename "$src"); dst="docs/industries/$ind/_input"; mkdir -p "$dst"
  for f in "$src"*; do
    [ -e "$dst/$(basename "$f")" ] && echo "є: $dst/$(basename "$f")" || { cp "$f" "$dst/"; echo "відновлено: $dst/$(basename "$f")"; }
  done
done
