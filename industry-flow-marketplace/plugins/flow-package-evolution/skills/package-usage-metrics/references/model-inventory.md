# Перелік моделей, меню й звітів на git-тегу

Усі команди — читання git за тегом клієнта; нічого не checkout-ити. `<тег>` = значення поля проєкту клієнта (напр. `package/v1.1`),
`<код>` = код клієнта. Шляхи `package/addons/` — як у структурі пакета (A-11/A-18); не збіглося з фактичним репо → записати в `memo`.

## Моделі td_*
```
git ls-tree -r --name-only <тег> package/addons | grep -E '^package/addons/td_[^/]+/models/.*\.py$'
git grep -nE "^\s*_name\s*=\s*['\"]" <тег> -- 'package/addons/td_*/models/*.py'
```
Для кожного файлу з `_name` перевірити клас: `models.TransientModel` / `models.AbstractModel` — виключити; клас з `_inherit` без
`_name` — не нова модель, виключити. `_name` з `td_<код>_` (кастом клієнта) — виключити; їх у `clients/<код>/addons/`, не в пакеті.
Файли Python розбирати як текст (`grep`, `python3 -I` з `ast.parse`), **не імпортувати й не виконувати**.

## Меню й звіти
```
git grep -nE "<menuitem|<record[^>]*model=\"ir\.ui\.menu\"" <тег> -- 'package/addons/td_*/views/*.xml' 'package/addons/td_*/data/*.xml'
git grep -nE "ir\.actions\.report" <тег> -- 'package/addons/td_*'
```
У звіт — xml id і тег, без цифр.

## `package/metrics/key-models.yaml` (веде Власник продукту; питання В-4)
```yaml
version: 1
models:
  - {model: sale.order, reason: "ядро продажів, використовується пакетом"}
  - {model: stock.picking, reason: "…"}
```
Лише технічні імена стандартних моделей Odoo, що їх пакет явно використовує; склад списку визначає людина.
