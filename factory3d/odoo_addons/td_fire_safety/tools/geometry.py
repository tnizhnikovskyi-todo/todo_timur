"""Геометрія пожежної безпеки (SPEC R-02, R-03, R-04): сітки покриття, відстані. Чисті функції, без ORM."""
import math

INF_GAP = 9999.0  # значення «розрив необмежений» (немає пристроїв), що зберігається в Float-полі


def fmt_point(x, y):
    """Формат точки R-02: «(122.0, 54.1)»."""
    return "(%s, %s)" % (round(x, 2), round(y, 2))


def grid_axis(a0, a1, step):
    """Координати сітки: a0 + step·i, i = 0…floor((a1 − a0)/step + 1e-9)."""
    n = int(math.floor((a1 - a0) / step + 1e-9))
    return [a0 + step * i for i in range(n + 1)]


def point_in_rect(x, y, x0, y0, x1, y1):
    return x0 <= x <= x1 and y0 <= y <= y1


def _min_dist(x, y, points):
    best = None
    for px, py in points:
        d = (x - px) ** 2 + (y - py) ** 2
        if best is None or d < best:
            best = d
    return math.sqrt(best) if best is not None else math.inf


def max_gap(points, xs, ys):
    """Найбільша з мінімальних відстаней від вузлів сітки (xs × ys) до `points` [(x, y)].

    Цикл за x зовнішній, за y внутрішній; точка максимуму — перша (строге «>»).
    Повертає (gap, (x, y)); без точок gap = inf, точка — перший вузол.
    """
    best, best_pt = -1.0, (xs[0], ys[0])
    if not points:
        return math.inf, best_pt
    for x in xs:
        for y in ys:
            d = _min_dist(x, y, points)
            if d > best:
                best, best_pt = d, (x, y)
    return best, best_pt


def coverage_gap(points_by_floor, x0, y0, x1, y1, step=0.5):
    """R-02: найбільший розрив покриття зони по поверхах.

    `points_by_floor` — список списків [(x, y)] активних детекторів по кожному поверху зони.
    Повертає (gap, (x, y)); поверх без детекторів дає gap = inf.
    """
    xs, ys = grid_axis(x0, x1, step), grid_axis(y0, y1, step)
    worst, worst_pt = -1.0, (xs[0], ys[0])
    for points in points_by_floor or [[]]:
        gap, pt = max_gap(points, xs, ys)
        if gap > worst:
            worst, worst_pt = gap, pt
    return worst, worst_pt


def plant_grid_gap(points, length, width, step=2.0):
    """R-03/R-04: сітка 2 м по будівлі (0…length × 0…width); повертає (max_d, (x, y))."""
    return max_gap(points, grid_axis(0.0, float(length), step), grid_axis(0.0, float(width), step))


def site_bounds(env):
    """Територія CB-12: (x0, y0, x1, y1) із параметрів td.base.site_*."""
    get = env["ir.config_parameter"].sudo().get_param
    return (float(get("td.base.site_x0_m", -32)), float(get("td.base.site_y0_m", -30)),
            float(get("td.base.site_x1_m", 182)), float(get("td.base.site_y1_m", 100)))


def plant_size(env):
    """Будівля CB-12: (довжина, ширина) з параметрів td.base.plant_*."""
    get = env["ir.config_parameter"].sudo().get_param
    return float(get("td.base.plant_length_m", 150)), float(get("td.base.plant_width_m", 72))
