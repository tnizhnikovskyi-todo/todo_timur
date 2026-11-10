# Перелік моделей, меню й звітів на git-тегу

Усі команди — читання git за тегом клієнта; нічого не checkout-ити. `<тег>` = значення поля проєкту клієнта (напр. `package/v1.1`),
`<код>` = код клієнта. Шляхи `package/addons/` — як у структурі пакета (A-11/A-18); не збіглося з фактичним репо → записати в `memo`.

## Нові моделі пакета
```
git ls-tree -r --name-only <тег> package/addons | grep -E '^package/addons/td_[^/]+/models/.*\.py$'
git grep -nE "^[[:space:]]*_name[[:space:]]*=[[:space:]]*['\"]" <тег> -- 'package/addons/td_*/models/*.py'
```
Для кожного файлу з `_name` перевірити клас: `models.TransientModel` / `models.AbstractModel` — виключити; клас з `_inherit` без
`_name` — не нова модель, виключити. `_name` пишеться через крапку (`td.order`, `td.quality.check`; `td_*` — імена модулів-тек). Кастом клієнта виключається
шляхом: у перелік потрапляють лише `_name` з `package/addons/td_*/models/` на тегу; доробки — у `clients/<код>/addons/`,
вони не пакет. Фільтра за шаблоном імені немає.
Файли Python розбирати як текст (`grep`, `python3 -I` з `ast.parse`), **не імпортувати й не виконувати**.

## Меню й звіти
```
git grep -nE "<menuitem|<record[^>]*model=\"ir\.ui\.menu\"" <тег> -- 'package/addons/td_*/views/*.xml' 'package/addons/td_*/data/*.xml'
git grep -nE "ir\.actions\.report" <тег> -- 'package/addons/td_*'
```
У звіт — xml id і тег, без цифр.

## `package/metrics/key-models.yaml` (рішення q36: AI-чернетка при релізі; відповідальний -- Власник продукту)
```yaml
version: 1
models:
  - {model: sale.order, reason: "ядро продажів, використовується пакетом"}
  - {model: stock.picking, reason: "…"}
```
Лише технічні імена стандартних моделей Odoo, що їх пакет явно використовує; склад списку визначає людина.
