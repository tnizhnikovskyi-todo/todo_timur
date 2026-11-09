# Контракт `transform.py` і `mapping.yaml`

Формат CSV шаблонів (UTF-8, `id`, `<field>/id`, `NN_<model>.csv`, `td/`) — `plugins/flow-package-build/references/master-data-format.md`
(копія для споживачів; власник — `flow-package-build:master-data-template-builder`, A-13; тут не копіюється). Доповнення клієнтського імпорту нижче.

## Доповнення до формату
- Простір імен external ID задає параметр `--ns`: **повне вивантаження (BA) — `mig_<к>`**, **пробна вибірка (AI) —
  `migtest_<к>`**. Вигляд: `<ns>.<model_slug>_<ключ джерела>`, `model_slug` = модель з крапками -> `_`. Пробні записи
  лишаються в `test-<к>` під `migtest_<к>.`, повне завантаження їх не перекриває, звірка їх не рахує
  (домен звірки — лише `mig_<к>.*`, `reconciliation.md`).
- Ключ джерела — внутрішній код старої системи (ключові колонки при маскуванні не чіпаються). Якщо єдиний ключ —
  ІПН/ЄДРПОУ/телефон/email, BA додає синтетичний стабільний код; хеш лишається запасним варіантом лише для
  повного вивантаження (`hash: true`, `sha1` від нормалізованого значення).
- Маски у вибірці: значення, що відповідає масці (`*_MASKED_NN`, `sha1:<hex>`), при `--ns migtest_*` НЕ трансформується
  (`digits`, `date`, `decimal` тощо до нього не застосовуються), а для полів із валідацією (vat, email, телефон) комірка
  лишається порожньою, кількість таких комірок іде в `totals.json` (`masked_skipped`). У повному вивантаженні масок немає.
- Посилання на довідники пакета — `td_md.<…>`; на довідники клієнта — `{ns}.<…>`.

## Виклик
```bash
python3 -I migration/transform.py --mapping migration/mapping.yaml --templates <тека_шаблонів_на_тегу> \
  --input <тека_вивантаження> --out <тека_вивантаження>/../out \
  --ns <mig_<к>|migtest_<к>>
```
Лише stdlib. Вихід — поза git (`_input/out/`): `NN_<model>.csv`, `errors.csv`, `dedup-report.csv`, `totals.json`.
Один скрипт для вибірки (AI) і повного вивантаження (BA); поведінка однакова, змінюється лише `--input`.

## mapping.yaml (ключі)
```yaml
client: <ідентифікатор>
package_tag: package/v0.1        # формат тегів — flow-core/references/id-patterns.md
files:
  - source: contractors.csv          # файл вивантаження
    template: 03_res.partner.csv     # файл шаблону на тегу
    key: {column: "Код", prefix: "{ns}.res_partner_", hash: false}   # hash: true -> sha1
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
