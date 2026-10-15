// Раскладка в метрах: группы — по горизонтали; ряды стеллажей — один за другим вглубь; стеллажи ряда — вдоль ряда; ярусы — вверх.
// Параметры конструкции (params.js): высота каждого яруса отдельно, нижний ярус на полу или поднят, зазоры, двусторонний ряд (спина к спине).
// Ряд, перетянутый мышкой, стоит там, где его поставили (координаты внутри родителя); родитель расширяется под него.

import { levelBase, levelH, levelsTop } from "./params.js";

function posOverride(tree, n, pad) {
  let any = false;
  for (const k of n.kids) { const p = tree.pos.get(k.id); if (p) { k.ox = p.x; k.oy = p.y; k.moved = true; any = true; } }
  if (any) { n.w = Math.max(n.w, ...n.kids.map((k) => k.ox + k.w + pad)); n.d = Math.max(n.d, ...n.kids.map((k) => k.oy + k.d + pad)); }
}

function measure(tree, n, depth = 0) {
  n.depth = depth;
  const t = tree.EP(n);
  const [tw, td] = n.rot ? [t.d, t.w] : [t.w, t.d];
  if (n.type === "level") {
    n.w = tw; n.d = td; n.h = levelBase(t, n.lvl) + levelH(t, n.lvl);
    // ячейки яруса — части его основания: вдоль ширины стелажа (повёрнутый ряд — вдоль глубины)
    const N = n.kids.length;
    n.kids.forEach((k, i) => {
      k.depth = depth + 1; k.h = n.h;
      if (n.rot) { k.w = n.w; k.d = n.d / N; k.ox = 0; k.oy = i * k.d; } else { k.w = n.w / N; k.d = n.d; k.ox = i * k.w; k.oy = 0; }
    });
    return;
  }
  if (n.type === "bayleaf") { n.w = tw; n.d = td; n.h = t.h > 0 ? t.h : 1.1; return; }
  n.kids.forEach((k) => measure(tree, k, depth + 1));
  const H = n.kids.length ? Math.max(...n.kids.map((k) => k.h)) : 0.2;
  if (n.type === "bay") { n.w = tw; n.d = td; n.nLv = n.kids.length ? Math.max(...n.kids.map((k) => k.lvl)) + 1 : 0; n.h = levelsTop(t, n.nLv) + 0.2; n.kids.forEach((k) => { k.ox = 0; k.oy = 0; }); return; }
  if (n.type === "rack") {
    if (!n.kids.length) { n.w = tw; n.d = td; n.h = 0.2; return; }
    const stack = t.form === "stack", g = stack ? 0.6 : (t.gap ?? 0.08), N = n.kids.length;
    if (t.dbl && !stack && N > 1) { // двусторонний ряд: секции парами спиной к спине, вдоль ряда идут пары
      const rg = t.rg ?? 0.1, cols = Math.ceil(N / 2), al = (k) => (n.rot ? k.d : k.w), dp = (k) => (n.rot ? k.w : k.d);
      const cw = Array.from({ length: cols }, (_, c) => Math.max(...n.kids.filter((_k, i) => i >> 1 === c).map(al))), side = Math.max(...n.kids.map(dp));
      let u0 = 0; const off = cw.map((w) => { const o = u0; u0 += w + g; return o; });
      n.kids.forEach((k, i) => { const u = off[i >> 1], v = (i & 1) * (side + rg); if (n.rot) { k.ox = v; k.oy = u; } else { k.ox = u; k.oy = v; } });
      if (n.rot) { n.w = 2 * side + rg; n.d = u0 - g; } else { n.w = u0 - g; n.d = 2 * side + rg; }
      n.h = H; return;
    }
    let a = 0;
    n.kids.forEach((k) => { if (n.rot) { k.ox = 0; k.oy = a; a += k.d + g; } else { k.ox = a; k.oy = 0; a += k.w + g; } });
    if (n.rot) { n.w = Math.max(...n.kids.map((k) => k.w)); n.d = a - g; } else { n.w = a - g; n.d = Math.max(...n.kids.map((k) => k.d)); }
    n.h = H; return;
  }
  if (n.type === "rackset") {
    let y = 0; const g = tree.TY(n.kids[0].tp).form === "stack" ? 1.2 : 2.4;
    n.kids.forEach((k) => { k.ox = 0; k.oy = y; y += k.d + g; });
    n.w = Math.max(...n.kids.map((k) => k.w)); n.d = y - g; posOverride(tree, n, 0); n.h = H; return;
  }
  if (!n.kids.length) { if (n.loc) { n.w = t.w; n.d = t.d; } else { n.w = 4; n.d = 4; } n.h = n.loc && t.h > 0 ? t.h : 1.2; return; }
  // группа: листья (ворота, тележки) — сеткой, подгруппы — справа по горизонтали;
  // порядок детей сохраняем; соседние листья собираем в один блок, больше 8 — в два ряда
  const pad = 1, head = 1.6, gap = depth <= 1 ? 4 : 2.5, blocks = [];
  const isLeaf = (k) => !k.kids.length && k.type === "group";
  for (let i = 0; i < n.kids.length;) {
    if (!isLeaf(n.kids[i])) { const k = n.kids[i++]; blocks.push({ items: [k], w: k.w, d: k.d }); continue; }
    const run = []; while (i < n.kids.length && isLeaf(n.kids[i])) run.push(n.kids[i++]);
    const cols = run.length > 8 ? Math.ceil(run.length / 2) : run.length, lg = 0.6;
    const cw = Math.max(...run.map((k) => k.w)), ch = Math.max(...run.map((k) => k.d));
    run.forEach((k, j) => { k.ox = (j % cols) * (cw + lg); k.oy = Math.floor(j / cols) * (ch + lg); });
    blocks.push({ items: run, w: cols * (cw + lg) - lg, d: Math.ceil(run.length / cols) * (ch + lg) - lg, block: true });
  }
  let x = pad;
  for (const b of blocks) { for (const k of b.items) { if (b.block) { k.ox += x; k.oy += head; } else { k.ox = x; k.oy = head; } } x += b.w + gap; }
  n.w = x - gap + pad; n.d = head + Math.max(...blocks.map((b) => b.d)) + pad; posOverride(tree, n, pad); n.h = H;
}

function place(n, x, y) { n.x = x; n.y = y; n.kids.forEach((k) => place(k, x + k.ox, y + k.oy)); }

// считает размеры и абсолютные координаты всех узлов; пишет tree.W0 / tree.D0
export function layout(tree) {
  measure(tree, tree.root);
  place(tree.root, 0, 0);
  tree.W0 = tree.root.w; tree.D0 = tree.root.d;
  return tree;
}
