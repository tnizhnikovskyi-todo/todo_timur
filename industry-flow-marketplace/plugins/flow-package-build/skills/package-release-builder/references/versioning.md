# Версіонування, SHA і дозволений diff

Рішення q19: версія модулів `19.0.X.Y`, тег `package/vX.Y`; суфікс `-odoo<N>` -- для гілок переходу на нову мажорну Odoo (режим `odoo-upgrade`). Суфікс у ТЕГУ (`package/vX.Y-odoo<N>`) -- припущення AI, не рішення q19; відкрите питання Архітектору (колізія з `package/vX.Y` на Odoo 19), див. `open-questions.md` п. 8.

## Режими
| Параметр | `release` = `params.mode: перша` (A-17 -> A-18) | `patch` = `hotfix` (A-19 -> A-18) | `odoo-upgrade` = `нова-версія` (D-03 -> A-17 -> A-18) |
|---|---|---|---|
| Тег | `package/vX.Y` | `package/vX.Y.Z` | `package/vX.Y-odoo<N>` (припущення AI, питання Архітектору) |
| Номер версії з | `ACCEPTANCE.md` | `hotfix/vX.Y.Z.md` + попередній тег `package/vX.Y` | `ACCEPTANCE.md` + `upgrade-<версія>.md` |
| База гілки (створює runner) | `inputs[ACCEPTANCE.md].sha` | SHA APPROVE з `CHECKS.md` | `inputs[ACCEPTANCE.md].sha` |
| База SHA для R-01/R-02 | SHA ревізії стенда з ACCEPTANCE | SHA APPROVE | SHA ревізії з ACCEPTANCE |
| Дозволений diff | вісім файлів (нижче) | лише `package/CHANGELOG.md`, `package/templates/CHANGELOG.md` | вісім файлів |
| `version` td_* | `19.0.X.Y` | не змінюється (Z лише в тегу) | `<N>.0.X.Y` |
| Додаткові розділи CHANGELOG | - | «Виправлено (hotfix)» (версії клієнтів ідентифікаторами з hotfix.md) | «Сумісність з Odoo» |
| ACCEPTANCE / A-17 | обов'язково | не застосовується | обов'язково |
| Тест оновлення (R-11) | з попереднього тега (`git.prev_tag`) | з `vX.Y` | не застосовується: `-u` не мігрує БД між мажорними версіями Odoo; міграція — `upgrade-<версія>.md` (D-03), тут лише читається її результат |
| «Міграція з попереднього тегу» | R-11 | R-11 | посилання на звіт D-03 + установка в чисту базу нової Odoo (R-09/R-10) |

## Вісім дозволених файлів (release, odoo-upgrade)
Різниця `<SHA ревізії>..HEAD` може містити лише:
1. `package/CHANGELOG.md`
2. `package/templates/CHANGELOG.md`
3. `package/templates/migration-plan.md`
4. `package/templates/training.md`
5. `package/demo/README.md` (A-15: SHA, режим використання стенда)
6. `package/demo/scenarios.md` (A-16: SHA у заголовку)
7. `package/ACCEPTANCE.md` (A-17: підпис)
8. `package/metrics/key-models.yaml` (рішення q36: AI-чернетка, затверджує Власник продукту; лише `release`/`odoo-upgrade`)

`package/demo/release-defects.md` (дефект пакета) у R-02 не враховується: при `returned` PR не мерджиться. Файли 5-7 з'являються в гілці як нащадки ревізії стенда; вони не є порушенням. Будь-який інший файл
(`package/addons/`, `config/`, `master-data/`, `templates/answers.yaml`, `questionnaire.md`, `SPEC.md`) — порушення R-02,
дефект пакета: «виправити на місці» заборонено.

## Ланцюг SHA (R-16)
SHA ревізії в `ACCEPTANCE.md` = SHA у заголовку `scenarios.md` = SHA у `demo/README.md`. Розбіжність — ескалація
Власнику продукту (не дефект і не правка файлів).

## Обчислення тега
- Змінні: `VER` = `vX.Y[.Z|-odoo<N>]`, `TAG` = `package/$VER` (гілку створює runner: `flow/<крок>-...`).
- `release`: X.Y з ACCEPTANCE. Якщо тег `package/vX.Y` існує — стоп (R-04).
- `patch`: `package/vX.Y` (поточний мажор-мінор з hotfix.md) + Z — з імені `package/hotfix/vX.Y.Z.md` (A-19 його вже зафіксував); тег `package/vX.Y.Z` існує — ескалація Тімліду (R-04), без автоінкременту.
- `odoo-upgrade`: X.Y з ACCEPTANCE, N — мажор Odoo з `upgrade-<версія>.md` (напр. 20).
- Попередній тег: `git.prev_tag` наряду, інакше `git tag -l 'package/v*' --sort=-v:refname`; немає — «Перша версія: попереднього тега немає», R-11 не застосовується.
- Теги анотовані; `git tag -f` і `git push --force` заборонені; тег ніколи не переноситься.
