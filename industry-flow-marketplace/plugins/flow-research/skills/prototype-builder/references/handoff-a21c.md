# Що A-21 віддає в A-21c (`showcase-content`)

A-21c працює **без доступу до Odoo** і без перезйомки; усе потрібне — у файлах `prototype-real/`.

| Артефакт | Зміст |
|---|---|
| `video/rec/<кліп>.mp4` + `<кліп>.json` | безперервні записи десктоп/телефон; `{ss, dur, ok, events[]}`, події `title`, `off`, `pain`, `focus` (лише для кліпів `rec_clips.mjs`; скриншот-кроки відео не створюють) (bbox у частках в'юпорта) з часом |
| `shoot/scenes` (`scenes.mjs`, `clips.mjs`, `scenario*.steps.mjs`) | сценарії й сцени з прив'язкою до кроків `SALES §6` |
| `facts.json` (корінь `prototype-real/`) | `checks[{scene,name,expected,ok}]` і стабільний словник `facts{<сцена>:{<ім'я>:значення}}` (ключ маркера `<!--fact:facts.<сцена>.<ім'я>-->`; `checks[]` позиційний, для маркерів не годиться) — значення з DOM по сцені; **єдине джерело чисел** у титрах і SHOW (розбіжність -> збірка A-21c падає) |
| `video/frames/<кліп>-N.png` | 2–3 кадри кожного кліпа з `video/rec/*.mp4` (ffmpeg) — для рецензента, який не відкриває відео (`reviewer-shots`) |
| `screens/`, `screens-mobile/` | скриншоти кроків (десктоп 1920×1080, DPR 1,33; телефон 1170×2532 у записі), `shoot/dom/*.json` |
| `shoot/console.log` | по рядку на кліп: тривалість, кадри, діалоги помилок, латиниця на екрані |
| `README.md` | покриття, імітації, «Відкинуто», посилання на PLAN і `complexity.md` |
| `ACCEPTED.md` | що саме прийнято (зразок/повний обсяг), SHA, дата — N-11; рішення людини, не AI |

Не віддавати: `shoot/.cookies.json`, `shoot/.db_stamp`, `odoo-serve.log` (сесійні cookie; `.gitignore` зрізу: `shoot/.cookies.json`, `shoot/.db_stamp`, `shoot/odoo-serve.log`).

Умови: `check_ui_text.py` зелений; консоль чиста; `facts.json` без `ok:false`; дані лише вигадані; `internal-raw` у матеріалах немає. Бренд ToDo, формати 16:9/9:16, SHOW — A-21c.
