/** @odoo-module **/
// UI-25 AlarmMarkers (SPEC 8.4.3): спрайти «!» над вузлами з відкритими тривогами (`D.energy.layer.alarms[]`).
// Спрайт — дитина кореня об'єкта сцени (`api.items.get(scene)`): ховається разом із шаром GLB, а клік по ньому
// вибирає об'єкт сцени штатним `pick` ядра (`userData.extPick`) — те саме, що `api.select(scene)`.
// Розмір — сталий у пікселях (`sizeAttenuation: false`); пульсація — в `onBeforeRender` (нульовий рендерер її не викликає).
// Геометрія спрайта має порожній `boundingBox`: рамка вибору й `focusOn` ядра (`Box3.setFromObject`) маркера не враховують.

export const MARKER_PX = 30;
export const LEVEL_HEX = { bad: "#e74c3c", warn: "#f39c12" };
const STACK_STEP = 0.7; // м: кілька тривог одного об'єкта ставляться одна над одною
const LIFT = 0.8; // м над найвищою точкою об'єкта

function drawIcon(canvas, hex) {
    const ctx = canvas.getContext("2d");
    if (!ctx) {
        return;
    }
    ctx.clearRect(0, 0, 64, 64);
    ctx.beginPath();
    ctx.arc(32, 32, 28, 0, Math.PI * 2);
    ctx.fillStyle = hex;
    ctx.fill();
    ctx.lineWidth = 4;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 40px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("!", 32, 35);
}

export class AlarmMarkers {
    /** `api` — api розширення ядра (THREE, scene, items, selected); `reduceMotion` — вимкнути пульсацію. */
    constructor(api, { reduceMotion } = {}) {
        this.api = api;
        const media = typeof matchMedia === "function" ? matchMedia("(prefers-reduced-motion: reduce)") : null;
        this.reduceMotion = reduceMotion ?? !!media?.matches;
        this.sprites = [];
        this.mats = {};
        this.geometry = null;
    }

    _material(level) {
        const T = this.api.THREE;
        if (!this.mats[level]) {
            const canvas = document.createElement("canvas");
            canvas.width = 64;
            canvas.height = 64;
            drawIcon(canvas, LEVEL_HEX[level] || LEVEL_HEX.warn);
            const map = new T.CanvasTexture(canvas);
            map.colorSpace = T.SRGBColorSpace;
            this.mats[level] = new T.SpriteMaterial({
                map,
                transparent: true,
                depthTest: false,
                depthWrite: false,
                sizeAttenuation: false,
            });
        }
        return this.mats[level];
    }

    /** Прибрати спрайти зі сцени (матеріали й текстури лишаються для наступного `sync`). */
    clear() {
        for (const sprite of this.sprites) {
            sprite.removeFromParent();
        }
        this.sprites = [];
    }

    /** Перебудувати маркери: `alarms` — записи шару; `enabled` — `show_markers`; `limit` — максимум спрайтів. */
    sync(alarms, { enabled = true, limit = 40 } = {}) {
        this.clear();
        if (!enabled) {
            return;
        }
        const T = this.api.THREE;
        const tops = new Map(); // scene → { root, local: Vector3, count }
        for (const alarm of alarms || []) {
            if (this.sprites.length >= limit) {
                break;
            }
            if (!alarm.scene) {
                continue;
            }
            let top = tops.get(alarm.scene);
            if (!top) {
                const root = this.api.items.get(alarm.scene);
                if (!root) {
                    continue; // частина моделі ще не приїхала: маркер з'явиться при наступному applyData
                }
                root.updateWorldMatrix(true, true);
                const box = new T.Box3().setFromObject(root);
                if (box.isEmpty()) {
                    continue;
                }
                const world = new T.Vector3((box.min.x + box.max.x) / 2, box.max.y + LIFT, (box.min.z + box.max.z) / 2);
                top = { root, world, count: 0, k: 1 / (root.getWorldScale(new T.Vector3()).x || 1) };
                tops.set(alarm.scene, top);
            }
            this.sprites.push(this._add(alarm, top));
        }
    }

    _add(alarm, top) {
        const T = this.api.THREE;
        const sprite = new T.Sprite(this._material(alarm.level));
        if (!this.geometry) {
            this.geometry = sprite.geometry.clone();
            this.geometry.boundingBox = new T.Box3(); // порожня: не входить у Box3 кореня об'єкта
        }
        sprite.geometry = this.geometry;
        sprite.name = "td_energy_marker";
        sprite.renderOrder = 999;
        sprite.userData = {
            extPick: true, // ядро (`pick`) приймає спрайт; `codeRoot` дає об'єкт сцени
            marker: true,
            scene: alarm.scene,
            alarmId: alarm.id,
            level: alarm.level,
            tooltip: alarm.title + " · " + alarm.time,
        };
        const world = top.world.clone();
        world.y += STACK_STEP * top.count++;
        sprite.position.copy(top.root.worldToLocal(world));
        sprite.scale.setScalar(0.03 * top.k);
        const size = new T.Vector2();
        sprite.onBeforeRender = (renderer, scene, camera) => {
            if (!camera.isPerspectiveCamera) {
                return;
            }
            const h = renderer.getSize(size).y || 1;
            const base = ((MARKER_PX / h) * 2 * Math.tan((camera.fov * Math.PI) / 360)) * top.k;
            sprite.scale.setScalar(base * this.pulse(alarm.scene));
        };
        top.root.add(sprite);
        return sprite;
    }

    /** Коефіцієнт пульсації (1 — без пульсації): вибраний вузол — сильніше й швидше; `reduceMotion` вимикає. */
    pulse(scene) {
        if (this.reduceMotion) {
            return 1;
        }
        const selected = this.api.selected?.userData?.code === scene;
        const t = performance.now() / 1000;
        return 1 + (selected ? 0.3 : 0.1) * Math.sin(t * (selected ? 6 : 3));
    }

    /** Зняти маркери й звільнити текстури та матеріали. */
    dispose() {
        this.clear();
        for (const mat of Object.values(this.mats)) {
            mat.map?.dispose();
            mat.dispose();
        }
        this.mats = {};
        this.geometry?.dispose();
        this.geometry = null;
    }
}
