# Шаблон вивантаження метрик (D-01 collect)

Прод клієнта AI не читає. Тімлід або підтримка клієнта рахує агрегати в проді сам (UI Odoo: Налаштування -> Технічне -> моделі / «Групувати»,
звіт, або запит власною інфраструктурою) і кладе файл у теку клієнта (Drive) або в репо за `params.upload_path`
(рекомендовано `clients/<код>/exports/<YYYY-MM>.csv`).

## Що порахувати (за період `[start, end)`, UTC, `end` не включно)
1. По кожній моделі з переліку скіла (`model-inventory.md`, тег клієнта): `created` — записів із `create_date` у періоді;
   `changed` — записів із `write_date` у періоді, створених раніше `start`. Архівні не рахувати.
2. Активні внутрішні користувачі за період — загалом (`key=internal_total`) і за ролями (необов'язково; `key=role:<код ролі>`).
3. Модель відсутня в проді -> `status=absent`; не вдалося порахувати -> `status=error` (числа порожні).

## Формат: CSV (UTF-8, роздільник `,`) або JSON з тими самими полями
Заголовок: `schema_version,client,period_start,period_end,kind,key,created,changed,status`

| Поле | Значення |
|---|---|
| `schema_version` | `1` |
| `client` | код клієнта за DATA_POLICY (не назва) |
| `period_start`, `period_end` | `YYYY-MM-DD` UTC, збігаються з `params.period` |
| `kind` | `model` (`key` = `_name`, `created`/`changed`) або `users` (`key` = `internal_total` або `role:<код>`, `created` = кількість, `changed` порожнє) |
| `status` | `ok` / `absent` / `error` |

Приклад:
```
1,CL-01,2026-12-01,2027-01-01,model,td.order,120,340,ok
1,CL-01,2026-12-01,2027-01-01,model,td.quality.check,,,absent
1,CL-01,2026-12-01,2027-01-01,users,internal_total,14,,ok
```

## Заборонено у файлі (перевіряє скіл за `flow-core/references/pii-patterns.md`)
ПІБ, e-mail, телефони, хости/URL, IP, логіни, секрети, вміст записів, текстові примітки. Лише числа, коди, коди ролей.
Файл із PII скіл повертає (`returned`) і не комітить.

## Перевірка скілом
Схема й версія; `client` = клієнт наряду; період = `params.period`; усі `created`/`changed` — цілі >= 0; жодного рядка поза переліком моделей;
`users/internal_total` присутній (інакше `active_internal_users: null`, «не виміряно»).
