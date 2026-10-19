// Слайс S1 «Структура місця» у прототипі: адресація (F01), каталог 50 типів (F08), пресети й бібліотека (F09-06/07).
// Запуск: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node build/constructor/proto/test_s1.js (після python3 build/constructor/proto/build.py)
const { launch, open } = require('./harness');
const res = [];
const ok = (name, cond, extra) => { res.push(cond); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? ' :: ' + extra : '')); };

async function prepare(page) {
  // активний шар, що допускає стелажі й зони; зона 20×20 у його куті
  return await page.evaluate(() => {
    const { S, E } = __f3d;
    const ly = S.layers.find((l) => l.slot_types.includes('pallet_rack') && l.slot_types.includes('floor_spot') && l.slot_types.includes('zone'))
      || S.layers.find((l) => l.slot_types.includes('pallet_rack'));
    if (!ly.slot_types.includes('zone')) ly.slot_types.push('zone');
    if (!ly.slot_types.includes('floor_spot')) ly.slot_types.push('floor_spot');
    S.ui.layer = ly.id;
    // чистий шар: прибираємо наявні місця шару, щоб рахунки в тесті були точними
    S.slots = S.slots.filter((s) => s.layer_id !== ly.id);
    S.placements = S.placements.filter((p) => p.layer_id !== ly.id);
    S.slots.push({ id: 'zt1', rid: null, etag: null, layer_id: ly.id, template: 'zone', code_prefix: 'ZT1', x: 30, y: 12, rotation: 0, params: { length: 40, width: 20, title: 'Тестова зона', color: '#9fb7c9' }, overrides: {}, parent_location_id: null });
    E.commit({});
    E.renderAll();
    return ly.id;
  });
}

async function t_catalog(page, errors) {
  await prepare(page);
  await page.click('#ltabs button[data-tab="types"]');
  ok('вкладка «Типи» є в лівій панелі', await page.locator('#btnOpenCatalog').count() === 1);
  await page.click('#btnOpenCatalog');
  await page.waitForSelector('dialog[open] #catalogGrid [data-type]');
  const cnt = { cards: await page.locator('#catalogGrid [data-type]').count() };
  ok('каталог: діалог зареєстровано', await page.evaluate(() => __f3d.core.registries.dialogs.has('catalog')));
  ok('каталог: за умовчанням показано ● і ○ (не —)', cnt.cards > 20 && cnt.cards < 50, String(cnt.cards));
  await page.uncheck('#catalogRel');
  ok('каталог: без фільтра — усі 50 типів', await page.locator('#catalogGrid [data-type]').count() === 50);
  await page.fill('#catalogSearch', 'gitterbox');
  ok('каталог: пошук за назвою', await page.locator('#catalogGrid [data-type]').count() === 1);
  await page.fill('#catalogSearch', '');
  await page.selectOption('dialog select[aria-label="Група"]', 'special');
  ok('каталог: фільтр за групою (8 спеціальних)', await page.locator('#catalogGrid [data-type]').count() === 8);
  await page.selectOption('dialog select[aria-label="Група"]', '');
  ok('каталог: кожна картка має SVG-превʼю форми', await page.evaluate(() => [...document.querySelectorAll('#catalogGrid [data-type]')].every((c) => c.querySelector('svg line'))));
  // картка R02: параметри, «Додати на план» у зону
  await page.click('#catalogGrid [data-type="r02"]');
  await page.waitForSelector('#btnAddToPlan');
  ok('картка: опис і габарит типу', (await page.textContent('#catalogDetail')).includes('Габарит'));
  await page.click('#btnAddToPlan');
  await page.selectOption('#planBox select', 'zt1');
  await page.fill('[data-f="plan-count"]', '3');
  await page.click('#btnPlanGo');
  await page.waitForTimeout(400);
  const placed = await page.evaluate(() => __f3d.S.slots.filter((s) => s.type_id === 'r02').map((s) => ({ p: s.code_prefix, deep: s.params.deep, x: s.x, y: s.y })));
  ok('«Додати на план»: 3 місця типу R02 у зоні з типом і параметрами типу', placed.length === 3 && placed.every((s) => s.deep === 2 && s.p.startsWith('R02-')), JSON.stringify(placed));
  ok('«Додати на план»: місця всередині зони (x 10…50, y 2…22)', placed.every((s) => s.x >= 10 && s.x <= 50 && s.y >= 2 && s.y <= 22));
  ok('«Додати на план»: префікси унікальні', new Set(placed.map((s) => s.p)).size === 3);
  // «Додати в проєкт»: режим розміщення зі стартовими параметрами типу
  await page.click('#ltabs button[data-tab="types"]');
  await page.click('#btnOpenCatalog');
  await page.waitForSelector('dialog[open] #catalogGrid [data-type]');
  await page.click('#catalogGrid [data-type="r11"]');
  await page.click('#btnAddToProject');
  await page.waitForTimeout(300);
  const pl = await page.evaluate(() => ({ placing: !!__f3d.V.placing, spec: __f3d.V.placing && __f3d.V.placing.spec }));
  ok('«Додати в проєкт»: режим розміщення типу R11 (полицевий стелаж)', pl.placing && pl.spec.template === 'shelf' && pl.spec.type_id === 'r11', JSON.stringify(pl.spec || {}).slice(0, 120));
  await page.keyboard.press('Escape');
  // «У проєкті»: тип з'явився в таблиці
  await page.click('#ltabs button[data-tab="types"]');
  ok('«У проєкті»: рядок R02 з 3 місцями', (await page.textContent('#projectTypes [data-type="r02"]')).includes('3 міс.'));
  // будівельний тип ворота: лише довідка
  await page.click('#btnOpenCatalog');
  await page.waitForSelector('dialog[open] #catalogGrid [data-type]');
  await page.click('#catalogGrid [data-type="bf03"]');
  ok('BF03 «Ворота / док» — довідка без кнопок додавання', await page.locator('#btnAddToProject').count() === 0);
  await page.keyboard.press('Escape');
  ok('каталог: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_type_block(page) {
  const id = await page.evaluate(() => __f3d.S.slots.find((s) => s.type_id === 'r02').id);
  await page.evaluate((id) => __f3d.selectObj({ kind: 'slot', id }), id);
  await page.waitForSelector('#typeBlock');
  ok('блок «Тип»: поточний тип R02 і поле «Глибина в палетах»', (await page.textContent('#typeBlock')).includes('як у типу') && await page.locator('#typeBlock [data-f="p.deep"]').count() === 1);
  await page.fill('#typeBlock [data-f="p.deep"]', '3');
  await page.waitForTimeout(200);
  const changed = await page.evaluate((id) => __f3d.S.sIdx.get(id).params.deep, id);
  ok('«Конструкція ряду»: параметр ряду змінено на 3', changed === 3);
  ok('блок «Тип»: показано, що ряд відрізняється від типу', (await page.textContent('#typeBlock')).includes('змінено параметрів відносно типу'));
  await page.click('#btnAsType');
  const back = await page.evaluate((id) => __f3d.S.sIdx.get(id).params.deep, id);
  ok('«Як у типу» повертає параметри типу (deep=2)', back === 2);
  // форма 3D: каркас для стелажа з deep/double_sided будується (не порожній)
  const frame = await page.evaluate((id) => { const s = __f3d.S.sIdx.get(id); const d = __f3d.core.live.slotDims(s); return __f3d.core.registries.shapes.get('pallet_rack').frame(__f3d.core.cells.normalizeParams('pallet_rack', s.params), d).length; }, id);
  ok('3D: каркас стелажа з новими параметрами не порожній', frame > 0, String(frame));
}

async function t_addr(page) {
  await page.evaluate(() => { __f3d.S.sel = null; __f3d.E.renderRight(); });
  await page.waitForSelector('#addrSite');
  const before = await page.evaluate(() => __f3d.cellsOf(__f3d.S.slots.find((s) => s.type_id === 'r02')).slice(0, 2).map((c) => c.code));
  ok('адресація: за умовчанням legacy-коди (ПРЕФІКС-B01-L1)', /-B01-L1$/.test(before[0]), before.join());
  // пресет «Зона-ряд-секція-ярус» + перегляд
  await page.selectOption('#addrSite select[aria-label="Режим адресації"]', 'own');
  await page.selectOption('#addrSite select[aria-label="Пресет шаблону"]', 'zone_row_bay_level');
  // у проєкті прикладу багато шарів і рядів: шаблон без {prefix} дає повтори кодів між шарами — це має блокувати збереження
  await page.waitForSelector('#addrSite [data-role="addr-dups"]');
  ok('адресація: повтори кодів між шарами блокують «Застосувати» (потрібен {prefix} чи зона)', await page.locator('#btnAddrApply').isDisabled());
  await page.fill('#addrSite [data-f="addr-tpl"]', '{prefix} {zone} {row} {bay} {level}');
  await page.waitForFunction(() => !document.querySelector('#addrSite [data-role="addr-dups"]'));
  const first = await page.textContent('#addrSite [data-role="addr-first"]');
  ok('адресація: перегляд показує перші коди за шаблоном', /-\d\d-\d ·/.test(first), first.slice(0, 80));
  ok('адресація: перегляд показує останній код і кількість', (await page.textContent('#addrSite [data-role="addr-last"]')).includes('усього'));
  ok('адресація: «Зміниться кодів» > 0', /Зміниться кодів: \d+/.test(await page.textContent('#addrSite [data-role="addr-changed"]')));
  // шаблон без {row}: коди рядів збігаються → повтори, застосувати не можна
  await page.fill('#addrSite [data-f="addr-tpl"]', '{bay} {level}');
  await page.waitForSelector('#addrSite [data-role="addr-dups"]');
  ok('адресація: список повторів із переходом до місця, «Застосувати» вимкнено', await page.locator('#addrSite [data-role="addr-dups"] a').count() > 0 && await page.locator('#btnAddrApply').isDisabled());
  await page.fill('#addrSite [data-f="addr-tpl"]', 'abc');
  ok('адресація: хибний шаблон — повідомлення про помилку', (await page.textContent('#addrSite [data-role="addr-preview"]')).includes('сегмент'));
  await page.fill('#addrSite [data-f="addr-tpl"]', '{prefix} {zone} {row} {bay} {level}');
  await page.waitForFunction(() => !document.querySelector('#btnAddrApply').disabled);
  await page.click('#btnAddrApply');
  await page.waitForTimeout(500);
  const after = await page.evaluate(() => ({ addr: __f3d.S.site.addr.tpl, codes: __f3d.cellsOf(__f3d.S.slots.find((s) => s.type_id === 'r02')).slice(0, 2).map((c) => c.code) }));
  ok('адресація застосована: S.site.addr і коди комірок місця', after.addr === '{prefix} {zone} {row} {bay} {level}' && after.codes[0] === 'R02-1-A-01-01-1', JSON.stringify(after));
  // номер ряду закріплено у нових місцях; власні налаштування місця
  const id = await page.evaluate(() => __f3d.S.slots.find((s) => s.type_id === 'r02').id);
  await page.evaluate((id) => __f3d.selectObj({ kind: 'slot', id }), id);
  await page.waitForSelector('#addrSlot');
  ok('місце: номер ряду показано, коди місця перелічено', await page.locator('#addrSlot [data-role="addr-row-no"]').count() === 1 && (await page.textContent('#addrSlot [data-role="addr-slot-codes"]')).includes('R02-1-A-'));
  await page.click('#btnRowPin');
  const pinned = await page.evaluate((id) => __f3d.S.sIdx.get(id).addr, id);
  ok('«Закріпити номер» пише row_no у addr місця', pinned && pinned.row_no >= 1, JSON.stringify(pinned));
  // зона: код замість номера → коди місць у зоні
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'zt1' }));
  await page.waitForSelector('#addrSlot');
  await page.fill('#addrSlot [data-f="addr-zone-code"]', 'ZT');
  await page.waitForTimeout(150);
  await page.click('#btnAddrSlotApply');
  await page.waitForTimeout(500);
  const zc = await page.evaluate(() => __f3d.cellsOf(__f3d.S.slots.find((s) => s.type_id === 'r02')).slice(0, 1).map((c) => c.code));
  ok('зона: «Код зони замість номера» змінює коди місць зони', zc[0] === 'R02-1-ZT-01-01-1', zc.join());
  // глибина «комірка» на площадці → яруси діляться на локації
  await page.evaluate(() => { __f3d.S.sel = null; __f3d.E.renderRight(); });
  await page.waitForSelector('#addrSite');
  await page.evaluate(() => { __f3d.S.slots.find((s) => s.type_id === 'r02').params.cells_per_level = 3; __f3d.core.cells.clearCellsCache(); });
  const n1 = await page.evaluate(() => __f3d.core.cells.cellCount(__f3d.S.slots.find((s) => s.type_id === 'r02')));
  await page.selectOption('#addrSite select[aria-label="Глибина локацій"]', 'cell');
  await page.fill('#addrSite [data-f="addr-tpl"]', '{prefix} {zone} {row} {bay} {level} {pos}');
  await page.waitForFunction(() => !document.querySelector('#btnAddrApply').disabled);
  await page.click('#btnAddrApply');
  await page.waitForTimeout(500);
  const n2 = await page.evaluate(() => { const s = __f3d.S.slots.find((q) => q.type_id === 'r02'); return { n: __f3d.core.cells.cellCount(s), p: s.params.cells_per_level || 1 }; });
  ok('глибина «комірка»: кожен ярус ділиться на 3 локації (код яруса-1…3)', n2.p === 3 && n2.n === n1 * 3, `${n1} → ${n2.n} (×${n2.p})`);
}

async function t_presets(page, errors) {
  await page.evaluate(() => { __f3d.S.site.addr = {}; __f3d.S.site.depth_mode = 'level'; __f3d.S.slots.forEach((s) => { if (s.template !== 'zone') { delete s.addr; } }); __f3d.core.cells.clearCellsCache(); __f3d.E.commit({}); });
  const id = await page.evaluate(() => __f3d.S.slots.find((s) => s.type_id === 'r02').id);
  await page.evaluate((id) => __f3d.selectObj({ kind: 'slot', id }), id);
  await page.waitForSelector('#presetBlock');
  await page.click('#btnPresetSave');
  await page.waitForSelector('dialog[open] [data-f="preset-name"]');
  await page.fill('dialog [data-f="preset-name"]', 'Мій ряд R02');
  await page.click('#btnPresetSaveGo');
  await page.waitForTimeout(500);
  const saved = await page.evaluate(async () => { const lib = await __f3d.adapter.library({ op: 'list' }); return lib.presets.map((p) => ({ n: p.name, k: p.kind, t: p.data.slot.template, deep: p.data.slot.params.deep, tc: p.data.slot.type_code })); });
  ok('пресет «ряд» збережено в бібліотеці (тип, параметри)', saved.length === 1 && saved[0].k === 'row' && saved[0].deep === 2 && saved[0].tc === 'r02', JSON.stringify(saved));
  // секція зі стелажа
  await page.click('#btnPresetSave');
  await page.waitForSelector('dialog[open] [data-f="preset-name"]');
  await page.fill('dialog [data-f="preset-name"]', 'Секція R02');
  await page.selectOption('dialog select[aria-label="Вид шаблону"]', 'section');
  await page.click('#btnPresetSaveGo');
  await page.waitForTimeout(500);
  // вставка: зона → ряд ×2
  await page.evaluate(() => __f3d.selectObj({ kind: 'slot', id: 'zt1' }));
  await page.waitForSelector('#presetBlock');
  const before = await page.evaluate(() => __f3d.S.slots.length);
  await page.click('#btnPresetInsert');
  await page.waitForSelector('dialog[open] #presetList [data-preset]');
  await page.locator('#presetList [data-preset]', { hasText: 'Мій ряд R02' }).click();
  await page.fill('[data-f="preset-count"]', '2');
  await page.click('#btnPresetInsertGo');
  await page.waitForTimeout(500);
  const after = await page.evaluate(() => __f3d.S.slots.filter((s) => s.type_id === 'r02').length);
  ok('зона → ряд ×2: у зоні з\'явилось 2 нових ряди типу R02', after === 5 && (await page.evaluate(() => __f3d.S.slots.length)) === before + 2, `r02=${after}`);
  // ряд → секція
  const rid = await page.evaluate(() => __f3d.S.slots.filter((s) => s.type_id === 'r02')[0].id);
  const bays0 = await page.evaluate((id) => __f3d.S.sIdx.get(id).params.bays, rid);
  await page.evaluate((id) => __f3d.selectObj({ kind: 'slot', id }), rid);
  await page.waitForSelector('#presetBlock');
  await page.click('#btnPresetInsert');
  await page.waitForSelector('dialog[open] #presetList [data-preset]');
  await page.fill('[data-f="preset-count"]', '2');
  await page.click('#btnPresetInsertGo');
  await page.waitForTimeout(400);
  const bays1 = await page.evaluate((id) => __f3d.S.sIdx.get(id).params.bays, rid);
  ok('ряд → секція ×2: кількість секцій ряду збільшилась', bays1 === bays0 + 2, `${bays0} → ${bays1}`);
  // бібліотека: діалог показує пресети; перейменування
  await page.click('#menuMore summary');
  await page.click('#menu-library');
  await page.waitForSelector('dialog[open] #libPresets [data-preset]');
  ok('бібліотека: діалог показує 2 шаблони', await page.locator('#libPresets [data-preset]').count() === 2);
  await page.keyboard.press('Escape');
  // власний тип у бібліотеку з каталогу
  await page.click('#ltabs button[data-tab="types"]');
  await page.click('#btnOpenCatalog');
  await page.waitForSelector('dialog[open] #catalogGrid [data-type]');
  await page.click('#catalogGrid [data-type="r11"]');
  await page.click('#btnToLibrary');
  await page.waitForTimeout(400);
  const types = await page.evaluate(async () => (await __f3d.adapter.library({ op: 'list' })).types.map((t) => ({ c: t.code, custom: t.is_custom, tpl: t.template })));
  ok('«У бібліотеку»: власна копія типу R11 (каталог не змінено)', types.length === 1 && types[0].custom && types[0].tpl === 'shelf');
  await page.keyboard.press('Escape');
  // «+ Новий тип» з власними параметрами → бібліотека → «У проєкті»
  await page.click('#ltabs button[data-tab="types"]');
  await page.click('#btnNewType');
  await page.waitForSelector('dialog[open] [data-f="type-name"]');
  await page.fill('dialog [data-f="type-name"]', 'Тестовий стелаж');
  await page.fill('dialog [data-f="p.bays"]', '9');
  await page.click('#btnTypeSave');
  await page.waitForTimeout(400);
  const custom = await page.evaluate(async () => (await __f3d.adapter.library({ op: 'list' })).types.filter((t) => t.name === 'Тестовий стелаж').map((t) => ({ bays: t.params.bays, custom: t.is_custom })));
  ok('«+ Новий тип»: власний тип у бібліотеці з параметрами', custom.length === 1 && custom[0].bays === 9 && custom[0].custom, JSON.stringify(custom));
  await page.click('#ltabs button[data-tab="types"]');
  ok('«У проєкті» показує власні типи бібліотеки', await page.locator('#projectTypes .it', { hasText: 'Тестовий стелаж' }).count() === 1);
  // зміна розміру типу пересобирає всі місця типу
  await page.locator('#projectTypes [data-type="r02"] button[aria-label="Змінити розмір типу"]').click();
  await page.waitForSelector('dialog[open] [data-f="size-bay_width"]');
  await page.fill('dialog [data-f="size-bay_width"]', '3.2');
  await page.click('#btnResizeGo');
  await page.waitForTimeout(400);
  const widths = await page.evaluate(() => __f3d.S.slots.filter((s) => s.type_id === 'r02').map((s) => s.params.bay_width));
  ok('розмір типу: bay_width=3.2 в усіх місцях R02', widths.length >= 3 && widths.every((w) => w === 3.2), JSON.stringify(widths));
  // бібліотека: видалення шаблону (артефакт = менеджер)
  await page.click('#menuMore summary');
  await page.click('#menu-library');
  await page.waitForSelector('dialog[open] #libPresets [data-preset]');
  await page.locator('#libPresets [data-preset]').first().locator('button[aria-label="Видалити шаблон"]').click();
  await page.waitForTimeout(300);
  ok('бібліотека: шаблон видалено', await page.locator('#libPresets [data-preset]').count() === 1);
  await page.keyboard.press('Escape');
  ok('пресети: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

(async () => {
  const { browser, page, errors } = await launch();
  await open(page);
  await t_catalog(page, errors);
  await t_type_block(page);
  await t_addr(page);
  await t_presets(page, errors);
  await browser.close();
  const bad = res.filter((x) => !x).length;
  console.log(`\nІТОГО S1 прототип: ${res.length - bad} passed, ${bad} failed`);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
