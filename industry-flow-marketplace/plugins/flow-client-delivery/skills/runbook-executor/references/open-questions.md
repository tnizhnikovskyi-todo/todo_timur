# Відкриті питання runbook-executor
- Картка B-13 (`clientData: commercial, executor: any`) суперечить dataRule B-08a: тестова база після B-06 містить персональні дані. Тут: після B-06 вимагається `executor: central`. Потрібна правка картки B-13.
- Запис `project.test_tag` робить runner/`flow-state-keeper`; підтвердити, що `report-format.md` приймає блок `project_fields` у memo (або додати структуроване поле).
- Конфлікт з карткою B-11: її failureModes забороняють AI «звіряти конфіг з config-log.md через odoo-mcp», а
  CONCEPT §2.4 дає B-11 режим «звірка». Тут звірка — лише метадані (`reconcile-scope.md`), результат — чернетка,
  перелік затверджує Тімлід. Потрібне рішення людини й правка failureMode B-11.
- Хто ставить модулі тегу: тут розгортання коду — Тімлід/C-00, `button_immediate_install` — лише в B-04 (а);
  картка B-11 вважає «AI сам установив тег» помилкою. Підтвердити.
- Картка B-04 `access` дозволяє запис «користувачів»; тут AI користувачів не створює (заводить Тімлід/BA).
- Статус інциденту: тут «виправлено на тесті — передано в B-12»; формулювання B-13 («-> застосовано в прод») — B-12.
- `config-drift.md` — новий артефакт: погодити шлях і внести в `flow/ARTIFACTS.md` та `inArtifacts` B-08a, B-11.
- Чи є в `package/config/` машинна мапа VP -> якір; без неї «звірка» деградує до ручної (вимога до A-12).
- Шаблон `package/templates/config-log.md` на тегу може бути відсутній -> `references/config-log-format.md` цього скіла і memo «шаблон не в пакеті».
- Конкретні ORM-патерни (`res.config.settings`, поля Odoo 19) не звірені з документацією: перед першим
  використанням — `boost:source-check`; чого не підтверджено — «очікує: виконує людина».
- Семантика `ir.module.module`: `latest_version` (збережена, версія в БД) vs `installed_version` (обчислювана, маніфест на диску) прийнята з пам'яті й узгоджена з `package-upgrade-runner/references/module-state-check.md`; локальних сирців Odoo немає — UNVERIFIED, підтвердити `boost:source-check` (`odoo/addons/base/models/ir_module.py`, 19.0), зокрема `adapt_version`. Узгодити формулювання `package-release-builder` (рядок 60).
- До першого бойового запуску підтвердити семантику `latest_version`/`installed_version` і `adapt_version` через `boost:source-check` за `odoo/addons/base/models/ir_module.py` (19.0) і зняти позначку UNVERIFIED одночасно тут і в `package-upgrade-runner` (В-10).
