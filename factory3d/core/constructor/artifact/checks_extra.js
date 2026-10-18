// Додаткові правила навантаження прототипу (до перенесення cell_load у ядро, MERGE.md §5.2 S2): стелаж на підлогу з урахуванням
// ярусів, ліміт комірки з ручної правки більший за ліміт стелажа, питоме навантаження з маси, коли в варіанта немає floor_load.
// Модуль Odoo їх не має (R-08 — дзеркало сервера); тут вони підключаються реєстром `checks` під перемикачем «load».
import { cellsOf, footprint, normalizeParams } from "../cells.js";
import { issue } from "../checks.js";
import { registries } from "../registry.js";

const fix1 = (v) => Number(v).toFixed(1).replace(".", ",");
const int = (v) => String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

function artifactLoad(scene, config) {
    const sev = config.mode;
    const out = [];
    for (const p of scene.placements) {
        const v = scene.variants.get(p.variant_id);
        const ly = scene.layers.get(p.layer_id) || {};
        if (!ly.max_floor_load || v.floor_load != null && v.floor_load !== "") {
            continue; // з floor_load рахує ядро
        }
        const area = Math.max((v.length / 1000) * (v.width / 1000), 0.01);
        const q = ((v.weight_kg || 0) * 9.81) / 1000 / area;
        if (q > ly.max_floor_load + 1e-6) {
            out.push(issue("load", sev, p.layer_id, [p.code], `${p.code}: навантаження ${fix1(q)} кН/м² перевищує ${fix1(ly.max_floor_load)}`, ["p:" + p.id], "floor"));
        }
    }
    for (const s of scene.slots.values()) {
        const ly = scene.layers.get(s.layer_id) || {};
        if (s.template !== "pallet_rack") {
            continue;
        }
        const pr = normalizeParams(s.template, s.params);
        const f = footprint(s.template, pr);
        const q = (pr.levels * pr.max_load_kg * 9.81) / 1000 / Math.max(f.l * f.w, 0.01);
        if (ly.max_floor_load > 0 && q > ly.max_floor_load + 1e-6) {
            out.push(issue("load", sev, s.layer_id, [s.code_prefix], `${s.code_prefix}: навантаження стелажа ${fix1(q)} кН/м² > ${fix1(ly.max_floor_load)} кН/м²`, ["s:" + s.id], "floor"));
        }
        for (const c of cellsOf(s)) {
            if (c.ov && c.max_load_kg > pr.max_load_kg) {
                out.push(issue("load", sev, s.layer_id, [s.code_prefix], `Комірка ${c.code}: ліміт ${int(c.max_load_kg)} кг > ${int(pr.max_load_kg)} кг стелажа`, ["s:" + s.id], "cell"));
                break;
            }
        }
    }
    return out;
}

export function registerArtifactChecks() {
    registries.checks.add("artifact_load", { config: "load", run: artifactLoad }, { sequence: 55, force: true });
}
