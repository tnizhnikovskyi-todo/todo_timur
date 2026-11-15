#!/usr/bin/env bash
# bootstrap.sh <тека-цільового-репо> [--force]
# Стартовий набір тесту етапу 1 пакета скілів industry-flow (без Odoo, галузь «меблі»).
# Робить: (1) копіює пакет industry-flow-marketplace (без _work/) у <ціль>/industry-flow-marketplace/;
#         (2) кладе кожен скіл пакета в <ціль>/.claude/skills/<скіл>/ (копія, не symlink);
#         (3) кладе агентів flow-core/agents/*.md у <ціль>/.claude/agents/;
#         (4) копіює template/ у корінь цілі (наявні файли не перезаписує без --force).
# Режими для наявного репо (з історією нарядів і звітів, напр. «меблі»; стартувати з гілки, де ця історія, напр. flow/A-12-2-test, а не з main):
#   (без прапорців) наявні шаблони, CLAUDE.md і наряди не чіпає; нові файли додає.
#   --upgrade  оновлення до нової версії пакета: завжди перегенерує CLAUDE.md і TEST-START.md; наряд, якого немає, копіює;
#              якщо <крок>.yaml (чи <крок>-N.yaml) уже є і його skill_ref застарів — кладе <крок>-<N+1>.yaml з attempt: N+1
#              (N — найбільший номер спроби серед нарядів і звітів), старі наряди й звіти не чіпає; чинний (той самий skill_ref) пропускає.
#   --force    перезаписує шаблони (CLAUDE.md, TEST-START, наряди) як є, з attempt: 1 — лише для нового репо; для наявного репо з історією — --upgrade.
#   В обох режимах flow/decisions.md, flow/params*, docs/**, package/DATA_POLICY.md не чіпаються.
# Ідемпотентний: повторний запуск оновлює копію пакета, скіли й агентів; шаблони не чіпає без --force/--upgrade.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_PKG="${FLOW_PKG_SRC:-$KIT_DIR/../industry-flow-marketplace}"
TEMPLATE="$KIT_DIR/template"

FORCE=0
UPGRADE=0
TARGET=""
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    --upgrade) UPGRADE=1 ;;
    -h|--help) sed -n 2,14p "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Невідомий прапорець: $a" >&2; exit 2 ;;
    *) if [ -z "$TARGET" ]; then TARGET="$a"; else echo "Забагато аргументів" >&2; exit 2; fi ;;
  esac
done

[ "$FORCE$UPGRADE" != "11" ] || { echo "--force і --upgrade разом не можна" >&2; exit 2; }
[ -n "$TARGET" ] || { echo "Використання: bootstrap.sh <тека-цільового-репо> [--force|--upgrade]" >&2; exit 2; }
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
tar -C "$SRC_PKG" --exclude=./_work --exclude=./.git --exclude=__pycache__ -cf - . | tar -C "$DEST_PKG" -xf -

# 2. Скіли: кожен plugins/*/skills/<скіл>/ -> .claude/skills/<скіл>/ (копія)
mkdir -p "$TARGET/.claude/skills" "$TARGET/.claude/agents"
n_skills=0
for sk in "$SRC_PKG"/plugins/*/skills/*/; do
  [ -f "${sk}SKILL.md" ] || continue
  name="$(basename "$sk")"
  rm -rf "$TARGET/.claude/skills/$name"
  cp -R "${sk%/}" "$TARGET/.claude/skills/$name"
  find "$TARGET/.claude/skills/$name" -name __pycache__ -type d -prune -exec rm -rf {} +
  n_skills=$((n_skills + 1))
done

# 3. Агенти
n_agents=0
for ag in "$SRC_PKG"/plugins/flow-core/agents/*.md; do
  [ -f "$ag" ] || continue
  cp -f "$ag" "$TARGET/.claude/agents/$(basename "$ag")"
  n_agents=$((n_agents + 1))
done

START_BR=""; [ "$UPGRADE" = 1 ] && START_BR="$(git -C "$TARGET" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"; [ "$START_BR" != HEAD ] || START_BR=""
# 4. Шаблони (без перезапису наявних, якщо немає --force)
n_new=0; n_skip=0; n_over=0; skipped_list=""
while IFS= read -r -d '' f; do
  rel="${f#"$TEMPLATE"/}"
  dst="$TARGET/$rel"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ]; then
    case "$rel" in
      flow/decisions.md|flow/params*|docs/*|package/DATA_POLICY.md) n_skip=$((n_skip + 1)); skipped_list="$skipped_list $rel"; continue ;;
    esac
    if [ "$UPGRADE" = 1 ] && [ "$rel" = "flow/ARTIFACTS.md" ] && ! grep -q "умова" "$dst"; then cp -f "$f" "$dst"; n_over=$((n_over + 1))
    elif [ "$UPGRADE" = 1 ] && [ "$rel" = "TEST-START.md" ]; then cp -f "$f" "$dst"; n_over=$((n_over + 1))
    elif [ "$FORCE" = 1 ]; then cp -f "$f" "$dst"; n_over=$((n_over + 1))
    else n_skip=$((n_skip + 1)); skipped_list="$skipped_list $rel"; fi
  else
    cp "$f" "$dst"; n_new=$((n_new + 1))
    # --upgrade: нові наряди з base_branch = гілка старту (для репо з історією це не main)
    if [ "$UPGRADE" = 1 ] && [ -n "$START_BR" ]; then case "$rel" in tests/naryad/*.yaml) sed -i "s#base_branch: main#base_branch: $START_BR#" "$dst" ;; esac; fi
  fi
done < <(find "$TEMPLATE" -type f -print0 | sort -z)

# 4a. --upgrade: наряди, що вже є (<крок>.yaml / <крок>-N.yaml) і мають застарілий skill_ref -> <крок>-<N+1>.yaml
n_att=0; att_list=""; diff_list=""
if [ "$UPGRADE" = 1 ]; then
  for f in "$TEMPLATE"/tests/naryad/*.yaml; do
    [ -f "$f" ] || continue
    stem="$(basename "$f" .yaml)"
    tdir="$TARGET/tests/naryad"
    [ -e "$tdir/$stem.yaml" ] || continue            # відсутній — уже скопійований кроком 4
    want="$(grep -m1 '^skill_ref:' "$f" || true)"
    cur=0
    for e in "$tdir/$stem.yaml" "$tdir/$stem"-[0-9]*.yaml; do
      [ -f "$e" ] || continue
      if [ -n "$want" ] && grep -qxF "$want" "$e"; then cur=1; fi
    done
    if [ "$cur" = 1 ]; then                            # чинний наряд цієї версії вже є — але вміст міг змінитись у межах версії
      norm() { grep -vE '^(attempt:|repo:)' "$1"; }
      same=0
      for e in "$tdir/$stem.yaml" "$tdir/$stem"-[0-9]*.yaml; do
        [ -f "$e" ] || continue
        grep -qxF "$want" "$e" || continue
        if [ "$(norm "$e")" = "$(norm "$f")" ]; then same=1; fi
      done
      [ "$same" = 1 ] || diff_list="$diff_list $stem"
      continue
    fi
    mx=1
    for e in "$tdir/$stem"-[0-9]*.yaml; do
      [ -f "$e" ] || continue
      k="$(basename "$e" .yaml)"; k="${k##*-}"; case "$k" in *[!0-9]*) continue ;; esac
      [ "$k" -le "$mx" ] || mx="$k"
    done
    for e in "$TARGET"/tests/reports/"$stem"-[0-9]*.md; do
      [ -f "$e" ] || continue
      k="$(basename "$e" .md)"; k="${k##*-}"; case "$k" in *[!0-9]*) continue ;; esac
      [ "$k" -le "$mx" ] || mx="$k"
    done
    for e in "$tdir/$stem.yaml" "$tdir/$stem"-[0-9]*.yaml; do
      [ -f "$e" ] || continue
      k="$(grep -m1 '^attempt:' "$e" | sed 's/[^0-9]//g')"
      case "$k" in ''|*[!0-9]*) continue ;; esac
      [ "$k" -le "$mx" ] || mx="$k"
    done
    nx=$((mx + 1))
    sed -e "s#base_branch: main#base_branch: ${START_BR:-main}#" -e "s/^attempt: .*/attempt: $nx/" -e "s#^\(repo: .*branch: flow/\)$stem-test#\1$stem-$nx-test#" "$f" > "$tdir/$stem-$nx.yaml"
    n_att=$((n_att + 1)); att_list="$att_list $stem-$nx.yaml"
  done
fi

# 4b. CLAUDE.md генерується з пакетного шаблону (єдине джерело: flow-core/references/templates/test-CLAUDE.md)
CTPL="$SRC_PKG/plugins/flow-core/references/templates/test-CLAUDE.md"
if [ -f "$CTPL" ]; then
  if [ ! -e "$TARGET/CLAUDE.md" ] || [ "$FORCE" = 1 ] || [ "$UPGRADE" = 1 ]; then
    sed -e '/^> Шаблон лежить у пакеті/d' -e 's/<галузь>/mebli/g' -e 's/<код>/mebli/g' "$CTPL" > "$TARGET/CLAUDE.md"
    echo "  CLAUDE.md: згенеровано з пакетного шаблону"
  else
    echo "  CLAUDE.md: наявний, не чіпав (--upgrade або --force)"
  fi
fi

# .gitignore: _input/ лишається поза git (sources-format.md); дописати, якщо рядка немає
GI="$TARGET/.gitignore"
touch "$GI"
grep -qxF 'docs/industries/*/_input/' "$GI" || printf '\n# bootstrap: робочі вхідні файли кроків (поза git)\ndocs/industries/*/_input/\n' >> "$GI"

echo "bootstrap: готово -> $TARGET"
echo "  пакет:   $DEST_PKG (без _work/)"
echo "  скілів:  $n_skills у .claude/skills/"
echo "  агентів: $n_agents у .claude/agents/"
if [ "$UPGRADE" = 1 ] && [ -e "$TARGET/START-HERE.md" ]; then echo "  УВАГА: START-HERE.md застарів (не оновлюється --upgrade) — онови або видали"; fi
echo "  нові спроби нарядів (--upgrade): $n_att$att_list"
if [ -n "$diff_list" ]; then echo "  УВАГА: наряд відрізняється від шаблону при тому самому skill_ref (змінено в межах версії; звіту ще немає — заміни вручну, є звіт — нова спроба):$diff_list"; fi
echo "  шаблони: нових $n_new, пропущено наявних $n_skip, перезаписано $n_over"
if [ -n "$skipped_list" ]; then echo "  пропущені (наявні; --force перезапише):$skipped_list"; fi
echo "Далі: прочитай TEST-START.md; закоміть результат (git add -A && git commit)."
