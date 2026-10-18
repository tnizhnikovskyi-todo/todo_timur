/** @odoo-module */
// Відповіді API-16…API-28 та C-38/C-45 для hoot-тестів. Згенеровано з contracts/*.json (заморожені контракти C-38…C-47,
// зміни лише через менеджера): джерело істини — JSON у каталозі contracts/, цей файл після змін контракту згенерувати знову.
export const CONTRACTS = {
    "API-16": {
        "ts": "2026-10-18T11:20:03Z",
        "now_local": "14:20",
        "meta": {
            "role": "manager",
            "can_prepare": true,
            "can_confirm_b": false,
            "write_enabled": true,
            "automation_enabled": true,
            "remote_switching_enabled": true,
            "limit_kw": 760,
            "contract_kw": 800,
            "refresh_s": 30
        },
        "engine": {
            "connected": true,
            "mode": "auto",
            "reason": null,
            "heartbeat_at": "2026-10-18T11:20:01Z",
            "age_s": 2,
            "config_version": 17,
            "applied_version": 17,
            "label": "Контролер ГРЩ і збирач на зв'язку · 14:20",
            "level": "ok"
        },
        "scenarios": {
            "on_count": 4,
            "total": 6,
            "items": [
                {
                    "id": 1,
                    "code": "peak",
                    "title": "Зрізання піку",
                    "text": "Тримати імпорт нижче уставки: спершу розряд BESS, потім пуск КГУ, далі відключення за пріоритетами.",
                    "enabled": true,
                    "applied": true,
                    "state": "armed",
                    "state_kind": "arm",
                    "status": "Чергування · запас 402 кВт",
                    "chips": [
                        "уставка 760 кВт · 95 %",
                        "прогноз 15 хв"
                    ],
                    "params": {
                        "limit_kw": 760,
                        "margin_kw": 20
                    },
                    "schema": [
                        {
                            "name": "limit_kw",
                            "label": "Уставка імпорту",
                            "type": "float",
                            "min": 100,
                            "max": 2000,
                            "unit": "кВт"
                        }
                    ],
                    "can_toggle": true,
                    "pending_action_id": null
                }
            ]
        },
        "shed": {
            "items": [
                {
                    "id": 1,
                    "n": 1,
                    "name": "Зарядна станція навантажувачів",
                    "how": "відкласти заряд до 30 хв",
                    "kw": 48,
                    "p_now_kw": 13.5,
                    "node_code": "CHARGING",
                    "active": true
                }
            ],
            "sum_kw": 174,
            "never": [
                "аспірація під час роботи верстатів",
                "ІТ і зв'язок",
                "охорона",
                "пожежна автоматика",
                "аварійне освітлення"
            ],
            "never_nodes": [
                "DUST-1",
                "LP-2",
                "LP-3",
                "OFFICE",
                "BOILER"
            ],
            "can_reorder": true,
            "limit_kw": 760
        },
        "commands": [
            {
                "code": "qs_close",
                "label": "Увімкнути секційний вимикач QS",
                "sub": "секції 1 і 2 разом",
                "cls": "B",
                "resource": "qs",
                "enabled": true,
                "disabled_reason": null
            }
        ],
        "pending": [
            {
                "id": 55,
                "summary": "Пуск КГУ",
                "prepared_by": "Іваненко І.",
                "second_expires_at": "2026-10-18T11:30:00Z",
                "can_confirm_second": true
            }
        ],
        "schedule": {
            "now": 14.333,
            "rows": [
                {
                    "resource": "bess",
                    "name": "BESS",
                    "bars": [
                        {
                            "from": 7.5,
                            "to": 11.0,
                            "label": "розряд · пік",
                            "cls": "d",
                            "source": "plan"
                        }
                    ]
                }
            ]
        },
        "journal": [
            {
                "id": 812,
                "time": "14:06",
                "what": "Заявка ТО",
                "detail": "PFC-2: ступінь 3 не вмикається",
                "who": "автоматика",
                "result": "створено",
                "result_kind": "info",
                "state": "done",
                "undo_available": false,
                "awaiting_second": false,
                "ref": {
                    "model": "maintenance.request",
                    "id": 48
                }
            }
        ],
        "journal_more": false
    },
    "API-17": {
        "action_id": 55,
        "token": "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MGFiY2RlZg",
        "ttl_s": 60,
        "kind": "qs_close",
        "cls": "B",
        "title": "Увімкнути секційний вимикач QS?",
        "text": "Секції 1 і 2 працюватимуть разом. Генерація СЕС піде на навантаження секції 1, експорт через T2 припиниться.",
        "sub": "секції 1 і 2 разом",
        "checks": [
            {
                "code": "ats_parallel_lock",
                "label": "Блокування паралельної роботи T1 і T2 від АВР — увімкнено",
                "state": "ok",
                "hard": true,
                "detail": ""
            },
            {
                "code": "qs_current_ok",
                "label": "Струм через QS після вмикання ≈ 40 А з 1600 А",
                "state": "ok",
                "hard": true,
                "detail": "40 А ≤ 1280 А"
            }
        ],
        "blocked": false,
        "blocked_reason": null,
        "needs_second": true,
        "confirm_label": "Підтвердити (1/2)",
        "disabled_reason": null
    },
    "API-18": {
        "action_id": 55,
        "state": "awaiting_second",
        "state_label": "Очікує другого підтвердження",
        "needs_second": true,
        "message": "Очікуємо друге підтвердження іншим енергетиком.",
        "blocked_reason": null
    },
    "API-22": {
        "id": 55,
        "name": "Увімкнути секційний вимикач QS",
        "state": "executing",
        "state_label": "Виконується",
        "summary": "Увімкнути секційний вимикач QS",
        "detail": "секції 1 і 2 разом",
        "result_text": null,
        "error": null,
        "finished_at": null,
        "needs_second": false,
        "checks": [
            {
                "code": "ats_parallel_lock",
                "label": "Блокування паралельної роботи T1 і T2 від АВР — увімкнено",
                "state": "ok",
                "hard": true,
                "detail": ""
            }
        ],
        "collector_checks": [
            {
                "code": "controller_remote",
                "state": "ok",
                "hard": true,
                "detail": "remote=1"
            }
        ],
        "undo_available": false
    },
    "API-23": {
        "day": "2026-10-18",
        "now": 14.333,
        "rows": [
            {
                "resource": "bess",
                "name": "BESS",
                "bars": [
                    {
                        "from": 7.5,
                        "to": 11.0,
                        "label": "розряд · пік",
                        "cls": "d",
                        "source": "plan"
                    }
                ]
            }
        ]
    },
    "API-27": [
        {
            "code": "qs_close",
            "label": "Увімкнути QS…",
            "kind": "qs_close",
            "cls": "B",
            "enabled": true,
            "disabled_reason": null
        }
    ],
    "API-28": {
        "items": [
            {
                "id": 812,
                "time": "14:06",
                "what": "Заявка ТО",
                "detail": "PFC-2: ступінь 3 не вмикається",
                "who": "автоматика",
                "result": "створено",
                "result_kind": "info",
                "state": "done",
                "undo_available": false,
                "awaiting_second": false,
                "ref": {
                    "model": "maintenance.request",
                    "id": 48
                }
            }
        ],
        "more": false
    },
    "C-38": {
        "actions": [
            {
                "code": "charge_bess",
                "label": "Зарядити BESS 50 кВт",
                "kind": "control",
                "class": "A",
                "params": {
                    "command_kind": "bess_charge",
                    "power_kw": 50
                }
            },
            {
                "code": "qs_on",
                "label": "Увімкнути QS…",
                "kind": "control",
                "class": "B",
                "params": {
                    "command_kind": "qs_close"
                }
            },
            {
                "code": "night_vent",
                "label": "Нічний режим вентиляції",
                "kind": "control",
                "class": "A",
                "params": {
                    "intent": "vent_night_mode"
                }
            }
        ],
        "intent_aliases": {
            "vent_night_mode": "vent_eco",
            "air_pressure_setpoint": "air_setpoint",
            "pv_self_consumption": "scenario_toggle:self",
            "heat_schedule_shift": null
        },
        "done_banner": {
            "id": 7,
            "code": "EXPORT-T2",
            "state": "done",
            "title": "Виконано: BESS заряджається 50 кВт",
            "text": "Команда виконана.",
            "actions": [
                {
                    "code": "undo",
                    "label": "Скасувати",
                    "kind": "control",
                    "class": "A",
                    "enabled": true
                }
            ]
        }
    },
    "C-45": {
        "td_energy.viewer_links": {
            "key": "default",
            "entry": {
                "open": "({code}) => Promise"
            },
            "owner": "td_energy_viewer3d (D); читає B у common/actions.js"
        },
        "td_energy.node_actions": {
            "key": "td_energy_control",
            "entry": {
                "match": "(node) => bool",
                "actions": "(node, ctx) => Promise<[{code, label, cls, onClick}]>"
            },
            "owner": "td_energy_control (B); читає B у pult/sld.js"
        },
        "td_energy.advice_handlers": {
            "key": "control",
            "entry": "({action, advice, component}) => Promise<bool>"
        },
        "bus": {
            "channel": "td_energy_control",
            "message": "td_energy_control/update",
            "payload": {
                "kinds": [
                    "action",
                    "scenario",
                    "engine",
                    "schedule",
                    "shed"
                ],
                "ts": "2026-10-18T11:20:03Z"
            }
        }
    },
};
