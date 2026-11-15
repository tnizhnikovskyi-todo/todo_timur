# Команди перевірок R-01...R-22

Підстановки: `SHA` — ревізія (patch: SHA APPROVE), `VER` — `vX.Y[...]`, `TAG` = `package/$VER`, `SCRATCH` — каталог scratchpad, `PREV` — попередній тег.
Вивід обмежувати (`| head -30`).

**Фаза `tag`:** перевірки робити на `<sha>` merge-коміту, а не на HEAD/робочому дереві: замість `HEAD` підставляти `<sha>`, файли читати через `git show <sha>:<path>`, склад — `git ls-tree --name-only <sha> package/addons/` (команди R-01, R-03, R-05, R-07, R-12). Гілку скілу не перемикати.

| ID | Команда / спосіб |
|---|---|
| R-01 | `git merge-base --is-ancestor $SHA HEAD && echo PASS` |
| R-02 | = результат autocheck `diff-allowed-7` (ручна команда лише для діагностики): `git diff --name-only $SHA..HEAD \| grep -vE '^(observations/\|package/(addons/td_[a-z0-9_]+_elearning/\|support/\|docs/user-guide/\|demo/\|ACCEPTANCE.md\|CHANGELOG.md\|CHECKS.md\|templates/(CHANGELOG\|migration-plan\|training\|demo-README).md\|metrics/key-models.yaml\|config/(manifest.yaml\|CONFIG.md))\|docs/industries/[^/]+/research/AI-DECISIONS.md\|flow/\|tests/\|\.claude/\|industry-flow-marketplace/\|CLAUDE.md\|TEST-START.md\|START-HERE.md)'` — вивід порожній або лише `package/templates/answers.yaml` = PASS; список = `versioning.md` пп. 1-18 (префікси замість точних рядків); `package/templates/answers.yaml` допустимий лише як додавання блоку `elearning:` (A-17b): `git diff $SHA..HEAD -- package/templates/answers.yaml \| grep -E '^[+-][^+-]' \| grep -vE '^\+(elearning:\|  (mode\|pass_score):)'` — порожньо = PASS |
| R-17 | `git show HEAD:package/metrics/key-models.yaml` існує (release/odoo-upgrade), кожна модель є в `_name`/`_inherit` у `package/addons/` (`git grep`); немає — повтор |
| R-03 | `for d in $(ls -d package/addons/td_* \| grep -vE '/td_(home_menu\|support\|knowledge)$'); do grep -h "'version'" $d/__manifest__.py; done` (або autocheck `version-eq`) (спільні вендорені `td_home_menu`, `td_support`, `td_knowledge` з §27/§27а мають власну версію і виключені) — усі `19.0.X.Y` (odoo-upgrade `<N>.0.X.Y`), X.Y = ACCEPTANCE |
| R-04 | `git ls-remote --tags origin "refs/tags/$TAG"` — порожньо = PASS |
| R-05a | при `elearning.mode: "on"` у CHANGELOG є рядок «Модулі до установки (A-17b)» з `website_slides` і `td_*_elearning`; `depends` elearning-модуля ⊂ {цей рядок, `addons/`, CONFIG} — інакше дефект |
| R-05 | множина тек `git ls-tree -d --name-only HEAD package/addons/ \| grep -vE '/td_[a-z0-9_]+_elearning$'` = `git ls-tree -d --name-only <SHA ревізії з ACCEPTANCE> package/addons/` (порівнювати саме теки з обох боків: файли на кшталт `AC-COVERAGE.md` не рахуються) (комплект; окремого переліку в ACCEPTANCE.md немає); усі `ls package/addons` = таблиця «Склад пакета», де `td_*_elearning` — окремий рядок з приміткою «A-17b» (дозволена добавка, не дефект; `flow-core:flow-autocheck`) |
| R-06 | (спільні td_home_menu/td_support/td_knowledge/td_<галузь>_knowledge -- PASS без LICENSE/коміту) у маніфесті вендореного `license`, у каталозі LICENSE, у файлі вендорингу джерело/коміт і version |
| R-07 | `grep -c -E '^#{2,3} (Версія\|Склад пакета\|Шаблони документів клієнта\|Зміни анкети\|Несумісні зміни\|Міграція з попереднього тегу\|Команда установки)' <розділ>` = 7 (+ режимні: «Передача клієнту» для release/odoo-upgrade) |
| R-08 | скрипт нижче (блоки `VP-xx` і поле `deprecated`, `answers-schema.md`); результат = «Зміни анкети» |
| R-09/R-10/R-11 | прогін знайти за C-03 («Статус на SHA»): push/PR — check-run на `head_sha`; dispatch — `actions_list` `event=workflow_dispatch`, `display_title` = `ci <SHA>…` (не `head_sha`) або commit status `context: ci`; `conclusion: success`; SHA прогону — предок HEAD і `git diff --name-only <SHA>..HEAD` лише `package/CHANGELOG.md`; лог — `get_job_logs` + grep; без логу `NOT_RUN`. Помилка checkout — ескалація, не FAIL пакета |
| R-12 | `grep -c` обов'язкових розділів `migration-plan.md`, `training.md` (див. шаблони) |
| R-13 | `git diff -U0 $PREV..HEAD -- package/addons/td_*/models` і `ls package/addons/td_*/migrations/<серія>.X.Y/` (`<серія>` = `19.0`, odoo-upgrade `<N>.0`) |
| R-14 | regex нижче по CHANGELOG, шаблонах, release-defects.md; у майстер-даних/демо — лише повідомлення про факт, без копіювання |
| R-21 | `boost:odoo19-lint` по `package/addons/td_*/` |
| R-18 | `test -f package/docs/user-guide/INDEX.md`; `S=$(<SHA_STAND з package/demo/README.md>)`; `git diff --quiet $S..HEAD -- package/addons ':!package/addons/td_*_elearning/*'` (код 0); `python3 -I <flow-package-build>/skills/user-guide-builder/scripts/check_guides.py --dir package/docs/user-guide --spec <шлях із рядка «Джерело сценаріїв:» INDEX> --stand-sha $S --addons package/addons --answers package/templates/answers.yaml --config package/config/CONFIG.md` (SKIPPED у UG-cover-dev/UG-cover-admin = не PASS); якщо є модуль: `python3 -I <flow-package-build>/skills/elearning-builder/scripts/check_elearning.py --module package/addons/td_<галузь>_elearning --guide package/docs/user-guide --answers package/templates/answers.yaml`; `grep -h "'version'" package/addons/td_*_elearning/__manifest__.py` = X.Y |
| R-19 | `grep -n -E 'support/' package/CHANGELOG.md` — лише в рядку виключення; `git grep -n 'package/support' -- package/templates package/docs` — порожньо; `python3 -I <flow-package-build>/skills/support-kb-builder/scripts/check_kb.py --dir package/support --addons package/addons` |
| R-20 | `for m in td_support td_home_menu td_knowledge; do test -d package/addons/$m || echo MISSING $m; grep -q $m package/config/manifest.yaml || echo NOT-IN-MANIFEST $m; done`; за MISSING/NOT-IN-MANIFEST — `grep -nE 'AI-[0-9]+.*(§27\|td_support\|td_home_menu)' docs/industries/*/research/AI-DECISIONS.md` (рядок про свідомий випуск без них); усі порожні — WARN; також WARN, якщо модуль є в `package/addons`, але не в `manifest.yaml` (`td_knowledge`, `td_<галузь>_knowledge` — у перелік установки за замовчуванням) |
| R-22 | `git ls-tree -r --name-only HEAD -- package/ \| grep -iE '\.(zip\|dump\|sql\.gz\|backup)$'` (порожньо = PASS) |
| R-16 | `grep -n <SHA> package/ACCEPTANCE.md package/demo/scenarios.md package/demo/README.md` |

## R-08: схема VP (без сторонніх бібліотек)
Нормативна схема — `questionnaire-builder/references/answers-schema.md`: блоки `^VP-\d{2,3}:` з полями `default`/`default_from`,
`deprecated: false | "з версії X.Y"`. Видалений ключ допустимий лише якщо на PREV він уже був deprecated.
```bash
cat > $SCRATCH/vp.py <<'EOF'
import sys,re,subprocess,json
def load(ref):
    try: s=subprocess.run(["git","show",ref+":package/templates/answers.yaml"],capture_output=True,text=True,check=True).stdout
    except Exception: return None
    d={};k=None
    for l in s.splitlines():
        m=re.match(r'^(VP-\d{2,3}):',l)
        if m: k=m.group(1); d[k]={}; continue
        m=re.match(r'^\s+(default|default_from|deprecated):\s*(.*)$',l)
        if m and k: d[k][m.group(1)]=m.group(2).strip().strip('"')
    return d
if not sys.argv[1]: print("Перша версія: попереднього тега немає"); sys.exit()
prev,head=load(sys.argv[1]),load("HEAD")
if prev is None: print("Перша версія: попереднього тега немає"); sys.exit()
dep=lambda b:b.get("deprecated","false") not in ("false","")
print("нові:",sorted(set(head)-set(prev)))
print("deprecated:",sorted(k for k in head if k in prev and dep(head[k]) and not dep(prev[k])))
print("FAIL видалено без deprecated:",sorted(k for k in set(prev)-set(head) if not dep(prev[k])))
print("defaults нових:",{k:head[k].get("default",head[k].get("default_from")) for k in set(head)-set(prev)})
EOF
python3 -I $SCRATCH/vp.py "$PREV"
```
Схема з іншою структурою блоків (немає `^VP-` на початку рядка) — питання Архітектору, не вгадувати. Тимчасові файли — лише в `$SCRATCH`, не в репо.

## R-14: regex даних клієнта
`\b\d{8}\b` (ЄДРПОУ; перевіряти контекст, є хибні збіги), `\+380\d{9}`, `[\w.+-]+@[\w-]+\.[\w.]+`, назви компаній/людей зі списку
CRM, якщо він є в наряді. Знайдене — не цитувати у звіті, лише файл і тип.

## Формат таблиці результатів (у `memo` і `checks[]`)
| ID | Статус | Доказ |
|---|---|---|
| R-01 | PASS / FAIL / NOT_RUN | команда + короткий вивід або run id |
