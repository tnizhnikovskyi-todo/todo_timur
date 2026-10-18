const { launch, open } = require('./harness');
(async () => {
  const { browser, page, errors } = await launch();
  await open(page, 600);
  await page.click('.layer[data-layer="ly_fg"]');
  await page.evaluate(() => { const V = __f3d.V; V.controls.target.set(125, 0, -27); V.camera.position.set(100, 38, -3); V.controls.update(); });
  await page.waitForTimeout(400);
  const pt = await page.evaluate(() => { const s = __f3d.S.slots.find((x) => x.code_prefix === 'FG-R1'); const c = __f3d.cellsOf(s)[40]; const w = __f3d.sGeom ? null : null; const a = (s.rotation) * Math.PI / 180; const x = s.x + c.lx * Math.cos(a) - c.ly * Math.sin(a), y = s.y + c.lx * Math.sin(a) + c.ly * Math.cos(a); const v = new THREE.Vector3(x, c.dz + c.h / 2 + 0.1, -y).project(__f3d.V.camera), r = __f3d.V.canvas.getBoundingClientRect(); return { sx: r.left + (v.x + 1) / 2 * r.width, sy: r.top + (1 - v.y) / 2 * r.height, code: c.code }; });
  await page.mouse.click(pt.sx, pt.sy); await page.waitForTimeout(400);
  const sel = await page.evaluate(() => ({ cell: __f3d.S.selCell, sel: __f3d.S.sel && __f3d.S.sel.id }));
  console.log('target', pt.code, 'got', JSON.stringify(sel), errors);
  await browser.close();
})();
