/* ===== діалоги: підтвердження, нова площадка, паспорт, картка варіанта, публікація, історія ===== */
function openDialog(o) {
  const dlg = h('dialog', { class: o.cls || '' });
  const close = (r) => { dlg.returnValue = r || ''; dlg.close(); };
  dlg.append(h('div', { class: 'dh' }, h('h2', null, o.title), h('button', { class: 'xbtn', type: 'button', 'aria-label': 'Закрити', onclick: () => close('') }, ic('x'))),
    h('div', { class: 'db' }, o.body),
    o.actions && o.actions.length ? h('div', { class: 'df' }, o.actions.map((a) => h('button', { class: 'btn ' + (a.cls || ''), type: 'button', disabled: a.disabled, id: a.id, onclick: async () => { const r = a.onClick ? await a.onClick(dlg) : undefined; if (r !== false) close(a.value || 'ok'); } }, a.label))) : null);
  dlg.addEventListener('close', () => { if (o.onClose) o.onClose(dlg.returnValue); dlg.remove(); });
  dlg.addEventListener('click', (e) => { if (e.target === dlg && o.light) close(''); });
  document.body.append(dlg); dlg.showModal();
  dlg.close2 = close;
  return dlg;
}
function confirmBox(o) {
  return new Promise((res) => {
    let done = false;
    openDialog({ title: o.title, cls: 'narrow', body: h('p', { style: { margin: 0 } }, o.text),
      actions: [{ label: o.cancel || 'Скасувати', value: 'no' }, { label: o.ok || 'Так', cls: o.danger ? 'danger' : 'primary', value: 'yes', onClick: () => { done = true; } }],
      onClose: () => res(done) });
  });
}

/* ===== нова площадка (CD-22, CD-24) ===== */
function openNewSite() {
  const hasSample = S.app.sites.some((s) => s.id === 'sample');
  let kind = 'empty'; const name = h('input', { type: 'text', value: 'Нова площадка', 'aria-label': 'Назва' });
  const radio = (v, t, sub, dis) => h('label', { class: 'row', style: { alignItems: 'flex-start', margin: '6px 0' } }, h('input', { type: 'radio', name: 'sk', value: v, checked: v === kind, disabled: dis, onchange: () => { kind = v; name.value = v === 'sample' ? 'Меблеве підприємство (приклад)' : 'Нова площадка'; } }), h('span', null, h('b', null, t), h('div', { class: 'small muted' }, sub)));
  openDialog({ title: 'Нова площадка', cls: 'narrow',
    body: h('div', { class: 'col' }, fld('Назва', name),
      radio('empty', 'Порожня площадка', 'Будівля 60×30×8 м, п’ять базових шарів, каталог із типовими варіантами.'),
      radio('sample', 'Меблеве підприємство (приклад)', hasSample ? 'Приклад уже є в списку площадок.' : 'Наш завод: будівля 150×72×9 м, стелажі, верстати, проходи, виходи.', hasSample)),
    actions: [{ label: 'Скасувати' }, { label: 'Створити', cls: 'primary', onClick: async () => { await createSite(kind, name.value.trim() || 'Нова площадка'); } }] });
}

/* ===== паспорт (тип обладнання) ===== */
function openPassportDialog(pid) {
  const isNew = !pid, pp = isNew ? { id: uid('pp_'), category: 'machine', role: '', name: 'Новий тип', manufacturer: '', model: '', variants: [] } : S.catalog.find((p) => p.id === pid);
  const d = clone(pp), dis = !canCatalog();
  const used = pp.variants.some((v) => S.placements.some((pl) => pl.variant_id === v.id));
  openDialog({ title: isNew ? 'Новий тип обладнання' : 'Тип обладнання (паспорт)', cls: 'narrow',
    body: h('div', { class: 'col' },
      fld('Назва типу', textInput({ value: d.name, dis, label: 'Назва', set: (v) => { d.name = v; } })),
      fld('Категорія (від неї залежить умовна модель)', selectEl(Object.entries(CATEGORIES), d.category, (v) => { d.category = v; }, dis, 'Категорія')),
      h('div', { class: 'grid2' }, fld('Виробник', textInput({ value: d.manufacturer, dis, label: 'Виробник', set: (v) => { d.manufacturer = v; } })), fld('Модель', textInput({ value: d.model, dis, label: 'Модель', set: (v) => { d.model = v; } }))),
      fld('Роль (код)', textInput({ value: d.role, dis, label: 'Роль', set: (v) => { d.role = v; } })),
      !isNew && used ? h('div', { class: 'note' }, 'Тип використовується на сцені: видалення вимкнено.') : null),
    actions: [
      !isNew ? { label: 'Видалити тип', cls: 'danger', disabled: dis || used, onClick: async () => { const ok = await confirmBox({ title: 'Видалити тип?', text: `«${pp.name}» і його варіанти (${pp.variants.length}) буде видалено з каталогу.`, ok: 'Видалити', danger: true }); if (!ok) return false; S.catalog = S.catalog.filter((p) => p.id !== pp.id); commit({ dirty: ['catalog'] }); } } : null,
      { label: 'Скасувати' },
      { label: 'Зберегти', cls: 'primary', disabled: dis, onClick: () => { Object.assign(pp, { name: d.name, category: d.category, manufacturer: d.manufacturer, model: d.model, role: d.role }); if (isNew) S.catalog.push(pp); commit({ dirty: ['catalog'] }); } }].filter(Boolean) });
}

/* ===== картка варіанта (CD-11, CD-12, CD-15…19) ===== */
function openVariantCard(pid, vid, newVariant) {
  const pp = S.catalog.find((p) => p.id === pid); if (!pp) return;
  const orig = newVariant || variantOf(vid), isNew = !!newVariant, dis = !canCatalog();
  const vd = clone(orig); vd.service = vd.service || { front: 0, back: 0, left: 0, right: 0 }; vd.utilities = vd.utilities || [];
  const M = { meta: vd.model ? clone(vd.model) : null, parsed: null, files: null, units: 'mm', zup: false, norm: null, removed: false, msg: null };
  if (vd.model) { M.units = vd.model.units || 'mm'; M.zup = vd.model.up === 'Z'; M.norm = V.models.get(vd.id) || null; }
  const set = (fn) => (v) => { fn(v); refreshPreview(); };
  const pvBox = h('div', { class: 'pv' }, h('div', { class: 'ph' }, 'Перегляд: обертання мишею / пальцем'));
  let preview = null;
  const refreshPreview = () => { if (preview) preview.show(pp.category, vd, M.norm); };
  const infoBox = h('div'), msgBox = h('div');
  const dimsEl = (k, l) => fld(l, numInput({ value: vd[k], dis, min: 10, max: 60000, step: 10, int: 1, label: l, f: k, set: set((v) => { vd[k] = v; }) }), 'мм');
  const rotChecks = h('div');
  const renderRot = () => {
    const any = vd.rotations.includes('any'), cur = vd.rotations.map(Number);
    rotChecks.replaceChildren(h('div', { class: 'checks' },
      [0, 90, 180, 270].map((a) => h('label', null, h('input', { type: 'checkbox', checked: any || cur.includes(a), disabled: dis || any, onchange: (e) => { const s = new Set(cur); if (e.target.checked) s.add(a); else s.delete(a); vd.rotations = [...s].sort((x, y) => x - y); if (!vd.rotations.length) vd.rotations = [0]; renderRot(); } }), a + '°')),
      h('label', null, h('input', { type: 'checkbox', checked: any, disabled: dis, onchange: (e) => { vd.rotations = e.target.checked ? ['any'] : [0, 90, 180, 270]; renderRot(); } }), 'будь-який')));
  };
  renderRot();
  const utilBox = h('div');
  const renderUtil = () => {
    utilBox.replaceChildren(...vd.utilities.map((u, i) => h('div', { class: 'mini u', style: { gridTemplateColumns: 'minmax(0,1fr) 62px 62px 62px 24px' } },
      selectEl(Object.entries(UTIL_KINDS), u.kind, (v) => { u.kind = v; }, dis, 'Вид'),
      ...['x', 'y', 'z'].map((k) => numInput({ value: u[k], dis, step: 50, label: k, set: (v) => { u[k] = v; } })),
      h('button', { class: 'xbtn', type: 'button', disabled: dis, 'aria-label': 'Видалити', onclick: () => { vd.utilities.splice(i, 1); renderUtil(); } }, ic('x')))),
      h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => { vd.utilities.push({ kind: 'electric', x: 0, y: 0, z: 1500 }); renderUtil(); } }, ic('plus'), 'Точка підключення'));
  };
  renderUtil();
  const q = vd.floor_load != null && vd.floor_load !== '' ? vd.floor_load : '';
  const left = h('div', { class: 'col' },
    h('div', { class: 'small muted' }, `Тип: ${pp.name} · ${CATEGORIES[pp.category]}${pp.manufacturer && pp.manufacturer !== '—' ? ' · ' + pp.manufacturer : ''}`),
    dis ? h('div', { class: 'note lock' }, S.app.mode === 'edit' ? 'Каталог редагують Менеджер і Технолог.' : 'Режим перегляду.') : null,
    fld('Назва варіанта', textInput({ value: vd.name, dis, label: 'Назва', set: (v) => { vd.name = v; } })),
    h('div', { class: 'grid3' }, dimsEl('length', 'Довжина'), dimsEl('width', 'Ширина'), dimsEl('height', 'Висота')),
    h('div', { class: 'lbl' }, 'Зона обслуговування, мм'),
    h('div', { class: 'grid4' }, [['front', 'спереду'], ['back', 'ззаду'], ['left', 'зліва'], ['right', 'справа']].map(([k, l]) => fld(l, numInput({ value: vd.service[k], dis, min: 0, step: 50, int: 1, label: l, set: (v) => { vd.service[k] = v; } })))),
    fld('Дозволені повороти', rotChecks),
    fld('Де можна ставити: шари', checkGroup(Object.entries(LAYER_KINDS), vd.allowed_layer_kinds, (v) => { vd.allowed_layer_kinds = v; }, dis)),
    fld('Де можна ставити: типи місць', checkGroup(Object.entries(TPL).map(([k, t]) => [k, t.name]), vd.allowed_slot_types, (v) => { vd.allowed_slot_types = v; }, dis)),
    h('div', { class: 'lbl' }, 'Точки підключення (від центру, мм)'), utilBox,
    h('div', { class: 'grid3' },
      fld('Потужність', numInput({ value: vd.power_kw, dis, min: 0, step: 0.5, label: 'Потужність', set: (v) => { vd.power_kw = v; } }), 'кВт'),
      fld('Щит', textInput({ value: vd.panel, dis, label: 'Щит', set: (v) => { vd.panel = v; } })),
      fld('Маса', numInput({ value: vd.weight_kg, dis, min: 0, step: 50, int: 1, label: 'Маса', set: (v) => { vd.weight_kg = v; } }), 'кг')),
    h('div', { class: 'grid3' },
      fld('Навантаження на підлогу', numInput({ value: q, dis, min: 0, step: 0.5, label: 'Навантаження', set: (v) => { vd.floor_load = v > 0 ? v : null; } }), 'кН/м², 0 = з маси'),
      fld('Точка прив’язки', selectEl([['center', 'Центр'], ['corner', 'Кут (лівий-нижній)']], vd.anchor, (v) => { vd.anchor = v; }, dis, 'Прив’язка')),
      fld('Передня сторона', selectEl(Object.entries(FRONT_SIDES), vd.front_side, (v) => { vd.front_side = v; refreshPreview(); }, dis, 'Передня сторона'))));

  /* --- блок моделі --- */
  const fileIn = h('input', { type: 'file', multiple: true, accept: '.glb,.gltf,.obj,.mtl,.fbx,.stl,.3mf,.dae,.step,.stp,.iges,.igs,.ifc', hidden: true, id: 'modelFile', 'aria-label': 'Файл моделі' });
  const dropEl = h('div', { class: 'drop', tabindex: 0, role: 'button', onclick: () => !dis && fileIn.click(), onkeydown: (e) => { if ((e.key === 'Enter' || e.key === ' ') && !dis) fileIn.click(); } }, 'Оберіть або перетягніть файл моделі', h('div', { class: 'small' }, 'GLB/glTF, OBJ(+MTL), FBX, STL, 3MF, DAE · до 20 МБ'));
  ['dragover', 'dragenter'].forEach((t) => dropEl.addEventListener(t, (e) => { e.preventDefault(); dropEl.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((t) => dropEl.addEventListener(t, () => dropEl.classList.remove('over')));
  dropEl.addEventListener('drop', (e) => { e.preventDefault(); if (!dis) onFiles(e.dataTransfer.files); });
  fileIn.addEventListener('change', () => onFiles(fileIn.files));
  const say = (kind, text) => { M.msg = text ? { kind, text } : null; msgBox.replaceChildren(...(M.msg ? [h('div', { class: 'note ' + (kind === 'err' ? 'err' : kind === 'warn' ? 'lock' : ''), style: { marginTop: '6px' }, role: 'status' }, text)] : [])); };
  const renormalize = () => { if (M.parsed) { M.norm = normalizeModel(M.parsed.obj, M.units, M.zup); } };
  const renderInfo = () => {
    const mt = M.removed ? null : (M.parsed ? M.parsed.meta : M.meta);
    if (!mt) { infoBox.replaceChildren(h('div', { class: 'small muted', style: { marginTop: '6px' } }, 'Моделі немає: у 3D показується умовна модель за категорією «' + CATEGORIES[pp.category] + '».')); return; }
    const sz = M.norm ? M.norm.size : null;
    infoBox.replaceChildren(h('dl', { class: 'kv', style: { marginTop: '8px' } },
      h('dt', null, 'Файл'), h('dd', null, mt.name), h('dt', null, 'Формат'), h('dd', null, mt.format.toUpperCase()),
      h('dt', null, 'Розмір файлу'), h('dd', null, fmtSize(mt.size)), h('dt', null, 'Трикутників'), h('dd', null, fmtInt(mt.tris)),
      h('dt', null, 'Габарити моделі'), h('dd', null, sz ? `${fmtInt(sz.x * 1000)} × ${fmtInt(sz.z * 1000)} × ${fmtInt(sz.y * 1000)} мм` : '—')),
      h('div', { class: 'row wrap', style: { marginTop: '8px' } },
        h('span', { class: 'lbl' }, 'Одиниці'),
        h('span', { class: 'seg' }, ['mm', 'm'].map((u) => h('button', { type: 'button', 'aria-pressed': String(M.units === u), disabled: dis, onclick: () => { M.units = u; renormalize(); renderInfo(); refreshPreview(); } }, u === 'mm' ? 'мм' : 'м'))),
        h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: M.zup, disabled: dis, onchange: (e) => { M.zup = e.target.checked; renormalize(); renderInfo(); refreshPreview(); } }), 'вісь Z вгору')),
      h('div', { class: 'row wrap', style: { marginTop: '8px' } },
        h('button', { class: 'btn sm', type: 'button', disabled: dis || !sz, onclick: () => { vd.length = Math.max(10, Math.round(sz.x * 1000)); vd.width = Math.max(10, Math.round(sz.z * 1000)); vd.height = Math.max(10, Math.round(sz.y * 1000)); $$('[data-f=length],[data-f=width],[data-f=height]', dlg).forEach((el) => { el.value = vd[el.dataset.f]; }); refreshPreview(); toast('Габарити підставлено з моделі.'); } }, 'Підставити габарити з моделі'),
        h('button', { class: 'btn sm danger', type: 'button', disabled: dis, onclick: () => { M.removed = true; M.parsed = null; M.files = null; M.norm = null; say(null); renderInfo(); refreshPreview(); } }, 'Прибрати модель')));
  };
  async function onFiles(list) {
    const arr = [...list]; if (!arr.length) return;
    say(null);
    const main = arr.find((f) => /\.(glb|gltf|obj|fbx|stl|3mf|dae|step|stp|iges|igs|ifc)$/i.test(f.name));
    if (!main) { say('err', 'Невідомий формат. Підтримуються: GLB/glTF, OBJ(+MTL), FBX, STL, 3MF, DAE.'); return; }
    const ext = main.name.split('.').pop().toLowerCase();
    if (['step', 'stp', 'iges', 'igs', 'ifc'].includes(ext)) { say('warn', `Формат .${ext.toUpperCase()}: перетворення на сервері (Odoo). У прототипі браузер його не читає — збережемо оригінал і зробимо облегчений GLB на сервері.`); return; }
    const total = arr.reduce((a, f) => a + f.size, 0);
    if (total > 20 * 1048576) { say('err', `Файл завеликий: ${fmt(total / 1048576, 1)} МБ. Ліміт — 20 МБ. Зменште модель або передайте оригінал на сервер для перетворення.`); return; }
    say('', 'Читаю модель…');
    try {
      const parsed = await parseModel(arr, ext);
      const tris = countTris(parsed.obj);
      const raw = new THREE.Box3().setFromObject(parsed.obj).getSize(new THREE.Vector3());
      M.parsed = { obj: parsed.obj, meta: { name: main.name, format: ext, size: total, tris, units: 'mm', up: 'Y', bbox: [0, 0, 0] } };
      M.files = parsed.files; M.removed = false;
      M.units = Math.max(raw.x, raw.y, raw.z) > 50 ? 'mm' : 'm';
      M.zup = ['stl', '3mf'].includes(ext);
      renormalize(); renderInfo(); refreshPreview();
      if (tris > 50000) say('warn', `Трикутників: ${fmtInt(tris)} (> 50 000). Рекомендуємо спростити модель — на сервері (Odoo) буде облегчений GLB. У прототипі модель усе одно показана.`);
      else say('ok', `Модель прочитано: ${fmtInt(tris)} трикутників.`);
    } catch (e) { console.warn(e); M.parsed = null; say('err', 'Не вдалося прочитати модель: ' + (e && e.message ? e.message : e)); }
  }
  const right = h('div', { class: 'col' },
    h('div', { class: 'lbl' }, '3D-модель'), pvBox, dropEl, fileIn, msgBox, infoBox,
    h('div', { class: 'small muted' }, 'STEP / IGES / IFC — перетворення на сервері (Odoo): зберігаємо оригінал і облегчений GLB, габарити й превʼю з моделі. Ліміт: 20 МБ і 50 тис. трикутників.'));
  renderInfo();
  const dlg = openDialog({ title: isNew ? 'Новий варіант' : 'Варіант: ' + orig.name, cls: 'wide', body: h('div', { class: 'vcard' }, left, right),
    onClose: () => { if (preview) preview.dispose(); },
    actions: [
      !isNew ? { label: 'Видалити варіант', cls: 'danger', disabled: dis, onClick: async () => {
        if (S.placements.some((p) => p.variant_id === orig.id)) { toast('Варіант використовується на сцені — спершу приберіть об’єкти.', 'warn'); return false; }
        const ok = await confirmBox({ title: 'Видалити варіант?', text: `«${orig.name}» буде видалено з каталогу.`, ok: 'Видалити', danger: true }); if (!ok) return false;
        pp.variants = pp.variants.filter((x) => x.id !== orig.id); files.del('model:' + orig.id); V.models.delete(orig.id); commit({ dirty: ['catalog'] }); } } : null,
      { label: 'Скасувати' },
      { label: 'Зберегти', cls: 'primary', disabled: dis, onClick: async () => {
        if (!vd.name.trim()) { toast('Вкажіть назву варіанта.', 'warn'); return false; }
        if (M.removed) { vd.model = null; await files.del('model:' + vd.id); V.models.delete(vd.id); }
        else if (M.parsed) {
          const sz = M.norm.size;
          vd.model = { name: M.parsed.meta.name, format: M.parsed.meta.format, size: M.parsed.meta.size, tris: M.parsed.meta.tris, units: M.units, up: M.zup ? 'Z' : 'Y', bbox: [Math.round(sz.x * 1000), Math.round(sz.z * 1000), Math.round(sz.y * 1000)] };
          await files.put('model:' + vd.id, { ext: M.parsed.meta.format, files: M.files });
          V.models.set(vd.id, M.norm);
        } else if (vd.model && M.meta) { vd.model.units = M.units; vd.model.up = M.zup ? 'Z' : 'Y'; if (M.norm) { const sz = M.norm.size; vd.model.bbox = [Math.round(sz.x * 1000), Math.round(sz.z * 1000), Math.round(sz.y * 1000)]; } }
        vd.rotations = vd.rotations.length ? vd.rotations : [0];
        if (isNew) pp.variants.push(vd); else Object.assign(orig, vd);
        if (!isNew && V.models.has(vd.id) && vd.model) { const m = V.models.get(vd.id); if (M.norm === m) { /* без змін */ } }
        commit({ dirty: ['catalog'] }); } }].filter(Boolean) });
  preview = createPreview(pvBox);
  refreshPreview();
}

/* ===== публікація (CD-20, CD-21) ===== */
function cellMap(slots) {
  const m = new Map();
  for (const s of slots) if (SOLID_SLOTS.includes(s.template)) for (const c of genCells(s)) { const w = cellWorld(s, c); m.set(c.code, [c.capacity, c.max_load_kg, c.blocked ? 1 : 0, rnd(w.x, 2), rnd(w.y, 2), rnd(s.rotation || 0, 0)].join('|')); }
  return m;
}
function computeDiff() {
  const b = S.site.active_version === 0 || !S.base ? { slots: [], placements: [], catalog: [], layers: [] } : S.base;
  const bc = cellMap(b.slots), cc = cellMap(S.slots), created = [], changed = [], removed = [];
  for (const [k, v] of cc) { if (!bc.has(k)) created.push(k); else if (bc.get(k) !== v) changed.push(k); }
  for (const k of bc.keys()) if (!cc.has(k)) removed.push(k);
  const bp = new Map(b.placements.map((p) => [p.id, JSON.stringify(p)])), pc = [], pch = [], prm = [];
  for (const p of S.placements) { if (!bp.has(p.id)) pc.push(p); else if (bp.get(p.id) !== JSON.stringify(p)) pch.push(p); }
  const cur = new Set(S.placements.map((p) => p.id)); for (const p of b.placements) if (!cur.has(p.id)) prm.push(p);
  const bv = new Map(); for (const p of b.catalog) for (const v of p.variants) bv.set(v.id, JSON.stringify(v));
  let vch = 0; for (const p of S.catalog) for (const v of p.variants) if (bv.has(v.id) && bv.get(v.id) !== JSON.stringify(v)) vch++;
  return { cellsNew: created, cellsChanged: changed, cellsRemoved: removed, plNew: pc, plChanged: pch, plRemoved: prm, variantsChanged: vch };
}
function openPublish() {
  const d = computeDiff(), first = S.site.active_version === 0;
  const ex = (arr, f) => arr.length ? arr.slice(0, 3).map(f).join(', ') + (arr.length > 3 ? ' … ' + f(arr[arr.length - 1]) : '') : '—';
  const K = d.cellsChanged.length + d.plChanged.length + d.variantsChanged, L = d.cellsRemoved.length + d.plRemoved.length;
  const total = d.cellsNew.length + d.plNew.length + K + L;
  const note = h('textarea', { placeholder: 'Що змінено в цій версії (необов’язково)', 'aria-label': 'Нотатка' });
  const row = (n, t, x) => h('div', { class: 'sumrow' }, h('div', { class: 'n' }, fmtInt(n)), h('div', null, h('div', null, t), h('div', { class: 'x' }, x)));
  openDialog({ title: 'Публікація версії ' + ((S.versions.reduce((a, v) => Math.max(a, v.n), 0)) + 1), cls: 'narrow',
    body: h('div', { class: 'col' },
      h('div', { class: 'note' }, 'Це імітація: записи в Odoo не створюються. Підтвердження зберігає нову версію макета в історії.'),
      h('div', { class: 'lbl' }, 'Буде створено в Odoo' + (first ? ' (перша публікація площадки)' : '')),
      row(d.cellsNew.length, 'місць зберігання (stock.location з f3d_code, barcode, місткістю)', ex(d.cellsNew, (x) => x)),
      row(d.plNew.length, 'одиниць обладнання / робочих центрів (maintenance.equipment, mrp.workcenter)', ex(d.plNew, (p) => p.code || p.name)),
      row(K, 'змінено', `комірок ${d.cellsChanged.length} · обладнання ${d.plChanged.length} · варіантів ${d.variantsChanged}`),
      row(L, 'видалено', `комірок ${d.cellsRemoved.length} · обладнання ${d.plRemoved.length}`),
      total === 0 && !first ? h('div', { class: 'note lock' }, 'З моменту останньої версії змін немає.') : null,
      fld('Нотатка до версії', note)),
    actions: [{ label: 'Скасувати' }, { label: 'Підтвердити й опублікувати', cls: 'primary', disabled: total === 0 && !first, onClick: async () => { await doPublish(note.value.trim(), d); } }] });
}
async function doPublish(note, d) {
  const n = S.versions.reduce((a, v) => Math.max(a, v.n), 0) + 1, snap = makeSnapshot(S);
  const meta = { n, at: new Date().toISOString(), by: store.userName, note, size: JSON.stringify(snap).length, counts: { created: d.cellsNew.length, equipment: d.plNew.length, changed: d.cellsChanged.length + d.plChanged.length + d.variantsChanged, removed: d.cellsRemoved.length + d.plRemoved.length } };
  S.versions.push(meta); S.site.active_version = n; S.base = snap; S.snaps[n] = snap; buildBaseMap();
  markDirty('versions'); markDirty('sites');
  computeChanged(); renderTop(); renderRight();
  await flushNow();
  toast(`Версію ${n} опубліковано (імітація: записи Odoo не створено).`);
}

/* ===== історія версій ===== */
function openHistory() {
  const body = h('div');
  const dlg = openDialog({ title: 'Історія версій', cls: 'narrow', body, actions: [{ label: 'Закрити' }] });
  const render = () => {
    const vs = [...S.versions].sort((a, b) => b.n - a.n);
    body.replaceChildren(
      h('div', { class: 'small muted', style: { marginBottom: '6px' } }, 'Повернення змінює чернетку; активна версія залишається, доки ви не опублікуєте нову.'),
      vs.length ? vs.map((v) => h('div', { class: 'ver' }, h('div', { class: 'vn' }, 'v' + v.n),
        h('div', { class: 'vi' }, h('div', null, fmtDate(v.at) + ' · ' + v.by, v.n === S.site.active_version ? h('span', { class: 'badge ok', style: { marginLeft: '8px' } }, 'активна') : null),
          h('div', { class: 'small' }, v.note || 'без нотатки'),
          v.counts ? h('div', { class: 'small muted mono' }, `+${v.counts.created} місць · +${v.counts.equipment} обл. · ~${v.counts.changed} · −${v.counts.removed}`) : null),
        h('button', { class: 'btn sm', type: 'button', disabled: !canManage(), title: canManage() ? '' : 'Повертає Менеджер у режимі редагування', onclick: async () => {
          const ok = await confirmBox({ title: `Повернути чернетку до v${v.n}?`, text: 'Поточна чернетка буде замінена знімком версії. Незбережені зміни пропадуть.', ok: 'Повернути', danger: true }); if (!ok) return;
          await revertTo(v.n); dlg.close2(''); } }, 'Повернути чернетку'))) : h('div', { class: 'empty' }, 'Версій ще немає. Натисніть «Опублікувати».'));
  };
  render();
}
