# Шаблони SQL для segment-selector

Діалект MySQL, один `SELECT`/`WITH` без `;`, ≤500 рядків — `industry-scoring/references/scoring-formula.md` §1.
Назви колонок нижче — з плану скіла; **ключ зв'язку `companies` ↔ `fin_history`, назви колонок року й виручки
в `fin_history` та формат `kved_2010` (з крапкою чи без) звірити з `db_schema` і першим запитом**. Позначено
`<ключ>`, `<рік>`, `<виручка>`. Не звіривши — не запускати. Кожен виконаний запит зберегти дослівно з номером
`Qn` у розділі «SQL-запити» файлу.

## Обов'язковий фільтр F (у кожному запиті)
```sql
c.status = 'зареєстровано' AND c.has_financials = 1 AND c.source IS NULL
AND c.kved_2010 LIKE '<префікс>%'        -- з decision.md; кілька префіксів: (… OR …)
-- + регіони/діапазони працівників і виручки з кроку 2 SKILL.md
```
Сегмент — лише `kved_2010`. `activities` не фільтрувати. `source='edr_dump'` — записи без регіону/КВЕД/контактів,
у пул не входять (умова `source IS NULL` — звірити значення з `db_schema`).

## Заборонені колонки
`ceo_name`, `phones`, `email`, `location` — не вибирати для файлів у репо, не вставляти у відповідь, не
писати в memo. Виняток — лише агрегати S4 (`COUNT` за доменом, без самих адрес).

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
       f24.<виручка> AS rev_2024, f25.<виручка> AS rev_2025
FROM companies c
LEFT JOIN fin_history f24 ON f24.<ключ> = c.<ключ> AND f24.<рік> = 2024
LEFT JOIN fin_history f25 ON f25.<ключ> = c.<ключ> AND f25.<рік> = 2025
WHERE <F> AND c.code NOT IN (<виключені ЄДРПОУ з crm.csv і попередніх раундів, пакетом>)
ORDER BY c.revenue DESC
LIMIT 200
```
Бал рахується поза SQL за `selection-criteria.md` (ілюстративні ваги). Відповідь >500 рядків не просити.

## S3. Детермінована вибірка зі seed і стратою (A-23)
```sql
SELECT c.code, LEFT(c.full_name,80) AS name, c.kved_2010, c.region, c.employees,
       MD5(CONCAT(c.code,'<seed>')) AS h
FROM companies c
WHERE <F> AND c.code NOT IN (<виключення>)
ORDER BY h
LIMIT 500
```
Страти за працівниками (наприклад, 3 рівні за терцилями пулу) і розкладка `варіант` A/B/C по колу всередині
кожної страти — поза SQL, з тим самим seed. Той самий seed -> той самий склад (SS-repro). Для A-23 у пулі
бажано лише компанії з корпоративним email: умову `email` не виводити, а відбирати через S4/службовий
фільтр `has_corp_email` без значення адреси (рядок `так/ні`).

## S4. Досяжність розсилки (лише агрегати)
```sql
SELECT COUNT(*) AS pool,
       SUM(c.email IS NOT NULL AND c.email <> '') AS with_email,
       SUM(SUBSTRING_INDEX(c.email,'@',-1) IN (<домени з free-mail-domains.md>)) AS free_domain
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
