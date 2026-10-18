// Слайс S2 «Зв'язок з Odoo» у прототипі: план публікації за видами, область, журнал і відкат (F02), ємність і категорії (F03),
// правила розміщення й перевірки cell_load/putaway_fit/code_conflict (F04).
// Запуск: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node build/constructor/proto/test_s2.js (після python3 build/constructor/proto/build.py)
const { launch, open } = require('./harness');
const res = [];
const ok = (name, cond, extra) => { res.push(cond); console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? ' :: ' + extra : '')); };

/** Чистий шар складу: зона 40×20 і два стелажі в ній; решту місць шару прибрано (опубліковані комірки стануть пропозиціями архівації). */
async function prepare(page) {
  return await page.evaluate(() => {
    const { S, E } = __f3d;
    const ly = S.layers.find((l) => l.slot_types.includes('pallet_rack') && l.slot_types.includes('zone')) || S.layers.find((l) => l.slot_types.includes('pallet_rack'));
    if (!ly.slot_types.includes('zone')) ly.slot_types.push('zone');
    S.ui.layer = ly.id;
    S.slots = S.slots.filter((s) => s.layer_id !== ly.id);
    S.placements = S.placements.filter((p) => p.layer_id !== ly.id);
    const params = { bays: 3, levels: 2, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000 };
    S.slots.push({ id: 'zs2', rid: null, etag: null, layer_id: ly.id, template: 'zone', code_prefix: 'ZS2', x: 30, y: 12, rotation: 0, params: { length: 40, width: 20, title: 'Зона S2', color: '#9fb7c9' }, overrides: {}, parent_location_id: null });
    S.slots.push({ id: 'sr1', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'S2-R1', x: 24, y: 10, rotation: 0, params: { ...params }, overrides: {}, parent_location_id: null });
    S.slots.push({ id: 'sr2', rid: null, etag: null, layer_id: ly.id, template: 'pallet_rack', code_prefix: 'S2-R2', x: 36, y: 14, rotation: 0, params: { ...params }, overrides: {}, parent_location_id: null });
    E.commit({});
    E.renderAll();
    return ly.id;
  });
}

async function t_plan(page, errors) {
  await prepare(page);
  await page.click('#btnPublish');
  await page.waitForSelector('dialog[open] [data-view="all"]');
  const chips = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('dialog [data-view]')].map((b) => [b.dataset.view, b.textContent])));
  ok('план: чипи видів із лічильниками (усе, створити, архів)', chips.all && /Створити · 12/.test(chips.create || '') && chips.archive, JSON.stringify(chips));
  await page.click('dialog [data-view="create"]');
  const rows = await page.locator('dialog .plan-row').count();
  ok('вид «Створити»: 12 рядків комірок двох рядів', rows === 12, String(rows));
  ok('рядки створення позначені, архівні — ні', await page.evaluate(() => {
    const boxes = [...document.querySelectorAll('dialog .plan-row input[type=checkbox]')];
    return boxes.length === 12 && boxes.every((b) => b.checked);
  }));
  await page.click('dialog [data-view="archive"]');
  ok('вид «Архів»: пропозиції не позначені за замовчуванням', await page.evaluate(() => {
    const boxes = [...document.querySelectorAll('dialog .plan-row input[type=checkbox]')];
    return boxes.length > 0 && boxes.every((b) => !b.checked);
  }));
  // область: лише ряд S2-R1 (+ рядки зони, що його містить, не додаються самі)
  await page.click('dialog [data-view="all"]');
  const opts = await page.evaluate(() => [...document.querySelectorAll('dialog select[aria-label="Зона або ряд"] option')].map((o) => o.textContent));
  ok('область: список «Зона або ряд»', opts.some((t) => /Ряд S2-R1/.test(t)) && opts.some((t) => /Зона/.test(t)), JSON.stringify(opts.slice(0, 4)));
  await page.selectOption('dialog select[aria-label="Зона або ряд"]', { label: opts.find((t) => /Ряд S2-R1/.test(t)) });
  await page.click('#planScopeOnly');
  const sel = await page.evaluate(() => document.querySelector('[data-role="plan-sum"]').textContent);
  ok('«Лише обране»: застосовується 6 комірок ряду', /Буде застосовано: 6 \(створити 6/.test(sel), sel);
  await page.click('#planSelectNone');
  ok('«Зняти все»: нічого не застосовується', /Буде застосовано: 0/.test(await page.evaluate(() => document.querySelector('[data-role="plan-sum"]').textContent)));
  ok('«Підтвердити» вимкнено без позначених рядків і без правок чернетки або з ними', await page.evaluate(() => typeof document.querySelector('#planConfirm').disabled === 'boolean'));
  await page.click('#planSelectAll');
  // «Файл для імпорту» не падає
  const dl = page.waitForEvent('download', { timeout: 4000 }).catch(() => null);
  await page.click('#planCsv');
  const d = await dl;
  ok('«Файл для імпорту (CSV)»: завантаження', !!d && /\.csv$/.test(d.suggestedFilename()), d ? d.suggestedFilename() : 'немає');
  // застосувати лише S2-R1
  await page.selectOption('dialog select[aria-label="Зона або ряд"]', { label: opts.find((t) => /Ряд S2-R1/.test(t)) });
  await page.click('#planScopeOnly');
  await page.fill('dialog textarea', 'S2: лише ряд R1');
  await page.click('#planConfirm');
  await page.waitForTimeout(700);
  const sim = await page.evaluate(async () => { const s = await __f3d.adapter.simState(); return { codes: Object.keys(s.locations).filter((c) => c.startsWith('S2-')), journal: s.journal.map((j) => [j.n, j.ops.length]) }; });
  ok('застосування частинами: в «Odoo» лише комірки S2-R1', sim.codes.length === 6 && sim.codes.every((c) => c.startsWith('S2-R1')), JSON.stringify(sim));
  ok('журнал: версія з 6 операціями', sim.journal.length === 1 && sim.journal[0][1] === 6, JSON.stringify(sim.journal));
  ok('план: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));

  // журнал і відкат
  await page.evaluate(() => { __f3d.E.runDialog('planLog'); });
  await page.waitForSelector('dialog[open] [data-role="journal"] .jrow');
  const row = await page.evaluate(() => { const r = document.querySelector('.jrow'); return { t: r.textContent, rb: !!r.querySelector('[data-act="rollback"]') && !r.querySelector('[data-act="rollback"]').disabled }; });
  ok('журнал: версія з лічильниками видів і кнопкою «Відкотити»', /створено 6/.test(row.t) && row.rb, row.t.slice(0, 120));
  await page.click('[data-act="ops"]');
  await page.waitForTimeout(200);
  ok('журнал: операції версії видно', /S2-R1-B01-L1/.test(await page.textContent('dialog')));
  await page.click('[data-act="rollback"]');
  await page.waitForSelector('#dlgYes');
  await page.click('#dlgYes');
  await page.waitForTimeout(800);
  const after = await page.evaluate(async () => { const s = await __f3d.adapter.simState(); return { active: Object.values(s.locations).filter((l) => l.code.startsWith('S2-') && l.active).length, rolled: s.journal.map((j) => j.rolled_back), slots: __f3d.S.slots.filter((x) => x.code_prefix.startsWith('S2-')).length }; });
  ok('відкат: створене в архіві, чернетка не змінилась', after.active === 0 && after.rolled[0] === true && after.slots === 2, JSON.stringify(after));
  ok('журнал: після відкату позначено «відкочено»', /відкочено/.test(await page.textContent('dialog')));
  await page.keyboard.press('Escape');
  // наступний план пропонує зміни знову: комірки відновлюються з архіву
  await page.waitForTimeout(300);
  await page.click('#btnPublish');
  await page.waitForSelector('dialog[open] [data-view="all"]');
  const again = await page.evaluate(() => [...document.querySelectorAll('dialog .plan-row')].filter((r) => /відновити з архіву/.test(r.textContent)).length);
  ok('після відкату план знову пропонує зміни (відновлення з архіву)', again === 6, String(again));
  await page.click('dialog button:has-text("Скасувати")');
  ok('журнал і відкат: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_capacity(page, errors) {
  await prepare(page);
  await page.evaluate(() => { __f3d.E.selectObj({ kind: 'slot', id: 'sr1' }); });
  await page.waitForSelector('#capacityBlock');
  const t = await page.textContent('#capacityBlock');
  ok('панель місця: «Зберігання й ємність» з габаритом, місткістю й джерелом ваги', /Комірка S2-R1-B01-L1: 2,70×1,10×1,50 м/.test(t) && /макс\. вага 1\s?000 кг \(тип місця\)/.test(t) && /комірок 6/.test(t), t.slice(0, 260));
  // категорії зберігання: нова категорія → призначити місцю
  await page.evaluate(() => { __f3d.E.selectObj(null); });
  await page.waitForSelector('#siteCapacity');
  ok('панель площадки: зведення ємності', /Комірок \d+ · палетомісць \d+/.test(await page.textContent('#siteCapacity')));
  await page.click('#btnCategories');
  await page.waitForSelector('#btnNewCategory');
  await page.click('#btnNewCategory');
  await page.fill('dialog input[aria-label="Назва категорії"]', 'Палетна 800');
  await page.fill('dialog input[aria-label="Макс. вага"]', '800');
  await page.selectOption('dialog select[aria-label="Політика"]', 'same');
  await page.click('#btnSaveCategory');
  await page.waitForSelector('dialog [data-cat]');
  ok('категорії: створено й показано в списку', /Палетна 800/.test(await page.textContent('dialog [data-role="categories"]')) && /800 кг/.test(await page.textContent('dialog [data-role="categories"]')));
  await page.keyboard.press('Escape');
  await page.evaluate(() => { __f3d.E.selectObj({ kind: 'slot', id: 'zs2' }); });
  await page.waitForSelector('#capacityBlock select[aria-label="Функція зони"]');
  const fnOpts = await page.evaluate(() => [...document.querySelectorAll('#capacityBlock select[aria-label="Функція зони"] option')].length);
  ok('зона: 10 функцій + «не задано»', fnOpts === 11, String(fnOpts));
  await page.selectOption('#capacityBlock select[aria-label="Функція зони"]', 'storage');
  await page.check('#capacityBlock [data-attr="temp"]');
  await page.waitForSelector('#capacityBlock input[aria-label="Температура від"]');
  await page.selectOption('#capacityBlock select[aria-label="Категорія зберігання"]', { label: 'Палетна 800' });
  const z = await page.evaluate(() => { const z = __f3d.S.slots.find((s) => s.id === 'zs2'); return { f: z.function_id, a: z.attr_ids, c: z.storage_category_id }; });
  ok('зона: функція, атрибут і категорія записані в місце', z.f === 'storage' && z.a.includes('temp') && z.c != null, JSON.stringify(z));
  // успадкування вниз: стелаж без власної категорії показує «як у зони»
  await page.evaluate(() => { __f3d.E.selectObj({ kind: 'slot', id: 'sr1' }); });
  await page.waitForSelector('#capacityBlock');
  const inh = await page.evaluate(() => document.querySelector('#capacityBlock select[aria-label="Категорія зберігання"]').selectedOptions[0].textContent);
  ok('категорія діє вниз: «як у зони: Палетна 800»', /як у зони: Палетна 800/.test(inh), inh);
  ok('ємність: комірка бере вагу категорії, коли власної немає', await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.id === 'sr1'); s.params.max_load_kg = 0; __f3d.E.commit({}); __f3d.E.renderRight(); return /макс\. вага 800 кг \(категорія\)/.test(document.querySelector('#capacityBlock').textContent); }));
  // план: категорія зберігання — зміна атрибутів комірок
  await page.evaluate(() => { __f3d.S.slots.find((x) => x.id === 'sr1').params.max_load_kg = 1000; __f3d.E.commit({}); });
  const kinds = await page.evaluate(async () => { const p = await __f3d.adapter.planPreview(); return [...new Set(p.lines.filter((l) => l.code.startsWith('S2-')).map((l) => l.kind))]; });
  ok('план: нові комірки несуть категорію зберігання (create)', kinds.includes('create'), JSON.stringify(kinds));
  ok('ємність: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_rules(page, errors) {
  await prepare(page);
  await page.evaluate(() => { __f3d.E.selectObj(null); });
  await page.waitForSelector('#btnRules');
  await page.click('#btnRules');
  await page.waitForSelector('#btnNewRule');
  await page.click('#btnNewRule');
  await page.waitForSelector('[data-role="putaway-form"]');
  await page.fill('[data-role="putaway-form"] input[data-lookup="product"]', 'корпус');
  await page.click('[data-role="putaway-form"] .lookup button:has-text("Корпус шафи")');
  await page.fill('[data-role="putaway-form"] input[data-lookup="package_type"]', 'довга');
  await page.click('[data-role="putaway-form"] .lookup button:has-text("Довга палета")');
  await page.fill('[data-role="putaway-form"] input[data-code-input]', 'S2-R1-B01-L1');
  await page.click('#btnSaveRule');
  await page.waitForSelector('[data-role="rules"] .rule-row');
  const row = await page.textContent('[data-role="rules"] .rule-row');
  ok('правила: правило створено, позначка «нове»', /Корпус шафи/.test(row) && /нове/.test(row) && /S2-R1-B01-L1/.test(row), row.slice(0, 160));
  ok('правила: «не вміститься» — довга палета 3,5 м у комірці 2,7 м', /Правило: не вміститься — .*не вміщується в габарит/.test(await page.textContent('[data-role="rules"] .rule-row')));
  const issue = await page.evaluate(() => __f3d.S.issues.list.some((i) => i.check === 'putaway_fit'));
  ok('putaway_fit не в налаштуваннях — у панелі проблем зауважень ще немає', issue === false);
  // підсвічування цілі правила
  await page.click('[data-act="highlight"]');
  const hl = await page.evaluate(() => ({ m: __f3d.S.ui.metric, id: !!__f3d.S.ui.ruleHighlight }));
  ok('«Підсвітити»: метрика rule_target активна', hl.m === 'rule_target' && hl.id);
  ok('«Зняти підсвітку» є в діалозі', await page.locator('#btnClearHighlight').count() === 1);
  await page.click('#btnClearHighlight');
  ok('«Зняти підсвітку» скидає метрику', await page.evaluate(() => !__f3d.S.ui.metric));
  // правило поповнення
  await page.click('[data-tab="replenish"]');
  await page.click('#btnNewRule');
  await page.waitForSelector('[data-role="replenish-form"]');
  await page.fill('[data-role="replenish-form"] input[data-lookup="product"]', 'лдсп');
  await page.click('[data-role="replenish-form"] .lookup button:has-text("ЛДСП")');
  await page.fill('[data-role="replenish-form"] input[data-code-input]', 'S2-R2-B01-L1');
  await page.fill('[data-role="replenish-form"] input[aria-label="Мінімум"]', '5');
  await page.fill('[data-role="replenish-form"] input[aria-label="Максимум"]', '2');
  await page.click('#btnSaveRule');
  ok('поповнення: максимум < мінімум відхиляється', /Максимум не може бути меншим/.test((await page.evaluate(() => [...document.querySelectorAll('.ftoast')].map((t) => t.textContent).join('|')))));
  await page.fill('[data-role="replenish-form"] input[aria-label="Максимум"]', '20');
  await page.click('#btnSaveRule');
  await page.waitForSelector('[data-role="rules"] .rule-row');
  ok('поповнення: правило min/max у списку', /мін 5 \/ макс 20/.test(await page.textContent('[data-role="rules"]')));
  await page.keyboard.press('Escape');
  // план: правила — окремий вид із залежністю від комірки, що створюється
  await page.click('#btnPublish');
  await page.waitForSelector('dialog [data-view="rules"]');
  await page.click('dialog [data-view="rules"]');
  const rl = await page.evaluate(() => [...document.querySelectorAll('dialog .plan-row')].map((r) => r.textContent));
  ok('план: вид «Правила» — два рядки створення з залежністю від комірок', rl.length === 2 && rl.every((t) => /←/.test(t)), JSON.stringify(rl).slice(0, 200));
  await page.click('#planConfirm');
  await page.waitForTimeout(800);
  const sim = await page.evaluate(async () => { const s = await __f3d.adapter.simState(); return { op: Object.keys(s.orderpoints).length, pa: Object.keys(s.putaway).length, linked: __f3d.S.site.rules.putaway.every((r) => r.odoo_rule_id) && __f3d.S.site.rules.replenish.every((r) => r.odoo_orderpoint_id), c: !!s.locations['S2-R1-B01-L1'] }; });
  ok('публікація правил: orderpoint і правило розміщення в «Odoo», батьківська комірка додана сама', sim.op === 1 && sim.pa === 1 && sim.linked && sim.c, JSON.stringify(sim));
  // «Куди покладе Odoo»: тепер правило застосоване
  await page.click('#btnRules');
  await page.waitForSelector('#btnWhere');
  await page.fill('dialog input[aria-label="Товар для підбору місця"]', 'корпус');
  await page.click('dialog .lookup button:has-text("Корпус шафи")');
  await page.fill('dialog input[aria-label="Упаковка"]', 'довга');
  await page.click('dialog .lookup button:has-text("Довга палета")');
  await page.click('#btnWhere');
  await page.waitForTimeout(300);
  const where = await page.textContent('[data-role="where-result"]');
  ok('«Куди покладе Odoo»: оцінка за застосованими правилами', /покладе в S2-R1-B01-L1/.test(where) && /оцінка/.test(where), where);
  ok('«Куди покладе»: ціль підсвічено', await page.evaluate(() => __f3d.S.ui.metric === 'rule_target' && __f3d.S.ui.whereCode === 'S2-R1-B01-L1'));
  await page.keyboard.press('Escape');
  // видалення зв'язаного правила = «буде видалено», відкат/повернення
  await page.click('#btnRules');
  await page.click('[data-act="delete"]');
  ok('видалення зв\'язаного правила: «буде видалено»', /буде видалено/.test(await page.textContent('[data-role="rules"] .rule-row')) && await page.evaluate(() => __f3d.S.site.rules.putaway[0].deleted === true));
  await page.click('[data-act="restore"]');
  ok('«Повернути» знімає позначку', await page.evaluate(() => __f3d.S.site.rules.putaway[0].deleted === false));
  await page.keyboard.press('Escape');
  ok('правила: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

async function t_checks(page, errors) {
  await prepare(page);
  await page.evaluate(() => { __f3d.E.selectObj(null); });
  await page.waitForSelector('#capChecks [data-check="cell_load"]');
  ok('налаштування перевірок ємності: cell_load, putaway_fit, code_conflict', await page.locator('#capChecks [data-check]').count() === 3);
  await page.check('#capChecks [data-check="cell_load"]');
  await page.check('#capChecks [data-check="code_conflict"]');
  ok('перевірки вмикаються й живуть у налаштуваннях', await page.evaluate(() => __f3d.S.settings.checks.cell_load.enabled && __f3d.S.settings.checks.code_conflict.enabled));
  await page.click('#btnDemoStock');
  await page.waitForTimeout(500);
  const n = await page.evaluate(() => __f3d.S.issues.list.filter((i) => i.check === 'cell_load').length);
  ok('демо-залишки: cell_load показує перевищення ваги (живі перевірки)', n > 0, String(n));
  await page.evaluate(() => { __f3d.adapter.simSetForeign({ 'S2-R1-B01-L1': 'Штрихкод зайнятий архівною локацією' }); });
  await page.click('#btnCheckCodes');
  await page.waitForTimeout(500);
  const cc = await page.evaluate(() => __f3d.S.issues.list.filter((i) => i.check === 'code_conflict').map((i) => i.message));
  ok('code_conflict: зайнятий код у «Odoo» (API-17) → зауваження', cc.some((m) => /S2-R1-B01-L1: Штрихкод зайнятий/.test(m)), JSON.stringify(cc));
  const sav = await page.evaluate(() => JSON.stringify(__f3d.S.settings.checks.cell_load));
  ok('налаштування перевірки записано в стан', /"enabled":true/.test(sav), sav);
  ok('перевірки: консоль без помилок', errors.length === 0, errors.slice(0, 3).join(' | '));
}

(async () => {
  for (const [name, fn] of [['plan', t_plan], ['capacity', t_capacity], ['rules', t_rules], ['checks', t_checks]]) {
    const { browser, page, errors } = await launch();
    try {
      await open(page, 800);
      await fn(page, errors);
    } catch (e) {
      ok(`${name}: сценарій не впав`, false, String(e.message).split('\n').slice(0, 3).join(' '));
    }
    await browser.close();
  }
  const failed = res.filter((x) => !x).length;
  console.log(`\nИТОГО S2: ${res.length - failed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
