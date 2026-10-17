const { launch, open, DIR } = require('./harness');
(async () => {
  const { browser, page, errors } = await launch();
  await open(page);
  const info = await page.evaluate(() => ({ layers: __f3d.S.layers.length, slots: __f3d.S.slots.length, pl: __f3d.S.placements.length, issues: __f3d.S.issues.list.length, ok: __f3d.V.ok, views: __f3d.V.views.size }));
  console.log(JSON.stringify(info));
  const iss = await page.evaluate(() => __f3d.S.issues.list.slice(0, 25).map((i) => i.level + ' ' + i.msg));
  console.log(iss.join('\n'));
  await page.screenshot({ path: DIR + '/shots/_smoke.png' });
  console.log('ERRORS:', errors.slice(0, 10));
  await browser.close();
})();
