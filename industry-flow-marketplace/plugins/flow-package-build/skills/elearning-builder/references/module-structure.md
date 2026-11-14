# Структура модуля `td_<галузь>_elearning`

```
td_<галузь>_elearning/
  __init__.py
  __manifest__.py        # depends: ['website_slides'] (+ 'website_slides_survey' лише після підтвердження у 19.0)
  README.md              # джерела звірки 19.0 (файл:рядок), як вмикається/вимикається, поріг
  data/
    params.xml           # ir.config_parameter: *.pass_score (за замовчуванням 80), *.mode (on|off)
    courses_<роль>.xml   # курс ролі + уроки + урок-тест + питання + відповіді (або один courses.xml)
  static/img/<роль>/     # копії знімків з package/docs/user-guide/img/<роль>/ (SC-NN-N.png)
  tests/
    __init__.py
    test_courses.py      # установка, курсів = ролей, >=5 питань на курс
```

Правила:
- Ім'я модуля — `td_<код галузі>_elearning` (код з пакета, напр. `td_mebli_elearning`); версія — за правилами `package-release-builder/references/versioning.md`.
- Маніфест: `license` як у решти `td_*` пакета (A-11), `depends` мінімальний; `data` — у порядку params -> курси.
- Усі `id` записів — локальні (`course_<роль>`, `lesson_<роль>_<n>`, `test_<роль>`, `q_<роль>_<n>`, `a_<роль>_<n>_<m>`); посилання `ref` — на ці id.
- Коментарі-маркери всередині `<record>`: `role: <роль>` (курс), `source: <роль>.md#SC-NN` (урок), `multi: true` (питання); їх читає `check_elearning.py`.
- Імена моделей і полів у прикладі — **чернетка**; перед використанням звірити з вихідниками 19.0 (`source-verification.md`).
- Дані `noupdate="1"`, щоб оновлення модуля не затирало правки клієнта (B-07 адаптує курси на клієнті).
- Без даних клієнтів; демо-користувачів курси не створюють.
