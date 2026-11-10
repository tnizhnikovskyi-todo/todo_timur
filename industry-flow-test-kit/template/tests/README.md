# tests/

- `naryad/<крок>.yaml` — наряди тесту (формат `industry-flow-marketplace/plugins/flow-core/references/naryad-format.md`, режим «підготовка матеріалів», без Odoo).
  Додатково `A-23-spisok.yaml` — попередній крок `segment-selector` (режим `список`), потрібний для `A-23.yaml` (режим `prep`).
- `reports/<ім’я наряду>[-<спроба>].md` (A-23-spisok.md, A-23.md, A-04-1.md, A-04-2.md) — звіт кроку (формат `report-format.md`); пише сесія замість `message_post`.
- Порядок і готові промпти — `TEST-START.md`.
