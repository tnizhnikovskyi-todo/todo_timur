"""R-03: безперервний лічильник `Ec(t)` з накопичувальних показань. Чисті функції без ORM (CE-06)."""

from bisect import bisect_right

QUALITY_ORDER = {"measured": 0, "interpolated": 1, "reset": 2, "missing": 3}


def worst(*qualities):
    """Найгірша якість (`missing` > `reset` > `interpolated` > `measured`); порожній набір — `measured`."""
    result = "measured"
    for q in qualities:
        if QUALITY_ORDER[q] > QUALITY_ORDER[result]:
            result = q
    return result


class Series:
    """Ряд точок `(t, c)` безперервного лічильника; `seg[i]` — якість сегмента `[t_i, t_{i+1}]`."""

    def __init__(self, ts, cs, seg, resets=(), interp_inside=False):
        self.ts, self.cs, self.seg = list(ts), list(cs), list(seg)
        self.resets = list(resets)  # (t_i, v_prev, v_i, c_i) — для подій і `counter_offset`
        self.interp_inside = interp_inside

    @classmethod
    def build(cls, points, base=0.0, reset_tol=1.0, max_kw=10.0, gap_max_s=900):
        """`points` — [(datetime, значення)], відсортовані за часом (дублікати часу відкидаються)."""
        ts, cs, seg, resets = [], [], [], []
        prev_t = prev_v = None
        for t, v in sorted(points, key=lambda p: p[0]):
            if prev_t is not None and t == prev_t:
                continue
            if prev_t is None:
                ts.append(t)
                cs.append(v + base)
            else:
                dt_s = (t - prev_t).total_seconds()
                d = v - prev_v
                c_prev = cs[-1]
                quality = "measured"
                if d >= 0:
                    c = c_prev + d
                elif d >= -reset_tol:
                    c = c_prev
                else:
                    quality = "reset"
                    c = c_prev + v if 0 <= v <= dt_s / 3600.0 * max_kw else c_prev
                    resets.append((t, prev_v, v, c))
                if quality == "measured" and dt_s > gap_max_s:
                    quality = "interpolated"
                ts.append(t)
                cs.append(c)
                seg.append(quality)
            prev_t, prev_v = t, v
        return cls(ts, cs, seg, resets)

    @classmethod
    def from_segments(cls, ts, cs, seg):
        """Ряд з уже безперервних значень (інтервали профілю): усередині сегмента — не краще за `interpolated`."""
        return cls(ts, cs, seg, interp_inside=True)

    def __bool__(self):
        return bool(self.ts)

    @property
    def last_c(self):
        return self.cs[-1] if self.cs else None

    def value_at(self, t):
        """`Ec(t)` — лінійна інтерполяція; поза `[t_0, t_last]` — `None`."""
        if not self.ts or t < self.ts[0] or t > self.ts[-1]:
            return None
        i = bisect_right(self.ts, t) - 1
        if self.ts[i] == t:
            return self.cs[i]
        t0, t1 = self.ts[i], self.ts[i + 1]
        return self.cs[i] + (self.cs[i + 1] - self.cs[i]) * (t - t0).total_seconds() / (t1 - t0).total_seconds()

    def _is_point(self, t):
        i = bisect_right(self.ts, t) - 1
        return i >= 0 and self.ts[i] == t

    def delta(self, a, b):
        """`(Ec(b) − Ec(a), якість)`; будь-який `None` — `(None, 'missing')`."""
        ea, eb = self.value_at(a), self.value_at(b)
        if ea is None or eb is None:
            return None, "missing"
        quals = [self.seg[i] for i in range(len(self.seg)) if self.ts[i] < b and self.ts[i + 1] > a]
        if self.interp_inside and not (self._is_point(a) and self._is_point(b)):
            quals.append("interpolated")
        return max(eb - ea, 0.0), worst(*quals)
