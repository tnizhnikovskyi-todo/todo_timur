# Середовище Odoo для warehouse3d (18.0 і 19.0 Community)

Порт `factory3d/tools/odoo` (Odoo 19) і `smartgen/tools/odoo` (Odoo 18) з параметром версії **`WH_ODOO=18|19`** (за замовчуванням 19).
Усе, крім скриптів, лежить **поза репозиторієм**; `setup.sh` ідемпотентний (готове пропускає, повторний запуск ≈ 1 с).

## Шпаргалка

```bash
T=<корінь worktree>/warehouse3d/tools/odoo          # скрипти свого worktree; addons-path = <корінь>/warehouse3d/odoo_addons
WH_ODOO=19 $T/setup.sh                              # Postgres 16, Odoo 19.0 (shallow), venv, конфіг, шаблонна база wh19_template (≈ 2,5 хв)
WH_ODOO=18 $T/setup.sh                              # те саме для 18.0: /home/user/odoo18*, шаблон wh18_template
WH_ODOO=19 $T/run_tests.sh wh_<ім'я> [test-tags]    # свіжа копія шаблона + -i усіх модулів + тести; друкує лише підсумок і ERROR з трейсбеками
WH_TEST_INSTALL=wh_constructor $T/run_tests.sh …    # ставити/тестувати лише вказані модулі; теги за замовчуванням /<модуль>
$T/new_db.sh | update.sh | serve.sh [stop|status] | drop_db.sh <db>   # порожня копія · -i/-u модулів · сервер у фоні (admin/admin) · видалення
$T/pg.sh start|stop|status|init                     # Postgres не стартує сам після рестарту контейнера
$T/setup.sh template|check                          # перезібрати шаблон · перевірка тестової інфраструктури (/stock:TestWarehouse)
```

Назви баз — `[a-z0-9_-]`; у кожного потоку свій префікс (`wh_w21_…`). Логи Odoo — у `/home/user/odoo<версія>-data/logs/`, у вивід скриптів потрапляють лише підсумок і помилки.

## Що де (для версії N = 18|19)

| Що | Де |
|---|---|
| Вихідники Odoo | `/home/user/odooN` — `git clone --depth 1 --branch N.0` |
| venv, конфіг, дані | `/home/user/odooN-venv` (Python 3.12), `/home/user/odooN.conf`, `/home/user/odooN-data` |
| Шаблонна база | `whN_template`: `stock, web, bus, mail, analytic` + залежності, без демо; `ALLOW_CONNECTIONS false` |
| Postgres | один кластер 16/main на обидві версії, роль `odoo`/`odoo`; налаштування для тестів (fsync=off) — лише для розробки |

## Відмінності 18 і 19, які враховують скрипти й модуль

- `--without-demo`: `all` (18) і `True` (19) — вибирає `env.sh` (`WH_NODEMO_VALUE`).
- JSON-маршрути: `type='json'` (18) і `type='jsonrpc'` (19, `json` — застарілий псевдонім із попередженням).
- Поле груп користувача: `groups_id` (18) і `group_ids` (19); те саме в `ir.ui.menu`. Категорії груп (18 — `ir.module.category`, 19 — `res.groups.privilege`) модуль не використовує.
- `_sql_constraints` застарів у 19 — модуль не користується (унікальний індекс у `init()`, `@api.constrains`).
- Паралельні прогони різних баз безпечні (окремі lock, порт з імені бази). Шаблон не перезбирайте під чужими прогонами.
- Тести, що чіпають моделі поза `depends`, позначайте `@tagged('post_install', '-at_install')`; `tests` не імпортуйте з `__init__.py` модуля.
