# Відкриті питання package-release-builder (продовження)

5. Клас «чиста база пакета» — `test-pkg-<пакет>` (визначено в `data-and-connections.md`); окремого `ci-<пакет>` немає.
6. Рішення q29 (стосується A-12, не R-09 тут): у версії 0.1 конфіг-пакет приймається за покроковою інструкцією; R-09 «установка однією командою» лишається вимогою релізу.
6a. Скрипти C-00 (установка за тегом, smoke, імпорт шаблонів) ще не існують — maturity <= 1, режим «вручну».
7. Шаблони migration-plan/training — сумісні розділи з `data-migration-planner`/`user-training-builder`, не дослівно.
8. Патч зі зміною моделей td_* при незмінній `version` не підтримується. Рішення q19: формат `version` — `19.0.X.Y`, тег `package/vX.Y`, суфікс `-odoo<N>` -- лише для гілок і тегів переходу на нову мажорну Odoo (`versioning.md`). Тег режиму `odoo-upgrade` -- `package/vX.Y-odoo<N>` (рішення q19).
10. `flow-step-runner`: при `waiting_human` пушити гілку кроку; на resume з тим самим `attempt` робити checkout наявної `origin/flow/...`, а не створювати гілку від `base_branch` (інакше перевірка кроку 8, запуск 2, п.1 дає ескалацію «гілку не запушено» на кожному повторі). Також: автоматичний resume після push без підкроку людини (Тімлід «дочекатись push» — суто технічне очікування) — до `flow-orchestrator`.
9. Планові спільні файли (§3.10): `flow-core/skills/flow-step-runner/references/pr-checklist.md`, `flow-package-build/references/module-skeleton.md`.
