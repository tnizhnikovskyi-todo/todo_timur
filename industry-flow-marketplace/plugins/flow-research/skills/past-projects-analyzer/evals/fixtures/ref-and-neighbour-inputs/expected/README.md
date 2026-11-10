Очікуваний результат: П-01 — код td_edge читається за ref `build/x` із sources.md (`git show build/x:…` або `origin/build/x:…`); `repo:odoo_addons/td_edge@<sha>`,
sha — коміт гілки build/x (його немає на гілці за замовчуванням). П-02 — ref немає, коду на гілці за замовчуванням немає: гілку build/x з `docs/build-log.md` агент
сам для П-02 не обирає, у «Прогалинах» запис про неповноту коду й відкрите питання про ref у memo. N = 2, П-03 виключено.
Збирання: `bash evals/fixtures/_common/setup_repo.sh ref-and-neighbour-inputs <dest>` (хук setup.sh створює гілку build/x і кладе crm.csv, README.md у `_input/`).
Перевірка: `check_past_projects.py --doc <результат> --sources <dest>/docs/industries/furniture/_input/sources.md --repo <dest> --scope-files docs/industries/furniture/past-projects.md` — PP-ref PASS, PP-input PASS.
Підстановка `<sha>` у expected/past-projects.md: `sed -i "s/<sha>/$(git -C <dest> rev-parse --short build/x)/" <результат>` (з `<dest>` — тека, зібрана setup_repo.sh).
