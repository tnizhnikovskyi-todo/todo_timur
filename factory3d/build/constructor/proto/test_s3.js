// Слайс S3 «Робота зі складом» у прототипі: скасування й повтор (F09-01), мультивиділення й рамка (F09-02/03), дублювання, копіювання й вставлення
// (F09-04/05), масив, масове створення, вирівнювання й групи (F09-08/09), етикети (F05), теплові карти (F07), пошук і картка (F06),
// мобільний режим 390×844 (F06-04), рівні доступу й збереження (N-02, N-05, N-08).
// Запуск: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node build/constructor/proto/test_s3.js (після python3 build/constructor/proto/build.py)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { launch, open } = require('./harness');
const res = [];
const ok = (name, cond, extra) => { res.push(!!cond); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra !== undefined && !cond ? ' :: ' + extra : '')); };
const DL = fs.mkdtempSync(path.join(os.tmpdir(), 's3dl-'));

/** Чиста сцена: шар «Склади» з відомими місцями (зона ZN, три ряди, місце на підлозі, машинне місце) і плоский вигляд. */
async function prepare(page) {
  return await page.evaluate(() => {
    const { S, E } = __f3d;
    const ly = S.layers.find((l) => l.kind === 'storage');
    for (const t of ['pallet_rack', 'floor_spot', 'floor_stack', 'zone', 'shelf']) if (!ly.slot_types.includes(t)) ly.slot_types.push(t);
    S.ui.layer = ly.id;
    S.slots = S.slots.filter((s) => s.layer_id !== ly.id);
    S.placements = S.placements.filter((p) => p.layer_id !== ly.id);
    const mk = (id, tpl, prefix, x, y, params) => ({ id, rid: null, etag: null, layer_id: ly.id, template: tpl, code_prefix: prefix, x, y, rotation: 0, params, overrides: {}, parent_location_id: null });
    const rack = { bays: 3, levels: 3, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000 };
    S.slots.push(mk('zt', 'zone', 'ZT', 60, 12, { length: 40, width: 20, title: 'Тестова зона', color: '#9fb7c9' }));
    S.slots.push(mk('ra', 'pallet_rack', 'RA', 45, 6, { ...rack }));
    S.slots.push(mk('rb', 'pallet_rack', 'RB', 45, 12, { ...rack }));
    S.slots.push(mk('rc', 'pallet_rack', 'RC', 45, 18, { ...rack }));
    S.slots.push(mk('f1', 'floor_spot', 'FS-1', 75, 6, { length: 2, width: 1.2, height: 1.5, capacity: 1, loc_kind: 'area', shape: 'zone' }));
    E.commit({});
    E.setView('plan');
    E.renderAll();
    E.undoReset();
    return ly.id;
  });
}
const ids = () => `(() => ({ slots: __f3d.S.slots.map((s) => s.id), n: __f3d.S.slots.length }))()`;
const flush = async (page) => { await page.evaluate(() => __f3d.E.flushNow()); await page.waitForTimeout(80); };
const screenOf = (page, id) => page.evaluate((id) => {
  const { S, V, core } = __f3d;
  const s = S.sIdx.get(id) || S.pIdx.get(id);
  const r = V.canvas.getBoundingClientRect();
  const v = new core.THREE.Vector3(s.x, 0.2, -s.y).project(V.camera);
  return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };
}, id);

async function t_undo(page, errors) {
  await prepare(page);
  const r0 = await page.evaluate(() => ({ n: __f3d.S.hist.stack.length, idx: __f3d.S.hist.idx, ui: !!document.getElementById('s3Undo') }));
  ok('історія: кнопки ↶ ↷ у розмітці', r0.ui);
  // правка → крок з підписом
  await page.evaluate(() => { const s = __f3d.S.sIdx.get('ra'); s.x += 3; __f3d.E.commit({}); });
  await page.waitForTimeout(250);
  const r1 = await page.evaluate(() => ({ n: __f3d.S.hist.stack.length, label: __f3d.E.undoState().undoLabel, can: __f3d.E.undoState().canUndo, btn: document.getElementById('s3Undo').disabled, title: document.getElementById('s3Undo').title }));
  ok('історія: крок «Переміщено: RA», кнопка ↶ активна з підписом', r1.label === 'Переміщено: RA' && r1.can && !r1.btn && r1.title.includes('Переміщено: RA'), JSON.stringify(r1));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(150);
  const r2 = await page.evaluate(() => ({ x: __f3d.S.sIdx.get('ra').x, redo: __f3d.E.undoState().canRedo }));
  ok('Ctrl+Z повертає положення (45) і вмикає повтор', r2.x === 45 && r2.redo, JSON.stringify(r2));
  await page.keyboard.press('Control+Shift+Z');
  await page.waitForTimeout(150);
  ok('Ctrl+Shift+Z повторює (48)', await page.evaluate(() => __f3d.S.sIdx.get('ra').x === 48));
  await page.keyboard.press('Control+z');
  await page.keyboard.press('Control+y');
  await page.waitForTimeout(200);
  ok('Ctrl+Y повторює після скасування', await page.evaluate(() => __f3d.S.sIdx.get('ra').x === 48));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(150);
  // видалення й скасування видалення (місце знову є, коди ті самі)
  const del = await page.evaluate(async () => {
    const { S, E } = __f3d;
    S.slots = S.slots.filter((s) => s.id !== 'rc'); S.sel = null; E.undoLabel('Видалення RC'); E.commit({});
    await new Promise((r) => setTimeout(r, 200));
    const gone = !S.sIdx.has('rc');
    const n1 = S.slots.length;
    await E.undo();
    return { gone, back: S.sIdx.has('rc'), n: S.slots.length - n1 };
  });
  ok('скасування видалення повертає місце RC', del.gone && del.back && del.n === 1, JSON.stringify(del));
  // безперервне введення в одне поле — один крок
  const co = await page.evaluate(async () => {
    const { S, E } = __f3d; const n0 = S.hist.idx;
    for (const v of [4, 5, 6]) { S.sIdx.get('rb').params.bays = v; E.scheduleSave(); await new Promise((r) => setTimeout(r, 200)); }
    return { added: S.hist.idx - n0, label: E.undoState().undoLabel };
  });
  ok('безперервна правка одного поля — один крок історії', co.added === 1 && co.label.startsWith('Параметри'), JSON.stringify(co));
  await page.evaluate(() => __f3d.E.undo());
  ok('скасування параметра повертає 3 секції', await page.evaluate(() => __f3d.S.sIdx.get('rb').params.bays === 3));
  // адресація площадки (S1, saveAddr) входить в історію
  const addr = await page.evaluate(async () => {
    const { S, E } = __f3d;
    const before = JSON.stringify(S.site.addr || null);
    await E.runDialog('addr.applySite', { vals: { addr: { tpl: '{prefix} {row} {bay} {level}' }, depth_mode: 'level', loc_tree: 'flat' }, renumber: 'new' });
    await new Promise((r) => setTimeout(r, 250));
    const changed = JSON.stringify(S.site.addr || null) !== before;
    const label = E.undoState().undoLabel;
    await E.undo();
    return { changed, label, restored: JSON.stringify(S.site.addr || null) === before };
  });
  ok('адресація площадки: крок «Адресація площадки», скасування повертає налаштування', addr.changed && addr.label === 'Адресація площадки' && addr.restored, JSON.stringify(addr));
  // режим перегляду: скасування неактивне з підказкою
  await page.evaluate(() => { __f3d.S.app.mode = 'view'; __f3d.E.renderAll(); });
  const v = await page.evaluate(() => ({ dis: document.getElementById('s3Undo').disabled, title: document.getElementById('s3Undo').title }));
  ok('N-02: у режимі перегляду ↶ неактивна з підказкою', v.dis && v.title.includes('Режим перегляду'), JSON.stringify(v));
  await page.evaluate(() => { __f3d.S.app.mode = 'edit'; __f3d.E.renderAll(); });
  ok('undo: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_multi(page, errors) {
  await prepare(page);
  await page.evaluate(() => __f3d.E.setView('plan'));
  await page.waitForTimeout(300);
  const pa = await screenOf(page, 'ra');
  const pb = await screenOf(page, 'rb');
  await page.mouse.click(pa.x, pa.y);
  await page.keyboard.down('Control');
  await page.mouse.click(pb.x, pb.y);
  await page.keyboard.up('Control');
  const m1 = await page.evaluate(() => ({ multi: __f3d.S.multi.map((r) => r.id), sel: __f3d.S.sel && __f3d.S.sel.id, title: document.querySelector('#multiPanel h3') && document.querySelector('#multiPanel h3').textContent }));
  ok('Ctrl+клік додає в виділення, панель «Виділено 2»', m1.multi.length === 2 && m1.title === 'Виділено 2' && m1.sel === 'rb', JSON.stringify(m1));
  // перетягування одного двигає всіх зі збереженням взаємного положення
  const before = await page.evaluate(() => ({ a: [__f3d.S.sIdx.get('ra').x, __f3d.S.sIdx.get('ra').y], b: [__f3d.S.sIdx.get('rb').x, __f3d.S.sIdx.get('rb').y] }));
  await page.mouse.move(pb.x, pb.y);
  await page.mouse.down();
  await page.mouse.move(pb.x + 30, pb.y + 4, { steps: 4 });
  await page.mouse.move(pb.x + 60, pb.y + 8, { steps: 4 });
  await page.mouse.up();
  await page.waitForTimeout(250);
  const after = await page.evaluate(() => ({ a: [__f3d.S.sIdx.get('ra').x, __f3d.S.sIdx.get('ra').y], b: [__f3d.S.sIdx.get('rb').x, __f3d.S.sIdx.get('rb').y], multi: __f3d.S.multi.length, label: __f3d.E.undoState().undoLabel }));
  const da = [after.a[0] - before.a[0], after.a[1] - before.a[1]];
  const db = [after.b[0] - before.b[0], after.b[1] - before.b[1]];
  ok('перетягування одного з виділених двигає обох на ту саму дельту', Math.abs(da[0]) > 0.5 && Math.abs(da[0] - db[0]) < 1e-6 && Math.abs(da[1] - db[1]) < 1e-6 && after.multi === 2, JSON.stringify({ da, db }));
  ok('переміщення групи — один крок «Переміщено об’єктів: 2»', after.label === 'Переміщено об’єктів: 2', after.label);
  await page.evaluate(() => __f3d.E.undo());
  ok('скасування повертає обох', await page.evaluate((b) => __f3d.S.sIdx.get('ra').x === b.a[0] && __f3d.S.sIdx.get('rb').x === b.b[0], before));
  // R повертає ряди групи навколо центра
  await page.evaluate(() => __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }]));
  const c0 = await page.evaluate(() => { const a = __f3d.S.sIdx.get('ra'), b = __f3d.S.sIdx.get('rb'); return { dx: b.x - a.x, dy: b.y - a.y }; });
  await page.keyboard.press('r');
  await page.waitForTimeout(150);
  const c1 = await page.evaluate(() => { const a = __f3d.S.sIdx.get('ra'), b = __f3d.S.sIdx.get('rb'); return { dx: b.x - a.x, dy: b.y - a.y, ra: a.rotation, rb: b.rotation }; });
  ok('R повертає виділені ряди на 90° із збереженням відстані', Math.abs(c1.dx + c0.dy) < 1e-6 && Math.abs(c1.dy - c0.dx) < 1e-6 && c1.ra === 90 && c1.rb === 90, JSON.stringify({ c0, c1 }));
  await page.evaluate(() => __f3d.E.undo());
  // рамка в 2D: Shift+протягнути цілком охоплює; Shift+Ctrl додає
  await page.evaluate(() => { __f3d.E.selectObj(null); __f3d.E.setView('plan'); });
  await page.waitForTimeout(300);
  const box = await page.evaluate(() => {
    const { S, V, core } = __f3d; const r = V.canvas.getBoundingClientRect();
    const pt = (x, y) => { const v = new core.THREE.Vector3(x, 0, -y).project(V.camera); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height }; };
    return { p0: pt(38, 24), p1: pt(54, 2.5) };
  });
  await page.keyboard.down('Shift');
  await page.mouse.move(box.p0.x, box.p0.y);
  await page.mouse.down();
  await page.mouse.move((box.p0.x + box.p1.x) / 2, (box.p0.y + box.p1.y) / 2, { steps: 3 });
  await page.mouse.move(box.p1.x, box.p1.y, { steps: 3 });
  await page.mouse.up();
  await page.keyboard.up('Shift');
  await page.waitForTimeout(200);
  const bx = await page.evaluate(() => __f3d.S.multi.map((r) => r.id).sort());
  ok('рамка Shift+протягнути виділяє три ряди (цілком у рамці)', bx.join() === 'ra,rb,rc', bx.join());
  await page.keyboard.down('Shift');
  await page.keyboard.down('Control');
  const pf = await screenOf(page, 'f1');
  await page.mouse.move(pf.x - 40, pf.y - 25);
  await page.mouse.down();
  await page.mouse.move(pf.x + 40, pf.y + 25, { steps: 4 });
  await page.mouse.up();
  await page.keyboard.up('Control');
  await page.keyboard.up('Shift');
  await page.waitForTimeout(200);
  ok('Shift+Ctrl+рамка додає до наявного виділення', await page.evaluate(() => __f3d.S.multi.map((r) => r.id).sort().join()) === 'f1,ra,rb,rc');
  // панель: список, кнопки
  ok('панель «Виділено 4»: список і кнопки дій', await page.evaluate(() => document.querySelectorAll('#multiList [data-key]').length === 4 && ['btnMultiDup', 'btnMultiCopy', 'btnMultiRot', 'btnMultiDel', 'btnMultiPreset'].every((i) => document.getElementById(i))));
  ok('multi: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_tools(page, errors) {
  await prepare(page);
  // Ctrl+D: ряд з наступним номером (RA → RB зайнято → RD…)
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'ra' }));
  await page.keyboard.press('Control+d');
  await page.waitForTimeout(200);
  const d1 = await page.evaluate(() => { const S = __f3d.S; const n = S.slots.filter((s) => s.layer_id === S.ui.layer && s.template === 'pallet_rack'); const c = S.slots.find((s) => s.id === S.sel.id); return { n: n.length, prefix: c.code_prefix, rid: c.rid, ov: Object.keys(c.overrides).length, y: c.y }; });
  ok('Ctrl+D: ряд — нова копія з наступним вільним номером (RA → RA-2)', d1.n === 4 && d1.prefix === 'RA-2' && d1.rid === null && d1.ov === 0, JSON.stringify(d1));
  await page.evaluate(() => __f3d.E.undo());
  ok('скасування дублювання прибирає копію', await page.evaluate(() => __f3d.S.slots.filter((s) => s.layer_id === __f3d.S.ui.layer && s.template === 'pallet_rack').length === 3));
  // ярус зверху: виділена комірка → +1 ярус
  await page.evaluate(() => { __f3d.selectObj({ kind: 'slot', id: 'rb' }); __f3d.S.selCell = __f3d.cellsOf(__f3d.S.sIdx.get('rb'))[0].code; });
  await page.keyboard.press('Control+d');
  await page.waitForTimeout(150);
  ok('Ctrl+D з виділеною коміркою: ярус зверху (3 → 4)', await page.evaluate(() => __f3d.S.sIdx.get('rb').params.levels === 4));
  await page.evaluate(() => __f3d.E.undo());
  // секція в кінці ряду
  await page.evaluate(() => { __f3d.selectObj({ kind: 'slot', id: 'rb' }); });
  await page.click('#btnDupBay');
  ok('«Секція в кінець ряду»: bays 3 → 4', await page.evaluate(() => __f3d.S.sIdx.get('rb').params.bays === 4));
  await page.evaluate(() => __f3d.E.undo());
  // зона: «(копія)»; місце на підлозі: наступний код
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'zt' }));
  await page.keyboard.press('Control+d');
  await page.waitForTimeout(150);
  const z = await page.evaluate(() => { const s = __f3d.S.sIdx.get(__f3d.S.sel.id); return { t: s.params.title, p: s.code_prefix }; });
  ok('Ctrl+D: зона — «(копія)» і новий код', z.t === 'Тестова зона (копія)' && z.p !== 'ZT', JSON.stringify(z));
  await page.evaluate(() => __f3d.E.undo());
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'f1' }));
  await page.keyboard.press('Control+d');
  await page.waitForTimeout(150);
  ok('Ctrl+D: місце на підлозі — наступний код FS-2', await page.evaluate(() => __f3d.S.sIdx.get(__f3d.S.sel.id).code_prefix === 'FS-2'));
  await page.evaluate(() => __f3d.E.undo());
  // Ctrl+C / Ctrl+V: у виділену зону
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'ra' }));
  await page.keyboard.press('Control+c');
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'zt' }));
  await page.keyboard.press('Control+v');
  await page.waitForTimeout(200);
  const pz = await page.evaluate(() => { const s = __f3d.S.sIdx.get(__f3d.S.sel.id); const z = __f3d.S.sIdx.get('zt'); return { prefix: s.code_prefix, inside: Math.abs(s.x - z.x) < 20 && Math.abs(s.y - z.y) < 10, ov: Object.keys(s.overrides).length, id: s.id }; });
  ok('Ctrl+V у виділену зону: копія всередині зони, нова й порожня', pz.inside && pz.prefix !== 'RA' && pz.ov === 0, JSON.stringify(pz));
  await page.evaluate(() => __f3d.E.undo());
  // вставлення в інший шар, якщо активний не допускає тип
  const lay = await page.evaluate(() => { const { S, E } = __f3d; const prod = S.layers.find((l) => l.kind === 'production'); S.ui.layer = prod.id; E.selectObj(null); E.renderAll(); return prod.slot_types.includes('pallet_rack'); });
  await page.keyboard.press('Control+v');
  await page.waitForTimeout(200);
  const pl = await page.evaluate(() => { const s = __f3d.S.sIdx.get(__f3d.S.sel && __f3d.S.sel.id); return s && __f3d.S.lIdx.get(s.layer_id).kind; });
  ok('Ctrl+V: шар «Виробництво» не допускає стелаж → копія в найближчий шар зі складами', lay === false && pl === 'storage', String(pl));
  await page.evaluate(() => { __f3d.E.undo(); __f3d.S.ui.layer = __f3d.S.layers.find((l) => l.kind === 'storage').id; });
  // масив N×M
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'f1' }));
  const arr = await page.evaluate(() => __f3d.E.arrayCopies({ nx: 3, ny: 2, dx: 2.5, dy: 1.8 }));
  const arr2 = await page.evaluate(() => __f3d.S.slots.filter((s) => s.template === 'floor_spot').map((s) => s.code_prefix).sort().join());
  ok('масив 3×2: 5 копій місця на підлозі з унікальними кодами', arr === 5 && arr2 === 'FS-1,FS-2,FS-3,FS-4,FS-5,FS-6', arr2 + ' / ' + arr);
  await page.evaluate(() => __f3d.E.undo());
  ok('масив — один крок історії', await page.evaluate(() => __f3d.S.slots.filter((s) => s.template === 'floor_spot').length === 1));
  // масове створення в зоні
  await page.evaluate(() => { __f3d.S.slots = __f3d.S.slots.filter((s) => s.template === 'zone'); __f3d.E.commit({}); __f3d.selectObj({ kind: 'slot', id: 'zt' }); });
  await page.evaluate(() => __f3d.E.runDialog('bulk'));
  await page.waitForSelector('#bulkBody');
  await page.fill('#bulkBody [data-s3="rows"]', '3');
  await page.fill('#bulkBody [data-s3="sections"]', '4');
  await page.fill('#bulkBody [data-s3="levels"]', '2');
  await page.waitForTimeout(100);
  const info = await page.textContent('#bulkInfo');
  ok('масове створення: попередній перегляд показує 3 ряди й 24 комірки', info.includes('Рядів: 3 із 3') && info.includes('комірок: 24'), info);
  ok('масове створення: SVG попереднього перегляду', await page.locator('#bulkPreview svg rect').count() >= 4);
  await page.click('#btnBulkGo');
  await page.waitForTimeout(300);
  const bulk = await page.evaluate(() => __f3d.S.slots.filter((s) => s.template === 'pallet_rack').map((s) => ({ b: s.params.bays, l: s.params.levels, y: s.y })));
  const zoneY = await page.evaluate(() => __f3d.S.sIdx.get('zt'));
  ok('масове створення: 3 стелажі 4×2 у зоні з проходом між рядами', bulk.length === 3 && bulk.every((r) => r.b === 4 && r.l === 2) && bulk.every((r) => Math.abs(r.y - zoneY.y) <= zoneY.params.width / 2), JSON.stringify(bulk));
  await page.evaluate(() => __f3d.E.undo());
  ok('масове створення — один крок історії', await page.evaluate(() => __f3d.S.slots.filter((s) => s.template === 'pallet_rack').length === 0));
  ok('tools: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_align(page, errors) {
  await prepare(page);
  await page.evaluate(() => { __f3d.S.sIdx.get('rb').x = 50; __f3d.S.sIdx.get('rc').x = 60; __f3d.E.commit({}); __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }, { kind: 'slot', id: 'rc' }]); });
  const x0 = await page.evaluate(() => ['ra', 'rb', 'rc'].map((i) => __f3d.S.sIdx.get(i).x));
  await page.click('#btnAlign-left');
  await page.waitForTimeout(150);
  const left = await page.evaluate(() => ['ra', 'rb', 'rc'].map((i) => { const g = __f3d.core.live.sGeom(__f3d.S.sIdx.get(i)); return +g.box[0].toFixed(3); }));
  ok('вирівнювання «Ліворуч»: лівий край однаковий', left.every((v) => Math.abs(v - left[0]) < 1e-3), JSON.stringify(left));
  await page.evaluate(() => __f3d.E.undo());
  await page.evaluate(() => __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }, { kind: 'slot', id: 'rc' }]));
  await page.evaluate(() => { __f3d.S.sIdx.get('rb').x = 47; __f3d.S.sIdx.get('rc').x = 62; __f3d.E.commit({}); __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }, { kind: 'slot', id: 'rc' }]); });
  await page.click('#btnDistX');
  await page.waitForTimeout(150);
  const gaps = await page.evaluate(() => { const b = ['ra', 'rb', 'rc'].map((i) => __f3d.core.live.sGeom(__f3d.S.sIdx.get(i)).box).sort((p, q) => p[0] - q[0]); return [b[1][0] - b[0][2], b[2][0] - b[1][2]].map((v) => +v.toFixed(3)); });
  ok('розподіл по X: проміжки між трьома рядами рівні', Math.abs(gaps[0] - gaps[1]) < 1e-3, JSON.stringify(gaps));
  await page.evaluate(() => __f3d.E.undo());
  // групування в нову зону й розгрупування
  await page.evaluate(() => __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }]));
  const codes0 = await page.evaluate(() => ['ra', 'rb'].flatMap((i) => __f3d.cellsOf(__f3d.S.sIdx.get(i)).map((c) => c.code)).join());
  await page.click('#btnGroupZone');
  await page.waitForTimeout(200);
  const g = await page.evaluate(() => { const z = __f3d.S.sIdx.get(__f3d.S.sel.id); const ra = __f3d.S.sIdx.get('ra'); return { tpl: z.template, title: z.params.title, inside: Math.abs(ra.x - z.x) < z.params.length / 2, n: __f3d.S.slots.filter((s) => s.layer_id === __f3d.S.ui.layer).length }; });
  const codes1 = await page.evaluate(() => ['ra', 'rb'].flatMap((i) => __f3d.cellsOf(__f3d.S.sIdx.get(i)).map((c) => c.code)).join());
  ok('групування: нова зона навколо виділених, коди комірок не змінились', g.tpl === 'zone' && g.inside && g.n === 6 && codes0 === codes1, JSON.stringify(g));
  await page.click('#btnUngroup');
  await page.waitForSelector('#dlgYes');
  await page.click('#dlgYes');
  await page.waitForFunction(() => __f3d.S.slots.filter((s) => s.layer_id === __f3d.S.ui.layer).length === 5 && !__f3d.S.sel);
  ok('розгрупування: зону прибрано, ряди лишились', await page.evaluate(() => __f3d.S.slots.filter((s) => s.layer_id === __f3d.S.ui.layer).length === 5));
  // властивості: лише змінені поля
  await page.evaluate(() => __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }]));
  const ap = await page.evaluate(() => { const y0 = __f3d.S.sIdx.get('ra').y; __f3d.E.applyProps({ dy: 1 }); return __f3d.S.sIdx.get('ra').y - y0 === 1 && __f3d.S.sIdx.get('ra').rotation === 0; });
  ok('властивості кількох: зсув Y застосовано, поворот не чіпано', ap);
  // видалення групи з підтвердженням
  await page.evaluate(() => __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }]));
  await page.click('#btnMultiDel');
  await page.waitForSelector('#dlgYes');
  await page.click('#dlgYes');
  await page.waitForFunction(() => !__f3d.S.sIdx.has('ra') && !__f3d.S.sIdx.has('rb'));
  ok('«Прибрати всі» видаляє виділені', await page.evaluate(() => !__f3d.S.sIdx.has('ra') && !__f3d.S.sIdx.has('rb') && __f3d.S.multi.length === 0));
  await page.evaluate(() => __f3d.E.undo());
  ok('скасування «Прибрати всі» повертає обох', await page.evaluate(() => __f3d.S.sIdx.has('ra') && __f3d.S.sIdx.has('rb')));
  // «Зберегти виділене» у бібліотеку
  await page.evaluate(() => __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }]));
  await page.click('#btnMultiPreset');
  await page.waitForSelector('dialog[open] [data-f="multi-preset-name"]');
  await page.fill('dialog[open] [data-f="multi-preset-name"]', 'Тест-група');
  await page.click('#btnMultiPresetGo');
  await page.waitForTimeout(250);
  const pr = await page.evaluate(() => __f3d.core.registries ? 1 : 0);
  const preset = await page.evaluate(async () => { const lib = await __f3d.adapter.library({ op: 'list' }); const p = lib.presets.find((x) => x.name === 'Тест-група'); return p && { kind: p.kind, n: p.data.slots.length }; });
  ok('«Зберегти виділене»: пресет «група» з двома місцями в бібліотеці', preset && preset.kind === 'group' && preset.n === 2, JSON.stringify(preset));
  ok('align: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}


async function t_labels(page, errors) {
  await prepare(page);
  await page.evaluate(() => { __f3d.E.setMulti([{ kind: 'slot', id: 'ra' }, { kind: 'slot', id: 'rb' }]); });
  await page.evaluate(() => __f3d.E.runDialog('labels'));
  await page.waitForSelector('#labelsBody');
  const n0 = await page.textContent('#labelsInfo');
  ok('етикетки: виділене (2 ряди × 9 комірок) → 18 етикеток на 1 аркуші', n0.includes('Етикеток: 18') && n0.includes('аркушів: 1'), n0);
  ok('етикетки: перегляд аркуша SVG із штрихкодами', await page.evaluate(() => document.querySelectorAll('#labelsPreview svg path').length >= 18));
  // розкладки: 70×36 → 24 на аркуші; 105×48 → 12; 100×150 → 1
  // розкладки (24 і 12 на аркуші, 100×150) перевіряє тест ядра; тут — перемикання в діалозі
  await page.selectOption('#labelsBody select[aria-label="Розкладка"]', '105x48');
  const n1 = await page.textContent('#labelsInfo');
  ok('розкладка 105×48: 18 етикеток → 2 аркуші (12 на аркуші)', n1.includes('аркушів: 2'), n1);
  await page.selectOption('#labelsBody select[aria-label="Розкладка"]', '70x36');
  await page.fill('#labelsBody [data-s3="skip"]', '10');
  await page.waitForTimeout(80);
  ok('«Пропустити перші 10»: 18 етикеток займають 2 аркуші (24 на аркуші)', (await page.textContent('#labelsInfo')).includes('аркушів: 2'));
  await page.fill('#labelsBody [data-s3="skip"]', '0');
  // фільтри: усі нові (прототип: rid=null) → без змін; «застосовані в Odoo» → 0
  await page.check('#labelsBody [data-s3="onlyApplied"]');
  await page.waitForTimeout(80);
  ok('фільтр «Лише застосовані в Odoo»: нові місця не друкуються', (await page.textContent('#labelsInfo')).includes('Етикеток: 0'));
  await page.uncheck('#labelsBody [data-s3="onlyApplied"]');
  await page.check('#labelsBody [data-s3="onlyNew"]');
  await page.waitForTimeout(80);
  ok('фільтр «Лише нові та перенумеровані»: нові місця друкуються', (await page.textContent('#labelsInfo')).includes('Етикеток: 18'));
  await page.uncheck('#labelsBody [data-s3="onlyNew"]');
  // ярус знизу
  await page.selectOption('#labelsBody select[aria-label="Що друкувати"]', 'tier');
  await page.fill('#labelsBody [data-s3="tier"]', '2');
  await page.waitForTimeout(80);
  ok('«Ярус знизу» №2: по 3 комірки в кожному з двох рядів → 6', (await page.textContent('#labelsInfo')).includes('Етикеток: 6'));
  await page.selectOption('#labelsBody select[aria-label="Що друкувати"]', 'selected');
  // стрілка вгору для ярусів вище точки сканування
  await page.selectOption('#labelsBody select[aria-label="Стрілка"]', 'up');
  await page.fill('#labelsBody [data-s3="scanLevel"]', '2');
  await page.waitForTimeout(80);
  // ZPL: завантаження файла й вміст
  await page.selectOption('#labelsBody select[aria-label="Штрихкод"]', 'code128');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#btnLabelsZpl')]);
  const zplPath = path.join(DL, 'l.zpl');
  await dl.saveAs(zplPath);
  const zpl = fs.readFileSync(zplPath, 'utf8');
  ok('ZPL: 18 форматів ^XA…^XZ з ^BC і кодом комірки', (zpl.match(/\^XA/g) || []).length === 18 && zpl.includes('^BCN') && /\^FDRA-B01-L1\^FS/.test(zpl), zpl.slice(0, 160));
  ok('ZPL: стрілка (^GB/^GD) лише для ярусів вище точки сканування', (zpl.match(/\^GD/g) || []).length === 6, String((zpl.match(/\^GD/g) || []).length));
  // PNG
  const [dl2] = await Promise.all([page.waitForEvent('download'), page.click('#btnLabelsPng')]);
  const pngPath = path.join(DL, 'l.png');
  await dl2.saveAs(pngPath);
  const png = fs.readFileSync(pngPath);
  ok('PNG: аркуш етикеток (підпис PNG, ненульовий розмір)', png.slice(1, 4).toString() === 'PNG' && png.length > 5000, String(png.length));
  // PDF у прототипі: «на сервері» (кнопка неактивна з підказкою)
  const pdf = await page.evaluate(() => ({ dis: document.getElementById('btnLabelsPdf').disabled, title: document.getElementById('btnLabelsPdf').title }));
  ok('PDF: у прототипі кнопка неактивна, підказка «формує сервер»', pdf.dis && pdf.title.includes('сервер'), JSON.stringify(pdf));
  // QR: попередження про дрібний QR/не-ASCII
  await page.selectOption('#labelsBody select[aria-label="Штрихкод"]', 'qr');
  await page.waitForTimeout(80);
  const qrz = await page.evaluate(() => document.querySelectorAll('#labelsPreview svg path').length);
  ok('QR: перегляд малює QR-коди', qrz >= 18);
  await page.keyboard.press('Escape');
  ok('labels: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_heat(page, errors) {
  await prepare(page);
  const sel = await page.evaluate(() => [...document.querySelectorAll('#s3Metric option')].map((o) => o.value));
  ok('«Показник»: звичайний + 5 показників', sel.join() === ',fill,below_min,empty,abc,age', sel.join());
  const out = {};
  for (const m of ['fill', 'below_min', 'empty', 'abc', 'age']) {
    await page.selectOption('#s3Metric', m);
    await page.waitForTimeout(150);
    out[m] = await page.evaluate(() => ({ rows: [...document.querySelectorAll('#s3Heat .s3-heat-row')].map((r) => [r.dataset.class, +r.querySelector('.num').textContent]), demo: !!document.querySelector('#s3Heat .s3-demo'), total: __f3d.S.slots.reduce((n, s) => n + __f3d.cellsOf(s).filter((c) => !c.disabled).length, 0) }));
  }
  const sum = (m) => out[m].rows.reduce((n, r) => n + r[1], 0);
  ok('легенда: кількість місць у класах дорівнює числу комірок (усі 5 показників)', ['fill', 'below_min', 'empty', 'abc', 'age'].every((m) => sum(m) === out[m].total), JSON.stringify(Object.fromEntries(Object.keys(out).map((m) => [m, sum(m) + '/' + out[m].total]))));
  const cls = (m) => out[m].rows.map((r) => r[0]).filter((k) => k !== 'new').join();
  ok('заповненість: 6 класів (порожньо, до 25, 25–50, 50–75, >75, без ємності)', cls('fill') === 'empty,q1,q2,q3,q4,nocap');
  ok('нижче мінімуму: класи «запасу немає / нижче / не нижче / без правила»', cls('below_min') === 'none,below,ok,norule');
  ok('ABC: A+B+C рух; «Без руху»', cls('abc') === 'A,B,C,0' && out.abc.rows[0][1] > 0);
  ok('вік запасу: п’ять вікових класів і «Порожньо»', cls('age') === 'a30,a90,a180,a365,a999,none');
  ok('нові комірки (без даних Odoo) рахуються окремим рядком легенди', out.fill.rows.some((r) => r[0] === 'new' && r[1] === 28));
  ok('демо-значення мають позначку «демо» (F07-08)', out.abc.demo && out.age.demo);
  // ABC: частки руху A ≈ 80 %, B ≈ 15 %
  const abc = await page.evaluate(() => { const st = __f3d.S.stock; const tot = [...st.byCode.values()].reduce((s, v) => s + v.moves, 0); const by = { A: 0, B: 0, C: 0 }; for (const [c, v] of st.byCode) { const k = st.abc.get(c); if (by[k] != null) by[k] += v.moves; } return { A: by.A / tot, B: by.B / tot, C: by.C / tot }; });
  ok('ABC: A ≈ 80 %, B ≈ 15 %, C ≈ 5 % руху', abc.A >= 0.8 && abc.A < 0.9 && abc.B > 0.08 && abc.C < 0.1, JSON.stringify(abc));
  // нове (не опубліковане) місце лишає колір шару
  const keep = await page.evaluate(() => { const { S, E } = __f3d; const c = __f3d.cellsOf(S.sIdx.get('ra'))[0]; const m = __f3d.core.registries.metrics.get('fill'); return { stock: S.stock.byCode.has(c.code), color: m.color(c) }; });
  ok('нове (не опубліковане) місце не отримує кольору показника', keep.stock === false && keep.color === null, JSON.stringify(keep));
  // вибір запам'ятовується; «Оновити дані» змінює час знімка
  await page.selectOption('#s3Metric', 'fill');
  const stored = await page.evaluate(() => window.localStorage.getItem('f3d_constructor_metric'));
  ok('вибір показника запам’ятовується (localStorage)', stored === 'fill', String(stored));
  const at0 = await page.evaluate(() => __f3d.S.stock.at);
  await page.waitForTimeout(1100);
  await page.click('#s3Refresh');
  await page.waitForTimeout(250);
  ok('«Оновити дані» перечитує залишки без перебудови плану (час знімка змінився)', await page.evaluate((a) => __f3d.S.stock.at !== a && __f3d.S.stock.rev > 1, at0));
  await page.reload();
  await open(page);
  ok('після перезавантаження показник відновлено', await page.evaluate(() => __f3d.S.ui.metric === 'fill' && !!__f3d.S.stock));
  ok('heat: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_search(page, errors) {
  await page.evaluate(() => { __f3d.E.setView('plan'); });
  const code = await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.template === 'pallet_rack' && x.layer_id !== 'zz'); return { code: __f3d.cellsOf(s)[0].code, id: s.id, layer: s.layer_id }; });
  // нормалізація: без регістру й розділювачів
  const norm = code.code.toLowerCase().replace(/[^a-z0-9]/g, '');
  await page.keyboard.press('/');
  await page.waitForSelector('#s3Goto');
  ok('«/» відкриває пошук і ставить курсор у поле', await page.evaluate(() => document.activeElement && document.activeElement.id === 's3Goto'));
  await page.fill('#s3Goto', norm);
  await page.waitForSelector('#s3GotoList [data-code]');
  ok('підказки: код без розділювачів і регістру знаходить ' + code.code, await page.evaluate((c) => [...document.querySelectorAll('#s3GotoList [data-code]')].some((b) => b.dataset.code === c), code.code));
  await page.press('#s3Goto', 'Enter');
  await page.waitForTimeout(250);
  const g = await page.evaluate(() => ({ sel: __f3d.S.sel && __f3d.S.sel.id, cell: __f3d.S.selCell, layer: __f3d.S.ui.layer, tgt: __f3d.E.camTarget() }));
  ok('Enter переходить до комірки: виділено місце й комірку, шар активний', g.sel === code.id && g.cell === code.code && g.layer === code.layer, JSON.stringify(g));
  const near = await page.evaluate((id) => { const s = __f3d.S.sIdx.get(id); const t = __f3d.E.camTarget(); return Math.hypot(t.x - s.x, t.y - s.y) < 25; }, code.id);
  ok('камера наїхала на місце', near);
  ok('картка місця в правій панелі з кодом комірки', (await page.textContent('#cardBlock')).includes(code.code));
  // кілька збігів — список
  await page.fill('#s3Goto', 'B01');
  await page.waitForTimeout(100);
  ok('кілька збігів — список підказок (до 8) із приміткою «ще»', await page.evaluate(() => document.querySelectorAll('#s3GotoList [data-code]').length === 8 && /ще \d+/.test(document.getElementById('s3GotoList').textContent)));
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(120);
  ok('Ctrl+K відкриває пошук', await page.evaluate(() => document.activeElement && document.activeElement.id === 's3Goto'));
  // «Де лежить»: вміст за товаром
  await page.fill('#s3Find', 'дсп білий');
  await page.press('#s3Find', 'Enter');
  await page.waitForSelector('#s3FindList [data-code]');
  const f = await page.evaluate(() => ({ info: document.getElementById('s3FindInfo').textContent, n: document.querySelectorAll('#s3FindList [data-code]').length, hl: __f3d.S.hl && __f3d.S.hl.codes.size }));
  ok('«Де лежить»: лічильник, список «місце + що лежить» і підсвітка', /Знайдено місць: \d+/.test(f.info) && f.n > 0 && f.hl === +f.info.match(/\d+/)[0], JSON.stringify(f));
  ok('підсвітка: кольорові комірки результатів у сцені', await page.evaluate(() => { const v = [...__f3d.V.views.values()].find((x) => x.cells && x.cellList.some((c) => __f3d.S.hl.codes.has(c.code))); return !!v; }));
  const one = await page.evaluate(() => { const hit = document.querySelector('#s3FindList [data-code]'); return hit.dataset.code; });
  await page.click('#s3FindList [data-code]');
  await page.waitForTimeout(200);
  ok('клік по результату переходить до комірки', await page.evaluate((c) => __f3d.S.selCell === c, one));
  await page.fill('#s3Find', 'zzzzzz');
  await page.press('#s3Find', 'Enter');
  await page.waitForTimeout(250);
  ok('порожній результат: 0 місць', (await page.textContent('#s3FindInfo')).includes('Знайдено місць: 0'));
  ok('search: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_card(page, errors) {
  await prepare(page);
  await page.evaluate(() => { __f3d.S.slots.find((s) => s.id === 'ra').rid = 1; });
  await page.evaluate(() => __f3d.E.setView('plan'));
  await page.waitForTimeout(250);
  const p = await page.evaluate(() => { const { S, V, core } = __f3d; const s = S.sIdx.get('ra'); const cell = __f3d.cellsOf(s)[0]; const r = V.canvas.getBoundingClientRect(); const w = { x: s.x + cell.lx, y: s.y + cell.ly }; const v = new core.THREE.Vector3(w.x, 0.5, -w.y).project(V.camera); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height }; });
  // підказка при наведенні (F06-05)
  await page.mouse.move(p.x - 20, p.y - 20);
  await page.mouse.move(p.x, p.y, { steps: 3 });
  await page.waitForTimeout(250);
  const tip = await page.evaluate(() => { const t = document.getElementById('s3Tip'); return { vis: !t.hidden, text: t.textContent }; });
  ok('підказка при наведенні: код комірки', tip.vis && tip.text.includes('RA-B0'), JSON.stringify(tip));
  await page.mouse.click(p.x, p.y);
  await page.waitForSelector('#cardBlock #s3Card');
  const card = await page.textContent('#cardBlock');
  const c0 = await page.evaluate(() => __f3d.S.selCell);
  ok('картка: код вибраної комірки, ємність і категорія', /^RA-B0\d-L\d$/.test(c0) && card.includes(c0) && card.includes('Місць') && card.includes('Категорія'), card.slice(0, 100));
  await page.evaluate(() => __f3d.E.setMetric('fill'));
  await page.evaluate((c) => __f3d.S.stock.byCode.set(c, { qty: 12, reserved: 2, fill: 0.5, age_days: 40, moves: 4, min: 5, max: 30, detail: { rows: [{ product: 'Плита ДСП', qty: 12, reserved: 2, lot: 'L-1', age_days: 40 }], moves: [{ date: '2026-09-01', product: 'Плита ДСП', qty: 3, from: 'WH/Stock', to: c }], rules: ['Плити → склад плит'], record: { model: 'stock.location', id: 77 } } }), c0);
  await page.evaluate(() => __f3d.E.renderRight());
  const card2 = await page.textContent('#cardBlock');
  ok('картка: залишки (товар, к-сть, резерв, партія, вік), min/max, правила, рух', ['Плита ДСП', '12 / 2', '5 / 30', 'L-1', '40 дн.', 'Плити → склад плит', '2026-09-01'].every((t) => card2.includes(t)), card2.slice(0, 300));
  ok('картка: заповненість 50 %', card2.includes('Заповненість: 50 %'));
  ok('картка: «Відкрити в Odoo» є, коли сервер віддав record і хост вміє відкривати записи', await page.evaluate(() => !!document.getElementById('btnOpenOdoo') === __f3d.core.registries.dialogs.has('record')));
  ok('card: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_mobile(page, errors) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);
  const w = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, app: document.getElementById('app').scrollWidth, inner: window.innerWidth, mode: __f3d.S.app.mode, mobile: __f3d.E.isMobile() }));
  ok('мобільний режим: ≤ 768 px, без горизонтальної прокрутки (390 px)', w.mobile && w.doc <= 390 && w.app <= 390, JSON.stringify(w));
  ok('мобільний режим: правка вимкнена (режим «Перегляд»)', w.mode === 'view');
  const ui = await page.evaluate(() => { const vis = (id) => { const e = document.getElementById(id); if (!e) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; }; return { burger: vis('s3Burger'), search: vis('s3mSearch'), objbtn: vis('s3ObjBtn'), left: vis('left'), right: vis('right'), mtabs: vis('mtabs'), modeSeg: vis('modeSeg'), publish: vis('btnPublish') }; });
  ok('мобільний режим: ☰, пошук зверху, «Панель об’єкта»; панелі згорнуті, правка й публікація сховані', ui.burger && ui.search && ui.objbtn && !ui.left && !ui.right && !ui.mtabs && !ui.modeSeg && !ui.publish, JSON.stringify(ui));
  await page.click('#s3Burger');
  await page.waitForTimeout(150);
  const open = await page.evaluate(() => { const r = document.getElementById('left').getBoundingClientRect(); return { w: Math.round(r.width), vis: r.width > 0, doc: document.documentElement.scrollWidth }; });
  ok('☰ відкриває ліву панель (≤ 88 % ширини) без прокрутки', open.vis && open.w <= 345 && open.doc <= 390, JSON.stringify(open));
  await page.click('#s3Burger');
  // пошук зверху: код → картка на весь екран
  const code = await page.evaluate(() => __f3d.cellsOf(__f3d.S.slots.find((s) => s.template === 'pallet_rack'))[0].code);
  await page.fill('#s3mSearch', code.toLowerCase().replace(/[^a-z0-9]/g, ''));
  await page.press('#s3mSearch', 'Enter');
  await page.waitForSelector('#s3CardOv:not([hidden])');
  const cov = await page.evaluate((c) => { const r = document.getElementById('s3CardOv').getBoundingClientRect(); return { w: r.width, h: r.height, text: document.getElementById('s3CardBody').textContent.includes(c) }; }, code);
  ok('пошук зверху: Enter → картка комірки на весь екран', cov.w >= 389 && cov.h >= 840 && cov.text, JSON.stringify(cov));
  await page.click('#s3CardClose');
  // редагування вимкнене: перетягування не рухає об'єкт
  const sid = await page.evaluate(() => __f3d.S.sel.id);
  const before = await page.evaluate((id) => [__f3d.S.sIdx.get(id).x, __f3d.S.sIdx.get(id).y], sid);
  const pt = await page.evaluate((id) => { const { S, V, core } = __f3d; const s = S.sIdx.get(id); const r = V.canvas.getBoundingClientRect(); const v = new core.THREE.Vector3(s.x, 0.5, -s.y).project(V.camera); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height }; }, sid);
  await page.mouse.move(pt.x, pt.y);
  await page.mouse.down();
  await page.mouse.move(pt.x + 25, pt.y + 25, { steps: 3 });
  await page.mouse.up();
  const after = await page.evaluate((id) => [__f3d.S.sIdx.get(id).x, __f3d.S.sIdx.get(id).y], sid);
  ok('мобільний режим: перетягування не змінює положення', before[0] === after[0] && before[1] === after[1]);
  // «Панель об'єкта» висувається
  await page.click('#s3ObjBtn');
  await page.waitForTimeout(150);
  const right = await page.evaluate(() => { const r = document.getElementById('right').getBoundingClientRect(); return { vis: r.width > 0, w: Math.round(r.width), doc: document.documentElement.scrollWidth }; });
  ok('«Панель об’єкта» висувається справа без прокрутки', right.vis && right.w <= 345 && right.doc <= 390, JSON.stringify(right));
  await page.click('#s3ObjBtn');
  await page.screenshot({ path: path.join(DL, 'mobile.png') });
  // повернення на ПК відновлює режим редагування
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(400);
  ok('повернення на ПК відновлює «Редагування» й панелі', await page.evaluate(() => __f3d.S.app.mode === 'edit' && !__f3d.E.isMobile() && document.getElementById('left').getBoundingClientRect().width > 100));
  ok('mobile: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_save(page, errors) {
  await prepare(page);
  // N-05: бірюзові «не збережено» до запису, «Зберегти все» знімає
  await page.evaluate(() => { __f3d.adapter.autosaveMs = 60000; const s = __f3d.S.sIdx.get('ra'); s.x += 1; __f3d.E.commit({}); });
  await page.waitForTimeout(250);
  const u = await page.evaluate(() => ({ unsaved: __f3d.S.unsaved.has('s:ra'), saveAll: !document.getElementById('menu-saveAll').disabled }));
  ok('N-05: змінений об’єкт позначено «не збережено», «Зберегти все» активна', u.unsaved && u.saveAll, JSON.stringify(u));
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'ra' }));
  ok('N-08: статус об’єкта «не збережено» у правій панелі', (await page.textContent('#statusBlock')).includes('не збережено'));
  await page.evaluate(() => document.getElementById('menu-saveAll').click());
  await page.waitForTimeout(500);
  ok('«Зберегти все» записує чергу: позначок немає', await page.evaluate(() => __f3d.S.unsaved.size === 0));
  ok('N-08: статус після збереження — «нове · лише в моделі»', (await page.evaluate(() => { __f3d.E.renderRight(); return document.getElementById('statusBlock').textContent; })).includes('нове · лише в моделі'));
  // «Скинути до даних Odoo»: повертає чернетку до активної версії
  const reset = await page.evaluate(() => { const m = __f3d.core.registries.menu.get('resetToOdoo'); return { has: !!__f3d.S.site.active_version, dis: m.disabled() }; });
  ok('«Скинути до даних Odoo» доступне при опублікованій версії', reset.has && !reset.dis, JSON.stringify(reset));
  await page.evaluate(() => { __f3d.core.registries.menu.get('resetToOdoo').run(); });
  await page.waitForSelector('#dlgYes');
  await page.click('#dlgYes');
  await page.waitForTimeout(700);
  ok('після скидання: площадка перезавантажена з версії, історія очищена', await page.evaluate(() => __f3d.S.hist.stack.length === 1 && __f3d.S.slots.length > 100));
  // N-02: рівні доступу
  await page.evaluate(() => { __f3d.S.rights = { ...__f3d.S.rights, is_manager: false, roles: [], can_publish: false }; __f3d.E.renderAll(); });
  const acc = await page.evaluate(() => ({ a: __f3d.E.access(), tag: document.getElementById('s3Access').textContent, pub: document.getElementById('btnPublish').disabled, pubTitle: document.getElementById('btnPublish').title }));
  ok('N-02: користувач лише «Перегляд» — мітка рівня, публікація неактивна з підказкою', acc.a.level === 'view' && acc.tag === 'Перегляд' && acc.pub && acc.pubTitle.length > 5, JSON.stringify(acc));
  await page.evaluate(() => { __f3d.S.rights = { ...__f3d.S.rights, roles: ['technologist'] }; __f3d.E.renderAll(); });
  ok('N-02: роль-проєктувальник → «Проєктування»', await page.evaluate(() => __f3d.E.access().level === 'design' && document.getElementById('s3Access').textContent === 'Проєктування'));
  await page.evaluate(() => { __f3d.S.rights = { ...__f3d.S.rights, is_manager: true, roles: ['manager'], can_publish: true }; __f3d.E.renderAll(); });
  ok('N-02: менеджер → «Застосування»', await page.evaluate(() => __f3d.E.access().level === 'apply' && document.getElementById('s3Access').textContent === 'Застосування'));
  // N-08: довідка гарячих клавіш
  await page.evaluate(() => __f3d.E.runDialog('hotkeys'));
  await page.waitForSelector('#hotkeysTable');
  const hk = await page.textContent('#hotkeysTable');
  ok('N-08: «Гарячі клавіші» перелічують Ctrl+Z, Ctrl+D, Ctrl+K, «/»', ['Ctrl+Z', 'Ctrl+D', 'Ctrl+K', 'Ctrl+C'].every((k) => hk.includes(k)), hk.slice(0, 200));
  await page.keyboard.press('Escape');
  ok('save: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

(async () => {
  const suites = { undo: t_undo, multi: t_multi, tools: t_tools, align: t_align, labels: t_labels, heat: t_heat, search: t_search, card: t_card, mobile: t_mobile, save: t_save };
  const only = process.argv[2];
  for (const [name, fn] of Object.entries(suites)) {
    if (only && only !== name) continue;
    const { browser, page, errors } = await launch({ viewport: { width: 1440, height: 900 } });
    try { await open(page); await fn(page, errors); } catch (e) { ok(name + ': виняток ' + e.message, false, (e.stack || '').split('\n').slice(0, 4).join(' | ')); }
    await browser.close();
  }
  const bad = res.filter((x) => !x).length;
  console.log(`\nІТОГО S3 прототип: ${res.length - bad} passed, ${bad} failed`);
  process.exit(bad ? 1 : 0);
})();
