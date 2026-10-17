const { launch, open, DIR } = require('./harness');
const fs = require('fs');
const SH = DIR + '/shots/';
const res = [];
const ok = (name, cond, extra) => { res.push([cond ? 'PASS' : 'FAIL', name]); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? ' :: ' + extra : '')); };
const proj = (page, x, y, z = 0) => page.evaluate(([x, y, z]) => { const V = __f3d.V, v = new THREE.Vector3(x, z, -y).project(V.camera), r = V.canvas.getBoundingClientRect(); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height }; }, [x, y, z]);

async function t_db() {
  const { browser, ctx, page, errors } = await launch();
  await ctx.addInitScript(() => {
    const store = new Map(); window.__dbStore = store;
    window.claude = { use: async (n) => {
      if (n === 'db') return { collection: (c) => ({ doc: (id) => ({
        get: async () => ({ exists: store.has(c + '/' + id), data: () => JSON.parse(JSON.stringify(store.get(c + '/' + id))) }),
        set: async (d) => { const s = JSON.stringify(d); if (new Blob([s]).size > 256 * 1024) throw new Error('doc too large ' + c + '/' + id); store.set(c + '/' + id, JSON.parse(s)); },
        delete: async () => { store.delete(c + '/' + id); } }) }) };
      if (n === 'user') return { id: async () => 'u_test123', name: async () => 'Олена Тест' };
      return null; } };
  });
  await open(page);
  ok('db: адаптер выбрал db', await page.evaluate(() => __f3d.store.kind === 'db'));
  ok('db: на загрузке ничего не записано', await page.evaluate(() => window.__dbStore.size === 0));
  await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-2'); p.x += 1; __f3d.commit({ dirty: ['placements'] }); });
  await page.waitForTimeout(1500);
  let info = await page.evaluate(() => { const m = window.__dbStore; let max = 0; const keys = []; for (const [k, v] of m) { const sz = new Blob([JSON.stringify(v)]).size; max = Math.max(max, sz); keys.push(k.split('/')[0]); } return { n: m.size, max, colls: [...new Set(keys)].sort(), ls: Object.keys(localStorage).filter((k) => k.startsWith('f3d1:')).length }; });
  ok('db: запись после первой правки в коллекции sites/layers/slots/placements/catalog/versions/settings', info.n >= 8 && ['catalog', 'layers', 'placements', 'settings', 'sites', 'slots', 'versions'].every((c) => info.colls.includes(c)), JSON.stringify(info));
  ok('db: каждый документ ≤ 256 КиБ', info.max <= 256 * 1024, 'max=' + info.max);
  ok('db: localStorage не используется', info.ls === 0);
  // публикация: автор — имя из claude.use("user")
  await page.click('#btnPublish'); await page.waitForSelector('dialog[open]');
  await page.click('dialog button:has-text("Підтвердити й опублікувати")'); await page.waitForTimeout(1200);
  const by = await page.evaluate(() => __f3d.S.versions.slice(-1)[0].by);
  ok('db: автор версии из claude.use("user")', by === 'Олена Тест', by);
  // большой документ режется на части
  const big = await page.evaluate(async () => {
    const arr = []; for (let i = 0; i < 3000; i++) arr.push({ id: 'pl_' + i, layer_id: 'ly_line', variant_id: 'x', x: i * 1.5, y: i * 2.5, rotation: 0, code: 'CODE-' + i, name: 'Тестове обладнання номер ' + i });
    const len = JSON.stringify(arr).length;
    await __f3d.store.set('versions', 'bigtest', arr);
    const back = await __f3d.store.get('versions', 'bigtest');
    let max = 0; for (const [k, v] of window.__dbStore) max = Math.max(max, new Blob([JSON.stringify(v)]).size);
    const chunks = [...window.__dbStore.keys()].filter((k) => k.startsWith('versions/bigtest')).length;
    return { len, ok: back.length === 3000 && back[2999].code === 'CODE-2999', max, chunks };
  });
  ok('db: версия > 256 КиБ режется на части и читается обратно', big.len > 200000 && big.ok && big.chunks > 3 && big.max <= 256 * 1024, JSON.stringify(big));
  // перезагрузка с тем же db-моком (хранилище в памяти страницы теряется) — пропускаем
  ok('db: консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t_features() {
  const { browser, page, errors } = await launch();
  await open(page);
  // тема
  await page.click('#btnTheme'); await page.waitForTimeout(500);
  ok('тема: переключение на тёмную', await page.evaluate(() => document.documentElement.dataset.theme === 'dark'));
  await page.click('#btnTheme'); await page.waitForTimeout(400);
  // подписи
  await page.click('#vtools button:has-text("Підписи")'); await page.waitForTimeout(200);
  await page.click('#vtools button:has-text("Підписи")');
  // линейка: клавиша M + два клика
  await page.keyboard.press('KeyM');
  const a = await proj(page, 50, 20, 0), b = await proj(page, 80, 20, 0);
  await page.mouse.click(a.x, a.y); await page.waitForTimeout(100); await page.mouse.click(b.x, b.y); await page.waitForTimeout(300);
  const rl = await page.textContent('#rlabel');
  ok('линейка: два клика → расстояние в метрах (30 м)', /^\s*(29,[5-9]|30,[0-5])\d* м/.test(rl), rl);
  await page.keyboard.press('Escape');
  // drag&drop из каталога
  await page.click('#ltabs button[data-tab="catalog"]'); await page.waitForTimeout(200);
  const before = await page.evaluate(() => __f3d.S.placements.length);
  const cb = await (await page.$('#vp canvas')).boundingBox();
  await page.dragAndDrop('.var >> nth=0', '#vp canvas', { targetPosition: { x: cb.width * 0.45, y: cb.height * 0.6 } });
  await page.waitForTimeout(500);
  const after = await page.evaluate(() => ({ n: __f3d.S.placements.length, last: __f3d.S.placements.slice(-1)[0] }));
  ok('DnD из каталога на сцену создаёт размещение', after.n === before + 1, JSON.stringify(after.last));
  // слои: добавить, переименовать, удалить
  await page.click('#ltabs button[data-tab="layers"]');
  await page.click('#leftBody button:has-text("Шар")'); await page.waitForTimeout(300);
  const nl = await page.evaluate(() => __f3d.S.layers.length);
  ok('«+ Шар» добавляет слой (31 шар моделі + новий)', nl === 32);
  await page.fill('#layerForm input[aria-label="Назва"]', 'Антресоль цеху'); await page.waitForTimeout(200);
  ok('имя слоя обновляется в списке', await page.evaluate(() => [...document.querySelectorAll('#layerList .nm')].some((e) => e.textContent === 'Антресоль цеху')));
  await page.click('#layerForm button:has-text("Видалити шар")'); await page.waitForSelector('dialog[open]');
  await page.click('dialog button:has-text("Видалити")'); await page.waitForTimeout(300);
  ok('удаление слоя через диалог на странице', await page.evaluate(() => __f3d.S.layers.length === 31));
  // правка проходов в слое «Склади»
  await page.click('.layer[data-layer="fg"]'); await page.waitForTimeout(200);
  const ai0 = await page.evaluate(() => __f3d.S.layers.find((l) => l.id === 'ly_fg').aisles.length);
  await page.click('#layerForm button:has-text("Прохід") >> nth=0'); await page.waitForTimeout(200);
  ok('«+ Прохід» добавляет проход', await page.evaluate((n) => __f3d.S.layers.find((l) => l.id === 'ly_fg').aisles.length === n + 1, ai0));
  // override ячейки
  await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.code_prefix === 'FG-R1'); __f3d.selectObj({ kind: 'slot', id: s.id }); });
  await page.click('#cellsBox tbody tr:nth-child(2)'); await page.waitForTimeout(200);
  await page.fill('#cellsBox input[aria-label="Місткість"]', '3'); await page.waitForTimeout(200);
  const ov = await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.code_prefix === 'FG-R1'); return s.overrides; });
  ok('ручная правка ячейки → overrides по коду', ov['FG-R1-B01-L2'] && ov['FG-R1-B01-L2'].capacity === 3, JSON.stringify(ov));
  await page.fill('#cellsBox input[aria-label="Макс. навантаження"]', '2500'); await page.waitForTimeout(300);
  const ld = await page.evaluate(() => __f3d.S.issues.list.filter((i) => i.check === 'load').map((i) => i.msg));
  ok('проверка нагрузки ячейки (лимит ячейки > стеллажа)', ld.length === 1 && /FG-R1-B01-L2/.test(ld[0]), JSON.stringify(ld));
  // Del с подтверждением
  await page.evaluate(() => { const p = __f3d.S.placements.slice(-1)[0]; __f3d.selectObj({ kind: 'placement', id: p.id }); });
  const nPl = await page.evaluate(() => __f3d.S.placements.length);
  await page.keyboard.press('Delete'); await page.waitForSelector('dialog[open]');
  ok('Delete открывает подтверждение на странице', await page.evaluate(() => /Видалити об’єкт/.test(document.querySelector('dialog').textContent)));
  await page.click('dialog button:has-text("Видалити")'); await page.waitForTimeout(300);
  ok('удаление объекта', await page.evaluate((n) => __f3d.S.placements.length === n - 1, nPl));
  // пустая площадка: размещение варианта из каталога и первая публикация
  await page.click('#btnNewSite'); await page.waitForSelector('dialog[open]'); await page.fill('dialog input[type=text]', 'Цех 2'); await page.click('dialog button:has-text("Створити")'); await page.waitForTimeout(1500);
  await page.click('.layer[data-layer="ly_prod"]');
  await page.click('#ltabs button[data-tab="catalog"]'); await page.waitForTimeout(200);
  await page.click('.var >> nth=0 >> button[aria-label="Поставити на сцену"]'); await page.waitForTimeout(300);
  const t = await proj(page, 30, 15, 0); await page.mouse.move(t.x, t.y); await page.mouse.move(t.x + 2, t.y + 2); await page.mouse.click(t.x + 2, t.y + 2); await page.waitForTimeout(500);
  ok('пустая площадка: размещение из каталога по клику', await page.evaluate(() => __f3d.S.placements.length === 1 && __f3d.S.placements[0].code.startsWith('M-')));
  await page.screenshot({ path: SH + '_empty_site.png' });
  await page.click('#btnPublish'); await page.waitForSelector('dialog[open]');
  const ptxt = await page.textContent('dialog');
  ok('первая публикация: сводка', /перша публікація/.test(ptxt) && /Буде створено в Odoo/.test(ptxt));
  await page.click('dialog button:has-text("Підтвердити й опублікувати")'); await page.waitForTimeout(800);
  ok('первая публикация → v1', await page.evaluate(() => __f3d.S.site.active_version === 1));
  // роль инженер редактирует сети
  await page.selectOption('#roleSel', 'engineer'); await page.click('#ltabs button[data-tab="layers"]'); await page.click('.layer[data-layer="ly_eng"]');
  ok('инженер: слой сетей редактируемый (нет замка)', await page.evaluate(() => !document.querySelector('.layer.active .ic[title]')));
  ok('консоль без ошибок', errors.length === 0, errors.slice(0, 4).join(' | '));
  await browser.close();
}

async function t_mobile() {
  const { browser, page, errors } = await launch({ viewport: { width: 400, height: 860 } });
  await open(page);
  await page.click('#mtabs button[data-mtab="catalog"]'); await page.waitForTimeout(300);
  await page.screenshot({ path: SH + '_mobile_catalog.png' });
  await page.click('.var >> nth=0 >> text=Картка'); await page.waitForSelector('dialog[open]'); await page.waitForTimeout(500);
  await page.screenshot({ path: SH + '_mobile_variant.png' });
  const w = await page.evaluate(() => { const d = document.querySelector('dialog'); const r = d.getBoundingClientRect(); return { l: r.left, r: r.right, sw: document.documentElement.scrollWidth }; });
  ok('моб.: диалог карточки в пределах экрана', w.l >= 0 && w.r <= 400 && w.sw <= 400, JSON.stringify(w));
  await page.keyboard.press('Escape'); await page.waitForTimeout(200);
  // выбор объекта → вкладка «Об’єкт»
  const pt = await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'SAW-1'); return { x: p.x, y: p.y }; });
  await page.evaluate(() => __f3d.setView('plan'));
  const c = await proj(page, pt.x, pt.y, 0.8); await page.mouse.click(c.x, c.y); await page.waitForTimeout(400);
  const tab = await page.evaluate(() => document.querySelector('#app').dataset.mtab);
  ok('моб.: выбор объекта открывает «Об’єкт»', tab === 'props', tab);
  await page.screenshot({ path: SH + '_mobile_props.png' });
  await page.click('#btnPublish'); await page.waitForSelector('dialog[open]'); await page.waitForTimeout(300);
  await page.screenshot({ path: SH + '_mobile_publish.png' });
  const w2 = await page.evaluate(() => { const d = document.querySelector('dialog'); const r = d.getBoundingClientRect(); return { l: r.left, r: r.right, sw: document.documentElement.scrollWidth }; });
  ok('моб.: диалог публикации в пределах экрана', w2.l >= 0 && w2.r <= 400 && w2.sw <= 400, JSON.stringify(w2));
  ok('моб.: консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}


async function t_formats() {
  const { browser, page, errors } = await launch();
  await open(page);
  await page.click('#ltabs button[data-tab="catalog"]'); await page.waitForTimeout(200);
  await page.click('.var >> nth=0 >> text=Картка'); await page.waitForSelector('dialog[open]');
  const info = async () => (await page.evaluate(() => [...document.querySelectorAll('dialog .kv dd')].map((d) => d.textContent).join('|'))).replace(/[  ]/g, '');
  for (const [f, exp] of [['cube_m.dae', '2000×1000×1000'], ['pyramid.3mf', '1000×600×900']]) {
    await page.setInputFiles('#modelFile', DIR + '/fixtures/' + f); await page.waitForTimeout(900);
    const t = await info();
    ok('формат ' + f + ': габариты ' + exp, t.includes(exp), t);
  }
  await page.setInputFiles('#modelFile', DIR + '/fixtures/dense_mm.obj'); await page.waitForTimeout(2500);
  const warn = await page.evaluate(() => [...document.querySelectorAll('dialog .note')].map((n) => n.textContent).join(' '));
  ok('> 50 тыс. треугольников: предупреждение и «упростить на сервере»', /50\s*000/.test(warn.replace(/ /g, ' ')) && /спростити|спростіть/.test(warn) && /сервері/.test(warn), warn.slice(0, 140));
  ok('FBX-загрузчик доступен', await page.evaluate(() => typeof THREE.FBXLoader === 'function' && typeof fflate === 'object'));
  ok('консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t_perf() {
  const { browser, page, errors } = await launch();
  await open(page);
  const r = await page.evaluate(() => {
    const S = __f3d.S; const v = S.catalog.flatMap((p) => p.variants).find((x) => x.name.includes('SAWTEQ S-310'));
    const t0 = performance.now();
    for (let i = 0; i < 220; i++) S.placements.push({ id: 'pf' + i, layer_id: 'ly_line', variant_id: 'cnc.centateq-p-110', slot_id: null, x: 5 + (i % 22) * 6.5, y: 4 + Math.floor(i / 22) * 6.5, rotation: (i % 4) * 90, code: 'PF-' + i, name: 'perf' });
    const ids = S.catalog.flatMap((p) => p.variants).map((x) => x.id);
    for (const p of S.placements) if (!__f3d.S.vIdx.has(p.variant_id) && !ids.includes(p.variant_id)) p.variant_id = v.id;
    __f3d.commit({ dirty: ['placements'] });
    const t1 = performance.now();
    const t2 = performance.now(); for (let i = 0; i < 5; i++) __f3d.runChecks(); const tc = (performance.now() - t2) / 5;
    const t3 = performance.now(); __f3d.V.renderer.render(__f3d.V.scene, __f3d.V.camera); const tr = performance.now() - t3;
    let cells = 0; for (const s of S.slots) cells += __f3d.cellsOf(s).length;
    return { n: S.placements.length, cells, commit: Math.round(t1 - t0), checks: Math.round(tc), render: Math.round(tr), views: __f3d.V.views.size };
  });
  console.log('perf', JSON.stringify(r));
  ok('~250 объектов и ~600 ячеек: commit < 4 c, проверки < 300 мс', r.n >= 250 && r.cells >= 600 && r.commit < 4000 && r.checks < 300, JSON.stringify(r));
  await page.waitForTimeout(500);
  await page.screenshot({ path: SH + '_perf.png' });
  ok('консоль без ошибок', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
}

async function t_ui() {
  const { browser, page, errors } = await launch();
  await open(page);
  const click = async (sel) => { await page.click(sel); await page.waitForTimeout(120); };
  // слой: контур, пожарный проход, выход, точка сети, порядок, тип
  await click('.layer[data-layer="territory"]');
  await click('#layerForm label:has-text("Задати контур") input');
  ok('слой: контур задан', await page.evaluate(() => !!__f3d.S.layers.find((l) => l.id === 'ly_territory').bounds));
  await page.fill('#layerForm .grid4 input >> nth=0', '-10'); await page.waitForTimeout(100);
  await click('#layerForm button:has-text("Прохід") >> nth=1');
  await click('#layerForm button:has-text("Вихід")');
  await click('#layerForm button:has-text("Точка")');
  const yd = await page.evaluate(() => { const l = __f3d.S.layers.find((x) => x.id === 'ly_territory'); return { fp: l.fire_paths.map((f) => f.kind).join(','), ut: l.utilities.length, b: l.bounds.x0 }; });
  ok('слой: пожарный проход, выход и точка сети добавлены', yd.fp === 'path,exit' && yd.ut === 1 && yd.b === -10, JSON.stringify(yd));
  await click('#layerForm button[aria-label="Вище"]');
  ok('слой: порядок меняется', await page.evaluate(() => { const s = [...__f3d.S.layers].sort((a, b) => a.sequence - b.sequence).map((l) => l.id); return s.indexOf('ly_territory') === 26; }));
  await page.selectOption('#layerForm select[aria-label="Тип"]', 'storage');
  await click('#layerList .layer >> nth=0 >> button.eye');
  ok('слой: видимость переключается', await page.evaluate(() => __f3d.S.layers.find((l) => l.id === 'ly_building').visible === false));
  await click('#layerList .layer >> nth=0 >> button.eye');
  // каталог: новый тип, новый вариант, размещение
  await click('#ltabs button[data-tab="catalog"]');
  await click('#leftBody button:has-text("Тип") >> nth=0');
  await page.waitForSelector('dialog[open]');
  await page.fill('dialog input[type=text] >> nth=0', 'Тестовий робот');
  await page.selectOption('dialog select', 'robot');
  await click('dialog button:has-text("Зберегти")');
  ok('каталог: новый тип создан', await page.evaluate(() => __f3d.S.catalog.some((p) => p.name === 'Тестовий робот' && p.category === 'robot')));
  await click('details.cat:has-text("Тестовий робот") >> button:has-text("Варіант")');
  await page.waitForSelector('dialog[open]');
  await page.fill('dialog input[aria-label="Назва"]', 'Робот-тест'); await page.fill('dialog input[data-f="length"]', '1800'); await page.fill('dialog input[data-f="width"]', '1800');
  await click('dialog button:has-text("Точка підключення")');
  await click('dialog label:has-text("Виробнитцво") input').catch(() => {});
  await click('dialog button:has-text("Зберегти")');
  const nv = await page.evaluate(() => { const v = __f3d.S.catalog.flatMap((p) => p.variants).find((x) => x.name === 'Робот-тест'); return v && { l: v.length, w: v.width, u: v.utilities.length }; });
  ok('каталог: новый вариант с габаритами и точкой подключения', nv && nv.l === 1800 && nv.w === 1800 && nv.u === 1, JSON.stringify(nv));
  // редактирование варианта и отмена
  await click('.var:has-text("Робот-тест") >> text=Картка');
  await page.waitForSelector('dialog[open]');
  await page.fill('dialog input[data-f="height"]', '2750');
  await click('dialog button:has-text("Скасувати")');
  ok('отмена карточки не меняет вариант', await page.evaluate(() => __f3d.S.catalog.flatMap((p) => p.variants).find((x) => x.name === 'Робот-тест').height !== 2750));
  // размещение через кнопку «+»
  await click('.layer >> nth=0').catch(() => {});
  await click('#ltabs button[data-tab="layers"]'); await click('.layer[data-layer="line"]');
  await click('#ltabs button[data-tab="catalog"]');
  await click('.var:has-text("Робот-тест") >> button[aria-label="Поставити на сцену"]');
  const t = await proj(page, 100, 40, 0); await page.mouse.move(t.x, t.y); await page.mouse.move(t.x + 2, t.y + 1); await page.mouse.click(t.x + 2, t.y + 1); await page.waitForTimeout(400);
  const rb = await page.evaluate(() => __f3d.S.placements.find((p) => p.code.startsWith('RB-')));
  ok('размещение нового варианта (робот)', !!rb, JSON.stringify(rb));
  // свойства: смена варианта, поворот произвольный
  await page.screenshot({ path: SH + '_ui_robot.png' });
  // переключение ролей на каждой вкладке
  for (const r of ['technologist', 'storekeeper', 'engineer', 'manager']) {
    await page.selectOption('#roleSel', r);
    for (const tab of ['layers', 'slots', 'catalog']) await click(`#ltabs button[data-tab="${tab}"]`);
  }
  // режим просмотра на всех вкладках
  await click('#modeSeg button[data-mode="view"]');
  for (const tab of ['layers', 'slots', 'catalog']) await click(`#ltabs button[data-tab="${tab}"]`);
  await click('#modeSeg button[data-mode="edit"]');
  // версия: история на пустой
  await click('#btnHistory'); await page.waitForSelector('dialog[open]'); await page.keyboard.press('Escape');
  // клавиши: стрелки двигают выбранный объект
  const p0 = await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-1'); __f3d.selectObj({ kind: 'placement', id: p.id }); return { x: p.x, y: p.y }; });
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowUp'); await page.waitForTimeout(200);
  const p1 = await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-1'); return { x: p.x, y: p.y }; });
  ok('стрелки двигают объект по шагу сетки', Math.abs(p1.x - p0.x - 0.5) < 1e-6 && Math.abs(p1.y - p0.y - 0.5) < 1e-6, JSON.stringify([p0, p1]));
  // ввод x в форме двигает объект
  await page.fill('#rightBody input[data-f="x"]', '80'); await page.waitForTimeout(200);
  ok('форма → 3D: x=80', await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'CNC-1'); const v = __f3d.V.views.get('p:' + p.id); return p.x === 80 && Math.abs(v.root.position.x - 80) < 1e-6; }));
  // fits=block: вынос за здание возвращает значение
  await page.fill('#rightBody input[data-f="x"]', '500'); await page.dispatchEvent('#rightBody input[data-f="x"]', 'change'); await page.waitForTimeout(300);
  const bx = await page.evaluate(() => __f3d.S.placements.find((q) => q.code === 'CNC-1').x);
  ok('форма: вынос за здание (fits=block) возвращает значение на начало правки', bx === 73.5, String(bx));
  ok('консоль без ошибок', errors.length === 0, errors.slice(0, 4).join(' | '));
  await browser.close();
}

(async () => {
  const which = process.argv.slice(2), all = { t_db, t_features, t_mobile, t_formats, t_perf, t_ui };
  for (const [k, f] of Object.entries(all)) { if (which.length && !which.includes(k)) continue; try { await f(); } catch (e) { ok(k + ' exception', false, String(e).split('\n').slice(0, 3).join(' ')); } }
  const fails = res.filter((r) => r[0] === 'FAIL'); console.log(`\nИТОГО: ${res.length - fails.length} passed, ${fails.length} failed`);
})();
