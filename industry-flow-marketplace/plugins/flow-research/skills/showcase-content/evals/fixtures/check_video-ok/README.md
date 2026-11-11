Фікстура check_video-ok: smoke.sh збирає зразок (--sample) через build_video.mjs з montage-ok (динамічний живий запис testsrc2 + заставки, 1920×1080 і 1080×1920, ≈15 с) і запускає check_video.py --sample. Очікується: код 0, VID-format/VID-freeze/VID-frames PASS.
Бінарні відео в репо не зберігаються (ліміт >1 MB): їх породжує evals/smoke.sh.
