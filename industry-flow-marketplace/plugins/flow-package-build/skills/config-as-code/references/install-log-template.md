# `package/config/install-log.md` (шаблон)

```
# Лог установки конфіг-пакета
- База: <alias/ім'я чистої бази>, Odoo 19.0, редакція <ce|ee>
- SHA гілки: <sha>   Версія скіла: config-as-code@<версія>   Режим: build|fix|new-version|validate
- Команда: install.sh --db <db> --answers package/templates/answers.example.yaml   (або: mcp-fallback, N/A)
- Секрети: не вносяться (лише змінні оточення)

## Прогін 1 (чиста база)
created=<N> updated=<N> unchanged=<N> manual=<N> errors=<N>   exit=<0|1|2>   тривалість=<c>
## Прогін 2 (та сама база)
created=0 updated=0 unchanged=<N> manual=<N> errors=0         exit=0
## Read-back VP
| VP | Очікувано (transform) | У базі | Статус |
## Ручні пункти
<список з CONFIG.md «Ручні кроки»>
## Помилки й виправлення
<лише ERROR/Traceback, `grep -E "ERROR|Traceback" -A 15`; без секретів і повного логу Odoo>
```
