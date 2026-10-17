const { launch, open, DIR } = require('./harness');
(async () => {
  const { browser, ctx, page, errors } = await launch();
  await ctx.addInitScript(() => {
    const thrower = () => { throw new DOMException('denied', 'SecurityError'); };
    Object.defineProperty(window, 'localStorage', { get: thrower });
    Object.defineProperty(window, 'indexedDB', { get: () => undefined });
  });
  await open(page, 600);
  console.log('kind', await page.evaluate(() => __f3d.store.kind), await page.textContent('#storeTag'));
  await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'PACK-1'); p.y += 2; __f3d.commit({ dirty: ['placements'] }); });
  await page.waitForTimeout(1500);
  await page.click('#btnPublish'); await page.waitForSelector('dialog[open]'); await page.click('dialog button:has-text("Підтвердити й опублікувати")'); await page.waitForTimeout(800);
  console.log('versions', await page.evaluate(() => __f3d.S.versions.length));
  await page.click('#ltabs button[data-tab="catalog"]'); await page.click('.var >> nth=0 >> text=Картка'); await page.waitForSelector('dialog[open]');
  await page.setInputFiles('#modelFile', DIR + '/fixtures/pyramid_mm.stl'); await page.waitForTimeout(700);
  await page.click('dialog button:has-text("Зберегти")'); await page.waitForTimeout(700);
  console.log('models', await page.evaluate(() => __f3d.V.models.size));
  console.log('ERR', errors);
  await browser.close();
})();
