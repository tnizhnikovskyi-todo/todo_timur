const { launch, open, DIR } = require('./harness');
const fs = require('fs');
const SH = DIR + '/shots/';
const res = [];
const ok = (name, cond, extra) => { res.push([cond ? 'PASS' : 'FAIL', name, extra || '']); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? ' :: ' + extra : '')); };
const proj = (page, x, y, z = 0) => page.evaluate(([x, y, z]) => { const V = __f3d.V, v = new THREE.Vector3(x, z, -y).project(V.camera), r = V.canvas.getBoundingClientRect(); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height }; }, [x, y, z]);
async function drag(page, a, b, steps = 10) { await page.mouse.move(a.x, a.y); await page.mouse.down(); for (let i = 1; i <= steps; i++) await page.mouse.move(a.x + (b.x - a.x) * i / steps, a.y + (b.y - a.y) * i / steps); await page.mouse.up(); await page.waitForTimeout(250); }
const ev = (page, fn, arg) => page.evaluate(fn, arg);
const toasts = (page) => page.evaluate(() => [...document.querySelectorAll('.toast')].map((t) => t.textContent));
const pl = (page, code) => page.evaluate((c) => { const p = __f3d.S.placements.find((x) => x.code === c); return p && { x: p.x, y: p.y, rotation: p.rotation, slot: p.slot_id }; }, code);

async function t1_load() {
  for (const [cs, vp, tag] of [['light', { width: 1440, height: 900 }, 'light-1440'], ['dark', { width: 1440, height: 900 }, 'dark-1440'], ['light', { width: 400, height: 860 }, 'light-400'], ['dark', { width: 400, height: 860 }, 'dark-400']]) {
    const { browser, page, errors } = await launch({ colorScheme: cs, viewport: vp });
    await open(page, 1500);
    const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth, bg: getComputedStyle(document.body).backgroundColor, th: document.documentElement.dataset.theme || 'auto' }));
    ok(`AC1 ${tag}: консоль без ошибок`, errors.length === 0, errors.slice(0, 3).join(' | '));
    ok(`AC1 ${tag}: нет горизонтальной прокрутки`, m.sw <= m.iw, `sw=${m.sw} iw=${m.iw}`);
    if (tag === 'dark-1440') { await page.screenshot({ path: SH + 'dark.png' }); ok('dark: фон тёмный', m.bg !== 'rgb(228, 226, 217)', m.bg); }
    if (tag === 'light-400') await page.screenshot({ path: SH + 'mobile.png' });
    if (tag === 'light-1440') {
      await page.screenshot({ path: SH + 'overview.png' });
      const d = await page.evaluate(() => { const S = __f3d.S; const fg = __f3d.cellsOf(S.slots.find((s) => s.code_prefix === 'FG-R1')); return { layers: S.layers.length, fgCells: fg.length, code: fg[3].code, machines: S.placements.length, issues: S.issues.list.length, b: S.site.building }; });
      ok('AC2 здание/слои/стеллажи/станки', d.layers >= 5 && d.fgCells === 72 && d.code === 'FG-R1-B01-L4' && d.machines >= 30, JSON.stringify(d));
      const persisted = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('f3d1:')).length);
      ok('Первый запуск: в хранилище ничего не записано', persisted === 0, 'keys=' + persisted);
    }
    await browser.close();
  }
}

async function t3_rack() {
  const { browser, page, errors } = await launch();
  await open(page);
  // слой «Склади»
  await page.click('.layer[data-layer="fg"]');
  await page.click('#ltabs button[data-tab="slots"]');
  await page.waitForTimeout(200);
  // параметры шаблона: 18 x 4
  const form = '#leftBody';
  await page.fill(`${form} input[data-f="p.bays"]`, '18');
  await page.fill(`${form} input[data-f="p.levels"]`, '4');
  await page.fill(`${form} input[type=text][aria-label="Префікс"]`, 'TST1');
  await page.click('#leftBody button:has-text("Поставити на сцену")');
  const target = await proj(page, 60, 60, 0);
  await page.mouse.move(target.x, target.y); await page.mouse.move(target.x + 3, target.y + 3);
  await page.waitForTimeout(150);
  await page.mouse.click(target.x + 3, target.y + 3);
  await page.waitForTimeout(500);
  let s = await page.evaluate(() => { const sl = __f3d.S.slots.find((x) => x.code_prefix === 'TST1'); return sl && { n: __f3d.cellsOf(sl).length, first: __f3d.cellsOf(sl)[0].code, last: __f3d.cellsOf(sl).slice(-1)[0].code, x: sl.x, y: sl.y }; });
  ok('AC3 шаблон pallet_rack 18×4 → 72 ячейки', s && s.n === 72, JSON.stringify(s));
  ok('AC3 коды ячеек', s && s.first === 'TST1-B01-L1' && s.last === 'TST1-B18-L4');
  // правка ярусов
  await page.fill('#rightBody input[data-f="p.levels"]', '5');
  await page.waitForTimeout(300);
  s = await page.evaluate(() => { const sl = __f3d.S.slots.find((x) => x.code_prefix === 'TST1'); return __f3d.cellsOf(sl).length; });
  ok('AC3 правка числа ярусов меняет ячейки (5 ярусов → 90)', s === 90, 'n=' + s);
  const rows = await page.evaluate(() => document.querySelectorAll('#cellsBox tbody tr').length);
  ok('AC3 список ячеек в форме', rows > 20, 'rows=' + rows);
  // откат на 4 для скриншота + клик по ячейке
  await page.fill('#rightBody input[data-f="p.levels"]', '4');
  await page.waitForTimeout(200);
  await page.click('#cellsBox tbody tr:nth-child(4)');
  await page.waitForTimeout(300);
  const c = await proj(page, 60, 60, 0);
  await page.evaluate(([x, y]) => __f3d.V && 0, [0, 0]);
  // фокус на ряд FG-R1 для скриншота
  await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.code_prefix === 'FG-R1'); __f3d.selectObj({ kind: 'slot', id: s.id }); });
  await page.evaluate(() => { const V = __f3d.V; V.controls.target.set(125, 0, -27); V.camera.position.set(100, 38, -3); V.controls.update(); });
  await page.waitForTimeout(400);
  await page.click('#cellsBox tbody tr:nth-child(4)');
  await page.waitForTimeout(400);
  await page.screenshot({ path: SH + 'rack.png' });
  ok('AC3 консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  const persisted = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('f3d1:')).length);
  await page.waitForTimeout(1200);
  const persisted2 = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('f3d1:')).length);
  ok('Запись в хранилище после первой правки', persisted2 > 5, `до=${persisted} после=${persisted2}`);
  await browser.close();
}

async function t4_aisle_collide() {
  const { browser, page, errors } = await launch();
  await open(page);
  // станок: CNC-1 → в проход (Головний проїзд 42..92 x 44.2..47.8)
  await page.click('.layer[data-layer="line"]');
  const p0 = await pl(page, 'CNC-1');
  const from = await proj(page, p0.x, p0.y, 0.8), to = await proj(page, 70, 46, 0.8);
  await drag(page, from, to);
  let p1 = await pl(page, 'CNC-1');
  let iss = await page.evaluate(() => __f3d.S.issues.list.filter((i) => i.check === 'aisles_free').map((i) => i.msg));
  ok('AC4 (warn) станок в проходе → «Прохід перекрито»', iss.length > 0 && iss[0].includes('Прохід перекрито') && p1.y > 40, JSON.stringify(iss) + ' pos=' + JSON.stringify(p1));
  const tt = await toasts(page);
  ok('AC4 (warn) тост с замечанием', tt.some((t) => t.includes('Прохід перекрито')), tt.join('|'));
  await page.evaluate(() => { const V = __f3d.V; V.controls.target.set(66, 0, -44); V.camera.position.set(52, 30, -20); V.controls.update(); });
  await page.waitForTimeout(500);
  await page.screenshot({ path: SH + 'checks.png' });
  await page.evaluate(() => __f3d.setView('iso')); await page.waitForTimeout(300);
  // вернуть на место и переключить на block
  await page.evaluate((p) => { const x = __f3d.S.placements.find((q) => q.code === 'CNC-1'); x.x = p.x; x.y = p.y; __f3d.commit({ dirty: ['placements'] }); }, p0);
  await page.click('#rightBody summary:has-text("Налаштування перевірок")');
  await page.selectOption('#rightBody select[aria-label="Проходи не перекриті"]', 'block');
  await page.waitForTimeout(200);
  const from2 = await proj(page, p0.x, p0.y, 0.8);
  await drag(page, from2, to);
  p1 = await pl(page, 'CNC-1');
  const tt2 = await toasts(page);
  ok('AC4 (block) объект вернулся на место', Math.abs(p1.x - p0.x) < 1e-6 && Math.abs(p1.y - p0.y) < 1e-6, JSON.stringify(p1));
  ok('AC4 (block) сообщение', tt2.some((t) => t.includes('Заблоковано') && t.includes('Прохід перекрито')), tt2.join('|'));
  // AC5: пересечение двух станков и поворот
  await page.selectOption('#rightBody select[aria-label="Проходи не перекриті"]', 'warn');
  await page.evaluate(() => { const a = __f3d.S.placements.find((q) => q.code === 'SAW-2'); a.x = 46; a.y = 8.5; __f3d.commit({ dirty: ['placements'] }); });
  const col = await page.evaluate(() => __f3d.S.issues.list.filter((i) => i.check === 'collide').map((i) => i.msg));
  ok('AC5 пересечение двух станков подсвечивается', col.length > 0, JSON.stringify(col));
  const vis = await page.evaluate(() => { const v = __f3d.V.views.get('p:' + __f3d.S.placements.find((q) => q.code === 'SAW-2').id); return v.fill.visible && v.fill.material === __f3d.V.mat.fill.warn; });
  ok('AC5 визуальная подсветка (orange fill)', vis);
  // вернуть SAW-2; повернуть CNC-1 → footprint
  await page.evaluate(() => { const a = __f3d.S.placements.find((q) => q.code === 'SAW-2'); a.x = 45.5; a.y = 14; __f3d.commit({ dirty: ['placements'] }); });
  const g0 = await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-1'); const g = __f3d.pGeom(p, __f3d.S.vIdx.get(p.variant_id).v); return g.box.map((v) => +v.toFixed(2)); });
  const cp = await proj(page, p0.x, p0.y, 0.8);
  await page.mouse.click(cp.x, cp.y); await page.waitForTimeout(200);
  await page.keyboard.press('KeyR'); await page.waitForTimeout(300);
  const g1 = await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-1'); const g = __f3d.pGeom(p, __f3d.S.vIdx.get(p.variant_id).v); return { box: g.box.map((v) => +v.toFixed(2)), rot: p.rotation }; });
  const w0 = g0[2] - g0[0], h0 = g0[3] - g0[1], w1 = g1.box[2] - g1.box[0], h1 = g1.box[3] - g1.box[1];
  ok('AC5 поворот на 90° пересчитывает footprint', g1.rot === 90 && Math.abs(w1 - h0) < 0.01 && Math.abs(h1 - w0) < 0.01, `${w0}x${h0} -> ${w1.toFixed(2)}x${h1.toFixed(2)}`);
  ok('AC4/5 консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t6_models() {
  const { browser, page, errors } = await launch();
  await open(page);
  // GLB генерируем в странице через GLTFExporter
  const b64 = await page.evaluate(() => new Promise((res) => {
    const g = new THREE.Group();
    const m = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.8, 1.2), new THREE.MeshStandardMaterial({ color: 0x4477aa })); m.position.y = 0.9; g.add(m);
    const c = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.6, 16), new THREE.MeshStandardMaterial({ color: 0xcc7733 })); c.position.set(0.5, 2.1, 0); g.add(c);
    new THREE.GLTFExporter().parse(g, (buf) => { const u = new Uint8Array(buf); let s = ''; for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); res(btoa(s)); }, (e) => res(''), { binary: true });
  }));
  fs.writeFileSync(DIR + '/fixtures/box_m.glb', Buffer.from(b64, 'base64'));
  ok('GLB сгенерирован GLTFExporter', fs.statSync(DIR + '/fixtures/box_m.glb').size > 500);
  await page.click('#ltabs button[data-tab="catalog"]');
  await page.waitForTimeout(200);
  await page.click('.var >> nth=0 >> text=Картка');
  await page.waitForSelector('dialog[open]');
  const files = [['box_m.glb', 'GLB'], ['box_mm.obj', 'OBJ'], ['pyramid_mm.stl', 'STL']];
  for (const [f, fmtName] of files) {
    await page.setInputFiles('#modelFile', DIR + '/fixtures/' + f);
    await page.waitForTimeout(900);
    const info = await page.evaluate(() => { const dd = [...document.querySelectorAll('dialog .kv dd')].map((d) => d.textContent); return dd; });
    const prev = await page.evaluate(() => { const c = document.querySelector('dialog .pv canvas'); return !!c && c.width > 10; });
    const txt = info.join(' | ').replace(/[\u00a0 ]/g, '');
    let good = false;
    if (fmtName === 'GLB') good = txt.includes('GLB') && txt.includes('2400×1200×2400');
    if (fmtName === 'OBJ') good = txt.includes('OBJ') && txt.includes('1200×800×1500') && txt.includes('|12|');
    if (fmtName === 'STL') good = txt.includes('STL') && txt.includes('3000×1500×1800') && txt.includes('|6|');
    ok(`AC6 ${fmtName}: превью и габариты`, good && prev, txt);
    if (fmtName === 'GLB') {
      // габариты из модели → в поля
      await page.click('dialog >> text=Підставити габарити з моделі');
      const dims = await page.evaluate(() => ['length', 'width', 'height'].map((k) => document.querySelector(`dialog [data-f=${k}]`).value));
      ok('AC6 «Підставити габарити» (GLB 2400×1200×2400)', dims[0] === '2400' && dims[1] === '1200' && dims[2] === '2400', dims.join('x'));
      await page.screenshot({ path: SH + 'model.png' });
    }
  }
  // STEP — серверное сообщение
  fs.writeFileSync(DIR + '/fixtures/part.step', 'ISO-10303-21;');
  await page.setInputFiles('#modelFile', DIR + '/fixtures/part.step');
  await page.waitForTimeout(300);
  const stepMsg = await page.evaluate(() => document.querySelector('dialog .note')?.textContent || '');
  ok('STEP → «перетворення на сервері»', /сервері/.test(stepMsg), stepMsg.slice(0, 80));
  // > 20 МБ
  fs.writeFileSync(DIR + '/fixtures/big.glb', Buffer.alloc(21 * 1048576, 1));
  await page.setInputFiles('#modelFile', DIR + '/fixtures/big.glb');
  await page.waitForTimeout(500);
  const big = await page.evaluate(() => [...document.querySelectorAll('dialog .note')].map((n) => n.textContent).join(' '));
  ok('Лимит 20 МБ: понятный отказ', /20 МБ/.test(big) && /завеликий/.test(big), big.slice(0, 100));
  fs.unlinkSync(DIR + '/fixtures/big.glb');
  // вернуть STL и сохранить → модель в сцене
  await page.setInputFiles('#modelFile', DIR + '/fixtures/pyramid_mm.stl');
  await page.waitForTimeout(700);
  await page.click('dialog button:has-text("Зберегти")');
  await page.waitForTimeout(800);
  const hasModel = await page.evaluate(() => { const v = __f3d.S.catalog.flatMap((p) => p.variants).find((x) => x.model); return v && { name: v.model.name, tris: v.model.tris, fmt: v.model.format, inMem: __f3d.V.models.has(v.id) }; });
  ok('Модель сохранена в варианте (метаданные в db, файл в IndexedDB)', hasModel && hasModel.fmt === 'stl' && hasModel.tris === 6 && hasModel.inMem, JSON.stringify(hasModel));
  const idb = await page.evaluate(async () => { const v = __f3d.S.catalog.flatMap((p) => p.variants).find((x) => x.model); const r = await __f3d.files.get('model:' + v.id); return !!r && r.files.length; });
  ok('Файл модели в IndexedDB', idb === 1, String(idb));
  ok('AC6 консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t7_dxf() {
  const { browser, page, errors } = await launch();
  await open(page);
  await page.click('#ltabs button[data-tab="catalog"]');
  await page.click('button:has-text("Підкладка DXF")');
  await page.waitForTimeout(300);
  await page.setInputFiles('#dxfFile', DIR + '/fixtures/plan.dwg');
  await page.waitForTimeout(300);
  const dwg = await page.evaluate(() => document.querySelector('#dxfPanel').textContent);
  ok('DWG → «конвертуйте в DXF; DWG буде на сервері»', /конвертуйте в DXF/.test(dwg) && /на сервері/.test(dwg));
  await page.setInputFiles('#dxfFile', DIR + '/fixtures/plan_mm.dxf');
  await page.waitForTimeout(700);
  let st = await page.evaluate(() => { const S = __f3d.S, V = __f3d.V, id = S.ui.layer; const m = S.settings.underlays[id]; return m && { n: m.n, units: m.units, drawn: V.underlays.has(id) }; });
  // ожидаем: 4 LINE + 4 (LWPOLYLINE замкн.) + 48 (CIRCLE) + ARC + 2 (POLYLINE)
  ok('AC7 DXF разобран и нарисован на полу', st && st.drawn && st.n > 60 && st.units === 'mm', JSON.stringify(st));
  await page.click('#dxfPanel button:has-text("До центру будівлі")');
  await page.evaluate(() => __f3d.setView('plan'));
  await page.waitForTimeout(500);
  const bb = await page.evaluate(() => { const o = __f3d.V.underlays.get(__f3d.S.ui.layer).o; o.geometry.computeBoundingBox(); const b = o.geometry.boundingBox; return [b.min.x, b.max.x, b.min.z, b.max.z].map((v) => +v.toFixed(2)); });
  ok('DXF: габарит 60×30 м после центровки', Math.abs((bb[1] - bb[0]) - 60) < 0.2 && Math.abs((bb[3] - bb[2]) - 30) < 0.2, JSON.stringify(bb));
  await page.screenshot({ path: SH + 'dxf.png' });
  // масштаб по двум точкам: берём концы линии (0,0)-(60,0) → 60 м на кресленні; «реально» 30 м → масштаб ×0.5
  const A = await page.evaluate(() => { const o = __f3d.V.underlays.get(__f3d.S.ui.layer).o; const p = o.geometry.attributes.position.array; return [{ x: p[0], y: -p[2] }, { x: p[3], y: -p[5] }]; });
  await page.click('#dxfPanel button:has-text("Прив’язати масштаб")');
  const a = await proj(page, A[0].x, A[0].y, 0), b = await proj(page, A[1].x, A[1].y, 0);
  await page.mouse.click(a.x, a.y); await page.waitForTimeout(150); await page.mouse.click(b.x, b.y); await page.waitForTimeout(300);
  const d = await page.evaluate(() => __f3d.S.ui.dxfScale && __f3d.S.ui.dxfScale.d);
  ok('Масштаб по двум точкам: измеренная длина ≈ 60 м', d && Math.abs(d - 60) < 1.2, String(d));
  await page.fill('#dxfPanel input[data-f="ulreal"]', '30');
  await page.click('#dxfPanel button:has-text("Застосувати")');
  await page.waitForTimeout(300);
  const sc = await page.evaluate(() => __f3d.S.settings.underlays[__f3d.S.ui.layer].scale);
  ok('Масштаб применён (~0.5)', sc > 0.45 && sc < 0.55, String(sc));
  ok('AC7 консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t8_publish() {
  const { browser, page, errors } = await launch();
  await open(page);
  const before = await pl(page, 'CNC-2');
  // изменить: переместить станок и добавить стеллаж
  await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-2'); p.x += 2; __f3d.commit({ dirty: ['placements'] }); });
  await page.evaluate(() => { __f3d.S.ui.layer = 'ly_fg'; __f3d.commit({}); const spec = { template: 'pallet_rack', prefix: 'NEW-R1', params: { bays: 6, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.9, positions_per_bay: 2, max_load_kg: 2000 } }; });
  await page.click('.layer[data-layer="fg"]');
  await page.evaluate(() => { const S = __f3d.S; S.slots.push({ id: 'sl_new', layer_id: 'ly_fg', template: 'pallet_rack', code_prefix: 'NEW-R1', x: 60, y: 60, rotation: 0, params: { bays: 6, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.9, positions_per_bay: 2, max_load_kg: 2000 }, overrides: {} }); __f3d.commit({ dirty: ['slots'] }); });
  await page.waitForTimeout(300);
  const chip = await page.textContent('#draftChip');
  ok('«Чернетка · змінено N»', /змінено [1-9]/.test(chip), chip);
  await page.click('#btnPublish');
  await page.waitForSelector('dialog[open]');
  await page.fill('dialog textarea', 'Тест: стелаж NEW-R1 і зсув CNC-2');
  const txt = await page.textContent('dialog');
  ok('Публикация: сводка «буде створено в Odoo»', /Буде створено в Odoo/.test(txt) && /24/.test(txt) && /змінено/.test(txt) && /видалено/.test(txt) && /NEW-R1-B01-L1/.test(txt) && /імітація/.test(txt));
  await page.screenshot({ path: SH + 'publish.png' });
  await page.click('dialog button:has-text("Підтвердити й опублікувати")');
  await page.waitForTimeout(900);
  const v = await page.evaluate(() => ({ vs: __f3d.S.versions.map((x) => x.n + ':' + x.note), av: __f3d.S.site.active_version }));
  ok('AC8 публикация создала версию 2', v.av === 2 && v.vs.length === 2, JSON.stringify(v));
  const chip2 = await page.textContent('#draftChip');
  ok('После публикации чернетка без змін', /без змін/.test(chip2), chip2);
  // версия лежит в хранилище
  const stored = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.includes(':versions:')).length);
  ok('Версии записаны в хранилище', stored >= 3, 'keys=' + stored);
  // правка и возврат к v1
  await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-2'); p.x += 3; __f3d.commit({ dirty: ['placements'] }); });
  await page.click('#btnHistory');
  await page.waitForSelector('dialog[open]');
  const hist = await page.textContent('dialog');
  ok('AC8 «Історія версій» показывает версии', /v2/.test(hist) && /v1/.test(hist) && /Тест: стелаж/.test(hist));
  await page.click('dialog .ver:has-text("v1") button');
  await page.waitForSelector('dialog:has-text("Повернути чернетку до v1?")');
  await page.click('dialog:has-text("Повернути чернетку до v1?") button:has-text("Повернути")');
  await page.waitForTimeout(800);
  const after = await pl(page, 'CNC-2');
  const hasNew = await page.evaluate(() => __f3d.S.slots.some((s) => s.code_prefix === 'NEW-R1'));
  ok('AC8 возврат к версии меняет черновик (CNC-2 на месте v1, NEW-R1 нет)', Math.abs(after.x - before.x) < 1e-6 && !hasNew, JSON.stringify(after) + ' new=' + hasNew);
  const chip3 = await page.textContent('#draftChip');
  ok('AC8 чернетка отличается от активной v2', /змінено [1-9]/.test(chip3), chip3);
  ok('AC8 консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t9_roles() {
  const { browser, page, errors } = await launch();
  await open(page);
  await page.selectOption('#roleSel', 'technologist');
  await page.waitForTimeout(300);
  await page.click('.layer[data-layer="fg"]');
  await page.waitForTimeout(300);
  const rack = await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.code_prefix === 'FG-R1'); return { x: s.x, y: s.y }; });
  const from = await proj(page, rack.x, rack.y - 5, 1);
  await drag(page, from, { x: from.x + 90, y: from.y + 30 });
  const rack2 = await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.code_prefix === 'FG-R1'); return { x: s.x, y: s.y }; });
  const tt = await toasts(page);
  ok('AC9 Технолог не двигает стеллаж склада', rack2.x === rack.x && rack2.y === rack.y, JSON.stringify(rack2));
  ok('AC9 подсказка «редагує Комірник»', tt.some((t) => /редагує/.test(t) && /Комірник/.test(t)), tt.join('|'));
  const dis = await page.evaluate(() => document.querySelector('#rightBody input[data-f="x"]').disabled);
  ok('AC9 поля свойств чужого слоя заблокированы', dis);
  const lockTxt = await page.evaluate(() => document.querySelector('#rightBody .note.lock')?.textContent || '');
  ok('AC9 подсказка в панели', /редагує Комірник/.test(lockTxt), lockTxt);
  // Комірник правит склад
  await page.selectOption('#roleSel', 'storekeeper');
  await page.waitForTimeout(300);
  const dis2 = await page.evaluate(() => document.querySelector('#rightBody input[data-f="x"]').disabled);
  ok('AC9 Комірник правит склад', !dis2);
  // режим просмотра
  await page.click('#modeSeg button[data-mode="view"]');
  await page.waitForTimeout(200);
  const dis3 = await page.evaluate(() => document.querySelector('#rightBody input[data-f="x"]').disabled);
  ok('Режим «Перегляд» блокирует правку', dis3);
  ok('AC9 консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t10_sites() {
  const { browser, page, errors } = await launch();
  await open(page);
  ok('AC10 переключатель содержит пункт «Порожня площадка»', await page.evaluate(() => [...document.querySelectorAll('#siteSel option')].some((o) => o.value === '__new:empty')));
  await page.selectOption('#siteSel', '__new:empty');
  await page.waitForTimeout(1800);
  let st = await page.evaluate(() => ({ n: __f3d.S.app.sites.length, name: __f3d.S.site.name, b: __f3d.S.site.building, layers: __f3d.S.layers.map((l) => l.name + ':' + l.elevation), cat: __f3d.S.catalog.flatMap((p) => p.variants).length, changed: __f3d.S.changed }));
  ok('AC10 новая порожня площадка', st.n === 2 && st.name === 'Порожня площадка' && st.b.length === 60 && st.b.width === 30 && st.b.height === 8 && st.layers.length === 5 && st.cat === 4 && st.changed === 0, JSON.stringify(st));
  await page.screenshot({ path: SH + '_empty.png' });
  const keys = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('f3d1:')).length);
  ok('Пример и новая площадка записаны в хранилище', keys > 15, 'keys=' + keys);
  await page.selectOption('#siteSel', 'sample');
  await page.waitForTimeout(1500);
  st = await page.evaluate(() => ({ name: __f3d.S.site.name, slots: __f3d.S.slots.length, pl: __f3d.S.placements.length }));
  ok('AC10 переключение обратно на пример', /Меблеве/.test(st.name) && st.slots > 50 && st.pl > 30, JSON.stringify(st));
  await page.selectOption('#siteSel', await page.evaluate(() => __f3d.S.app.sites.find((s) => s.id !== 'sample').id));
  await page.waitForTimeout(1200);
  st = await page.evaluate(() => ({ name: __f3d.S.site.name, slots: __f3d.S.slots.length }));
  ok('AC10 переключение на пустую', st.name === 'Порожня площадка' && st.slots === 0, JSON.stringify(st));
  // перезагрузка: состояние берётся из хранилища
  await page.reload(); await page.waitForFunction(() => document.documentElement.dataset.ready === '1'); await page.waitForTimeout(800);
  st = await page.evaluate(() => ({ name: __f3d.S.site.name, n: __f3d.S.app.sites.length }));
  ok('Перезагрузка: площадка из хранилища', st.name === 'Порожня площадка' && st.n === 2, JSON.stringify(st));
  ok('AC10 консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

(async () => {
  const which = process.argv.slice(2);
  const all = { t1_load, t3_rack, t4_aisle_collide, t6_models, t7_dxf, t8_publish, t9_roles, t10_sites };
  for (const [k, f] of Object.entries(all)) {
    if (which.length && !which.includes(k)) continue;
    try { await f(); } catch (e) { ok(k + ' exception', false, String(e).split('\n').slice(0, 3).join(' ')); }
  }
  const fails = res.filter((r) => r[0] === 'FAIL');
  console.log(`\nИТОГО: ${res.length - fails.length} passed, ${fails.length} failed`);
})();
