"""Евакуація: аварійні виходи на довгих стінах, найкоротші шляхи до них в обхід обладнання й
перегородок (Дейкстра на сітці 0,5 м), найбільша відстань від робочого місця до виходу.

Перешкоди бере з layout.OBST, тож рахувати треба після збирання сцени (site.build_evacuation).
Результат пишеться в evac_routes.json — його читає odoo_demo.py без Blender.
"""
import heapq
import json
import math
import os

from .layout import D, W, ZONES

ROUTES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evac_routes.json")
STEP = 0.5
DOOR_W = 1.2  # аварійні двері 1,2 м у світлі

# Виходи: code, x, y (на стіні), бік. Місця — у проміжках між обладнанням біля стін.
EXITS = [("EX-S1", 14.0, 0.0, "S"), ("EX-S2", 51.0, 0.0, "S"), ("EX-S3", 68.5, 0.0, "S"),
         ("EX-S4", 91.0, 0.0, "S"), ("EX-S5", 110.8, 0.0, "S"), ("EX-S6", 135.4, 0.0, "S"),
         ("EX-N1", 14.0, D, "N"), ("EX-N2", 50.0, D, "N"), ("EX-N3", 75.0, D, "N"), ("EX-N5", 111.0, D, "N"),
         ("EX-N4", 140.0, D, "N"), ("EX-IN", 98.4, 0.0, "S")]  # EX-N5 — з компресорної, EX-IN — вхід персоналу

# Перегородки (для пошуку шляху): (x0, y0, x1, y1, [прорізи (центр, ширина)])
WALLS = [
    (42.0, 46.0, 92.0, 46.0, [(48.5, 4.0), (66.0, 3.0), (89.0, 4.0)]),
    (42.0, 46.0, 42.0, D, [(64.0, 2.0)]),
    (92.0, 46.0, 92.0, D, [(52.0, 2.0)]),
    (58.0, 66.0, 58.0, D, []), (66.0, 66.0, 66.0, D, []), (58.0, 66.0, 66.0, 66.0, [(62.0, 1.6)]),
    (110.0, 60.0, 122.0, 60.0, [(113.0, 1.6), (119.0, 3.6)]),
    (110.0, 60.0, 110.0, D, []), (116.0, 60.0, 116.0, D, []),
]
BIG_AREA = 300.0  # великі прямокутники OBST — це «без колон», а не непрохідні зони (склад плит, відвантаження)


def _grid(obst_rects):
    nx, ny = int(W / STEP), int(D / STEP)
    free = [[True] * ny for _ in range(nx)]

    def block(x0, y0, x1, y1):
        for i in range(max(0, int(x0 / STEP)), min(nx, int(math.ceil(x1 / STEP)))):
            for j in range(max(0, int(y0 / STEP)), min(ny, int(math.ceil(y1 / STEP)))):
                free[i][j] = False

    for x0, y0, x1, y1 in obst_rects:
        if (x1 - x0) * (y1 - y0) < BIG_AREA:
            block(x0, y0, x1, y1)
    for x0, y0, x1, y1, gaps in WALLS:
        if y0 == y1:
            segs, pos = [], x0
            for c, w in sorted(gaps):
                segs.append((pos, c - w / 2))
                pos = c + w / 2
            segs.append((pos, x1))
            for a, b in segs:
                block(a, y0 - 0.15, b, y0 + 0.15)
        else:
            segs, pos = [], y0
            for c, w in sorted(gaps):
                segs.append((pos, c - w / 2))
                pos = c + w / 2
            segs.append((pos, y1))
            for a, b in segs:
                block(x0 - 0.15, a, x0 + 0.15, b)
    return free, nx, ny


def _dijkstra(free, nx, ny):
    dist = [[math.inf] * ny for _ in range(nx)]
    prev = {}
    heap = []
    for code, x, y, side in EXITS:
        j = 0 if side == "S" else ny - 1
        for i in range(int((x - DOOR_W / 2) / STEP), int((x + DOOR_W / 2) / STEP) + 1):
            if 0 <= i < nx and free[i][j]:
                dist[i][j] = STEP / 2
                heapq.heappush(heap, (STEP / 2, i, j))
                prev[(i, j)] = code
    nb = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142),
          (-1, -1, 1.4142)]
    while heap:
        d, i, j = heapq.heappop(heap)
        if d > dist[i][j]:
            continue
        for di, dj, c in nb:
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and free[a][b]:
                if di and dj and not (free[i + di][j] and free[i][j + dj]):
                    continue  # не зрізати кути перешкод
                nd = d + c * STEP
                if nd < dist[a][b]:
                    dist[a][b] = nd
                    prev[(a, b)] = (i, j)
                    heapq.heappush(heap, (nd, a, b))
    return dist, prev


def _path(prev, i, j):
    pts = []
    cur = (i, j)
    while isinstance(cur, tuple):
        pts.append(((cur[0] + 0.5) * STEP, (cur[1] + 0.5) * STEP))
        cur = prev.get(cur)
    return pts, cur  # cur — код виходу


def _simplify(pts, tol=0.6):
    """Дуглас—Пекер: лишає кути маршруту."""
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    L = math.hypot(x1 - x0, y1 - y0) or 1e-9
    k, dmax = 0, 0
    for n, (x, y) in enumerate(pts[1:-1], 1):
        d = abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / L
        if d > dmax:
            k, dmax = n, d
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return _simplify(pts[:k + 1], tol)[:-1] + _simplify(pts[k:], tol)


def compute(obst_rects):
    free, nx, ny = _grid(obst_rects)
    dist, prev = _dijkstra(free, nx, ny)
    worst = (0, None)
    for i in range(nx):
        for j in range(ny):
            if free[i][j] and dist[i][j] < math.inf and dist[i][j] > worst[0]:
                worst = (dist[i][j], ((i + 0.5) * STEP, (j + 0.5) * STEP))
    routes = {}
    for code, name, (x0, y0, x1, y1), *_ in ZONES:
        if code in ("Z-OFFICE", "Z-SOC"):
            continue  # модулі мають власні виходи
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        best = None
        for r in range(0, 40):  # найближча вільна клітинка до центру зони
            for i in range(int((cx - r * STEP) / STEP), int((cx + r * STEP) / STEP) + 1):
                for j in range(int((cy - r * STEP) / STEP), int((cy + r * STEP) / STEP) + 1):
                    if 0 <= i < nx and 0 <= j < ny and free[i][j] and dist[i][j] < math.inf:
                        if best is None or dist[i][j] < dist[best[0]][best[1]]:
                            best = (i, j)
            if best:
                break
        if not best:
            continue
        pts, exit_code = _path(prev, *best)
        routes[code] = dict(name=name, exit=exit_code, length=round(dist[best[0]][best[1]], 1),
                            path=[(round(x, 2), round(y, 2)) for x, y in _simplify(pts)])
    return dict(exits=[dict(code=c, x=x, y=y, side=s) for c, x, y, s in EXITS], routes=routes,
                max_distance=round(worst[0], 1), worst_point=worst[1])


def save(data):
    with open(ROUTES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load():
    if not os.path.exists(ROUTES_PATH):
        return None
    with open(ROUTES_PATH, encoding="utf-8") as f:
        return json.load(f)
