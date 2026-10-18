/** @odoo-module */
// Фікстури HOOT-тестів редактора (файл без тестів): відповідь API-03 `load` і мок RPC.

const mgr = { is_manager: true, roles: ["manager"], editable_layer_ids: [1, 2, 3], can_publish: true, can_edit_catalog: true };

/** Мінімальна площадка: шари «Будівля» (1), «Склади» (2, комірник), «Виробництво» (3, технолог); один стелаж, один станок, прохід. */
export function makeLoad(over = {}) {
    const variant = {
        id: 11,
        name: "Верстат 3,0 × 1,5 м",
        length: 3000,
        width: 1500,
        height: 1800,
        service: { front: 1000, back: 300, left: 300, right: 300 },
        rotations: "q",
        front_side: "s",
        anchor: "center",
        layer_kinds: ["production"],
        slot_types: [],
        utilities: [],
        power_kw: 7.5,
        panel: "",
        weight_kg: 1800,
        floor_load: 3.9,
        create_workcenter: false,
        model: null,
        etag: "v1",
    };
    const layer = (id, uid, name, kind, extra = {}) => ({
        id,
        uid,
        name,
        kind,
        sequence: id * 10,
        elevation: 0,
        grid_step: 0.5,
        aisle_width: 3,
        max_floor_load: 0,
        bounds: null,
        slot_types: [],
        edit_groups: [],
        color: "#6f8396",
        opacity: 0.5,
        style: "solid",
        visible: true,
        aisles: [],
        fire_paths: [],
        utilities: [],
        underlay: null,
        etag: "2026-10-17 10:00:00.000001",
        ...extra,
    });
    const data = {
        ok: true,
        site: {
            id: 1,
            name: "Тестова площадка",
            code: "TEST",
            building: { length: 60, width: 30, height: 8 },
            column_grid: { step_x: 6, step_y: 6 },
            default_parent_location: null,
            active_version: { id: 5, n: 1 },
            draft_base_version: { id: 5, n: 1 },
            draft_rev: 3,
            draft_changes: 0,
            has_changes: false,
            settings: { autosave_ms: 1500, max_model_mb: 20, max_triangles: 50000, eps_mm: 1, reach_default_m: 15, publish_enabled: true },
        },
        layers: [
            layer(1, "lyb", "Будівля", "building", { slot_types: ["zone"] }),
            layer(2, "lys", "Склади", "storage", {
                slot_types: ["pallet_rack", "zone"],
                edit_groups: [{ id: 41, name: "Конструктор: комірник", role: "storekeeper" }],
                color: "#3f9b6a",
            }),
            layer(3, "lyp", "Виробництво", "production", {
                slot_types: ["machine_spot", "zone"],
                edit_groups: [{ id: 42, name: "Конструктор: технолог", role: "technologist" }],
                aisles: [{ id: "ai1", name: "Проїзд", x0: 10, y0: 20, x1: 40, y1: 23 }],
                color: "#2f78b5",
                max_floor_load: 40,
            }),
        ],
        slots: [
            {
                id: 21,
                uid: "slrack",
                layer_id: 2,
                template: "pallet_rack",
                code_prefix: "PR-1",
                x: 10,
                y: 5,
                rotation: 0,
                params: { bays: 18, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000 },
                overrides: {},
                parent_location_id: null,
                cell_count: 72,
                etag: "2026-10-17 10:00:00.000002",
            },
            {
                id: 22,
                uid: "slzone",
                layer_id: 1,
                template: "zone",
                code_prefix: "Z-1",
                x: 0,
                y: 0,
                rotation: 0,
                params: { polygon: [[1, 1], [11, 1], [11, 7], [1, 7]] },
                overrides: {},
                parent_location_id: null,
                cell_count: 0,
                etag: "2026-10-17 10:00:00.000003",
            },
        ],
        placements: [
            {
                id: 31,
                uid: "plm1",
                layer_id: 3,
                variant_id: 11,
                slot_id: null,
                cell_code: null,
                x: 20,
                y: 8,
                rotation: 0,
                code: "M-1",
                name: "Верстат 1",
                equipment: null,
                etag: "2026-10-17 10:00:00.000004",
            },
        ],
        catalog: [
            { passport_id: 7, name: "Універсальний верстат", role: "generic_machine", manufacturer: "—", model: "Типовий", category: "machine", variants: [variant] },
        ],
        checks: [
            { check: "fits", enabled: true, mode: "block", params: {} },
            { check: "collide", enabled: true, mode: "block", params: {} },
            { check: "service_free", enabled: true, mode: "warn", params: {} },
            { check: "aisles_free", enabled: true, mode: "block", params: {} },
            { check: "load", enabled: true, mode: "warn", params: {} },
            { check: "utility_reach", enabled: true, mode: "warn", params: { max_m: 15 } },
            { check: "fire", enabled: true, mode: "block", params: {} },
        ],
        versions: [{ id: 5, n: 1, published_at: "2026-10-16 09:00:00", by: "Admin", note: "Початкова", state: "published", counts: { layers: 3, slots: 2, cells: 72, placements: 1 } }],
        rights: { ...mgr },
    };
    return Object.assign(data, over);
}

/** Інша площадка для перемикача (AC-66): порожня, з базовими шарами. */
export function makeSecondSite() {
    const d = makeLoad();
    d.site = { ...d.site, id: 2, name: "Порожня площадка", code: "EMPTY", active_version: null, draft_changes: 0 };
    d.layers = d.layers.map((l, i) => ({ ...l, id: 101 + i, uid: "e" + l.uid }));
    d.slots = [];
    d.placements = [];
    d.versions = [];
    return d;
}

/**
 * Мок RPC: `routes[route]` — функція (params) → відповідь або значення; усі виклики пишуться в `rpc.calls`.
 * Невідомий маршрут — помилка тесту.
 */
export function mockRpc(routes) {
    const rpc = async (route, params) => {
        rpc.calls.push({ route, params });
        const h = routes[route];
        if (!h) {
            throw new Error(`mockRpc: невідомий маршрут ${route}`);
        }
        return typeof h === "function" ? await h(params, rpc.calls.length) : h;
    };
    rpc.calls = [];
    rpc.of = (route) => rpc.calls.filter((c) => c.route === route);
    return rpc;
}
