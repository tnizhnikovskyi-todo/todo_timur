# Фікстура mebli-r19-internal-raw-push

Синтетична. `OWNER-INTAKE.md` (todo_data.allowed_sources містить crm), `odoo/crm_lead.json` — 23 програні ліди за ціною (3 сторінки по 10), `preflight-result.md` — push заборонено.
Очікувано: N=23 повним перебором; сирі спостереження в research/sources/ (не запушені); у past-projects.md лише агрегати; PP-internal PASS.
Еталон «меблі»: гілка `flow/A-03b-deep` @ 008541fb4d4ced7adfa7061c1edf5576eaa9bf36 (тестове репо `/home/user/industry-flow-test-mebli`), `docs/industries/mebli/research/`.


Увага: назви полів у `odoo/crm_lead.json` (`lost_reason`, `kved_section`) умовні й не є полями Odoo; у реальному запиті їх беруть з `odoo_get_fields`.
