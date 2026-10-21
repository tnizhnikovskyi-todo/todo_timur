/** @odoo-module */
// Спільні хелпери HOOT-тестів моста «Енергетика в 3D» (файл без тестів): макет шару 14:20 і монтування ядра з шаром.
import { mountViewer as baseMount } from "@td_viewer3d/../tests/hoot/helpers";

const node = (code, scene, state, extra = {}) => ({
    code, scene, kind: "line", name: code, state, load: null, i_a: null, p_kw: null, rating_a: null,
    card: true, alarms: 0, worst: null, title: null, ...extra,
});

/** `energy.layer` за схемою SPEC 8.4.2 (макет 14:20): C2 — тривога, PFC-2 — увага, PV-INV — генерує, CHP — вимкнено. */
export const makeLayer = () => ({
    schema: 1,
    thresholds: { warn_pct: 80, alarm_pct: 100 },
    show_markers: true,
    can_pult: true,
    nodes: [
        node("BW-2", "BW-2", "ok", { name: "ШР-2", load: 0.3, i_a: 192, p_kw: 124, rating_a: 630 }),
        node("C1", "CABLES", "ok", { name: "C1" }),
        node("C2", "CABLES", "alarm", { name: "C2", p_kw: 128, alarms: 1, worst: "bad", title: "Лічильник PM-QF-C2 не на зв'язку" }),
        node("PFC-2", "PFC-2", "warn", { kind: "cell", name: "PFC-2", alarms: 1, worst: "warn", title: "Ступінь 3 у несправності" }),
        node("PV-INV", "PV-INV", "gen", { kind: "generator", name: "СЕС", p_kw: 309 }),
        node("CHP", "CHP", "off", { kind: "generator", name: "КГУ" }),
        node("T1", "T1", "ok", { kind: "transformer", name: "T1", load: 0.5, i_a: 360, p_kw: 340, rating_a: 1443 }),
        node("NOSCENE-1", null, "alarm", { name: "Без об'єкта", alarms: 1, worst: "bad", title: "Тривога без сцени" }),
        node("QS", "QS", "off", { kind: "cell", name: "QS", card: false }),
    ],
    alarms: [
        { id: 212, node: "C2", scene: "CABLES", level: "bad", title: "Лічильник PM-QF-C2 не на зв'язку", time: "13:47", state: "active" },
        { id: 213, node: "PFC-2", scene: "PFC-2", level: "warn", title: "Ступінь 3 у несправності", time: "13:55", state: "acked" },
        { id: 214, node: "NOSCENE-1", scene: null, level: "bad", title: "Тривога без сцени", time: "13:58", state: "active" },
    ],
    summary: { alarm: 2, warn: 1, gen: 1, off: 2 },
});

/**
 * Змонтувати ядро з шаром `energy.layer` у `D`; `layer: null` — «старий сервер» без шару.
 * `engineering: true` дочікується частини моделі з об'єктами енергетики (BW-2, CABLES, PFC-2, T1 …).
 */
export async function mountEnergy({ layer = makeLayer(), engineering = true, mutate, ...rest } = {}) {
    const res = await baseMount({
        model: engineering ? "core" : "none",
        ...rest,
        mutate: (fx) => {
            if (layer) {
                fx.data.energy.layer = structuredClone(layer);
            }
            mutate?.(fx);
        },
    });
    if (engineering) {
        await res.viewer.loadPart("engineering");
    }
    return res;
}

/** Перший меш об'єкта: туди `paint` кладе `emissive`. */
export function firstMesh(root) {
    let mesh = null;
    root.traverse((o) => {
        if (!mesh && o.isMesh && o.material?.emissive) {
            mesh = o;
        }
    });
    return mesh;
}

/**
 * Добові серії `GET …/energy/day` (SPEC R-59): вводи 07:00–10:00 (слоти 28…39) по 50 кВт·год, зонний тариф: напівпік 8,4 до 08:00, пік 12,6 (1,5×) далі;
 * СЕС 10 кВт·год на слот; споживач SAW-1: 5 кВт (07:00), 15 кВт (08:00), 35 кВт (09:00); решта споживачів ШР-1 — по 20 кВт. `cost: false` — без вартості.
 */
export function makeSeries({ cost = true } = {}) {
    const z = () => new Array(96).fill(0);
    const kwh = z();
    const price = z();
    const gen = z();
    const saw = z();
    const bw = z();
    for (let s = 28; s < 40; s++) {
        kwh[s] = 50;
        price[s] = s < 32 ? 8.4 : 12.6;
        gen[s] = 10;
        saw[s] = s < 32 ? 5 : s < 36 ? 15 : 35;
        bw[s] = 20;
    }
    const costs = kwh.map((v, i) => Math.round(v * price[i] * 100) / 100);
    const sum = (a) => a.reduce((x, y) => x + y, 0);
    const grid = { kwh, export: z() };
    if (cost) {
        grid.cost = costs;
    }
    const totals = { kwh: sum(kwh), export_kwh: 0, gen_kwh: sum(gen), peak_kw: 200, peak_slot: 28 };
    if (cost) {
        totals.cost = sum(costs);
    }
    return {
        schema: 1, day: "2026-10-12", slot_min: 15, built_to: 39, contract_kw: 800, cost,
        grid, gen: { kwh: gen }, consumers: { "SAW-1": saw, "SAW-2": bw, "EDGE-1": bw, "EDGE-2": bw, "CNC-1": bw, "CNC-2": bw, "SORT-1": bw }, totals,
    };
}
