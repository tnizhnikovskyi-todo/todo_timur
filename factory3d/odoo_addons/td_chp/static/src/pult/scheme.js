/** @odoo-module **/
// UI-04 `scheme.js`: мнемосхема, 6 шарів з міжшаровими переходами («→ шар»). Порт `d_scheme.js` мокапу
// (сітка 8 px, один радіус кутів, однакові штуцери); значення — зі `store`, а не з моделі мокапу.

import { clamp, fmt, setCls, setText } from "./util";

export const LAYER_TABS = [
    ["ov", "Огляд"],
    ["ge", "Газ і електрика"],
    ["ht", "Тепло ВТ і опалення"],
    ["lt", "НТ і повітря"],
    ["ex", "Вихлоп і викиди"],
    ["sf", "Масло і безпека"],
];

/** `makeScheme(store, {valveTxt, vpTxt})` → {LAYERS, mount(host, onLayer), setLayer(id), render()}. */
export function makeScheme(store, { valveTxt, vpTxt }) {
    const S = store.S;
    const V = store.V;
    const th = () => store.th;
    const LAYERS=[];
    const PIPE_R=12;
    function parsePts(d){
      const pts=[]; let cx=0,cy=0; const re=/([MHV])\s*(-?\d+(?:\.\d+)?)\s*(-?\d+(?:\.\d+)?)?/g; let m;
      while((m=re.exec(d))){ if(m[1]==='M'){ cx=+m[2]; cy=+m[3]; } else if(m[1]==='H'){ cx=+m[2]; } else { cy=+m[2]; } pts.push([cx,cy]); }
      return pts.filter((p,i)=>i===0||p[0]!==pts[i-1][0]||p[1]!==pts[i-1][1]);
    }
    function roundPts(pts,r){
      let d='M'+pts[0][0]+' '+pts[0][1];
      for(let i=1;i<pts.length-1;i++){
        const a=pts[i-1],b=pts[i],c=pts[i+1]; const l1=Math.hypot(b[0]-a[0],b[1]-a[1]), l2=Math.hypot(c[0]-b[0],c[1]-b[1]); const rr=Math.min(r,l1/2,l2/2);
        const p1=[b[0]-(b[0]-a[0])/l1*rr,b[1]-(b[1]-a[1])/l1*rr], p2=[b[0]+(c[0]-b[0])/l2*rr,b[1]+(c[1]-b[1])/l2*rr];
        d+=' L'+p1[0].toFixed(1)+' '+p1[1].toFixed(1)+' Q'+b[0]+' '+b[1]+' '+p2[0].toFixed(1)+' '+p2[1].toFixed(1);
      }
      const l=pts[pts.length-1]; return d+' L'+l[0]+' '+l[1];
    }
    function layer(id,title,h,fn,y0){
      const L={id:id,title:title,vals:[],acts:[],bars:[],els:{},svg:''}; let out='', tail=''; const boxes=[], pipes=[];
      const uid=n=>'ly-'+id+'-'+n;
      const inside=(x,y)=>boxes.some(b=>x>=b.x-2&&x<=b.x+b.w+2&&y>=b.y&&y<=b.y+b.h+2);
      const cls=(base,x,y,halo)=>base+(halo===false||(halo===undefined&&inside(x,y))?'':' h');
      const A={
        box(n,x,y,w,hh,l,s,act,rx){
          boxes.push({x:x,y:y,w:w,h:hh});
          out+='<rect class="box" id="'+uid(n)+'" x="'+x+'" y="'+y+'" width="'+w+'" height="'+hh+'" rx="'+(rx||6)+'"/>';
          if(l) out+='<text class="tb" x="'+(x+w/2)+'" y="'+(y+(hh>=44?18:hh/2+5))+'" text-anchor="middle">'+l+'</text>';
          if(s) out+='<text class="tl" x="'+(x+w/2)+'" y="'+(y+34)+'" text-anchor="middle">'+s+'</text>';
          if(act) L.acts.push([uid(n),'act',act]);
        },
        reg(n,c,fn2){ L.acts.push([uid(n),c,fn2]); },
        hl(n,node){ L.acts.push([uid(n),'alm',()=>S.hl&&S.hl.node===node&&S.hl.kind==='alarm']); L.acts.push([uid(n),'wrn',()=>S.hl&&S.hl.node===node&&S.hl.kind==='warn']); },
        val(n,x,y,fn2,anchor,base,halo){
          const b=base||'tm';
          out+='<text class="'+cls(b,x,y,halo)+'" id="'+uid(n)+'" x="'+x+'" y="'+y+'"'+(anchor?' text-anchor="'+anchor+'"':'')+'>…</text>';
          L.vals.push([uid(n),fn2,b,cls(b,x,y,halo).indexOf(' h')>0]);
        },
        lab(x,y,t,anchor,c,halo){ out+='<text class="'+cls(c||'tl',x,y,halo)+'" x="'+x+'" y="'+y+'"'+(anchor?' text-anchor="'+anchor+'"':'')+'>'+t+'</text>'; },
        pipe(d,kind,flow,extra){
          const pts=parsePts(d); const thin=extra&&extra.indexOf('thin')>=0; pipes.push({pts:pts,kind:kind,thin:thin});
          const rd=roundPts(pts,PIPE_R);
          out+='<path class="pipe p-'+kind+(extra?' '+extra:'')+'" d="'+rd+'"/>'; if(flow) out+='<path class="fl '+flow+'" d="'+rd+'"/>';
        },
        nozzle(x,y,o,kind,thin){ tail+=nzl(x,y,o,kind,thin); },
        xlink(x,y,o,sgn,dir,kind,target,label,lx,ly,anchor,flow){
          const P=(a,b)=>o==='v'?[x+b,y+sgn*a]:[x+sgn*a,y+b];
          const pts=dir==='out'?[[16,-9],[28,-9],[38,0],[28,9],[16,9]]:[[16,0],[28,9],[38,9],[38,-9],[28,-9]];
          const poly=pts.map(p=>P(p[0],p[1]).map(v=>v.toFixed(1)).join(',')).join(' ');
          const d=dir==='out'?(o==='v'?'M'+x+' '+y+' V'+(y+sgn*16):'M'+x+' '+y+' H'+(x+sgn*16)):(o==='v'?'M'+x+' '+(y+sgn*16)+' V'+y:'M'+(x+sgn*16)+' '+y+' H'+x);
          A.pipe(d,kind,flow);
          const nm=(LAYER_TABS.find(t=>t[0]===target)||[0,target])[1];
          tail+='<g class="xl" data-target="'+target+'" tabindex="0" role="button" aria-label="Перейти на шар: '+nm+'"><polygon class="k-'+kind+'" points="'+poly+'"/><text class="tl h" x="'+lx+'" y="'+ly+'" text-anchor="'+(anchor||'start')+'">'+label+'</text></g>';
        },
        wire(d,w,dash){ const pts=parsePts(d); out+='<path class="wire" d="'+roundPts(pts,PIPE_R)+'"'+(w||dash?' style="'+(w?'stroke-width:'+w+';':'')+(dash?'stroke-dasharray:5 4':'')+'"':'')+'/>'; },
        valve(n,x,y,openFn){
          out+='<polygon class="valve" id="'+uid(n)+'" points="'+(x-11)+','+(y-9)+' '+(x+11)+','+(y+9)+' '+(x+11)+','+(y-9)+' '+(x-11)+','+(y+9)+'"/>';
          if(openFn) L.acts.push([uid(n),'open',openFn]);
        },
        pump(n,x,y,onFn){
          out+='<circle class="pump" id="'+uid(n)+'" cx="'+x+'" cy="'+y+'" r="16"/><path class="pump-t" d="M'+(x-6)+' '+(y-7)+' L'+(x+8)+' '+y+' L'+(x-6)+' '+(y+7)+' Z"/>';
          if(onFn) L.acts.push([uid(n),'on',onFn]);
        },
        fan(n,x,y,onFn){
          let b=''; [0,120,240].forEach(a=>{ b+='<path d="M'+x+' '+y+' L'+x+' '+(y-13)+' Q'+(x+9)+' '+(y-10)+' '+(x+5)+' '+(y-1)+' Z" transform="rotate('+a+' '+x+' '+y+')"/>'; });
          out+='<g class="fan" id="'+uid(n)+'"><circle cx="'+x+'" cy="'+y+'" r="16" fill="none" stroke="var(--text-2)" stroke-width="1.5"/>'+b+'</g>';
          if(onFn) L.acts.push([uid(n),'on',onFn]);
        },
        circ(n,x,y,r,act){ boxes.push({x:x-r,y:y-r,w:2*r,h:2*r}); out+='<circle class="box" id="'+uid(n)+'" cx="'+x+'" cy="'+y+'" r="'+r+'"/>'; if(act) L.acts.push([uid(n),'act',act]); },
        bar(n,x,y,w,hh,fn2){
          out+='<rect class="bar-bg" x="'+x+'" y="'+y+'" width="'+w+'" height="'+hh+'" rx="3"/><rect class="bar-fg" id="'+uid(n)+'" x="'+x+'" y="'+y+'" width="0" height="'+hh+'" rx="3"/>';
          L.bars.push([uid(n),w,fn2]);
        },
        raw(s){ out+=s; }
      };
      function nzl(x,y,o,kind,thin){
        const a=thin?6:7, b=thin?11:16;
        const w=o==='h'?a:b, hh=o==='h'?b:a;
        return '<rect class="nz k-'+kind+'" x="'+(x-w/2)+'" y="'+(y-hh/2)+'" width="'+w+'" height="'+hh+'" rx="1.5"/>';
      }
      fn(A);
      // автоматичні штуцери там, де кінець труби впирається в край блока
      const seen={};
      pipes.forEach(p=>{
        [p.pts[0],p.pts[p.pts.length-1]].forEach(pt=>{
          boxes.forEach(b=>{
            const px=pt[0], py=pt[1]; let o=null;
            if((Math.abs(px-b.x)<=1||Math.abs(px-(b.x+b.w))<=1)&&py>b.y+3&&py<b.y+b.h-3) o='h';
            else if((Math.abs(py-b.y)<=1||Math.abs(py-(b.y+b.h))<=1)&&px>b.x+3&&px<b.x+b.w-3) o='v';
            if(o&&b.w!==2*b.h||o&&true){ const k=px+','+py; if(!seen[k]){ seen[k]=1; tail+=nzl(px,py,o,p.kind,p.thin); } }
          });
        });
      });
      L.svg='<svg class="mn" viewBox="0 '+(y0||0)+' 1000 '+(h-(y0||0))+'" role="img" aria-label="Мнемосхема: '+title+'">'+out+tail+'</svg>';
      LAYERS.push(L); return L;
    }
    const lvlCls=(v,w,a)=>v>=a?'alarm':(v>=w?'warn':'ok');

    function buildLayers(){
      /* ---------- Огляд ---------- */
      layer('ov','Огляд',544,A=>{
        // газ
        A.pipe('M104 96 H296','gas','g');
        A.box('grp',16,64,88,64,'ГРП','газ ~2,1 бар');
        A.valve('yv1',168,96,()=>S.valves); A.valve('yv2',232,96,()=>S.valves);
        A.lab(168,76,'YV1','middle'); A.lab(232,76,'YV2','middle');
        A.val('gasp',112,124,()=>'p '+fmt(V.gasP,2)+' бар','start'); A.val('gasq',200,124,()=>fmt(V.gas,0)+' м³/год','start');
        A.box('eng',296,48,160,112,'Двигун ГПД','V16 · газопоршневий',()=>S.rpm>50); A.hl('eng','engine'); A.val('rpm',376,148,()=>fmt(V.rpm,0)+' об/хв','middle');
        // генератор і електрика
        A.wire('M456 96 H504',6);
        A.circ('gen',544,96,40,()=>S.rpm>50); A.hl('gen','generator'); A.raw('<text class="tb" x="544" y="104" text-anchor="middle" style="font-size:22px">G</text>');
        A.lab(544,44,'генератор 0,4 кВ','middle'); A.val('pel',544,156,()=>fmt(V.pel,0)+' кВт','middle');
        A.wire('M584 96 H680',4); A.raw('<rect class="qf closed" id="ly-ov-qf" x="680" y="80" width="32" height="32" rx="3"/>'); A.reg('qf','closed',()=>S.qf); A.hl('qf','qf');
        A.lab(696,68,'QF-CHP','middle','tb'); A.val('qfs',696,132,()=>S.qf?'увімкнено':'вимкнено','middle');
        A.wire('M712 96 H784',4); A.raw('<path class="bus" d="M784 48 V144"/>');
        A.lab(800,64,'Шина S2','start','tb'); A.lab(800,82,'ГРЩ 0,4 кВ','start'); A.val('u',800,106,()=>fmt(V.U,0)+' В','start'); A.val('f',800,124,()=>fmt(V.f,2)+' Гц','start');
        // вихлоп: двигун → каталізатор → ТО вихлопу
        A.pipe('M296 144 H232 V472 H296','exh','e');
        A.box('cat',200,344,64,48,'Каталіз.',null,()=>S.rpm>200); A.hl('cat','cat'); A.val('dpcat',232,382,()=>fmt(V.dpCat,0)+' мбар','middle');
        A.nozzle(232,344,'v','exh'); A.nozzle(232,392,'v','exh');
        A.lab(216,308,'вихлоп до ТО','end'); A.val('t1',216,326,()=>fmt(V.tCatOut,0)+' °C','end');
        // ОЖ: двигун ↔ пластинчастий ТО
        A.pipe('M336 160 V216','sup','h'); A.pipe('M416 216 V160','ret','h');
        A.val('tj',432,194,()=>'ОЖ '+fmt(V.tJo,0)+' / '+fmt(V.tJi,0)+' °C','start');
        A.box('phe',296,216,160,112,'Пластинчастий ТО','ОЖ → мережа',()=>V.flow>0.5); A.val('qphe',376,284,()=>fmt(V.qPhe,0)+' кВт','middle');
        // мережева вода: зворотка → ТО1 → проміжна → ТО2 → подача
        A.pipe('M800 304 H456','ret','h'); A.pipe('M744 304 V328','ret','c'); A.pipe('M608 328 V304','ret','c'); A.valve('mv',744,304,()=>V.mixPos>5); A.lab(744,278,'клапан зворотки','middle');
        A.lab(472,292,'зворотка','start'); A.val('tret',536,292,()=>fmt(V.tRet,1)+' °C','start');
        A.pipe('M376 328 V416','sup','h'); A.lab(392,364,'проміжна','start'); A.val('tmid',392,382,()=>fmt(V.tMid,1)+' °C','start');
        A.box('he',296,416,160,72,'ТО вихлопних газів',null,()=>V.flow>0.5); A.val('qexh',376,468,()=>fmt(V.qExh,0)+' кВт','middle');
        A.pipe('M456 432 H800','sup','h');
        A.lab(472,420,'подача','start'); A.val('tsup',520,420,()=>fmt(V.tSup,1)+' °C','start');
        A.box('ck',584,328,176,80,'Сухі градирні','dump radiator',()=>S.fan>1);
        A.fan('f1',624,386,()=>S.fan>1); A.fan('f2',664,386,()=>S.fan>1); A.val('fp',744,380,()=>fmt(V.fan,0)+' %','end'); A.val('fq',744,398,()=>fmt(V.qCooler,0)+' кВт','end','tl');
        A.box('bo',800,272,176,176,'Котельня','контур опалення',()=>V.qBoiler>5); A.val('qb',888,368,()=>fmt(V.qBoiler,0)+' кВт','middle'); A.val('fl',888,388,()=>fmt(V.flow,1)+' м³/год','middle','tl');
        // вихлоп після ТО
        A.pipe('M456 472 H528','exh','e'); A.box('mf',528,448,96,48,'Глушник',null,()=>S.rpm>200,12);
        A.pipe('M624 472 H688','exh','e'); A.box('st',688,448,24,72,null,null,()=>S.rpm>200,3); A.lab(700,536,'Труба','middle','tb');
        A.lab(492,512,'гази після ТО','middle'); A.val('t2',492,528,()=>fmt(V.tE2,0)+' °C','middle');
      });
      /* ---------- Газ і електрика ---------- */
      layer('ge','Газ і електрика',480,A=>{
        A.lab(16,24,'Газова рампа та подача газу','start','tb');
        A.pipe('M104 96 H768','gas','g'); A.box('grp',16,64,88,64,'ГРП','вхід газу');
        const nm_=(x,t)=>A.lab(x,60,t,'middle');
        A.valve('bv',144,96,()=>true); nm_(144,'Кран'); A.val('bvv',144,132,()=>'відкр.','middle');
        A.box('flt',192,80,48,32,'',null,()=>S.valves); nm_(216,'Фільтр'); A.val('fltv',216,132,()=>fmt(V.dpFilter,0)+' мбар','middle');
        A.box('reg',264,80,48,32,'',null,()=>S.valves); nm_(288,'Регулятор'); A.val('regv',288,132,()=>fmt(V.gasReg,0)+' мбар','middle');
        A.box('psl',336,80,48,32,'',null); nm_(360,'PSL / PSH'); A.val('pslv',360,132,()=>V.gasP<th().gas_min_bar?['PSL!','alarm']:['норма','ok'],'middle');
        A.valve('yv1',440,96,()=>S.valves); nm_(440,'YV1'); A.valve('yv2',512,96,()=>S.valves); nm_(512,'YV2');
        A.val('yvv',476,132,()=>valveTxt()[0],'middle'); A.lab(476,152,'valve proving','middle'); A.val('vp',476,168,()=>vpTxt(),'middle');
        A.box('gm',568,72,64,48,'',null,()=>S.valves); nm_(600,'Лічильник газу'); A.val('gmv',600,140,()=>fmt(V.gas,0)+' м³/год','middle'); A.val('gmt',600,156,()=>fmt(S.gasTotal,0)+' м³','middle','tl');
        A.box('thr',672,72,64,48,'',null,()=>S.valves); nm_(704,'Змішувач'); A.val('thrv',704,140,()=>fmt(V.thr,0)+' %','middle');
        A.box('eng',768,48,160,96,'Двигун ГПД V16','газопоршневий',()=>S.rpm>50); A.val('rpm',848,132,()=>fmt(V.rpm,0)+' об/хв','middle');
        A.lab(16,208,'Електрика: генератор → QF-CHP → шина S2','start','tb');
        A.wire('M848 144 V240',6); A.circ('gen',848,280,40,()=>S.rpm>50);
        A.raw('<text class="tb" x="848" y="288" text-anchor="middle" style="font-size:22px">G</text>'); A.val('pel',832,336,()=>fmt(V.pel,0)+' кВт','end');
        A.lab(832,352,'0,4 кВ, 50 Гц','end');
        A.wire('M888 280 H904',3); A.box('avr',904,248,80,64,'АРН',null,()=>S.rpm>1200); A.val('avr1',944,284,()=>'Iзб '+fmt(V.excI,1)+' А','middle'); A.val('avr2',944,300,()=>'cos φ '+fmt(V.cos,2),'middle');
        A.wire('M848 320 V368 H880',3); A.box('prot',880,344,104,48,'Захисти ген.',null); A.val('prot1',932,382,()=>'норма','middle','tm ok');
        A.wire('M808 280 H712',4); A.raw('<rect class="qf closed" id="ly-ge-qf" x="680" y="264" width="32" height="32" rx="3"/>'); A.reg('qf','closed',()=>S.qf);
        A.lab(728,262,'QF-CHP','start','tb'); A.val('qfs',696,316,()=>S.qf?'увімкнено':'вимкнено','middle');
        A.box('roc',632,168,128,48,'Захист ROCOF',null); A.reg('roc','alm',()=>S.rocofFlag);
        A.val('roc1',696,206,()=>S.rocofFlag?['СПРАЦЮВАВ','alarm']:('df/dt '+fmt(V.dfdt,2)+' Гц/с'),'middle'); A.wire('M696 216 V264',2,true);
        A.wire('M680 280 H624',4); A.box('mtr',544,256,80,48,'Лічильник','TEDOM-1'); A.val('mt1',584,328,()=>fmt(V.eTot,0)+' кВт·год','middle');
        A.wire('M544 280 H432',4); A.raw('<path class="bus" d="M432 224 V336"/>'); A.lab(432,212,'Шина S2','middle','tb'); A.lab(424,356,'ГРЩ 0,4 кВ','end');
        A.val('u',416,276,()=>fmt(V.U,0)+' В','end'); A.val('f',416,294,()=>fmt(V.f,2)+' Гц','end');
        A.wire('M432 336 V400',4); A.lab(448,392,'Живлення 24 В пост. струму: зарядний → АКБ → стартер','start','tb');
        A.box('chg',400,400,112,56,'Зарядний',null); A.val('chg1',456,442,()=>fmt(V.batI,1)+' А','middle');
        A.wire('M512 428 H568',5); A.box('bat',568,400,112,56,'АКБ 24 В',null); A.val('bat1',624,442,()=>[fmt(V.batV,1)+' В',V.batV<th().bat_min_v?'alarm':'ok'],'middle');
        A.wire('M680 428 H736',5); A.box('stm',736,400,112,56,'Стартер',null,()=>S.starter); A.val('stm1',792,442,()=>fmt(V.starterI,0)+' А','middle'); A.lab(792,472,'на вінець маховика','middle');
      });
      /* ---------- Тепло ВТ і опалення ---------- */
      layer('ht','Тепло ВТ і опалення',448,A=>{
        A.lab(16,24,'Контур ВТ: ОЖ двигуна (~90/80 °C)','start','tb'); A.lab(496,24,'Мережевий контур опалення','start','tb');
        A.box('eng',16,56,128,112,'Двигун ВТ','контур ОЖ',()=>S.rpm>50); A.val('tj',80,152,()=>fmt(V.tJo,0)+' / '+fmt(V.tJi,0)+' °C','middle');
        A.box('oc',16,224,128,64,'Маслоохолоджувач',null,()=>S.rpm>50); A.val('oc1',80,268,()=>fmt(V.tOil,0)+' → '+fmt(V.tOilOut,0)+' °C','middle');
        A.xlink(144,240,'h',1,'in','oil','sf','← Масло',190,244,'start','o'); A.xlink(144,272,'h',1,'out','oil','sf','→ Масло',190,276,'start','o');
        A.pipe('M48 168 V224','sup','h','thin'); A.pipe('M112 224 V168','ret','h','thin');
        A.pipe('M144 88 H304','sup','h'); A.pipe('M304 136 H144','ret','h');
        A.pump('pht',224,88,()=>V.pHT.run); A.lab(224,64,'Насос ВТ','middle'); A.val('pht1',224,118,()=>fmt(V.pHT.f,0)+' Гц · '+fmt(V.pHT.I,0)+' А','middle');
        A.box('xht',264,184,64,32,'',null); A.val('xht1',296,205,()=>fmt(V.pExpHT,1)+' бар','middle'); A.lab(296,232,'бак ВТ','middle'); A.pipe('M296 184 V136','sup',null,'thin');
        A.box('phe',304,56,128,112,'Пластинчастий ТО','ОЖ → мережа',()=>V.flow>0.5); A.val('phe1',368,152,()=>fmt(V.qPhe,0)+' кВт','middle');
        A.pipe('M432 88 H512','sup','h'); A.lab(472,72,'проміжна','middle'); A.val('tm',472,116,()=>fmt(V.tMid,0)+' °C','middle');
        A.box('he',512,56,112,112,'ТО вих. газів',null,()=>V.flow>0.5); A.val('he1',568,112,()=>fmt(V.qExh,0)+' кВт','middle'); A.val('he2',568,132,()=>'в обхід '+fmt(S.bypass*100,0)+' %','middle','tl');
        A.xlink(552,168,'v',1,'in','exh','ex','← Вихлоп',540,200,'end','e'); A.xlink(584,168,'v',1,'out','exh','ex','→ Вихлоп',596,200,'start','e');
        A.pipe('M624 88 H664','sup','h'); A.box('hm',664,56,88,80,'Лічильник',null); A.lab(708,90,'тепла','middle','tb'); A.val('hm1',708,108,()=>fmt(V.hmP,0)+' кВт','middle'); A.val('hm2',708,126,()=>fmt(V.hmTot,0)+' Гкал','middle','tl');
        A.pipe('M752 88 H816','sup','h'); A.lab(784,72,'подача','middle'); A.val('ts',784,116,()=>fmt(V.tSup,1)+' °C','middle');
        A.box('bo',816,56,168,112,'Котельня','контур опалення',()=>V.qBoiler>5); A.val('bo1',900,132,()=>fmt(V.qBoiler,0)+' кВт','middle'); A.val('bo2',900,152,()=>fmt(V.flow,1)+' м³/год','middle','tl');
        A.pipe('M900 168 V224 H368 V168','ret','h');
        A.pump('phe_p',688,224,()=>V.pHe.run); A.lab(688,256,'Насос опалення','middle'); A.val('ph1',688,272,()=>fmt(V.pHe.f,0)+' Гц · '+fmt(V.pHe.I,0)+' А','middle');
        A.box('xh',432,248,72,32,'',null); A.val('xh1',468,269,()=>fmt(V.pExpH,1)+' бар','middle'); A.lab(468,300,'бак опалення','middle'); A.pipe('M468 248 V224','ret',null,'thin');
        A.valve('mv',832,224,()=>V.mixPos>5); A.lab(876,204,'Змішувальний клапан','end','tb');
        A.val('mv1',848,248,()=>'клапан '+fmt(V.mixPos,0)+' %','start'); A.val('mv2',848,266,()=>['до клапана '+fmt(V.tRetRaw,1)+' °C',V.tRetRaw>75?'alarm':V.tRetRaw>65?'warn':''],'start'); A.val('mv3',848,284,()=>['на вході ТО '+fmt(V.tRet,1)+' °C',V.tRet>th().ret_set_c?'alarm':V.tRet>th().ret_set_c-4?'warn':'ok'],'start'); A.lab(848,302,'уставка ≤ '+fmt(th().ret_set_c,0)+' °C','start');
        A.pipe('M832 232 V368 H800','ret','c'); A.pipe('M608 368 H576 V224','ret','c');
        A.box('ck',608,320,192,96,'Сухі градирні ВТ',null,()=>S.fan>1);
        A.fan('f1',664,380,()=>S.fan>1); A.fan('f2',712,380,()=>S.fan>1); A.val('ck1',784,376,()=>fmt(V.fan,0)+' %','end'); A.val('ck2',784,394,()=>fmt(V.qCooler,0)+' кВт','end','tl');
        A.lab(16,344,'ВТ-контур: насос ВТ → пластинчастий ТО (замкнений на двигун).','start');
        A.lab(16,364,'Мережа: зворотка → пластинчастий ТО → ТО вихлопних газів → подача.','start');
        A.lab(16,384,'Зворотка > '+fmt(th().ret_set_c,0)+' °C: клапан частину потоку відводить на градирню.','start');
      });
      /* ---------- НТ і повітря ---------- */
      layer('lt','НТ і повітря',488,A=>{
        A.lab(16,24,'Повітря на горіння: фільтр → турбокомпресор → охолоджувач суміші → двигун','start','tb');
        A.pipe('M144 104 H256','air','a'); A.pipe('M384 104 H472','air','a'); A.pipe('M616 104 H736','air','a');
        A.box('af',16,64,128,80,'Повітряний фільтр',null,()=>S.rpm>200); A.val('af1',80,124,()=>'ΔP '+fmt(V.airDp,1)+' мбар','middle');
        A.box('tc',256,64,128,80,'Турбокомпресор','компресор',()=>S.rpm>1200); A.val('tc1',320,120,()=>fmt(V.tcRpm/1000,0)+' тис. об/хв','middle'); A.val('tc2',320,136,()=>'p '+fmt(V.pBoost,2)+' бар','middle','tl');
        A.box('ic',472,64,144,80,'Охолоджувач суміші','інтеркулер',()=>S.rpm>200); A.val('ic1',544,124,()=>fmt(V.tAirIn,0)+' → '+fmt(V.tAirOut,0)+' °C','middle');
        A.box('en',736,64,144,80,'Двигун (впуск)','газ + повітря',()=>S.rpm>50); A.val('en1',808,124,()=>'p суміші '+fmt(V.pMix,2)+' бар','middle');
        A.lab(16,192,'Контур НТ (~40/45 °C): окремий від ВТ','start','tb');
        A.pipe('M552 144 V256 H640','lt','l'); A.pipe('M696 296 V352 H504 V144','lt','l');
        A.box('cl',640,216,192,80,'Градирня НТ',null,()=>S.fanLT>1); A.fan('f1',704,266,()=>S.fanLT>1); A.fan('f2',752,266,()=>S.fanLT>1); A.val('cl1',816,262,()=>fmt(V.fanLT,0)+' %','end'); A.val('cl2',816,280,()=>fmt(V.qLT,0)+' кВт','end','tl');
        A.pump('plt',600,352,()=>V.pLT.run); A.lab(600,328,'Насос НТ','middle'); A.val('plt1',600,386,()=>fmt(V.pLT.f,0)+' Гц · '+fmt(V.pLT.I,1)+' А','middle');
        A.box('xlt',424,232,64,32,'',null); A.val('xlt1',456,253,()=>fmt(V.pExpLT,1)+' бар','middle'); A.lab(456,224,'бак НТ','middle'); A.pipe('M488 248 H504','lt',null,'thin');
        A.val('lt1',488,176,()=>'НТ '+fmt(V.tLTin,0)+' → '+fmt(V.tLTout,0)+' °C','end'); A.val('lt2',488,192,()=>fmt(V.flowLT,1)+' м³/год','end','tl');
        A.lab(16,412,'Вентиляція контейнера','start','tb');
        A.pipe('M128 448 H160','air','a','thin'); A.pipe('M288 448 H336','air','a','thin'); A.pipe('M664 448 H712','air','a','thin'); A.pipe('M840 448 H872','air','a','thin');
        A.box('lv1',16,424,112,48,'Жалюзі',null); A.val('lv1v',72,464,()=>fmt(V.louver,0)+' % відкр.','middle','tl');
        A.box('fs',160,424,128,48,'Вент. припливний',null,()=>S.fanSup>1); A.val('fsv',224,464,()=>fmt(V.fanSup,0)+' %','middle','tl');
        A.box('cn',336,416,328,64,'Контейнер',null); A.val('cn1',500,462,()=>['t '+fmt(V.tCont,1)+' °C',V.tCont>45?'alarm':V.tCont>38?'warn':'ok'],'middle');
        A.box('fe',712,424,128,48,'Вент. витяжний',null,()=>S.fanExh>1); A.val('fev',776,464,()=>fmt(V.fanExh,0)+' %','middle','tl');
        A.box('lv2',872,424,112,48,'Жалюзі',null);
      });
      /* ---------- Вихлоп і викиди ---------- */
      layer('ex','Вихлоп і викиди',464,A=>{
        A.lab(16,24,'Вихлоп: двигун → турбіна → каталізатор → заслінка → ТО → глушник → труба','start','tb');
        A.pipe('M128 200 H176','exh','e'); A.pipe('M272 200 H320','exh','e'); A.pipe('M448 200 H592','exh','e');
        A.pipe('M520 200 V112 H816 V168','exh','b','dash'); A.lab(668,104,'байпас (в обхід ТО)','middle');
        A.pipe('M720 200 H768','exh','e'); A.pipe('M864 200 H904','exh','e'); A.pipe('M916 312 V344','exh',null,'thin');
        A.xlink(632,248,'v',1,'in','sup','ht','← Тепло ВТ',616,282,'end','h'); A.xlink(680,248,'v',1,'out','sup','ht','→ Тепло ВТ',696,282,'start','h');
        A.box('en',16,152,112,96,'Двигун',null,()=>S.rpm>50); A.lab(72,196,'перед турбіною','middle'); A.val('en1',72,216,()=>fmt(V.tTurb,0)+' °C','middle');
        A.box('tb',176,168,96,64,'Турбіна ТК',null,()=>S.rpm>1200); A.val('tb1',224,214,()=>fmt(V.tE1,0)+' °C','middle');
        A.box('ct',320,152,128,96,'Каталізатор','окислювальний',()=>S.rpm>200); A.hl('ct','cat'); A.val('ct1',384,214,()=>fmt(V.tE1,0)+' → '+fmt(V.tCatOut,0)+' °C','middle'); A.val('ct2',384,232,()=>'ΔP '+fmt(V.dpCat,1)+' мбар','middle','tl');
        A.valve('dmp',520,200,()=>S.bypass<0.5); A.lab(532,188,'Заслінка','start'); A.val('dmp1',520,232,()=>V.bypass>0.9?['в обхід','warn']:(V.bypass<0.1?['на ТО','ok']:['перехід','warn']),'middle');
        A.box('he',592,152,128,96,'ТО вих. газів',null,()=>V.flow>0.5&&S.bypass<0.9); A.val('he1',656,214,()=>'Q '+fmt(V.qExh,0)+' кВт','middle'); A.val('he2',656,232,()=>'після '+fmt(V.tE2,0)+' °C','middle','tl');
        A.box('mf',768,168,96,64,'Глушник',null,()=>S.rpm>200,12);
        A.box('st',904,72,24,240,null,null,()=>S.rpm>200,3); A.lab(916,60,'Труба','middle','tb'); A.val('st1',896,330,()=>fmt(V.tStack,0)+' °C','end');
        A.val('wi',616,298,()=>fmt(V.tMid,0)+' °C','end'); A.val('wo',696,298,()=>fmt(V.tSup,0)+' °C','start');
        A.lab(16,280,'Окислювальний каталізатор знижує CO; SCR (NOx) у комплектації немає.','start');
        A.lab(16,300,'Заслінка «на ТО»: гази віддають тепло воді; «в обхід»: гарячі гази йдуть у трубу.','start');
        A.box('an',576,344,352,104,'Аналіз викидів (на трубі)',null);
        A.lab(592,388,'NOx','start'); A.bar('nox',632,378,176,12,()=>[V.nox/th().nox_limit,lvlCls(V.nox,th().nox_limit*0.9,th().nox_limit)]); A.val('nox1',824,388,()=>fmt(V.nox,0)+' / '+fmt(th().nox_limit,0),'start');
        A.lab(592,412,'CO','start'); A.bar('co',632,402,176,12,()=>[V.co/th().co_limit,lvlCls(V.co,th().co_limit*0.9,th().co_limit)]); A.val('co1',824,412,()=>fmt(V.co,0)+' / '+fmt(th().co_limit,0),'start');
        A.val('o2',592,438,()=>'O₂ '+fmt(V.o2,1)+' % · мг/нм³ на 5 % O₂ · CO до каталізатора '+fmt(V.coRaw,0),'start','tl');
      });
      /* ---------- Масло і безпека ---------- */
      layer('sf','Масло і безпека',480,A=>{
        A.lab(16,88,'Маслосистема','start','tb');
        A.pipe('M160 160 H320','oil','o'); A.pipe('M448 160 H504','oil','o'); A.pipe('M576 160 H640','oil','o'); A.pipe('M712 208 V248 H144 V200','oil','o');
        A.pipe('M64 296 V200','oil','o','thin'); A.pipe('M104 200 V272 H188 V296','oil',null,'thin dash');
        A.box('sump',16,128,144,72,'Картер',null,()=>S.rpm>50); A.val('lv',88,168,()=>fmt(V.oilLvl,1)+' %','middle'); A.bar('lvb',28,180,120,8,()=>[V.oilLvl/100,V.oilLvl<45?'alarm':V.oilLvl<60?'warn':'ok']);
        A.pump('op',240,160,()=>S.rpm>50); A.lab(240,136,'Маслонасос','middle');
        A.box('oc',320,128,128,72,'Маслоохолоджувач',null,()=>S.rpm>50); A.val('oc1',384,176,()=>fmt(V.tOil,0)+' → '+fmt(V.tOilOut,0)+' °C','middle');
        A.xlink(360,128,'v',-1,'in','sup','ht','← Тепло ВТ',350,100,'end','h'); A.xlink(408,128,'v',-1,'out','ret','ht','→ Тепло ВТ',418,100,'start','h');
        A.box('of',504,136,72,48,'Фільтр',null); A.val('of1',540,206,()=>'ΔP '+fmt(V.dpOilF,2)+' бар','middle','tl');
        A.box('en',640,112,144,96,'Двигун',null,()=>S.rpm>50); A.val('en1',712,160,()=>'p '+fmt(V.pOil,1)+' бар','middle'); A.val('en2',712,180,()=>'t '+fmt(V.tOil,0)+' °C','middle');
        A.val('cons',320,236,()=>'витрата масла '+fmt(V.oilCons,2)+' г/кВт·год','start','tl');
        A.valve('tu',64,248,()=>S.topup); A.lab(16,240,'долив','start'); A.lab(116,264,'зливання','start');
        A.box('fr',16,296,104,104,'Свіже масло',null); A.bar('frb',28,356,80,10,()=>[V.oilFresh/100,V.oilFresh<20?'warn':'ok']); A.val('fr1',68,386,()=>fmt(V.oilFresh,0)+' %','middle');
        A.box('ws',136,296,104,104,'Відпрацьоване',null); A.bar('wsb',148,356,80,10,()=>[V.oilWaste/100,V.oilWaste>80?'warn':'ok']); A.val('ws1',188,386,()=>fmt(V.oilWaste,0)+' %','middle');
        A.lab(272,288,'Безпека','start','tb');
        A.box('gd',272,304,168,120,'Газоаналізатор',null); A.reg('gd','alm',()=>V.lel>=th().lel_alarm_pct); A.reg('gd','wrn',()=>V.lel>=th().lel_warn_pct&&V.lel<th().lel_alarm_pct);
        A.val('gd1',288,346,()=>[fmt(V.lel,1)+' % НКПР',lvlCls(V.lel,th().lel_warn_pct,th().lel_alarm_pct)],'start'); A.bar('gdb',288,360,136,10,()=>[V.lel/30,lvlCls(V.lel,th().lel_warn_pct,th().lel_alarm_pct)]);
        A.raw('<path d="M333.3 356 V374 M378.7 356 V374" stroke="var(--text)" stroke-width="1.5"/>'); A.lab(288,392,'пороги '+fmt(th().lel_warn_pct,0)+' / '+fmt(th().lel_alarm_pct,0)+' %','start'); A.val('gd2',288,412,()=>V.lel>=th().lel_alarm_pct?['аварія','alarm']:V.lel>=th().lel_warn_pct?['попередження','warn']:['норма','ok'],'start');
        A.box('fi',448,304,168,120,'Пожежа та гасіння',null); A.reg('fi','alm',()=>S.fire);
        A.val('fi1',464,346,()=>S.fire?['ПОЖЕЖА','alarm']:['сигналізація: норма','ok'],'start'); A.val('fi2',464,366,()=>S.ext==='ready'?['гасіння: готове','ok']:(S.ext==='release'?['гасіння: випуск','alarm']:['гасіння: спрацювало','warn']),'start');
        A.lab(464,388,'балон з речовиною','start'); A.bar('fib',464,396,136,10,()=>[S.extLevel/100,S.extLevel<30?'warn':'ok']);
        A.pipe('M532 424 V448','fire',null,'thin'); A.box('fn',468,448,128,24,'форсунки гасіння',null);
        A.box('es',624,304,168,120,'Аварійний стоп',null); A.reg('es','alm',()=>!S.estopLoop);
        A.val('es1',640,346,()=>S.estopLoop?['контур замкнений','ok']:['контур розімкнений','alarm'],'start'); A.lab(640,368,'кнопки: шафа, двері,','start'); A.lab(640,384,'зовнішня','start');
        A.box('rc',800,304,168,120,'Захист мережі ROCOF',null); A.reg('rc','alm',()=>S.rocofFlag);
        A.val('rc1',816,346,()=>S.rocofFlag?['СПРАЦЮВАВ','alarm']:['норма','ok'],'start'); A.val('rc2',816,368,()=>'df/dt '+fmt(V.dfdt,2)+' / 1,0 Гц/с','start','tl'); A.val('rc3',816,386,()=>'зсув '+fmt(V.dphi,1)+' / 12°','start','tl'); A.val('rc4',816,406,()=>S.qf?'QF-CHP: увімкнено':'QF-CHP: вимкнено','start','tl');
      },64);
    }

    let host = null;
    let current = "ov";
    function mount(el, onLayer) {
        host = el;
        buildLayers();
        host.textContent = "";
        LAYERS.forEach((L) => {
            const d = document.createElement("div");
            d.className = "layer";
            d.id = "ly-" + L.id;
            d.hidden = L.id !== current;
            d.innerHTML = L.svg;
            host.appendChild(d);
            L.root = d;
        });
        const go = (id) => {
            setLayer(id);
            if (onLayer) {
                onLayer(id);
            }
        };
        const onClick = (e) => {
            const g = e.target.closest && e.target.closest(".xl");
            if (g) {
                go(g.dataset.target);
            }
        };
        const onKey = (e) => {
            if (e.key === "Enter" || e.key === " ") {
                const g = e.target.closest && e.target.closest(".xl");
                if (g) {
                    e.preventDefault();
                    go(g.dataset.target);
                }
            }
        };
        host.addEventListener("click", onClick);
        host.addEventListener("keydown", onKey);
        return () => {
            host.removeEventListener("click", onClick);
            host.removeEventListener("keydown", onKey);
        };
    }
    function setLayer(id) {
        current = id;
        LAYERS.forEach((L) => {
            if (L.root) {
                L.root.hidden = L.id !== id;
            }
        });
        render();
    }
    function render() {
        const L = LAYERS.find((l) => l.id === current);
        if (!L || !L.root) {
            return;
        }
        const el = (id) => L.els[id] || (L.els[id] = L.root.querySelector('[id="' + id + '"]'));
        L.vals.forEach((v) => {
            const r = v[1]();
            const t = Array.isArray(r) ? r[0] : r;
            const e = el(v[0]);
            setText(e, t);
            setCls(e, v[2] + (v[3] ? " h" : "") + (Array.isArray(r) && r[1] ? " " + r[1] : ""));
        });
        L.acts.forEach((a) => {
            const e = el(a[0]);
            const on = !!a[2]();
            if (e.classList.contains(a[1]) !== on) {
                e.classList.toggle(a[1], on);
            }
        });
        L.bars.forEach((b) => {
            const e = el(b[0]);
            const r = b[2]();
            e.setAttribute("width", (b[1] * clamp(isFinite(r[0]) ? r[0] : 0, 0, 1)).toFixed(1));
            setCls(e, "bar-fg " + r[1]);
        });
        const svg = L.root.firstChild;
        const FL = {
            "f-gas": S.valves && V.gas > 1,
            "f-heat": V.flow > 0.5,
            "f-exh": S.rpm > 200,
            "f-lt": V.flowLT > 0.5,
            "f-oil": S.pOil > 0.5,
            "f-air": S.rpm > 200 || S.fanSup > 1,
            "f-byp": S.bypass > 0.3 && S.rpm > 200,
            "f-cool": V.qCooler > 3,
        };
        Object.keys(FL).forEach((c) => {
            if (svg.classList.contains(c) !== FL[c]) {
                svg.classList.toggle(c, FL[c]);
            }
        });
    }
    return { LAYERS, mount, setLayer, render };
}
