# Ревю коду `td_genset` (Odoo 18.0) перед тестовим сервером

Гілка `claude/dreamy-ramanujan-p2wlej`, HEAD `9628f48`; обсяг — `git diff d062947..HEAD -- smartgen/td_genset`
(64 файли). Дата: 08.10.2026. Код не змінювався, git не чіпався.

Метод: сфокусоване трасування ризиків 1–8 (cron команд, забір, стан-машина, планувальник, події/тривоги, дані,
віджет, якість) від реального входу до результату; звірка з SPEC §4.1/§8/§9/§12, ТР 2.6.3/2.7/2.8/А.5–А.7,
`relay_api.md` і джерелами Odoo 18 (`odoo/addons/base/models/ir_cron.py`, `odoo/sql_db.py`,
`addons/bus/static/src/services/bus_service.js`, `addons/bus/models/ir_websocket.py`). Живий замір догону —
на тимчасовій базі `td_rev_perf` (видалена) з локальним `RelayMock` з `tests/common.py`; до реального
ретранслятора звернень не було. Безпекові знахідки зі `ЗВІТ_БЕЗПЕКИ_td_genset.md` тут не дублюються.

## Вердикт

**Можна на тест після двох невеликих правок 🟠 (п. 1–2).** Блокуючих 🔴 знахідок немає.
Підсумок: 🔴 0 · 🟠 2 · 🟡 6 · 🟢 12.

## 1. Знахідки

| № | Крит. | Файл:рядок | Сценарій (вхід → неправильний результат) | Виправлення | AC / ФВ |
| --- | --- | --- | --- | --- | --- |
| 1 | 🟠 | `models/genset_command.py:693–700` (гілка `link_restored_at` у `_step_awaiting`), `:938–948` (`_step_waiting_link` ставить `link_restored_at`), `:595–599` (`_post` його не скидає) | Команда в `awaiting` → зв'язок зник → `waiting_link` → відновлено (`link_restored_at = T2`, `attempt = 0`, нове вікно) → перший знімок не підтвердив → повтор POST → `done` (`done_at = T3`) → `awaiting`. Далі `link_restored_at` досі заповнений, тож: (а) будь-який знімок з `ts ≥ T3` і `ts > link_lost_at` дає `_confirmation_retry` **негайно**, без `done_at + retry_every_min` і `DONE_GRACE`; (б) якщо знімка після `T3` ще немає, а `now > T2 + retry_every_min + 1 хв` — повтор «немає знімка після відновлення зв'язку» **одразу після `done`**, не давши контролеру жодного знімка; (в) захист «поки триває пуск (стани 1–4) — без POST» у цій гілці не перевіряється. Наслідок: після відновлення зв'язку 5 спроб вичерпуються за ~5–6 хв (замість вікна 10 хв), тривога «не підтверджена за 10 хв» хибна; для `start`/тесту «без навантаження» повторний `start` може піти під час прокрутки | У `_post` (і в `_set_state('sent', …)`) скидати `link_restored_at = False`, `link_lost_at = False`; гілку `link_restored_at` застосовувати лише до першого рішення після відновлення (наприклад, умова `self.link_restored_at and (not self.done_at or self.done_at <= self.link_restored_at)`), далі — загальна логіка з `base + every`, `DONE_GRACE` і `_start_in_progress`. Регресійний тест: AC-18 з другою невдалою спробою після відновлення — перевірити інтервал між POST ≥ `retry_every_min` | AC-18, AC-14, AC-25, ФВ-9, ФВ-12, §4.1 п. 1, 3 |
| 2 | 🟠 | `static/src/pult/pult_widget.js:78` (`onWillStart(() => this.loadState())`), `:108–117` (`loadState`), `:119–129` (`refresh`), `:136`, `:139–146` (`fallbackPoll`) | `orm.call("get_pult_state")` або `record.load()` відхиляється (обрив мережі на телефоні, 30-с резервне опитування саме тоді, коли websocket не підключений, закінчена сесія, тимчасова 5xx) → у `onWillStart` виняток ламає рендер форми генератора; у `refresh()` з `setTimeout`/`setInterval` — необроблений Promise → діалог «Uncaught Promise … RPC_ERROR» щоразу (кожні 30 с при опитуванні) | Обгорнути `loadState()`/`refresh()` у `try/catch`: лишати попередній `state.pult`, у `onWillStart` при помилці показувати в шаблоні «Пульт тимчасово недоступний» замість падіння; помилки резервного опитування — без діалогу (лог/`notification` один раз). Тест: `TestW3UiHttp` з мок-відмовою RPC | AC-61, AC-62, ФВ-17, ФВ-43 |
| 3 | 🟡 | `models/genset_monitoring.py:62–66` (відмова `/status` → `return`), `:99–131` (`_td_relay_failed` не оновлює зв'язок), `:175` (єдиний виклик `_update_link_state` — усередині `_apply_status`) | Ретранслятор недоступний (таймаут/5xx) 20 хв → знімків немає, але `link_state` лишається `online`: картка «Онлайн», пульт активний (`can_control`), «Поточні дані» без банера застарілості, команда з пульта → POST → транспортні повтори → через 10 хв тривога «не підтверджена»; подія `link` і «Зв'язок відновлено після N хв» не створюються. ТР 2.8.6: «немає знімків ≥ `link_lost_min`» → `offline` незалежно від причини | У гілці `RelayUnavailable` в `_td_relay_failed` (і після відмови сторінки) викликати `gensets._update_link_state(None, now=now)` у savepoint — умова `fresh` за `last_reading_at`/`relay_last_reading_at` переведе в `offline` через 3 хв і поверне `online` після першого `/status` | AC-09, AC-10, AC-24, ФВ-7, 2.8.6 |
| 4 | 🟡 | `models/genset_command.py:624–630`, `:642–643` (`sent` ≥ 2 хв без фіналу → `timeout`), `:872–882` (`retry` → `to_send` → новий POST без перевірки старого `relay_cmd_id`) | `POST` → `201` → API ретранслятора недоступний 2–3 хв (команда на ретрансляторі виконалася) → `_relay_failed('timeout')` → новий POST тієї ж команди. Для режимів рятує `not_needed` у `_precheck` (за знімком), для `start` — ні (див. п. 5); для автоматів — лише якщо є свіжий знімок | При `RelayUnavailable` під час `sent` не рахувати `SENT_TIMEOUT` (чекати доступності API), або перед повторним POST один раз перечитати `GET /commands/<relay_cmd_id>` | AC-15, AC-17, ФВ-11 |
| 5 | 🟡 | `models/genset_command.py:951–989` (`_precheck_result`: для `start` немає умови «вже працює/триває пуск») | Повторний `start` (п. 1, п. 4 або звичайний повтор підтвердження) надсилається, коли двигун уже у станах 1–9 (прокрутка/прогрів/робота); `_start_in_progress` перевіряється лише в `awaiting` | У `_precheck_result`: `command == 'start'` і `genset.is_running`/`genset_status ∈ 5…9` → `not_needed` «уже працює»; `genset_status ∈ 1…4` → чекати хвилину (`to_send`), як для застарілого знімка автомата | AC-13, AC-25, AC-26, ФВ-9, ФВ-10 |
| 6 | 🟡 | `models/genset_monitoring.py:327–334` (`_apply_reading` → `write`) + `models/genset.py:183, 224, 254, 370` (`tracking=True` на `link_state`, `controller_mode`, `remote_lock`, `control_source`) | Догон 30 днів: кожна сторінка переписує стан генератора історичним останнім знімком → до ~90 tracking-повідомлень «Режим: Авто → Ручний» у чатері заднім числом (плюс bus `reading` на кожну сторінку) — шум поруч із «Догнано історію» | У `catchup_mode` писати стан `with_context(tracking_disable=True)` і не слати `_notify_bus('reading')` на кожну сторінку (лише після `_finish_catchup`) | AC-45, ФВ-3 |
| 7 | 🟡 | `models/genset_monitoring.py:145–146` (скидання `relay_unavailable_since` при будь-якому успішному `/status`) vs `:122–127` | `/status` працює, а `/readings` стабільно 5xx (частково зламаний ретранслятор) → лічильник щохвилини обнуляється → тривога «Ретранслятор недоступний N хв» ніколи не створюється, знімки не надходять, п. 3 також не спрацьовує | Скидати `relay_unavailable_since` лише після успішної сторінки `/readings` (або рахувати окремо для `/readings`) | AC-10, ФВ-7 |
| 8 | 🟡 | `models/genset_command.py:522–526` (`_start_window` перед очікуванням свіжого знімка для автомата) | Команда автомата при знімку старшому за 2 хв → `to_send` «Очікуємо показання», але `first_sent_at`/`deadline_at` уже поставлено → вікно повторів тече без жодного POST; при тривалій паузі знімків (до переходу в `offline` — 3 хв) частина вікна втрачається | `_start_window` викликати лише перед фактичним POST або транспортним повтором (А.5: «перша спроба POST, навіть невдала») | AC-15, AC-21, ФВ-14 |
| 9 | 🟢 | `models/genset_command.py:742–750` (`_find_confirmation` завжди викликає `GET /latest`) | SPEC §8: `/latest` — лише коли знімка з `ts ≥ done_at` ще немає; тепер — на кожному кроці `awaiting` (до 8 кроків за запуск) → зайві запити | Викликати `/latest`, лише якщо `readings` порожні | §8, ФВ-9 |
| 10 | 🟢 | `models/genset_command.py:719–721`, `:591` («Спроба N з M») | Політика `until_next`: після тривоги `attempt` далі росте → у журналі «Спроба 12 з 5» | Після тривоги показувати «повтор N після тривоги» або не збільшувати `attempt` | AC-34, ФВ-21 |
| 11 | 🟢 | `models/genset_monitoring.py:114, 170` (код `relay_hostid`) vs `models/genset_command.py:571` (код `relay_unknown_hostid`) | Та сама умова «ретранслятор не знає hostid» має два коди: тривогу з команди (`relay_unknown_hostid`) `_apply_status` ніколи не знімає | Один код (`relay_hostid`), знімати в `_apply_status` | AC-11, 2.8.4 |
| 12 | 🟢 | `models/genset_reading.py:921–943` (`convert_value`), `:164, :816` (`NO_DATA_RAW` лише для `regs`) | Якщо в `values` колись прийде числове `32766` (контракт обіцяє `null`), воно збережеться як значення (тиск оливи 32766 kPa) | Захисно: у `convert_value` для float/integer `32766` → `None` | AC-06, SPEC §4 |
| 13 | 🟢 | `models/genset_monitoring.py:256–288` (`_find_cursor_for_date`) | Бінарний пошук обмежений лише `log2(relay_last_reading_id)` (≈ 18–31 запитів по 20 с таймауту кожен) усередині одного savepoint першої сторінки; якщо сторінка після нього впаде — пошук повторюється щохвилини | Явний ліміт кроків (наприклад 40) і збереження знайденого курсору окремим savepoint до завантаження сторінки | А.7, AC-45 |
| 14 | 🟢 | `data/ir_cron.xml:45–46` (`nextcall` 00:30 UTC) | SPEC §12 «03:30 Kyiv»: узимку чистка о 02:30 за Києвом (коментар це визнає) | Прийнятно; або `nextcall` обчислювати через `kyiv_localize` у `post_init_hook` | AC-58 |
| 15 | 🟢 | `wizard/refuel_wizard_views.xml:59–70` | П'ятий cron `cron_recompute_liters` оголошений у файлі подань майстра і відсутній у SPEC §12 (є лише в §4.1 п. 14) | Перенести в `data/ir_cron.xml`, додати рядок у SPEC §12 | AC-69 |
| 16 | 🟢 | `static/src/pult/pult_widget.js:79–87, 100–102` | Підписка на канал і `loadState` — один раз у `onMounted`/`onWillStart`; якщо форма переходить на інший запис (⟨ ⟩ у списку з двома генераторами) без перестворення віджета, канал і стан лишаться від попереднього генератора | Перевірити на двох генераторах; за потреби `onWillUpdateProps` → перепідписка і `loadState` при зміні `record.resId` | AC-62 |
| 17 | 🟢 | `models/genset_event.py:614–634` (`_td_external_event`, вікно дублів ±12 хв за `mode_to`) | Дві незалежні зміни на той самий режим упродовж 12 хв (застосунок 10:00 → панель 10:08) зливаються в одну подію без другої тривоги | Дубль лише для пар «знімок ↔ хмара» (різні `source`), не для двох знімків | AC-27 |
| 18 | 🟢 | `models/genset_schedule.py:95` (повідомлення валідації) | Вікно через північ («22:00–06:00») за AC-29 відхиляється, але текст не підказує, що його треба ввести двома рядками (22:00–24:00 і наступний день 00:00–06:00; `_next_transition` такі рядки зливає коректно) | Доповнити текст помилки підказкою | AC-29, ФВ-18 |
| 19 | 🟢 | Дублі: `genset_monitoring.py:93–97` ≡ `genset_scheduler.py:65–69` (блокування рядка); `TECH_RELAY_CODES` з різним вмістом у `genset_monitoring.py:28` і `genset_command.py:87`; `MODE_COMMANDS` з різними кортежами у `genset_event.py:20` і `genset_command.py:75`; `KYIV` ×3 (`genset_reading.py:161`, `genset_fuel.py:65`, `genset_schedule.py:12`); `hhmm`/`kyiv_hhmm` ×3 (`genset_alarm.py:494`, `genset_schedule.py:63`, `genset_fuel.py:117`); три парсери часу (`genset_event.py:662`, `genset_command.py:107`, `genset_reading.py:901`); `_is_manual_stop_batch` (`genset_command.py:1005–1011`) робить `search` при кожному з 2–3 викликів на крок | Однойменні константи з різною семантикою — пастка при подальших правках | Винести в один модуль-утиліту (`tools.py`); перейменувати `MODE_COMMANDS`/`TECH_RELAY_CODES` за змістом; кешувати `_is_manual_stop_batch` на крок | якість |
| 20 | 🟢 | Міжблокові методи поза SPEC §9 / ТР А.11: `td.genset.event._td_process` (монiторинг кличе його замість задокументованого `_process_readings`, бо потрібна статистика), `_td_sync_signal_codes`, `_td_rows`; `td.genset.alarm._td_apply_state_alarms`, `_td_signal_state`; `td.genset._td_post_info`, `_td_check_group`, `_td_notification`, `_td_relay_failed`, `_pult_prepare`, `_timer_cancel_by_command`, `_test_end_early`; `td.genset.command._log_final`, `_trigger_cron`, `_precheck_result`; `td.genset.reading._td_values_with_ohms`, `_td_fix_nulls` | Контракт між потоками фактично ширший за задокументований | Додати до А.11/§9 (або зробити `_process_readings` таким, що повертає статистику, і прибрати виклик `_td_process` з монiторингу) | А.11, §9 |

## 2. Перевірено, проблем немає

1. **Cron команд** (`genset_command.py:417–479`). `_lock_due_ids` — `SELECT … FOR NO KEY UPDATE SKIP LOCKED` у транзакції
   cron до будь-якого savepoint, тож блокування переживає відкат кроку; другий воркер і наступний запуск бачать
   команду лише в новому стані з `next_attempt_at` у майбутньому — подвійна відправка одного `to_send` неможлива.
   Кожен крок — `with cr.savepoint()`; у Odoo 18 `_FlushingSavepoint.rollback()` сам робить `cr.clear()`
   (`odoo/sql_db.py:123–128`), тож `invalidate_all()` у `_process_due` надлишковий, але нешкідливий; помилка
   кроку → лог, `next_attempt_at += 1 хв`, решта команд обробляється, cron завершується без винятку
   (`_update_failure_count` не спрацьовує). `_trigger()` викликається в `_enqueue` (транзакція майстра/планувальника)
   і в `_schedule_next_run` поза savepoint; у `_trigger_list` запис `ir.cron.trigger` іде в тій самій транзакції,
   а `NOTIFY` — у `postcommit` (`ir_cron.py:674–703`): при відкаті savepoint планувальника тригер відкочується
   разом із командою, `NOTIFY` лише будить воркер — узгоджено. FK `ir_cron_trigger → ir_cron` потребує `FOR KEY SHARE`,
   сумісного з `FOR NO KEY UPDATE` воркера. `MAX_STEPS_PER_RUN = 8` і `DUE_TOLERANCE` 30 с дають каденцію
   «2, 4, 6, 8, 10-а хвилина» (AC-14). Пакет «Ручний + Стоп» — `ORDER BY genset_id, id`, обидва POST в одному
   кроці; ліміт 2 «у роботі» (`sent/awaiting/retry`) за А.5.
2. **Cron забору** (`genset_monitoring.py:46–91, 207–254`). Одна сторінка = один savepoint; `_notify_progress(done,
   remaining)` у `finally`; ручних `commit()`/`rollback()`/`sleep` у моделях немає (grep). За `ir_cron.py:398–450`
   `_run_job` комітить після кожного `_callback` і повторює до 10 разів при `remaining > 0`, далі `PARTIALLY_DONE`
   → `_reschedule_asap`. `RelayError` на сторінці → відкат savepoint, `readings_cursor` незмінний, cron завершується
   успішно (AC-04, AC-10). `_find_cursor_for_date` — бінарний пошук `limit=1`, монотонний, завершується за
   `log2(high)` кроків. **Замір** (`td_rev_perf`, `RelayMock`, ретранслятор 1.1.1 → `raw=1`, 2 500 знімків по
   1/хв з циклами «відключення → робота», `oil_pressure = null` кожен 97-й): сторінка 500 знімків — 1,6–2,1 с,
   пік виділеної пам'яті 13 МБ, 2 HTTP-запити (`/status` + `/readings`; на першій ще 1 проба курсору), RSS процесу
   189 МБ. Догон 30 днів (43 200 знімків) ≈ 87 сторінок ≈ 2,5 хв сумарно: ~9 запусків cron по 10 сторінок
   (≈ 17–20 с кожен) — укладається в типовий `limit_time_real_cron` 120 с (на проді не підтверджено — ТР 2.6.2 п. 5).
   Після догону: `catchup_mode = False`, 7 подій `run` + 7 `outage`, тривог 0 (у догоні не створюються, остання
   сторінка не мала активних умов), чатер «Догнано історію: 2 днів, 2500 знімків, 14 подій» (AC-45).
3. **Стан-машина**. `awaiting` без знімків після `done_at` чекає (`next_attempt_at += 1 хв`), повтор — лише за
   знімком з `ts ≥ done_at` і незміненим режимом не раніше `done_at + retry_every_min` (з `DONE_GRACE`), або без
   знімка довше `retry_every_min + 1 хв` при `online` (§4.1 п. 3) — поза сценарієм п. 1. `waiting_link` →
   `deadline_at = max(deadline + час без зв'язку, now + вікно)`, `attempt = 0`. Пакет «Ручний + Стоп»: при
   `controller_mode = stop` обидві `not_needed` «Не потрібно: уже Стоп», інакше обидві надсилаються й у Ручному;
   `manual` підтверджується `{manual, stop}`, `stop` — `gen_on_load = False` і стан `{10…13, 15, 0}`. Автомати —
   лише за знімком ≤ 2 хв (`FRESH_READING`), збіг із ціллю → `not_needed`. `until_next`: тривога один раз
   (`alarm_raised_at`), далі `to_send` кожні `late_retry_every_min`; підтвердження знімає `cmd_unconfirmed`/
   `breaker_unconfirmed`. `_cancel_pending` викликається **до** `_enqueue` у `_schedule_transition`,
   `_follow_schedule`, `_timer_start`, `_test_start`, `_test_finish` — команди поточного переходу не чіпає;
   `sent/awaiting` лише позначаються `cancel_requested` і скасовуються при першому `retry` (А.5).
   `crank_failure` у будь-якому знімку після `done_at` для `start`/`test` → `failed` + тривога, без повторів (AC-26).
4. **Планувальник**. Перший запуск без `sched_last_eval_at` — лише запам'ятовує стан (`genset_scheduler.py:76–78`).
   Вікно через північ — двома рядками (AC-29 вимагає відмову для «18:00–09:00»); `kyiv_localize(day, 24.0)` → 00:00
   наступного дня, `_next_transition` зливає дотичні вікна (у т. ч. через північ) — межа опівночі не є переходом.
   DST: `kyiv_localize` — `NonExistentTimeError` → 04:00, `AmbiguousTimeError` → `is_dst=True`; вікна порівнюються
   як UTC-моменти, тож повторна година 25.10.2026 не дає других команд, а 29.03.2026 `auto` іде о 04:00 (AC-37;
   тести `test_ac37_dst_spring_forward/_fall_back` перевіряють саме ці ночі й `_window_moments`). Пропущений
   перехід: `now − sched_last_eval_at > 2 хв` → межа з `_next_transition` → `late_transition_at`, а `_precheck`
   пропускає команду, якщо після межі є `external_control` (AC-34, ФВ-21). Таймер: 1 хв…24 год, `+15/+30/+60` —
   не далі `now + 24 год` (`genset_scheduler.py:286–295`); тест повертає в режим за таймером (з паузи) або
   розкладом (`_test_finish`); `_next_transition` обходить 9 днів (−1…+7) з винятками через `_window_bounds`.
5. **Події/тривоги**. Межі — за `relay_id` (`_td_process` фільтрує `relay_id > prev_reading.relay_id`, рядки
   `ORDER BY relay_id`). «Керування не з Odoo» не спрацьовує на власні команди: `_td_odoo_command` шукає команду
   з тим самим цільовим режимом/автоматом за `retry_window_min + 2` хв (`genset_event.py:651–658`); автомати — лише
   в Ручному без зміни `is_running`/`mains_ok` (§4.1 п. 10); `cloud_commands_seen` — лише записи новіші за
   `cloud_cmd_last_utc`, перший `/status` не породжує історичних подій. Ескалація (`genset_alarm.py:409–446`):
   рівень без користувача пропускається з попередженням у логах і затримки йдуть далі (§4.1 п. 12); `not_quiet` у
   тихі години → `next_escalation_at = _quiet_end` (інтервал через північ, `genset_config.py:214–243`); `always` —
   не переноситься; `chatter` — лише чатер. «Прийняв» → `acked`, `next_escalation_at = NULL`, `_cron_escalate`
   бере лише `active`; `_raise` не дублює незняті (`state != cleared`, тобто й `acked`). Фронт `True→False`
   закриває подію й знімає тривогу (`_td_sync_signal_codes`); сигнали `gen_*` — лише у станах 8–9 (§4.1 п. 5).
   `link_lost`: `offline` через `link_lost_min` без даних (`link_changed_at = останні дані + 3 хв`), тривога через
   `link_alarm_min` від цього моменту — ≈ 13 хв (§4.1 п. 4). Догон: `_td_sync_signal_codes(raise_alarms=False)`,
   `_td_rule_fuel`/`_td_external_event` без `_raise`, ТО і запас каністр пропускаються (`genset_fuel.py:857, 1185`),
   `refuel_unconfirmed` не створюється (`:664`); після догону `_evaluate_current` піднімає актуальні сигнали,
   датчики без даних і низький рівень палива, знімає застарілі (`genset_alarm.py:465–484`) — підтверджено заміром.
6. **Дані**. `_create_from_payload` передає в `create` лише ключі з не-`None` значенням (`convert_value`), тож
   `null` і відсутній ключ → NULL у базі, а `_td_fix_nulls` додатково обнуляє `fuel_liters`/`fuel_source`/
   `run_hours_total` там, де їх немає з чого обчислити; `last_values_json` зберігає `values` з `null`
   (AC-06). Перерахунок літрів (`_recompute_liters_batch`, `genset_fuel.py:948–1000`): `level is None` → NULL
   лишається NULL. Оми: ключі `*_sensor_ohm` (≥ 1.1.3) або `regs["18"|"20"|"22"] / 10` з відкиданням `32766`;
   решта `regs`/`coils` не зберігається (AC-68; перевірено на `raw=1`). `values_extra` — лише невідомі ключі,
   `*_text` відкинуті. `fuel_liters` у картці після догону — 126 L `pct` при 87 % і 145 L.
7. **Віджет**. `onWillUnmount`: `unsubscribe`, `deleteChannel`, `clearTimeout`/`clearInterval` усіх трьох
   таймерів; `fallbackPoll` порівнює з `"CONNECTED"` — саме таке значення `WORKER_STATE` в Odoo 18
   (`websocket_worker.js:36–41`), `bus_service.isActive` існує (`bus_service.js:252`); дебаунс 500 мс, `record.load()`
   пропускається для «брудного» запису. Без генератора (`resId` порожній) — текст «Збережіть генератор…», запитів
   немає. `get_pult_state` → `check_access('read')`, без адреси/токена. `current_data_html`: усі значення — через
   `markupsafe.escape` або `Markup % …` (підписи, `relay_hostid`, `relay_version`, ключі `values_extra`);
   у шаблоні OWL — лише `t-esc`, `t-raw`/`t-out` немає. `_build_bus_channel_list(channels)` відповідає сигнатурі
   Odoo 18 (`addons/bus/models/ir_websocket.py:58`), зразок `mail`.
8. **Якість**. Маркерів «Заглушка W0»/`TODO`/`FIXME` у коді немає (лишилась лише константа `STUB_MARK` у
   `tests/test_w0_smoke.py:23`). Усі `UserError`/`ValidationError`/`AccessError`, тексти чатера, сповіщень і
   `display_notification` — через `_()`/`_lt()`; літерали поза `_()` — лише мітки selection і повідомлення
   `_sql_constraints` (їх Odoo перекладає сам); у `pult_widget.js` — `_t`, текст шаблону перекладається
   стандартно. Забороненого синтаксису (`<tree>`, `attrs`, `states`, `t-raw`, `group_operator`) у поданнях
   немає. Жодних звернень до `gen-relay.todo.ltd` з тестів; токен у логах маскується.

## 3. Відхилення від SPEC, не відображені в §4.1

| # | Де | Що в коді | Що в SPEC/ТР | Оцінка |
| --- | --- | --- | --- | --- |
| 1 | `genset_command.py:742–750` | `GET /latest` на кожному кроці `awaiting` | §8: лише якщо знімка з `ts ≥ done_at` ще немає | 🟢, п. 9 |
| 2 | `genset_monitoring.py:62–66, 175` | `link_state` переоцінюється лише при успішному `/status` | 2.8.6: `offline`, коли немає знімків ≥ `link_lost_min` (будь-яка причина) | 🟡, п. 3 |
| 3 | `genset_event.py:22` (`ODOO_COMMAND_STATES`) | Для «керування не з Odoo» враховуються й команди у станах `waiting_link/done/done_late/failed` | 2.8.1: `sent/awaiting/retry` | корисне розширення (зміна, що підтвердила нашу `done`-команду, не вважається зовнішньою); зафіксувати в §4.1 |
| 4 | `genset_command.py:622–623` | `404 no such command` на `GET /commands/<id>` → як `failed` → повтор | 2.6.3 цього випадку не описує | прийнятно; зафіксувати |
| 5 | `genset_command.py:565–581`, `genset_monitoring.py:111–117` | Тех. тривоги `relay_cmd_rejected`, `relay_unknown_hostid`, `relay_hostid` | 2.8.4 їх не містить (там `relay_cmd_format`, `relay_cmd_disabled`, `relay_auth`, `relay_health`, `relay_unavailable`) | додати в 2.8.4, звести до одного коду (п. 11) |
| 6 | `genset_alarm.py:440–445` | `next_escalation_at` наступного рівня = запланований момент поточного + (`delay_{i+1}` − `delay_i`) | 2.8.2: `date_raised + next_level.delay_min` | збігається без тихих годин; після переносу на кінець тихих годин наступні рівні зсуваються разом (логічніше) — зафіксувати |
| 7 | `genset_command.py:522–526` | Вікно повторів стартує при очікуванні свіжого знімка для автомата | А.5: від першої спроби POST | 🟡, п. 8 |
| 8 | `wizard/refuel_wizard_views.xml:59–70` | П'ятий cron `cron_recompute_liters` (1 день, priority 20, запуск через `_trigger()`) | §12 — чотири cron | 🟢, п. 15 |
| 9 | `data/ir_cron.xml:45–46` | `cron_cleanup` о 00:30 UTC | §12: 03:30 Kyiv | 🟢, п. 14 |
| 10 | `genset_command.py:1023` | `_cancel_pending(…, sources=('schedule','timer','exception','test'))` — команди з пульта (`button`) не скасовуються новим переходом/таймером | 2.6.3: «новий перехід/таймер/тест скасовує незавершені команди попереднього переходу» (без уточнення джерел) | узгоджено з А.5 (переходи скасовують лише автоматичні); зафіксувати в §4.1 |
| 11 | `genset_scheduler.py:80–87` | Пропущений перехід визначається як `in_window(now) ≠ sched_in_window`; зміна рядків розкладу під час роботи теж дає перехід на наступній хвилині | 2.7.2 п. 2–3 описує порівняння з `in_window(sched_last_eval_at)` | еквівалентно для простою; для редагування розкладу — очікувана поведінка «лише на переходах», зафіксувати |
| 12 | `genset_config.py:294–303` | Перший рівень ланцюжка зобов'язаний мати `delay_min = 0`, затримки не спадають | 2.3.9 такої перевірки не описує | корисна валідація; зафіксувати |

## Додаток. Протокол заміру догону

База `td_rev_perf` (копія `td_template` + `td_genset`), `odoo-bin shell`, `RelayMock` з `tests/common.py`
(патч `requests.Session.request`), генератор «Perf» (`relay_enabled`, `catchup_from_date = −30 днів`),
2 500 знімків по хвилині (останній — за хвилину до запуску): цикл 360 хв — 18–19-а хв прокрутка (стан 3),
20–49-а робота під навантаженням без мережі (стан 9), решта очікування; `oil_pressure = null` кожні 97 хв;
рівень палива −1 % кожні 300 хв. Запуски `_cron_pull_readings()` з `commit()` після кожного:

| Сторінка | Час, с | Пік пам'яті, МБ | HTTP | Курсор | `catchup_mode` |
| --- | --- | --- | --- | --- | --- |
| 1 | 2,08 | 13,5 | 3 (1 проба курсору) | 500 | так |
| 2 | 1,75 | 13,0 | 2 | 1000 | так |
| 3 | 1,63 | 13,1 | 2 | 1500 | так |
| 4 | 1,65 | 13,1 | 2 | 2000 | так |
| 5 | 1,72 | 13,1 | 2 | 2500 | ні (`_finish_catchup`) |

Підсумок: події `run` 7, `outage` 7, `gap` 0; тривог 0; `link_state = online`; `fuel_liters` 126 L (`pct`),
`fuel_sensor_ohm` 189,2 Ом з `regs`; чатер — «Догнано історію: 2 днів, 2500 знімків, 14 подій.». Базу видалено.

---

## Статус виправлень (08.10.2026)

Виправлено обидві 🟠 і п'ять 🟡 знахідок (п. 1–8); решта — у беклог. Гілка `claude/dreamy-ramanujan-p2wlej`, коміти
після `6b84fbe` (без push). Кожне виправлення логіки має регресійний тест; без виправлень ці 8 тестів падають
(контрольний прогін на коді з відкоченими моделями й віджетом), з виправленнями — зелені.

| № | Крит. | Що зроблено | Коміт | Регресійний тест |
| --- | --- | --- | --- | --- |
| 1 | 🟠 | `_post` скидає `link_restored_at`/`link_lost_at`; гілка «перший знімок після відновлення вирішує» — лише до першого нового POST (`done_at ≤ link_restored_at`), далі — `done_at + retry_every_min`, `DONE_GRACE`, «триває пуск 1–4» | `90ff4d6` | `TestW2Commands.test_ac18_after_link_restore_next_retry_waits_interval` |
| 2 | 🟠 | `pult_widget.js`: `loadState()`/`refresh()` у `try/catch`; без даних — «Пульт тимчасово недоступний», з даними — останній стан із позначкою; одне сповіщення на серію помилок; після помилки — повтор резервним опитуванням і при живому websocket | `88cf87c` | `TestW3UiHttp.test_ac62_pult_survives_rpc_failure` (Chrome) |
| 3 | 🟡 | `_td_relay_failed` (таймаут/5xx) → `_update_link_state(None)`: знімків немає ≥ `link_lost_min` → «Немає зв'язку» і коли недоступний сам ретранслятор | `b3a6d17` | `TestW1LinkHealth.test_ac09_relay_unavailable_link_goes_offline` |
| 4 | 🟡 | `sent` + `RelayUnavailable` — 2 хв не рахуються, `GET /commands/<id>` перечитується, щойно API відповість (без повторного POST) | `15ccf14` | `TestW2Commands.test_ac17_sent_relay_unavailable_no_repost` |
| 5 | 🟡 | `_precheck` для `start`: двигун працює → «Не потрібно: генератор уже працює»; стани 1–4 → чекати без POST | `15ccf14` | `TestW2Commands.test_ac25_start_when_running_or_cranking` |
| 6 | 🟡 | Догон: `_track_discard` на транзакцію сторінки (без трекінгу «Режим: …»/«Керує: …» заднім числом), bus `reading` — один раз після `_finish_catchup` | `b3a6d17` | `TestW1PullReadings.test_ac45_catchup_without_alarm_avalanche` (трекінг і bus) |
| 7 | 🟡 | `relay_unavailable_since` і тривогу `relay_unavailable` скидає лише успішна сторінка `/readings` (`_td_relay_available`), не будь-який успішний `/status` | `b3a6d17` | `TestW1LinkHealth.test_ac10_readings_5xx_counts_even_if_status_ok` |
| 8 | 🟡 | `_start_window` — лише перед POST або транспортним повтором, не під час очікування свіжого знімка автомата чи кінця пуску | `15ccf14` | `TestW2Commands.test_ac21_breaker_window_starts_with_first_post` |
| — | — | Нові тексти — в `i18n/uk_UA.po` (1858 рядків, без порожніх і `fuzzy`) | `461d58d` | — |

**Перевірка (HEAD `461d58d`):** `run_tests.sh td_int_d` — код 0, 154 тести (147 + 7 нових), без WARNING/ERROR;
`run_stand_tests.sh td_int_d_stand` — 45/45; `update.sh td_int_d` — код 0.

**Беклог (лишено як є):**

- п. 9 — `GET /latest` на кожному кроці `awaiting` (SPEC §8: лише коли знімка з `ts ≥ done_at` ще немає);
- п. 10 — «Спроба N з M» росте після тривоги за політикою `until_next`;
- п. 11 — два коди для «ретранслятор не знає hostid» (`relay_hostid` / `relay_unknown_hostid`), тех. коди поза 2.8.4
  (`relay_cmd_rejected`, `relay_unknown_hostid`, `relay_hostid`) — звести й додати в 2.8.4;
- п. 12 — захисне `32766` → `None` у `convert_value` для чисел з `values`;
- п. 13 — ліміт кроків бінарного пошуку курсору й окремий savepoint для знайденого курсору;
- п. 14 — `cron_cleanup` з `nextcall` 00:30 UTC: 03:30 за Києвом улітку (UTC+3), 02:30 узимку (UTC+2); SPEC §12 —
  «03:30 Kyiv»;
- п. 15 — п'ятий cron `cron_recompute_liters` оголошено в `wizard/refuel_wizard_views.xml`, у SPEC §12 його немає;
- п. 16 — перепідписка віджета пульта при переході на інший запис без перестворення (`onWillUpdateProps`);
- п. 17 — злиття двох незалежних подій «Керування не з Odoo» на той самий режим у межах 12 хв;
- п. 18 — підказка про вікно через північ у тексті помилки розкладу;
- п. 19 — дублі хелперів і однойменні константи з різним змістом (`MODE_COMMANDS`, `KYIV`, `hhmm`/`kyiv_hhmm`,
  парсери часу; `TECH_RELAY_CODES` у моніторингу прибрано в `b3a6d17`) → модуль-утиліта; кеш
  `_is_manual_stop_batch` на крок;
- п. 20 — міжблокові методи поза SPEC §9 / ТР А.11 — задокументувати;
- розділ 3, п. 3, 4, 6, 10, 11, 12 — зафіксувати в SPEC §4.1 як прийняту поведінку.
