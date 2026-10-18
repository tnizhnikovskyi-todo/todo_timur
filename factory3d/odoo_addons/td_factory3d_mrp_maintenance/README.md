# td_factory3d_mrp_maintenance

Міст ENV-1 (`factory3d/build/ENV_DECISIONS.md`): `depends` = `td_factory3d`, `mrp_maintenance`; `auto_install`.
У `post_init_hook` заповнює порожні `maintenance.equipment.workcenter_id` за збігом `td_code` обладнання
з `td_code` робочого центру (A-15).

**Мост не тестирован — нет Enterprise** (`mrp_maintenance` є лише в Enterprise; у цьому середовищі не ставиться).
