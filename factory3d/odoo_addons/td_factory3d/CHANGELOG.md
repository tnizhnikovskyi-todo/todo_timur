# Changelog

## Unreleased
- Тест `test_view_js_guards`: у виглядах усіх встановлених factory3d_*/td_genset немає Python-конструкцій у JS-виразах канбану (`in (...)`, `not`, `True`), `datetime.time.min/max` у доменах і порівнянь поля з полем (QA меню 16.10.2026).

## 19.0.1.0.0
- Первый выпуск: каркас, группы, параметры, меню.
- W5: оркестратор `post_init_hook` (кроки 1–11, звіт), `uninstall_hook`, server action
  «Повторити міграцію демо-даних», тести прав і хуків, `DEPLOY_TEST.md`, міст `factory3d_base_mrp_maintenance`.
- Розділ «Міграція демо 13.10.2026»: фактичні кількості будуть записані після ТК-01…ТК-05 (див. DEPLOY_TEST.md).
