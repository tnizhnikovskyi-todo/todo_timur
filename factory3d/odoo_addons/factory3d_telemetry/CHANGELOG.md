# Changelog

## 19.0.1.1.0
- CR-01: узгоджено payload команд запису (API-06/07) між Odoo і колектором.
- Правки за зауваженнями X-xx (узгодження SPEC/ARCHITECTURE, тестів і даних стенда).
- Форматування (ruff), README модуля, мосту та колектора, закріплені версії в requirements.txt.

## 19.0.1.0.0
- Перший випуск: колектори, джерела, сигнали, показання, годинні агрегати, команди; API `/f3d/telemetry/*`;
  пороги → заявки ТО; ТО за лічильником; міграція демо рівня 0; міст `factory3d_telemetry_viewer`.

## Міграція демо

Фактичні результати хуків рівня 0:

| Сценарій | Результат |
|---|---|
| Чиста база | state=skipped; каталог: created=29, bound=28, bind_missing=27, no_equipment=29; meters=0 |
| З `iot_sim` без `x_f3d_signal` | signals_migrated=0, state=done; sim_catalog: updated=27, unparsed=2 |
| Копія демо-бази | не перевірено (немає бази) |
