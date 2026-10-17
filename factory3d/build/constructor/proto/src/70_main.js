/* ===== збереження, версії, площадки, запуск ===== */
S.snaps = {}; S.snapSaved = new Set(); S.saving = false;
const markDirty = (k) => S.dirty.add(k);
const scheduleSave = debounce(() => { flush(); }, 700);

function curTheme() { const t = document.documentElement.dataset.theme; return t || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); }
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem('f3d-theme', t); } catch (e) { /* ок */ }
  V.theme = curTheme();
  if (V.ok) { recolorMats(); syncScene(true); }
  renderTop(); renderStamp();
}

/* --- diff чернетки відносно активної версії --- */
function mapOf(src) {
  const m = new Map(), rj = (r) => { const c = Object.assign({}, r); delete c.visible; return JSON.stringify(c); };
  for (const l of src.layers) m.set('l:' + l.id, rj(l));
  for (const s of src.slots) m.set('s:' + s.id, rj(s));
  for (const p of src.placements) m.set('p:' + p.id, rj(p));
  for (const pp of src.catalog) { m.set('t:' + pp.id, JSON.stringify([pp.category, pp.name, pp.manufacturer, pp.model, pp.role])); for (const v of pp.variants) m.set('v:' + v.id, JSON.stringify(v)); }
  m.set('site', JSON.stringify([src.site.name, src.site.building, src.site.column_grid]));
  m.set('cfg', JSON.stringify([src.settings.checks, src.settings.reach_n]));
  return m;
}
function buildBaseMap() { S.baseMap = S.base ? mapOf(S.base) : null; }
function computeChanged() {
  if (!S.baseMap) { S.changed = 0; return; }
  const cur = mapOf(S); let n = 0;
  for (const [k, v] of cur) if (S.baseMap.get(k) !== v) n++;
  for (const k of S.baseMap.keys()) if (!cur.has(k)) n++;
  S.changed = n;
}

/* --- запис у сховище --- */
async function writeColl(c) {
  const id = S.site.id;
  switch (c) {
    case 'sites': return store.set('sites', id, S.site);
    case 'layers': return store.set('layers', id, S.layers);
    case 'slots': return store.set('slots', id, S.slots);
    case 'placements': return store.set('placements', id, S.placements);
    case 'catalog': return store.set('catalog', id, S.catalog);
    case 'settings': return store.set('settings', id, { checks: S.settings.checks, reach_n: S.settings.reach_n, labels: S.settings.labels, underlays: S.settings.underlays });
    case 'versions': return store.set('versions', id, S.versions);
    case 'app': return store.set('settings', 'app', { sites: S.app.sites, active: S.app.active });
    default: return null;
  }
}
async function flush() {
  if (S.saving) { S.again = true; return; }
  if (S.persisted && !S.dirty.size) return;
  S.saving = true; let d = [];
  try {
    if (!S.persisted) for (const k of ['sites', 'layers', 'slots', 'placements', 'catalog', 'settings', 'versions', 'app']) S.dirty.add(k);
    d = [...S.dirty]; S.dirty.clear();
    for (const c of d) await writeColl(c);
    for (const n of Object.keys(S.snaps)) { const key = S.site.id + ':' + n; if (!S.snapSaved.has(key)) { await store.set('versions', S.site.id + '.v' + n, S.snaps[n]); S.snapSaved.add(key); } }
    S.persisted = true;
  } catch (e) {
    console.warn(e); d.forEach((c) => S.dirty.add(c));
    toast('Не вдалося зберегти зміни: ' + (e && e.message ? e.message : e), 'err');
  } finally { S.saving = false; if (S.again) { S.again = false; scheduleSave(); } renderNotice(); }
}
async function flushNow() { while (S.saving) await sleep(15); await flush(); while (S.saving) await sleep(15); }
const markAllDirty = () => ['sites', 'layers', 'slots', 'placements', 'catalog', 'settings', 'versions', 'app'].forEach(markDirty);

/* --- зміна стану: дискретні дії --- */
function commit(opts) {
  opts = opts || {};
  (opts.dirty || []).forEach(markDirty);
  reindex(); S.issues = runChecks();
  syncScene(); renderAll(); if (S.persisted || (opts.dirty || []).length) scheduleSave();
}

/* --- завантаження площадки --- */
function applyLoaded(st) {
  S.site = st.site; S.layers = st.layers; S.slots = st.slots; S.placements = st.placements; S.catalog = st.catalog;
  S.settings = Object.assign(defaultSettings(), st.settings || {});
  S.settings.checks = Object.assign(defaultChecks(), S.settings.checks || {}); S.settings.underlays = S.settings.underlays || {};
  S.versions = st.versions || []; S.base = st.base || null; S.snaps = st.snaps || {}; S.snapSaved = new Set(st.savedKeys || []);
  for (const l of S.layers) { l.aisles = l.aisles || []; l.fire_paths = l.fire_paths || []; l.utilities = l.utilities || []; }
  reindex(); buildBaseMap();
  S.sel = null; S.selCell = null; S.edit = null; S.dirty.clear();
  const first = S.layers.find((l) => l.kind === 'production') || S.layers.find((l) => l.kind !== 'building') || S.layers[0];
  S.ui.layer = first.id; S.ui.dxfScale = null;
  V.models.clear();
  S.issues = runChecks(); computeChanged();
}
async function loadSiteFromStore(id) {
  const [site, layers, slots, pls, cat, set, vers] = await Promise.all(['sites', 'layers', 'slots', 'placements', 'catalog', 'settings', 'versions'].map((c) => store.get(c, id)));
  if (!site || !layers || !cat) return null;
  const av = site.active_version || 0, base = await store.get('versions', id + '.v' + av);
  return { site, layers, slots: slots || [], placements: pls || [], catalog: cat, settings: set || defaultSettings(), versions: vers || [], base, snaps: {}, savedKeys: base ? [id + ':' + av] : [] };
}
async function bootData() {
  const app = await store.get('settings', 'app');
  if (app && app.sites && app.sites.length) {
    S.app.sites = app.sites; S.app.active = app.sites.some((s) => s.id === app.active) ? app.active : app.sites[0].id;
    const st = await loadSiteFromStore(S.app.active);
    if (st) { S.persisted = true; applyLoaded(st); await addFullSample(); return; }
  }
  const st = buildSample(); st.snaps = { 1: st.base };
  S.app.sites = [{ id: 'sample', name: st.site.name }]; S.app.active = 'sample'; S.persisted = false; applyLoaded(st);
}
/* Збережений приклад старшої версії (неповний набір шарів і об'єктів) лишається з правками користувача;
   повний приклад додається окремою площадкою й стає активним. */
async function addFullSample() {
  const FULL = 'sample_full';
  if (!S.app.sites.some((s) => s.id === 'sample') || S.app.sites.some((s) => s.id === FULL)) return;
  const old = await store.get('sites', 'sample');
  if (!old || (old.seed_rev || 0) >= SEED_REV) return;
  const st = buildSample(FULL); st.snaps = { 1: st.base };
  st.site.name = 'Меблеве підприємство (повний приклад)';
  S.app.sites.push({ id: FULL, name: st.site.name }); S.app.active = FULL;
  applyLoaded(st); markAllDirty(); S.persisted = true;
  await flushNow();
  toast('Додано повний приклад: усі шари й об’єкти моделі. Попередній приклад з вашими правками — у списку площадок.');
}
async function afterSiteLoad() {
  renderAll(); syncScene(true); setView('iso');
  await Promise.all([loadVariantModels(), loadUnderlays()]);
}
async function switchSite(id) {
  if (id === S.app.active) return;
  await flushNow();
  const st = await loadSiteFromStore(id);
  if (!st) { toast('Не вдалося відкрити площадку.', 'err'); renderTop(); return; }
  S.app.active = id; applyLoaded(st); markDirty('app'); scheduleSave();
  await afterSiteLoad();
}
async function createSite(kind, name) {
  if (!S.persisted) { await flushNow(); }
  const st = kind === 'sample' ? buildSample() : buildEmptySite(name);
  if (kind === 'sample') st.snaps = { 1: st.base };
  else { st.base = makeSnapshot(st); st.snaps = { 0: st.base }; }
  st.site.name = name;
  S.app.sites.push({ id: st.site.id, name }); S.app.active = st.site.id;
  applyLoaded(st); markAllDirty(); S.persisted = true;
  await flushNow();
  await afterSiteLoad();
  toast(kind === 'sample' ? 'Приклад завантажено в сховище.' : 'Створено порожню площадку.');
}
async function revertTo(n) {
  const snap = S.snaps[n] || await store.get('versions', S.site.id + '.v' + n);
  if (!snap) { toast('Знімок версії не знайдено.', 'err'); return; }
  const c = clone(snap), av = S.site.active_version, nm = S.site.name;
  S.site = c.site; S.site.active_version = av; S.site.name = nm;
  S.layers = c.layers; S.slots = c.slots; S.placements = c.placements; S.catalog = c.catalog;
  S.settings.checks = Object.assign(defaultChecks(), c.settings.checks); S.settings.reach_n = c.settings.reach_n;
  reindex(); S.sel = null; S.selCell = null;
  if (!layerOf(S.ui.layer)) S.ui.layer = S.layers[0].id;
  V.models.clear();
  commit({ dirty: ['sites', 'layers', 'slots', 'placements', 'catalog', 'settings'] });
  loadVariantModels();
  toast(`Чернетку повернуто до версії ${n}.`);
}

/* --- події --- */
function bindEvents() {
  $('#siteSel').addEventListener('change', (e) => {
    const v = e.target.value;
    if (v.startsWith('__new:')) {
      renderTop();
      if (!(S.app.role === 'manager' && S.app.mode === 'edit')) { toast('Площадки створює Менеджер у режимі редагування.', 'warn'); return; }
      const k = v.slice(6); createSite(k, k === 'sample' ? 'Меблеве підприємство (приклад)' : 'Порожня площадка');
    } else switchSite(v);
  });
  $('#roleSel').addEventListener('change', (e) => { S.app.role = e.target.value; S.edit = null; S.issues = runChecks(); renderAll(); const ly = layerOf(S.ui.layer); if (ly && S.app.mode === 'edit' && !canEditLayer(ly)) toast(lockHint(ly), 'warn'); });
  $$('#modeSeg button').forEach((b) => b.addEventListener('click', () => { S.app.mode = b.dataset.mode; S.edit = null; cancelModes(); renderAll(); }));
  $('#btnNewSite').addEventListener('click', openNewSite);
  $('#btnPublish').addEventListener('click', openPublish);
  $('#btnHistory').addEventListener('click', openHistory);
  $('#btnTheme').addEventListener('click', () => applyTheme(curTheme() === 'dark' ? 'light' : 'dark'));
  $$('#ltabs button').forEach((b) => b.addEventListener('click', () => setLeftTab(b.dataset.tab)));
  $$('#mtabs button').forEach((b) => b.addEventListener('click', () => setMTab(b.dataset.mtab)));
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (!document.documentElement.dataset.theme) applyTheme(curTheme()); });
  document.addEventListener('keydown', onKey);
}
function nudge(dx, dy) {
  if (!S.sel) return; const rec = recOfRef(S.sel), ly = layerOf(rec.layer_id);
  if (!canEditLayer(ly)) { toastLock(ly); return; }
  const kind = S.sel.kind, st = ly.grid_step || 0.5;
  beginEdit(kind, rec); rec.x = rnd(rec.x + dx * st, 4); rec.y = rnd(rec.y + dy * st, 4);
  liveEdit([kind === 'placement' ? 'placements' : 'slots']); endEdit(); syncPropsValues();
}
function onKey(e) {
  const t = e.target, typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT');
  if (document.querySelector('dialog[open]')) return;
  if (e.key === 'Escape') { if (V.placing || V.ruler.on || V.pickMode) cancelModes(); else if (S.sel) selectObj(null); return; }
  if (typing) return;
  if (e.ctrlKey || e.metaKey || e.altKey && e.code !== 'KeyR') return;
  if (e.code === 'KeyR') { e.preventDefault(); rotateSel(e.shiftKey ? -1 : 1); }
  else if (e.code === 'Delete' || e.code === 'Backspace') { if (S.sel) { e.preventDefault(); askDelete(); } }
  else if (e.code === 'KeyM') { const on = !V.ruler.on; cancelModes(); V.ruler.on = on; renderVTools(); }
  else if (e.code.startsWith('Arrow') && S.sel) {
    e.preventDefault(); const k = e.shiftKey ? 10 : 1;
    nudge(e.code === 'ArrowRight' ? k : e.code === 'ArrowLeft' ? -k : 0, e.code === 'ArrowUp' ? k : e.code === 'ArrowDown' ? -k : 0);
  }
}

async function boot() {
  try { const t = localStorage.getItem('f3d-theme'); if (t === 'dark' || t === 'light') document.documentElement.dataset.theme = t; } catch (e) { /* ок */ }
  V.theme = curTheme();
  await store.init();
  await bootData();
  initScene();
  bindEvents();
  window.__f3d = { S, V, store, files, runChecks, setView, commit, cellsOf, buildSample, computeDiff, openPublish, openHistory, parseDxf, selectObj, flushNow, createSite, switchSite, startPlacing, addPlacementAt, pGeom, sGeom };
  await afterSiteLoad();
  document.documentElement.dataset.ready = '1';
}
boot().catch((e) => { console.error('boot', e); const b = $('#app'); if (b) b.append(h('div', { class: 'note err', style: { position: 'fixed', left: '10px', bottom: '10px', zIndex: 200 } }, 'Помилка запуску: ' + (e && e.message ? e.message : e))); });
