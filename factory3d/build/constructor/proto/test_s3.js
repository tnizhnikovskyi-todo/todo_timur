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
  await page.waitForTimeout(200);
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
  await page.waitForTimeout(150);
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

(async () => {
  const suites = { undo: t_undo, multi: t_multi, tools: t_tools, align: t_align };
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
