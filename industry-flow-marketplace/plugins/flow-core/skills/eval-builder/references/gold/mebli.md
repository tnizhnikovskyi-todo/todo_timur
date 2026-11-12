# Еталон «меблі»: індекс евал-кейсів хронології галузі (WP-11; N-17)

**Правило «посилання, не копія»**: кейс посилається на еталонний артефакт шляхом і SHA (заголовок розділу), а не копією даних. Еталон — репо тестового флоу галузі `mebli` (`docs/industries/mebli/`, `tests/reports/`, `observations/`) і `_work/FIRST-TIME-RIGHT.md` §1 (хронологія зауважень людини). Копіювати меблевий зміст, дані клієнтів, бінарники зрізу (png, mp4) у `evals/` заборонено; фікстура — **шлях + SHA** (для візуальних кейсів — шлях до кадру/скріна у репо еталона + SHA коміту й, за потреби, опис «що видно»).
SHA еталонів: відкрите питання (`references/open-questions.md`, п. 3; передано координатору для додавання до §5 плану) — SHA тестового репо «меблі» на момент прийняття людиною невідомий. Його вписує AI-інженер при `init` в окрему колонку таблиці нижче; до того кейси хронології відтворювані лише за описом (`FIRST-TIME-RIGHT` §1), у INDEX — «SHA еталона: відкрите питання», SHA не вигадувати.

## Таблиця «зауваження FTR §1 -> кейс -> скіл -> WP»
| FTR §1 № | Кейс (id) | Скіл (набір `evals/<скіл>/`) | WP власника скіла | SHA еталона (репо «меблі») |
|---|---|---|---|---|
| 1 | `mebli-r01-html-mock-instead-of-slice` | prototype-builder | 09 | відкрите питання (до `init`) |
| 2, 7 | `mebli-r02-not-selling`, `mebli-r07-regress-approved-dynamics` | showcase-content | 10 | відкрите питання (до `init`) |
| 3 | `mebli-r03-no-brand` | showcase-content (+ check_brand) | 10 | відкрите питання (до `init`) |
| 4, 6 | `mebli-r04-formats-mobile`, `mebli-r06-static-frames` | showcase-content | 10 | відкрите питання (до `init`) |
| 5 | `mebli-r05-buyer-without-dashboard` | concept-mapper | 07 | відкрите питання (до `init`) |
| 8 | `mebli-r08-content-role-missing` | showcase-content | 10 | відкрите питання (до `init`) |
| 9, 17 | `mebli-r09-no-lesson`, `mebli-r17-remark-not-recorded` | skill-retro, flow-step-runner | 11 | відкрите питання (до `init`) |
| 10, 18 | `mebli-r10-shallow-industry`, `mebli-r18-sources-coverage` | industry-deep-dive | 06 | відкрите питання (до `init`) |
| 11, 15 | `mebli-r11-md-not-page`, `mebli-r15-three-pages` | concept-presentation | 08 | відкрите питання (до `init`) |
| 13 | `mebli-r13-no-rejected-register` | industry-deep-dive, concept-presentation | 06, 08 | відкрите питання (до `init`) |
| 14 | `mebli-r14-competitor-names-only` | industry-deep-dive | 06 | відкрите питання (до `init`) |
| 16, 24 | `mebli-r16-editions-asked-late`, `mebli-r24-owner-questions-after-synthesis` | owner-questionnaire | 05 | відкрите питання (до `init`); r24 застаріло в 0.3.0: питань власнику після синтезу немає, лише вето на A-20c |
| 19 | `mebli-r19-internal-raw-push` | past-projects-analyzer (+ preflight) | 05 | відкрите питання (до `init`) |
| 20 | `mebli-r20-no-reuse-block` | reuse-modules | 05 | відкрите питання (до `init`) |
| 21 | `mebli-r21-incomplete-concept` | completeness-audit | 07 | відкрите питання (до `init`) |
| 22 | `mebli-r22-ee-claim-unverified` | industry-deep-dive | 06 | відкрите питання (до `init`) |
| 23 | `mebli-r23-owner-returned-rejected` | industry-deep-dive, concept-mapper | 06, 07 | відкрите питання (до `init`); застаріло в 0.3.0: K1 і «правило доказів» скасовано (LESSONS §24), кейс лишається як історичний |
| С-01 | `mebli-c01-ai-recommends-against-intake` | concept-mapper | 07 | відкрите питання (до `init`) |
У цьому плагіні (WP-11) власні кейси r09 і r17 живуть в `skill-retro/evals` і `flow-step-runner/evals`; решту кейсів ведуть власники своїх скілів у WP 05–10 (`evals/evals.json` скіла). `eval-builder` лише веде цей індекс, перевіряє наявність кейсів за `id` (`init-complete`) і прогоняє регрес.

## Як читати кейс хронології
Кейс має форму «**поганий артефакт -> рецензент (скіл або чек-лист) має повернути**»: фікстура — посилання на еталон поганої версії (шлях@SHA), `expected.checks` — що рецензент називає (за чек-листом з `review-checklists/`), `must_not` — «схвалити/пропустити». Кейс **червоний на версії, де людина побачила помилку** (антипатерн 3 з `case-sources.md`).
