# Посібник адміністратора

## Перший запуск
Установіть модулі за `package/config/CONFIG.md`.

## Параметри
| Параметр | Ключ answers.yaml | За замовчуванням |
|---|---|---|
| Поріг | `elearning.pass_score` | 80 |

## Профілі
A, light, B.

## Редакції
CE; EE — апгрейд.

## Користувачі й ролі
Групи доступу `td_*` і стандартні; призначення ролі — в налаштуваннях користувача.

## Майстер-дані й імпорт
Шаблони `package/master-data/*.csv`; імпорт за порядком з README.

## Обмін з обліковою системою
Немає обміну.

## Пошта
Налаштуйте вхідну й вихідну пошту; перевірте відправлення тестовим листом.

## Оновлення версії
Оновіть модулі пакета (`-u`), перевірте, за потреби відкотіть.

## Резервні копії
Копіюйте базу і filestore щодня; відновлення перевіряйте на тестовій базі.

## Звернення в підтримку (td_support)
Модуль не злито.

## База знань (td_knowledge)
Модуль не злито.

## SC-03 Змінити параметр порогу
Статус: готово

| № | Дія | Що видно |
|---|---|---|
| 1 | Відкрийте «Налаштування» й змініть значення | ![Крок 1](img/admin/SC-03-1.png) |

Параметри `stock.warehouse_code` (VP-02): код складу.
Порогу відповідає VP-01.

## Встановлення бази клієнта
Сервер: Ubuntu 22.04, PostgreSQL 16, Python 3.12; код Odoo 19.0 і пакет лежать у `/opt/odoo/odoo` і `/opt/odoo/addons-td`. Модулі до установки — розділ «Модулі до установки» файла `package/config/CONFIG.md`, у порядку залежностей.
```bash
createdb klient_prod
/opt/odoo/odoo/odoo-bin -d klient_prod --addons-path=/opt/odoo/odoo/addons,/opt/odoo/addons-td \
  -i td_x --load-language=uk_UA --without-demo=all --stop-after-init
```
Межа: конфіг-пакет на базу клієнта застосовує ToDo за B-04 (скрипт `apply.py` пакета працює лише з базами `test-*`, `demo-*`, `emu-*`; рішення AI-07, власник має вето). Адміністратор клієнта до B-04 лише перевіряє результат.

## Безпека
Змініть пароль адміністратора після установки (довжина не менше 12 символів), увімкніть двофакторну автентифікацію (2FA) кожному користувачу з правами адміністратора. У `odoo.conf` задайте:
```ini
list_db = False
admin_passwd = <довгий-випадковий-майстер-пароль>
```
`list_db = False` ховає екран вибору бази; майстер-пароль (`admin_passwd`) зберігайте в менеджері паролів. Ключі інтеграцій (BAS, пошта) не лежать у тексті модулів: зберігайте їх у параметрах каналу й міняйте при звільненні відповідальних.

## Резервні копії й відновлення
Щодня копіюйте базу і filestore (`/var/lib/odoo/filestore/klient_prod`).
```bash
pg_dump -Fc klient_prod > klient_prod.dump
tar czf filestore.tgz -C /var/lib/odoo/filestore klient_prod
createdb klient_test && pg_restore -d klient_test klient_prod.dump
mkdir -p /var/lib/odoo/filestore/klient_test && tar xzf filestore.tgz -C /var/lib/odoo/filestore/klient_test --strip-components=1 && chown -R odoo: /var/lib/odoo/filestore/klient_test
/opt/odoo/odoo/odoo-bin neutralize -d klient_test
```
Копію для тесту знешкодьте: `odoo-bin neutralize` вимикає листи й cron. Далі вручну: у модулях td_* вимкніть канали обміну, перевірте адресу пошти й ключі інтеграцій тестової бази.

## Оновлення версії
Зупиніть сервіс, зробіть резервну копію, оновіть модулі, запустіть сервіс.
```bash
sudo systemctl stop odoo
/opt/odoo/odoo/odoo-bin -d klient_prod --addons-path=/opt/odoo/odoo/addons,/opt/odoo/addons-td -u td_x --stop-after-init
sudo systemctl start odoo
```

## Пошта
У режимі розробника відкрийте «Налаштування», знайдіть системний параметр `web.base.url` і вкажіть адресу сайту. Вихідний сервер — «Налаштування» → «Ел. пошта»; адресу відправника задайте в налаштуваннях сервера вихідної пошти. Перевірте тестовим листом.

## Користувачі
Створення: «Налаштування» → «Користувачі та компанії» → «Користувачі» → «Створити»; вкажіть часовий пояс (TZ) `Europe/Kyiv`, мову «Українська» і групи ролі.
