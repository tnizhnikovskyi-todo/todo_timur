// Будівля: контур, колони, стіни, проходи (F18), техніка складу (N-06), перевірки будівлі (N-07) — слайс S5.
// Файл підключено в index.js заздалегідь (MERGE.md §5.0): реєструє перевірки `inside` / `aisle_width` / `height` у реєстрі `checks`;
// режим «Будівля» (building_ui.js) і 3D будівлі (building_3d.js) підключаються звідси. Чисте ядро — building_core.js (дзеркало services/building.py).
import { checkAisleWidth, checkHeight, checkInside, setSiteProvider } from "./building_core.js";
import { registries } from "./registry.js";
import { S } from "./state.js";
import "./building_3d.js";
import "./building_ui.js";

setSiteProvider(() => S.site);

registries.checks.add("inside", { run: checkInside, label: "Усередині контуру й поза об'єктами будівлі" }, { sequence: 100, force: true });
registries.checks.add("aisle_width", { run: checkAisleWidth, label: "Ширина проходу за технікою" }, { sequence: 110, force: true });
registries.checks.add("height", { run: checkHeight, label: "Висота до стелі й спринклерів" }, { sequence: 120, force: true });
