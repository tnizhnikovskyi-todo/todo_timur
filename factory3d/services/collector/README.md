# collector

Колектор телеметрії factory3d: читає Modbus TCP / MQTT / BACnet/IP / HTTP push, буферизує в SQLite і
відправляє в Odoo (`factory3d_telemetry`, `/f3d/telemetry/*`). Специфікація — SPEC §8.

## Запуск і тести

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e . --no-deps
    .venv/bin/pytest -q -m "not stand" tests/unit
    cp .env.example .env && docker compose -f docker-compose.collector.yml up -d

## CLI (`python -m collector <команда>`)

`run` — основний цикл; `check-config` — перевірка env і зв'язку з Odoo; `dump-config` — вивід конфігурації
з Odoo; `test-source <код>` — разове опитування джерела; `drain-buffer` — відправити буфер і вийти.
Код виходу 2 — помилка конфігурації (наприклад, токен коротший за 32 символи).

## Порти

8080 — HTTP push (`F3D_HTTP_PUSH_PORT`); 9108 — метрики/health (`F3D_METRICS_PORT`);
47808/udp — BACnet/IP (`F3D_BACNET_BIND`).

## Конфігурація (env, префікс `F3D_`)

| Змінна | Default | Призначення |
|---|---|---|
| `F3D_ODOO_URL` | обов'язково | адреса Odoo |
| `F3D_ODOO_CA` | порожньо | CA для самопідписаного TLS |
| `F3D_COLLECTOR_CODE` | обов'язково | код колектора (= `f3d.collector.code`) |
| `F3D_COLLECTOR_TOKEN` | обов'язково, ≥ 32 символи | Bearer-токен |
| `F3D_CONFIG_POLL_S` | 60 | перечитування конфігурації |
| `F3D_PUSH_INTERVAL_S` / `F3D_PUSH_MAX` | 5 / 1000 | період і розмір пакета (≤ 2000) |
| `F3D_STATUS_INTERVAL_S` | 60 | період статусу |
| `F3D_COMMANDS_POLL_S` | 5 | опитування черги команд |
| `F3D_WRITE_ENABLED` | 0 | стоп-кран запису в пристрої |
| `F3D_ALLOW_HOSTS` | обов'язково | allow-list хостів/IP/CIDR пристроїв і брокера |
| `F3D_BUFFER_DIR` / `F3D_BUFFER_MAX_MB` | `./state` / 200 | SQLite-буфер |
| `F3D_HTTP_PUSH_PORT` | 8080 | приймач HTTP push |
| `F3D_HTTP_PUSH_TOKEN_<ROUTE>` | порожньо | токен маршруту |
| `F3D_HTTP_PUSH_SECRET_<ROUTE>` | порожньо | секретний суфікс шляху |
| `F3D_HTTP_PUSH_ALLOW_IPS` | порожньо | allow-list відправників |
| `F3D_MQTT_PASSWORD`, інші `*_ref` | — | секрети, на які посилаються `params.*_ref` |
| `F3D_BACNET_BIND` / `F3D_BACNET_DEVICE_ID` | `0.0.0.0:47808` / 3999 | BACnet |
| `F3D_METRICS_PORT` | 9108 | метрики |
| `F3D_LOG_LEVEL`, `F3D_LOG_JSON` | `INFO`, `1` | логи |
| `F3D_TZ` | `Europe/Kyiv` | лише для логів; `ts` — UTC |
| `F3D_CLOCK_SKEW_WARN_S` | 30 | попередження про розходження годинників |

Відсутня змінна для `*_ref` → джерело `error`, інші джерела працюють.
