# Відкрите після workflow 0.4.0 (перед фіксом)

## Статус (перевірка 2026-11-14, після фіксу)
Закрито 1–19. Уже були виправлені: SHA_RE/sha_eq/index-headings; `<галузь>` у git_diff_allowed; diff-allowed A-18; `--stand-sha` (псевдонім `--modules-sha`); skip_market_check (A-07.yaml, flow-map, A-21d); slice-coverage (A-21d у flow-map/step-skill-map/step-cards/checks); CS-plan-modules (лише модулі); product-decision-drafter (A-17b ∥ A-17c, INDEX); E6 (test-kit CLAUDE.md, flow-state-keeper); Playwright за замовчуванням; `--answers` у A-17b; назви `elearning.mode` у лапках і «Дані на екранах ролей»; кирилична «А» в rec_ok.
Закрито цим фіксом: мітки `Показників дашборда`/`Коробка входу`/`Коробка показу` пишуть concept-mapper і prototype-builder (шаблони screens.md, BOX.tpl.md, slice-plan-template.md); перелік установки `website_slides` + `td_<галузь>_elearning` (elearning-builder Крок 6, config-as-code Крок 4, A-17b/A-18 allow, картка A-17b); §27 у reuse-modules (RU-core), concept-mapper/BOX (CM-box-core), config-as-code, support-desk, support-kb-builder (KB-support); евали.


## Перелік (відновлено; первісний текст — у рецензіях кіл 1–23 workflow 0.4.0)

| # | Пункт — чим закрито | Файл |
|---|---|---|
| 1 | autocheck.py (SHA_RE, sha_eq), checks/A-17.yaml, index-headings | flow-core/skills/flow-autocheck |
| 2 | autocheck.py git_diff_allowed: підстановка `<галузь>` | flow-core/skills/flow-autocheck |
| 3 | checks/A-18.yaml diff-allowed (answers.yaml, AI-DECISIONS) | flow-core/skills/flow-autocheck |
| 4 | `--stand-sha` (псевдонім `--modules-sha`) у check_guides.py | flow-package-build/skills/user-guide-builder |
| 5 | мітки Показників дашборда / Коробка входу / Коробка показу в шаблонах | concept-mapper, prototype-builder |
| 6 | skip_market_check: A-07.yaml, flow-map, A-21d | flow-core/references, checks |
| 7 | перелік установки website_slides + td_<галузь>_elearning | elearning-builder Крок 6, config-as-code Крок 4 |
| 8 | slice-coverage (A-21d у flow-map/step-skill-map/step-cards/checks; E3 — completeness-audit) | flow-core/references, completeness-audit |
| 9 | CS-plan-modules: лише модулі з каталогом | completeness-audit/scripts |
| 10 | product-decision-drafter: A-17b ∥ A-17c, INDEX | flow-package-evolution |
| 12 | Playwright/Chromium — засіб знімків за замовчуванням | user-guide-builder, prototype-builder |
| 13 | E6: test-kit CLAUDE.md (test-CLAUDE.md), flow-state-keeper | flow-core/references/templates/test-CLAUDE.md |
| 14 | `--answers` у script-check-elearning | elearning-builder, checks |
| 15 | рецензент A-17c = Власник продукту | support-kb-builder, картка A-17c |
| 16 | gates-aggregator: джерела повернень A-16b/A-17b/A-17c; demo-base-builder: A-16b refresh | gates-aggregator, demo-base-builder |
| 17 | лічильник checks (48), примітка A-17 на карті | flow-map, README |
| 18 | звірка зі стандартом Odoo: локальні вихідники 19.0 допустимі | elearning-builder, user-guide-builder |
| 19 | §27а: вирівняти RU-core / CM-box-core з td_knowledge | частково: склад RU-core / CM-box-core = 3 модулі (td_home_menu, td_support, td_knowledge) вирівняно; наповнення статтями td_<галузь>_knowledge з інструкцій A-16b відкладено на прохід після 0.4.0 (зараз статті пропонує лише support-kb-builder п. 5б) |

Первісний повний текст зауважень є в рецензіях workflow 0.4.0; тут зафіксовано лише факт закриття.

## Залишок після фінального кола (2026-11-15, людина: «нехай це буде останнє»)
- major: у тестових нарядах немає блоку `review:` — незалежний аудит покриття A-16b у тесті ніщо не запускає; у тесті «меблі» закриває менеджерська сесія зовнішнім аудитом Fable. До наступної версії: додати `review:` у шаблон наряду A-16b.
- minor: UG-cover-dev — один словник `po` на всі модулі, порядок обходу може дати хибний FAIL.
- minor: E2 `flow_position` не перевіряється автоперевіркою в тестовому режимі.
