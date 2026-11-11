# Зразок на погодження і перемонтаж без перезйомки (N-18, К-10)

## Зразок (`params.sample: true`)
Перед повним обсягом — **15 с + 1 кадр титра**: `node scripts/build_video.mjs --root <prototype-real> full --sample [--intake docs/industries/<галузь>/OWNER-INTAKE.md]` → `video/sample-<slug>-16x9.mp4` (і `-9x16`, якщо Reels у анкеті) та `video/sample-title-*.png`; `check_video.py --sample` (10–20 с). Далі `result: waiting_human`, `waiting_for {role: Власник продукту, what: "прийняти зразок (стиль титрів, бренд, динаміка)", resume: {step: A-21c, params: {sample: false}}}`. Зауваження щодо стилю надходять на зразку, а не на готовому обсязі. Повний обсяг без прийнятого зразка не ставити.

## Перемонтаж (зміна титрів, порядку, довжини, бренд-кіту)
1. Лише правка `captions.yaml` / `SHOW.tpl.md` → `build_video.mjs` / `make_show.mjs`. Запис не чіпати, Odoo не відкривати.
2. Потрібен фрагмент, якого в `video/rec/` немає або `to` > тривалості запису → повернення в A-21 з причиною («потрібна перезйомка: <сцена>, <що не видно>»).
3. Схвалене — за `accepted-format.md` (A/B «було / стало»).
4. Після збірки: `check_video.py` (VID-*), `check_facts.py`, `check_brand.py`, `check_privacy.py`; кадри для рецензента — `video/frames/` (генерує `check_video.py`).
