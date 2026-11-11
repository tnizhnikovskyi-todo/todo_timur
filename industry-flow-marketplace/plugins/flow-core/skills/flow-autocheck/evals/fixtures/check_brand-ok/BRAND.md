# Фірмовий стиль ToDo для продаючих матеріалів і сторінок власника

Джерело: брендований бланк ToDo (`claude-methodology-marketplace/plugins/odoo19-discovery-closeout/skills/discovery-report-builder/assets/report_template.docx`);
комплект перенесено з еталона `flow/A-21-real` @ `74c90ca` (`prototype-real/brand-todo/`).

- Логотип: `todo-logo.png` (знак + «ToDo», на білому/світлому фоні), `todo-mark.png` (лише знак). У сторінках-Artifact — як `data:`-URI (base64 PNG), не як окремий файл.
- Кольори: помаранчевий ToDo `#FE5000` (акцент, кнопки, виділення), темний `#101820` (текст, темні фони), білий `#FFFFFF`; допоміжні сірі з бланка — `#808080`, `#BFBFBF`.
- Шрифт: Open Sans (Regular, Italic, Bold, BoldItalic) — `fonts/` (ліцензія Apache 2.0, `fonts/LICENSE-OpenSans.txt`). У сторінках — Google Fonts; у відео й PDF — локальні файли з `fonts/`.
- Правило: матеріали продають рішення **ToDo** для галузевої фабрики/підприємства — ToDo як автор/постачальник (логотип ToDo на заставках, у куті відео, у футері one-pager).
  Демо-клієнт у сценарії — клієнт; його логотип лишається лише всередині Odoo.
- Перевірка: `flow-core:flow-autocheck` `check_brand.py <файли> --brand <цей файл>` (BR-colors, BR-font, BR-logo).
