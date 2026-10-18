# Changelog

## 19.0.1.0.0 — W4-C «Чергування (телефон)»: вкладка «Обхід», журнал, події на відхилення
- Моделі: `td.energy.round.template` (+ `.slot`, `.template.item`), `td.energy.round` (+ `.item`), `td.energy.event.kind='round'`,
  налаштування `td_energy_mobile_*` (M-H1…M-H7).
- API (ORM-RPC): `get_mobile`, `action_toggle_item`, `action_finish`, `action_start`, `get_journal`, `action_cancel` (API-H1…H6);
  значення пунктів — з `td.signal` або `get_pult(kpis)` (R-H4), виконавець блокується за першим, хто відмітив (D-76).
- Крони: відкриття (10 хв), закриття «не виконано» (15 хв), ротація (7 діб); `neutralize.sql` вимикає їх усі.
- Клієнт: вкладка «Обхід» у реєстрі `td_energy.mobile_tabs` (sequence 40, без `badge`), оптимістична відмітка, «Завершити обхід»,
  «Останні обходи»; на сторінці hoot (`/web/tests`) вкладку додають лише тести модуля, тож hoot W1 лишається з трьома вкладками.
- Дані: шаблон `TP-GRSH` (2 слоти, 6 пунктів; ПРИПУЩЕННЯ до узгодження з електриками, Q-H1), параметри `td.energy_mobile.*`.
- Правок `td_energy` модуль не вносить.
