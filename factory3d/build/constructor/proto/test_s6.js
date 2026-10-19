// Слайс S6 «Спільна робота й навчання» у прототипі: варіанти (F12), коментарі й значки (F13), рівні й мініатюра (N-01), історія версій (N-03),
// мови UK/EN, тури й інструкція (F19). Блокування зон (F14) у прототипі не емулюються: перевіряється лише відсутність кнопок, а логіка —
// на підміненому адаптері. Запуск: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node build/constructor/proto/test_s6.js [варіанти|коментарі|рівні|мова|тури|історія|блокування]
// (після python3 build/constructor/proto/build.py)
const { launch, open } = require('./harness');
const res = [];
const ok = (name, cond, extra) => { res.push(!!cond); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra !== undefined && !cond ? ' :: ' + extra : '')); };
const ev = (page, fn, arg) => page.evaluate(fn, arg);
const tab = async (page, name) => { await page.click(`#ltabs button[data-tab="${name}"]`); await page.waitForTimeout(150); };
const nSlots = (page) => ev(page, () => __f3d.S.slots.length);
const menu = async (page, key) => {
  await page.evaluate(() => { const d = document.getElementById('menuMore'); if (d) d.open = true; });
  await page.click('#menu-' + key);
};
const addRack = (page, prefix, x = 30, y = 20) => ev(page, ([p, x0, y0]) => {
  const { E, core } = __f3d;
  E.addSlotAt({ kind: 'slot', template: 'pallet_rack', prefix: p, params: core.data.defaultParams('pallet_rack') }, x0, y0);
}, [prefix, x, y]);
/** Екранні координати точки плану (м) у режимі «План». */
const screenOf = (page, x, y, z = 0) => ev(page, ([x0, y0, z0]) => {
  const { V, core } = __f3d;
  const v = new core.THREE.Vector3(x0, z0, -y0).project(V.camera);
  const r = V.canvas.getBoundingClientRect();
  return { x: r.left + (v.x * 0.5 + 0.5) * r.width, y: r.top + (-v.y * 0.5 + 0.5) * r.height };
}, [x, y, z]);

async function t_chrome(page, errors) {
  ok('рівні: рядок навігації з кнопками ↓ ↑ ⟲ і «Клік виділяє»', !!(await page.$('#s6Crumbs #s6Down')) && !!(await page.$('#s6Up')) && !!(await page.$('#s6Reset')) && !!(await page.$('#s6PickSel')));
  const picks = await ev(page, () => [...document.querySelectorAll('#s6PickSel option')].map((o) => o.textContent));
  ok('«Клік виділяє»: Місце, Стелаж, Ряд, Зона', JSON.stringify(picks) === JSON.stringify(['Місце', 'Стелаж', 'Ряд', 'Зона']), JSON.stringify(picks));
  ok('вкладки «Варіанти» й «Коментарі» в лівій панелі', !!(await page.$('#ltabs button[data-tab="variants"]')) && !!(await page.$('#ltabs button[data-tab="comments"]')));
  ok('меню: кнопка варіанта, EN, Тури й Інструкція в «Ще»', !!(await page.$('#menu-variants')) && !!(await page.$('#menu-lang')) && !!(await page.$('#menu-tours')) && !!(await page.$('#menu-help')));
  const vbtn = await page.textContent('#menu-variants');
  ok('кнопка варіанта показує активний: «Варіант: Як є»', /Варіант: Як є/.test(vbtn), vbtn);
  await page.waitForTimeout(400);
  const px = await ev(page, () => { const c = document.getElementById('s6MiniCanvas'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] !== d[0] || d[i + 1] !== d[1]) n++; return [c.width, c.height, n]; });
  ok('мініатюра намальована (контур, об’єкти, рамка виду)', px[0] > 100 && px[1] > 40 && px[2] > 300, JSON.stringify(px));
  ok('capabilities прототипа: варіанти й коментарі є, блокування зон немає', await ev(page, () => { const { can } = __f3d.core; return can('variants') && can('comments') && !can('locks'); }));
  ok('блокування: у прототипі немає блоку списку й значків', !(await page.$('#s6LockList')) && !(await page.$('#s6Locks .s6-lockb')));
  ok('тур-запрошення не показується під автоматизацією (navigator.webdriver)', !(await page.$('#s6TourInvite')));
  ok('помилок консолі немає', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_variants(page) {
  await tab(page, 'variants');
  ok('вкладка: один варіант «Як є», активний, «Видалити» вимкнено', (await page.$$('#s6VarList .s6-item')).length === 1 && await ev(page, () => document.querySelector('#s6VarList [data-act=delete]').disabled));
  const base = await nSlots(page);
  await page.click('#s6VarCreate');
  await page.waitForSelector('#s6VarName');
  ok('назва нового варіанта запропонована: «Проєкт A»', (await page.inputValue('#s6VarName')) === 'Проєкт A');
  await page.click('#s6VarOk');
  await page.waitForFunction(() => document.querySelectorAll('#s6VarList .s6-item').length === 2);
  ok('«Створити з поточного»: два варіанти, активний — «Проєкт A»', /Варіант: Проєкт A/.test(await page.textContent('#menu-variants')));
  await addRack(page, 'S6-A1');
  const withRack = await nSlots(page);
  ok('правка в проєкті A: стелаж додано', withRack === base + 1);
  await page.waitForTimeout(900);
  await page.click('#s6VarList .s6-item[data-active="0"] [data-act=activate]');
  await page.waitForFunction((n) => __f3d.S.slots.length === n, base, { timeout: 8000 });
  ok('перехід у «Як є»: правки проєкту A не видно, чернетка не втрачена', (await nSlots(page)) === base && /Як є/.test(await page.textContent('#menu-variants')));
  await tab(page, 'variants');
  const cmp = await ev(page, () => [...document.querySelectorAll('#s6VarCmp tbody tr')].map((r) => r.dataset.key + ':' + [...r.children].slice(1).map((c) => c.textContent).join('|')));
  ok('порівняння: шість рядків із цифрами й різницею', cmp.length === 6 && /^cells:/.test(cmp[0]) && cmp.every((r) => r.split('|').length === 3), JSON.stringify(cmp));
  const cellsRow = await ev(page, () => [...document.querySelectorAll('#s6VarCmp tbody tr[data-key=cells] td')].map((c) => c.textContent.replace(/\s/g, '')));
  ok('порівняння: «Місць» А=B або різниця з Δ', cellsRow.length === 4 && cellsRow[3] !== '—', JSON.stringify(cellsRow));
  await page.click('#s6VarList .s6-item[data-active="0"] [data-act=activate]');
  await page.waitForFunction((n) => __f3d.S.slots.length === n, withRack, { timeout: 8000 });
  ok('назад у проєкт A: стелаж на місці', await ev(page, () => __f3d.S.slots.some((s) => s.code_prefix === 'S6-A1')));
  await tab(page, 'variants');
  await page.click('#s6VarList .s6-item[data-active="0"] [data-act=rename]');
  await page.waitForSelector('#s6VarName');
  await page.fill('#s6VarName', 'Базовий');
  await page.click('#s6VarOk');
  await page.waitForFunction(() => /Базовий/.test(document.getElementById('s6VarList').textContent));
  ok('перейменування «Як є» → «Базовий»', true);
  await page.click('#s6VarList .s6-item[data-active="0"] [data-act=delete]');
  await page.waitForSelector('#dlgYes');
  await page.click('#dlgYes');
  await page.waitForFunction(() => document.querySelectorAll('#s6VarList .s6-item').length === 1);
  ok('видалення неактивного варіанта з підтвердженням', true);
  // навчальна копія
  await ev(page, () => __f3d.E.createVariant('Навчальна копія', { training: true }));
  await page.waitForSelector('#s6Train:not([hidden])');
  ok('панель «Навчальна копія»: «Залишити зміни» й «Скасувати»; публікація вимкнена', !!(await page.$('#s6TrainKeep')) && !!(await page.$('#s6TrainCancel')) && await ev(page, () => document.getElementById('btnPublish').disabled));
  await addRack(page, 'S6-T1', 40, 30);
  await page.waitForTimeout(900);
  await page.click('#s6TrainCancel');
  await page.waitForFunction(() => document.getElementById('s6Train').hidden && !__f3d.S.slots.some((s) => s.code_prefix === 'S6-T1'), null, { timeout: 8000 });
  ok('«Скасувати»: копію прибрано, навчальні правки зникли', true);
  ok('після скасування публікація знову доступна', await ev(page, () => !document.getElementById('btnPublish').disabled));
}

async function t_comments(page) {
  const rack = await ev(page, () => { const s = __f3d.S.slots.find((x) => x.template === 'pallet_rack'); return { id: s.id, x: s.x, y: s.y }; });
  await ev(page, (id) => __f3d.E.selectObj({ kind: 'slot', id }), rack.id);
  await page.waitForSelector('#s6CmText');
  ok('блок «Коментарі» в правій панелі для вибраного ряду', /Коментарі/.test(await page.textContent('#s6Comments h3')));
  await page.fill('#s6CmText', 'Перевірити стелаж на місці');
  await page.click('#s6CmAdd');
  await page.waitForSelector('#s6Badges .s6-badge');
  const tone1 = await ev(page, () => [...document.querySelectorAll('#s6Badges .s6-badge')].map((b) => b.dataset.tone + ':' + b.textContent));
  ok('значок на сцені: синій (нотатка) з числом 1', tone1.includes('note:1'), JSON.stringify(tone1));
  await page.selectOption('#s6CmKind', 'task');
  await page.fill('#s6CmText', 'Перемірити прохід');
  await page.click('#s6CmAdd');
  await page.waitForFunction(() => document.querySelector('#s6Badges .s6-badge[data-tone="task"]'));
  const t2 = await ev(page, () => document.querySelector('#s6Badges .s6-badge').textContent);
  ok('додали задачу: значок помаранчевий, число 2', t2 === '2');
  const pos = await ev(page, () => { const b = document.querySelector('#s6Badges .s6-badge'); return [b.hidden, b.style.left, b.style.top]; });
  ok('значок розташований над об’єктом сцени (проєкція)', pos[0] === false && /px$/.test(pos[1]) && /px$/.test(pos[2]), JSON.stringify(pos));
  await page.click('#s6Comments [data-kind="task"] [data-act="resolve"]');
  await page.waitForFunction(() => document.querySelector('#s6Badges .s6-badge').dataset.tone === 'note');
  ok('задачу вирішено: лишається синя нотатка', true);
  await page.click('#s6Comments [data-kind="note"] [data-act="resolve"]');
  await page.waitForFunction(() => document.querySelector('#s6Badges .s6-badge').dataset.tone === 'done');
  ok('усе вирішено: значок сірий', true);
  // список
  await tab(page, 'comments');
  await page.selectOption('[data-f="state"]', 'all');
  const rows = await page.$$('#s6CmRows .s6-item');
  ok('вкладка «Коментарі»: список із двох записів (фільтр «Усі»)', rows.length === 2);
  await page.selectOption('[data-f="state"]', 'open');
  ok('фільтр «Відкриті»: порожньо', (await page.$$('#s6CmRows .s6-item')).length === 0);
  await page.selectOption('[data-f="state"]', 'all');
  await page.selectOption('[data-f="kind"]', 'task');
  ok('фільтр за видом «Задачі»: один запис', (await page.$$('#s6CmRows .s6-item')).length === 1);
  await page.selectOption('[data-f="kind"]', 'all');
  await page.fill('#s6CmQ', 'прохід');
  await page.waitForFunction(() => document.querySelectorAll('#s6CmRows .s6-item').length === 1);
  ok('фільтр за текстом «прохід»', true);
  await ev(page, () => __f3d.E.selectObj(null));
  await tab(page, 'comments');
  await page.fill('#s6CmQ', '');
  await page.waitForTimeout(300);
  await page.click('#s6CmRows .s6-item');
  await page.waitForTimeout(200);
  ok('клік по запису списку виділяє об’єкт коментаря', await ev(page, (id) => __f3d.S.sel && __f3d.S.sel.id === id, rack.id));
  await ev(page, () => __f3d.E.selectObj(null));
  await tab(page, 'comments');
  await page.check('#s6CmOnly');
  ok('«лише цей об’єкт» без виділення — коментарі площадки (їх немає)', (await page.$$('#s6CmRows .s6-item')).length === 0);
  // клік по значку відкриває гілку
  await page.click('#s6Badges .s6-badge');
  await page.waitForSelector('#s6Thread');
  ok('клік по значку відкриває гілку коментарів об’єкта', (await page.$$('#s6Thread .s6-item')).length === 2);
  await page.keyboard.press('Escape');
  // коментар до комірки й площадки
  await ev(page, (id) => { __f3d.E.selectObj({ kind: 'slot', id }); const c = __f3d.cellsOf(__f3d.S.sIdx.get(id))[0]; __f3d.S.selCell = c.code; __f3d.E.renderRight(); }, rack.id);
  await page.fill('#s6CmText', 'Комірка пошкоджена');
  await page.click('#s6CmAdd');
  await page.waitForFunction(() => document.querySelectorAll('#s6Badges .s6-badge').length === 2);
  ok('коментар до комірки — окремий значок', true);
  await ev(page, () => __f3d.E.selectObj(null));
  await page.fill('#s6CmText', 'Загальна нотатка по складу');
  await page.click('#s6CmAdd');
  await page.waitForFunction(() => document.querySelectorAll('#s6Badges .s6-badge').length === 3);
  ok('коментар до площадки — значок над будівлею', true);
  await page.click('#s6Comments [data-act="delete"]');
  await page.waitForSelector('#dlgYes');
  await page.click('#dlgYes');
  await page.waitForFunction(() => document.querySelectorAll('#s6Badges .s6-badge').length === 2);
  ok('видалення коментаря з підтвердженням', true);
  // у режимі плану значки теж є
  await ev(page, () => __f3d.E.setView('plan'));
  await page.waitForTimeout(400);
  ok('значки видно і в «Плані»', await ev(page, () => [...document.querySelectorAll('#s6Badges .s6-badge')].some((b) => !b.hidden)));
}

async function t_levels(page) {
  await ev(page, () => __f3d.E.setView('plan'));
  await page.waitForTimeout(400);
  const rack = await ev(page, () => {
    const { S, core } = __f3d;
    const row = S.slots.find((s) => s.template === 'pallet_rack' && s.rotation !== undefined && core.cells.cellsOf(s).length > 6);
    return { id: row.id, x: row.x, y: row.y, code: core.cells.cellsOf(row)[0].code };
  });
  await ev(page, (id) => __f3d.E.selectObj({ kind: 'slot', id }), rack.id);
  await page.click('#s6Down');
  await page.waitForTimeout(200);
  const f1 = await ev(page, () => __f3d.S.ui.focus);
  ok('«↓» заглиблює до виділеного (зона або ряд)', !!f1 && !!(f1.zone || f1.row), JSON.stringify(f1));
  await page.click('#s6Down');
  await page.click('#s6Down');
  const f2 = await ev(page, () => __f3d.S.ui.focus);
  ok('далі: ряд, стелаж, ярус', f2 && f2.row === rack.id && f2.bay != null, JSON.stringify(f2));
  const vis = await ev(page, (id) => { const { V } = __f3d; let hidden = 0; let shown = 0; for (const [k, v] of V.views) { if (k[0] === 's' || k[0] === 'p') { if (v.root.visible) shown++; else hidden++; } } return { hidden, shown, rowVisible: V.views.get('s:' + id).root.visible }; }, rack.id);
  await page.waitForTimeout(200);
  const vis2 = await ev(page, (id) => { const { V } = __f3d; let hidden = 0; let shown = 0; for (const [k, v] of V.views) { if (k[0] === 's' || k[0] === 'p') { if (v.root.visible) shown++; else hidden++; } } return { hidden, shown, rowVisible: V.views.get('s:' + id).root.visible }; }, rack.id);
  ok('фокус ховає решту об’єктів сцени, ряд лишається', vis2.rowVisible === true && vis2.hidden > vis2.shown, JSON.stringify([vis, vis2]));
  ok('крихти: склад › … › ряд › стелаж', (await page.$$('#s6Crumbs button[data-level]')).length >= 3);
  ok('підсвітка комірок стелажа (S.hl «level»)', await ev(page, () => __f3d.S.hl && __f3d.S.hl.kind === 'level' && __f3d.S.hl.codes.size > 0));
  await page.click('#s6Up');
  ok('«↑» піднімає на рівень', await ev(page, () => __f3d.S.ui.focus && __f3d.S.ui.focus.bay == null && __f3d.S.ui.focus.row != null));
  await page.keyboard.press('u');
  ok('клавіша U — рівень вище (ряд → зона/склад)', await ev(page, (id) => !__f3d.S.ui.focus || __f3d.S.ui.focus.row !== id, rack.id));
  await page.click('#s6Reset');
  await page.waitForTimeout(200);
  ok('«⟲» скидає фокус: об’єкти знову видно', await ev(page, () => !__f3d.S.ui.focus && [...__f3d.V.views.values()].every((v) => v.root.visible)));
  // клік по сцені: рівень вибору і повторний клік
  await ev(page, () => { __f3d.S.app.mode = 'view'; __f3d.E.selectObj(null); });
  await ev(page, () => __f3d.E.setView('plan'));
  await page.selectOption('#s6PickSel', 'row');
  const cell = await ev(page, (id) => { const s = __f3d.S.sIdx.get(id); const c = __f3d.core.cells.generateCells(s.template, s.code_prefix, s.x, s.y, s.rotation || 0, s.params, s.overrides || {}, 0)[0]; return { x: c.x, y: c.y, z: c.z0 + c.h / 2, code: c.code }; }, rack.id);
  await ev(page, (c) => __f3d.E.focusOn(c.x, c.y, 16), cell);
  await page.waitForTimeout(400);
  const sp = await screenOf(page, cell.x, cell.y, cell.z);
  await page.mouse.click(sp.x, sp.y);
  await page.waitForTimeout(300);
  const a = await ev(page, () => ({ sel: __f3d.S.sel && __f3d.S.sel.id, cell: __f3d.S.selCell, bay: __f3d.S.ui.selBay }));
  ok('«Клік виділяє: Ряд» — вибрано ряд без комірки', a.sel && a.cell == null && a.bay == null, JSON.stringify(a));
  await page.mouse.click(sp.x, sp.y);
  await page.waitForTimeout(300);
  const b = await ev(page, () => ({ sel: __f3d.S.sel && __f3d.S.sel.id, kind: __f3d.S.sel && __f3d.S.sel.kind, tpl: __f3d.S.sel && __f3d.S.sIdx.get(__f3d.S.sel.id).template }));
  ok('повторний клік піднімає вибір (ряд → зона або склад)', b.sel == null || b.tpl === 'zone', JSON.stringify(b));
  await page.selectOption('#s6PickSel', 'bay');
  await ev(page, (id) => { __f3d.E.selectObj(null); __f3d.E.setActiveLayer(__f3d.S.sIdx.get(id).layer_id); }, rack.id);
  await page.mouse.click(sp.x, sp.y);
  await page.waitForTimeout(300);
  const c = await ev(page, () => ({ sel: __f3d.S.sel && __f3d.S.sel.id, cell: __f3d.S.selCell, bay: __f3d.S.ui.selBay, hl: __f3d.S.hl && __f3d.S.hl.codes.size }));
  ok('«Клік виділяє: Стелаж» — підсвічено комірки стелажа', c.bay && c.bay.index != null && c.hl > 0 && c.cell == null, JSON.stringify(c));
  await page.mouse.click(sp.x, sp.y);
  await page.waitForTimeout(300);
  const d = await ev(page, () => ({ bay: __f3d.S.ui.selBay, hl: __f3d.S.hl }));
  ok('повторний клік: зі стелажа до ряду (підсвітку знято)', d.bay == null && d.hl == null, JSON.stringify(d));
  await page.selectOption('#s6PickSel', 'cell');
  // мініатюра: клік переносить камеру
  await ev(page, () => { __f3d.E.selectObj(null); __f3d.E.setView('plan'); });
  await page.waitForTimeout(300);
  const t0 = await ev(page, () => { const t = __f3d.V.controls.target; return [t.x, t.z]; });
  const box = await page.locator('#s6MiniCanvas').boundingBox();
  await page.mouse.click(box.x + box.width * 0.15, box.y + box.height * 0.2);
  await page.waitForTimeout(300);
  const t1 = await ev(page, () => { const t = __f3d.V.controls.target; return [t.x, t.z]; });
  ok('клік по мініатюрі переносить камеру', Math.abs(t1[0] - t0[0]) > 10 || Math.abs(t1[1] - t0[1]) > 5, JSON.stringify([t0, t1]));
  await page.click('#s6MiniToggle');
  ok('кнопка «Мініатюра» ховає мініатюру', await ev(page, () => document.getElementById('s6Mini').hidden));
  await page.click('#s6MiniToggle');
}

async function t_lang(page) {
  const before = await page.textContent('#btnPublish');
  ok('за замовчуванням UK: «Опублікувати»', /Опублікувати/.test(before), before);
  await page.click('#menu-lang');
  await page.waitForTimeout(300);
  const en = await ev(page, () => ({ pub: document.getElementById('btnPublish').textContent, hist: document.getElementById('btnHistory').textContent, tabs: [...document.querySelectorAll('#ltabs button')].map((b) => b.textContent.trim()), lang: document.getElementById('f3dRoot').lang, btn: document.getElementById('menu-lang').textContent, mode: [...document.querySelectorAll('#modeSeg button')].map((b) => b.textContent) }));
  ok('EN: шапка перекладена («Publish», «History»)', /Publish/.test(en.pub) && /History/.test(en.hist), JSON.stringify(en));
  ok('EN: вкладки (Layers, Places, Catalog, Variants, Comments)', ['Layers', 'Places', 'Catalog', 'Variants', 'Comments'].every((t) => en.tabs.includes(t)), JSON.stringify(en.tabs));
  ok('EN: режими й кнопка мови (UK), lang кореня', en.mode.join() === 'View,Edit' && en.btn === 'UK' && en.lang === 'en', JSON.stringify(en));
  await tab(page, 'variants');
  const ven = await page.textContent('#s6Variants h3');
  ok('EN: вкладка варіантів перекладена (t())', /Layout variants/.test(ven) && /Create from current/.test(ven), ven);
  ok('EN: підказки сцени (title) перекладені DOM-перекладачем', await ev(page, () => /Minimap/.test(document.getElementById('s6Mini').title)));
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
  await page.waitForTimeout(800);
  ok('вибір мови запам’ятовується після перезавантаження', /Publish/.test(await page.textContent('#btnPublish')));
  await page.click('#menu-lang');
  await page.waitForTimeout(300);
  ok('повернення до UK відновлює тексти', /Опублікувати/.test(await page.textContent('#btnPublish')) && await ev(page, () => document.getElementById('f3dRoot').lang === 'uk'));
}

async function t_tours(page, errors) {
  const ids = await ev(page, () => __f3d.core.E.startTour && 1);
  ok('рушій турів підключено', ids === 1);
  await page.click('#menuMore summary').catch(() => {});
  await menu(page, 'tours');
  await page.waitForSelector('#s6Tours');
  const tours = await ev(page, () => [...document.querySelectorAll('#s6Tours [data-tour]')].map((e) => e.dataset.tour));
  ok('список: тур новачка й 11 тематичних', tours.length === 12 && tours[0] === 'welcome' && ['basic', 'rack', 'import', 'scratch', 'address', 'putaway', 'apply', 'find', 'labels', 'docs', 'team'].every((x) => tours.includes(x)), JSON.stringify(tours));
  await page.click('#s6Tours [data-tour="welcome"] [data-act="start"]');
  await page.waitForSelector('#s6TourCard');
  ok('тур новачка: «Крок 1 / 13», є підсвічування', /Крок 1 \/ 13/.test(await page.textContent('#s6TourCard')) && !(await ev(page, () => document.getElementById('s6TourHole').hidden)));
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(150);
  ok('→ — наступний крок (рівні)', /Крок 2 \/ 13/.test(await page.textContent('#s6TourCard')));
  await page.keyboard.press('ArrowLeft');
  ok('← — назад', /Крок 1 \/ 13/.test(await page.textContent('#s6TourCard')));
  for (let i = 0; i < 2; i++) await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(150);
  ok('крок «дія»: є «Показати мені»', !!(await page.$('#s6TourShow')));
  await page.click('#s6TourShow');
  await page.waitForTimeout(200);
  ok('«Показати мені» виконало дію й позначило ✓', /✓/.test(await page.textContent('#s6TourCard')) && await ev(page, () => __f3d.S.ui.leftTab === 'layers'));
  const covered = await ev(page, () => { const c = document.getElementById('s6TourCard').getBoundingClientRect(); const h = document.getElementById('s6TourHole').getBoundingClientRect(); return !(c.right < h.left || c.left > h.right || c.bottom < h.top || c.top > h.bottom); });
  ok('картка не закриває підсвічений елемент', covered === false);
  for (let i = 0; i < 20; i++) { const done = await ev(page, () => !document.getElementById('s6TourCard')); if (done) break; await page.keyboard.press('ArrowRight'); await page.waitForTimeout(60); }
  await page.waitForFunction(() => !document.getElementById('s6TourCard'));
  ok('після 13-го кроку тур завершується й запам’ятовується «пройдено»', await ev(page, () => localStorage.getItem('f3d_tour_done:welcome') === '1'));
  await ev(page, () => __f3d.E.startTour('find'));
  await page.waitForSelector('#s6TourCard');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.getElementById('s6TourCard'));
  ok('Esc закриває тур', true);
  // тур, що змінює дані: навчальна копія
  const base = await nSlots(page);
  await ev(page, () => __f3d.E.startTour('rack'));
  await page.waitForSelector('#s6TourCard');
  await page.waitForSelector('#s6Train:not([hidden])');
  ok('тур «rack» створив навчальну копію (панель «Навчальна копія»)', true);
  for (let i = 0; i < 2; i++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(100); }
  await page.click('#s6TourShow');
  await page.waitForTimeout(500);
  ok('«Показати мені» поставило стелаж у копії', await ev(page, () => __f3d.S.slots.some((s) => s.code_prefix === 'TOUR-R1')));
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(150);
  await page.click('#s6TourShow');
  await page.waitForTimeout(300);
  ok('«Показати мені» змінило яруси на 3', await ev(page, () => __f3d.S.slots.find((s) => s.code_prefix === 'TOUR-R1').params.levels === 3));
  await page.keyboard.press('Escape');
  await page.waitForSelector('#dlgYes');
  ok('перерваний тур пропонує «Залишити зміни» чи «Скасувати»', /Залишити зміни/.test(await page.textContent('dialog')));
  await page.click('dialog [class*="fbtn"]:not(.primary)');
  await page.waitForFunction((n) => __f3d.S.slots.length === n && !document.querySelector('#s6Train:not([hidden])'), base, { timeout: 8000 });
  ok('«Скасувати»: стелаж туру зник, робочий варіант повернувся', true);
  // адресне посилання
  await page.evaluate(() => { location.hash = '#tour-basic'; });
  await page.waitForSelector('#s6TourCard');
  ok('посилання #tour-basic запускає тур', /Крок 1 \/ 6/.test(await page.textContent('#s6TourCard')));
  await page.keyboard.press('Escape');
  // інструкція
  await menu(page, 'help');
  await page.waitForSelector('#s6Help');
  const topics = await page.$$('#s6Help nav button');
  ok('«Інструкція»: 36 тем', topics.length === 36, String(topics.length));
  await page.click('#s6Help nav button[data-topic="locks"]');
  ok('вибір теми показує її текст', /Блокування зон/.test(await page.textContent('#s6HelpBody h3')));
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('dialog[open]'));
  ok('Esc повертає до моделі', true);
  await menu(page, 'help');
  await page.click('#s6HelpBack');
  await page.waitForFunction(() => !document.querySelector('dialog[open]'));
  ok('«← До моделі» закриває інструкцію', true);
  // EN
  await page.click('#menu-lang');
  await menu(page, 'help');
  await page.waitForSelector('#s6Help');
  ok('інструкція англійською', /Getting started/.test(await page.textContent('#s6HelpBody h3')));
  await page.keyboard.press('Escape');
  await ev(page, () => __f3d.E.startTour('welcome'));
  await page.waitForSelector('#s6TourCard');
  ok('тур англійською: «Step 1 / 13»', /Step 1 \/ 13/.test(await page.textContent('#s6TourCard')), await page.textContent('#s6TourCard'));
  await page.keyboard.press('Escape');
  await page.click('#menu-lang');
}

async function t_invite(page) {
  await ev(page, () => localStorage.clear());
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
  await page.waitForSelector('#s6TourInvite', { timeout: 4000 });
  ok('при першому вході — пропозиція «Тур новачка» (13 кроків)', /13 кроків/.test(await page.textContent('#s6TourInvite')));
  await page.click('#s6InviteYes');
  await page.waitForSelector('#s6TourCard');
  ok('«Пройти тур» запускає тур новачка', /Крок 1 \/ 13/.test(await page.textContent('#s6TourCard')));
  await page.keyboard.press('Escape');
  await ev(page, () => localStorage.clear());
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
  await page.waitForSelector('#s6TourInvite', { timeout: 4000 });
  await page.click('#s6InviteNo');
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
  await page.waitForTimeout(1200);
  ok('«Не показувати» — пропозиції більше немає', !(await page.$('#s6TourInvite')));
}

async function t_history(page) {
  await page.click('#btnHistory');
  await page.waitForSelector('#s6History');
  ok('історія: список версій із позначкою «активна»', (await page.$$('#s6History .ver')).length >= 1 && /активна/.test(await page.textContent('#s6History')));
  await page.click('#s6VerCheckpoint');
  await page.waitForSelector('#s6VerNote');
  await page.fill('#s6VerNote', 'Перед змінами');
  await page.click('#s6VerNoteOk');
  await page.waitForFunction(() => /Перед змінами/.test(document.getElementById('s6History').textContent));
  ok('«Зберегти контрольну точку…» додає запис без публікації', !!(await page.$('#s6History [data-kind="checkpoint"]')));
  const active = await ev(page, () => __f3d.S.site.active_version.n);
  ok('активна версія не змінилась', await ev(page, (n) => __f3d.S.site.active_version.n === n, active));
  await page.click('#s6History [data-kind="checkpoint"] [data-act="view"]');
  await page.waitForSelector('#s6VerView');
  const svg = await ev(page, () => [...document.querySelectorAll('#s6VerView svg')].map((s) => s.querySelectorAll('polygon').length));
  ok('«Переглянути»: дві схеми (версія й чернетка) з об’єктами', svg.length === 2 && svg[0] > 50 && svg[1] > 50, JSON.stringify(svg));
  const mrows = await ev(page, () => [...document.querySelectorAll('#s6VerView tbody tr')].map((r) => r.dataset.key));
  ok('«Переглянути»: цифри п’яти показників поряд із чернеткою', mrows.length === 5);
  await page.keyboard.press('Escape');
  await page.waitForSelector('#s6History');
  await page.click('#s6History [data-kind="checkpoint"] [data-act="note"]');
  await page.waitForSelector('#s6VerNote');
  await page.fill('#s6VerNote', 'Інша нотатка');
  await page.click('#s6VerNoteOk');
  await page.waitForFunction(() => /Інша нотатка/.test(document.getElementById('s6History').textContent));
  ok('нотатку до версії змінено', true);
  // відновлення: спершу автокопія
  await addRack(page, 'S6-H1', 50, 30);
  await page.waitForTimeout(900);
  const before = await ev(page, () => __f3d.S.versions.length);
  await page.click('#s6History [data-kind="checkpoint"] [data-act="restore"]');
  await page.waitForSelector('#dlgYes');
  await page.click('#dlgYes');
  await page.waitForFunction(() => !document.querySelector('dialog[open]'), null, { timeout: 8000 });
  await page.waitForTimeout(600);
  ok('«Відновити»: чернетку повернуто, правка після точки зникла', await ev(page, () => !__f3d.S.slots.some((s) => s.code_prefix === 'S6-H1')));
  const after = await ev(page, () => __f3d.S.versions.map((v) => v.note));
  ok('перед відновленням створено автокопію (окрему контрольну точку)', after.some((n) => /Автокопія перед відновленням/.test(n)), JSON.stringify(after));
  ok('кількість записів історії зросла', after.length > before);
}

async function t_locks(page) {
  // прототип блокування не емулює; логіку перевіряємо на підміненому адаптері «сервера»
  await ev(page, () => {
    const { adapter, core, S } = __f3d;
    const exp = new Date(Date.now() + 240000).toISOString().replace('T', ' ').slice(0, 19);
    const me = { zone_uid: '', user: 'Я', mine: true, expires_at: exp };
    window.__locks = [];
    adapter.capabilities.locks = true;
    core.setCapabilities(adapter.capabilities);
    adapter.locks = async (req) => {
      if (req.op === 'acquire') {
        const foreign = window.__locks.find((l) => l.zone_uid === req.zone_uid && !l.mine);
        if (foreign) throw Object.assign(new Error('Зону «Z-FG» редагує ' + foreign.user + ' до 14:35.'), { code: 'locked', lock: foreign, locks: window.__locks });
        if (!window.__locks.find((l) => l.zone_uid === req.zone_uid)) window.__locks.push({ ...me, zone_uid: req.zone_uid });
      } else if (req.op === 'release') {
        window.__locks = window.__locks.filter((l) => !l.mine || (req.zone_uid && l.zone_uid !== req.zone_uid));
      }
      return { ok: true, locks: window.__locks.map((l) => ({ ...l })), ttl: 300, heartbeat: 60 };
    };
    S.app.mode = 'edit';
    window.__f3d.E.renderAll();
  });
  const racks = await ev(page, () => { const { S, E } = __f3d; const r = S.slots.find((s) => s.template === 'pallet_rack' && S.sIdx.get(E.zoneKeyOf(s)) && S.sIdx.get(E.zoneKeyOf(s)).template === 'zone'); return { rack: r.id, key: E.zoneKeyOf(r) }; });
  await ev(page, (id) => __f3d.E.selectObj({ kind: 'slot', id }), racks.rack);
  await page.waitForFunction(() => window.__locks.length === 1, null, { timeout: 4000 });
  ok('вибір об’єкта в режимі редагування бере зону в оренду', await ev(page, (k) => window.__locks[0].zone_uid === k, racks.key));
  await page.waitForSelector('#s6LockBanner[data-mine="1"]');
  ok('банер «Зона заблокована за вами до …»', /за вами до \d\d:\d\d/.test(await page.textContent('#s6LockBanner')));
  await page.waitForSelector('#s6Locks .s6-lockb[data-mine="1"]');
  ok('значок оренди на сцені — зелений, «Ви»', /Ви/.test(await page.textContent('#s6Locks .s6-lockb')));
  // чужа оренда
  await ev(page, (k) => { window.__locks = [{ zone_uid: k, user: 'Іван Петренко', mine: false, expires_at: new Date(Date.now() + 200000).toISOString().replace('T', ' ').slice(0, 19) }]; __f3d.E.selectObj(null); }, racks.key);
  await ev(page, () => __f3d.E.refreshLocks());
  await ev(page, (id) => __f3d.E.selectObj({ kind: 'slot', id }), racks.rack);
  await page.waitForSelector('#s6LockBanner[data-mine="0"]');
  ok('чужа зона: банер «редагує Іван Петренко до …»', /редагує Іван Петренко до \d\d:\d\d/.test(await page.textContent('#s6LockBanner')));
  ok('чужа зона: toast із повідомленням', /Іван Петренко/.test(await page.textContent('#toast')));
  ok('значок чужої зони — червоний', await ev(page, () => !!document.querySelector('#s6Locks .s6-lockb[data-mine="0"]')));
  // вихід з режиму редагування знімає свої оренди
  await ev(page, (k) => { window.__locks = [{ zone_uid: k, user: 'Я', mine: true, expires_at: new Date(Date.now() + 200000).toISOString().replace('T', ' ').slice(0, 19) }]; }, racks.key);
  await ev(page, (id) => { __f3d.E.selectObj(null); __f3d.E.selectObj({ kind: 'slot', id }); }, racks.rack);
  await page.waitForTimeout(300);
  await page.click('#modeSeg [data-mode="view"]');
  await page.waitForFunction(() => window.__locks.length === 0, null, { timeout: 4000 });
  ok('перехід у «Перегляд» знімає оренду', true);
}

(async () => {
  const suites = { chrome: t_chrome, варіанти: t_variants, коментарі: t_comments, рівні: t_levels, мова: t_lang, тури: t_tours, запрошення: t_invite, історія: t_history, блокування: t_locks };
  const only = process.argv[2];
  for (const [name, fn] of Object.entries(suites)) {
    if (only && only !== name) continue;
    const { browser, ctx, page, errors } = await launch({ viewport: { width: 1440, height: 900 } });
    if (name === 'запрошення') {
      await ctx.addInitScript(() => Object.defineProperty(navigator, 'webdriver', { get: () => false }));
    }
    try { await open(page); await fn(page, errors); } catch (e) { ok(name + ': виняток ' + e.message, false, (e.stack || '').split('\n').slice(0, 4).join(' | ')); }
    await browser.close();
  }
  const bad = res.filter((x) => !x).length;
  console.log(`\nІТОГО S6 прототип: ${res.length - bad} passed, ${bad} failed`);
  process.exit(bad ? 1 : 0);
})();
