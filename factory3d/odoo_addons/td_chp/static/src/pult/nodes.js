/** @odoo-module **/
// UI-05 `nodes.js`: 37 вузлів у 8 системах, `nodeActive`, `nodeBadge`, `S.hl` (R-05). Порт `b_sim.js:455–707`:
// значення беруться зі `store` (S, V, K, th), а не з моделі мокапу.

import { fmt, hms } from "./util";

export const SYS = [
    ["all", "Усі"],
    ["eng", "Двигун"],
    ["gas", "Газ"],
    ["ht", "Тепло ВТ"],
    ["lt", "Тепло НТ"],
    ["exh", "Вихлоп"],
    ["air", "Повітря"],
    ["el", "Електрика"],
    ["safe", "Безпека"],
];
export const LHV_DEFAULT = 9.5;

export const curStepId = (S) => (S.state === 1 && S.stepI >= 0 && S.stepI < STEP_IDS.length ? STEP_IDS[S.stepI] : "");
export const STEP_IDS = ["vent", "warm", "lube", "proving", "crank", "ign", "idle", "sync", "load"];

/** Вузли мапляться на `store` (S, V, th, to): `makeNodes(store)` → {NODES, NODE_ORDER, nodeActive, nodeBadge, valveTxt, vpTxt}. */
export function makeNodes(store) {
    const S = store.S;
    const V = store.V;
    const th = () => store.th;
    const toLeft = (frag) => store.toLeft(frag);
    const toSince = (frag) => store.toSince(frag);
    const stat=(txt,cls)=>[txt,cls||''];
    const runTxt=on=>on?['Працює','ok']:['Зупинено',''];
    function valveTxt(){
      if(S.valves) return ['Відкрито','ok'];
      if(curStepId(S)==='proving') return ['Тест','warn'];
      return ['Закрито',''];
    }
    function vpTxt(){ return S.vp.st==='ok'?['Успішно','ok']:(S.vp.st==='run'?['Виконується','warn']:(S.vp.st==='leak'?['Витік','alarm']:['—',''])); }
    const NODES={
      engine:{sys:'eng',name:'Двигун ГПД',chip:'Двигун',sub:'Газопоршневий V16, 1500 об/хв',rows:[
        ['Частота обертання',()=>fmt(V.rpm,0),'об/хв'],
        ['Тиск масла',()=>fmt(V.pOil,1),'бар'],
        ['t ОЖ (вихід)',()=>[fmt(V.tJo,1),V.tJo>=th().jacket_max_c?'alarm':V.tJo>=th().jacket_warn_c?'warn':''],'°C'],
        ['t ОЖ (вхід)',()=>fmt(V.tJi,1),'°C'],
        ['t масла',()=>fmt(V.tOil,1),'°C'],
        ['Потужність на валу',()=>fmt(V.pShaft,0),'кВт'],
        ['Моточаси',()=>fmt(S.hours,1),'год']]},
      flywheel:{sys:'eng',name:'Маховик / муфта',chip:'Маховик',sub:'Пружна муфта між двигуном і генератором',rows:[
        ['Частота обертання',()=>fmt(V.rpm,0),'об/хв'],
        ['Крутний момент',()=>fmt(V.torque,2),'кН·м'],
        ['t підшипника',()=>fmt(V.tBrg,1),'°C'],
        ['Вібрація',()=>fmt(V.vib,1),'мм/с']]},
      turbo:{sys:'eng',name:'Турбокомпресор',chip:'Турбокомпресор',sub:'Турбіна на вихлопі + компресор повітря',rows:[
        ['Обороти ротора',()=>fmt(V.tcRpm,0),'об/хв'],
        ['p наддуву (абс.)',()=>fmt(V.pBoost,2),'бар'],
        ['t газів перед турбіною',()=>fmt(V.tTurb,0),'°C'],
        ['t газів після турбіни',()=>fmt(V.tE1,0),'°C'],
        ['t повітря після компресора',()=>fmt(V.tAirIn,0),'°C']]},
      oil:{sys:'eng',name:'Маслосистема',chip:'Масло: картер',sub:'Картер, насос, маслоохолоджувач, фільтр',rows:[
        ['Рівень у картері',()=>[fmt(V.oilLvl,1),V.oilLvl<45?'alarm':V.oilLvl<60?'warn':''],'%'],
        ['Тиск масла',()=>fmt(V.pOil,1),'бар'],
        ['t масла до охолоджувача',()=>fmt(V.tOil,1),'°C'],
        ['t масла після',()=>fmt(V.tOilOut,1),'°C'],
        ['ΔP масляного фільтра',()=>fmt(V.dpOilF,2),'бар'],
        ['Витрата масла',()=>fmt(V.oilCons,2),'г/кВт·год'],
        ['Автодолив',()=>S.topup?['Працює','warn']:['Очікування','']]]},
      oiltanks:{sys:'eng',name:'Баки масла й автодолив',chip:'Баки масла',sub:'Свіже й відпрацьоване масло',rows:[
        ['Свіже масло, рівень',()=>[fmt(V.oilFresh,1),V.oilFresh<20?'warn':''],'%'],
        ['Відпрацьоване, рівень',()=>[fmt(V.oilWaste,1),V.oilWaste>80?'warn':''],'%'],
        ['Клапан автодоливу',()=>S.topup?['Відкрито','warn']:['Закрито','']],
        ['Картер, рівень',()=>fmt(V.oilLvl,1),'%'],
        ['До заміни масла',()=>fmt(toLeft('масл'),0),'год']]},
      starter:{sys:'eng',name:'Стартер',chip:'Стартер',sub:'Електростартер 24 В',rows:[
        ['Стан',()=>S.starter?['Прокрутка','warn']:['Очікування','']],
        ['Струм стартера',()=>fmt(V.starterI,0),'А'],
        ['Напруга АКБ',()=>fmt(V.batV,1),'В'],
        ['Кількість пусків',()=>fmt(S.starts,0),'']]},
      battery:{sys:'eng',name:'АКБ 24 В і зарядний пристрій',chip:'АКБ / ЗП',sub:'2 × 12 В, буферний заряд',rows:[
        ['Напруга АКБ',()=>[fmt(V.batV,1),V.batV<th().bat_min_v?'alarm':V.batV<th().bat_min_v+1?'warn':''],'В'],
        ['Струм зарядного',()=>fmt(V.batI,1),'А'],
        ['Режим ЗП',()=>S.starter?['Розряд','warn']:(V.batI>6?['Заряд','warn']:['Буфер','ok'])],
        ['Ємність АКБ',()=>fmt(100,0),'А·год']]},
      gasramp:{sys:'gas',name:'Газова рампа',chip:'Газова рампа',sub:'Кран, фільтр, регулятор, датчики мін./макс.',rows:[
        ['Кран на вході',()=>S.inletValve?['Відкрито','ok']:['Закрито','warn']],
        ['p на вході',()=>[fmt(V.gasP,2),V.gasP<th().gas_min_bar?'alarm':V.gasP<th().gas_warn_bar?'warn':''],'бар'],
        ['ΔP газового фільтра',()=>fmt(V.dpFilter,0),'мбар'],
        ['p після регулятора',()=>fmt(V.gasReg,0),'мбар'],
        ['Датчик min (PSL)',()=>S.psl?['Спрацював','alarm']:['Норма','ok']],
        ['Датчик max (PSH)',()=>S.psh?['Спрацював','alarm']:['Норма','ok']]]},
      yv:{sys:'gas',name:'Клапани YV1/YV2, valve proving',chip:'Клапани YV1/YV2',sub:'Два електромагнітні клапани + контроль герметичності',rows:[
        ['Клапан YV1',()=>valveTxt()],
        ['Клапан YV2',()=>valveTxt()],
        ['Valve proving',()=>vpTxt()],
        ['Остання перевірка',()=>S.vp.time?hms(S.vp.time):'—'],
        ['Витік між клапанами',()=>fmt(V.vpLeak,1),'мбар/хв']]},
      gasmeter:{sys:'gas',name:'Лічильник газу',chip:'Лічильник газу',sub:'Обʼємний, з коректором',rows:[
        ['Витрата',()=>fmt(V.gas,1),'м³/год'],
        ['Лічильник',()=>fmt(S.gasTotal,0),'м³'],
        ['За добу',()=>fmt(S.gDay,0),'м³'],
        ['Теплота згоряння (LHV)',()=>fmt(th().lhv_kwh_m3,1),'кВт·год/м³']]},
      mixer:{sys:'gas',name:'Змішувач / дросель',chip:'Змішувач',sub:'Газ + повітря, дросельна заслінка',rows:[
        ['Положення дроселя',()=>fmt(V.thr,0),'%'],
        ['Коефіцієнт надлишку повітря λ',()=>fmt(V.lambda,2),''],
        ['p суміші після охолодження',()=>fmt(V.pMix,2),'бар']]},
      phe:{sys:'ht',name:'Пластинчастий ТО',chip:'Пластинч. ТО',sub:'ОЖ двигуна ВТ → мережевий контур',rows:[
        ['ОЖ: вхід / вихід (замкнений)',()=>fmt(V.tJo,0)+' / '+fmt(V.tJi,0),'°C'],
        ['Мережа вхід (зворотка)',()=>fmt(V.tRet,1),'°C'],
        ['Мережа вихід (проміжна)',()=>fmt(V.tMid,1),'°C'],
        ['ΔT ступеня',()=>fmt(V.tMid-V.tRet,1),'К'],
        ['Витрата',()=>fmt(V.flow,1),'м³/год'],
        ['Q',()=>fmt(V.qPhe,0),'кВт']]},
      pumpHT:{sys:'ht',name:'Насос ВТ-контура двигуна',chip:'Насос ВТ',sub:'Циркуляція ОЖ двигуна (~90/80 °C)',rows:[
        ['Стан',()=>runTxt(V.pHT.run)],
        ['Частота',()=>fmt(V.pHT.f,1),'Гц'],
        ['Струм',()=>fmt(V.pHT.I,1),'А'],
        ['Тиск нагнітання',()=>fmt(V.pDisHT,2),'бар'],
        ['Тиск у контурі ВТ',()=>fmt(V.pExpHT,2),'бар']]},
      pumpHeat:{sys:'ht',name:'Насос контуру опалення',chip:'Насос опалення',sub:'Мережевий контур до котельні',rows:[
        ['Стан',()=>runTxt(V.pHe.run)],
        ['Частота',()=>fmt(V.pHe.f,1),'Гц'],
        ['Струм',()=>fmt(V.pHe.I,1),'А'],
        ['Витрата',()=>fmt(V.flow,1),'м³/год'],
        ['Тиск у контурі',()=>fmt(V.flow>0?V.pLoop:0,2),'бар']]},
      mixv:{sys:'ht',name:'Трьоххідний змішувальний клапан',chip:'Змішувальний клапан',sub:'Захист зворотки: уставка ≤ 70 °C',rows:[
        ['Положення (на градирню)',()=>fmt(V.mixPos,0),'%'],
        ['t зворотки до клапана',()=>[fmt(V.tRetRaw,1),V.tRetRaw>75?'alarm':V.tRetRaw>65?'warn':''],'°C'],
        ['t зворотки на вході ТО',()=>[fmt(V.tRet,1),V.tRet>th().ret_set_c?'alarm':V.tRet>th().ret_set_c-4?'warn':''],'°C'],
        ['Уставка',()=>'≤ '+fmt(th().ret_set_c,0),'°C'],
        ['Обмеження потужності',()=>V.cap<0.995?[fmt(V.cap*100,0),'warn']:['немає',''],V.cap<0.995?'%':'']]},
      exp:{sys:'ht',name:'Розширювальні баки',chip:'Розш. баки',sub:'ВТ, НТ і опалення',rows:[
        ['Бак ВТ',()=>fmt(V.pExpHT,2),'бар'],
        ['Бак НТ',()=>fmt(V.pExpLT,2),'бар'],
        ['Бак опалення',()=>fmt(V.pExpH,2),'бар'],
        ['Стан',()=>['Норма','ok']]]},
      loop:{sys:'ht',name:'Контур тепла',chip:'Контур тепла',sub:'Подача/зворотка до котельні',rows:[
        ['t подачі (після ТО вихлопу)',()=>fmt(V.tSup,1),'°C'],
        ['t проміжна (між ТО)',()=>fmt(V.tMid,1),'°C'],
        ['t зворотки',()=>fmt(V.tRet,1),'°C'],
        ['ΔT',()=>fmt(V.dT,1),'К'],
        ['Витрата',()=>fmt(V.flow,1),'м³/год'],
        ['У котельню',()=>fmt(V.qBoiler,0),'кВт'],
        ['На градирню ВТ',()=>fmt(V.qCooler,0),'кВт']]},
      heatmeter:{sys:'ht',name:'Тепловий лічильник',chip:'Лічильник тепла',sub:'Ультразвуковий, на контурі опалення',rows:[
        ['Теплова потужність',()=>fmt(V.hmP,0),'кВт'],
        ['Витрата',()=>fmt(V.hmFlow,1),'м³/год'],
        ['Подача / зворотка',()=>fmt(V.tSup,0)+' / '+fmt(V.tRet,0),'°C'],
        ['Вироблено тепла',()=>fmt(V.hmTot,1),'Гкал'],
        ['Сьогодні',()=>fmt(S.qDay,2),'Гкал']]},
      cooler:{sys:'ht',name:'Сухі градирні ВТ',chip:'Градирні ВТ',sub:'На відгалуженні зворотки (через клапан), на даху',rows:[
        ['Вентилятори',()=>fmt(V.fan,0),'%'],
        ['Q скидання',()=>fmt(V.qCooler,0),'кВт'],
        ['t вхід (зворотка до клапана)',()=>V.qCooler>3?fmt(V.tRetRaw,1):'—','°C'],
        ['t вихід (в пластинчастий ТО)',()=>V.qCooler>3?fmt(V.tCoolOut,1):'—','°C'],
        ['Витрата',()=>fmt(V.flowC,1),'м³/год'],
        ['t повітря',()=>fmt(S.tAmb,1),'°C']]},
      intercooler:{sys:'lt',name:'Охолоджувач суміші (інтеркулер)',chip:'Інтеркулер',sub:'Повітря після компресора → НТ-вода',rows:[
        ['t повітря до охолодження',()=>fmt(V.tAirIn,0),'°C'],
        ['t суміші після',()=>fmt(V.tAirOut,0),'°C'],
        ['t НТ вхід / вихід',()=>fmt(V.tLTin,0)+' / '+fmt(V.tLTout,0),'°C'],
        ['Q НТ',()=>fmt(V.qLT,0),'кВт'],
        ['Витрата НТ',()=>fmt(V.flowLT,1),'м³/год']]},
      pumpLT:{sys:'lt',name:'Насос НТ-контура',chip:'Насос НТ',sub:'Низькотемпературний контур ~40/45 °C',rows:[
        ['Стан',()=>runTxt(V.pLT.run)],
        ['Частота',()=>fmt(V.pLT.f,1),'Гц'],
        ['Струм',()=>fmt(V.pLT.I,1),'А'],
        ['Тиск нагнітання',()=>fmt(V.pDisLT,2),'бар'],
        ['Тиск у контурі НТ',()=>fmt(V.pExpLT,2),'бар']]},
      coolerLT:{sys:'lt',name:'Сухa градирня НТ',chip:'Градирня НТ',sub:'Окремо від ВТ, на даху',rows:[
        ['Вентилятори',()=>fmt(V.fanLT,0),'%'],
        ['Q скидання',()=>fmt(V.qLT,0),'кВт'],
        ['t вхід / вихід',()=>fmt(V.tLTout,1)+' / '+fmt(V.tLTin,1),'°C'],
        ['Витрата',()=>fmt(V.flowLT,1),'м³/год'],
        ['t повітря',()=>fmt(S.tAmb,1),'°C']]},
      cat:{sys:'exh',name:'Окислювальний каталізатор',chip:'Каталізатор',sub:'Окислення CO і CxHy; SCR немає',rows:[
        ['t до каталізатора',()=>fmt(V.tE1,0),'°C'],
        ['t після каталізатора',()=>fmt(V.tCatOut,0),'°C'],
        ['ΔP',()=>[fmt(V.dpCat,1),V.dpCat>18?'warn':''],'мбар'],
        ['CO до / після',()=>V.co>0?fmt(V.coRaw,0)+' / '+fmt(V.co,0):'—','мг/нм³']]},
      bypass:{sys:'exh',name:'Байпасна заслінка вихлопу',chip:'Заслінка вихлопу',sub:'На ТО вихлопних газів / в обхід',rows:[
        ['Положення',()=>V.bypass>0.9?['В обхід','warn']:(V.bypass<0.1?['На ТО','ok']:['Перехід','warn'])],
        ['Привід',()=>fmt(V.bypass*100,0),'%'],
        ['Режим',()=>S.bypassMode==='auto'?'Авто':(S.bypassMode==='ht'?'На ТО':'В обхід')]]},
      exhhe:{sys:'exh',name:'ТО вихлопних газів',chip:'ТО вихлопу',sub:'Кожухотрубний, догрів води',rows:[
        ['Гази: вхід (після катал.)',()=>fmt(V.tCatOut,0),'°C'],
        ['Гази: вихід',()=>fmt(V.tE2,0),'°C'],
        ['Мережа вхід (проміжна)',()=>fmt(V.tMid,1),'°C'],
        ['Мережа вихід (подача)',()=>fmt(V.tSup,1),'°C'],
        ['ΔT ступеня',()=>fmt(V.tSup-V.tMid,1),'К'],
        ['Витрата',()=>fmt(V.flow,1),'м³/год'],
        ['Q',()=>fmt(V.qExh,0),'кВт']]},
      stack:{sys:'exh',name:'Вихлоп: глушник і труба',chip:'Глушник/труба',sub:'ТО вихлопу → глушник → труба',rows:[
        ['t до ТО',()=>fmt(V.tCatOut,0),'°C'],
        ['t після ТО',()=>fmt(V.tE2,0),'°C'],
        ['t на виході труби',()=>fmt(V.tStack,0),'°C'],
        ['Протитиск',()=>fmt(V.backP,0),'мбар'],
        ['Димність',()=>S.rpm>200?['Норма','ok']:['—','']]]},
      emis:{sys:'exh',name:'Аналіз викидів',chip:'Аналіз викидів',sub:'NOx, CO, O₂ (на 5 % O₂), до граничних значень',rows:[
        ['NOx',()=>[fmt(V.nox,0)+' / '+fmt(th().nox_limit,0),V.nox>th().nox_limit?'alarm':V.nox>th().nox_limit*0.9?'warn':''],'мг/нм³'],
        ['CO',()=>[fmt(V.co,0)+' / '+fmt(th().co_limit,0),V.co>th().co_limit?'alarm':V.co>th().co_limit*0.9?'warn':''],'мг/нм³'],
        ['O₂ у вихлопі',()=>fmt(V.o2,1),'%'],
        ['NOx від ліміту',()=>fmt(V.nox/th().nox_limit*100,0),'%']]},
      airf:{sys:'air',name:'Повітряний фільтр',chip:'Повітр. фільтр',sub:'Повітря на горіння',rows:[
        ['ΔP фільтра',()=>[fmt(V.airDp,1),V.airDp>12?'warn':''],'мбар'],
        ['Поріг заміни',()=>'15','мбар'],
        ['Остання заміна',()=>fmt(toSince('фільтр'),0),'год тому']]},
      vent:{sys:'air',name:'Вентиляція контейнера',chip:'Вентилятори/жалюзі',sub:'Припливний і витяжний вентилятори, жалюзі',rows:[
        ['Припливний вентилятор',()=>fmt(V.fanSup,0),'%'],
        ['Витяжний вентилятор',()=>fmt(V.fanExh,0),'%'],
        ['Жалюзі',()=>fmt(V.louver,0),'% відкр.'],
        ['t в контейнері',()=>[fmt(V.tCont,1),V.tCont>45?'alarm':V.tCont>38?'warn':''],'°C']]},
      generator:{sys:'el',name:'Генератор',chip:'Генератор',sub:'Синхронний, 0,4 кВ, 50 Гц',rows:[
        ['P активна',()=>fmt(V.pel,0),'кВт'],
        ['U лінійна',()=>fmt(V.U,0),'В'],
        ['I фазна',()=>fmt(V.I,0),'А'],
        ['cos φ',()=>fmt(V.cos,3),''],
        ['f',()=>fmt(V.f,2),'Гц'],
        ['Захист: зворотна потужність',()=>['Норма','ok']],
        ['Захист: перевантаження (I/Iном)',()=>[fmt(V.Ipct,0),V.Ipct>105?'warn':''],'%']]},
      avr:{sys:'el',name:'АРН і збудження',chip:'АРН / збудження',sub:'Регулювання за cos φ',rows:[
        ['Струм збудження',()=>fmt(V.excI,1),'А'],
        ['Напруга збудження',()=>fmt(V.excU,0),'В'],
        ['Уставка cos φ',()=>fmt(S.cosSet,2),''],
        ['Q реактивна',()=>fmt(V.Q,0),'квар'],
        ['Режим АРН',()=>'cos φ = const']]},
      cabinet:{sys:'el',name:'Шафа керування',chip:'Шафа керування',sub:'Контролер КГУ, Modbus TCP',rows:[
        ['Стан (u72, 40000)',()=>String(S.state),''],
        ['Режим на щиті',()=>S.remote?['Дистанційне','ok']:['Місцеве','warn']],
        ['Дозвіл КГУ',()=>S.permit?['Є','ok']:['Немає','warn']],
        ['Мережа S2',()=>S.grid?['Наявна','ok']:['Відсутня','alarm']],
        ['Живлення контролера',()=>fmt(V.ctrlV,1),'В']]},
      qf:{sys:'el',name:'Ввід QF-CHP і захист ROCOF',chip:'QF-CHP / ROCOF',sub:'Комірка на шині S2 ГРЩ',rows:[
        ['QF-CHP',()=>S.qf?['Увімкнено','ok']:['Вимкнено','']],
        ['Захист ROCOF',()=>S.rocofFlag?['Спрацював','alarm']:['Норма','ok']],
        ['df/dt',()=>fmt(V.dfdt,2),'Гц/с (уст. 1,0)'],
        ['Векторний зсув',()=>fmt(V.dphi,1),'° (уст. 12)'],
        ['U мережі',()=>fmt(V.uGrid,0),'В']]},
      emeter:{sys:'el',name:'Лічильник ел. енергії TEDOM-1',chip:'Лічильник ел.',sub:'Комерційний облік КГУ',rows:[
        ['P активна',()=>fmt(V.pel,0),'кВт'],
        ['Q реактивна',()=>fmt(V.Q,0),'квар'],
        ['Активна енергія',()=>fmt(V.eTot,0),'кВт·год'],
        ['Реактивна енергія',()=>fmt(V.eRe,0),'квар·год'],
        ['Сьогодні',()=>fmt(S.eDay,0),'кВт·год']]},
      gasdet:{sys:'safe',name:'Газоаналізатор у контейнері',chip:'Газоаналізатор',sub:'Метан, % НКПР; пороги 10 / 20 %',rows:[
        ['Концентрація',()=>[fmt(V.lel,1),V.lel>=th().lel_alarm_pct?'alarm':V.lel>=th().lel_warn_pct?'warn':''],'% НКПР'],
        ['Поріг попередження',()=>fmt(th().lel_warn_pct,0),'%'],
        ['Поріг аварії',()=>fmt(th().lel_alarm_pct,0),'%'],
        ['Стан',()=>V.lel>=th().lel_alarm_pct?['Аварія','alarm']:(V.lel>=th().lel_warn_pct?['Попередження','warn']:['Норма','ok'])]]},
      fire:{sys:'safe',name:'Пожежна сигналізація та гасіння',chip:'Пожежа / гасіння',sub:'Димові/теплові датчики, автоматичне гасіння',rows:[
        ['Сигналізація',()=>S.fire?['ПОЖЕЖА','alarm']:['Норма','ok']],
        ['Гасіння',()=>S.ext==='ready'?['Готове','ok']:(S.ext==='release'?['Випуск','alarm']:['Спрацювало','warn'])],
        ['Балон з речовиною',()=>fmt(S.extLevel,0),'%'],
        ['Датчики дим / тепло',()=>S.fire?['Спрацювали','alarm']:['Норма','ok']]]},
      estop:{sys:'safe',name:'Контур аварійного стопу',chip:'Аварійний стоп',sub:'Кнопки: шафа, двері контейнера, зовнішня',rows:[
        ['Контур ES',()=>S.estopLoop?['Замкнений','ok']:['Розімкнений','alarm']],
        ['Кнопка в шафі',()=>S.esCab?'натиснута':'не натиснута'],
        ['Кнопка на дверях',()=>S.esDoor?'натиснута':'не натиснута'],
        ['Кнопка зовнішня',()=>S.esExt?'натиснута':'не натиснута']]}
    };
    const NODE_ORDER=Object.keys(NODES).sort((a,b)=>SYS.findIndex(s=>s[0]===NODES[a].sys)-SYS.findIndex(s=>s[0]===NODES[b].sys));
    function nodeActive(id){
      switch(id){
        case 'engine':case 'flywheel':case 'generator':case 'turbo':case 'oil':case 'avr': return S.rpm>50;
        case 'gasramp':case 'yv':case 'gasmeter':case 'mixer': return S.valves;
        case 'phe':case 'loop':case 'exhhe':case 'heatmeter':case 'mixv':case 'pumpHT': return V.flow>0.5;
        case 'pumpHeat': return V.pHe.run;
        case 'pumpLT':case 'intercooler': return S.rpm>50;
        case 'coolerLT': return S.fanLT>1;
        case 'stack':case 'cat':case 'emis': return S.rpm>200;
        case 'bypass': return S.rpm>200;
        case 'cooler': return S.fan>1;
        case 'vent': return S.fanSup>1;
        case 'starter': return S.starter;
        case 'oiltanks': return S.topup;
        default: return null;
      }
    }
    function nodeBadge(id){
      if(S.hl&&S.hl.node===id) return S.hl.kind==='alarm'?['Аварія','alarm']:['Попередження','warn'];
      const a=nodeActive(id);
      if(a===null) return ['Норма','ok'];
      return a?['Працює','ok']:['Не працює',''];
    }
    return { NODES, NODE_ORDER, nodeActive, nodeBadge, valveTxt, vpTxt };
}
