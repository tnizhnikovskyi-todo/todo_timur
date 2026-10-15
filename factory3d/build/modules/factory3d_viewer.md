# factory3d_viewer
Статус: IN_PROGRESS — интеграционный прогон (менеджер): совместимость с access/telemetry, демо-детект; ранее DONE (юнит/HOOT/туры/стенд на CE-шаблоне); вне среды: копия демо-базы `odoo`, ТК-07 планшет, dist/index.html (Blender)
Тесты: 170/170 пусто, 211/211 демо-шаблон f3d_demo_tpl (+viewer_sale, test-модуль, 54 hoot, туры), TestDemoWizard 2/2; ruff OK (2026-10-15); ТК: 11 прогнаны ✅, ТК-07 ⏭
Решений без заказчика: 19 (ниже)
Упирался в лимит: 0
Требует внимания человека: прогон на копии базы `odoo` (тесты считают ожидания из данных CE-шаблона, DEC-11); ТК-07 на планшете; AC-38 пересборка dist (Blender); eslint с prettier (нет сети); подпись security-review §13.3 менеджером; правки SPEC: DEC-5, DEC-12, DEC-15; мелочь: повторный ▶ не останавливает програвання (ТК-09)

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| D (демо-шаблон) | принят | 1bdb774 | f3d_demo_tpl: 35 РЦ, 731 лок., WH/MO/00231, base+iot_sim |
| W0 | принят | e59553e | TestInstall 6/6 (1 skip без демо) |
| W1a | принят | e3fcaea | /factory3d_viewer+/test_factory3d_viewer 60/60 (демо-тесты skip) |
| W1b-1 | принят (на демо 9 FAIL → W1c) | 3c285ed | 111/111 пусто; демо 132/141 |
| W1c (демо-фиксы) | принят | edeb760 | 131/131 пусто; демо 161/161 |
| W3 | принят | 45ff25b | 131/131 пусто; демо — те же 9 FAIL (W1c) |
| W1b-2 | принят (дельта chains ждёт W1b-1) | 4a7da35 | 84/84 (демо skip) |
| W2 | принят | 90dd23b | TestViewerHoot 52 hoot; демо 162/162 |
| W4 | принят | 2859c22 | демо 185/185, пусто 155/155, туры OK |
| W5 | принят | 7bb4e6b | демо 192/192; TestDemoWizard 2/2 (354 с); ruff OK |
| W4b (флейк тура) | принят | b64290b | без ERROR в логе |
| ТК (стенд) | принят | bc72b6e | 11 ✅, ТК-07 ⏭ |
| W5c (майстер UI/крон) | принят | 3f872cf | пусто 170, демо 211; TestDemoWizard 2/2 |
| W2c (знімки, банер) | принят | d0880e1 | hoot 54; пусто 167, демо 208 |
| W6 | принят | 868aa12 | TestPerf+TestNeutralize 9/9; SQL-пороги AC-52 не держатся → W7 |
| W7 (SQL AC-52, uninstall) | принят | 1fcfa70 | /data 202→75 запр., /delta 64→29; демо 202/202 |

## Решения без заказчика
- DEC-1: §13.0 требует копию демо-базы `odoo`, её в среде нет — шаблон `f3d_demo_tpl` собирается из `f3d_template`
  установкой `factory3d_base,factory3d_iot_sim` и заливкой `plant/odoo_push.py` по XML-RPC (скрипт
  `factory3d/tools/odoo/make_demo_tpl.sh`); прогоны с демо — `F3D_TEMPLATE_DB=f3d_demo_tpl run_tests.sh …`.
- DEC-2: порядок data в manifest — `security/kiosk_user.xml` после `data/actions.xml` (user_kiosk ссылается на action_f3d_viewer); строки access/правила/меню/кроны добавляются вместе с моделями воркеров. — `__manifest__.py`
- DEC-3: W1 разбит на W1a (M-01, tools, API, test_factory3d_viewer) и W1b (провайдеры M-01a…h) — объём не помещается в один контекст воркера; порядок слияния W1a → W1b → W3.
- DEC-4: `zz_fail` бросает ValueError только при context `zz_fail` или параметре `factory3d.test.zz_fail` — иначе ERROR в логе валит каждый прогон (run_tests strict). — `test_factory3d_viewer/models/providers.py`
- DEC-5: встроенные провайдеры — по файлу на провайдер `models/viewer_provider_<key>.py` (а не все в `viewer_provider.py`) — параллельная сборка W1b-1/W1b-2 без конфликтов.
- DEC-6: провайдеры chains/signals сами пишут свой статус в `meta.sections` (live/partial/missing/denied); `docks` пишет logistics, не chains. — `models/viewer_provider_chains.py`, `viewer_provider_signals.py`
- DEC-7: в шаблоне f3d_demo_tpl шаги push `modules,iot_module,signals` пропущены (Enterprise iot, zip-импорт); `x_f3d_signal` пуст, сигналы есть в `f3d_sim_signal` (1168) — AC-17 на демо проверяется моками; `plant/odoo_push.py` получил CE-правки (поля Enterprise через fields_get, lot_name при приёмке). — `factory3d/tools/odoo/make_demo_tpl.sh`
- DEC-8: ir.rule только чтение для group_f3d_user на maintenance.equipment/request с f3d_code (в Odoo 19 обычный пользователь видит лишь «свои» — противоречит §4.4). — `security/security.xml`
- DEC-9: `energy.profile_k` нет в model_static.json — запасная таблица PROFILE_KF из plant/energy.py; `next_maintenance` — ближайшая открытая preventive-заявка (в 19 нет next_action_date). — `models/viewer_provider_production.py`, `viewer_provider_maintenance.py`
- DEC-10: эмиттеры шины перекрывают также `_write_multi` (вычисляемые state пишутся через flush); `_since` по `ts >= since` (точность — секунда); идемпотентность 60 с только для periodic; ACL res.config.settings для group_f3d_admin (иначе пункт меню не виден, сохранение — base.group_system). — `models/bus_emitters.py`, `viewer_event.py`, `viewer_snapshot.py`, `security/ir.model.access.csv`
- DEC-11: отличия CE-шаблона от базы `odoo` (696 кодовых локаций вместо 689, пересекающиеся логи OEE, потери «Equipment Failure», нет нумерации MR/…) — тесты считают ожидание из данных по правилу SPEC, хардкод SPEC проверяется при совпадении данных; в коде: KIT-* получают picking/production, FR-компоненты → to=ASM, DOCK-* не в source_locations. — `tests/test_payload_*.py`, `tools/chains.py`, `models/viewer_provider_stock.py`, `viewer_provider_logistics.py`
- DEC-12: клиент — панель/оверлей/поток/учения/энергия в одном `core.js` (общее замыкание), без разбиения на panel/overlay/flow/drill/energy.js; порог lite `deviceMemory <= 4` (Chrome отдаёт максимум 8 — при `<= 8` lite был бы всегда); вложенные шаблонные литералы запрещены (rjsmin их портит). — `static/src/viewer/core.js`, `lite.js`
- DEC-13: майстер демо не ставит модули (шаг modules → skipped с перечнем; button_immediate_install в кроне опасен); после шагов вызываются хуки base (codes, passports.link, docks.register, zones.bind); пункт «Демо-дані» в корне меню (seq 16, AC-64). — `wizard/demo_steps.py`, `views/menus.xml`
- DEC-14: тур киоска — browser_js в test_tours.py (на странице киоска нет tour manager); click_open_record_tour — нулевой рендерер (f3d_test), т.к. WebGL в headless Chrome медленный; sale.order.action_f3d_show ищет МО по origin. — `tests/test_tours.py`, `factory3d_viewer_sale/models/sale_order.py`
- DEC-15: `neutralize.sql` лежит в `data/` (Odoo читает только `data/neutralize.sql`), а не в корне модуля, как в дереве SPEC §0; дополнительно `bus_enabled=False` (§13.3). — `data/neutralize.sql`
- DEC-16: AC-38 `dist/index.html` не пересобран — `build_scene.py --embed` требует Blender (`bpy`); `factory3d/viewer/index.html` уже обёртка над ядром, GLB в static совпадают с dist побайтно. eslint: конфиг Odoo требует prettier (нет сети) — прочие правила Odoo 0 ошибок. — `docs/modules/factory3d_viewer/DEPLOY_TEST.md`
- DEC-17: PayloadBuilder — оптимистичный проход под одним savepoint; при сбое провайдера откат и повтор с изоляцией каждого (AC-13 сохраняется, −2 SQL на провайдер); uninstall удаляет ir.model.data user_kiosk и архивирует пользователя. — `tools/payload.py`, `hooks.py`
- DEC-18: `f3d.viewer.snapshot.ts` берётся из `dates.now(env)` (шкала demo_clock, A-10), чтобы `shift_date` совпадал с «сегодня» API-05 при демо-часах; на проде demo_clock пуст — реальное время. — `models/viewer_snapshot.py`
- DEC-19: в `demo_steps.py` `print` переопределён на запись в лог майстра (порт plant без правки текстов шагов) — не stdout; майстер не деактивирует свой крон изнутри (Odoo 19 запрещает), крон выходит сам при пустой очереди; «зависший» running старше 35 мин не блокирует новый запуск. — `wizard/demo_steps.py:38`, `wizard/demo_wizard.py`
