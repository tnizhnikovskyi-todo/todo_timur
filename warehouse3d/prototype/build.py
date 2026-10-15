# Собирает прототип sklad.html (опубликован как артефакт «Склад меблевої фабрики») из шаблона и снимка данных Odoo.
from pathlib import Path
d = Path(__file__).parent
(d / "sklad.html").write_text((d / "sklad.template.html").read_text().replace("__DATA__", (d / "data.json").read_text()))
