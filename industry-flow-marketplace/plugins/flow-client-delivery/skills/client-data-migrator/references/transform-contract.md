# Контракт `transform.py` і `mapping.yaml`

Формат CSV шаблонів (UTF-8, `id`, `<field>/id`, `NN_<model>.csv`, `td/`) — `flow-package-build/references/master-data-format.md`
(власник — A-13; тут не копіюється). Доповнення клієнтського імпорту нижче.

## Доповнення до формату
- Префікс external ID клієнта: `mig_<к>.`; повний вигляд `mig_<к>.<model_slug>_<ключ джерела>`, `model_slug` = модель з крапками -> `_`.
- Ключ джерела — внутрішній код старої системи. Якщо єдиний ключ — ІПН/ЄДРПОУ/телефон/email, використовувати `sha1` від нормалізованого значення (в `id` не потрапляє сире значення ПД).
- Посилання на довідники пакета — `td_md.<…>`; на довідники клієнта — `mig_<к>.<…>`.

## Виклик
```bash
python3 -I migration/transform.py --mapping migration/mapping.yaml --templates <тека_шаблонів_на_тегу> \
  --input <тека_вивантаження> --out <тека_вивантаження>/../out
```
Лише stdlib. Вихід — поза git (`_input/out/`): `NN_<model>.csv`, `errors.csv`, `dedup-report.csv`, `totals.json`.
Один скрипт для вибірки (AI) і повного вивантаження (BA); поведінка однакова, змінюється лише `--input`.

## mapping.yaml (ключі)
```yaml
client: <ідентифікатор>
package_tag: v0.1.0
files:
  - source: contractors.csv          # файл вивантаження
    template: 03_res.partner.csv     # файл шаблону на тегу
    key: {column: "Код", prefix: "mig_<к>.res_partner_", hash: false}   # hash: true -> sha1
    columns:                          # колонка шаблону -> правило
      name: {from: "Назва", transform: strip}
      vat:  {from: "ЄДРПОУ", transform: digits}
      country_id/id: {const: "base.ua", why: "усі контрагенти в Україні за SOW"}
      x_edge_type: {from: "Тип кромки", map: {"ПВХ": "pvc"}, client_extension: true}   # поле доробки B-05
    dedup: {keys: ["vat", "normalized_name"], on_conflict: report}
    totals: {count: true, sums: []}
```
Правила: усі обов'язкові колонки шаблону є в `columns`; `const` — лише з `why`; значення без відповідника в
`map` -> `errors.csv` з `MISSING_REF`, а не вгадування; `client_extension: true` — поле поза шаблоном A-13
(доробка B-05), потребує модуля в базі.

## Трансформації
`strip`, `digits`, `date` (вхідний формат -> ISO), `decimal` (кома/крапка), `uom` (за довідником одиниць клієнта),
`upper`/`lower`, `map` (таблиця значень). Нових типів не вигадувати без запису в memo.

## Вихідні файли
| Файл | Колонки | Примітка |
|---|---|---|
| `errors.csv` | `file`, `row`, `code`, `column` | без значень полів; код: `DUP`, `INVALID`, `OUT_OF_SCOPE`, `MISSING_REF` |
| `dedup-report.csv` | `model`, `key_hash`, `count`, `resolution` | лише лічильники й хеші; `resolution`: `merged`/`conflict` |
| `totals.json` | `{ "<файл>": {"count": N, "sums": {"<показник>": X}} }` | BA переносить у колонки джерела |

Конфлікт дедуплікації (однакове ІПН, різні назви) не зливається мовчки: `resolution=conflict`, запис лишається
одним із кандидатів за правилом у `mapping.yaml`, рішення — PM/BA.
