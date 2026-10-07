// Visual check of the genset mockup: screenshots of every page at PC and phone width,
// horizontal-overflow report and page errors.
//
//   node smartgen/tools/check_layout.js [mockup.html] [outdir] [light,dark]
//
// The artifact service wraps the page in a skeleton (doctype, viewport meta, base styles)
// on publish; publish_head.html is that skeleton, so local renders match the published page.
const fs = require("fs");
const path = require("path");
let chromium;
try { ({ chromium } = require("playwright")); } catch { ({ chromium } = require("/opt/node-tools/node_modules/playwright")); }

const here = __dirname;
const src = path.resolve(process.argv[2] || path.join(here, "..", "mockup_odoo_genset.html"));
const outdir = path.resolve(process.argv[3] || path.join(here, "..", "shots"));
const schemes = (process.argv[4] || "light").split(",");
const SIZES = [["pc", 1440, 900], ["phone", 390, 844]];
const PAGES = ["form", "readings", "analytics", "events", "fuel", "settings"];

(async () => {
  fs.mkdirSync(outdir, { recursive: true });
  const page = path.join(outdir, "_render.html");
  fs.writeFileSync(page, fs.readFileSync(path.join(here, "publish_head.html"), "utf8") + fs.readFileSync(src, "utf8") + "</body></html>");
  const browser = await chromium.launch();
  let problems = 0;
  for (const scheme of schemes) for (const [size, w, h] of SIZES) {
    const phone = size === "phone";
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: phone ? 2 : 1, colorScheme: scheme, isMobile: phone, hasTouch: phone });
    const p = await ctx.newPage();
    p.on("pageerror", e => { problems++; console.log(`ERROR ${scheme} ${size}: ${e.message}`); });
    for (const name of PAGES) {
      await p.goto(`file://${page}#${name}`);
      await p.waitForTimeout(name === "form" ? 1500 : 600);
      const sw = await p.evaluate(() => document.documentElement.scrollWidth);
      const flag = sw > w ? `  OVERFLOW: page is ${sw}px wide` : "";
      if (flag) problems++;
      console.log(`${scheme} ${size} ${name}${flag}`);
      await p.screenshot({ path: path.join(outdir, `${scheme}_${size}_${name}.png`), fullPage: true });
    }
    await ctx.close();
  }
  await browser.close();
  fs.unlinkSync(page);
  console.log(problems ? `${problems} problem(s)` : `ok, screenshots in ${outdir}`);
  process.exitCode = problems ? 1 : 0;
})();
