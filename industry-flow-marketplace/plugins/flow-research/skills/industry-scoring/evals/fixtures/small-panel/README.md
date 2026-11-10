# Фікстура small-panel

СИНТЕТИЧНІ дані (не з реєстру). Усі розділи довідника, крім виключених 84, 97, 98, 99 і двох відсутніх — 29 та 61
(як у живому odb-catalog: компаній з фінансами немає). У розділу 82 (7-й у топ-10) панель зростання = 10.
Порогу панелі в параметрі немає (`../happy-top10/param.txt`), тож N довідкове = 30.

Генерація (детермінована): `python3 -I gen_q2.py . ../../../references` -> Q2.json;
`python3 -I ../happy-top10/build_expected.py . ../../../references ../happy-top10` -> expected-scoring.md, expected-top10.json,
metrics.csv, metrics.json (Q1, param.txt, search-results.json — з happy-top10).

Очікувано: `python3 -I ../../../scripts/check_scoring.py expected-scoring.md --param ../happy-top10/param.txt --metrics-csv metrics.csv --snapshot 2026-08 --exclude 84,97,98,99`
-> SC-panel WARN (82, панель 10, N=30), SC-coverage WARN (29, 61), FAIL немає.
