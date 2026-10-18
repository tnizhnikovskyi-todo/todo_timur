"""R-04: звичайна регресія найменших квадратів. Чистий Python (без numpy/scipy), без ORM.

`fit(X, y)` — `X` — список рядків значень драйверів (без одиниці), `y` — ряд. Розв'язок нормальних рівнянь
`(XᵀX)β = Xᵀy` методом Гауса з частковим вибором головного елемента; стовпці центруються й нормуються на σ
(математично те саме, але стійко до масштабу: `x ≈ 800…1400` не псує точність константи).
"""

import math

SINGULAR_EPS = 1e-9


class OlsError(Exception):
    """Базова помилка регресії."""


class SingularError(OlsError):
    """Драйвери лінійно залежні або сталі."""


def _solve(matrix, rhs):
    """Гаус із частковим вибором головного елемента; ведучий елемент `< SINGULAR_EPS` → `SingularError`."""
    n = len(rhs)
    rows = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) < SINGULAR_EPS:
            raise SingularError("singular")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(col + 1, n):
            factor = rows[r][col] / rows[col][col]
            if factor:
                for c in range(col, n + 1):
                    rows[r][c] -= factor * rows[col][c]
    beta = [0.0] * n
    for i in range(n - 1, -1, -1):
        beta[i] = (rows[i][n] - sum(rows[i][j] * beta[j] for j in range(i + 1, n))) / rows[i][i]
    return beta


def fit(X, y):
    """`→ (const, [coef…], r2, rmse)`; `k = 0` → `(mean(y), [], 0.0, σ(y))`."""
    n = len(y)
    if n == 0:
        raise OlsError("empty")
    k = len(X[0]) if X else 0
    mean_y = math.fsum(y) / n
    if k == 0:
        sse = math.fsum((v - mean_y) ** 2 for v in y)
        return mean_y, [], 0.0, math.sqrt(sse / n)
    cols = [[row[j] for row in X] for j in range(k)]
    means = [math.fsum(c) / n for c in cols]
    stds = []
    for j in range(k):
        var = math.fsum((v - means[j]) ** 2 for v in cols[j]) / n
        if var <= 1e-18 * max(1.0, means[j] ** 2):
            raise SingularError("constant")
        stds.append(math.sqrt(var))
    z = [[(cols[j][i] - means[j]) / stds[j] for j in range(k)] for i in range(n)]
    gram = [[math.fsum(z[i][a] * z[i][b] for i in range(n)) / n for b in range(k)] for a in range(k)]
    rhs = [math.fsum(z[i][a] * (y[i] - mean_y) for i in range(n)) / n for a in range(k)]
    beta_z = _solve(gram, rhs)
    coefs = [beta_z[j] / stds[j] for j in range(k)]
    const = mean_y - sum(coefs[j] * means[j] for j in range(k))
    sse = math.fsum((y[i] - const - sum(coefs[j] * X[i][j] for j in range(k))) ** 2 for i in range(n))
    sst = math.fsum((v - mean_y) ** 2 for v in y)
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    return const, coefs, r2, math.sqrt(max(sse, 0.0) / n)
