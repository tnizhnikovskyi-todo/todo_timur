# Реестр дефектов QA (timur-o19demo)

Источник — отчёты `factory3d/build/qa/<m>.md`. Статусы: OPEN → FIX (в работе у coder) → DONE (в `claude/factory3d-build`,
раскатано таймером) → VERIFIED (проверено на сервере). Приоритет: P1 критичный, P2 средний, P3 низкий.

| ID | Модуль | P | Суть | Статус |
|---|---|---|---|---|
| V-1 | viewer | P1 | `quality.check.lot_id` → в Odoo 19 `lot_ids`: падают провайдеры quality/logistics/stock | DONE 7415e55 |
| S-1 | iot_sim | P1 | post_init_hook (реестр, каталог) не вызывается при `-u` с прототипа: нужен post-migrate 19.0.2.0.0 | OPEN |
| T-1 | telemetry | P1 | миграция прототипа застряла в `partial`: verify FL-5/battery warn≠норма (порог есть в каталоге, нет на уровне 0); повтор → ~350 расхождений; не привязаны 28 заявок, уровень 0 не выключен | OPEN |
| M-1 | machine_connect | P2 | API-01 принимает Bearer любого активного коллектора (AC-67: 401), cutmap.py:31-33 | OPEN |
| T-2 | telemetry | P2 | `_rate_check` пишет строку коллектора на каждый push (DEC-19 не до конца), f3d_collector.py:230-241 | OPEN |
| T-3 | telemetry | P2 | троттлинг `_touch` сбрасывается при смене IP; за Cloudflare IP меняется каждый запрос | OPEN |
| T-4 | telemetry | P2 | действие «Телеметрія» показывает сигналы вместо тревог (фильтры в одной OR-группе), f3d_signal_views.xml:183-187 | OPEN |
| M-2 | machine_connect | P2 | смены OEE считают незакрытые записи журнала часа прошлых дней работой до конца смены, f3d_oee_shift.py:190,254,266 | OPEN |
| B-1 | base | P2 | f3d.zone.f3d_code > 32 символов молча обрезается, нужна ValidationError (AC-01) | OPEN |
| B-2 | base | P2 | Enterprise: оборудование с f3d_code РЦ без workcenter_id не связывается (hooks/zones.py:75-86) | OPEN |
| S-2 | iot_sim | P2 | params у 8/276 устройств, у 31 ADAM нет раскладки каналов (SPEC §5.2) | OPEN |
| S-3 | iot_sim | P2 | данные каталога: T1/T2 unit 1/2 вместо 96; сигналы PV-INV на родителе; FL-6 не пассивный | OPEN |
| B-3 | base | P3 | f3d_resolve возвращает архивную зону (противоречие SPEC AC-05/AC-06) | OPEN |
| B-4 | base | P3 | повторная миграция затирает migration_state done→skipped и отчёт (AC-30) | OPEN |
| S-4 | iot_sim | P3 | «Перевірити зв'язок» при пустом url → offline навсегда вместо unconfigured | OPEN |
| S-5 | iot_sim | P3 | params_schema сценариев: device без enum, мастер принимает несуществующее устройство | OPEN |
| T-5 | telemetry | P3 | last_error стирается при неизвестном state; value+text принимаются вместе; 405 отдаёт HTML; нет icon.png | OPEN |
| A-1 | access | P2 | роль Охрана: в CSV RW на f3d.access.door, по SPEC §13.3 только alarm*; ограничение только в write() (f3d_access_door.py:79); проверить под ролью | OPEN |
| A-2 | access | P3 | два меню «Сервери BioStar» (id 520, 521) | OPEN |
| A-3 | access | P3 | сервер BioStar-эмулятора: read_enabled, state=error, опрос каждую минуту (сервис эмулятора не запущен); migration_state=partial | OPEN |
| E-1 | energy | P2 | у 67 счётчиков нет показаний kwh_total, интервалы и распределение = 0; вероятно нет живых данных (сервис эмулятора не запущен) и/или T-1 | OPEN |
| E-2 | energy | P3 | сигнал SAW-1/p_now отстаёт от последнего показания (20:36 против 21:00) | OPEN |
| E-3 | energy | P2 | моста factory3d_energy_mrp_workorder нет (FR-08, AC-37–41): на Enterprise не реализовано (ENV) | OPEN |
| Y-1 | yard | P3 | док: путь LPR из AC-82 /f3d/lpr → 404, реальный /f3d/telemetry/event с route=lpr; поправить SPEC/ТК-02 | OPEN |
| Y-2 | yard | P2 | фильтр «сегодня» КПП сравнивает день по Киеву с context_today браузера: 00:00–03:00 Киева (21–24 UTC) карточки не видны; падает test_dispatch_tour | OPEN |
| F-1 | fire_safety | P3 | при тревоге FA-CUT не создана активность на FACP-1 (AC-17): возможно, пустая группа оповещения — проверить | OPEN |

Операции на сервере после исправлений: повторить миграцию telemetry (T-1), остановить зависший f3d.sim.run id 1 (running).

Не дефект (решение менеджера): крон access «ротація і закриття відміток» закроет 35 открытых hr.attendance от 12.10 — поведение по SPEC (stale_close), на тестовой базе допустимо.
