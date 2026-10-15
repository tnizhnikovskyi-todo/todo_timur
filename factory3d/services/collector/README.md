# collector

Колектор телеметрії factory3d: читає Modbus TCP / MQTT / BACnet/IP / HTTP push, буферизує в SQLite і
відправляє в Odoo (`factory3d_telemetry`, `/f3d/telemetry/*`). Специфікація — SPEC §8.

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/pytest -q -m "not stand"
    cp .env.example .env && docker compose -f docker-compose.collector.yml up -d

Стан: каркас W0 (`collector/core/types.py`, `collector/plugins/base.py`, `tests/conftest.py`).
