# Формат конфіг-пакета `package/config/`

Пропозиція за замовчуванням; рішення про формат приймає Архітектор у A-10 (розділ ALLOCATION). Цей файл -- нормативний
для `config-as-code`; на нього спираються `ci-pipeline-builder`, `runbook-executor`, `demo-base-builder`,
`package-release-builder`, `package-upgrade-runner`.

## Структура
```
package/config/
  CONFIG.md          зміст config-spec + розділи-контракти (config-md-additions.md)
  manifest.yaml      версія формату (2), Odoo, профілі модулів на редакції `edition_profiles`, порядок файлів даних
  vp-map.yaml        VP-xx -> {track, kind, anchor, transform, ac}; параметри `edition`, `contract_mode`
  data/NN_<область>.yaml
  install-log.md     (install-log-template.md; розділ на кожну редакцію)
  (еталони install.sh, apply.py, validate.py -- `flow-core/references/templates/tools-odoo/` (q17); C-00 копіює в `tools/odoo/`; сигнатури еталонів відрізняються від «CLI-контракту» нижче -- розбіжність у README «Лишається відкритим»)
package/addons/<готове>/                      вендорене (vendoring.md)
```

## manifest.yaml
```yaml
format: 2                 # 1 = старий плоский `modules:` з `edition:`; нові пакети -- лише 2
odoo: "19.0"
editions: both            # з docs/industries/<галузь>/OWNER-INTAKE.md (ce|ee|both); не вгадується
edition_profiles:         # ce завжди; ee -- при editions: both|ee; ee ⊇ ce
  ce:
    modules:              # порядок = порядок установки
      - {name: sale_management, origin: std-ce, source: standard, ac: [AC-01]}
      - {name: td_mebli_core, origin: td, source: code, ac: [AC-02]}
      - {name: ready_x, origin: todo-ready, source: vendored, ac: [AC-09], path: package/addons/ready_x}
  ee:
    modules:              # усе з ce + EE + мости
      - {name: sale_management, origin: std-ce, source: standard, ac: [AC-01]}
      - {name: td_mebli_core, origin: td, source: code, ac: [AC-02]}
      - {name: ready_x, origin: todo-ready, source: vendored, ac: [AC-09], path: package/addons/ready_x}
      - {name: <EE-модуль>, origin: std-ee, source: standard, ac: [AC-12]}
      - {name: td_mebli_core_ee, origin: td, source: code, ac: [AC-12]}   # міст: auto_install, лише в ee
data_files: [data/10_settings.yaml, data/20_groups.yaml]
```
`origin` (хто автор): `std-ce` | `std-ee` | `td` (наш `td_*`, A-11) | `todo-ready` (готовий модуль ToDo з `REUSE.md`, A-03c, рішення «беремо/адаптуємо»; трек «готове» в ALLOCATION) | `integration` (інтеграційний/сторонній вендорений за q42).
`source` (як потрапляє): `standard` | `code` | `vendored`; відповідність: `std-ce`/`std-ee` ↔ `standard`; `td` ↔ `code`; `todo-ready`/`integration` ↔ `vendored` (`vendoring.md`). Поле `config` не є модулем -- у `modules:` не вноситься.
Правила: `std-ee` і `td_*_ee` -- лише в профілі `ee`; `td_*` ядра без EE у `depends`; жодної AGPL-залежності (`license` залежностей); при `editions: ce` ключа `ee` немає. Усі `name` -- технічні імена з ALLOCATION (колонка «модуль Odoo»).

## vp-map.yaml
```yaml
VP-02:
  track: config            # standard | config | ready | code
  kind: settings           # settings | config_param | record | group | automation | mail_template | cron | td_param (config-kinds-odoo19.md)
  anchor: "ir.config_parameter:[key=sale.x]:value"   # див. формат якоря
  transform: {"1": "...", "2": "...", "3": "..."}   # значення VP -> значення в Odoo (або identity)
  ac: [AC-03]
# параметри редакції і режиму договору -- звичайні VP-записи з default (kind: config_param/td_param за ALLOCATION):
edition:       {track: config, kind: td_param, anchor: "ir.config_parameter:[key=td_<пакет>.edition]:value", transform: identity, default: ce}   # ce|ee
contract_mode: {track: config, kind: td_param, anchor: "ir.config_parameter:[key=td_<пакет>.contract_mode]:value", transform: identity, default: "<від власника/ТР>"}
```
Перелік значень `contract_mode` скіл не вигадує (рішення власника, §21 №17). `edition` у `answers.yaml` має збігатися з профілем, на який застосовується пакет.
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

**`settings` -- `res.config.settings` transient: після `execute()` запис не читається, а `fields_get` не повертає `config_parameter`,
`implied_group`, `default_model`.** Спосіб read-back залежить від типу поля (`odoo_get_fields` з фільтром `type, relation, related`):
- поле `related` (`company_id.<поле>`) -> **лише** якір `res.company:xml_id=base.main_company:<поле компанії>` через `odoo_search_read`;
  модель і запис якоря брати з ланцюжка `related`, який повертає `odoo_get_fields`; `base.main_company` -- лише типовий випадок для `company_id.*` в однокомпанійній тестовій базі; якщо ланцюжок веде не на компанію, якір вказати явно у `vp-map.yaml`;
  `default_get` для нього не застосовується (він повертає лише `default_*`, `group_*`, `module_*` і `config_parameter`; `related` обчислюється при створенні запису);
- решта полів (`group_*`, `module_*`, `default_*`, `config_parameter`) -> `odoo_execute` model `res.config.settings`, method `default_get`,
  args `[[<поля пункту>]]`, `connection_id`; порівняти з `transform(answers.example.yaml)`. Додатково, коли місце зберігання відоме з CONFIG.md/вихідників:
  - `config_parameter=<ключ>` -> `ir.config_parameter:[key=<ключ>]:value` (значення порівняти до й після `execute()`);
  - `implied_group`/`group_*` -> членство `implied_ids` групи в `base.group_user`; `default_*` -> `ir.default`.
`CFG-readback: FAIL` (не MANUAL) -- лише коли не спрацював жоден із двох способів для поля, крім пунктів `manual: true`.
Поведінку `default_get` підтвердити через `boost:source-check` (відкрите питання).

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

## CLI-контракт скриптів (еталони є в `flow-core/references/templates/tools-odoo/`, сигнатури відрізняються)
Контракт -- вимога до скриптів `tools/odoo/`; до вирішення розбіжності з еталонами на нього **не спираються** (C-03 пропускає job
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
