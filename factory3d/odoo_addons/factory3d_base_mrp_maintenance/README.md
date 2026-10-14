# factory3d_base_mrp_maintenance

Міст ENV-1 (`factory3d/build/ENV_DECISIONS.md`): `depends` = `factory3d_base`, `mrp_maintenance`; `auto_install`.
У `post_init_hook` заповнює порожні `maintenance.equipment.workcenter_id` за збігом `f3d_code` обладнання
з `f3d_code` робочого центру (A-15).

**Мост не тестирован — нет Enterprise** (`mrp_maintenance` є лише в Enterprise; у цьому середовищі не ставиться).
