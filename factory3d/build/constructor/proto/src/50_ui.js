/* ===== інтерфейс: права, форми, панелі ===== */
const canEditLayer = (ly) => !!ly && S.app.mode === 'edit' && ly.edit_roles.includes(S.app.role);
const canManage = () => S.app.mode === 'edit' && S.app.role === 'manager';
const canCatalog = () => S.app.mode === 'edit' && (S.app.role === 'manager' || S.app.role === 'technologist');
function lockHint(ly) {
  if (S.app.mode !== 'edit') return 'Режим перегляду: правка вимкнена. Увімкніть «Редагування».';
  const rs = ly.edit_roles.filter((r) => r !== 'manager').map(roleName), mg = ly.edit_roles.includes('manager');
  return `Шар «${ly.name}» редагує ${rs.length ? rs.join(', ') + (mg ? ' і Менеджер' : '') : 'Менеджер'}`;
}
const toastLock = (ly) => toast(lockHint(ly), 'warn');

/* ===== побудова полів ===== */
function numInput(o) {
  const el = h('input', { type: 'number', step: o.step == null ? 'any' : o.step, min: o.min, max: o.max, value: o.value == null ? '' : String(rnd(o.value, 4)), disabled: o.dis, 'data-f': o.f, inputmode: 'decimal', 'aria-label': o.label });
  if (!o.dis) {
    el.addEventListener('focus', () => o.begin && o.begin());
    el.addEventListener('input', () => {
      if (el.value === '' || el.validity.badInput) return;
      let v = parseFloat(el.value); if (!isFinite(v)) return;
      if (o.int) v = Math.round(v);
      if (o.min != null && v < o.min - 1e-9) return;
      if (o.max != null && v > o.max + 1e-9) return;
      o.set(v);
    });
    el.addEventListener('change', () => o.end && o.end());
  }
  return el;
}
const fld = (label, el, unit, cls) => h('label', { class: 'fld' + (cls ? ' ' + cls : '') }, h('span', null, label, unit ? h('i', null, ' · ' + unit) : null), el);
function textInput(o) {
  const el = h('input', { type: 'text', value: o.value == null ? '' : o.value, disabled: o.dis, 'aria-label': o.label, 'data-f': o.f });
  if (!o.dis) { el.addEventListener('focus', () => o.begin && o.begin()); el.addEventListener('input', () => o.set(el.value)); el.addEventListener('change', () => o.end && o.end()); }
  return el;
}
function selectEl(opts, value, onChange, dis, label) {
  const el = h('select', { disabled: dis, 'aria-label': label }, opts.map(([v, t]) => h('option', { value: v, selected: String(v) === String(value) }, t)));
  el.addEventListener('change', () => onChange(el.value));
  return el;
}
function checkGroup(opts, vals, onChange, dis) {
  return h('div', { class: 'checks' }, opts.map(([v, t]) => {
    const cb = h('input', { type: 'checkbox', checked: vals.includes(v), disabled: dis });
    cb.addEventListener('change', () => { const cur = new Set(vals); if (cb.checked) cur.add(v); else cur.delete(v); onChange([...cur]); });
    return h('label', null, cb, t);
  }));
}
function paramFields(tpl, params, o) { // o: {dis, begin, end, onChange}
  const spec = TPL[tpl];
  return h('div', { class: 'grid2' }, spec.params.map((p) => {
    const val = getp(params, p.k);
    if (p.type === 'text') return fld(p.l, textInput({ value: val, dis: o.dis, label: p.l, begin: o.begin, end: o.end, set: (v) => { setp(params, p.k, v); o.onChange(); } }), null, 'span2');
    if (p.type === 'color') { const c = h('input', { type: 'color', value: val || '#9fb7c9', disabled: o.dis, 'aria-label': p.l }); c.addEventListener('focus', () => o.begin && o.begin()); c.addEventListener('input', () => { setp(params, p.k, c.value); o.onChange(); }); c.addEventListener('change', () => o.end && o.end()); return fld(p.l, c); }
    return fld(p.l, numInput({ value: val, min: p.min, max: p.max, step: p.step, int: p.int, dis: o.dis, label: p.l, f: 'p.' + p.k, begin: o.begin, end: o.end, set: (v) => { setp(params, p.k, v); o.onChange(); } }), p.u);
  }));
}

/* ===== верхня панель ===== */
function renderTop() {
  const ss = $('#siteSel'); ss.replaceChildren(...S.app.sites.map((s) => h('option', { value: s.id, selected: s.id === S.app.active }, s.name)),
    S.app.sites.some((s) => s.id !== 'sample') ? null : h('option', { value: '__new:empty' }, '+ Порожня площадка'),
    S.app.sites.some((s) => s.id === 'sample') ? null : h('option', { value: '__new:sample' }, '+ Меблеве підприємство (приклад)'));
  const rs = $('#roleSel'); rs.replaceChildren(...ROLES.map((r) => h('option', { value: r.id, selected: r.id === S.app.role }, r.name)));
  $$('#modeSeg button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.mode === S.app.mode)));
  const pub = $('#btnPublish'); pub.disabled = !(S.app.mode === 'edit' && S.app.role === 'manager');
  pub.title = pub.disabled ? 'Публікує Менеджер у режимі редагування' : '';
  $('#btnNewSite').disabled = !(S.app.role === 'manager' && S.app.mode === 'edit');
  renderChips();
  const tt = $('#btnTheme'); tt.replaceChildren(ic(curTheme() === 'dark' ? 'sun' : 'moon'));
  $('#storeTag').textContent = store.kind === 'db' ? 'Збереження: база артефакта' : store.kind === 'local' ? 'Збереження: браузер' : 'Без збереження (лише сесія)';
}
function renderChips() {
  computeChanged();
  const chip = $('#draftChip'), n = S.changed;
  chip.textContent = isNarrow() ? `Чернетка · ${n || 0}` : (n ? `Чернетка · змінено ${n}` : 'Чернетка · без змін');
  chip.classList.toggle('dirty', n > 0);
  const v = S.site && S.site.active_version ? 'v' + S.site.active_version : 'не опубліковано';
  chip.title = 'Активна версія: ' + v;
}

/* ===== вкладки ===== */
function updateTabs() {
  $$('#ltabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === S.ui.leftTab)));
  const m = $('#app').dataset.mtab;
  $$('#mtabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.mtab === m)));
}
function setLeftTab(t) { S.ui.leftTab = t; $('#app').dataset.mtab = t; renderLeft(); updateTabs(); }
function setMTab(t) { if (t === 'props') { $('#app').dataset.mtab = 'props'; updateTabs(); renderRight(); } else setLeftTab(t); }
const isNarrow = () => window.matchMedia('(max-width: 900px)').matches;
function renderLeft() {
  const root = $('#leftBody'); root.replaceChildren();
  if (S.ui.leftTab === 'layers') renderLayersTab(root);
  else if (S.ui.leftTab === 'slots') renderSlotsTab(root);
  else renderCatalogTab(root);
}
function renderAll() { renderTop(); renderLeft(); renderRight(); renderVTools(); renderStamp(); renderNotice(); renderDxfPanel(); updateTabs(); }

/* ===== шари ===== */
function setActiveLayer(id) {
  if (S.ui.layer === id) return;
  const nl = layerOf(id); if (nl && !nl.visible) { nl.visible = true; markDirty('layers'); if (S.persisted) scheduleSave(); } // активний шар завжди видимий
  S.ui.layer = id; S.issues = runChecks();
  syncScene(); renderLayerList(); renderLayerForm(); renderStamp(); renderDxfPanel(); if (S.ui.leftTab === 'slots') renderLeft();
  requestRender();
}
function renderLayersTab(root) {
  const add = h('button', { class: 'btn sm', type: 'button', disabled: !canManage(), onclick: addLayer, title: canManage() ? '' : 'Шари додає Менеджер' }, ic('plus'), 'Шар');
  root.append(h('div', { class: 'sec' }, h('h3', null, 'Шари', add), h('div', { id: 'layerList' })), h('div', { class: 'sec', id: 'layerForm' }));
  renderLayerList(); renderLayerForm();
}
function renderLayerList() {
  const box = $('#layerList'); if (!box) return;
  const lys = [...S.layers].sort((a, b) => a.sequence - b.sequence), cnt = new Map();
  for (const x of S.slots) cnt.set(x.layer_id, (cnt.get(x.layer_id) || 0) + 1);
  for (const x of S.placements) cnt.set(x.layer_id, (cnt.get(x.layer_id) || 0) + 1);
  const rows = []; let grp = null;
  for (const ly of lys) {
    if (ly.group && ly.group !== grp) {
      const gl = lys.filter((l) => l.group === ly.group);
      rows.push(h('div', { class: 'lgroup', role: 'presentation' }, h('span', null, ly.group), h('span', { class: 'c' }, gl.length)));
    }
    grp = ly.group || null;
    const n = cnt.get(ly.id) || 0;
    rows.push(h('div', { class: 'layer' + (ly.id === S.ui.layer ? ' active' : '') + (ly.visible ? '' : ' hidden'), role: 'button', tabindex: 0, 'data-layer': ly.key || ly.id, onclick: () => setActiveLayer(ly.id), onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveLayer(ly.id); } } },
      h('button', { class: 'eye', type: 'button', 'aria-label': ly.visible ? 'Сховати шар' : 'Показати шар', onclick: (e) => { e.stopPropagation(); ly.visible = !ly.visible; markDirty('layers'); S.issues = runChecks(); syncScene(); renderLayerList(); if (S.persisted) scheduleSave(); } }, ic(ly.visible ? 'eye' : 'eyeoff')),
      h('span', { class: 'sw', style: { background: ly.color } }),
      h('span', { class: 'nm', title: ly.name }, ly.name),
      canEditLayer(ly) ? null : h('span', { class: 'ic', title: lockHint(ly) }, ic('lock')),
      h('span', { class: 'meta' }, (ly.elevation >= 0 ? '+' : '') + fmt(ly.elevation, 1) + ' м · ' + n)));
  }
  const keep = box.querySelector('.layers'), top = keep ? keep.scrollTop : 0;
  box.replaceChildren(h('div', { class: 'layers' + (lys.length > 12 ? ' tall' : '') }, rows));
  const nl = box.querySelector('.layers'); if (nl) { nl.scrollTop = top; const act = nl.querySelector('.layer.active'); if (act && !keep) act.scrollIntoView({ block: 'nearest' }); }
}
function addLayer() {
  const ly = mkLayer(S.site.id, { name: 'Новий шар', kind: 'custom', elevation: 3, grid_step: 0.5, color: '#9a6bb3', sequence: Math.max(0, ...S.layers.map((l) => l.sequence)) + 1, max_floor_load: 10 });
  S.layers.push(ly); S.ui.layer = ly.id; commit({ dirty: ['layers'] });
}
function layerEdit(dirtyFn) { dirtyFn(); markDirty('layers'); S.issues = runChecks(); syncScene(); renderLayerList(); renderChecksBlock(); renderChips(); scheduleSave(); }
function renderLayerForm() {
  const box = $('#layerForm'); if (!box) return;
  const ly = layerOf(S.ui.layer); box.replaceChildren(); if (!ly) return;
  const dis = !canManage();
  const ed = (fn) => () => { layerEdit(fn); };
  const num = (label, key, unit, o) => fld(label, numInput(Object.assign({ value: ly[key], dis, label, set: (v) => layerEdit(() => { ly[key] = v; }) }, o)), unit);
  const frag = [];
  frag.push(h('h3', null, 'Параметри шару'));
  if (dis) frag.push(h('div', { class: 'note lock' }, S.app.mode === 'edit' ? 'Параметри шарів змінює Менеджер.' : lockHint(ly)));
  frag.push(h('div', { class: 'col' },
    fld('Назва', textInput({ value: ly.name, dis, label: 'Назва', set: (v) => layerEdit(() => { ly.name = v; }) })),
    fld('Група у списку', textInput({ value: ly.group || '', dis, label: 'Група', set: (v) => layerEdit(() => { ly.group = v.trim(); }) })),
    h('div', { class: 'grid2' },
      fld('Тип', selectEl(Object.entries(LAYER_KINDS), ly.kind, (v) => layerEdit(() => { ly.kind = v; }), dis, 'Тип')),
      num('Відмітка', 'elevation', 'м', { step: 0.1 })),
    h('div', { class: 'grid3' }, num('Крок сітки', 'grid_step', 'м', { step: 0.05, min: 0.05 }), num('Ширина проходів', 'aisle_width', 'м', { step: 0.1, min: 0 }), num('Навант. на підлогу', 'max_floor_load', 'кН/м²', { step: 1, min: 0 })),
    h('div', { class: 'row' }, fld('Колір', h('input', { type: 'color', value: ly.color, disabled: dis, onchange: (e) => layerEdit(() => { ly.color = e.target.value; }) })),
      fld('Непрозорість', h('input', { type: 'range', min: 0.1, max: 1, step: 0.05, value: ly.opacity, disabled: dis, oninput: (e) => layerEdit(() => { ly.opacity = parseFloat(e.target.value); }) }))),
    fld('Контур шару', h('div', { class: 'col' },
      h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: !!ly.bounds, disabled: dis, onchange: (e) => { layerEdit(() => { ly.bounds = e.target.checked ? { x0: 0, y0: 0, x1: S.site.building.length, y1: S.site.building.width } : null; }); renderLayerForm(); } }), 'Задати контур (інакше — межі будівлі)'),
      ly.bounds ? h('div', { class: 'grid4' }, ['x0', 'y0', 'x1', 'y1'].map((k) => numInput({ value: ly.bounds[k], dis, label: k, step: 0.5, set: (v) => layerEdit(() => { ly.bounds[k] = v; }) }))) : null), 'м'),
    h('label', { class: 'row', title: 'Мережі, пожежна безпека, ІТ: об’єкти шару не перевіряються на перетини, зони обслуговування, проходи й пожежні проходи' },
      h('input', { type: 'checkbox', checked: !!ly.overlay, disabled: dis, onchange: (e) => layerEdit(() => { ly.overlay = e.target.checked; }) }), 'Шар-накладка (мережі й системи)'),
    fld('Допустимі типи місць', checkGroup(Object.entries(TPL).map(([k, t]) => [k, t.name]), ly.slot_types, (v) => layerEdit(() => { ly.slot_types = v; }), dis)),
    fld('Редагують ролі', checkGroup(ROLES.map((r) => [r.id, r.name]), ly.edit_roles, (v) => layerEdit(() => { ly.edit_roles = v.includes('manager') ? v : ['manager', ...v]; }), dis)),
  ));
  // проходи
  const rectRows = (arr, kind) => arr.map((a, i) => h('div', { class: 'mini fp' },
    textInput({ value: a.name || '', dis, label: 'Назва', set: (v) => layerEdit(() => { a.name = v; }) }),
    ...['x0', 'y0', 'x1', 'y1'].map((k) => numInput({ value: a[k], dis, label: k, step: 0.1, set: (v) => layerEdit(() => { a[k] = v; }) })),
    h('button', { class: 'xbtn', type: 'button', disabled: dis, 'aria-label': 'Видалити', onclick: () => { layerEdit(() => arr.splice(i, 1)); renderLayerForm(); } }, ic('x'))));
  const cx = S.site.building.length / 2, cy = S.site.building.width / 2;
  const fireAll = ly.fire_paths || (ly.fire_paths = []);
  frag.push(h('hr'), h('div', { class: 'h3' }, 'Проходи шару'),
    h('div', null, rectRows(ly.aisles)),
    h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => { const t = camTarget(), w = ly.aisle_width || 2.5; layerEdit(() => ly.aisles.push({ id: uid('ai_'), name: 'Прохід ' + (ly.aisles.length + 1), x0: rnd(t.x - 6), y0: rnd(t.y - w / 2), x1: rnd(t.x + 6), y1: rnd(t.y + w / 2) })); renderLayerForm(); } }, ic('plus'), 'Прохід'));
  const paths = fireAll.filter((f) => f.kind === 'path'), exits = fireAll.filter((f) => f.kind === 'exit');
  frag.push(h('hr'), h('div', { class: 'h3' }, 'Пожежні проходи й виходи'),
    h('div', null, paths.map((a) => h('div', { class: 'mini fp' }, textInput({ value: a.name || '', dis, label: 'Назва', set: (v) => layerEdit(() => { a.name = v; }) }),
      ...['x0', 'y0', 'x1', 'y1'].map((k) => numInput({ value: a[k], dis, label: k, step: 0.1, set: (v) => layerEdit(() => { a[k] = v; }) })),
      h('button', { class: 'xbtn', type: 'button', disabled: dis, 'aria-label': 'Видалити', onclick: () => { layerEdit(() => fireAll.splice(fireAll.indexOf(a), 1)); renderLayerForm(); } }, ic('x'))))),
    exits.length ? h('details', null, h('summary', { class: 'small muted' }, `Виходи: ${exits.length}`), exits.map((a) => h('div', { class: 'mini u' }, textInput({ value: a.code || '', dis, label: 'Код', set: (v) => layerEdit(() => { a.code = v; a.name = 'Вихід ' + v; }) }),
      numInput({ value: a.x, dis, label: 'x', step: 0.5, set: (v) => layerEdit(() => { a.x = v; }) }), numInput({ value: a.y, dis, label: 'y', step: 0.5, set: (v) => layerEdit(() => { a.y = v; }) }),
      h('button', { class: 'xbtn', type: 'button', disabled: dis, 'aria-label': 'Видалити', onclick: () => { layerEdit(() => fireAll.splice(fireAll.indexOf(a), 1)); renderLayerForm(); } }, ic('x'))))) : null,
    h('div', { class: 'row wrap' },
      h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => { const t = camTarget(); layerEdit(() => fireAll.push({ id: uid('fp_'), kind: 'path', name: 'Пожежний прохід ' + (paths.length + 1), x0: rnd(t.x - 6), y0: rnd(t.y - 0.6), x1: rnd(t.x + 6), y1: rnd(t.y + 0.6) })); renderLayerForm(); } }, ic('plus'), 'Прохід'),
      h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => { layerEdit(() => fireAll.push({ id: uid('fp_'), kind: 'exit', code: 'EX-' + (exits.length + 1), name: 'Вихід EX-' + (exits.length + 1), x: rnd(cx), y: 0, side: 'S', w: 2, d: 2.5 })); renderLayerForm(); } }, ic('plus'), 'Вихід')));
  // мережі
  const ut = ly.utilities || (ly.utilities = []);
  frag.push(h('hr'), h('div', { class: 'h3' }, 'Точки щитів і магістралей'),
    ut.length ? h('details', null, h('summary', { class: 'small muted' }, `Точок: ${ut.length}`), ut.map((a) => h('div', { class: 'mini u' },
      selectEl(Object.entries(UTIL_KINDS), a.kind, (v) => layerEdit(() => { a.kind = v; }), dis, 'Вид'),
      numInput({ value: a.x, dis, label: 'x', step: 0.5, set: (v) => layerEdit(() => { a.x = v; }) }), numInput({ value: a.y, dis, label: 'y', step: 0.5, set: (v) => layerEdit(() => { a.y = v; }) }),
      h('button', { class: 'xbtn', type: 'button', disabled: dis, 'aria-label': 'Видалити', onclick: () => { layerEdit(() => ut.splice(ut.indexOf(a), 1)); renderLayerForm(); } }, ic('x'))))) : h('div', { class: 'small muted' }, 'Точок немає.'),
    h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => { const t = camTarget(); layerEdit(() => ut.push({ id: uid('u'), kind: 'electric', x: rnd(t.x, 1), y: rnd(t.y, 1) })); renderLayerForm(); } }, ic('plus'), 'Точка'));
  // порядок і видалення
  const sorted = [...S.layers].sort((a, b) => a.sequence - b.sequence), idx = sorted.indexOf(ly);
  const move = (d) => { const o = sorted[idx + d]; if (!o) return; layerEdit(() => { const t = ly.sequence; ly.sequence = o.sequence; o.sequence = t; if (ly.sequence === o.sequence) ly.sequence += d; }); renderLayerForm(); };
  frag.push(h('hr'), h('div', { class: 'row wrap' },
    h('button', { class: 'btn sm icon', type: 'button', disabled: dis || idx <= 0, 'aria-label': 'Вище', onclick: () => move(-1) }, ic('up')),
    h('button', { class: 'btn sm icon', type: 'button', disabled: dis || idx >= sorted.length - 1, 'aria-label': 'Нижче', onclick: () => move(1) }, ic('down')),
    h('span', { class: 'grow' }),
    h('button', { class: 'btn sm danger', type: 'button', disabled: dis || S.layers.length < 2, onclick: () => deleteLayer(ly) }, ic('trash'), 'Видалити шар')));
  box.append(...frag);
}
async function deleteLayer(ly) {
  const n = S.slots.filter((s) => s.layer_id === ly.id).length + S.placements.filter((p) => p.layer_id === ly.id).length;
  const ok = await confirmBox({ title: 'Видалити шар?', text: `Шар «${ly.name}»${n ? ` містить ${n} об’єктів — вони теж будуть видалені.` : '.'}`, ok: 'Видалити', danger: true });
  if (!ok) return;
  S.slots = S.slots.filter((s) => s.layer_id !== ly.id); S.placements = S.placements.filter((p) => p.layer_id !== ly.id); S.layers = S.layers.filter((l) => l.id !== ly.id);
  delete S.settings.underlays[ly.id]; files.del('dxf:' + S.site.id + ':' + ly.id); V.uldata.delete(ly.id);
  if (S.sel && !S.sIdx.has(S.sel.id) && !S.pIdx.has(S.sel.id)) S.sel = null;
  S.ui.layer = (S.layers.find((l) => l.kind === 'production') || S.layers[0]).id;
  commit({ dirty: ['layers', 'slots', 'placements', 'settings'] });
}

/* ===== місця (шаблони) ===== */
function renderSlotsTab(root) {
  const ly = layerOf(S.ui.layer); if (!ly) return;
  const dis = !canEditLayer(ly);
  const T = S.ui.tpl = S.ui.tpl || { template: 'pallet_rack', prefix: 'R1', params: clone(TPL.pallet_rack.def) };
  const spec = TPL[T.template];
  const sec = h('div', { class: 'sec' }, h('h3', null, 'Новий шаблон'));
  if (dis) sec.append(h('div', { class: 'note lock' }, lockHint(ly)));
  const allowed = ly.slot_types.includes(T.template);
  sec.append(h('div', { class: 'col' },
    fld('Шаблон', selectEl(Object.entries(TPL).map(([k, t]) => [k, t.name]), T.template, (v) => { T.template = v; T.params = clone(TPL[v].def); T.prefix = TPL[v].prefix; renderLeft(); }, false, 'Шаблон')),
    h('div', { class: 'small muted' }, spec.info),
    fld('Префікс коду', textInput({ value: T.prefix, label: 'Префікс', set: (v) => { T.prefix = v; } }), 'напр. FG-R1'),
    paramFields(T.template, T.params, { dis: false, onChange: () => { /* лише форма */ } }),
    !allowed ? h('div', { class: 'note err' }, `Шар «${ly.name}» не допускає цей шаблон. Змініть «Допустимі типи місць» у параметрах шару.`) : null,
    h('button', { class: 'btn primary', type: 'button', disabled: dis || !allowed, onclick: () => startPlacing({ kind: 'slot', template: T.template, prefix: T.prefix || spec.prefix, params: T.params }) }, 'Поставити на сцену')));
  root.append(sec);
  const slots = S.slots.filter((s) => s.layer_id === ly.id);
  const total = slots.reduce((a, s) => a + cellCount(s), 0);
  root.append(h('div', { class: 'sec' }, h('h3', null, `Місця шару · ${slots.length}`),
    slots.length ? h('div', { class: 'rowlist' }, slots.map((s) => h('div', { class: 'it' + (S.sel && S.sel.id === s.id ? ' sel' : ''), role: 'button', tabindex: 0, onclick: () => { selectObj({ kind: 'slot', id: s.id }); focusOn(s.x, s.y); }, onkeydown: (e) => { if (e.key === 'Enter') { selectObj({ kind: 'slot', id: s.id }); focusOn(s.x, s.y); } } },
      h('span', { class: 't' }, (s.template === 'zone' ? s.params.title + ' · ' : '') + s.code_prefix), h('span', { class: 'tag' }, TPL[s.template].name.split(' ')[0]), h('span', { class: 'm' }, SOLID_SLOTS.includes(s.template) ? cellCount(s) + ' ком.' : '—')))) : h('div', { class: 'empty' }, 'На цьому шарі місць ще немає.'),
    h('div', { class: 'small muted', style: { marginTop: '6px' } }, `Комірок на шарі: ${fmtInt(total)}`)));
}

/* ===== каталог ===== */
function renderCatalogTab(root) {
  const dis = !canCatalog(), q = (S.ui.catQ || '').toLowerCase();
  root.append(h('div', { class: 'sec' }, h('h3', null, 'Каталог обладнання',
    h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => openPassportDialog(null) }, ic('plus'), 'Тип')),
    h('input', { type: 'text', placeholder: 'Пошук: тип, виробник, модель', value: S.ui.catQ || '', 'aria-label': 'Пошук', style: { width: '100%' }, oninput: (e) => { S.ui.catQ = e.target.value; const pos = e.target.selectionStart; renderLeft(); const ni = $('#leftBody input[type=text]'); if (ni) { ni.focus(); ni.setSelectionRange(pos, pos); } } })));
  if (dis) root.append(h('div', { class: 'note lock', style: { marginBottom: '8px' } }, S.app.mode === 'edit' ? 'Каталог редагують Менеджер і Технолог.' : 'Режим перегляду.'));
  for (const [ck, cn] of Object.entries(CATEGORIES)) {
    const pps = S.catalog.filter((p) => p.category === ck && (!q || (p.name + ' ' + p.manufacturer + ' ' + p.model + ' ' + p.variants.map((v) => v.name).join(' ')).toLowerCase().includes(q)));
    if (!pps.length) continue;
    root.append(h('details', { class: 'cat', open: true },
      h('summary', null, cn, h('span', { class: 'c' }, pps.reduce((a, p) => a + p.variants.length, 0))),
      pps.map((p) => h('div', { class: 'pp' },
        h('div', { class: 'ph' }, h('b', null, p.name), h('button', { class: 'btn sm', type: 'button', title: 'Тип: виробник, модель, категорія', onclick: () => openPassportDialog(p.id) }, 'Тип')),
        h('div', { class: 'mf' }, [p.manufacturer, p.model].filter((x) => x && x !== '—').join(' · ') || 'без виробника'),
        p.variants.map((v) => h('div', { class: 'var', draggable: 'true', title: 'Перетягніть на сцену', ondragstart: (e) => { e.dataTransfer.setData('text/f3d-variant', v.id); e.dataTransfer.setData('text/plain', v.name); e.dataTransfer.effectAllowed = 'copy'; } },
          h('span', { class: 'vn' }, v.name),
          h('span', { class: 'vm' }, `${fmt(v.length / 1000, 1)}×${fmt(v.width / 1000, 1)}×${fmt(v.height / 1000, 1)} м`, v.model ? h('span', { class: 'tag', title: 'Є 3D-модель' }, '3D') : null),
          h('button', { class: 'btn sm icon', type: 'button', title: 'Поставити на сцену', 'aria-label': 'Поставити на сцену', onclick: () => startPlacing({ kind: 'placement', variantId: v.id }) }, ic('plus')),
          h('button', { class: 'btn sm', type: 'button', onclick: () => openVariantCard(p.id, v.id) }, 'Картка'))),
        h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => { const nv = mkVariant({ name: 'Новий варіант', length: p.variants[0] ? p.variants[0].length : 2000, width: p.variants[0] ? p.variants[0].width : 1000, height: p.variants[0] ? p.variants[0].height : 1800 }); openVariantCard(p.id, nv.id, nv); } }, ic('plus'), 'Варіант')))));
  }
  root.append(h('div', { class: 'sec', style: { marginTop: '12px' } }, h('h3', null, 'Підкладка'),
    h('button', { class: 'btn', type: 'button', onclick: () => openDxfPanel() }, ic('upload'), 'Підкладка DXF'),
    h('div', { class: 'small muted', style: { marginTop: '4px' } }, 'DXF для обведення в масштабі; DWG — на сервері.')));
}

/* ===== область 3D: інструменти, штамп, повідомлення ===== */
function renderVTools() {
  const box = $('#vtools'); if (!box) return;
  const b = (icon, label, fn, pressed) => h('button', { class: 'btn', type: 'button', onclick: fn, 'aria-pressed': pressed == null ? null : String(!!pressed), title: label, 'aria-label': label }, ic(icon), h('span', { class: 'lg' }, label));
  box.replaceChildren(
    b('cube', '3D', () => setView('iso')), b('plan', 'План', () => setView('plan')), b('fit', 'Вписати', () => setView(V.camMode || 'iso')),
    b('ruler', 'Лінійка', () => { const on = !V.ruler.on; cancelModes(); V.ruler.on = on; if (on) toast('Лінійка: клацніть дві точки на підлозі активного шару.'); renderVTools(); }, V.ruler.on),
    b('tag', 'Підписи', () => { S.settings.labels = !S.settings.labels; requestRender(); renderVTools(); }, S.settings.labels),
    V.placing ? h('button', { class: 'btn danger', type: 'button', onclick: cancelModes }, ic('x'), h('span', null, 'Скасувати')) : null);
}
function renderStamp() {
  const st = $('#stamp'); if (!st || !S.site) return;
  const ly = layerOf(S.ui.layer);
  st.replaceChildren(
    h('div', null, 'Площадка'), h('div', { class: 'mono' }, S.site.name.length > 22 ? S.site.name.slice(0, 21) + '…' : S.site.name),
    h('div', null, 'Шар'), h('div', { class: 'mono' }, ly ? ly.name : '—'),
    h('div', null, 'Відмітка'), h('div', { class: 'mono' }, ly ? (ly.elevation >= 0 ? '+' : '') + fmt(ly.elevation, 1) + ' м' : '—'),
    h('div', null, 'Сітка'), h('div', { class: 'mono' }, ly ? fmt(ly.grid_step, 2) + ' м' : '—'),
    h('div', null, 'Курсор'), h('div', { class: 'mono', id: 'curPos' }, '—'),
    h('div', null, 'Об’єкт'), h('div', { class: 'mono', id: 'hoverName', style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '190px' } }, '—'));
}
function updateStamp() { const el = $('#curPos'); if (el) el.textContent = `x ${fmt(V.cursor.x, 1)} · y ${fmt(V.cursor.y, 1)}`; }
function renderNotice() {
  const box = $('#vnotice'); if (!box) return; box.replaceChildren();
  if (S.site && S.site.sample && !S.persisted && !S.dirty.size && !S.ui.noticeClosed)
    box.append(h('div', { class: 'note' }, 'Відкрито приклад без збереження. Запис у сховище почнеться після першої зміни.',
      h('div', { class: 'row', style: { marginTop: '6px' } },
        h('button', { class: 'btn sm', type: 'button', onclick: async () => { markAllDirty(); await flushNow(); renderNotice(); renderTop(); toast('Приклад завантажено в сховище.'); } }, ic('upload'), 'Завантажити приклад'),
        h('button', { class: 'btn sm', type: 'button', onclick: () => { S.ui.noticeClosed = true; renderNotice(); } }, 'Закрити'))));
}
/* ===== вибір ===== */
function selectObj(ref) {
  S.sel = ref ? { kind: ref.kind, id: ref.id } : null; S.selCell = null; S.edit = null;
  if (ref) { const rec = recOfRef(ref); if (rec && rec.layer_id !== S.ui.layer) { S.ui.layer = rec.layer_id; S.issues = runChecks(); syncScene(); renderLayerList(); renderLayerForm(); renderStamp(); } }
  renderRight(); updateVisual(); { const rb = $('#rightBody'); if (rb) rb.scrollTop = 0; }
  if (S.ui.leftTab === 'slots') renderLeft();
  if (ref && isNarrow() && $('#app').dataset.mtab !== 'props') { $('#app').dataset.mtab = 'props'; updateTabs(); }
}

/* ===== сеанс правки (live у формі, блокування — при завершенні) ===== */
function beginEdit(kind, rec) { if (!S.edit || S.edit.rec !== rec) S.edit = { kind, rec, snap: clone(rec), before: S.issues }; }
function liveEdit(dirty) {
  markDirty(dirty); S.issues = runChecks(); syncScene();
  renderChecksBlock(); renderChips(); renderLayerList(); renderDerived(); renderCellsBox(); scheduleSave();
}
function restoreRec(rec, snap) { for (const k of Object.keys(rec)) if (!(k in snap)) delete rec[k]; for (const k of Object.keys(snap)) rec[k] = clone(snap[k]); }
function endEdit() {
  const e = S.edit; if (!e) return; S.edit = null;
  const after = runChecks(), key = objKey(e.kind, e.rec.id), nb = newBlocks(e.before, after, key);
  if (nb.length) {
    restoreRec(e.rec, e.snap); S.issues = runChecks(); syncScene();
    toast('Заблоковано: ' + nb[0].msg + '. Значення повернуто.', 'err');
    renderRight(); renderChips(); renderLayerList(); return;
  }
  S.issues = after; updateVisual(); renderChecksBlock();
}
function syncPropsValues() {
  const rec = S.sel && recOfRef(S.sel); if (!rec) return;
  $$('#rightBody [data-f]').forEach((el) => {
    if (document.activeElement === el) return;
    const f = el.dataset.f, v = f.startsWith('p.') ? getp(rec.params, f.slice(2)) : rec[f];
    if (v != null) el.value = String(rnd(v, 4));
  });
  renderDerived();
}

/* ===== правий бік: властивості ===== */
function renderRight() {
  const root = $('#rightBody'); if (!root) return;
  root.replaceChildren();
  const rec = S.sel && recOfRef(S.sel);
  if (!rec) { S.sel = null; renderSiteProps(root); }
  else if (S.sel.kind === 'placement') renderPlacementProps(root, rec);
  else renderSlotProps(root, rec);
  root.append(h('div', { class: 'sec', id: 'checksBlock' }));
  renderChecksBlock();
}
function renderSiteProps(root) {
  const dis = !canManage(), b = S.site.building, cg = S.site.column_grid;
  const ed = (fn) => () => fn();
  const upd = () => { markDirty('sites'); S.issues = runChecks(); syncScene(true); setView(V.camMode || 'iso'); renderChips(); scheduleSave(); };
  root.append(h('div', { class: 'sec' }, h('h3', null, 'Площадка'),
    dis ? h('div', { class: 'note lock', style: { marginBottom: '8px' } }, S.app.mode === 'edit' ? 'Параметри площадки змінює Менеджер.' : lockHint(layerOf(S.ui.layer))) : null,
    h('div', { class: 'col' },
      fld('Назва', textInput({ value: S.site.name, dis, label: 'Назва', set: (v) => { S.site.name = v; const e = S.app.sites.find((s) => s.id === S.site.id); if (e) e.name = v; markDirty('sites'); markDirty('app'); renderTop(); renderStamp(); scheduleSave(); renderChips(); } })),
      h('div', { class: 'grid3' },
        fld('Довжина', numInput({ value: b.length, dis, min: 5, max: 1000, step: 1, label: 'Довжина', set: (v) => { b.length = v; upd(); } }), 'м'),
        fld('Ширина', numInput({ value: b.width, dis, min: 5, max: 1000, step: 1, label: 'Ширина', set: (v) => { b.width = v; upd(); } }), 'м'),
        fld('Висота', numInput({ value: b.height, dis, min: 2, max: 60, step: 0.5, label: 'Висота', set: (v) => { b.height = v; upd(); } }), 'м')),
      h('div', { class: 'grid2' },
        fld('Крок колон X', numInput({ value: cg.step_x, dis, min: 0, max: 100, step: 1, label: 'Крок колон X', set: (v) => { cg.step_x = v; upd(); } }), 'м'),
        fld('Крок колон Y', numInput({ value: cg.step_y, dis, min: 0, max: 100, step: 1, label: 'Крок колон Y', set: (v) => { cg.step_y = v; upd(); } }), 'м')),
      h('div', { class: 'small muted' }, `Активна версія: ${S.site.active_version ? 'v' + S.site.active_version : 'не опубліковано'}. Об’єктів: ${S.slots.length} місць, ${S.placements.length} одиниць обладнання.`),
      h('div', { class: 'note' }, 'Клацніть об’єкт на сцені або в списках, щоб побачити точні параметри. Перетягування працює з прив’язкою до сітки активного шару.'))));
}
function lockNote(ly) { return canEditLayer(ly) ? null : h('div', { class: 'note lock', style: { marginBottom: '8px' } }, ic('lock'), ' ', lockHint(ly)); }
function renderPlacementProps(root, pl) {
  const ly = layerOf(pl.layer_id), dis = !canEditLayer(ly), v = variantOf(pl.variant_id), kind = 'placement';
  const ed = { begin: () => beginEdit(kind, pl), end: endEdit };
  const dirty = ['placements'];
  const set = (fn) => (val) => { fn(val); liveEdit(dirty); };
  const opts = []; for (const p of S.catalog) for (const x of p.variants) opts.push([x.id, `${p.name} — ${x.name}`]);
  const rots = v && !(v.rotations || []).includes('any') ? (v.rotations || [0]).map(Number) : null;
  root.append(h('div', { class: 'sec' }, h('h3', null, 'Обладнання'), lockNote(ly),
    h('div', { class: 'col' },
      h('div', { class: 'grid2' },
        fld('Код', textInput({ value: pl.code, dis, label: 'Код', f: 'code', set: set((x) => { pl.code = x; }), ...ed })),
        fld('Назва', textInput({ value: pl.name, dis, label: 'Назва', set: set((x) => { pl.name = x; }), ...ed }))),
      fld('Варіант (тип обладнання)', selectEl(opts, pl.variant_id, (x) => { beginEdit(kind, pl); pl.variant_id = x; liveEdit(dirty); endEdit(); renderRight(); }, dis, 'Варіант')),
      h('div', { class: 'grid3' },
        fld('x', numInput({ value: pl.x, dis, step: snapStep(pl), f: 'x', label: 'x', set: set((x) => { pl.x = x; }), ...ed }), 'м'),
        fld('y', numInput({ value: pl.y, dis, step: snapStep(pl), f: 'y', label: 'y', set: set((x) => { pl.y = x; }), ...ed }), 'м'),
        fld('Поворот', rots ? selectEl(rots.map((r) => [r, r + '°']), normDeg(Math.round(pl.rotation || 0)), (x) => { beginEdit(kind, pl); pl.rotation = Number(x); liveEdit(dirty); endEdit(); }, dis, 'Поворот')
          : numInput({ value: pl.rotation || 0, dis, step: 15, f: 'rotation', label: 'Поворот', set: set((x) => { pl.rotation = normDeg(x); }), ...ed }), rots ? null : '°')),
      fld('Висота над шаром (z)', numInput({ value: pl.z || 0, dis, step: 0.1, f: 'z', label: 'z', set: set((x) => { if (x) pl.z = x; else delete pl.z; }), ...ed }), 'м'),
      h('label', { class: 'row', title: 'Люди й транспорт рухаються: не враховуються в перетинах, проходах, зонах обслуговування й пожежних проходах' },
        h('input', { type: 'checkbox', checked: !!pl.dynamic, disabled: dis, onchange: (e) => { beginEdit(kind, pl); if (e.target.checked) pl.dynamic = true; else delete pl.dynamic; liveEdit(dirty); endEdit(); } }), 'Динамічний об’єкт (рухомий)'),
      h('div', { id: 'derived' }),
      h('div', { class: 'row wrap' },
        h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => rotateSel(1) }, ic('rot'), 'Повернути 90°'),
        h('button', { class: 'btn sm', type: 'button', onclick: () => { const x = variantOf(pl.variant_id); if (x) openVariantCard(passportOf(x.id).id, x.id); } }, 'Картка варіанта'),
        h('span', { class: 'grow' }),
        h('button', { class: 'btn sm danger', type: 'button', disabled: dis, onclick: askDelete }, ic('trash'), 'Видалити')))));
  renderDerived();
}
function renderDerived() {
  const box = $('#derived'); if (!box || !S.sel) return;
  const rec = recOfRef(S.sel); if (!rec) return;
  if (S.sel.kind === 'placement') {
    const v = variantOf(rec.variant_id), p = passportOf(rec.variant_id); if (!v) return;
    const g = pGeom(rec, v), host = rec.slot_id ? S.sIdx.get(rec.slot_id) : null;
    const q = v.floor_load != null && v.floor_load !== '' ? Number(v.floor_load) : (v.weight_kg * 9.81 / 1000) / Math.max(g.L * g.W, 0.01);
    box.replaceChildren(h('dl', { class: 'kv' },
      h('dt', null, 'Тип'), h('dd', null, p.name), h('dt', null, 'Виробник'), h('dd', null, p.manufacturer || '—'),
      h('dt', null, 'Footprint'), h('dd', null, `${fmt(g.L, 2)} × ${fmt(g.W, 2)} м · ${normDeg(Math.round(rec.rotation || 0))}°`),
      h('dt', null, 'Охоплення AABB'), h('dd', null, `${fmt(g.box[2] - g.box[0], 2)} × ${fmt(g.box[3] - g.box[1], 2)} м`),
      h('dt', null, 'Центр'), h('dd', null, `${fmt(g.cx, 2)} ; ${fmt(g.cy, 2)}`),
      h('dt', null, 'Потужність'), h('dd', null, v.power_kw ? fmt(v.power_kw, 1) + ' кВт' : '—'),
      h('dt', null, 'Маса · на підлогу'), h('dd', null, `${fmtInt(v.weight_kg)} кг · ${fmt(q, 1)} кН/м²`),
      h('dt', null, 'Місце'), h('dd', null, host ? host.code_prefix : '—')));
  } else {
    const d = slotDims(rec), n = cellCount(rec), cap = cellsOf(rec).reduce((a, c) => a + (c.blocked ? 0 : c.capacity || 0), 0);
    box.replaceChildren(h('dl', { class: 'kv' },
      h('dt', null, 'Шаблон'), h('dd', null, TPL[rec.template].name),
      h('dt', null, 'Footprint'), h('dd', null, `${fmt(d.L, 2)} × ${fmt(d.W, 2)} м`),
      SOLID_SLOTS.includes(rec.template) ? [h('dt', null, 'Комірок'), h('dd', null, fmtInt(n)), h('dt', null, 'Місткість'), h('dd', null, fmtInt(cap))] : null));
  }
}
function renderSlotProps(root, s) {
  const ly = layerOf(s.layer_id), dis = !canEditLayer(ly), kind = 'slot', dirty = ['slots'];
  const ed = { begin: () => beginEdit(kind, s), end: endEdit };
  const set = (fn) => (val) => { fn(val); liveEdit(dirty); };
  const spec = TPL[s.template];
  root.append(h('div', { class: 'sec' }, h('h3', null, spec.name), lockNote(ly),
    h('div', { class: 'col' },
      h('div', { class: 'grid2' },
        fld('Код / префікс', textInput({ value: s.code_prefix, dis, label: 'Префікс', set: set((x) => { s.code_prefix = x; }), ...ed })),
        fld('Шар', h('input', { type: 'text', value: ly.name, disabled: true }))),
      h('div', { class: 'grid3' },
        fld('x', numInput({ value: s.x, dis, step: snapStep(s), f: 'x', label: 'x', set: set((x) => { s.x = x; }), ...ed }), 'м'),
        fld('y', numInput({ value: s.y, dis, step: snapStep(s), f: 'y', label: 'y', set: set((x) => { s.y = x; }), ...ed }), 'м'),
        fld('Поворот', numInput({ value: s.rotation || 0, dis, step: 15, f: 'rotation', label: 'Поворот', set: set((x) => { s.rotation = normDeg(x); }), ...ed }), '°')),
      paramFields(s.template, s.params, { dis, begin: ed.begin, end: ed.end, onChange: () => liveEdit(dirty) }),
      fld('Висота над шаром (z)', numInput({ value: s.z || 0, dis, step: 0.1, f: 'z', label: 'z', set: set((x) => { if (x) s.z = x; else delete s.z; }), ...ed }), 'м'),
      h('div', { id: 'derived' }),
      h('div', { class: 'row wrap' },
        h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => rotateSel(1) }, ic('rot'), 'Повернути 90°'),
        h('span', { class: 'grow' }),
        h('button', { class: 'btn sm danger', type: 'button', disabled: dis, onclick: askDelete }, ic('trash'), 'Видалити')))));
  if (SOLID_SLOTS.includes(s.template)) root.append(h('div', { class: 'sec', id: 'cellsBox' }));
  renderDerived(); renderCellsBox();
}
function renderCellsBox() {
  const box = $('#cellsBox'); if (!box || !S.sel || S.sel.kind !== 'slot') return;
  const s = S.sIdx.get(S.sel.id); if (!s) return;
  const ly = layerOf(s.layer_id), dis = !canEditLayer(ly), cells = cellsOf(s), lim = S.ui.cellsAll ? cells.length : 120;
  const nOv = Object.keys(s.overrides || {}).length;
  const rows = cells.slice(0, lim).map((c) => h('tr', { class: (S.selCell === c.code ? 'sel ' : '') + (c.ov ? 'ov ' : '') + (c.blocked ? 'blk' : ''), 'data-code': c.code, onclick: () => { S.selCell = S.selCell === c.code ? null : c.code; updateVisual(); renderCellsBox(); } },
    h('td', null, c.code), h('td', null, c.capacity == null ? '—' : c.capacity), h('td', null, c.max_load_kg == null ? '—' : fmtInt(c.max_load_kg))));
  box.replaceChildren(h('h3', { class: 'h3' }, `Комірки · ${fmtInt(cells.length)}`),
    h('div', { class: 'scroll' }, h('table', { class: 'cells' }, h('thead', null, h('tr', null, h('th', null, 'Код'), h('th', null, 'Місць'), h('th', null, 'Макс. кг'))), h('tbody', null, rows))),
    cells.length > lim ? h('button', { class: 'btn sm', type: 'button', style: { marginTop: '6px' }, onclick: () => { S.ui.cellsAll = true; renderCellsBox(); } }, `Показати всі (${cells.length})`) : null,
    h('div', { class: 'small muted', style: { marginTop: '4px' } }, 'Це майбутні stock.location із f3d_code, barcode і місткістю. * — ручна правка комірки.'));
  const sc = S.selCell && cells.find((c) => c.code === S.selCell);
  if (sc) {
    const ov = () => { s.overrides = s.overrides || {}; return (s.overrides[sc.code] = s.overrides[sc.code] || {}); };
    const upd = () => { liveEdit(['slots']); };
    box.append(h('div', { class: 'note', style: { marginTop: '8px' } }, h('div', { class: 'h3' }, 'Комірка ' + sc.code),
      h('div', { class: 'grid2' },
        fld('Місткість', numInput({ value: sc.capacity, dis, min: 0, int: 1, step: 1, label: 'Місткість', set: (v) => { ov().capacity = v; upd(); } })),
        fld('Макс. навантаження', numInput({ value: sc.max_load_kg, dis, min: 0, step: 50, label: 'Макс. навантаження', set: (v) => { ov().max_load_kg = v; upd(); } }), 'кг')),
      h('label', { class: 'row', style: { marginTop: '6px' } }, h('input', { type: 'checkbox', checked: !!sc.blocked, disabled: dis, onchange: (e) => { ov().blocked = e.target.checked; upd(); } }), 'Не використовувати (заблокована)'),
      h('button', { class: 'btn sm', type: 'button', style: { marginTop: '6px' }, disabled: dis || !sc.ov, onclick: () => { delete s.overrides[sc.code]; upd(); } }, 'Скинути ручні правки')));
  }
  if (nOv) box.append(h('div', { class: 'small muted', style: { marginTop: '6px' } }, `Ручних правок: ${nOv}`));
}

/* ===== перевірки (CD-13/14) ===== */
function issueRow(it, selKey) {
  const names = it.keys.map((k) => { const r = k.startsWith('p:') ? S.pIdx.get(k.slice(2)) : S.sIdx.get(k.slice(2)); return r ? (r.code || r.code_prefix || r.name) : '?'; });
  return h('div', { class: 'issue ' + it.level, role: 'button', tabindex: 0, onclick: () => gotoIssue(it, selKey), onkeydown: (e) => { if (e.key === 'Enter') gotoIssue(it, selKey); } },
    h('div', { class: 'im' }, it.msg, h('div', { class: 'io' }, (it.level === 'block' ? 'ЗАБОРОНА' : 'ПОПЕРЕДЖЕННЯ') + ' · ' + (CHECKS.find((c) => c.id === it.check) || {}).name)));
}
function gotoIssue(it, selKey) {
  const key = it.keys.find((k) => k !== selKey) || it.keys[0], ref = { kind: key.startsWith('p:') ? 'placement' : 'slot', id: key.slice(2) }, rec = recOfRef(ref);
  if (!rec) return; selectObj(ref); focusOn(rec.x, rec.y);
}
function renderChecksBlock() {
  const box = $('#checksBlock'); if (!box) return;
  const selKey = S.sel ? objKey(S.sel.kind, S.sel.id) : null, ly = layerOf(S.ui.layer);
  const all = S.issues.list, mine = selKey ? all.filter((i) => i.keys.includes(selKey)) : [];
  const layerList = all.filter((i) => i.layerId === S.ui.layer && !mine.includes(i));
  const nb = all.filter((i) => i.level === 'block').length, nw = all.length - nb;
  const frag = [h('h3', null, 'Перевірки', h('span', { class: 'row' }, nb ? h('span', { class: 'badge b' }, nb + ' заборон') : null, nw ? h('span', { class: 'badge w' }, nw + ' попер.') : null, !all.length ? h('span', { class: 'badge ok' }, 'усе гаразд') : null))];
  if (selKey) { frag.push(h('div', { class: 'lbl', style: { margin: '4px 0' } }, 'Вибраний об’єкт'), mine.length ? h('div', { class: 'issues' }, mine.map((i) => issueRow(i, selKey))) : h('div', { class: 'small muted' }, 'Зауважень немає.')); }
  frag.push(h('div', { class: 'lbl', style: { margin: '8px 0 4px' } }, `Шар «${ly ? ly.name : ''}»`), layerList.length ? h('div', { class: 'issues' }, layerList.slice(0, 40).map((i) => issueRow(i, selKey))) : h('div', { class: 'small muted' }, 'Зауважень немає.'));
  if (layerList.length > 40) frag.push(h('div', { class: 'small muted' }, `… ще ${layerList.length - 40}`));
  const dis = !canManage(), cfg = S.settings.checks;
  frag.push(h('details', { style: { marginTop: '10px' }, open: S.ui.cfgOpen, ontoggle: (e) => { S.ui.cfgOpen = e.target.open; } }, h('summary', { class: 'lbl', style: { cursor: 'pointer' } }, 'Налаштування перевірок'),
    dis ? h('div', { class: 'note lock', style: { margin: '6px 0' } }, 'Налаштування змінює Менеджер.') : null,
    CHECKS.map((c) => h('div', { class: 'row', style: { margin: '5px 0' }, title: c.hint },
      h('input', { type: 'checkbox', checked: cfg[c.id].enabled, disabled: dis, 'aria-label': c.name, onchange: (e) => { cfg[c.id].enabled = e.target.checked; liveCfg(); } }),
      h('span', { style: { flex: 1, minWidth: 0 } }, c.name),
      selectEl([['warn', 'Попередження'], ['block', 'Заборона']], cfg[c.id].mode, (v) => { cfg[c.id].mode = v; liveCfg(); }, dis, c.name))),
    h('div', { class: 'row', style: { marginTop: '6px' } }, h('span', { style: { flex: 1 } }, 'Макс. відстань до точки мережі, N'),
      numInput({ value: S.settings.reach_n, dis, min: 1, max: 200, step: 1, label: 'N', set: (v) => { S.settings.reach_n = v; liveCfg(); } }), 'м')));
  box.replaceChildren(...frag);
}
function liveCfg() { markDirty('settings'); S.issues = runChecks(); updateVisual(); renderChips(); renderChecksBlock(); scheduleSave(); }

/* ===== дії над виділеним ===== */
function rotateSel(dir) {
  if (!S.sel) return; const rec = recOfRef(S.sel); const ly = layerOf(rec.layer_id);
  if (!canEditLayer(ly)) { toastLock(ly); return; }
  const kind = S.sel.kind; beginEdit(kind, rec);
  let next = normDeg((rec.rotation || 0) + 90 * dir);
  if (kind === 'placement') {
    const v = variantOf(rec.variant_id), rs = (v.rotations || [0]);
    if (!rs.includes('any')) { const al = rs.map(Number).sort((a, b) => a - b); let c = rec.rotation || 0, ok = null; for (let i = 0; i < 4; i++) { c = normDeg(c + 90 * dir); if (al.includes(c)) { ok = c; break; } } if (ok == null) { toast('Для цього варіанта поворот не дозволено', 'warn'); S.edit = null; return; } next = ok; }
  }
  rec.rotation = next;
  liveEdit([kind === 'placement' ? 'placements' : 'slots']); endEdit(); renderRight();
  const ne = S.issues.byKey.get(objKey(kind, rec.id)); if (ne && ne.level === 'warn') toast(ne.items[0].msg, 'warn');
}
async function askDelete() {
  if (!S.sel) return; const rec = recOfRef(S.sel), ly = layerOf(rec.layer_id);
  if (!canEditLayer(ly)) { toastLock(ly); return; }
  const nm = rec.code || rec.code_prefix || rec.name;
  const extra = S.sel.kind === 'slot' && cellCount(rec) ? ` Буде видалено ${cellCount(rec)} комірок.` : '';
  const ok = await confirmBox({ title: 'Видалити об’єкт?', text: `«${nm}» буде видалено з чернетки.${extra}`, ok: 'Видалити', danger: true });
  if (!ok) return;
  if (S.sel.kind === 'placement') S.placements = S.placements.filter((p) => p.id !== rec.id);
  else { S.slots = S.slots.filter((s) => s.id !== rec.id); for (const p of S.placements) if (p.slot_id === rec.id) p.slot_id = null; }
  const k = S.sel.kind === 'placement' ? 'placements' : 'slots';
  S.sel = null; S.selCell = null; commit({ dirty: [k, 'placements'] });
}
/* додавання */
function addPlacementAt(variantId, x, y, snap) {
  const ly = layerOf(S.ui.layer), v = variantOf(variantId); if (!ly || !v) return;
  if (!canEditLayer(ly)) { toastLock(ly); return; }
  const st = ly.grid_step || 0.5;
  const cat = (passportOf(variantId) || {}).category, pre = { machine: 'M', rack: 'RK', forklift: 'FL', conveyor: 'CV', cabinet: 'SW', robot: 'RB' }[cat] || 'EQ';
  let n = 1; while (S.placements.some((p) => p.code === pre + '-' + pad2(n))) n++;
  const pl = { id: uid('pl_'), layer_id: ly.id, variant_id: variantId, slot_id: null, x: snap ? snapV(x, st) : x, y: snap ? snapV(y, st) : y, rotation: 0, code: pre + '-' + pad2(n), name: v.name };
  const before = S.issues; S.placements.push(pl); S.pIdx.set(pl.id, pl); assignSlot(pl);
  const after = runChecks(), nb = newBlocks(before, after, 'p:' + pl.id);
  if (nb.length) { S.placements.pop(); S.pIdx.delete(pl.id); toast('Заблоковано: ' + nb[0].msg, 'err'); return; }
  S.sel = { kind: 'placement', id: pl.id }; commit({ dirty: ['placements'] });
  const st2 = S.issues.byKey.get('p:' + pl.id); if (st2) toast(st2.items[0].msg, 'warn');
}
function addSlotAt(spec, x, y) {
  const ly = layerOf(S.ui.layer); if (!ly) return;
  const s = { id: uid('sl_'), layer_id: ly.id, template: spec.template, code_prefix: spec.prefix, x, y, rotation: 0, params: clone(spec.params), overrides: {} };
  const before = S.issues; S.slots.push(s); S.sIdx.set(s.id, s);
  const after = runChecks(), nb = newBlocks(before, after, 's:' + s.id);
  if (nb.length) { S.slots.pop(); S.sIdx.delete(s.id); toast('Заблоковано: ' + nb[0].msg, 'err'); return; }
  S.sel = { kind: 'slot', id: s.id }; commit({ dirty: ['slots'] });
  const n = cellCount(s); toast(n ? `Створено місце «${s.code_prefix}»: ${fmtInt(n)} комірок.` : `Створено місце «${s.code_prefix}».`);
}
