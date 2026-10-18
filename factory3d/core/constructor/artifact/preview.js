// Інтерактивне превʼю варіанта в картці артефакта (CD-19): умовна модель за категорією або модель із файла, габарит, зона
// обслуговування, сітка; рендер на вимогу, OrbitControls. Той самий код фігур, що й у сцені редактора (scene.js).
import { serviceObb } from "../geometry.js";
import { dashRect, lineGeo, variantBody } from "../scene.js";
import { THREE } from "../three.js";
import { V } from "../state.js";
import { h } from "../util.js";

export function createVariantPreview(host) {
    let r;
    try {
        r = new THREE.WebGLRenderer({ antialias: true });
    } catch {
        host.append(h("div", { class: "nogl" }, "WebGL недоступний"));
        return { show() {}, dispose() {} };
    }
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const cv = r.domElement;
    host.prepend(cv);
    const sc = new THREE.Scene();
    sc.background = new THREE.Color(V.col.scene || "#eeeeee");
    const cam = new THREE.PerspectiveCamera(40, 1, 0.05, 800);
    const lk = Number(THREE.REVISION) >= 155 ? Math.PI : 1;
    sc.add(new THREE.AmbientLight(0xffffff, 0.85 * lk));
    const dl = new THREE.DirectionalLight(0xffffff, 0.6 * lk);
    dl.position.set(3, 6, 4);
    sc.add(dl);
    let raf = 0;
    let cur = null;
    let disposed = false;
    const req = () => {
        if (raf || disposed) {
            return;
        }
        raf = requestAnimationFrame(() => {
            raf = 0;
            if (!disposed) {
                r.render(sc, cam);
            }
        });
    };
    const ctl = new THREE.OrbitControls(cam, cv);
    ctl.addEventListener("change", req);
    const resize = () => {
        const w = host.clientWidth;
        const hh = host.clientHeight;
        if (w < 2 || hh < 2) {
            return;
        }
        r.setSize(w, hh, false);
        cam.aspect = w / hh;
        cam.updateProjectionMatrix();
        req();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(host);
    let fitted = false;
    let lastM = 1;
    const freeOwn = (g) =>
        g.traverse((o) => {
            if (o.userData.own && o.geometry) {
                o.geometry.dispose();
            }
        });
    return {
        show(cat, v, norm) {
            if (cur) {
                sc.remove(cur);
                freeOwn(cur);
            }
            const L = v.length / 1000;
            const W = v.width / 1000;
            const H = v.height / 1000;
            const m = Math.max(L, W, H);
            const g = new THREE.Group();
            g.add(variantBody(cat, v, norm, false));
            g.add(dashRect(L / 2, W / 2, 0, 0, V.mat.dash.normal, 0.02));
            const so = serviceObb(v, 0, 0, 0);
            if (so) {
                g.add(dashRect(so.a, so.b, so.cx, so.cy, V.mat.svc, 0.015));
            }
            const n = Math.max(4, Math.ceil(m * 2));
            const pts = [];
            const half = (n / 2) * Math.max(0.5, m / 4);
            const stp = (half * 2) / n;
            for (let i = 0; i <= n; i++) {
                const t = -half + i * stp;
                pts.push(t, 0, -half, t, 0, half, -half, 0, t, half, 0, t);
            }
            const gl = new THREE.LineSegments(lineGeo(pts), V.mat.gridMinor);
            gl.userData.own = 1;
            g.add(gl);
            sc.add(g);
            cur = g;
            if (!fitted || Math.abs(m - lastM) / lastM > 0.25) {
                const dir = fitted ? cam.position.clone().sub(ctl.target).normalize() : new THREE.Vector3(0.55, 0.42, 0.72).normalize();
                ctl.target.set(0, H / 3, 0);
                cam.position.copy(ctl.target).addScaledVector(dir, m * 2.3);
                fitted = true;
                lastM = m;
            }
            ctl.target.y = H / 3;
            ctl.update();
            req();
        },
        dispose() {
            disposed = true;
            ro.disconnect();
            ctl.dispose();
            if (cur) {
                freeOwn(cur);
            }
            r.dispose();
            try {
                r.forceContextLoss();
            } catch {
                /* ок */
            }
            cv.remove();
        },
    };
}
