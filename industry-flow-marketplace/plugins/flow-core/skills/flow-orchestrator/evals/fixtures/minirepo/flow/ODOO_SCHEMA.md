| логічне ім'я | модель | технічне ім'я / значення | тип | примітка |
|---|---|---|---|---|
| stage.queue | project.task.type | Черга | stage | фікстура |
| stage.in_progress | project.task.type | В роботі | stage | |
| stage.automatic_check | project.task.type | Автоперевірка | stage | |
| stage.on_human | project.task.type | На рішенні людини | stage | |
| stage.done | project.task.type | Готово | stage | |
| stage.returned | project.task.type | Повернено | stage | |
| stage.escalation | project.task.type | Ескалація | stage | |
| stage.stopped | project.task.type | Зупинено | stage | |
| task.lease_until | project.task | x_lease_until | datetime | |
| task.step | project.task | x_step | char | |
| task.scope | project.task | x_scope | char | |
| project.prod_alias | project.project | x_prod_alias | char | лише `prod-metrics-<код>` |
| project.flow_agent_users | res.users | група «Агенти флоу» | group | |
| project.ai_stopped | project.project | x_ai_stopped | boolean | стоп-лист «AI зупинено» |
| partner.ai_consent | res.partner | x_ai_consent | selection | `given` / `withdrawn` («AI-обробка: відкликано») |
| partner.on_support | res.partner | x_on_support | boolean | клієнт «на супроводі» |
| task.params | project.task | x_params | text | параметри флоу (YAML) |
| task.executor | project.task | x_executor | selection | central / any / human |
| task.attempt | project.task | x_attempt | integer | |
