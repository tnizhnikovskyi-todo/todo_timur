// Збірка відео A-21c одним викликом: facts.json -> заставки (rec_cards) -> монтаж (montage) -> check_video.py. Без Odoo й без перезйомки.
// Використання (з кореня репо галузі): node build_video.mjs --root <prototype-real> [full|reels|all] [--sample] [--intake OWNER-INTAKE.md]
import fs from 'fs'; import path from 'path';
import { execFileSync, spawnSync } from 'child_process';
import { here, ROOT, REC, flag, opt, positional, loadCaptions, loadFacts, die } from './lib.mjs';

const cap = loadCaptions(); loadFacts(); // падає, якщо facts.json немає або має checks з ok:false
const which = positional[0] || 'all'; const sample = flag('sample');
const node = (script, args) => execFileSync(process.execPath, [path.join(here, script), '--root', ROOT, ...args], { stdio: 'inherit' });
const need = Object.keys(cap.cards || {}).filter((n) => !fs.existsSync(path.join(REC, `card_${n}.mp4`)) || flag('cards'));
if (need.length) node('rec_cards.mjs', need);
node('montage.mjs', [which, ...(sample ? ['--sample'] : [])]);
const intake = opt('intake');
const args = [path.join(here, 'check_video.py'), path.join(ROOT, 'video'), ...(intake ? ['--intake', intake] : []), ...(sample ? ['--sample'] : [])];
const r = spawnSync('python3', ['-I', ...args], { stdio: 'inherit' });
if (r.status) die('check_video.py: є FAIL — виправити титри/фрагменти (captions.yaml) і зібрати знову; перезйомка — лише через повернення в A-21');
