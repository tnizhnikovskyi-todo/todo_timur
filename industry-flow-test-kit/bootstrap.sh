#!/usr/bin/env bash
# bootstrap.sh <тека-цільового-репо> [--force]
# Стартовий набір тесту етапу 1 пакета скілів industry-flow (без Odoo, галузь «меблі»).
# Робить: (1) копіює пакет industry-flow-marketplace (без _work/) у <ціль>/industry-flow-marketplace/;
#         (2) кладе кожен скіл пакета в <ціль>/.claude/skills/<скіл>/ (копія, не symlink);
#         (3) кладе агентів flow-core/agents/*.md у <ціль>/.claude/agents/;
#         (4) копіює template/ у корінь цілі (наявні файли не перезаписує без --force).
# Ідемпотентний: повторний запуск оновлює копію пакета, скіли й агентів; шаблони не чіпає без --force.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_PKG="${FLOW_PKG_SRC:-$KIT_DIR/../industry-flow-marketplace}"
TEMPLATE="$KIT_DIR/template"

FORCE=0
TARGET=""
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    -h|--help) sed -n 2,9p "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Невідомий прапорець: $a" >&2; exit 2 ;;
    *) if [ -z "$TARGET" ]; then TARGET="$a"; else echo "Забагато аргументів" >&2; exit 2; fi ;;
  esac
done

[ -n "$TARGET" ] || { echo "Використання: bootstrap.sh <тека-цільового-репо> [--force]" >&2; exit 2; }
[ -d "$SRC_PKG/plugins" ] || { echo "Немає пакета: $SRC_PKG (очікую plugins/)" >&2; exit 1; }
[ -d "$TEMPLATE" ] || { echo "Немає шаблонів: $TEMPLATE" >&2; exit 1; }
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"
SRC_PKG="$(cd "$SRC_PKG" && pwd)"
[ "$TARGET" != "$SRC_PKG" ] || { echo "Ціль збігається з джерелом пакета" >&2; exit 1; }
case "$TARGET/" in "$SRC_PKG"/*) echo "Ціль усередині пакета" >&2; exit 1 ;; esac

# 1. Пакет без _work/ (повна заміна копії; .git, якщо був у джерелі, не копіюється)
DEST_PKG="$TARGET/industry-flow-marketplace"
rm -rf "$DEST_PKG"
mkdir -p "$DEST_PKG"
tar -C "$SRC_PKG" --exclude=./_work --exclude=./.git -cf - . | tar -C "$DEST_PKG" -xf -

# 2. Скіли: кожен plugins/*/skills/<скіл>/ -> .claude/skills/<скіл>/ (копія)
mkdir -p "$TARGET/.claude/skills" "$TARGET/.claude/agents"
n_skills=0
for sk in "$SRC_PKG"/plugins/*/skills/*/; do
  [ -f "${sk}SKILL.md" ] || continue
  name="$(basename "$sk")"
  rm -rf "$TARGET/.claude/skills/$name"
  cp -R "${sk%/}" "$TARGET/.claude/skills/$name"
  n_skills=$((n_skills + 1))
done

# 3. Агенти
n_agents=0
for ag in "$SRC_PKG"/plugins/flow-core/agents/*.md; do
  [ -f "$ag" ] || continue
  cp -f "$ag" "$TARGET/.claude/agents/$(basename "$ag")"
  n_agents=$((n_agents + 1))
done

# 4. Шаблони (без перезапису наявних, якщо немає --force)
n_new=0; n_skip=0; n_over=0; skipped_list=""
while IFS= read -r -d '' f; do
  rel="${f#"$TEMPLATE"/}"
  dst="$TARGET/$rel"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ]; then
    if [ "$FORCE" = 1 ]; then cp -f "$f" "$dst"; n_over=$((n_over + 1))
    else n_skip=$((n_skip + 1)); skipped_list="$skipped_list $rel"; fi
  else
    cp "$f" "$dst"; n_new=$((n_new + 1))
  fi
done < <(find "$TEMPLATE" -type f -print0 | sort -z)

# .gitignore: _input/ лишається поза git (sources-format.md); дописати, якщо рядка немає
GI="$TARGET/.gitignore"
touch "$GI"
grep -qxF 'docs/industries/*/_input/' "$GI" || printf '\n# bootstrap: робочі вхідні файли кроків (поза git)\ndocs/industries/*/_input/\n' >> "$GI"

echo "bootstrap: готово -> $TARGET"
echo "  пакет:   $DEST_PKG (без _work/)"
echo "  скілів:  $n_skills у .claude/skills/"
echo "  агентів: $n_agents у .claude/agents/"
echo "  шаблони: нових $n_new, пропущено наявних $n_skip, перезаписано $n_over"
if [ -n "$skipped_list" ]; then echo "  пропущені (наявні; --force перезапише):$skipped_list"; fi
echo "Далі: прочитай TEST-START.md; закоміть результат (git add -A && git commit)."
