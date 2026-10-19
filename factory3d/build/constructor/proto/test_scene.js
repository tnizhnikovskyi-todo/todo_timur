// Повнота сцени: усі 31 шар і усі кодовані об'єкти 3D-моделі (scene_inventory.json) є в прикладі прототипу
const fs = require('fs');
const { launch, open } = require('./harness');
const INV = process.env.SCENE_INVENTORY || require('path').join(__dirname, '../../../odoo_addons/td_constructor/data/scene_inventory.json');
let pass = 0, fail = 0;
const ok = (n, c, d) => { if (c) { pass++; console.log('PASS', n, d !== undefined ? ':: ' + d : ''); } else { fail++; console.log('FAIL', n, d !== undefined ? ':: ' + d : ''); } };
(async () => {
  const inv = JSON.parse(fs.readFileSync(INV, 'utf8'));
  const { browser, page, errors } = await launch();
  await open(page);
  const size = fs.statSync(__dirname + '/index.html').size;
  ok('розмір сторінки < 900 КБ (збірка F3D_PROTO_MINIFY=1 після S1…S6: 833 КБ; +15 % дало б 957 КБ — стеля 900 КБ; після S5 було 697 КБ)', size < 900 * 1024, Math.round(size / 1024) + ' КБ');
  const st = await page.evaluate((codes) => {
    const S = __f3d.S, covered = new Set();
    for (const p of S.placements) covered.add(p.code);
    for (const s of S.slots) { covered.add(s.code_prefix); if (s.scene_code) covered.add(s.scene_code); for (const c of __f3d.cellsOf(s)) covered.add(c.code); }
    const missing = codes.filter((c) => !covered.has(c));
    const iss = S.issues.list;
    return { visible: S.layers.filter((l) => l.visible).length, layers: S.layers.length, groups: [...new Set(S.layers.map((l) => l.group))].length, missing, blocks: iss.filter((i) => i.level === 'block').length, issues: iss.length,
      pl: S.placements.length, slots: S.slots.length, dyn: S.placements.filter((p) => p.dynamic).map((p) => p.code), zed: S.placements.filter((p) => p.z).length,
      keys: S.layers.map((l) => l.key + '|' + l.name + '|' + l.group).join(';'), ok: __f3d.V.ok };
  }, Object.keys(inv.objects));
  ok('31 шар', st.layers === 31, st.layers);
  ok('шари збігаються з переглядачем (ключ, назва, група)', st.keys === inv.layers.map((l) => l.key + '|' + l.label + '|' + l.group).join(';'));
  ok('при відкритті видимі 13 шарів (мережі, пожежа, ІТ, територія й дах приховані)', st.visible === 13, st.visible);
  ok('8 груп шарів', st.groups === 8, st.groups);
  ok('усі ' + Object.keys(inv.objects).length + ' кодованих об’єктів моделі є в прикладі', st.missing.length === 0, st.missing.slice(0, 8).join(','));
  ok('0 блокувань і 0 попереджень при відкритті', st.blocks === 0 && st.issues === 0, `blocks=${st.blocks} issues=${st.issues}`);
  const expDyn = Object.entries(inv.objects).filter(([, o]) => o.kind === 'person' || o.kind === 'vehicle').map(([c]) => c).sort().join(',');
  ok('люди й транспорт — динамічні', st.dyn.sort().join(',') === expDyn, st.dyn.length);
  ok('зміщення z зберігається для об’єктів вище підлоги', st.zed > 20, st.zed);
  const ui = await page.evaluate(() => ({ groups: document.querySelectorAll('#layerList .lgroup').length, layers: document.querySelectorAll('#layerList .layer').length, txt: [...document.querySelectorAll('#layerList .lgroup span:first-child')].map((e) => e.textContent).join('|') }));
  ok('список «Шари»: 8 заголовків груп і 31 шар', ui.groups === 8 && ui.layers === 31, JSON.stringify(ui));
  const cells = await page.evaluate(() => {
    const S = __f3d.S, one = (c) => __f3d.cellsOf(S.slots.find((s) => s.code_prefix === c)).map((x) => x.code);
    return { unload: one('UNLOAD-4'), rck: one('RCK-R8').slice(-2), eb: one('EB-U2').slice(-2), fur: one('FUR-R6').slice(-1), plt: one('PLT-09C') };
  });
  ok('code_style exact: одна комірка з кодом місця', cells.unload.length === 1 && cells.unload[0] === 'UNLOAD-4' && cells.plt[0] === 'PLT-09C', JSON.stringify(cells));
  ok('коди комірок стелажів збігаються з моделлю', cells.rck.join() === 'RCK-R8-3C,RCK-R8-3D' && cells.eb.join() === 'EB-U2-S4-L2,EB-U2-S4-L3' && cells.fur[0] === 'FUR-R6-S06-L4', JSON.stringify(cells));
  const roles = await page.evaluate(() => Object.fromEntries(__f3d.S.layers.map((l) => [l.key, l.edit_roles.join('+') + '/' + l.kind])));
  ok('ролі й види шарів за групами', roles.fg === 'manager+storekeeper/storage' && roles.line === 'manager+technologist/production' && roles.energy === 'manager+engineer/engineering' && roles.fire === 'manager+engineer/engineering'
    && roles.odoo_it === 'manager+engineer/engineering' && roles.territory === 'manager/yard' && roles.people === 'manager/custom' && roles.building === 'manager/building', JSON.stringify(roles));
  const pp = await page.evaluate(() => __f3d.S.catalog.filter((p) => p.role.startsWith('scene_')).map((p) => p.name + ':' + p.variants.length));
  ok('автопаспорти «Об’єкти сцени» на вид', pp.length >= 10 && pp.every((x) => x.startsWith('Об’єкти сцени')), pp.join(' | '));
  // активація інженерного шару показує його об'єкти
  await page.click('.layer[data-layer="ly_lighting"]'); await page.waitForTimeout(400);
  const act = await page.evaluate(() => ({ ly: __f3d.S.ui.layer, el: __f3d.S.layers.find((l) => l.key === 'lighting').elevation }));
  const vis = await page.evaluate(() => !__f3d.V.hidden.has('ly_lighting')); // видимість шару — стан сеансу (V.hidden), а не поле запису
  ok('активація інженерного шару «Освітлення» робить його видимим', act.ly === 'ly_lighting' && act.el > 7 && vis === true, JSON.stringify(act));
  ok('консоль без помилок', errors.length === 0, errors.slice(0, 4).join(' | '));
  await browser.close();
  console.log(`\nІТОГО: ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
