/** @odoo-module */
// Завантаження моделі на сервер (API-09, SPEC §8.3): multipart POST `/f3d/constructor/model/upload`, прогрес через XHR.
import { ModelImportError } from "./normalize";

export const UPLOAD_URL = "/f3d/constructor/model/upload";

function csrfToken() {
    return globalThis.odoo?.csrf_token || "";
}

/**
 * @param {number} variantId
 * @param {{original: File|Blob, glb?: Blob|null, meta: object}} data
 * @param {{onProgress?: (fraction: number) => void, XHR?: typeof XMLHttpRequest, url?: string, csrf?: string}} [opts]
 * @returns {Promise<{status: string, meta: object, glb_url: string|null, original_url: string|null, message: string}>}
 */
export function uploadModel(variantId, { original, glb, meta }, opts = {}) {
    const fd = new FormData();
    fd.append("variant_id", String(variantId));
    fd.append("csrf_token", opts.csrf ?? csrfToken());
    fd.append("original", original, original.name || "model.bin");
    if (glb) {
        fd.append("glb", glb, "model.glb");
    }
    fd.append("meta", JSON.stringify(meta || {}));
    return new Promise((resolve, reject) => {
        const xhr = new (opts.XHR || XMLHttpRequest)();
        xhr.open("POST", opts.url || UPLOAD_URL);
        xhr.responseType = "text";
        if (xhr.upload && opts.onProgress) {
            xhr.upload.onprogress = (e) => e.lengthComputable && opts.onProgress(e.loaded / e.total);
        }
        xhr.onerror = () => reject(new ModelImportError("upload_failed", "Помилка мережі під час завантаження моделі."));
        xhr.onload = () => {
            let body = null;
            try {
                body = JSON.parse(xhr.responseText);
            } catch {
                body = null;
            }
            const res = body && typeof body === "object" && "result" in body && !("status" in body) ? body.result : body;
            const err = res?.ok === false || res?.error || xhr.status >= 400;
            if (err) {
                const code = xhr.status === 413 ? "too_large" : res?.code || (res?.error && res.error.code) || "upload_failed";
                const msg = res?.message || res?.error?.message || (xhr.status === 413 ? "Файл завеликий." : `Помилка завантаження (${xhr.status}).`);
                reject(new ModelImportError(code, msg));
                return;
            }
            resolve(res || {});
        };
        xhr.send(fd);
    });
}
