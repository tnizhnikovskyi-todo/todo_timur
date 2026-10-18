# td_access

Odoo 19: СКУД Suprema BioStar 2 (P-10) — журнал подій, відмітки `hr.attendance`, картки, відвідувачі,
люди по зонах. Залежності: `td_factory3d`, `hr_attendance`, `mail`; Python: `requests`.

## Установка

`odoo-bin -d <db> -i td_access`. Параметри — `td.access.*` (SPEC §5.1); стоп-крани
`read_enabled`/`write_enabled` вимкнені за замовчуванням. Пароль BioStar вводить адміністратор у налаштуваннях.

Стан: каркас W0 (групи, параметри, меню «Доступ»); моделі, представлення, крони додають W1–W4.
