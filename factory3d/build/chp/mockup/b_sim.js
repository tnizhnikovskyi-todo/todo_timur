<script>
(function(){
'use strict';
/* ===== Утиліти ===== */
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v)), lerp=(a,b,t)=>a+(b-a)*t;
const approach=(c,t,dt,tau)=>c+(t-c)*(1-Math.exp(-dt/tau));
const ease=p=>p*p*(3-2*p);
const nfs={};
function fmt(v,d=0){
  if(!isFinite(v)) return '—';
  if(Math.abs(v)<Math.pow(10,-d)/2) v=0;
  const f=nfs[d]||(nfs[d]=new Intl.NumberFormat('uk-UA',{minimumFractionDigits:d,maximumFractionDigits:d}));
  return f.format(v);
}
const pad=n=>String(n).padStart(2,'0');
const hms=d=>pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds());
const REDUCED=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
const T0=performance.now(); const tsec=()=>(performance.now()-T0)/1000;
function setText(el,t){ if(el&&el.textContent!==t) el.textContent=t; }
function setCls(el,c){ if(el&&el.getAttribute('class')!==c) el.setAttribute('class',c); }
const A3={}; // API 3D (заповнюється нижче)

/* ===== Константи й стан ===== */
const ST={RESERVE:0,START:1,RUN:2,ALARM:3,COOL:4};
const ST_KEY=['reserve','start','run','alarm','cool'];
const ST_NAME=['Резерв','Пуск','Робота','Аварія','Охолодження'];
const MODES={heat:'За тепловим графіком',el:'За електричним графіком',peak:'Зрізання піку',manual:'Ручний'};
const PN=800, LHV=9.5, CO2K=1.98, COOL_K=3, COOLER_CAP=900, LT_CAP=150, RET_SET=70, IN_GEN=1178;
const STEPS=[
  {id:'vent',name:'Вентиляція контейнера',dur:1.6},
  {id:'warm',name:'Попередній підігрів ОЖ',dur:2.0},
  {id:'lube',name:'Попереднє змащення',dur:1.6},
  {id:'proving',name:'Перевірка герметичності клапанів',dur:2.2},
  {id:'crank',name:'Прокрутка стартером',dur:2.0},
  {id:'ign',name:'Запалювання',dur:1.8},
  {id:'idle',name:'Холостий хід',dur:1.8},
  {id:'sync',name:'Синхронізація з мережею',dur:3.0},
  {id:'load',name:'Набір навантаження',dur:3.6}
];
const stepDur=i=>(STEPS[i].id==='warm'&&S.warmSkip)?0.5:STEPS[i].dur;
const stepName=i=>STEPS[i].name+((STEPS[i].id==='warm'&&S.warmSkip)?' (не потрібен)':'');
const qOf=x=>x>=0.5?497+(x-0.5)*718:lerp(70,497,x/0.5);
const gOf=x=>x>=0.5?109+(x-0.5)*180:lerp(22,109,x/0.5);
const xFromQ=q=>clamp(0.5+(q-497)/718,0.5,1);
const heatDemand=t=>694.5+38*Math.sin(t/480*2*Math.PI)+12*Math.sin(t/97*2*Math.PI);
const PEAKS=[[8,11],[17,21]];
const hourNow=()=>{const d=new Date();return d.getHours()+d.getMinutes()/60;};
const inPeak=h=>PEAKS.some(p=>h>=p[0]&&h<p[1]);
const CYL=['A1','A2','A3','A4','A5','A6','A7','A8','B1','B2','B3','B4','B5','B6','B7','B8'];
const CYL_DEV=[-6,4,-2,9,28,-7,3,-5,2,-8,5,-3,-12,6,1,-4];
const CYL_PLUG=[2400,2400,2400,2400,3560,2400,2400,2400,2400,2400,2400,2400,2400,2400,2400,2400];

const S={
  state:ST.RUN, mode:'heat', setpoint:80, heatDir:'auto', bypassMode:'auto', cosSet:0.98,
  load:0.775, rpm:1500, qf:true, valves:true, stepI:-1, stepT:0, warmSkip:false, coolLeft:0,
  permit:true, remote:true, rsw:true, grid:true,
  gasFault:false, tempFault:false, retFault:false, gasLeak:false, fire:false, rocofFlag:false, estopLoop:true,
  gasP:2.10, tJo:89.4, tJi:80.4, tOil:96.2, pOil:4.6, qth:694.5, gas:158.5, fan:0, fanLT:55,
  tRetB:58, tRetEff:58, mixPos:0, cap:1, capWarned:false, retT:0, bypass:0,
  tE1:495, tE2:182, tAmb:9.0, lel:0.6, lelWarned:false, tCont:31, fanSup:45, fanExh:45, louver:100,
  oilLvl:66.8, oilFresh:68, oilWaste:31, topup:false, airDp:7.4, batV:27.2, starter:false, starterI:0, starts:612,
  ext:'ready', extLevel:100, extT:0, gasTotal:3940620, tLT:42,
  vp:{st:'ok',time:new Date(Date.now()-238*60000)},
  alarm:null, hl:null, sel:null, sys:'all', cb:0, esAsk:false, ilShow:false,
  hours:18400.0, eDay:0, qDay:0, gDay:0, cDay:0, runDay:0, nacc:0, tab:'main',
  sync:{du:0,df:0,dp:0,ok:false}
};
const V={};
const N={};
const nz=k=>(N[k]===undefined?(N[k]=0):N[k]);
function noiseTick(){ ['rpm','pel','qth','gas','cos','u','f','oil','tj','dem','tx','p','k1','k2','k3'].forEach(k=>{N[k]=clamp((N[k]||0)*0.55+(Math.random()*2-1)*0.75,-1,1);}); }

function modeTarget(){
  const h=hourNow();
  switch(S.mode){
    case 'el': return (h>=7&&h<22)?0.88:0.66;
    case 'peak': return inPeak(h)?1.0:0.60;
    case 'manual': return S.setpoint/100;
    default: return xFromQ(heatDemand(tsec()));
  }
}

/* ===== Журнал ===== */
const J=[];
function log(lv,tx,t){ J.unshift({t:t||new Date(),lv,tx,ack:lv==='info'}); if(J.length>60) J.pop(); journalDirty=true; }
let journalDirty=true;
function seedJournal(){
  const now=Date.now(); const m=60000;
  [[238,'info','Пуск КГУ-1: команда класу Б підтверджена (2/2), головний енергетик'],
   [237,'info','Valve proving YV1/YV2: герметичність підтверджена (витік 0,3 мбар/хв)'],
   [236,'info','Синхронізація з мережею S2: ΔU 0,4 %, Δf 0,02 Гц, Δφ 2° · QF-CHP увімкнено'],
   [171,'warn','Тиск газу 1,58 бар: наближення до межі 1,5 бар (квитовано)'],
   [120,'info','Відведення тепла: авто (котельня, надлишок — на градирню ВТ)'],
   [64,'info','Автодолив масла: рівень картера 66 → 74 %, свіже масло −1,4 %'],
   [25,'info','Графік потреби котельні оновлено: ≈ 690 кВт'],
   [12,'warn','Пропущено одне опитування Modbus (регістр 40000), зв’язок відновлено']
  ].forEach(r=>{ const e={t:new Date(now-r[0]*m),lv:r[1],tx:r[2],ack:r[1]==='info'||r[0]>100}; J.unshift(e); });
}
function renderJournal(){
  if(!journalDirty) return; journalDirty=false;
  const ol=$('#jr'); ol.textContent='';
  const names={info:'Інфо',warn:'Попередж.',alarm:'Аварія'};
  J.slice(0,8).forEach(e=>{
    const li=document.createElement('li');
    const tm=document.createElement('time'); tm.textContent=hms(e.t); tm.dateTime=e.t.toISOString();
    const lv=document.createElement('span'); lv.className='lv '+e.lv; lv.textContent=names[e.lv];
    const tx=document.createElement('span'); tx.className='tx'+(e.ack?'':' un'); tx.textContent=e.tx;
    if(e.lv!=='info'){ const ak=document.createElement('span'); ak.className='ak'; ak.textContent=e.ack?'квитовано':'не квитовано'; tx.appendChild(ak); }
    li.append(tm,lv,tx); ol.appendChild(li);
  });
  $('#btn-ack').disabled=!J.some(e=>!e.ack);
}
function ackAll(){
  let n=0; J.forEach(e=>{ if(!e.ack){e.ack=true;n++;} });
  if(S.alarm) S.alarm.acked=true;
  if(n){ log('info','Квитування: підтверджено повідомлень — '+n+' (оператор)'); setMsg('Повідомлення квитовано.','ok'); }
  journalDirty=true;
}

/* ===== Повідомлення, інтерлоки ===== */
function setMsg(t,k){ const m=$('#cmd-msg'); m.textContent=t; m.className='msg'+(k?' '+k:''); }
function interlocks(){
  const L=[
    {ok:S.state!==ST.COOL,t:'КГУ не в стані «Охолодження»',bad:'КГУ охолоджується'},
    {ok:S.state!==ST.ALARM,t:'Немає активної аварії (скинуто)',bad:'активна аварія — потрібне скидання'},
    {ok:S.permit,t:'«Дозвіл КГУ» (chp_permit)',bad:'немає дозволу КГУ'},
    {ok:S.gasP>=1.5,t:'Тиск газу ≥ 1,5 бар',d:' (зараз '+fmt(S.gasP,2)+' бар)',bad:'тиск газу '+fmt(S.gasP,2)+' бар < 1,5 бар'},
    {ok:S.remote,t:'Режим «Дистанційне» на щиті (ctl_remote)',bad:'на щиті не «Дистанційне»'},
    {ok:S.rsw,t:'«Дистанційні перемикання дозволені» (настройка)',bad:'дистанційні перемикання не дозволені'},
    {ok:S.grid,t:'Напруга мережі S2 наявна',bad:'мережа S2 відсутня'},
    {ok:!S.rocofFlag,t:'Захист ROCOF / векторний зсув не спрацював',bad:'спрацював захист ROCOF'},
    {ok:S.lel<10,t:'Газоаналізатор < 10 % НКПР',d:' (зараз '+fmt(S.lel,1)+' %)',bad:'загазованість '+fmt(S.lel,0)+' % НКПР'},
    {ok:!S.fire&&S.ext==='ready',t:'Пожежної тривоги немає, гасіння готове',bad:'пожежна тривога / гасіння'},
    {ok:S.tRetEff<=RET_SET,t:'t зворотки ≤ 70 °C',d:' (зараз '+fmt(S.tRetEff,0)+' °C)',bad:'t зворотки '+fmt(S.tRetEff,0)+' °C > 70 °C'},
    {ok:S.tJo<95,t:'t ОЖ < 95 °C',d:' (зараз '+fmt(S.tJo,0)+' °C)',bad:'t ОЖ '+fmt(S.tJo,0)+' °C ≥ 95 °C'},
    {ok:S.batV>=23.5,t:'АКБ 24 В ≥ 23,5 В',d:' (зараз '+fmt(S.batV,1)+' В)',bad:'АКБ '+fmt(S.batV,1)+' В'},
    {ok:S.oilLvl>=40&&S.estopLoop,t:'Рівень масла ≥ 40 %, контур аварійного стопу замкнений',bad:'рівень масла / контур аварійного стопу'}
  ];
  return {list:L,failed:L.filter(x=>!x.ok),ok:L.every(x=>x.ok)};
}
function renderIL(){
  const box=$('#il'); box.hidden=!S.ilShow; if(!S.ilShow) return;
  const il=interlocks();
  const head=$('#il-head');
  head.className='il-head '+(il.ok?'good':'bad');
  setText(head,il.ok?'Умови пуску виконані':'Пуск заблоковано: '+il.failed.map(x=>x.bad).join('; '));
  const ul=$('#il-list'); const key=il.list.map(x=>x.ok?1:0).join('')+il.list.map(x=>x.d||'').join('|');
  if(ul.dataset.k===key) return; ul.dataset.k=key; ul.textContent='';
  il.list.forEach(x=>{
    const li=document.createElement('li'); li.className=x.ok?'ok':'bad';
    const mk=document.createElement('span'); mk.className='mk'; mk.textContent=x.ok?'✓':'✗'; mk.setAttribute('aria-hidden','true');
    const tx=document.createElement('span'); tx.textContent=x.t+(x.d||'')+(x.ok?' — виконано':' — не виконано');
    li.append(mk,tx); ul.appendChild(li);
  });
}

/* ===== Команди ===== */
function remoteBlock(){ if(!S.remote) return 'на щиті не обрано «Дистанційне» (ctl_remote)'; if(!S.rsw) return 'дистанційні перемикання не дозволені в настройках'; return ''; }
function closeDialogs(){ S.cb=0; S.esAsk=false; }
function cmdStart(){
  S.esAsk=false;
  const il=interlocks(); S.ilShow=true;
  if(!il.ok){ S.cb=0; const tx='Пуск заблоковано: '+il.failed.map(x=>x.bad).join('; '); setMsg(tx,'warn'); log('warn',tx); return; }
  S.cb=1; S.ilShow=false; setMsg('Команда класу Б: потрібні два підтвердження.','');
}
function cbConfirm1(){ if(S.cb!==1) return; S.cb=2; log('info','Пуск: підтвердження 1/2 (енергетик). Очікує другого підтвердження'); setMsg('Очікує другого підтвердження — головний енергетик.','warn'); }
function cbConfirm2(){
  if(S.cb!==2) return;
  const il=interlocks();
  if(!il.ok){ S.cb=0; S.ilShow=true; const tx='Пуск заблоковано: '+il.failed.map(x=>x.bad).join('; '); setMsg(tx,'warn'); log('warn',tx); return; }
  S.cb=0; log('info','Пуск: підтвердження 2/2 (головний енергетик). Команду прийнято'); beginStart();
}
function cbCancel(){ if(S.cb){ S.cb=0; S.ilShow=false; log('info','Команду «Пуск» скасовано до другого підтвердження'); setMsg('Пуск скасовано.',''); } }
function enterStep(i){ S.stepI=i; S.stepT=0; if(STEPS[i].id==='proving') S.vp={st:'run',time:null}; }
function beginStart(){
  S.state=ST.START; S.warmSkip=S.tJo>=55; S.ilShow=false; S.hl=null; S.valves=false; S.qf=false; S.load=0; S.cap=1; S.capWarned=false;
  enterStep(0); setMsg('Виконується послідовність пуску…','');
}
function cmdStop(){
  const b=remoteBlock();
  if(b){ const tx='Команду «Стоп» не прийнято: '+b; setMsg(tx,'warn'); log('warn',tx); return; }
  if(S.state===ST.RUN){ log('info','Команда «Стоп» (оператор): розвантаження, відключення QF-CHP'); beginCool('стоп оператора'); setMsg('Стоп: розвантаження й охолодження.',''); }
  else if(S.state===ST.START){ log('warn','Пуск перервано оператором'); S.qf=false; S.load=0; S.starter=false; if(S.rpm>50) beginCool('перервано пуск'); else toReserve(); setMsg('Пуск перервано.','warn'); }
}
function cmdEStop(){ S.cb=0; S.ilShow=false; S.esAsk=true; }
function esConfirm(){ S.esAsk=false; S.estopLoop=false; log('alarm','Аварійний стоп: розімкнено контур ES (кнопка на пульті)'); raiseAlarm('Аварійний стоп оператора','estop',true); setMsg('Аварійний стоп виконано. Потрібні квитування й скидання аварії.','alarm'); }
function beginCool(reason){
  S.state=ST.COOL; S.coolLeft=60; closeDialogs(); S.stepI=-1; S.starter=false;
  log('info','Охолодження 60 с ('+reason+')');
}
function toReserve(){ S.state=ST.RESERVE; S.valves=false; S.qf=false; S.load=0; S.stepI=-1; S.starter=false; log('info','КГУ-1 зупинено: стан «Резерв»'); if(S.hl&&S.hl.kind==='warn'&&S.grid&&!S.rocofFlag) S.hl=null; }
function raiseAlarm(tx,node,estop){
  if(S.state===ST.ALARM) return;
  S.state=ST.ALARM; S.alarm={text:tx,node:node,acked:false}; S.hl={node:node,kind:'alarm'};
  S.qf=false; S.load=0; S.valves=false; S.stepI=-1; S.starter=false; closeDialogs();
  if(!estop) log('alarm','Аварія: '+tx+'. Закрито газові клапани YV1/YV2, QF-CHP відключено');
}
function tripGrid(kind){
  S.qf=false; S.load=0;
  if(kind==='rocof'){
    S.hl={node:'qf',kind:'warn'};
    log('alarm','Захист ROCOF / векторний зсув: df/dt = 2,4 Гц/с (> 1,0), Δφ = 14° (> 12°). QF-CHP відключено, острівний режим не передбачено → охолодження');
    setMsg('Спрацював ROCOF: QF-CHP відключено, охолодження.','alarm');
  } else {
    S.hl={node:'qf',kind:'warn'};
    log('warn','Зникла мережа S2: QF-CHP відключено, острівний режим не передбачено → охолодження');
    setMsg('Зникла мережа S2: КГУ переходить в охолодження.','warn');
  }
  if(S.rpm>50) beginCool(kind==='rocof'?'спрацював ROCOF':'зникла мережа'); else toReserve();
}
function resetAll(){
  const was=S.state===ST.ALARM;
  S.gasFault=false; S.tempFault=false; S.grid=true; S.retFault=false; S.gasLeak=false; S.fire=false; S.rocofFlag=false; S.estopLoop=true;
  S.ext='ready'; S.extLevel=100; S.extT=0; S.lelWarned=false; S.lel=0.6; S.tRetB=Math.min(S.tRetB,60);
  if(S.alarm) S.alarm.acked=true; J.forEach(e=>{e.ack=true;});
  S.alarm=null; S.hl=null;
  if(was) { S.state=ST.RESERVE; S.rpm=Math.min(S.rpm,200); }
  log('info','Імітацію скасовано: аварію скинуто, мережу, тиск газу, зворотку та безпеку відновлено');
  setMsg('Аварію скинуто. КГУ в резерві.','ok');
}

/* ===== Історія, енергія за добу ===== */
const HIST=[];
function synthHistory(){
  const now=Date.now(), step=60000, offFrom=now-9*3600e3, offTo=now-4*3600e3;
  let seed=7; const rnd=()=>{ seed=(seed*16807)%2147483647; return seed/2147483647-0.5; };
  const midnight=new Date(); midnight.setHours(0,0,0,0);
  for(let t=now-24*3600e3;t<=now;t+=step){
    const d=new Date(t); const hh=d.getHours()+d.getMinutes()/60;
    let f=1; if(t>offFrom&&t<offTo) f=0; else if(t<=offFrom) f=clamp((offFrom-t)/180e3,0,1); else f=clamp((t-offTo)/360e3,0,1);
    const x=clamp(0.74+0.09*Math.sin((hh-15)/24*2*Math.PI)+0.025*Math.sin(t/9e5)+0.012*Math.sin(t/2.4e5)+rnd()*0.01,0.5,1);
    const pe=800*x*f, pt=f>0?qOf(x)*clamp(f*1.3,0,1):0, g=f>0?gOf(x)*clamp(f*1.3,0,1):0;
    HIST.push({t:t,pe:pe,pt:pt,g:g});
  }
  HIST.forEach(p=>{ if(p.t>=midnight.getTime()){ S.eDay+=p.pe/60; S.qDay+=p.pt/60/1163; S.gDay+=p.g/60; S.cDay+=p.g/60*CO2K; if(p.pe>5) S.runDay+=1/60; } });
}
let lastPush=Date.now();
function pushHist(){
  const now=Date.now(); if(now-lastPush<5000) return; lastPush=now;
  HIST.push({t:now,pe:V.pel,pt:V.qth,g:V.gas});
  const lim=now-24*3600e3-60000; while(HIST.length&&HIST[0].t<lim) HIST.shift();
}

/* ===== Фізика/симуляція ===== */
function syncCalc(p){
  const dp=150*Math.exp(-3.2*p)*Math.cos(2*Math.PI*(1.2*p+0.5*p*p));
  S.sync.dp=dp; S.sync.du=2.4*Math.exp(-3*p)+0.2; S.sync.df=0.30*Math.exp(-3.4*p)+0.01;
  S.sync.ok=p>0.8&&Math.abs(dp)<10&&S.sync.du<1&&S.sync.df<0.05;
}
const curId=()=>(S.state===ST.START&&STEPS[S.stepI])?STEPS[S.stepI].id:'';
function step(dt){
  S.nacc+=dt; if(S.nacc>=1){ S.nacc-=1; noiseTick(); }
  S.gasP=approach(S.gasP,S.gasFault?1.15:2.10,dt,1.4);
  S.lel=approach(S.lel,S.gasLeak?32:0.6,dt,S.gasLeak?2:3);
  // зворотка опалення, змішувальний клапан
  S.tRetB=approach(S.tRetB,S.retFault?84:((S.heatDir==='cooler'||S.state!==ST.RUN)?52:58),dt,S.retFault?2.5:5);
  S.mixPos=approach(S.mixPos,clamp((S.tRetB-60)*8,0,100),dt,1.2);
  S.tRetEff=S.tRetB-8*S.mixPos/100;
  // Станова машина
  if(S.state===ST.START){
    const id=STEPS[S.stepI].id, dur=stepDur(S.stepI); S.stepT+=dt; const p=clamp(S.stepT/dur,0,1);
    switch(id){
      case 'vent': S.rpm=0; S.valves=false; break;
      case 'warm': S.rpm=0; if(!S.warmSkip) S.tJo=Math.min(58,S.tJo+3*dt); break;
      case 'lube': S.rpm=0; break;
      case 'proving': S.rpm=0; S.valves=false; break;
      case 'crank': S.starter=true; S.rpm=lerp(0,250,p); break;
      case 'ign': S.starter=p<0.45; S.valves=true; S.rpm=lerp(250,900,p); break;
      case 'idle': S.valves=true; S.rpm=lerp(900,1500,p); break;
      case 'sync': S.rpm=1500; syncCalc(p); break;
      case 'load': S.rpm=1500; S.qf=true; S.load=Math.min(modeTarget(),S.cap)*ease(p); break;
    }
    if(S.stepT>=dur){
      if(id==='proving'){ S.vp={st:'ok',time:new Date()}; log('info','Valve proving YV1/YV2: герметичність підтверджена (витік 0,3 мбар/хв)'); }
      if(id==='sync'){ S.qf=true; log('info','Синхронізація з мережею S2: ΔU '+fmt(S.sync.du,1)+' %, Δf '+fmt(S.sync.df,2)+' Гц, Δφ '+fmt(Math.abs(S.sync.dp),0)+'° · QF-CHP увімкнено'); }
      if(S.stepI+1>=STEPS.length){ S.state=ST.RUN; S.stepI=-1; S.starts++; S.load=Math.min(modeTarget(),S.cap); log('info','Пуск завершено: КГУ-1 в роботі, P ел. = '+fmt(PN*S.load,0)+' кВт'); setMsg('КГУ-1 в роботі.','ok'); }
      else enterStep(S.stepI+1);
    }
    if(S.state===ST.START){
      if(!S.grid) tripGrid('grid');
      else if(S.rocofFlag) tripGrid('rocof');
      else if(!S.permit){ log('warn','Дозвіл КГУ знято під час пуску: зупинка'); S.qf=false; S.load=0; beginCool('зняття дозволу'); }
    }
  } else if(S.state===ST.RUN){
    S.rpm=approach(S.rpm,1500,dt,0.5); S.valves=true; S.qf=true;
    const tg=Math.min(modeTarget(),S.cap); S.load+=clamp(tg-S.load,-0.04*dt,0.04*dt);
    if(!S.grid) tripGrid('grid');
    else if(S.rocofFlag) tripGrid('rocof');
    else if(!S.permit){ log('warn','«Дозвіл КГУ» знято: контрольована зупинка'); beginCool('зняття дозволу КГУ'); }
  } else if(S.state===ST.COOL){
    S.coolLeft-=dt*COOL_K;
    S.load=Math.max(0,S.load-0.35*dt);
    if(S.load<0.02){ S.load=0; if(S.qf){ S.qf=false; log('info','QF-CHP відключено, двигун на холостому ході'); } }
    if(S.coolLeft>0){ S.rpm=approach(S.rpm,1500,dt,0.4); S.valves=true; }
    else { S.coolLeft=0; toReserve(); }
  } else if(S.state===ST.ALARM){
    S.rpm=approach(S.rpm,0,dt,1.3); if(S.rpm<8) S.rpm=0; S.load=0; S.qf=false; S.valves=false;
  } else {
    S.rpm=approach(S.rpm,0,dt,1.0); if(S.rpm<8) S.rpm=0; S.load=0; S.qf=false; S.valves=false;
  }
  if(S.state!==ST.START) S.starter=S.starter&&false;
  // Захисти (пуск/робота/охолодження)
  const active=S.state===ST.START||S.state===ST.RUN||S.state===ST.COOL;
  if(active){
    if(S.gasP<1.5) raiseAlarm('Низький тиск газу: '+fmt(S.gasP,2)+' бар < 1,5 бар','gasramp');
    else if(S.tJo>=97) raiseAlarm('Перегрів ОЖ: '+fmt(S.tJo,1)+' °C ≥ 97 °C','engine');
    else {
      S.cap=S.tRetEff>RET_SET?clamp(1-(S.tRetEff-RET_SET)/6*0.5,0.5,1):1;
      if(S.cap<1&&!S.capWarned){ S.capWarned=true; log('warn','Висока t зворотки '+fmt(S.tRetEff,1)+' °C > 70 °C: клапан відводить тепло на градирню, зниження потужності'); }
      if(S.cap>=1&&S.tRetEff<RET_SET-1) S.capWarned=false;
      S.retT=S.tRetEff>=75.5?S.retT+dt:0;
      if(S.retT>=2) raiseAlarm('Висока температура зворотки: '+fmt(S.tRetEff,1)+' °C > 70 °C (уставка)','mixv');
    }
  } else { S.cap=approach(S.cap,1,dt,2); S.retT=0; }
  // Безпека (у будь-якому стані)
  if(S.lel>=10&&!S.lelWarned){ S.lelWarned=true; log('warn','Газоаналізатор: '+fmt(S.lel,0)+' % НКПР (поріг 10 %): вентиляція на максимум'); }
  if(S.lel<8) S.lelWarned=false;
  if(S.lel>=20&&S.state!==ST.ALARM) raiseAlarm('Загазованість у контейнері: '+fmt(S.lel,0)+' % НКПР ≥ 20 %','gasdet');
  if(S.fire&&S.state!==ST.ALARM) raiseAlarm('Пожежа в контейнері: спрацювала пожежна сигналізація','fire');
  if(S.fire){
    S.extT+=dt;
    if(S.ext==='ready'&&S.extT>3){ S.ext='release'; log('alarm','Автоматичне гасіння: випуск вогнегасної речовини в контейнер'); }
    if(S.ext==='release'){ S.extLevel=Math.max(0,S.extLevel-25*dt); if(S.extLevel<=0) S.ext='done'; }
  }
  // Підсистеми
  const x=S.load, rpmF=S.rpm/1500, hi=S.rpm>1200&&S.valves;
  const qT=hi?qOf(x):(S.rpm>200&&S.valves?30:0);
  const gT=!S.valves?0:(S.rpm<1200?22*clamp(S.rpm/1200,0.3,1):gOf(x));
  S.qth=approach(S.qth,qT,dt,2.5); S.gas=approach(S.gas,gT,dt,1.2);
  let tjT;
  if(S.tempFault) tjT=107; else if(S.state===ST.RUN) tjT=84+7*x; else if(S.state===ST.START) tjT=(S.warmSkip?66:55)+22*rpmF; else if(S.state===ST.COOL) tjT=70; else tjT=S.state===ST.ALARM?60:45;
  S.tJo=approach(S.tJo,tjT,dt,S.tempFault?4.5:11);
  S.tJi=S.tJo-(S.rpm>200?9:2);
  S.tOil=approach(S.tOil,S.rpm>200?90+8*x:42,dt,14);
  const lubeStep=curId()==='lube'||curId()==='proving'||curId()==='warm';
  const poT=S.rpm>1000?4.6:(lubeStep?1.6:(S.rpm>10?1.5+3*rpmF:0)); S.pOil=approach(S.pOil,poT,dt,0.8);
  S.bypass=approach(S.bypass,S.bypassMode==='bypass'?1:(S.bypassMode==='ht'?0:(S.state===ST.RUN?0:1)),dt,2);
  S.tE1=approach(S.tE1,hi?410+110*x:(S.rpm>200&&S.valves?190:S.tAmb),dt,3);
  S.tE2=approach(S.tE2,hi?lerp(170+15*x,S.tE1+4,S.bypass):(S.rpm>200&&S.valves?90:S.tAmb),dt,3);
  S.tLT=approach(S.tLT,S.rpm>50?45:S.tAmb+12,dt,12);
  S.hours+=S.rpm>50?dt/3600:0;
  // масло: розхід, автодолив
  if(S.rpm>50){ S.oilLvl-=0.0075*(0.5+x)*dt; }
  if(!S.topup&&S.oilLvl<66&&S.rpm>50){ S.topup=true; log('info','Автодолив масла: рівень картера '+fmt(S.oilLvl,1)+' % < 66 %'); }
  if(S.topup){ S.oilLvl+=0.12*dt; S.oilFresh-=0.02*dt; if(S.oilLvl>=74){ S.topup=false; log('info','Автодолив масла завершено: картер 74 %, свіже масло '+fmt(S.oilFresh,1)+' %'); } }
  // вентиляція контейнера
  let fT,lT;
  if(S.fire){ fT=0; lT=0; }
  else if(S.lel>=10||curId()==='vent'){ fT=100; lT=100; }
  else if(S.state===ST.RUN){ fT=clamp(30+(S.tCont-28)*7,30,100); lT=100; }
  else if(S.state===ST.COOL||S.state===ST.START){ fT=60; lT=100; }
  else if(S.state===ST.ALARM){ fT=40; lT=100; }
  else { fT=S.tCont>38?60:0; lT=fT>0?100:0; }
  S.fanSup=approach(S.fanSup,fT,dt,1); S.fanExh=approach(S.fanExh,fT,dt,1); S.louver=approach(S.louver,lT,dt,1);
  if(S.fanSup<0.5&&fT===0) S.fanSup=S.fanExh=0;
  S.tCont=approach(S.tCont,S.tAmb+(S.rpm>50?18+10*x:3)-0.08*S.fanSup+(S.fire?30:0),dt,15);
  S.airDp=approach(S.airDp,S.rpm>50?5.4+2.6*S.gas/160:0.3,dt,3);
  S.batV=approach(S.batV,S.starter?22.6+0.04*(1-clamp(S.stepT/2,0,1))*10:27.2,dt,S.starter?0.35:2.5);
  S.starterI=S.starter?approach(S.starterI,380*Math.exp(-S.stepT*0.6)+140,dt,0.25):approach(S.starterI,0,dt,0.2);
  S.gasTotal+=S.gas*dt/3600;
  computeV(dt);
  // Енергія за добу
  S.eDay+=V.pel*dt/3600; S.qDay+=V.qth*dt/3600/1163; S.gDay+=V.gas*dt/3600; S.cDay+=V.gas*CO2K*dt/3600; if(V.pel>5) S.runDay+=dt/3600;
}
function pumpV(run,fmin,fmax,x,inom){ const f=run?fmin+(fmax-fmin)*x:0; return {run:run,f:f,I:run?inom*(0.35+0.65*Math.pow(f/50,3)):0}; }
function computeV(dt){
  const x=S.load, hi=S.rpm>1200;
  V.rpm=hi?S.rpm+nz('rpm')*2.5:S.rpm;
  V.pel=S.qf?Math.max(0,PN*x*(1+nz('pel')*0.006)):0;
  V.pShaft=V.pel/0.96;
  V.qRaw=Math.max(0,S.qth*(1+nz('qth')*0.005));
  V.gas=Math.max(0,S.gas*(1+nz('gas')*0.006));
  // генератор, АРН
  V.cos=S.qf?clamp(S.cosSet+nz('cos')*0.002,0.85,1):0;
  V.Q=S.qf?V.pel*Math.tan(Math.acos(V.cos)):0;
  V.U=S.rpm>=1400?400+1.4*nz('u'):(S.rpm>250&&S.state!==ST.ALARM?400*S.rpm/1500:0);
  V.f=S.rpm/30+(S.rpm>1200?nz('f')*0.015:0);
  V.I=(S.qf&&V.U>50)?V.pel*1000/(Math.sqrt(3)*V.U*V.cos):0;
  V.Ipct=V.I/IN_GEN*100;
  V.excI=S.rpm>=1400?5.5+14*x+(1-V.cos)*20+nz('u')*0.15:0; V.excU=V.excI*3.6;
  V.eTot=10912450+S.eDay; V.eRe=2748320+S.eDay*0.2;
  // двигун, масло
  V.pOil=S.pOil+(S.pOil>3?nz('oil')*0.08:0); V.tJo=S.tJo+nz('tj')*0.15; V.tJi=S.tJi+nz('tj')*0.12; V.tOil=S.tOil+nz('tj')*0.15;
  V.tOilOut=S.rpm>200?V.tOil-9:V.tOil; V.dpOilF=S.rpm>200?0.45+0.1*nz('oil'):0;
  V.oilLvl=S.oilLvl; V.oilFresh=S.oilFresh; V.oilWaste=S.oilWaste; V.oilCons=S.rpm>50?0.22+0.012*nz('oil'):0;
  V.torque=S.rpm>50&&V.pShaft>0?V.pShaft/(S.rpm*2*Math.PI/60):0;
  V.tBrg=50+(S.rpm>50?6+8*x:0)+nz('tj')*0.3; V.vib=S.rpm>50?1.6+0.8*x+nz('p')*0.1:0;
  // газова рампа
  V.gasP=S.gasP+nz('p')*0.01; V.gasReg=S.valves?98+nz('p')*1.5:0; V.dpFilter=S.valves?11+V.gas/40:0;
  V.thr=S.valves?(hi?18+62*x+nz('k1')*1:12):0; V.lambda=hi?1.62-0.1*x+nz('k2')*0.005:0; V.pMix=hi?1.0+1.15*x:0;
  V.tcRpm=hi?30000+22000*x+nz('k1')*200:(S.rpm>200?9000:0); V.pBoost=hi?1.1+1.2*x:(S.rpm>200?1.0:1.0);
  V.tAirIn=hi?150+30*x:S.tAmb; V.tAirOut=hi?(52+6*x):S.tAmb;
  // тепловий блок з урахуванням заслінки вихлопу
  V.qPhe=0.55*V.qRaw; V.qExh=0.45*V.qRaw*(1-S.bypass); V.qth=V.qPhe+V.qExh;
  const Q=V.qth; const dem=heatDemand(tsec())+nz('dem')*4;
  let b,c;
  if(S.state!==ST.RUN){ b=0; c=Q; }
  else if(S.heatDir==='boiler'){ b=Q; c=0; }
  else if(S.heatDir==='cooler'){ b=0; c=Q; }
  else { b=Math.min(Q,dem); c=Q-b; if(c<8){ b=Q; c=0; } }
  V.qBoiler=b; V.qCooler=c; V.demand=dem;
  const pump=S.state!==ST.RESERVE&&!(S.state===ST.ALARM&&S.tJo<60);
  V.flow=pump?Math.max(14,Q/(1.163*20)):0;
  V.tRetRaw=S.tRetB+nz('tx')*0.2; V.tRet=S.tRetEff+nz('tx')*0.2; V.mixPos=S.mixPos; V.cap=S.cap;
  V.tMid=V.flow>0?V.tRet+V.qPhe/(1.163*V.flow):V.tRet; V.tSup=V.flow>0?V.tMid+V.qExh/(1.163*V.flow):V.tRet; V.dT=V.tSup-V.tRet; V.tPheOut=V.tMid;
  V.flowC=c>3?c/(1.163*15):0; V.tCoolOut=V.tRetRaw-(V.flowC>0?c/(1.163*V.flowC):0);
  const fanT=c>3?Math.max(12,c/COOLER_CAP*100):0; S.fan=approach(S.fan,fanT,dt,2); if(S.fan<0.5&&fanT===0) S.fan=0;
  V.fan=S.fan; V.pLoop=3.2+nz('p')*0.04;
  V.hmTot=9412.6+S.qDay; V.hmP=b; V.hmFlow=V.flow;
  // НТ-контур
  V.qLT=hi?40+85*x:(S.rpm>200?10:0);
  V.flowLT=S.rpm>50?Math.max(8,V.qLT/(1.163*5)):0;
  V.tLTin=40+nz('tx')*0.2; V.tLTout=V.flowLT>0?V.tLTin+V.qLT/(1.163*V.flowLT):V.tLTin;
  const fLT=V.qLT>3?clamp(20+V.qLT/LT_CAP*60,0,100):0; S.fanLT=approach(S.fanLT,fLT,dt,2); if(fLT===0&&S.fanLT<0.5) S.fanLT=0; V.fanLT=S.fanLT;
  V.pExpHT=1.6+0.012*(S.tJo-45)+nz('p')*0.01; V.pExpLT=1.4+0.008*(S.tLT-20)+nz('p')*0.01; V.pExpH=V.pLoop-0.3;
  // насоси
  const pHT=pumpV(pump,38,48,x,14.5), pHe=pumpV(V.flow>0.5,34,46,x,6.2), pLT=pumpV(S.rpm>50,40,47,x,4.1);
  V.pHT=pHT; V.pHe=pHe; V.pLT=pLT;
  V.pDisHT=pump?2.4+0.5*x:0; V.pDisLT=S.rpm>50?1.9+0.2*x:0;
  // вихлоп
  V.tE1=S.tE1+nz('tx')*1.5; V.tCatOut=V.tE1+(hi?16+nz('k1')*1.5:0); V.tE2=S.tE2+nz('tx')*0.8; V.tStack=Math.max(S.tAmb,V.tE2-12);
  V.tTurb=V.tE1+(hi?60:0); V.dpCat=hi?6+6*V.gas/160+nz('k3')*0.3:(S.rpm>200?2:0);
  V.nox=hi?150+80*x+nz('k1')*4:0; V.coRaw=hi?520-220*x+nz('k2')*10:0; V.co=hi?38+55*(1-x)+nz('k2')*3:0; V.o2=hi?8.4-0.8*x+nz('k3')*0.05:0;
  V.bypass=S.bypass;
  // повітря/контейнер
  V.airDp=S.airDp+nz('k3')*0.05; V.tCont=S.tCont; V.fanSup=S.fanSup; V.fanExh=S.fanExh; V.louver=S.louver;
  // безпека
  V.lel=S.lel+(S.lel<5?nz('k1')*0.1:0);
  // старт/живлення
  V.batV=S.batV+nz('u')*0.03; V.starterI=S.starterI;
  V.batI=S.starter?0:clamp((27.2-S.batV)*8+1.3+nz('k2')*0.1,0.8,30);
  // ККД
  const fuel=V.gas*LHV; const ok=fuel>20&&S.rpm>1200;
  V.etaE=ok?V.pel/fuel*100:0; V.etaH=ok?Q/fuel*100:0; V.etaT=V.etaE+V.etaH;
  V.co2=V.gas*CO2K;
  // діагностика циліндрів
  const mean=hi?S.tE1+55:S.tE1; let sum=0; const cyl=[];
  for(let i=0;i<16;i++){
    const t=mean+(hi?CYL_DEV[i]+nz(i%2?'k1':'k2')*3:0);
    cyl.push({t:t,dev:0,knock:0,kv:0,ms:0,plug:CYL_PLUG[i]+(S.hours-18400)});
    sum+=t;
  }
  const avg=sum/16; V.cylAvg=avg;
  cyl.forEach((c,i)=>{
    c.dev=hi?c.t-avg:0;
    c.knock=hi?6+9*x+(i===4?9:0)+Math.abs(CYL_DEV[i])*0.1+Math.abs(nz(i%3?'k1':'k3'))*2.5:0;
    c.kv=hi?22.5+4*x+(i===4?3.4:0)+(CYL_DEV[i]>8?0.6:0)+nz(i%2?'k2':'k3')*0.3:0;
    c.ms=hi?1.38-0.2*x-(i===4?0.26:0)+nz(i%2?'k3':'k1')*0.02:0;
  });
  V.cyl=cyl;
}

/* ===== Вузли 3D: системи і картки параметрів ===== */
const SYS=[['all','Усі'],['eng','Двигун'],['gas','Газ'],['ht','Тепло ВТ'],['lt','Тепло НТ'],['exh','Вихлоп'],['air','Повітря'],['el','Електрика'],['safe','Безпека']];
const stat=(txt,cls)=>[txt,cls||''];
const runTxt=on=>on?['Працює','ok']:['Зупинено',''];
function valveTxt(){
  if(S.valves) return ['Відкрито','ok'];
  if(curId()==='proving') return ['Тест','warn'];
  return ['Закрито',''];
}
function vpTxt(){ return S.vp.st==='ok'?['Успішно','ok']:(S.vp.st==='run'?['Виконується','warn']:['Витік','alarm']); }
const NODES={
  engine:{sys:'eng',name:'Двигун ГПД',chip:'Двигун',sub:'Газопоршневий V16, 1500 об/хв',rows:[
    ['Частота обертання',()=>fmt(V.rpm,0),'об/хв'],
    ['Тиск масла',()=>fmt(V.pOil,1),'бар'],
    ['t ОЖ (вихід)',()=>[fmt(V.tJo,1),V.tJo>=95?'alarm':V.tJo>=92?'warn':''],'°C'],
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
    ['До заміни масла',()=>fmt(1000+17900-S.hours,0),'год']]},
  starter:{sys:'eng',name:'Стартер',chip:'Стартер',sub:'Електростартер 24 В',rows:[
    ['Стан',()=>S.starter?['Прокрутка','warn']:['Очікування','']],
    ['Струм стартера',()=>fmt(V.starterI,0),'А'],
    ['Напруга АКБ',()=>fmt(V.batV,1),'В'],
    ['Кількість пусків',()=>fmt(S.starts,0),'']]},
  battery:{sys:'eng',name:'АКБ 24 В і зарядний пристрій',chip:'АКБ / ЗП',sub:'2 × 12 В, буферний заряд',rows:[
    ['Напруга АКБ',()=>[fmt(V.batV,1),V.batV<23.5?'alarm':V.batV<24.5?'warn':''],'В'],
    ['Струм зарядного',()=>fmt(V.batI,1),'А'],
    ['Режим ЗП',()=>S.starter?['Розряд','warn']:(V.batI>6?['Заряд','warn']:['Буфер','ok'])],
    ['Ємність АКБ',()=>fmt(100,0),'А·год']]},
  gasramp:{sys:'gas',name:'Газова рампа',chip:'Газова рампа',sub:'Кран, фільтр, регулятор, датчики мін./макс.',rows:[
    ['Кран на вході',()=>['Відкрито','ok']],
    ['p на вході',()=>[fmt(V.gasP,2),V.gasP<1.5?'alarm':V.gasP<1.7?'warn':''],'бар'],
    ['ΔP газового фільтра',()=>fmt(V.dpFilter,0),'мбар'],
    ['p після регулятора',()=>fmt(V.gasReg,0),'мбар'],
    ['Датчик min (PSL 1,5 бар)',()=>V.gasP<1.5?['Спрацював','alarm']:['Норма','ok']],
    ['Датчик max (PSH 3,0 бар)',()=>['Норма','ok']]]},
  yv:{sys:'gas',name:'Клапани YV1/YV2, valve proving',chip:'Клапани YV1/YV2',sub:'Два електромагнітні клапани + контроль герметичності',rows:[
    ['Клапан YV1',()=>valveTxt()],
    ['Клапан YV2',()=>valveTxt()],
    ['Valve proving',()=>vpTxt()],
    ['Остання перевірка',()=>S.vp.time?hms(S.vp.time):'—'],
    ['Витік між клапанами',()=>S.vp.st==='ok'?'0,3':'—','мбар/хв']]},
  gasmeter:{sys:'gas',name:'Лічильник газу',chip:'Лічильник газу',sub:'Обʼємний, з коректором',rows:[
    ['Витрата',()=>fmt(V.gas,1),'м³/год'],
    ['Лічильник',()=>fmt(S.gasTotal,0),'м³'],
    ['За добу',()=>fmt(S.gDay,0),'м³'],
    ['Теплота згоряння (LHV)',()=>fmt(LHV,1),'кВт·год/м³']]},
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
    ['t зворотки на вході ТО',()=>[fmt(V.tRet,1),V.tRet>RET_SET?'alarm':V.tRet>RET_SET-4?'warn':''],'°C'],
    ['Уставка',()=>'≤ 70','°C'],
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
    ['Протитиск',()=>fmt(S.rpm>200?12+6*S.load:0,0),'мбар'],
    ['Димність',()=>S.rpm>200?['Норма','ok']:['—','']]]},
  emis:{sys:'exh',name:'Аналіз викидів',chip:'Аналіз викидів',sub:'NOx, CO, O₂ (на 5 % O₂), до граничних значень',rows:[
    ['NOx',()=>[fmt(V.nox,0)+' / 250',V.nox>250?'alarm':V.nox>225?'warn':''],'мг/нм³'],
    ['CO',()=>[fmt(V.co,0)+' / 300',V.co>300?'alarm':V.co>270?'warn':''],'мг/нм³'],
    ['O₂ у вихлопі',()=>fmt(V.o2,1),'%'],
    ['NOx від ліміту',()=>fmt(V.nox/250*100,0),'%']]},
  airf:{sys:'air',name:'Повітряний фільтр',chip:'Повітр. фільтр',sub:'Повітря на горіння',rows:[
    ['ΔP фільтра',()=>[fmt(V.airDp,1),V.airDp>12?'warn':''],'мбар'],
    ['Поріг заміни',()=>'15','мбар'],
    ['Остання заміна',()=>fmt(S.hours-17600,0),'год тому']]},
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
    ['Живлення контролера',()=>fmt(24.1+nz('u')*0.05,1),'В']]},
  qf:{sys:'el',name:'Ввід QF-CHP і захист ROCOF',chip:'QF-CHP / ROCOF',sub:'Комірка на шині S2 ГРЩ',rows:[
    ['QF-CHP',()=>S.qf?['Увімкнено','ok']:['Вимкнено','']],
    ['Захист ROCOF',()=>S.rocofFlag?['Спрацював','alarm']:['Норма','ok']],
    ['df/dt',()=>S.rocofFlag?'2,4':fmt(0.03+Math.abs(nz('f'))*0.05,2),'Гц/с (уст. 1,0)'],
    ['Векторний зсув',()=>S.rocofFlag?'14':fmt(0.6+Math.abs(nz('f')),1),'° (уст. 12)'],
    ['U мережі',()=>S.grid?fmt(400+nz('u'),0):'0','В']]},
  emeter:{sys:'el',name:'Лічильник ел. енергії TEDOM-1',chip:'Лічильник ел.',sub:'Комерційний облік КГУ',rows:[
    ['P активна',()=>fmt(V.pel,0),'кВт'],
    ['Q реактивна',()=>fmt(V.Q,0),'квар'],
    ['Активна енергія',()=>fmt(V.eTot,0),'кВт·год'],
    ['Реактивна енергія',()=>fmt(V.eRe,0),'квар·год'],
    ['Сьогодні',()=>fmt(S.eDay,0),'кВт·год']]},
  gasdet:{sys:'safe',name:'Газоаналізатор у контейнері',chip:'Газоаналізатор',sub:'Метан, % НКПР; пороги 10 / 20 %',rows:[
    ['Концентрація',()=>[fmt(V.lel,1),V.lel>=20?'alarm':V.lel>=10?'warn':''],'% НКПР'],
    ['Поріг попередження',()=>'10','%'],
    ['Поріг аварії',()=>'20','%'],
    ['Стан',()=>V.lel>=20?['Аварія','alarm']:(V.lel>=10?['Попередження','warn']:['Норма','ok'])]]},
  fire:{sys:'safe',name:'Пожежна сигналізація та гасіння',chip:'Пожежа / гасіння',sub:'Димові/теплові датчики, автоматичне гасіння',rows:[
    ['Сигналізація',()=>S.fire?['ПОЖЕЖА','alarm']:['Норма','ok']],
    ['Гасіння',()=>S.ext==='ready'?['Готове','ok']:(S.ext==='release'?['Випуск','alarm']:['Спрацювало','warn'])],
    ['Балон з речовиною',()=>fmt(S.extLevel,0),'%'],
    ['Датчики дим / тепло',()=>S.fire?['Спрацювали','alarm']:['Норма','ok']]]},
  estop:{sys:'safe',name:'Контур аварійного стопу',chip:'Аварійний стоп',sub:'Кнопки: шафа, двері контейнера, зовнішня',rows:[
    ['Контур ES',()=>S.estopLoop?['Замкнений','ok']:['Розімкнений','alarm']],
    ['Кнопка в шафі',()=>S.estopLoop?'не натиснута':'натиснута'],
    ['Кнопка на дверях',()=>'не натиснута'],
    ['Кнопка зовнішня',()=>'не натиснута']]}
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
let ddCache=[], badgeEl=null;
function buildNodeList(){
  const seg=$('#sys-seg');
  SYS.forEach(s=>{
    const b=document.createElement('button'); b.type='button'; b.dataset.sys=s[0]; b.textContent=s[1]; b.setAttribute('aria-pressed',s[0]==='all'?'true':'false');
    b.addEventListener('click',()=>setSystem(s[0])); seg.appendChild(b);
  });
  const host=$('#nodes');
  NODE_ORDER.forEach(id=>{
    const b=document.createElement('button'); b.type='button'; b.dataset.node=id; b.dataset.sys=NODES[id].sys; b.textContent=NODES[id].chip; b.setAttribute('aria-pressed','false'); b.title=NODES[id].name;
    b.addEventListener('click',()=>selectNode(S.sel===id?null:id,true));
    host.appendChild(b);
  });
}
function setSystem(sys){
  S.sys=sys;
  $$('#sys-seg button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.sys===sys?'true':'false'));
  $$('#nodes button').forEach(b=>{ b.hidden=!(sys==='all'||b.dataset.sys===sys); });
  if(S.sel&&sys!=='all'&&NODES[S.sel].sys!==sys) selectNode(null,false);
  if(A3.setSystem) A3.setSystem(sys);
}
function selectNode(id,fromList){
  S.sel=id; renderNodeDetail(true);
  if(id&&fromList&&A3.focus) A3.focus(id);
}
A3.pick=id=>{ if(id&&S.sys!=='all'&&NODES[id].sys!==S.sys) setSystem('all'); selectNode(id,false); };
function renderNodeDetail(force){
  const host=$('#node-detail');
  $$('#nodes button').forEach(b=>{
    b.setAttribute('aria-pressed',b.dataset.node===S.sel?'true':'false');
    const hl=S.hl&&S.hl.node===b.dataset.node; b.classList.toggle('hl-alarm',!!hl&&S.hl.kind==='alarm'); b.classList.toggle('hl-warn',!!hl&&S.hl.kind==='warn');
  });
  if(!S.sel){
    if(force||host.dataset.id){ host.dataset.id=''; host.innerHTML='<p class="nd-empty">Оберіть вузол у 3D-моделі (клік) або зі списку: тут з’являться його живі параметри. Кнопки систем вище підсвічують групу вузлів у 3D.</p>'; ddCache=[]; badgeEl=null; }
    return;
  }
  const d=NODES[S.sel];
  if(force||host.dataset.id!==S.sel){
    host.dataset.id=S.sel; host.textContent=''; ddCache=[];
    const hd=document.createElement('div'); hd.className='nd-h';
    const l=document.createElement('div'); const h=document.createElement('h3'); h.textContent=d.name; const sub=document.createElement('div'); sub.className='nd-sub'; sub.textContent=d.sub; l.append(h,sub);
    const r=document.createElement('div'); badgeEl=document.createElement('span'); badgeEl.className='badge'; r.appendChild(badgeEl);
    hd.append(l,r); host.appendChild(hd);
    const dl=document.createElement('dl'); dl.className='nd-rows'; dl.style.marginTop='8px';
    d.rows.forEach(row=>{
      const w=document.createElement('div'); const dt=document.createElement('dt'); dt.textContent=row[0];
      const dd=document.createElement('dd'); const v=document.createElement('span'); dd.appendChild(v);
      if(row[2]){ const u=document.createElement('small'); u.textContent=row[2]; dd.appendChild(u); }
      w.append(dt,dd); dl.appendChild(w); ddCache.push({dd:dd,v:v,fn:row[1]});
    });
    host.appendChild(dl);
  }
  ddCache.forEach(c=>{ const r=c.fn(); const t=Array.isArray(r)?r[0]:r; const cls=Array.isArray(r)?r[1]:''; setText(c.v,t); const nc=cls||''; if(c.dd.className!==nc) c.dd.className=nc; });
  const bd=nodeBadge(S.sel); setText(badgeEl,bd[0]); const bc='badge '+bd[1]; if(badgeEl.className!==bc) badgeEl.className=bc;
}

/* ===== ТО ===== */
const MAINT=[
  {n:'Планове ТО (кожні 2 000 мотогод)',every:2000,last:17000},
  {n:'Заміна моторного масла',every:1000,last:17900},
  {n:'Свічки запалювання',every:4000,last:16000},
  {n:'Повітряний фільтр',every:2000,last:17600},
  {n:'Огляд каталізатора',every:8000,last:16000}
];
let toEls=[];
function buildTO(){
  const host=$('#to-list');
  MAINT.forEach(m=>{
    const it=document.createElement('div'); it.className='to-item';
    const r=document.createElement('div'); r.className='r'; const n=document.createElement('span'); n.className='n'; n.textContent=m.n; const v=document.createElement('span'); v.className='v'; r.append(n,v);
    const bar=document.createElement('div'); bar.className='bar to'; bar.setAttribute('aria-hidden','true'); const i=document.createElement('i'); bar.appendChild(i);
    const s=document.createElement('div'); s.className='note';
    it.append(r,bar,s); host.appendChild(it); toEls.push({m:m,v:v,i:i,s:s,bar:bar});
  });
}
function toLeft(m){ return m.last+m.every-S.hours; }
function renderTO(){
  toEls.forEach(e=>{
    const left=toLeft(e.m), used=clamp(1-left/e.m.every,0,1);
    setText(e.v,'через '+fmt(left,0)+' год');
    e.i.style.width=(used*100).toFixed(1)+'%';
    const warn=left<e.m.every*0.15; e.bar.classList.toggle('warn',warn); e.v.classList.toggle('warn',warn);
    setText(e.s,'≈ '+fmt(left/24,0)+' діб за безперервної роботи · наступне при '+fmt(e.m.last+e.m.every,0)+' мотогод');
  });
}

/* ===== Рендер DOM ===== */
const BQ={};
function bind(){ $$('[data-b]').forEach(el=>{ BQ[el.dataset.b]=el; }); }
const B=(k,t)=>setText(BQ[k],t);
let lastStateKey='';
function renderHeader(){
  const key=ST_KEY[S.state]; const pl=$('#plaque');
  if(pl.dataset.st!==key) pl.dataset.st=key;
  pl.classList.toggle('unack',S.state===ST.ALARM&&S.alarm&&!S.alarm.acked);
  setText($('#pl-name'),ST_NAME[S.state].toUpperCase()); setText($('#pl-code'),String(S.state));
  let sub='';
  switch(S.state){
    case ST.RUN: sub=fmt(V.pel,0)+' кВт · '+fmt(S.load*100,0)+' %'+(S.cap<0.995?' · обмеження '+fmt(S.cap*100,0)+' %':''); break;
    case ST.START: sub='Крок '+(S.stepI+1)+'/'+STEPS.length+': '+stepName(S.stepI); break;
    case ST.COOL: sub='Охолодження: '+Math.ceil(S.coolLeft)+' с'; break;
    case ST.ALARM: sub=S.alarm?S.alarm.text:''; break;
    default: sub=interlocks().ok?'Готова до пуску':'Пуск заблоковано';
  }
  setText($('#pl-sub'),sub);
  const sk=key+(S.state===ST.ALARM&&S.alarm?S.alarm.text:'');
  if(sk!==lastStateKey){ lastStateKey=sk; setText($('#state-live'),'Стан КГУ: '+ST_NAME[S.state]+(S.state===ST.ALARM&&S.alarm?'. '+S.alarm.text:'')); }
  $('#tab-dot').hidden=!(S.state===ST.ALARM&&S.alarm&&!S.alarm.acked);
  setText($('#hdr-mode'),MODES[S.mode]);
  setText($('#hdr-time'),hms(new Date()));
  const setP=(id,ok,t)=>{ const li=$(id); li.classList.toggle('ok',ok); if(t) setText($('.t',li),t); };
  setP('#perm-permit',S.permit); setP('#perm-gas',S.gasP>=1.5,'Тиск газу '+fmt(S.gasP,2)+' бар '+(S.gasP>=1.5?'≥':'<')+' 1,5');
  setP('#perm-remote',S.remote); setP('#perm-rsw',S.rsw); setP('#perm-grid',S.grid);
}
function renderControl(){
  const st=S.state;
  $('#btn-start').disabled=!(st===ST.RESERVE||st===ST.ALARM||st===ST.COOL)||S.cb>0;
  $('#btn-stop').disabled=!(st===ST.RUN||st===ST.START);
  $('#btn-estop').disabled=st===ST.ALARM;
  $('#clsb').hidden=S.cb===0;
  if(S.cb){
    $('#btn-cb1').hidden=S.cb!==1; $('#btn-cb2').hidden=S.cb!==2;
    $('#cb-c1').classList.toggle('done',S.cb>=2);
    setText($('#clsb-p'),S.cb===1?'Пуск виконується лише після двох підтверджень: енергетика та головного енергетика. Підтвердіть перший крок.':'Очікує другого підтвердження: головний енергетик. (Демо: підтвердіть кнопкою нижче.)');
  }
  $('#es-confirm').hidden=!S.esAsk;
  renderIL();
  const seq=$('#seq'); seq.hidden=st!==ST.START;
  if(st===ST.START){
    const ol=$('#seq-steps');
    if(!ol.children.length){ STEPS.forEach((s,i)=>{ const li=document.createElement('li'); const mk=document.createElement('span'); mk.className='mk'; mk.setAttribute('aria-hidden','true'); const n=document.createElement('span'); const t=document.createElement('span'); t.className='mono'; t.style.fontSize='12px'; li.append(mk,n,t); ol.appendChild(li); }); }
    let total=0,done=0; STEPS.forEach((s,i)=>{ const d=stepDur(i); total+=d; if(i<S.stepI) done+=d; else if(i===S.stepI) done+=Math.min(S.stepT,d); });
    Array.from(ol.children).forEach((li,i)=>{
      const cls=i<S.stepI?'done':(i===S.stepI?'cur':''); if(li.className!==cls) li.className=cls;
      setText(li.firstChild,i<S.stepI?'✓':(i===S.stepI?'▶':'○'));
      setText(li.children[1],(i+1)+'. '+stepName(i));
      setText(li.lastChild,i===S.stepI?fmt(Math.max(0,stepDur(i)-S.stepT),1)+' с':'');
    });
    $('#seq-bar').style.width=(done/total*100).toFixed(1)+'%';
    const cid=curId(); setText($('#seq-t'),'Пуск КГУ-1 · '+fmt(done/total*100,0)+' %');
    let note='';
    switch(cid){
      case 'vent': note='Вентилятори на 100 %, газоаналізатор '+fmt(V.lel,1)+' % НКПР'; break;
      case 'warm': note=S.warmSkip?'ОЖ ≥ 55 °C: підігрів не потрібен':'Підігрів ОЖ: '+fmt(V.tJo,1)+' °C → 58 °C'; break;
      case 'lube': note='Тиск масла '+fmt(V.pOil,1)+' бар'; break;
      case 'proving': note='YV1/YV2: випробування тиском, витік '+fmt(0.3,1)+' мбар/хв'; break;
      case 'crank': note='Стартер: '+fmt(V.starterI,0)+' А, АКБ '+fmt(V.batV,1)+' В, '+fmt(V.rpm,0)+' об/хв'; break;
      case 'load': note='P ел. '+fmt(V.pel,0)+' кВт'; break;
      default: note='Обертів: '+fmt(V.rpm,0)+' об/хв · газ '+fmt(V.gas,0)+' м³/год';
    }
    setText($('#seq-note'),note);
    const syncing=cid==='sync', synced=S.stepI>7;
    const needle=$('#sync-needle'); const ang=syncing?S.sync.dp:0;
    needle.setAttribute('transform','rotate('+ang.toFixed(1)+' 75 75)');
    setText($('#sy-du'),syncing||synced?fmt(synced?0.3:S.sync.du,1)+' %':'—');
    setText($('#sy-df'),syncing||synced?fmt(synced?0.02:S.sync.df,2)+' Гц':'—');
    setText($('#sy-dp'),syncing||synced?fmt(synced?2:Math.abs(S.sync.dp),0)+'°':'—');
    const ss=$('#sync-st'); const okk=synced||(syncing&&S.sync.ok); ss.classList.toggle('ok',okk);
    setText(ss,synced?'Синхронізовано':(syncing?(okk?'Синхронізм':'Підгонка'):'Очікування'));
  }
  const cb=$('#cool-box'); cb.hidden=st!==ST.COOL;
  if(st===ST.COOL){ setText($('#cool-t'),Math.ceil(S.coolLeft)+' с'); $('#cool-bar').style.width=((60-S.coolLeft)/60*100).toFixed(1)+'%'; }
  const man=S.mode==='manual'; const rng=$('#rng-sp'); if(rng.disabled===man) rng.disabled=!man;
  setText($('#out-sp'),S.setpoint+' % · '+fmt(PN*S.setpoint/100,0)+' кВт');
  setText($('#out-cos'),fmt(S.cosSet,2)+' · Q '+fmt(Math.round(V.pel>5?V.Q:PN*0.775*Math.tan(Math.acos(S.cosSet))),0)+' квар');
  const tg=modeTarget(); let mi='';
  switch(S.mode){
    case 'heat': mi='Навантаження за потребою котельні: '+fmt(V.demand||heatDemand(tsec()),0)+' кВт тепла → '+fmt(tg*100,0)+' %.'; break;
    case 'el': mi='Добовий графік: 07–22 год — 88 %, вночі — 66 %. Ціль зараз '+fmt(tg*100,0)+' %.'; break;
    case 'peak': mi='Пікові вікна 08–11 та 17–21: 100 %, поза вікном 60 %. Ціль зараз '+fmt(tg*100,0)+' %.'; break;
    default: mi='Ручна уставка оператора: '+S.setpoint+' %.';
  }
  setText($('#mode-info'),mi);
  setText($('#ret-note'),S.cap<0.995?'Обмеження потужності до '+fmt(S.cap*100,0)+' %: t зворотки '+fmt(V.tRet,1)+' °C > 70 °C. Далі — аварійний останов.':'Захист зворотки: уставка ≤ 70 °C (зараз '+fmt(V.tRet,1)+' °C, клапан '+fmt(V.mixPos,0)+' %); вище — зниження потужності, далі аварійний останов.');
}
function renderKPI(){
  B('pel',fmt(V.pel,0)); B('pel_s',fmt(S.load*100,0)+' % від '+PN+' кВт');
  B('qth',fmt(V.qth,0)); B('qth_s','котельня '+fmt(V.qBoiler,0)+' · градирня '+fmt(V.qCooler,0));
  B('gas',fmt(V.gas,0)); B('gas_s','≈ '+fmt(V.gas*LHV,0)+' кВт палива');
  B('etat',fmt(V.etaT,1)); B('etae',fmt(V.etaE,1)); B('etah',fmt(V.etaH,1)); B('eta_s','ел. + тепл. до палива (LHV)');
  B('e_day',fmt(S.eDay,0)); B('e_day_s','з 00:00 · '+fmt(S.runDay,1)+' год роботи');
  B('q_day',fmt(S.qDay,2)); B('q_day_s','газ за добу '+fmt(S.gDay,0)+' м³');
  B('mh',fmt(S.hours,1)); const nxt=Math.min.apply(null,MAINT.map(toLeft)); B('to_s','до найближчого ТО: '+fmt(nxt,0)+' год');
  B('co2',fmt(V.co2,0)); B('co2_s','сьогодні ≈ '+fmt(S.cDay/1000,2)+' т');
  B('cos',fmt(V.cos,2)); B('q_s','Q = '+fmt(V.Q,0)+' квар (інд.)');
  B('nox',fmt(V.nox,0)); B('nox_s','ліміт 250 · CO '+fmt(V.co,0)+' / 300 мг/нм³');
  B('hm',fmt(V.hmTot,1)); B('hm_s','подача '+fmt(V.tSup,0)+' · зворотка '+fmt(V.tRet,0)+' °C · '+fmt(V.hmFlow,1)+' м³/год');
  B('em',fmt(V.eTot,0)); B('em_s','реактивна '+fmt(V.eRe,0)+' квар·год');
}
/* ===== Тренд ===== */
const TR={range:24,hoverX:null,last:0};
function drawTrend(){
  const wrap=$('#trend-wrap'); const W=Math.floor(wrap.clientWidth); if(W<200) return;
  const Hh=W<520?240:(W>=800?360:290); const m={l:42,r:40,t:20,b:22};
  const svg=$('#trend'); svg.setAttribute('viewBox','0 0 '+W+' '+Hh); svg.setAttribute('width',W); svg.setAttribute('height',Hh);
  const t1=Date.now(), t0=t1-TR.range*3600e3, iw=W-m.l-m.r, ih=Hh-m.t-m.b;
  const X=t=>m.l+(t-t0)/(t1-t0)*iw, Y=v=>m.t+(1-v/1000)*ih, YG=v=>m.t+(1-v/250)*ih;
  let s='';
  for(let i=0;i<=5;i++){
    const y=m.t+ih*i/5;
    s+='<line x1="'+m.l+'" x2="'+(W-m.r)+'" y1="'+y.toFixed(1)+'" y2="'+y.toFixed(1)+'" stroke="var(--line)" stroke-width="1"/>';
    s+='<text x="'+(m.l-6)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end">'+(1000-200*i)+'</text>';
    s+='<text x="'+(W-m.r+6)+'" y="'+(y+4).toFixed(1)+'">'+(250-50*i)+'</text>';
  }
  const d=new Date(t0); let step;
  if(TR.range===24){ d.setMinutes(0,0,0); d.setHours(Math.ceil((d.getHours()+(t0>d.getTime()?1:0))/4)*4); step=4*3600e3; }
  else { d.setSeconds(0,0); d.setMinutes(Math.ceil((d.getMinutes()+(t0>d.getTime()?1:0))/10)*10); step=10*60e3; }
  for(let tt=d.getTime();tt<=t1;tt+=step){
    const x=X(tt).toFixed(1); const dd=new Date(tt);
    s+='<line x1="'+x+'" x2="'+x+'" y1="'+m.t+'" y2="'+(m.t+ih)+'" stroke="var(--line)" stroke-width="1" stroke-dasharray="2 4"/>';
    s+='<text x="'+x+'" y="'+(Hh-6)+'" text-anchor="middle">'+pad(dd.getHours())+':'+pad(dd.getMinutes())+'</text>';
  }
  s+='<text x="'+(m.l-6)+'" y="10" text-anchor="end" style="font-size:10px">кВт</text>';
  s+='<text x="'+(W-m.r+6)+'" y="10" style="font-size:10px">м³/год</text>';
  let lo=0,hi=HIST.length; while(lo<hi){ const mid=(lo+hi)>>1; if(HIST[mid].t<t0) lo=mid+1; else hi=mid; }
  const n=HIST.length-lo, dec=Math.max(1,Math.floor(n/(iw*1.2)));
  const ser=(k,fy,col)=>{ let p=''; for(let i=lo;i<HIST.length;i+=dec){ const h=HIST[i]; p+=X(h.t).toFixed(1)+','+fy(h[k]).toFixed(1)+' '; } const h=HIST[HIST.length-1]; if(h) p+=X(h.t).toFixed(1)+','+fy(h[k]).toFixed(1); return '<polyline fill="none" stroke="'+col+'" stroke-width="2" stroke-linejoin="round" points="'+p+'"/>'; };
  if(HIST.length){ s+=ser('g',YG,'var(--ser-gas)')+ser('pt',Y,'var(--ser-th)')+ser('pe',Y,'var(--ser-el)'); }
  if(TR.hoverX!==null&&HIST.length){
    const tt=t0+(TR.hoverX-m.l)/iw*(t1-t0); let bi=lo,bd=1e18; for(let i=lo;i<HIST.length;i++){ const dd=Math.abs(HIST[i].t-tt); if(dd<bd){bd=dd;bi=i;} }
    const h=HIST[bi], x=X(h.t).toFixed(1);
    s+='<line x1="'+x+'" x2="'+x+'" y1="'+m.t+'" y2="'+(m.t+ih)+'" stroke="var(--text-2)" stroke-width="1"/>';
    s+='<circle cx="'+x+'" cy="'+Y(h.pe).toFixed(1)+'" r="3.5" fill="var(--ser-el)"/><circle cx="'+x+'" cy="'+Y(h.pt).toFixed(1)+'" r="3.5" fill="var(--ser-th)"/><circle cx="'+x+'" cy="'+YG(h.g).toFixed(1)+'" r="3.5" fill="var(--ser-gas)"/>';
    const dt=new Date(h.t);
    setText($('#trend-ro'),pad(dt.getHours())+':'+pad(dt.getMinutes())+' · P ел. '+fmt(h.pe,0)+' кВт · P тепл. '+fmt(h.pt,0)+' кВт · газ '+fmt(h.g,0)+' м³/год');
  }
  svg.innerHTML=s; TR.last=Date.now(); TR.W=W; TR.m=m;
}
function initTrend(){
  const svg=$('#trend');
  svg.addEventListener('pointermove',e=>{ const r=svg.getBoundingClientRect(); const sx=(TR.W||r.width)/r.width; const x=(e.clientX-r.left)*sx; TR.hoverX=clamp(x,TR.m?TR.m.l:0,TR.W-(TR.m?TR.m.r:0)); drawTrend(); });
  svg.addEventListener('pointerleave',()=>{ TR.hoverX=null; setText($('#trend-ro'),'Наведіть вказівник на графік, щоб побачити значення.'); drawTrend(); });
  $$('#trend-seg button').forEach(b=>b.addEventListener('click',()=>{ TR.range=+b.dataset.range; $$('#trend-seg button').forEach(x=>x.setAttribute('aria-pressed',x===b?'true':'false')); drawTrend(); }));
  if(window.ResizeObserver) new ResizeObserver(()=>drawTrend()).observe($('#trend-wrap')); else window.addEventListener('resize',drawTrend);
}

/* ===== Синхроноскоп (розмітка) ===== */
function initSyncDial(){
  const P=(a,r)=>{ const q=a*Math.PI/180; return [(75+r*Math.sin(q)).toFixed(1),(75-r*Math.cos(q)).toFixed(1)]; };
  let t=''; for(let a=0;a<360;a+=15){ const l=a%90===0?10:(a%30===0?7:4); const p1=P(a,66-l),p2=P(a,66); t+='<line x1="'+p1[0]+'" y1="'+p1[1]+'" x2="'+p2[0]+'" y2="'+p2[1]+'"/>'; }
  $('#sync-ticks').innerHTML=t;
  const a=P(-12,64), b=P(12,64), c=P(12,48), d=P(-12,48);
  $('#sync-win').setAttribute('d','M'+a.join(' ')+' A64 64 0 0 1 '+b.join(' ')+' L'+c.join(' ')+' A48 48 0 0 0 '+d.join(' ')+' Z');
}

/* ===== Діагностика ===== */
let diagBuilt=false, cylRows=[], auxRows=[];
const AUX=[
  ['Маслосистема',()=>V.oilLvl<45?['Попередження','warn']:['Норма','ok'],()=>'картер '+fmt(V.oilLvl,1)+' %, p '+fmt(V.pOil,1)+' бар, t '+fmt(V.tOil,0)+' °C, '+fmt(V.oilCons,2)+' г/кВт·год'],
  ['Автодолив масла',()=>S.topup?['Працює','warn']:['Очікування',''],()=>'свіже '+fmt(V.oilFresh,0)+' %, відпрацьоване '+fmt(V.oilWaste,0)+' %'],
  ['Насос ВТ',()=>V.pHT.run?['Працює','ok']:['Зупинено',''],()=>fmt(V.pHT.f,1)+' Гц, '+fmt(V.pHT.I,1)+' А, p '+fmt(V.pExpHT,2)+' бар'],
  ['Насос опалення',()=>V.pHe.run?['Працює','ok']:['Зупинено',''],()=>fmt(V.pHe.f,1)+' Гц, '+fmt(V.pHe.I,1)+' А, '+fmt(V.flow,1)+' м³/год'],
  ['Насос НТ',()=>V.pLT.run?['Працює','ok']:['Зупинено',''],()=>fmt(V.pLT.f,1)+' Гц, '+fmt(V.pLT.I,1)+' А, '+fmt(V.tLTin,0)+'/'+fmt(V.tLTout,0)+' °C'],
  ['Змішувальний клапан зворотки',()=>V.cap<0.995?['Обмеження','warn']:(V.tRet>RET_SET-4?['Увага','warn']:['Норма','ok']),()=>'клапан '+fmt(V.mixPos,0)+' %, зворотка '+fmt(V.tRet,1)+' °C (уставка ≤ 70)'],
  ['Розширювальні баки',()=>['Норма','ok'],()=>'ВТ '+fmt(V.pExpHT,2)+', НТ '+fmt(V.pExpLT,2)+', опалення '+fmt(V.pExpH,2)+' бар'],
  ['Градирня ВТ',()=>S.fan>1?['Працює','ok']:['Очікування',''],()=>fmt(V.fan,0)+' %, '+fmt(V.qCooler,0)+' кВт'],
  ['Градирня НТ',()=>S.fanLT>1?['Працює','ok']:['Очікування',''],()=>fmt(V.fanLT,0)+' %, '+fmt(V.qLT,0)+' кВт'],
  ['Турбокомпресор / інтеркулер',()=>S.rpm>1200?['Працює','ok']:['Зупинено',''],()=>fmt(V.tcRpm,0)+' об/хв, p наддуву '+fmt(V.pBoost,2)+' бар, t суміші '+fmt(V.tAirOut,0)+' °C'],
  ['Каталізатор',()=>V.dpCat>18?['Увага','warn']:['Норма','ok'],()=>fmt(V.tE1,0)+' → '+fmt(V.tCatOut,0)+' °C, ΔP '+fmt(V.dpCat,1)+' мбар'],
  ['Заслінка вихлопу',()=>V.bypass>0.9?['В обхід','warn']:(V.bypass<0.1?['На ТО','ok']:['Перехід','warn']),()=>'привід '+fmt(V.bypass*100,0)+' %'],
  ['Аналіз викидів',()=>V.nox>250||V.co>300?['Перевищення','alarm']:['Норма','ok'],()=>'NOx '+fmt(V.nox,0)+'/250, CO '+fmt(V.co,0)+'/300 мг/нм³'],
  ['Газова рампа, valve proving',()=>S.gasP<1.5?['Аварія','alarm']:vpTxt(),()=>'p '+fmt(V.gasP,2)+' бар, ΔP фільтра '+fmt(V.dpFilter,0)+' мбар, YV1/YV2 '+(S.valves?'відкр.':'закр.')],
  ['Повітряний фільтр',()=>V.airDp>12?['Увага','warn']:['Норма','ok'],()=>'ΔP '+fmt(V.airDp,1)+' мбар (поріг 15)'],
  ['Вентиляція контейнера',()=>V.fanSup>1?['Працює','ok']:['Очікування',''],()=>'вент. '+fmt(V.fanSup,0)+' %, жалюзі '+fmt(V.louver,0)+' %, t '+fmt(V.tCont,1)+' °C'],
  ['Газоаналізатор',()=>V.lel>=20?['Аварія','alarm']:(V.lel>=10?['Попередження','warn']:['Норма','ok']),()=>fmt(V.lel,1)+' % НКПР (10 / 20 %)'],
  ['Пожежна сигналізація і гасіння',()=>S.fire?['Пожежа','alarm']:(S.ext==='ready'?['Норма','ok']:['Спрацювало','warn']),()=>'балон '+fmt(S.extLevel,0)+' %'],
  ['Контур аварійного стопу',()=>S.estopLoop?['Замкнений','ok']:['Розімкнений','alarm'],()=>'шафа, двері, зовнішня'],
  ['Захист ROCOF / вектор. зсув',()=>S.rocofFlag?['Спрацював','alarm']:['Норма','ok'],()=>'уставки df/dt 1,0 Гц/с, Δφ 12°'],
  ['Стартер, АКБ 24 В, ЗП',()=>V.batV<23.5?['Попередження','warn']:['Норма','ok'],()=>'АКБ '+fmt(V.batV,1)+' В, ЗП '+fmt(V.batI,1)+' А, пусків '+fmt(S.starts,0)],
  ['АРН, захисти генератора',()=>V.Ipct>105?['Увага','warn']:['Норма','ok'],()=>'збудження '+fmt(V.excI,1)+' А, cos φ '+fmt(V.cos,2)+', I/Iном '+fmt(V.Ipct,0)+' %'],
  ['Лічильники (TEDOM-1, тепло, газ)',()=>['Норма','ok'],()=>fmt(V.eTot,0)+' кВт·год · '+fmt(V.hmTot,1)+' Гкал · '+fmt(S.gasTotal,0)+' м³']
];
function buildDiag(){
  const tb=$('#cyl-table tbody');
  CYL.forEach((n,i)=>{
    const tr=document.createElement('tr'); if(i===8) tr.className='sep';
    const cells=[]; for(let k=0;k<7;k++){ const td=document.createElement('td'); if(k>0&&k<6) td.className='n'; tr.appendChild(td); cells.push(td); }
    cells[0].textContent=n; cells[0].style.fontWeight='600';
    tb.appendChild(tr); cylRows.push(cells);
  });
  const ab=$('#aux-table tbody');
  AUX.forEach(a=>{
    const tr=document.createElement('tr'); const c1=document.createElement('td'); c1.textContent=a[0]; const c2=document.createElement('td'); const bd=document.createElement('span'); c2.appendChild(bd); const c3=document.createElement('td'); c3.className='wrapc'; tr.append(c1,c2,c3); ab.appendChild(tr); auxRows.push({bd:bd,c3:c3,a:a});
  });
  diagBuilt=true;
}
function renderDiag(){
  if(S.tab!=='diag') return; if(!diagBuilt) buildDiag();
  const run=S.rpm>1200; let maxDev=0,maxK=0,tmin=1e9,tmax=-1e9;
  V.cyl.forEach((c,i)=>{
    const r=cylRows[i]; const ad=Math.abs(c.dev); maxDev=Math.max(maxDev,ad); maxK=Math.max(maxK,c.knock); tmin=Math.min(tmin,c.t); tmax=Math.max(tmax,c.t);
    setText(r[1],run?fmt(c.t,0):'—');
    const dc=ad>40?'alarm':ad>25?'warn':'ok'; setText(r[2],run?(c.dev>0?'+':'')+fmt(c.dev,0):'—'); setCls(r[2],'n '+(run?dc:''));
    const kc=c.knock>=60?'alarm':c.knock>=35?'warn':'ok'; setText(r[3],run?fmt(c.knock,0):'—'); setCls(r[3],'n '+(run?kc:''));
    setText(r[4],run?fmt(c.kv,1):'—'); setCls(r[4],'n '+(run&&c.kv>29?'warn':''));
    setText(r[5],run?fmt(c.ms,2):'—');
    const pp=c.plug/4000*100, pc=pp>=95?'alarm':pp>=80?'warn':'ok';
    setCls(r[6],pc); setText(r[6],(pp>=95?'Замінити':pp>=80?'Зношується':'Норма')+' · '+fmt(c.plug,0)+' год ('+fmt(pp,0)+' %)');
  });
  setText($('#diag-sum'),run?('середня '+fmt(V.cylAvg,0)+' °C · розкид '+fmt(tmax-tmin,0)+' К · макс. Δ '+fmt(maxDev,0)+' К · детонація до '+fmt(maxK,0)):'двигун не працює: показники недоступні');
  let bad=0;
  auxRows.forEach(o=>{ const r=o.a[1](); setText(o.bd,r[0]); setCls(o.bd,'bdg '+(r[1]||'')); setText(o.c3,o.a[2]()); if(r[1]==='warn'||r[1]==='alarm') bad++; });
  setText($('#aux-sum'),bad?('потребують уваги: '+bad):'усі системи в нормі');
}
function setTab(t){
  S.tab=t; const m=t==='main';
  $('#panel-main').hidden=!m; $('#panel-diag').hidden=m;
  $('#tab-main').setAttribute('aria-selected',m?'true':'false'); $('#tab-diag').setAttribute('aria-selected',m?'false':'true');
  $('#tab-main').tabIndex=m?0:-1; $('#tab-diag').tabIndex=m?-1:0;
  if(!m) renderDiag(); else { drawTrend(); }
}

/* ===== Обробники подій ===== */
function bindEvents(){
  $('#btn-start').addEventListener('click',cmdStart);
  $('#btn-stop').addEventListener('click',cmdStop);
  $('#btn-estop').addEventListener('click',cmdEStop);
  $('#btn-cb1').addEventListener('click',cbConfirm1);
  $('#btn-cb2').addEventListener('click',cbConfirm2);
  $('#btn-cbx').addEventListener('click',cbCancel);
  $('#btn-es-yes').addEventListener('click',esConfirm);
  $('#btn-es-no').addEventListener('click',()=>{ S.esAsk=false; setMsg('Аварійний стоп скасовано.',''); });
  $('#btn-ack').addEventListener('click',ackAll);
  $('#sel-mode').addEventListener('change',e=>{ S.mode=e.target.value; log('info','Режим змінено: «'+MODES[S.mode]+'»'); });
  const rng=$('#rng-sp'); rng.addEventListener('input',()=>{ S.setpoint=+rng.value; }); rng.addEventListener('change',()=>{ log('info','Ручна уставка навантаження: '+S.setpoint+' % ('+fmt(PN*S.setpoint/100,0)+' кВт)'); });
  const rc=$('#rng-cos'); rc.addEventListener('input',()=>{ S.cosSet=+rc.value; }); rc.addEventListener('change',()=>{ log('info','Уставка cos φ АРН: '+fmt(S.cosSet,2)+' (Q = '+fmt(PN*S.load*Math.tan(Math.acos(S.cosSet)),0)+' квар)'); });
  $('#sel-heat').addEventListener('change',e=>{ S.heatDir=e.target.value; log('info','Напрямок тепла: '+e.target.options[e.target.selectedIndex].text); });
  $('#sel-byp').addEventListener('change',e=>{ S.bypassMode=e.target.value; log('info','Заслінка вихлопу: '+e.target.options[e.target.selectedIndex].text); });
  $('#d-gas').addEventListener('click',()=>{ S.gasFault=true; log('warn','Імітація: падіння тиску газу на вході рампи'); setMsg('Імітація: низький тиск газу.','warn'); });
  $('#d-temp').addEventListener('click',()=>{ S.tempFault=true; log('warn','Імітація: перегрів ОЖ двигуна'); setMsg('Імітація: перегрів ОЖ.','warn'); });
  $('#d-grid').addEventListener('click',()=>{ S.grid=false; log('warn','Імітація: зникла мережа S2 0,4 кВ'); });
  $('#d-retn').addEventListener('click',()=>{ S.retFault=true; log('warn','Імітація: гаряча зворотка з котельні (t росте вище 70 °C)'); setMsg('Імітація: гаряча зворотка.','warn'); });
  $('#d-lel').addEventListener('click',()=>{ S.gasLeak=true; log('warn','Імітація: витік газу в контейнері (загазованість)'); setMsg('Імітація: загазованість.','warn'); });
  $('#d-fire').addEventListener('click',()=>{ S.fire=true; S.extT=0; log('warn','Імітація: пожежа в контейнері'); setMsg('Імітація: пожежа.','warn'); });
  $('#d-rocof').addEventListener('click',()=>{ S.rocofFlag=true; log('warn','Імітація: спрацював захист ROCOF / векторний зсув'); });
  $('#d-reset').addEventListener('click',resetAll);
  $('#ck-permit').addEventListener('change',e=>{ S.permit=e.target.checked; log(S.permit?'info':'warn','Дозвіл КГУ (chp_permit): '+(S.permit?'видано':'знято')); });
  $('#ck-remote').addEventListener('change',e=>{ S.remote=e.target.checked; log(S.remote?'info':'warn','ctl_remote: '+(S.remote?'«Дистанційне»':'«Місцеве» на щиті')); });
  $('#ck-rsw').addEventListener('change',e=>{ S.rsw=e.target.checked; log(S.rsw?'info':'warn','Дистанційні перемикання: '+(S.rsw?'дозволені':'заборонені')); });
  $('#btn-demo-jump').addEventListener('click',()=>{ if(S.tab!=='main') setTab('main'); const d=$('#demo'); d.open=true; d.scrollIntoView({block:'center',behavior:REDUCED?'auto':'smooth'}); $('#d-gas').focus({preventScroll:true}); });
  const themes=['auto','light','dark']; let ti=0; const tb=$('#btn-theme');
  tb.addEventListener('click',()=>{ ti=(ti+1)%3; const v=themes[ti]; if(v==='auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme',v); tb.textContent='Тема: '+(v==='auto'?'авто':v==='light'?'світла':'темна'); });
  $('#tab-main').addEventListener('click',()=>setTab('main')); $('#tab-diag').addEventListener('click',()=>setTab('diag'));
  $('.tabs').addEventListener('keydown',e=>{ if(e.key==='ArrowRight'||e.key==='ArrowLeft'){ const t=S.tab==='main'?'diag':'main'; setTab(t); $('#tab-'+t).focus(); e.preventDefault(); } });
}

