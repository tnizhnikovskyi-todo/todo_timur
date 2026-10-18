/** @odoo-module */
// Відповіді API-05/06/07/12/13 (C-30) для hoot-тестів. Згенеровано з fixtures/contracts.json (заморожені контракти,
// зміни лише через менеджера): `contracts.json` — джерело істини, цей файл після змін контракту згенерувати знову.
export const CONTRACTS = {
    "API-05": {
        "meta": {
            "now": "2026-10-17T11:20:00",
            "now_local": "14:20",
            "period": "now",
            "data_state": "ok",
            "age_s": 12,
            "subtitle": "Меблеве підприємство · ввід 10 кВ · T1 і T2 по 1000 кВА · ГРЩ 0,4 кВ, дві секції · договірна потужність 800 кВт",
            "contract_kw": 800,
            "tariff_uah": 8.4,
            "refresh_s": 30,
            "control_available": false,
            "capabilities": {
                "ack": true,
                "take": true,
                "cost": true,
                "outage_plan": true,
                "report": false
            }
        },
        "kpis": {
            "grid": {
                "kw": 358,
                "pct": 45,
                "reserve_kw": 442,
                "export_kw": 0
            },
            "load": {
                "kw": 667,
                "pv_share_pct": 46,
                "chp_state": "stop"
            },
            "energy": {
                "label": "З мережі сьогодні",
                "kwh": 6284,
                "cost_uah": 52786,
                "price_uah": 8.4
            },
            "peak": {
                "label": "Пік доби (15 хв)",
                "kw": 631,
                "note": "о 07:30 · 79 % договірної"
            },
            "generation": {
                "pv_kw": 309,
                "pv_pct_kwp": 34,
                "bess_soc_pct": 82,
                "bess_kw": 0,
                "genset": {
                    "state": "reserve",
                    "label": "резерв",
                    "fuel_pct": 78
                }
            },
            "cos_phi": {
                "plant": 0.93,
                "sections": [
                    0.95,
                    0.88
                ],
                "target": 0.95,
                "warn": 0.92,
                "alarm": 0.9,
                "low_sections": [
                    2
                ]
            }
        },
        "advice": {
            "id": 12,
            "code": "EXPORT-T2",
            "title": "СЕС віддає 26 кВт у мережу через T2.",
            "text": "Надлишок генерації експортується. Можна зарядити BESS або увімкнути QS і вирівняти секції.",
            "level": "warn",
            "node_code": "T2",
            "actions": [
                {
                    "code": "open_event",
                    "label": "Відкрити подію",
                    "kind": "link",
                    "class": null,
                    "enabled": true,
                    "params": {
                        "xmlid": "td_energy.action_td_energy_event",
                        "res_id": null
                    }
                },
                {
                    "code": "charge_bess",
                    "label": "Зарядити BESS 50 кВт",
                    "kind": "control",
                    "class": "A",
                    "enabled": false,
                    "params": {
                        "command_kind": "bess_charge"
                    }
                }
            ]
        },
        "sld": {
            "canvas": [
                1320,
                452
            ],
            "nodes": [
                {
                    "code": "GRID-10KV",
                    "label": "Ввід 10 кВ",
                    "shape": "box",
                    "x": 580,
                    "y": 24,
                    "w": 160,
                    "h": 44,
                    "state": "ok",
                    "lines": [
                        "Ввід 10 кВ",
                        "358 кВт з мережі"
                    ],
                    "title": "Ввід 10 кВ",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "RM6-1",
                    "label": "RM6-1",
                    "shape": "box",
                    "x": 580,
                    "y": 100,
                    "w": 160,
                    "h": 44,
                    "state": "ok",
                    "lines": [
                        "RM6-1",
                        "2 відгалуження"
                    ],
                    "title": "RM6-1",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "T1",
                    "label": "T1",
                    "shape": "box",
                    "x": 230,
                    "y": 192,
                    "w": 200,
                    "h": 64,
                    "state": "ok",
                    "lines": [
                        "T1",
                        "384 кВт · 34 %"
                    ],
                    "title": "T1",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "T2",
                    "label": "T2",
                    "shape": "box",
                    "x": 890,
                    "y": 192,
                    "w": 200,
                    "h": 64,
                    "state": "ok",
                    "lines": [
                        "T2",
                        "експорт 26 кВт"
                    ],
                    "title": "T2",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "SEC-1",
                    "label": "Секція шин 1 · 0,4 кВ",
                    "shape": "bar",
                    "x": 40,
                    "y": 298,
                    "w": 590,
                    "h": 6,
                    "state": "ok",
                    "lines": [
                        "Секція шин 1 · 0,4 кВ"
                    ],
                    "title": "Секція шин 1 · 0,4 кВ",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "SEC-2",
                    "label": "Секція шин 2 · 0,4 кВ",
                    "shape": "bar",
                    "x": 690,
                    "y": 298,
                    "w": 590,
                    "h": 6,
                    "state": "ok",
                    "lines": [
                        "Секція шин 2 · 0,4 кВ"
                    ],
                    "title": "Секція шин 2 · 0,4 кВ",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "Q1",
                    "label": "Q1 · 1600 А",
                    "shape": "label",
                    "x": 342,
                    "y": 266,
                    "w": 0,
                    "h": 0,
                    "state": "ok",
                    "lines": [
                        "Q1 · 1600 А"
                    ],
                    "title": "Q1 · 1600 А",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "Q2",
                    "label": "Q2 · 1600 А",
                    "shape": "label",
                    "x": 1002,
                    "y": 266,
                    "w": 0,
                    "h": 0,
                    "state": "ok",
                    "lines": [
                        "Q2 · 1600 А"
                    ],
                    "title": "Q2 · 1600 А",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "QS",
                    "label": "QS",
                    "shape": "switch",
                    "x": 636,
                    "y": 289,
                    "w": 48,
                    "h": 24,
                    "state": "off",
                    "lines": [
                        "QS"
                    ],
                    "title": "QS",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "PV-INV",
                    "label": "СЕС",
                    "shape": "box",
                    "x": 1110,
                    "y": 192,
                    "w": 88,
                    "h": 64,
                    "state": "gen",
                    "lines": [
                        "СЕС",
                        "309 кВт"
                    ],
                    "title": "СЕС",
                    "facts": [
                        "309 кВт зараз · 34 % піку",
                        "Виробіток сьогодні 2184 кВт·год",
                        "Інверторів на зв'язку: 8 з 8"
                    ],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "CHP",
                    "label": "КГУ",
                    "shape": "box",
                    "x": 1214,
                    "y": 192,
                    "w": 88,
                    "h": 64,
                    "state": "off",
                    "lines": [
                        "КГУ",
                        "стоп"
                    ],
                    "title": "КГУ",
                    "facts": [],
                    "card": false,
                    "anchor": null
                },
                {
                    "code": "PFC-1",
                    "label": "PFC-1",
                    "shape": "box",
                    "x": 50,
                    "y": 336,
                    "w": 120,
                    "h": 84,
                    "state": "ok",
                    "lines": [
                        "PFC-1",
                        "280 квар",
                        "8 з 10 ступенів"
                    ],
                    "title": "PFC-1",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "BW-3",
                    "label": "ШР-3",
                    "shape": "box",
                    "x": 190,
                    "y": 336,
                    "w": 120,
                    "h": 84,
                    "state": "ok",
                    "lines": [
                        "ШР-3",
                        "88 А · 14 %",
                        "8 відгалужень"
                    ],
                    "title": "ШР-3",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "BW-2",
                    "label": "ШР-2",
                    "shape": "box",
                    "x": 330,
                    "y": 336,
                    "w": 120,
                    "h": 84,
                    "state": "ok",
                    "lines": [
                        "ШР-2",
                        "192 А · 30 %",
                        "лінії C–D"
                    ],
                    "title": "ШР-2",
                    "facts": [
                        "192 А з 630 А · 30 %",
                        "124 кВт · 10 відгалужень, 2 не працюють"
                    ],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "C1",
                    "label": "C1",
                    "shape": "box",
                    "x": 470,
                    "y": 336,
                    "w": 120,
                    "h": 84,
                    "state": "ok",
                    "lines": [
                        "C1",
                        "141 А · 22 %",
                        "лінія C1"
                    ],
                    "title": "C1",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "BW-1",
                    "label": "ШР-1",
                    "shape": "box",
                    "x": 694,
                    "y": 336,
                    "w": 90,
                    "h": 84,
                    "state": "ok",
                    "lines": [
                        "ШР-1",
                        "75 А · 12 %"
                    ],
                    "title": "ШР-1",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "BW-4",
                    "label": "ШР-4",
                    "shape": "box",
                    "x": 792,
                    "y": 336,
                    "w": 90,
                    "h": 84,
                    "state": "ok",
                    "lines": [
                        "ШР-4",
                        "61 А · 10 %"
                    ],
                    "title": "ШР-4",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "C2",
                    "label": "C2",
                    "shape": "box",
                    "x": 890,
                    "y": 336,
                    "w": 90,
                    "h": 84,
                    "state": "alarm",
                    "lines": [
                        "C2",
                        "немає даних",
                        "лічильник"
                    ],
                    "title": "C2",
                    "facts": [
                        "Лічильник PM-QF-C2 не на зв'язку з 13:47",
                        "Оцінка за балансом секції: ≈ 96 кВт"
                    ],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "PFC-2",
                    "label": "PFC-2",
                    "shape": "box",
                    "x": 988,
                    "y": 336,
                    "w": 90,
                    "h": 84,
                    "state": "warn",
                    "lines": [
                        "PFC-2",
                        "175 квар",
                        "5 з 10 ступенів"
                    ],
                    "title": "PFC-2",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "BESS",
                    "label": "BESS",
                    "shape": "box",
                    "x": 1086,
                    "y": 336,
                    "w": 90,
                    "h": 84,
                    "state": "ok",
                    "lines": [
                        "BESS",
                        "82 %",
                        "очікування"
                    ],
                    "title": "BESS",
                    "facts": [],
                    "card": true,
                    "anchor": null
                },
                {
                    "code": "ATS-1",
                    "label": "АВР · ДГУ",
                    "shape": "box",
                    "x": 1184,
                    "y": 336,
                    "w": 90,
                    "h": 84,
                    "state": "off",
                    "lines": [
                        "АВР · ДГУ",
                        "мережа"
                    ],
                    "title": "АВР · ДГУ",
                    "facts": [],
                    "card": true,
                    "anchor": "SEC-2"
                }
            ],
            "edges": [
                {
                    "from": "RM6-1",
                    "to": "GRID-10KV",
                    "state": "ok"
                },
                {
                    "from": "T1",
                    "to": "RM6-1",
                    "state": "ok"
                },
                {
                    "from": "T2",
                    "to": "RM6-1",
                    "state": "ok"
                },
                {
                    "from": "SEC-1",
                    "to": "T1",
                    "state": "ok"
                },
                {
                    "from": "SEC-2",
                    "to": "T2",
                    "state": "ok"
                },
                {
                    "from": "PV-INV",
                    "to": "T2",
                    "state": "gen"
                },
                {
                    "from": "CHP",
                    "to": "T2",
                    "state": "off"
                },
                {
                    "from": "PFC-1",
                    "to": "SEC-1",
                    "state": "ok"
                },
                {
                    "from": "BW-3",
                    "to": "SEC-1",
                    "state": "ok"
                },
                {
                    "from": "BW-2",
                    "to": "SEC-1",
                    "state": "ok"
                },
                {
                    "from": "C1",
                    "to": "SEC-1",
                    "state": "ok"
                },
                {
                    "from": "BW-1",
                    "to": "SEC-2",
                    "state": "ok"
                },
                {
                    "from": "BW-4",
                    "to": "SEC-2",
                    "state": "ok"
                },
                {
                    "from": "C2",
                    "to": "SEC-2",
                    "state": "alarm"
                },
                {
                    "from": "PFC-2",
                    "to": "SEC-2",
                    "state": "warn"
                },
                {
                    "from": "BESS",
                    "to": "SEC-2",
                    "state": "ok"
                },
                {
                    "from": "ATS-1",
                    "to": "SEC-2",
                    "state": "off"
                }
            ]
        },
        "profile": {
            "step_min": 15,
            "now_slot": 57,
            "contract_kw": 800,
            "cons": [
                210,
                212,
                214,
                216,
                218,
                210,
                212,
                214,
                216,
                218,
                210,
                212,
                214,
                216,
                218,
                210,
                212,
                214,
                216,
                218,
                210,
                212,
                214,
                216,
                218,
                210,
                212.0,
                324.0,
                436.0,
                548.0,
                650,
                652,
                654,
                656,
                658,
                650,
                652,
                654,
                656,
                658,
                650,
                652,
                654,
                656,
                658,
                650,
                652,
                654,
                436,
                438,
                430,
                669,
                671,
                673,
                675,
                667,
                669,
                671,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
            ],
            "grid": [
                210.0,
                212.0,
                214.0,
                216.0,
                218.0,
                210.0,
                212.0,
                214.0,
                216.0,
                218.0,
                210.0,
                212.0,
                214.0,
                216.0,
                218.0,
                210.0,
                212.0,
                214.0,
                216.0,
                218.0,
                210.0,
                212.0,
                214.0,
                216.0,
                218.0,
                210.0,
                195.8,
                277.7,
                354.2,
                427.1,
                487.5,
                446.3,
                404.1,
                361.4,
                318.9,
                266.9,
                226.0,
                186.5,
                148.8,
                113.3,
                70.4,
                40.2,
                13.2,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0.6,
                28.2,
                59.2,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
            ],
            "pv": [
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                16.2,
                46.3,
                81.8,
                120.9,
                162.5,
                205.7,
                249.9,
                294.6,
                339.1,
                383.1,
                426.0,
                467.5,
                507.2,
                544.7,
                579.6,
                611.8,
                640.8,
                666.4,
                688.5,
                706.8,
                721.3,
                731.6,
                737.9,
                740.0,
                737.9,
                731.6,
                721.3,
                706.8,
                688.5,
                666.4,
                640.8,
                611.8,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
            ],
            "cons_fc": [
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                671,
                671,
                671,
                671,
                671,
                671,
                671,
                524,
                524,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564,
                564.0,
                476.5,
                389.0,
                301.5,
                214,
                214
            ],
            "grid_fc": [
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                59.2,
                122.7,
                155.8,
                191.2,
                228.7,
                268.0,
                308.6,
                203.2,
                245.3,
                327.6,
                369.4,
                410.3,
                449.6,
                486.6,
                520.2,
                548.7,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                564.0,
                476.5,
                389.0,
                301.5,
                214.0,
                214.0
            ],
            "peak": {
                "kw": 631,
                "slot": 30
            },
            "forecast_days_used": 8
        },
        "foot": {
            "forecast_kwh": 9120,
            "export_kwh": 118,
            "imbalance": {
                "pct": 1.8,
                "hour": "13:00–14:00",
                "tol_pct": 3
            }
        },
        "alarms": {
            "active_count": 3,
            "items": [
                {
                    "id": 101,
                    "level": "alarm",
                    "time": "13:47",
                    "title": "Лічильник PM-QF-C2 не на зв'язку",
                    "detail": "33 хв без даних (Modbus). Енергія фідера C2 рахується як оцінка.",
                    "state": "active",
                    "acked_by": null,
                    "acked_by_me": false,
                    "acked_at": null,
                    "assigned": null,
                    "taken_by_me": false,
                    "node_code": "C2",
                    "request_id": null,
                    "request_assignable": false,
                    "actions": [
                        {
                            "code": "diag",
                            "label": "Діагностика"
                        }
                    ],
                    "diag": "Джерело MB-U14-PM-QF-C2 (iot-sim:502, unit 14): немає відповіді з 13:47:12 · колектор COL-MAIN на зв'язку · перевірте лінію й комірку QF-C2."
                },
                {
                    "id": 102,
                    "level": "warn",
                    "time": "14:06",
                    "title": "PFC-2: ступінь 3 не вмикається",
                    "detail": "cos φ секції 2 — 0,88.",
                    "state": "acked",
                    "acked_by": "Іваненко І.",
                    "acked_by_me": false,
                    "acked_at": "14:08",
                    "assigned": "Іваненко І.",
                    "taken_by_me": false,
                    "node_code": "PFC-2",
                    "request_id": 77,
                    "request_assignable": false,
                    "actions": [
                        {
                            "code": "request",
                            "label": "Заявка ТО"
                        }
                    ],
                    "diag": null
                },
                {
                    "id": 90,
                    "level": "info",
                    "time": "07:02",
                    "title": "Тест АВР і ДГУ пройдено",
                    "detail": "Перемикання на ДГУ 8,4 с, повернення на мережу без зауважень.",
                    "state": "na",
                    "acked_by": null,
                    "acked_by_me": false,
                    "acked_at": null,
                    "assigned": null,
                    "taken_by_me": false,
                    "node_code": "ATS-1",
                    "request_id": null,
                    "request_assignable": false,
                    "actions": [],
                    "diag": null
                }
            ]
        },
        "top": [
            {
                "code": "DUST-1",
                "name": "Вентилятори аспірації",
                "kw": 96
            },
            {
                "code": "COMPRESSOR",
                "name": "Компресорна",
                "kw": 88
            }
        ],
        "mo": {
            "rows": [
                {
                    "name": "WH/MO/00418",
                    "product": "Корпус шафи-купе 2000",
                    "kwh": 214,
                    "cost_uah": 1798,
                    "share_pct": 3.4
                }
            ],
            "pools_kwh": 1120
        },
        "maint": [
            {
                "title": "PFC-2 · ступінь 3 не вмикається",
                "sub": "заявка з тривоги · 14:06",
                "state": "Нова",
                "kind": "request",
                "id": 77
            },
            {
                "title": "ШР-2 · планове відключення 25.10 07:00–09:00",
                "sub": "на узгодженні",
                "state": "Чернетка",
                "kind": "outage",
                "id": 5
            }
        ]
    },
    "API-06": {
        "active_count": 2,
        "items": [
            {
                "id": 101,
                "level": "alarm",
                "time": "13:47",
                "title": "Лічильник PM-QF-C2 не на зв'язку",
                "detail": "33 хв без даних (Modbus). Енергія фідера C2 рахується як оцінка.",
                "state": "active",
                "acked_by": null,
                "acked_by_me": false,
                "acked_at": null,
                "assigned": null,
                "taken_by_me": false,
                "node_code": "C2",
                "request_id": null,
                "request_assignable": false,
                "actions": [
                    {
                        "code": "diag",
                        "label": "Діагностика"
                    }
                ],
                "diag": "Джерело MB-U14-PM-QF-C2 (iot-sim:502, unit 14): немає відповіді з 13:47:12 · колектор COL-MAIN на зв'язку · перевірте лінію й комірку QF-C2."
            },
            {
                "id": 102,
                "level": "warn",
                "time": "14:06",
                "title": "PFC-2: ступінь 3 не вмикається",
                "detail": "cos φ секції 2 — 0,88.",
                "state": "acked",
                "acked_by": "Іваненко І.",
                "acked_by_me": false,
                "acked_at": "14:08",
                "assigned": "Іваненко І.",
                "taken_by_me": false,
                "node_code": "PFC-2",
                "request_id": 77,
                "request_assignable": false,
                "actions": [
                    {
                        "code": "request",
                        "label": "Заявка ТО"
                    }
                ],
                "diag": null
            }
        ]
    },
    "API-07": {
        "node": {
            "code": "BW-2",
            "name": "ШР-2 · лінії C–D, нестинг, портал",
            "kind": "line",
            "kind_label": "Шинопровід 630 А",
            "path": [
                {
                    "code": "SWB-1",
                    "name": "ГРЩ 0,4 кВ"
                },
                {
                    "code": "SEC-1",
                    "name": "Секція 1"
                },
                {
                    "code": "QF-2",
                    "name": "QF-2"
                },
                {
                    "code": "BW-2",
                    "name": "ШР-2"
                }
            ],
            "chips": [
                {
                    "text": "Під напругою",
                    "state": "ok"
                },
                {
                    "text": "Шинопровід 630 А · живиться від QF-2",
                    "state": "ok"
                },
                {
                    "text": "Лічильник PM-QF-2 на зв'язку",
                    "state": "ok"
                }
            ],
            "can_3d": true
        },
        "kpis": {
            "current": {
                "a": 192,
                "pct": 30,
                "phases": [
                    188,
                    195,
                    193
                ],
                "rating_a": 630
            },
            "power": {
                "kw": 124,
                "p_inst_kw": 217,
                "cos_phi": 0.91
            },
            "energy": {
                "kwh": 1384,
                "cost_uah": 11626,
                "orders": 7
            },
            "peak": {
                "a": 328,
                "time": "07:45",
                "warn_a": 504
            },
            "idle": {
                "kw": 2.4,
                "names": [
                    "VSAW-1",
                    "CNC-4"
                ]
            }
        },
        "chart": {
            "step_min": 15,
            "now_slot": 57,
            "a": [
                60.4,
                64.0,
                67.6,
                62.2,
                65.8,
                66.4,
                61.0,
                64.6,
                68.2,
                62.8,
                63.4,
                67.0,
                61.6,
                65.2,
                68.8,
                60.4,
                64.0,
                67.6,
                62.2,
                65.8,
                66.4,
                61.0,
                64.6,
                68.2,
                62.8,
                63.4,
                67.0,
                93.3,
                128.5,
                163.7,
                187.1,
                190.7,
                194.3,
                188.8,
                192.4,
                193.1,
                187.7,
                191.3,
                194.8,
                189.4,
                190.1,
                193.7,
                188.3,
                191.8,
                195.4,
                187.1,
                190.7,
                194.3,
                125.5,
                129.1,
                129.8,
                192.6,
                196.2,
                199.7,
                194.3,
                195.0,
                198.6,
                193.2,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
            ],
            "warn_a": 504,
            "rating_a": 630,
            "peak": {
                "a": 328,
                "slot": 31
            }
        },
        "taps": {
            "sum_kw": 120.7,
            "aux_kw": 3.3,
            "count": 2,
            "rows": [
                {
                    "tap": "TAP-SAW-3",
                    "code": "SAW-3",
                    "name": "Пакетний розкрій",
                    "inst_kw": 45,
                    "now_kw": 31,
                    "state": "run",
                    "job": "WH/MO/00418 · розкрій плит",
                    "node_code": "SAW-3"
                },
                {
                    "tap": "TAP-CNC-4",
                    "code": "CNC-4",
                    "name": "Обробний центр",
                    "inst_kw": 22,
                    "now_kw": 0.9,
                    "state": "mnt",
                    "job": "заявка ТО · CNC-4 · заміна шпинделя",
                    "node_code": "CNC-4"
                }
            ]
        },
        "meter": {
            "code": "PM-QF-2",
            "model": "Schneider PM5560",
            "ct_ratio": "630/5",
            "last_ts": "14:20:05",
            "last_kwh": 1284517,
            "next_verification": "2026-10-30",
            "balance_pct": -1.2
        },
        "protection": {
            "breaker": "QF-2",
            "rating_a": 630,
            "trip_unit": "електронний",
            "ir": {
                "ratio": 0.9,
                "a": 567
            },
            "trips_year": 0,
            "thermography": {
                "date": "2026-10-21",
                "state": "Заплановано"
            }
        },
        "events": [
            {
                "time": "07:45",
                "text": "Максимум доби 328 А, нижче порогу уваги",
                "kind": "peak"
            }
        ],
        "maintenance": [
            {
                "title": "CNC-4 · заміна шпинделя",
                "when": "у роботі",
                "state": "У роботі",
                "id": 12
            }
        ],
        "outage": {
            "plan_id": 5,
            "when": "25.10 · 07:00–09:00",
            "reason": "протяжка з'єднань шинопроводу",
            "orders": 3,
            "state": "pending",
            "state_label": "на узгодженні"
        },
        "extra": {}
    },
    "API-12": {
        "meta": {
            "now": "2026-10-17T11:20:00",
            "now_local": "14:20",
            "data_state": "ok",
            "age_s": 12,
            "refresh_s": 30,
            "control_available": false,
            "capabilities": {
                "ack": true,
                "take": true,
                "cost": true
            }
        },
        "state": {
            "grid_kw": 358,
            "pct": 45,
            "pv_kw": 309,
            "bess": {
                "soc_pct": 82,
                "kw": 0,
                "text": "Очікування, 0 кВт"
            },
            "genset_ats": {
                "text": "ДГУ · АВР: мережа"
            },
            "cos_phi": {
                "plant": 0.93,
                "low_sections": [
                    2
                ]
            }
        },
        "alarms": {
            "active_count": 1,
            "active": [
                {
                    "id": 101,
                    "level": "alarm",
                    "time": "13:47",
                    "title": "Лічильник PM-QF-C2 не на зв'язку",
                    "detail": "33 хв без даних (Modbus). Енергія фідера C2 рахується як оцінка.",
                    "state": "active",
                    "acked_by": null,
                    "acked_by_me": false,
                    "acked_at": null,
                    "assigned": null,
                    "taken_by_me": false,
                    "node_code": "C2",
                    "request_id": null,
                    "request_assignable": false,
                    "actions": [
                        {
                            "code": "diag",
                            "label": "Діагностика"
                        }
                    ],
                    "diag": "Джерело MB-U14-PM-QF-C2 (iot-sim:502, unit 14): немає відповіді з 13:47:12 · колектор COL-MAIN на зв'язку · перевірте лінію й комірку QF-C2."
                },
                {
                    "id": 102,
                    "level": "warn",
                    "time": "14:06",
                    "title": "PFC-2: ступінь 3 не вмикається",
                    "detail": "cos φ секції 2 — 0,88.",
                    "state": "acked",
                    "acked_by": "Іваненко І.",
                    "acked_by_me": false,
                    "acked_at": "14:08",
                    "assigned": "Іваненко І.",
                    "taken_by_me": false,
                    "node_code": "PFC-2",
                    "request_id": 77,
                    "request_assignable": false,
                    "actions": [
                        {
                            "code": "request",
                            "label": "Заявка ТО"
                        }
                    ],
                    "diag": null
                }
            ],
            "info_today": [
                {
                    "time": "07:02",
                    "text": "Тест АВР і ДГУ пройдено"
                }
            ],
            "advice": null
        },
        "scheme": [
            {
                "code": "GRID-10KV",
                "name": "Ввід 10 кВ",
                "value": "358 кВт з мережі",
                "state": "ok"
            },
            {
                "code": "T1",
                "name": "T1",
                "value": "384 кВт · 34 %",
                "state": "ok"
            },
            {
                "code": "T2",
                "name": "T2",
                "value": "експорт 26 кВт",
                "state": "ok"
            },
            {
                "code": "BW-2",
                "name": "ШР-2",
                "value": "192 А · 30 %",
                "state": "ok"
            },
            {
                "code": "C2",
                "name": "C2",
                "value": "немає даних",
                "state": "alarm"
            },
            {
                "code": "PFC-2",
                "name": "PFC-2",
                "value": "175 квар",
                "state": "warn"
            },
            {
                "code": "PV-INV",
                "name": "СЕС",
                "value": "309 кВт",
                "state": "gen"
            },
            {
                "code": "BESS",
                "name": "BESS",
                "value": "82 %",
                "state": "ok"
            },
            {
                "code": "ATS-1",
                "name": "АВР · ДГУ",
                "value": "мережа",
                "state": "off"
            }
        ]
    },
    "API-13": {
        "ts": "2026-10-17T11:20:00",
        "cards": [
            {
                "code": "PV-INV",
                "title": "СЕС",
                "kind": "pv",
                "state": "gen",
                "kpis": [
                    {
                        "label": "Потужність",
                        "value": "309",
                        "unit": "кВт"
                    },
                    {
                        "label": "% піку СЕС",
                        "value": "34",
                        "unit": "%"
                    },
                    {
                        "label": "Виробіток сьогодні",
                        "value": "2184",
                        "unit": "кВт·год"
                    },
                    {
                        "label": "Інверторів на зв'язку",
                        "value": "8 з 8",
                        "unit": ""
                    }
                ],
                "facts": [
                    "Пік сьогодні 640 кВт о 12:30"
                ],
                "node_code": "PV-INV",
                "can_3d": true
            },
            {
                "code": "CHP",
                "title": "КГУ",
                "kind": "chp",
                "state": "off",
                "kpis": [
                    {
                        "label": "Стан",
                        "value": "стоп",
                        "unit": ""
                    },
                    {
                        "label": "Потужність",
                        "value": "0",
                        "unit": "кВт"
                    },
                    {
                        "label": "Мотогодини",
                        "value": "1204",
                        "unit": "год"
                    },
                    {
                        "label": "Витрата газу",
                        "value": "0",
                        "unit": "м³/год"
                    }
                ],
                "facts": [],
                "node_code": "CHP",
                "can_3d": true
            },
            {
                "code": "BESS",
                "title": "BESS",
                "kind": "bess",
                "state": "ok",
                "kpis": [
                    {
                        "label": "Заряд",
                        "value": "82",
                        "unit": "%"
                    },
                    {
                        "label": "Потужність",
                        "value": "0",
                        "unit": "кВт"
                    },
                    {
                        "label": "Режим",
                        "value": "очікування",
                        "unit": ""
                    }
                ],
                "facts": [
                    "Резерв на відключення мережі 30 %"
                ],
                "node_code": "BESS",
                "can_3d": true
            },
            {
                "code": "ATS-1",
                "title": "АВР",
                "kind": "ats",
                "state": "off",
                "kpis": [
                    {
                        "label": "Положення",
                        "value": "мережа",
                        "unit": ""
                    },
                    {
                        "label": "Режим АВР",
                        "value": "авто",
                        "unit": ""
                    },
                    {
                        "label": "Джерело 1 / 2",
                        "value": "норма / резерв",
                        "unit": ""
                    }
                ],
                "facts": [
                    "Критичне навантаження 148 кВт"
                ],
                "node_code": "ATS-1",
                "can_3d": true
            }
        ]
    }
};
