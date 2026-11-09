# Версіонування, SHA і дозволений diff

## Режими
| Параметр | `release` (A-17 -> A-18) | `patch` (A-19 -> A-18) | `odoo-upgrade` (D-03 -> A-17 -> A-18) |
|---|---|---|---|
| Тег | `package/vX.Y` | `package/vX.Y.Z` | `package/vX.Y-odoo<N>` |
| Номер версії з | `ACCEPTANCE.md` | `hotfix/vX.Y.Z.md` + попередній тег `package/vX.Y` | `ACCEPTANCE.md` + `upgrade-<версія>.md` |
| Гілка від | коміт з `ACCEPTANCE.md` | SHA APPROVE з `CHECKS.md` | коміт з `ACCEPTANCE.md` |
| База SHA для R-01/R-02 | SHA ревізії стенда з ACCEPTANCE | SHA APPROVE | SHA ревізії з ACCEPTANCE |
| Дозволений diff | сім файлів (нижче) | лише `package/CHANGELOG.md`, `package/templates/CHANGELOG.md` | сім файлів |
| `version` td_* | `19.0.X.Y` | не змінюється (Z лише в тегу) | `<N>.0.X.Y` |
| Додаткові розділи CHANGELOG | - | «Виправлено (hotfix)» (версії клієнтів ідентифікаторами з hotfix.md) | «Сумісність з Odoo» |
| ACCEPTANCE / A-17 | обов'язково | не застосовується | обов'язково |
| Тест оновлення | з попереднього `vX.(Y-1)` або останнього тега | з `vX.Y` | з останнього тега попередньої Odoo |

## Сім дозволених файлів (release, odoo-upgrade)
Різниця `<SHA ревізії>..HEAD` може містити лише:
1. `package/CHANGELOG.md`
2. `package/templates/CHANGELOG.md`
3. `package/templates/migration-plan.md`
4. `package/templates/training.md`
5. `package/demo/README.md` (A-15: SHA, режим використання стенда)
6. `package/demo/scenarios.md` (A-16: SHA у заголовку)
7. `package/ACCEPTANCE.md` (A-17: підпис)

Файли 5-7 з'являються в гілці як нащадки ревізії стенда; вони не є порушенням. Будь-який інший файл
(`package/addons/`, `config/`, `master-data/`, `templates/answers.yaml`, `questionnaire.md`, `SPEC.md`) — порушення R-02,
дефект пакета: «виправити на місці» заборонено.

## Ланцюг SHA (R-16)
SHA ревізії в `ACCEPTANCE.md` = SHA у заголовку `scenarios.md` = SHA у `demo/README.md`. Розбіжність — ескалація
Власнику продукту (не дефект і не правка файлів).

## Обчислення тега
- `release`: X.Y з ACCEPTANCE. Якщо тег `package/vX.Y` існує — стоп (R-04).
- `patch`: `package/vX.Y` (поточний мажор-мінор з hotfix.md) + Z = наступний за найбільшим існуючим `package/vX.Y.*`; перший патч — 1.
- `odoo-upgrade`: X.Y з ACCEPTANCE, N — мажор Odoo з `upgrade-<версія>.md` (напр. 20).
- Попередній тег: `git tag -l 'package/v*' --sort=-v:refname`; немає — «Перша версія: попереднього тега немає», R-11 не застосовується.
- Теги анотовані; `git tag -f` і `git push --force` заборонені; тег ніколи не переноситься.
