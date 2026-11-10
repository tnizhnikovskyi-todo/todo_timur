| логічне ім'я | модель | технічне ім'я / значення | тип | примітка |
|---|---|---|---|---|
| stage.queue | project.task.type | Черга | stage | фікстура |
| stage.in_progress | project.task.type | В роботі | stage | |
| stage.on_human | project.task.type | На рішенні людини | stage | |
| stage.escalation | project.task.type | Ескалація | stage | |
| task.lease_until | project.task | x_lease_until | datetime | |
| stage.autocheck | project.task.type | Автоперевірка | stage | фікстура |
| stage.done | project.task.type | Готово | stage | фікстура |
| stage.returned | project.task.type | Повернено | stage | фікстура |
| stage.stopped | project.task.type | Зупинено | stage | фікстура |
| task.step | project.task | x_step | char | фікстура |
| task.executor | project.task | x_executor | selection | фікстура |
| task.client_data | project.task | x_client_data | selection | фікстура |
| task.scope_kind | project.task | x_scope_kind | selection | фікстура |
| task.scope_id | project.task | x_scope_id | char | фікстура |
| task.attempt | project.task | x_attempt | integer | фікстура |
| task.kind | project.task | x_kind | selection | фікстура |
| gate.decision | project.task | x_decision | selection | фікстура |
| project.ai_stop | project.project | x_ai_stop | boolean | фікстура |
| project.ai_stop_reason | project.project | x_ai_stop_reason | char | фікстура |
| project.flow_agent_users | project.project | x_flow_agent_users | many2many | фікстура |
