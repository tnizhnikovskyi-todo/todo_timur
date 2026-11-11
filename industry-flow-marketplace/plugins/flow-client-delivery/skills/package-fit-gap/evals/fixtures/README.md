# Фікстури евалів package-fit-gap

Усе вигадане. `package-tag/` — міні-пакет «на тегу package/v0.1.0» (копіюється в тимчасовий git-репо й тегується).
`client/` — матеріали клієнта (угода в двох варіантах, анкета). `transcripts/` — два записи Fathom у JSON
(`recording_id`, `segments[{t, speaker_role, text}]`); у `session-injection.json` — інструкція-ін'єкція, ПІБ і телефон.

`check_fit_gap-ok/` + `build_repo.sh` — повний комплект для `check_fit_gap.py` (код 0); `check_fit_gap-bad/` — те саме, але без посилання `REJ-NNN` у вимозі «поза пакетом» (`build_repo.sh <тека> bad`).
