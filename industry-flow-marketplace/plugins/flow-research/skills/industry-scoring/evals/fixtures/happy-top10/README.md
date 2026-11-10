# Фікстури happy-top10

СИНТЕТИЧНІ дані (не з реєстру) для перевірки процедури, а не цифр: Q1–Q4.json — «відповіді» запитів із
`references/scoring-formula.md` на 40 розділів (Q1 покриття, Q2 усі метрики одним запитом: sec, companies, revenue, r_last, r_base, panel_n; Q3 ambig_share; Q4 SC-repro на 3 розділи топ-10); db_schema.txt — копія відповіді `db_schema` на 2026-11-09;
snapshot.txt — вхід наряду з датою знімка; param.txt, decisions.md — параметр критерію і фрагмент
`flow/decisions.md`; search-results.json — результати веб-пошуку для 6 розділів (URL вигадані, example.com).

Еталон: `build_expected.py` збирає з фікстур `expected-scoring.md`, `expected-top10.json` (порядок:
15, 11, 03, 07, 36, 27, 25, 23, 42, 31) і `metrics.json`. Самоперевірка (має дати 0 FAIL; SC-coverage дає WARN, бо фікстура — лише 40 розділів):
`python3 -I build_expected.py . ../../../references && python3 -I ../../../scripts/check_scoring.py expected-scoring.md --param param.txt --metrics-csv metrics.csv --snapshot 2026-08 --exclude 84,97,98,99`.

Три форми порогу панелі в параметрі (кожна має розпізнаватися; перевірка на фікстурі `../small-panel/`, панель топ-10 ≤ 1 200):
`for p in "мін. панель 5000" "мінімальна панель для growth = 5000" "min_panel=5000"; do f=$(mktemp); echo "$p" > "$f"; python3 -I ../../../scripts/check_scoring.py ../small-panel/expected-scoring.md --metrics-csv ../small-panel/metrics.csv --param "$f" --snapshot 2026-08 --exclude 84,97,98,99; rm -f "$f"; done`
— у всіх трьох SC-panel каже «< 5000» (N з параметра), а не довідкове 30. SC-criterion FAIL у цій перевірці очікуваний (параметр з одного рядка не збігається з формулою еталона); дивитися лише на SC-panel.
