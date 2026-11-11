# Формат `captions.yaml` (prototype-real/captions.yaml)

Пише A-21c (чернетка — `scripts/captions_seed.mjs` із подій записів A-21). Єдине джерело структури обох відео й усіх титрів; перемонтаж = правка цього файла + `build_video.mjs`, без Odoo й без перезйомки. Підмножина YAML: мапи, списки, flow-запис `{k: v}` / `[a, b]`, рядки в лапках, `#` коментарі.

```yaml
version: 1
lang: uk
slug: <галузь>                    # video/<slug>-16x9.mp4, video/<slug>-9x16.mp4
cards:                            # заставки (rec_cards.mjs; шаблони references/cards/*.html)
  intro: {format: 16x9, secs: 7, lines: ["Біль 1 — **виділення**", "Біль 2"], headline: "ToDo показує, як ... веде **Odoo 19**", note: "Показ на вигаданих даних"}
  hook:  {tpl: hook, format: 9x16, secs: 3.3, kicker: "Власнику ...", headline: "Питання про **біль**?", sub: "Покажемо в Odoo"}
  outro: {format: 16x9, secs: 7.5, headline: "...", cta: "<з BRAND.md>", tagline: "Покажемо на **ваших даних**", note: "..."}
  outro_r: {tpl: outro, format: 9x16, secs: 6.5, headline: "...", cta: "...", tagline: "...", note: "..."}
formats:
  video_16x9:
    pieces:
      - {type: card, card: intro}
      - {type: desk, clip: D_dash, from: 0, to: 12, speed: 1, block: director, focus: [0.1, 0.2, 0.3, 0.2],
         titles: [{at: 0.4, secs: 3, kicker: "ВЛАСНИК", text: "Маржа **{{fact:margin}}** видно до підтвердження", pain: PAIN-03, sales: "SALES §2 №4"}]}
      - {type: phone, clip: M_sale, from: 0, to: 9, speed: 1.15, side: {kicker: "МЕНЕДЖЕР", pain: "біль ролі"},
         titles: [{at: 0.3, secs: 2.5, text: "Замовлення з телефона", big: "{{fact:margin}}", label: "маржа замовлення"}]}
      - {type: card, card: outro}
  reels_9x16:
    pieces:
      - {type: card, card: hook}
      - {type: reel, clip: M_sale, from: 0, to: 4.5, speed: 1.5, titles: [{at: 0.3, kicker: "МЕНЕДЖЕР", text: "Маржа {{fact:margin}} з телефона"}]}
      - {type: card, card: outro_r}
```

## Поля фрагмента (`pieces[]`)
| Поле | Зміст |
|---|---|
| `type` | `card` (заставка з `cards`), `desk` (десктоп-запис, 16:9), `phone` (телефон у рамці зліва + бічна панель, 16:9), `reel` (телефон ≈86 % ширини, 9:16) |
| `clip`, `from`, `to`, `speed` | запис `video/rec/<clip>.mp4` (+ `.json` з `ss`, `dur`), секунди від початку сценарію; `to ≤ dur` запису, інакше потрібна перезйомка (A-21); `speed` 0,5–3; тривалість фрагмента = `(to−from)/speed` ≥ 1,2 с |
| `scene` | сцена `facts.json` для `{{fact:ім'я}}` (типово = `clip`) |
| `block: director` | блок керівника (≈10 с сумарно на формат) |
| `focus: [x,y,w,h]` | частки в'юпорта (`focus`-події запису): наближення до ключової цифри |
| `side {kicker, pain}` | лише `phone`: заголовок ролі й біль (перший крок) |
| `titles[]` | `at` (с від початку фрагмента, у вихідному часі), `secs` (≥ 1,5; типово до кінця −0,3), `kicker`, `text` (`**виділення**`), `kind: title\|pain` (pain — на весь екран, лише десктоп), `top: true` (титр угорі), `big`+`label` (бічна цифра `phone`), `pain`/`sales` (довідково: PAIN-xx, рядок SALES) |

## Заповнювачі чисел
`{{fact:<сцена>.<ім'я>}}` або `{{fact:<ім'я>}}` (сцена фрагмента); `{{pl:<ключ>|форма-1|форма-2,3,4|форма-5+}}` — число з відмінюванням («1 замовлення, 3 замовлення, 5 замовлень»). Число з одиницею без заповнювача — WARN (`montage.mjs`) і FAIL у `check_facts.py`.

## Що збірка відхиляє (код 1)
факту немає / `checks[].ok:false`; титр < 1,5 с; титри накладаються; титр виходить за фрагмент; `to` > тривалості запису; немає запису чи картки; немає блока керівника; Reels без гачка; бічна цифра з іншої сцени.
