/** @odoo-module */
// Спільні хелпери HOOT-тестів редактора (файл без тестів): фікстури W1, мок RPC.

export const FIXTURES = "/td_constructor/static/tests/fixtures";

// Hoot підміняє window.fetch (дозволені лише blob:/data:), тож статику беремо рідним fetch із чистого iframe.
let frame = null;
async function nativeText(url) {
    if (!frame || !frame.isConnected) {
        frame = document.createElement("iframe");
        frame.style.display = "none";
        document.documentElement.appendChild(frame);
    }
    const r = await frame.contentWindow.fetch(new URL(String(url), window.location.href).href);
    return await r.text();
}
const cache = {};

/** Золота фікстура W1 (cells_golden.json / checks_golden.json). */
export async function golden(name) {
    if (!cache[name]) {
        cache[name] = JSON.parse(await nativeText(`${FIXTURES}/${name}.json`));
    }
    return structuredClone(cache[name]);
}

export const near = (a, b, tol) => Math.abs(a - b) <= tol;
