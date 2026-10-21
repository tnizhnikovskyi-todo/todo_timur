
/* ===== 3D-модель (three.js r147, лише примітиви) ===== */
function init3D(){
  const wrap=$('#cv-wrap'), canvas=$('#cv'), fb=$('#cv-fallback');
  const fail=msg=>{ fb.hidden=false; if(msg) setText($('#cv-fb-msg'),msg); $$('#shell-seg button,#btn-reset-view').forEach(b=>{b.disabled=true;}); };
  if(!window.THREE||!THREE.OrbitControls){ fail('Не вдалося завантажити three.js (CDN недоступний). Решта пульта працює, параметри вузлів доступні зі списку.'); return; }
  let renderer;
  try{ renderer=new THREE.WebGLRenderer({canvas:canvas,antialias:true,powerPreference:'high-performance'}); }
  catch(e){ fail('WebGL недоступний у цьому браузері. Решта пульта працює.'); return; }
  if(!renderer.getContext()){ fail('WebGL недоступний у цьому браузері.'); return; }
  if(THREE.ColorManagement){ if('legacyMode' in THREE.ColorManagement) THREE.ColorManagement.legacyMode=false; else THREE.ColorManagement.enabled=true; }
  renderer.outputEncoding=THREE.sRGBEncoding;
  renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#888888';
  const scene=new THREE.Scene(); scene.background=new THREE.Color('#d7dce0');
  const camera=new THREE.PerspectiveCamera(38,1.4,0.1,220);
  const HOME={pos:new THREE.Vector3(9.4,6.4,11.6),tgt:new THREE.Vector3(0.8,1.9,0.2)};
  camera.position.copy(HOME.pos);
  const controls=new THREE.OrbitControls(camera,canvas);
  controls.target.copy(HOME.tgt); controls.enableDamping=!REDUCED; controls.dampingFactor=0.08;
  controls.maxPolarAngle=Math.PI*0.495; controls.minDistance=2.5; controls.maxDistance=34; controls.screenSpacePanning=true; controls.update();

  /* --- освітлення --- */
  const hemi=new THREE.HemisphereLight(0xffffff,0x888888,0.85); scene.add(hemi);
  const key=new THREE.DirectionalLight(0xffffff,1.0); key.position.set(7,14,11); key.castShadow=true;
  key.shadow.mapSize.set(1024,1024); const sc_=key.shadow.camera; sc_.left=-13; sc_.right=13; sc_.top=10; sc_.bottom=-10; sc_.near=1; sc_.far=45; key.shadow.bias=-0.0006;
  scene.add(key);
  const fillA=new THREE.PointLight(0xffffff,0.5,11); fillA.position.set(-3,2.4,0.4); scene.add(fillA);
  const fillB=new THREE.PointLight(0xffffff,0.5,11); fillB.position.set(3.2,2.4,0.4); scene.add(fillB);
  const world=new THREE.Group(); scene.add(world);

  /* --- реєстр матеріалів і кольорів з токенів --- */
  const reg=[];
  function regColor(m,tok){ reg.push({m:m,tok:tok}); m.color.set(css(tok)); return m; }
  const nodes={}; let cur=null; const mcache=new Map();
  function defNode(id){ const g=new THREE.Group(); g.name=id; world.add(g); nodes[id]={id:id,group:g,mats:[],meshes:[],sys:NODES[id]?NODES[id].sys:'eng'}; cur=nodes[id]; return cur; }
  function nm(tok,o){
    const key=cur.id+'|'+tok+'|'+(o?JSON.stringify(o):'');
    if(mcache.has(key)) return mcache.get(key);
    const m=new THREE.MeshStandardMaterial(Object.assign({roughness:0.55,metalness:0.3},o||{}));
    regColor(m,tok); cur.mats.push(m); mcache.set(key,m); return m;
  }
  function M(geo,mat,x,y,z,parent){
    const m=new THREE.Mesh(geo,mat); m.position.set(x||0,y||0,z||0); m.castShadow=true; m.receiveShadow=true; m.userData.node=cur.id; cur.meshes.push(m); (parent||cur.group).add(m); return m;
  }
  const BX=(w,h,d)=>new THREE.BoxGeometry(w,h,d);
  const CY=(r,h,s)=>new THREE.CylinderGeometry(r,r,h,s||28);
  const TO_=(R,r)=>new THREE.TorusGeometry(R,r,10,40);
  const cylX=(r,len,mat,x,y,z,parent)=>{ const m=M(CY(r,len),mat,x,y,z,parent); m.rotation.z=Math.PI/2; return m; };
  const cylZ=(r,len,mat,x,y,z,parent)=>{ const m=M(CY(r,len),mat,x,y,z,parent); m.rotation.x=Math.PI/2; return m; };
  const cylY=(r,len,mat,x,y,z,parent)=>M(CY(r,len),mat,x,y,z,parent);
  const ringX=(R,r,mat,x,y,z,parent)=>{ const m=M(TO_(R,r),mat,x,y,z,parent); m.rotation.y=Math.PI/2; return m; };
  const ringY=(R,r,mat,x,y,z,parent)=>{ const m=M(TO_(R,r),mat,x,y,z,parent); m.rotation.x=Math.PI/2; return m; };

  /* --- лампи (індикатори стану) --- */
  const LAMP={on:{},off:null}; const lamps=[];
  function lamp(x,y,z,r,axis,parent){
    const m=new THREE.MeshStandardMaterial({roughness:0.4,metalness:0}); const g=new THREE.Mesh(CY(r,r*1.4,14),m);
    if(axis==='x') g.rotation.z=Math.PI/2; else if(axis==='z') g.rotation.x=Math.PI/2;
    g.position.set(x,y,z); g.userData.node=cur.id; cur.meshes.push(g); (parent||cur.group).add(g); const o={m:m,kind:null}; lamps.push(o); return o;
  }
  function setLamp(o,kind){
    if(o.kind===kind) return; o.kind=kind;
    if(!kind){ o.m.color.copy(LAMP.off); o.m.emissive.set(0x000000); o.m.emissiveIntensity=0; }
    else { o.m.color.copy(LAMP.on[kind]); o.m.emissive.copy(LAMP.on[kind]); o.m.emissiveIntensity=0.9; }
  }

  /* --- труби з анімованою текстурою потоку --- */
  const PIPE_TOK={gas:'--pipe-gas',sup:'--pipe-sup',ret:'--pipe-ret',exh:'--pipe-exh',lt:'--pipe-lt',oil:'--pipe-oil',air:'--pipe-air',fire:'--pipe-fire'};
  const stripe={}; const flows=[];
  function stripeOf(kind){
    if(!stripe[kind]){ const c=document.createElement('canvas'); c.width=64; c.height=8; const t=new THREE.CanvasTexture(c); t.wrapS=THREE.RepeatWrapping; t.encoding=THREE.sRGBEncoding; stripe[kind]={c:c,ctx:c.getContext('2d'),base:t,clones:[]}; }
    return stripe[kind];
  }
  function paintStripes(){
    Object.keys(stripe).forEach(k=>{
      const o=stripe[k], x=o.ctx; x.fillStyle=css(PIPE_TOK[k]); x.fillRect(0,0,64,8);
      x.fillStyle='rgba(255,255,255,0.30)'; x.fillRect(16,0,24,8); x.fillStyle='rgba(0,0,0,0.14)'; x.fillRect(44,0,4,8);
      o.base.needsUpdate=true; o.clones.forEach(t=>{ t.needsUpdate=true; });
    });
  }
  function roundedPath(pts,r){
    const path=new THREE.CurvePath(); const P=pts.map(p=>new THREE.Vector3(p[0],p[1],p[2])); let c=P[0].clone();
    for(let i=1;i<P.length-1;i++){
      const a=P[i-1],b=P[i],n=P[i+1]; const d1=b.clone().sub(a), d2=n.clone().sub(b); const l1=d1.length(), l2=d2.length();
      const rr=Math.min(r,l1/2,l2/2); const p1=b.clone().sub(d1.normalize().multiplyScalar(rr)); const p2=b.clone().add(d2.normalize().multiplyScalar(rr));
      if(c.distanceTo(p1)>1e-4) path.add(new THREE.LineCurve3(c.clone(),p1));
      path.add(new THREE.QuadraticBezierCurve3(p1,b.clone(),p2)); c=p2;
    }
    const last=P[P.length-1]; if(c.distanceTo(last)>1e-4) path.add(new THREE.LineCurve3(c.clone(),last)); return path;
  }
  function pipe(pts,r,kind,grp,corner){
    const path=roundedPath(pts,corner||0.16); const len=path.getLength();
    const geo=new THREE.TubeGeometry(path,Math.max(12,Math.ceil(len*12)),r,10,false);
    const o=stripeOf(kind); const tex=o.base.clone(); tex.wrapS=THREE.RepeatWrapping; tex.repeat.set(Math.max(1,len/0.6),1); tex.needsUpdate=true; o.clones.push(tex);
    const mat=new THREE.MeshStandardMaterial({map:tex,roughness:0.45,metalness:0.25}); cur.mats.push(mat);
    const m=new THREE.Mesh(geo,mat); m.castShadow=true; m.receiveShadow=true; m.userData.node=cur.id; cur.meshes.push(m); cur.group.add(m);
    flows.push({tex:tex,grp:grp}); return m;
  }
  function cable(pts,r,tok){
    const path=roundedPath(pts,0.12); const geo=new THREE.TubeGeometry(path,Math.max(10,Math.ceil(path.getLength()*10)),r,8,false);
    return M(geo,nm(tok||'--s-steel-d',{roughness:0.8,metalness:0.1}),0,0,0);
  }

  /* --- ґрунт, фундамент, сітка --- */
  const groundMat=new THREE.MeshStandardMaterial({roughness:1,metalness:0}); regColor(groundMat,'--s-floor');
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(80,80),groundMat); ground.rotation.x=-Math.PI/2; ground.receiveShadow=true; scene.add(ground);
  const padMat=new THREE.MeshStandardMaterial({roughness:0.95,metalness:0}); regColor(padMat,'--s-pad');
  const pad=new THREE.Mesh(new THREE.BoxGeometry(17,0.06,5.6),padMat); pad.position.set(0.4,-0.03+0.002,0.4); pad.receiveShadow=true; scene.add(pad);
  let grid=null;
  function makeGrid(){ if(grid){ scene.remove(grid); grid.geometry.dispose(); grid.material.dispose(); } const c=new THREE.Color(css('--s-grid')); grid=new THREE.GridHelper(60,60,c,c); grid.position.y=0.004; grid.material.transparent=true; grid.material.opacity=0.55; scene.add(grid); }

  /* --- корпус контейнера --- */
  const shellMat=new THREE.MeshStandardMaterial({roughness:0.72,metalness:0.18}); regColor(shellMat,'--s-shell');
  const shellDark=new THREE.MeshStandardMaterial({roughness:0.6,metalness:0.3}); regColor(shellDark,'--s-shell-d');
  const floorMat=new THREE.MeshStandardMaterial({roughness:0.9,metalness:0.05}); regColor(floorMat,'--s-pad');
  const Shell={front:new THREE.Group(),back:new THREE.Group(),roofFront:null,all:[],mode:'cut'};
  scene.add(Shell.front,Shell.back);
  function sbox(w,h,d,x,y,z,mat,parent){ const m=new THREE.Mesh(BX(w,h,d),mat); m.position.set(x,y,z); m.receiveShadow=true; (parent||scene).add(m); Shell.all.push(m); return m; }
  sbox(12,0.2,2.5,0,0.1,0,shellDark); sbox(11.84,0.012,2.34,0,0.206,0,floorMat);
  sbox(12,2.62,0.08,0,1.51,-1.21,shellMat,Shell.back); sbox(12,2.62,0.08,0,1.51,1.21,shellMat,Shell.front);
  for(let i=-11;i<=11;i++){ sbox(0.05,2.5,0.03,i*0.5,1.5,-1.265,shellDark,Shell.back); sbox(0.05,2.5,0.03,i*0.5,1.5,1.265,shellDark,Shell.front); }
  sbox(0.08,2.62,2.5,-5.96,1.51,0,shellMat); sbox(0.08,2.62,2.5,5.96,1.51,0,shellMat);
  sbox(12,0.08,1.25,0,2.86,-0.625,shellMat); Shell.roofFront=sbox(12,0.08,1.25,0,2.86,0.625,shellMat);
  [[-5.97,-1.19,Shell.back],[5.97,-1.19,Shell.back],[-5.97,1.19,Shell.front],[5.97,1.19,Shell.front]].forEach(p=>sbox(0.14,2.9,0.14,p[0],1.45,p[1],shellDark,p[2]));
  const lblC=document.createElement('canvas'); lblC.width=1024; lblC.height=128; const lblT=new THREE.CanvasTexture(lblC); lblT.encoding=THREE.sRGBEncoding;
  function paintLabel(){ const x=lblC.getContext('2d'); x.clearRect(0,0,1024,128); x.fillStyle=css('--text'); x.font='700 84px "Fira Sans Condensed","Arial Narrow",Arial,sans-serif'; x.textBaseline='middle'; x.fillText('КГУ-1 · TEDOM · 800 кВт',16,68); lblT.needsUpdate=true; }
  const lbl=new THREE.Mesh(new THREE.PlaneGeometry(4.4,0.55),new THREE.MeshBasicMaterial({map:lblT,transparent:true,depthWrite:false})); lbl.position.set(-3.2,2.3,1.285); Shell.front.add(lbl);
  const lbl2=lbl.clone(); lbl2.position.set(-3.2,2.3,-1.285); lbl2.rotation.y=Math.PI; Shell.back.add(lbl2);

  /* --- динамічні елементи --- */
  const fanSets={ht:[],lt:[],sup:[],exh:[]}; const levels=[]; const louvers=[]; const levers=[];
  function bladeFan(parent,r,n,tok,axis){
    const g=new THREE.Group(); parent.add(g);
    if(axis==='z') g.rotation.x=Math.PI/2; else if(axis==='x') g.rotation.z=Math.PI/2;
    // для осі z/x обертаємо вкладену групу навколо локальної Y
    const spin=new THREE.Group(); g.add(spin);
    cylY(r*0.2,0.06,nm(tok,{metalness:0.4}),0,0,0,spin);
    for(let b=0;b<n;b++){ const bg=new THREE.Group(); bg.rotation.y=b*2*Math.PI/n; spin.add(bg); const bl=M(BX(r*0.78,0.012,r*0.28),nm(tok,{metalness:0.4}),r*0.58,0,0,bg); bl.rotation.x=0.45; }
    return spin;
  }
  function coolerUnit(cx,fansList,tokBody){
    [[-1.0,-0.5],[1.0,-0.5],[-1.0,0.5],[1.0,0.5]].forEach(l=>M(BX(0.08,0.5,0.08),nm('--s-steel-d'),cx+l[0],3.15,-0.65+l[1]));
    M(BX(2.2,0.5,1.1),nm(tokBody||'--s-fin',{roughness:0.8}),cx,3.65,-0.65);
    for(let i=0;i<10;i++) M(BX(0.02,0.46,1.12),nm('--s-steel',{roughness:0.8}),cx-0.9+i*0.2,3.65,-0.65);
    [-0.55,0.55].forEach(dx=>{
      const fgp=new THREE.Group(); fgp.position.set(cx+dx,3.94,-0.65); cur.group.add(fgp); fansList.push(fgp);
      M(TO_(0.47,0.035),nm('--s-steel-d'),cx+dx,3.92,-0.65).rotation.x=Math.PI/2;
      cylY(0.09,0.12,nm('--s-steel-d'),0,0,0,fgp);
      for(let b=0;b<5;b++){ const bg=new THREE.Group(); bg.rotation.y=b*2*Math.PI/5; fgp.add(bg); const bl=M(BX(0.38,0.014,0.13),nm('--s-plate',{metalness:0.4}),0.27,0,0,bg); bl.rotation.x=0.45; }
      M(TO_(0.2,0.012),nm('--s-steel'),cx+dx,3.97,-0.65).rotation.x=Math.PI/2; M(TO_(0.36,0.012),nm('--s-steel'),cx+dx,3.97,-0.65).rotation.x=Math.PI/2;
      M(BX(0.96,0.014,0.02),nm('--s-steel'),cx+dx,3.97,-0.65); M(BX(0.02,0.014,0.96),nm('--s-steel'),cx+dx,3.97,-0.65);
    });
  }

  /* ===== ВУЗОЛ: двигун (V16) ===== */
  const ECX=-1.0, AXY=0.95, GZ=-1.05, GY=1.1;
  defNode('engine');
  M(BX(6.6,0.12,1.3),nm('--s-steel-d'),0.55,0.26,0);
  M(BX(2.7,0.62,0.92),nm('--s-engine'),ECX,0.92,0);
  [-1,1].forEach(side=>{
    const g=new THREE.Group(); g.position.set(ECX,1.22,0); g.rotation.x=side*0.52; cur.group.add(g);
    for(let i=0;i<8;i++){ const x=-1.19+i*0.34;
      M(CY(0.14,0.34,20),nm('--s-head'),x,0.17,0,g);
      M(BX(0.29,0.26,0.4),nm('--s-head',{metalness:0.4}),x,0.47,0,g);
      M(CY(0.04,0.2,12),nm('--s-steel-d'),x,0.8,0,g);
    }
    M(BX(2.7,0.08,0.34),nm('--s-steel-d'),0,0.68,0,g);
  });
  cylX(0.11,2.4,nm('--s-steel'),ECX,1.95,0);
  cylX(0.3,0.15,nm('--s-steel-d'),-2.45,AXY,0);
  M(BX(0.5,0.3,0.3),nm('--s-steel-d'),-1.2,1.05,0.58);

  /* ===== ВУЗОЛ: турбокомпресор ===== */
  defNode('turbo');
  cylX(0.22,0.3,nm('--s-steel-d'),0.5,1.75,0); cylX(0.12,0.2,nm('--s-steel'),0.72,1.75,0); cylX(0.2,0.25,nm('--s-steel'),0.9,1.75,0);
  cylX(0.12,0.12,nm('--s-plate'),1.07,1.75,0); ringX(0.22,0.025,nm('--s-steel-d'),0.62,1.75,0);
  pipe([[0.9,1.75,0.2],[0.9,1.75,0.35],[0.9,2.3,0.35],[0.0,2.3,0.35]],0.07,'air','air',0.12);
  cylX(0.07,0.25,nm('--s-steel'),0.5,1.55,-0.2);

  /* ===== ВУЗОЛ: охолоджувач суміші (інтеркулер) ===== */
  defNode('intercooler');
  M(BX(1.2,0.42,0.7),nm('--s-steel',{roughness:0.6}),-0.6,2.41,0.25);
  for(let i=0;i<12;i++) M(BX(0.02,0.4,0.72),nm('--s-fin'),-1.1+i*0.095,2.41,0.25);
  M(BX(1.24,0.03,0.74),nm('--s-steel-d'),-0.6,2.635,0.25);
  cylY(0.09,0.2,nm('--s-steel-d'),-0.6,2.12,0.12);
  cylY(0.05,0.14,nm('--s-steel-d'),-1.0,2.68,-0.05); cylY(0.05,0.14,nm('--s-steel-d'),-0.2,2.68,-0.05);
  pipe([[-1.0,2.62,-0.05],[-1.0,2.74,-0.05],[-1.0,2.74,-0.45],[-5.0,2.74,-0.45],[-5.0,3.4,-0.45]],0.05,'lt','lt',0.12);
  pipe([[-4.4,3.4,-0.85],[-4.4,2.68,-0.85],[-0.2,2.68,-0.85],[-0.2,2.68,-0.05],[-0.2,2.62,-0.05]],0.05,'lt','lt',0.12);

  /* ===== ВУЗОЛ: маховик/муфта ===== */
  defNode('flywheel');
  cylX(0.56,0.4,nm('--s-steel'),0.55,AXY,0);
  const fw=new THREE.Group(); fw.position.set(0.95,AXY,0); cur.group.add(fw);
  cylX(0.5,0.12,nm('--s-steel-d',{metalness:0.6}),0,0,0,fw);
  for(let i=0;i<6;i++){ const bg=new THREE.Group(); bg.rotation.x=i*Math.PI/3; fw.add(bg); M(BX(0.1,0.34,0.06),nm('--s-head'),0.0,0.26,0,bg); }
  cylX(0.26,0.4,nm('--s-cab-d',{roughness:0.9,metalness:0.1}),0.35,0,0,fw);
  ringX(0.5,0.03,nm('--s-steel'),0.06,0,0,fw);

  /* ===== ВУЗОЛ: маслосистема (картер, охолоджувач, фільтри) ===== */
  defNode('oil');
  M(BX(2.5,0.3,0.78),nm('--s-steel-d'),ECX,0.47,0);
  M(BX(0.5,0.42,0.2),nm('--s-steel',{roughness:0.5}),-1.6,0.8,0.62);
  for(let i=0;i<7;i++) M(BX(0.5,0.38,0.012),nm('--s-fin'),-1.6,0.8,0.54+i*0.025);
  cylZ(0.09,0.3,nm('--s-cab-d'),-0.9,0.75,0.6); cylZ(0.09,0.3,nm('--s-cab-d'),-0.55,0.75,0.6);
  cylY(0.03,0.2,nm('--s-steel'),-0.9,0.95,0.6); cylY(0.03,0.2,nm('--s-steel'),-0.55,0.95,0.6);
  cylX(0.025,0.5,nm('--s-steel'),-1.2,0.6,0.6);

  /* ===== ВУЗОЛ: баки масла й автодолив ===== */
  defNode('oiltanks');
  [[-4.6,'frb'],[-4.05,'wsb']].forEach(t=>{
    cylY(0.22,0.9,nm('--s-tank'),t[0],0.65,0.85); cylY(0.24,0.05,nm('--s-steel-d'),t[0],1.12,0.85); cylY(0.24,0.05,nm('--s-steel-d'),t[0],0.2+0.025,0.85);
    M(BX(0.06,0.82,0.02),nm('--s-steel-d'),t[0],0.65,1.075);
    const lv=M(BX(0.04,1,0.015),nm('--pipe-oil',{roughness:0.4}),t[0],0.65,1.088); levels.push({m:lv,y0:0.25,h:0.8,fn:t[1]==='frb'?()=>V.oilFresh/100:()=>V.oilWaste/100});
  });
  pipe([[-4.6,1.14,0.85],[-4.6,1.3,0.85],[-2.5,1.3,0.85],[-2.5,0.5,0.85],[-2.5,0.5,0.4]],0.04,'oil','topup',0.12);
  M(BX(0.2,0.2,0.2),nm('--s-steel-d'),-3.5,1.3,0.85); const tuLamp=lamp(-3.5,1.46,0.85,0.04,'y');
  pipe([[-2.3,0.35,0.3],[-3.2,0.35,0.3],[-3.2,0.35,0.85],[-3.83,0.35,0.85]],0.04,'oil',null,0.12); M(BX(0.14,0.14,0.14),nm('--s-steel-d'),-3.2,0.35,0.58);

  /* ===== ВУЗОЛ: стартер ===== */
  defNode('starter');
  cylX(0.14,0.45,nm('--s-steel-d'),-2.72,AXY,0.32); M(BX(0.14,0.14,0.14),nm('--s-steel'),-2.72,1.14,0.32); cylX(0.07,0.2,nm('--s-steel'),-2.5,AXY,0.2);
  const stLamp=lamp(-2.72,1.26,0.32,0.035,'y');

  /* ===== ВУЗОЛ: АКБ та зарядний пристрій ===== */
  defNode('battery');
  M(BX(0.55,0.3,0.36),nm('--s-cab-d'),-4.8,0.4,-0.55); M(BX(0.5,0.12,0.3),nm('--s-steel'),-4.8,0.61,-0.55);
  M(BX(0.5,0.04,0.4),nm('--s-steel-d'),-4.8,0.78,-0.55);
  M(BX(0.34,0.44,0.16),nm('--s-cab'),-4.8,1.02,-0.62); const chLamp=lamp(-4.8,1.1,-0.535,0.03,'z');
  cable([[-4.7,0.56,-0.55],[-4.7,0.9,-0.55],[-3.2,0.9,-0.55]],0.015,'--s-steel-d');

  /* ===== ВУЗОЛ: газова рампа ===== */
  defNode('gasramp');
  pipe([[-6.8,0.05,GZ],[-6.8,GY,GZ],[-2.9,GY,GZ],[-2.9,2.3,GZ],[0.88,2.3,GZ],[0.88,2.3,-0.4],[0.88,1.95,-0.4]],0.075,'gas','gas',0.16);
  M(BX(0.2,0.22,0.22),nm('--s-steel-d'),-5.4,GY,GZ); M(BX(0.32,0.03,0.06),new THREE.MeshStandardMaterial({color:0xb3261e,roughness:0.6}),-5.4,GY+0.2,GZ);
  cylY(0.17,0.55,nm('--s-steel'),-4.75,0.78,GZ); ringX(0.17,0.02,nm('--s-steel-d'),-4.75,GY,GZ);
  cylY(0.12,0.42,nm('--s-steel-d'),-4.1,1.38,GZ); cylY(0.25,0.14,nm('--s-steel'),-4.1,1.68,GZ);
  cylY(0.02,0.25,nm('--s-steel'),-4.45,1.25,GZ); cylZ(0.075,0.04,new THREE.MeshStandardMaterial({color:0xf2f2f2,roughness:0.5}),-4.45,1.42,GZ);
  M(BX(0.1,0.14,0.1),nm('--s-cab-d'),-3.88,1.3,GZ+0.0); M(BX(0.1,0.14,0.1),nm('--s-cab-d'),-3.76,1.3,GZ+0.0);
  const pslLamp=lamp(-3.82,1.42,GZ,0.03,'y');

  /* ===== ВУЗОЛ: клапани YV1/YV2 і valve proving ===== */
  defNode('yv');
  const yvLamps=[]; [-3.55,-3.15].forEach(x=>{ M(BX(0.3,0.3,0.3),nm('--s-steel-d'),x,GY,GZ); M(BX(0.14,0.22,0.14),nm('--s-cab-d'),x,GY+0.26,GZ); yvLamps.push(lamp(x,GY+0.42,GZ,0.045,'y')); });
  cylY(0.03,0.25,nm('--s-steel'),-3.35,GY+0.2,GZ); cylZ(0.06,0.04,new THREE.MeshStandardMaterial({color:0xf2f2f2,roughness:0.5}),-3.35,GY+0.36,GZ);

  /* ===== ВУЗОЛ: лічильник газу ===== */
  defNode('gasmeter');
  M(BX(0.38,0.34,0.3),nm('--s-cab',{metalness:0.2}),-2.9,1.55,GZ); cylZ(0.1,0.03,new THREE.MeshStandardMaterial({color:0xf2f2f2,roughness:0.5}),-2.9,1.58,GZ+0.16);
  ringZ_(-2.9,1.58,GZ+0.16);
  function ringZ_(x,y,z){ const m=M(TO_(0.1,0.01),nm('--s-steel-d'),x,y,z); }

  /* ===== ВУЗОЛ: змішувач / дросель ===== */
  defNode('mixer');
  M(BX(0.3,0.3,0.3),nm('--s-steel-d'),0.88,1.8,-0.4); cylZ(0.08,0.12,nm('--s-steel'),0.88,1.75,-0.2); M(BX(0.12,0.2,0.12),nm('--s-cab-d'),1.1,1.8,-0.4); cylY(0.05,0.1,nm('--s-steel'),0.88,1.99,-0.4);

  /* ===== ВУЗОЛ: повітряний фільтр ===== */
  defNode('airf');
  cylZ(0.22,0.4,nm('--s-cab',{metalness:0.2}),0.88,1.8,-0.85); cylZ(0.24,0.04,nm('--s-steel-d'),0.88,1.8,-1.05); cylZ(0.24,0.04,nm('--s-steel-d'),0.88,1.8,-0.65);
  cylZ(0.07,0.2,nm('--s-steel'),0.88,1.8,-0.55);

  /* ===== ВУЗОЛ: генератор ===== */
  defNode('generator');
  cylX(0.6,2.0,nm('--s-gen'),2.55,AXY,0);
  for(let i=0;i<6;i++) ringX(0.61,0.03,nm('--s-steel-d'),1.8+i*0.3,AXY,0);
  cylX(0.42,0.22,nm('--s-steel-d'),3.66,AXY,0);
  M(BX(0.8,0.4,0.6),nm('--s-cab',{metalness:0.2}),2.5,1.78,0);
  [[1.95,0.45],[3.15,0.45],[1.95,-0.45],[3.15,-0.45]].forEach(p=>M(BX(0.3,0.1,0.5),nm('--s-steel-d'),p[0],0.38,p[1]));

  /* ===== ВУЗОЛ: АРН / збудження ===== */
  defNode('avr');
  M(BX(0.42,0.32,0.16),nm('--s-cab'),3.3,1.22,-0.72); M(BX(0.3,0.1,0.02),nm('--s-screen'),3.3,1.28,-0.63).material.emissive=new THREE.Color(0x335577);
  const avrLamp=lamp(3.45,1.14,-0.635,0.025,'z');

  /* ===== ВУЗОЛ: шафа керування ===== */
  defNode('cabinet');
  M(BX(0.7,2.1,1.8),nm('--s-cab'),-5.5,1.25,0);
  [-0.6,0,0.6].forEach(z=>M(BX(0.03,1.8,0.55),nm('--s-cab-d'),-5.14,1.25,z));
  const screenMat=new THREE.MeshStandardMaterial({roughness:0.3,metalness:0.1}); regColor(screenMat,'--s-screen'); screenMat.emissive=new THREE.Color(0x335577); screenMat.emissiveIntensity=0.6;
  const screen=new THREE.Mesh(BX(0.02,0.26,0.4),screenMat); screen.position.set(-5.12,1.6,0); screen.userData.node='cabinet'; cur.meshes.push(screen); cur.group.add(screen);
  const cabLamps={run:lamp(-5.12,1.95,0.33,0.04,'x'),warn:lamp(-5.12,1.95,0.45,0.04,'x'),alarm:lamp(-5.12,1.95,0.57,0.04,'x')};
  M(BX(0.5,0.05,1.5),nm('--s-steel-d'),-5.5,2.33,0);

  /* ===== ВУЗОЛ: ввід QF-CHP / захист ROCOF (на ГРЩ, поза контейнером) ===== */
  defNode('qf');
  M(BX(0.7,1.6,0.45),nm('--s-cab'),-4.5,0.83,1.78); M(BX(0.3,0.2,0.04),nm('--s-screen'),-4.5,1.35,2.015).material.emissive=new THREE.Color(0x335577);
  M(BX(0.12,0.3,0.05),nm('--s-steel-d'),-4.5,0.95,2.0); const qfLamp=lamp(-4.3,1.35,2.02,0.03,'z'); const rcLamp=lamp(-4.7,1.35,2.02,0.03,'z');
  M(BX(0.8,0.05,0.5),nm('--s-steel-d'),-4.5,1.65,1.78);
  cable([[-4.5,1.68,1.78],[-4.5,2.4,1.78],[-4.5,2.4,0.8],[-5.5,2.4,0.8],[-5.5,2.36,0.8]],0.035,'--s-steel-d');

  /* ===== ВУЗОЛ: лічильник ел. енергії TEDOM-1 ===== */
  defNode('emeter');
  M(BX(0.45,0.55,0.2),nm('--s-cab'),-3.4,0.9,1.72); M(BX(0.32,0.12,0.02),nm('--s-screen'),-3.4,1.05,1.83).material.emissive=new THREE.Color(0x335577);
  M(BX(0.4,0.04,0.3),nm('--s-steel-d'),-3.4,0.6,1.72); M(BX(0.06,0.5,0.06),nm('--s-steel-d'),-3.4,0.35,1.72);

  /* ===== ВУЗОЛ: пластинчастий ТО (+ контур ОЖ) ===== */
  defNode('phe');
  M(BX(1.05,0.12,0.6),nm('--s-steel-d'),4.37,0.32,-0.55);
  for(let i=0;i<20;i++) M(BX(0.026,1.0,0.46),nm(i%2?'--s-plate':'--s-plate-d',{metalness:0.5}),3.99+i*0.04,0.9,-0.55);
  M(BX(0.08,1.12,0.52),nm('--s-cab-d'),3.93,0.9,-0.55); M(BX(0.08,1.12,0.52),nm('--s-cab-d'),4.83,0.9,-0.55);
  cylX(0.02,0.95,nm('--s-steel'),4.38,1.37,-0.55); cylX(0.02,0.95,nm('--s-steel'),4.38,0.43,-0.55);
  cylX(0.06,0.14,nm('--s-steel-d'),3.84,1.0,-0.45); cylX(0.06,0.14,nm('--s-steel-d'),3.84,0.6,-0.65);
  cylX(0.06,0.14,nm('--s-steel-d'),4.92,1.0,-0.45); cylX(0.06,0.14,nm('--s-steel-d'),4.92,0.6,-0.65);
  pipe([[0.2,1.0,-0.46],[0.2,1.0,-0.92],[3.6,1.0,-0.92],[3.6,1.0,-0.45],[3.84,1.0,-0.45]],0.065,'sup','loopA',0.14);
  pipe([[3.84,0.6,-0.65],[3.7,0.6,-0.65],[3.7,0.6,-0.98],[0.2,0.6,-0.98],[0.2,0.6,-0.46]],0.065,'ret','loopA',0.14);

  /* ===== ВУЗОЛ: насос ВТ ===== */
  defNode('pumpHT');
  cylZ(0.18,0.14,nm('--s-steel-d'),2.6,0.6,-0.98); cylX(0.12,0.36,nm('--s-gen'),2.82,0.6,-0.98); ringX(0.125,0.015,nm('--s-steel'),2.66,0.6,-0.98);
  M(BX(0.3,0.05,0.25),nm('--s-steel-d'),2.75,0.3,-0.98);
  const phtLamp=lamp(2.95,0.76,-0.98,0.03,'y');

  /* ===== ВУЗОЛ: розширювальні баки ===== */
  defNode('exp');
  [[-2.2,'--pipe-sup'],[-1.6,'--pipe-lt'],[-1.0,'--pipe-ret']].forEach(t=>{ cylY(0.2,0.7,nm('--s-tank'),t[0],0.6,-0.92); cylY(0.21,0.06,nm('--s-steel-d'),t[0],0.97,-0.92); ringY(0.2,0.02,nm(t[1]),t[0],0.82,-0.92); cylY(0.03,0.12,nm('--s-steel'),t[0],0.2+0.06,-0.92); });
  M(BX(1.6,0.05,0.5),nm('--s-steel-d'),-1.6,0.24,-0.92);

  /* ===== ВУЗОЛ: ТО вихлопних газів ===== */
  defNode('exhhe');
  cylX(0.32,1.25,nm('--s-ins'),4.9,0.78,0.55);
  [4.3,5.5].forEach(x=>ringX(0.34,0.035,nm('--s-steel-d'),x,0.78,0.55));
  cylX(0.2,0.1,nm('--s-steel-d'),4.24,0.78,0.55); cylX(0.2,0.1,nm('--s-steel-d'),5.56,0.78,0.55);
  [4.5,5.3].forEach(x=>M(BX(0.2,0.34,0.5),nm('--s-steel-d'),x,0.33,0.55));
  cylY(0.06,0.2,nm('--s-steel'),4.55,1.17,0.55); cylY(0.06,0.2,nm('--s-steel'),5.05,1.17,0.55);

  /* ===== ВУЗОЛ: окислювальний каталізатор ===== */
  defNode('cat');
  cylX(0.34,1.0,nm('--s-plate',{metalness:0.55,roughness:0.35}),2.2,2.4,0); cylX(0.22,0.18,nm('--s-steel-d'),1.61,2.4,0); cylX(0.22,0.18,nm('--s-steel-d'),2.79,2.4,0);
  [1.7,2.7].forEach(x=>ringX(0.36,0.03,nm('--s-steel-d'),x,2.4,0));
  cylY(0.025,0.18,nm('--s-steel'),2.0,2.78,0); cylY(0.025,0.18,nm('--s-steel'),2.5,2.78,0);

  /* ===== ВУЗОЛ: байпасна заслінка вихлопу ===== */
  defNode('bypass');
  M(BX(0.36,0.34,0.36),nm('--s-steel-d'),4.05,1.6,0.55); cylY(0.09,0.22,nm('--s-cab-d'),4.05,1.88,0.55);
  const lvBy=new THREE.Group(); lvBy.position.set(4.05,2.02,0.55); cur.group.add(lvBy); M(BX(0.3,0.03,0.04),nm('--s-head'),0.1,0,0,lvBy); levers.push({g:lvBy,fn:()=>S.bypass*1.5});
  pipe([[4.05,1.6,0.55],[4.05,1.6,0.98],[5.72,1.6,0.98],[5.72,0.78,0.98],[5.72,0.78,0.55]],0.1,'exh','byp',0.2);

  /* ===== ВУЗОЛ: вихлоп (труби, глушник, труба) ===== */
  defNode('stack');
  pipe([[0.5,1.9,0],[0.5,2.4,0],[4.05,2.4,0],[4.05,2.4,0.55],[4.05,0.78,0.55],[4.3,0.78,0.55]],0.17,'exh','exh',0.22);
  pipe([[5.52,0.78,0.55],[5.72,0.78,0.55],[5.72,0.78,-0.5]],0.11,'exh','exh',0.1);
  cylY(0.3,1.3,nm('--s-stack'),5.6,1.0,-0.8); [0.37,1.63].forEach(y=>M(TO_(0.3,0.03),nm('--s-steel-d'),5.6,y,-0.8).rotation.x=Math.PI/2);
  cylY(0.17,4.1,nm('--s-stack'),5.6,3.7,-0.8); cylY(0.23,0.05,nm('--s-steel-d'),5.6,5.78,-0.8);
  [2.6,4.2].forEach(y=>M(TO_(0.17,0.025),nm('--s-steel-d'),5.6,y,-0.8).rotation.x=Math.PI/2);

  /* ===== ВУЗОЛ: аналіз викидів ===== */
  defNode('emis');
  M(BX(0.5,0.5,0.25),nm('--s-cab'),4.4,1.55,-1.03); M(BX(0.34,0.14,0.02),nm('--s-screen'),4.4,1.65,-0.9).material.emissive=new THREE.Color(0x335577);
  const emLamp=lamp(4.58,1.42,-0.9,0.025,'z');
  cylZ(0.035,0.3,nm('--s-steel'),5.6,2.6,-0.62);
  pipe([[5.6,2.6,-0.62],[4.65,2.6,-0.62],[4.65,2.6,-1.03],[4.65,1.8,-1.03]],0.02,'exh',null,0.1);

  /* ===== ВУЗОЛ: контур тепла (подача/зворотка, магістралі на дах) ===== */
  defNode('loop');
  pipe([[4.92,1.0,-0.45],[4.98,1.0,-0.45],[4.98,1.6,-0.45],[4.55,1.6,-0.45],[4.55,1.6,0.55],[4.55,1.27,0.55]],0.065,'sup','loopA',0.12);
  pipe([[5.05,1.27,0.55],[5.05,2.2,0.55],[5.05,2.2,-0.45],[6.8,2.2,-0.45],[6.8,0.05,-0.45]],0.07,'sup','loopA',0.14);
  pipe([[6.8,0.05,-0.2],[6.8,2.45,-0.2],[5.2,2.45,-0.2],[5.2,0.6,-0.2],[5.2,0.6,-0.65],[4.92,0.6,-0.65]],0.07,'ret','boil',0.14);
  pipe([[6.5,2.45,-0.05],[6.5,2.45,0.3],[6.5,3.45,0.3],[5.05,3.45,0.3],[5.05,3.45,-0.03],[-3.55,3.45,-0.03]],0.07,'ret','cool',0.14);
  pipe([[-3.55,3.45,-1.27],[5.2,3.45,-1.27],[5.2,3.45,-0.2],[5.2,2.45,-0.2]],0.07,'ret','cool',0.14);
  [-0.45,-0.2].forEach(z=>{ ringX(0.1,0.02,nm('--s-steel-d'),5.99,z===-0.45?2.2:2.45,z); });

  /* ===== ВУЗОЛ: насос контуру опалення ===== */
  defNode('pumpHeat');
  cylY(0.17,0.12,nm('--s-steel-d'),5.2,1.5,-0.2); cylY(0.12,0.34,nm('--s-gen'),5.2,1.76,-0.2); ringY(0.13,0.015,nm('--s-steel'),5.2,1.62,-0.2);
  const phLamp=lamp(5.2,1.96,-0.2,0.03,'y');

  /* ===== ВУЗОЛ: трьоххідний змішувальний клапан ===== */
  defNode('mixv');
  M(BX(0.26,0.26,0.26),nm('--s-steel-d'),6.5,2.45,-0.2); cylZ(0.05,0.3,nm('--pipe-ret'),6.5,2.45,0.05); cylY(0.1,0.22,nm('--s-cab-d'),6.5,2.69,-0.2);
  const lvMx=new THREE.Group(); lvMx.position.set(6.5,2.82,-0.2); cur.group.add(lvMx); M(BX(0.3,0.03,0.04),nm('--s-head'),0.1,0,0,lvMx); levers.push({g:lvMx,fn:()=>S.mixPos/100*1.5});

  /* ===== ВУЗОЛ: тепловий лічильник ===== */
  defNode('heatmeter');
  M(BX(0.3,0.22,0.22),nm('--s-cab'),6.25,2.2,-0.45); M(BX(0.2,0.08,0.02),nm('--s-screen'),6.25,2.28,-0.33).material.emissive=new THREE.Color(0x335577);
  cylX(0.09,0.12,nm('--s-steel'),6.07,2.2,-0.45); cylX(0.09,0.12,nm('--s-steel'),6.43,2.2,-0.45);

  /* ===== ВУЗОЛ: сухі градирні ВТ на даху ===== */
  defNode('cooler');
  coolerUnit(-2.3,fanSets.ht); coolerUnit(0.3,fanSets.ht);

  /* ===== ВУЗОЛ: градирня НТ на даху ===== */
  defNode('coolerLT');
  coolerUnit(-4.8,fanSets.lt,'--s-engine');

  /* ===== ВУЗОЛ: насос НТ ===== */
  defNode('pumpLT');
  cylX(0.16,0.14,nm('--s-steel-d'),-4.4,3.1,-0.85); cylX(0.11,0.34,nm('--s-gen'),-4.2,3.1,-0.85); M(BX(0.3,0.04,0.25),nm('--s-steel-d'),-4.3,2.95,-0.85);
  const pltLamp=lamp(-4.12,3.24,-0.85,0.03,'y');

  /* ===== ВУЗОЛ: вентиляція контейнера ===== */
  defNode('vent');
  M(BX(0.95,0.65,0.05),nm('--s-steel-d'),-4.2,2.1,-1.145);
  cylZ(0.3,0.12,nm('--s-steel'),-4.2,2.1,-1.07);
  const fSup=bladeFan(cur.group,0.26,5,'--s-plate','z'); fSup.parent.position.set(-4.2,2.1,-1.03); fanSets.sup.push(fSup);
  for(let i=0;i<5;i++){ const sl=new THREE.Group(); sl.position.set(-4.2,1.9+i*0.1,-1.11); cur.group.add(sl); M(BX(0.82,0.012,0.11),nm('--s-steel'),0,0,0,sl); louvers.push(sl); }
  M(BX(0.06,0.7,0.7),nm('--s-steel-d'),6.07,2.35,0.75);
  cylX(0.3,0.12,nm('--s-steel'),6.14,2.35,0.75);
  const fExh=bladeFan(cur.group,0.26,5,'--s-plate','x'); fExh.parent.position.set(6.18,2.35,0.75); fanSets.exh.push(fExh);
  for(let i=0;i<5;i++){ const sl=new THREE.Group(); sl.position.set(6.24,2.15+i*0.1,0.75); cur.group.add(sl); M(BX(0.012,0.11,0.62),nm('--s-steel'),0,0,0,sl); louvers.push(sl); }

  /* ===== ВУЗОЛ: газоаналізатор ===== */
  defNode('gasdet');
  M(BX(0.22,0.28,0.2),nm('--s-cab'),-2.6,2.66,0.9); const gdLamp=lamp(-2.6,2.66,1.01,0.035,'z'); cylY(0.03,0.1,nm('--s-steel'),-2.6,2.78,0.9);
  M(BX(0.18,0.22,0.16),nm('--s-cab'),-4.4,2.66,-0.9);

  /* ===== ВУЗОЛ: пожежна сигналізація та гасіння ===== */
  defNode('fire');
  [[-3.2,0.4],[1.8,0.5]].forEach(p=>{ cylY(0.1,0.05,nm('--s-cab'),p[0],2.795,p[1]); });
  const fiLamp=lamp(-3.2,2.765,0.4,0.03,'y');
  cylY(0.15,0.7,nm('--pipe-fire'),-5.0,0.55,0.35); cylY(0.05,0.08,nm('--s-steel'),-5.0,0.93,0.35); M(BX(0.2,0.2,0.08),nm('--s-steel-d'),-5.0,0.9,0.52);
  pipe([[-5.0,0.97,0.35],[-5.0,2.62,0.35],[-1.5,2.62,0.35]],0.03,'fire',null,0.12);
  [-3.6,-2.2,-1.5].forEach(x=>{ cylY(0.04,0.1,nm('--s-steel-d'),x,2.54,0.35); });
  const bottleLv=M(BX(0.06,1,0.02),nm('--pipe-oil'),-5.0,0.55,0.51); levels.push({m:bottleLv,y0:0.25,h:0.6,fn:()=>S.extLevel/100});

  /* ===== ВУЗОЛ: контур аварійного стопу ===== */
  defNode('estop');
  M(BX(0.1,0.22,0.22),nm('--s-steel-d'),-5.1,1.15,0.5); cylX(0.07,0.05,nm('--pipe-fire'),-5.04,1.15,0.5);
  M(BX(0.06,0.3,0.3),nm('--s-steel-d'),6.07,1.3,0.2); cylX(0.07,0.05,nm('--pipe-fire'),6.12,1.3,0.2);
  const esLamp1=lamp(-5.1,1.32,0.5,0.025,'x'), esLamp2=lamp(6.1,1.5,0.2,0.025,'x');

  /* ===== Дим з труби (спрайти) ===== */
  const smokeTex=(function(){ const c=document.createElement('canvas'); c.width=c.height=64; const x=c.getContext('2d'); const g=x.createRadialGradient(32,32,2,32,32,30); g.addColorStop(0,'rgba(255,255,255,0.9)'); g.addColorStop(1,'rgba(255,255,255,0)'); x.fillStyle=g; x.fillRect(0,0,64,64); return new THREE.CanvasTexture(c); })();
  const smoke=[]; for(let i=0;i<42;i++){ const m=new THREE.SpriteMaterial({map:smokeTex,color:0x888888,transparent:true,opacity:0,depthWrite:false}); const s=new THREE.Sprite(m); s.visible=false; scene.add(s); smoke.push({s:s,age:0,life:1,on:false,vx:0,vy:0,vz:0}); }
  let emitAcc=0;
  function spawn(p){ p.on=true; p.age=0; p.life=3+Math.random()*1.6; p.s.visible=true; p.s.position.set(5.6+(Math.random()-0.5)*0.08,5.85,-0.8+(Math.random()-0.5)*0.08); p.vx=0.35+Math.random()*0.3; p.vy=0.9+Math.random()*0.5; p.vz=(Math.random()-0.5)*0.15; }
  function updateSmoke(dt){
    const rate=(S.rpm>200&&S.valves)?(2.8+9*clamp(S.load,0,1)*(S.rpm/1500)):0; emitAcc+=rate*dt;
    while(emitAcc>=1){ emitAcc-=1; const p=smoke.find(q=>!q.on); if(!p) break; spawn(p); }
    smoke.forEach(p=>{ if(!p.on) return; p.age+=dt; const k=p.age/p.life; if(k>=1){ p.on=false; p.s.visible=false; return; }
      p.s.position.x+=p.vx*dt; p.s.position.y+=p.vy*dt; p.s.position.z+=p.vz*dt; const sz=0.35+1.9*k; p.s.scale.set(sz,sz,1); p.s.material.opacity=0.5*Math.sin(Math.min(1,k*4)*Math.PI/2)*(1-k); });
  }

  /* --- тема: токени → 3D --- */
  const HL={alarm:new THREE.Color(),warn:new THREE.Color(),sel:new THREE.Color()};
  function applyTheme(){
    scene.background.set(css('--s-bg'));
    hemi.color.set(css('--s-sky')); hemi.groundColor.set(css('--s-ground')); hemi.intensity=parseFloat(css('--s-hemi-i'))||0.8;
    key.color.set(css('--s-key')); key.intensity=parseFloat(css('--s-key-i'))||1;
    const fi=parseFloat(css('--s-fill-i'))||0.4; fillA.intensity=fi; fillB.intensity=fi;
    reg.forEach(r=>r.m.color.set(css(r.tok)));
    smoke.forEach(p=>p.s.material.color.set(css('--s-smoke')));
    HL.alarm.set(css('--st-alarm')); HL.warn.set(css('--st-warn')); HL.sel.set(css('--accent'));
    LAMP.on={ok:new THREE.Color(css('--st-run')),warn:new THREE.Color(css('--st-warn')),alarm:new THREE.Color(css('--st-alarm'))}; LAMP.off=new THREE.Color(css('--s-lamp-off'));
    lamps.forEach(o=>{ const k=o.kind; o.kind='?'; setLamp(o,k); });
    paintStripes(); paintLabel(); makeGrid();
  }

  /* --- режими корпусу --- */
  function setShell(mode){
    Shell.mode=mode; const glass=mode==='glass';
    [shellMat,shellDark].forEach(m=>{ m.transparent=glass; m.opacity=glass?0.13:1; m.depthWrite=!glass; m.needsUpdate=true; });
    Shell.front.visible=mode!=='cut'; Shell.roofFront.visible=mode!=='cut';
    $$('#shell-seg button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.shell===mode?'true':'false'));
  }
  $$('#shell-seg button').forEach(b=>b.addEventListener('click',()=>setShell(b.dataset.shell)));

  /* --- фільтр системи: приглушення сторонніх вузлів --- */
  let sysSel='all';
  function inSys(id){ return sysSel==='all'||nodes[id].sys===sysSel; }
  function applySys(){
    Object.keys(nodes).forEach(id=>{
      const dim=!inSys(id); nodes[id].mats.forEach(m=>{ if(m.transparent!==dim){ m.transparent=dim; m.opacity=dim?0.14:1; m.depthWrite=!dim; m.needsUpdate=true; } });
      nodes[id].dim=dim;
    });
  }
  A3.setSystem=s=>{ sysSel=s; applySys(); };

  /* --- вибір, підсвітка, камера --- */
  const ray=new THREE.Raycaster(); const mouse=new THREE.Vector2(); let hover=null, down=null, tween=null;
  function pickables(){ const a=[]; Object.keys(nodes).forEach(id=>{ if(!nodes[id].dim) nodes[id].meshes.forEach(m=>a.push(m)); }); if(Shell.mode==='solid') Shell.all.forEach(m=>{ if(m.visible) a.push(m); }); return a; }
  function pickAt(e){
    const r=canvas.getBoundingClientRect(); mouse.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1); ray.setFromCamera(mouse,camera);
    const hit=ray.intersectObjects(pickables(),false)[0]; return hit&&hit.object.userData.node?hit.object.userData.node:null;
  }
  canvas.addEventListener('pointerdown',e=>{ down={x:e.clientX,y:e.clientY,t:performance.now()}; });
  canvas.addEventListener('pointerup',e=>{ if(!down) return; const moved=Math.hypot(e.clientX-down.x,e.clientY-down.y); const dt=performance.now()-down.t; down=null; if(moved<6&&dt<700){ const id=pickAt(e); A3.pick(id); } });
  let lastMove=0;
  canvas.addEventListener('pointermove',e=>{ if(e.buttons) return; const n=performance.now(); if(n-lastMove<60) return; lastMove=n; const id=pickAt(e); if(id!==hover){ hover=id; canvas.style.cursor=id?'pointer':'grab'; } });
  canvas.addEventListener('pointerleave',()=>{ hover=null; });
  function tweenTo(pos,tgt,dur){
    if(REDUCED){ camera.position.copy(pos); controls.target.copy(tgt); controls.update(); return; }
    tween={t:0,dur:dur,p0:camera.position.clone(),t0:controls.target.clone(),p1:pos.clone(),t1:tgt.clone()};
  }
  A3.focus=id=>{
    const n=nodes[id]; if(!n) return; const box=new THREE.Box3().setFromObject(n.group); const c=box.getCenter(new THREE.Vector3());
    const dir=camera.position.clone().sub(controls.target); const dist=Math.min(dir.length(),Math.max(6.5,box.getSize(new THREE.Vector3()).length()*1.6));
    tweenTo(c.clone().add(dir.normalize().multiplyScalar(dist)),c,0.7);
  };
  $('#btn-reset-view').addEventListener('click',()=>tweenTo(HOME.pos,HOME.tgt,0.8));

  function updateHighlight(t){
    const hl=S.hl, sel=S.sel;
    Object.keys(nodes).forEach(id=>{
      const n=nodes[id]; let col=null, k=0;
      if(hl&&hl.node===id){ col=hl.kind==='alarm'?HL.alarm:HL.warn; const pulsing=hl.kind==='warn'||(S.alarm&&!S.alarm.acked); k=REDUCED?0.45:(pulsing?0.22+0.5*(0.5+0.5*Math.sin(t*6.5)):0.32); }
      else if(sel===id){ col=HL.sel; k=0.34; }
      else if(hover===id){ col=HL.sel; k=0.16; }
      else if(sysSel!=='all'&&!n.dim){ col=HL.sel; k=0.1; }
      n.mats.forEach(m=>{ if(col){ m.emissive.copy(col); m.emissiveIntensity=k; } else if(m.emissiveIntensity!==0){ m.emissiveIntensity=0; } });
    });
    const blink=(f)=>REDUCED||Math.floor(t*f)%2===0;
    const run=S.state===ST.RUN, mid=S.state===ST.START||S.state===ST.COOL, al=S.state===ST.ALARM;
    setLamp(cabLamps.run,run?'ok':null); setLamp(cabLamps.warn,(mid&&blink(2))?'warn':null); setLamp(cabLamps.alarm,(al&&(!S.alarm||S.alarm.acked||blink(3)))?'alarm':null);
    const vk=S.valves?'ok':(curId()==='proving'?'warn':null); yvLamps.forEach(l=>setLamp(l,vk)); setLamp(pslLamp,S.gasP<1.5?'alarm':'ok');
    setLamp(tuLamp,S.topup?'warn':null); setLamp(stLamp,S.starter?'warn':null); setLamp(chLamp,S.starter?'warn':'ok');
    setLamp(phtLamp,V.pHT&&V.pHT.run?'ok':null); setLamp(phLamp,V.pHe&&V.pHe.run?'ok':null); setLamp(pltLamp,V.pLT&&V.pLT.run?'ok':null);
    setLamp(avrLamp,S.rpm>1200?'ok':null); setLamp(qfLamp,S.qf?'ok':null); setLamp(rcLamp,S.rocofFlag?'alarm':'ok');
    setLamp(emLamp,V.nox>250||V.co>300?'alarm':(S.rpm>1200?'ok':null));
    setLamp(gdLamp,S.lel>=20?'alarm':(S.lel>=10?'warn':'ok')); setLamp(fiLamp,S.fire?'alarm':(S.ext==='ready'?'ok':'warn'));
    setLamp(esLamp1,S.estopLoop?'ok':'alarm'); setLamp(esLamp2,S.estopLoop?'ok':'alarm');
  }

  /* --- анімація --- */
  function animate(dt,t){
    if(tween){ tween.t+=dt; const k=ease(Math.min(1,tween.t/tween.dur)); camera.position.lerpVectors(tween.p0,tween.p1,k); controls.target.lerpVectors(tween.t0,tween.t1,k); if(tween.t>=tween.dur) tween=null; }
    levels.forEach(l=>{ const v=clamp(l.fn(),0.01,1); l.m.scale.y=l.h*v; l.m.position.y=l.y0+l.h*v/2; });
    louvers.forEach(g=>{ g.rotation.set(g.position.x>0?0:(1-S.louver/100)*1.2,0,g.position.x>0?(1-S.louver/100)*1.2:0); });
    levers.forEach(l=>{ l.g.rotation.y=l.fn(); });
    if(!REDUCED){
      fw.rotation.x+=(S.rpm/1500)*10*dt;
      const f1=(S.fan/100)*16*dt; fanSets.ht.forEach(g=>{ g.rotation.y+=f1; });
      const f2=(S.fanLT/100)*16*dt; fanSets.lt.forEach(g=>{ g.rotation.y+=f2; });
      const f3=(S.fanSup/100)*18*dt; fanSets.sup.forEach(g=>{ g.rotation.y+=f3; });
      const f4=(S.fanExh/100)*18*dt; fanSets.exh.forEach(g=>{ g.rotation.y+=f4; });
      const sp={gas:S.valves?clamp(V.gas/160,0,1.4)*1.5:0, exh:S.rpm>200?(S.rpm/1500)*2.4:0, loopA:V.flow>0.5?V.flow/30*1.1:0, boil:V.qBoiler>3?V.flow/30*1.3:0, cool:V.qCooler>3?1.2:0,
        lt:V.flowLT>0.5?V.flowLT/20*1.2:0, air:S.rpm>200?(S.rpm/1500)*1.8:0, byp:(S.bypass>0.3&&S.rpm>200)?2.0*S.bypass:0, topup:S.topup?0.8:0};
      flows.forEach(f=>{ f.tex.offset.x-=(sp[f.grp]||0)/0.6*dt; });
      updateSmoke(dt);
    }
    updateHighlight(t);
  }
  function resize(){
    const w=wrap.clientWidth, h=wrap.clientHeight; if(!w||!h) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2)); renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix();
  }
  if(window.ResizeObserver) new ResizeObserver(resize).observe(wrap); else window.addEventListener('resize',resize);
  let visible=true; if(window.IntersectionObserver) new IntersectionObserver(es=>{ visible=es[0].isIntersecting; }).observe(wrap);

  /* --- тема: слухачі --- */
  const mq=window.matchMedia('(prefers-color-scheme: dark)');
  if(mq.addEventListener) mq.addEventListener('change',applyTheme); else if(mq.addListener) mq.addListener(applyTheme);
  new MutationObserver(applyTheme).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  if(document.fonts&&document.fonts.ready) document.fonts.ready.then(paintLabel);

  applyTheme(); setShell('cut'); resize(); applySys();
  for(let i=0;i<80;i++) updateSmoke(0.1);
  let last=performance.now();
  function frame(ts){
    requestAnimationFrame(frame);
    const dt=Math.min(0.1,(ts-last)/1000); last=ts;
    if(document.hidden||!visible) return;
    animate(dt,ts/1000); controls.update(); renderer.render(scene,camera);
  }
  requestAnimationFrame(frame);
}

/* ===== Головний цикл ===== */
function renderAll(){ renderHeader(); renderControl(); renderKPI(); renderLayers(); renderNodeDetail(false); renderJournal(); renderTO(); renderDiag(); }
let lastTick=performance.now();
function tick(){
  const now=performance.now(); let dt=(now-lastTick)/1000; lastTick=now; dt=Math.min(dt,1);
  step(dt); pushHist(); renderAll();
  if(S.tab==='main'&&Date.now()-TR.last>(TR.range===1?2000:5000)) drawTrend();
}
function init(){
  seedJournal(); synthHistory(); bind(); buildNodeList(); setSystem('all'); buildTO(); initSyncDial(); initTrend(); initLayers(); bindEvents();
  computeV(0.25); renderNodeDetail(true); renderAll(); drawTrend();
  init3D();
  setInterval(tick,250);
}
init();
})();
</script>
