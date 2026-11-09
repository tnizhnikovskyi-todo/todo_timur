# Область CONFIG.md -> вид пункту даних

Факти про Odoo 19 нижче -- орієнтир; кожен сумнівний звіряти через `odoo_get_fields` на чистій базі і `boost:source-check`.
Чого не підтверджено -- `manual` або «Відкриті питання», не вигадувати.

| Область | Вид | Правило |
|---|---|---|
| Модулі | `manifest.yaml: modules` | лише технічні імена з ALLOCATION; `module_*` у `res.config.settings` **не** використовувати для установки модулів |
| Налаштування (`res.config.settings`) | `settings` | поля звірити `odoo_get_fields`; прапорці `group_*` та параметри; застосування через `execute()` (побічні дії -- apply-semantics.md) |
| Системні параметри | `config_param` | `ir.config_parameter`; ключ і значення рядком |
| Компанія | `record` | запис `base.main_company` за xml-id, лише поля з CONFIG.md |
| Групи й права | `group` | поля груп змінилися в 18-19 (odoo19-config-pitfalls.md); посилання на групи -- xml-id; логіни/паролі користувачів -- не в пакет |
| Автоматизації, серверні дії | `automation` | `base.automation`, `ir.actions.server`; серверна дія з кодом -- лише якщо ALLOCATION це допускає, інакше `manual` + питання на A-10 |
| Шаблони листів | `mail_template` | `mail.template` за xml-id; вихідний поштовий сервер з паролем -- `manual`, пароль з env |
| Крони | `cron` | `ir.cron` за xml-id, без полів, видалених у 19 (pitfalls) |
| Склади, маршрути, послідовності | `record` | стандартні записи -- за xml-id (`stock.warehouse0` лише якщо існує в чистій базі), нові -- `td_config.` |
| Studio-подання, інтеграції з обліковими даними, секрети | -- | `manual: true` з причиною |
| Параметри `td_*` (трек «код») | `td_param` | лише запис значення VP в параметр; моделі/поля `td_*` не описувати |
