# W2 «Енергетика · Керування»: спецификация (новый модуль `td_energy_control`, слой «Енергетика в 3D», плагин сборщика, эмулятор)

Версия 0.1 · 18.10.2026 · стандарт `docs/DOC_STANDARD.md` · техническое решение: `build/energy/W2_ARCH.md` (далее ARCH: FR-46…FR-70, A-38…A-63, Q-26…Q-33, C-38…C-47, план сборки §6).
Вход: `build/energy/GAP.md` (решения E-01…E-11, §2 путь управления, §6 модели, §7 волны; матрица CT-01…CT-15), макет `Control.dc.html` (экран «Керування») и `Main.dc.html` (действия рекомендации «Зарядити BESS 50 кВт», «Увімкнути QS…», диалог подтверждения QS, «Скасувати», кнопка «Відкрити в 3D»).
Опирается на: `build/energy/W1_SPEC.md` и `W1_ARCH.md` (C-30…C-37; слот рекомендации M-26/R-32; группы §4.2; R-26 состояния узлов; R-33 шина; провайдер 3D `td.viewer.provider.energy`); `docs/ARCHITECTURE.md` §5, §6.4, §6.5, §6.7; `docs/modules/td_telemetry` (`td.command`, API-01…API-07, «четыре предохранителя» AC-88); `docs/modules/td_viewer3d` (M-01 контракт провайдера, R-25 точка расширения, A.12 `energy`); `docs/modules/td_genset_factory3d` (ADP-11).
После слияния раскладывается в `docs/modules/td_energy_control/{SPEC,ARCHITECTURE}.md` (новый модуль), `docs/modules/td_energy_viewer3d/…` (мост 3D), разделы R-26/VX в `docs/modules/td_viewer3d/SPEC.md` и ADP-12 в `docs/modules/td_genset_factory3d/SPEC.md`. До слияния те документы не меняются.

**Язык документа.** Проза, заголовки и таблицы — на русском (по заданию волны); строки интерфейса, тексты макета, сообщения об ошибках в коде и подписи в журнале (всё в «ёлочках» и в `"…"` внутри кода) — на украинском, как в продукте (`docs/DOC_STANDARD.md`: «Рядки UI — українською в коді»). Технические имена — английские.

**Безопасность (рамка всего документа).** Модуль управляет только электроснабжением и энергопотреблением завода (QS, BESS, КГУ, PFC, сброс нагрузок, уставка давления воздуха, сцены освещения/вентиляции через BMS, пробный пуск ДГУ). **Он не управляет пожарной сигнализацией, спринклерами, дымоудалением, эвакуационным и аварийным освещением, защитой людей, СКУД, защитой станков и жизнеобеспечивающими блокировками** (R-60, AC-165, ТБ-12). Все эти системы — только входы (чтение) для блокировок. Автоматика работает в сборщике/контроллере, Odoo задаёт режимы, уставки, расписание и приоритеты (E-03, E-05).

## Условные обозначения, диапазоны ID, отклонения от макета

**Имена (E-09, A-23 W1).** Модули `td_energy_control` (новый), `td_energy_viewer3d` (мост 3D, новый), `td_energy`, `td_telemetry`, `td_bms`, `td_viewer3d`, `td_genset_factory3d`, `td_iot_sim`; модели `td.*`; поля стандартных моделей `td_*`; группы и меню — как в W1. Параметры `ir.config_parameter` модуля — `td.energy_control.<param>` (конвенция `docs/ARCHITECTURE.md` §5: `td.<module>.<param>`; отличие от строки 13 таблицы GAP §6 `td.energy.control_enabled` — решение A-38). Маршруты `/f3d/*` и коды существующих сигналов **не меняются**; новые HTTP-маршруты коллектора — `/td/energy/automation/*` (GAP §2.3). Python-пакет плагина сборщика — `td_collector_energy` (pip `td-collector-energy`, entry points в группе `factory3d_collector.plugins`; группа и пакет `f3d_collector` остаются по RENAME §2.4).

**Диапазоны ID** (нумерация блока «Энергетика» продолжается после W1; вне таблиц ID всегда с модулем: `td_energy_control M-33`, `td_viewer3d R-26`):

| Тип | W1 закончил на | W2 берёт | Где действует |
|---|---|---|---|
| FR | FR-45 (`td_energy`) | FR-46…FR-68 | `td_energy_control`, `td_energy_viewer3d`, коллектор, эмулятор |
| M | M-28 | M-29…M-42 | M-29…M-40 `td_energy_control`; M-41, M-42 `td_energy_viewer3d` |
| V | V-34 | V-35…V-47 | `td_energy_control` (V-35…V-45), `td_energy_viewer3d` (V-46, V-47) |
| UI | UI-11 | UI-12…UI-28 | клиентские компоненты |
| API | API-15 | API-16…API-28 | ORM-RPC (16…23, 27, 28), HTTP (24, 25), интент коллектора (26) |
| R | R-38 | R-39…R-67 | алгоритмы и правила (R-39…R-66 — `td_energy_control`, слой 3D, сборщик, эмулятор; R-67 — мост ДГУ) |
| AC | AC-158 | AC-159…AC-310 | `td_energy_control`, плагин, ядро сборщика, эмулятор, мост 3D, стенд (разд. 12; ADP-12 — AC-275…AC-277, `td_viewer3d` R-26 — AC-278…AC-281) |
| ТК / ТБ / ТП | ТК-18 / ТБ-10 / ТП-09 | ТК-19…ТК-28 / ТБ-11…ТБ-15 / ТП-10…ТП-12 | стенд, безопасность, производительность (разд. 13) |
| A (решения автора) | A-37 | A-38…A-62 (+A-63 мост ДГУ) | разд. 15 |
| Q | Q-25 | Q-26…Q-33 | ARCH §5, разд. 15 |
| D (отклонения от макета) | D-18 | D-19…D-46 | ниже |
| C (контракты) | C-37 | C-38…C-47 | ARCH §2.1 |
| `td_genset_factory3d` | FR-21, M-11, ADP-11, R-16, AC-83, A-23 | FR-69, ADP-12, R-67, AC-275…AC-277, A-63 | мост ДГУ (разд. 8.3, R-67) |
| `td_viewer3d` | FR-44, R-25, AC-67, X-92 | FR-70, R-26 (VX-01…VX-05), AC-278…AC-281, X-93 | разд. 8.4 |

Уточнение нумерации: AC для `td_genset_factory3d` (ADP-12) и `td_viewer3d` (R-26) взяты из сквозного диапазона W2 (AC-275…AC-281), чтобы не пересекаться с AC-74…AC-83 моста и AC-01…AC-67 просмотрщика. Итого **AC-159…AC-308 = 150 критериев**; FR-69 (мост ДГУ) и FR-70 (расширение просмотрщика) — дополнительные требования (ARCH §1.3).

Обозначения: UT — юнит-тест `odoo.tests` (`TransactionCase`/`HttpCase`); UT-JS — hoot-тест (`web.assets_unit_tests`); UT-PY — pytest коллектора/плагина/эмулятора (без Odoo); TC — стенд (эмулятор + сборщик + Odoo); MAN — ручная проверка (скриншот, браузер). `req`=`required=True`, `idx`=`index=True`. Все `Datetime` — UTC naive; «Київ» — `Europe/Kyiv` (`tools/dates.py` `td_energy`). Строки UI — на украинском в коде. Классы команд A/B — разд. 9 R-39.

### Отклонения от макета (D-xx)

| ID | Где в макете | Что в реализации | Почему |
|---|---|---|---|
| D-19 | Control: журнал, исполнитель «ви» | Имя пользователя; для не-людей — «автоматика», «сценарій «Пік»», «розклад», «скасування»; чип результата: «виконано», «створено», «збережено, очікує збирач», «не виконано», «заблоковано», «скасовано» | Несколько пользователей; бизнес-журнал с источниками `origin` (R-56) |
| D-20 | Control: переключатель сценария меняется одним кликом, тост «записано в журнал» | Включение/выключение — класс B: диалог (prepare/confirm), затем состояние «Очікує застосування» до подтверждения сборщиком (`applied_version`); переключатель показывает состояние Odoo, чип — состояние движка | E-06; Odoo не выполняет автоматику — истину о состоянии даёт сборщик |
| D-21 | Control: все плитки команд доступны всем | Права E-06: класс A — «Енергетик»; класс B — «Головний енергетик» или второе подтверждение другим «Енергетиком»; недоступные действия — `disabled` с пояснением «потрібне друге підтвердження» | E-06 |
| D-22 | Control: диалог — все проверки «гаразд» | Проверки вычисляются: `гаразд` / `не виконано` / `немає даних`; жёсткая проверка «не виконано» или «немає даних» (fail-closed) блокирует «Виконати» с причиной; мягкие — предупреждения | R-41; hard-блокировка только в сборщике, Odoo — подсказка |
| D-23 | Control: «Розклад на сьогодні» — только просмотр; вертикаль «зараз» на 59,7 % | Просмотр в OWL; план (`source='plan'`) строится из прогноза W1 R-28; ручные слоты (`manual`) — стандартные list/form для «Головного енергетика»; «зараз» — текущее время Киева | Макет без редактирования; E-06 (изменение расписания — класс B) |
| D-24 | Control: кнопки ↑/↓ сразу меняют порядок | Режим «Змінити порядок»: ↑/↓ локально, «Зберегти порядок» — одно действие `shed_reorder` (класс B), «Скасувати» — откат | Одно действие журнала вместо N; класс B |
| D-25 | Control: приоритеты — пять нагрузок с фиксированными кВт | Строки `td.energy.shed.item`; узлы: `CHARGING`, `RV-ALL`, `DRY-1`, `COMPRESSOR` («Компресор 2 (резервний)» → единственный узел «Компресорна 2 × GA 37»), `LP-1` («Освітлення складів»); `kw_reducible` — настраиваемый справочник (сид 48/60/17/37/12 = 174), рядом фактический `p_now` | В данных нет отдельного узла «Компресор 2» и «Освітлення складів»; установленные мощности W0 (`CHARGING` 13,5 кВт, `LP-1` 6,3 кВт) не совпадают с макетом, поэтому `kw_reducible` — оценка, а не ограничение |
| D-26 | Control: «Не відключаються ніколи» — статический текст | Динамический список: узлы `is_critical`, которых нет среди активных приоритетов, + постоянный перечень (аспирация во время работы станков, ИТ и связь, охрана, пожарная автоматика, аварийное освещение — R-60). Критичные узлы, присутствующие в приоритетах (компрессорная, склады), сбрасываются только частично или по условию и только в «Зрізанні піку», не при резервном питании (R-49, R-51) | Данные W0 помечают компрессорную и щиты освещения `is_critical` (питаются от ДГУ), а макет сбрасывает «Компресор 2» и «Освітлення складів» |
| D-27 | Control: чипы статуса сценариев | Текст чипа складывается в Odoo по шаблону (R-43) из фактов движка; примеры макета воспроизводятся: «Чергування · запас 402 кВт», «Активний · заряд BESS 26 кВт», «Збій: PFC-2 ступінь 3» (из W1 `fault_step`), «Наступний запуск о 23:00», «Готовий · паливо 78 %» (из `_td_genset_summary`), «Вимкнено» | Язык и факты — в Odoo; движок отдаёт только числа |
| D-28 | Control: чип «Контролер ГРЩ і збирач на зв'язку · 14:20» | Три состояния: «на зв'язку · HH:MM», «не на зв'язку · {вік}» (heartbeat старше `td.energy_control.heartbeat_stale_s`), «автоматику призупинено» (`automation_enabled=false` или движок в `hold`) | CT-01 |
| D-29 | Main: «Зарядити BESS 50 кВт» сразу выполняет команду | Та же последовательность prepare → диалог → confirm; для класса A диалог краткий (Enter подтверждает) | Control: «кожна ручна команда проходить блокування й підтвердження» |
| D-30 | Main: баннер «Виконано … Скасувати» | Отмена — отдельное действие `undo` (`origin='undo'`), доступна `td.energy_control.undo_window_min` (15 мин); баннер строится из последнего выполненного действия рекомендации (R-55 п.4) | Журнал и права для отмены |
| D-31 | Main: тост «Команду надіслано: BESS заряджається…» | Тост по состояниям: «Надіслано» → «Виконується» → «Виконано»/«Не виконано: {причина}» (до `verify_timeout_s`) | Реальное подтверждение устройством |
| D-32 | Control: «Тест ДГУ без навантаження · 10 хв» | Выполняется `td_genset` (`_test_start('idle')`, ADP-12); длительность — `td.genset.config.test_minutes` (на стенде 10); в журнале «Энергетики» — «прийнято td_genset» + ссылка; подтверждение пуска — собственная стейт-машина `td_genset` | E-01: `td_genset` — отдельный продукт |
| D-33 | Control: «КГУ … вийде на 400 кВт за 6 хв» | Число — параметр `chp_ramp_min` (6); эмулятор по умолчанию выходит за 60 с (флаг мира `chp_start_s=360` даёт 6 мин) | Модель W0 эмулятора |
| D-34 | Control: проверки КГУ «Тиск газу 2,1 бар», «Охолодження й вентиляція готові», «Дозвіл оператора КГУ» | Сигналы `energy_control/chp/gas_bar`, `…/permit` (регистры контроллера) и `infra/chp/state` (готовность: `stop`, не `cooling`); отдельного сигнала «вентиляция КГУ» нет — проверка входит в `chp_ready` | В данных нет отдельных сигналов |
| D-35 | Control: «Освітленість проходів ≥ 75 лк», «CO₂ 620 ppm < 1000» | Мягкие проверки `aisle_lux_ge`, `co2_lt`: нет сигнала → «немає даних» без блокировки | Сигналы BMS есть не на каждом объекте |
| D-36 | Control: «Мінімальний тиск споживачів 6,2 бар» | Регистр `energy_control/air/min_consumer_bar` (эмулятор 6,2; на объекте — параметр контроллера) | Единый источник правды для hard-проверки в сборщике |
| D-37 | Main: тост «Відкривається «Переглядач» із шаром «Енергетика»» | Реальный переход в `f3d_viewer.action`: режим раскраски «Електромережа: стан вузлів», маркеры тревог, слои GLB `energy`, `backup`; узел подсвечивается и выбирается (FR-62…FR-64) | Требование W2 |
| D-38 | Main: в панели узла QS/BESS кнопки «Увімкнути QS…», «Зарядити 50 кВт» | Кнопки регистрирует `td_energy_control` через `registry.category("td_energy.node_actions")`; для замкнутого QS — «Вимкнути QS…», для заряда BESS — «Зупинити заряд» | C-46; симметричные действия |
| D-39 | Control: BESS 100 кВт / 200 кВт·год | Параметр сценария `bess_max_kw` (сид 100) ограничивает автоматику; эмулятор технически способен на 200 кВт (`BESS_KW_MAX`); ручная команда `bess_discharge` — до `bess_max_kw` | Макет и модель W0 расходятся |
| D-40 | Control: «Нічний режим · вентиляція RoofVent на 30 %» | Действие — режим BMS «Знижена вентиляція» (`VEL`) и уставка ночи `sp_night` для каждой установки `kind='roofvent'`; «30 %» — справочный текст чипа из параметра `vent_pct`; отдельного сигнала «ограничение вентилятора, %» в `td_bms` нет | То, что умеет `td_bms` |
| D-41 | Control: «ціна газу 19,80 ₴/м³» | Параметр сценария `gas_price_uah_m3` (19,80); цена сети — зона тарифа `td.energy.tariff` (W1); `td.energy.price` (W3) подменит параметр без изменения движка | Q-31 |
| D-42 | Control: строка журнала «Заявка ТО · PFC-2 … · автоматика · створено» | Журнал объединяет `td.energy.action` и события `td.energy.event` (`kind in ('pfc','control')`) со ссылкой на заявку ТО; результат «створено» — если есть `maintenance_request_id` | R-56 п.2 |
| D-43 | Control: ничего о втором подтверждении | Баннер «Очікує другого підтвердження: {дія} — {хто готував}» и кнопка «Підтвердити (2/2)» для другого «Енергетика»; уведомление через `mail.activity`/шину | E-06 |
| D-44 | Control: меню «Налаштування» вверху | В W2 — подраздел «Керування» в меню «Енергетика» (seq 8) и «Журнал команд» (seq 9, стандартный list); настройки — блок в `res.config.settings` | Меню W1 §3.3 |
| D-45 | Решение менеджера (отменяет R-66/AC-232/A-51 в исходной редакции) | **Архивных таблиц нет.** Деинсталляция `td_energy_control` удаляет его данные как у любого модуля Odoo: `td.energy.action` (журнал), сценарии, приоритеты, слоты, блокировки, виды команд, сигналы/источники `energy_control`, кроны, параметры. `_restore_archive` и таблицы `td_energy_*_archive` не создаются; `uninstall_hook` только сбрасывает флаги и публикует сборщику пустую конфигурацию | Проще и предсказуемее; журнал команд — бизнес-журнал модуля, а не данные других модулей (аудит — резервная копия БД) |
| D-46 | Решение менеджера (Q-27) | Параметр `td.energy_control.remote_switching_enabled` (**default `False`**): «Дистанційне перемикання комутаційних апаратів дозволено». Пока он `False`, команды дистанционного перемикання — `qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test` (поле `remote_gated=True` вида команды, M-31) — **отказываются** с `UserError("Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled. Зверніться до адміністратора.")` в `prepare`, `confirm` и `confirm_second`; плитка `enabled=false` с той же причиной; флаг публикуется сборщику в API-24 `flags.remote_switching_enabled`, плагин дополнительно отказывает (`rejected`). Остальные команды (заряд/остановка BESS, `chp_stop`, сцены BMS, уставка воздуха, конфигурация) не затрагиваются. Demo-данные (`demo/ir_config_parameter_demo.xml`) и `hooks._td_enable_stand` ставят `True`; `neutralize.sql` возвращает `False` | Регламент объекта (Q-27) не подтверждён: дистанционное переключение отдельно от `write_enabled` |

---

# ЧАСТЬ I. `td_energy_control` (новый модуль)

## 0. Дерево файлов

Владельцы: **A** — бэкенд `td_energy_control` + адаптер ДГУ, **B** — фронтенд `td_energy_control` + правки клиента `td_energy`, **C** — движок сборщика, ядро сборщика (расширение контекста плагина), эмулятор, **D** — мост 3D `td_energy_viewer3d` + расширение `td_viewer3d` (ARCH §6). Файлы без буквы — менеджер (каркас, разд. 6.0 ARCH).

```
odoo_addons/td_energy_control/
├── __manifest__.py                       (менеджер) разд. 1
├── __init__.py                           (менеджер) from . import models, controllers; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                              A  post_init_hook: _load_sources_signals, _seed_defaults, _bump_config; uninstall_hook (архивных таблиц нет, D-45)
├── models/
│   ├── __init__.py                       A
│   ├── td_source_signal.py               A  M-38 (selection_add `energy_ctl`, `energy_control`; регистрация валидаторов; вид события `control`)
│   ├── td_energy_scenario.py             A  M-29
│   ├── td_energy_shed_item.py            A  M-30
│   ├── td_energy_command_kind.py         A  M-31
│   ├── td_energy_interlock.py            A  M-32
│   ├── td_energy_action.py               A  M-33 (журнал + поток prepare/confirm/undo)
│   ├── td_energy_schedule_slot.py        A  M-34
│   ├── td_energy_control.py              A  M-35 (AbstractModel, API экрана)
│   ├── td_energy_advice.py               A  M-36 (правила R-55)
│   ├── td_command.py                     A  M-37
│   ├── td_energy_control_state.py        A  M-39
│   └── res_config_settings.py            A  M-40
├── controllers/{__init__.py, automation.py}   A  API-24, API-25
├── tools/
│   ├── __init__.py                       A
│   ├── interlocks.py                     A  R-41 (чистые проверки)
│   ├── kinds.py                          A  R-42 (параметры, схемы, текст диалога)
│   ├── config_builder.py                 A  R-43 (JSON конфига, канонический вид, ETag)
│   ├── status_text.py                    A  R-43 п.5 (чипы сценариев)
│   ├── planner.py                        A  R-54 (план дня)
│   ├── journal.py                        A  R-56
│   ├── bus.py                            A  шина `td_energy_control` (A-41)
│   └── genset_link.py                    A  мягкий вызов ADP-12 (разд. 8.3)
├── data/
│   ├── ir_config_parameter.xml           A  разд. 5.1
│   ├── ir_cron.xml                       A  разд. 6
│   ├── td_energy_scenario_data.xml       A  6 сценариев (разд. 5.2)
│   ├── td_energy_command_kind_data.xml   A  виды команд (разд. 5.3)
│   ├── td_energy_interlock_data.xml      A  реестр блокировок (разд. 5.4)
│   ├── td_energy_shed_item_data.xml      A  5 приоритетов (разд. 5.5)
│   ├── energy_control_sources.csv        A  2 источника (разд. 5.6)
│   ├── energy_control_signals.csv        A  сигналы управления (разд. 5.6)
│   └── neutralize.sql                    A
├── security/{ir.model.access.csv, td_energy_control_security.xml}   A  разд. 4 (новых групп нет)
├── static/src/control/{control.js, control.xml, scenarios.js, scenarios.xml, shed.js, shed.xml, commands.js, commands.xml,
│                        confirm_dialog.js, confirm_dialog.xml, params_dialog.js, params_dialog.xml, bus.js, schedule.js, schedule.xml, journal.js, journal.xml, control.scss}   B  UI-12…UI-20
├── static/src/handlers/{advice_handler.js, node_actions.js, done_banner.js}   B  UI-21, UI-22
├── static/tests/{control.test.js, confirm_dialog.test.js, advice_handler.test.js, node_actions.test.js, fixtures/contracts.js}   B  hoot
├── views/
│   ├── td_energy_control_views.xml       B  V-35 (client action), V-36 (состояние управления)
│   ├── td_energy_scenario_views.xml      B  V-37
│   ├── td_energy_shed_item_views.xml     B  V-38
│   ├── td_energy_command_kind_views.xml  B  V-39
│   ├── td_energy_interlock_views.xml     B  V-40
│   ├── td_energy_action_views.xml        B  V-41
│   ├── td_energy_schedule_slot_views.xml B  V-42
│   ├── td_command_views.xml              B  V-43 (поле «Дія енергетики» в форме команды)
│   ├── res_config_settings_views.xml     B  V-44
│   └── menus.xml                         B  V-45
└── tests/
    ├── test_scenario.py, test_shed.py, test_kinds.py, test_interlocks.py, test_action_flow.py, test_action_second.py,
    │   test_undo.py, test_journal.py, test_schedule.py, test_advice_rules.py, test_config_api.py, test_state_api.py,
    │   test_intent_payload.py, test_security.py, test_source_signal.py, test_hooks.py, test_neutralize.py,
    │   test_crons.py, test_genset_exec.py, common.py     A
    ├── test_ui.py, test_hoot.py          B  (HttpCase: клиентское действие и меню; hoot-набор по образцу `td_energy/tests/test_w1_hoot.py`)
    └── stand/test_tk_control.py          A  ТК-19…ТК-28 (pytest против стенда)

odoo_addons/td_energy_viewer3d/            D  мост 3D (разд. 8.4), auto_install
├── __manifest__.py, __init__.py          (менеджер)
├── models/{__init__.py, viewer_provider.py, td_energy_node.py, res_config_settings.py}   D  M-41, M-42
├── tools/{__init__.py, layer.py}                    D  R-57
├── static/src/layer/{energy_layer.js, markers.js, colors.js, links.js, energy_layer.scss}   D  UI-23…UI-27
├── static/tests/hoot/*.test.js                      D
├── views/{td_energy_viewer3d_views.xml}             D  V-46 (настройки слоя), V-47 (серверное действие и меню)
└── tests/{test_layer_payload.py, test_delta.py, test_kiosk.py, test_deeplink.py, test_hoot.py}   D

odoo_addons/td_viewer3d/                   D  только указанные файлы (разд. 8.4: VX-01…VX-05)
├── static/src/viewer/core.js                        D  минимальные аддитивные вставки (≤ 90 строк)
├── static/src/action/viewer_action.js               D  `opts.onOpenAction`
├── static/tests/hoot/extension_energy.test.js       D  AC-278…AC-281
└── tests/test_r26_extension.py                      D

odoo_addons/td_genset_factory3d/adapters/td_genset.py     A  +ADP-12 (разд. 8.3), tests/test_adp12.py   A

odoo_addons/td_energy/static/src/            B  минимальные правки клиента W1 (разд. 3.4)
├── common/actions.js                                B  deep-link в 3D (C-45), реестры
├── pult/{sld.js, sld.xml, pult.xml, pult.js}        B  реестр действий панели узла (C-46), баннер «Виконано»
└── tests/…                                          B  новые hoot-тесты td_energy: `static/tests/control_hooks.test.js`

services/collector_plugins/td_collector_energy/       C  разд. 8.1
services/collector/collector/{plugins/base.py, core/app.py, core/scheduler.py, core/commands.py, core/errors.py, core/odoo_client.py, core/live.py}   C  разд. 8.1.2 (C-40)
services/collector/{requirements-extra.txt}           C
services/iot_sim/iot_sim/{models/{swb,bess,chp,compressor,meter,pv}.py, protocols/modbus_maps/{__init__,swbctl}.py}   C  разд. 8.2
services/iot_sim/{catalog/signals.csv, tests/unit/{test_swbctl.py, test_control_models.py}}                           C
odoo_addons/td_iot_sim/data/{td_sim_signal.csv, td_sim_scenario.xml}                C
```

## 1. Манифест `td_energy_control` (дельта от шаблона)

- `name` «Енергетика — Керування»; `summary` «Сценарії автоматики, пріоритети скидання, ручні команди з блокуваннями й підтвердженням, розклад і журнал»; `version` `19.0.1.0.0`; `author` `ToDo`; `license` `LGPL-3`; `category` `Manufacturing/Manufacturing`; `application` `False`; `installable` `True`; `auto_install` `False`.
- `depends`: `td_energy` (≥ 19.0.1.1.0, W1), `td_telemetry` (`td.command`, коллектор), `td_bms` (цели ночного режима и сцен; `depends` td_telemetry, web — лёгкий). Необязательные (мягкая зависимость через `self.env.get(...)`/`importlib`): `td_genset_factory3d` (тест ДГУ, ADP-12), `td_viewer3d` (не нужен: 3D — отдельный мост).
- `data` (порядок): `security/td_energy_control_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/td_energy_interlock_data.xml`, `data/td_energy_command_kind_data.xml`, `data/td_energy_scenario_data.xml`, `data/td_energy_shed_item_data.xml`, `data/ir_cron.xml`, `views/td_energy_scenario_views.xml`, `views/td_energy_shed_item_views.xml`, `views/td_energy_command_kind_views.xml`, `views/td_energy_interlock_views.xml`, `views/td_energy_action_views.xml`, `views/td_energy_schedule_slot_views.xml`, `views/td_command_views.xml`, `views/res_config_settings_views.xml`, `views/td_energy_control_views.xml` (клиентское действие), `views/menus.xml` (последним).
- `assets`: `web.assets_backend`: `td_energy_control/static/src/control/**`, `td_energy_control/static/src/handlers/**`; `web.assets_unit_tests`: `td_energy_control/static/tests/**/*.js`.
- `post_init_hook`: `hooks.post_init_hook` (идемпотентный): `_load_sources_signals(env)` (разд. 5.6), `_seed_defaults(env)` (разд. 5.2…5.5 — только если записей нет), `_bump_config(env)` (`config_version`+1). `uninstall_hook`: **архивных таблиц нет** (D-45) — модуль удаляется вместе со своими данными, как любой модуль Odoo; хук удаляет сигналы и источники `module='energy_control'` и `type='energy_ctl'` (в т. ч. зависимые записи `td.command` `origin='energy'`), крон-задачи, параметры `td.energy_control.*`, сбрасывает `write_enabled`/`automation_enabled`/`remote_switching_enabled` в `False` и публикует сборщику пустую конфигурацию (A-51).
- Внешних Python-зависимостей у Odoo-части нет. Сборщик: `td-collector-energy` (разд. 8.1).

## 2. Модели

Все идентификаторы моделей — `td.energy.*` (пространство W1 `td.energy.*` остаётся за `td_energy`; новые названия не пересекаются с W1: `scenario`, `shed.item`, `command.kind`, `interlock`, `action`, `schedule.slot`, `control`, `control.state`). Чтение моделей — `group_td_energy_user`; все изменения бизнес-данных — только через методы моделей под `sudo()` после проверки прав (разд. 4), прямой `write/create/unlink` с клиента запрещён ACL (user/manager имеют только `read`), кроме случаев, указанных в таблицах.

### M-29 `td.energy.scenario` — сценарий автоматики (FR-46, FR-47, R-43, R-45…R-50)

`_name = "td.energy.scenario"`, `_description = "Енергетика: сценарій автоматики"`, `_order = "sequence, id"`. Ровно 6 записей, создаются данными (разд. 5.2); `create`/`unlink` для не-администратора запрещены (`AccessError`).

| Поле | Тип | Параметры |
|---|---|---|
| `code` | Selection | `peak`/«Зрізання піку», `self`/«Самоспоживання СЕС», `pfc`/«Компенсація реактивної потужності», `night`/«Нічний режим (BMS)», `backup`/«Резервне живлення», `chp`/«КГУ за графіком і ціною»; req, idx, readonly; `UNIQUE(code)` |
| `name` | Char | size=64, req (название карточки = метка значения `code`) |
| `description` | Text | req; тексты карточек макета (разд. 5.2) |
| `sequence` | Integer | default 10 (порядок карточек: peak 10, self 20, pfc 30, night 40, backup 50, chp 60) |
| `enabled` | Boolean | default по сиду (peak ✓, self ✗, pfc ✓, night ✓, backup ✓, chp ✗ — состояние макета); меняется только действием `scenario_toggle` (контекст `td_energy_control_internal`) |
| `params` | Json | default `PARAM_DEFAULTS[code]`; валидация `@api.constrains("params")` по таблице ниже → `ValidationError("Сценарій {name}: параметр {key} — {помилка}.")`; неизвестные ключи отклоняются |
| `params_text` | Text | compute/inverse (JSON, как `td.command.payload_text`), только для формы администратора |
| `config_version` | Integer | readonly: значение `td.energy.control.state.config_version` на момент последнего изменения `enabled`/`params` |
| `applied` | Boolean | compute (не хранится): `state.applied_version >= config_version` |
| `engine_state` | Selection | `unknown`/«Немає даних» (default), `off`/«Вимкнено», `armed`/«Чергування», `active`/«Активний», `warn`/«Збій»; readonly; пишет API-25 |
| `engine_facts` | Json | readonly: числа от движка (`margin_kw`, `bess_kw`, `export_kw`, `reason`, `next_run`, …) |
| `engine_ts` | Datetime | readonly: время последнего отчёта движка |
| `state_signal_id` | Many2one `td.signal` | readonly, `energy_control/auto/<code>/state` |
| `state_kind` | Selection | compute: `act`/`arm`/`warn`/`off` (цвет чипа макета; R-43 п.5) |
| `state_text` | Char | compute: текст чипа по шаблону (R-43 п.5) |
| `changed_by`, `changed_at` | Many2one `res.users` / Datetime | readonly |

**Параметры сценариев** (`params`; тип, границы «мин…макс», сид; **«граница кода»** — значение, которое сборщик не превышает независимо от конфига, R-44 п.6):

| Сценарий | Ключ | Тип, границы | Сид | Примечание |
|---|---|---|---|---|
| `peak` | `limit_kw` | float 100…2000 | 760 | уставка импорта (макет: «уставка 760 кВт · 95 %» = 95 % от `contract_kw` 800); процент в чипе = `limit_kw / contract_kw` |
| | `activate_margin_kw` | float 0…200 | 30 | движок активируется, когда прогноз 15 мин ≥ `limit_kw − activate_margin_kw` или мгновенный импорт ≥ `limit_kw` |
| | `margin_kw` | float 0…100 | 20 | мгновенная цель `limit_kw − margin_kw` |
| | `release_margin_kw` | float 0…200 | 40 | |
| | `release_hold_s` | int 30…1800 | 180 | |
| | `stage_delay_s` | int 10…600 | 60 | пауза между ступенями BESS → КГУ → сброс |
| | `bess_max_kw` | float 0…200 | 100 | граница кода 200 (D-39) |
| | `bess_min_soc_pct` | float 10…90 | 30 | эффективный пол = `max(это, td.energy.bess_reserve_pct)` |
| | `chp_allowed`, `shed_allowed` | bool | true, true | ступени 2 и 3 |
| `self` | `export_max_kw` | float 0…100 | 20 | «експорт ≤ 20 кВт» |
| | `export_deadband_kw` | float 0…50 | 5 | |
| | `bess_target_soc_pct` | float 50…100 | 95 | «BESS до 95 %» |
| | `bess_max_kw` | float 0…200 | 100 | |
| | `curtail_pv` | bool | true | «далі обмеження інверторів» |
| | `curtail_delay_s`, `restore_hold_s` | int 10…600 | 60, 120 | |
| `pfc` | — | — | — | уставка cos φ берётся из `td.energy.cos_phi_target` (E-10, одна группа настроек) и добавляется в `scenarios.pfc.params.cos_target` конфига API-24; сценарий лишь включает автоматический режим контроллера (R-47); чип показывает «ціль cos φ 0,95», «крок 35 квар» (из `pfc_step_kvar` узла) |
| `night` | `from`, `to` | строка `HH:MM` | `23:00`, `06:30` | локальное время Киева; окно может пересекать полночь |
| | `days` | list[int 1…7] | `[1..7]` | дни, с которых **начинается** окно |
| | `vent_mode`, `day_vent_mode` | строка из `td_bms.tools.hvac.MODE_LABELS` | `VEL`, `VE` | режимы BMS (D-40) |
| | `vent_pct` | int 10…100 | 30 | справочно для чипа «RoofVent 30 %» |
| | `light_scene_number`, `light_scene_day_number` | int 1…16 | 1, 2 | номера `td.bms.light.scene.number` (дежурный/рабочий) |
| | `heat_setpoint_c` | float 5…30 | 16.0 | запись в `sp_night_signal_id` установок |
| `backup` | `genset_capacity_kw` | float 50…5000 | 507 | `p_inst_kw` узла `GENSET` |
| | `critical_kw` | float 0…5000 | 180 | справочно: «критичні 180 кВт» |
| | `restore_delay_s` | int 30…1800 | 120 | стабильная сеть перед восстановлением |
| `chp` | `min_run_h` | float 0.5…24 | 2.0 | «мін. робота 2 год» |
| | `min_off_min` | int 0…240 | 30 | |
| | `gas_price_uah_m3` | float 0…200 | 19.80 | D-41 |
| | `gas_m3_per_kwh` | float 0.1…1.0 | 0.25 | 199 м³/ч ÷ 800 кВт (эмулятор R-12) |
| | `price_margin_uah_kwh` | float 0…50 | 0.5 | |
| | `use_slots` | bool | true | пуск в слотах `resource='chp'`, `executes=True` |
| | `ramp_min` | int 1…30 | 6 | справочно для диалога (D-33) |

Методы: `_td_apply_change(vals, action)` (internal, `sudo`, контекст `td_energy_control_internal`): записывает `enabled`/`params`, `changed_by/at`, `config_version = state.bump()`; `write()` без контекста и не от `base.group_system` → `AccessError("Зміна сценарію можлива лише дією керування (клас B).")`; `_td_engine_update(item)` (API-25): обновляет `engine_*` (игнорирует отчёт с `config_version_applied` меньшей текущей для `enabled`); `_td_state_text()` (R-43 п.5).

### M-30 `td.energy.shed.item` — приоритет сброса нагрузки (FR-48, R-51)

`_name = "td.energy.shed.item"`, `_description = "Енергетика: пріоритет скидання"`, `_order = "sequence, id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `sequence` | Integer | req, default 10; порядок = приоритет (меньше — сбрасывается первым) |
| `name` | Char | size=96, req («Зарядна станція навантажувачів») |
| `node_id` | Many2one `td.energy.node` | req, ondelete restrict, domain `[('kind','=','consumer')]` |
| `action` | Selection | `off`/«Вимкнути», `reduce`/«Знизити», `pause`/«Пауза», `defer`/«Відкласти»; req |
| `param_value` | Float | `reduce`: 1…99 (%), `pause`/`defer`: 1…120 (мин), `off`: 0 |
| `kw_reducible` | Float | ≥ 0, кВт, снимаемые (сид макета) |
| `condition` | Selection | `none`/«Без умов» (default), `air_pressure_min`/«Тиск повітря не нижче уставки», `no_active_cycle`/«Без втрати циклу» |
| `condition_value` | Float | для `air_pressure_min` — бар (6,5) |
| `how` | Char | compute: «відкласти заряд до 30 хв» / «знизити до 70 %» / «пауза до 20 хв, без втрати циклу» / «вимкнути, тиск ≥ 6,5 бар» / «знизити до 50 %» (шаблоны по `action`, `param_value`, `condition`) |
| `signal_id` | Many2one `td.signal` | domain `module='energy_control'`, `energy_control/shed/<node.code>/limit_pct`; req, если `active` |
| `active` | Boolean | default True |
| `p_now_kw` | Float | compute (не хранится): `node_id.p_now` (если сигнал свежий) |

Ограничения: (1) `UNIQUE(node_id) WHERE active` (частичный индекс в `init()`); (2) узел `is_critical` допускается только для частичного или условного сброса: `action='reduce'` или `condition != 'none'`; иначе `ValidationError("Вузол {code} критичний: скидання лише часткове або за умовою.")` (элемент получает `critical=True` в конфиге и пропускается при резервном питании, R-49); (3) узел с `workcenter_id` и `condition != 'no_active_cycle'` → `ValidationError("Вузол {code} пов'язаний із робочим центром: потрібна умова «Без втрати циклу».")`; (4) узел, код которого входит в `NEVER_SHED_CODES` (константа `tools/kinds.py`; сид пуст, расширяется кодом) — запрет; (5) `kw_reducible` — справочная оценка (сид макета: 48/60/17/37/12), может превышать `p_inst_kw` узла (данные W0: `CHARGING` 13,5 кВт, `LP-1` 6,3 кВт против макета) — в форме лишь предупреждение, не ошибка; реальный эффект виден по `p_now`. Изменение порядка — только действием `shed_reorder` (API-17, `params={"order":[id,…]}`, класс B). Состав и параметры строк (создание, удаление, `action`, `param_value`, `kw_reducible`, `condition`) редактирует только `group_td_energy_chief` в списке V-38; `create/write/unlink` для строк с полями-настройками автоматически создаёт запись `td.energy.action` (`origin='config'`, `kind_code='shed_edit'`, `cls='B'`, `state='done'`, `confirmed_by=uid`) и `state.bump()`; для не-chief — `AccessError`.

### M-31 `td.energy.command.kind` — вид команды (FR-49, FR-50, R-39, R-42)

`_name = "td.energy.command.kind"`, `_description = "Енергетика: вид команди"`, `_order = "sequence, id"`. Данные (разд. 5.3), редактирует только администратор (поля `cls`, `checks`, `executor`, `resource` — `readonly` в форме остальных ролей).

| Поле | Тип | Параметры |
|---|---|---|
| `code` | Char | size=32, req, idx, `UNIQUE`; `[a-z0-9_]+` |
| `name` | Char | size=96, req (заголовок плитки: «Заряд BESS 50 кВт» — шаблон с `{power_kw}`) |
| `sub_template` | Char | size=128 («до {until} або {soc_limit_pct} %») |
| `sequence` | Integer | |
| `tile` | Boolean | плитка на экране (8 из макета) |
| `cls` | Selection | `A`/`B`, req (R-39) |
| `executor` | Selection | `intent`/«Збирач (інтент)», `config`/«Конфігурація Odoo», `genset`/«ДГУ (td_genset)», req |
| `resource` | Selection | `bess`, `qs`, `chp`, `pfc`, `air`, `light`, `vent`, `genset`, `config`; req (ключ арбитража, R-44 п.4) |
| `params_schema` | Json | список `{"name","label","type":"float\|int\|time\|enum\|bool","min","max","default","unit","choices"}` (R-42 п.1) |
| `checks` | Json | упорядоченный список `{"code": "<interlock.code>", "soft": bool}`; `hard` определяет реестр M-32, `soft` может только ослабить |
| `confirm_title`, `confirm_text` | Char / Text | шаблоны диалога с `{param}` («Увімкнути секційний вимикач QS?» / «Секції 1 і 2 працюватимуть разом…») |
| `undo_kind_id` | Many2one self | обратный вид (R-56 п.4) |
| `valid_s` | Integer | TTL команды в очереди (`expires_at = now + valid_s`), default `td.energy_control.command_ttl_s` |
| `active` | Boolean | default True |
| `remote_gated` | Boolean | D-46: команда дистанционного перемикання (`qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`); при `td.energy_control.remote_switching_enabled=False` `prepare`/`confirm`/`confirm_second` → `UserError`, `available` не меняется, плитка `enabled=false` |
| `available` | Boolean | compute: R-42 п.2 (`genset` — мост установлен; `light`/`vent` — есть цели BMS; `intent` — источник `ENERGY-CTL` активен) |
| `unavailable_reason` | Char | compute |

Методы: `normalize(params)` → dict (приведение типов, границы, `ValidationError("Команда {name}: параметр {label} поза межами {min}…{max} {unit}.")`); `render(params)` → `{"title","sub","text"}`; `build_checks(params)` → список для M-33 (R-41).

### M-32 `td.energy.interlock` — реестр блокировок (FR-51, R-41)

`_name = "td.energy.interlock"`, `_description = "Енергетика: блокування"`, `_order = "sequence, id"`. Строка — **настройка именованной проверки**; код проверки — в реестре `tools/interlocks.CHECKS` (Odoo) и `td_collector_energy/interlocks.py` (сборщик) под тем же `code`; `safe_eval` и код из БД запрещены.

| Поле | Тип | Параметры |
|---|---|---|
| `code` | Char | size=32, req, idx, `UNIQUE`; должен быть ключом `CHECKS`, иначе `ValidationError("Невідома перевірка {code}.")` |
| `name` | Char | size=128, req: шаблон строки диалога, напр. «Заряд {soc} % < {limit} %» |
| `hard` | Boolean | `True` — блокирует выполнение **в сборщике**; в диалоге Odoo блокирует «Виконати» |
| `fail_closed` | Boolean | для `hard`: «немає даних» тоже блокирует (default True) |
| `where` | Selection | `both` (Odoo+сборщик, default), `odoo` (только подсказка; напр. топливо ДГУ), `collector` (только сборщик) |
| `inputs` | Json | список кодов сигналов, нужных проверке (для конфига сборщика и `data_fresh`) |
| `params` | Json | пороги (R-41); меняет только администратор (`td_factory3d.group_td_admin`), каждое изменение — `td.energy.action` `origin='config'`, `kind_code='interlock_param'` и `state.bump()` (R-41 п.7) |
| `sequence`, `active` | Integer, Boolean | |

### M-33 `td.energy.action` — действие оператора, автоматики и конфигурации; журнал (FR-50, FR-52, R-40, R-56)

`_name = "td.energy.action"`, `_description = "Енергетика: дія керування"`, `_order = "create_date desc, id desc"`, `_inherit = ["mail.thread"]` (чаттер: «Створено», «Підтверджено», «Результат»). Одно действие оператора = одна команда `td.command` (интент) или одно изменение конфигурации; N шагов устройства выполняет сборщик (R-52).

| Поле | Тип | Параметры |
|---|---|---|
| `name` | Char | readonly, `copy=False`, последовательность `ir.sequence` `ACT/%(y)s/#####` (`td_energy_control.seq_action`) |
| `kind_id` | Many2one `td.energy.command.kind` | idx, ondelete restrict; пусто для событий автоматики |
| `kind_code` | Char | size=48, idx, stored: код вида или `auto_<scenario>_<step>` (R-56 п.3) |
| `origin` | Selection | `manual`/«Вручну», `advice`/«Рекомендація», `schedule`/«Розклад», `auto`/«Автоматика», `undo`/«Скасування», `config`/«Конфігурація»; default `manual`, idx |
| `cls` | Selection | `A`/`B`; для `auto` — пусто |
| `state` | Selection | `prepared`/«Підготовлено», `awaiting_second`/«Очікує другого підтвердження», `queued`/«У черзі», `sent`/«Передано збирачу», `executing`/«Виконується», `done`/«Виконано», `failed`/«Не виконано», `blocked`/«Заблоковано», `expired`/«Прострочено», `cancelled`/«Скасовано»; default `prepared`, idx, tracking |
| `params` | Json | нормализованные параметры вида |
| `checks` | Json | результат Odoo-проверок последнего `prepare/confirm`: `[{"code","label","state":"ok\|fail\|unknown","hard","detail"}]` |
| `collector_checks` | Json | результат проверок сборщика (API-25 `actions[].checks`) |
| `token_hash` | Char | size=64, idx: `sha256(token)`; токен не хранится (R-40 п.2) |
| `token_expires_at` | Datetime | |
| `needs_second` | Boolean | выставляется в `prepare`: `cls='B'` и `prepared_by` без `group_td_energy_chief`; дальше не меняется |
| `prepared_by`, `confirmed_by`, `second_by` | Many2one `res.users` | readonly; `second_by ≠ prepared_by`, `≠ confirmed_by` (constraint) |
| `prepared_at`, `confirmed_at`, `second_at`, `second_expires_at`, `started_at`, `finished_at` | Datetime | readonly |
| `command_id` | Many2one `td.command` | ondelete set null |
| `scenario_id`, `node_id`, `advice_id` | Many2one | ondelete set null |
| `undo_of_id` | Many2one self | ondelete set null; `undone_by_id` Many2one self (readonly) |
| `undo_params` | Json | параметры обратного действия (прежняя уставка, прежний порядок, прежнее состояние сценария) — фиксируются на `confirm` |
| `undo_available` | Boolean | compute (не хранится): R-56 п.5 |
| `config_version` | Integer | для `executor='config'`: версия после публикации |
| `applied` | Boolean | compute: для `config` — `state.applied_version >= config_version`; для остальных — `state = 'done'` |
| `idem` | Char | size=40: `sha1("<id>:<kind_code>")`, частичный `UNIQUE WHERE idem IS NOT NULL` |
| `summary`, `detail`, `actor_text`, `result_text`, `error` | Char | size 128/256/96/96/256: строки журнала (D-19) |
| `ref_model`, `ref_id` | Char / Integer | внешний объект (`td.genset.command`, `maintenance.request`) для ссылки |

Индексы: `(state, create_date)`, `(kind_code, state)`, `(node_id, create_date)`.

Методы (полная семантика — R-40; публичные обёртки — M-35/API-17…API-21):
`_td_prepare(kind, params, origin='manual', advice=None, scenario=None)` → запись `prepared` + токен; `_td_confirm(token)`; `_td_confirm_second()`; `_td_cancel(token)`; `_td_enqueue()` (создаёт `td.command`, R-40 п.6); `_td_on_command(cmd)` (вызов из M-37 при смене состояния команды); `_td_on_engine(item)` (API-25: `actions[]`); `_td_undo()`; `_td_close(state, result_text, error=None)` (единственная точка завершения: `finished_at`, `bus.tick(env, 'action')` шины `td_energy_control`, `advice.action_done`, сообщение в чаттер); `_cron_expire()` (разд. 6); `_td_log_auto(ev)` (из `events[]` API-25 → запись `origin='auto'`).

Права на запись: `create/write/unlink` — только `sudo()` внутри методов; ACL для всех групп — `read`; `unlink` запрещён всем, кроме администратора (журнал не удаляется; ротация — не в W2, Q-33).

### M-34 `td.energy.schedule.slot` — слот расписания (FR-53, R-54)

`_name = "td.energy.schedule.slot"`, `_description = "Енергетика: слот розкладу"`, `_order = "resource, time_from, id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `resource` | Selection | `bess`/«BESS», `chp`/«КГУ», `vent`/«Вентиляція RoofVent», `light`/«Освітлення цеху», `charging`/«Зарядна станція», `genset`/«ДГУ»; req, idx |
| `date` | Date | пусто = повторяется по `weekdays` |
| `weekdays` | Char | size=7, default `1111111` (пн…вс), только когда `date` пуста |
| `time_from`, `time_to` | Float | 0…24 (часы Киева; `7.5` = 07:30); `time_to > time_from`, иначе `ValidationError("Слот не може перетинати північ: розділіть його.")` |
| `mode` | Selection | `charge`/«заряд», `discharge`/«розряд», `run`/«пуск», `night`/«ніч», `day`/«день», `duty`/«черговий», `work`/«робочий», `test`/«тест» |
| `label` | Char | size=48 (текст полосы: «розряд · пік», «заряд від СЕС», «ніч 30 %», «день 100 %», «черговий», «робочий», «заряд», «тест», «пуск за ціною») |
| `setpoint_kw` | Float | для BESS/КГУ |
| `source` | Selection | `plan`/«План (прогноз)», `scenario`/«Сценарій», `manual`/«Вручну», `genset`/«td_genset»; default `manual`, idx |
| `executes` | Boolean | compute stored: `source='manual'` и `resource in ('bess','chp')` — слот выполняется движком (BESS — шаг `slots` R-54 п.5; КГУ — R-50); остальные слоты — только отображение |
| `bar_class` | Selection | compute: `c` (charge), `d` (discharge), `n` (night, duty), `g` (run, test), `o` (day, work) — цвета полос макета |
| `scenario_id` | Many2one | set null |
| `active` | Boolean | default True |

Создание/изменение слотов с `source='manual'` — `group_td_energy_chief` (список/форма V-42; каждое изменение — запись `td.energy.action` `kind_code='schedule_edit'`, класс B, автоматически: override `create/write/unlink` логирует и бампит `config_version`); `plan/scenario/genset` пишет только планировщик (R-54).

### M-35 `td.energy.control` — API экрана «Керування» (AbstractModel; FR-46…FR-54)

`_name = "td.energy.control"`, `_description = "Енергетика: дані екрана Керування"`. Все методы `@api.model`; на входе — проверка группы (`group_td_energy_user` для чтения, `group_td_energy_manager` для `prepare/confirm/…`). Сигнатуры — API-16…API-23, API-27, API-28 (разд. 7). Хуки расширения (пустые в базе): `_td_control_extra(self) -> dict` (дополнительные блоки ответа `get_control`).

### M-36 `td.energy.advice` — расширение: правила и баннер «Виконано» (FR-54, R-55)

`_inherit = "td.energy.advice"`. Добавляет: `_td_advice_rule_export_t2(now)`, `_td_advice_rule_peak_risk(now)`, `_td_advice_rule_chp_price(now)` (реестр R-32 W1 собирает их без изменений); `get_open()` (override): если открытой рекомендации нет, а последнее выполненное действие `origin='advice'` находится в окне `undo_window_min` и `undo_available` — возвращает баннер «Виконано» (R-55 п.4); `_td_on_action_done(action)` — `action_done(note)` через `with_user(action.confirmed_by)`.

### M-37 `td.command` — расширение (R-40 п.6, R-52)

`_inherit = "td.command"`. Добавляет `energy_action_id` (Many2one `td.energy.action`, idx, ondelete set null, readonly). `write()` (override, после `super`): если изменился `state` и есть `energy_action_id` — `action._td_on_command(self)`. `create()` (override): `origin='energy'` без `energy_action_id` или без контекста `td_energy_control_internal` → `UserError("Команди енергетики створює лише модуль керування.")`; команда на сигнал `module='energy_control'` от не-`sudo` → `AccessError` (существующая проверка `td.command` остаётся: группа менеджера телеметрии; модуль создаёт команды через `sudo()`).

### M-38 `td.source` / `td.signal` / `td.energy.event` — расширение (C-41, FR-60, FR-68)

`td.source.type`: `selection_add=[("energy_ctl", "Керування енергетикою (збирач)")]`, `ondelete={"energy_ctl": "cascade"}`; `td.source.module` и `td.signal.module`: `selection_add=[("energy_control", "Керування енергетикою")]`, `ondelete={"energy_control": "set default"}`. Тип `energy_ctl` **не локальный** (`_f3d_local_types` не меняется): нужен `collector_id`. Валидация параметров/адресов: модуль при импорте регистрирует `tools.address.PARAMS_VALIDATORS["energy_ctl"] = _params_energy_ctl` (допустимые ключи `engine` {`tick_s` int 1…10, `config_poll_s` int 5…60}, `doc`; секреты запрещены — стандартная `_secret_errors`) и `ADDRESS_VALIDATORS["energy_ctl"] = lambda a: []`; это временное решение A-40 (официальная точка расширения типов в `td_telemetry` запрошена в Q-30). Ограничения: `td.signal` с `module='energy'` остаётся read-only (W1 M-15, AC-81 действует); `module='energy_control'` допускает `write_enabled`; `td.signal` модуля `energy_control` не может иметь `source_id.module in ('fire_safety','access','machine_connect')` и `code`, начинающийся с `fire/`, `evacuation/`, `sprinklers/`, `access/`, `workcenters/` (R-60 п.2) → `ValidationError("Сигнал {code}: керування цією системою заборонене.")`. `td.energy.event.kind` (W1 M-21): `selection_add=[("control", "Керування")]`, `ondelete={"control": "cascade"}` — события движка, блокировок и `CTRL-HEARTBEAT` создаются через `td.energy.event._td_log(level, 'control', code, text, dedup_min=…)` (W1), `warn`/`bad`; авторазрешение (`_td_auto_resolve('control', code)`) — при восстановлении (`CTRL-HEARTBEAT`, `mode` → `auto`), остальные закрываются автоматически через 24 ч (`cron_td_energy_control_watch`) или вручную (`action_resolve`, W1 R-25). Всё — в файле `models/td_source_signal.py`.

### M-39 `td.energy.control.state` — состояние управления (singleton; FR-57, R-43)

`_name = "td.energy.control.state"`, `_description = "Енергетика: стан керування"`. Одна запись (`xml-id td_energy_control.state_main`, `get()` создаёт при отсутствии).

| Поле | Тип | Параметры |
|---|---|---|
| `config_version` | Integer | default 1; только `bump()` |
| `config_etag` | Char | size=64: sha256 канонического JSON конфига (R-43 п.2) |
| `applied_version` | Integer | default 0: максимум `config_version_applied` из отчётов сборщика |
| `engine_mode` | Selection | `unknown` (default), `off`, `hold`, `auto` |
| `engine_reason` | Char | size=128 (причина `hold`/`off`) |
| `engine_info` | Json | `{"started_at","ticks","tick_ms_p95","writes_last_min","collector"}` |
| `heartbeat_at`, `last_state_at`, `last_config_pull_at` | Datetime | readonly |
| `collector_id` | Many2one `td.collector` | readonly |
| `connected` | Boolean | compute (не хранится): `now − heartbeat_at ≤ heartbeat_stale_s` |

Методы: `get()`, `bump()` (атомарно, `UPDATE … RETURNING`; пересчитывает `config_etag`), `_td_report(body)` (API-25).

### M-40 `res.config.settings` — расширение (V-44)

Поля `td_energy_control_*` с `config_parameter` для параметров разд. 5.1 (группы: «Запобіжники», «Підтвердження», «Виконання», «Автоматика»). `set_values`: изменение `write_enabled`/`automation_enabled` — только администратор (`td_factory3d.group_td_admin`), пишет запись журнала `td.energy.action` `origin='config'`, `kind_code='switch_flag'`, и `state.bump()`.

### M-41 `td.viewer.provider.energy_layer` — провайдер слоя «Енергетика в 3D» (`td_energy_viewer3d`; FR-62, R-57)

`_name = "td.viewer.provider.energy_layer"` (`AbstractModel`, **без** `_inherit` моделей просмотрщика — duck typing, `docs/ARCHITECTURE.md` §6.7, `td_viewer3d` M-01), `_f3d_sequence = 101` (после `td.viewer.provider.energy` 100), `_f3d_sections = ("energy",)`, `_f3d_group = "td_factory3d.group_td_user"` (как у `td.viewer.provider.energy`; киоск-пользователь тоже видит раскраску; `card` — только для `group_td_energy_user` и не в киоске). Методы: `_f3d_viewer_collect(payload, ctx)` → `deep_merge(payload.setdefault("energy", {}), {"layer": tools.layer.build(env, ctx)})`; `_f3d_viewer_delta(patch, ctx)` → если `ctx["changes"]` содержит `td.energy` или сигналы с префиксами W1 `ENERGY_PREFIXES` — `deep_merge(patch.setdefault("energy", {}), {"layer": layer})`, иначе ничего; `_f3d_viewer_bus_models()` → `["td.signal", "td.energy"]`. `from odoo.addons.td_viewer3d.tools.payload import deep_merge` — импорт внутри методов (как `td_energy` R-18).

### M-42 `td.energy.node` и `res.config.settings` (мост 3D) — расширение (V-46, V-47, R-58)

`td.energy.node.action_td_open_3d(code=None)` (`api.model`; группа `group_td_energy_user`): возвращает `ir.actions.client` `tag="f3d_viewer.action"` с параметрами R-58 (слои, режим `td_energy`, `code`). Параметры `td.energy_viewer3d.layers` (JSON-список ключей слоёв GLB для «Відкрити в 3D», default `["building","zones","line","facade","energy","backup","roofdeck"]`), `td.energy_viewer3d.marker_limit` (int, default 40), `td.energy_viewer3d.show_markers` (bool, default True).

## 3. Представления и меню

### 3.1 Представления V-35…V-47

| ID | XML-id (`td_energy_control.`, мост — `td_energy_viewer3d.`) | Тип / модель | Структура |
|---|---|---|---|
| V-35 | `action_td_energy_control` | `ir.actions.client`, `tag="td_energy_control.control"`, `name="Керування енергетикою заводу"` | открывает UI-12 |
| V-36 | `view_td_energy_control_state_form`, `action_td_energy_control_state` | form `td.energy.control.state` (readonly) | поля: `engine_mode`, `engine_reason`, `connected`, `heartbeat_at`, `config_version`, `applied_version`, `config_etag`, `last_state_at`, `last_config_pull_at`, `collector_id`, `engine_info` (Text JSON); кнопка «Опублікувати конфігурацію» (`bump`, администратор) |
| V-37 | `view_td_energy_scenario_list` / `_form`, `action_td_energy_scenario` | list/form `td.energy.scenario` | list: `sequence` (handle), `name`, `enabled` (badge), `engine_state` (badge: `active` success, `armed` info, `warn` warning, `off` muted), `applied` (boolean), `engine_ts`; form (readonly для всех, кроме `params_text` администратора): `description`, `params_text`, `engine_facts` (Text JSON), `config_version`, `state_signal_id`; без кнопок включения (включение — экран «Керування», класс B) |
| V-38 | `view_td_energy_shed_item_list` / `_form`, `action_td_energy_shed_item` | list (editable="bottom", `group_td_energy_chief`) / form | list: `sequence` (handle), `name`, `node_id`, `action`, `param_value`, `condition`, `condition_value`, `kw_reducible`, `p_now_kw` (readonly), `signal_id`, `active`, `how` (readonly); для не-chief — без редактирования |
| V-39 | `view_td_energy_command_kind_list` / `_form`, `action_td_energy_command_kind` | list/form | list: `sequence`, `code`, `name`, `cls` (badge A/B), `executor`, `resource`, `tile`, `available`; form: все поля, `params_schema`/`checks` — Text JSON; редактирование — администратор |
| V-40 | `view_td_energy_interlock_list` / `_form`, `action_td_energy_interlock` | list/form | list: `sequence`, `code`, `name`, `hard`, `fail_closed`, `where`, `active`; form: `params` (Text JSON), `inputs`; редактирование — администратор |
| V-41 | `view_td_energy_action_list` / `_form` / `_search` / `_pivot`, `action_td_energy_action` | list/form/search/pivot `td.energy.action` | list (readonly): `create_date`, `name`, `summary`, `kind_code` (optional hide), `origin`, `cls` (badge), `state` (badge: `done` success, `executing`/`sent`/`queued` info, `awaiting_second` warning, `failed`/`blocked` danger, `expired`/`cancelled` muted), `prepared_by`, `confirmed_by`, `second_by`, `result_text`; form: statusbar `state`, блоки «Дія» (`params`, `checks`, `collector_checks` — таблицы из Text JSON), «Підтвердження», «Результат», чаттер; header-кнопки: «Підтвердити (2/2)» (`action_confirm_second`, `invisible="state != 'awaiting_second'"`), «Скасувати» (`action_cancel`, state ∈ `prepared/awaiting_second/queued`), «Скасувати дію» (`action_undo`, `invisible="not undo_available"`); search: фильтры «Мої» (`prepared_by = uid`), «Очікують підтвердження» (`state = awaiting_second`), «Помилки» (`state in (failed, blocked, expired)`), «Автоматика» (`origin = auto`), «Сьогодні», группировка `origin`, `state`, `kind_code`, `node_id`; pivot: строки `kind_code`, колонки `state`, мера `count` |
| V-42 | `view_td_energy_schedule_slot_list` / `_form` / `_search`, `action_td_energy_schedule_slot` | list (editable bottom для chief)/form/search | list: `resource`, `date`, `weekdays`, `time_from`, `time_to` (widget `float_time`), `mode`, `label`, `setpoint_kw`, `source` (badge), `executes`, `active`; кнопка списка «Перебудувати план» (`action_rebuild_plan`, chief) |
| V-43 | `view_td_command_form_td_energy_control` | form `td.command` (изменение) | поле `energy_action_id` в группе «Керування» (`invisible="not energy_action_id"`) |
| V-44 | `res_config_settings_view_form_td_energy_control` | `res.config.settings` (изменение) | в блоке `app name="td_energy"` раздел «Керування»: «Запобіжники» (`write_enabled`, `automation_enabled`; только администратор, подсказка о 5 предохранителях), «Підтвердження» (`confirm_ttl_s`, `second_ttl_s`, `undo_window_min`), «Виконання» (`command_ttl_s`, `exec_timeout_s`, `step_timeout_s`, `verify_timeout_s`, `apply_timeout_s`), «Автоматика» (`engine_tick_s`, `config_poll_s`, `stale_hold_s`, `min_write_interval_s`, `max_writes_per_min`, `shed_restore_step_s`), «Рекомендації» (`export_advice_min`) |
| V-45 | `views/menus.xml` | `ir.ui.menu` | таблица 3.3 |
| V-46 | `res_config_settings_view_form_td_energy_viewer3d` | `res.config.settings` (изменение, мост) | блок «Енергетика в 3D»: `td_energy_viewer3d_layers` (Text JSON), `…_marker_limit`, `…_show_markers` |
| V-47 | `action_td_energy_3d` | `ir.actions.server` (код: `action = env["td.energy.node"].action_td_open_3d()`) | меню «Енергетика в 3D» |

### 3.2 Клиентские компоненты (OWL) UI-12…UI-28

Всё — `@odoo/owl`, `registry.category("actions")`; данные — `orm.call("td.energy.control", …)`; строки UI на украинском; каждый интерактивный элемент — `<button>` с `aria-label`, минимум 36 px (кнопки ↑/↓ как в макете), переключатели — `role="switch"` + `aria-checked`; состояние не только цветом (текст чипа). Токены цветов — `td_energy.scss` W1 (UI-11): чипы `act`: фон `#ecfdf5`, текст `#065f46`; `arm`: `#eff6ff`/`#1e40af`; `warn`: `#fff7ed`/`#9a3412`; `off`: `#f3f4f6`/`#374151`; переключатель включён `#0f766e`, выключен `#d1d5db`; акцент `#714B67`.

| ID | Компонент / тег | Содержимое и поведение |
|---|---|---|
| UI-12 | `Control` (`td_energy_control.control`) | Шапка (крошки «Енергетика / Керування», h1 «Керування енергетикою заводу», подзаголовок «Режими, сценарії автоматики, пріоритети навантажень і ручні команди», `EngineChip`); информационная полоса с текстом макета («Сценарії виконує контролер ГРЩ і збирач сигналів, без затримок Odoo. Тут задаються режими, уставки й розклад. Кожна ручна команда проходить блокування й підтвердження і пишеться в журнал. Захист людей і пожежна автоматика працюють окремо й тут не керуються.»); баннер ожидания второго подтверждения (D-43); секции UI-14, UI-15 и UI-16 рядом, UI-19, UI-20. Данные: `get_control()` (API-16); обновление: подписка на шину `td_energy_control` (хук `useControlBus(callback, kinds)` в `static/src/control/bus.js`: канал `td_energy_control`, сообщение `td_energy_control/update` `{"kinds": ["action","scenario","engine","schedule","shed"], "ts"}` без данных, A-41; дебаунс 2 с), резервный таймер 30 с. Состояние: `data`, `dialog`, `reorder`, `busy`. Тосты — по состояниям D-31 |
| UI-13 | `EngineChip` | `engine.connected && mode=='auto'` → зелёный «Контролер ГРЩ і збирач на зв'язку · HH:MM»; `connected && mode in (hold, off)` → янтарный «Автоматику призупинено: {reason}»; `!connected` → красный «Збирач не на зв'язку · {вік}» (D-28) |
| UI-14 | `ScenarioGrid`, `ScenarioCard` | Заголовок секции «Сценарії автоматики» и «увімкнено N з 6»; сетка `repeat(auto-fill, minmax(320px, 1fr))`; карточка: `h3` название, чип `state_text` (цвет `state_kind`), `role="switch"` (класс B: клик открывает `ConfirmDialog` для `scenario_toggle`; состояние переключателя = `enabled` из Odoo; если `!applied` — дополнительный чип «Очікує застосування»), описание, чипы параметров (`chips[]`), кнопка «Параметри» (UI-18) |
| UI-15 | `ShedList` | Заголовок «Пріоритети відключення навантажень», подзаголовок «Що зменшувати першим, коли не вистачає BESS і КГУ, щоб утримати {limit_kw} кВт»; `ol` строк: круглый номер, `name`, `how`, `−{kw_reducible} кВт`, кнопки «Вище»/«Нижче» (`aria-label`, 36 × 36) только в режиме «Змінити порядок» (D-24); подвал «Разом можна зняти **{sum} кВт**. Не відключаються ніколи: {never_text}.» (D-26); кнопки «Змінити порядок» (chief/manager) → «Зберегти порядок» (открывает `ConfirmDialog` `shed_reorder`) / «Скасувати» |
| UI-16 | `CommandTiles` | Заголовок «Ручні команди», подзаголовок «Права: енергетик і головний енергетик · кожна команда з підтвердженням»; сетка 2 колонки, плитка `min-height: 56px`: `label` (жирный) и `sub`; класс B — бейдж «B» и подсказка; `available=false` или нет прав — `disabled` + `title` причины; клик → `prepare` → `ConfirmDialog` |
| UI-17 | `ConfirmDialog` | `role="dialog" aria-modal="true"`, максимальная ширина 500 px; заголовок «{title}?», абзац `text`, подзаголовок «Перевірка блокувань», список «{label} — **гаразд**» (зелёный) / «**не виконано**» (красный, причина) / «**немає даних**» (янтарный; для `hard+fail_closed` блокирует); для класса B без `chief`: строка «Потрібне друге підтвердження іншим енергетиком» и кнопка «Підтвердити (1/2)»; кнопки «Скасувати», «Виконати» (`disabled`, если `blocked`); обратный отсчёт TTL токена (`confirm_ttl_s`), по истечении — «Час підтвердження минув, відкрийте діалог знову»; после `confirm` — блок прогресса «Надіслано → Виконується → Виконано / Не виконано: {error}» (опрос `get_action(id)` каждые 2 с до `finished_at`, не дольше `verify_timeout_s + 30`); Esc = «Скасувати» (`cancel(token)`), Enter подтверждает класс A без блокировок; фокус в диалоге, возврат фокуса на плитку |
| UI-18 | `ParamsDialog` | Форма параметров сценария по `params_schema` сценария (поля из API-16 `scenarios[].schema`), подсказки с границами; «Зберегти» → `prepare('scenario_params', …)` → `ConfirmDialog` |
| UI-19 | `ScheduleTimeline` | Секция «Розклад на сьогодні», справа «зараз {HH:MM} · план складено з прогнозу навантаження й СЕС»; сетка `200px 1fr`, минимальная ширина 860 px, шкала 00…24 шаг 3 ч, 6 строк (BESS, КГУ, Вентиляція RoofVent, Освітлення цеху, Зарядна станція, ДГУ), полосы `left = from/24`, `width = (to−from)/24`, цвета `bar_class` (`c` `#99f6e4/#134e4a`, `d` `#c4b5fd/#3b0764`, `n` `#bfdbfe/#1e3a8a`, `g` `#fde68a/#78350f`, `o` `#e5e7eb/#374151`), подпись в полосе и `title`; вертикаль «зараз» (чёрная, 2 px) на `now/24`; под таблицей — текстовая таблица для скринридеров (`visually-hidden`) |
| UI-20 | `Journal` | Секция «Журнал команд і перемикань»; строка: время `HH:MM` (52 px), `<b>{summary}</b> · {detail}`, `actor_text`, чип результата (`виконано` зелёный, `створено`/`збережено, очікує збирач` синий, `не виконано`/`заблоковано` красный, `скасовано` серый); для действий с `undo_available` — кнопка «Скасувати дію» (открывает `ConfirmDialog` для `undo`); для `awaiting_second` — «Підтвердити (2/2)» (только другой `manager`); кнопка «Показати більше» (50 записей за шаг, `before_id`) и ссылка «Усі записи» → V-41 |
| UI-21 | `ControlAdviceHandler` | Регистрирует `registry.category("td_energy.advice_handlers").add("control", handler)`: `handler({action, advice, component})` вызывает `prepare(command_kind, params, {advice_id})` и показывает `ConfirmDialog`; после `done` возвращает `true` (Пульт перечитывает `advice`, `alarms`); для `act.code='undo'` — `undo(action_id)` (R-55 п.4) |
| UI-22 | `NodeActions` | Регистрирует `registry.category("td_energy.node_actions").add("td_energy_control", {match, actions})`: для узла `QS` — «Увімкнути QS…» (`qs_close`) или «Вимкнути QS…» (`qs_open`) по `sld_state`; для `BESS` — «Зарядити 50 кВт» (`bess_charge`) или «Зупинити заряд» (`bess_stop`) по состоянию; действия из `get_node_actions(code)` (API-27) и стилем `o_td_en_btn--teal` (D-38) |
| UI-28 | `DoneBanner` | Вариант баннера Пульта `advice.state==='done'` (зелёный, иконка «галочка», текст `title` жирным + `text`, кнопка «Скасувати»; без «Пізніше»): классы `o_td_en_advice--done` в `pult.xml`, стиль в `control.scss` |
| UI-23…UI-27 | `td_energy_viewer3d` | Описаны в разд. 8.4.3 (`EnergyLayerExtension`, `StateColors`, `AlarmMarkers`, `NodeBlock`, `ViewerLinks`) |

### 3.3 Меню (`views/menus.xml`)

| XML-id | Название | Родитель | seq | Группы | Действие |
|---|---|---|---|---|---|
| `td_energy_control.menu_td_energy_control` | Керування | `td_energy.menu_td_energy` | 8 | `td_energy.group_td_energy_user` | `action_td_energy_control` |
| `td_energy_control.menu_td_energy_action` | Журнал команд | `td_energy.menu_td_energy` | 9 | `td_energy.group_td_energy_user` | `action_td_energy_action` |
| `td_energy_control.menu_td_energy_scenario` | Сценарії автоматики | `td_energy.menu_td_energy_config` | 50 | `td_energy.group_td_energy_manager` | `action_td_energy_scenario` |
| `td_energy_control.menu_td_energy_shed_item` | Пріоритети скидання | `td_energy.menu_td_energy_config` | 51 | `td_energy.group_td_energy_manager` | `action_td_energy_shed_item` |
| `td_energy_control.menu_td_energy_schedule_slot` | Розклад (слоти) | `td_energy.menu_td_energy_config` | 52 | `td_energy.group_td_energy_manager` | `action_td_energy_schedule_slot` |
| `td_energy_control.menu_td_energy_interlock` | Блокування | `td_energy.menu_td_energy_config` | 53 | `td_energy.group_td_energy_manager` | `action_td_energy_interlock` |
| `td_energy_control.menu_td_energy_command_kind` | Види команд | `td_energy.menu_td_energy_config` | 54 | `td_factory3d.group_td_admin` | `action_td_energy_command_kind` |
| `td_energy_control.menu_td_energy_control_state` | Стан керування | `td_energy.menu_td_energy_config` | 55 | `td_factory3d.group_td_admin` | `action_td_energy_control_state` |
| `td_energy_viewer3d.menu_td_energy_3d` | Енергетика в 3D | `td_energy.menu_td_energy` | 90 | `td_energy.group_td_energy_user` | `action_td_energy_3d` |

Пункт «Керування» появляется только после установки модуля (W1 D-18). Порядок верхнего меню: Пульт (5), Чергування (6), Керування (8), Журнал команд (9), Завантаження вузлів (15), …

### 3.4 Правки клиента `td_energy` (владелец B; минимальные, аддитивные; AC-292, AC-301, AC-302)

1. `static/src/common/actions.js`: экспортируется `viewerLinks = registry.category("td_energy.viewer_links")`; `openViewer(opts)` — если есть запись `default`, вызывает `link.open({code: opts?.code})`; иначе поведение W1 (уведомление или `f3d_viewer.action` с `params.layers`, исправление ключа `layer` → `layers: ["energy"]`); `show3d(code)` — если есть запись `default`, `link.open({code})` (работает и для узлов без `equipment_id`, если в слое есть `scene`), иначе существующий путь `action_f3d_show` (C-45).
2. `static/src/pult/sld.js`, `sld.xml`: под кнопками панели узла — цикл по записям реестра `td_energy.node_actions` (контракт: `{match(node) → bool, actions(node, ctx) → Promise<[{code, label, cls, onClick}]>}`), кнопки класса `o_td_en_btn` (C-46).
3. `static/src/pult/pult.xml`, `pult.js`: вариант баннера `advice.state === 'done'` (UI-28): класс `o_td_en_advice--done`, скрыта «Пізніше».
4. `static/tests/control_hooks.test.js`: hoot-тесты пунктов 1–3 (AC-292, AC-301, AC-302). Других изменений W1-кода нет; бэкенд `td_energy` не меняется (A-41).

## 4. Права

### 4.1 `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_energy_scenario_user,td.energy.scenario user,model_td_energy_scenario,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_scenario_admin,td.energy.scenario admin,model_td_energy_scenario,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_shed_item_user,td.energy.shed.item user,model_td_energy_shed_item,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_shed_item_chief,td.energy.shed.item chief,model_td_energy_shed_item,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_shed_item_admin,td.energy.shed.item admin,model_td_energy_shed_item,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_command_kind_user,td.energy.command.kind user,model_td_energy_command_kind,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_command_kind_admin,td.energy.command.kind admin,model_td_energy_command_kind,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_interlock_user,td.energy.interlock user,model_td_energy_interlock,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_interlock_admin,td.energy.interlock admin,model_td_energy_interlock,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_action_user,td.energy.action user,model_td_energy_action,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_action_admin,td.energy.action admin,model_td_energy_action,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_schedule_slot_user,td.energy.schedule.slot user,model_td_energy_schedule_slot,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_schedule_slot_chief,td.energy.schedule.slot chief,model_td_energy_schedule_slot,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_schedule_slot_admin,td.energy.schedule.slot admin,model_td_energy_schedule_slot,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_control_state_user,td.energy.control.state user,model_td_energy_control_state,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_control_state_admin,td.energy.control.state admin,model_td_energy_control_state,td_factory3d.group_td_admin,1,1,1,1
```

`td.energy.control` — `AbstractModel` без ACL (проверка в методах, M-35). «Енергетик» (`group_td_energy_manager`) наследует `group_td_energy_user` и напрямую только читает эти модели; все его действия — через M-35/M-33 под `sudo()`. Новых групп нет (E-06: группы из W1; `group_td_energy_chief` — «Головний енергетик»). Record rules не нужны (модели без компании; как `td.energy.event` W1 §4.3).

### 4.2 Матрица прав (R-39)

| Операция | `…_user` | `…_manager` («Енергетик») | `…_chief` («Головний енергетик») | администратор |
|---|---|---|---|---|
| Видеть экран, журнал, расписание, проверки | ✓ | ✓ | ✓ | ✓ |
| `prepare` команды класса A, `confirm` A | ✗ | ✓ | ✓ | ✓ |
| `prepare` команды/действия класса B | ✗ | ✓ | ✓ | ✓ |
| `confirm` B, единолично | ✗ | ✗ (становится `awaiting_second`) | ✓ | ✓ |
| `confirm_second` B (другое лицо) | ✗ | ✓ (≠ готовил, ≠ подтверждал) | ✓ (≠ …) | ✓ |
| `undo` | ✗ | по классу обратного вида | по классу | ✓ |
| Изменять состав/параметры `shed.item`, слоты `manual` | ✗ | ✗ | ✓ | ✓ |
| Изменять `command.kind`, `interlock.params`, флаги `write_enabled`/`automation_enabled`, `config_poll_s` | ✗ | ✗ | ✗ | ✓ |
| Тест ДГУ (`genset_test`, B) | ✗ | первое лицо | ✓ | ✓ + права `td_genset` (`group_tech`, ADP-12 R-67) |

### 4.3 Предохранители («пять + один»)

Чтобы устройство получило запись: (1) `td.telemetry.write_enabled`; (2) `td.energy_control.write_enabled`; (3) `td.source.write_enabled` источника (`MB-U73-SWB-CMD`, `ENERGY-CTL`, а для BMS — соответствующие источники `td_bms`; плюс `td.bms.write_enabled`); (4) `td.signal.write_enabled`; (5) `F3D_WRITE_ENABLED=true` в сборщике. Для автономных действий сценариев дополнительно (6) `td.energy_control.automation_enabled`. Отдельно от предохранителей — переключатель `td.energy_control.remote_switching_enabled` (D-46, Q-27, default `False`): при `False` команды дистанционного перемикання (`remote_gated`) отказываются с `UserError` независимо от прочих флагов. По умолчанию все `False` (прод) — на тестовом сервере включение делает менеджер скриптом `hooks._td_enable_stand(env)` (R-61; ставит и `remote_switching_enabled=True`). `neutralize.sql` сбрасывает (2), (3), (4), (6) и `remote_switching_enabled` (разд. 5.7). Стоп-кран `module='energy'` (W1 AC-81) не меняется: все записываемые сигналы этого модуля имеют `module='energy_control'`.

### 4.4 Защита данных и действий

- Токен `prepare` — случайные 24 байта (`secrets.token_urlsafe`), в БД только `sha256`; сравнение `hmac.compare_digest`; токен принадлежит пользователю (`prepared_by`), другой пользователь с токеном → `AccessError`.
- `confirm` атомарен: `SELECT … FOR UPDATE` на записи действия; повторный `confirm` того же токена возвращает тот же результат без новой команды (R-40 п.4).
- Конфиг для сборщика не содержит секретов и стоимости; `/td/energy/automation/*` — Bearer-токен коллектора (`td.collector._authenticate`), `auth="public"`, `csrf=False`, rate-limit `collector._rate_check()`.
- Стоимость (`group_td_energy_cost`) на экране «Керування» не показывается.
- Запрещено: запись в `td_genset` (только адаптер ADP-12), изменение меню `td_genset`, `x_`-поля, `safe_eval` над данными БД, управление сигналами системной безопасности (R-60).

## 5. Данные

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| Ключ | По умолчанию | Назначение |
|---|---|---|
| `td.energy_control.write_enabled` | `False` | предохранитель (2): ручные команды устройствам |
| `td.energy_control.automation_enabled` | `False` | предохранитель (6): автоматика сборщика выполняет действия; иначе движок в режиме `off` (мониторинг) |
| `td.energy_control.confirm_ttl_s` | `60` | TTL токена `prepare` → `confirm` |
| `td.energy_control.second_ttl_s` | `600` | ожидание второго подтверждения |
| `td.energy_control.command_ttl_s` | `120` | `expires_at` команды в очереди `td.command` |
| `td.energy_control.exec_timeout_s` | `60` | максимальное время выполнения интента в сборщике |
| `td.energy_control.step_timeout_s` | `8` | запись одного шага |
| `td.energy_control.verify_timeout_s` | `30` | ожидание подтверждения устройством (сумма шагов ≤ `exec_timeout_s`) |
| `td.energy_control.apply_timeout_s` | `60` | ожидание применения конфигурации сборщиком |
| `td.energy_control.undo_window_min` | `15` | окно отмены и баннер «Виконано» |
| `td.energy_control.heartbeat_stale_s` | `30` | heartbeat движка старше — «не на зв'язку» |
| `td.energy_control.engine_tick_s` | `2` | период цикла движка |
| `td.energy_control.config_poll_s` | `10` | период опроса конфига движком |
| `td.energy_control.stale_hold_s` | `30` | вход несвежее → движок в `hold` |
| `td.energy_control.min_write_interval_s` | `10` | минимальный интервал повторной записи того же сигнала |
| `td.energy_control.max_writes_per_min` | `30` | предохранитель частоты записей движка |
| `td.energy_control.shed_restore_step_s` | `20` | шаг восстановления сброшенных нагрузок |
| `td.energy_control.plan_horizon_days` | `2` | на сколько суток вперёд строится план (R-54) |
| `td.energy_control.export_advice_min` | `5` | минут экспорта для правила EXPORT-T2 (R-55) |
| `td.energy_control.journal_limit` | `50` | записей журнала за один запрос |
| `td.energy_control.remote_switching_enabled` | `False` (demo/стенд — `True`) | D-46 / Q-27: дистанционное перемикання (`qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`) разрешено; иначе `UserError` |

### 5.2 `data/td_energy_scenario_data.xml` — 6 сценариев (noupdate; тексты и параметры макета `Control.dc.html`)

| `code` | `name` | `description` (макет) | `enabled` | Чипы параметров (макет → источник) |
|---|---|---|---|---|
| `peak` | Зрізання піку | «Тримати імпорт нижче уставки: спершу розряд BESS, потім пуск КГУ, далі відключення за пріоритетами.» | ✓ | «уставка {limit_kw} кВт · {limit_pct} %», «прогноз 15 хв» |
| `self` | Самоспоживання СЕС | «Надлишок СЕС заряджає BESS. Експорт у мережу не більше 20 кВт, далі обмеження інверторів.» | ✗ | «експорт ≤ {export_max_kw} кВт», «BESS до {bess_target_soc_pct} %» |
| `pfc` | Компенсація реактивної потужності | «Автоматичні ступені PFC-1 і PFC-2 тримають цільовий cos φ на кожній секції.» | ✓ | «ціль cos φ {cos_phi_target}», «крок {pfc_step_kvar} квар» |
| `night` | Нічний режим (BMS) | «Поза змінами: вентиляція RoofVent на 30 %, у цеху — черговий сценарій освітлення, опалення на 16 °C.» | ✓ | «{from}–{to}», «RoofVent {vent_pct} %», «{heat_setpoint_c} °C» |
| `backup` | Резервне живлення | «Зникла мережа: АВР переводить на ДГУ, неважливі навантаження вимикаються, критичні лишаються.» | ✓ | «АВР → ДГУ», «критичні {critical_kw} кВт» |
| `chp` | КГУ за графіком і ціною | «Пуск КГУ, коли газ дешевший за мережу або коли BESS не вистачає для зрізання піку.» | ✗ | «мін. робота {min_run_h} год», «ціна газу {gas_price_uah_m3} ₴/м³» |

Чипы формируются в `tools/status_text.py` (`chips(scenario)`; числа форматируются `0,0` с запятой, `95 %` = округлённое `limit_kw / contract_kw · 100`).

### 5.3 `data/td_energy_command_kind_data.xml` — 16 видов команд

Колонки: `code` · заголовок плитки / sub · класс · исполнитель · ресурс · проверки (R-41; «м» — мягкая) · параметры (`name` тип границы, default) · обратный вид.

| `code` | Плитка (`name` / `sub_template`) | `cls` | `executor` | `resource` | Проверки | Параметры | `undo_kind` |
|---|---|---|---|---|---|---|---|
| `qs_close` | «Увімкнути секційний вимикач QS» / «секції 1 і 2 разом» | B | intent | qs | `controller_remote`, `data_fresh`, `no_island`, `ats_parallel_lock`, `qs_current_ok` | — | `qs_open` |
| `qs_open` | «Вимкнути секційний вимикач QS» / «секції окремо» | B | intent | qs | `controller_remote`, `data_fresh` | — | `qs_close` |
| `bess_charge` | «Заряд BESS {power_kw} кВт» / «до {until} або {soc_limit_pct} %» | A | intent | bess | `controller_remote`, `data_fresh`, `no_island`, `bess_ok`, `bess_soc_lt_limit`, `bess_temp_ok` | `power_kw` float 1…`bess_max_kw`, 50; `until` time `HH:MM`, 16:00; `soc_limit_pct` float 50…100, 95 | `bess_stop` |
| `bess_discharge` | «Розряд BESS {power_kw} кВт» / «на {duration_min} хв» | B | intent | bess | `controller_remote`, `data_fresh`, `bess_ok`, `bess_reserve_kept`, `bess_temp_ok` | `power_kw` float 1…`bess_max_kw`, 100; `duration_min` int 1…240, 60 | `bess_stop` |
| `bess_stop` | «Зупинити BESS» / «повернути автоматичний режим» | A | intent | bess | `controller_remote` | — | — |
| `chp_start` | «Пуск КГУ» / «TEDOM Quanto D800» | B | intent | chp | `controller_remote`, `data_fresh`, `no_island`, `chp_ready`, `chp_gas_pressure`, `chp_permit` | — | `chp_stop` |
| `chp_stop` | «Зупинка КГУ» / «з охолодженням» | B | intent | chp | `controller_remote`, `chp_min_run` | — | `chp_start` |
| `genset_test` | «Тест ДГУ без навантаження» / «{test_minutes} хв» | B | genset | genset | `genset_fuel` (м), `genset_heater` (м), `no_island`, `genset_idle` | `mode` enum `idle`, `idle` | — |
| `light_break` | «Освітлення цеху · сценарій «Перерва»» / «{level_pct} % на {duration_min} хв» | A | intent | light | `controller_remote`, `no_fire_alarm`, `aisle_lux_ge` (м) | `level_pct` int 10…100, 50; `duration_min` int 1…120, 30; `scene_number` int 1…16, 3 | `light_restore` |
| `light_restore` | «Освітлення цеху · повернути режим» / «за розкладом» | A | intent | light | `no_fire_alarm` | — | — |
| `vent_eco` | «Вентиляція · режим «Економ»» / «RoofVent {vent_pct} %» | A | intent | vent | `controller_remote`, `no_fire_alarm`, `co2_lt` (м) | `vent_pct` int 30…100, 70; `duration_min` int 1…480, 120 | `vent_restore` |
| `vent_restore` | «Вентиляція · повернути режим» / «за розкладом» | A | intent | vent | `no_fire_alarm` | — | — |
| `air_setpoint` | «Компресорна · тиск {setpoint_bar} бар» / «змінити уставку з {current_bar} до {setpoint_bar} бар» | B | intent | air | `controller_remote`, `data_fresh`, `air_setpoint_min` | `setpoint_bar` float 5,0…8,5, 6,5 | `air_setpoint` (с `undo_params.setpoint_bar = current_bar`) |
| `scenario_toggle` | «Сценарій «{scenario}»: {on_off}» | B | config | config | — | `scenario` enum, `enabled` bool | `scenario_toggle` |
| `scenario_params` | «Параметри сценарію «{scenario}»» | B | config | config | — | по схеме сценария (M-29) | `scenario_params` |
| `shed_reorder` | «Порядок скидання навантажень» | B | config | config | — | `order` list[int] | `shed_reorder` |

Плитки (`tile=True`, порядок и подписи как в макете): `qs_close`, `bess_charge`, `bess_discharge`, `chp_start`, `genset_test`, `light_break`, `vent_eco`, `air_setpoint` — 8 штук. `confirm_title`/`confirm_text` — тексты диалогов макета: QS «Увімкнути секційний вимикач QS?» / «Секції 1 і 2 працюватимуть разом. Генерація СЕС піде на навантаження секції 1, експорт через T2 припиниться.»; `bess_charge` «BESS заряджатиметься від надлишку СЕС і мережі до {until}.»; `bess_discharge` «BESS віддаватиме {power_kw} кВт у секцію 2 протягом {duration_min} хв.»; `chp_start` «КГУ запуститься й вийде на {chp_kw} кВт за {ramp_min} хв. Мінімальний час роботи — {min_run_h} год.»; `genset_test` «ДГУ запуститься на холостому ходу на {test_minutes} хв, АВР лишається на мережі.»; `light_break` «Освітлення ліній знизиться до {level_pct} % на {duration_min} хв, проходи лишаються на 100 %.»; `vent_eco` «Дахові установки знизять продуктивність до {vent_pct} %, CO₂ контролюється.»; `air_setpoint` «Уставка тиску мережі стисненого повітря знизиться з {current_bar} до {setpoint_bar} бар.».

### 5.4 `data/td_energy_interlock_data.xml` — реестр блокировок (20 строк)

Колонки: `code` · `name` (шаблон строки диалога) · `hard` · `fail_closed` · `where` · `inputs` (коды сигналов) · `params` (сид). Алгоритмы — R-41.

| `code` | `name` | hard | f_closed | where | inputs | `params` |
|---|---|---|---|---|---|---|
| `controller_remote` | «Контролер у дистанційному режимі» | ✓ | ✓ | both | `energy_control/ctl/remote` | — |
| `data_fresh` | «Дані свіжі» | ✓ | ✓ | both | (остальные входы проверки) | `max_age_s` 60 |
| `no_island` | «Мережа є, острівного режиму немає» | ✓ | ✓ | both | `infra/ats/position`, `infra/ats/src1_ok` | — |
| `ats_parallel_lock` | «Блокування паралельної роботи T1 і T2 від АВР — увімкнено» | ✓ | ✓ | both | `energy_control/ats/parallel_lock` | — |
| `qs_current_ok` | «Струм через QS після вмикання ≈ {i_a} А з {rating_a} А» | ✓ | ✓ | both | `energy/sections/S1/p_kw`, `energy/sections/S2/p_kw`, `energy/cells/QS/state` | `rating_a` 1600, `max_ratio` 0.8, `cos_phi` 0.95 |
| `bess_ok` | «BESS на зв'язку, без аварії» | ✓ | ✓ | both | `infra/bess/state` | — |
| `bess_soc_lt_limit` | «Заряд {soc} % < {limit} %» | ✓ | ✓ | both | `infra/totals/bess_soc` | — |
| `bess_reserve_kept` | «Резерв на відключення мережі {reserve} % збережено» | ✓ | ✓ | both | `infra/totals/bess_soc`, `energy_control/bess/reserve_pct` | `capacity_kwh` 387 |
| `bess_temp_ok` | «Температура шафи {t} °C» | ✓ | ✗ | both | `energy_control/bess/temp_c` | `max_c` 40 |
| `chp_ready` | «КГУ зупинена й готова до пуску» | ✓ | ✓ | both | `infra/chp/state` | — |
| `chp_gas_pressure` | «Тиск газу {bar} бар» | ✓ | ✓ | both | `energy_control/chp/gas_bar` | `min_bar` 1.5 |
| `chp_permit` | «Дозвіл оператора КГУ» | ✓ | ✓ | both | `energy_control/chp/permit` | — |
| `chp_min_run` | «Мінімальний час роботи КГУ {h} год відпрацьовано» | ✓ | ✗ | collector | `infra/chp/state`, `infra/chp/hours` | `min_run_h` 2 |
| `no_fire_alarm` | «Пожежної тривоги немає» | ✓ | ✗ | both | `fire/panel/state` (если есть) | — |
| `genset_fuel` | «Паливо ДГУ {pct} %» | ✗ | — | odoo | (адаптер ADP-03) | `min_pct` 30 |
| `genset_heater` | «Підігрів двигуна увімкнено» | ✗ | — | odoo | (адаптер) | — |
| `genset_idle` | «ДГУ не в роботі й тест не йде» | ✓ | ✗ | odoo | (адаптер) | — |
| `aisle_lux_ge` | «Освітленість проходів ≥ {lux} лк» | ✗ | — | both | `lighting/groups/*/e_now` (проходы по BMS) | `min_lux` 75 |
| `co2_lt` | «CO₂ у цеху {ppm} ppm < {limit} ppm» | ✗ | — | both | `ventilation/totals/co2_ppm` (если есть) | `max_ppm` 1000 |
| `air_setpoint_min` | «Мінімальний тиск споживачів {min} бар» | ✓ | ✓ | both | `energy_control/air/min_consumer_bar` | `margin_bar` 0.2, `max_bar` 8.5 |

`hard` при `where='odoo'` блокирует только «Виконати» в Odoo (у сборщика этих проверок нет: `td_genset` имеет собственные `_precheck`); `where='collector'` — в диалоге строка «перевіряє збирач» (состояние `unknown`, не блокирует) и жёсткая проверка в сборщике (R-41 п.3).

### 5.5 `data/td_energy_shed_item_data.xml` — приоритеты (макет `loads`, порядок `prio`)

| № | `name` | `node_id` (код) | `action` | `param_value` | `kw_reducible` | `condition` | `how` (вычисляется) |
|---|---|---|---|---|---|---|---|
| 1 | Зарядна станція навантажувачів | `CHARGING` | `defer` | 30 | 48 | `none` | «відкласти заряд до 30 хв» |
| 2 | Дахова вентиляція RoofVent | `RV-ALL` | `reduce` | 70 | 60 | `none` | «знизити до 70 %» |
| 3 | Сушильна камера DRY-1 | `DRY-1` | `pause` | 20 | 17 | `no_active_cycle` | «пауза до 20 хв, без втрати циклу» |
| 4 | Компресор 2 (резервний) | `COMPRESSOR` | `off` | 0 | 37 | `air_pressure_min` (6,5) | «вимкнути, тиск ≥ 6,5 бар» |
| 5 | Освітлення складів | `LP-1` | `reduce` | 50 | 12 | `none` | «знизити до 50 %» |

Сумма `kw_reducible` = 174 кВт (макет: «Разом можна зняти 174 кВт»). `COMPRESSOR` и `LP-1` — узлы `is_critical` (W0): строки допускаются M-30 п.2 (`condition` / `reduce`), имеют `critical=True` и выполняются только в `peak`. Узел `DRY-1` имеет `workcenter_id` → условие `no_active_cycle` обязательно (M-30 п.3). Сигналы `signal_id` — `energy_control/shed/<node.code>/limit_pct` (разд. 5.6).

### 5.6 `data/energy_control_sources.csv`, `energy_control_signals.csv`, `hooks._load_sources_signals(env)`

Источники (колонки как у W1 `energy_sources.csv`; `module='energy_control'`, `read_enabled=1`, `write_enabled=0`; создаются идемпотентно, существующие не меняются):

| `code` | Тип | Параметры | Оборудование |
|---|---|---|---|
| `MB-U73-SWB-CMD` | `modbus_tcp`, unit 73, host `iot-sim`, порт 502, `timeout_s=3`, `retries=2`, `max_block=125`, `gap_max=8` | окно управления контроллера ГРЩ (HR 200…299; ДОПУЩЕНИЕ A-45, на объекте — документ контроллера) | `SWB-1` |
| `ENERGY-CTL` | `energy_ctl`, `params={"engine": {"tick_s": 2, "config_poll_s": 10}}` | виртуальный «источник» движка и интентов в сборщике | — |

Сигналы `MB-U73-SWB-CMD` (Modbus FC3 чтение HR; запись FC6 в тот же адрес; тип u16; `R/W`; `kind=gauge`, если не указано; `period_s=10`, `store_period_s=300`, `viewer_visible=0`; `write_enabled=0` в данных для всех):

| Код сигнала | HR | R/W | Единица / масштаб | Семантика |
|---|---|---|---|---|
| `energy_control/ctl/heartbeat` | 290 | R | счётчик | контроллер жив (растёт каждую секунду, 0…65535) |
| `energy_control/ctl/remote` | 291 | R | 0/1 | 1 — дистанционное управление разрешено (переключатель «Местное/Дистанционное»), `kind=state` `["local","remote"]` |
| `energy_control/qs/cmd` | 200 | W | 0 ничего, 1 открыть, 2 замкнуть | контроллер выполняет и сбрасывает в 0 |
| `energy_control/qs/ack` | 201 | R | 0 нет, 1 выполнено, 2 отказано блокировкой контроллера, 3 сбой | результат последней команды |
| `energy_control/ats/parallel_lock` | 202 | R | 0/1 | блокировка параллельной работы T1/T2 от АВР |
| `energy_control/pfc/mode` | 210 | RW | 0 ручной (ступени выключены), 1 авто | |
| `energy_control/pfc/cos_target` | 211 | RW | ×0,01 | 95 = 0,95 (E-10) |
| `energy_control/bess/mode` | 220 | RW | 0 авто, 1 принудительный заряд, 2 принудительный разряд, 3 удержание (0 кВт) | |
| `energy_control/bess/setpoint_kw` | 221 | RW | кВт 0…200 | |
| `energy_control/bess/until_soc` | 222 | RW | % 0…100 (0 — без границы) | заряд останавливается при ≥, разряд — при ≤ |
| `energy_control/bess/valid_s` | 223 | RW | с 0…65535 | **сторожевой таймер**: по истечении контроллер возвращает режим 0 (авто) |
| `energy_control/bess/remaining_s` | 224 | R | с | остаток `valid_s` |
| `energy_control/bess/reserve_pct` | 225 | R | % | пол разряда контроллера (30) |
| `energy_control/bess/ack` | 226 | R | 0 принято, 2 отказано (пол SOC/температура), 3 сбой | |
| `energy_control/bess/temp_c` | 227 | R | ×0,1 °C | температура шкафа |
| `energy_control/chp/cmd` | 230 | W | 0 ничего, 1 пуск, 2 остановка | |
| `energy_control/chp/ack` | 231 | R | 0 нет, 1 выполнено, 2 отказано (газ/разрешение/сбой), 3 сбой | |
| `energy_control/chp/permit` | 232 | R | 0/1 | разрешение оператора КГУ |
| `energy_control/chp/gas_bar` | 233 | R | ×0,01 бар | давление газа (210 = 2,10) |
| `energy_control/air/setpoint_bar` | 240 | RW | ×0,01 бар | уставка давления (700 = 7,00) |
| `energy_control/air/min_consumer_bar` | 241 | R | ×0,01 бар | минимальное давление потребителей (620) |
| `energy_control/pv/limit_pct` | 250 | RW | % 0…100 | ограничение мощности инверторов СЭС (100 — без ограничения) |
| `energy_control/shed/CHARGING/limit_pct` | 260 | RW | % 0…100 | лимит нагрузки (100 — без лимита, 0 — выключено) |
| `energy_control/shed/RV-ALL/limit_pct` | 261 | RW | % | то же |
| `energy_control/shed/DRY-1/limit_pct` | 262 | RW | % | |
| `energy_control/shed/COMPRESSOR/limit_pct` | 263 | RW | % | |
| `energy_control/shed/LP-1/limit_pct` | 264 | RW | % | |
| `energy_control/shed/valid_s` | 270 | RW | с | **сторожевой таймер** ограничений сброса и `pv/limit_pct`: по истечении все лимиты возвращаются в 100 % |

**Формат `address`** (JSON по `td_telemetry` Приложение A.1; запись — как у плагина `modbus_tcp`: `raw = (value − offset) / scale`, `address.write.fc/addr`): `{"fc":3,"addr":221,"type":"u16","write":{"fc":6,"addr":221}}`; для сигналов с масштабом ×0,01 — дополнительно `"scale":0.01` (`pfc/cos_target`, `air/setpoint_bar`, `air/min_consumer_bar`, `chp/gas_bar`) или 0,1 (`bess/temp_c`); `kind=state` (`ctl/remote`) — `"map":{"0":"local","1":"remote"}`; сигналы только для чтения — без `write`. Движок и Odoo оперируют **инженерными** значениями (кВт, бар, %, с), регистры — сырые u16. `unit` Modbus берётся из параметров источника (73).

Сигналы `ENERGY-CTL`: `energy_control/intent` (`kind=event`, `write_enabled=0`; единственный «записываемый» сигнал для интентов; `address={}`), `energy_control/auto/heartbeat` (`counter`, 10 с; публикует движок, значение — счётчик тиков), `energy_control/auto/{peak,self,pfc,night,backup,chp}/state` (`kind=state`, `states=["off","armed","active","warn"]`, `store_period_s=60`, пишет движок; `alarm_states` не задан). Всего **36 сигналов** (28 + 8) и **2 источника**. Порогов и `alarm_states` для сигналов управления не задано (чтобы не создавать заявки ТО): событие «Контролер у місцевому режимі» формируется в R-44 п.5.

Ожидаемый результат `post_init_hook` на демо-БД после W1 (`td.source` 136): `td.source` 138 (+2), `td.signal` модуля `energy_control` +36; `td.energy.scenario` 6; `td.energy.command.kind` 16; `td.energy.interlock` 20; `td.energy.shed.item` 5; `td.energy.schedule.slot` ≥ 10 (R-54); `td.energy.control.state` 1; повторный `-u` ничего не меняет (AC-229, AC-235).

### 5.7 `neutralize.sql`

`UPDATE ir_config_parameter SET value='False' WHERE key IN ('td.energy_control.write_enabled','td.energy_control.automation_enabled','td.energy_control.remote_switching_enabled');` `UPDATE td_source SET write_enabled=false, read_enabled=false WHERE module='energy_control';` `UPDATE td_signal SET write_enabled=false WHERE module='energy_control';` `UPDATE ir_cron SET active=false WHERE id IN (… 3 новых кронов …)`; `UPDATE td_command SET state='cancelled' WHERE origin='energy' AND state IN ('queued','sent');`.

## 6. Крон-задачи и фоновые процессы

Все — `user_id=base.user_root`, `try/except` с `_logger.exception`, без проброса исключения.

| XML-id | Название | Интервал | Метод | Один прогон | Лимит |
|---|---|---|---|---|---|
| `cron_td_energy_control_expire` | Керування: завершення прострочених | 1 мин | `td.energy.action._cron_expire` | R-40 п.12: `prepared` с `token_expires_at < now` → `expired`; `awaiting_second` с `second_expires_at < now` → `expired`; `queued/sent` команда просрочена → `expired`; `executing` дольше `exec_timeout_s + 30` без отчёта → `failed` (`error="Немає підтвердження виконання від збирача: перевірте пристрій вручну"`) и событие `td.energy.event` `kind='control'`; конфиг-действия с `now − finished_at > apply_timeout_s` и `applied=False` → событие «Збирач не застосував конфігурацію v{N}» (однократно) | ≤ 2 с |
| `cron_td_energy_control_plan` | Керування: план дня | 60 мин (`nextcall` hh:05) | `td.energy.schedule.slot._cron_plan` | R-54 для `plan_horizon_days` суток; удаление плановых слотов старше 2 суток | ≤ 3 с |
| `cron_td_energy_control_watch` | Керування: нагляд за рушієм | 1 мин | `td.energy.control.state._cron_watch` | если `automation_enabled` и `heartbeat_at` старше `heartbeat_stale_s·4` — событие `td.energy.event` `level='bad'`, `kind='control'`, `code='CTRL-HEARTBEAT'`, «Рушій автоматики не на зв'язку» (`dedup_min=15`); авторазрешение при восстановлении (`_td_auto_resolve`); события `kind='control'` старше 24 ч → `resolved`; пересчёт `config_etag` (R-43 п.1); `bus.tick('engine')` | ≤ 1 с |

Не действуют при выключенном `td.energy.read_enabled` только `plan` и `watch`; `expire` — всегда.

## 7. HTTP/JSON API

Вызовы ORM-RPC (`orm.call`) — от имени пользователя (методы `@api.model` модели `td.energy.control`, M-35); все ответы — JSON-совместимые dict. HTTP-маршруты — для сборщика (Bearer-токен `td.collector`). Ошибки Odoo — `AccessError`/`UserError`/`ValidationError` с украинским текстом (приведены ниже). Временные поля ответов — ISO UTC (`…Z`), «часы Киева» — `HH:MM`.

| ID | Сигнатура / маршрут | Вход → выход | Ошибки |
|---|---|---|---|
| API-16 | `td.energy.control.get_control()` | → JSON экрана (7.1) | без группы → `AccessError("Немає доступу до Енергетики.")` |
| API-17 | `td.energy.control.prepare(kind, params=None, advice_id=None)` | `kind` — `td.energy.command.kind.code` или ключ интента рекомендации W3 (R-55 п.6); → ответ `prepare` (7.2) | не `manager` → `AccessError("Керувати енергетикою може лише енергетик.")`; неизвестный/неактивный вид → `UserError("Невідома команда: %s.")`; `available=False` → `UserError("Команда «%s» недоступна: %s.")`; `ValidationError` параметров (M-31); `executor in (intent, genset)` и `write_enabled=False` → `UserError("Керування вимкнено: td.energy_control.write_enabled. Зверніться до адміністратора.")` |
| API-18 | `td.energy.control.confirm(token)` | → `{"action_id","state","state_label","needs_second","message","blocked_reason"}` | токен неизвестен → `UserError("Підтвердження не знайдено. Відкрийте діалог знову.")`; чужой токен → `AccessError("Токен належить іншому користувачу.")`; просроченный → `UserError("Час підтвердження минув. Відкрийте діалог знову.")`; жёсткая проверка → действие `blocked`, ответ (без исключения) с `blocked_reason` |
| API-19 | `td.energy.control.confirm_second(action_id)` | → как API-18 | тот же пользователь → `UserError("Друге підтвердження має дати інший енергетик.")`; состояние ≠ `awaiting_second` → `UserError("Дія не очікує другого підтвердження.")`; просрочено → `UserError("Час другого підтвердження минув.")`; не `manager` → `AccessError` |
| API-20 | `td.energy.control.cancel(token)` | → `{"action_id","state":"cancelled"}` (идемпотентно) | чужой токен → `AccessError` |
| API-21 | `td.energy.control.undo(action_id)` | → ответ `prepare` для обратного действия (`origin='undo'`) | `undo_available=False` → `UserError("Скасування недоступне: %s.")` |
| API-22 | `td.energy.control.get_action(action_id)` | → `{"id","name","state","state_label","summary","detail","result_text","error","finished_at","needs_second","checks","collector_checks","undo_available"}` | чужое действие без группы → `AccessError` |
| API-23 | `td.energy.control.get_schedule(day=None)` | `day` `YYYY-MM-DD` (Киев), default сегодня → `{"day","now","rows":[…]}` (R-54 п.8) | — |
| API-24 | `GET /td/energy/automation/config` | Bearer; `If-None-Match` → 200 JSON (7.3) или 304 | 401 `unauthorized`, 403 `forbidden`, 405 `method_not_allowed`, 429 `rate_limited` |
| API-25 | `POST /td/energy/automation/state` | Bearer; тело 7.4 → `{"accepted_actions","accepted_events","rejected":[…],"config_version","config_etag","server_time"}` | 400 `bad_json`/`bad_schema`, 401, 403 `collector_mismatch`, 413 `payload_too_large` (> 256 КБ), 429 |
| API-26 | `td.command.payload` для `energy_control/intent` → `plugin.call(signal, payload)` (7.5) | → `result_data` сборщика | см. 7.5 |
| API-27 | `td.energy.control.get_node_actions(code)` | `code` узла схемы → `[{"code","label","kind","cls","enabled","disabled_reason"}]` (для `QS`, `BESS`; остальные узлы — `[]`) | — |
| API-28 | `td.energy.control.get_journal(limit=None, before_id=None, origin=None)` | → `{"items":[journal…],"more":bool}` (R-56) | — |

### 7.1 Ответ API-16 (ключи и типы; пример — 14:20 макета)

```json
{"ts":"2026-10-18T11:20:03Z","now_local":"14:20",
 "meta":{"role":"manager","can_prepare":true,"can_confirm_b":false,"write_enabled":true,"automation_enabled":true,"remote_switching_enabled":true,
         "limit_kw":760,"contract_kw":800,"refresh_s":30},
 "engine":{"connected":true,"mode":"auto","reason":null,"heartbeat_at":"2026-10-18T11:20:01Z","age_s":2,
           "config_version":17,"applied_version":17,"label":"Контролер ГРЩ і збирач на зв'язку · 14:20","level":"ok"},
 "scenarios":{"on_count":4,"total":6,"items":[
   {"id":1,"code":"peak","title":"Зрізання піку","text":"Тримати імпорт нижче уставки: …","enabled":true,"applied":true,
    "state":"armed","state_kind":"arm","status":"Чергування · запас 402 кВт","chips":["уставка 760 кВт · 95 %","прогноз 15 хв"],
    "params":{"limit_kw":760,"margin_kw":20},"schema":[{"name":"limit_kw","label":"Уставка імпорту","type":"float","min":100,"max":2000,"unit":"кВт"}],
    "can_toggle":true,"pending_action_id":null}]},
 "shed":{"items":[{"id":1,"n":1,"name":"Зарядна станція навантажувачів","how":"відкласти заряд до 30 хв","kw":48,"p_now_kw":13.5,"node_code":"CHARGING","active":true}],
         "sum_kw":174,"never":["аспірація під час роботи верстатів","ІТ і зв'язок","охорона","пожежна автоматика","аварійне освітлення"],
         "never_nodes":["DUST-1","LP-2","LP-3","OFFICE","BOILER"],"can_reorder":true,"limit_kw":760},
 "commands":[{"code":"qs_close","label":"Увімкнути секційний вимикач QS","sub":"секції 1 і 2 разом","cls":"B","resource":"qs","enabled":true,"disabled_reason":null}],
 "pending":[{"id":55,"summary":"Пуск КГУ","prepared_by":"Іваненко І.","second_expires_at":"2026-10-18T11:30:00Z","can_confirm_second":true}],
 "schedule":{"now":14.333,"rows":[{"resource":"bess","name":"BESS","bars":[{"from":7.5,"to":11.0,"label":"розряд · пік","cls":"d","source":"plan"}]}]},
 "journal":[{"id":812,"time":"14:06","what":"Заявка ТО","detail":"PFC-2: ступінь 3 не вмикається","who":"автоматика","result":"створено","result_kind":"info","state":"done","undo_available":false,"awaiting_second":false,"ref":{"model":"maintenance.request","id":48}}],
 "journal_more":false}
```

Правила полей: `engine.level` — `ok` (связь и режим `auto`), `warn` (`hold`/`off`), `bad` (нет связи); `engine.label` — по UI-13; `scenarios.items[].status` — R-43 п.5; `pending` — только действия `awaiting_second`, видимые `manager`; `commands[].enabled=false` + `disabled_reason` («Немає прав: потрібна роль «Енергетик»», «Керування вимкнено адміністратором», «Команда недоступна: …»); `shed.never` — D-26; без стоимости; размер ответа ≤ 40 КБ (ТП-10).

### 7.2 Ответ API-17 `prepare`

```json
{"action_id":55,"token":"Zm9v…","ttl_s":60,"kind":"qs_close","cls":"B","title":"Увімкнути секційний вимикач QS?",
 "text":"Секції 1 і 2 працюватимуть разом. Генерація СЕС піде на навантаження секції 1, експорт через T2 припиниться.",
 "sub":"секції 1 і 2 разом",
 "checks":[{"code":"ats_parallel_lock","label":"Блокування паралельної роботи T1 і T2 від АВР — увімкнено","state":"ok","hard":true,"detail":""},
           {"code":"qs_current_ok","label":"Струм через QS після вмикання ≈ 40 А з 1600 А","state":"ok","hard":true,"detail":"40 А ≤ 1280 А"}],
 "blocked":false,"blocked_reason":null,"needs_second":true,"confirm_label":"Підтвердити (1/2)","disabled_reason":null}
```

`checks[].label` — шаблон `td.energy.interlock.name` с подставленными значениями; `state` ∈ `ok|fail|unknown`; `blocked` — есть `hard` с `state='fail'` или (`hard`, `fail_closed`, `unknown`); `blocked_reason` — первая такая проверка; `confirm_label` — «Виконати» (класс A или `chief`) / «Підтвердити (1/2)»; повторный `prepare` того же пользователя с тем же `kind` и `params` в течение 5 с возвращает ту же запись с новым токеном без создания дубля (R-40 п.1).

### 7.3 Ответ API-24 `GET /td/energy/automation/config` (контракт сборщика; C-39)

```json
{"schema":1,"config_version":17,"etag":"9f2c…","server_time":"2026-10-18T11:20:03Z","tz":"Europe/Kyiv",
 "flags":{"automation_enabled":true,"write_enabled":true,"remote_switching_enabled":true},
 "engine":{"tick_s":2,"config_poll_s":10,"stale_hold_s":30,"min_write_interval_s":10,"max_writes_per_min":30,
           "exec_timeout_s":60,"step_timeout_s":8,"verify_timeout_s":30,"shed_restore_step_s":20},
 "plant":{"contract_kw":800,"pv_kwp":920,"bess_kwh":387,"bess_max_kw":200,"bess_reserve_pct":30,"cos_phi_target":0.95,
          "genset_kw":507,"chp_kw":800,"qs_rating_a":1600},
 "scenarios":{"peak":{"enabled":true,"params":{"limit_kw":760,"…":0}},"self":{"enabled":false,"params":{}},"pfc":{"enabled":true,"params":{"cos_target":0.95}},
              "night":{"enabled":true,"params":{"from":"23:00","to":"06:30","days":[1,2,3,4,5,6,7],"vent_mode":"VEL","day_vent_mode":"VE","vent_pct":30,"light_scene_number":1,"light_scene_day_number":2,"heat_setpoint_c":16.0}},
              "backup":{"enabled":true,"params":{}},"chp":{"enabled":false,"params":{}}},
 "shed":[{"id":1,"seq":1,"node":"CHARGING","action":"defer","param":30,"kw":48,"critical":false,"signal":"energy_control/shed/CHARGING/limit_pct","condition":"none","condition_value":null}],
 "never_shed":["DUST-1","LP-2","LP-3","OFFICE","BOILER","EF-ELEC","EF-CHG"],
 "slots":[{"id":9,"resource":"chp","date":null,"weekdays":"1111100","from":16.0,"to":19.0,"mode":"run","setpoint_kw":null}],
 "tariff":{"zones":[{"from":0.0,"to":7.0,"price":3.4},{"from":7.0,"to":23.0,"price":8.4},{"from":23.0,"to":24.0,"price":3.4}],"currency":"UAH"},
 "bms":{"night":{"vent":[{"unit":"RV-01","mode_signal":"ventilation/units/RV-01/mode","sp_night_signal":"ventilation/units/RV-01/setpoint_night_c"}],
                 "light":[{"group":"LT-01","scene_signal":"lighting/groups/LT-01/scene","aisle":false}]},
        "vent_eco":{"vent":[{"unit":"RV-01","mode_signal":"ventilation/units/RV-01/mode"}]},
        "light_break":{"light":[{"group":"LT-01","scene_signal":"lighting/groups/LT-01/scene","aisle":false}]}},
 "signals":{"qs_cmd":"energy_control/qs/cmd","qs_ack":"energy_control/qs/ack","qs_state":"energy/cells/QS/state","ats_lock":"energy_control/ats/parallel_lock",
            "pfc_mode":"energy_control/pfc/mode","pfc_cos":"energy_control/pfc/cos_target","bess_mode":"energy_control/bess/mode","bess_sp":"energy_control/bess/setpoint_kw",
            "bess_until":"energy_control/bess/until_soc","bess_valid":"energy_control/bess/valid_s","bess_ack":"energy_control/bess/ack","bess_temp":"energy_control/bess/temp_c",
            "chp_cmd":"energy_control/chp/cmd","chp_ack":"energy_control/chp/ack","chp_permit":"energy_control/chp/permit","chp_gas":"energy_control/chp/gas_bar",
            "air_sp":"energy_control/air/setpoint_bar","air_min":"energy_control/air/min_consumer_bar","pv_limit":"energy_control/pv/limit_pct",
            "shed_valid":"energy_control/shed/valid_s","remote":"energy_control/ctl/remote","ctl_hb":"energy_control/ctl/heartbeat",
            "auto_hb":"energy_control/auto/heartbeat"},
 "inputs":{"p_total":"energy/totals/p_now","air_bar":"equipment/COMPRESSOR/pressure_bar","grid_kw":"infra/totals/grid_kw","export_kw":"infra/totals/export_kw","pv_kw":"infra/totals/pv_now","bess_kw":"infra/totals/bess_kw",
           "bess_soc":"infra/totals/bess_soc","bess_state":"infra/bess/state","chp_state":"infra/chp/state","chp_kw":"infra/totals/chp_kw","chp_hours":"infra/chp/hours",
           "ats_pos":"infra/ats/position","src1_ok":"infra/ats/src1_ok","s1_p":"energy/sections/S1/p_kw","s2_p":"energy/sections/S2/p_kw",
           "pfc1_fault":"energy/cells/PFC-1/fault_step","pfc2_fault":"energy/cells/PFC-2/fault_step","fire_state":"fire/panel/state"},
 "interlocks":{"qs_current_ok":{"hard":true,"fail_closed":true,"params":{"rating_a":1600,"max_ratio":0.8,"cos_phi":0.95}}},
 "limits":{"bess_kw_max":200,"pv_limit_min_pct":10,"air_bar_min":5.0,"air_bar_max":8.5}}
```

Правила: (1) **Ключи `schema`, `config_version`, `etag`, `server_time` не входят в канонический JSON для ETag** (R-43 п.2); (2) значения `flags.*` читаются из `ir.config_parameter` при каждом запросе; (3) `signals`/`inputs` — логические имена → коды сигналов; плагин не содержит жёстко закодированных кодов (кроме названий логических ключей); (4) `bms` строится из `td.bms.hvac.unit` (`kind='roofvent'`, `mode_signal_id`, `sp_night_signal_id`) и `td.bms.light.group` (`scene_signal_id`; `aisle = (fixture_kind == 'highbay_rack')`; группы `aisle` не диммируются и не выключаются сценой «Перерва»); если у `td_bms` пустые сигналы — соответствующие массивы пусты (ночной режим → состояние `warn` «немає цілей BMS»); (5) `limits` — *границы, которые Odoo может только сужать* относительно констант кода сборщика (R-44 п.6); (6) размер ответа ≤ 64 КБ; (7) ответ не содержит стоимости, токенов, паролей.

### 7.4 Тело API-25 `POST /td/energy/automation/state` (раз в 10 с или немедленно при смене действия)

```json
{"collector":"COL-1","config_version_applied":17,"sent_at":"2026-10-18T11:20:03Z",
 "engine":{"mode":"auto","reason":null,"started_at":"2026-10-18T06:00:00Z","ticks":19401,"tick_ms_p95":14,"writes_last_min":2,
           "controller_remote":true},
 "scenarios":{"peak":{"state":"armed","ts":"…","facts":{"margin_kw":402,"proj_kw":358,"grid_kw":356}},
              "self":{"state":"off","ts":"…","facts":{}},
              "pfc":{"state":"warn","ts":"…","facts":{"fault":"PFC-2 ступінь 3"}}},
 "actions":[{"id":55,"idem":"3f…","state":"done","step":4,"steps_total":4,"ts":"…","result":"BESS: заряд 50 кВт до 16:00 (valid_s 5700)","error":null,
             "checks":[{"code":"bess_soc_lt_limit","state":"ok","hard":true,"detail":"82 % < 95 %"}]}],
 "events":[{"event_id":"b9…(uuid4 hex)","ts":"…","scenario":"peak","kind":"auto_step","text":"BESS · розряд 62 кВт","signal":"energy_control/bess/mode","value":2,"result":"виконано"}]}
```

Ответ: `accepted_actions` — количество применённых элементов `actions[]` (состояние действия только «вперёд» в порядке `executing < done|failed|blocked`; повторный отчёт того же состояния — идемпотентный, без эффектов); `accepted_events` — новые `event_id` (повторные игнорируются); `rejected` — `[{"id" | "event_id", "reason": "unknown_action|already_final|bad_state|duplicate"}]`; `config_version`, `config_etag` — для немедленного `GET config`, когда `etag` отличается от кэша плагина. Ограничения: `actions` ≤ 100, `events` ≤ 200 за запрос, тело ≤ 256 КБ. Обновляет: `td.energy.control.state` (`heartbeat_at`, `engine_mode`, `engine_info`, `applied_version = max(applied_version, config_version_applied)`), `td.energy.scenario._td_engine_update`, `td.energy.action._td_on_engine`/`_td_log_auto`, `bus.tick('engine'|'scenario'|'action')`.

### 7.5 API-26: интент (`td.command.payload`) и результат (`result_data`)

Odoo создаёт **одну** `td.command` на действие: `signal_id = energy_control/intent`, `payload`, `value=0`, `origin='energy'`, `expires_at = now + command_ttl_s`, `energy_action_id`.

```json
{"v":1,"action_id":55,"idem":"3f9a…(sha1)","kind":"bess_charge","cls":"A","params":{"power_kw":50,"until":"16:00","soc_limit_pct":95},
 "requested_by":"ivanenko","requested_at":"2026-10-18T11:20:30Z","expires_at":"2026-10-18T11:22:30Z","tz":"Europe/Kyiv","limits":{"bess_kw_max":200}}
```

`kind` ∈ `qs_close, qs_open, bess_charge, bess_discharge, bess_stop, chp_start, chp_stop, light_break, light_restore, vent_eco, vent_restore, air_setpoint` (исполнители `intent`); остальные виды интентом не передаются. Схема и границы `params` — R-42 (сборщик проверяет независимо от Odoo; JSON-схема `intent.schema.json` в пакете плагина). Ядро сборщика (`CommandLoop`) вызывает `plugin.call()` (`CALL_TIMEOUT_S = 10 с`): плагин **только принимает и ставит в очередь** интент и возвращает `result_data` ≤ 64 КБ:

```json
{"accepted":true,"run_id":"r-3f9a","state":"executing","checks":[{"code":"controller_remote","state":"ok","detail":"remote=1"}]}
```

либо отказ без выполнения: `{"accepted":false,"state":"blocked","reason":"Блокування: ats_parallel_lock — не виконано (lock=0)","checks":[…]}`, `{"accepted":false,"state":"rejected","reason":"unknown kind"|"bad params: …"|"expired"|"busy: bess"}`; повторная доставка того же `idem` — ответ из сохранённого результата (`"duplicate":true`) без повторного выполнения (R-52 п.6). Итоговое состояние выполнения (`done|failed`) приходит отдельно через API-25 `actions[]`. `td.command` получает `done` (транспорт принят), `failed` — только если плагин выбросил исключение/тайм-аут `call()`.

### 7.6 Формат записи журнала (API-28)

`{"id","time":"HH:MM" (Киев; для старше суток "DD.MM HH:MM"),"what","detail","who","result","result_kind":"ok|info|bad|muted","state","undo_available","awaiting_second","ref":{"model","id"}|null}`; `what`/`detail`/`who`/`result` — D-19; сортировка по времени убывания; ключи стоимости отсутствуют.

## 8. Сервисная часть

### 8.1 Плагин сборщика `td_collector_energy` (владелец C; E-03, E-05, FR-55…FR-57)

**Место в сборщике.** `td_collector_energy` — Python-пакет-плагин в группе entry points `factory3d_collector.plugins` (как `f3d_collector_bms`, `f3d_collector_yard`): тип источника `energy_ctl`, класс `EnergyCtlPlugin(SourcePlugin)`, `push_mode = True`. Единственный источник этого типа — `ENERGY-CTL` (разд. 5.6). Плагин объединяет **цикл автоматики** (6 сценариев, R-44…R-51) и **исполнителя интентов** оператора (R-52); пишет в устройства через другие источники сборщика (Modbus `MB-U73-SWB-CMD`, BMS), используя те же плагины протоколов, флаги записи и allowlist. PLC сможет перехватить автоматику позже через тот же контракт конфига/уставок/расписания (E-05): плагин — лишь одна из реализаций API-24/25.

#### 8.1.1 Структура пакета

```
services/collector_plugins/td_collector_energy/
├── pyproject.toml            name `td-collector-energy`, requires-python >=3.12, зависимостей нет (aiohttp, jsonschema — из ядра/теста),
│                             [project.entry-points."factory3d_collector.plugins"] energy_ctl = "td_collector_energy:EnergyCtlPlugin"
├── README.md, CHANGELOG.md
├── td_collector_energy/
│   ├── __init__.py           экспорт EnergyCtlPlugin
│   ├── plugin.py             EnergyCtlPlugin: validate/connect/subscribe/call/health/disconnect
│   ├── config.py             загрузка API-24 (ETag, кэш, проверка схемы, дифф версий), класс Config (frozen dataclass)
│   ├── inputs.py             Inputs: снимок живых значений из ctx.live со свежестью; производные (прогноз 15 мин, скользящие окна)
│   ├── engine.py             Engine: цикл, режимы off/hold/auto, арбитраж ресурсов, перекрытие (override)
│   ├── actuator.py           Actuator: запись «только при изменении», мин. интервал, предохранитель частоты, чтение обратно
│   ├── scenarios/{__init__,common,peak,selfcons,pfc,night,backup,chp}.py   чистые функции step(...) по R-45…R-50
│   ├── interlocks.py         реестр CHECKS (R-41), оценка по Inputs
│   ├── intents.py            kind → шаги/проверки/границы params (R-42), JSON-схемы
│   ├── executor.py           Executor: очередь интентов, шаги, верификация, fail-safe, идемпотентность (R-52)
│   ├── store.py              атомарное сохранение состояния (JSON), восстановление после рестарта
│   ├── reporter.py           пакетный POST API-25, буфер при сбое, дедуп событий
│   ├── timeutil.py           Europe/Kyiv, окна через полночь, DST
│   └── schemas/{params.energy_ctl.json, address.energy_ctl.json, config.schema.json, intent.schema.json}
└── tests/                    разд. 13.1 (UT-PY), `tests/stand/test_tk_energy.py` (ТК)
```

#### 8.1.2 Расширение ядра сборщика (C-40; аддитивное, обратно совместимое; владелец C)

| Файл | Изменение |
|---|---|
| `collector/core/live.py` (новый) | `LiveCache`: `update(readings: Iterable[Reading])`, `get(code) -> Reading \| None`, `age_s(code, now) -> float \| None`, `snapshot(codes) -> dict`, `note_write(code, value, ts)`, `last_write(code)`; потокобезопасность не нужна (один event loop); память — строка на код, без истории |
| `collector/core/scheduler.py` | после `apply_signal_scale` в цикле опроса и в `Emitter.emit` — вызов `live.update(...)` (если `live` передан; `Scheduler`/`Emitter` получают необязательный аргумент `live=None`) |
| `collector/core/commands.py` | новый `CommandLoop.read_now(code) -> Reading \| None`: разовое чтение сигнала через `plugin.poll([signal])` с масштабом ядра и обновлением `LiveCache` (таймаут `call_timeout_s`; без записи в буфер); новый `CommandLoop.write_direct(code, value=None, text=None, *, expires_at=None) -> str`: те же проверки, что `_execute` (найти сигнал; `source.write_enabled`; `signal.write_enabled`; `registry.write_enabled`; `settings.write_enabled`; `expires_at`), вызов `plugin.write()` с таймаутом `call_timeout_s`; ошибки — `WriteRefused(reason)` (новый класс в `core/errors.py`) или исключение плагина; **без** записи в буфер результатов |
| `collector/plugins/base.py` | `PluginContext` получает необязательные поля `live: LiveCache \| None = None`, `write_signal: Callable[..., Awaitable[str]] \| None = None` (= `write_direct`), `read_signal: Callable[[str], Awaitable[Reading \| None]] \| None = None` (= `read_now`), `odoo: OdooClient \| None = None`, `clock: Clock \| None = None`, `state_dir: Path \| None = None` (каталог `settings.state_file`); старые плагины не меняются |
| `collector/core/app.py` | `Collector` создаёт `LiveCache`, передаёт в `Scheduler`/`Emitter`; `_make_ctx` заполняет новые поля |
| `collector/core/odoo_client.py` | если общего `request(method, path, …)` недостаточно — тонкие методы `automation_config(etag)` и `automation_state(body)` (те же заголовки Bearer, `If-None-Match`, таймауты, `OdooError`) |
| `requirements-extra.txt` | строка `td-collector-energy @ file:///opt/plugins/td_collector_energy` |

Тесты ядра: `tests/unit/test_live.py`, `test_ctx_extension.py`, `test_write_direct.py` (AC-236…AC-238); существующие тесты ядра остаются зелёными.

#### 8.1.3 Жизненный цикл плагина

- `validate(source)`: `params` по `params.energy_ctl.json` (`engine.tick_s` 1…10, `engine.config_poll_s` 5…60); единственный экземпляр: второй `connect()` → `ConnectError("energy_ctl: дублікат джерела")`.
- `connect()`: загружает `Store` (состояние с диска; отбрасывает старше 7 суток), первую конфигурацию API-24 (из кэша `Store`, если Odoo недоступен ≤ 7 суток; иначе — состояние `off`, `health=online` без действий; повторные попытки с бэкоффом 1→60 с); сетевого соединения с устройствами не открывает (это делают их плагины).
- `subscribe()`: создаёт задачи `_config_loop` (опрос API-24 раз в `config_poll_s`, `If-None-Match`), `_engine_loop` (R-44; период `tick_s`), `_report_loop` (API-25 раз в 10 с или немедленно при смене состояния действия), `_heartbeat_loop` (раз в 10 с `ctx.emit(Reading("energy_control/auto/heartbeat", value=ticks))` и состояний сценариев при изменении). Возвращается сразу.
- `call(signal, payload)`: только для `energy_control/intent`; проверки `v`, схемы, `expires_at`, `idem` (повтор → сохранённый результат), жёстких блокировок (R-41) **синхронно**; ставит в очередь `Executor`; возвращает `result_data` API-26 за ≤ 1 с (никогда не ждёт выполнения шагов). Неизвестный сигнал → `NotSupported`.
- `write()` — `NotSupported`. `health()` — `online`, если жив `_engine_loop` (тик не старше `3·tick_s`) и конфиг валиден; иначе `error` с причиной.
- `disconnect()`: останавливает задачи; **не** выполняет записей в устройства (безопасное состояние обеспечивают сторожевые таймеры контроллера, R-53 №7); сохраняет `Store`.

#### 8.1.4 Логирование, метрики, окружение

Логгер `collector.plugin.energy_ctl.ENERGY-CTL`; уровни: `INFO` — смена режима движка, смена `config_version`, запуск/завершение интента, смена ступени сценария; `WARNING` — блокировки, отказы устройства, несвежие входы; `DEBUG` — тик. Токены/секреты не печатаются. В `Health.stats` — `ticks`, `tick_ms_p95`, `writes_last_min`, `intents_total`, `blocked_total`, `config_version`, `mode`. Переменные окружения сборщика (существующие): `F3D_WRITE_ENABLED` (предохранитель 5), `F3D_COMMANDS_POLL_S` (стенд 2 с вместо 5), `F3D_STATE_FILE` (каталог состояния плагина `td_energy_ctl.json`).

### 8.2 Эмулятор `iot_sim`: окно управления контроллера ГРЩ и реакции моделей (владелец C; FR-59, R-59, C-47)

Карта регистров — ДОПУЩЕНИЕ для эмулятора (A-45); на объекте действует документ контроллера, изменения только в `address` сигналов (данные), код плагина не меняется. Адреса, типы и семантика регистров — таблица разд. 5.6 (unit 73, HR 200…291, u16, FC3/FC6).

| Файл | Изменение |
|---|---|
| `iot_sim/protocols/modbus_maps/swbctl.py` (новый) | `UNIT = 73`; `build(ctx)` добавляет HR 200…291 в `ctx.unit(73, "SWB-CTRL")`: чтение из флагов мира (`ctl.*`) и сигналов; запись через `set`-колбэки; `ctx.write_accept == False` → `ModbusError(4)`; значения вне границ → `ModbusError(3)`; команды (QS, КГУ) пишут `ctx.command(UNIT, "QS cmd = 2")` в события мира; регистры `cmd` самоочищаются на следующем тике |
| `iot_sim/protocols/modbus_maps/__init__.py` | `swbctl` добавляется в список `mod` в `build_all` (перед `bind_catalog`, собственные карты имеют приоритет; HR 100…123 остаются за `bind_catalog` W1) |
| `iot_sim/models/swb.py` | потребляет флаги: `qs_closed` (команда), `pfc_mode`, `pfc_cos_target` (вместо только `settings.pfc_cos_target`); QS: команда `2` (замкнуть) выполняется, если `ats_parallel_lock == 1` и нет острова, иначе `ack = 2`; `1` (разомкнуть) — всегда; heartbeat `ctl/heartbeat` (+1 за симулированную секунду); `ctl/remote` (флаг `ctl_remote`, default 1): при `0` все команды игнорируются с `ack = 2` |
| `iot_sim/models/bess.py` | режимы `bess_mode`: `0` авто (существующее поведение; флаг `bess_auto_idle` → 0 кВт), `1` принудительный заряд `+min(setpoint, 200)` до `until_soc` или SOC 100, `2` принудительный разряд `−min(setpoint, 200)` пока SOC > `max(until_soc, reserve_pct)`, `3` удержание 0 кВт; сторожевой таймер `valid_s` (уменьшается на `dt`; в 0 → режим `0`, `remaining_s` = остаток); отказ `ack = 2` для разряда при SOC ≤ `reserve_pct` (30) или температуре шкафа > 40 °C; `temp_c = 25 + 0,05·\|P\|` |
| `iot_sim/models/chp.py` | `chp/cmd`: `1` → `chp_run = True`, если `permit == 1` и `gas_bar ≥ 1,5`, иначе `ack = 2`; `2` → `chp_run = False`; длительность запуска — флаг `chp_start_s` (default 60; D-33); `gas_bar` — флаг (default 2,10; сценарий `chp_no_gas` → 0,80); существующий HR 40007 остаётся источником тех же флагов |
| `iot_sim/models/compressor.py` | номинальное давление = `air_setpoint_bar − 0,19` (default уставка 7,00 → 6,81, поведение W0 сохранено); `min_consumer_bar` = 6,20 (const-регистр) |
| `iot_sim/models/pv.py` | мощность каждого инвертора умножается на `pv_limit_pct / 100` (default 100) |
| `iot_sim/models/meter.py` | `consumer_p(world, code)` умножается на `shed_factor(code) = limit_pct / 100` (default 1); сумма нагрузки добавляет флаг `extra_load_kw` (может быть отрицательным, лишь ≥ `−load`); при `qs_closed` мощности вводов Q1 и Q2 выравниваются `(P1 + P2) / 2`; сторожевой таймер сброса `shed_valid_s` (в 0 → все лимиты и `pv_limit_pct` возвращаются в 100) |
| `catalog/signals.csv`, `td_iot_sim/data/td_sim_signal.csv` | +28 строк «новий» для сигналов `MB-U73-SWB-CMD` (разд. 5.6) с номерами `n` начиная со следующего свободного; `bind_catalog` не конфликтует с `swbctl.py` |
| `td_iot_sim/data/td_sim_scenario.xml` + `catalog/…` | сценарии: `peak_load` `{extra_kw, duration_s}` (добавляет `extra_load_kw`), `export_demo` `{export_kw}` (BESS авто в режиме удержания 0 кВт, нагрузка подгоняется так, чтобы экспорт = `export_kw`: `load_eff = gen − export_kw` при `gen > export_kw`), `ctl_local` (`ctl_remote = 0`), `chp_no_gas` (`gas_bar = 0,80`) |

Тесты: `tests/unit/test_swbctl.py` (регистры, границы, `write_accept`, самоочистка `cmd`, heartbeat), `tests/unit/test_control_models.py` (реакции BESS/КГУ/QS/PFC/воздуха/PV/сброса, сторожевые таймеры, `peak_load`, `export_demo`). Стенд: пакетные сценарии ТК-20…ТК-27 (разд. 13.2).

### 8.3 Тест ДГУ: адаптер ADP-12 в `td_genset_factory3d` (FR-66, R-67; владелец A)

Адаптер `adapters/td_genset.py` (единственное место доступа к `td_genset`, W1 R-14…R-16) получает `start_test(gen, mode, user) -> dict` (**ADP-12**): (1) `mode == 'idle'` (W2 — только без нагрузки; `load` — Q-29); (2) `gen.sudo()._test_start('idle', user)` (метод `td_genset` `genset_scheduler.py`; группа `td_genset.group_tech` проверяется `td_energy_control` через права «Енергетик»/«Головний енергетик» — в `td_genset` вызов идёт с `sudo()`, `_td_check_group` пропускает `env.su`); (3) возвращает `{"accepted": True, "minutes": <config.test_minutes>, "test_end": "<iso UTC>", "ref": {"model": "td.genset", "id": gen.id}}`; ошибки `UserError` из `td_genset` («Тест уже йде.», «Оберіть варіант тесту…») адаптер пробрасывает без изменений. Дополнительно `test_facts(gen) -> dict` (`fuel_pct`, `running`, `test_running` (`gen.test_end`), `island` (`not mains_ok`), `coolant_c`) для проверок `genset_fuel`, `genset_heater` (`coolant_c ≥ 30` °C), `genset_idle`. Доступ из `td_energy_control` — мягкий: `tools/genset_link.py` (`importlib.import_module("odoo.addons.td_genset_factory3d.adapters.td_genset")` при наличии модуля в `ir.module.module` со состоянием `installed`; иначе вид `genset_test` имеет `available=False`, причина «Не встановлено міст td_genset_factory3d»). Тест адаптера — `td_genset_factory3d/tests/test_adp12.py` (AC-275, AC-276; AC-277 — исполнитель в `td_energy_control`). `td_genset` не меняется.

### 8.4 «Енергетика в 3D»: мост `td_energy_viewer3d` и расширение `td_viewer3d` (владелец D; FR-62…FR-65, FR-70, C-44, C-45)

**Решение (A-52).** Слой — **отдельный мост-модуль** `td_energy_viewer3d` (`depends`: `td_energy`, `td_viewer3d`; `auto_install: True`; LGPL-3), по образцу `td_constructor_viewer3d`: Python-провайдер (duck typing, контракт `td_viewer3d` M-01) отдаёт **аддитивный** ключ `energy.layer` в payload (`meta.schema` остаётся `"1.1"`: ключ вложен в раздел `energy`, клиент без моста его игнорирует), JS-расширение рисует слой в ядре просмотрщика. Обоснование: `td_energy` не зависит от `td_viewer3d`, а JS-импорт `@td_viewer3d/viewer/core` в `td_energy` сломал бы бандл без просмотрщика; существующий провайдер `td.viewer.provider.energy` (seq 100) не меняется. Ядро просмотрщика для этого получает минимальные аддитивные точки расширения (**VX-01…VX-05**, `td_viewer3d` R-26); без расширений поведение ядра не меняется.

#### 8.4.1 `td_viewer3d` R-26: расширение ядра (VX-01…VX-05; FR-70; AC-278…AC-281)

Расширяет R-25 (`registerViewerExtension(ext)`): в `ext` появляются **необязательные** члены (отсутствует — ничего не делает; исключение расширения логируется и не ломает ядро и другие расширения):

| ID | Член `ext` | Контракт |
|---|---|---|
| VX-01 | `colorModes: [{key, label, legend}]` | ядро добавляет радио-кнопки в группу «Розфарбування» (`name="cmode"`, значение `key`, подпись `label`), сохраняет `colorMode`; `getState().mode` возвращает `key`; `applyParams({mode})` принимает ключи расширений |
| VX-02 | `modeColor(mode, root, D) → THREE.Color \| null` | вызывается из `modeColor(root)` ядра, когда `colorMode` — ключ расширения; `null` — без подсветки; результат смешивается как у встроенных режимов (`paint`, коэффициент 0,45) |
| VX-03 | `applyData(api, D, info)` | `api` — как в R-25; `info = {reason: "load"\|"patch"\|"snapshot"\|"now", keys: Set<string>}`; вызывается после `setData`, после каждого `applyPatch` с непустым патчем и после возврата «Зараз»/снимка; ядро после вызова запускает `repaintAll()`, если `colorMode` — режим расширения |
| VX-04 | `cardBlocks(code, D, api) → string[]` | список HTML-фрагментов, которые ядро добавляет в конец карточки выбранного объекта (после `energyHtml`); экранирование — ответственность расширения (`esc`); пустой массив — ничего |
| VX-05 | `onAction(api, action, arg, el)` и `api.openAction(action) → boolean` | элементы с `data-ext="<id>:<action>:<arg>"` в карточке/панели делегируются расширению с `id`; `api.openAction(act)` вызывает `opts.onOpenAction(act)` (`viewer_action.js`: `this.action.doAction(act)`); в режиме киоска `opts.onOpenAction` не задан → `false` |

Также `api` расширяется полями `select(code)`, `focusOn(obj)`, `codeRoot(code)` (существуют) и `labelsRoot` (контейнер меток) — без изменений поведения. Файлы: `td_viewer3d/static/src/viewer/core.js` (вставки ≤ 90 строк), `static/src/action/viewer_action.js` (`onOpenAction`), тесты `static/tests/hoot/extension_energy.test.js`, `tests/test_r26_extension.py`. Ограничения: `rjsmin` — без вложенных шаблонных литералов в изменяемых местах; `dist/viewer` не обновляется.

#### 8.4.2 Payload `energy.layer` (R-57; M-41)

```json
{"layer":{"schema":1,"thresholds":{"warn_pct":80,"alarm_pct":100},
  "nodes":[{"code":"BW-2","scene":"BW-2","kind":"line","name":"ШР-2","state":"ok","load":0.30,"i_a":192,"p_kw":124.0,"rating_a":630,
            "card":true,"alarms":0,"worst":null,"title":null},
           {"code":"C2","scene":"CABLES","kind":"line","name":"C2","state":"alarm","load":null,"i_a":null,"p_kw":128.0,"rating_a":null,
            "card":true,"alarms":1,"worst":"bad","title":"Лічильник PM-QF-C2 не на зв'язку"}],
  "alarms":[{"id":212,"node":"C2","scene":"CABLES","level":"bad","title":"Лічильник PM-QF-C2 не на зв'язку","time":"13:47","state":"active"}],
  "summary":{"alarm":1,"warn":2,"gen":1,"off":3}}}
```

Правила: `nodes` — узлы `sld_show=True` (W1 R-26; ≈ 21) видов `line`, `transformer`, `cell` (feeder/cable/incomer/coupler/pfc), `generator`, `storage`, `ats`, `section`; `state` = `td.energy.node.sld_state` (`ok|warn|alarm|off|gen`, **та же логика и пороги `td.energy.load_warn_pct/_alarm_pct`, что и в Пульте**); `load` — доля 0…∞ (`p_now / номинал`, W1 R-26) или `null`; `scene` — код объекта сцены: `equipment_id.td_code`, иначе `node.code`; для кабельных линий `C1`, `C2` — `CABLES` (единственный объект сцены; состояние объекта = худшее среди узлов с тем же `scene`); `scene=null`, если кода нет среди известных кодов сцены (множество из `ctx["static"]` — `model_static.json` `td_viewer3d`: `energy.lines|transformers|cells`, `equipment`, `zones`; воркер D берёт существующий загрузчик статики `td_viewer3d.tools.payload`; если множество получить невозможно — `scene = equipment.td_code or node.code` без проверки, A-53) — узел остаётся в списке (карточка доступна), но не раскрашивается и не имеет маркера; `alarms[]` — открытые `td.energy.event` (`state in ('active','acked')`, `level in ('warn','bad')`, `node_id`), ≤ `marker_limit` (40), сортировка `bad` → `warn`, далее по времени; `title` ≤ 80 символов; `time` — Киев `HH:MM`; `card` — `false` в киоске и без группы; ключи стоимости и имена пользователей (`acked_by`, `assigned_user_id`) **не отдаются**; для `ctx["kiosk"]` — `title` без технических деталей диагностики. Размер `layer` ≤ 12 КБ, построение ≤ 150 мс (ТП-11). Дельта (`_f3d_viewer_delta`) — **полная замена** `layer` (списки заменяются целиком по `deep_merge`).

#### 8.4.3 Клиент моста (UI-23…UI-27)

`registerViewerExtension({colorModes, modeColor, applyData, cardBlocks, onAction})` в `static/src/layer/energy_layer.js`:

| ID | Компонент | Поведение |
|---|---|---|
| UI-23 | `EnergyLayerExtension` | Держит `state = {byScene: Map, alarms, version}` из `D.energy.layer`; `applyData` обновляет карту и маркеры (только если `info.keys` содержит `energy`); без `D.energy.layer` (старый сервер) — расширение неактивно, режим не показывается |
| UI-24 | `StateColors` | Режим `td_energy` «Електромережа: стан вузлів» (легенда: «норма», «увага ≥ {warn_pct} %», «тривога ≥ {alarm_pct} % / немає даних», «генерує/працює», «вимкнено/резерв»); `modeColor`: `ok` → `C_OK` (`#27ae60`), `warn` → `C_WARN` (`#f39c12`), `alarm` → `C_BAD` (`#e74c3c`), `gen` → янтарный (`#b45309`), `off` → серый (`#9ca3af`); кодирование не только цветом: в карточке — текстовый чип состояния |
| UI-25 | `AlarmMarkers` | Для каждой записи `alarms[]` со `scene` — спрайт (канва 64 × 64: круг `--bad`/`--warn`, знак «!») над самой высокой точкой `codeRoot(scene)` (`Box3`), `renderOrder` выше сцены, масштаб постоянный в пикселях; пульсация (`reduceMotion` отключает); клик по маркеру — `api.select(scene)`; подсказка `title` + время; ≤ `marker_limit`; снятие/перестроение при `applyData`; `dispose` геометрии/текстур; скрыт, когда `show_markers=false` или слой `energy` выключен |
| UI-26 | `NodeBlock` | `cardBlocks(code)`: блок «Енергетика»: чип состояния («Норма», «Увага», «Тривога», «Генерує», «Вимкнено»), `P {p_kw} кВт`, `{i_a} А · {load%}` (если есть), перечень тревог узла (≤ 3) и кнопка «Відкрити картку вузла» (`data-ext="td_energy:open_card:<node code>"`) — только если `card=true` и разрешён `openAction` (не киоск); `onAction` → `api.openAction({type:"ir.actions.client",tag:"td_energy.node_card",name:<code>,params:{code}})` (V-23 W1) |
| UI-27 | `ViewerLinks` | Регистрирует `registry.category("td_energy.viewer_links").add("default", {open})`, где `open({code})` вызывает `orm.call("td.energy.node","action_td_open_3d",[code\|\|null])` и `action.doAction(result)`; без модуля `td_viewer3d` запись не регистрируется (мост `auto_install` не устанавливается) |

#### 8.4.4 «Відкрити в 3D» и подсветка узла (R-58; FR-64)

`td.energy.node.action_td_open_3d(code=None)` возвращает `{"type":"ir.actions.client","tag":"f3d_viewer.action","name":"Завод 3D","target":"current","params":{"layers":<td.energy_viewer3d.layers>,"mode":"td_energy","tab":"energy","code":<scene|null>,"td_energy_node":<code|null>}}`: `code` узла преобразуется в `scene` по правилам 8.4.2; неизвестный `code` → `UserError("Вузол %s не знайдено.")`; узел без `scene` → `params.code = null` и сообщение-предупреждение в клиенте «Для вузла {code} немає об'єкта в 3D; відкрито шар «Енергетика»». Просмотрщик (`applyParams`): `layers` → `mode` → `tab` → `code` (`select(ensureCode(code))` + `focusOn`); выбранный узел получает жёлтую обводку ядра (`C_SEL`) и блок UI-26; маркер выбранного узла пульсирует. Точки входа в Odoo: (1) Пульт, «Відкрити в 3D» (UI-01 W1) → `viewerLinks.default.open({})`; (2) панель узла схемы и карточка узла, «Показати в 3D» → `open({code})`; (3) мобильный «Де це в 3D» → `open({code})`; (4) меню «Енергетика в 3D» (V-47). Назад: в карточке просмотрщика (UI-26) — «Відкрити картку вузла»; из карточки — крошки W1.

## 9. Алгоритмы и правила

### R-39 Классы команд и права (E-06, A-39; FR-53)

1. Класс задаёт `td.energy.command.kind.cls` (M-31, разд. 5.3), пользователь его не меняет. **Класс A** (роль «Енергетик»): заряд BESS, остановка BESS, сцена освещения «Перерва» и её восстановление, вентиляция «Економ» и её восстановление, подтверждение/«взять в работу» тревог (W1 A-29). **Класс B** («Головний енергетик» или второе подтверждение другим «Енергетиком»): переключение QS (оба направления), пуск и остановка КГУ, разряд BESS, тест ДГУ, уставка давления воздуха, изменение приоритетов сброса, включение/выключение сценария. По решению A-39 к классу B отнесены также действия той же природы, которые E-06 прямо не называет: изменение параметров сценария (`scenario_params`), редактирование состава сброса (`shed_edit`), ручных слотов (`schedule_edit`) и порогов блокировок (`interlock_param`).
2. Права по матрице 4.2. «Енергетик» = `group_td_energy_manager`, «Головний енергетик» = `group_td_energy_chief` (W1 §4.2; chief наследует manager).
3. **Второе подтверждение.** Действие класса B, подготовленное пользователем без `group_td_energy_chief`, после `confirm` получает состояние `awaiting_second` (`needs_second=True`), `second_expires_at = now + second_ttl_s` (600 с). Второе подтверждение (`confirm_second`) даёт **другое лицо** из `group_td_energy_manager`: `second_by ∉ {prepared_by, confirmed_by}` (SQL-проверка + Python). Администратор без группы энергетика не подтверждает. После второго подтверждения действие выполняется (R-40 п.6). Истечение `second_expires_at` → `expired`.
4. Действие, подготовленное и подтверждённое `chief`, выполняется единолично (`needs_second=False`). `chief` может быть вторым лицом для действия `manager`.
5. Уведомление об `awaiting_second`: `bus.tick('action')` (баннер на экране «Керування», D-43) и `mail.activity` (тип «К выполнению», срок `second_expires_at`) для ≤ 10 пользователей `group_td_energy_manager`, кроме инициатора; activity закрывается при выполнении, отклонении или истечении.
6. Класс отмены (`undo`) — класс обратного вида (`undo_kind`).
7. Токен принадлежит пользователю, вызвавшему `prepare` (R-40 п.2); `confirm` чужого токена запрещён.
8. **Дистанционное перемикання (D-46, Q-27).** Виды с `remote_gated=True` (`qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`) при `td.energy_control.remote_switching_enabled=False` отказываются в `prepare`, `confirm`, `confirm_second` и `undo` с `UserError("Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled. Зверніться до адміністратора.")` (проверка стоит раньше проверок блокировок); плитка и кнопки узла — `enabled=false` с причиной «Дистанційне перемикання вимкнено адміністратором».

### R-40 Поток `prepare → confirm → выполнение` (FR-50, FR-55; M-33)

1. **`prepare(kind, params, advice_id)`** (API-17): проверка прав (R-39) и `available`; `params = kind.normalize(params)` (дефолты из `params_schema`, границы, приведение типов; `bess_charge.until` — время Киева `HH:MM`); дедупликация: запись этого же пользователя с тем же `kind_code` и хешем `params`, `state='prepared'`, созданная ≤ 5 с назад, используется повторно (новый токен); иначе новая запись `prepared` (`prepared_by`, `prepared_at`, `cls`, `summary`, `detail` по `kind.render`); для исполнителей `intent`/`genset` проверяется `td.energy_control.write_enabled`; вычисляются Odoo-проверки (R-41) → `checks`; токен `secrets.token_urlsafe(24)`; `token_hash = sha256`; `token_expires_at = now + confirm_ttl_s`. Ответ — 7.2.
2. **Токен**: в БД только хеш; сравнение постоянного времени; после `confirm`/`cancel`/истечения токен недействителен (`token_hash` не очищается — для идемпотентности п.4).
3. **`confirm(token)`** (API-18), в транзакции с `SELECT … FOR UPDATE` записи: (а) токен неизвестен → `UserError`; чужой → `AccessError`; (б) состояние `prepared` и `token_expires_at < now` → `expired` + `UserError("Час підтвердження минув…")`; (в) повторный расчёт Odoo-проверок; жёсткая блокировка → `_td_close('blocked', reason)` и ответ `blocked_reason` (без исключения); (г) конфликт ресурса (п.9) → `blocked`; (д) фиксация `undo_params` (текущая уставка воздуха из сигнала; прежние `enabled/params` сценария; прежний порядок сброса; прежние сцены освещения — только у сборщика); (е) `confirmed_by`, `confirmed_at`; (ж) класс B без chief → `awaiting_second` (R-39 п.3), иначе `_td_enqueue` (п.6).
4. **Идемпотентность `confirm`:** повторный вызов с тем же токеном тем же пользователем, когда состояние уже ≠ `prepared` и ≠ `expired/cancelled`, возвращает текущее состояние без новой команды (`message` «Уже надіслано»); двойной клик в UI не создаёт двух `td.command` (SQL: частичный `UNIQUE(idem)`; `idem = sha1("<id>:<kind_code>")`).
5. **`confirm_second(action_id)`** (API-19): блокировка строки; права и различие лиц; не просрочено; повторный расчёт проверок (жёсткая блокировка → `blocked`); `second_by`, `second_at`; `_td_enqueue`.
6. **`_td_enqueue()`** по `kind.executor`: **`intent`** — проверки наличия сигнала `energy_control/intent`, `write_enabled` сигнала и источника (иначе `blocked` «Запис вимкнено: {що}»); `td.command.create` (`sudo`, контекст `td_energy_control_internal`): `signal_id`, `value=0`, `payload` (7.5), `origin='energy'`, `expires_at=now+command_ttl_s`, `requested_by=confirmed_by`, `note=name`, `energy_action_id`; действие → `queued`, `started_at=now`. **`genset`** — `tools/genset_link.start_test(...)` (ADP-12): успех → `done`, `result_text="Тест ДГУ прийнято td_genset"`, `ref_model/ref_id`; `UserError` → `blocked` (текст ошибки). **`config`** — применить изменение (`scenario._td_apply_change`, порядок `shed_item`, `interlock`), `config_version = state.bump()`, действие → `done`, `result_text="збережено, очікує збирач"` (становится «виконано», когда `applied`; вычисляется в `_td_result_text()`), `started_at=finished_at=now`.
7. **Состояния транспорта** (`td.command` → действие, через M-37): `sent` → `sent`; `done` с `result_data.accepted=true` → `executing`; `done` с `accepted=false` → `blocked` (`state='blocked'`) или `failed` (`state='rejected'`) с `reason`; `failed` → `failed` (`error` команды); `expired` → `expired`; `cancelled` → `cancelled`.
8. **Финал от сборщика** (API-25 `actions[]`): `executing` (обновляет `step`), `done`/`failed`/`blocked` → `_td_close`. Состояние меняется только «вперёд» (`queued < sent < executing < done|failed|blocked`); исключение — отчёт сборщика считается **авторитетным** и для действия в состоянии `expired` (сборщик выполнил интент, но результат транспорта потерян: R-53 №6): `expired → executing/done/failed/blocked` разрешено, когда `idem` совпадает; другие конечные состояния не меняются.
9. **Конфликт ресурса:** для исполнителей `intent` разрешено одно действие в состояниях `queued/sent/executing` на `kind.resource`; новое действие на тот же ресурс → `blocked` «Для ресурсу «{resource}» уже виконується дія {name}». Сборщик дополнительно отказывает `rejected: busy: <resource>`.
10. **`_td_close(state, result_text, error)`**: `finished_at=now`, `state`, `result_text`, `error`; чаттер; `bus.tick('action')` (шина `td_energy_control`), для действий над QS/BESS/КГУ — `td_energy.tools.bus.tick(env, 'state')`; если `advice_id` и `state='done'` — `advice._td_on_action_done(self)`; закрытие `mail.activity`; для `blocked/failed/expired` — событие `td.energy.event` `kind='control'`, `level='warn'` (не для `blocked` из проверок оператора: только запись в журнале).
11. **`cancel(token)`**: `prepared/awaiting_second` → `cancelled` (Esc в диалоге); команда `queued` → `td.command.action_cancel()` и действие `cancelled`; другие состояния → `UserError("Скасувати можна лише підготовлену або таку, що очікує, дію.")`.
12. **`_cron_expire`** — разд. 6 (просрочка `prepared`, `awaiting_second`, `queued/sent`, `executing`, конфиг без применения).

### R-41 Реестр блокировок (FR-51; M-32; C-39)

1. Блокировки — **именованные проверки** (`CHECKS[code](ctx, params) -> Result(state, detail, values)`) в двух реализациях: `td_energy_control/tools/interlocks.py` (Odoo, подсказка в диалоге) и `td_collector_energy/interlocks.py` (сборщик, **жёсткое выполнение**). Обе должны проходить таблицу золотых случаев ниже (AC-195…AC-199, AC-241, AC-242). Код проверок не берётся из БД; строка `td.energy.interlock` лишь настраивает `hard`, `fail_closed`, `params`, `where`.
2. **Свежесть.** Значение сигнала считается отсутствующим (`None`), если `age > max(3·period_s, max_age_s)`; `max_age_s` = 60 с (`data_fresh.params`), на стороне Odoo `age = now − td.signal.last_ts`, на стороне сборщика — `LiveCache.age_s`. Состояние `unknown` — когда нужный вход `None`.
3. **Итог действия.** `blocked = any(c.hard and (c.state == 'fail' or (c.state == 'unknown' and c.fail_closed)))`. Мягкие (`soft` в виде или `hard=False`) только показываются. Проверка `where='odoo'` не выполняется сборщиком; `where='collector'` в диалоге имеет `state='unknown'` и текст «перевіряє збирач» (не блокирует); `where='both'` — в обоих местах по тем же правилам.
4. **В сборщике** проверки видов интентов выполняются синхронно в `call()` перед постановкой в очередь, а проверки `post`-условий (например, `bess_ok`) повторяются перед **активирующим** шагом выполнения (R-52 п.2). Любая жёсткая неудача → `blocked`, ни одной записи в устройство.
5. **Золотые случаи** (вход → ожидаемое `state`; «—» — вход отсутствует/несвеж):

| Проверка | Вход | Ожидание |
|---|---|---|
| `controller_remote` | `remote=1` | ok |
| | `remote=0` | fail |
| | — | unknown (блокирует: hard, fail_closed) |
| `no_island` | `ats_pos=2`, `src1_ok=1` | ok |
| | `ats_pos=3` (остров) | fail |
| | `ats_pos=2`, `src1_ok=0` | fail |
| `ats_parallel_lock` | `lock=1` / `0` / — | ok / fail / unknown |
| `qs_current_ok` | `p1=150`, `p2=100`, `cos=0,95`, `rating=1600`, `max_ratio=0,8` → I = 25 / (√3·0,4·0,95) ≈ 38 А | ok, подпись «≈ 40 А з 1600 А» (округление до 5 А) |
| | `p1=1700`, `p2=0` → I ≈ 1292 А > 1280 А | fail |
| | QS уже `closed` | ok, detail «QS уже замкнений» |
| `bess_ok` | `bess_state ∈ {1,2,4}` / `{0,3}` / — | ok / fail / unknown |
| `bess_soc_lt_limit` | `soc=82`, `limit=95` | ok, «Заряд 82 % < 95 %» |
| | `soc=95`, `limit=95` | fail |
| `bess_reserve_kept` | `soc=82`, `P=100`, `T=60 мин`, `cap=387`, `reserve=30` → `82 − 25,84 = 56,2` | ok |
| | `soc=50`, те же → `24,2` | fail |
| `bess_temp_ok` | `t=24` / `t=41` / — | ok / fail / unknown (не блокирует: fail_closed=false) |
| `chp_ready` | `chp_state=0` / `1`,`2`,`3` | ok / fail |
| `chp_gas_pressure` | `gas=2,10`, `min=1,5` / `0,80` | ok / fail |
| `chp_permit` | `1` / `0` / — | ok / fail / unknown |
| `chp_min_run` | КГУ не работает | ok; работает 1,2 ч при `min_run_h=2` → fail; 2,3 ч → ok |
| `no_fire_alarm` | сигнала нет (модуль пожарной не установлен) | ok, «не підключено» |
| | `alarm` / `ok` | fail / ok; stale → unknown (не блокирует) |
| `air_setpoint_min` | `setpoint=6,5`, `min=6,2`, `margin=0,2`, `max=8,5` | ok |
| | `6,3` / `8,6` | fail / fail |
| `aisle_lux_ge` | min `e_now = 80` / `60` / сигналов нет | ok / fail (мягкая) / unknown |
| `co2_lt` | `620` ppm / `1200` / — | ok / fail (мягкая) / unknown |
| `genset_fuel` | `fuel=78`, `min=30` / `25` | ok / fail (мягкая) |
| `genset_idle` | не работает, не тест, сеть есть / работает | ok / fail (жёсткая в Odoo) |
| `data_fresh` | все входы вида свежи / один несвеж | ok / fail, detail «немає свіжих даних: {коди}» |

6. **Границы кода сборщика (config может только сужать):** `max_ratio ≤ 0,9`, `min_bar ≥ 1,0`, `max_c ≤ 45`, `max_age_s ≤ 120`, `bess_kw_max ≤ 200`, `air_bar ∈ [5,0; 8,5]`, `pv_limit_min_pct ≥ 10`, `soc_floor_pct ≥ 10`. Значение конфига вне границы — применяется граница кода, событие `config` «значення {k} обмежено».
7. Пороги `td.energy.interlock.params` меняет только администратор; изменение → запись журнала `td.energy.action` (`origin='config'`, `kind_code='interlock_param'`, класс B, `confirmed_by` — администратор, который по W1 §4.2 имеет группу `chief`) и `state.bump()`.

### R-42 Виды команд: параметры, шаги выполнения, верификация (FR-49, FR-55; M-31; C-39)

1. **Параметры.** Поле `params_schema` (M-31) описывает форму диалога и границы в Odoo; сборщик проверяет те же границы независимо (JSON-схема `intent.schema.json`) и применяет «границы кода» (R-41 п.6). Невалидный параметр → `rejected: bad params: {ключ}`.
2. **`available`** (M-31): `intent` — активны источник `ENERGY-CTL` и сигнал `energy_control/intent`, для `light_*`/`vent_*` — непустой список целей BMS в конфиге (API-24 `bms`), для `air_setpoint` — сигналы `air_sp`, `air_min` в конфиге; `genset` — мост ADP-12; `config` — всегда.
3. **Шаги выполнения** — собственность сборщика (`intents.py`); Odoo передаёт только `kind` и `params`. Все шаги **уровневые** (устанавливают значение, а не переключают), поэтому повтор безопасен. Верификация — чтение обратно через `ctx.read_signal` (разовый опрос сигнала каждую секунду до `verify_timeout_s`; `LiveCache` обновляется так же):

| `kind` | Шаги (логические сигналы, API-24 `signals`) | Верификация | Fail-safe | Перекрытие ресурса |
|---|---|---|---|---|
| `qs_close` | `qs_cmd = 2` | `qs_state == closed` ≤ 10 с; `qs_ack ≠ 2` (иначе `failed: «Контролер відмовив: блокування»`) | нет (команда атомарна) | — |
| `qs_open` | `qs_cmd = 1` | `qs_state == open` ≤ 10 с | — | — |
| `bess_charge` | `bess_sp = power_kw`; `bess_until = soc_limit_pct`; `bess_valid = valid_s`, где `valid_s = секунды до until` (Киев; `until` ≤ now → `rejected: «Час «до» має бути пізніше за поточний»`; максимум 43 200); `bess_mode = 1` | чтение `bess_mode == 1` и `bess_ack == 0` ≤ 10 с; **мягко**: через 30 с `bess_kw ≥ 0,5·power_kw` (иначе предупреждение в `result`) | `bess_mode = 0`, `bess_valid = 0` | ручное перекрытие `bess` до `now + valid_s` |
| `bess_discharge` | `bess_sp = power_kw`; `bess_until = floor_soc` (`max(reserve_pct, 10)`); `bess_valid = duration_min·60`; `bess_mode = 2` | `bess_mode == 2`, `bess_ack == 0`; мягко `bess_kw ≤ −0,5·power_kw` | `bess_mode = 0` | перекрытие `bess` на `duration_min` |
| `bess_stop` | `bess_mode = 0`; `bess_valid = 0` | `bess_mode == 0` | — | снимает перекрытие `bess` |
| `chp_start` | `chp_cmd = 1` | ≤ 30 с: `chp_state ∈ {1,2}` и `chp_ack ≠ 2` | нет: при неудаче пуск не повторяется, результат `failed`; КГУ в состоянии `1/2` автоматически не останавливается | КГУ «во владении оператора» (сценарий `chp` её не останавливает) |
| `chp_stop` | `chp_cmd = 2` | ≤ 30 с: `chp_state ≠ 2` | — | снимает владение |
| `air_setpoint` | `air_sp = setpoint_bar` (инженерные единицы, бар; адрес сигнала имеет `scale=0,01`, плагин Modbus делит: `raw = value/scale`) | чтение `air_sp` равно ≤ 10 с | возврат прежней уставки (`undo_params`) при неудачной верификации | перекрытия `air` нет |
| `light_break` | для каждой цели `bms.light_break.light` (`aisle=false`): запись `scene_signal = scene_number`, `text="fade=2.0"`; запомнить прежнюю сцену | ≥ 80 % целей читаются обратно ≤ 15 с | восстановить запомненные сцены | перекрытие `light` на `duration_min`; по истечении — автоматическое восстановление (R-52 п.8) |
| `light_restore` | восстановить запомненные сцены, иначе `light_scene_day_number` | как выше | — | снимает перекрытие |
| `vent_eco` | для каждой цели `bms.vent_eco.vent`: `mode_signal` (текст) = `eco_mode` (`VEL`); запомнить прежний режим | ≥ 80 % целей ≤ 15 с | восстановить режимы | перекрытие `vent` на `duration_min`; автовосстановление до `day_vent_mode` |
| `vent_restore` | `mode_signal` = запомненный или `day_vent_mode` | как выше | — | снимает перекрытие |

4. **Тексты диалога** (`confirm_title`, `confirm_text`, `sub`) — шаблоны разд. 5.3, значение `{chp_kw}` = `plant.chp_kw / 2` (400 кВт, D-33 «вийде на 400 кВт»), `{ramp_min}` = параметр `chp.ramp_min`, `{test_minutes}` — адаптер ADP-12, `{current_bar}` — из сигнала `air_sp`.

### R-43 Публикация конфигурации и статус сценариев (FR-47, FR-57; C-39)

1. **`config_version`.** Счётчик в `td.energy.control.state` (M-39); `bump()` вызывается изменением: `td.energy.scenario` (`enabled`, `params`), `td.energy.shed.item` (любое поле), слотов `executes=True`, `td.energy.interlock` (`params`, `hard`, `fail_closed`, `active`), флагов `write_enabled`/`automation_enabled`, параметров `td.energy_control.*` движка, `td.energy.cos_phi_target`, `td.energy.bess_reserve_pct`, `td.energy.pv_kwp`. Изменения внешних данных (цели BMS, тариф, `is_critical` узлов) ловит `cron_td_energy_control_watch`: пересчитывает канонический JSON, сравнивает `config_etag`, при расхождении — `bump()`.
2. **Канонический JSON:** `json.dumps(cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` без ключей `server_time`, `etag`, `config_version`; `etag = sha256(canonical).hexdigest()`; `ETag: "<etag>"`.
3. **Применение.** Плагин валидирует конфиг по `config.schema.json`; невалидный → оставляет предыдущий валидный, в API-25 `engine.reason="config invalid: …"`, событие `config`. `config_version_applied` — версия конфига, по которой движок работает сейчас. `td.energy.control.state.applied_version = max(…)`.
4. Действие `executor='config'` считается **применённым**, когда `applied_version ≥ action.config_version` (`applied`, `result_text`: «виконано» / «збережено, очікує збирач»). Карточка сценария: переключатель = `enabled` (Odoo), дополнительный чип «Очікує застосування» при `!applied`.
5. **Чипы сценариев** (`state_text`, `state_kind`): `enabled=False` → «Вимкнено», `off`; нет отчёта движка ≥ `2·heartbeat_stale_s` → «Немає даних від рушія», `off`; далее по таблице (`{…}` — из `engine_facts`; числа с запятой, `0,0`):

| Сценарий | `armed` (`arm`) | `active` (`act`) | `warn` (`warn`) |
|---|---|---|---|
| `peak` | «Чергування · запас {margin_kw} кВт» | «Зрізання піку · {stage}» (`bess`: «BESS {bess_kw} кВт»; `chp`: «BESS + КГУ»; `shed`: «скинуто {shed_n}»; `…` комбинация через « + ») | «Збій: {reason}» |
| `self` | «Очікування · експорт {export_kw} кВт» | «Активний · заряд BESS {bess_kw} кВт» или «Обмеження СЕС {pv_limit_pct} %» | «Збій: {reason}» |
| `pfc` | — | «Активний · cos φ {cos1} / {cos2}» | «Збій: {fault}» (напр. «PFC-2 ступінь 3»; из `engine_facts.fault` или W1 `fault_step`) |
| `night` | «Наступний запуск о {from}» | «Активний до {to}» | «Збій: {reason}» (напр. «немає цілей BMS») |
| `backup` | «Готовий · паливо {fuel_pct} %» (`fuel_pct` — W1 `_td_genset_summary`; без него «Готовий») | «Мережі немає · скинуто {shed_n}» | «Збій: {reason}» |
| `chp` | «Очікує вигідної ціни» | «Працює · {chp_kw} кВт» | «Збій: {reason}» |

### R-44 Движок автоматики: цикл, режимы, входы, арбитраж (FR-56, FR-57; C-39, C-40)

1. **Режимы.** `off` — нет валидной конфигурации, или `flags.automation_enabled=false`, или `flags.write_enabled=false`: движок только читает и отчитывается (состояния сценариев — `off`, чипы показывают «Вимкнено»/факты без действий). `hold` — движок жив, но **не пишет** (причины: контроллер в местном режиме `remote=0`; несвежий критичный вход дольше `stale_hold_s`; пожарная тревога для ресурсов `vent`/`light`; превышено `max_writes_per_min`; ошибка конфига). `auto` — норма. Переход в `hold` оставляет имеющиеся принудительные режимы устройств до истечения их сторожевых таймеров (R-53 №7). Каждая смена режима — событие `mode`.
2. **Тик** (`tick_s`, 2 с; если тик длится дольше периода — следующий стартует сразу, лог `WARNING`, но без накопления): (а) `Inputs` из `ctx.live`; (б) определить режим (п.1); (в) если `auto` — выполнить сценарии в порядке **`backup`, `peak`, `self`, `slots` (шаг BESS-слотов, R-54 п.5), `chp`, `night`, `pfc`** (каждый — чистая функция `step(inputs, cfg, state, now) → Output(requests, status, events)`); (г) арбитраж запросов (п.4); (д) `Actuator` применяет желаемые значения (п.7); (е) обновление состояний и событий; (ж) heartbeat каждые 10 с. Исключение сценария перехватывается: сценарий → `warn` «внутрішня помилка», остальные продолжают.
3. **Входы и свежесть.** Критичные входы: `peak` — `grid_kw`, `bess_soc`; `self` — `export_kw`, `pv_kw`, `bess_soc`; `backup` — `ats_pos`, `src1_ok`; `chp` — `chp_state`; `night`, `pfc` — `remote`. Отсутствующий критичный вход → сценарий `warn` «немає даних: {коди}» без записей; `grid_kw` отсутствует дольше `stale_hold_s` → движок `hold`.
4. **Арбитраж.** Ресурсы: `bess`, `chp`, `shed`, `pv`, `vent`, `light`, `pfc`, `qs`, `air`. Порядок приоритета: **ручное перекрытие оператора** (R-52 п.8) > `backup` > `peak` > `self` > `slots` > `chp` > `night` > `pfc`. Запрос низшего приоритета на ресурс, который в этом тике уже захвачен высшим или заблокирован перекрытием, отбрасывается (событие `override`, раз на смену). `bess`: разряд (`peak`, `backup`) всегда побеждает заряд (`self`).
5. **Местный режим контроллера** (`remote=0`): `hold`, причина «контролер у місцевому режимі», событие `interlock` раз на смену, `td.energy.event` `kind='control'` `level='warn'` (из Odoo через API-25 `events`, дедуп 60 мин).
6. **Границы кода** (константы `limits.py`): `bess_kw_max=200`, `pv_limit_min_pct=10`, `air_bar ∈ [5,0; 8,5]`, `soc_floor_pct ≥ 10`, `min_write_interval_s ≥ 2`, `max_writes_per_min ≤ 120`, `tick_s ∈ [1,10]`. Значения конфига применяются как `min(code, cfg)` (для нижних границ — `max`).
7. **Политика записи (`Actuator`).** Желаемое значение `desired[signal]` записывается, если `desired ≠ readback` (или `≠ last_write`, когда чтение назад недоступно) и `now − last_write(signal) ≥ min_write_interval_s`; принудительные режимы BESS и лимиты сброса **перезаписываются** каждые `valid_s / 3` (сторожевой таймер контроллера, R-53 №7); первая неудача записи → повтор через `min_write_interval_s`, третья подряд → сценарий `warn`, ресурс освобождается, событие `failsafe`. Предохранитель частоты: `> max_writes_per_min` записей за скользящую минуту → `hold` на 5 мин, событие `failsafe`.
8. **Пожарная тревога** (`fire_state = alarm`): записи для `vent`, `light` прекращаются (движок не конфликтует с противопожарной логикой), `night` → `warn` «пожежна тривога», событие `interlock`; после сброса — продолжается. Остальные ресурсы не меняются (R-60).
9. **Владение.** Движок помнит, чем он управляет (`bess_owner ∈ {None, scenario, manual}`, `chp.started_by`, список сброшенных нагрузок со временем, `night.applied`, перекрытия), и сохраняет в `Store`; после рестарта состояние восстанавливается и **сверяется с устройством** (чтение назад): расхождение → владение сбрасывается, принудительные режимы устройства не трогаются до истечения `valid_s`.
10. **События движка** (`events[]` API-25; `kind`): `auto_step` (движок изменил состояние устройства: «BESS · розряд 62 кВт»), `auto_release` (восстановление), `interlock` (блокировка/отказ), `override` (ручное перекрытие), `failsafe`, `mode`, `config`. Odoo пишет их в журнал как `origin='auto'` (R-56 п.3); `interlock`/`failsafe`/`mode(hold)` дополнительно создают `td.energy.event` `kind='control'`.

### R-45 Сценарий «Срезание пика» (BESS → КГУ → сброс; FR-56; CT-04)

Параметры — M-29 `peak`; входы: `grid_kw`, `bess_kw`, `bess_soc`, `bess_state`, `chp_state`, `air_bar`, `ctl_remote`. Состояние в `Store`: `stage ∈ {idle, bess, chp, shed}`, `stage_since`, `acc_kws`, `block_start`, `release_since`, `shed_list`, `chp_started_by_peak`.

1. **Прогноз интервала спроса.** Блок 15 мин выровнен по UTC-эпохе (`block_start = floor(epoch/900)·900`, переход DST не влияет). Каждый тик: `acc += grid_kw·dt`; `remaining = 900 − (now − block_start)`; `proj_kw = (acc + grid_kw·remaining) / 900`. В начале блока `acc=0`; первые 30 с блока `proj_kw = grid_kw`.
2. **Активация.** `active_cond = proj_kw ≥ limit_kw − activate_margin_kw  или  grid_kw ≥ limit_kw`. Из `idle` при `active_cond` → `stage = bess` (событие `auto_step` «Зрізання піку: старт, прогноз {proj} кВт»).
3. **Цель.** Пока `stage ≠ idle`: `target_grid = limit_kw − margin_kw`; `excess = grid_kw − target_grid` (кВт; `grid_kw` уже учитывает текущую работу BESS/КГУ/сброса).
4. **Ступень 1 — BESS.** `p_max = min(bess_max_kw, 200)`; `floor_soc = max(bess_min_soc_pct, bess_reserve_pct)`; `bess_available = bess_state ∈ {1,2,4} ∧ soc > floor_soc + 2 ∧ ¬manual_override(bess)`; `bess_now = max(0, −bess_kw)`; `p_target = clamp(bess_now + excess, 0, p_max)`; если `bess_available ∧ excess > 0` (или `p_target` отличается от желаемого ≥ 5 кВт): запрос ресурса `bess` = `{mode: 2, setpoint_kw: round(p_target), until_soc: floor_soc, valid_s: 30}` (перезапись каждые 10 с). SOC ≤ `floor_soc` → BESS недоступен, событие `interlock` «BESS на резерві {soc} %» (раз на смену). `uncovered = excess − (p_target − bess_now)`.
5. **Ступень 2 — КГУ.** Если `chp_allowed ∧ uncovered > 0` длится ≥ `stage_delay_s` и КГУ готова (`chp_state = 0`, проверки `chp_ready`, `chp_gas_pressure`, `chp_permit` — ok, минимальная пауза `min_off_min` истекла, сценарий `chp` не владеет КГУ): запрос `chp` = `start`, `chp.started_by = 'peak'`, `stage = chp`. КГУ ещё разгоняется (`chp_state = 1`) — ждать (не эскалировать) до `stage_delay_s`.
6. **Ступень 3 — сброс.** Если `shed_allowed ∧ uncovered > 0` длится ≥ `stage_delay_s` после ступени 2 (или КГУ недоступна/запрещена): `stage = shed`; `need = uncovered`; выполнить R-51 `shed(items, need)`; далее каждые `stage_delay_s` (если `uncovered` по-прежнему > 0) — следующие элементы.
7. **Отпускание.** Если `proj_kw ≤ limit_kw − release_margin_kw ∧ grid_kw ≤ limit_kw − release_margin_kw` непрерывно `release_hold_s`: последовательно **в обратном порядке** — восстановление сброшенных (R-51 `restore`, шаг `shed_restore_step_s`); затем КГУ: `stop` только если `started_by = 'peak'` и отработано `min_run_h` (иначе остаётся, владение переходит к сценарию `chp`, если он включён, или останавливается позже по тому же правилу); затем BESS: `setpoint` уменьшается шагами по `p_max/4` каждые 10 с до 0 и `mode = 0`; `stage = idle`; событие `auto_release` «Зрізання піку завершено».
8. **Статус.** `idle` → `armed`, факты `margin_kw = limit_kw − grid_kw`, `proj_kw`, `grid_kw`; `bess|chp|shed` → `active`, факты `stage`, `bess_kw`, `shed_n`; отказ устройства (`bess_ack = 2` дважды, ошибка записи 3 раза) → `warn`, `reason`.
9. Проверки сценария: `bess_ok`, `controller_remote`, `no_island` (в острове сценарий приостанавливает `backup`, R-49).

### R-46 Сценарий «Самопотребление СЭС» (FR-56; CT-05)

Входы: `pv_kw`, `export_kw`, `bess_kw`, `bess_soc`, `bess_state`; параметры — M-29 `self`.

1. Активно, когда `pv_kw ≥ 1`. Иначе `armed`, факты `export_kw`.
2. Если `export_kw > export_max_kw + export_deadband_kw` ∧ BESS доступен для заряда (`bess_state ∈ {1,2,4}`, `soc < bess_target_soc_pct − 0,5`, `¬manual_override(bess)`, BESS не разряжается по R-45): `charge_now = max(0, bess_kw)`; `p = clamp(charge_now + (export_kw − export_max_kw), 0, min(bess_max_kw, 200))`; запрос `bess` = `{mode: 1, setpoint_kw: round(p), until_soc: bess_target_soc_pct, valid_s: 30}`.
3. **Ограничение СЭС** (`curtail_pv`): если после шага 2 остаток `uncovered = export_kw − export_max_kw − (p − charge_now) > export_deadband_kw` держится `curtail_delay_s`: интегральный шаг `limit_pct = max(pv_limit_min_pct, limit_pct_now − ceil(100·uncovered / pv_kwp))` (не чаще `min_write_interval_s`), запрос `pv` = `{pv_limit_pct, shed_valid_s: 60}`; `limit_pct_now` берётся из чтения `pv_limit` назад (изначально 100).
4. **Отпускание:** если `export_kw < export_max_kw − export_deadband_kw` непрерывно `restore_hold_s`: `limit_pct = min(100, limit_pct_now + 5)` каждые `min_write_interval_s`; BESS: при `export_kw = 0` и (`soc ≥ target` или `pv_kw < 1`) → `mode = 0`.
5. Статус: `active` — «заряд BESS {p} кВт» или «Обмеження СЕС {limit_pct} %»; `armed` — экспорт в норме; `warn` — отказ BESS/инверторов.

### R-47 Сценарий «Компенсация реактивной мощности (PFC)» (FR-56; CT-06)

Регулирование ступеней выполняет PFC-контроллер; движок лишь задаёт режим и цель и контролирует отказы.

1. Сценарий `enabled` и `auto`: желаемые `pfc_mode = 1`, `pfc_cos = cos_phi_target` (инженерные единицы, напр. 0,95; адрес сигнала имеет `scale=0,01`, регистр = 95; значение из `plant.cos_phi_target`, E-10: единая группа настроек); запись при старте, смене цели, расхождении с чтением назад.
2. Сценарий выключен (`enabled=false`) и движок в `auto`/`off` с разрешённой записью: `pfc_mode = 0` (ручной режим; на стенде эмулятор отключает ступени — A-45). Изменение — действие класса B, поэтому случайное отключение исключено.
3. Мониторинг: `pfc1_fault`, `pfc2_fault > 0` → сценарий `warn`, `fault = "PFC-{s} ступінь {k}"`; значения `cos φ` секций (`energy/sections/S{1,2}/cos_phi`) — в фактах `cos1`, `cos2`. Заявку ТО и события создаёт W1 (CT-05, R-35); движок их **не** дублирует.
4. `hold` из-за местного режима не меняет состояние PFC.

### R-48 Сценарий «Ночной режим (BMS)» (FR-56; CT-07)

Параметры — M-29 `night`; цели — API-24 `bms.night` (`vent[]` — установки `roofvent` с `mode_signal`, `sp_night_signal`; `light[]` — группы с `scene_signal`; группы `aisle` тоже переводятся в дежурный сценарий ночью).

1. **Окно:** `from`/`to` — местное время Киева (R-63); `from > to` — пересекает полночь. `in_window(now)`: день начала окна ∈ `days` (для части после полуночи — предыдущие календарные сутки).
2. **Вход в окно:** для каждой установки `mode_signal = vent_mode` (текст, напр. `VEL`) и, если есть, `sp_night_signal = heat_setpoint_c`; для каждой группы `scene_signal = light_scene_number`, `text = "fade=2.0"`. Запись идемпотентна; запоминается время записи. Событие `auto_step` «Нічний режим: вентиляція RoofVent {n} шт. → {vent_pct} %, освітлення — черговий сценарій».
3. **Выход из окна:** `mode_signal = day_vent_mode`, `scene_signal = light_scene_day_number`; событие `auto_release` «Вентиляція · денний режим: RoofVent {n} шт. → 100 %» (текст макета).
4. **Старт/смена конфига внутри окна:** если чтение назад ≠ желаемому — записать (идемпотентно). Вне окна ничего не пишется (сценарий не «держит» день).
5. **Ручное вмешательство в BMS:** если после записи чтение назад цели отличается от желаемого дольше 60 с, а движок эту цель не менял — цель помечается `overridden` до следующей границы окна, событие `override`; движок её не перезаписывает.
6. Пропуски записей: пожарная тревога (R-44 п.8), ручное перекрытие ресурса `vent`/`light` (R-52 п.8); `remote=0` не влияет (цели BMS идут не через контроллер ГРЩ); `bms.night` пуст → `warn` «немає цілей BMS».
7. Статус: в окне `active`, факты `until` (`to`); вне окна `armed`, факты `next_run` (ближайшее начало окна, Киев `HH:MM`).

### R-49 Сценарий «Резервное питание» (АВР → ДГУ; FR-56; CT-08)

АВР переключает **аппаратно**; движок лишь сбрасывает нагрузки и восстанавливает их.

1. `mains_lost = (src1_ok == 0) ∨ (ats_pos == 3)`; устойчивое условие ≥ 2 тиков (дебаунс 4 с) → `active`; ресурсы приоритета `backup` > все (R-44 п.4); сценарий `peak` приостанавливается, его ресурсы освобождаются (сбросы R-45 восстанавливаются только после восстановления сети).
2. Действие при `active`: `need = max(0, p_total − 0,9·genset_capacity_kw)` (`p_total` — `energy/totals/p_now`; отсутствует → `need = ∞`); выполнить R-51 `shed(items, need)` сразу и далее каждые `stage_delay_s` (из `peak.params`, иначе 10 с), пока `need` не покрыт или список не исчерпан. Элементы с `critical=true` (узел `is_critical`: компрессорная, склады) пропускаются — критичные нагрузки питаются от ДГУ; узлы из `never_shed` не трогаются по построению. BESS остаётся в `mode = 0` (островным режимом BESS управляет сам контроллер BESS; движок не форсирует).
3. Восстановление: `src1_ok = 1 ∧ ats_pos = 2` непрерывно `restore_delay_s` → R-51 `restore` шаг за шагом; `stage = armed`; событие `auto_release` «Мережа відновлена: навантаження повернено».
4. Статус: `armed` (сеть есть), факты `fuel_pct` добавляет Odoo (W1 `_td_genset_summary`); `active` — факты `shed_n`; `warn` — нет данных `ats_pos`/`src1_ok`.
5. Тест ДГУ (`genset_test`) и плановые отключения (W1 `td.energy.outage.plan`) сценарий не запускают.

### R-50 Сценарий «КГУ по графику и цене» (FR-56; CT-09)

Параметры — M-29 `chp`; входы: `chp_state`, `chp_kw`, `chp_hours`; конфиг: `tariff.zones`, `slots` (`resource='chp'`).

1. `chp_cost = gas_price_uah_m3 · gas_m3_per_kwh` (₴/кВт·ч; сид: 19,80 · 0,25 = 4,95); `grid_price` — цена текущей зоны тарифа (местное время, R-63); `price_ok = (grid_price − chp_cost) ≥ price_margin_uah_kwh`; `slot_active` — текущее время в слоте `resource='chp'`, `executes=True`, разрешённом по дню (`use_slots=true`). `wanted = slot_active ∨ price_ok` (в выключенном сценарии — `wanted=false`).
2. **Пуск:** `wanted ∧ chp_state = 0 ∧ ¬hold`, пауза `min_off_min` после последней остановки истекла, проверки `chp_ready`, `chp_gas_pressure`, `chp_permit` — ok, КГУ не во владении оператора → запрос `chp = start`, `started_by = 'chp'`, событие `auto_step` «КГУ: пуск за ціною ({grid_price} ₴ проти {chp_cost} ₴)».
3. **Остановка:** `¬wanted ∧ chp_state = 2 ∧ started_by = 'chp' ∧ отработано ≥ min_run_h` → `stop`. КГУ с `started_by ∈ {'peak','manual'}` этим сценарием не останавливается.
4. `chp_state = 3` (авария) → `warn` «КГУ в аварії». Пуск «Срезания пика» ступень 2 (R-45) не зависит от `enabled` этого сценария (только от `chp_allowed`), но учитывает паузу `min_off_min` и владение.
5. Статус: `armed` — «Очікує вигідної ціни»; `active` — работает (факты `chp_kw`); `off` — сценарий выключен.

### R-51 Сброс и восстановление нагрузок (FR-48; CT-10; используют R-45, R-49)

1. **Список:** `shed[]` из API-24 по `seq`; элементы с узлом в `never_shed` или вне списка сигналов пропускаются (событие `interlock` раз на смену). Элементы с `critical=true` (допускаются M-30 только для частичного/условного сброса) выполняются только сценарием `peak`; `backup` их пропускает. `never_shed` — коды `is_critical` узлов **без** активной строки приоритета плюс `NEVER_SHED_CODES`; движок проверяет ещё раз.
2. **`shed(items, need_kw)`:** для каждого элемента по порядку, ещё не сброшенного: (а) условие — `air_pressure_min`: `air_bar ≥ condition_value`; `no_active_cycle`: в v1 нет сигнала состояния цикла → `unknown` → элемент **пропускается** (событие «пропущено: немає даних про цикл {вузол}», Q-32); `none` — ок; (б) запись: `off`, `pause`, `defer` → `limit_pct = 0`; `reduce` → `limit_pct = param`; вместе с `shed_valid_s = 60` (перезапись каждые 20 с, сторожевой таймер контроллера); (в) `pause`/`defer` ставят таймер `param` минут, после которого элемент восстанавливается автоматически; (г) `cumulative += kw_reducible`; остановка, когда `cumulative ≥ need_kw`; событие `auto_step` «Скинуто: {name} — {how}».
3. **`restore()`:** в обратном порядке сброса, один элемент за `shed_restore_step_s` (20 с): `limit_pct = 100`; когда восстановлены все — `shed_valid_s = 0`. Событие `auto_release` «Повернуто: {name}».
4. Состояние сброса (`shed_list` со временем) хранится в `Store`; после рестарта движок читает `limit_pct` назад и согласует список.
5. Лимиты нагрузок выполняют устройства/контроллер (на стенде — эмулятор, R-59); при исчезновении движка сторожевой таймер `shed_valid_s` возвращает нагрузки (R-53 №7).

### R-52 Выполнение интента оператора в сборщике (FR-55; C-39; `executor.py`)

1. **Приём (`call`).** Синхронно, ≤ 1 с: схема `intent.schema.json` (`v=1`, обязательные ключи, границы); `expires_at` (с поправкой на расхождение часов по `server_time` конфига) > now; `idem` уже известен → сохранённый результат (`duplicate: true`); `kind` известен; `params` в границах (R-42); жёсткие проверки R-41 (`where ∈ {both, collector}`) **по свежим входам**; ресурс свободен (R-40 п.9) и в очереди ≤ 4 интентов; предохранители (`write_enabled`, `controller_remote`). Неудача → `result_data` `accepted=false` (7.5); успех → запись в `Store` (`state=executing`) и постановка в очередь ресурса.
2. **Выполнение** (задача на интент; один выполняемый интент на ресурс): перед **первым** шагом — повторить жёсткие проверки; перед **активирующим** шагом (запись, меняющая поток энергии: `bess_mode`, `chp_cmd`, `qs_cmd`, `air_sp`, сцены/режимы BMS) — повторить проверки, чьи входы изменились (`bess_ok`, `no_island`, `ats_parallel_lock`, `no_fire_alarm`).
3. **Шаг:** `ctx.write_signal(code, value, text)` с таймаутом `step_timeout_s` (8 с); ошибка → один повтор через 1 с; вторая ошибка → `failed` + fail-safe. Далее верификация (R-42): `ctx.read_signal` раз в секунду до `verify_s` шага (по умолчанию 10 с; КГУ 30 с; BMS 15 с), предикат из таблицы R-42.
4. **Результат.** Все шаги и обязательная верификация пройдены → `done`, `result` — строка ≤ 256 символов («BESS: заряд 50 кВт до 16:00 (valid_s 5700)»). **Мягкая** верификация (например, `bess_kw ≥ 0,5·power_kw` через 30 с) не пройдена → `done` с примечанием «попередження: …». **Жёсткая** не пройдена → fail-safe → `failed` («Не підтверджено пристроєм: {що}»); в `result` — итог fail-safe.
5. **Fail-safe** — шаги из таблицы R-42 (`bess_mode = 0`, восстановление уставки/сцен/режимов): best-effort, по одному повтору, без блокировки очереди; неудача fail-safe → событие `failsafe` и текст «стан пристрою невідомий: перевірте вручну».
6. **Идемпотентность.** `Store.intents[idem] = {state, run_id, result, ts}` (хранение 24 ч или 500 записей); повторный `call` с тем же `idem` возвращает сохранённый результат без повторного выполнения; все шаги уровневые, поэтому даже повторное выполнение безопасно.
7. **Тайм-ауты.** Общий `exec_timeout_s` (60 с) от приёма; превышение → `failed` + fail-safe. Рестарт плагина во время `executing` → при старте такие интенты отчитываются `failed` («рушій перезапущено під час виконання; стан пристрою невідомий — перевірте»); автоматического продолжения нет.
8. **Ручное перекрытие (`override`).** Успешные `bess_charge`/`bess_discharge` → `override[bess] = {until, action_id}` (до `now + valid_s` / длительности); `light_break`, `vent_eco` → `override[light|vent]` до конца `duration_min`, после чего исполнитель **сам** запускает восстановление (`light_restore`/`vent_restore` по запомненному состоянию; событие `auto_release` «Освітлення: перерва завершена»); `bess_stop`, `light_restore`, `vent_restore` снимают перекрытие; `chp_start` → `chp.owner='manual'`, `chp_stop` снимает. Перекрытия хранятся в `Store`, блокируют записи сценариев на ресурс (R-44 п.4), событие `override` один раз.
9. **Отчётность.** Каждая смена состояния (`executing` → шаг N из M, `done`, `failed`, `blocked`) ставится в очередь `Reporter` и отправляется немедленно (API-25).
10. **Счётчики записей.** Записи исполнителя учитываются в `max_writes_per_min`, но предохранитель частоты отключает только автоматику (оператор имеет приоритет).

### R-53 Режимы отказов (FR-55, FR-57)

| № | Событие | Поведение | Состояние устройства | Что видит оператор |
|---|---|---|---|---|
| 1 | Odoo недоступен | Движок работает на кешированной конфигурации (≤ 7 суток, `Store`); `Reporter` буферизует до 200 действий и 1000 событий (более старые отбрасываются со счётчиком), отправляет после восстановления; новые ручные команды невозможны | не меняется; сценарии действуют | экран недоступен; после восстановления журнал пополняется |
| 2 | Сборщик недоступен | `td.command` остаётся `queued` → `expired` (`command_ttl_s`); действие `expired` «Збирач не забрав команду»; автоматика не работает | сторожевые таймеры контроллера возвращают BESS (30 с) и сброс (60 с) | чип «Збирач не на зв'язку · {вік}», событие `CTRL-HEARTBEAT` |
| 3 | Контроллер ГРЩ не отвечает (Modbus) | Запись → `failed` («пристрій не відповідає»); входы несвежие → R-44 п.3: `warn`/`hold` | неизвестно; сторожевые таймеры | действие «не виконано», карточки `warn` |
| 4 | Местный режим (`remote=0`) | `blocked` для интентов; движок `hold` | не меняется | «Контролер у дистанційному режимі — не виконано», чип «автоматику призупинено» |
| 5 | Несвежие входы | Сценарий `warn`; `grid_kw` > `stale_hold_s` → `hold`; жёсткие проверки fail-closed | не меняется | «немає даних: {коди}» |
| 6 | Потеря результата транспорта (сборщик выполнил интент, `POST result` не дошёл, `td.command` стал `expired`) | Сборщик в API-25 отчитывается об окончательном состоянии действия по `idem`; Odoo принимает его как авторитетное (R-40 п.8) | соответствует результату | действие переходит `expired → done/failed` |
| 7 | Падение движка/сборщика во время принудительного режима | Сторожевые таймеры: BESS `valid_s` (автоматика 30 с, ручные — заданные оператором), `shed/valid_s` 60 с (сбросы и ограничение СЭС возвращаются в 100 %); КГУ, QS, уставка воздуха **не** имеют таймера (физические состояния) | BESS авто; нагрузки возвращены; КГУ/QS остаются | чип «Збирач не на зв'язку» |
| 8 | Частичный сбой шагов интента | Fail-safe (R-52 п.5), `failed` | безопасное (авто) | «Не виконано: {крок}» |
| 9 | Верификация не пройдена | Fail-safe, `failed` | безопасное | «Не підтверджено пристроєм» |
| 10 | Интент просрочен до выполнения | `rejected: expired` | не меняется | «Прострочено» |
| 11 | Ручное и автоматическое действия конфликтуют | Перекрытие оператора (R-44 п.4, R-52 п.8); событие `override` | как задал оператор | строка журнала «ручний режим BESS до {час}» |
| 12 | Невалидный конфиг | Плагин оставляет предыдущий валидный; `engine.reason="config invalid: …"`; событие `config` | не меняется | чип `warn` на экране |
| 13 | Расхождение часов (> 30 с между `server_time` и часами сборщика) | `expires_at` сравнивается со скорректированным временем; событие `config` `warn`; расчёты блоков 15 мин — по часам сборщика | — | событие в журнале |
| 14 | Отключён предохранитель во время работы | Исполнитель: остальные шаги отменяются (`failed` «Запис вимкнено під час виконання») + fail-safe, если запись ещё разрешена; движок → `off`: активного восстановления нет, возвращают сторожевые таймеры | постепенно авто | чип «автоматику призупинено» |
| 15 | Устройство отказало (`ack = 2`) | `failed` с причиной; сценарий — `warn` после 2 отказов | не меняется | причина в журнале |
| 16 | Превышена частота записей | `hold` на 5 мин, событие `failsafe` | не меняется; таймеры возвращают | чип «призупинено: частота записів» |
| 17 | Рестарт плагина | `Store` восстанавливает владение; сверка с устройством (R-44 п.9); `executing` интенты → `failed` (R-52 п.7) | не меняется | «рушій перезапущено» |
| 18 | Стоп-кран источника выключен | `WriteRefused` → как №14 | — | действие `blocked` «Запис вимкнено: джерело {code}» |

### R-54 Расписание и план дня (FR-53; M-34)

1. **Вход планировщика** `_td_plan_day(day)` (метод `td.energy.schedule.slot`): типовой профиль потребления `cons[96]` (кВт) и профиль СЭС `pv[96]` (кВт) по локальным индексам 15 мин — функции W1 R-28 (`td_energy/tools/forecast.py`: типовой день по дню недели, `forecast_weeks`/`forecast_min_days`); при нехватке истории (< `forecast_min_days`) — запасной план из сида (разряд 07:30–11:00, заряд от СЭС 11:00–16:00, разряд 16:00–17:30).
2. **Перестроение.** Для каждых суток горизонта (`plan_horizon_days`): удалить слоты `source in ('plan','scenario')` этих суток (по `date`), создать заново (п.3–п.6); `manual` не трогать; пересекающиеся `plan`-полосы, накрытые `manual`, обрезаются при выводе (п.7). Идемпотентно; запуск — `cron_td_energy_control_plan`, `post_init_hook`, кнопка «Перебудувати план», после изменения `enabled/params` сценариев.
3. **BESS (`plan`).** Разряд: интервалы 15 мин, где `cons − pv ≥ peak.limit_kw − peak.activate_margin_kw` → слить соседние (разрыв ≤ 30 мин), метка «розряд · пік» (для окна, заканчивающегося на границе смены, — «розряд · зміна»), `mode='discharge'`, `setpoint_kw = peak.bess_max_kw`; заряд: интервалы, где `pv − cons > self.export_max_kw` (длительностью ≥ 30 мин) → «заряд від СЕС», `mode='charge'`.
4. **КГУ (`scenario`).** Только при `chp.enabled`: интервалы, где `price_ok` по зонам тарифа, и ручные слоты `chp`; метка «пуск за ціною». При `chp.enabled = false` — без полос (макет).
5. **Выполнение слотов.** Слоты `executes` (`manual`, `resource ∈ {bess, chp}`) публикуются в конфиг (`slots[]`); шаг движка `slots`: в окне `bess`-слота с `mode='charge'` → запрос `bess` `{mode:1, setpoint_kw, until_soc: self.bess_target_soc_pct, valid_s:30}`, `mode='discharge'` → `{mode:2, setpoint_kw, until_soc: floor_soc, valid_s:30}`; приоритет ниже `peak`/`self` и ручного перекрытия. Слоты `chp` обрабатывает R-50. Остальные слоты (`plan`, `scenario`, `genset`, `charging`, `vent`, `light`) выполнения не имеют.
6. **Ночные полосы.** `night.enabled`: `vent` — «ніч {vent_pct} %» `[0, to]`, «день 100 %» `[to, from]`, «ніч {vent_pct} %» `[from, 24]`; `light` — «черговий» / «робочий» / «черговий» (`mode='duty'`/`'work'`); `night.enabled=false` — одна полоса «день 100 %» / «робочий» на все сутки. Окно через полночь разбивается на два слота (`time_to > time_from`).
7. **ДГУ (`genset`).** Если есть мост: из `adapters.schedule_info(gen)` (W1 ADP-07) слоты `mode='test'` на сутки (метка «тест»); иначе пусто.
8. **Вывод `get_schedule(day)`** (API-23): строки в порядке `bess, chp, vent, light, charging, genset` с названиями «BESS», «КГУ», «Вентиляція RoofVent», «Освітлення цеху», «Зарядна станція», «ДГУ»; `bars[]` — `{from, to, label, cls, source}`, отсортировано по `from`; `manual` перекрывает `plan` в конфликтном интервале (`plan` обрезается); `now` = текущие часы Киева как float (14,333 = 14:20).
9. **Сид** (post_init): `charging` — два `manual`-слота `mode='charge'` 00:00–06:00 и 22:00–24:00, метка «заряд», `weekdays='1111111'`; остальное — после первого прогона планировщика; всего ≥ 10 слотов на демо-БД.

### R-55 Правила рекомендаций и баннер «Выполнено» (FR-54; M-36; C-38)

1. **`_td_advice_rule_export_t2(now)`** → `EXPORT-T2`. Условия (все): минимальное значение `infra/totals/export_kw` за последние `export_advice_min` мин (по `td.reading`; запасное — `last_value` со `status='ok'` и свежим `last_ts`) `> self.export_max_kw`; `energy/cells/QS/state = open`; `infra/totals/pv_now ≥ 1`. Результат: `{code:"EXPORT-T2", dedup_key:"EXPORT-T2", level:"info", node_code:"T2", expires_in_min:60, title:"СЕС віддає {export} кВт у мережу через T2.", text:"Секційний вимикач QS вимкнено, і генерація СЕС більша за навантаження секції 2. Заряд BESS 50 кВт збереже до {until} приблизно {kwh} кВт·год на старт другої зміни.", actions:[{"code":"open_event","label":"Відкрити подію","kind":"link",…}, {"code":"charge_bess","label":"Зарядити BESS 50 кВт","kind":"control","class":"A","params":{"command_kind":"bess_charge","power_kw":50,"until":"{until}","soc_limit_pct":95}}, {"code":"qs_on","label":"Увімкнути QS…","kind":"control","class":"B","params":{"command_kind":"qs_close"}}]}`; `until` — ближайшее из `16:00`, `23:00`, которое позже `now + 30 мин` (Киев); `kwh = round(50·hours_until / 10)·10` (макет: «приблизно 80 кВт·год»); действие `charge_bess` не возвращается, если `bess_soc ≥ 95`.
2. **`_td_advice_rule_peak_risk(now)`** → `PEAK-RISK`: сценарий `peak` выключен, `grid_kw ≥ peak.limit_kw − peak.activate_margin_kw` непрерывно ≥ 2 мин; `level:"warn"`; действия: `enable_peak` (`scenario_toggle`, B), `discharge_bess` (`bess_discharge` 100 кВт, 60 мин, B); текст: «Імпорт {grid} кВт наближається до уставки {limit} кВт. Увімкніть «Зрізання піку» або розрядіть BESS.».
3. **`_td_advice_rule_chp_price(now)`** → `CHP-PRICE`: сценарий `chp` выключен; `grid_price − chp_cost ≥ 2·price_margin`; КГУ `chp_state = 0`, `permit = 1`, `gas ≥ min`; `level:"info"`; действия: `enable_chp` (`scenario_toggle`, B), `chp_start` (B); текст: «Газ дешевший за мережу: КГУ вигідно запустити ({grid_price} ₴ проти {chp_cost} ₴ за кВт·год).».
4. **Результат действия → рекомендация.** `td.energy.action` с `advice_id` в состоянии `done` → `advice._td_on_action_done(action)`: `action_done(note=result_text)` (`state='done'`). **Баннер «Выполнено»:** override `get_open()` — если открытой рекомендации нет и есть `td.energy.action` `origin='advice'`, `state='done'`, `finished_at ≥ now − undo_window_min`, `undo_available` — возвращает `{id, code, title, text, level:"info", state:"done", node_code, actions:[{"code":"undo","label":"Скасувати","kind":"control","class":<класс обратного вида>,"params":{"command_kind":"undo","action_id":<id>},"enabled":true}]}` (`title/text`: BESS — «BESS заряджається {power_kw} кВт.» / «Експорт через T2 усунено, до {until} накопичиться ≈ {kwh} кВт·год.»; QS — «QS увімкнено.» / «Секції працюють разом, генерація СЕС іде на навантаження заводу.»). После `undo` или истечения окна баннер исчезает.
5. Правила выполняются `cron_td_energy_advice` (W1, 5 мин) через реестр `_td_advice_rule_*`; каждое ≤ 1 с; исключение правила логируется и не останавливает остальные; без `read_enabled` не действуют.
6. **Совместимость с рекомендациями W3.** Действия `kind='control'` из правил W3 (`td_energy_resources`) несут `params={"intent": <ключ>}` вместо W1-формата `params.command_kind`. `prepare` принимает такой ключ как `kind` и разворачивает через константу `ADVICE_INTENT_ALIASES` (модуль `models/td_energy_control.py`, M-35): `vent_night_mode` → `scenario_toggle` `{scenario:'night', enabled:true}`; `pv_self_consumption` → `scenario_toggle` `{scenario:'self', enabled:true}`; `air_pressure_setpoint` → `air_setpoint` (значение — `params.setpoint_bar`, иначе подставляется `current_bar` и оператор задаёт значение в диалоге); `heat_schedule_shift` — в W2 нет вида команды (графики отопления не управляются) → `UserError("Команда «heat_schedule_shift» не підтримується в цій версії.")`, клиент показывает уведомление, действие не создаётся. Класс определяется видом (`class: null` в действии W3 допустим); `advice_id` передаётся как обычно. Контракт расширяется без изменений W1/W3 (риск R9).

### R-56 Журнал и отмена (FR-52; D-19, D-42)

1. **Состав.** `get_journal` (API-28) объединяет: (а) `td.energy.action` в состояниях `awaiting_second`, `queued`, `sent`, `executing`, `done`, `failed`, `blocked`, `expired` (`prepared`, `cancelled` не показываются); (б) `td.energy.event` за 24 ч с `kind in ('pfc','control')`. Порядок — по времени убывания; пагинация `before_id` (единый счётчик: id действия или `-id события`).
2. **Строки событий.** `what` = «Заявка ТО», если у события есть заявка (`maintenance_request_id`/ссылка W1), иначе `title`; `detail` = `detail` или `title`; `who` = «автоматика»; `result` = «створено» (есть заявка) / «виконано» (`resolved`) / «активно»; `ref` = `maintenance.request`.
3. **Строки автоматики.** `_td_log_auto(ev)` создаёт `td.energy.action` (`origin='auto'`, `kind_code='auto_<scenario>_<kind>'`, `state='done'`, `idem=ev.event_id`, `summary`, `detail=ev.text`, `actor_text='сценарій «{Пік|Самоспоживання|PFC|Ніч|Резерв|КГУ}»'`, `result_text='виконано'`); `summary` по сигналу: BESS — «BESS · розряд/заряд/зупинка», КГУ — «КГУ · пуск/зупинка», сброс — «Скидання · {name}», `night` — «Вентиляція · нічний/денний режим», иное — по `ev.kind`. Дедупликация по `event_id`; одинаковые события ≥ 60 с друг от друга.
4. **Чипы результата:** `done` → «виконано» (`ok`); `done`+`config`+`!applied` → «збережено, очікує збирач» (`info`); `queued/sent/executing` → «виконується» (`info`); `awaiting_second` → «очікує 2-го підтвердження» (`info`); `failed` → «не виконано» (`bad`); `blocked` → «заблоковано» (`bad`); `expired` → «прострочено» (`muted`).
5. **`undo_available`** (вычисляется): `state='done'`; есть `undo_kind`; `finished_at ≥ now − undo_window_min`; нет более позднего действия на том же `resource` в `queued…done`; `undone_by_id` пусто.
6. **`undo(action_id)`**: создаёт `prepared`-действие `origin='undo'`, `undo_of_id`, вид = `undo_kind`, `params = undo_params` (уставка воздуха — предыдущее значение; `scenario_toggle` — обратное `enabled`; `scenario_params` — предыдущие `params`; `shed_reorder` — предыдущий порядок; для `qs_*`/`bess_*`/`chp_*` — без параметров), `summary = "Скасування: {summary оригинала}"`; далее обычный `confirm` (права по классу обратного вида); успех → `undone_by_id` оригинала.
7. Журнал не удаляется (ротация — Q-33).

### R-57 Слой «Энергетика в 3D»: правила payload

Описано в разд. 8.4.2 (структура `energy.layer`, состояния, выбор `scene`, маркеры, киоск, размер). Дополнительно: `thresholds` берутся из `td.energy.load_warn_pct/_alarm_pct` (W1 §5.1), поэтому цвет узла в 3D совпадает с Пультом (AC-284); провайдер не пишет в БД и работает с правами пользователя (`_f3d_group`), чтение узлов/событий — `sudo()` только на чтение с отсечением полей по описанию.

### R-58 «Відкрити в 3D» и подсветка узла

Описано в разд. 8.4.4 (`action_td_open_3d`, параметры `f3d_viewer.action`, порядок `applyParams`, точки входа).

### R-59 Эмулятор: реакции моделей

Описано в разд. 8.2 (регистры 5.6 и таблица моделей). Дополнительные правила: (1) `cmd`-регистры (QS, КГУ) самоочищаются в следующем тике; игнорирование команды при `ctl_remote=0` даёт `ack=2`; (2) сторожевые таймеры считаются по симулированному времени мира (`world.clock`), поэтому ускорение времени (`POST /sim/v1/time`) ускоряет и их; (3) после `POST /sim/v1/reset` все флаги управления возвращаются к значениям по умолчанию (`bess_mode=0`, `chp_run=False`, `qs_closed=False`, лимиты 100 %, уставка воздуха 7,00, `pfc_mode=1`, `pfc_cos_target` из настроек мира, `ctl_remote=1`).

### R-60 Безопасность: что не управляется и как это обеспечено (FR-58; AC-165)

1. **Не управляются вообще:** пожарная сигнализация, спринклеры, дымоудаление, молниезащита, эвакуационное и аварийное освещение, СКУД, защита людей, защита станков и производственные остановки (`workcenters/…`), охранные системы, ИТ и связь; автоматические выключатели фидеров (QF), релейная защита; полное отключение «критичных» нагрузок (`is_critical`) — запрещено (частичный/условный сброс приоритетных критичных узлов — только в `peak`, R-51).
2. **Три уровня запрета:** (а) Odoo: `td.signal` модуля `energy_control` не может иметь код с префиксами `fire/`, `evacuation/`, `sprinklers/`, `smoke/`, `lightning/`, `access/`, `workcenters/`, `security/`, `yard/` или источник модулей `fire_safety`, `access`, `machine_connect` (M-38); `td.energy.shed.item` не принимает узел `is_critical` и производственные станки без условия цикла (M-30); (б) конфиг: сборщик пишет **только** в сигналы, перечисленные в `signals`, `shed[].signal`, `bms.*` API-24; (в) сборщик: константа `DENY_PREFIXES` — попытка записи в код с запрещённым префиксом → `WriteRefused("заборонено: {префікс}")` и событие `interlock`, даже если он попал в конфиг.
3. Пожарная тревога (`fire_state = alarm`) — **вход**: приостанавливает записи ресурсов `vent`/`light` (R-44 п.8) и блокирует `light_*`/`vent_*` (`no_fire_alarm`); движок никогда не «сбрасывает» её и не взаимодействует с противопожарной логикой.
4. QS — единственная коммутационная операция, только класс B, только при `remote=1`, блокировке АВР и токе ≤ 80 % номинала (R-41); дистанционное управление QS на объекте — Q-27.
5. В документации и UI — оговорка D-26/информационная полоса UI-12.

### R-61 Стенд и демо-данные (E-11; FR-67)

1. `hooks._td_enable_stand(env)` (вызывает менеджер через `odoo-bin shell`; **не** из `post_init_hook`): `td.telemetry.write_enabled=True`, `td.energy_control.write_enabled=True`, `td.energy_control.automation_enabled=True`, `td.energy_control.remote_switching_enabled=True` (D-46); `write_enabled=True` для источников `MB-U73-SWB-CMD`, `ENERGY-CTL` и для сигналов `module='energy_control'` с R/W и W (`qs/cmd`, `pfc/*`, `bess/{mode,setpoint_kw,until_soc,valid_s}`, `chp/cmd`, `air/setpoint_bar`, `pv/limit_pct`, `shed/*`, `intent`); для целей BMS ночного режима — соответствующие сигналы и `td.bms.write_enabled`; возвращает перечень изменений. Сборщик: `F3D_WRITE_ENABLED=true`, `F3D_COMMANDS_POLL_S=2`; эмулятор: `SIM_WRITE_ACCEPT=1`.
2. Приёмка на стенде (ТК-19…ТК-28): воспроизведение макета — `export_demo` (экспорт 26 кВт, BESS 82 %, QS открыт), рекомендация EXPORT-T2 → «Зарядити BESS 50 кВт» → диалог → выполнено → «Скасувати»; QS: диалог с проверкой «блокування АВР — гаразд», второе подтверждение; `peak_load` → BESS → КГУ → сброс; `mains_loss` → резервное питание; ночной режим на границе `23:00` (время мира `POST /sim/v1/time`); `pfc_step_fault` остаётся сценарием W1.
3. Генератор истории (W1 R-36) уже наполняет профиль для плана (R-54).

### R-62 Шина `td_energy_control` и обновление клиентов (A-41)

Строковый канал `td_energy_control`, тип `td_energy_control/update`, сообщение `{"kinds": ["action"|"scenario"|"engine"|"schedule"|"shed"], "ts": iso_utc}` без данных; `tools/bus.py` модуля копирует механику W1 R-33 (накопление в `precommit`, `_sendone` в `postcommit`, throttle `td.energy.bus_throttle_s` на воркер, сбой шины глотается); кто тикает: `td.energy.action._td_close`/переходы (`action`), `scenario._td_apply_change`/`_td_engine_update` (`scenario`), `control.state._td_report` (`engine`), планировщик (`schedule`), изменения `shed.item` (`shed`). Клиент: `kind → части get_control` (`action` → `journal`, `pending`; `scenario` → `scenarios`; `engine` → `engine`; `schedule` → `schedule`; `shed` → `shed`), дебаунс 2 с, резервный опрос 30 с. Дополнительно — тики W1 `td_energy.tools.bus` (`state`, `advice`) после действий над QS/BESS/КГУ и рекомендациями, чтобы обновлялся Пульт.

### R-63 Время и часовой пояс

Хранение — UTC naive; «Киев» — `Europe/Kyiv` (`tools/dates.py` W1, `zoneinfo` в плагине). `time_from/time_to` слотов, окна `night`, зоны тарифа, `bess_charge.until` — **настенное** местное время. Сутки 23/25 ч (переход DST): шкала `get_schedule` остаётся 00…24; ночное окно следует за настенными часами; `valid_s` для `bess_charge` = разность абсолютных UTC-моментов (не часов на шкале); блок спроса 15 мин (R-45) — по UTC-эпохе; тики DST не создают двойных/пропущенных блоков. День недели слотов и `night.days` — локальный (1 = понедельник).

### R-64 Производительность и объёмы

`get_control` ≤ 400 мс и ≤ 40 SQL (один `search_read` сигналов управления, один поиск действий/событий для журнала); `prepare` ≤ 300 мс, `confirm` ≤ 300 мс; API-24 ≤ 200 мс (ETag-кеш в `state`, пересчёт не чаще 1 раза в минуту и после `bump`); API-25 ≤ 300 мс для 100 действий и 200 событий; тик движка ≤ 50 мс p95, память плагина ≤ 60 МБ, записей в устройства ≤ 30/мин; объёмы: `td.energy.action` ≈ 100–300/сутки (события автоматики троттлятся ≥ 60 с), ≈ 70 000/год, индексы `(state, create_date)`, `(kind_code, state)`; `td.command` ≈ 1 на действие; `Store` ≤ 1 МБ.

### R-65 Некорректные данные и конфиг

(1) Odoo: `ValidationError` для `params` сценариев/слотов/приоритетов (M-29…M-34); API-24 всегда отдаёт валидный JSON по схеме (пустые массивы вместо `null`); (2) сборщик: неизвестные ключи в `scenarios.*.params` игнорируются с предупреждением, отсутствующие — дефолты кода; значения вне границ — граница кода (R-41 п.6, R-44 п.6) и событие `config`; `slots` с `from ≥ to` отбрасываются; `shed[]` с отсутствующим сигналом пропускается; (3) интент с неизвестным `kind`/`v` → `rejected`; (4) чтение назад с `q != good` считается отсутствующим значением.

### R-66 Миграция и деинсталляция

Новая установка (первая версия `19.0.1.0.0`): `post_init_hook` (разд. 1, 5.6) — идемпотентный; миграций нет. Повторный `-u` не меняет количеств (AC-235). **Деинсталляция (D-45):** архивных таблиц нет — модуль удаляется вместе со своими данными, как любой модуль Odoo. `uninstall_hook` удаляет служебные данные (сигналы и источники `energy_control`/`energy_ctl`, кроны, параметры), сбрасывает флаги `write_enabled`/`automation_enabled`/`remote_switching_enabled` и публикует пустую конфигурацию; журнал `td.energy.action`, сценарии, приоритеты сброса, слоты, блокировки и виды команд удаляются вместе с моделями. Повторная установка создаёт данные заново (`post_init_hook`). `td_energy` после удаления модуля: `meta.control_available=false` (W1 `_td_control_available` смотрит на `ir.module.module`), кнопки `kind='control'` в Пульте исчезают (обработчик не зарегистрирован; D-02).

### R-67 Тест ДГУ через адаптер (`td_genset_factory3d`; FR-66, FR-69; ADP-12)

1. Исполнитель `genset` (R-40 п.6): `tools/genset_link.start_test()` → `adapters.td_genset.start_test(gen, 'idle', user)`; `gen` — первый активный `td.genset` (`adapters.generators(env)`); генератора нет → `blocked` «Генератор не налаштовано».
2. Проверки диалога (Odoo): `genset_fuel` (мягкая, ≥ `min_pct`), `genset_heater` (мягкая, `coolant_c ≥ 30` или `unknown`), `no_island` (жёсткая), `genset_idle` (жёсткая: `not running`, `not test_running`, `mains_ok`) — значения из `adapters.test_facts`.
3. Результат: `UserError` `td_genset` (например, «Тест уже йде.») → действие `blocked` с текстом; успех → `done`, `result_text="Тест ДГУ прийнято td_genset: {minutes} хв"`, `ref` на запись `td.genset`; фактический пуск и подтверждение — конечный автомат `td.genset.command` (до `done`/`failed` с тревогой `td_genset`) — вне журнала W2.
4. Класс B; права — `group_td_energy_manager` + второе подтверждение или `chief`; `td_genset` не меняется.

## 10. Состояния и переходы

| Объект | Состояния | Переходы (кто) |
|---|---|---|
| `td.energy.action.state` | `prepared → awaiting_second → queued → sent → executing → done`; `prepared/awaiting_second → expired/cancelled`; `queued/sent/executing → failed/blocked/expired`; `prepared/awaiting_second/queued → blocked`; `expired → executing/done/failed/blocked` (только отчёт сборщика по `idem`) | `prepare`, `confirm`, `confirm_second`, `_td_enqueue`, `td.command` (M-37), API-25, `_cron_expire`, `cancel` |
| `td.command.state` (команды W2) | `queued → sent → done/failed/expired/cancelled` | коллектор (`GET commands`, `POST commands/result`), `_cron_expire` `td_telemetry` |
| `td.energy.scenario.engine_state` | `unknown ⇄ off/armed/active/warn` | API-25 (движок); `unknown` — нет отчёта `2·heartbeat_stale_s` |
| `td.energy.control.state.engine_mode` | `unknown/off/hold/auto` | API-25 |
| Интент в сборщике | `accepted → executing → done/failed`; `rejected/blocked` (без выполнения) | `Executor` |
| Режим движка | `off ⇄ auto ⇄ hold` | R-44 п.1 |
| Этап `peak` | `idle → bess → chp → shed → idle` | R-45 |

## 11. Обработка ошибок

- Все публичные методы `td.energy.control` на входе: группа; `AccessError("Немає доступу до Енергетики.")`; части `get_control` изолированы — ошибка одной (`scenarios`, `shed`, `commands`, `schedule`, `journal`) → `{"error": "…"}` в этой части, остальные отдаются, `_logger.exception` (UI: «Не вдалося завантажити: {частина}»).
- Сигналы несвежие/отсутствуют → проверки `unknown`, `null` в значениях; методы не бросают исключений из-за отсутствия данных.
- Гонки: `confirm`/`confirm_second` — `FOR UPDATE`; два «вторых» подтверждения — проиграл второй (`UserError("Дія вже підтверджена.")`).
- Часовые пояса — R-63. Шина недоступна — глотается (резервный опрос).
- Ошибки сборщика — таблица R-53; тексты на украинском, без внутренних путей и токенов.
- HTTP: тело JSON-конверт `{"error": {"code","message"}}` (как `td_telemetry`).

## 12. Acceptance Criteria

Колонка «Тип»: UT (юнит-тест Odoo), UT-JS (hoot), UT-PY (pytest коллектора/плагина/эмулятора, без Odoo), TC (стенд), MAN (ручная проверка). Все тесты Odoo — `post_install`, `-at_install`, тег `td`. Фикстуры — разд. 13.0. Колонка «FR» — требование ARCH §1.3. **Итого: AC-159…AC-308 = 150 критериев** (td_energy_control + плагин + эмулятор + мост 3D: AC-159…AC-274, AC-282…AC-308; `td_genset_factory3d` ADP-12: AC-275…AC-277; `td_viewer3d` R-26: AC-278…AC-281).

### 12.1 Сценарии и конфигурация — AC-159…AC-170

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-159 | FR-46 | Given чистая установка; Then `td.energy.scenario` имеет ровно 6 записей `peak,self,pfc,night,backup,chp`; `enabled`: peak, pfc, night, backup — `True`, self, chp — `False`; `description` ровно как в макете (5.2); `create`/`unlink` не-администратором → `AccessError` | UT |
| AC-160 | FR-46 | Given `scenario.params`; When `limit_kw=50`, или `night.from="25:00"`, или неизвестный ключ, или `days=[0,8]`; Then `ValidationError` «Сценарій {name}: параметр {key} — …»; значения по умолчанию — валидны для всех 6 сценариев | UT |
| AC-161 | FR-47 | Given `engine_state='armed'`, `facts.margin_kw=402` для `peak`; When `_td_state_text()`; Then «Чергування · запас 402 кВт», `state_kind='arm'`; `enabled=False` → «Вимкнено», `off`; `pfc` `warn` с `fault="PFC-2 ступінь 3"` → «Збій: PFC-2 ступінь 3», `warn`; `night` `armed` с `next_run="23:00"` → «Наступний запуск о 23:00»; `self` `active`, `bess_kw=26` → «Активний · заряд BESS 26 кВт»; `backup` `armed` `fuel_pct=78` → «Готовий · паливо 78 %»; нет отчёта ≥ `2·heartbeat_stale_s` → «Немає даних від рушія» | UT |
| AC-162 | FR-47 | Given сид; Then `chips()` воспроизводит макет: peak «уставка 760 кВт · 95 %», «прогноз 15 хв»; self «експорт ≤ 20 кВт», «BESS до 95 %»; pfc «ціль cos φ 0,95», «крок 35 квар»; night «23:00–06:30», «RoofVent 30 %», «16 °C»; backup «АВР → ДГУ», «критичні 180 кВт»; chp «мін. робота 2 год», «ціна газу 19,80 ₴/м³» | UT |
| AC-163 | FR-47, FR-53 | Given manager; When `scenario.write({'enabled': True})` без контекста действия → `AccessError`; When `prepare('scenario_toggle', {scenario:'peak', enabled:False})` + `confirm` (chief) → `enabled=False`, `config_version` = текущая версия состояния, `changed_by`; обратное изменение через `undo` | UT |
| AC-164 | FR-57 | Given `state`; When дважды `bump()` (также два параллельных UPDATE) → +2 без дублей; изменение `scenario.params`, `shed.item.sequence`, `interlock.params`, слота `executes`, `td.energy.cos_phi_target` → `config_version` растёт; изменение `engine_facts`/`engine_ts` — нет | UT |
| AC-165 | FR-58 | Given сигнал `module='energy_control'`; When код `fire/panel/x`, `workcenters/SAW-1/x`, `access/x`, или источник `module='fire_safety'`; Then `ValidationError` «Сигнал {code}: керування цією системою заборонене.»; `module='energy'` + `write_enabled=True` → `ValidationError` (W1 AC-81 действует) | UT |
| AC-166 | FR-57 | Given коллектор с токеном; When `GET /td/energy/automation/config`; Then 200 JSON со всеми ключами 7.3 (`schema=1`, `config_version`, `etag`, `flags`, `engine`, `plant`, `scenarios`, `shed`, `never_shed`, `slots`, `tariff`, `bms`, `signals`, `inputs`, `interlocks`, `limits`) и заголовком `ETag`; повторный с `If-None-Match` → 304; после `bump()` → 200 с новым `etag`; без токена/с неверным → 401; выключенный коллектор → 403; `POST` → 405 JSON; ответ не содержит `cost`, токенов, паролей | UT |
| AC-167 | FR-57 | Given конфиг; Then `etag` не зависит от `server_time`/порядка ключей; изменение `limit_kw` меняет `etag`; размер ответа на демо-данных (6 сценариев, 5 сбросов, ≤ 40 слотов, 25 RoofVent) ≤ 64 КБ | UT |
| AC-168 | FR-47 | Given `td_bms` с 25 установками `roofvent` (`mode_signal_id`, `sp_night_signal_id`) и группами освещения; Then `bms.night.vent` имеет 25 элементов с `mode_signal`, `bms.night.light` — группы с `scene_signal`, `aisle=true` только для `fixture_kind='highbay_rack'`; `light_break` не содержит `aisle`-групп; отсутствующие сигналы → пустые массивы | UT |
| AC-169 | FR-57 | Given `scenario_toggle` выполнен; When до `POST state` → `applied=False` (чип «Очікує застосування»); после `POST state` с `config_version_applied ≥ config_version` → `applied=True`; `state.applied_version` не уменьшается | UT |
| AC-170 | FR-51 | Given `get_control().engine`; Then heartbeat свежий + `mode=auto` → `level='ok'`, `label="Контролер ГРЩ і збирач на зв'язку · HH:MM"`; `mode=hold` → `warn`; heartbeat старше `heartbeat_stale_s` → `bad`, «Збирач не на зв'язку · {вік}»; `automation_enabled=False` → `warn`, «автоматику призупинено» | UT |

### 12.2 Приоритеты сброса — AC-171…AC-176

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-171 | FR-48 | Given сид; Then 5 строк в порядке макета (CHARGING, RV-ALL, DRY-1, COMPRESSOR, LP-1), `kw_reducible` 48/60/17/37/12, `how` ровно: «відкласти заряд до 30 хв», «знизити до 70 %», «пауза до 20 хв, без втрати циклу», «вимкнути, тиск ≥ 6,5 бар», «знизити до 50 %» | UT |
| AC-172 | FR-48, FR-58 | Given `shed.item`; When узел `is_critical` с `action='off'` и `condition='none'` (с `reduce` или с условием — разрешено, `critical=True`); или `DRY-1` с `condition≠no_active_cycle`; или вторая активная строка на тот же узел; Then `ValidationError` (или `IntegrityError` для дубля) с текстами M-30; `kw_reducible > p_inst_kw` — только предупреждение | UT |
| AC-173 | FR-48 | Given `prepare('shed_reorder', {order:[…]})`; When `confirm` (chief) → порядок изменён, `config_version` +1; manager → `awaiting_second` и порядок не изменён до второго подтверждения; обратный `undo` восстанавливает порядок | UT |
| AC-174 | FR-48 | Given `get_control().shed`; Then `sum_kw=174`; `never` содержит 5 фраз макета; `never_nodes` = коды узлов `is_critical` без активной строки приоритета; `limit_kw=760` | UT |
| AC-175 | FR-57 | Given API-24; Then `shed[]` по `seq`, каждый элемент имеет `signal=energy_control/shed/<node>/limit_pct`; неактивные не отдаются; `critical` = `node.is_critical`; `never_shed` = критичные узлы без активной строки + `NEVER_SHED_CODES` | UT |
| AC-176 | FR-48, FR-53 | Given роли; When `create/write/unlink` `shed.item`: manager → `AccessError`; chief → разрешено и создаёт `td.energy.action` (`kind_code='shed_edit'`, `cls='B'`, `state='done'`) и `bump()`; user → `AccessError` | UT |

### 12.3 Виды команд, поток, классы и права — AC-177…AC-194

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-177 | FR-49 | Given сид; Then 16 видов; 8 `tile=True` в порядке макета (qs_close, bess_charge, bess_discharge, chp_start, genset_test, light_break, vent_eco, air_setpoint); класс A — bess_charge, bess_stop, light_break, light_restore, vent_eco, vent_restore; остальные B; `executor/resource/checks` по 5.3 | UT |
| AC-178 | FR-49, FR-53 | Given `get_control().commands`; Then 8 плиток с `label/sub` макета («Заряд BESS 50 кВт» / «до 16:00 або 95 %», «Освітлення цеху · сценарій «Перерва»» / «50 % на 30 хв», …); user → `enabled=False`, `disabled_reason` «Немає прав: потрібна роль «Енергетик»»; `write_enabled=False` → `enabled=False` для `intent`/`genset` | UT |
| AC-179 | FR-50 | Given manager; When `prepare('qs_close')`; Then ключи ответа 7.2, `ttl_s=60`, `checks` в порядке вида, `needs_second=True` (chief → `False`), токен ≥ 32 символов; в БД только `token_hash` (sha256), токена нет | UT |
| AC-180 | FR-50 | Given `prepare`; When повтор ≤ 5 с тем же пользователем/`kind`/`params`; Then тот же `action_id`, новый токен, старый недействителен; после 5 с — новая запись | UT |
| AC-181 | FR-49 | Given `bess_charge`; When `power_kw=500`, или `until` в прошлом, или `soc_limit_pct=40`; Then `ValidationError`/`UserError` («параметр … поза межами 1…100 кВт») | UT |
| AC-182 | FR-50, FR-55 | Given класс A, manager; When `confirm(token)`; Then действие `queued`; создана **одна** `td.command` (`signal=energy_control/intent`, `payload.v=1`, `payload.kind='bess_charge'`, `origin='energy'`, `expires_at ≈ now+120 с`, `energy_action_id`); повторный `confirm` того же токена возвращает то же состояние без новой команды | UT |
| AC-183 | FR-50 | Given токен; When чужой пользователь → `AccessError`; просроченный → действие `expired` + `UserError`; неизвестный → `UserError`; после `cancel` → `UserError` | UT |
| AC-184 | FR-53 | Given класс B; When manager `confirm` → `awaiting_second`, `second_expires_at ≈ now+600`, `td.command` нет; chief → сразу `queued` | UT |
| AC-185 | FR-53 | Given `awaiting_second`; When тот же пользователь → `UserError`; другой manager → `queued`, `second_by`; view-only → `AccessError`; другому chief разрешено; после `second_expires_at` → `expired` | UT |
| AC-186 | FR-53 | Given `awaiting_second`; Then `mail.activity` ≤ 10 manager-ам, кроме инициатора; закрывается при выполнении/истечении; `get_control().pending` показывает действие только manager-ам, `can_confirm_second=False` для инициатора | UT |
| AC-187 | FR-50 | Given действие на ресурс `bess` в `queued/sent/executing`; When `confirm` нового действия на `bess`; Then оно `blocked` «Для ресурсу «bess» уже виконується дія …» | UT |
| AC-188 | FR-55 | Given `td.command`; When состояние `sent` → действие `sent`; `done` с `result_data.accepted=true` → `executing`; `done` с `accepted=false,state=blocked` → `blocked`; `state=rejected` → `failed`; `failed` → `failed`; `expired` → `expired`; `cancelled` → `cancelled` | UT |
| AC-189 | FR-55 | Given API-25 `actions[]`; When `done` → `finished_at`, `result_text`, `bus` `action`; действие с `advice_id` → `advice.state='done'`; повтор того же состояния — без эффекта; состояние «назад» → `rejected: already_final`; действие `expired` + отчёт `done` по `idem` → `done` | UT |
| AC-190 | FR-47, FR-57 | Given `scenario_toggle`; When `confirm`; Then сразу `done`, `config_version` увеличен, `applied=False`, `result_text` «збережено, очікує збирач»; после отчёта сборщика — «виконано» | UT |
| AC-191 | FR-50 | Given `cancel(token)`; Then `prepared` → `cancelled`; повтор идемпотентен; `queued` → `td.command` `cancelled` и действие `cancelled`; `executing` → `UserError` | UT |
| AC-192 | FR-58 | Given `td.energy_control.write_enabled=False`; When `prepare('qs_close')` → `UserError` «Керування вимкнено…»; When `write_enabled=True`, но `write_enabled` источника `ENERGY-CTL`/сигнала `False` → `confirm` даёт `blocked` «Запис вимкнено: …», `td.command` не создана | UT |
| AC-193 | FR-55 | Given `td.command.create` с `origin='energy'`; When вне модуля (без контекста и `energy_action_id`) → `UserError`; без группы менеджера телеметрии и не `sudo` → `AccessError` (существующее правило) | UT |
| AC-194 | FR-66 | Given без моста `td_genset_factory3d`; Then `genset_test.available=False`, причина «Не встановлено міст td_genset_factory3d», `prepare` → `UserError`; с мостом — `available=True` | UT |
| AC-309 | FR-58 | Given `td.energy_control.remote_switching_enabled=False` (D-46); When `prepare` для `qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`; Then `UserError` «Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled…»; те же действия, подготовленные до выключения флага, не проходят `confirm`/`confirm_second`; `get_control().commands[]` для них `enabled=false` с причиной; `bess_charge`, `bess_stop`, `chp_stop`, `light_*`, `vent_*`, `air_setpoint`, `scenario_*`, `shed_reorder` не затронуты | UT |
| AC-310 | FR-58 | Given флаг `True`; Then `prepare('qs_close')` проходит как в AC-177…AC-194; `API-24 flags.remote_switching_enabled` равен значению параметра и меняет ETag; `neutralize.sql` и новая установка без demo дают `False`; demo-данные и `_td_enable_stand` дают `True` | UT |

### 12.4 Реестр блокировок — AC-195…AC-204

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-195 | FR-51 | Given Odoo-реализация; When золотые случаи R-41 п.5 для `controller_remote`, `no_island`, `ats_parallel_lock`, `data_fresh`; Then ожидаемые `ok/fail/unknown` | UT |
| AC-196 | FR-51 | When `qs_current_ok`: `p1=150,p2=100,cos=0,95` → `ok`, подпись «≈ 40 А з 1600 А»; `p1=1700,p2=0` → `fail`; QS уже `closed` → `ok` | UT |
| AC-197 | FR-51 | When `bess_ok`, `bess_soc_lt_limit` (82<95 ok; 95 fail), `bess_reserve_kept` (82 %, 100 кВт, 60 мин → 56,2 ok; 50 % → 24,2 fail), `bess_temp_ok` (24 ok, 41 fail, — unknown) | UT |
| AC-198 | FR-51 | When `chp_ready` (0 ok; 1/2/3 fail), `chp_gas_pressure` (2,10 ok; 0,80 fail), `chp_permit` (1/0/—), `chp_min_run` | UT |
| AC-199 | FR-51 | When `air_setpoint_min` (6,5 ok; 6,3 fail; 8,6 fail), `aisle_lux_ge` (80 ok; 60 fail; — unknown), `co2_lt` (620 ok; 1200 fail), `genset_fuel`, `genset_idle`, `no_fire_alarm` (нет сигнала → ok «не підключено») | UT |
| AC-200 | FR-51 | Given комбинации `hard/fail_closed/state`; Then `blocked` по R-41 п.3: `hard`+`fail` → блок; `hard`+`unknown`+`fail_closed` → блок; `hard`+`unknown`+`¬fail_closed` → не блок; мягкая `fail` → не блок; `where='collector'` → `unknown` «перевіряє збирач» без блока | UT |
| AC-201 | FR-51 | Given сигнал с `last_ts` старше `max(3·period_s, 60 с)` или `status='stale'`; Then значение `None` → `unknown` | UT |
| AC-202 | FR-51 | Given `td.energy.interlock`; When `code` неизвестен → `ValidationError`; `params` меняет не-админ → `AccessError`; админ → запись `interlock_param` в журнале и `bump()` | UT |
| AC-203 | FR-51 | Given `lock=0`; When `prepare('qs_close')` → `blocked=True`, `blocked_reason` «Блокування паралельної роботи T1 і T2 від АВР — не виконано»; `confirm` → действие `blocked`, `td.command` не создана | UT |
| AC-204 | FR-51 | Given `light_break`; When lux-сигналов нет → `aisle_lux_ge='unknown'`, `blocked=False`; `fire/panel/state=alarm` → `no_fire_alarm='fail'`, `blocked=True` | UT |

### 12.5 Журнал и отмена — AC-205…AC-210

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-205 | FR-52 | Given действия в разных состояниях; When `get_journal`; Then убывание по времени; `prepared`/`cancelled` отсутствуют; строка имеет `what/detail/who/result/result_kind` по D-19; `before_id` даёт следующую страницу; `limit` ≤ `journal_limit` | UT |
| AC-206 | FR-52 | Given событие `kind='pfc'` с заявкой ТО; Then строка «Заявка ТО» · деталь события · «автоматика» · «створено», `ref` на `maintenance.request` | UT |
| AC-207 | FR-52, FR-68 | Given `events[]` API-25; When `_td_log_auto(ev)`; Then запись `origin='auto'`, `actor_text='сценарій «Пік»'`, `summary` «BESS · розряд», `result_text='виконано'`; повторный `event_id` игнорируется | UT |
| AC-208 | FR-52, FR-54 | Given выполненная `bess_charge`; When ≤ 15 мин → `undo_available=True`; `undo(id)` → `prepared`-действие `bess_stop`, `origin='undo'`, `undo_of_id`; после `done` у оригинала `undone_by_id`, `undo_available=False`; > 15 мин или новое действие на `bess` → `False` | UT |
| AC-209 | FR-52 | When `undo` для `qs_close` → `qs_open` (класс B), `air_setpoint` → возврат `current_bar`, `scenario_toggle` → обратное `enabled`, `scenario_params` → предыдущие `params`, `shed_reorder` → предыдущий порядок | UT |
| AC-210 | FR-52 | Given действие; Then чаттер содержит «Підготовлено», «Підтверджено», «Результат»; форма `td.command` показывает `energy_action_id` (V-43) | UT |

### 12.6 Расписание — AC-211…AC-216

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-211 | FR-53 | When `get_schedule()`; Then 6 строк в порядке «BESS», «КГУ», «Вентиляція RoofVent», «Освітлення цеху», «Зарядна станція», «ДГУ»; `now` — часы Киева float; `bars[]` отсортированы по `from`, `0 ≤ from < to ≤ 24` | UT |
| AC-212 | FR-53 | Given история `_td_backfill`; When `_td_plan_day`; Then BESS-полосы `discharge`/`charge` по R-54 п.3 в пределах 0…24; без истории (< `forecast_min_days`) — запасной план (07:30–11:00 разряд, 11:00–16:00 заряд, 16:00–17:30 разряд) | UT |
| AC-213 | FR-53 | Given `night.enabled`; Then `vent`: «ніч 30 %» 0–06:30, «день 100 %» 06:30–23:00, «ніч 30 %» 23:00–24; `light`: «черговий»/«робочий»/«черговий»; `night.enabled=False` — одна полоса; `chp.enabled=False` → строка КГУ пуста, `True` → полосы по цене | UT |
| AC-214 | FR-53 | When слот `time_to ≤ time_from` → `ValidationError`; `manual`-слот создаёт/меняет не-chief → `AccessError`; chief → действие `schedule_edit` (B) и `bump()` | UT |
| AC-215 | FR-53 | Given `manual`-слот BESS в окне `plan`; Then в выводе `plan` обрезан; `executes=True` только для `manual` `bess/chp`; `slots[]` конфига содержит только `executes=True`, `active` | UT |
| AC-216 | FR-53 | When `_td_plan_day` дважды; Then то же количество слотов; `plan` старше 2 суток удаляются; сутки 25 ч (DST) не дают слотов вне 0…24 | UT |

### 12.7 Рекомендации — AC-217…AC-222

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-217 | FR-54 | Given `export_kw` > 20 не менее 5 мин, `QS=open`, `pv_now ≥ 1` (14:20); When `_cron_advice`; Then `EXPORT-T2` с `title` «СЕС віддає 26 кВт у мережу через T2.», `text` макета (`until=16:00`, «приблизно 80 кВт·год»), действиями `open_event`, `charge_bess` (control, A), `qs_on` (control, B); QS `closed` или экспорта нет → рекомендации нет; `soc ≥ 95` → действия `charge_bess` нет | UT |
| AC-218 | FR-54 | Given `peak` выключен, `grid_kw ≥ limit−30` ≥ 2 мин → `PEAK-RISK`; `chp` выключен, `grid_price − chp_cost ≥ 2·margin`, КГУ готова → `CHP-PRICE`; условие исчезло → `expired`; дубль по `dedup_key` не создаётся | UT |
| AC-219 | FR-54 | Given `td_energy_control` установлен; When `get_open()`; Then действия `kind='control'` имеют `enabled=True` и `class` (`A`/`B`), `meta.control_available=true` | UT |
| AC-220 | FR-54 | Given `prepare('bess_charge', …, advice_id)` → `confirm` → `done`; Then `advice.state='done'`, `result_note=result_text`; Given действие W3 с `params.intent`: `vent_night_mode`, `pv_self_consumption`, `air_pressure_setpoint` → `prepare` создаёт `scenario_toggle night`, `scenario_toggle self`, `air_setpoint`; `heat_schedule_shift` → `UserError` без создания действия (R-55 п.6) | UT |
| AC-221 | FR-54 | Given выполненное действие рекомендации; When `get_open()`; Then баннер `state='done'` (BESS: «BESS заряджається 50 кВт.» / «Експорт через T2 усунено, до 16:00 накопичиться ≈ 80 кВт·год.») с действием `undo`; после `undo` или истечения `undo_window_min` → `False` | UT |
| AC-222 | FR-54 | Given `td_energy_control` не установлен; Then `meta.control_available=false`, кнопки `control` не отдаются (W1 AC-116/AC-117 остаются зелёными) | UT |

### 12.8 HTTP, безопасность, данные, кроны — AC-223…AC-235

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-223 | FR-57 | When `POST state` валиден; Then обновлены `engine_mode`, `heartbeat_at`, `scenario.engine_*`, `applied_version`; ответ `accepted_actions/accepted_events/rejected`; повтор `event_id` игнорируется; «назад» → `rejected: already_final`; неизвестный `id` → `rejected: unknown_action` | UT |
| AC-224 | FR-57 | When `actions` > 100 или `events` > 200 → 400 `bad_schema`; тело > 256 КБ → 413; не JSON → 400 `bad_json`; `collector` ≠ токен → 403 `collector_mismatch`; без токена → 401; `GET` → 405 | UT |
| AC-225 | FR-68 | Given `events[]` `interlock`/`failsafe`/`mode(hold)`; Then запись журнала `origin='auto'` и `td.energy.event` `kind='control'` (значение `kind` добавлено `selection_add`; dedup 60 мин; `_td_log` W1); `auto_step`/`auto_release` — только журнал; события `control` старше 24 ч → `resolved` | UT |
| AC-226 | FR-53 | Given матрица 4.2; Then user не может `prepare`; manager не может `confirm` B единолично; chief может; admin редактирует `command.kind`/`interlock.params`; прямой `write` на `action`, `scenario`, `control.state` запрещён всем, кроме контекста модуля | UT |
| AC-227 | FR-58 | When токен другого пользователя; повторное использование после `cancel`; строки с кавычками/`;--` в `kind`/`params`; `params` не dict; Then отказы без побочных эффектов, SQL-инъекций нет | UT |
| AC-228 | FR-60 | Given `td.source` `type='energy_ctl'`; When с `collector_id` и `params={"engine":{"tick_s":2}}` → OK; без коллектора → `ValidationError`; `tick_s=50` или секрет в `params` → `ValidationError`; `module='energy_control'` допустим | UT |
| AC-229 | FR-60, FR-61 | Given демо-БД после W1; When `post_init_hook`; Then `td.source` 138, `td.signal` `energy_control` +36 с адресами HR 200…291 (28 на `MB-U73-SWB-CMD` + 8 на `ENERGY-CTL`), scenarios 6, kinds 16, interlocks 20, shed 5, slots ≥ 10, state 1; `write_enabled=False` везде; повтор не меняет количеств | UT |
| AC-230 | FR-67 | When `hooks._td_enable_stand(env)`; Then флаги `td.telemetry.write_enabled`, `td.energy_control.write_enabled`, `automation_enabled` = `True`, `write_enabled` источников и записываемых сигналов `energy_control`; возвращает перечень изменений; `post_init_hook` этого не делает | UT |
| AC-231 | FR-61 | When `neutralize.sql`; Then флаги `write_enabled`/`automation_enabled` = `False`, источники и сигналы `energy_control` без записи/чтения, 3 крон-задачи выключены, команды `origin='energy'` в `queued/sent` → `cancelled` | UT |
| AC-232 | FR-61 | When `uninstall_hook` и удаление модуля (D-45); Then источники/сигналы `energy_control`, крон-задачи, параметры удалены, флаги сброшены; таблиц `td_energy_*_archive` **нет**; данные моделей модуля удалены вместе с ними; `meta.control_available=false` в `td_energy`; повторная установка создаёт данные заново (`post_init_hook`), `_restore_archive` не существует | UT |
| AC-233 | FR-50 | When `_cron_expire`; Then просроченные `prepared` → `expired`; `awaiting_second` > 600 с → `expired`; `queued/sent` просроченная команда → `expired`; `executing` дольше `exec_timeout_s + 30` → `failed` и `td.energy.event kind='control'`; конфиг-действие без применения > 60 с → событие один раз | UT |
| AC-234 | FR-57 | When `_cron_watch`; Then `automation_enabled` и heartbeat старше `4·heartbeat_stale_s` → событие `CTRL-HEARTBEAT` (dedup 15 мин), авторазрешение при восстановлении; изменение BMS-целей/тарифа → `config_etag` меняется и `bump()` | UT |
| AC-235 | FR-61 | Given `td_energy_control` установлен; Then регрессия: `td_energy` (W0 142 + W1), `td_telemetry` (`td.command`), `td_bms` зелёные; повторный `-u td_energy_control` не меняет количеств | UT |

### 12.9 Ядро сборщика — AC-236…AC-238

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-236 | FR-55 | Given `LiveCache`; When `update/get/age_s/snapshot/note_write`; Then возраст вычисляется по часам; `Scheduler`/`Emitter` подают показания после масштаба ядра; без `live` поведение не меняется (существующие тесты ядра зелёные) | UT-PY |
| AC-237 | FR-55 | Given `PluginContext`; Then новые поля `live/write_signal/read_signal/odoo/clock/state_dir` имеют `None` по умолчанию; `_make_ctx` заполняет их для любого источника; плагины `modbus_tcp`, `bacnet_ip`, `mqtt`, `http_push`, `helvarnet`, `sics` работают без изменений | UT-PY |
| AC-238 | FR-55, FR-58 | When `write_direct`: пишет только при всех предохранителях (`source.write_enabled`, `signal.write_enabled`, `registry.write_enabled`, `settings.write_enabled`, `expires_at`), иначе `WriteRefused` с причиной; таймаут; не пишет в буфер результатов; `read_now` возвращает `Reading` с масштабом ядра и обновляет `LiveCache` | UT-PY |

### 12.10 Плагин `td_collector_energy`: конфиг, блокировки, режимы — AC-239…AC-248

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-239 | FR-57 | Given fake Odoo; When загрузка API-24: 200, затем `If-None-Match` → 304; Odoo недоступен ≤ 7 суток → работает из кеша `Store`; невалидный конфиг → остаётся предыдущий валидный, `engine.reason="config invalid: …"`, событие `config` | UT-PY |
| AC-240 | FR-57 | When конфиг без необязательных ключей → дефолты кода; неизвестные ключи `params` → предупреждение; `slots` с `from ≥ to` отброшены; `shed[]` без сигнала пропущены | UT-PY |
| AC-241 | FR-51 | Given реестр CHECKS сборщика; When золотые случаи R-41 п.5 (все проверки `where ∈ {both, collector}`); Then те же ожидания, что в AC-195…AC-199 | UT-PY |
| AC-242 | FR-51 | When `hard`+`unknown`+`fail_closed` → блок; `soft`+`unknown` → не блок; `where='odoo'` не выполняется; свежесть `max(3·period, max_age_s)` | UT-PY |
| AC-243 | FR-58 | When значение конфига вне границы (`bess_kw_max=500`, `air_bar_max=9,5`, `min_bar=0,5`, `max_ratio=0,95`); Then применена граница кода (200; 8,5; 1,0; 0,9) и событие `config` | UT-PY |
| AC-244 | FR-56 | When `automation_enabled=false` или `write_enabled=false` → `off` (0 записей); `remote=0`, `grid_kw` несвежий > `stale_hold_s`, пожарная тревога (для `vent/light`), breaker → `hold`; иначе `auto`; каждый переход — событие `mode` | UT-PY |
| AC-245 | FR-56 | Given ручное перекрытие `bess`; Then `peak/self` не пишут BESS (событие `override` раз); `backup` > `peak` > `self` > `slots` > `chp` > `night`; разряд `peak` побеждает заряд `self` | UT-PY |
| AC-246 | FR-56 | When `Actuator`: запись только при изменении и не чаще `min_write_interval_s`; принудительные режимы перезаписываются каждые `valid_s/3`; неудачная запись → повтор, 3 подряд → сценарий `warn` + `failsafe`; `> max_writes_per_min` → `hold` 5 мин | UT-PY |
| AC-247 | FR-57 | Given Odoo недоступен 10 мин (fake clock); Then движок действует по кешу, `Reporter` буферизует ≤ 200 действий / 1000 событий (более старые отбрасываются со счётчиком) и отправляет после восстановления | UT-PY |
| AC-248 | FR-56 | When рестарт; Then `Store` восстанавливает владение, перекрытия, `shed_list`; расхождение с устройством (чтение назад) сбрасывает владение; интенты `executing` отчитываются `failed` «рушій перезапущено…» | UT-PY |

### 12.11 Плагин: сценарии — AC-249…AC-258

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-249 | FR-56 | `peak`: блок 15 мин по UTC-эпохе; `proj=(acc+grid·remaining)/900`; активация при `proj ≥ limit−30` или `grid ≥ limit`; переход DST не создаёт двойных/пропущенных блоков | UT-PY |
| AC-250 | FR-56 | `peak` ступень 1: `limit=760`, `grid=800`, SOC 82 → запрос BESS `{mode:2, setpoint=clamp(bess_now+excess,0,100), until_soc=30, valid_s=30}`; SOC ≤ 32 → BESS недоступен, событие `interlock`; перезапись каждые 10 с | UT-PY |
| AC-251 | FR-56 | `peak` ступени 2–3: `uncovered>0` ≥ `stage_delay_s` → `chp start` (проверки ok, `started_by='peak'`); КГУ недоступна/запрещена → сброс по приоритетам до покрытия `uncovered`; не эскалирует, пока КГУ разгоняется | UT-PY |
| AC-252 | FR-56 | `peak` отпускание: `release_hold_s` → восстановление в обратном порядке с шагом `shed_restore_step_s`; КГУ `stop` только после `min_run_h`; BESS ramp-down до `mode=0`; событие `auto_release` | UT-PY |
| AC-253 | FR-56 | `self`: экспорт 26 кВт, SOC 82 → BESS `{mode:1, setpoint=clamp(…), until_soc=95}`; экспорт ≤ 25 — без действий; ограничение СЭС интегральное после `curtail_delay_s`; восстановление +5 % после `restore_hold_s` | UT-PY |
| AC-254 | FR-56 | `self`: SOC ≥ 95 → только curtail; `peak` активен → `self` не заряжает | UT-PY |
| AC-255 | FR-56 | `pfc`: enabled → `pfc_mode=1`, `pfc_cos=0,95` (регистр 95; из `plant.cos_phi_target`); disabled → `pfc_mode=0`; `fault_step=3` → `warn` «PFC-2 ступінь 3»; движок не создаёт событий-заявок | UT-PY |
| AC-256 | FR-56 | `night`: окно 23:00–06:30 через полночь и `days`; вход — `vent_mode`, `sp_night`, сцена дежурного; выход — `day_vent_mode`, `light_scene_day_number`; старт внутри окна идемпотентен; DST (последнее воскресенье октября/марта) — по настенному времени; ручное изменение цели → `overridden` до границы; `bms.night` пуст → `warn` | UT-PY |
| AC-257 | FR-56 | `backup`: `src1_ok=0` ≥ 2 тика (4 с) → сброс по приоритетам до `need=max(0,p_total−0,9·507)`; элементы `critical=true` и `never_shed` пропускаются; `peak` приостановлен; восстановление после `restore_delay_s` по шагам | UT-PY |
| AC-258 | FR-56 | `chp`: `grid 8,4 − (19,80·0,25=4,95) ≥ 0,5` → пуск (проверки ok, `min_off_min` истёк); слот `chp`; остановка только после `min_run_h` и `started_by='chp'`; КГУ `peak`/manual не останавливается; `chp_state=3` → `warn` | UT-PY |

### 12.12 Плагин: интенты и исполнитель — AC-259…AC-268

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-259 | FR-55 | When `call()` валидного интента → `accepted=true` ≤ 1 с; `v≠1`, неизвестный `kind`, `params` вне границ, `expires_at` в прошлом → `rejected` с причиной; дубль `idem` → `duplicate:true`; ресурс занят → `rejected: busy: bess` | UT-PY |
| AC-260 | FR-55 | Given fake `write_signal/read_signal`; Then для каждого из 12 видов интентов последовательность записей и верификация соответствуют таблице R-42 п.3 | UT-PY |
| AC-261 | FR-55 | `qs_close`: `qs_ack=2` → `failed` «Контролер відмовив: блокування»; `qs_state=closed` ≤ 10 с → `done`; `qs_state` не изменился → `failed` | UT-PY |
| AC-262 | FR-55 | `bess_charge`: `valid_s` = секунды до `until` (Киев; максимум 43 200), `until ≤ now` → `rejected`; неудачная верификация → fail-safe `bess_mode=0`; мягкая проверка `bess_kw` → примечание в `result` | UT-PY |
| AC-263 | FR-55 | When ошибка записи → 1 повтор; вторая → `failed` + fail-safe; `exec_timeout_s` (60) → `failed`; тайм-аут верификации → `failed` | UT-PY |
| AC-264 | FR-58 | Given `lock=0` → `blocked` без единой записи; `remote=0` → `blocked`; код из `DENY_PREFIXES` или вне конфига → `WriteRefused` + событие `interlock` | UT-PY |
| AC-265 | FR-56 | Given `bess_charge` done → перекрытие `bess` до `valid_s`; `light_break` → автовосстановление через `duration_min` (событие `auto_release`); `bess_stop`/`light_restore` снимают; `chp_start` → владение manual | UT-PY |
| AC-266 | FR-57 | When `Reporter`: пакетирование, немедленная отправка смены действия, повтор при 5xx/429 с бэкоффом, дедуп `event_id`, лимиты 100/200 за запрос, throttle одинаковых событий ≥ 60 с | UT-PY |
| AC-267 | FR-57 | When `Store`: атомарная запись (tmp+rename), отбрасывание > 7 суток, лимит 500 интентов/24 ч, повреждённый файл → старт с пустого состояния и событие | UT-PY |
| AC-268 | FR-55 | When `EnergyCtlPlugin`: `validate`, единственный экземпляр, `subscribe` создаёт 4 задачи, `health()` online/error, `disconnect` без записей в устройства, heartbeat `Reading` `energy_control/auto/heartbeat` каждые 10 с | UT-PY |

### 12.13 Эмулятор — AC-269…AC-274

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-269 | FR-59 | Given `swbctl`; When FC3/FC6 на HR 200…291; Then чтение/запись по 5.6, значения вне границ → exception 3, `write_accept=False` → exception 4, `cmd` самоочищаются, heartbeat растёт на симулированную секунду, `ctl_remote=0` → `ack=2` | UT-PY |
| AC-270 | FR-59 | BESS: режимы 0–3, `until_soc`, `setpoint`; `valid_s` → 0 по времени мира возвращает режим 0; разряд при SOC ≤ 30 → `ack=2`, режим не меняется; температура = `25+0,05·\|P\|` | UT-PY |
| AC-271 | FR-59 | `qs/cmd=2` → QS замкнут только при `parallel_lock=1` и без острова, `energy/cells/QS/state=1`, Q1=Q2; иначе `ack=2`; `pfc_mode=0` → `steps_on=0`; `pfc_cos_target` меняет `steps_on` | UT-PY |
| AC-272 | FR-59 | `chp/cmd=1` → `chp_run`, разгон по `chp_start_s`; отказ (`ack=2`) при `gas<1,5` или `permit=0`; `air/setpoint=6,50` → давление ≈ 6,31 бар, `7,00` → 6,81 (W0 сохранено) | UT-PY |
| AC-273 | FR-59 | `shed/<CODE>/limit_pct` уменьшает `consumer_p` пропорционально; `pv/limit_pct` уменьшает `p_kw` инверторов; `shed/valid_s` → 0 возвращает все лимиты и `pv/limit_pct` в 100 | UT-PY |
| AC-274 | FR-59, FR-67 | Сценарии `peak_load {extra_kw}`, `export_demo {export_kw}` (экспорт ровно `export_kw`, BESS авто 0 кВт), `ctl_local`, `chp_no_gas`; `POST /sim/v1/reset` возвращает значения по умолчанию (R-59 п.3) | UT-PY |

### 12.14 Мост ДГУ, расширение просмотрщика — AC-275…AC-281

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-275 | FR-69 | Given `td_genset_factory3d`; When `start_test(gen,'idle',user)`; Then вызывается `_test_start('idle', user)` под `sudo`, ответ `{accepted, minutes, test_end, ref}`; `mode='load'` → `UserError` «Лише тест без навантаження»; `UserError` `td_genset` («Тест уже йде.») пробрасывается | UT |
| AC-276 | FR-69 | When `test_facts(gen)`; Then `fuel_pct`, `running`, `test_running`, `island`, `coolant_c`; без снимка — `None` без исключений | UT |
| AC-277 | FR-66, FR-69 | Given мост; When `genset_test` (manager + второе подтверждение или chief); Then `done` с `ref` на `td.genset`, `result_text` «Тест ДГУ прийнято td_genset: N хв»; «Тест уже йде.» → `blocked`; проверки `genset_fuel`, `genset_heater`, `genset_idle`, `no_island` в диалоге | UT |
| AC-278 | FR-65, FR-70 | Given расширение с `colorModes`/`modeColor` (VX-01/02); Then радио в группе «Розфарбування», `applyParams({mode})` включает режим, `modeColor` красит, `getState().mode` = ключ; исключение расширения логируется, ядро и другие расширения работают; без расширения режимы не меняются | UT-JS |
| AC-279 | FR-65, FR-70 | Given VX-03; Then `applyData(api, D, info)` после `load/patch/snapshot/now` с `info.keys`; для режима расширения после вызова `repaintAll()` | UT-JS |
| AC-280 | FR-65, FR-70 | Given VX-04/05; Then `cardBlocks` добавляются в карточку; клик по `data-ext` → `onAction`; `api.openAction` → `opts.onOpenAction`; в киоске → `false` | UT-JS |
| AC-281 | FR-65, FR-70 | Given регрессия; Then `td_constructor_viewer3d` (`applyLayout`) и AC-01…AC-67 просмотрщика зелёные; `registerViewerExtension` без новых членов работает как раньше | UT |

### 12.15 «Энергетика в 3D» — AC-282…AC-293

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-282 | FR-62 | Given демо-БД; When `td.viewer.provider.energy_layer._f3d_viewer_collect`; Then `energy.layer` по схеме 8.4.2 (≈ 21 узел, `thresholds` 80/100, `alarms`); `meta.schema` остаётся `"1.1"`; `_f3d_sequence=101`; пользователь без `td_factory3d.group_td_user` — раздел `denied` | UT |
| AC-283 | FR-62 | Then `scene` = `equipment.td_code` или `node.code`; `C1`,`C2` → `CABLES`; неизвестный код → `scene=null` (узел в списке, без маркера); состояние объекта сцены = худшее среди узлов с тем же `scene` | UT |
| AC-284 | FR-62 | Given пример 14:20 (W1 R-26); Then `state` совпадает с `td.energy.node.sld_state` и Пультом: `C2` alarm, `PFC-2` warn, `PV-INV` gen, `CHP` off, `ATS-1` off, `QS` off, `T2` ok; пороги меняются вместе с `td.energy.load_*_pct` | UT |
| AC-285 | FR-62 | Then `alarms[]` — только `active/acked`, `warn\|bad`, ≤ `marker_limit`, `bad` первыми, `title ≤ 80`; нет `acked_by`/пользователей/стоимости | UT |
| AC-286 | FR-62 | Given изменение `td.energy` или энергетического `td.signal`; When `_f3d_viewer_delta`; Then `patch.energy.layer` — полная замена (списки не конкатенируются); другие изменения — без `layer` | UT |
| AC-287 | FR-62 | Given `ctx.kiosk`; Then раскраска и `alarms` есть, `card=false`, `title` без технических деталей диагностики; пользователь без `group_td_energy_user` (не киоск) — тоже `card=false` | UT |
| AC-288 | FR-62 | Given `StateColors`; When `modeColor('td_energy', root)`; Then `ok`→зелёный, `warn`→жёлтый, `alarm`→красный, `gen`→янтарный, `off`→серый; неизвестный `scene` → `null`; легенда содержит пороги | UT-JS |
| AC-289 | FR-62 | Given `AlarmMarkers`; Then спрайты для `alarms[]` со `scene` в `codeRoot`, ≤ лимита; снимаются/`dispose` при обновлении и выключении слоя; `reduceMotion` выключает пульсацию; клик → `api.select(scene)` | UT-JS |
| AC-290 | FR-63 | Given `NodeBlock`; Then чип состояния, `P`, ток/%, ≤ 3 тревоги, кнопка «Відкрити картку вузла» только при `card` и наличии `openAction`; клик → `openAction` `td_energy.node_card` с `params.code` | UT-JS |
| AC-291 | FR-64 | When `action_td_open_3d('BW-2')`; Then `f3d_viewer.action` с `layers` (параметр), `mode='td_energy'`, `tab='energy'`, `code='BW-2'`; `PFC-2` без `scene` → `code=null`; неизвестный код → `UserError`; без `code` — только слой | UT |
| AC-292 | FR-64 | Given td_energy client (§3.4 п.1); Then «Відкрити в 3D» и «Показати в 3D» (Пульт, панель узла, карточка, мобильный) используют `viewerLinks.default`; без моста — путь W1/уведомление; ключ `layer` исправлен на `layers` | UT-JS |
| AC-293 | FR-62…FR-64 | Given стенд (ТК-28); When «Відкрити в 3D» → режим «Електромережа: стан вузлів», маркер на `C2`; клик по ШР-2 → блок «Енергетика» → «Відкрити картку вузла» открывает `td_energy.node_card`; «Показати в 3D» для `BW-2` подсвечивает узел; смена состояния (сценарий эмулятора) обновляет цвет и маркеры ≤ 10 с; скриншоты | TC/MAN |

### 12.16 Экран «Керування» (UI) и правки клиента td_energy — AC-294…AC-303

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-294 | FR-46 | Given `HttpCase`; When открыть `action_td_energy_control`; Then без JS-ошибок, h1 «Керування енергетикою заводу», информационная полоса, чип связи (3 состояния), меню «Керування» (seq 8) и «Журнал команд» | UT |
| AC-295 | FR-47 | hoot: 6 карточек, чипы/текст, `role="switch"` + `aria-checked`, «увімкнено N з 6», клик по переключателю открывает диалог и **не** меняет состояние без `confirm`, чип «Очікує застосування» при `!applied` | UT-JS |
| AC-296 | FR-48 | hoot: 5 приоритетов, «Разом можна зняти 174 кВт», режим «Змінити порядок» (кнопки «Вище»/«Нижче» 36 × 36 с `aria-label`), «Зберегти порядок» открывает диалог `shed_reorder`, «Скасувати» возвращает порядок | UT-JS |
| AC-297 | FR-49 | hoot: 8 плиток в порядке макета, `disabled` + `title` по правам/предохранителю, бейдж «B» | UT-JS |
| AC-298 | FR-49, FR-50 | hoot: диалог — заголовок «{title}?», проверки «гаразд/не виконано/немає даних», «Виконати» `disabled` при `blocked`, «Підтвердити (1/2)» для B manager, отсчёт TTL, Esc → `cancel`, прогресс «Надіслано → Виконується → Виконано/Не виконано», фокус в диалоге | UT-JS |
| AC-299 | FR-52, FR-53 | hoot: расписание — 6 строк, `left/width` полос по `from/to`, вертикаль «зараз», текстовая таблица; журнал — строки с чипами, «Скасувати дію», «Підтвердити (2/2)», «Показати більше» | UT-JS |
| AC-300 | FR-54 | hoot: в `td_energy.advice_handlers` есть `control`; клик «Зарядити BESS 50 кВт» → диалог `bess_charge` с `advice_id`; после `done` Пульт перечитывает `advice`/`alarms`; баннер «Виконано» с «Скасувати» → диалог `undo` | UT-JS |
| AC-301 | FR-46 | hoot (td_energy client §3.4 п.2): панель узла `QS`/`BESS` содержит кнопки из реестра `td_energy.node_actions` в зависимости от состояния («Увімкнути QS…»/«Вимкнути QS…», «Зарядити 50 кВт»/«Зупинити заряд»); без реестра — как в W1 | UT-JS |
| AC-302 | FR-54 | hoot (§3.4 п.3): `advice.state==='done'` → зелёный баннер без «Пізніше», с «Скасувати» | UT-JS |
| AC-303 | FR-46 | MAN: десктоп 1440 и планшет 1024 — без горизонтального скролла (кроме расписания), клавиатурная навигация, видимый фокус; скриншоты экрана и диалога для приёмки | MAN |

### 12.17 Сквозные проверки на стенде — AC-304…AC-308

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-304 | FR-54, FR-55 | ТК-20: `export_demo` (экспорт 26 кВт, BESS 82 %, QS открыт); When EXPORT-T2 → «Зарядити BESS 50 кВт» → диалог → «Виконати»; Then ≤ 30 с `td.energy.action` `done`, `bess_mode=1` в эмуляторе, `bess_kw ≈ +50`, экспорт исчезает, баннер «Виконано»; «Скасувати» → `bess_mode=0` | TC |
| AC-305 | FR-49, FR-51, FR-53 | ТК-21: «Увімкнути QS…» (manager): диалог с «Блокування паралельної роботи T1 і T2 від АВР — гаразд», «Підтвердити (1/2)» → второй энергетик «Підтвердити (2/2)» → `energy/cells/QS/state=closed`, Q1=Q2; `lock=0` в эмуляторе → «заблоковано», 0 записей; `ctl_local` → «не виконано: контролер у місцевому режимі»; «Скасувати» → QS open | TC |
| AC-306 | FR-56 | ТК-23: `peak_load` (+300 кВт) при включённом `peak`; Then BESS разряд → (≥ 60 с) КГУ пуск → (≥ 60 с) сброс в порядке списка; `grid_kw` ≤ `limit_kw`; после снятия нагрузки — восстановление в обратном порядке, КГУ останавливается после `min_run_h`, BESS `mode=0`; журнал «сценарій «Пік»» | TC |
| AC-307 | FR-56 | ТК-25/26: (а) время мира 22:59 → 23:00: `night` → BMS-цели получили `VEL`/дежурный сценарий; 06:30 — день; (б) `mains_loss`: `backup` сбросил неважные, критичные остались; после восстановления сети +`restore_delay_s` — возвращены | TC |
| AC-308 | FR-57 | ТК-27: остановить сборщик → ≤ 60 с BESS/сбросы вернулись (сторожевые таймеры), чип «Збирач не на зв'язку», событие `CTRL-HEARTBEAT`; остановить Odoo на 5 мин → автоматика действует, после запуска журнал и состояния дополнены; рестарт сборщика → владение восстановлено, `executing` интенты `failed`; отключение `write_enabled` посреди выполнения → остальные шаги отменены | TC |

## 13. План тестирования (для Opus)

### 13.0 Фикстуры и требования к тестируемости

- `td_energy_control/tests/common.py`: `TestControlCommon(TransactionCase)` — `_user(groups)` (пользователи `viewer` = `group_td_energy_user`, `en1`, `en2` = `group_td_energy_manager`, `chief` = `group_td_energy_chief`, `admin`); `_fresh(code, value, text=None, age_s=0)` (запись `td.signal.last_value/last_ts/status`); `_snapshot_1420()` — состояние макета 14:20 (`grid_kw=356`, `export_kw=26`, `pv_now=309`, `bess_soc=82`, `bess_state=1`, `chp_state=0`, `ats_pos=2`, `src1_ok=1`, `QS=open`, `lock=1`, `remote=1`, `gas=2,10`, `permit=1`, `air_min=6,20`, `p1/p2` для тока QS 38 А); `_enable_control()` (флаги, `write_enabled` источников/сигналов); `_collector()` (коллектор с токеном для HTTP-тестов); время — мок `td_energy.tools.dates.now_utc`.
- Плагин: `tests/fakes.py` — `FakeClock` (управляемые `sleep/now/monotonic`), `FakeLive`, `FakeDevice` (карта регистров и реакции BESS/QS/КГУ по R-59), `FakeCtx` (записи `write_signal`, `read_signal` из `FakeDevice`, `emit`), `FakeOdoo` (aiohttp-сервер API-24/25 с управляемыми ответами и сбоями), `golden.py` (таблица R-41 п.5 как данные); все тесты детерминированы (без реального времени и сети).
- Эмулятор: существующий `tests/conftest.py` (мир с каталогом, часы, `world.set_flag`).
- JS: hoot (`web.assets_unit_tests`), мок `orm.call` возвращает JSON из разд. 7; фикстура `static/tests/fixtures/contracts.js`.
- Временные функции вызываются через `dates.now_utc(env)`/`Clock`, которые мокируются; генератор истории (`_td_backfill`) — детерминирован по `seed`.

### 13.1 Юнит-тесты

**Бэкенд Odoo (A)** — `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_control $T/run_tests.sh <db> /td_energy_control:<Класс>`:

| Файл | Класс | Покрывает |
|---|---|---|
| `test_scenario.py` | `TestScenario` | AC-159…AC-164, AC-169 |
| `test_shed.py` | `TestShed` | AC-171…AC-176 |
| `test_kinds.py` | `TestKinds` | AC-177, AC-178, AC-181, AC-194 |
| `test_action_flow.py` | `TestActionFlow` | AC-179, AC-180, AC-182, AC-183, AC-187…AC-193 |
| `test_action_second.py` | `TestActionSecond` | AC-184…AC-186 |
| `test_interlocks.py` | `TestInterlocks` | AC-195…AC-204 |
| `test_undo.py` | `TestUndo` | AC-208, AC-209 |
| `test_journal.py` | `TestJournal` | AC-205…AC-207, AC-210, AC-225 |
| `test_schedule.py` | `TestSchedule` | AC-211…AC-216 |
| `test_advice_rules.py` | `TestAdviceRules` | AC-217…AC-222 |
| `test_config_api.py` | `TestConfigApi` | AC-166…AC-168, AC-175 |
| `test_state_api.py` | `TestStateApi` | AC-170, AC-223, AC-224 |
| `test_intent_payload.py` | `TestIntentPayload` | AC-182 (форма `payload`), AC-188 |
| `test_security.py` | `TestSecurity` | AC-226, AC-227 |
| `test_source_signal.py` | `TestSourceSignal` | AC-165, AC-228 |
| `test_hooks.py` | `TestHooks` | AC-229, AC-230, AC-232, AC-235 |
| `test_neutralize.py` | `TestNeutralize` | AC-231 |
| `test_crons.py` | `TestCrons` | AC-233, AC-234 |
| `test_genset_exec.py` | `TestGensetExec` | AC-194, AC-277 (с имитацией адаптера, если мост не установлен) |
| `test_remote_switching.py` | `TestRemoteSwitching` | AC-309, AC-310 |
| `test_contracts.py` | `TestContracts` | набор ключей API-16/17/18/22/24/25/26/28 равен `contracts/*.json` (заморозка C-38…C-47) |
| `td_genset_factory3d/tests/test_adp12.py` | `TestAdp12` | AC-275, AC-276 (`F3D_TEST_INSTALL=td_energy,td_genset,td_genset_factory3d $T/run_tests.sh <db> /td_genset_factory3d:TestAdp12`) |

**Фронтенд (B)**: `test_ui.py::TestControlUi` (HttpCase, AC-294); `test_hoot.py::TestControlHoot.test_hoot_suite` (запускает `/web/tests?headless…&id=<hash('@td_energy_control')>` по образцу `td_energy/tests/test_w1_hoot.py`) — AC-295…AC-302 (файлы `control.test.js`, `confirm_dialog.test.js`, `advice_handler.test.js`, `node_actions.test.js`); `td_energy/static/tests/control_hooks.test.js` — AC-292, AC-301 (хуки), AC-302 (выполняется существующим hoot-набором `td_energy` `TestW1Hoot`); AC-303 — MAN.

**Сборщик, плагин, эмулятор (C)**, pytest (`pytest -q`):

| Файл | Покрывает |
|---|---|
| `services/collector/tests/unit/test_live.py`, `test_ctx_extension.py`, `test_write_direct.py` | AC-236…AC-238 |
| `td_collector_energy/tests/test_config.py` | AC-239, AC-240, AC-243 |
| `test_interlocks.py` | AC-241, AC-242 (золотые случаи из `golden.py`) |
| `test_engine.py` | AC-244, AC-245, AC-247, AC-248 |
| `test_actuator.py` | AC-246 |
| `test_scenario_peak.py` | AC-249…AC-252 |
| `test_scenario_self.py`, `test_scenario_pfc.py` | AC-253…AC-255 |
| `test_scenario_night.py` | AC-256 (включая DST) |
| `test_scenario_backup.py`, `test_scenario_chp.py` | AC-257, AC-258 |
| `test_intents.py` | AC-259…AC-262 |
| `test_executor.py` | AC-263…AC-265 |
| `test_reporter.py`, `test_store.py`, `test_plugin.py` | AC-266…AC-268 |
| `services/iot_sim/tests/unit/test_swbctl.py` | AC-269 |
| `services/iot_sim/tests/unit/test_control_models.py` | AC-270…AC-274 |

**Мост 3D и просмотрщик (D)**: `td_energy_viewer3d/tests/{test_layer_payload.py::TestLayerPayload (AC-282…AC-285), test_delta.py::TestDelta (AC-286), test_kiosk.py::TestKiosk (AC-287), test_deeplink.py::TestDeepLink (AC-291), test_hoot.py::TestEnergyLayerHoot (AC-288…AC-290)}`; `td_viewer3d/static/tests/hoot/extension_energy.test.js` (AC-278…AC-280); `td_viewer3d/tests/test_r26_extension.py` и полный прогон `/td_viewer3d` + `/td_constructor_viewer3d` (AC-281).

### 13.2 Стендовые сценарии ТК-19…ТК-28 (`td_energy_control/tests/stand/test_tk_control.py` + Playwright)

Предпосылки (E-11): постоянные сервисы тестового сервера — эмулятор `iot_sim` и сборщик с плагином `td_collector_energy`; установлены `td_energy`, `td_energy_control`, `td_bms`, `td_genset`, `td_genset_factory3d`, `td_viewer3d`, `td_energy_viewer3d`, `td_iot_sim`; выполнен `_td_backfill(days=90)` (W1); `hooks._td_enable_stand(env)`; сборщик `F3D_WRITE_ENABLED=true`, `F3D_COMMANDS_POLL_S=2`; эмулятор `SIM_WRITE_ACCEPT=1`; пользователи `viewer`, `en1`, `en2`, `chief`.

| ТК | Название | Шаги | Ожидается |
|---|---|---|---|
| ТК-19 | Экран живой | `en1`: «Енергетика → Керування», ждать 90 с | чип «Контролер ГРЩ і збирач на зв'язку · HH:MM»; 6 карточек, «увімкнено 4 з 6» (peak, pfc, night, backup); приоритеты (5, «174 кВт»); 8 плиток; расписание из 6 строк и линией «зараз»; журнал; без ошибок консоли; значения обновляются без перезагрузки (шина) |
| ТК-20 | Рекомендация → BESS → «Скасувати» (AC-304) | `POST /sim/v1/scenario/export_demo/start {"export_kw": 26}`; QS открыт; ждать 5 мин → Пульт показывает EXPORT-T2; «Зарядити BESS 50 кВт» → диалог → «Виконати» | ≤ 30 с действие `done`; эмулятор `bess_mode=1`, `bess_kw ≈ +50`; экспорт ≈ 0; баннер «Виконано … Скасувати»; «Скасувати» → `bess_mode=0`, журнал «Скасування» |
| ТК-21 | QS: диалог, второе подтверждение, блокировка (AC-305) | `en1`: «Увімкнути QS…» → диалог с «Блокування … — гаразд», «Струм ≈ N А з 1600 А» → «Підтвердити (1/2)»; `en2`: баннер/журнал «Підтвердити (2/2)»; повтор с `lock=0` (флаг эмулятора) и `ctl_local` | QS `closed`, Q1=Q2; с `lock=0` — «заблоковано», в журнале 0 записей устройства; `ctl_local` — «Контролер у дистанційному режимі — не виконано»; `chief` выполняет без второго подтверждения; «Скасувати» → QS open |
| ТК-22 | Прочие команды | `chief`: `bess_discharge` 100 кВт/60 мин; `chp_start`; `air_setpoint` 6,5; `genset_test`; `en1`: `light_break`, `vent_eco`; `en1` пытается `chp_start` | разряд −100 кВт и режим 2 (до `valid_s`); КГУ `run` (ускорение времени — D-33); давление ≈ 6,31 бар, `undo` → 6,81; td_genset принимает тест (`td.genset.command`); BMS-сигналы записаны, после `duration_min` (время мира) восстановлено автоматически; `en1` → `awaiting_second` |
| ТК-23 | Срезание пика (AC-306) | `peak` включён; `POST /sim/v1/scenario/peak_load/start {"extra_kw": 300}` | BESS разряд → (≥ 60 с) КГУ → (≥ 60 с) сброс по списку; `grid_kw ≤ limit_kw`; после `stop` — восстановление в обратном порядке; журнал «сценарій «Пік»»; чип `peak` «Зрізання піку · …» → «Чергування · запас … кВт» |
| ТК-24 | Самопотребление и PFC | включить `self` (класс B, 2 лица); `export_demo` 26; SOC → 95; выключить/включить `pfc`; `pfc_step_fault {section:2, step:3}` | BESS заряжается по экспорту, при SOC 95 — ограничение СЭС и возврат; `pfc` выключен → `pfc_mode=0`, ступени 0, cos φ ниже нормы (W1 чип), включён → восстановлено; с неисправностью — чип «Збій: PFC-2 ступінь 3», заявка ТО от W1 |
| ТК-25 | Ночной режим (AC-307а) | `POST /sim/v1/time` → 22:59, затем 23:00; потом 06:30 | в 23:00 цели BMS получили `VEL`/дежурный сценарий/16 °C, журнал «Вентиляція · нічний режим»; в 06:30 — день (`VE`), «RoofVent 25 шт. → 100 %»; чип «Наступний запуск о 23:00» ↔ «Активний до 06:30» |
| ТК-26 | Резервное питание (AC-307б) | `mains_loss` (сценарий W0), после — восстановление | `backup` `active`, неважные нагрузки сброшены, критичные остались; после восстановления + `restore_delay_s` — возвращены; чип «Мережі немає · скинуто N» → «Готовий · паливо 78 %» |
| ТК-27 | Отказы (AC-308) | остановить сборщик; запустить; остановить Odoo на 5 мин; выключить `write_enabled` посреди выполнения | сторожевые таймеры возвращают BESS/сброс ≤ 60 с; чип «Збирач не на зв'язку», событие `CTRL-HEARTBEAT`; автономия по кешу; после рестарта владение восстановлено; остальные шаги отменены |
| ТК-28 | 3D (AC-293) | Пульт → «Відкрити в 3D»; клик по ШР-2; «Відкрити картку вузла»; Пульт → узел `BW-2` → «Показати в 3D»; изменить состояние (`pfc_step_fault`/отключение счётчика) | режим «Електромережа: стан вузлів», маркеры по тревогам, блок «Енергетика», переход в карточку, подсветка узла; цвет/маркер обновляются ≤ 10 с; киоск без карточки |

### 13.3 Тесты безопасности (ТБ-11…ТБ-15)

- ТБ-11: токены и идемпотентность — чужой/просроченный/повторный токен, инъекции в `kind`/`params`, двойной `confirm` (AC-183, AC-182, AC-227).
- ТБ-12: запрет управления системами безопасности — Odoo (AC-165, AC-172), конфиг (`signals`-allowlist), сборщик `DENY_PREFIXES` и запись вне конфига (AC-264); пожарная тревога блокирует `vent/light` (AC-204, AC-244).
- ТБ-13: права E-06 — user/manager/chief/admin по матрице 4.2, второе подтверждение другим лицом, запрет самоподтверждения и обхода администратором (AC-184…AC-186, AC-226).
- ТБ-14: предохранители — каждый из шести по отдельности отключает запись (`td.telemetry.write_enabled`, `td.energy_control.write_enabled`, `source.write_enabled`, `signal.write_enabled`, `F3D_WRITE_ENABLED`, `automation_enabled` для автоматики); `neutralize.sql`; `module='energy'` остаётся read-only (AC-192, AC-238, AC-244, AC-231, AC-165).
- ТБ-15: HTTP — Bearer, `collector_mismatch`, лимиты, rate-limit, отсутствие секретов/стоимости в ответах API-24/25 (AC-166, AC-224).

### 13.4 Тесты производительности (ТП-10…ТП-12)

- ТП-10: `get_control` ≤ 400 мс и ≤ 40 SQL, `prepare`/`confirm` ≤ 300 мс, API-24 ≤ 200 мс, API-25 (100 действий + 200 событий) ≤ 300 мс (R-64).
- ТП-11: `energy.layer` ≤ 12 КБ, построение ≤ 150 мс на 123 узлах; дельта ≤ 100 мс; клиент — ≤ 40 маркеров без падения ниже 30 кадр/с на планшете (MAN).
- ТП-12: тик движка ≤ 50 мс p95 на 1000 тиков; память ≤ 60 МБ за 1 ч с `FakeOdoo`; записей в устройства ≤ 30/мин; `Store` ≤ 1 МБ.

### 13.5 DEPLOY_TEST (новый `docs/modules/td_energy_control/DEPLOY_TEST.md`)

1. Копия демо-БД после W1 → `-i td_energy_control,td_energy_viewer3d`: количества (разд. 5.6: `td.source` 138, сигналы `energy_control` +36, scenarios 6, kinds 16, interlocks 20, shed 5, slots ≥ 10); `write_enabled=False` и `automation_enabled=False`; экран открывается, плитки показывают «Керування вимкнено адміністратором».
2. Повторный `-u`: без изменений; `neutralize.sql`; откат: `uninstall` удаляет данные модуля без архивных таблиц (D-45), Пульт `td_energy` без кнопок управления, 3D-слой исчезает, `td_viewer3d` работает; повторная установка создаёт данные заново (AC-232).
3. Стенд: установить плагин сборщика (`pip install`), перезапустить сборщик, `ENERGY-CTL` становится `online`; `_td_enable_stand`; ТК-19…ТК-28.
4. Регрессия: `/td_energy`, `/td_telemetry`, `/td_bms`, `/td_viewer3d`, `/td_constructor_viewer3d`, `/td_genset_factory3d`; `pytest` коллектора, плагинов и эмулятора.

## 14. Definition of Done (W2)

- Все UT/UT-JS/UT-PY AC-159…AC-302 (кроме MAN/TC) зелёные; ТК-19…ТК-28 пройдены на стенде; AC-303 (скриншоты) принят.
- Регрессия зелёная: `td_energy` (W0 142 + W1), `td_telemetry`, `td_bms`, `td_viewer3d` (AC-01…AC-67), `td_constructor_viewer3d`, `td_genset_factory3d` (101), `td_genset` (223), коллектор (`pytest tests/unit`), плагины `f3d_collector_*`, эмулятор (`tests/unit`).
- `ruff` без ошибок (Odoo-модули, плагин, ядро сборщика, эмулятор); JS — проверка `rjsmin` (без вложенных шаблонных литералов в `core.js`).
- `neutralize.sql`, `CHANGELOG`/`README` модулей (`td_energy_control`, `td_energy_viewer3d`, `td_collector_energy`), `DEPLOY_TEST`; обзор безопасности ТБ-11…ТБ-15; инструкция ARCH §4.
- Предохранители по умолчанию выключены в `post_init_hook`; `_td_enable_stand` не вызывается автоматически.
- Документы разложены в `docs/modules/*` (после слияния): `td_energy_control`, `td_energy_viewer3d`, R-26/VX в `td_viewer3d`, ADP-12 в `td_genset_factory3d`.

## 15. Открытые вопросы и решения автора

Вопросы Q-26…Q-33 — ARCH §5 (те же номера).

### Решения автора (A-38…A-62; A-63 — мост ДГУ)

| ID | Решение | Обоснование |
|---|---|---|
| A-38 | Параметры модуля — `td.energy_control.*` (`write_enabled`, `automation_enabled`, …), а не `td.energy.control_enabled` из GAP §6 п.13 | Конвенция `docs/ARCHITECTURE.md` §5 (`td.<module>.<param>`); стоп-кран `write_enabled` = «пятый предохранитель» |
| A-39 | К классу B отнесены также `scenario_params`, `shed_edit`, `schedule_edit`, `interlock_param`, `chp_stop`, `qs_open` | E-06 называет часть действий; остальные — той же природы (изменение уставок/состава/состояний) |
| A-40 | Тип источника `energy_ctl` регистрируется валидаторами `PARAMS_VALIDATORS/ADDRESS_VALIDATORS` при импорте `td_energy_control` | Не меняем `td_telemetry` в W2; официальная точка расширения — Q-30 |
| A-41 | Собственная шина `td_energy_control` (kinds `action/scenario/engine/schedule/shed`); бэкенд `td_energy` не меняется; клиентские правки `td_energy` минимальны (разд. 3.4) | Белый список `KINDS` в W1 `tools/bus.py`; изоляция модуля |
| A-42 | Новый модуль `td_energy_control`, а не расширение `td_energy` (обоснование ARCH §2.1) | Управление отключается/удаляется без потери читающего приложения; предохранители по умолчанию; отдельный цикл тестов и рисков; слот `control_available` уже предусмотрен W1 (C-32) |
| A-43 | Движок — `push_mode`-плагин `energy_ctl` в сборщике + аддитивное расширение `PluginContext` (`live`, `write_signal`, `read_signal`, `odoo`) | Минимальные изменения ядра, обратная совместимость, те же предохранители записи; без отдельного процесса |
| A-44 | Шаги выполнения видов интентов и границы `params` — **собственность сборщика**; Odoo передаёт `kind` + `params` | Hard-блокировки и безопасность не зависят от доверия к данным Odoo; Odoo-проверка — подсказка (GAP §2.3) |
| A-45 | Окно управления на `SWB-CTRL` (unit 73, HR 200…291) — единственный источник `MB-U73-SWB-CMD` для стенда. **Подтверждено менеджером (Q-26): допущение сохраняется; карты регистров реальных объектов — позже (данные `address`, код не меняется)** | Один контроллер ГРЩ как точка управления (E-03); на объекте меняется только `address` (Q-26) |
| A-46 | Все команды устройствам — уровневые (устанавливают значение), не переключатели | Безопасный повтор, идемпотентность при дублировании доставки |
| A-47 | Сторожевые таймеры: `bess/valid_s`, `shed/valid_s` (вместе с `pv/limit_pct`) — «мёртвая рука» контроллера | Fail-safe при падении сборщика/движка (R-53 №7) |
| A-48 | Тексты чипов сценариев составляет Odoo по шаблону из чисел движка | Язык и согласованность с макетом; движок без UI-строк |
| A-49 | Двухшаговый поток `prepare → confirm` с токеном (TTL 60 с), `confirm` идемпотентен; диалог показывает проверки из Odoo | Диалог макета; защита от двойных кликов |
| A-50 | Действия `config` применяются в Odoo сразу, «применённость» — по `applied_version` сборщика; чип «Очікує застосування» | Истину о выполнении даёт сборщик (D-20) |
| A-51 | Журнал = `td.energy.action` + события W1; отмена — отдельное действие в пределах `undo_window_min`; **при деинсталляции данные модуля удаляются вместе с ним, архивных таблиц нет (D-45, решение менеджера)** (R-66) | Единый бизнес-журнал (GAP CT-14); права по классу; поведение как у любого модуля Odoo |
| A-52 | Слой 3D — мост `td_energy_viewer3d` + аддитивные VX-01…VX-05 в `td_viewer3d`; ключ `energy.layer` не меняет `meta.schema` | `td_energy` не зависит от `td_viewer3d`; образец `td_constructor_viewer3d` |
| A-53 | `scene` узла = `equipment.td_code` или `node.code`; `C1`/`C2` → `CABLES` (худшее состояние); маркеры рисует клиент | Модель сцены имеет один объект кабелей |
| A-54 | Ночной режим — режимы BMS `VEL`/`VE` и `sp_night`; «30 %» — справочный текст | Что умеет `td_bms` (D-40) |
| A-55 | Эмулятор: сброс через `consumer_p` в `meter.py`; `export_demo`, `peak_load`; ручной режим PFC отключает ступени | Воспроизводимость макета на стенде |
| A-56 | Ограничение СЭС (`pv/limit_pct`) делит сторожевой таймер со сбросом (`shed/valid_s`) | Меньше регистров; одинаковая семантика fail-safe |
| A-57 | «Срезание пика» v1 — ступенчатый гистерезисный алгоритм по прогнозу 15-мин блока; не оптимизатор | Простота, проверяемость, безопасность |
| A-58 | План дня (`plan`/`scenario`) информационный; выполняются только ручные слоты BESS/КГУ | Прогноз не является командой; E-06 для редактирования |
| A-59 | Выключение сценария `pfc` пишет `pfc_mode=0` (класс B) | Семантика переключателя макета |
| A-60 | Второе подтверждение — другое лицо, TTL 600 с, без обхода администратором | E-06 |
| A-61 | Жёсткие проверки: `fail_closed` для безопасностно-критичных, `fail_open` для комфортных; флаги на строке реестра | Доступность без потери безопасности (R-41) |
| A-62 | Тест ДГУ — через адаптер моста (ADP-12), только `idle`, `td_genset` не меняется | E-01 |
| A-63 | (`td_genset_factory3d`) ADP-12 вызывает `_test_start('idle')` под `sudo`; права проверяет `td_energy_control` | `td_genset._td_check_group` пропускает `env.su`; права «Енергетика» ≠ `group_tech` |
| X-93 | (`td_viewer3d`) VX-01…VX-05 аддитивны; ядро не зависит от `td_energy`; без расширений поведение не меняется | Совместимость с `td_constructor_viewer3d` |
