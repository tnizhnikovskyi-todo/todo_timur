// Раскладка в метрах: группы — по горизонтали; ряды стеллажей — один за другим вглубь; стеллажи ряда — вдоль ряда; ярусы — вверх.
// Ряд, перетянутый мышкой, стоит там, где его поставили (координаты внутри родителя); родитель расширяется под него.

function posOverride(tree, n, pad) {
  let any = false;
  for (const k of n.kids) { const p = tree.pos.get(k.id); if (p) { k.ox = p.x; k.oy = p.y; k.moved = true; any = true; } }
  if (any) { n.w = Math.max(n.w, ...n.kids.map((k) => k.ox + k.w + pad)); n.d = Math.max(n.d, ...n.kids.map((k) => k.oy + k.d + pad)); }
}

function measure(tree, n, depth = 0) {
  n.depth = depth;
  const t = tree.TY(n.tp);
  const [tw, td] = n.rot ? [t.d, t.w] : [t.w, t.d];
  if (n.type === "level") { n.w = tw; n.d = td; n.h = (n.lvl + 1) * t.lh; return; }
  if (n.type === "bayleaf") { n.w = tw; n.d = td; n.h = 1.1; return; }
  n.kids.forEach((k) => measure(tree, k, depth + 1));
  const H = n.kids.length ? Math.max(...n.kids.map((k) => k.h)) : 0.2;
  if (n.type === "bay") { n.w = tw; n.d = td; n.nLv = n.kids.length ? Math.max(...n.kids.map((k) => k.lvl)) + 1 : 0; n.h = n.nLv * t.lh + 0.2; n.kids.forEach((k) => { k.ox = 0; k.oy = 0; }); return; }
  if (n.type === "rack") {
    if (!n.kids.length) { n.w = tw; n.d = td; n.h = 0.2; return; }
    let a = 0; const g = t.form === "stack" ? 0.6 : 0.08;
    n.kids.forEach((k) => { if (n.rot) { k.ox = 0; k.oy = a; a += k.d + g; } else { k.ox = a; k.oy = 0; a += k.w + g; } });
    if (n.rot) { n.w = Math.max(...n.kids.map((k) => k.w)); n.d = a - g; } else { n.w = a - g; n.d = Math.max(...n.kids.map((k) => k.d)); }
    n.h = H; return;
  }
  if (n.type === "rackset") {
    let y = 0; const g = tree.TY(n.kids[0].tp).form === "stack" ? 1.2 : 2.4;
    n.kids.forEach((k) => { k.ox = 0; k.oy = y; y += k.d + g; });
    n.w = Math.max(...n.kids.map((k) => k.w)); n.d = y - g; posOverride(tree, n, 0); n.h = H; return;
  }
  if (!n.kids.length) { if (n.loc) { n.w = t.w; n.d = t.d; } else { n.w = 4; n.d = 4; } n.h = 1.2; return; }
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
