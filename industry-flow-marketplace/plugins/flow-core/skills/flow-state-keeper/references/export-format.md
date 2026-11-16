# Формат знімка й експортних файлів (C-02)

Джерело колонок і шапки — `flow-core/references/flow-state.md` §2–§4 (копія — `package/templates/flow-state.md`); тут — лише те, що потрібно рендереру `scripts/state_export.py`. Файли рендерить **скрипт**, не модель: модель збирає JSON-знімок з Odoo, скрипт видає md.

## Знімок (JSON; частинами — одна тека `parts/*.json`, скрипт зливає й дедуплікує, останній виграє)
```json
{"schema_version": 1, "taken": "<ISO>", "repo_sha": "<sha>",
 "package": {"industry": "", "package_tag": "", "candidate_tag": null, "phase": "", "flow_version": 2},
 "steps": [{"step": "B-09", "scope": "client/cl-03", "state": "done", "attempt": 1, "last_report": "<ISO>", "pr": "<url|null>", "task": "odoo:task/412"}],
 "clients": [{"client_id": "cl-03", "state": "супровід", "current_step": "B-10", "flags": ["підтверджено PM: ні"], "changed": "<дата>",
              "pilot": false, "package_tag": "", "candidate_tag": null, "go_live": "<дата>", "test_alias": "test-cl-03",
              "aggregates_consent": true, "ai_stop": false, "approve_sha": null, "gmail_label": null, "contract_file_id": null}],
 "decisions": [{"decision_id": "D-0007", "date": "", "gate": "B-08c", "scope": "", "decision": "затверджено", "returned_to": null, "role": "PM", "task": "odoo:task/398", "comment": "<=200 символів"}],
 "runs": [{"step": "", "scope": "", "attempt": 1, "result": "done", "finished": "<ISO>", "skill_versions": {"плагін:скіл": "0.1.0"}, "usage": {"cost_usd": 0, "tokens_in": 0, "tokens_out": 0}, "task": ""}],
 "open_questions": [{"date": "", "step": "", "question": "", "owner": "", "status": ""}],
 "ai_stop": [{"type": "", "id": "", "reason": "", "date": "", "by": ""}]}
```
Стабільні ключі рядків: steps `step|scope`; runs `step|scope|attempt`; decisions `decision_id`; clients `client_id`; open_questions `date|step|question`; ai_stop `type|id`. Значення без даних — `null` (у файлі `н/д`); булеві — так/ні.

## Інкрементність
`--merge`: частини зливаються з `flow/.snapshot.json` у клоні (стабільні ключі нижче; рядки, яких немає у частинах, зберігаються; `decisions` лише додаються, наявне рішення не перезаписується; у `runs` база зберігає лише білий список колонок). Без `--merge` знімок має бути повним. `last_export` — `taken` бази.

## Правила рендеру (скрипт робить їх сам)
- Шапка однакова в усіх файлах (`flow-state.md` §2); `taken` і `repo_sha` беруться зі знімка — повторний рендер того самого знімка дає **порожній diff**.
- Файли: `flow/state.md`, `flow/decisions.md`, `flow/open-questions.md`, `flow/ai-stop.md`, `flow/runs/<YYYY-MM>.md` (по `finished`; один рядок на запуск), `clients/REGISTRY.md`. Сортування: за кроком (природне), `scope`, `attempt`; клієнти — за ідентифікатором; рішення — за `decision_id`.
- Запуск у `flow/runs/` — лише білий список колонок (`step, scope, attempt, result, skill_versions, usage, задача`); `memo`, `checks[].msg`, тексти зауважень скрипт не друкує, навіть якщо вони є у знімку.
- Знімок із e-mail, телефоном, URL, секретом, ПІБ-подібним, ЄДРПОУ/IBAN або alias бази з `:`/`/`/`@` → `render`/`verify` завершуються з кодом 2 і переліком полів (без значень). Це друга лінія захисту; перша — не класти такого у знімок.
- Ідентифікатор клієнта — за `package/DATA_POLICY.md` «Ідентифікатор клієнта в репозиторії» (формат `cl-NN`); юрособа, ЄДРПОУ, контакти — ніколи.
- Ростер, табель, `project.flow_agent_users` і «Параметри флоу» в експорт не потрапляють.

## Команди
```
python3 -I scripts/state_export.py check-ids --ids ids.json
python3 -I scripts/state_export.py render  --merge --snapshot parts/ --out <клон репо>
python3 -I scripts/state_export.py verify  --merge --snapshot parts/ --dir <клон репо> [--show]
python3 -I scripts/state_export.py prune   --older-than 2026-01 --dir <клон репо>
python3 -I scripts/state_export.py stats   --runs runs-p1.json runs-p2.json
```

## Зрілість і рядок «Рішення:» (q16, q22)
Після кнопки рішення про зрілість скіла keeper вписує нову `maturity` і рядок «Рішення: <скіл>, <стара> → <нова>, <користувач>, <дата кнопки>» у PR автоекспорту; дозволені лише шляхи `flow/**` (+ `clients/REGISTRY.md`) — інакше auto-merge не спрацює. Блокуюче відкрите питання для власника (Тімлід / Власник продукту; не вигадувати): носій не визначено (пропозиція: ключ `maturity` картки `flow/cards/<код>.json` + рядок у журналі рішень; шлях карток теж відкритий); до рішення maturity у репо не змінюється, рядок іде в опис PR і звіт, файл не створюється.

Поле `flags` клієнта: «підтверджено PM: ні» (рішення q44) позначає ознаку, яку D-01 і B-10 беруть із позначкою «не підтверджено PM»; споживачі показують цю позначку у своїх звітах.

## Режим `manager` (0.4.2): без Odoo й без `state_export.py`
`state_export.py render` вимагає знімка Odoo (`--snapshot`) і в `manager` **не запускається**: файли пише менеджер вручну за правилами нижче (скрипт — лише для `queue`). Джерела — `tests/reports/<наряд>.md` (блоки `run`, `handoff`, `checks`) і `flow/decisions.md`; ті самі правила приватності (без `memo`, текстів `checks[].msg`, ПДн, URL-секретів).

**`flow/runs/<наряд>.md`** — один файл на наряд (у `queue` — `flow/runs/<YYYY-MM>.md`), шаблон:
```
# <наряд> — <result>
| step | scope | attempt | result | skill_versions | usage | pr | head_sha | base | finished |
|---|---|---|---|---|---|---|---|---|---|
| <крок> | <scope> | <N> | <done|returned|…> | <плагін:скіл x.y.z> | $<cost> (оцінка) | <#PR або url> | <sha> | <гілка старту> | <ISO> |
Кола рецензії: <review_rounds>. Рішення AI: <AI-NN, …>. Дефекти: <D-NN, …|нема>.
```
Білий список колонок той самий, що для `queue` (`step, scope, attempt, result, skill_versions, usage` + `pr, head_sha, base, finished` із `handoff`); текст `memo` і зауважень не друкувати.

**`flow/state.md`** — збудувати **з нуля** з `tests/reports/*.md` і `flow/decisions.md` (не доповнювати наосліп): 1) шапка: `<!-- Знімок із tests/reports/ і flow/decisions.md; режим manager; не редагувати вручну -->` (рядок заглушки «ТЕСТОВИЙ РЕЖИМ. Заглушка… Не оновлювати» **замінюється** цим), `Знято: <дата> · SHA репо: <HEAD гілки> · Джерело: tests/reports + flow/decisions.md · Версія схеми: 1`; 2) розділ «Пакет» — поля заглушки (`package_tag`/`candidate_tag` з `handoff` релізу або `н/д`; `фаза`, `flow_position` — з останнього звіту); 3) «Кроки пакета» — один рядок на наряд (`step|scope|стан|спроба|останній звіт|PR|задача=—`), останній звіт кроку виграє; 4) «Клієнти» — порожньо; 5) «Рішення» — посилання на `flow/decisions.md`. Повторний `export` того самого стану дає порожній diff.
