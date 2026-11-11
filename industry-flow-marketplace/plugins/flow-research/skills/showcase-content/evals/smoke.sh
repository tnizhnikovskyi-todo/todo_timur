#!/usr/bin/env bash
# Димові перевірки showcase-content на згенерованих фікстурах (бінарників у репо немає): ffmpeg lavfi + Playwright.
# Запуск з будь-якого місця: bash evals/smoke.sh [робоча-тека]. Потрібні ffmpeg/ffprobe, node, playwright (NODE_PATH, якщо глобально), python3.
# Очікування: ok-фікстури -> код 0; bad-фікстури -> код 1. Підсумок — рядки PASS/FAIL, код виходу 1, якщо хоч один очікуваний результат не збігся.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; SK="$(dirname "$HERE")"; S="$SK/scripts"; FX="$HERE/fixtures"
W="${1:-$(mktemp -d)}"; mkdir -p "$W"; FAILS=0
expect() { # <очікуваний код> <назва> <команда…>
  local want="$1" name="$2"; shift 2; "$@" >"$W/last.log" 2>&1; local got=$?
  if [ "$got" -eq "$want" ]; then echo "PASS  $name (код $got)"; else echo "FAIL  $name (очікувався $want, отримано $got)"; tail -8 "$W/last.log"; FAILS=$((FAILS+1)); fi
}
mk() { # <тека> <фікстура>: чиста prototype-real з текстовими файлами фікстури + живі записи testsrc2
  local d="$W/$1"; rm -rf "$d"; mkdir -p "$d/video/rec" "$d/screens" "$d/screens-mobile"; cp "$FX/$2"/* "$d/" 2>/dev/null; cp "$FX/common/OWNER-INTAKE.md" "$W/OWNER-INTAKE.md"
  ffmpeg -v error -y -f lavfi -i "testsrc2=s=1920x1080:r=30:d=12" -c:v libx264 -pix_fmt yuv420p "$d/video/rec/D_demo.mp4"
  ffmpeg -v error -y -f lavfi -i "testsrc2=s=1170x2532:r=30:d=8" -c:v libx264 -pix_fmt yuv420p "$d/video/rec/M_demo.mp4"
  echo '{"ss":0,"dur":12,"ok":true,"events":[]}' > "$d/video/rec/D_demo.json"; echo '{"ss":0,"dur":8,"ok":true,"events":[]}' > "$d/video/rec/M_demo.json"
  ffmpeg -v error -y -f lavfi -i "testsrc2=s=1920x1080" -frames:v 1 "$d/screens/a.png"; ffmpeg -v error -y -f lavfi -i "testsrc2=s=780x1688" -frames:v 1 "$d/screens-mobile/m.png"
}
# 1. montage ok -> зразок + check_video ok
mk ok montage-ok
expect 0 "build_video --sample (montage-ok) + check_video" node "$S/build_video.mjs" --root "$W/ok" all --sample --intake "$W/OWNER-INTAKE.md"
expect 0 "check_video.py --sample на зібраних відео" python3 -I "$S/check_video.py" "$W/ok/video" --intake "$W/OWNER-INTAKE.md" --sample --no-frames
# 2. статичне відео 5 с -> VID-freeze FAIL
mk bad check_video-bad; ffmpeg -v error -y -f lavfi -i "color=c=0x336699:s=1920x1080:r=30:d=5" -c:v libx264 -pix_fmt yuv420p "$W/bad/video/sample-bad-16x9.mp4"
cp "$FX/montage-ok/captions.yaml" "$W/bad/captions.yaml"
expect 1 "check_video.py на статичному відео (очікується FAIL)" python3 -I "$S/check_video.py" "$W/bad/video" --intake "$W/OWNER-INTAKE.md" --sample
grep -q '"VID-freeze"' "$W/last.log" && grep -B1 -A2 'VID-freeze' "$W/last.log" | grep -q FAIL && echo "PASS  VID-freeze = FAIL на статичному відео" || { echo "FAIL  VID-freeze не FAIL на статичному"; FAILS=$((FAILS+1)); }
# 3. титр 1,0 с < 1,5 -> montage падає
mk mbad montage-bad; expect 1 "montage на титрі 1,0 с (очікується помилка)" node "$S/build_video.mjs" --root "$W/mbad" full --sample
# 4. факт відсутній / ok:false -> падає
mk nofact montage-ok; sed -i 's/"margin": "31,5 %", //' "$W/nofact/facts.json"; expect 1 "montage без факта margin (очікується помилка)" node "$S/montage.mjs" --root "$W/nofact" full --sample
mk badchk montage-ok; sed -i 's/"ok": true/"ok": false/' "$W/badchk/facts.json"; expect 1 "facts.json з ok:false (очікується помилка)" node "$S/montage.mjs" --root "$W/badchk" full --sample
# 5. SHOW: ok і число не з facts.json
mk show make_show-ok; expect 0 "make_show (ok)" node "$S/make_show.mjs" --root "$W/show"
grep -q 'fact:D_demo.margin\|fact:facts.D_demo.margin' "$W/show/SHOW.md" && echo "PASS  SHOW.md має маркери фактів" || { echo "FAIL  у SHOW.md немає маркерів фактів"; FAILS=$((FAILS+1)); }
[ -s "$W/show/SHOW.pdf" ] && echo "PASS  SHOW.pdf створено" || { echo "FAIL  SHOW.pdf немає"; FAILS=$((FAILS+1)); }
mk showbad make_show-bad; expect 1 "make_show з числом поза facts.json (очікується помилка)" node "$S/make_show.mjs" --root "$W/showbad" --no-pdf
# 6. зображення для SHOW
expect 0 "make_images" node "$S/make_images.mjs" --root "$W/show"
echo "---"; [ "$FAILS" -eq 0 ] && echo "SMOKE: усе як очікувалось ($W)" || echo "SMOKE: розбіжностей $FAILS ($W)"; exit $([ "$FAILS" -eq 0 ] && echo 0 || echo 1)
