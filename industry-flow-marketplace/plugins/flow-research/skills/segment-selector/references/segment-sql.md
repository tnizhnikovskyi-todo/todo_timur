# Шаблони SQL для segment-selector

Діалект MariaDB 11.4 (MySQL-сумісний), один `SELECT`/`WITH` без `;`, ≤500 рядків — `industry-scoring/references/scoring-formula.md` §1.
Колонки `fin_history`: `code` (ключ зв'язку з `companies.code`), `year`, `revenue` (перевірено `db_schema`
2026-11-09). Формат `kved_2010` (з крапкою чи без) і значення `source` звірити першим запитом. Кожен виконаний запит зберегти дослівно з номером
`Qn` у розділі «SQL-запити» файлу.

## Обов'язковий фільтр F (у кожному запиті)
```sql
c.status = 'зареєстровано' AND c.has_financials = 1 AND c.source IS NULL
AND c.kved_2010 LIKE '<префікс>%'        -- з decision.md; кілька префіксів: (… OR …)
-- + регіони/діапазони працівників і виручки з кроку 2 SKILL.md
```
Сегмент — лише `kved_2010`. `activities` не фільтрувати. `source='edr_dump'` — записи без регіону/КВЕД/контактів,
у пул не входять; `source IS NULL` = записи Opendatabot (`db_schema`).

## Заборонені колонки
`ceo_name`, `phones`, `email`, `location` — не вибирати для файлів у репо, не вставляти у відповідь, не
писати в memo. Винятки: (1) агрегати S4 і ознака `has_corp_email` у S3 — вирази без значення адреси;
(2) S6 — `email` лише в A-23 `адреси`, лише центральним агентом, результат лише в місце з DATA_POLICY
«Місця зберігання».

## S1. Розмір пулу
```sql
SELECT COUNT(*) AS pool,
       SUM(c.kved_ambig = 1) AS ambig,
       SUM(c.employees IS NULL) AS no_employees
FROM companies c WHERE <F>
```

## S2. Вибірка з даними для балу (A-05, B-01)
```sql
SELECT c.code, LEFT(c.full_name,80) AS name, c.kved_2010, c.region, c.employees,
       c.revenue, c.revenue_year, c.kved_ambig,
       f24.revenue AS rev_2024, f25.revenue AS rev_2025
FROM companies c
LEFT JOIN fin_history f24 ON f24.code = c.code AND f24.year = 2024
LEFT JOIN fin_history f25 ON f25.code = c.code AND f25.year = 2025
WHERE <F> AND c.employees BETWEEN <від> AND <до>   -- діапазон з кроку 2 SKILL.md; поза діапазоном — окремий запит ±1 розряд
  AND c.code NOT IN (<виключені ЄДРПОУ з crm.csv і попередніх раундів, пакетом>)
ORDER BY MD5(CONCAT(c.code,'<seed>'))
LIMIT <min(500, розмір пулу з S1)>
```
Порядок детермінований (seed), не за виручкою: виручка не зрізає пул до розрахунку балу. Бал рахується поза SQL
за `selection-criteria.md` (ілюстративні ваги). Відповідь >500 рядків не просити.

## S3. Детермінована вибірка зі seed і стратою (A-23)
```sql
SELECT c.code, LEFT(c.full_name,80) AS name, c.kved_2010, c.region, c.employees,
       (c.email IS NOT NULL AND c.email <> ''
        AND LOWER(SUBSTRING_INDEX(c.email,'@',-1)) NOT IN (<домени з free-mail-domains.md>)) AS has_corp_email,
       MD5(CONCAT(c.code,'<seed>')) AS h
FROM companies c
WHERE <F> AND c.code NOT IN (<виключення>)
ORDER BY h
LIMIT 500
```
Страти за працівниками (наприклад, 3 рівні за терцилями пулу) і розкладка `варіант` A/B/C по колу всередині
кожної страти — поза SQL, з тим самим seed. Той самий seed -> той самий склад (SS-repro). Склад списку A-23: лише рядки з `has_corp_email = 1` — додати `AND <вираз>` до WHERE (адреса не виводиться);
колонка лишається для SS-addr, у CSV завжди `так`. Корпоративних менше за розмір -> список коротший і розділ «Нестача…».
Рядки «ні» призначені для каналу «дзвінок Sales» і в цей файл не йдуть. `c.email` у SELECT вибірки не додавати.

## S4. Досяжність розсилки (лише агрегати)
```sql
SELECT COUNT(*) AS pool,
       SUM(c.email IS NOT NULL AND c.email <> '') AS with_email,
       SUM(LOWER(SUBSTRING_INDEX(c.email,'@',-1)) IN (<домени з free-mail-domains.md>)) AS free_domain
FROM companies c WHERE <F>
```
Корпоративні = `with_email - free_domain`. Адреси не повертаються. Орієнтир (знімок 2026-08, меблі,
`kved_2010 LIKE '31.0%'`): 1 486 / 507 / 413 -> корпоративних ~94; це факт одного вимірювання, не норма.

## S5. Повторна звірка списку (SS-registry, SS-repro)
```sql
SELECT c.code, c.status, c.has_financials, c.kved_2010
FROM companies c
WHERE c.code IN (<ЄДРПОУ пакетом ≤500>)
```
Розбіжності: `status <> 'зареєстровано'`, `has_financials <> 1`, `kved_2010` поза фільтром, ЄДРПОУ немає -> FAIL
рядка, рядок прибрати й назвати у memo.

## S6. Файл адрес (лише A-23 `адреси`, лише центральний агент)
```sql
SELECT c.code, c.email
FROM companies c
WHERE c.code IN (<ЄДРПОУ з mailing-list.csv, має_корп_email = так, пакетом ≤500>)
  AND c.email IS NOT NULL AND c.email <> ''
  AND LOWER(SUBSTRING_INDEX(c.email,'@',-1)) NOT IN (<домени з free-mail-domains.md>)
```
Після запиту (q07) відсіяти адреси, що містять ПІБ особи (`ім'я.прізвище@`): лишити загальні (role-based);
сумнівні виключити й порахувати. Відповідь не показувати в чаті й не вставляти в memo; записати лише в місце з
DATA_POLICY «Місця зберігання» (q08: Google Drive, доступ за ролями).
У «SQL-запити» репо — текст запиту без результату.
