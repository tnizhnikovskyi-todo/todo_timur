"""Одноразовий генератор `data/chp_signals.json` (контракт C-chp-01) із карти SPEC td_chp §5.2.

Карта нижче (`MAP_TEXT`) — дослівна копія блоку §5.2; запуск: `python3 gen_chp_signals.py [шлях.json]`
(без аргументу — `../data/chp_signals.json`). Результат детермінований: рядок — сигнал `chp/<код>`; рядки з кількома
кодами розгортаються за порядком, `cyl/<id>/…` — на 16 циліндрів A1…A8, B1…B8 (адреса = база + індекс). Усі сигнали
`kind=gauge`: пульт читає числа, а `kind=state` вимагає текстових станів, яких контролер по Modbus не віддає.
Формат запису: `{code,name,unit,kind,pdu,type,scale,rw,period_s,decimals,warn_low,warn_high,alarm_low,alarm_high,
create_request,note}`; `rw` — `R|W|RW`; відсутній поріг — `null`.
"""

import json
import re
import sys
from pathlib import Path

DEFAULT_PERIOD_S = 10  # `ctl/cmd` — командний регістр без періоду в карті
CYL_IDS = [f"{row}{n}" for row in "AB" for n in range(1, 9)]

NAMES = {
    "ctl/state": "стан агрегата",
    "ctl/cmd": "команда керування",
    "ctl/ack": "результат команди",
    "ctl/ack_reason": "причина відхилення команди",
    "ctl/mode": "режим роботи",
    "ctl/sp_pct": "уставка потужності",
    "ctl/cos_set": "уставка cos φ",
    "ctl/heat_dir": "напрямок тепла",
    "ctl/bypass_mode": "режим заслінки вихлопу",
    "ctl/step": "крок пуску",
    "ctl/step_left": "залишок кроку пуску",
    "ctl/cool_left": "залишок охолодження",
    "ctl/sync_du": "синхронізація: Δ напруги",
    "ctl/sync_df": "синхронізація: Δ частоти",
    "ctl/sync_dphi": "синхронізація: Δ фази",
    "ctl/sync_ok": "синхронізація: готовність",
    "ctl/warm_skip": "підігрів ОЖ не потрібен",
    "ctl/target_pct": "ціль режиму",
    "ctl/heat_demand": "потреба котельні в теплі",
    "ctl/remote": "режим «Дистанційне» на щиті",
    "ctl/permit": "дозвіл КГУ",
    "alarm/code": "код аварії",
    "alarm/trip": "причина зупинки без аварії",
    "eng/rpm": "обороти двигуна",
    "eng/torque": "крутний момент",
    "eng/shaft_kw": "потужність на валу",
    "eng/t_jacket_out": "температура ОЖ на виході",
    "eng/t_jacket_in": "температура ОЖ на вході",
    "eng/p_oil": "тиск масла",
    "eng/t_oil": "температура масла",
    "eng/t_bearing": "температура підшипника",
    "eng/vib": "вібрація",
    "eng/tc_rpm": "обороти турбокомпресора",
    "eng/p_boost": "тиск наддуву",
    "eng/t_turb_in": "температура перед турбіною",
    "eng/t_air_in": "температура повітря на вході",
    "eng/t_air_out": "температура наддувного повітря",
    "eng/throttle": "положення дроселя",
    "eng/lambda": "коефіцієнт надлишку повітря λ",
    "eng/p_mix": "тиск суміші",
    "eng/hours": "мотогодини",
    "eng/starts": "кількість пусків",
    "eng/starter_a": "струм стартера",
    "eng/bat_v": "напруга АКБ",
    "eng/bat_a": "струм АКБ",
    "eng/starter_on": "стартер увімкнено",
    "oil/level": "рівень масла",
    "oil/t_out": "температура масла на виході",
    "oil/dp_filter": "перепад тиску на масляному фільтрі",
    "oil/cons": "витрата масла",
    "oil/fresh": "свіже масло в баку",
    "oil/waste": "відпрацьоване масло в баку",
    "oil/topup": "автодолив масла",
    "gen/p_kw": "електрична потужність",
    "gen/u_v": "напруга генератора",
    "gen/i_a": "струм генератора",
    "gen/cos": "cos φ",
    "gen/q_kvar": "реактивна потужність",
    "gen/f_hz": "частота",
    "gen/i_pct": "струм, % номіналу",
    "gen/exc_a": "струм збудження",
    "gen/exc_v": "напруга збудження",
    "gen/load_pct": "навантаження",
    "gas/flow": "витрата газу",
    "gas/p_in": "тиск газу на вході",
    "gas/p_reg": "тиск газу після регулятора",
    "gas/dp_filter": "перепад тиску на газовому фільтрі",
    "gas/yv1": "газовий клапан YV1",
    "gas/yv2": "газовий клапан YV2",
    "gas/vp_state": "перевірка герметичності клапанів",
    "gas/vp_leak": "витік при перевірці клапанів",
    "gas/vp_ts": "час останньої перевірки клапанів",
    "gas/total": "лічильник газу",
    "gas/day": "витрата газу за добу",
    "gas/psl": "датчик мінімального тиску газу",
    "gas/psh": "датчик максимального тиску газу",
    "gas/inlet_valve": "кран на вході газу",
    "ht/q_total": "теплова потужність",
    "ht/t_sup": "температура подачі",
    "ht/t_mid": "температура ВТ проміжна",
    "ht/t_ret": "температура зворотки після клапана",
    "ht/t_ret_raw": "температура зворотки до клапана",
    "ht/flow": "витрата теплоносія",
    "ht/q_phe": "тепло пластинчастого теплообмінника",
    "ht/q_exh": "тепло вихлопного теплообмінника",
    "ht/q_boiler": "тепло в котельню",
    "ht/q_cooler": "тепло в охолоджувач",
    "ht/mix_pos": "положення змішувального клапана",
    "ht/cap_pct": "обмеження потужності за теплом",
    "ht/p_loop": "тиск у контурі опалення",
    "ht/p_exp_ht": "тиск розширювального бака ВТ",
    "ht/p_exp_lt": "тиск розширювального бака НТ",
    "ht/p_exp_h": "тиск розширювального бака опалення",
    "ht/pump_ht_f": "частота насоса ВТ",
    "ht/pump_he_f": "частота насоса опалення",
    "ht/pump_ht_a": "струм насоса ВТ",
    "ht/pump_he_a": "струм насоса опалення",
    "ht/p_dis_ht": "тиск нагнітання насоса ВТ",
    "ht/cooler_fan": "вентилятор охолоджувача",
    "ht/t_cool_out": "температура після охолоджувача",
    "ht/flow_cool": "витрата через охолоджувач",
    "ht/heat_total": "лічильник тепла",
    "ht/heat_day": "тепло за добу",
    "ht/pump_ht_run": "насос ВТ працює",
    "ht/pump_he_run": "насос опалення працює",
    "lt/q_kw": "теплова потужність НТ",
    "lt/flow": "витрата НТ",
    "lt/t_in": "температура НТ на вході",
    "lt/t_out": "температура НТ на виході",
    "lt/fan": "вентилятор НТ",
    "lt/pump_f": "частота насоса НТ",
    "lt/pump_a": "струм насоса НТ",
    "lt/p_dis": "тиск нагнітання насоса НТ",
    "lt/pump_run": "насос НТ працює",
    "exh/t_e1": "температура вихлопу після турбіни",
    "exh/t_cat_out": "температура після каталізатора",
    "exh/t_e2": "температура вихлопу після теплообмінника",
    "exh/t_stack": "температура вихлопу в трубі",
    "exh/dp_cat": "перепад тиску на каталізаторі",
    "exh/nox": "викиди NOx",
    "exh/co": "викиди CO",
    "exh/co_raw": "CO до каталізатора",
    "exh/o2": "вміст O₂ у вихлопі",
    "exh/bypass_pct": "положення заслінки вихлопу",
    "exh/back_p": "протитиск вихлопу",
    "air/dp_filter": "перепад тиску на повітряному фільтрі",
    "air/t_cont": "температура в контейнері",
    "air/fan_sup": "вентилятор припливу",
    "air/fan_exh": "вентилятор витяжки",
    "air/louver": "жалюзі",
    "air/t_amb": "температура зовнішнього повітря",
    "safe/lel": "загазованість",
    "safe/fire": "пожежна сигналізація",
    "safe/ext_state": "стан гасіння",
    "safe/ext_level": "рівень засобу гасіння",
    "safe/estop_loop": "контур аварійного стопу",
    "safe/rocof": "захист ROCOF",
    "safe/rocof_dfdt": "ROCOF: df/dt",
    "safe/rocof_dphi": "ROCOF: векторний зсув",
    "safe/grid_ok": "мережа S2",
    "safe/u_grid": "напруга мережі",
    "safe/qf_closed": "вимикач QF-CHP",
    "safe/ctrl_v": "живлення контролера",
    "safe/es_cab": "аварійний стоп: шафа",
    "safe/es_door": "аварійний стоп: двері",
    "safe/es_ext": "аварійний стоп: зовнішня кнопка",
    "em/kwh": "лічильник електроенергії",
    "em/kvarh": "лічильник реактивної енергії",
    "em/kwh_day": "виробіток за добу",
    "em/runh_day": "наробіток за добу",
}
CYL_NAMES = {
    "t": "температура",
    "knock": "детонація",
    "kv": "напруга пробою",
    "ms": "тривалість іскри",
    "plug_h": "наробіток свічки",
}

MAP_TEXT = """\
# ctl — стан і керування
ctl/state|40000|u16|1|||2||S.state: 0 резерв,1 пуск,2 робота,3 аварія,4 охолодження (= infra/chp/state)
ctl/cmd|40900|u16|1||W|||1 пуск,2 стоп,3 аварійний стоп,4 скидання аварії; пристрій очищає після виконання
ctl/ack|40901|u16|1|||2||0 немає результату (скидається при новій cmd),1 прийнято,2 відхилено
ctl/ack_reason|40902|u16|1|||2||причина відхилення (R-06)
ctl/mode|40903|u16|1||RW|2||S.mode: 0 heat,1 el,2 peak,3 manual,4 профіль макета (лише емулятор,D-11)
ctl/sp_pct|40904|u16|1|%|RW|2||S.setpoint 50…100
ctl/cos_set|40905|u16|0,01||RW|2||S.cosSet 0,90…1,00
ctl/heat_dir|40906|u16|1||RW|2||S.heatDir: 0 auto,1 boiler,2 cooler
ctl/bypass_mode|40907|u16|1||RW|2||S.bypassMode: 0 auto,1 ht,2 bypass
ctl/step|40908|u16|1|||2||S.stepI+1; 0 — не пуск; 1…9 (R-13)
ctl/step_left|40909|u16|0,1|с||2||залишок кроку (stepDur−stepT)
ctl/cool_left|40910|u16|1|с||2||S.coolLeft
ctl/sync_du|40911|i16|0,1|%||2||S.sync.du
ctl/sync_df|40912|i16|0,01|Гц||2||S.sync.df
ctl/sync_dphi|40913|i16|1|°||2||S.sync.dp
ctl/sync_ok|40914|u16|1|||2||прапор S.sync.ok
ctl/warm_skip|40915|u16|1|||2||прапор S.warmSkip
ctl/target_pct|40917|u16|0,1|%||2||ціль режиму (modeTarget()·100)
ctl/heat_demand|40918|u16|1|кВт||10||V.demand — потреба котельні
ctl/remote|40930|u16|1|||2||S.remote,прапор: «Дистанційне» на щиті
ctl/permit|40931|u16|1|||2||S.permit,прапор: дозвіл КГУ
alarm/code|40920|u16|1|||2|A≥1 ✓з|S.alarm: 0,111 тиск газу,112 перегрів ОЖ,113 зворотка,114 загазованість,115 пожежа,116 аварійний стоп
alarm/trip|40921|u16|1|||2||остання причина зупинки без аварії: 0,1 зникла мережа S2,2 ROCOF,3 знято дозвіл
# eng — двигун,турбіна,пуск
eng/rpm|40100|u16|1|об/хв||2||V.rpm
eng/torque|40101|u16|0,01|кН·м||5||V.torque
eng/shaft_kw|40102|u16|1|кВт||5||V.pShaft
eng/t_jacket_out|40103|i16|0,1|°C||2|W≥92 A≥95 ✓з|V.tJo
eng/t_jacket_in|40104|i16|0,1|°C||5||V.tJi
eng/p_oil|40105|u16|0,01|бар||2||V.pOil
eng/t_oil|40106|i16|0,1|°C||5||V.tOil
eng/t_bearing|40107|i16|0,1|°C||5||V.tBrg
eng/vib|40108|u16|0,01|мм/с||5||V.vib
eng/tc_rpm|40109|u16|10|об/хв||5||V.tcRpm
eng/p_boost|40110|u16|0,01|бар||5||V.pBoost
eng/t_turb_in|40111|i16|0,1|°C||5||V.tTurb
eng/t_air_in|40112|i16|0,1|°C||5||V.tAirIn
eng/t_air_out|40113|i16|0,1|°C||5||V.tAirOut
eng/throttle|40114|u16|0,1|%||5||V.thr
eng/lambda|40115|u16|0,001|||5||V.lambda
eng/p_mix|40116|u16|0,01|бар||5||V.pMix
eng/hours|40120|u32|0,1|год||60||S.hours (мотогодини; ТО M-04)
eng/starts|40122|u32|1|||60||S.starts
eng/starter_a|40124|u16|1|А||2||V.starterI
eng/bat_v|40125|u16|0,1|В||5|W≤24,5 A≤23,5|V.batV
eng/bat_a|40126|u16|0,1|А||5||V.batI
eng/starter_on|40127|u16|1|||2||прапор S.starter
# oil — масло
oil/level|40130|u16|0,1|%||5|W≤60 A≤45 ✓з|V.oilLvl
oil/t_out|40131|i16|0,1|°C||5||V.tOilOut
oil/dp_filter|40132|u16|0,01|бар||5||V.dpOilF
oil/cons|40133|u16|0,01|г/кВт·год||10||V.oilCons
oil/fresh|40134|u16|0,1|%||10|W≤20|V.oilFresh
oil/waste|40135|u16|0,1|%||10|W≥80|V.oilWaste
oil/topup|40136|u16|1|||5||прапор S.topup
# gen — генератор,АРН
gen/p_kw|40001|u16|1|кВт||2||V.pel (= infra/totals/chp_kw)
gen/u_v|40140|u16|0,1|В||2||V.U
gen/i_a|40141|u16|1|А||2||V.I
gen/cos|40142|u16|0,001|||2||V.cos
gen/q_kvar|40143|i16|1|квар||2||V.Q
gen/f_hz|40144|u16|0,01|Гц||2||V.f
gen/i_pct|40145|u16|0,1|%||5|W≥105|V.Ipct
gen/exc_a|40146|u16|0,1|А||5||V.excI
gen/exc_v|40147|u16|1|В||5||V.excU
gen/load_pct|40148|u16|0,1|%||2||S.load·100
# gas — газова рампа
gas/flow|40003|u16|0,1|м³/год||2||V.gas (= infra/chp/gas_m3h)
gas/p_in|40200|u16|0,01|бар||2|W≤1,7 A≤1,5 ✓з|V.gasP
gas/p_reg|40201|u16|1|мбар||5||V.gasReg
gas/dp_filter|40202|u16|1|мбар||5||V.dpFilter
gas/yv1,gas/yv2|40203,40204|u16|1|||2||S.valves: 0 закрито,1 відкрито,2 тест
gas/vp_state|40205|u16|1|||2||S.vp.st: 0 —,1 виконується,2 успішно,3 витік
gas/vp_leak|40206|u16|0,1|мбар/хв||5||витік valve proving
gas/vp_ts|40207|u32|1|с (Unix UTC)||10||S.vp.time; 0 — немає
gas/total|40210|u32|1|м³||60||S.gasTotal
gas/day|40212|u32|1|м³||60||S.gDay
gas/psl,gas/psh,gas/inlet_valve|40214,40215,40216|u16|1|||5||прапори: датчик min (1 — спрацював),max,кран (1 — відкрито)
# ht — тепло ВТ,опалення
ht/q_total|40002|u16|1|кВт||2||V.qth (= infra/chp/heat_kw)
ht/t_sup|40300|i16|0,1|°C||2||V.tSup
ht/t_mid|40301|i16|0,1|°C||5||V.tMid
ht/t_ret|40302|i16|0,1|°C||2|W≥66 A≥70 ✓з|V.tRet (на вході ТО,після клапана)
ht/t_ret_raw|40303|i16|0,1|°C||2|W≥65 A≥75|V.tRetRaw (до клапана)
ht/flow|40304|u16|0,1|м³/год||5||V.flow
ht/q_phe,ht/q_exh|40305,40306|u16|1|кВт||5||V.qPhe,V.qExh
ht/q_boiler,ht/q_cooler|40307,40308|u16|1|кВт||5||V.qBoiler,V.qCooler
ht/mix_pos|40309|u16|0,1|%||5||V.mixPos
ht/cap_pct|40310|u16|0,1|%||5|W≤99,5|V.cap ·100,обмеження потужності
ht/p_loop|40311|u16|0,01|бар||10||V.pLoop
ht/p_exp_ht,ht/p_exp_lt,ht/p_exp_h|40312,40313,40314|u16|0,01|бар||10||V.pExpHT/pExpLT/pExpH
ht/pump_ht_f,ht/pump_he_f|40315,40317|u16|0,1|Гц||5||V.pHT.f,V.pHe.f
ht/pump_ht_a,ht/pump_he_a|40316,40318|u16|0,1|А||5||V.pHT.I,V.pHe.I
ht/p_dis_ht|40319|u16|0,01|бар||10||V.pDisHT
ht/cooler_fan|40320|u16|0,1|%||5||V.fan
ht/t_cool_out|40321|i16|0,1|°C||5||V.tCoolOut
ht/flow_cool|40322|u16|0,1|м³/год||5||V.flowC
ht/heat_total|40324|u32|0,1|Гкал||60||V.hmTot
ht/heat_day|40326|u32|0,01|Гкал||60||S.qDay
ht/pump_ht_run,ht/pump_he_run|40328,40329|u16|1|||2||прапори V.pHT.run,V.pHe.run
# lt — тепло НТ
lt/q_kw|40400|u16|1|кВт||5||V.qLT
lt/flow|40401|u16|0,1|м³/год||5||V.flowLT
lt/t_in,lt/t_out|40402,40403|i16|0,1|°C||5||V.tLTin,V.tLTout
lt/fan|40404|u16|0,1|%||5||V.fanLT
lt/pump_f|40405|u16|0,1|Гц||5||V.pLT.f
lt/pump_a|40406|u16|0,1|А||5||V.pLT.I
lt/p_dis|40407|u16|0,01|бар||10||V.pDisLT
lt/pump_run|40408|u16|1|||2||прапор V.pLT.run
# exh — вихлоп і викиди
exh/t_e1|40500|i16|0,1|°C||5||V.tE1 (після турбіни,до каталізатора)
exh/t_cat_out|40501|i16|0,1|°C||5||V.tCatOut
exh/t_e2|40502|i16|0,1|°C||5||V.tE2
exh/t_stack|40503|i16|0,1|°C||5||V.tStack
exh/dp_cat|40504|u16|0,1|мбар||10|W≥18|V.dpCat
exh/nox|40505|u16|1|мг/нм³||10|W≥225 A≥250|V.nox
exh/co|40506|u16|1|мг/нм³||10|W≥270 A≥300|V.co
exh/co_raw|40507|u16|1|мг/нм³||10||V.coRaw
exh/o2|40508|u16|0,01|%||10||V.o2
exh/bypass_pct|40509|u16|0,1|%||5||V.bypass·100
exh/back_p|40510|u16|1|мбар||10||протитиск (b_sim.js:620)
# air — повітря,контейнер
air/dp_filter|40600|u16|0,1|мбар||10|W≥12 A≥15|V.airDp
air/t_cont|40601|i16|0,1|°C||5|W≥38 A≥45|V.tCont
air/fan_sup,air/fan_exh|40602,40603|u16|0,1|%||5||V.fanSup,V.fanExh
air/louver|40604|u16|0,1|%||5||V.louver
air/t_amb|40605|i16|0,1|°C||10||S.tAmb
# safe — безпека,мережа
safe/lel|40610|u16|0,1|% НКПР||2|W≥10 A≥20 ✓з|V.lel
safe/fire|40611|u16|1|||2||прапор S.fire
safe/ext_state|40612|u16|1|||2||S.ext: 0 готове,1 випуск,2 спрацювало
safe/ext_level|40613|u16|1|%||10||S.extLevel
safe/estop_loop|40614|u16|1|||2||S.estopLoop: 1 замкнений
safe/rocof|40615|u16|1|||2||прапор S.rocofFlag
safe/rocof_dfdt|40616|u16|0,01|Гц/с||5||df/dt (b_sim.js:659)
safe/rocof_dphi|40617|u16|0,1|°||5||векторний зсув
safe/grid_ok|40618|u16|1|||2||S.grid: 1 мережа S2 наявна
safe/u_grid|40619|u16|0,1|В||5||U мережі
safe/qf_closed|40620|u16|1|||2||S.qf: 1 QF-CHP увімкнено
safe/ctrl_v|40621|u16|0,1|В||10||живлення контролера
safe/es_cab,safe/es_door,safe/es_ext|40622,40623,40624|u16|1|||2||кнопки аварійного стопу: 1 натиснута
# em — лічильник TEDOM-1,добові
em/kwh|40700|u32|1|кВт·год||60||V.eTot
em/kvarh|40702|u32|1|квар·год||60||V.eRe
em/kwh_day|40704|u32|0,1|кВт·год||60||S.eDay
em/runh_day|40706|u16|0,01|год||60||S.runDay
# cyl — 16 циліндрів** (`<id>` = A1…A8,B1…B8; індекс `i` = 0…15 за порядком)
cyl/<id>/t|40800+i|i16|0,1|°C||10||V.cyl[i].t
cyl/<id>/knock|40816+i|u16|1|од.||10|W≥35 A≥60|.knock
cyl/<id>/kv|40832+i|u16|0,1|кВ||10|W≥29|.kv (пробій)
cyl/<id>/ms|40848+i|u16|0,01|мс||10||.ms (іскра)
cyl/<id>/plug_h|40864+i|u16|1|год||60|W≥3200 A≥3800|.plug (наробіток свічки)
"""


def _num(text):
    return float(text.strip().replace(",", "."))


def _decimals(scale):
    text = f"{scale:.6f}".rstrip("0")
    return len(text.split(".")[1]) if "." in text else 0


def _thresholds(text):
    """`W≥92 A≥95 ✓з` → ({warn_low, warn_high, alarm_low, alarm_high}, create_request)."""
    res = dict.fromkeys(("warn_low", "warn_high", "alarm_low", "alarm_high"), None)
    create_request = False
    for token in text.split():
        if token == "✓з":
            create_request = True
            continue
        m = re.fullmatch(r"([WA])([≥≤])(-?[\d,\.]+)", token)
        if not m:
            raise ValueError(f"пороги: незрозумілий токен «{token}»")
        level = "warn" if m.group(1) == "W" else "alarm"
        side = "high" if m.group(2) == "≥" else "low"
        res[f"{level}_{side}"] = _num(m.group(3))
    return res, create_request


def _notes(mock, count):
    parts = [p.strip() for p in mock.split(",")]
    if count > 1 and len(parts) == count and all(re.match(r"^[VS]\.", p) for p in parts):
        return parts
    return [mock.strip()] * count


def parse(map_text):
    rows = []
    for line in map_text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("|")
        if len(f) != 9:
            raise ValueError(f"очікується 9 полів, отримано {len(f)}: {line}")
        codes, pdu, typ, scale, unit, rw, period, thr, mock = (x.strip() for x in f)
        scale_v = _num(scale)
        thr_v, create_request = _thresholds(thr)
        if codes.startswith("cyl/<id>/"):
            metric = codes[len("cyl/<id>/") :]
            base = int(pdu.split("+")[0])
            items = [
                (f"cyl/{cid}/{metric}", base + i, f"циліндр {cid}, {CYL_NAMES[metric]}")
                for i, cid in enumerate(CYL_IDS)
            ]
            notes = [mock.strip()] * len(items)
        else:
            code_list = codes.split(",")
            pdu_list = [int(p) for p in pdu.split(",")]
            if len(code_list) != len(pdu_list):
                raise ValueError(f"кількість кодів і адрес не збігається: {line}")
            items = [(c, a, NAMES[c]) for c, a in zip(code_list, pdu_list, strict=True)]
            notes = _notes(mock, len(items))
        for (code, addr, name), note in zip(items, notes, strict=True):
            rows.append(
                {
                    "code": f"chp/{code}",
                    "name": f"КГУ: {name}",
                    "unit": unit,
                    "kind": "gauge",
                    "pdu": addr,
                    "type": typ,
                    "scale": scale_v,
                    "rw": rw or "R",
                    "period_s": int(period or DEFAULT_PERIOD_S),
                    "decimals": _decimals(scale_v),
                    **thr_v,
                    "create_request": create_request,
                    "note": note,
                }
            )
    return rows


def build():
    rows = parse(MAP_TEXT)
    codes = [r["code"] for r in rows]
    if len(set(codes)) != len(codes) or len(rows) != 230:
        raise ValueError(f"очікується 230 унікальних сигналів, отримано {len(rows)} / {len(set(codes))}")
    return json.dumps(rows, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "chp_signals.json"
    )
    target.write_text(build(), encoding="utf-8")
    print(f"{target}: 230 сигналів")
