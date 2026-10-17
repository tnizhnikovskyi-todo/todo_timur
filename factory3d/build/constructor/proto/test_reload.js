const { launch, open } = require('./harness');
(async () => {
  const { browser, page, errors } = await launch();
  await open(page, 600);
  await page.evaluate(() => { const p = __f3d.S.placements.find((q) => q.code === 'PACK-1'); p.y += 2; __f3d.commit({ dirty: ['placements'] }); });
  await page.waitForTimeout(1500);
  const c1 = await page.textContent('#draftChip');
  await page.reload(); await page.waitForFunction(() => document.documentElement.dataset.ready === '1'); await page.waitForTimeout(800);
  const c2 = await page.textContent('#draftChip');
  const pos = await page.evaluate(() => __f3d.S.placements.find((q) => q.code === 'PACK-1').y);
  const notice = await page.evaluate(() => document.querySelector('#vnotice').children.length);
  console.log(c1, '|', c2, '| y=', pos, '| notice=', notice, '| versions=', await page.evaluate(() => __f3d.S.versions.length), errors);
  // «Завантажити приклад» из пустого хранилища
  const ctx2 = await browser.newContext(); const p2 = await ctx2.newPage();
  await browser.close();
})();
