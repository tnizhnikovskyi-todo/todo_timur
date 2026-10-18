# Постоянный стенд на тестовом сервере (E-11)

Стенд = эмулятор оборудования `iot_sim` + сборщик сигналов `collector` (плагины: modbus_tcp, mqtt, http_push,
bacnet_ip, helvarnet, sics, opcua, rest_vendor). Эмулятор поднимает «оборудование» по протоколам, сборщик читает его
и шлёт показания в Odoo (`/f3d/telemetry/*`, модуль `td_telemetry`), поэтому `td.signal` и все модули поверх него
(энергетика, здание, двор, верстаты) работают на живых данных. Раньше стенд жил в контейнере менеджера и умирал вместе
с ним; теперь это две службы systemd на самом сервере. Маршруты `/f3d/...` и коды сигналов не менялись (RENAME.md §3).

Файлы: `install_stand.sh` (ставит на сервере), `stand_odoo_setup.py` (Odoo-сторона, запускает менеджер снаружи).

## Кто что делает

| Шаг | Кто | Команда |
|---|---|---|
| 1. Новая БД `odoo`, модули `td_*` установлены (RENAME.md §7) | менеджер | — |
| 2. Токены и параметры в Odoo | менеджер | `stand_odoo_setup.py setup > td-stand.secrets` |
| 3. Передать файл `td-stand.secrets` клиенту (два значения, не хранить в git и чатах) | менеджер | — |
| 4. Проверка без изменений | клиент | `sudo TD_SECRETS_FILE=/root/td-stand.secrets bash /mnt/f3d-addons/factory3d/tools/server/install_stand.sh --check` |
| 5. Установка | клиент | `sudo TD_SECRETS_FILE=/root/td-stand.secrets bash /mnt/f3d-addons/factory3d/tools/server/install_stand.sh` |
| 6. История за 90 дней (через ≥ 5 минут после п. 5) | менеджер | `stand_odoo_setup.py backfill` |

После установки файл с токенами можно удалить: значения лежат в `/etc/td-stand/*.env` (0640 root:td-stand).

## Команды клиента

    sudo TD_SECRETS_FILE=/root/td-stand.secrets bash install_stand.sh --check   # план, ничего не меняет; код 3 = есть препятствия
    sudo TD_SECRETS_FILE=/root/td-stand.secrets bash install_stand.sh           # установить или обновить (идемпотентно)
    sudo bash install_stand.sh --status                                         # службы, health, ответ Odoo
    sudo bash install_stand.sh --uninstall [--purge]                            # снять службы и venv; Odoo и БД не трогает

Токены можно передать иначе: переменные `TD_COLLECTOR_TOKEN` / `TD_SIM_API_TOKEN`, файлы `TD_COLLECTOR_TOKEN_FILE` /
`TD_SIM_API_TOKEN_FILE` (в файле только значение). Повторный запуск без токенов берёт значения из `/etc/td-stand/*.env`.
Обновление кода стенда: `git pull` в `/mnt/f3d-addons`, затем снова `install_stand.sh` (пересоберёт venv, если изменились
исходники `factory3d/services`, и перезапустит изменившиеся службы). Новые токены: менеджер делает `setup --rotate`,
клиент запускает установку с новым файлом.

Переменные: `TD_REPO` (git-клон, по умолчанию тот, где лежит скрипт), `TD_ODOO_URL` (`http://127.0.0.1:8069`),
`TD_COLLECTOR_CODE` (`COL-MAIN`), `TD_PUSH_PORT` (8080), `TD_PYTHON`, `TD_IP_FILTER=0` (не ограничивать сеть служб),
`TD_HARDEN=0` (без песочницы systemd: нужен, если в `journalctl` у службы `status=226/NAMESPACE`, например в LXC),
`--no-mqtt` (не ставить брокер).

## Что ставится

| Что | Где |
|---|---|
| venv эмулятора, код `iot_sim` и `catalog/` | `/opt/td-stand/venv-sim`, `/opt/td-stand/iot-sim` (запуск через `PYTHONPATH`: эмулятор ищет `catalog/` рядом с пакетом) |
| venv сборщика: `f3d_collector` + плагины bms, yard, machine_connect (в одном venv: плагины подхватываются через entry points) | `/opt/td-stand/venv-collector` |
| env-файлы (секреты; свои правки — в `iot-sim.local.env`, `collector.local.env`, их скрипт не трогает) | `/etc/td-stand/` |
| буфер сборщика, снимок эмулятора, сертификаты | `/var/lib/td-stand/{collector,sim}` |
| службы `td-iot-sim`, `td-collector` (User `td-stand`, `Restart=always`, journald, `MemoryMax` 1G/640M, `CPUQuota`, `TasksMax`) | `/etc/systemd/system/` |
| псевдонимы `iot-sim`, `mosquitto`, `collector` → 127.0.0.1 (так их зовёт seed Odoo, в т.ч. `td_access` → `https://iot-sim:8443`) | блок `# BEGIN td-stand` в `/etc/hosts` |
| брокер MQTT: пакет `mosquitto`, `listener 1883 127.0.0.1`, пользователи `sim`, `collector` | `/etc/mosquitto/conf.d/td-stand.conf`, `/etc/mosquitto/td-stand.passwd` |

Порты (всё на loopback, обе службы ещё и ограничены `IPAddressDeny=any` + `IPAddressAllow=localhost`, если Odoo на этом
же сервере): эмулятор TCP 502 (Modbus, через `CAP_NET_BIND_SERVICE`), 4001, 4840, 8081, 8082, 8083, 8090, 8443, 50000,
UDP 47808, 50001; сборщик TCP 8080 (HTTP push), 9108 (health, метрики), UDP 127.0.0.2:47808 (BACnet, чтобы не
конфликтовать с эмулятором на 127.0.0.1:47808). Если порт занят чужим процессом, `--check` и установка остановятся с
перечнем процессов. Секреты стенда (OPC UA, woodStore, MQTT, LPR и т. д.) генерируются при первой установке и дальше
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

### 3. История за 90 дней (td_energy, R-36)

Нужен `td.energy.interval._td_backfill(days=90)` после ≥ 5 минут работы стенда (чтобы были первые показания счётчиков;
иначе на стыке истории и живых данных будут пропуски). Метод приватный (`_`), и Odoo отвечает на RPC-вызов
«Private methods cannot be called remotely», поэтому `backfill` делает так: создаёт временное `ir.actions.server`
(модель `td.energy.interval`, код `env['td.energy.interval']._td_backfill(days=90, seed=20261018, purge=False)`),
запускает его `ir.actions.server.run`, возвращает статистику R-36 п. 10 и удаляет действие. Идемпотентно: повторный запуск
вставляет 0 строк (`ON CONFLICT DO NOTHING`); `--purge` удаляет только строки с `is_backfill = True`. Работает до нескольких
минут (ТП-07: ≤ 120 с); если у Odoo `workers > 0` и `limit_time_real` обрывает запрос, выполнить на сервере по R-36:

    echo 'env["td.energy.interval"]._td_backfill(days=90)' | sudo -u odoo odoo shell -d odoo --no-http -c /etc/odoo/odoo.conf

(Предложение владельцу td_energy: публичная обёртка над `_td_backfill`, чтобы вызывать его напрямую по RPC.)

## Диагностика

    sudo bash install_stand.sh --status
    journalctl -u td-iot-sim -u td-collector -f                 # логи (JSON), при старте сборщик пишет ~2 тыс. строк asyncua
    curl -s http://127.0.0.1:8090/sim/v1/health ; curl -s http://127.0.0.1:9108/health
    systemctl status td-iot-sim td-collector mosquitto

| Симптом | Причина и что делать |
|---|---|
| `/f3d/telemetry/health` не отвечает `ok: true` | Odoo не выбрал БД: при нескольких БД (`odoo` и `odoo_f3d_old` после перехода) задайте в `odoo.conf` `db_name = odoo` или `dbfilter = ^odoo$`; либо `td_telemetry` не установлен |
| Odoo не принял токен (401) | токен не от этой БД или отозван: менеджер `setup --rotate`, клиент повторяет установку |
| `--check`: порт занят | остановите чужой процесс; порты эмулятора фиксированы seed-данными Odoo, порт приёмника LPR меняется `TD_PUSH_PORT` |
| нужен Python ≥ 3.12 | Ubuntu 24.04 / Debian 13 — штатный; на 22.04 / Debian 12 поставьте `python3.12` и задайте `TD_PYTHON` |
| pip не скачивает пакеты | нужен доступ к PyPI с сервера; прокси — через `HTTPS_PROXY` в окружении sudo (`sudo -E`) |
| источник `MQTT-MOBILE` offline | брокер не поднят: `systemctl status mosquitto`; в `/etc/mosquitto` уже были свои `listener`, скрипт их не менял (настройте вручную: пользователи `sim`, `collector`, пароли из env-файлов) |
| сеть служб ограничена `IPAddressAllow=localhost`, а нужен внешний доступ | `TD_IP_FILTER=0` и повторная установка, либо drop-in `systemctl edit …` |

Что скрипт не делает: не трогает Odoo, его конфиг, БД и таймер `f3d-update`; не открывает порты наружу и не правит
фаервол; не запускает backfill (это шаг менеджера). `--uninstall` оставляет `/etc/td-stand` и `/var/lib/td-stand`
(секреты, буфер), `--purge` удаляет и их вместе с пользователем `td-stand`; пакет `mosquitto` остаётся.
