// Слайс S5 «Будівля, майстер, документи» у прототипі: режим «Будівля» (F18: контур, колони, стіни, проходи, прив'язка, лінійки, 3D, перевірки,
// техніка N-06), скасування правок будівлі, мастер «З нуля» (F16), документи (F15: специфікація стелажів і план).
// Запуск: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node build/constructor/proto/test_s5.js (після python3 build/constructor/proto/build.py)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { launch, open } = require('./harness');
const res = [];
const ok = (name, cond, extra) => { res.push(!!cond); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra !== undefined && !cond ? ' :: ' + extra : '')); };
const DL = fs.mkdtempSync(path.join(os.tmpdir(), 's5dl-'));

/** Нова порожня площадка 60×30×8: п'ять базових шарів, чистий стан. */
async function blank(page, name = 'S5') {
  const made = await page.evaluate(async (name) => {
    const { E, S } = __f3d;
    const done = await E.createSite({ name, code: name.toUpperCase(), building: { l: 60, w: 30, h: 8 } });
    await new Promise((r) => setTimeout(r, 300));
    E.setView('plan');
    return done && S.site.name === name;
  }, name);
  ok('нова площадка ' + name + ' створена', made);
}
const flush = async (page) => { await page.evaluate(() => __f3d.E.flushNow()); await page.waitForTimeout(80); };
/** Екранні координати світової точки (x, y) активного шару. */
const screenOf = (page, x, y) => page.evaluate(([x, y]) => {
  const { V, core } = __f3d;
  const r = V.canvas.getBoundingClientRect();
  const v = new core.THREE.Vector3(x, 0, -y).project(V.camera);
  return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };
}, [x, y]);
const clickWorld = async (page, x, y, opts = {}) => {
  const p = await screenOf(page, x, y);
  await page.mouse.move(p.x, p.y);
  await page.mouse.down();
  await page.mouse.up();
  if (opts.wait !== 0) await page.waitForTimeout(opts.wait || 60);
};
const bl = (page) => page.evaluate(() => { const l = __f3d.S.layers.find((x) => x.kind === 'building'); return { items: l.items.length, kinds: l.items.map((i) => i.kind), bounds: l.bounds, aisles: l.aisles.length }; });

async function t_mode(page, errors) {
  await blank(page);
  const r0 = await page.evaluate(() => ({ btn: !!document.getElementById('btnBuildingMode'), tab: !!document.querySelector('#ltabs button[data-tab="building"]'), edit: document.querySelector('#modeSeg button[data-mode="edit"]').getAttribute('aria-pressed') }));
  ok('кнопка «Будівля» поруч із 3D/План і вкладка «Будівля»', r0.btn && r0.tab && r0.edit === 'true', JSON.stringify(r0));
  await page.click('#btnBuildingMode');
  await page.waitForTimeout(250);
  const r1 = await page.evaluate(() => ({ on: __f3d.E.buildingState.on, pressed: document.getElementById('btnBuildingMode').getAttribute('aria-pressed'), edit: document.querySelector('#modeSeg button[data-mode="edit"]').getAttribute('aria-pressed'), tab: __f3d.S.ui.leftTab, cam: __f3d.V.camMode, rulers: !!document.getElementById('b5Rx'), tools: document.querySelectorAll('#b5Tools button').length, layer: __f3d.S.layers.find((l) => l.id === __f3d.S.ui.layer).kind }));
  ok('режим «Будівля» увімкнено: «Редагувати» знято, вкладка, «План», лінійки, 8 інструментів, активний шар «Будівля»', r1.on && r1.pressed === 'true' && r1.edit === 'false' && r1.tab === 'building' && r1.cam === 'plan' && r1.rulers && r1.tools === 8 && r1.layer === 'building', JSON.stringify(r1));
  await page.click('#modeSeg button[data-mode="edit"]');
  await page.waitForTimeout(200);
  const r2 = await page.evaluate(() => ({ on: __f3d.E.buildingState.on, edit: document.querySelector('#modeSeg button[data-mode="edit"]').getAttribute('aria-pressed'), rulers: !!document.getElementById('b5Rx'), tab: __f3d.S.ui.leftTab }));
  ok('«Редагувати» виводить із режиму «Будівля»', !r2.on && r2.edit === 'true' && !r2.rulers && r2.tab !== 'building', JSON.stringify(r2));
}

async function t_contour(page, errors) {
  await blank(page, 'S5C');
  await page.evaluate(() => {
    const { S, E } = __f3d;
    const ly = S.layers.find((l) => l.kind === 'storage');
    if (!ly.slot_types.includes('pallet_rack')) ly.slot_types.push('pallet_rack');
    S.slots.push({ id: 'k1', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'K1', x: 20, y: 10, rotation: 0, params: { bays: 3, levels: 3, bay_width: 2.7, depth: 1.1, level_height: 1.5 }, overrides: {}, parent_location_id: null });
    S.slots.push({ id: 'k2', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'K2', x: 30, y: 18, rotation: 0, params: { bays: 3, levels: 3, bay_width: 2.7, depth: 1.1, level_height: 1.5 }, overrides: {}, parent_location_id: null });
    E.commit({});
    E.undoReset();
  });
  await page.click('#btnBuildingMode');
  await page.waitForTimeout(200);
  await page.click('#btnContourAuto');
  await page.waitForTimeout(250);
  const c = await page.evaluate(() => ({ b: __f3d.S.layers.find((l) => l.kind === 'building').bounds, area: document.getElementById('b5Area').textContent, verts: document.querySelectorAll('#b5Verts .b5-vrow').length }));
  // K1: x 15.95…24.05, y 9.45…10.55; K2: x 25.95…34.05, y 17.45…18.55 → охоплення + 2 м
  ok('«За складом (+2 м)»: контур-прямокутник з відступом 2 м, площа й периметр', c.b && c.b.length === 4 && c.b[0][0] === 13.95 && c.b[2][0] === 36.05 && c.b[0][1] === 7.45 && c.b[2][1] === 20.55 && /Площа/.test(c.area) && c.verts === 4, JSON.stringify(c));
  // додати вершину через кнопку, перетягнути, видалити
  await page.click('#btnVertexPlus');
  await page.waitForTimeout(150);
  const v = await page.evaluate(() => ({ n: __f3d.S.layers.find((l) => l.kind === 'building').bounds.length, sel: __f3d.E.buildingState.sel }));
  ok('«+ Вершина» додає вершину (5) після останньої, вона виділена', v.n === 5 && v.sel && v.sel.kind === 'vertex' && v.sel.index === 4, JSON.stringify(v));
  const p0 = await screenOf(page, 13.95, 7.45);
  const target = await screenOf(page, 12, 5);
  await page.mouse.move(p0.x, p0.y);
  await page.mouse.down();
  await page.mouse.move((p0.x + target.x) / 2, (p0.y + target.y) / 2, { steps: 4 });
  await page.mouse.move(target.x, target.y, { steps: 4 });
  await page.mouse.up();
  await page.waitForTimeout(150);
  const d = await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').bounds[0]);
  ok('вершину контуру можна перетягнути (прив\'язка до сітки 0,5)', Math.abs(d[0] - 12) < 0.6 && Math.abs(d[1] - 5) < 0.6, JSON.stringify(d));
  await page.keyboard.press('Delete');
  await page.waitForTimeout(100);
  const del = await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').bounds.length);
  ok('Delete видаляє виділену вершину (мінімум 3)', del === 4, String(del));
  // скасування: Ctrl+Z повертає вершину
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(200);
  ok('Ctrl+Z скасовує видалення вершини', (await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').bounds.length)) === 5);
}

async function t_items(page, errors) {
  await blank(page, 'S5I');
  await page.click('#btnBuildingMode');
  await page.waitForTimeout(200);
  await page.click('#tool-column');
  await clickWorld(page, 10, 10);
  await page.keyboard.press('Escape');
  const a = await bl(page);
  ok('інструмент «Колона»: клац створює колону К-1 на сітці', a.items === 1 && a.kinds[0] === 'column', JSON.stringify(a));
  const nm = await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').items[0]);
  ok('колона: прив\'язка до сітки 0,5 м і ім\'я К-1', nm.x === 10 && nm.y === 10 && nm.name === 'К-1' && nm.w === 0.4, JSON.stringify(nm));
  // стіна: два кліки
  await page.click('#tool-wall');
  await clickWorld(page, 20, 5);
  await clickWorld(page, 30, 5);
  await page.keyboard.press('Escape');
  const w = await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').items.find((i) => i.kind === 'wall'));
  ok('«Стіна»: відрізок із двох кліків (довжина 10, товщина 0,2, кут 0)', w && w.w === 10 && w.th === 0.2 && w.rot === 0 && w.x === 25 && w.y === 5, JSON.stringify(w));
  // прохід: два кліки
  await page.click('#tool-aisle');
  await clickWorld(page, 5, 20);
  await clickWorld(page, 25, 20);
  await page.keyboard.press('Escape');
  const ai = await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').aisles);
  ok('«Прохід»: осьовий прямокутник завширшки з шару', ai.length === 1 && ai[0].x0 === 5 && ai[0].x1 === 25 && ai[0].y1 - ai[0].y0 > 2.4, JSON.stringify(ai));
  // колони сіткою
  await page.click('#btnColumnGrid');
  await page.waitForSelector('#dlgColumnGrid');
  await page.click('#dlgColumnGrid');
  await page.waitForTimeout(250);
  const g = await bl(page);
  ok('«Колони сіткою» додають колони за кроком площадки', g.items > 5 && g.kinds.filter((k) => k === 'column').length > 4, JSON.stringify(g));
  // виділення клацом і видалення
  await page.evaluate(() => { __f3d.E.buildingState.sel = null; });
  await clickWorld(page, 25, 5);
  const sel = await page.evaluate(() => __f3d.E.buildingState.sel);
  ok('клац по об\'єкту виділяє його (стіна)', sel && sel.kind === 'item', JSON.stringify(sel));
  await page.keyboard.press('Delete');
  await page.waitForTimeout(150);
  const after = await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').items.some((i) => i.kind === 'wall'));
  ok('Delete видаляє виділену стіну', !after);
  // undo: усі правки будівлі відкочуються
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(250);
  const u1 = await page.evaluate(() => __f3d.S.layers.find((l) => l.kind === 'building').items.some((i) => i.kind === 'wall'));
  ok('Ctrl+Z повертає видалену стіну', u1);
  for (let i = 0; i < 8; i++) { await page.keyboard.press('Control+z'); await page.waitForTimeout(120); }
  const u2 = await bl(page);
  ok('кілька Ctrl+Z скасовують усі правки будівлі (колони, стіна, прохід)', u2.items === 0 && u2.aisles === 0, JSON.stringify(u2));
  await page.keyboard.press('Control+Shift+Z');
  await page.waitForTimeout(200);
  ok('Ctrl+Shift+Z повторює (колона К-1)', (await bl(page)).items === 1);
}

async function t_checks(page, errors) {
  await blank(page, 'S5K');
  await page.evaluate(() => {
    const { S, E } = __f3d;
    const ly = S.layers.find((l) => l.kind === 'storage');
    if (!ly.slot_types.includes('pallet_rack')) ly.slot_types.push('pallet_rack');
    const rack = { bays: 3, levels: 3, bay_width: 2.7, depth: 1.1, level_height: 1.5 };
    S.slots.push({ id: 'c1', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'IN-1', x: 10, y: 10, rotation: 0, params: { ...rack }, overrides: {}, parent_location_id: null });
    S.slots.push({ id: 'c2', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'COL-1', x: 30, y: 10, rotation: 0, params: { ...rack }, overrides: {}, parent_location_id: null });
    S.slots.push({ id: 'c3', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'ROW-A', x: 10, y: 20, rotation: 0, params: { ...rack }, overrides: {}, parent_location_id: null });
    S.slots.push({ id: 'c4', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'ROW-B', x: 10, y: 22.4, rotation: 0, params: { ...rack }, overrides: {}, parent_location_id: null });
    E.commit({});
    E.undoReset();
  });
  await page.click('#btnBuildingMode');
  await page.waitForTimeout(200);
  // контур 0…40 × 0…25 (L-подібний виріз у правому верхньому куті), колона в стелажі COL-1
  await page.evaluate(() => {
    const { S, E } = __f3d;
    const ly = S.layers.find((l) => l.kind === 'building');
    ly.bounds = [[0, 0], [40, 0], [40, 12], [25, 12], [25, 30], [0, 30]];
    ly.items.push({ id: 'col', kind: 'column', name: 'К-1', x: 30, y: 10, w: 0.4, d: 0.4, rot: 0, location_uid: null });
    S.site.aisle_tech = 'reach';
    S.site.sprinkler_height = 4.5;
    E.commit({});
    E.renderAll();
  });
  // вмикаємо перевірки з панелі
  for (const id of ['inside', 'aisle_width', 'height']) {
    await page.click(`#b5Tools ~ * [data-check="${id}"], [data-check="${id}"]`);
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(250);
  const iss = await page.evaluate(() => __f3d.S.issues.list.filter((i) => ['inside', 'aisle_width', 'height'].includes(i.check)).map((i) => i.check + ':' + i.codes.join('+')));
  ok('inside: стелаж поза контуром і в колоні', iss.includes('inside:COL-1'), JSON.stringify(iss));
  ok('aisle_width: вузький проїзд між рядами ROW-A і ROW-B (ричтрак ≥ 2,8 м)', iss.includes('aisle_width:ROW-A+ROW-B'), JSON.stringify(iss));
  ok('height: стелаж 4,75 м ближче 0,5 м до спринклерів (4,5 м)', iss.includes('height:IN-1'), JSON.stringify(iss));
  const panel = await page.evaluate(() => document.getElementById('b5Issues')?.textContent || '');
  ok('панель «Перевірки будівлі» показує зауваження', /колон|контур|проїзд|спринклер/.test(panel), panel.slice(0, 120));
  // техніка складу: «Ручний візок» знімає зауваження про проїзд
  await page.evaluate(() => { const { S, E } = __f3d; S.site.aisle_tech = 'hand'; E.commit({}); });
  await page.waitForTimeout(200);
  const iss2 = await page.evaluate(() => __f3d.S.issues.list.filter((i) => i.check === 'aisle_width').length);
  ok('техніка «Ручний візок» (1,2 м) знімає зауваження про вузький проїзд', iss2 === 0, String(iss2));
}

async function t_3d(page, errors) {
  const g = await page.evaluate(() => {
    const { V, S } = __f3d;
    if (!V.bld5 || !V.bld5.g) return { ok: false };
    const kinds = [];
    V.bld5.g.traverse((o) => { if (o.isInstancedMesh) kinds.push('instanced:' + o.count); else if (o.isLineLoop) kinds.push('loop'); });
    return { ok: true, kinds, children: V.bld5.g.children.length };
  });
  ok('3D будівлі: група зі стінами/контуром і лінією спринклерів у сцені', g.ok && g.kinds.filter((k) => k === 'loop').length >= 3, JSON.stringify(g));
}


async function t_wizard(page, errors) {
  await blank(page, 'S5W');
  await page.evaluate(() => __f3d.E.setLeftTab('wizard'));
  await page.click('#btnWizStart');
  await page.waitForSelector('#wizSteps');
  const s0 = await page.evaluate(() => ({ steps: document.querySelectorAll('#wizSteps button').length, step: __f3d.S.site.wizard_state.step }));
  ok('майстер: 6 кроків, початок на кроці «Будівля»', s0.steps === 6 && s0.step === 0, JSON.stringify(s0));
  // крок 1: застосувати (контур 60×30, колони сіткою 6×6, стіни по контуру)
  await page.click('[data-w="walls"]');
  await page.click('#btnWizApply');
  await page.waitForTimeout(250);
  const b = await page.evaluate(() => { const l = __f3d.S.layers.find((x) => x.kind === 'building'); return { bounds: l.bounds, cols: l.items.filter((i) => i.kind === 'column').length, walls: l.items.filter((i) => i.kind === 'wall').length, created: __f3d.S.site.wizard_state.created.items.length }; });
  ok('крок «Будівля»: контур-прямокутник, колони сіткою (9×4), 4 стіни, створене записано у стан', b.bounds && b.bounds.length === 4 && b.cols === 36 && b.walls === 4 && b.created === 40, JSON.stringify(b));
  // повторне «Застосувати» заміщує створене кроком, а не дублює
  await page.click('#btnWizApply');
  await page.waitForTimeout(200);
  ok('повторне «Застосувати» замінює створене (без дублів)', (await page.evaluate(() => __f3d.S.layers.find((x) => x.kind === 'building').items.length)) === 40);
  // крок 2: зони рівно
  await page.click('#btnWizNext');
  await page.waitForTimeout(150);
  await page.click('#btnWizEven');
  await page.waitForTimeout(150);
  const zf = await page.evaluate(() => __f3d.S.site.wizard_state.form.zones.length);
  ok('«Розкласти рівно»: дві зони у формі', zf === 2, String(zf));
  await page.click('#btnWizApply');
  await page.waitForTimeout(250);
  const z = await page.evaluate(() => ({ zones: __f3d.S.slots.filter((s) => s.template === 'zone').length, fn: __f3d.S.slots.filter((s) => s.template === 'zone').map((s) => s.function_id) }));
  ok('крок «Зони»: створено дві зони з функцією', z.zones === 2 && z.fn.every((f) => f != null), JSON.stringify(z));
  // крок 3: ряди
  await page.click('#btnWizNext');
  await page.waitForTimeout(150);
  await page.click('#btnWizApply');
  await page.waitForTimeout(300);
  const r = await page.evaluate(() => ({ racks: __f3d.S.slots.filter((s) => s.template === 'pallet_rack').length, created: __f3d.S.site.wizard_state.created.rows.length }));
  ok('крок «Ряди»: створено ряди в обох зонах', r.racks >= 4 && r.racks === r.created, JSON.stringify(r));
  // undo/redo правки майстра: один крок скасування = «Застосувати» кроку
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(300);
  const u = await page.evaluate(() => __f3d.S.slots.filter((s) => s.template === 'pallet_rack').length);
  ok('Ctrl+Z скасовує крок «Ряди» (рядів немає)', u === 0, String(u));
  await page.keyboard.press('Control+Shift+Z');
  await page.waitForTimeout(300);
  ok('Ctrl+Shift+Z повертає ряди кроку', (await page.evaluate(() => __f3d.S.slots.filter((s) => s.template === 'pallet_rack').length)) === r.racks);
  await page.click('#btnWizApply');
  await page.waitForTimeout(250);
  ok('повторне «Застосувати» рядів замінює створене (без дублів)', (await page.evaluate(() => __f3d.S.slots.filter((s) => s.template === 'pallet_rack').length)) === r.racks);
  // крок 4–6
  await page.click('#btnWizNext');
  await page.waitForSelector('#addrSite');
  ok('крок «Адресація»: блок адресації площадки', true);
  await page.click('#btnWizNext');
  await page.waitForSelector('#wizIssues');
  const nextOk = await page.evaluate(() => document.getElementById('btnWizNext').disabled);
  ok('крок «Перевірки»: без помилок «Далі» відкрито', nextOk === false);
  // помилка (заборона): стелаж поза будівлею закриває «Далі»
  await page.evaluate(() => {
    const { S, E } = __f3d;
    const ly = S.layers.find((l) => l.kind === 'storage');
    S.slots.push({ id: 'out', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'OUT', x: 200, y: 200, rotation: 0, params: { bays: 3, levels: 3, bay_width: 2.7, depth: 1.1, level_height: 1.5 }, overrides: {}, parent_location_id: null });
    E.commit({});
    E.renderAll();
  });
  await page.waitForTimeout(200);
  const blocked = await page.evaluate(() => ({ dis: document.getElementById('btnWizNext').disabled, txt: document.getElementById('wizIssues').textContent }));
  ok('при помилці перевірки «Далі» закрито', blocked.dis === true && /Помилок/.test(blocked.txt), JSON.stringify(blocked));
  await page.evaluate(() => { const { S, E } = __f3d; S.slots = S.slots.filter((s) => s.id !== 'out'); E.commit({}); E.renderAll(); });
  await page.waitForTimeout(200);
  await page.click('#btnWizNext');
  await page.waitForSelector('#wizSummary');
  const sm = await page.evaluate(() => document.getElementById('wizSummary').textContent + '|' + !!document.getElementById('btnWizPublish'));
  ok('крок «План змін»: зведення створеного, кнопки застосування', /зон 2/.test(sm) && /true$/.test(sm), sm);
  await page.click('#btnWizFinish');
  await page.waitForTimeout(150);
  ok('«Завершити майстер»: стан позначено завершеним, вкладка «Шари»', await page.evaluate(() => __f3d.S.site.wizard_state.done === true && __f3d.S.ui.leftTab === 'layers'));
  // стан переживає перезавантаження
  await flush(page);
  await page.waitForTimeout(900);
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
  await page.waitForTimeout(800);
  const st = await page.evaluate(() => ({ name: __f3d.S.site.name, done: __f3d.S.site.wizard_state && __f3d.S.site.wizard_state.done, zones: __f3d.S.site.wizard_state && __f3d.S.site.wizard_state.created.zones.length }));
  ok('стан майстра зберігається в проєкті (після перезавантаження)', st.name === 'S5W' && st.done === true && st.zones === 2, JSON.stringify(st));
}

async function t_docs(page, errors) {
  // специфікація (на площадці майстра є ряди)
  await page.evaluate(() => __f3d.E.runDialog('spec'));
  await page.waitForSelector('#specTable table');
  const sp = await page.evaluate(() => ({ sum: document.getElementById('specSummary').textContent, rows: document.querySelectorAll('#specTable tbody tr').length, scopes: document.querySelectorAll('#specBody select')[0].options.length }));
  ok('специфікація: підсумок і таблиця за типорозмірами, області (склад і зони)', /Стелажів: \d+/.test(sp.sum) && sp.rows > 0 && sp.scopes >= 3, JSON.stringify(sp));
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#btnSpecCsv')]);
  const csv = fs.readFileSync(await dl.path(), 'utf8');
  ok('специфікація: CSV з BOM, роздільник «;», рядки «Рама», «Балка»', csv.startsWith('﻿') && csv.includes(';') && /Рама/.test(csv) && /Балка/.test(csv), csv.slice(0, 100));
  await page.click('#btnSpecPdf');
  await page.waitForTimeout(200);
  ok('специфікація: PDF у прототипі — «на сервері» (повідомлення)', /сервер/i.test(await page.evaluate(() => document.getElementById('toast').textContent)));
  await page.evaluate(() => { const d = document.querySelector('dialog[open]'); d && d.close(); });
  // план
  await page.evaluate(() => __f3d.E.runDialog('planDoc'));
  await page.waitForSelector('#planPrev svg');
  const pl = await page.evaluate(() => { const svg = document.querySelector('#planPrev svg'); return { poly: svg.querySelectorAll('polygon').length, texts: [...svg.querySelectorAll('text')].map((t) => t.textContent), info: document.getElementById('planInfo').textContent }; });
  ok('план: SVG з контуром, колонами, рядами й підписами, штамп і масштаб', pl.poly > 40 && pl.texts.some((t) => /^R\d-\d$/.test(t)) && pl.texts.some((t) => /Масштаб 1:\d+/.test(t)) && pl.texts.includes('Проєкт') && pl.texts.some((t) => /\d+(\.\d+)? м$/.test(t)), JSON.stringify(pl).slice(0, 300));
  const a3 = await page.evaluate(() => document.querySelector('#planPrev svg').getAttribute('viewBox'));
  await page.evaluate(() => { const sel = document.querySelectorAll('#planBody select'); sel[1].value = 'A4'; sel[1].dispatchEvent(new Event('change')); sel[2].value = 'portrait'; sel[2].dispatchEvent(new Event('change')); });
  await page.waitForTimeout(150);
  const a4 = await page.evaluate(() => document.querySelector('#planPrev svg').getAttribute('viewBox'));
  ok('план: формат A3 альбомна (420×297) → A4 книжкова (210×297)', a3 === '0 0 420 297' && a4 === '0 0 210 297', a3 + ' → ' + a4);
  const [svg] = await Promise.all([page.waitForEvent('download'), page.click('#btnPlanSvg')]);
  ok('план: SVG-файл', /<svg/.test(fs.readFileSync(await svg.path(), 'utf8')));
  const [png] = await Promise.all([page.waitForEvent('download'), page.click('#btnPlanPng')]);
  const pngBuf = fs.readFileSync(await png.path());
  ok('план: PNG 3200 px (сигнатура PNG, ширина)', pngBuf.slice(1, 4).toString() === 'PNG' && pngBuf.readUInt32BE(16) === 3200, String(pngBuf.length));
  await page.click('#btnPlanPdf');
  await page.waitForTimeout(200);
  ok('план: PDF у прототипі — «на сервері»', /сервер/i.test(await page.evaluate(() => document.getElementById('toast').textContent)));
  await page.evaluate(() => { const d = document.querySelector('dialog[open]'); d && d.close(); });
}

(async () => {
  const { browser, page, errors } = await launch();
  try {
    await open(page);
    await t_mode(page, errors);
    await t_contour(page, errors);
    await t_items(page, errors);
    await t_checks(page, errors);
    await t_3d(page, errors);
    await t_wizard(page, errors);
    await t_docs(page, errors);
  } catch (e) {
    ok('виняток сценарію', false, e.stack || String(e));
  }
  const real = errors.filter((e) => !/favicon|Failed to load resource|WebGL|swiftshader|GPU stall|ReadPixels/i.test(e));
  ok('помилок консолі немає', real.length === 0, real.slice(0, 4).join(' | '));
  await browser.close();
  const bad = res.filter((x) => !x).length;
  console.log(`\nІТОГО S5: ${res.length - bad} passed, ${bad} failed`);
  process.exit(bad ? 1 : 0);
})();
