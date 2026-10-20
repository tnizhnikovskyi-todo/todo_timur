/** @odoo-module */
import { whenReady } from "@odoo/owl";
import { F3dViewer } from "@td_viewer3d/viewer/core";
import { DataClient } from "@td_viewer3d/viewer/data_client";
import { F3dWall } from "@td_viewer3d/viewer/wall";

/** FR-33: раз на добу о 04:00 перезавантажити сторінку кіоска (витоки пам'яті довгих сесій). */
export function reloadAt0400(now = new Date(), reload = () => window.location.reload()) {
    if (now.getHours() === 4 && now.getMinutes() === 0) {
        try {
            const key = `f3d.kiosk.reloaded.${now.toDateString()}`;
            if (window.sessionStorage.getItem(key)) {
                return false;
            }
            window.sessionStorage.setItem(key, "1");
        } catch {
            /* без sessionStorage — лише хвилинне вікно */
        }
        reload();
        return true;
    }
    return false;
}

/** Сторінка кіоска (SPEC §8.6): без шини (A-03), опитування /delta кожні `refresh` с, ядро в lite-режимі. */
export async function startKiosk(el) {
    const token = el.dataset.token;
    let params = {};
    try {
        params = JSON.parse(el.dataset.params || "{}");
    } catch {
        /* порожні параметри */
    }
    const client = new DataClient({
        base: "/f3d/kiosk/" + token,
        kiosk: true,
        token,
        refreshS: Number(params.refresh) || 15,
    });
    if (params.wall) {
        document.documentElement.dataset.theme = params.wall.theme || "dark"; // телевізор: темна тема до створення ядра
    }
    const viewer = new F3dViewer(el, { client, lite: params.lite ?? "auto", kiosk: true, params });
    await viewer.mount();
    await viewer.load();
    await viewer.applyParams(params);
    if (params.wall) {
        // R-27: режим «стіна» (`?wall=1`): плейлист слайдів поверх кіоска; налаштування (слайди, тривалість) — з сервера
        const wall = new F3dWall(viewer, el, params.wall).start();
        const query = new URLSearchParams(window.location.search);
        if (query.has("f3d_test") || query.has("debug")) {
            window.odoo = window.odoo || {};
            window.odoo.f3dWall = wall;
        }
    }
    window.addEventListener("online", () => client.setOnline(true));
    window.addEventListener("offline", () => client.setOnline(false));
    if (navigator.onLine === false) {
        client.setOnline(false);
    }
    setInterval(() => reloadAt0400(), 60000);
    return viewer;
}

whenReady(() => {
    const el = document.getElementById("f3d-kiosk");
    if (el) {
        startKiosk(el);
    }
});
