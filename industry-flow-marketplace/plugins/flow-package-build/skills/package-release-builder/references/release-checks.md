# Команди перевірок R-01...R-16

Підстановки: `SHA` — ревізія (patch: SHA APPROVE), `TAG` — `package/...`, `PREV` — попередній тег.
Вивід обмежувати (`| head -30`).

| ID | Команда / спосіб |
|---|---|
| R-01 | `git merge-base --is-ancestor $SHA HEAD && echo PASS` |
| R-02 | `git diff --name-only $SHA..HEAD \| grep -vxFf allowed.txt` — вивід порожній = PASS; `allowed.txt` з `versioning.md` для режиму |
| R-03 | `grep -h "'version'" package/addons/td_*/__manifest__.py` — усі `19.0.X.Y` (odoo-upgrade `<N>.0.X.Y`), X.Y = ACCEPTANCE |
| R-04 | `git ls-remote --tags origin "refs/tags/$TAG"` — порожньо = PASS |
| R-05 | множина `ls package/addons` = перелік комплекту ACCEPTANCE = таблиця «Склад пакета» (`flow-core:flow-autocheck`) |
| R-06 | у маніфесті вендореного `license`, у каталозі LICENSE, у файлі вендорингу джерело/коміт і version |
| R-07 | `grep -c -E '^#{2,3} (Версія\|Склад пакета\|Шаблони документів клієнта\|Зміни анкети\|Несумісні зміни\|Міграція з попереднього тегу\|Команда установки)' <розділ>` = 7 (+ режимні) |
| R-08 | скрипт нижче; множина = ключі в «Зміни анкети» |
| R-09/R-10/R-11 | `actions_get` статус `success`, `head_sha` прогону = `git rev-parse HEAD`; лог — `get_job_logs` + grep; без логу `NOT_RUN` |
| R-12 | `grep -c` обов'язкових розділів `migration-plan.md`, `training.md` (див. шаблони) |
| R-13 | `git diff -U0 $PREV..HEAD -- package/addons/td_*/models` і `ls package/addons/td_*/migrations/19.0.X.Y/` |
| R-14 | regex нижче по CHANGELOG, шаблонах, release-defects.md; у майстер-даних/демо — лише повідомлення про факт, без копіювання |
| R-15 | `boost:odoo19-lint` по `package/addons/td_*/` |
| R-16 | `grep -n <SHA> package/ACCEPTANCE.md package/demo/scenarios.md package/demo/README.md` |

## R-08: ключі answers.yaml (без сторонніх бібліотек)
```bash
for r in "$PREV" HEAD; do
  git show "$r:package/templates/answers.yaml" 2>/dev/null \
   | python3 -I -c "import sys,re;[print(m.group(1)) for l in sys.stdin if (m:=re.match(r'^([A-Za-z0-9_.-]+):',l))]" \
   | sort > "/tmp/keys.$(echo $r | tr / _)"
done
comm -13 /tmp/keys.<PREV> /tmp/keys.HEAD   # нові
comm -23 /tmp/keys.<PREV> /tmp/keys.HEAD   # видалені/deprecated
```
Вкладені структури схеми цей спосіб не бачить; якщо ключі вкладені — використати `yaml`, якщо він встановлений, інакше
питання Архітектору. Тимчасові файли — у каталозі scratchpad, не в репо. Відкрите питання: точний формат
позначки deprecated у схемі A-09 не відомий.

## R-14: regex даних клієнта
`\b\d{8}\b` (ЄДРПОУ; перевіряти контекст, є хибні збіги), `\+380\d{9}`, `[\w.+-]+@[\w-]+\.[\w.]+`, назви компаній/людей зі списку
CRM, якщо він є в наряді. Знайдене — не цитувати у звіті, лише файл і тип.

## Формат таблиці результатів (у `memo` і `checks[]`)
| ID | Статус | Доказ |
|---|---|---|
| R-01 | PASS / FAIL / NOT_RUN | команда + короткий вивід або run id |
