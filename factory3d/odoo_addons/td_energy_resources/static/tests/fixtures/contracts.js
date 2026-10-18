/** @odoo-module */
// Відповіді API-01/02/06/10 та контракти C-01/C-02 для hoot-тестів. Згенеровано з fixtures/contracts.json
// (заморожені контракти, зміни лише через менеджера): `contracts.json` — джерело істини.
export const CONTRACTS = {
    "_meta": {
        "version": "1.0",
        "frozen": "2026-10-18",
        "owner": "менеджер (зміни лише через нього)",
        "source": "build/energy/W3_SPEC.md розд. 7 (API-01…API-10), R-08…R-12, R-25; build/energy/W3_ARCH.md §2.1 (C-01, C-02)",
        "purpose": "Заморожені форми відповідей td.energy.res.dashboard / td.energy.opportunity та супутніх методів: моки для hoot-тестів воркера C; бекенд воркерів E (API-01, API-10) і B (API-02…API-06) звіряється з цим файлом тестами (`test_contract_shape`).",
        "rules": [
            "Усі значення — приклад (макет, 14:20 за Києвом, субота 17.10.2026); значущі лише ключі, їх типи й набір.",
            "`null` — немає свіжих даних (UI показує «—»). `chart.series` — завжди 96 елементів (локальні слоти); слоти після `now_slot` — null.",
            "Ключі вартості (`cost_uah`, `save_uah_month`, `plan_sum`, `all_sum`, `cost`, `price`, `capabilities.cost`) ВІДСУТНІ без групи td_energy.group_td_energy_cost; підписи без «₴».",
            "`API-01` — по одній відповіді `get_resources(code)` на ресурс: `meta` і `tabs` однакові для всіх вкладок, `resource` — різний; ядро без моста не виводить KPI `indoor`, `recovery` і не підміняє `list` вкладки «Тепло».",
            "`kpis[].tone ∈ {good, bad, neutral}`; `quality ∈ {measured, estimated}`; `meta.data_state ∈ {ok, partial, stale}`; `list.basis ∈ {rate, qty_day}`.",
            "Сигнал уставки тиску повітря — `energy_control/air/setpoint_bar` (W2); не `air/setpoint_bar`.",
            "`actions[]` — контракт W1 C-32 (`kind ∈ {link, ticket, control}`); `enabled = (kind != 'control') or td.energy.advice._td_control_available()`; якщо немає жодної `enabled`-дії — в кінець додається `fallback_action`."
        ]
    },
    "API-01": {
        "el": {
            "meta": {
                "now": "2026-10-17T11:20:00",
                "now_local": "14:20",
                "data_state": "ok",
                "age_s": 18,
                "refresh_s": 30,
                "control_available": false,
                "capabilities": {
                    "cost": true,
                    "export": true,
                    "manage": true
                },
                "total": {
                    "cost_uah": 65156,
                    "text": "Сьогодні разом: 65 156 ₴ · Електрика, Газ, Вода. Похідні не додаються: Тепло, Стиснене повітря."
                }
            },
            "tabs": [
                {
                    "code": "el",
                    "name": "Електрика",
                    "rate": 358,
                    "rate_unit": "кВт",
                    "cost_uah": 52786,
                    "sub": "358 кВт · 52 786 ₴"
                },
                {
                    "code": "gas",
                    "name": "Газ",
                    "rate": 46,
                    "rate_unit": "м³/год",
                    "cost_uah": 12118,
                    "sub": "46 м³/год · 12 118 ₴"
                },
                {
                    "code": "heat",
                    "name": "Тепло",
                    "rate": 390,
                    "rate_unit": "кВт",
                    "sub": "390 кВт · з BMS"
                },
                {
                    "code": "air",
                    "name": "Стиснене повітря",
                    "rate": 9.8,
                    "rate_unit": "м³/хв",
                    "cost_uah": 5393,
                    "sub": "9,8 м³/хв · 5 393 ₴"
                },
                {
                    "code": "water",
                    "name": "Вода",
                    "rate": 0.4,
                    "rate_unit": "м³/год",
                    "cost_uah": 252,
                    "sub": "0,4 м³/год · 252 ₴"
                }
            ],
            "resource": {
                "code": "el",
                "name": "Електрика",
                "color": "#714B67",
                "kpis": [
                    {
                        "id": "grid_now",
                        "label": "Імпорт з мережі зараз",
                        "value": 358,
                        "unit": "кВт",
                        "note": "45 % договірної 800 кВт",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "today",
                        "label": "Сьогодні",
                        "value": 6284,
                        "unit": "кВт·год",
                        "note": "52 786 ₴ · 8,40 ₴/кВт·год",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "generation",
                        "label": "Власна генерація сьогодні",
                        "value": 1840,
                        "unit": "кВт·год",
                        "note": "СЕС 82 % · КГУ 0 % · частка 29 %",
                        "tone": "good",
                        "quality": "measured"
                    },
                    {
                        "id": "reactive",
                        "label": "Реактивна енергія сьогодні",
                        "value": 2514,
                        "unit": "квар·год",
                        "note": "tg φ 0,40",
                        "tone": "neutral",
                        "quality": "measured"
                    }
                ],
                "chart": {
                    "title": "Імпорт з мережі, кВт",
                    "note": "ліміт — договірна 800 кВт",
                    "unit": "кВт",
                    "y_max": 900,
                    "ticks": [
                        300,
                        600,
                        900
                    ],
                    "step_min": 15,
                    "now_slot": 57,
                    "series": [
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        210.0,
                        231.0,
                        251.0,
                        272.0,
                        292.0,
                        312.0,
                        332.0,
                        352.0,
                        371.0,
                        390.0,
                        408.0,
                        426.0,
                        444.0,
                        461.0,
                        477.0,
                        493.0,
                        508.0,
                        522.0,
                        535.0,
                        548.0,
                        560.0,
                        571.0,
                        581.0,
                        591.0,
                        599.0,
                        606.0,
                        613.0,
                        618.0,
                        623.0,
                        626.0,
                        629.0,
                        630.0,
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
                    "limit": 800,
                    "foot": "Пік доби 631 кВт о 11:45. З 10:30 частина енергії СЕС віддавалась у мережу (118 кВт·год)."
                },
                "list": {
                    "title": "Найбільші споживачі зараз",
                    "basis": "rate",
                    "unit": "кВт",
                    "items": [
                        {
                            "code": "COMPRESSOR",
                            "name": "Компресорна",
                            "value": 52,
                            "share": 1.0,
                            "quality": "measured"
                        },
                        {
                            "code": "RV-ALL",
                            "name": "Вентиляція RV",
                            "value": 47,
                            "share": 0.904,
                            "quality": "measured"
                        },
                        {
                            "code": "NEST-1",
                            "name": "Нестинг ЧПК",
                            "value": 41,
                            "share": 0.788,
                            "quality": "measured"
                        }
                    ],
                    "unaccounted": null
                },
                "notes": [
                    {
                        "id": 21,
                        "title": "Вентиляція працює поза змінами",
                        "text": "Уночі RV-ALL споживає 88 % денного рівня.",
                        "save_uah_month": 45725,
                        "actions": [
                            {
                                "code": "control",
                                "label": "Змінити режим",
                                "kind": "control",
                                "class": null,
                                "params": {
                                    "intent": "vent_night_mode"
                                },
                                "enabled": false
                            },
                            {
                                "code": "open",
                                "label": "Відкрити",
                                "kind": "link",
                                "class": null,
                                "params": {
                                    "xmlid": "td_energy_resources.action_td_energy_opportunity",
                                    "res_id": 21
                                },
                                "enabled": true
                            }
                        ]
                    },
                    {
                        "id": 22,
                        "title": "Холостий хід верстатів під напругою",
                        "text": "Верстати стоять під напругою поза змінами.",
                        "save_uah_month": 10439,
                        "actions": [
                            {
                                "code": "open",
                                "label": "Відкрити",
                                "kind": "link",
                                "class": null,
                                "params": {
                                    "xmlid": "td_energy_resources.action_td_energy_opportunity",
                                    "res_id": 22
                                },
                                "enabled": true
                            }
                        ]
                    }
                ]
            }
        },
        "gas": {
            "meta": {
                "now": "2026-10-17T11:20:00",
                "now_local": "14:20",
                "data_state": "ok",
                "age_s": 18,
                "refresh_s": 30,
                "control_available": false,
                "capabilities": {
                    "cost": true,
                    "export": true,
                    "manage": true
                },
                "total": {
                    "cost_uah": 65156,
                    "text": "Сьогодні разом: 65 156 ₴ · Електрика, Газ, Вода. Похідні не додаються: Тепло, Стиснене повітря."
                }
            },
            "tabs": [
                {
                    "code": "el",
                    "name": "Електрика",
                    "rate": 358,
                    "rate_unit": "кВт",
                    "cost_uah": 52786,
                    "sub": "358 кВт · 52 786 ₴"
                },
                {
                    "code": "gas",
                    "name": "Газ",
                    "rate": 46,
                    "rate_unit": "м³/год",
                    "cost_uah": 12118,
                    "sub": "46 м³/год · 12 118 ₴"
                },
                {
                    "code": "heat",
                    "name": "Тепло",
                    "rate": 390,
                    "rate_unit": "кВт",
                    "sub": "390 кВт · з BMS"
                },
                {
                    "code": "air",
                    "name": "Стиснене повітря",
                    "rate": 9.8,
                    "rate_unit": "м³/хв",
                    "cost_uah": 5393,
                    "sub": "9,8 м³/хв · 5 393 ₴"
                },
                {
                    "code": "water",
                    "name": "Вода",
                    "rate": 0.4,
                    "rate_unit": "м³/год",
                    "cost_uah": 252,
                    "sub": "0,4 м³/год · 252 ₴"
                }
            ],
            "resource": {
                "code": "gas",
                "name": "Газ",
                "color": "#b45309",
                "kpis": [
                    {
                        "id": "rate",
                        "label": "Витрата зараз",
                        "value": 46,
                        "unit": "м³/год",
                        "note": "котельня BOILER · КГУ стоїть",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "today",
                        "label": "Сьогодні",
                        "value": 612,
                        "unit": "м³",
                        "note": "12 118 ₴ · 19,80 ₴/м³",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "limit",
                        "label": "Ліміт доби за договором",
                        "value": 1200,
                        "unit": "м³",
                        "note": "використано 51 %",
                        "tone": "good",
                        "quality": "measured"
                    },
                    {
                        "id": "eff",
                        "label": "ККД котельні",
                        "value": 91.4,
                        "unit": "%",
                        "note": "норма ≥ 90 %",
                        "tone": "good",
                        "quality": "estimated"
                    }
                ],
                "chart": {
                    "title": "Витрата газу, м³/год",
                    "note": "ліміт години — 80 м³/год",
                    "unit": "м³/год",
                    "y_max": 90,
                    "ticks": [
                        30,
                        60,
                        90
                    ],
                    "step_min": 15,
                    "now_slot": 57,
                    "series": [
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        22.0,
                        23.3,
                        24.5,
                        25.8,
                        27.1,
                        28.3,
                        29.5,
                        30.8,
                        31.9,
                        33.1,
                        34.3,
                        35.4,
                        36.4,
                        37.5,
                        38.5,
                        39.5,
                        40.4,
                        41.3,
                        42.1,
                        42.9,
                        43.6,
                        44.3,
                        44.9,
                        45.5,
                        46.0,
                        46.5,
                        46.9,
                        47.2,
                        47.5,
                        47.7,
                        47.9,
                        48.0,
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
                    "limit": 80,
                    "foot": "Нічна витрата 22 м³/год, у зміну 46 м³/год. Пік 48 м³/год о 11:15."
                },
                "list": {
                    "title": "Споживачі газу",
                    "basis": "rate",
                    "unit": "м³/год",
                    "items": [
                        {
                            "code": "BOILER",
                            "name": "Котельня цеху",
                            "value": 41,
                            "share": 1.0,
                            "quality": "measured"
                        },
                        {
                            "code": "DRY-1",
                            "name": "Сушильна камера (газовий пальник)",
                            "value": 4,
                            "share": 0.098,
                            "quality": "estimated"
                        },
                        {
                            "code": "CHP",
                            "name": "КГУ TEDOM (резерв)",
                            "value": 0,
                            "share": 0.0,
                            "quality": "measured"
                        },
                        {
                            "code": "CANTEEN",
                            "name": "Їдальня",
                            "value": 1,
                            "share": 0.024,
                            "quality": "estimated"
                        }
                    ],
                    "unaccounted": {
                        "value": 0.0,
                        "pct": 0.0
                    }
                },
                "notes": [
                    {
                        "id": 31,
                        "title": "Розігрів перед зміною починається зарано",
                        "text": "Цех досягає 18 °C о 06:05, а зміна о 07:00. Пізніший старт на 40 хв.",
                        "save_uah_month": 6900,
                        "actions": [
                            {
                                "code": "open",
                                "label": "Відкрити",
                                "kind": "link",
                                "class": null,
                                "params": {
                                    "xmlid": "td_energy_resources.action_td_energy_opportunity",
                                    "res_id": 31
                                },
                                "enabled": true
                            }
                        ]
                    }
                ]
            }
        },
        "heat": {
            "meta": {
                "now": "2026-10-17T11:20:00",
                "now_local": "14:20",
                "data_state": "ok",
                "age_s": 18,
                "refresh_s": 30,
                "control_available": false,
                "capabilities": {
                    "cost": true,
                    "export": true,
                    "manage": true
                },
                "total": {
                    "cost_uah": 65156,
                    "text": "Сьогодні разом: 65 156 ₴ · Електрика, Газ, Вода. Похідні не додаються: Тепло, Стиснене повітря."
                }
            },
            "tabs": [
                {
                    "code": "el",
                    "name": "Електрика",
                    "rate": 358,
                    "rate_unit": "кВт",
                    "cost_uah": 52786,
                    "sub": "358 кВт · 52 786 ₴"
                },
                {
                    "code": "gas",
                    "name": "Газ",
                    "rate": 46,
                    "rate_unit": "м³/год",
                    "cost_uah": 12118,
                    "sub": "46 м³/год · 12 118 ₴"
                },
                {
                    "code": "heat",
                    "name": "Тепло",
                    "rate": 390,
                    "rate_unit": "кВт",
                    "sub": "390 кВт · з BMS"
                },
                {
                    "code": "air",
                    "name": "Стиснене повітря",
                    "rate": 9.8,
                    "rate_unit": "м³/хв",
                    "cost_uah": 5393,
                    "sub": "9,8 м³/хв · 5 393 ₴"
                },
                {
                    "code": "water",
                    "name": "Вода",
                    "rate": 0.4,
                    "rate_unit": "м³/год",
                    "cost_uah": 252,
                    "sub": "0,4 м³/год · 252 ₴"
                }
            ],
            "resource": {
                "code": "heat",
                "name": "Тепло",
                "color": "#c2410c",
                "kpis": [
                    {
                        "id": "power",
                        "label": "Теплова потужність",
                        "value": 390,
                        "unit": "кВт",
                        "note": "подача 70 °C · зворот 52 °C",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "today",
                        "label": "Сьогодні",
                        "value": 5183,
                        "unit": "кВт·год",
                        "note": "теплобаланс BMS",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "indoor",
                        "label": "Температура в цеху",
                        "value": 18.2,
                        "unit": "°C",
                        "note": "уставка 18 °C · зовні 7 °C",
                        "tone": "good",
                        "quality": "measured"
                    },
                    {
                        "id": "recovery",
                        "label": "Рекуперація AHU-1",
                        "value": 63,
                        "unit": "%",
                        "note": "норма ≥ 70 %",
                        "tone": "bad",
                        "quality": "estimated"
                    }
                ],
                "chart": {
                    "title": "Теплова потужність, кВт",
                    "note": "теплобаланс цеху з BMS · котли 1 200 кВт",
                    "unit": "кВт",
                    "y_max": 600,
                    "ticks": [
                        200,
                        400,
                        600
                    ],
                    "step_min": 15,
                    "now_slot": 57,
                    "series": [
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        150.0,
                        163.0,
                        176.0,
                        190.0,
                        203.0,
                        216.0,
                        228.0,
                        241.0,
                        253.0,
                        265.0,
                        277.0,
                        289.0,
                        300.0,
                        311.0,
                        321.0,
                        331.0,
                        341.0,
                        350.0,
                        359.0,
                        367.0,
                        374.0,
                        382.0,
                        388.0,
                        394.0,
                        399.0,
                        404.0,
                        408.0,
                        412.0,
                        415.0,
                        417.0,
                        419.0,
                        420.0,
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
                    "limit": null,
                    "foot": "Найбільша частка тепла — Вентиляція RV-ALL (58 %)."
                },
                "list": {
                    "title": "Куди йде тепло",
                    "basis": "rate",
                    "unit": "кВт",
                    "items": [
                        {
                            "code": "RV-ALL",
                            "name": "Вентиляція цеху",
                            "value": 228,
                            "share": 1.0,
                            "quality": "measured"
                        },
                        {
                            "code": "AHU-1",
                            "name": "Припливна установка AHU-1",
                            "value": 74,
                            "share": 0.325,
                            "quality": "measured"
                        },
                        {
                            "code": "DOCK",
                            "name": "Втрати через ворота",
                            "value": 46,
                            "share": 0.202,
                            "quality": "estimated"
                        },
                        {
                            "code": "OFFICE",
                            "name": "Офіс і побутові",
                            "value": 42,
                            "share": 0.184,
                            "quality": "estimated"
                        }
                    ],
                    "unaccounted": {
                        "value": 0.0,
                        "pct": 0.0
                    }
                },
                "notes": [
                    {
                        "id": 41,
                        "title": "Рекуперація AHU-1 нижча за норму",
                        "text": "Рекуперація 63 % при нормі 70 %; можливо, забруднено фільтр.",
                        "save_uah_month": 6054,
                        "actions": [
                            {
                                "code": "ticket",
                                "label": "Створити заявку",
                                "kind": "ticket",
                                "class": null,
                                "params": {
                                    "node_code": "COMPRESSOR",
                                    "title": "Витоки стисненого повітря",
                                    "description": "Нічна витрата вища за норму. [OPP-41]"
                                },
                                "enabled": true
                            },
                            {
                                "code": "open",
                                "label": "Відкрити",
                                "kind": "link",
                                "class": null,
                                "params": {
                                    "xmlid": "td_energy_resources.action_td_energy_opportunity",
                                    "res_id": 41
                                },
                                "enabled": true
                            }
                        ]
                    }
                ]
            }
        },
        "air": {
            "meta": {
                "now": "2026-10-17T11:20:00",
                "now_local": "14:20",
                "data_state": "ok",
                "age_s": 18,
                "refresh_s": 30,
                "control_available": false,
                "capabilities": {
                    "cost": true,
                    "export": true,
                    "manage": true
                },
                "total": {
                    "cost_uah": 65156,
                    "text": "Сьогодні разом: 65 156 ₴ · Електрика, Газ, Вода. Похідні не додаються: Тепло, Стиснене повітря."
                }
            },
            "tabs": [
                {
                    "code": "el",
                    "name": "Електрика",
                    "rate": 358,
                    "rate_unit": "кВт",
                    "cost_uah": 52786,
                    "sub": "358 кВт · 52 786 ₴"
                },
                {
                    "code": "gas",
                    "name": "Газ",
                    "rate": 46,
                    "rate_unit": "м³/год",
                    "cost_uah": 12118,
                    "sub": "46 м³/год · 12 118 ₴"
                },
                {
                    "code": "heat",
                    "name": "Тепло",
                    "rate": 390,
                    "rate_unit": "кВт",
                    "sub": "390 кВт · з BMS"
                },
                {
                    "code": "air",
                    "name": "Стиснене повітря",
                    "rate": 9.8,
                    "rate_unit": "м³/хв",
                    "cost_uah": 5393,
                    "sub": "9,8 м³/хв · 5 393 ₴"
                },
                {
                    "code": "water",
                    "name": "Вода",
                    "rate": 0.4,
                    "rate_unit": "м³/год",
                    "cost_uah": 252,
                    "sub": "0,4 м³/год · 252 ₴"
                }
            ],
            "resource": {
                "code": "air",
                "name": "Стиснене повітря",
                "color": "#0369a1",
                "kpis": [
                    {
                        "id": "rate",
                        "label": "Витрата зараз",
                        "value": 9.8,
                        "unit": "м³/хв",
                        "note": "тиск 7,1 бар · уставка 7,0",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "spec",
                        "label": "Питома потужність",
                        "value": 5.3,
                        "unit": "кВт/(м³/хв)",
                        "note": "норма ≤ 6,0",
                        "tone": "good",
                        "quality": "measured"
                    },
                    {
                        "id": "today_el",
                        "label": "Електрика компресорів сьогодні",
                        "value": 642,
                        "unit": "кВт·год",
                        "note": "5 393 ₴",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "night_leak",
                        "label": "Витоки вночі",
                        "value": 1.6,
                        "unit": "м³/хв",
                        "note": "16 % від денної витрати",
                        "tone": "bad",
                        "quality": "measured"
                    }
                ],
                "chart": {
                    "title": "Витрата стисненого повітря, м³/хв",
                    "note": "2 × Atlas Copco GA 37 VSD+",
                    "unit": "м³/хв",
                    "y_max": 12,
                    "ticks": [
                        4,
                        8,
                        12
                    ],
                    "step_min": 15,
                    "now_slot": 57,
                    "series": [
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        1.6,
                        2.0,
                        2.4,
                        2.8,
                        3.2,
                        3.6,
                        4.0,
                        4.4,
                        4.7,
                        5.1,
                        5.5,
                        5.8,
                        6.2,
                        6.5,
                        6.8,
                        7.1,
                        7.4,
                        7.7,
                        7.9,
                        8.2,
                        8.4,
                        8.6,
                        8.8,
                        9.0,
                        9.2,
                        9.3,
                        9.4,
                        9.6,
                        9.6,
                        9.7,
                        9.8,
                        9.8,
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
                    "limit": null,
                    "foot": "Вночі витрата 1,6 м³/хв — це витоки в мережі."
                },
                "list": {
                    "title": "Споживачі повітря зараз",
                    "basis": "rate",
                    "unit": "м³/хв",
                    "items": [
                        {
                            "code": "EDGE-1",
                            "name": "Крайкооблицювання A",
                            "value": 2.4,
                            "share": 1.0,
                            "quality": "estimated"
                        },
                        {
                            "code": "NEST-1",
                            "name": "Нестинг ЧПК",
                            "value": 1.8,
                            "share": 0.75,
                            "quality": "estimated"
                        },
                        {
                            "code": "PRESS-1",
                            "name": "Мембранний прес",
                            "value": 1.5,
                            "share": 0.625,
                            "quality": "estimated"
                        }
                    ],
                    "unaccounted": {
                        "value": 4.1,
                        "pct": 41.8
                    }
                },
                "notes": [
                    {
                        "id": 51,
                        "title": "Витоки стисненого повітря",
                        "text": "Нічна витрата 1,6 м³/хв — 16 % від денної.",
                        "save_uah_month": 33787,
                        "actions": [
                            {
                                "code": "ticket",
                                "label": "Створити заявку",
                                "kind": "ticket",
                                "class": null,
                                "params": {
                                    "node_code": "COMPRESSOR",
                                    "title": "Витоки стисненого повітря",
                                    "description": "Нічна витрата вища за норму. [OPP-51]"
                                },
                                "enabled": true
                            },
                            {
                                "code": "open",
                                "label": "Відкрити",
                                "kind": "link",
                                "class": null,
                                "params": {
                                    "xmlid": "td_energy_resources.action_td_energy_opportunity",
                                    "res_id": 51
                                },
                                "enabled": true
                            }
                        ]
                    }
                ]
            }
        },
        "water": {
            "meta": {
                "now": "2026-10-17T11:20:00",
                "now_local": "14:20",
                "data_state": "ok",
                "age_s": 18,
                "refresh_s": 30,
                "control_available": false,
                "capabilities": {
                    "cost": true,
                    "export": true,
                    "manage": true
                },
                "total": {
                    "cost_uah": 65156,
                    "text": "Сьогодні разом: 65 156 ₴ · Електрика, Газ, Вода. Похідні не додаються: Тепло, Стиснене повітря."
                }
            },
            "tabs": [
                {
                    "code": "el",
                    "name": "Електрика",
                    "rate": 358,
                    "rate_unit": "кВт",
                    "cost_uah": 52786,
                    "sub": "358 кВт · 52 786 ₴"
                },
                {
                    "code": "gas",
                    "name": "Газ",
                    "rate": 46,
                    "rate_unit": "м³/год",
                    "cost_uah": 12118,
                    "sub": "46 м³/год · 12 118 ₴"
                },
                {
                    "code": "heat",
                    "name": "Тепло",
                    "rate": 390,
                    "rate_unit": "кВт",
                    "sub": "390 кВт · з BMS"
                },
                {
                    "code": "air",
                    "name": "Стиснене повітря",
                    "rate": 9.8,
                    "rate_unit": "м³/хв",
                    "cost_uah": 5393,
                    "sub": "9,8 м³/хв · 5 393 ₴"
                },
                {
                    "code": "water",
                    "name": "Вода",
                    "rate": 0.4,
                    "rate_unit": "м³/год",
                    "cost_uah": 252,
                    "sub": "0,4 м³/год · 252 ₴"
                }
            ],
            "resource": {
                "code": "water",
                "name": "Вода",
                "color": "#0f766e",
                "kpis": [
                    {
                        "id": "rate",
                        "label": "Витрата зараз",
                        "value": 0.4,
                        "unit": "м³/год",
                        "note": "основний ввід",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "today",
                        "label": "Сьогодні",
                        "value": 4.2,
                        "unit": "м³",
                        "note": "252 ₴",
                        "tone": "neutral",
                        "quality": "measured"
                    },
                    {
                        "id": "night",
                        "label": "Нічна витрата",
                        "value": 0.05,
                        "unit": "м³/год",
                        "note": "норма ≤ 0,05",
                        "tone": "good",
                        "quality": "measured"
                    },
                    {
                        "id": "boiler",
                        "label": "Підживлення котельні",
                        "value": 0.3,
                        "unit": "м³",
                        "note": "норма ≤ 0,5 м³/добу",
                        "tone": "good",
                        "quality": "measured"
                    }
                ],
                "chart": {
                    "title": "Витрата води, м³/год",
                    "note": "ввід і підживлення котельні",
                    "unit": "м³/год",
                    "y_max": 0.6,
                    "ticks": [
                        0.2,
                        0.4,
                        0.6
                    ],
                    "step_min": 15,
                    "now_slot": 57,
                    "series": [
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.05,
                        0.07,
                        0.09,
                        0.1,
                        0.12,
                        0.14,
                        0.16,
                        0.17,
                        0.19,
                        0.21,
                        0.22,
                        0.24,
                        0.26,
                        0.27,
                        0.28,
                        0.3,
                        0.31,
                        0.32,
                        0.34,
                        0.35,
                        0.36,
                        0.37,
                        0.38,
                        0.38,
                        0.39,
                        0.4,
                        0.4,
                        0.41,
                        0.41,
                        0.42,
                        0.42,
                        0.42,
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
                    "limit": null,
                    "foot": "Нічна витрата 0,05 м³/год в нормі."
                },
                "list": {
                    "title": "Споживачі води",
                    "basis": "qty_day",
                    "unit": "м³",
                    "items": [
                        {
                            "code": "SOCIAL",
                            "name": "Побутові приміщення",
                            "value": 2.6,
                            "share": 1.0,
                            "quality": "estimated"
                        },
                        {
                            "code": "SPRAY-1",
                            "name": "Фарбувальна камера",
                            "value": 1.1,
                            "share": 0.423,
                            "quality": "estimated"
                        },
                        {
                            "code": "BOILER",
                            "name": "Підживлення котельні",
                            "value": 0.3,
                            "share": 0.115,
                            "quality": "measured"
                        },
                        {
                            "code": "CANTEEN",
                            "name": "Їдальня",
                            "value": 0.2,
                            "share": 0.077,
                            "quality": "estimated"
                        }
                    ],
                    "unaccounted": {
                        "value": 0.0,
                        "pct": 0.0
                    }
                },
                "notes": []
            }
        }
    },
    "API-02": {
        "description": "td.energy.opportunity.get_list(resource_code=None, states=('open',)) — контракт C-01 для W4.",
        "response": {
            "items": [
                {
                    "id": 31,
                    "code": "preheat_early",
                    "resource": "gas",
                    "title": "Розігрів перед зміною починається зарано",
                    "text": "Цех досягає 18 °C о 06:05, а зміна о 07:00. Пізніший старт на 40 хв.",
                    "save_uah_month": 6900,
                    "est_qty_month": 348.5,
                    "in_plan": true,
                    "state": "open",
                    "found_at": "2026-10-17T00:30:12",
                    "request_id": null,
                    "actions": [
                        {
                            "code": "heat_settings",
                            "label": "Відкрити налаштування опалення BMS",
                            "kind": "link",
                            "class": null,
                            "params": {
                                "xmlid": "td_bms.action_td_bms_heat_balance_open"
                            },
                            "enabled": true
                        },
                        {
                            "code": "open",
                            "label": "Відкрити",
                            "kind": "link",
                            "class": null,
                            "params": {
                                "xmlid": "td_energy_resources.action_td_energy_opportunity",
                                "res_id": 31
                            },
                            "enabled": true
                        }
                    ]
                },
                {
                    "id": 51,
                    "code": "air_leaks",
                    "resource": "air",
                    "title": "Витоки стисненого повітря",
                    "text": "Нічна витрата 1,6 м³/хв — 16 % від денної.",
                    "save_uah_month": 33787,
                    "est_qty_month": 4022.2,
                    "in_plan": false,
                    "state": "open",
                    "found_at": "2026-10-17T00:30:14",
                    "request_id": 118,
                    "actions": [
                        {
                            "code": "ticket",
                            "label": "Створити заявку",
                            "kind": "ticket",
                            "class": null,
                            "params": {
                                "node_code": "COMPRESSOR",
                                "title": "Витоки стисненого повітря",
                                "description": "Нічна витрата вища за норму. [OPP-51]"
                            },
                            "enabled": true
                        },
                        {
                            "code": "open",
                            "label": "Відкрити",
                            "kind": "link",
                            "class": null,
                            "params": {
                                "xmlid": "td_energy_resources.action_td_energy_opportunity",
                                "res_id": 51
                            },
                            "enabled": true
                        }
                    ]
                }
            ],
            "plan_sum": 6900,
            "all_sum": 40687
        }
    },
    "API-06": {
        "description": "td.energy.opportunity.get_plan_summary()",
        "response": {
            "plan_sum": 6900,
            "all_sum": 40687,
            "plan_count": 1,
            "open_count": 2
        }
    },
    "API-07": {
        "description": "GET /td/energy/resources/export?day=YYYY-MM-DD[&day_to=YYYY-MM-DD][&resources=gas,air] (auth=user)",
        "response": {
            "status": 200,
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "filename": "energoresursy_2026-10-17.xlsx",
            "sheets": {
                "Ресурси": [
                    "Ресурс",
                    "Потік",
                    "Об'єкт",
                    "Початок (Київ)",
                    "Кількість",
                    "Одиниця",
                    "Ціна, ₴",
                    "Вартість, ₴",
                    "Якість"
                ],
                "Підсумок": [
                    "Ресурс",
                    "Потік",
                    "Кількість",
                    "Одиниця",
                    "Вартість, ₴"
                ]
            },
            "cost_columns": [
                "Ціна, ₴",
                "Вартість, ₴"
            ]
        },
        "errors": {
            "400": "невірна дата / код ресурсу / діапазон > export_max_days",
            "403": "немає group_td_energy_user",
            "413": "рядків > 200 000"
        }
    },
    "API-10": {
        "description": "td.energy.res.dashboard._td_totals(day_from, day_to, resource_codes=None) — внутрішній (W4, звіти).",
        "response": [
            {
                "resource": "el",
                "qty": 6284.0,
                "kwh_eq": 6284.0,
                "cost": 52786.0,
                "co2_kg": 2325.1
            },
            {
                "resource": "gas",
                "qty": 612.0,
                "kwh_eq": 6426.0,
                "cost": 12117.6,
                "co2_kg": 1199.5
            },
            {
                "resource": "water",
                "qty": 4.2,
                "kwh_eq": 0.0,
                "cost": 252.0,
                "co2_kg": 0.0
            }
        ]
    },
    "C-01": {
        "description": "Контракт для W4 `td_energy_analytics`: td.energy.usage (SQL-view, R-07) і флаги ресурсу.",
        "usage_fields": [
            "resource_id",
            "flow",
            "ts_start",
            "day",
            "hour_local",
            "node_id",
            "point_id",
            "meter_id",
            "qty",
            "kwh_eq",
            "cost",
            "co2_kg",
            "quality",
            "is_backfill"
        ],
        "usage_flows": {
            "import": "td.energy.interval role=incomer (kwh)",
            "export": "kwh_export > 0",
            "generation": "role=generation",
            "load": "role=feeder",
            "supply": "res.interval metric=main, point.kind=source",
            "branch": "інші точки res.interval"
        },
        "resource_flags": [
            "in_energy_cost",
            "is_derived",
            "co2_kg_per_unit",
            "kwh_per_unit"
        ],
        "methods": [
            "td.energy.price._td_price_at(resource, dt_local=None) -> float",
            "td.energy.res.interval._td_backfill(days=90, until=None, seed=20261018, purge=False, resources=None) -> dict",
            "td_energy_resources.tools.shifts: shift_of, is_shift, windows_for, night_window"
        ]
    },
    "C-02": {
        "description": "Контракт дій для W2 `td_energy_control`: формат actions[] = W1 C-32; W3 не задає сценарії й команди.",
        "action": {
            "code": "air_setpoint",
            "label": "Знизити уставку тиску",
            "kind": "control",
            "class": null,
            "params": {
                "intent": "air_pressure_setpoint"
            },
            "enabled": false
        },
        "rule_control_intents": [
            "vent_night_mode",
            "air_pressure_setpoint",
            "pv_self_consumption"
        ],
        "params_intent": "дії control несуть params.intent; W2 зіставляє наміри через ADVICE_INTENT_ALIASES (W2 R-55 п. 6)",
        "unsupported_intents": {
            "heat_schedule_shift": "W2 не підтримує: правило preheat_early показує дію kind=link «Відкрити налаштування опалення BMS» (xmlid td_bms.action_td_bms_heat_balance_open), а не команду; control_intent правила порожній"
        },
        "setpoint_signal": "energy_control/air/setpoint_bar (власник W2; W3 лише читає); запасний параметр td.energy_resources.air_setpoint_bar — коли сигналу немає"
    }
};
