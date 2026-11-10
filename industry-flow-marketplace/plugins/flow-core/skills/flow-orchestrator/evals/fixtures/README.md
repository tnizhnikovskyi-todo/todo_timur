# Фікстури евалів flow-orchestrator
- `minirepo/` — спільний мінірепо флоу: `flow/cards/` (A-11, A-12, A-13, A-14, A-15, B-04, B-06, B-10, D-01, D-02), `flow/flow-map.md` (копія `plugins/flow-core/references/`),
  `flow/ODOO_SCHEMA.md`, `flow/ARTIFACTS.md`, `package/flow/dispatcher.yaml`, `package/DATA_POLICY.md`, `plugins/<плагін>/.claude-plugin/plugin.json` (каталог версій).
  `sh setup.sh <тека>` створює git-репо й друкує SHA HEAD (його підставляє harness у `inputs[].sha` і `catalog`).
- `<id>/state.json` — знімок стану тестової бази flow для кейсу: `tasks` (стадії, звіти C-01 з `held_slot`), `open_tasks`, `stoplist`, `slots_used`, `catalog`, `ready`. Знеособлено, прод-даних немає.
- Завантаження стану: harness для кожного елемента `tasks` викликає `odoo_create` у тестову базу flow (`connection_id` бази flow) — задача з YAML `description`, стадією за `ODOO_SCHEMA.md`
  і звітом через `message_post` (`run:` YAML); `stoplist` — запис «AI зупинено» на проєкті. Альтернатива без бази: подати `state.json` як записані відповіді `odoo_search_read`.
- Кейси з `requires: odoo-mcp:test` запускаються проти тестової бази flow; фікстура — еталон початкового стану.
- Входи кейсів (A-11/A-12, перший запуск): за кроком 2.5 SKILL.md в autocheck іде по одному входу на крок-джерело (path = where реєстру: A-10 → ALLOCATION.md, A-08 → `docs/industries/demo/ТР.md`, A-09 → `package/questionnaire.md`); решта входів A-08/A-09 (`package/SPEC.md`, `package/templates/answers.yaml`, `answers.example.yaml`) перевіряються `git cat-file -e <sha>:<path>`; вхід A-14 (CHECKS.md) на першій спробі не включається. Плейсхолдер `<галузь>` → `demo`. Файли-заглушки є в `minirepo/`. Перевірено на всіх входах A-12: autocheck зі скороченим набором → PASS (exit 0), `cat-file -e` для трьох решти → ok.
- Логічні імена для стоп-листа, згоди, «на супроводі», параметрів і виконавця — у `minirepo/flow/ODOO_SCHEMA.md`; `consent`/`on_support` у `state.json` відповідають `partner.ai_consent`/`partner.on_support`.
- Картка B-01 у мінірепо не потрібна: кейс `monthly-order` перевіряє «не дубльовано» за наявною задачею B-01 зі `state.json`; D-02(а) залежить лише від стадії цієї задачі.
