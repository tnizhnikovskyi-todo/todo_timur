# DEPLOY_TEST td_factory3d (чек-лист §13.5)

Статус ТК: **ТК-01…ТК-06 ждут копию демо-базы** (бази `odoo` тестового сервера в цій середі немає;
`plant/odoo_push.py` вимагає живу Odoo з модулем `factory3d` — локально зібрати демо-базу швидко не вдалося).
Фактичні кількості: _не записані_.

Автоматично перевірено на чистій базі (`run_tests.sh f3d_factory3d_base_w5 /td_factory3d`): юніт-тести зелені,
установка без WARNING/ERROR, `migration_state='skipped'`, `neutralize.sql` виконується.

## Чек-лист
1. [ ] Дамп бази `odoo` → відновити як `odoo_f3d_test`; зберегти знімки S1–S5 (SPEC §13.2) у файли.
2. [ ] ТК-01: `-i td_factory3d --stop-after-init`; перевірити `migration_state=done`, звіт, кроки 1–11 у лозі.
   Очікувано: docks 14, locations 682, workcenters 35, employees 35, equipment 210 (203+7), linked 207,
   components 63, zones.bind roots 21/locations 695/workcenters 35/equipment 170, batches_updated 6/created 18/
   attached 18/total 24, mismatches 0, views_dropped 2, fields_dropped 3. Факт: ____
3. [ ] ТК-02 (коди й зони, SQL §13.2). Факт: ____
4. [ ] ТК-03 (пакети, S1/S2/S4, x_* зникли). Факт: ____
5. [ ] ТК-04 (інтерфейс, UI). Факт: ____
6. [ ] Юніт-тести на `odoo_f3d_test`: `--test-tags /td_factory3d` → 0 падінь. Факт: ____
7. [ ] ТК-05: повтор міграції (`batches_created: 0`), деінсталяція (x_* відновлені = S1; S3, S5 незмінні), повторна установка.
8. [ ] ТК-06 після правки `plant/odoo_pull.py` (Q-09).
9. [ ] Відкат: видалити `odoo_f3d_test`; робоча база не змінювалась (перед її установкою — `keep_x_fields=True`).
10. [ ] Записати фактичні кількості в CHANGELOG («Міграція демо 13.10.2026»).

## Не покрито юніт-тестом (потребує ТК/MAN)
AC-10…AC-12 і AC-14 на реальних кількостях, AC-19, AC-24…AC-31 на демо-даних, AC-34/35 на 207 одиницях — ТК-01…ТК-04.
