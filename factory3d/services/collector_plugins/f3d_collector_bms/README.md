# f3d-collector-bms

Плагін колектора factory3d `helvarnet`: освітлення Helvar Imagine 950 (DALI) за протоколом HelvarNet (TCP 50000).
Специфікація: `docs/modules/factory3d_bms/SPEC.md` §8, R-31…R-37.

## Встановлення

`services/collector/requirements-extra.txt` містить `./../collector_plugins/f3d_collector_bms`
(`pip install --no-deps`); entry point `factory3d_collector.plugins: helvarnet`.

## Параметри і адреса

- `params`: `host`, `router` (обов.), `port` (50000), `protocol` (`tcp`; `udp` не підтримується), `timeout_s`,
  `cluster`, `version`, `rate_per_s`, `push`, `membership_ttl_s` — `schemas/params.helvarnet.json`.
- `address`: `group`/`device`, `query` (`level|power|scene|faults|faulty|router`), `devices`, `sample`, `mask`,
  `scale`, `fade_s`, `block` — `schemas/address.helvarnet.json`.

## Обмеження

Дозволені лише команди 102, 104, 109, 110, 152, 161, 164, 191 і записи C:11/C:13; група 40 (EMERGENCY) і групи поза
сигналами джерела — `NotSupported`. Метрики `collector_helvarnet_*` плагін збільшує через `getattr(ctx.metrics, …)`;
їх оголошення — у `collector/core/metrics.py`.

## Тести

`pytest services/collector_plugins/f3d_collector_bms -q` (потрібні `pytest`, `pytest-asyncio`, `jsonschema`).
