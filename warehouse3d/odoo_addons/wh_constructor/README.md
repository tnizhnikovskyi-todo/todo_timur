# wh_constructor — тонкий модуль Odoo для «Конструктора складу» (D-22)

Відає застосунок `warehouse3d/app` з адреси бази, зберігає проєкти, версії та блокування зон; права — групи Odoo.
Odoo 18 і 19 Community, залежності: `stock`, `web`. Застосування змін до локацій (W-13) тут ще немає.

## Склад модуля

- Моделі: `wh.project` (ключ у застосунку, компанія, склади, `data` — JSON проєкту v2, схема, ревізія `rev`),
  `wh.project.version` (знімок при кожному «Зберегти», зберігаються останні 50; параметр `wh_constructor.max_versions`),
  `wh.zone.lock` (проєкт, склад, ключ зони, користувач, термін; 5 хв, параметр `wh_constructor.lock_ttl`),
  `wh.library` (спільний довідник компанії: типи місць і шаблони, JSON `{types, templates}`, ревізія `rev`; читає «перегляд», пише «проєктування»).
- Групи: «Конструктор: перегляд» ⊂ «проєктування» ⊂ «застосування в Odoo» (кожна наступна включає попередню; перегляд включає
  «Склад: користувач», щоб було видно меню). Правило записів за компанією. Адміністратор отримує «застосування» при встановленні.
- Меню: Склад → Конфігурація → Конструктор складу (група «перегляд»; видимість меню «Конфігурація» розширює `post_init_hook`).

## HTTP (усі `auth="user"`, JSON-RPC; префікс `/wh_constructor`)

| Маршрут | Дія |
|---|---|
| `/app` | сторінка застосунку (`static/app/index.html` + `<base>` і `window.__WH_ODOO__`); 404 з підказкою, якщо немає збірки |
| `/api/me` | користувач і права `{view, design, apply}` |
| `/api/projects`, `/project/load`, `/project/delete` | список, завантаження, видалення |
| `/api/project/save` | `{key, data, base_rev, commit, comment}` → `ok` + нова `rev`, або `stale` (в базі новіше) |
| `/api/project/versions`, `/project/restore` | історія; відновлення створює нову ревізію й версію |
| `/api/lock/acquire`, `/lock/release`, `/lock/list` | захоплення/продовження, звільнення, чинні блокування; зайнята — `{ok:false, owner, expires}` |
| `/api/library/load`, `/library/save` | довідник типів і шаблонів; `save` `{data, base_rev}` → `ok` + `rev`, або `stale` + поточні `data` (клієнт зливає й повторює) |

Відмова за правами — `{status:"denied"}`, помилка перевірки — `{status:"error"}`.

## Збірка і тести

```bash
cd warehouse3d/app && npm run build:odoo        # збірка в static/app модуля (не в git)
warehouse3d/tools/odoo/run_tests.sh wh_t        # WH_ODOO=18|19; середовище — warehouse3d/tools/odoo/ENV.md
```
