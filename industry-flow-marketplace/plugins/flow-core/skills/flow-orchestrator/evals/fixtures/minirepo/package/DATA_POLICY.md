# DATA_POLICY (фікстура)

## Відкликання згоди на AI-обробку
Клієнт з «AI-обробка: відкликано»: кроки з `clientData: personal` виконує лише людина.

## Класи доступу до баз Odoo (allow-list)
| клас кроку | alias |
|---|---|
| код/конфіг пакета | flow, test-<клієнт> |
| D-01 collect | flow (дані — вивантаження людини, params.upload_path) |
| client-help-bot (q37) | prod-ro-k01 (лише читання; `client_data: personal`, `executor: central`) |
