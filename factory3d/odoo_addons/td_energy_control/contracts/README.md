# Заморожені контракти W2 (C-38…C-47)

Джерело — `build/energy/W2_SPEC.md` §5.6, §7, §8.3, §8.4.2 і `W2_ARCH.md` §2.1. Зміни — **лише через менеджера**.
Файли — приклади-еталони структури (ключі й типи); тести `td_energy_control/tests/test_contracts.py` звіряють набір
ключів із реальними відповідями.

| Файл | Контракт | Кому |
|---|---|---|
| `api16_get_control.json`, `api17_prepare.json`, `api18_confirm.json`, `api22_get_action.json`, `api23_get_schedule.json`, `api27_node_actions.json`, `api28_journal.json` | API-16…API-23, API-27, API-28 (ORM-RPC `td.energy.control`) | A → B |
| `api24_config.json` | API-24 `GET /td/energy/automation/config` (C-39); `flags.remote_switching_enabled` (D-46) | A → C |
| `api25_state_request.json`, `api25_state_response.json` | API-25 `POST /td/energy/automation/state` (C-39) | C → A |
| `api26_intent.json`, `api26_result_*.json` | API-26 `td.command.payload` / `result_data` (C-39) | A ⇄ C |
| `c38_advice_actions.json` | C-38: действия рекомендаций `kind='control'`, алиасы интентов W3, баннер «Виконано» | A → `td_energy` |
| `c41_td_command.json` | C-41: `td.command`, `energy_ctl`, `energy_control` | A ← `td_telemetry` |
| `c42_adp12.json` | C-42: ADP-12 `start_test` / `test_facts` | A → `td_genset_factory3d` |
| `c43_bms_targets.json` | C-43: цели BMS (только чтение) | A ← `td_bms` |
| `c44_energy_layer.json` | C-44: `energy.layer` | D → `td_viewer3d` |
| `c45_c46_client_registries.json` | C-45, C-46, шина `td_energy_control` | B, D |
| `c47_registers.json` | C-47: окно управления SWB-CTRL, unit 73, HR 200…291 (ДОПУЩЕНИЕ A-45, Q-26) | C ⇄ эмулятор, A (сигналы) |

C-40 (расширение `PluginContext`, `LiveCache`, `CommandLoop.write_direct/read_now`) — SPEC §8.1.2.
