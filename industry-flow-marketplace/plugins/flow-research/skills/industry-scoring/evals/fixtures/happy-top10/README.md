# Фікстури happy-top10

СИНТЕТИЧНІ дані (не з реєстру) для перевірки процедури, а не цифр: Q1–Q5.json — «відповіді» запитів із
`references/scoring-formula.md` на 40 розділів; db_schema.txt — копія відповіді `db_schema` на 2026-11-09;
snapshot.txt — вхід наряду з датою знімка; param.txt, decisions.md — параметр критерію і фрагмент
`flow/decisions.md`; search-results.json — результати веб-пошуку для 6 розділів (URL вигадані, example.com).

Еталон: `build_expected.py` збирає з фікстур `expected-scoring.md`, `expected-top10.json` (порядок:
15, 11, 03, 07, 36, 27, 25, 23, 42, 31) і `metrics.json`. Самоперевірка (має дати 0 FAIL):
`python3 -I build_expected.py . ../../../references && python3 -I ../../../scripts/check_scoring.py expected-scoring.md --param param.txt --metrics metrics.json --snapshot 2026-08 --exclude 84,97,98,99`.
