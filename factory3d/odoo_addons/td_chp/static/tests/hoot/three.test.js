/** @odoo-module */
// AC-21: three.js — власна копія r147, вантажиться `loadJS` лише при відкритті дії; без WebGL — `#cv-fallback`,
// решта пульта працює. «web.assets_backend без static/lib/three» перевіряє `tests/test_hoot.py` (бандл на сервері).
import { describe, expect, test } from "@odoo/hoot";
import { queryAll, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { assets } from "@web/core/assets";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { loadThree, THREE_VERSION } from "@td_chp/pult/scene3d";
import { mockChp, mountPult } from "./helpers";

describe.current.tags("desktop");
defineMailModels();

test("loadThree: loadJS three.min.js і OrbitControls.js з /td_chp/static/lib/three/, REVISION == 147", async () => {
    const urls = [];
    patchWithCleanup(assets, {
        loadJS(url) {
            urls.push(url);
            return super.loadJS(url);
        },
    });
    const had = Boolean(window.THREE);
    const THREE = await loadThree();
    expect(String(THREE.REVISION)).toBe("147");
    expect(THREE_VERSION).toBe("147");
    expect(typeof THREE.OrbitControls).toBe("function");
    if (!had) {
        expect(urls.length).toBe(2);
        expect(urls[0]).toMatch(/^\/td_chp\/static\/lib\/three\/three\.min\.js\?v=/);
        expect(urls[1]).toMatch(/^\/td_chp\/static\/lib\/three\/OrbitControls\.js\?v=/);
    }
});

test("без WebGL: #cv-fallback замість 3D, решта пульта працює", async () => {
    mockChp({ webgl: false });
    await mountPult();
    expect(queryOne("#cv-fallback").hidden).toBe(false);
    expect(queryText("#cv-fallback b")).toBe("3D недоступне");
    expect(queryText("#cv-fb-msg")).toMatch(/WebGL недоступний/);
    expect(queryOne("#cv").hidden).toBe(true);
    // решта працює: вузли зі списку, KPI, команди
    expect(queryAll("#nodes button").length).toBe(37);
    expect(queryText("[data-b=pel]")).toBe("620");
    expect(queryText("#pl-name")).toBe("РОБОТА");
});

test("відкриття дії не вантажить three.js до виклику: до монтування нових <script> немає", async () => {
    const before = queryAll("script[src*='three']").length;
    mockChp({ webgl: false });
    await mountPult();
    // без WebGL three.js навіть не вантажиться
    expect(queryAll("script[src*='three']").length).toBe(before);
});
