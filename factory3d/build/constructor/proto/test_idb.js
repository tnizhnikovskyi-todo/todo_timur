const { launch, open, DIR } = require('./harness');
(async () => {
  const { browser, page, errors } = await launch();
  await open(page);
  await page.click('#ltabs button[data-tab="catalog"]');
  await page.click('.var >> nth=0 >> text=Змінити'); await page.waitForSelector('dialog[open]');
  await page.setInputFiles('#modelFile', DIR + '/fixtures/pyramid_mm.stl'); await page.waitForTimeout(800);
  await page.click('dialog button:has-text("Зберегти")'); await page.waitForTimeout(1500);
  // DXF тоже
  await page.click('button:has-text("Підкладка DXF")'); await page.setInputFiles('#dxfFile', DIR + '/fixtures/plan_mm.dxf'); await page.waitForTimeout(800);
  await page.waitForTimeout(1500);
  await page.reload(); await page.waitForFunction(() => document.documentElement.dataset.ready === '1'); await page.waitForTimeout(1500);
  const r = await page.evaluate(() => ({ models: __f3d.V.models.size, ul: __f3d.V.underlays.size, ulMeta: __f3d.S.layers.filter((l) => l.underlay).length }));
  console.log(JSON.stringify(r), r.models === 1 && r.ul === 1 ? 'PASS IDB persisted across reload' : 'FAIL');
  console.log('ERR', errors);
  await browser.close();
})();
