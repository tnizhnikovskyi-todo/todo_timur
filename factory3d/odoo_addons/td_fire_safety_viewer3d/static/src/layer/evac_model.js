/** @odoo-module **/
// Евакуація в 3D (вау №8): чиста модель — час, маршрути, положення людей, лічильники. Без THREE і DOM, тому тестується окремо
// (static/tests/hoot/evac.test.js). Дані — `D.evacuation.live` (td_fire_safety R-21a): безособові рядки людей навчання
// {n, zone, exit, out_ms, out_exit, wrong}; шлях людини — маршрут її зони (`D.evacuation.routes[zone].path`) до виходу.
// Рух людини — інтерполяція шляхом так, щоб вона ДОЙШЛА до виходу рівно в момент проходу СКУД (`out_ms`); тих, хто ще не вийшов,
// не пускаємо далі за `PENDING_CAP` довжини шляху: до дверей вони дійдуть лише за подією проходу.

export const EXT_ID = "td_fire_evac";
export const WALK_MPS = 1.3; // м/с — швидкість ходьби, за якою людина «стартує» так, щоб дійти до виходу в момент проходу
export const PENDING_CAP = 0.6; // частка шляху, далі якої людина без події проходу не просувається
export const REPLAY_TAIL_S = 90; // у «Потоці зміни» після кінця навчання кадр ще показується стільки секунд
export const KEEP_AFTER_END_S = 600; // у живому режимі після кінця евакуації (стадія «оцінювання») плашка й люди лишаються не довше
export const CLOSED_STATES = ["done", "cancelled"]; // закрите чи скасоване навчання в 3D не показується ніколи
export const WALL_Y = 0.6; // м, коридор уздовж стіни для людей, що йдуть не своїм виходом
export const SMOKE_TOP = 9.5; // м, стеля цеху
const KYIV = "Europe/Kyiv";

const fmt = new Intl.DateTimeFormat("en-GB", { timeZone: KYIV, hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });

/**
 * Живий стан тривоги з payload або `null` (немає навчання й справжньої тривоги, або старий сервер без ключа).
 * Закрите (`done`) і скасоване (`cancelled`) навчання не показується, навіть якщо старий сервер його ще віддає.
 */
export function liveOf(D) {
    const live = D?.evacuation?.live;
    return live && live.start_ms != null && !CLOSED_STATES.includes(live.state) ? live : null;
}

/** Секунд від київської півночі для епохи в мс (повзунок «Потоку зміни» теж у київських хвилинах доби). */
export function kyivSecondsOfDay(ms) {
    const parts = Object.fromEntries(fmt.formatToParts(new Date(ms)).map((p) => [p.type, p.value]));
    return (Number(parts.hour) % 24) * 3600 + Number(parts.minute) * 60 + Number(parts.second);
}

export const mmss = (sec) => {
    const s = Math.max(0, Math.floor(sec));
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
};

export const spanS = (live) => (live.end_ms != null ? (live.end_ms - live.start_ms) / 1000 : null);

/**
 * Секунд від тривоги на «зараз»: живий режим — годинник сервера з payload (`now_ms`) + час, що минув після його отримання
 * (`perfNow − recvPerf`); після завершення навчання кадр завмирає на кінці й зникає через `KEEP_AFTER_END_S` (10 хв). «Потік зміни» (`simMin` — київська хвилина доби
 * з `api.simMinutes()`, VX-08) — відтворення того самого навчання за часом доби. `null` — нема що показувати.
 */
export function elapsedAt(live, { perfNow = 0, recvPerf = 0, simMin = null } = {}) {
    if (!live) {
        return null;
    }
    const span = spanS(live);
    if (simMin != null) {
        const e = simMin * 60 - kyivSecondsOfDay(live.start_ms);
        return e < 0 || (span != null && e > span + REPLAY_TAIL_S) ? null : e;
    }
    const serverNow = live.now_ms + (perfNow - recvPerf);
    if (span != null && (serverNow - live.end_ms) / 1000 > KEEP_AFTER_END_S) {
        return null; // навчання давно завершилось і ще не закрите: плашку й людей прибираємо
    }
    const raw = (serverNow - live.start_ms) / 1000;
    return span != null ? Math.min(raw, span) : Math.max(0, raw);
}

// ---------------------------------------------------------------- геометрія шляху (будівельні координати x, y, м)
export const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

export function pathLength(pts) {
    let s = 0;
    for (let i = 1; i < pts.length; i++) {
        s += dist(pts[i - 1], pts[i]);
    }
    return s;
}

/** Точка на відстані `s` від початку ламаної (за межами — кінці). */
export function pointAt(pts, s) {
    if (pts.length === 1 || s <= 0) {
        return pts[0].slice();
    }
    let left = s;
    for (let i = 1; i < pts.length; i++) {
        const seg = dist(pts[i - 1], pts[i]);
        if (left <= seg && seg > 0) {
            const k = left / seg;
            return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * k, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * k];
        }
        left -= seg;
    }
    return pts[pts.length - 1].slice();
}

/** Дрібний детермінований зсув стартової точки людини в зоні (щоб не стояли в одній точці), м. */
export function jitter(n) {
    return [(((n * 37) % 9) - 4) * 0.35, (((n * 53) % 9) - 4) * 0.35];
}

/**
 * Шлях людини (від старту в зоні до дверей виходу): маршрут її зони до призначеного виходу; якщо вийшла іншим виходом —
 * через коридор уздовж стіни: до стіни, уздовж неї, до дверей. `null` — зона невідома (немає маршруту).
 */
export function personPath(p, routes, exits, plantW = 72) {
    const route = routes?.[p.zone];
    if (!route?.path?.length) {
        return null;
    }
    const j = jitter(p.n);
    const base = route.path;
    const start = [base[0][0] + j[0], base[0][1] + j[1]];
    const ex = exits?.find((e) => e.code === (p.out_exit || p.exit));
    if (p.wrong && ex) {
        const wallY = ex.y > plantW / 2 ? plantW - WALL_Y : WALL_Y;
        const pts = [start, [start[0], wallY], [ex.x, wallY], [ex.x, ex.y]];
        return pts.filter((pt, i) => i === 0 || dist(pt, pts[i - 1]) > 0.05);
    }
    const pts = [start, ...base.slice(1).map((pt) => pt.slice())];
    if (ex && dist(pts[pts.length - 1], [ex.x, ex.y]) > 0.3) {
        pts.push([ex.x, ex.y]);
    }
    return pts;
}

// ---------------------------------------------------------------- людина в момент e (секунд від тривоги)
/**
 * `{inside, s, len, stuck, goneFor}`: `inside` — ще в будівлі; `s` — пройдена довжина шляху (м); `goneFor` — скільки секунд тому
 * вийшла (для згасання точки); `stuck` — не вийшла, а з тривоги минуло більше `stuck_after_s` (або навчання вже закінчилось).
 */
export function personAt(p, pts, e, live, outS = null) {
    const len = pathLength(pts);
    const react = 8 + ((p.n * 7) % 20);
    if (p.out_ms != null) {
        const T = outS ?? (p.out_ms - live.start_ms) / 1000; // `outS` — момент «виходу» для малювання (запізніле повідомлення про прохід)
        if (e >= T) {
            return { inside: false, s: len, len, stuck: false, goneFor: e - T };
        }
        const walk = len / WALK_MPS;
        const start = Math.max(0.5, Math.min(T - walk, T - 1));
        const k = Math.min(1, Math.max(0, (e - start) / (T - start)));
        return { inside: true, s: len * k, len, stuck: false, goneFor: 0 };
    }
    const s = Math.min(len * PENDING_CAP, Math.max(0, (e - react) * WALK_MPS));
    const span = spanS(live);
    const stuck = e > (live.stuck_after_s ?? 120) || (span != null && e >= span);
    return { inside: true, s, len, stuck, goneFor: 0 };
}

// ---------------------------------------------------------------- лічильники й підсумок
/** Лічильники на момент e: у будівлі, вийшли, по зонах, застряглі, не своїм виходом. */
export function countsAt(live, routes, exits, e) {
    const byZone = {};
    const stuck = [];
    const wrong = [];
    let inside = 0;
    for (const p of live.people || []) {
        const z = p.zone || "—";
        const row = (byZone[z] ??= { total: 0, inside: 0 });
        row.total++;
        const T = p.out_ms != null ? (p.out_ms - live.start_ms) / 1000 : null;
        const gone = T != null && e >= T;
        if (!gone) {
            inside++;
            row.inside++;
            const pts = personPath(p, routes, exits);
            const st = pts ? personAt(p, pts, e, live) : { stuck: e > (live.stuck_after_s ?? 120) };
            if (st.stuck) {
                stuck.push({ n: p.n, zone: p.zone });
            }
        } else if (p.wrong) {
            wrong.push({ n: p.n, zone: p.zone, from: p.exit, to: p.out_exit });
        }
    }
    const total = (live.people || []).length;
    return { total, inside, out: total - inside, byZone, stuck, wrong };
}

/**
 * Коди вентиляційних установок, зупинених пожежним блокуванням (тривога чи навчання): сигнал перевірки td_bms дає
 * `deviation === "fire"` («зупинено пожежною сигналізацією»), і установка справді не працює. Вимкнені за розкладом
 * (`off_hours`), у режимі очікування, у несправності чи без даних — не блокування.
 */
export function blockedUnits(D) {
    return Object.entries(D?.ventilation?.units || {})
        .filter(([, u]) => u && u.deviation === "fire" && u.state !== "on")
        .map(([code]) => code)
        .sort();
}

/** Люки димовидалення відкриті (система SMOKE-CTRL активна). */
export const ventsOpen = (D) => !!D?.fire?.systems?.["SMOKE-CTRL"]?.vents_open;

/** Дим у димовій зоні на момент e: товщина шару від стелі, м, і непрозорість. */
export function smokeAt(e) {
    const t = Math.max(0, e);
    return { h: Math.min(SMOKE_TOP - 1.5, 1.2 + t * 0.05), opacity: Math.min(0.5, 0.2 + t / 400) };
}
