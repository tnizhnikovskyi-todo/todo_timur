// Слайс S4 «Структура з Odoo, файли» у прототипі: імпорт структури складу (F10-05, F11-02/03), розбір кодів і лоток «Не розміщено» (F10-01…04),
// імпорт CSV (cp1251, «;») й XLSX, експорт CSV/XLSX «туди-назад» (F11-01/04), авторозкладка (F17), «Оновити з Odoo» й розбіжності (F02-09/12).
// Запуск: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node build/constructor/proto/test_s4.js [імпорт|файли|лоток|розкладка|розбіжності|правила]
// (після python3 build/constructor/proto/build.py)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { launch, open } = require('./harness');
const res = [];
const ok = (name, cond, extra) => { res.push(!!cond); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra !== undefined && !cond ? ' :: ' + extra : '')); };
const DL = fs.mkdtempSync(path.join(os.tmpdir(), 's4dl-'));

const ev = (page, fn, arg) => page.evaluate(fn, arg);
/** Усі коди комірок проєкту (справжній cellsOf) — відсортований масив. */
const codes = (page) => ev(page, () => [...new Set(__f3d.S.slots.flatMap((s) => __f3d.cellsOf(s).filter((c) => !c.disabled).map((c) => c.code)))].sort());
const toast = async (page) => (await page.textContent('#toast').catch(() => '')) || '';
const menu = async (page, key) => {
  await page.evaluate(() => { const d = document.getElementById('menuMore'); if (d) d.open = true; });
  await page.click('#menu-' + key);
};
/** Кодування Windows-1251 для кирилиці (ASCII без змін) — файл «з Excel» у CSV. */
const CP_EXTRA = { 'Ї': 0xaf, 'ї': 0xbf, 'І': 0xb2, 'і': 0xb3, 'Є': 0xaa, 'є': 0xba, 'Ґ': 0xa5, 'ґ': 0xb4, '«': 0xab, '»': 0xbb };
const cp1251 = (text) => Buffer.from([...text].map((ch) => { const c = ch.charCodeAt(0); return c < 128 ? c : CP_EXTRA[ch] || (c >= 0x410 && c <= 0x44f ? c - 0x410 + 0xc0 : 0x3f); }));

/** Імпорт структури з «Odoo» прототипа (приклад стрічки) у НОВИЙ проєкт; за потреби — з маскою за зразками. */
async function importSample(page, { suggest = true } = {}) {
  await ev(page, () => { const { S } = __f3d; S.rights = { ...S.rights, is_manager: true, roles: ['manager'] }; });
  await ev(page, () => __f3d.E.runDialog('importLocations'));
  await page.waitForSelector('#impOdoo');
  await page.click('#impOdoo');
  await page.waitForSelector('#impCells');
  if (suggest) {
    await page.waitForSelector('[data-role="suggest"] button');
    await page.click('[data-role="suggest"] button');
  }
  await page.click('#impGo');
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  await page.waitForTimeout(500);
}

async function t_import(page, errors) {
  // меню «Ще»: усі нові пункти
  await page.evaluate(() => { document.getElementById('menuMore').open = true; });
  const ids = await ev(page, () => ['importLocations', 'exportLocations', 'parseCodes', 'syncOdoo', 'autolayout'].map((k) => !!document.getElementById('menu-' + k)));
  ok('меню «Ще»: Імпорт, Експорт, Розбір кодів, Оновити з Odoo, Авторозкладка', ids.every(Boolean), JSON.stringify(ids));
  ok('вкладка «Лоток» у лівій панелі', !!(await page.$('#ltabs button[data-tab="tray"]')));
  await ev(page, () => { const { S } = __f3d; S.rights = { ...S.rights, is_manager: true, roles: ['manager'] }; });
  await ev(page, () => __f3d.E.runDialog('importLocations'));
  await page.waitForSelector('#impOdoo');
  ok('імпорт: джерела — файл і структура з Odoo', !!(await page.$('#impFile')) && !!(await page.$('#impOdoo')));
  ok('імпорт: «Імпортувати» вимкнено, доки немає джерела', await page.evaluate(() => document.getElementById('impGo').disabled));
  await page.click('#impOdoo');
  await page.waitForSelector('#impCells');
  const sum0 = await page.textContent('#impSummary');
  ok('перегляд: місць, рядків структури, залишків, складів; нескладські типи пропущено', /93/.test(sum0) && /рядків структури/.test(sum0) && /складів: 1/.test(sum0) && /Нескладські типи пропущено: 1/.test(sum0), sum0.slice(0, 300));
  ok('перегляд без правил: усе під зонами стало місцями на підлозі, у лотку 3', /місць на підлозі 90/.test(sum0) && /У лоток «Не розміщено»: 3/.test(sum0), sum0.slice(0, 300));
  const sug = await page.$$eval('[data-role="suggest"]', (els) => els.map((e) => e.textContent));
  ok('підказка маски за зразками з часткою збігів', sug.length >= 1 && /\{зона:a\}-\{ряд\}-\{секція\}-\{ярус\}/.test(sug[0]) && /86/.test(sug[0]), JSON.stringify(sug));
  await page.click('[data-role="suggest"] button');
  const sum1 = await page.textContent('#impParsed');
  ok('після застосування маски: зон 3, рядів 5, місць на підлозі 4, лоток 3', /зон 3, рядів 5, місць на підлозі 4/.test(sum1) && /лоток «Не розміщено»: 3/.test(sum1), sum1);
  ok('режим «новий проєкт з файлу» вибрано за замовчуванням для менеджера', await page.evaluate(() => document.getElementById('impNew').checked));
  const before = await ev(page, () => ({ site: __f3d.S.site.id, n: __f3d.S.app.sites.length }));
  await page.click('#impGo');
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  await page.waitForTimeout(600);
  const after = await ev(page, () => { const { S, E } = __f3d; return { site: S.site.id, name: S.site.name, n: S.app.sites.length, slots: S.slots.length, zones: S.slots.filter((s) => s.template === 'zone').length, tray: E.trayItems().map((t) => t.code).sort(), rules: S.site.parse_rules.rules.map((r) => r.mask), b: S.site.building, undo: E.undoState().undoLabel }; });
  ok('результат: новий проєкт «з файлу» (склад із назвою зі стрічки), 12 місць, 3 зони', after.site !== before.site && after.n === before.n + 1 && /Склад/.test(after.name) && after.slots === 12 && after.zones === 3, JSON.stringify(after));
  ok('лоток: Брак, Повернення, UNK-77; правило маски збережено в проєкті', JSON.stringify(after.tray) === JSON.stringify(['UNK-77', 'Брак', 'Повернення'].sort()) && after.rules[0] === '{зона:a}-{ряд}-{секція}-{ярус}', JSON.stringify(after));
  const ext = await ev(page, () => { const zs = __f3d.S.slots.filter((s) => s.template === 'zone'); const b = __f3d.S.site.building; return { right: Math.max(...zs.map((z) => z.x + z.params.length / 2)), top: Math.max(...zs.map((z) => z.y + z.params.width / 2)), L: b.length, W: b.width }; });
  ok('зони в контурі будівлі (будівля нового проєкту росте лише за потреби); підпис кроку «Імпорт структури: 90 місць»', ext.right <= ext.L && ext.top <= ext.W && after.undo === 'Імпорт структури: 90 місць', JSON.stringify([ext, after.undo]));
  const cs = await codes(page);
  ok('коди комірок проєкту = коди локацій Odoo (справжній cellsOf)', cs.length === 90 && cs.includes('A-03-06-3') && cs.includes('B-02-08-2') && cs.includes('BUF-4'), cs.length);
  const geo = await ev(page, () => {
    const zones = __f3d.S.slots.filter((s) => s.template === 'zone');
    const inside = (s) => zones.some((z) => Math.abs(s.x - z.x) <= z.params.length / 2 && Math.abs(s.y - z.y) <= z.params.width / 2);
    const blocks = __f3d.S.slots.filter((s) => s.template !== 'zone');
    const iss = __f3d.S.issues.list.filter((i) => i.level === 'block').length;
    return { allInside: blocks.every(inside), blocks: iss };
  });
  ok('авторозкладка після імпорту: усі ряди всередині зон, без блокувань перевірок', geo.allInside && geo.blocks === 0, JSON.stringify(geo));
  // вкладка «Лоток»
  await page.click('#ltabs button[data-tab="tray"]');
  await page.waitForSelector('#trayBlock');
  ok('лоток: «Без правила й зони-родителя: 3», підпис вкладки з числом', /Без правила й зони-родителя: 3/.test(await page.textContent('#trayCount')) && /Лоток \(3\)/.test(await page.textContent('#ltabs button[data-tab="tray"]')));
  // Ctrl+Z повертає проєкт одним кроком
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(400);
  ok('Ctrl+Z: імпорт скасовано одним кроком (місць немає)', await ev(page, () => __f3d.S.slots.length === 0));
  await page.keyboard.press('Control+Shift+z');
  await page.waitForTimeout(400);
  ok('Ctrl+Shift+Z повертає структуру', (await codes(page)).length === 90);
  ok('імпорт: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_files(page, errors) {
  await ev(page, () => { const { S } = __f3d; S.rights = { ...S.rights, is_manager: true, roles: ['manager'] }; });
  // CSV у Windows-1251 з «;» — мапа колонок за українськими заголовками
  const rows = [['Повна назва локації', 'Тип локації', 'Штрихкод', 'Батьківська локація', 'Товар', 'Кількість']];
  for (const z of ['Зона 1', 'Зона 2']) {
    rows.push([`WH/Stock/${z}`, 'Вигляд', '', 'WH/Stock', '', '']);
    for (let r = 1; r <= 2; r++) for (let b = 1; b <= 3; b++) for (let l = 1; l <= 2; l++) {
      const code = `${z.slice(-1)}${String(r).padStart(2, '0')}${b}${l}`.replace(/^(\d)(\d\d)(\d)(\d)$/, 'Z$1-$2-0$3-$4');
      rows.push([`WH/Stock/${z}/${code}`, 'Внутрішня локація', code, `WH/Stock/${z}`, l === 1 ? 'Плита' : '', l === 1 ? 5 : '']);
    }
  }
  rows.push(['WH/Stock/Брак', 'Внутрішня локація', '', 'WH/Stock', '', ''], ['Partners/Customers', 'Клієнтська локація', '', 'Partners', '', '']);
  const csv = rows.map((r) => r.join(';')).join('\r\n');
  await ev(page, () => __f3d.E.runDialog('importLocations'));
  await page.waitForSelector('#impFile');
  await page.setInputFiles('#impFile', { name: 'wh.csv', mimeType: 'text/csv', buffer: cp1251(csv) });
  await page.waitForSelector('#impMapGrid');
  const info = await page.textContent('#impMap');
  ok('CSV: кодування windows-1251, роздільник «;», рядків даних 28', /windows-1251/.test(info) && /роздільник ;/.test(info) && /рядків: 28/.test(info), info.slice(0, 200));
  const mapped = await page.$$eval('#impMapGrid select', (els) => els.map((e) => e.selectedOptions[0].textContent));
  ok('колонки за заголовками UK (повна назва, тип, штрихкод, батько, товар, кількість)', ['Повна назва локації', 'Тип локації', 'Штрихкод', 'Батьківська локація', 'Товар', 'Кількість'].every((h) => mapped.includes(h)), JSON.stringify(mapped));
  const sum = await page.textContent('#impSummary');
  ok('перегляд: 25 місць (24 комірки + Брак), залишків 12, нескладські типи пропущено', /\b25\b/.test(await page.textContent('#impCells')) && /залишків: 12/.test(sum) && /Нескладські типи пропущено: 1/.test(sum), sum.slice(0, 300));
  await page.waitForSelector('[data-role="suggest"] button');
  const sug = await page.$$eval('[data-role="suggest"] .mono', (els) => els.map((e) => e.textContent));
  ok('підказка маски для кодів Z1-01-01-1', sug.some((m) => /\{(зона|префікс)(:a)?\}/.test(m)) && sug.some((m) => /\{ряд\}-\{секція\}-\{ярус\}/.test(m)), JSON.stringify(sug));
  await page.click('[data-role="suggest"] button');
  await page.click('#impCurrent');
  ok('режим «поточний проєкт» вмикає поле? (назва проєкту зникає)', !(await page.$('#impName')));
  await page.click('#impNew');
  await page.fill('#impName', 'Імпорт із CSV');
  await page.click('#impGo');
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  await page.waitForTimeout(500);
  const st = await ev(page, () => ({ name: __f3d.S.site.name, tray: __f3d.E.trayItems().map((t) => t.code) }));
  const cs1 = await codes(page);
  ok('імпорт CSV: проєкт «Імпорт із CSV», 24 комірки + лоток «Брак»', st.name === 'Імпорт із CSV' && cs1.length === 24 && st.tray.length === 1 && st.tray[0] === 'Брак', JSON.stringify([st, cs1.length]));
  // експорт CSV і XLSX
  await ev(page, () => __f3d.E.runDialog('exportLocations'));
  await page.waitForSelector('#expGo');
  await page.check('#expZones');
  await page.selectOption('#expBody select[aria-label="Формат"]', 'csv');
  const dl1 = page.waitForEvent('download');
  await page.click('#expGo');
  const d1 = await dl1;
  const csvPath = path.join(DL, 'export.csv');
  await d1.saveAs(csvPath);
  const text = fs.readFileSync(csvPath, 'utf8').replace(/^﻿/, '');
  const lines = text.trim().split(/\r\n/);
  ok('експорт CSV: UTF-8 з BOM, заголовок формату імпорту Odoo, 24 комірки + 2 батьки-зони', fs.readFileSync(csvPath)[0] === 0xef && lines[0] === 'name,location_id,usage,barcode,posx,posy,posz' && lines.length === 1 + 24 + 2, lines.slice(0, 3).join(' | ') + ' n=' + lines.length);
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  await ev(page, () => __f3d.E.runDialog('exportLocations'));
  await page.waitForSelector('#expGo');
  await page.check('#expZones');
  const dl2 = page.waitForEvent('download');
  await page.click('#expGo');
  const d2 = await dl2;
  const xlsxPath = path.join(DL, 'export.xlsx');
  await d2.saveAs(xlsxPath);
  ok('експорт XLSX: файл .xlsx (zip)', /\.xlsx$/.test(d2.suggestedFilename()) && fs.readFileSync(xlsxPath)[0] === 0x50, d2.suggestedFilename());
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  // туди-назад: імпорт цього XLSX у новий проєкт — ті самі коди й нічого в лотку
  await ev(page, () => __f3d.E.runDialog('importLocations'));
  await page.waitForSelector('#impFile');
  await page.setInputFiles('#impFile', xlsxPath);
  await page.waitForSelector('#impMapGrid');
  ok('XLSX: аркуш «Локації», заголовки name/location_id/… розпізнано', /аркуш «Локації»/.test(await page.textContent('#impMap')) && (await page.$$eval('#impMapGrid select', (els) => els.filter((e) => e.value !== '').length)) >= 5);
  await page.waitForSelector('[data-role="suggest"] button').catch(() => null);
  const sg = await page.$$('[data-role="suggest"] button');
  if (sg.length) await sg[0].click();
  await page.fill('#impName', 'Назад з XLSX');
  await page.click('#impGo');
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  await page.waitForTimeout(500);
  const cs2 = await codes(page);
  const tray2 = await ev(page, () => __f3d.E.trayItems().length);
  ok('round-trip XLSX: ті самі 24 коди, лоток порожній', JSON.stringify(cs2) === JSON.stringify(cs1) && tray2 === 0, JSON.stringify([cs2.length, tray2]));
  ok('файли: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_tray(page, errors) {
  await importSample(page);
  await page.click('#ltabs button[data-tab="tray"]');
  await page.waitForSelector('.tray-row');
  const n0 = await page.$$eval('.tray-row', (els) => els.length);
  ok('лоток: 3 записи з причинами', n0 === 3 && /не збігається з жодним правилом/.test(await page.textContent('#trayList')));
  await ev(page, () => __f3d.E.setView('plan'));
  // розмістити через діалог «Розмістити в…»
  await page.click('.tray-row[data-code="UNK-77"] [data-act="place"]');
  await page.waitForSelector('#trayPlaceGo');
  const zoneOpts = await page.$$eval('#trayPlaceBody select option', (els) => els.map((e) => e.textContent));
  ok('«Розмістити в…»: вільне місце й зони площадки', zoneOpts.includes('Зона A') && zoneOpts.includes('Зона B') && zoneOpts.length === 4, JSON.stringify(zoneOpts));
  await page.selectOption('#trayPlaceBody select', { label: 'Зона B' });
  await page.click('#trayPlaceGo');
  await page.waitForTimeout(400);
  const placed = await ev(page, () => {
    const { S } = __f3d;
    const s = S.slots.find((x) => x.code_prefix === 'UNK-77');
    const z = S.slots.find((x) => x.params.title === 'Зона B');
    return { tpl: s && s.template, inZone: !!s && Math.abs(s.x - z.x) <= z.params.length / 2 && Math.abs(s.y - z.y) <= z.params.width / 2, label: __f3d.E.undoState().undoLabel };
  });
  ok('місце на підлозі з точним кодом UNK-77 у зоні B; крок «Розміщено з лотка: 1»', placed.tpl === 'floor_spot' && placed.inZone && placed.label === 'Розміщено з лотка: 1', JSON.stringify(placed));
  ok('запис зник з лотка', (await page.$$eval('.tray-row', (els) => els.length)) === 2 && (await codes(page)).includes('UNK-77'));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(400);
  await page.click('#ltabs button[data-tab="tray"]');
  ok('Ctrl+Z повертає запис у лоток', (await page.$$eval('.tray-row', (els) => els.length)) === 3 && !(await codes(page)).includes('UNK-77'));
  // перетягування запису на зону сцени
  const pt = await ev(page, () => {
    const { S, V, core } = __f3d;
    const z = S.slots.find((x) => x.params.title === 'Зона A');
    __f3d.E.focusOn(z.x, z.y, 40);
    const r = V.canvas.getBoundingClientRect();
    const v = new core.THREE.Vector3(z.x, 0.1, -z.y).project(V.camera);
    return { x: (v.x + 1) / 2 * r.width, y: (1 - v.y) / 2 * r.height, id: z.id };
  });
  await page.waitForTimeout(500);
  const pt2 = await ev(page, () => { const { S, V, core } = __f3d; const z = S.slots.find((x) => x.params.title === 'Зона A'); const r = V.canvas.getBoundingClientRect(); const v = new core.THREE.Vector3(z.x, 0.1, -z.y).project(V.camera); return { x: (v.x + 1) / 2 * r.width, y: (1 - v.y) / 2 * r.height }; });
  await page.dragAndDrop('.tray-row[data-code="UNK-77"]', '#vp canvas', { targetPosition: { x: Math.round(pt2.x), y: Math.round(pt2.y) } });
  await page.waitForTimeout(500);
  const dropped = await ev(page, () => { const { S } = __f3d; const s = S.slots.find((x) => x.code_prefix === 'UNK-77'); const z = S.slots.find((x) => x.params.title === 'Зона A'); return s ? { inZone: Math.abs(s.x - z.x) <= z.params.length / 2 && Math.abs(s.y - z.y) <= z.params.width / 2, tray: __f3d.E.trayItems().length } : null; });
  ok('перетягування запису лотка на зону A: місце створено в зоні, у лотку лишилось 2', !!dropped && dropped.inZone && dropped.tray === 2, JSON.stringify(dropped) + ' pt=' + JSON.stringify(pt2));
  // Брак — кирилиця: відмова з поясненням, нічого не змінюється
  await ev(page, () => __f3d.E.undoRecord());
  const nb = await ev(page, () => __f3d.S.slots.length);
  await page.click('#ltabs button[data-tab="tray"]');
  await page.click('.tray-row[data-code="Брак"] [data-act="place"]');
  await page.waitForSelector('#trayPlaceGo');
  await page.click('#trayPlaceGo');
  await page.waitForTimeout(300);
  ok('код «Брак» (кирилиця) не стає місцем: пояснення, стан без змін', (await ev(page, () => __f3d.S.slots.length)) === nb && /Код не підходить для місця/.test(await toast(page)), await toast(page));
  await page.keyboard.press('Escape');
  // фільтр і «Очистити лоток»
  await page.click('#ltabs button[data-tab="tray"]');
  await page.fill('#trayFilter', 'пов');
  await page.waitForTimeout(100);
  ok('фільтр лотка за назвою', (await page.$$eval('.tray-row', (els) => els.map((e) => e.dataset.code))).join() === 'Повернення');
  ok('лоток: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_layout(page, errors) {
  await importSample(page);
  await ev(page, () => __f3d.E.setView('plan'));
  // «ручні положення»: розкидати ряди зони A
  const snap0 = await ev(page, () => {
    const { S, E } = __f3d;
    const z = S.slots.find((x) => x.params.title === 'Зона A');
    const rs = S.slots.filter((s) => s.template === 'pallet_rack' && Math.abs(s.x - z.x) <= z.params.length / 2 && Math.abs(s.y - z.y) <= z.params.width / 2);
    rs.forEach((r, i) => { r.x = z.x + (i - 1) * 3; r.y = z.y + 2; r.rotation = i === 1 ? 90 : 0; });
    E.commit({});
    E.undoRecord();
    return { zone: z.id, ids: rs.map((r) => r.id), pos: rs.map((r) => [r.x, r.y, r.rotation]), codes: null };
  });
  const codes0 = await codes(page);
  await ev(page, (id) => __f3d.E.selectObj({ kind: 'slot', id }), snap0.zone);
  await page.waitForSelector('#btnAutoZone');
  ok('панель зони: «Розкласти автоматично»', !(await page.evaluate(() => document.getElementById('btnAutoZone').disabled)));
  const h0 = await ev(page, () => __f3d.S.hist.stack.length);
  await page.click('#btnAutoZone');
  await page.waitForTimeout(500);
  const after = await ev(page, ({ ids }) => {
    const { S, E } = __f3d;
    const rs = ids.map((id) => S.sIdx.get(id));
    const ys = rs.map((r) => r.y).sort((a, b) => a - b);
    return { rot: rs.every((r) => r.rotation === 0), xs: new Set(rs.map((r) => r.x)).size, gaps: ys.slice(1).map((y, i) => +(y - ys[i]).toFixed(2)), steps: S.hist.stack.length, label: E.undoState().undoLabel };
  }, snap0);
  ok('авторозкладка зони: ряди вглиб з проходами, однаковий початок, повороти зняті', after.rot && after.xs === 1 && after.gaps.every((g) => g >= 4.0) && after.gaps.length === snap0.ids.length - 1, JSON.stringify(after));
  ok('авторозкладка = ОДИН крок історії з підписом', after.steps === h0 + 1 && after.label === 'Авторозкладка: Зона A', JSON.stringify(after));
  ok('коди комірок не змінилися після розкладки', JSON.stringify(await codes(page)) === JSON.stringify(codes0));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(400);
  const back = await ev(page, ({ ids }) => ids.map((id) => { const r = __f3d.S.sIdx.get(id); return [r.x, r.y, r.rotation]; }), snap0);
  ok('Ctrl+Z повертає ручні положення одним кроком', JSON.stringify(back) === JSON.stringify(snap0.pos), JSON.stringify(back));
  // вся площадка з меню: нічого не вміщається — нічого не змінюється
  const before = await ev(page, () => JSON.stringify(__f3d.S.slots));
  await ev(page, () => { __f3d.S.site.building.length = 20; __f3d.S.site.building.width = 10; });
  await menu(page, 'autolayout');
  await page.waitForTimeout(300);
  ok('не вміщається в контур: повідомлення «Нічого не змінено», стан той самий', /Нічого не змінено/.test(await toast(page)) && (await ev(page, () => JSON.stringify(__f3d.S.slots))) === before, await toast(page));
  await ev(page, () => { __f3d.S.site.building.length = 200; __f3d.S.site.building.width = 100; });
  await menu(page, 'autolayout');
  await page.waitForTimeout(500);
  const site = await ev(page, () => {
    const zs = __f3d.S.slots.filter((s) => s.template === 'zone').sort((a, b) => a.x - b.x);
    return { n: zs.length, order: zs.map((z) => z.params.title), sameShelf: zs.every((z) => z.y === zs[0].y) || zs[2].y > zs[0].y, noOverlap: zs.every((z, i) => i === 0 || z.x - z.params.length / 2 >= zs[i - 1].x + zs[i - 1].params.length / 2 - 1e-6 || z.y !== zs[i - 1].y) };
  });
  ok('авторозкладка площадки: зони по горизонталі без накладання', site.n === 3 && site.noOverlap, JSON.stringify(site));
  ok('розкладка: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_sync(page, errors) {
  await importSample(page);
  // перший виклик створює базу порівняння
  await ev(page, () => { __f3d.E.runDialog('syncOdoo'); });
  await page.waitForTimeout(500);
  ok('«Оновити з Odoo»: база порівняння створена, розбіжностей немає', /Базу порівняння/.test(await toast(page)), await toast(page));
  // Odoo змінився: перейменування, архів, нова локація, інший батько
  await ev(page, async () => {
    const feed = await __f3d.adapter.locations({ op: 'feed' });
    const list = feed.feed.locations.map((l) => ({ ...l }));
    list.find((l) => l.code === 'A-01-01-1').name = 'Перейменована комірка';
    list.find((l) => l.code === 'A-01-02-1').active = false;
    list.find((l) => l.code === 'BUF-1').parent = 'WH/Stock/Зона A';
    list.find((l) => l.code === 'BUF-1').parent_id = list.find((l) => l.name === 'Зона A').id;
    list.push({ id: 9001, code: 'NEW-1', name: 'NEW-1', parent: 'WH/Stock', parent_id: null, usage: 'internal', barcode: 'NEW-1', qty: 0, active: true });
    __f3d.adapter.simSetFeed(list);
  });
  await ev(page, () => { __f3d.E.runDialog('syncOdoo'); });
  await page.waitForSelector('#syncList');
  const groups = await page.$$eval('#syncList h4', (els) => els.map((e) => e.textContent.split(':')[0]));
  ok('розбіжності: з\'явилося, зникло, перейменовано, інший батько', ['З\'явилося в Odoo', 'Зникло в Odoo (архів чи видалення)', 'Перейменовано в Odoo', 'Інший батько в Odoo'].every((g) => groups.includes(g)), JSON.stringify(groups));
  const rows = await page.$$eval('#syncList .frow', (els) => els.map((e) => e.textContent));
  ok('рядки: NEW-1, A-01-02-1, A-01-01-1 «Перейменована комірка», BUF-1', ['NEW-1', 'A-01-02-1', 'Перейменована комірка', 'BUF-1'].every((t) => rows.some((r) => r.includes(t))), JSON.stringify(rows));
  // «Залишити моє» для всіх — нічого не змінюється, але база оновлюється
  const snap = await ev(page, () => JSON.stringify(__f3d.S.slots));
  await page.click('#syncAllMine');
  await page.click('#syncApply');
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  ok('«Залишити все моє»: модель не змінилась, у лотку нічого нового', (await ev(page, () => JSON.stringify(__f3d.S.slots))) === snap && (await ev(page, () => __f3d.E.trayItems().length)) === 3);
  await ev(page, () => { __f3d.E.runDialog('syncOdoo'); });
  await page.waitForTimeout(400);
  ok('після рішення база порівняння оновлена: розбіжностей більше немає', /Розбіжностей з Odoo немає/.test(await toast(page)), await toast(page));
  // ще раз змінити й прийняти все
  await ev(page, async () => {
    const list = (await __f3d.adapter.locations({ op: 'feed' })).feed.locations.map((l) => ({ ...l }));
    list.find((l) => l.code === 'A-02-01-1').active = false;
    list.find((l) => l.code === 'A-01-01-2').name = 'Нова назва 2';
    list.push({ id: 9002, code: 'NEW-2', name: 'NEW-2', parent: 'WH/Stock', parent_id: null, usage: 'internal', barcode: 'NEW-2', qty: 0, active: true });
    __f3d.adapter.simSetFeed(list);
  });
  await ev(page, () => __f3d.E.undoRecord());
  await ev(page, () => { __f3d.E.runDialog('syncOdoo'); });
  await page.waitForSelector('#syncAllOdoo');
  await page.click('#syncAllOdoo');
  await page.click('#syncApply');
  await page.waitForSelector('dialog[open]', { state: 'detached' });
  await page.waitForTimeout(500);
  const acc = await ev(page, () => {
    const { S, E } = __f3d;
    const cells = S.slots.flatMap((s) => __f3d.cellsOf(s));
    return { gone: !cells.some((c) => c.code === 'A-02-01-1' && !c.disabled), name: (cells.find((c) => c.code === 'A-01-01-2') || {}).name, tray: E.trayItems().map((t) => [t.code, t.reason]), label: E.undoState().undoLabel };
  });
  ok('«Прийняти все з Odoo»: зниклу комірку вимкнено, назву оновлено, нова — в лоток з причиною', acc.gone && acc.name === 'Нова назва 2' && acc.tray.some(([c, r]) => c === 'NEW-2' && r === 'new_in_odoo') && acc.label === 'Оновлення з Odoo', JSON.stringify(acc));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(400);
  ok('Ctrl+Z повертає вимкнену комірку', (await codes(page)).includes('A-02-01-1'));
  ok('розбіжності: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_rules(page, errors) {
  await importSample(page);
  await page.click('#ltabs button[data-tab="tray"]');
  await page.click('#trayParse');
  await page.waitForSelector('#pcBody');
  const stats = await page.textContent('#pcStats');
  ok('«Розбір кодів»: «З N місць розібрано M» (90 комірок + 3 у лотку)', /З 93 місць розібрано 86/.test(stats), stats);
  ok('нерозпізнані коди з прикладами', /Не розпізнано: 7/.test(await page.textContent('#pcUnparsed')) && /BUF-1/.test(await page.textContent('#pcExamples')));
  const ruleCount = await page.$$eval('.pc-rule', (els) => els.length);
  ok('правило з імпорту є в списку', ruleCount === 1);
  await page.click('#pcAdd');
  const inp = (await page.$$('.pc-rule .pc-mask'))[1];
  await inp.fill('BUF-{позиція}');
  await page.waitForTimeout(100);
  ok('нове правило «BUF-{позиція}»: розібрано стало 90', /З 93 місць розібрано 90/.test(await page.textContent('#pcStats')), await page.textContent('#pcStats'));
  await inp.fill('{фрукт}');
  ok('хибна маска: повідомлення про помилку й заборона збереження', (await page.textContent('#pcStats')).includes('правил із помилкою: 1'));
  await page.click('#pcSave');
  await page.waitForTimeout(200);
  ok('збереження хибного правила відхилено (діалог лишається)', !!(await page.$('#pcBody')) && /Виправте правила/.test(await toast(page)), await toast(page));
  await inp.fill('BUF-{позиція}');
  await page.selectOption('.pc-rule:nth-child(2) select[aria-label="Тип місця"]', 'floor_spot');
  await page.click('#pcGuessBtn');
  await page.click('#pcSave');
  await page.waitForSelector('dialog[open]', { state: 'detached' }).catch(() => null);
  await page.keyboard.press('Escape');
  const rules = await ev(page, () => __f3d.S.site.parse_rules.rules.map((r) => [r.mask, r.type]));
  ok('правила збережено в проєкті', rules.length === 2 && rules[1][0] === 'BUF-{позиція}' && rules[1][1] === 'floor_spot', JSON.stringify(rules));
  // збереження в сховищі прототипа: перезавантаження сторінки
  await ev(page, () => __f3d.E.flushNow());
  await page.waitForTimeout(300);
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
  await page.waitForTimeout(800);
  const reloaded = await ev(page, () => ({ rules: (__f3d.S.site.parse_rules.rules || []).length, tray: __f3d.E.trayItems().map((t) => t.code).sort(), name: __f3d.S.site.name }));
  ok('після перезавантаження: правила й лоток на місці (3 запису)', reloaded.rules === 2 && reloaded.tray.length === 3, JSON.stringify(reloaded));
  ok('правила: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

(async () => {
  const suites = { імпорт: t_import, файли: t_files, лоток: t_tray, розкладка: t_layout, розбіжності: t_sync, правила: t_rules };
  const only = process.argv[2];
  for (const [name, fn] of Object.entries(suites)) {
    if (only && only !== name) continue;
    const { browser, page, errors } = await launch({ viewport: { width: 1440, height: 900 } });
    try { await open(page); await fn(page, errors); } catch (e) { ok(name + ': виняток ' + e.message, false, (e.stack || '').split('\n').slice(0, 4).join(' | ')); }
    await browser.close();
  }
  const bad = res.filter((x) => !x).length;
  console.log(`\nІТОГО S4 прототип: ${res.length - bad} passed, ${bad} failed`);
  process.exit(bad ? 1 : 0);
})();
