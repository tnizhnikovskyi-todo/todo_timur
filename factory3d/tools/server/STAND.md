# Постоянный стенд на тестовом сервере (E-11)

Стенд = эмулятор оборудования `iot_sim` + сборщик сигналов `collector` (плагины: modbus_tcp, mqtt, http_push,
bacnet_ip, helvarnet, sics, opcua, rest_vendor) + имитатор ретранслятора SmartGen `fake_relay` (профиль D700) для
приложения «Генератори» (`td_genset`). Эмулятор поднимает «оборудование» по протоколам, сборщик читает его
и шлёт показания в Odoo (`/f3d/telemetry/*`, модуль `td_telemetry`), поэтому `td.signal` и все модули поверх него
(энергетика, здание, двор, верстаты) работают на живых данных. Раньше стенд жил в контейнере менеджера и умирал вместе
с ним; теперь это службы systemd на самом сервере (`td-iot-sim`, `td-collector`, `td-genset-relay`). Маршруты `/f3d/...` и коды сигналов не менялись (RENAME.md §3).

Файлы: `install_stand.sh` (ставит на сервере), `stand_odoo_setup.py` (Odoo-сторона, запускает менеджер снаружи).

## Кто что делает

| Шаг | Кто | Команда |
|---|---|---|
| 1. Новая БД `odoo`, модули `td_*` установлены (RENAME.md §7) | менеджер | — |
| 2. Токены и параметры в Odoo | менеджер | `stand_odoo_setup.py setup > td-stand.secrets` |
| 3. Передать файл `td-stand.secrets` клиенту (два значения, не хранить в git и чатах) | менеджер | — |
| 4. Проверка без изменений | клиент | `sudo TD_SECRETS_FILE=/root/td-stand.secrets bash <клон>/factory3d/tools/server/install_stand.sh --check` |
| 5. Установка | клиент | `sudo TD_SECRETS_FILE=/root/td-stand.secrets bash <клон>/factory3d/tools/server/install_stand.sh` |
| 6. История за 90 дней (через ≥ 5 минут после п. 5) | менеджер | `stand_odoo_setup.py backfill` |
| 7. Живой генератор `td_genset` (см. «Живой генератор» ниже) | менеджер, затем клиент | `stand_odoo_setup.py genset --token-file td-stand.secrets --wait 0`, затем установка (п. 5) с тем же файлом |

После установки файл с токенами можно удалить: значения лежат в `/etc/td-stand/*.env` (0640 root:td-stand).

## Команды клиента

    sudo TD_SECRETS_FILE=/root/td-stand.secrets bash install_stand.sh --check   # план, ничего не меняет; код 3 = есть препятствия
    sudo TD_SECRETS_FILE=/root/td-stand.secrets bash install_stand.sh           # установить или обновить (идемпотентно)
    sudo bash install_stand.sh --status                                         # службы, health, ответ Odoo
    sudo bash install_stand.sh --uninstall [--purge]                            # снять службы и venv; Odoo и БД не трогает
    sudo TD_SECRETS_FILE=… bash install_stand.sh --no-relay                     # без имитатора ретранслятора (как было раньше)

Токены можно передать иначе: переменные `TD_COLLECTOR_TOKEN` / `TD_SIM_API_TOKEN` / `TD_RELAY_API_TOKEN` /
`TD_RELAY_SIM_TOKEN`, файлы `TD_COLLECTOR_TOKEN_FILE` / `TD_SIM_API_TOKEN_FILE` / `TD_RELAY_API_TOKEN_FILE` /
`TD_RELAY_SIM_TOKEN_FILE` (в файле только значение). Токены имитатора ретранслятора в файле секретов необязательны: без них
установка генерирует свои (тогда менеджер берёт их из `/etc/td-stand/genset-relay.env`, см. ниже). Повторный запуск без токенов берёт значения из `/etc/td-stand/*.env`.
Обновление кода стенда: `git pull` в git-клоне (на timur-o19demo — `/opt/timur-o19/timur-o19e/git/todo_timur`), затем снова `install_stand.sh` (пересоберёт venv, если изменились
исходники `factory3d/services`, и перезапустит изменившиеся службы). Новые токены: менеджер делает `setup --rotate`,
клиент запускает установку с новым файлом.

Переменные: `TD_REPO` (git-клон, по умолчанию тот, где лежит скрипт), `TD_ODOO_URL` (`http://127.0.0.1:8069`),
`TD_COLLECTOR_CODE` (`COL-MAIN`), `TD_PUSH_PORT` (8080), `TD_SIM_PORT_BIOSTAR_HTTP` (HTTP-порт эмулятора BioStar,
8081; пишется в `iot-sim.env` как `SIM_PORT_BIOSTAR_HTTP`; Odoo и сборщик ходят в BioStar по HTTPS 8443, им менять
нечего), `TD_SIM_PORT_GENSET_RELAY` (порт имитатора ретранслятора, 8087; проверяются диапазон 1…65535, совпадение с другими
портами стенда и то, что порт не 8081), `TD_GENSET_RELAY_HOSTID` (hostid имитатора, по умолчанию `53494D47454E534554443730`,
не совпадает с hostid настоящего модуля), `TD_PYTHON`, `TD_IP_FILTER=0` (не ограничивать сеть служб),
`TD_IP_ALLOW` (доп. сети в фильтр `IPAddressAllow` служб через пробел, например `172.16.0.0/12`, чтобы Odoo из
контейнера Docker обращался к эмулятору; фильтр остаётся включённым), `TD_HARDEN=0` (без песочницы systemd: нужен, если в `journalctl` у службы `status=226/NAMESPACE`, например в LXC),
`--no-mqtt` (не ставить брокер).

**timur-o19demo** (Odoo в Docker, опубликован на хосте как 127.0.0.1:8094; 127.0.0.1:8081 занят ретранслятором SmartGen,
его не трогаем; клон — `/opt/timur-o19/timur-o19e/git/todo_timur`, пути `/mnt/f3d-addons` на хосте нет):

    sudo TD_SECRETS_FILE=/root/td-stand.secrets TD_ODOO_URL=http://127.0.0.1:8094 TD_SIM_PORT_BIOSTAR_HTTP=8181 \
        TD_IP_ALLOW=172.16.0.0/12 \
        bash /opt/timur-o19/timur-o19e/git/todo_timur/factory3d/tools/server/install_stand.sh --check

Затем та же команда без `--check`. Обращение Odoo → эмулятор (`td.iot_sim.url`, сценарии и сбои из пульта) из контейнера
в сети bridge не попадёт на `127.0.0.1:8090` хоста: менеджер задаёт `td.iot_sim.url` = адрес хоста со стороны
контейнера (шлюз сети compose, на timur-o19demo `http://172.18.0.1:8090`; `stand_odoo_setup.py params` с `TD_SIM_URL`),
а установка — `TD_IP_ALLOW=172.16.0.0/12`, чтобы фильтр служб пропускал сеть Docker. Сбор показаний это не затрагивает.

Плагины сборщика: `f3d_collector_bms`, `f3d_collector_yard`, `machine_connect`, `td_collector_energy` (`energy_ctl`,
автоматика энергетики W2). Источник `GENSET-RELAY` (`td_genset`) сборщик не опрашивает: Odoo ходит к ретранслятору
сам (локальный тип источника, его `state` ведёт только сборщик), поэтому состояние `unknown` нормально и после запуска
имитатора. Признак «жив» — `link_state = online` у генератора и свежие сигналы `infra/genset/GENSET/*`.

## Что ставится

| Что | Где |
|---|---|
| venv эмулятора, код `iot_sim` и `catalog/` | `/opt/td-stand/venv-sim`, `/opt/td-stand/iot-sim` (запуск через `PYTHONPATH`: эмулятор ищет `catalog/` рядом с пакетом) |
| venv сборщика: `f3d_collector` + плагины bms, yard, machine_connect (в одном venv: плагины подхватываются через entry points) | `/opt/td-stand/venv-collector` |
| env-файлы (секреты; свои правки — в `iot-sim.local.env`, `collector.local.env`, их скрипт не трогает) | `/etc/td-stand/` |
| буфер сборщика, снимок эмулятора, сертификаты | `/var/lib/td-stand/{collector,sim}` |
| venv имитатора ретранслятора и его код (`fake_relay.py`, `genset_model.py`, `profiles/` из `factory3d/odoo_addons/td_genset/relay`; из pip нужен только `tzdata`) | `/opt/td-stand/venv-relay`, `/opt/td-stand/genset-relay` |
| env имитатора: `RELAY_API_TOKEN` (Bearer для Odoo), `RELAY_SIM_TOKEN` (Bearer для `/sim/v1`, его же получает `iot_sim` как `SIM_GENSET_RELAY_TOKEN`), порт, hostid | `/etc/td-stand/genset-relay.env` (0640 root:td-stand; свои правки — в `genset-relay.local.env`) |
| службы `td-iot-sim`, `td-collector`, `td-genset-relay` (User `td-stand`, `Restart=always`, journald, `MemoryMax` 1G/640M/256M, `CPUQuota`, `TasksMax`) | `/etc/systemd/system/` |
| псевдонимы `iot-sim`, `mosquitto`, `collector` → 127.0.0.1 (так их зовёт seed Odoo, в т.ч. `td_access` → `https://iot-sim:8443`) | блок `# BEGIN td-stand` в `/etc/hosts` |
| брокер MQTT: пакет `mosquitto`, `listener 1883 127.0.0.1`, пользователи `sim`, `collector` | `/etc/mosquitto/conf.d/td-stand.conf`, `/etc/mosquitto/td-stand.passwd` |

Порты (всё на loopback, обе службы ещё и ограничены `IPAddressDeny=any` + `IPAddressAllow=localhost`, если Odoo на этом
же сервере): эмулятор TCP 502 (Modbus, через `CAP_NET_BIND_SERVICE`), 4001, 4840, 8081 (`TD_SIM_PORT_BIOSTAR_HTTP`), 8082, 8083, 8090, 8443, 50000,
UDP 47808, 50001; имитатор ретранслятора TCP 8087 (`TD_SIM_PORT_GENSET_RELAY`; слушает 0.0.0.0, защищён тем же
`IPAddressDeny=any` + `IPAddressAllow=localhost` + `TD_IP_ALLOW`, что и эмулятор, и двумя токенами); сборщик TCP 8080 (HTTP push), 9108 (health, метрики), UDP 127.0.0.2:47808 (BACnet, чтобы не
конфликтовать с эмулятором на 127.0.0.1:47808). Если порт занят чужим процессом, `--check` и установка остановятся с
перечнем процессов. **Порт 8081 на timur-o19demo занят настоящим ретранслятором SmartGen чужой системы: имитатор на нём не
стартует (скрипт отказывается от `TD_SIM_PORT_GENSET_RELAY=8081`), а `stand_odoo_setup.py genset` отказывается подключать Odoo
к порту 8081 и к `*.todo.ltd`.** Секреты стенда (OPC UA, woodStore, MQTT, LPR и т. д.) генерируются при первой установке и дальше
не меняются; в репозитории секретов нет.

## Odoo-сторона (менеджер, по RPC)

Все шаги делает `stand_odoo_setup.py` (только stdlib, XML-RPC). Вход: `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`
(пароль или API-ключ пользователя с `td_factory3d.group_td_admin`, например `admin`).

    export ODOO_URL=https://timur-o19demo.todo.ltd ODOO_DB=odoo ODOO_USER=admin ODOO_PASSWORD=…
    (umask 077; python3 stand_odoo_setup.py setup > td-stand.secrets)   # в stdout только две строки KEY=VALUE
    python3 stand_odoo_setup.py status                                  # что видит Odoo, без секретов
    python3 stand_odoo_setup.py backfill                                # --days 90 (по умолчанию), --purge, --force

### 1. Токен сборщика

- Модель `td.collector` (td_telemetry), запись с `code = COL-MAIN` (seed `td_telemetry.collector_main`; если её нет —
  `create({"code": "COL-MAIN", "name": "…"})`).
- Метод `action_generate_token([id])` (публичный, только `group_td_admin`): пишет `token_hash` (sha256), `token_hint`
  (последние 4 символа), `token_set_at`; сам токен возвращает один раз в `result["context"]["default_token"]`
  (43 символа, `secrets.token_urlsafe(32)`). Повторный вызов выпускает новый токен и ломает старый.
- Helper не выпускает токен повторно, если `token_set_at` уже заполнен (`--rotate` — выпустить). Токен печатается в stdout
  один раз как `TD_COLLECTOR_TOKEN=…`; клиент подаёт его в `install_stand.sh`.
- Сборщик ходит с `Authorization: Bearer <токен>` и `F3D_COLLECTOR_CODE=COL-MAIN`. Отзыв: `action_revoke_token`.

### 2. Параметры (`ir.config_parameter`)

| Ключ | Значение | Зачем |
|---|---|---|
| `td.iot_sim.url` | `http://127.0.0.1:8090` | пульт «Емулятор» в Odoo ходит в REST эмулятора |
| `td.iot_sim.token` | = `SIM_API_TOKEN` (`TD_SIM_API_TOKEN` в stdout helper) | Bearer для `/sim/v1`; helper генерирует и хранит в Odoo |
| `td.iot_sim.read_enabled` / `write_enabled` | `True` / `True` (`TD_SIM_WRITE_ENABLED=0` — запретить сценарии и сбои) | опрос статуса, команды из пульта |
| `td.telemetry.read_enabled` / `write_enabled` | `True` / `False` | приём показаний; запись в устройства выключена (в паре с `F3D_WRITE_ENABLED=0` сборщика) |
| `td.energy`, `td.bms`, `td.yard`, `td.fire_safety`, `td.genset`, `td.machine_connect` `.read_enabled` / `.write_enabled` | `True` / `False` (только ключи, которые уже есть в базе) | чтение живых данных модулями |
| `td.base.environment` | `test` (helper проверяет, но не меняет) | хук td_telemetry включает чтение только при `test`; нейтрализация БД сбрасывает всё в `False` |

Источник `td.source` с `code = HTTP-PUSH` (приёмник LPR, раньше правился вручную, `http_push_params`): `params` =
`{"routes": ["lpr"], "allow_ips": ["iot-sim", "127.0.0.1"], "token_ref": "F3D_HTTP_PUSH_TOKEN_LPR", "secret_ref":
"F3D_HTTP_PUSH_SECRET_LPR"}`. Это имена переменных сборщика, значения лежат в `/etc/td-stand/collector.env` и совпадают
с `SIM_LPR_PUSH_*` эмулятора; helper дополняет `params` и ничего секретного в Odoo не пишет. Остальные источники (`MB-*`,
`BAC-*`, `OPCUA-*`, `SICS-*`, `MQTT-MOBILE`, …) приходят из data-файлов модулей и привязаны к `COL-MAIN`; хосты в них —
`iot-sim` и `mosquitto`, поэтому нужен блок в `/etc/hosts`.

### 3. История за 90 дней (td_energy, R-36) и демо аналитики

Коротко: `stand_odoo_setup.py backfill` (электрика `td.energy.interval` и ресурсы `td.energy.res.interval`, по
`--chunk-days 5` суток на вызов: прокси перед Odoo — Cloudflare — обрывает запрос примерно через 100 с, а 90 суток одним
вызовом — несколько минут; 5 суток ≈ 25 с; при 502/504 кусок повторяется — запись идемпотентна), затем
`stand_odoo_setup.py seed` (W4 R-20 `_td_seed_demo(days=90)`, одним вызовом, повтор заменяет прежний сид).
Подробности метода — ниже.


Нужен `td.energy.interval._td_backfill(days=90)` после ≥ 5 минут работы стенда (чтобы были первые показания счётчиков;
иначе на стыке истории и живых данных будут пропуски). Метод приватный (`_`), и Odoo отвечает на RPC-вызов
«Private methods cannot be called remotely», поэтому `backfill` делает так: создаёт временное `ir.actions.server`
(модель `td.energy.interval`, код `env['td.energy.interval']._td_backfill(days=90, seed=20261018, purge=False)`),
запускает его `ir.actions.server.run`, возвращает статистику R-36 п. 10 и удаляет действие. Идемпотентно: повторный запуск
вставляет 0 строк (`ON CONFLICT DO NOTHING`); `--purge` удаляет только строки с `is_backfill = True`. Работает до нескольких
минут (ТП-07: ≤ 120 с); если у Odoo `workers > 0` и `limit_time_real` обрывает запрос, выполнить на сервере по R-36:

    echo 'env["td.energy.interval"]._td_backfill(days=90)' | sudo -u odoo odoo shell -d odoo --no-http -c /etc/odoo/odoo.conf

(Предложение владельцу td_energy: публичная обёртка над `_td_backfill`, чтобы вызывать его напрямую по RPC.)

## Живой генератор (td_genset + имитатор ретранслятора)

`td_genset/relay/fake_relay.py` с профилем D700 изображает ретранслятор SmartGen HGM6120N (таймеры, топливо, нагрузка,
аварии; API `td_genset/relay_api.md` + `/sim/v1/*`). Odoo (`td_genset`) опрашивает его раз в минуту (`ir.cron`), мост
`td_genset_factory3d` публикует показания в 26 сигналов `infra/genset/GENSET/*`, узел энергосети `GENSET` и 3D-карточка берут их
оттуда. Имитатор держит состояние в памяти: после перезапуска службы он стартует с профиля (топливо 82 %).

**Порядок** (токены выдаёт менеджер, тот же файл идёт на хост):

1. Менеджер (токены в файл, в вывод не печатаются; повторный запуск идемпотентен):

       export ODOO_URL=https://timur-o19demo.todo.ltd ODOO_DB=odoo ODOO_USER=admin ODOO_PASSWORD=…
       python3 stand_odoo_setup.py genset --token-file td-stand.secrets --wait 0

   Команда: создаёт или обновляет `td.genset` («ДГУ D700», профиль D700, контроллер HGM6120N, `hostid` имитатора, мощность и бак
   из `td.genset3d.profile`), применяет профиль, связывает генератор с 3D-объектом (`maintenance.equipment`, `td_code = GENSET`) и узлом
   энергосети `GENSET` (`td.genset3d.link`), пишет `td_genset.relay_url` и `td_genset.relay_token`, включает 7 кронов (4 `td_genset`,
   3 `td_genset_factory3d`), `td.genset.read_enabled` и `requests_enabled`. Команды из Odoo в имитатор не включаются
   (`commands_allowed` и `td.genset.write_enabled` остаются выключенными). Ничего не удаляет и не архивирует. Адрес имитатора для
   контейнера Odoo — `--relay-url` (по умолчанию `http://172.18.0.1:8087`, шлюз compose-сети, как у `td.iot_sim.url`; `/api/v1`
   добавляется сам; также `TD_RELAY_URL`, `TD_SIM_URL` и `TD_SIM_PORT_GENSET_RELAY`). Если `td_genset.relay_url` уже задан другим
   адресом, команда останавливается (`--force` перезаписывает). Токены берутся из `--token-file` (`TD_RELAY_API_TOKEN`,
   `TD_RELAY_SIM_TOKEN` или те же имена без `TD_`; если их там нет, выдаются и дописываются в файл с правами 0600).
2. Клиент на хосте (имитатор ставится вместе со стендом; `td-stand.secrets` — файл из п. 1):

       CL=/opt/timur-o19/timur-o19e/git/todo_timur
       sudo git -C $CL fetch origin claude/td-genset-stand
       sudo git -C $CL checkout claude/td-genset-stand      # пока ветка не влита в рабочую; потом достаточно git pull
       sudo TD_SECRETS_FILE=/root/td-stand.secrets TD_ODOO_URL=http://127.0.0.1:8094 TD_SIM_PORT_BIOSTAR_HTTP=8181 \
           TD_SIM_PORT_GENSET_RELAY=8087 TD_IP_ALLOW=172.16.0.0/12 bash $CL/factory3d/tools/server/install_stand.sh

   (перед этим можно `--check`). Служба `td-genset-relay` стартует на 0.0.0.0:8087; `td-iot-sim` получает `SIM_GENSET_RELAY_URL` =
   `http://127.0.0.1:8087` и `SIM_GENSET_RELAY_TOKEN`. Повторный запуск идемпотентен: имитатор перезапускается, только если
   изменились код, env или unit.
3. Проверка на хосте (токены из env-файла, на экран не выводятся):

       sudo bash install_stand.sh --status                    # в т. ч. строка «ретранслятор (имитатор)»
       sudo bash -c '. /etc/td-stand/genset-relay.env; curl -s -K - http://127.0.0.1:8087/sim/v1/state <<<"header = \"Authorization: Bearer $RELAY_SIM_TOKEN\""'; echo
       sudo bash -c '. /etc/td-stand/genset-relay.env; curl -s -K - http://127.0.0.1:8087/api/v1/status <<<"header = \"Authorization: Bearer $RELAY_API_TOKEN\""'; echo
       curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8087/api/v1/status       # без токена: 401

   Ожидаемо: `"profile": "D700"`, `"state": "standby"`, `fuel_pct` около 82 и в `/api/v1/status` один модуль (`hostid` из env). Из
   контейнера Odoo: `curl -s -o /dev/null -w '%{http_code}\n' http://172.18.0.1:8087/api/v1/status` даёт 401 (достижимо; другой код
   или таймаут — фаервол хоста или `TD_IP_ALLOW`).
4. Менеджер повторяет команду (теперь без `--wait 0`): она просит Odoo опросить имитатор и печатает первое показание (связь,
   режим, состояние, кВт, топливо). Крон делает то же раз в минуту.

**История.** За 90 суток её нет, и `backfill --target genset` не добавлен: у `td_genset` нет ни сида, ни пакетного забора
(`_cron_pull_readings` читает с курсора `GET /readings` имитатора, а имитатор хранит журнал только с момента запуска, без
предзаполнения); синтетические показания пришлось бы писать прямо в `td.genset.reading` (около 100 полей) и отдельно воспроизводить
события, которые `td_genset` выводит из последовательности показаний. Поэтому история накапливается с момента запуска.

**Перезапуск имитатора** (переустановка с изменённым кодом или env, `systemctl restart td-genset-relay`, перезагрузка хоста): его
журнал в памяти, поэтому состояние возвращается к профилю (топливо 82 %, режим `auto`, сеть в норме). Курсор Odoo
(`td.genset.readings_cursor`) при этом не откатывается, а `td_genset` пропускает уже виденные id, поэтому имитатор стартует с
`RELAY_ID_BASE=epoch`: id показаний идут от секунд Unix на момент старта и всегда выше прежних, Odoo продолжает читать без пропуска. Показания,
которые Odoo успел забрать до перезапуска, остаются в `td.genset.reading`. Если имитатор запущен вручную без `RELAY_ID_BASE`, id после
перезапуска идут с 1: Odoo не видит новых показаний, пока id не догонит курсор (команда `genset` напишет об этом предупреждение).

Сценарии `blackout` и `genset_test` эмулятора должны вести имитатор через `/sim/v1/*` (контракт td_genset §8.6): `iot_sim` для
этого получает `SIM_GENSET_RELAY_URL` и `SIM_GENSET_RELAY_TOKEN`. Но в текущем `services/iot_sim` HTTP-клиента ретранслятора ещё нет
(сценарии лишь выставляют флаги, а ATS в запасном режиме §8.14), поэтому пока генератор по сценариям не реагирует; вручную:
`POST /sim/v1/mains {"available": false}`, затем `POST /sim/v1/load {"kw": 348}` (Bearer `RELAY_SIM_TOKEN`).

## Диагностика

    sudo bash install_stand.sh --status
    journalctl -u td-iot-sim -u td-collector -f                 # логи (JSON), при старте сборщик пишет ~2 тыс. строк asyncua
    curl -s http://127.0.0.1:8090/sim/v1/health ; curl -s http://127.0.0.1:9108/health
    systemctl status td-iot-sim td-collector td-genset-relay mosquitto
    journalctl -u td-genset-relay -n 50 --no-pager

| Симптом | Причина и что делать |
|---|---|
| `/f3d/telemetry/health` не отвечает `ok: true` | Odoo не выбрал БД: при нескольких БД (`odoo` и `odoo_f3d_old` после перехода) задайте в `odoo.conf` `db_name = odoo` или `dbfilter = ^odoo$`; либо `td_telemetry` не установлен |
| Odoo не принял токен (401) | токен не от этой БД или отозван: менеджер `setup --rotate`, клиент повторяет установку |
| `--check`: порт занят | остановите чужой процесс; порты эмулятора фиксированы seed-данными Odoo, порт приёмника LPR меняется `TD_PUSH_PORT` |
| нужен Python ≥ 3.12 | Ubuntu 24.04 / Debian 13 — штатный; на 22.04 / Debian 12 поставьте `python3.12` и задайте `TD_PYTHON` |
| pip не скачивает пакеты | нужен доступ к PyPI с сервера; прокси — через `HTTPS_PROXY` в окружении sudo (`sudo -E`) |
| источник `MQTT-MOBILE` offline | брокер не поднят: `systemctl status mosquitto`; в `/etc/mosquitto` уже были свои `listener`, скрипт их не менял (настройте вручную: пользователи `sim`, `collector`, пароли из env-файлов) |
| `genset`: «показаний пока нет», связь offline | имитатор не ответил Odoo: служба не запущена (`systemctl status td-genset-relay`), токен API в Odoo не совпал (401: повторите установку с файлом из `genset --token-file`) или контейнер не достучался до `172.18.0.1:8087` (`TD_IP_ALLOW`, фаервол хоста); крон подхватит данные сам |
| сеть служб ограничена `IPAddressAllow=localhost`, а нужен внешний доступ | `TD_IP_FILTER=0` и повторная установка, либо drop-in `systemctl edit …` |

Имитатор ретранслятора не имеет отношения к настоящему ретранслятору SmartGen на 127.0.0.1:8081: другой порт (8087), другой
`hostid`, свои токены; Odoo `genset` подключает только к нему.

Что скрипт не делает: не трогает Odoo, его конфиг, БД и таймер `f3d-update`; не открывает порты наружу и не правит
фаервол; не запускает backfill (это шаг менеджера). `--uninstall` оставляет `/etc/td-stand` и `/var/lib/td-stand`
(секреты, буфер), `--purge` удаляет и их вместе с пользователем `td-stand`; пакет `mosquitto` остаётся.
