# factory3d_telemetry

Спільний хребет збору даних factory3d (Odoo 19): колектори, джерела, сигнали, показання, команди;
API `/f3d/telemetry/*`; пороги → заявки ТО; ТО за лічильником. Клієнт — `factory3d/services/collector`.
Специфікація: `factory3d/docs/modules/factory3d_telemetry/SPEC.md`.

## Встановлення

Залежності: `factory3d_base`, `maintenance`, `mail`, `bus`. Міст до переглядача — `factory3d_telemetry_viewer`
(auto_install). Хук `post_init` виконує міграцію демо рівня 0 (звіт — у параметрі `level0_migrated`).

    F3D_TEST_INSTALL=factory3d_telemetry,factory3d_telemetry_viewer \
        factory3d/tools/odoo/run_tests.sh <db> /factory3d_telemetry,/factory3d_telemetry_viewer

## Параметри (`ir.config_parameter`, `factory3d.telemetry.*`, noupdate)

| Ключ | За замовчуванням | Призначення |
|---|---|---|
| `read_enabled` | `True` у тестах, інакше `False` (CB-10) | стоп-кран прийому показань (інакше API відповідає 423) |
| `write_enabled` | `False` | стоп-кран команд запису в пристрої |
| `keep_days` / `keep_hours_days` | 30 / 400 | зберігання сирих показань / годинних агрегатів |
| `default_store_period_s` | 300 | період запису за замовчуванням |
| `stale_periods` / `stale_min_s` | 3 / 60 | поріг «застарілий» |
| `bus_min_interval_s` | 10 | мінімальний інтервал повідомлень bus |
| `realarm_cooldown_s` | 3600 | пауза повторної тривоги |
| `push_max_readings` / `push_rate_per_min` | 2000 / 60 | ліміти API прийому |
| `meter_lead_pct` | 5 | випередження заявки ТО за лічильником |
| `default_team_id` | порожньо (хук) | команда для заявок |
| `drop_level0`, `level0_migrated` | `False`, `{}` | міграція рівня 0 |
| `stale_notify_min` | 0 | зарезервовано (Q-11) |

## Інструкції (ARCHITECTURE §4, коротко)

1. Колектор: Завод 3D → Телеметрія → Колектори → створити, «Згенерувати токен» (показується один раз),
   вписати в `.env` колектора, запустити `docker compose up -d`; через ≤ 2 хв стан «онлайн».
2. Пристрій Modbus: Джерела → створити (хост у `F3D_ALLOW_HOSTS`), Сигнали → адреса, період; «Перевірити адресу».
3. Поріг і заявка: на сигналі задати «Тривога, вище», гістерезис, заголовок заявки; заявка з'являється в ТО.
4. ТО за лічильником: вкладка «Сигнали» обладнання → група «ТО за лічильником» (сигнал, інтервал, останнє ТО).
5. Стоп-крани: Налаштування → Завод 3D → Телеметрія («Приймати показання», «Дозволяти команди»).
   Копія проду — `tools/neutralize.sql`.
6. Журнал і графік: Завод 3D → Телеметрія → Показання (графік 2 доби), «Годинні агрегати» для довших періодів.
