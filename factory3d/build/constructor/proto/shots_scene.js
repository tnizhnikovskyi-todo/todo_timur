// Знімки прикладу з усіма шарами й об'єктами: overview, layers (групи), engineering, mobile
const { launch, open, DIR } = require('./harness');
const SH = DIR + '/shots/';
(async () => {
  let { browser, page, errors } = await launch();
  await open(page, 2500);
  await page.screenshot({ path: SH + 'overview.png' });
  // Шари: панель зі списком по групах
  await page.evaluate(() => { const l = document.querySelector('#layerList .layers'); if (l) l.scrollTop = 0; });
  await page.screenshot({ path: SH + 'layers.png' });
  // Інженерія: активний шар «Електропостачання», решта інженерних видимі; вигляд iso
  await page.click('.layer[data-layer="energy"]'); await page.waitForTimeout(400);
  for (const k of ['ventilation', 'lighting']) { await page.click(`.layer[data-layer="${k}"] button.eye`); await page.waitForTimeout(150); }
  await page.evaluate(() => { const l = document.querySelector('#layerList .layers'); const a = document.querySelector('.layer[data-layer="energy"]'); if (a) a.scrollIntoView({ block: 'center' }); });
  await page.evaluate(() => __f3d.setView('iso'));
  await page.waitForTimeout(800);
  await page.screenshot({ path: SH + 'engineering.png' });
  // Пожежна безпека
  await page.click('.layer[data-layer="fire"]'); await page.waitForTimeout(600);
  await page.click('.layer[data-layer="evacuation"] button.eye'); await page.waitForTimeout(400);
  await page.screenshot({ path: SH + 'fire.png' });
  console.log('desktop errors', errors.length, errors.slice(0, 3));
  await browser.close();
  ({ browser, page, errors } = await launch({ viewport: { width: 400, height: 800 } }));
  await open(page, 2500);
  await page.screenshot({ path: SH + 'mobile.png' });
  await page.click('#mtabs button[data-mtab="layers"]').catch(() => {}); await page.waitForTimeout(400);
  await page.screenshot({ path: SH + 'mobile_layers.png' });
  console.log('mobile errors', errors.length, errors.slice(0, 3));
  await browser.close();
})();
