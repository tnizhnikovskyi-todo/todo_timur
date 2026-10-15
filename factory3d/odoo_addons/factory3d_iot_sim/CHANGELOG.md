# Changelog — factory3d_iot_sim

## 19.0.2.0.0
- Пульт емулятора (`f3d.sim.panel`), пристрої/сигнали (каталог 1168, з них 151 `protocol=none`), сценарії (15), запуски, події,
  майстри запуску сценарію і збою, API для сервісу (`/f3d/sim/health|devices|events`), крон рівня 0 з автоперемиканням,
  `neutralize.sql`, групи доступу `group_f3d_user/manager/admin`.
- Стенд (W6): перевірено ТК-01 (follow_odoo), ТК-10, ТК-15, ТБ-05/08/09/10, ТП-06 (частково) на шаблонній базі; див.
  `docs/modules/factory3d_iot_sim/TEST_REPORT.md`, `DEPLOY_TEST.md`.
- Додано `static/description/icon.png`.
