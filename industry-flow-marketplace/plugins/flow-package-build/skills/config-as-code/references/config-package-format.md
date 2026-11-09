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
  install-log.md     (install-log-template.md)
  (майбутнє, у 0.1 НЕ постачається: install.sh, bin/apply.py, bin/validate.py -- див. «CLI-контракт»)
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
  kind: settings           # settings | config_param | record | group | automation | mail_template | cron | td_param (config-kinds-odoo19.md)
  anchor: "ir.config_parameter:[key=sale.x]:value"   # див. формат якоря
  transform: {"1": "...", "2": "...", "3": "..."}   # значення VP -> значення в Odoo (або identity)
  ac: [AC-03]
```
Трек `code`: `kind: td_param`, `anchor: "ir.config_parameter:[key=td_<пакет>.vp_xx]:value"` (`<пакет>` = `scope.id`, дефіси -> `_`),
у CONFIG.md позначка «реалізує модуль td_* (A-11)». Ключ за замовчуванням -- контракт до рішення A-11 (`WARN` у `checks`);
A-11 читає той самий ключ.

### Формат якоря
Єдиний формат: `<model>:<селектор>:<поле>`, де селектор -- `xml_id=<module.name>` або домен-скорочення `[поле=значення,...]`.
Read-back знаходить запис через `odoo_search_read` (для `xml_id=` -- спершу `ir.model.data`, далі `res_id`). Приклади за видами:
| kind | Якір |
|---|---|
| `config_param` | `ir.config_parameter:[key=sale.auto_done_setting]:value` |
| `td_param` | `ir.config_parameter:[key=td_<пакет>.vp_04]:value` |
| `record` | `res.company:xml_id=base.main_company:<поле>` |
| `group` | `res.groups:xml_id=td_config.<slug>:<поле>` або членство: `res.groups:xml_id=base.group_user:implied_ids` |
| `settings` | алгоритм нижче -- якір на місце зберігання, не на `res.config.settings` |
| `mail_template`, `cron`, `automation` | `<модель>:xml_id=td_config.<slug>:<поле>` |

**`settings` -- `res.config.settings` transient: після `execute()` читати з неї не можна.** Алгоритм визначення якоря:
через `odoo_get_fields res.config.settings` (і джерело з CONFIG.md) визначити, як поле зберігається:
- `config_parameter=<ключ>` -> `ir.config_parameter:[key=<ключ>]:value`;
- `related`/на `company_id` -> `res.company:xml_id=base.main_company:<поле компанії>`;
- `implied_group`/`group_*` -> членство `implied_ids` групи в `base.group_user` (або відповідній);
- `default_model`/`default_*` -> `ir.default` (`[field_id.model=..., field_id.name=...]`);
- не визначено -> пункт `manual` або `CFG-readback: MANUAL`; **не PASS**.

## Пункт даних (`data/NN_*.yaml`)
```yaml
- id: td_config.sale_order_policy        # власний xml-id: лише простір td_config.
  kind: settings|config_param|record|group|automation|mail_template|cron|td_param
  model: res.config.settings
  values: {<поле>: "{{VP-02}}"}          # літерал або {{VP-xx}}; посилання на записи -- xml-id
  ac: [AC-03]
  source: "<джерело Odoo 19 з CONFIG.md>"
  manual: false                          # true + reason: для того, що не виражається даними
  reason: ""
```

## CLI-контракт майбутніх скриптів (у 0.1 скриптів НЕМАЄ)
Контракт -- вимога до скриптів, коли їх випустять (беклог AI-інженера); до того на нього **не спираються** (C-03 пропускає job
конфігу з явним статусом, A-12 застосовує через odoo-mcp).
| Команда | Дія | Коди виходу |
|---|---|---|
| `bin/validate.py --answers <файл> [--schema package/templates/answers.yaml]` | без бази: YAML валідні, відповіді за схемою, `vp-map` <-> схема, модулі є в addons_path/переліку | 0 -- ок, 1 -- помилки валідації, 2 -- помилка запуску |
| `install.sh --db <db> --answers <файл> [--addons-path ...]` | validate -> установка модулів -> застосування -> JSON-підсумок | 0 -- ок, 1 -- помилка даних/установки, 2 -- помилка запуску |

JSON-підсумок: `{"created":N,"updated":N,"unchanged":N,"manual":N,"errors":[...]}`. Змінні оточення: `ODOO_BIN`, `ADDONS_PATH`.
Ідемпотентність: повторний запуск на тій самій базі -> `created=0, updated=0`.

## Заголовки CONFIG.md (grep-контракт)
`## Модулі до установки`, `## Параметри установки (VP-xx)`, `## Команда установки`, `## Ручні кроки`, `## Зміни версії`,
`## Відкриті питання`. Не перейменовувати: їх шукають (за grep у відповідних скілах) A-13, A-15, A-18, B-04, C-03.
