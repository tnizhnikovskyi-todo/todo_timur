#!/bin/bash
# Збирає еталонний мокап «Пульт КГУ» в один index.html (three.js r147 з CDN — лише для еталона; у td_chp — власна копія).
D="$(cd "$(dirname "$0")" && pwd)"
{ cat "$D/a_head.html"
  echo '<script src="https://cdn.jsdelivr.net/npm/three@0.147.0/build/three.min.js"></script>'
  echo '<script src="https://cdn.jsdelivr.net/npm/three@0.147.0/examples/js/controls/OrbitControls.js"></script>'
  cat "$D/b_sim.js" "$D/d_scheme.js" "$D/c_3d.js"
} > "$D/index.html"
wc -c < "$D/index.html"
