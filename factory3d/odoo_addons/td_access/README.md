# factory3d_access

Odoo 19: СКУД Suprema BioStar 2 (P-10) — журнал подій, відмітки `hr.attendance`, картки, відвідувачі,
люди по зонах. Залежності: `factory3d_base`, `hr_attendance`, `mail`; Python: `requests`.

## Установка

`odoo-bin -d <db> -i factory3d_access`. Параметри — `factory3d.access.*` (SPEC §5.1); стоп-крани
`read_enabled`/`write_enabled` вимкнені за замовчуванням. Пароль BioStar вводить адміністратор у налаштуваннях.

Стан: каркас W0 (групи, параметри, меню «Доступ»); моделі, представлення, крони додають W1–W4.
