#!/usr/bin/env bash
# Самоперевірка preflight.sh: усі 8 профілів, --needs, --step, невідомий профіль. Код 0 = ок. Використання: bash selftest_preflight.sh
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; fail=0
st() { python3 -I -c 'import json,sys; d={r["id"]:r["status"] for r in json.load(sys.stdin)}; print(d.get(sys.argv[1],"-"))' "$1"; }
chk() { # назва, очікуваний статус id, id, аргументи...
  local name="$1" want="$2" id="$3"; shift 3
  local got; got="$(env -i PATH="$PATH" bash "$D/preflight.sh" "$@" 2>/dev/null | st "$id")"
  [[ "$got" == "$want" ]] && echo "ok   $name: $id=$got" || { echo "FAIL $name: $id=$got (очікувалось $want)"; fail=1; }
}
for p in research outreach drive mail; do chk "$p" PASS profile --profile $p; chk "$p" SKIP odoo19 --profile $p; chk "$p" SKIP playwright --profile $p; done
chk base SKIP playwright --profile base; chk base FAIL odoo19 --profile base; chk base SKIP ffmpeg --profile base
chk repo SKIP playwright --profile repo; chk repo SKIP ffmpeg --profile repo; chk repo FAIL odoo19 --profile repo
chk content SKIP odoo19 --profile content; chk content FAIL playwright --profile content
chk research-internal FAIL sources-push --profile research-internal; chk research-internal SKIP odoo19 --profile research-internal
chk needs FAIL playwright --profile repo --needs odoo,browser; chk needs SKIP odoo19 --profile repo --needs browser
chk step FAIL odoo19 --profile repo --step A-21; chk step2 SKIP odoo19 --profile repo --step A-21c; chk unknown WARN profile --profile zzz; chk unknown FAIL odoo19 --profile zzz
chk step3 FAIL sources-push --profile research-internal --step A-05; chk step3 SKIP sources-push --profile research --step A-05
chk none WARN sources-push
chk none WARN core-deps-script --needs odoo
exit $fail
