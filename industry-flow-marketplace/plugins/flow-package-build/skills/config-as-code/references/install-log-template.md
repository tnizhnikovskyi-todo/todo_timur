# `package/config/install-log.md` (шаблон)

```
# Лог установки конфіг-пакета
- База: <alias/ім'я чистої бази>, Odoo 19.0, редакція <ce|ee>
- SHA гілки: <sha>   Версія скіла: config-as-code@<версія>   Режим: build|fix|new-version|validate
- Спосіб: mcp-fallback через odoo-mcp, connection_id=<id>, база <alias>; install-one-command: N/A (скриптів немає)
- Стан бази на старті: чиста | не чиста (fix)
- Секрети: не вносяться (лише змінні оточення)

## Прогін 1 (чиста база)
created=<N> updated=<N> unchanged=<N> manual=<N> errors=<N>   тривалість=<c>
## Прохід 2 (порівняння за xml-id, без записів)
розбіжностей=0 відсутніх=0 unchanged=<N> manual=<N>
## Read-back VP
| VP | Очікувано (transform) | У базі | Статус |
## Config-log (еквівалент для `config-review`; передається йому як config-log)
Читання стану -- база <alias>, `connection_id=<id>`.
| Пункт CONFIG.md | xml-id | Фактичне значення (read-back) | Статус (PASS/FAIL/MANUAL) |
## Ручні пункти
<список з CONFIG.md «Ручні кроки»>
## Помилки й виправлення
<лише ERROR/Traceback, `grep -E "ERROR|Traceback" -A 15`; без секретів і повного логу Odoo>
```
