# Формат конфіг-пакета `package/config/`

Пропозиція за замовчуванням; рішення про формат приймає Архітектор у A-10 (розділ ALLOCATION). Цей файл -- нормативний
для `config-as-code`; на нього спираються `ci-pipeline-builder`, `runbook-executor`, `demo-base-builder`,
`package-release-builder`, `package-upgrade-runner`.

## Структура
```
package/config/
  CONFIG.md          зміст config-spec + розділи-контракти (config-md-additions.md)
  manifest.yaml      версія формату, Odoo, редакція, модулі, порядок файлів даних
  vp-map.yaml        VP-xx -> {track, kind, anchor, transform, ac}
  data/NN_<область>.yaml
  install.sh  bin/apply.py  bin/validate.py   копії зі скіла (заголовок з версією скіла); у пакеті не редагуються
  install-log.md     (install-log-template.md)
package/addons/<готове>/                      вендорене (vendoring.md)
```

## manifest.yaml
```yaml
format: 1
odoo: "19.0"
edition: ce|ee
modules:                  # порядок = порядок установки
  - {name: sale_management, source: standard, ac: [AC-01]}
  - {name: ready_x, source: vendored, ac: [AC-09], path: package/addons/ready_x}
data_files: [data/10_settings.yaml, data/20_groups.yaml]
```
`source`: `standard` | `config` | `vendored`. Усі `name` -- технічні імена з ALLOCATION (колонка «модуль Odoo»).

## vp-map.yaml
```yaml
VP-02:
  track: config            # standard | config | ready | code
  kind: settings           # settings | config_param | field | ... (config-kinds-odoo19.md); для code -- td_param
  anchor: "res.config.settings:<поле>"   # див. формат якоря
  transform: {"1": "...", "2": "...", "3": "..."}   # значення VP -> значення в Odoo (або identity)
  ac: [AC-03]
```
Трек `code`: `kind: td_param`, `anchor: "ir.config_parameter:<td-ключ>"`, у CONFIG.md позначка «реалізує модуль td_* (A-11)».
Відкрите питання: ключ `td_param` узгодити з A-11.

### Формат якоря
`<model>:<xml_id>` або `<model>:[домен]:<поле>` -- за ним read-back знаходить запис через `odoo_search_read`.
Для `res.config.settings` значення читається з місця, куди його пише `execute()` (див. apply-semantics.md).

## Пункт даних (`data/NN_*.yaml`)
```yaml
- id: td_config.sale_order_policy        # власний xml-id: лише простір td_config.
  kind: settings|config_param|record|group|automation|mail_template|cron
  model: res.config.settings
  values: {<поле>: "{{VP-02}}"}          # літерал або {{VP-xx}}; посилання на записи -- xml-id
  ac: [AC-03]
  source: "<джерело Odoo 19 з CONFIG.md>"
  manual: false                          # true + reason: для того, що не виражається даними
  reason: ""
```

## CLI-контракт (на нього спирається C-03)
| Команда | Дія | Коди виходу |
|---|---|---|
| `bin/validate.py --answers <файл> [--schema package/templates/answers.yaml]` | без бази: YAML/XML/CSV валідні, відповіді за схемою, `vp-map` <-> схема, модулі є в addons_path/переліку | 0 -- ок, 1 -- помилки валідації, 2 -- помилка запуску |
| `install.sh --db <db> --answers <файл> [--addons-path ...]` | validate -> установка модулів -> `apply.py` -> JSON-підсумок | 0 -- ок, 1 -- помилка даних/установки, 2 -- помилка запуску |

JSON-підсумок: `{"created":N,"updated":N,"unchanged":N,"manual":N,"errors":[...]}`. Змінні оточення: `ODOO_BIN`, `ADDONS_PATH`.
Ідемпотентність: повторний запуск на тій самій базі -> `created=0, updated=0`.
Скрипти в цій версії скіла не постачаються (відкрите питання в SKILL.md): контракт -- вимога до них.

## Заголовки CONFIG.md (grep-контракт)
`## Модулі до установки`, `## Параметри установки (VP-xx)`, `## Команда установки`, `## Ручні кроки`, `## Зміни версії`,
`## Відкриті питання`. Не перейменовувати: їх шукають A-13, A-14, A-15, B-04, C-03.
