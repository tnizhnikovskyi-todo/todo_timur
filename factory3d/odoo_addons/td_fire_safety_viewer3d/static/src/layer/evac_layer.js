/** @odoo-module **/
// Евакуація в 3D (вау №8; розширення ядра R-26: VX-03 applyData, VX-08 simMinutes/onSimTime/invalidate): по тривозі (навчальній
// або справжній) у сцені оживають маршрути (бігучі стрілки до виходів), виходи, дим у димових зонах, заблокована вентиляція
// й люки, точки людей (рухаються до виходів за подіями проходів СКУД) та плашка «у будівлі N людей · 02:15 від тривоги».
// Дані — `D.evacuation.live` (td_fire_safety R-21a) + `D.evacuation.routes/exits`, `D.ventilation.units`, `D.fire.systems`, `D.access`;
// без `live` (старий сервер або тривоги немає) розширення нічого не малює. Ядро `core.js` не змінювалось.
// Час: у «живому» режимі — годинник сервера (`live.now_ms`), у «Потоці зміни» — `api.simMinutes()` (VX-08), зміну часу ловить
// `api.onSimTime`; кадр просимо `api.invalidate()`.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { esc, plural } from "@td_viewer3d/viewer/format";
import {
    EXT_ID, SMOKE_TOP, WALK_MPS, blockedUnits, countsAt, elapsedAt, liveOf, mmss, personAt, personPath, pointAt, smokeAt, spanS, ventsOpen,
} from "@td_fire_safety_viewer3d/layer/evac_model";

export { EXT_ID };
export const GROUP_NAME = "td_fire_evac_layer";
const TICK_MS = 50; // ~20 к/с: цього досить для плавного руху й не палить GPU
const RIBBON_W = 1.5; // м, ширина стрічки маршруту
const RIBBON_Y = 0.14; // м над підлогою
const CHEVRON_M = 2.5; // м шляху на одну стрілку
const FLOW_SPEED = 0.9; // стрілок за секунду
const RUN_MPS = WALK_MPS * 2.2; // швидкість «наздоганяння» точки до цілі (без телепортів)
const COLORS = { route: 0x2ee86b, fire: 0xff9a1a, idle: 0x8fd4a8, exit: 0x1fe27a, person: 0x2c8cff, wrong: 0xffa000, stuck: 0xff2a1a };
const b2t = (T, x, y, z) => new T.Vector3(x, z, -y); // будівельні координати → three (ядро: (x, z, −y))

function chevronTexture(T) {
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 64;
    const ctx = canvas.getContext("2d");
    if (ctx) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 13;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(34, 9);
        ctx.lineTo(92, 32);
        ctx.lineTo(34, 55);
        ctx.stroke();
    }
    const tex = new T.CanvasTexture(canvas);
    tex.wrapS = T.RepeatWrapping;
    tex.colorSpace = T.SRGBColorSpace;
    return tex;
}

function textSprite(T, text, color, scale = 1) {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 80;
    const tex = new T.CanvasTexture(canvas);
    tex.colorSpace = T.SRGBColorSpace;
    const sprite = new T.Sprite(new T.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
    sprite.renderOrder = 20;
    sprite.userData.textKey = "";
    sprite.userData.baseScale = scale;
    sprite.scale.set(7 * scale, 2.2 * scale, 1);
    setSpriteText(sprite, text, color);
    return sprite;
}

function setSpriteText(sprite, text, color) {
    const key = text + "|" + color;
    if (sprite.userData.textKey === key) {
        return;
    }
    sprite.userData.textKey = key;
    const tex = sprite.material.map;
    const canvas = tex.image;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
        return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(20,28,36,0.82)";
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(6, 8, 244, 64, 16);
    } else {
        ctx.rect(6, 8, 244, 64);
    }
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 34px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 128, 42, 232);
    tex.needsUpdate = true;
}

const hex = (n) => "#" + n.toString(16).padStart(6, "0");

/** Стрічка уздовж ламаної: квадри з UV, що ростуть уздовж ходу (u — у «стрілках»), щоб зсув текстури рухав стрілки до виходу. */
function ribbonGeometry(T, pts) {
    const pos = [];
    const uv = [];
    const idx = [];
    let cum = 0;
    for (let i = 1; i < pts.length; i++) {
        const [x0, y0] = pts[i - 1];
        const [x1, y1] = pts[i];
        const len = Math.hypot(x1 - x0, y1 - y0);
        if (len < 1e-6) {
            continue;
        }
        const nx = (-(y1 - y0) / len) * (RIBBON_W / 2);
        const ny = ((x1 - x0) / len) * (RIBBON_W / 2);
        const base = pos.length / 3;
        for (const [px, py] of [[x0 + nx, y0 + ny], [x0 - nx, y0 - ny], [x1 + nx, y1 + ny], [x1 - nx, y1 - ny]]) {
            const v = b2t(T, px, py, RIBBON_Y);
            pos.push(v.x, v.y, v.z);
        }
        uv.push(cum / CHEVRON_M, 1, cum / CHEVRON_M, 0, (cum + len) / CHEVRON_M, 1, (cum + len) / CHEVRON_M, 0);
        idx.push(base, base + 1, base + 2, base + 1, base + 3, base + 2);
        cum += len;
    }
    const geo = new T.BufferGeometry();
    geo.setAttribute("position", new T.Float32BufferAttribute(pos, 3));
    geo.setAttribute("uv", new T.Float32BufferAttribute(uv, 2));
    geo.setIndex(idx);
    return geo;
}

const reduceMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export const evacExtension = {
    id: EXT_ID,
    states: new WeakMap(),

    stateOf(api) {
        let st = this.states.get(api.scene);
        if (!st) {
            st = {
                group: null, key: "", live: null, recvPerf: 0, raf: 0, lastTick: 0, off: null, plate: null, plateHtml: "", tex: null,
                ribbons: [], exits: new Map(), smokes: [], fire: null, dots: new Map(), counters: new Map(), marks: [], elapsed: null,
            };
            this.states.set(api.scene, st);
        }
        return st;
    },

    // ядро перезавантажило модель/розкладку: об'єкти (вентиляція, люки) могли змінитись — підсвітку збираємо заново
    applyLayout(api) {
        const st = this.stateOf(api);
        if (st.group) {
            this.buildMarks(api, st);
        }
    },

    // VX-03: після setData / applyPatch / знімка / «Зараз»
    applyData(api, D) {
        const live = liveOf(D);
        if (!live) {
            this.clear(api);
            return;
        }
        const T = api.THREE;
        const st = this.stateOf(api);
        st.live = live;
        st.recvPerf = performance.now();
        const key = [live.name, live.mode, live.zone, Object.keys(D.evacuation.routes || {}).length, (live.smoke || []).map((s) => s.code).join()].join("|");
        if (!st.group || st.key !== key) {
            this.clearScene(api, st);
            this.build(api, st, T, D);
            st.key = key;
        }
        this.buildMarks(api, st);
        if (!st.off && typeof api.onSimTime === "function") {
            st.off = api.onSimTime(() => this.tick(api, performance.now(), true)); // VX-08
        }
        this.start(api, st);
        this.tick(api, performance.now(), true);
    },

    // ---- побудова сцени ---------------------------------------------------------------------------
    build(api, st, T, D) {
        const E = D.evacuation;
        const live = st.live;
        st.group = new T.Group();
        st.group.name = GROUP_NAME;
        api.scene.add(st.group);
        st.tex = chevronTexture(T);
        for (const [zone, r] of Object.entries(E.routes || {})) {
            if (!r.path || r.path.length < 2) {
                continue;
            }
            const mat = new T.MeshBasicMaterial({
                map: st.tex, color: COLORS.route, transparent: true, opacity: 0.9, depthWrite: false, side: T.DoubleSide, toneMapped: false,
            });
            const mesh = new T.Mesh(ribbonGeometry(T, r.path), mat);
            mesh.renderOrder = 10;
            mesh.userData.zone = zone;
            st.group.add(mesh);
            st.ribbons.push(mesh);
        }
        for (const e of E.exits || []) {
            const g = new T.Group();
            const door = new T.Mesh(
                new T.BoxGeometry(1.5, 2.6, 0.5),
                new T.MeshBasicMaterial({ color: COLORS.exit, transparent: true, opacity: 0.5, depthWrite: false, toneMapped: false }),
            );
            door.position.copy(b2t(T, e.x, e.y, 1.3));
            const ring = new T.Mesh(
                new T.RingGeometry(1.1, 1.6, 40),
                new T.MeshBasicMaterial({ color: COLORS.exit, transparent: true, opacity: 0.6, depthWrite: false, side: T.DoubleSide, toneMapped: false }),
            );
            ring.rotation.x = -Math.PI / 2;
            ring.position.copy(b2t(T, e.x, e.y + (e.y > 36 ? -1.2 : 1.2), 0.16));
            const label = textSprite(T, e.code, hex(COLORS.exit));
            label.position.copy(b2t(T, e.x, e.y + (e.y > 36 ? -2.5 : 2.5), 3.8));
            g.add(door, ring, label);
            st.group.add(g);
            st.exits.set(e.code, { door, ring, label });
        }
        for (const s of live.smoke || []) {
            const mat = new T.MeshBasicMaterial({ color: 0x2d2a28, transparent: true, opacity: 0.3, depthWrite: false, toneMapped: false });
            const box = new T.Mesh(new T.BoxGeometry(1, 1, 1), mat);
            box.renderOrder = 5;
            box.userData.rect = s;
            const edges = new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(1, 1, 1)), new T.LineBasicMaterial({ color: 0xb8a48c, transparent: true, opacity: 0.7 }));
            box.add(edges); // обрис димової зони (масштабується разом із коробкою)
            st.group.add(box);
            st.smokes.push(box);
        }
        if (live.origin) {
            const flame = textSprite(T, "Пожежа · " + live.zone, hex(COLORS.stuck), 1.2);
            flame.position.copy(b2t(T, live.origin[0], live.origin[1], 5));
            const core = new T.Mesh(
                new T.SphereGeometry(0.9, 18, 12),
                new T.MeshBasicMaterial({ color: 0xff5a1f, transparent: true, opacity: 0.85, toneMapped: false }),
            );
            core.position.copy(b2t(T, live.origin[0], live.origin[1], 1.2));
            st.group.add(flame, core);
            st.fire = { flame, core };
        }
        const counted = new Set((live.people || []).map((p) => p.zone).filter(Boolean));
        for (const zone of counted) {
            const r = E.routes?.[zone];
            if (!r?.path?.length) {
                continue;
            }
            const sprite = textSprite(T, zone + " · 0", hex(COLORS.person), 0.8);
            sprite.position.copy(b2t(T, r.path[0][0], r.path[0][1], 3.2));
            st.group.add(sprite);
            st.counters.set(zone, sprite);
        }
        const plateHost = api.labelsRoot?.parentElement;
        if (plateHost) {
            st.plate = document.createElement("div");
            st.plate.className = "o_td_ev_plate";
            st.plate.setAttribute("role", "status");
            st.plate.setAttribute("aria-live", "polite");
            plateHost.appendChild(st.plate);
        }
    },

    // підсвітка заблокованої вентиляції й люків: коробки навколо об'єктів ядра (їхні мешы не чіпаємо — ядро їх пакетує)
    buildMarks(api, st) {
        const T = api.THREE;
        for (const m of st.marks) {
            st.group.remove(m.box);
            m.box.geometry.dispose();
            m.box.material.dispose();
        }
        st.marks = [];
        const D = api.D;
        const codes = [];
        for (const code of blockedUnits(D)) {
            codes.push({ code, kind: "vent", color: 0xffb020 });
        }
        if (ventsOpen(D)) {
            for (const code of api.items.keys()) {
                if (/^SV-\d+$/.test(code)) {
                    codes.push({ code, kind: "hatch", color: 0x35d0ff });
                }
            }
        }
        for (const { code, kind, color } of codes) {
            const root = api.items.get(code);
            if (!root) {
                continue;
            }
            const box3 = new T.Box3().setFromObject(root);
            if (box3.isEmpty()) {
                continue;
            }
            const size = box3.getSize(new T.Vector3()).addScalar(0.5);
            const mat = new T.MeshBasicMaterial({ color, transparent: true, opacity: 0.35, depthWrite: false, toneMapped: false });
            const box = new T.Mesh(new T.BoxGeometry(size.x, size.y, size.z), mat);
            box.position.copy(box3.getCenter(new T.Vector3()));
            box.renderOrder = 8;
            st.group.add(box);
            st.marks.push({ code, kind, box, root });
        }
    },

    clearScene(api, st) {
        if (st.group) {
            api.scene.remove(st.group);
            st.group.traverse((o) => {
                o.geometry?.dispose?.();
                const mats = [].concat(o.material || []);
                for (const m of mats) {
                    m.map?.dispose?.();
                    m.dispose?.();
                }
            });
        }
        st.plate?.remove();
        Object.assign(st, {
            group: null, key: "", plate: null, plateHtml: "", tex: null, ribbons: [], exits: new Map(), smokes: [], fire: null,
            dots: new Map(), counters: new Map(), marks: [],
        });
    },

    clear(api) {
        const st = this.stateOf(api);
        if (st.raf) {
            cancelAnimationFrame(st.raf);
            st.raf = 0;
        }
        const had = !!st.group;
        this.clearScene(api, st);
        st.live = null;
        if (had) {
            api.invalidate?.();
        }
    },

    // ---- анімація ---------------------------------------------------------------------------------
    start(api, st) {
        if (st.raf) {
            return;
        }
        const slow = reduceMotion();
        const loop = (ms) => {
            const root = api.labelsRoot;
            if (!root || !root.isConnected || !st.live) {
                st.raf = 0; // сцену знищено разом із в'ювером або тривога скінчилась
                return;
            }
            st.raf = requestAnimationFrame(loop);
            const now = ms || performance.now();
            if (now - st.lastTick < (slow ? 1000 : TICK_MS)) {
                return;
            }
            this.tick(api, now, false);
        };
        st.raf = requestAnimationFrame(loop);
    },

    clock(api, st, nowMs) {
        const sim = typeof api.simMinutes === "function" ? api.simMinutes() : null; // VX-08
        return elapsedAt(st.live, { perfNow: nowMs, recvPerf: st.recvPerf, simMin: sim });
    },

    tick(api, nowMs, force) {
        const st = this.stateOf(api);
        const live = st.live;
        if (!st.group || !live) {
            return;
        }
        const dt = Math.min(0.25, Math.max(0, (nowMs - (st.lastTick || nowMs)) / 1000));
        st.lastTick = nowMs;
        const D = api.D;
        const E = D.evacuation;
        const e = this.clock(api, st, nowMs);
        st.elapsed = e;
        st.group.visible = e != null;
        if (st.plate) {
            st.plate.hidden = e == null;
        }
        if (e == null) {
            api.invalidate?.();
            return;
        }
        const counts = countsAt(live, E.routes, E.exits, e);
        this.animateRoutes(st, nowMs, counts, live);
        this.animateExits(api, st, nowMs, counts, live);
        this.animateSmoke(st, e, nowMs);
        this.animateMarks(api, st, nowMs);
        this.animatePeople(api, st, e, dt, E, live, force);
        this.animateCounters(st, counts);
        this.paintPlate(api, st, e, counts, live, D);
        api.invalidate?.(); // ядро малює «за потребою» (VX-08)
    },

    animateRoutes(st, nowMs, counts, live) {
        const phase = reduceMotion() ? 0 : (nowMs / 1000) * FLOW_SPEED;
        if (st.tex) {
            st.tex.offset.x = -(phase % 1);
        }
        for (const r of st.ribbons) {
            const z = r.userData.zone;
            const busy = (counts.byZone[z]?.inside || 0) > 0 || live.mode === "alarm";
            r.material.color.setHex(z === live.zone_code ? COLORS.fire : busy ? COLORS.route : COLORS.idle);
            r.material.opacity = busy ? 0.92 : 0.38;
        }
    },

    animateExits(api, st, nowMs, counts, live) {
        const pulse = 0.5 + 0.5 * Math.sin(nowMs / 260);
        const used = {};
        for (const p of live.people || []) {
            const code = p.out_exit || null;
            if (code) {
                used[code] = (used[code] || 0) + 1;
            }
        }
        for (const [code, o] of st.exits) {
            const n = used[code] || 0;
            o.door.material.opacity = 0.35 + 0.35 * pulse + (n ? 0.1 : 0);
            o.ring.material.opacity = 0.3 + 0.5 * pulse;
            o.ring.scale.setScalar(1 + 0.18 * pulse);
            setSpriteText(o.label, n ? code + " · " + n : code, hex(COLORS.exit));
        }
    },

    animateSmoke(st, e, nowMs) {
        const { h, opacity } = smokeAt(e);
        const breath = 1 + 0.03 * Math.sin(nowMs / 700);
        for (const box of st.smokes) {
            const r = box.userData.rect;
            const w = r.x1 - r.x0;
            const d = r.y1 - r.y0;
            box.scale.set(w, h * breath, d);
            box.position.set((r.x0 + r.x1) / 2, SMOKE_TOP - (h * breath) / 2, -(r.y0 + r.y1) / 2);
            box.material.opacity = opacity;
        }
        if (st.fire) {
            const s = 1 + 0.2 * Math.sin(nowMs / 90) + 0.1 * Math.sin(nowMs / 37);
            st.fire.core.scale.setScalar(s);
        }
    },

    animateMarks(api, st, nowMs) {
        const pulse = 0.5 + 0.5 * Math.sin(nowMs / 320);
        for (const m of st.marks) {
            m.box.visible = api.isShown ? api.isShown(m.root) !== false : true;
            m.box.material.opacity = 0.22 + 0.3 * pulse;
        }
    },

    animatePeople(api, st, e, dt, E, live, force) {
        const T = api.THREE;
        const replay = typeof api.simMinutes === "function" && api.simMinutes() != null;
        const seen = new Set();
        for (const p of live.people || []) {
            const pts = personPath(p, E.routes, E.exits);
            if (!pts) {
                continue;
            }
            seen.add(p.n);
            let dot = st.dots.get(p.n);
            if (!dot) {
                const mesh = new T.Mesh(
                    new T.SphereGeometry(0.8, 16, 12),
                    new T.MeshBasicMaterial({ color: COLORS.person, toneMapped: false }),
                );
                mesh.renderOrder = 12;
                st.group.add(mesh);
                dot = { mesh, cur: null, label: null, outS: null, arrivedAt: null };
                st.dots.set(p.n, dot);
            }
            // про прохід СКУД дізнаємось із запізненням (опитування, шина): якщо подія вже в минулому, точка добігає до виходу за ~2 с
            // замість миттєвого зникнення; у «Потоці зміни» (replay) час подій точний і повзунок вільний.
            const T0 = p.out_ms != null ? (p.out_ms - live.start_ms) / 1000 : null;
            if (T0 == null) {
                dot.outS = null;
            } else if (replay || force) {
                dot.outS = T0;
            } else if (dot.outS == null) {
                dot.outS = T0 < e - 0.5 ? e + 2 : T0;
            }
            const state = personAt(p, pts, e, live, dot.outS);
            if (dot.cur == null) {
                dot.cur = state.s;
            }
            // згладжування: точка наздоганяє ціль зі швидкістю RUN_MPS (різка зміна часу/даних не телепортує)
            const step = force ? Infinity : RUN_MPS * dt;
            dot.cur += Math.max(-step, Math.min(step, state.s - dot.cur));
            const reached = !state.inside && dot.cur >= state.len - 0.3;
            if (reached) {
                dot.arrivedAt ??= performance.now();
            } else {
                dot.arrivedAt = null;
            }
            const gone = reached ? (performance.now() - dot.arrivedAt) / 1000 : 0;
            const at = pointAt(pts, dot.cur);
            dot.mesh.position.copy(b2t(T, at[0], at[1], 0.9));
            const visible = state.inside || !reached || gone < 1.4;
            dot.mesh.visible = visible;
            const fade = reached ? Math.max(0, 1 - gone / 1.4) : 1;
            const scale = state.stuck && state.inside ? 1.5 + 0.35 * Math.sin(performance.now() / 160) : 1;
            dot.mesh.scale.setScalar(Math.max(0.01, fade * scale));
            dot.mesh.material.color.setHex(state.stuck && state.inside ? COLORS.stuck : p.wrong ? COLORS.wrong : COLORS.person);
            if (state.stuck && state.inside) {
                if (!dot.label) {
                    dot.label = textSprite(T, "", hex(COLORS.stuck), 0.9);
                    st.group.add(dot.label);
                }
                setSpriteText(dot.label, "№" + p.n + " · " + (p.zone || "—") + " · застряг", hex(COLORS.stuck));
                dot.label.position.set(dot.mesh.position.x, 3.4, dot.mesh.position.z);
                dot.label.visible = true;
            } else if (dot.label) {
                dot.label.visible = false;
            }
        }
        for (const [n, dot] of [...st.dots]) {
            if (!seen.has(n)) {
                st.group.remove(dot.mesh);
                dot.mesh.geometry.dispose();
                dot.mesh.material.dispose();
                if (dot.label) {
                    st.group.remove(dot.label);
                }
                st.dots.delete(n);
            }
        }
    },

    animateCounters(st, counts) {
        for (const [zone, sprite] of st.counters) {
            const row = counts.byZone[zone] || { inside: 0, total: 0 };
            const col = row.inside ? hex(COLORS.stuck) : hex(COLORS.exit);
            setSpriteText(sprite, zone + " · " + (row.inside ? row.inside : "0 ✓"), col);
        }
    },

    // ---- плашка -----------------------------------------------------------------------------------
    plateHtml(st, e, counts, live, D) {
        const real = live.mode === "alarm";
        const access = D.access;
        let inside = counts.inside;
        let zones = counts.byZone;
        if (real && access?.on_site) {
            inside = access.on_site.total ?? access.on_site.employees ?? 0; // справжня тривога: лічильники СКУД «наживо»
            zones = Object.fromEntries(Object.entries(access.zones || {}).map(([z, n]) => [z, { inside: n, total: n }]));
        }
        const limit = live.limit_s || 300;
        const span = spanS(live);
        const done = span != null;
        const head = (real ? "Пожежна тривога" : "Навчальна тривога") + (live.name ? " " + esc(live.name) : "");
        let h = "<div class=\"o_td_ev_head\"><span class=\"o_td_ev_badge\">" + (done ? "завершено" : "ТРИВОГА") + "</span><b>" + head + "</b>";
        h += "<span class=\"o_td_ev_zone\">зона «" + esc(live.zone) + "»</span></div>";
        h += "<div class=\"o_td_ev_main\">у будівлі <b class=\"o_td_ev_n\">" + inside + "</b> " + plural(inside, "людина", "людини", "людей");
        h += " · <b class=\"o_td_ev_t\">" + mmss(e) + "</b> від тривоги</div>";
        if (!real) {
            const pct = counts.total ? Math.round((counts.out / counts.total) * 100) : 100;
            const over = e > limit;
            h += "<div class=\"o_td_ev_bar\"><i style=\"width:" + pct + "%\"></i></div>";
            h += "<div class=\"o_td_ev_sub\">вийшли " + counts.out + " з " + counts.total + " · норматив " + mmss(limit);
            h += over ? " <span class=\"o_td_ev_bad\">перевищено</span>" : "";
            h += done ? " · час евакуації " + mmss(span) : "";
            h += "</div>";
        }
        const chips = Object.entries(zones)
            .filter(([z]) => z !== "—")
            .sort((a, b) => b[1].inside - a[1].inside || a[0].localeCompare(b[0]))
            .slice(0, 10);
        if (chips.length) {
            h += "<div class=\"o_td_ev_zones\">";
            for (const [z, row] of chips) {
                h += "<span class=\"o_td_ev_chip " + (row.inside ? "o_td_ev_chip_on" : "o_td_ev_chip_ok") + "\">" + esc(z) + " " + (row.inside || "0 ✓") + "</span>";
            }
            h += "</div>";
        }
        if (counts.stuck.length) {
            h += "<div class=\"o_td_ev_stuck\">Застряг: " + counts.stuck.map((s) => "№" + s.n + " · " + esc(s.zone || "—")).join(", ") + "</div>";
        }
        if (counts.wrong.length) {
            const shown = counts.wrong.slice(0, 4).map((w) => "№" + w.n + " " + esc(w.from || "—") + " → " + esc(w.to || "—")).join(", ");
            h += "<div class=\"o_td_ev_wrong\">Не своїм виходом: " + counts.wrong.length + " (" + shown + (counts.wrong.length > 4 ? " …" : "") + ")</div>";
        }
        const vents = blockedUnits(D);
        const open = ventsOpen(D);
        if (vents.length || open) {
            h += "<div class=\"o_td_ev_sys\">" + (vents.length ? "Вентиляція заблокована: <b>" + vents.length + "</b>" : "") + (vents.length && open ? " · " : "") + (open ? "люки димовидалення відкриті" : "") + "</div>";
        }
        return h;
    },

    paintPlate(api, st, e, counts, live, D) {
        if (!st.plate) {
            return;
        }
        const html = this.plateHtml(st, e, counts, live, D);
        if (html !== st.plateHtml) {
            st.plateHtml = html;
            st.plate.innerHTML = html;
        }
    },
};

registerViewerExtension(evacExtension);
