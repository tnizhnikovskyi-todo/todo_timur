/** @odoo-module */
// Ядро інтерактивного превью (CD-19): сцена, камера, OrbitControls, підлога-сітка 1 м, підписи габаритів, рендер на вимогу.
// Не залежить від OWL — компонент model_preview.js лише створює його й викликає setModel()/dispose(). Той самий код знімає мініатюру.
import { disposeObject } from "../model/three";

/** Налаштування для тестів: `rendererFactory(T)` повертає «нульовий» рендерер замість WebGLRenderer (патерн testMode переглядача). */
export const PREVIEW_CONFIG = { rendererFactory: null };

/** Нульовий рендерер для HOOT: лічильники викликів замість малювання. */
export function createNullRenderer() {
    const canvas = document.createElement("canvas");
    canvas.setPointerCapture = () => {};
    canvas.releasePointerCapture = () => {};
    return {
        isNull: true,
        domElement: canvas,
        renders: 0,
        disposed: 0,
        contextLost: 0,
        size: [0, 0],
        setPixelRatio() {},
        setSize(w, h) {
            this.size = [w, h];
        },
        render() {
            this.renders++;
        },
        dispose() {
            this.disposed++;
        },
        forceContextLoss() {
            this.contextLost++;
        },
    };
}

const mm = (v) => `${Math.round(v * 1000)} мм`;

function labelEl(text) {
    const d = document.createElement("div");
    d.className = "o_f3d_mp_label";
    d.textContent = text;
    return d;
}

/**
 * @param {HTMLElement} el контейнер (position: relative)
 * @param {{three: object, spinSpeed?: number}} opts `three` — модуль `loadThree()`
 * @returns {object|null} контролер або `null`, якщо WebGL недоступний
 */
export function createPreview(el, { three }) {
    const T = three.THREE;
    let renderer;
    try {
        renderer = PREVIEW_CONFIG.rendererFactory
            ? PREVIEW_CONFIG.rendererFactory(T)
            : new T.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    } catch {
        return null;
    }
    if (!renderer) {
        return null;
    }
    const scene = new T.Scene();
    const camera = new T.PerspectiveCamera(40, 1, 0.01, 200);
    camera.position.set(3, 2, 4);
    const canvas = renderer.domElement;
    canvas.classList.add("o_f3d_mp_canvas");
    canvas.style.display = "block";
    el.appendChild(canvas);
    const labelRenderer = new three.CSS2DRenderer();
    const lre = labelRenderer.domElement;
    lre.className = "o_f3d_mp_labels";
    lre.style.cssText = "position:absolute;inset:0;pointer-events:none;overflow:hidden";
    el.appendChild(lre);
    const controls = new three.OrbitControls(camera, canvas);
    controls.enableDamping = false; // рендер на вимогу: без інерції
    controls.autoRotate = false;
    controls.autoRotateSpeed = 3;

    scene.add(new T.HemisphereLight(0xffffff, 0x8794a3, 1.6));
    const sun = new T.DirectionalLight(0xffffff, 2.2);
    sun.position.set(4, 8, 5);
    scene.add(sun);

    const c = {
        T, renderer, camera, scene, controls, labelRenderer,
        model: null,
        ownsModel: true,
        grid: null,
        labels: [],
        raf: 0,
        spin: false,
        disposed: false,
        frames: 0,
        size: { w: 0, h: 0 },
    };

    const draw = () => {
        if (c.disposed) {
            return;
        }
        c.frames++;
        renderer.render(scene, camera);
        labelRenderer.render(scene, camera);
    };
    c.render = draw;
    c.requestRender = () => {
        if (!c.raf && !c.disposed) {
            c.raf = requestAnimationFrame(() => {
                c.raf = 0;
                if (c.spin) {
                    controls.update(); // автообертання: кадр за кадром, лише поки ввімкнено
                }
                draw();
                if (c.spin && !c.disposed) {
                    c.requestRender();
                }
            });
        }
    };
    controls.addEventListener("change", c.requestRender);

    c.resize = () => {
        const w = Math.max(1, el.clientWidth || 320);
        const h = Math.max(1, el.clientHeight || 240);
        if (w === c.size.w && h === c.size.h) {
            return;
        }
        c.size = { w, h };
        renderer.setPixelRatio?.(Math.min(globalThis.devicePixelRatio || 1, 2));
        renderer.setSize(w, h, false);
        canvas.style.width = "100%";
        canvas.style.height = "100%";
        labelRenderer.setSize(w, h);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        c.requestRender();
    };

    c.setSpin = (on) => {
        c.spin = !!on;
        controls.autoRotate = c.spin;
        c.requestRender();
    };

    function clearModel() {
        if (c.model) {
            scene.remove(c.model);
            if (c.ownsModel) {
                disposeObject(c.model);
            }
            c.model = null;
        }
        for (const l of c.labels) {
            scene.remove(l);
            l.element.remove();
        }
        c.labels = [];
        if (c.grid) {
            scene.remove(c.grid);
            c.grid.geometry.dispose();
            c.grid.material.dispose();
            c.grid = null;
        }
    }

    /**
     * Показує модель (метри, Y-up, низ Y=0): ставить сітку 1 м, підписи габаритів, наводить камеру.
     * @param {THREE.Object3D} obj
     * @param {{owns?: boolean, labels?: boolean}} [o] `owns=false` — об'єкт чужий (не звільняти ресурси при заміні)
     */
    c.setModel = (obj, { owns = true, labels = true } = {}) => {
        clearModel();
        c.model = obj;
        c.ownsModel = owns;
        scene.add(obj);
        obj.updateMatrixWorld(true);
        const box = new T.Box3().setFromObject(obj);
        const size = box.getSize(new T.Vector3());
        const ctr = box.getCenter(new T.Vector3());
        c.box = { size: [size.x, size.y, size.z], center: [ctr.x, ctr.y, ctr.z] };
        const gs = Math.max(4, Math.ceil((Math.max(size.x, size.z) * 2.2) / 2) * 2);
        c.grid = new T.GridHelper(gs, gs, 0x7d8895, 0xc5ccd4);
        c.grid.position.set(ctr.x, 0, ctr.z);
        scene.add(c.grid);
        if (labels) {
            const add = (text, x, y, z) => {
                const o2 = new three.CSS2DObject(labelEl(text));
                o2.position.set(x, y, z);
                scene.add(o2);
                c.labels.push(o2);
            };
            const off = 0.1 * Math.max(size.x, size.z, 0.3);
            add(mm(size.x), ctr.x, box.min.y, box.max.z + off); // довжина — по фронтальному ребру
            add(mm(size.z), box.min.x - off, box.min.y, ctr.z); // ширина — по лівому ребру
            add(mm(size.y), box.max.x + off * 0.5, ctr.y, box.max.z + off * 0.5); // висота — біля переднього правого ребра
        }
        const r = Math.max(size.x, size.y, size.z, 0.05);
        const dist = (r * 1.05) / Math.tan((camera.fov * Math.PI) / 360);
        controls.target.copy(ctr);
        const dir = new T.Vector3(0.9, 0.55, 1.15).normalize();
        camera.position.copy(ctr).addScaledVector(dir, dist);
        camera.near = dist / 100;
        camera.far = dist * 60;
        camera.updateProjectionMatrix();
        controls.minDistance = r * 0.3;
        controls.maxDistance = dist * 6;
        controls.update();
        c.requestRender();
    };

    /** Повертає PNG-Blob зображення зараз (мініатюра). */
    c.snapshot = (w = 256, h = 256, type = "image/png") =>
        new Promise((res) => {
            renderer.setSize(w, h, false);
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            draw();
            canvas.toBlob((b) => {
                c.size = { w: 0, h: 0 };
                c.resize();
                res(b);
            }, type);
        });

    c.dispose = () => {
        if (c.disposed) {
            return;
        }
        c.disposed = true;
        if (c.raf) {
            cancelAnimationFrame(c.raf);
            c.raf = 0;
        }
        controls.removeEventListener("change", c.requestRender);
        controls.dispose();
        clearModel();
        renderer.dispose();
        renderer.forceContextLoss?.();
        canvas.remove();
        lre.remove();
    };

    c.resize();
    return c;
}
