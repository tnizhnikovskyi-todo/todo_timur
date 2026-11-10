# Маршрутизація за ризиком (крок 13) і тег релізу A-18 (крок 14б)

## Крок 13
Причина → `routing: {to: human|auto, reason}` у звіті. **До людини**, якщо будь-що з:
- `check.mode ∈ {human, both}` при `maturity < 3`; `maturity < 3` (немає ключа `maturity` → вважати `< 3`, `open-questions.md` №6);
- ризик за diff (`reason: risk:<клас>`), **ризик перекриває зрілість**: `security/`, `ir.model.access.csv`, `ir.rule`, `res.groups`, `migrations/`, `pre/post-migrate`, `clients/<id>/`, будь-що з `client_data != none`, шляхи з `check.risk_paths`;
  **гроші/рахунки/податки** — перевіряються командою `git diff -U0 <git.base>...<git.head> -- '*.py' '*.xml' '*.csv' | grep -E '^\+' | grep -Ei 'fields\.Monetary|account\.(move|tax)|\b(price|amount|tax|currency)\w*'` — є збіг → `risk:money`;
- аудит: `maturity: 3` і `(кількість завершених запусків цього step+scope + 1) mod check.audit_every_n == 0` (за замовчуванням 10; лічильник — `odoo_execute … search_count` задач цього `step`+`scope.id` у стадіях `stage.autocheck` і `stage.done` — обидві означають завершений запуск без повернення); лічильник недоступний → аудит; `audit: true` у звіті, стадія `stage.on_human`.
Інакше (`maturity 3`, без ризику, поза аудитом) достатньо AI-рецензента й гейтів → стадія `stage.autocheck` (за `odoo-bridge.md` §4: `done` → `stage.autocheck` за `routing: auto` або `stage.on_human` за `routing: human`;
перехід `stage.autocheck` → `stage.done` робить не runner, а `flow-autocheck`/оркестратор). Runner **сам `stage.done` не ставить**.


## Крок 14б
б) A-18 `params.phase: tag`: після `done` скіл формує `release {tag, sha, command}`. Runner перевіряє тег за `id-patterns.md` (`^package/v\d+\.\d+(-odoo\d+)?$` — суфікс лише для переходу на нову мажорну Odoo, рішення q19; патч — `^package/v\d+\.\d+\.\d+$`), що `sha` — вершина `base_branch` із схваленим гейтом A-18, і лише тоді виконує `command` (`git tag -a … && git push origin <тег>`); іншого push у `base_branch` немає. Не вдалося → `escalated_to: Тімлід` (`flow-map.md`).

