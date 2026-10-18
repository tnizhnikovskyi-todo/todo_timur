# iot_sim — емулятор обладнання factory3d

Сервіс імітує протоколи обладнання (OPC UA, Modbus, BACnet, MQTT, REST) за каталогом сигналів
(`catalog/signals.csv` = Додаток A SPEC `td_iot_sim`). Повна специфікація — `docs/modules/td_iot_sim/SPEC.md`.
Стан W0: каркас; працює лише `GET /sim/v1/health`.

## Запуск

    python -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp .env.example .env   # заповнити SIM_* (токен >= 32 символів)
    python -m iot_sim check-config | run | dump-catalog

Порти (SPEC §8.1.3): REST 8090, OPC UA 4840, Modbus 502, BACnet 47808/udp, woodStore 8082, jobs 8083, SICS 4001.
Compose: `docker-compose.sim.yml` (профілі demo/dev), брокер mosquitto потребує `mosquitto/passwd`.

## Каталог

    python tools/gen_catalog.py          # згенерувати catalog/signals.csv і data/td_sim_signal.csv Odoo-модуля
    python tools/gen_catalog.py --check  # звірити з Додатком A

## Тести

    .venv/bin/pytest tests/unit -q
