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
